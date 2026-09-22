#!/usr/bin/env python3
"""EL TALLER — se le pregunta al modelo, pero solo lo que se puede verificar.

QUE HACE. Corre los mensajes de la vara por el camino vivo, mira QUE CASILLA
QUEDO VACIA, y para cada una le hace al modelo UNA pregunta de diagnostico con
el mismo tablero delante. Despues **verifica la respuesta contra el repo** y
agrupa las causas por clase.

LA REGLA QUE ORDENA TODO, y es la unica que hace que esto no sea humo:

    NO se le pregunta al modelo que PREFIERE. Se le pregunta algo cuya
    respuesta el codigo pueda comprobar.

    "¿que tablero te resulta mas comodo?"   opinion. No predice nada.
    "¿en que campo escribirias esto?"       VERIFICABLE: o nombra un campo
                                            que existe en el enum, o no.
    "¿de donde sacaste ese numero?"         VERIFICABLE: o las palabras que
                                            cita estan en el mensaje, o no.

Un modelo contesta con una explicacion plausible de por que hizo algo, no con
la causa. Si la respuesta no se puede comprobar, no es un dato: es prosa bien
escrita, y este repo ya tiene medido que los cambios sacados de prosa dan 1 de
3 contra 6 de 6 de los estructurales.

LO QUE SEPARA, Y ES EL PRODUCTO. Hoy dos fracasos distintos se ven iguales:

    HUECO DE TABLERO   el modelo PODIA escribirlo y no lo hizo, o lo escribio
                       en el lugar equivocado. Se arregla con la forma.
    HUECO DE ESQUEMA   no habia donde escribirlo. Se arregla construyendo la
                       casilla, que es lo que la FICHA 57 tiene que decidir.

La bifurcacion sale de la respuesta verificada, no de nuestra lectura.

LO QUE ESTE SCRIPT NO HACE, a proposito:
  - No edita el tablero ni el prompt. Deja una lista.
  - No puntua ni mueve el piso: eso es `tanda_interpretacion` con
    `leer_interpretacion`, y dos definiciones de correcto se separan el dia
    que alguien toca una.
  - No corre en la bateria: llama al modelo y tarda minutos.

Uso, desde la raiz:

    python3 banco_pruebas/taller.py                    # los que fallan hoy
    python3 banco_pruebas/taller.py --solo M7,M11,M17
    python3 banco_pruebas/taller.py --repeticiones 3   # una respuesta no es
                                                       # una causa
"""
import argparse
import asyncio
import json
import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from banco_pruebas import clon_produccion, observador  # noqa: E402
from banco_pruebas import sim_firestore  # noqa: E402
from banco_pruebas.leer_interpretacion import (  # noqa: E402
    CASILLA, DEUDA, _juntar, _norm, cargar_vara)
from banco_pruebas.tanda_interpretacion import TIENDA, _un_turno  # noqa: E402


# ── LAS PREGUNTAS, UNA POR TIPO DE CASILLA ──────────────────────────────────
#
# Cada una viene con su VERIFICADOR. Sin verificador no hay pregunta: eso es lo
# que impide que esto se llene de preguntas lindas que no deciden nada.
#
# `pide` recibe la casilla de la vara y el mensaje, y devuelve el texto de la
# pregunta. `comprueba` recibe la respuesta cruda del modelo y el contexto, y
# devuelve (veredicto, detalle). Los tres veredictos:
#
#     HUECO_TABLERO  contesto algo que existe: podia haberlo escrito
#     HUECO_ESQUEMA  dijo que no hay donde, y tiene razon
#     CONFUSO        no contesto en el formato pedido. No se cuenta

TABLERO, ESQUEMA, CONFUSO = "HUECO_TABLERO", "HUECO_ESQUEMA", "CONFUSO"

NADA = "NINGUNO"


def _p_campo(casilla, mensaje, enums):
    """Para una casilla de condicion u orden: ¿en que campo lo escribirias?

    LA LISTA VA ADENTRO DE LA PREGUNTA, y la primera corrida enseño por que.
    Sin ella el modelo contesto "Precio", "Requerimientos tecnicos" y
    "Observaciones adicionales" —nombres plausibles que NO existen— y el
    verificador los conto como CONFUSO. Eso no medía al modelo: medía una
    pregunta mal hecha.

    Y EL CONTRASTE ENTRE LAS DOS FORMAS ES EL DATO, no un descarte. Con la
    lista delante se ve si el problema es que no sabe DONDE va, o que no
    estaba mirando la lista cuando lleno el tablero. Se corre con `--sin-lista`
    para tener las dos mitades.
    """
    que = casilla.get("valor") or casilla.get("n")
    cabeza = (f"El cliente dijo: \"{mensaje}\"\n\n"
              f"No anotaste nada para esta parte: {que}\n\n")
    if enums.get("sin_lista"):
        return (cabeza + f"Contesta UNA SOLA LINEA con el NOMBRE EXACTO de un "
                f"campo del catalogo donde eso se pueda escribir, o la palabra "
                f"{NADA} si ningun campo sirve. Nada mas que eso.")
    return (cabeza + "Estos son TODOS los campos del catalogo:\n"
            + ", ".join(enums["campos"]) + "\n\n"
            + f"Contesta UNA SOLA LINEA: copia de esa lista el campo donde eso "
              f"se puede escribir, o la palabra {NADA} si ninguno sirve. Nada "
              f"mas que eso.")


