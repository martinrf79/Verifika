"""
Smoke local: manda unos mensajes por el flujo REAL (process_message) para ver a
Nemotron y el corrector trabajando contra Firestore, sin Telegram ni webhook.

Uso (via el lanzador correr_local.ps1, que carga las env vars):
    correr_local.ps1 smoke
    correr_local.ps1 smoke -AllNemotron        # todo el pipeline en Nemotron

O directo, si ya tenes las env vars cargadas:
    .\venv-win\Scripts\python.exe smoke_local.py [tienda_id]
"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.orchestrator import process_message
from app.config import get_settings

TIENDA = sys.argv[1] if len(sys.argv) > 1 else os.getenv("SMOKE_TIENDA", "verifika")
USER = "smoke_local_user"

MENSAJES = [
    "Hola, que tal",
    "Tenes algun mouse para gaming?",
    "Cuanto sale el mas barato con envio a Cordoba capital?",
]


async def main():
    s = get_settings()
    print("=" * 60)
    print(f"Solver provider     : {s.LLM_PROVIDER}")
    print(f"Interpreter provider: {s.INTERPRETER_PROVIDER}")
    print(f"Corrector provider  : {os.getenv('VERIFIKA_CORRECTOR_PROVIDER', 'deepseek')}")
    print(f"Tienda              : {TIENDA}")
    print(f"GCP project         : {s.GCP_PROJECT}")
    print("=" * 60)

    for i, msg in enumerate(MENSAJES, 1):
        print(f"\n[{i}] CLIENTE: {msg}")
        t0 = time.time()
        try:
            resp = await process_message(
                user_id=USER, raw_message=msg, tienda_id=TIENDA, canal="telegram")
            print(f"    BOT ({round(time.time()-t0,1)}s): {resp}")
        except Exception as e:
            print(f"    ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            break


if __name__ == "__main__":
    asyncio.run(main())
