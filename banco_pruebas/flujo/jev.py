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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entorno import REPO  # noqa: E402

from app.core.flujo.nuevo.jev import MODELO, URL  # noqa: E402,F401
USD_POR_MILLON = 0.042
GASTO = os.path.join(REPO, "banco_pruebas", "jev", "gasto_jev.jsonl")


def llamar_jev(state, qs, prueba):
    """Una llamada a Jev con preguntas de lista cerrada, la de produccion, `app/core/flujo/nuevo/jev.llamar`, con la
    espera larga del banco; anota el gasto en `jev/gasto_jev.jsonl`. Devuelve ({pregunta: elegido}, tokens de entrada)."""
    from app.core.flujo.nuevo.jev import llamar
    r, tokens = llamar(state, qs, espera=120, intentos=5)
    with open(GASTO, "a") as fh:
        fh.write(json.dumps({"cuando": time.strftime("%Y-%m-%dT%H:%M:%S"), "prueba": prueba, "tokens": tokens,
                             "usd": round(tokens * USD_POR_MILLON / 1e6, 5)}) + "\n")
    return r, tokens