def _v_campo(respuesta, casilla, enums):
    """Se comprueba contra el enum de campos: existe o no existe."""
    r = _norm(respuesta).strip().split("\n")[0].strip()
    if not r:
        return CONFUSO, "no contesto"
    if NADA.lower() in r:
        return ESQUEMA, "dice que ningun campo sirve"
    for campo in enums["campos"]:
        if _norm(campo) in r:
            return TABLERO, f"nombra `{campo}`, que existe"
    return CONFUSO, f"nombro algo que no es un campo: {respuesta[:60]}"


def _p_cita(casilla, mensaje, enums):
    """Para un numero inventado: ¿de donde lo sacaste?"""
    return (f"El cliente dijo: \"{mensaje}\"\n\n"
            f"Escribiste una condicion de precio con un numero. Copia LAS "
            f"PALABRAS EXACTAS del mensaje del cliente donde dice ese numero. "
            f"Si el cliente no dijo ningun numero, contesta solo {NADA}.")


def _v_cita(respuesta, casilla, enums):
    """Se comprueba contra el MENSAJE: la cita esta o no esta."""
    r = respuesta.strip()
    if not r:
        return CONFUSO, "no contesto"
    if NADA.lower() in _norm(r):
        return TABLERO, ("admite que el cliente no dijo el numero: el techo "
                         "sale de el, no del mensaje")
    men = _norm(enums["mensaje"])
    trozo = _norm(r).strip(' ."\'')
    if trozo and trozo in men:
        return ESQUEMA, f"cita algo que SI esta en el mensaje: {r[:60]}"
    return TABLERO, f"cita algo que NO esta en el mensaje: {r[:60]}"


def _p_tema(casilla, mensaje, enums):
    """Para un tema declarado de mas: ¿cual pregunto el cliente?"""
    return (f"El cliente dijo: \"{mensaje}\"\n\n"
            f"Pediste temas de la casa. Contesta UNA SOLA LINEA: copia LAS "
            f"PALABRAS del mensaje donde el cliente pregunta por una politica "
            f"de la tienda —garantia, cuotas, envios, cambios, facturacion—. "
            f"Si no pregunto ninguna, contesta solo {NADA}.")


def _v_tema(respuesta, casilla, enums):
    r = respuesta.strip()
    if not r:
        return CONFUSO, "no contesto"
    if NADA.lower() in _norm(r):
        return TABLERO, ("admite que el cliente no pregunto ninguna: el tema "
                         "lo agrego el")
    men = _norm(enums["mensaje"])
    trozo = _norm(r).strip(' ."\'')
    if trozo and trozo in men:
        return ESQUEMA, f"cita algo del mensaje: {r[:60]}"
    return TABLERO, f"cita algo que NO esta en el mensaje: {r[:60]}"


# QUE PREGUNTA LE TOCA A CADA TIPO DE CASILLA. Una casilla sin pregunta se
# lista y no se interroga: inventarle una seria empezar a preguntar por
# preguntar.
PREGUNTAS = {
    "condicion": (_p_campo, _v_campo),
    "orden": (_p_campo, _v_campo),
    "barato": (_p_campo, _v_campo),
    "consulta": (_p_campo, _v_campo),
    "sin_umbral_inventado": (_p_cita, _v_cita),
    "temas_limpios": (_p_tema, _v_tema),
    "sin_mecanismo": (_p_campo, _v_campo),
}


async def _preguntar_al_modelo(texto: str) -> str:
    """UNA llamada, sin tablero y sin moldes: es una pregunta de diagnostico,
    no un turno. Que no lleve herramientas es a proposito —se le pide que
    conteste, no que busque— y ademas deja la respuesta en texto plano, que es
    lo que el verificador sabe leer."""
    from app.core.llm_reintento import _cliente, _modelo
    cli = _cliente()
    if cli is None:
        return ""
    r = cli.chat.completions.create(
        model=_modelo(), temperature=0.0, max_tokens=120,
        messages=[{"role": "user", "content": texto}])
    return (r.choices[0].message.content or "") if r.choices else ""


