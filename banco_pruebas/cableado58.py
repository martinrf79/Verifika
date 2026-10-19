"""EL CABLEADO SOBRE LAS 58 — el flujo nuevo por el webhook entero, sin modelo (19-oct-2026, orden de Martin).

Cada charla de las 58 de `vara_58.json` corre turno por turno por el clon de produccion —el webhook de WhatsApp, el
antijailbreak, el orchestrator, el cierre y Firestore en RAM— con dos cambios:
  1. el turno es `banco_pruebas.flujo.turno.procesar_turno`, el flujo nuevo;
  2. las dos llamadas al modelo devuelven lo escrito a mano en `banco_pruebas/traducciones58.py`.
Lo que recibe el cliente se califica con las casillas de `vara_58.json`, que no se tocan: las decidio Martin.

El control: `--grabadas <etiqueta>` usa en el ULTIMO turno de cada charla la traduccion que grabo Gemini en
`banco_pruebas/nexos/ficha_casillas_corridas.jsonl`. Si el cableado anda con lo mio y no con lo del modelo, lo mio
esta hecho a la medida del cableado y no vale.

  python3 -m banco_pruebas.cableado58                         las 58
  python3 -m banco_pruebas.cableado58 C27 C46 --ver           esas, con lo que recibio el cliente
  python3 -m banco_pruebas.cableado58 --grabadas f10e_58_gg1  el control con las traducciones de Gemini
"""
import asyncio
import json
import os
import sys

from banco_pruebas import clon_produccion as C

LLAMADAS_AL_MODELO = []
GRABADAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nexos", "ficha_casillas_corridas.jsonl")


def charlas() -> list:
    doc = json.load(open("banco_pruebas/vara_58.json", encoding="utf-8"))
    return [c for c in doc["charlas"] if c["id"].startswith("C")]


def grabadas(etiqueta: str) -> dict:
    out = {}
    for x in open(GRABADAS, encoding="utf-8"):
        f = json.loads(x)
        if f["etiqueta"] == etiqueta:
            try:
                out[f["id"]] = json.loads(f["crudo"]).get("llena") or {}
            except (ValueError, AttributeError):
                out[f["id"]] = {}
    return out


def instalar():
    C.preparar_entorno()
    C.instalar()
    from app.core import orchestrator
    from banco_pruebas.flujo import interprete, turno
    orchestrator.procesar_turno = turno.procesar_turno
    # NI UNA LLAMADA AL MODELO: cada intento se anota, aunque quien llamo se trague el error, y la corrida lo dice.
    from app.core import llm_reintento

    def _sin_modelo(*a, **k):
        LLAMADAS_AL_MODELO.append(1)
        raise RuntimeError("el cableado58 no llama al modelo")
    llm_reintento._cliente = _sin_modelo
    return interprete


def correr(charla: dict, traducciones: list, interprete, explicar: dict) -> list:
    """Los turnos de una charla: lo que recibio el cliente y cada casilla con su nota."""
    from banco_pruebas.sonda_charlas import nota_casilla
    uid = f"cableado_{charla['id']}"
    C.reiniciar_cliente(uid)
    cola = list(traducciones)
    interprete.interpretar = lambda *a, **k: cola.pop(0) if cola else {}
    interprete.explicar = lambda pregunta, *a, **k: explicar.get(pregunta, "")
    respuestas, turnos = [], []
    for t in charla["turnos"]:
        texto = "\n".join(asyncio.run(C.turno(uid, t["texto"])))
        respuestas.append(texto)
        turnos.append({"texto": t["texto"], "respuesta": texto,
                       "casillas": [(k["n"], nota_casilla(k, [], texto, respuestas)) for k in t["casillas"]]})
    return turnos


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ver = "--ver" in sys.argv
    etiqueta = sys.argv[sys.argv.index("--grabadas") + 1] if "--grabadas" in sys.argv else ""
    if etiqueta:
        args = [a for a in args if a != etiqueta]
    interprete = instalar()
    from banco_pruebas.traducciones58 import EXPLICAR, T
    del_modelo = grabadas(etiqueta) if etiqueta else {}
    bien, mal = [], []
    for charla in charlas():
        if args and charla["id"] not in args:
            continue
        trad = list(T.get(charla["id"]) or [])
        if len(trad) != len(charla["turnos"]):
            raise SystemExit(f"{charla['id']}: {len(trad)} traducciones para {len(charla['turnos'])} turnos")
        if etiqueta:
            if charla["id"] not in del_modelo:
                print(f"{charla['id']} SIN GRABACION")
                mal.append(charla["id"])
                continue
            trad[-1:] = [del_modelo[charla["id"]]]
        turnos = correr(charla, trad, interprete, EXPLICAR)
        malas = [n for t in turnos for n, ok in t["casillas"] if ok is not True]
        (mal if malas else bien).append(charla["id"])
        print(f"{charla['id']} {'bien' if not malas else 'MAL: ' + '; '.join(malas)}")
        if ver or (malas and len(args) <= 3 and args):
            for i, t in enumerate(turnos, 1):
                print(f"  T{i} cliente: {t['texto']}\n  " + t["respuesta"].replace("\n", "\n  "))
    print(f"\nCABLEADO{' con ' + etiqueta if etiqueta else ''}: {len(bien)} de {len(bien) + len(mal)} charlas bien")
    if mal:
        print("mal: " + " ".join(mal))
    if LLAMADAS_AL_MODELO:
        print(f"ERROR: {len(LLAMADAS_AL_MODELO)} intentos de llamar al modelo")
        sys.exit(1)


if __name__ == "__main__":
    main()
