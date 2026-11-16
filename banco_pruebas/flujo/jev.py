"""JEV: ELIGE DE LISTAS CERRADAS LO QUE LOS NEXOS DEJAN DUDOSO (16-nov-2026).

Jev no separa ni traduce: recibe el mensaje y, por cada parte dudosa, una lista cerrada de candidatos con su
descripcion, mas "ninguno". Lo usan los nexos de rubro, tema y condicion, y `reales.py`. Antes vivia en `nexo_tema.py`;
se paso a su archivo el 16-nov al ordenar el flujo, sin cambiar la llamada.

La API es la de typesafe, modelo `jev-latest`, con la clave `TYPESAFE_API_KEY`. Cada llamada anota sus tokens y su
costo en `banco_pruebas/jev/gasto_jev.jsonl`, el libro de Jev que comparten el flujo y las pruebas viejas de `jev/`.
Lo que respondio en cada banco queda grabado en `grabado/*_jev.jsonl` y `grabado/nexo_tema_dudoso.jsonl`: las
calificaciones lo leen de ahi, sin gasto.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entorno import REPO  # noqa: E402

URL = "https://api.typesafe.ai/v1/systemone"
MODELO = "jev-latest"
USD_POR_MILLON = 0.042
GASTO = os.path.join(REPO, "banco_pruebas", "jev", "gasto_jev.jsonl")


def llamar_jev(state, qs, prueba):
    """Una llamada a Jev con preguntas de lista cerrada; anota el gasto en `jev/gasto_jev.jsonl`.
    Devuelve ({pregunta: elegido}, tokens de entrada)."""
    body = {"state": state, "model": MODELO, "questions": qs}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + os.environ["TYPESAFE_API_KEY"].strip(), "Content-Type": "application/json"})
    for intento in range(5):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=120))
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and intento < 4:
                time.sleep(3 * 2 ** intento)
                continue
            raise
    with open(GASTO, "a") as fh:
        fh.write(json.dumps({"cuando": time.strftime("%Y-%m-%dT%H:%M:%S"), "prueba": prueba,
                             "tokens": r["usage"]["input_tokens"],
                             "usd": round(r["usage"]["input_tokens"] * USD_POR_MILLON / 1e6, 5)}) + "\n")
    return {k: v["choice"] for k, v in r["answers"].items()}, r["usage"]["input_tokens"]
