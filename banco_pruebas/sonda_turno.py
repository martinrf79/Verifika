#!/usr/bin/env python3
"""
SONDA DE TURNO — mira por dentro del sistema tal como esta, sin cambiarlo.

Que hace
    Corre UN turno real del bot -el mismo codigo que corre en produccion, la
    misma fuente de verdad, el mismo modelo- y va imprimiendo la entrada y la
    salida de cada etapa del turno. No inventa un camino nuevo: envuelve las
    ocho etapas que ya existen en app/core/turno.py y las deja pasar.

Que NO hace
    No modifica ni una linea del repo. No agrega flags. No cambia la
    arquitectura. No dice verde ni rojo: imprime datos. Si una etapa se rompe,
    se detiene ahi y muestra el error completo con el dato que la rompio.

Etapas que muestra, en el orden real del turno
    1  decisor        llamada UNO al modelo, que herramientas pide
    2  herramientas   ejecucion en paralelo contra la fuente de verdad
    3  resolver       resolucion de candidatos
    4  mesa           armado de la tabla de puntos
    5  redactor       llamada DOS al modelo, la mesa llena
    6  armar          texto final a partir de la mesa
    7  obligaciones   agregados que no salen de la mesa
    8  cierre         cierre y cobro

Donde vive y por que
    banco_pruebas/ NO deploya: esta en el paths-ignore de deploy.yml y en
    .gcloudignore, asi que este archivo no reconstruye la imagen de Cloud Run
    ni entra en ella. Se puede tocar sin riesgo para produccion.

Uso, desde la raiz del repo
    python3 banco_pruebas/sonda_turno.py "tu pregunta de prueba"
    python3 banco_pruebas/sonda_turno.py --user 5491100000000 "tu pregunta"
    python3 banco_pruebas/sonda_turno.py --json salida.json "tu pregunta"
    python3 banco_pruebas/sonda_turno.py --tope 4000 "tu pregunta"

Por defecto usa un user_id de sonda propio, sonda_<timestamp>, para no pisar
ninguna conversacion real de Firestore. Con --user reproduce sobre un usuario
concreto, y ahi si escribe en la conversacion de ese usuario.
"""

import argparse
import asyncio
import json
import os
import sys
import time
import traceback

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

TOPE = 2500          # caracteres por valor impreso; --tope lo cambia
REGISTRO: list = []  # todo lo que paso, para volcar a JSON


# ─────────────────────────────────────────────────────────── presentacion

def linea(c="-"):
    print(c * 72)


def cabecera(n, nombre, detalle=""):
    print()
    linea("=")
    print("ETAPA {}  {}{}".format(n, nombre, ("  " + detalle) if detalle else ""))
    linea("=")


def volcar(etiqueta, valor):
    txt = valor if isinstance(valor, str) else json.dumps(
        valor, ensure_ascii=False, indent=2, default=str)
    if len(txt) > TOPE:
        txt = txt[:TOPE] + "\n... [cortado, largo real {} caracteres]".format(len(txt))
    print(etiqueta + ":")
    for l in txt.splitlines():
        print("    " + l)


def resumir(valor):
    """Version corta para el JSON de salida, sin tope de impresion."""
    try:
        json.dumps(valor, ensure_ascii=False, default=str)
        return valor
    except Exception:
        return repr(valor)[:4000]


# ─────────────────────────────────────────────────────────── envoltorios

ORDEN = {
    "_pedir_herramientas": (1, "DECISOR, llamada uno al modelo"),
    "_ejecutar_en_paralelo": (2, "HERRAMIENTAS contra la fuente de verdad"),
    "resolver": (3, "RESOLVER candidatos"),
    "tabla": (4, "MESA, tabla de puntos"),
    "_redactar": (5, "REDACTOR, llamada dos al modelo"),
    "armar": (6, "ARMAR texto desde la mesa"),
    "_obligaciones": (7, "OBLIGACIONES fuera de la mesa"),
    "_cerrar": (8, "CIERRE y cobro"),
}


def _entrada(nombre, args, kwargs):
    n, titulo = ORDEN.get(nombre, (0, nombre))
    cabecera(n, titulo, "(" + nombre + ")")
    interesantes = []
    for a in args:
        if isinstance(a, (str, int, float, bool)) or a is None:
            interesantes.append(a)
        elif isinstance(a, (list, dict)):
            interesantes.append(a)
        else:
            interesantes.append("<" + type(a).__name__ + ">")
    volcar("entra", {"posicionales": interesantes,
                     "con_nombre": {k: resumir(v) for k, v in kwargs.items()}})


def _salida(nombre, valor, ms, error=None):
    if error is None:
        volcar("sale", resumir(valor))
        print("tiempo: {} ms".format(ms))
        REGISTRO.append({"etapa": nombre, "ms": ms, "sale": resumir(valor)})
    else:
        print()
        print("ROTO EN ESTA ETAPA")
        print("tipo: " + type(error).__name__)
        print("mensaje: " + str(error)[:1200])
        print()
        print("traza:")
        for l in traceback.format_exc().splitlines():
            print("    " + l)
        REGISTRO.append({"etapa": nombre, "ms": ms,
                         "error": type(error).__name__ + ": " + str(error)[:600]})


def envolver_sync(modulo, nombre):
    original = getattr(modulo, nombre)

    def envoltorio(*args, **kwargs):
        _entrada(nombre, args, kwargs)
        t = time.time()
        try:
            r = original(*args, **kwargs)
        except Exception as e:
            _salida(nombre, None, int((time.time() - t) * 1000), e)
            raise
        _salida(nombre, r, int((time.time() - t) * 1000))
        return r

    setattr(modulo, nombre, envoltorio)


