"""
CHARLA SOBRE FIRESTORE SIMULADO — corre el camino vivo de punta a punta con la
base local real y DeepSeek vivo. Sin credenciales de Google.

Uso:
    python3 banco_pruebas/charla_sim.py               # guion de ejemplo
    python3 banco_pruebas/charla_sim.py guion.txt     # un mensaje por linea

Cada respuesta pasa por el JUEZ de invariantes (banco_pruebas/juez.py); si
alguna viola uno, el proceso termina con codigo distinto de cero.
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

    from banco_pruebas.juez import juzgar

    problemas_total = 0
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
        # JUEZ de invariantes: la tanda falla sola si una respuesta viola uno
        # (stock contradicho, promesa prohibida, marcador sin estampar, precio
        # de lista pisado, narracion interna). Sin juez habia que LEER todo.
        if resp.startswith("<<ERROR"):
            problemas_total += 1
        else:
            for p in juzgar(resp, tienda_id=TIENDA):
                print(f"    [JUEZ] PROBLEMA: {p}")
                problemas_total += 1

    if problemas_total:
        print(f"[JUEZ] TANDA CON {problemas_total} PROBLEMA(S)")
    else:
        print("[JUEZ] tanda limpia")
    return problemas_total


if __name__ == "__main__":
    raise SystemExit(1 if asyncio.run(main()) else 0)
