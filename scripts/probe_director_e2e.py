"""
PROBE DIRECTOR E2E — el rediseno de punta a punta (DIRECTOR_LLM + INTENCION_MANDA),
sistema real (process_message). El LLM gobierna el carrito; el codigo lo ejecuta y
cotiza. Verifica: compra, pregunta intercalada SIN arrastre, sacar, total respaldado.

Uso (cargar secrets antes):
    .\\correr_local.ps1 py scripts\\probe_director_e2e.py
"""
import os
import sys
import asyncio
import time
from pathlib import Path

os.environ["DIRECTOR_LLM"] = "true"   # no esta en el preset: este env manda

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import banco_cierre as bc  # carga preset (INTENCION_MANDA=true) + orchestrator

TURNOS = [
    "hola, quiero 2 mouse M170 negro",                  # agregar x2
    "donde aprieto el boton de encendido de la placa?",  # PREGUNTA: no arrastra
    "sumale un teclado k380 negro",                     # agregar teclado
    "saca el mouse",                                    # sacar -> queda teclado
    "cuanto me queda en total?",                        # total respaldado
]


async def main():
    user = f"probe_dir_{int(time.time())}"
    print(f"\n=== PROBE DIRECTOR E2E (DIRECTOR_LLM=on, INTENCION_MANDA=on) ===")
    print(f"    solver={bc.settings.LLM_PROVIDER} {bc.settings.DEEPSEEK_MODEL}\n")
    for i, msg in enumerate(TURNOS, 1):
        t0 = time.time()
        try:
            resp = await bc.process_message(user_id=user, raw_message=msg,
                                            tienda_id=bc.TIENDA, canal="telegram")
        except Exception as e:
            resp = f"[ERROR {type(e).__name__}: {e}]"
        tele = bc.leer_turno(user)
        print(f"[{i}] CLIENTE: {msg}")
        print(f"    BOT ({round(time.time()-t0,1)}s, etapa={tele.get('estado')}): "
              f"{str(resp).strip()}\n")


if __name__ == "__main__":
    asyncio.run(main())