def envolver_async(modulo, nombre):
    original = getattr(modulo, nombre)

    async def envoltorio(*args, **kwargs):
        _entrada(nombre, args, kwargs)
        t = time.time()
        try:
            r = await original(*args, **kwargs)
        except Exception as e:
            _salida(nombre, None, int((time.time() - t) * 1000), e)
            raise
        _salida(nombre, r, int((time.time() - t) * 1000))
        return r

    setattr(modulo, nombre, envoltorio)


# ─────────────────────────────────────────────────────────── etapa cero

def etapa_cero():
    cabecera(0, "ENTORNO, antes de tocar nada")
    print("raiz del repo: " + RAIZ)
    print("python: " + sys.version.split()[0])

    faltan = []
    try:
        from app.config import get_settings
        s = get_settings()
    except Exception as e:
        print("NO SE PUDO CARGAR app.config: " + repr(e))
        traceback.print_exc()
        sys.exit(1)

    clave = (getattr(s, "GEMINI_API_KEY", "") or
             os.environ.get("GEMINI_API_KEY", ""))
    print("clave de modelo presente: " + ("si, largo " + str(len(clave))
                                          if clave else "NO"))
    if not clave:
        faltan.append("GEMINI_API_KEY, sin clave el turno cae al fallback y "
                      "la sonda no mide nada")
    for campo in ("GEMINI_MODEL", "GEMINI_BASE_URL", "TIENDA_ID",
                  "DECISOR_MODEL", "DECISOR_BASE_URL", "HISTORY_LIMIT"):
        print("  {} = {}".format(campo, getattr(s, campo, "<no existe>")))

    try:
        from app.storage.firestore_client import get_conversation
        print("firestore_client importado")
    except Exception as e:
        print("NO SE PUDO IMPORTAR firestore_client: " + repr(e))
        faltan.append("acceso a Firestore")

    try:
        from app.core import herramientas as H
        esquemas = H.esquemas(getattr(s, "TIENDA_ID", ""))
        nombres = []
        for e in esquemas or []:
            try:
                nombres.append(e["function"]["name"])
            except Exception:
                nombres.append(str(e)[:40])
        print("herramientas que ve el modelo: {}".format(len(nombres)))
        print("  " + ", ".join(nombres))
    except Exception as e:
        print("NO SE PUDIERON LEER LOS ESQUEMAS DE HERRAMIENTAS: " + repr(e))
        faltan.append("esquemas de herramientas")

    if faltan:
        print()
        print("FALTANTES QUE VAN A ENSUCIAR LA MEDICION:")
        for f in faltan:
            print("  - " + f)
    return faltan


# ─────────────────────────────────────────────────────────── main

def main():
    global TOPE
    ap = argparse.ArgumentParser()
    ap.add_argument("pregunta")
    ap.add_argument("--user", default=None,
                    help="user_id real a reproducir; por defecto uno de sonda")
    ap.add_argument("--tienda", default=None)
    ap.add_argument("--canal", default="telegram")
    ap.add_argument("--tope", type=int, default=TOPE)
    ap.add_argument("--json", default=None,
                    help="archivo donde volcar todo lo capturado")
    args = ap.parse_args()
    TOPE = args.tope

    faltan = etapa_cero()

    from app.core import turno as T
    from app.core import tabla as TB
    from app.core.orchestrator import process_message

    envolver_async(T, "_pedir_herramientas")
    envolver_async(T, "_ejecutar_en_paralelo")
    envolver_sync(T, "resolver")
    envolver_sync(TB, "tabla")
    envolver_async(T, "_redactar")
    envolver_sync(TB, "armar")
    envolver_sync(T, "_obligaciones")
    envolver_async(T, "_cerrar")

    user = args.user or ("sonda_" + str(int(time.time())))
    cabecera(0, "TURNO", "user_id " + user + "  canal " + args.canal)
    print("pregunta: " + args.pregunta)
    if args.user is None:
        print("usuario de sonda: no pisa ninguna conversacion real")
    else:
        print("ATENCION: reproduce sobre el usuario real " + args.user +
              ", escribe en su conversacion")

    t0 = time.time()
    error = None
    try:
        respuesta = asyncio.run(process_message(
            user, args.pregunta, args.tienda, args.canal))
    except Exception as e:
        error = e
        respuesta = None

    print()
    linea("=")
    print("RESPUESTA FINAL AL CLIENTE")
    linea("=")
    if error is not None:
        print("EL TURNO SE ROMPIO ANTES DE RESPONDER")
        print("tipo: " + type(error).__name__)
        print("mensaje: " + str(error)[:1200])
        print()
        traceback.print_exc()
    else:
        print(respuesta)
    print()
    print("tiempo total del turno: {} ms".format(int((time.time() - t0) * 1000)))

    try:
        from app.core.llm_reintento import sin_cupo
        c = sin_cupo()
        if c.get("veces"):
            print()
            print("AVISO: la llamada al modelo fallo {} vez o veces sin "
                  "recuperarse. Esta corrida NO mide el codigo.".format(c["veces"]))
            print("ultimo error: " + str(c.get("ultimo"))[:300])
    except Exception:
        pass

    if faltan:
        print()
        print("RECORDATORIO: la etapa cero encontro faltantes, releer arriba.")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"pregunta": args.pregunta, "user_id": user,
                       "respuesta": respuesta,
                       "error": (type(error).__name__ + ": " + str(error))
                       if error else None,
                       "etapas": REGISTRO},
                      f, ensure_ascii=False, indent=2, default=str)
        print()
        print("capturado en " + args.json)


if __name__ == "__main__":
    main()
