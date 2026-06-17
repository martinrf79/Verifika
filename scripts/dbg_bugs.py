"""
Reproduce offline las causas raiz de los bugs del test adversario 15-jun:
  (A) "10%" leido como cantidad 10  -> que emite el interprete
  (B) resolver que salta de categoria -> "ASRock B450M Steel Legend" (placa
      base) cae en una placa de video; "Monitor Samsung Odyssey G9 49" no entra.

Uso:
    $env:BANCO_PRESET="config/camino_nuevo.env"
    .\correr_local.ps1 py scripts\dbg_bugs.py
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

import logging  # noqa: E402
import structlog  # noqa: E402
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))

from app.core.interpretador import interpretar_mensaje  # noqa: E402
from app.core.director import _resolver  # noqa: E402

TIENDA = "verifika_prod"


async def bug_a():
    print("\n===== BUG A: '10%' como cantidad =====")
    cart = [{"id": "GPU0001", "nombre": "Placa de video Asus ROG Strix RTX 4080 Super",
             "cantidad": 1}]
    hist = [
        {"role": "user", "content": "Quiero la Asus ROG Strix RTX 4080 Super"},
        {"role": "assistant", "content": "Dale, la RTX 4080 Super sale "
            "$2.962.000. Con 10% por transferencia te queda $2.665.800."},
    ]
    for msg in [
        "Si pago por transferencia, ¿cuánto es el 10% de descuento exacto de la Asus ROG Strix RTX 4080 Super?",
        "haceme el 10% de descuento",
        "quiero el 10% de descuento",
    ]:
        r = await interpretar_mensaje(msg, hist, "dbg", estado_anterior="cierre",
                                      tienda_id=TIENDA, carrito_actual=cart)
        print(f"  '{msg[:55]}...' -> intencion={r.get('intencion')} "
              f"acciones={r.get('acciones_carrito')}")


def bug_b():
    print("\n===== BUG B: resolver que salta de categoria =====")
    for term in [
        "ASRock B450M Steel Legend",
        "placa base ASRock B450M Steel Legend",
        "Motherboard Asus TUF B650-Plus WiFi",
        "Monitor Samsung Odyssey G9 49",
        "Notebook Lenovo Legion 5 Core i7",
    ]:
        r = _resolver(term, TIENDA)
        est = r.get("estado")
        if est == "ok":
            it = r["item"]
            print(f"  '{term}' -> OK: {it.get('nombre')} | cat={it.get('categoria')}")
        elif est == "ambiguo":
            print(f"  '{term}' -> AMBIGUO: "
                  + ", ".join(f"{c.get('nombre')}" for c in r["candidatos"]))
        else:
            print(f"  '{term}' -> {est}")


async def main():
    await bug_a()
    bug_b()


if __name__ == "__main__":
    asyncio.run(main())
