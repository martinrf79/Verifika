"""EL CABLEADO SOBRE LAS 58 — el flujo vivo por el webhook entero, sin modelo (20-oct-2026, orden de Martin).

Cada charla de las 58 de `vara_58.json` corre turno por turno por el clon de produccion —el webhook de WhatsApp, el
antijailbreak, el orchestrator, el flujo, el cierre y Firestore en RAM—, y las dos llamadas al modelo devuelven lo
escrito a mano en `banco_pruebas/agendas58.py`: la agenda de cada turno y la explicacion de saber general.
Lo que recibe el cliente se califica con las casillas de `vara_58.json`, que no se tocan: las decidio Martin.

El control contra la trampa es la corrida final con el modelo, comparada pregunta por pregunta con `agendas58.py`.

  python3 -m banco_pruebas.cableado58                         las 58
  python3 -m banco_pruebas.cableado58 C27 C46 --ver           esas, con lo que recibio el cliente
"""
import asyncio
import json
import sys

from banco_pruebas import clon_produccion as C

LLAMADAS_AL_MODELO = []


# Las complejas de la vara que ya entraron: varios rubros a varios destinos, la clase que Martin probo en vivo, y la
# memoria a varios turnos.
COMPLEJAS = ("K03", "K06", "K07", "K10", "K11", "K20", "K21")


def charlas() -> list:
    doc = json.load(open("banco_pruebas/vara_58.json", encoding="utf-8"))
    return [c for c in doc["charlas"] if c["id"].startswith("C") or c["id"] in COMPLEJAS]


def instalar():
    C.preparar_entorno()
    C.instalar()
    from app.core.flujo import interprete
    # NI UNA LLAMADA AL MODELO: cada intento se anota, aunque quien llamo se trague el error, y la corrida lo dice.
    from app.core import llm_reintento

    def _sin_modelo(*a, **k):
        LLAMADAS_AL_MODELO.append(1)
        raise RuntimeError("el cableado58 no llama al modelo")
    llm_reintento._cliente = _sin_modelo
    return interprete


def correr(charla: dict, agendas: list, interprete, explicar: dict) -> list:
    """Los turnos de una charla: lo que recibio el cliente y cada casilla con su nota."""
    from banco_pruebas.sonda_charlas import nota_casilla
    uid = f"cableado_{charla['id']}"
    C.reiniciar_cliente(uid)
    cola = list(agendas)

    async def _interpretar(*a, **k):
        return cola.pop(0) if cola else {}

    async def _explicar(pregunta, *a, **k):
        return explicar.get(pregunta, "")
    interprete.interpretar, interprete.explicar = _interpretar, _explicar
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
    interprete = instalar()
    from banco_pruebas.agendas58 import AGENDAS, EXPLICAR
    bien, mal = [], []
    for charla in charlas():
        if args and charla["id"] not in args:
            continue
        agendas = list(AGENDAS.get(charla["id"]) or [])
        if len(agendas) != len(charla["turnos"]):
            raise SystemExit(f"{charla['id']}: {len(agendas)} agendas para {len(charla['turnos'])} turnos")
        turnos = correr(charla, agendas, interprete, EXPLICAR)
        malas = [n for t in turnos for n, ok in t["casillas"] if ok is not True]
        (mal if malas else bien).append(charla["id"])
        print(f"{charla['id']} {'bien' if not malas else 'MAL: ' + '; '.join(malas)}")
        if ver or (malas and len(args) <= 3 and args):
            for i, t in enumerate(turnos, 1):
                print(f"  T{i} cliente: {t['texto']}\n  " + t["respuesta"].replace("\n", "\n  "))
    print(f"\nCABLEADO: {len(bien)} de {len(bien) + len(mal)} charlas bien")
    if mal:
        print("mal: " + " ".join(mal))
    if LLAMADAS_AL_MODELO:
        print(f"ERROR: {len(LLAMADAS_AL_MODELO)} intentos de llamar al modelo")
        sys.exit(1)


if __name__ == "__main__":
    main()
