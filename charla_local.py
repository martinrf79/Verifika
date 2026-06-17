"""
Charla local: conversa con el flujo REAL (process_message) leyendo un guion de
mensajes desde un archivo de texto (una linea = un mensaje del cliente), sin
Telegram ni webhook. Pensado para que el asistente itere pruebas sin molino.

Uso (con las env cargadas por correr_local.ps1 o a mano):
    .\\venv-win\\Scripts\\python.exe charla_local.py <tienda> <guion.txt> [user_id] [pausa_seg]

La pausa entre turnos (default 15s) cuida la cuota del free tier.
"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.orchestrator import process_message

TIENDA = sys.argv[1] if len(sys.argv) > 1 else "verifika_prod"
GUION = sys.argv[2] if len(sys.argv) > 2 else ""
USER = sys.argv[3] if len(sys.argv) > 3 else "charla_local_user"
PAUSA = float(sys.argv[4]) if len(sys.argv) > 4 else 15.0

if not GUION or not os.path.exists(GUION):
    print("Falta el guion: charla_local.py <tienda> <guion.txt> [user] [pausa]")
    raise SystemExit(1)

MENSAJES = [ln.strip() for ln in
            Path(GUION).read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


async def main():
    print(f"[charla] tienda={TIENDA} user={USER} turnos={len(MENSAJES)} "
          f"pausa={PAUSA}s")
    for i, msg in enumerate(MENSAJES, 1):
        print(f"\n[{i}] CLIENTE: {msg}")
        t0 = time.time()
        try:
            resp = await process_message(
                user_id=USER, raw_message=msg, tienda_id=TIENDA,
                canal="telegram")
            print(f"    BOT ({round(time.time() - t0, 1)}s): {resp}")
        except Exception as e:
            print(f"    ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            break
        if i < len(MENSAJES):
            await asyncio.sleep(PAUSA)


if __name__ == "__main__":
    asyncio.run(main())
