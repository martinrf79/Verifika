"""
Prueba aislada y barata: ¿el interprete emite el comando cambiar_cantidad?

Una sola llamada al LLM (no el escenario entero). Simula un carrito con 3
teclados + 1 mouse y el mensaje "mejor que sean 2 teclados", e imprime que
acciones_carrito devolvio. Asi se itera el prompt sin correr 9 turnos.

Uso:
    $env:BANCO_PRESET="config/camino_nuevo.env"
    .\correr_local.ps1 py scripts\dbg_interp_cantidad.py
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _cargar_preset(nombre=None):
    nombre = nombre or os.getenv("BANCO_PRESET", "config/camino_nuevo.env")
    p = ROOT / nombre
    for raw in p.read_text(encoding="utf-8-sig").splitlines():
        l = raw.strip()
        if l and not l.startswith("#") and "=" in l:
            k, v = l.split("=", 1)
            os.environ[k.strip()] = v.strip()


_cargar_preset()
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import logging
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))

from app.core.interpretador import interpretar_mensaje  # noqa: E402

TIENDA = "verifika_prod"
CARRITO = [
    {"id": "TEC0003", "nombre": "Teclado Logitech K380 Negro", "cantidad": 3},
    {"id": "MOU0001", "nombre": "Mouse Logitech G203 Lightsync Negro",
     "cantidad": 1},
]
# Historia COMPLETA como en la corrida real del banco (turnos 1-5), para
# reproducir el contexto que hace que el interprete no emita el comando.
HISTORY = [
    {"role": "user", "content": "hola, buenas"},
    {"role": "assistant", "content": "¡Hola! ¿Cómo andás? Bienvenido a "
        "Verifika Tech. Decime, ¿qué buscás?"},
    {"role": "user", "content": "que teclados tenes?"},
    {"role": "assistant", "content": "Mirá, tenemos varios modelos de Logitech: "
        "G915 TKL, K380 y G413 TKL SE. ¿Cuál te interesa?"},
    {"role": "user", "content": "dame el precio de 3 teclados, capaz "
        "inalambricos, no se bien el color"},
    {"role": "assistant", "content": "Para 3 teclado tengo estas opciones: "
        "Teclado Logitech G915 TKL Negro a $512.500 o Teclado Logitech K380 "
        "Negro a $55.000. Cual preferis?"},
    {"role": "user", "content": "los 3 K380 negros"},
    {"role": "assistant", "content": "¡Buenísimo! Presupuesto: 3x Teclado "
        "Logitech K380 Negro $165.000. Total $165.000. ¿Te parece bien?"},
    {"role": "user", "content": "sumale un mouse G203 negro"},
    {"role": "assistant", "content": "¡Dale! Te queda así: 3x K380 $165.000, "
        "1x Mouse G203 $37.500. Total $202.500. ¿Te parece bien?"},
]

CASOS = [
    "mejor que sean 2 teclados",
    "saca el mouse",
    "dejalo en 1 teclado",
    "sumale otro teclado",
    "cuanto sale en total?",   # NO debe tocar el carrito
]


async def main():
    for msg in CASOS:
        r = await interpretar_mensaje(
            msg, HISTORY, "dbg", estado_anterior="cierre",
            tienda_id=TIENDA, carrito_actual=CARRITO)
        print(f"\nMENSAJE: {msg}")
        print(f"  intencion       : {r.get('intencion')}")
        print(f"  producto_resuelto: {r.get('producto_resuelto')}")
        print(f"  acciones_carrito : {r.get('acciones_carrito')}")


if __name__ == "__main__":
    asyncio.run(main())
