#!/usr/bin/env python3
"""
LA TANDA VIVA — las charlas que ya rompieron, corridas ANTES del deploy.

POR QUE EXISTE, y es una decision de METODO mas que de codigo. Hasta el
11-sep-2026 el unico instrumento que medía charlas reales corría DESPUES: Martin
probaba por WhatsApp, algo salia mal, se leian los logs por el issue 31 y se
arreglaba. Cada arreglo se verificaba con UNA pregunta en la sonda, y la
siguiente prueba real rompia con otra redaccion de la misma pregunta. Eso no es
mala suerte: es que la verificacion era mas angosta que el defecto.

Esta tanda invierte el orden. Las charlas que rompieron quedan grabadas con las
palabras EXACTAS del cliente, y se corren contra el modelo real antes de
pushear. Si el numero no sube, el arreglo no sirvio.

QUE CORRE. El camino VIVO entero, por `clon_produccion`: el webhook de
WhatsApp, el antijailbreak, el turno, las guardias, el cierre y la particion en
partes. Lo unico doblado es Firestore, en RAM y con el catalogo real, y el
envio a Meta. El modelo es el de verdad, con la clave GRATIS.

    python3 banco_pruebas/tanda_viva.py
    python3 banco_pruebas/tanda_viva.py --charla parlante
    python3 banco_pruebas/tanda_viva.py --json salida.json

CUANTO CUESTA. Once turnos, dos llamadas al modelo cada uno. Entra de sobra en
la cuota diaria gratis; la vara de la llamada uno gasta 36.

── LAS DOS CLASES DE JUICIO, y la diferencia importa ─────────────────────────

INVARIANTES DE ESTADO. Salen del turno, no de leer el castellano, y valen para
TODOS los turnos sin que nadie los escriba caso por caso. Son los tres que los
logs de produccion ya venian gritando el 11-sep:

  - `turno_incompleto` con `abiertos` -> el turno se fue con un punto sin
    contestar. Medido: turno `1fe1d20c`, `abiertos=['pide_precio:1']`.
  - `salteados` -> el turno TENIA con que contestar y no lo dijo. Medido con la
    sonda: `salteados=['pide_precio:1']`.
  - `tema_no_resuelto` con ambiguos -> un nombre de tema empato con varias
    claves de la casa y se sirvieron TODAS. Medido: turno `630341c4`,
    'consulta de precio del producto mas caro' abrio `asesoramiento`,
    `compat_consola` y `consulta_algo_mas`, y de ahi salieron los tres parrafos
    sobre consolas que el cliente nunca pregunto. Es la D7 del mapa.
  - el fallback de produccion -> el turno exploto.

LO QUE ESPERA CADA TURNO. Lo escribo yo, turno por turno, y por eso NO es una
heuristica del bot: es la vara. `plata: True` quiere decir que el cliente pidio
un precio y tiene que leer un numero de plata en ESE mensaje, sin repreguntar.
Esa es, textual, la queja de Martin del 11-sep: "al ultimo tengo que
repreguntar el precio para que me lo diga".

── DE DONDE SALEN LAS CHARLAS ────────────────────────────────────────────────

De los logs de produccion, con las palabras exactas del cliente, leidas por el
issue 31. No son casos inventados ni redactados de nuevo: si se los retoca para
que pasen, la tanda deja de medir lo que pasa en el telefono.
"""

import argparse
import asyncio
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)


# ── LAS CHARLAS, tal cual las escribio el cliente ────────────────────────────
#
# `plata` es la unica expectativa por turno y quiere decir: en ESTE mensaje
# tiene que haber un numero de plata. Cuando es False, el turno no pidio precio
# y un numero de plata no se exige ni se prohibe.

CHARLAS = {
    "parlante": {
        "origen": "WhatsApp 5493547504287, 11-sep-2026 15:32 UTC",
        "turnos": [
            ("Dame precio de un parlante ten en cuenta que estamos en crisis", True),
            ("Cual es el mas caro para saber", True),
            ("Precio", True),
        ],
    },
    "teclado_notebook": {
        "origen": "WhatsApp 5493547504287, 11-sep-2026 14:58 UTC",
        "turnos": [
            ("Dame precio del aparato con teclas mas barato que tengas", True),
            ("Ok por donde lo busco", False),
            ("No mejor dame precio del articulo mas caro que tengas", True),
            ("Notebook", True),
            ("Cual es la mas cara", True),
        ],
    },
    "extremos": {
        "origen": "WhatsApp 5493547504287, 11-sep-2026 15:30 UTC",
        "turnos": [
            ("Dame precio del aparato con teclas mas barato que tengas", True),
            ("Y el mas caro que tengas", True),
            ("Y el mas barato, dame presupuesto del mas barato", True),
        ],
    },
}

