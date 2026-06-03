"""
Prueba de la interpretacion rica (Defensa 1) con DeepSeek. Sin Firestore.

Corre el interprete con INTERPRETE_RICO=true sobre los mensajes reales que
rompieron y muestra los slots que extrae: intenciones, items con cantidad y
confianza, destinos con cajon, atributo consultado, forma de pago, pide_descuento
y ambiguedades. Sirve para ver si DeepSeek llena bien el esquema antes de
engancharlo al Solver.

Correr:
    winvenv\\Scripts\\python.exe scripts\\prueba_interprete_rico.py
"""
import os
import sys
import json
import asyncio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_sec = os.path.join(ROOT, ".secrets.env")
if not os.path.exists(_sec):
    raise SystemExit("Falta .secrets.env")
for _l in open(_sec, encoding="utf-8"):
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        k, v = _l.split("=", 1)
        os.environ[k.strip()] = v.strip()

os.environ["INTERPRETE_RICO"] = "true"
os.environ["INTERPRETER_PROVIDER"] = "deepseek"
os.environ["INTERPRETE_ANCLA_CATALOGO"] = "false"  # aislar la extraccion

import logging
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))

sys.path.insert(0, ROOT)
from app.core.interpretador import interpretar_mensaje  # noqa: E402

# Historial chico para el caso que depende de contexto (de las de 45000).
HIST_CATALOGO = [
    {"role": "user", "content": "que tenes"},
    {"role": "assistant", "content": (
        "Tenemos memorias RAM desde $95.000, webcams desde $35.000, "
        "una lampara LED Xiaomi a $45.000 y teclados desde $12.000.")},
]

CASOS = [
    ("Despeñaderos cascada", [],
     "ok dame el descuento en el envio y en el total para 3 memorias de 450000 "
     "y 3 webcams con envio a zona santa maria, barrio el mirador calle figueroa "
     "alcorta despeñaderos cp5121 necesito que los dos articulos esten en envases "
     "originales por la garantia extendida o si no tendre que dirijirme a quien "
     "corresponda."),
    ("Cordoba doble envio", [],
     "Dame precio de 2 teclados economicos, uno con envio a Colon 4500 Cordoba "
     "capital y otro a Dean Funes 434 para mi sobrina, pago todo junto con "
     "Mercado Pago"),
    ("Cuotas", [],
     "2 teclados con envio gratis, cuanto me queda el total en efectivo y en "
     "cuotas sin interes?"),
    ("De las de 45000 (con contexto)", HIST_CATALOGO,
     "de las de 45000, los sabados no envien porque no estoy solo lunes o martes"),
]


def _show(nombre, r):
    print("=" * 70)
    print(nombre)
    print("  intenciones      :", r.get("intenciones"))
    print("  etapa            :", r.get("estado_conversacion"))
    print("  items            :")
    for it in r.get("items", []):
        print("     ", json.dumps(it, ensure_ascii=False))
    print("  destinos         :")
    for d in r.get("destinos", []):
        print("     ", json.dumps(d, ensure_ascii=False))
    print("  atributo         :", r.get("atributo_consultado"))
    print("  forma_pago       :", r.get("forma_pago"))
    print("  pide_descuento   :", r.get("pide_descuento"))
    print("  ambiguedades     :", r.get("ambiguedades"))
    print("  confianza global :", r.get("confianza"))
    print()


async def main():
    for nombre, hist, msg in CASOS:
        try:
            r = await interpretar_mensaje(msg, hist, trace_id="test",
                                          tienda_id="verifika_2k")
        except Exception as e:
            r = {"error": str(e)[:200]}
        _show(nombre, r)


if __name__ == "__main__":
    asyncio.run(main())
