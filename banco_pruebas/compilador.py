#!/usr/bin/env python3
"""EL COMPILADOR — de la ficha del traductor al pedido que ejecuta el motor.

QUE ES. El prototipo, en el banco, de los pasos 1 a 3 del plan del 23-sep:
VALIDAR la ficha, ATERRIZAR las palabras del cliente en valores del catalogo
y COMPILAR la ficha al pedido. El pedido sale con la MISMA forma que hoy
escribe el modelo en el camino vivo —consultas, temas, envios, reparto,
afirma—, y eso es lo que permite medirlo con la vara de 19 y el mismo lector
que dio el piso de 56 de 57, sin tocar produccion.

EL REPARTO DE TRABAJO, que es toda la idea:

    el modelo      traduce: partes, intencion, origen, rubro, criterios con
                   las PALABRAS del cliente
    este codigo    decide: que campo, que valor del catalogo, que operador,
                   que tema de la casa. Determinista, sin llamar a nadie.

LO QUE NO HACE, a proposito:
  - No inventa una cifra: un umbral sale solo de un numero escrito en el
    valor que el cliente dijo.
  - No adivina un rubro: si la parte se refiere a algo anterior, el rubro
    queda vacio y lo resuelve la memoria —paso 6—.
  - No elige entre dos temas que empatan: los pasa, y el motor ya sabe
    servir candidatos.

Uso, desde la raiz:
    python3 banco_pruebas/compilador.py --modelo deepseek
    python3 banco_pruebas/compilador.py --modelo gemini --solo M1,M6
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from banco_pruebas import clon_produccion  # noqa: E402
from banco_pruebas import traductor as T  # noqa: E402
from banco_pruebas.leer_interpretacion import (  # noqa: E402
    CASILLA, DEUDA, _norm)

TIENDA = T.TIENDA
VARA_19 = os.path.join(RAIZ, "banco_pruebas", "vara_interpretacion.json")


# ── 1 A 3 · VALIDAR, ATERRIZAR Y COMPILAR VIVEN EN app/ ─────────────────────
#
# Desde el 23-sep el codigo corre en produccion: `app/core/interprete.py`. Aca
# se importa, asi que lo que mide el banco es lo que corre, y no hay dos
# copias. Los nombres se re-exportan para los tests y los scripts.
from app.core.interprete import (  # noqa: E402,F401
    _BARATO, _CARO, _NIEGA, _TECHO, _PISO, _cifras, _criterios_validos,
    _escrito, _negado, _raiz, aterrizar, compilar, validar)


# ── LA MEDICION: la vara de 19, con el lector del piso ─────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", default="deepseek",
                    choices=("gemini", "deepseek"))
    ap.add_argument("--tablero", default="v5")
    ap.add_argument("--solo", default="")
    ap.add_argument("--json", default="")
    args = ap.parse_args()
    clon_produccion.preparar_entorno()
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    tab = T.tablero()
    sistema, esq = T.prompt(tab, args.tablero), T.esquema(tab, args.tablero)
    with open(VARA_19, encoding="utf-8") as f:
        vara = json.load(f)
    quiero = {x.strip().upper() for x in args.solo.split(",") if x.strip()}
    mensajes = [m for m in vara["mensajes"] if not quiero or m["id"] in quiero]

    def uno(m):
        ficha, ms = T.traducir(m["texto"], args.modelo, sistema, esq)
        limpia, avisos = validar(ficha, m["texto"], tab)
        return m, ficha, limpia, avisos, compilar(limpia, m["texto"], tab), ms

    with cf.ThreadPoolExecutor(4) as ex:
        filas = list(ex.map(uno, mensajes))
    ok = de = 0
    crudo = []
    for m, ficha, limpia, avisos, pedido, ms in filas:
        res = [(c["n"], CASILLA[c["tipo"]](c, pedido))
               for c in m["casillas"] if c["tipo"] != DEUDA]
        o = sum(1 for _n, v in res if v)
        ok += o
        de += len(res)
        print(f"{'OK' if o == len(res) else 'XX'} {m['id']:<4} {o}/{len(res)} "
              f"{ms}ms  {m['texto'][:60]}")
        for n, v in res:
            if not v:
                print(f"      - {n}")
        for a in avisos:
            print(f"      ! {a}")
        crudo.append({"id": m["id"], "ficha": ficha, "pedido": pedido,
                      "avisos": avisos, "casillas": res, "ms": ms})
    print(f"\n{args.modelo.upper()} {args.tablero} + compilador: {ok} de {de} "
          f"en la vara de 19 (piso del camino vivo: 56 de 57)")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(crudo, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
