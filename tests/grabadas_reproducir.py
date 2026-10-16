"""Reproduce charlas grabadas por el camino vivo, sin modelo y sin red, y
califica lo que recibio el cliente con la vara de las 58. Corre en su propio
proceso: instala el doble de Firestore y el conector del banco sobre `app`, y
eso no tiene que tocar a los demas tests. Lo llama `test_casos_grabados.py`.

  python3 tests/grabadas_reproducir.py gp_montos_1 [ID ...]
Imprime una linea JSON por charla: {"id", "mal": [[turno, casilla]], "sin_grabacion": [turnos]}.
"""
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)
for k in ("GEMINI_API_KEY_PROD", "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "BANCO_CLAVE_PAGA"):
    os.environ.pop(k, None)
os.environ["GEMINI_API_KEY"] = "sin-red"  # nunca se llama: cada salida del modelo viene de la grabacion

from banco_pruebas import clon_produccion as C  # noqa: E402

C.preparar_entorno()
C.instalar()
from banco_pruebas import sonda_charlas as S  # noqa: E402

etiqueta, pedidas = sys.argv[1], set(sys.argv[2:])
vara = {c["id"]: c for c in S.charlas("todas")}
for x in open(S.SALIDA, encoding="utf-8"):
    if f'"{etiqueta}"' not in x[:300]:
        continue
    g = json.loads(x)
    if g["etiqueta"] != etiqueta or (pedidas and g["id"] not in pedidas):
        continue
    turnos = S.correr_clon(vara[g["id"]], grabado=g["turnos"])
    resp = [t["respuesta"] for t in turnos]
    mal = [[t["turno"], k["n"]] for t, tv in zip(turnos, vara[g["id"]]["turnos"]) for k in tv["casillas"]
           if S.nota_casilla(k, [], t["respuesta"], resp[:t["turno"]]) is False]
    print("GRABADA " + json.dumps({"id": g["id"], "mal": mal,
                                   "sin_grabacion": [t["turno"] for t in turnos if t.get("sin_grabacion")]},
                                  ensure_ascii=False), flush=True)
