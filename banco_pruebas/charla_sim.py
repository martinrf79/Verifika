"""
CHARLA SOBRE FIRESTORE SIMULADO — corre el camino vivo de punta a punta con la
base local real y DeepSeek vivo. Sin credenciales de Google.

Uso:
    python3 scripts/charla_sim.py                 # guion de ejemplo
    python3 scripts/charla_sim.py guion.txt       # un mensaje por linea
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from banco_pruebas.sim_firestore import install

TIENDA = "verifika_prod"
USER = "sim_user"

_GUION_DEMO = [
    "hola, tenes mouse?",
    "cual es el mas barato?",
    "y un teclado barato? sumalo",
    "cuanto sale todo con envio a Cordoba capital pagando por transferencia?",
    "es seguro comprar por internet?",
]


async def main():
    info = install()
    print(f"[sim] Firestore simulado: {info['productos']} productos, {info['faq']} FAQ. "
          f"DeepSeek vivo. Memoria en RAM.\n")

    from app.core.orchestrator import process_message

    if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
        mensajes = [l.strip() for l in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
                    if l.strip() and not l.strip().startswith("#")]
    else:
        mensajes = _GUION_DEMO

    for i, msg in enumerate(mensajes, 1):
        print(f"[{i}] CLIENTE: {msg}")
        t0 = time.time()
        try:
            resp = await process_message(USER, msg, tienda_id=TIENDA, canal="sim")
        except Exception as e:
            import traceback
            resp = f"<<ERROR {type(e).__name__}: {e}>>"
            traceback.print_exc()
        ms = int((time.time() - t0) * 1000)
        print(f"    BOT ({ms} ms): {resp}\n")


if __name__ == "__main__":
    asyncio.run(main())
