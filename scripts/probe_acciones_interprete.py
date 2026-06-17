"""
PROBE ACCIONES INTERPRETE — valida en VIVO que el interprete, con DIRECTOR_LLM on,
emita buenas acciones_carrito: agregar ante una compra, lista VACIA ante una
pregunta, sacar/cambiar cuando corresponde. Es la hipotesis central del rediseno.

Uso (cargar secrets antes):
    .\\correr_local.ps1 py scripts\\probe_acciones_interprete.py
"""
import os
import sys
import asyncio
from pathlib import Path

os.environ["DIRECTOR_LLM"] = "true"
os.environ["CONFIRMACION_PROVIDER"] = "true"
os.environ.setdefault("LLM_PROVIDER", "deepseek")
os.environ.setdefault("INTERPRETER_PROVIDER", "deepseek")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import logging
import structlog
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))

from app.core.interpretador import interpretar_mensaje  # noqa: E402

TIENDA = "verifika_prod"

# (mensaje, history, que esperamos de acciones_carrito)
CASOS = [
    ("hola, quiero 2 mouse M170 negro", [], "agregar mouse x2"),
    ("donde aprieto el boton de encendido de la placa?",
     [{"role": "assistant", "content": "Tenes 2x Mouse M170 en el carrito, $24.000"}],
     "VACIA (es pregunta)"),
    ("cuanto sale el teclado k380?", [], "VACIA (pregunta de precio)"),
    ("sumale un teclado k380 negro",
     [{"role": "assistant", "content": "Llevas 2x Mouse M170, $24.000"}],
     "agregar teclado"),
    ("sacame el mouse",
     [{"role": "assistant", "content": "Llevas 2x Mouse M170 y 1 teclado K380"}],
     "sacar mouse"),
    ("mejor que sean 3 teclados",
     [{"role": "assistant", "content": "Llevas 1 Teclado K380 y 1 Mouse"}],
     "cambiar_cantidad teclado a 3"),
    ("gracias, despues sigo", [], "VACIA (despedida)"),
]


async def main():
    print("\n=== PROBE ACCIONES INTERPRETE (DIRECTOR_LLM on) ===\n")
    for msg, hist, esperado in CASOS:
        r = await interpretar_mensaje(msg, hist, "probe", tienda_id=TIENDA)
        acc = r.get("acciones_carrito", "FALTA")
        print(f"CLIENTE: {msg}")
        print(f"  intencion={r.get('intencion')}  acciones={acc}")
        print(f"  esperado: {esperado}\n")


if __name__ == "__main__":
    asyncio.run(main())