def _vacias(turno: dict, mensaje_vara: dict) -> list:
    """Las casillas que quedaron SIN LLENAR en este turno. Usa la MISMA
    definicion de lleno que el puntaje —`leer_interpretacion.CASILLA`— porque
    dos definiciones de correcto se separan el dia que alguien toca una."""
    v1 = _juntar({}, turno["vueltas"][0] if turno["vueltas"] else {})
    v2 = v1
    for p in turno["vueltas"][1:2]:
        v2 = _juntar(v2, p)
    fuera = []
    for c in mensaje_vara["casillas"]:
        if c["tipo"] == DEUDA:
            fuera.append(c)
            continue
        f = CASILLA.get(c["tipo"])
        if f and not f(c, v1) and not f(c, v2):
            fuera.append(c)
    return fuera


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", default="M7,M11,M17",
                    help="ids de la vara. Default: los que fallan hoy")
    ap.add_argument("--repeticiones", type=int, default=2)
    ap.add_argument("--pausa", type=float, default=6.0)
    ap.add_argument("--json", default="")
    ap.add_argument("--sin-lista", action="store_true",
                    help="no le muestra el enum de campos: la otra mitad del "
                         "contraste")
    args = ap.parse_args()

    # EL MISMO MONTAJE QUE LA TANDA, y por el mismo motivo: la clave la elige
    # `clon_produccion` y no hay una segunda forma. Escribir aca un selector
    # propio seria la cosa suelta que la regla 2 prohibe.
    clon_produccion.preparar_entorno()
    sim_firestore.install()
    observador.instalar(consola=False)
    from app.core.contexto_turno import set_current_tienda
    from app.core.filtros_catalogo import campos_filtrables
    set_current_tienda(TIENDA)

    vara = cargar_vara()
    quiero = [s.strip().upper() for s in args.solo.split(",") if s.strip()]
    mensajes = [m for m in vara["mensajes"] if m["id"] in quiero]
    campos = sorted(campos_filtrables(TIENDA))

    print("=" * 62)
    print("EL TALLER — se pregunta, y despues se comprueba contra el repo")
    print("=" * 62)
    print(f"mensajes: {', '.join(m['id'] for m in mensajes)}   "
          f"corridas: {args.repeticiones}   "
          f"campos a la vista: {'NO' if args.sin_lista else 'si'}")

    hallazgos = []
    for corrida in range(1, args.repeticiones + 1):
        for m in mensajes:
            trace = f"taller-{m['id']}-{corrida}"
            turno = await _un_turno(m["texto"], trace)
            if turno["caido"]:
                print(f"\n{m['id']} corrida {corrida}: TURNO CAIDO, se saltea")
                continue
            for c in _vacias(turno, m):
                par = PREGUNTAS.get(c["tipo"])
                if not par:
                    print(f"\n{m['id']}  [{c.get('clase','?')}] {c['n']}"
                          f"\n   sin pregunta para el tipo `{c['tipo']}`")
                    continue
                pide, comprueba = par
                enums = {"campos": campos, "mensaje": m["texto"],
                         "sin_lista": args.sin_lista}
                texto = pide(c, m["texto"], enums)
                await asyncio.sleep(args.pausa)
                try:
                    cruda = await _preguntar_al_modelo(texto)
                except Exception as e:  # noqa: BLE001
                    print(f"   ERROR {type(e).__name__}: {str(e)[:100]}")
                    continue
                veredicto, detalle = comprueba(cruda, c, enums)
                hallazgos.append(
                    {"id": m["id"], "clase": c.get("clase", "?"),
                     "casilla": c["n"], "tipo": c["tipo"], "corrida": corrida,
                     "respuesta": cruda.strip()[:160],
                     "veredicto": veredicto, "detalle": detalle})
                print(f"\n{m['id']}  [{c.get('clase','?')}] {c['n']}")
                print(f"   MODELO: {cruda.strip()[:110]}")
                print(f"   {veredicto}: {detalle}")

    print("\n" + "=" * 62)
    print("LAS CAUSAS, AGRUPADAS Y VERIFICADAS")
    print("=" * 62)
    for v, titulo in ((TABLERO, "HUECO DE TABLERO — podia escribirlo y no lo "
                                "hizo. Se arregla con la FORMA"),
                      (ESQUEMA, "HUECO DE ESQUEMA — no hay donde escribirlo. "
                                "Hay que construir la casilla"),
                      (CONFUSO, "CONFUSO — no contesto lo que se le pidio. NO "
                                "se cuenta")):
        deeste = [h for h in hallazgos if h["veredicto"] == v]
        print(f"\n{titulo}")
        if not deeste:
            print("   ninguno")
            continue
        porcasilla: dict = {}
        for h in deeste:
            porcasilla.setdefault((h["id"], h["clase"], h["casilla"]),
                                  []).append(h)
        for (mid, clase, nombre), hs in porcasilla.items():
            print(f"   {mid} [{clase}] {nombre}")
            print(f"      {len(hs)} de {args.repeticiones} corridas · "
                  f"{hs[0]['detalle']}")
    print("\nUNA RESPUESTA NO ES UNA CAUSA. Lo que vale es lo que se repite en")
    print("todas las corridas Y ademas se pudo comprobar contra el repo.")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(hallazgos, f, ensure_ascii=False, indent=1)
        print(f"\ncrudo en {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