# Un numero de plata en el texto que recibe el cliente.
_RE_PLATA = re.compile(r"\$\s?\d[\d.]*")


def _fallas_de_estado(eventos: list, mensaje: str) -> list:
    """Los invariantes que salen del ESTADO del turno. Ninguno lee castellano."""
    fallas = []
    for e in eventos:
        nombre = e.get("event")
        if nombre == "turno_incompleto" and (e.get("abiertos") or []):
            fallas.append(f"punto abierto: {e['abiertos']}")
        if nombre == "turno_ok" and (e.get("salteados") or 0):
            fallas.append("el turno tenia con que contestar y no lo dijo")
        if nombre == "tema_no_resuelto" and (e.get("ambiguos") or []):
            nombres = [a[0] if isinstance(a, (list, tuple)) else a
                       for a in e["ambiguos"]]
            fallas.append(f"tema ambiguo servido entero: {nombres}")
    from banco_pruebas import clon_produccion
    if clon_produccion.es_fallback(mensaje):
        fallas.append("el turno EXPLOTO y salio el fallback de produccion")
    return fallas


async def _correr(nombres: list) -> dict:
    from banco_pruebas import clon_produccion, observador
    clon_produccion.preparar_entorno()
    clon_produccion.instalar()
    observador.instalar(consola=False)

    salida = {"charlas": [], "turnos": 0, "ok": 0, "eventos": []}
    for nombre in nombres:
        charla = CHARLAS[nombre]
        user = f"tanda_{nombre}"
        clon_produccion.reiniciar_cliente(user)
        filas = []
        for texto, quiere_plata in charla["turnos"]:
            with observador.turno() as t:
                partes = await clon_produccion.turno(user, texto)
            mensaje = "\n\n".join(partes)
            salida["eventos"] += list(t.eventos)
            fallas = _fallas_de_estado(t.eventos, mensaje)
            if quiere_plata and not _RE_PLATA.search(mensaje):
                fallas.append("PIDIO PRECIO Y NO HAY UN NUMERO DE PLATA")
            largo = sum(len(p) for p in partes)
            filas.append({"cliente": texto, "bot": mensaje, "fallas": fallas,
                          "largo": largo, "partes": len(partes)})
            salida["turnos"] += 1
            if not fallas:
                salida["ok"] += 1
        salida["charlas"].append({"nombre": nombre, "origen": charla["origen"],
                                  "turnos": filas})
    return salida


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--charla", action="append", choices=sorted(CHARLAS),
                    help="solo esta charla; se puede repetir")
    ap.add_argument("--json", dest="destino", default=None)
    ap.add_argument("--todo", action="store_true",
                    help="imprimir tambien los mensajes que salieron bien")
    args = ap.parse_args()

    nombres = args.charla or sorted(CHARLAS)
    datos = asyncio.run(_correr(nombres))

    print()
    print("TANDA VIVA — las charlas que ya rompieron, contra el modelo real")
    print()
    for ch in datos["charlas"]:
        malos = [f for f in ch["turnos"] if f["fallas"]]
        print(f"-- charla {ch['nombre']}  ({ch['origen']})")
        print(f"   {len(ch['turnos']) - len(malos)} de {len(ch['turnos'])} turnos limpios")
        for i, f in enumerate(ch["turnos"], 1):
            if not f["fallas"] and not args.todo:
                continue
            marca = "MAL " if f["fallas"] else "ok  "
            print(f"   [{marca}] {i}. CLIENTE  {f['cliente']}")
            for x in f["fallas"]:
                print(f"            -> {x}")
            print(f"            largo {f['largo']}  partes {f['partes']}")
            if args.todo or f["fallas"]:
                for ln in (f["bot"] or "").splitlines():
                    print(f"            | {ln}")
        print()

    largos = [f["largo"] for ch in datos["charlas"] for f in ch["turnos"]]
    print(f"TURNOS LIMPIOS: {datos['ok']} de {datos['turnos']}")
    if largos:
        print(f"LARGO: maximo {max(largos)}, promedio {sum(largos) // len(largos)}")
    print()
    # EL MISMO NUMERO QUE EL DE PRODUCCION, Y LA MISMA FUNCION. Si la tanda y
    # el issue 31 contaran cada uno por su lado, dos numeros de la misma cosa
    # terminan discrepando y no se sabe cual creer.
    from banco_pruebas.produccion import numero_del_motor
    print("\n".join(numero_del_motor(datos.get("eventos") or [])))

    print("Un turno limpio es: sin punto abierto, sin punto salteado, sin tema")
    print("ambiguo servido entero, sin fallback, y con el precio adentro cuando")
    print("el cliente lo pidio.")
    print()

    if args.destino:
        with open(args.destino, "w", encoding="utf-8") as fh:
            json.dump(datos, fh, ensure_ascii=False, indent=2)
        print(f"capturado en {args.destino}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
