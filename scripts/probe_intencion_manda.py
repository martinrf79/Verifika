"""
PROBE INTENCION_MANDA — reproduce en VIVO el sintoma de la charla real de Martin
(15-jun): el presupuesto vigente se arrastra y se re-estampa ante una PREGUNTA,
tapando lo que el cliente realmente dice.

Corre la misma charla con el flag INTENCION_MANDA on u off (segun el arg) para
comparar. El flag se setea ANTES de importar banco_cierre; el preset no lo trae,
asi que este env manda.

Uso:
    .\\correr_local.ps1 py scripts\\probe_intencion_manda.py off
    .\\correr_local.ps1 py scripts\\probe_intencion_manda.py on
"""
import os
import sys
import asyncio
import time
from pathlib import Path

MODO = (sys.argv[1] if len(sys.argv) > 1 else "on").lower()
os.environ["INTENCION_MANDA"] = "true" if MODO == "on" else "false"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import banco_cierre as bc  # carga preset + orchestrator

# Charla que reproduce el sintoma: primero mete algo al carrito, despues PREGUNTA
# cosas que no tocan el carrito. El bot NO debe repetir el presupuesto ni ignorar
# la pregunta.
TURNOS = [
    "hola, quiero 2 mouse M170 negro",                 # arma presupuesto (carrito)
    "donde aprieto el boton de encendido de la placa?",  # PREGUNTA: no es el pedido
    "no es eso lo que pregunto, lei mi pregunta",        # PREGUNTA: insiste
    "che pregunto otra cosa, no entendes",               # PREGUNTA: insiste
    "ahora si, quiero un teclado",                       # cambio de rumbo (compra)
]


async def main():
    user = f"probe_im_{MODO}_{int(time.time())}"
    print(f"\n=== PROBE INTENCION_MANDA = {MODO.upper()} (flag={os.environ['INTENCION_MANDA']}) ===")
    print(f"    solver={bc.settings.LLM_PROVIDER} {bc.settings.DEEPSEEK_MODEL}\n")
    for i, msg in enumerate(TURNOS, 1):
        t0 = time.time()
        try:
            resp = await bc.process_message(user_id=user, raw_message=msg,
                                            tienda_id=bc.TIENDA, canal="telegram")
        except Exception as e:
            resp = f"[ERROR {type(e).__name__}: {e}]"
        tele = bc.leer_turno(user)
        dt = round(time.time() - t0, 1)
        print(f"[{i}] CLIENTE: {msg}")
        print(f"    BOT ({dt}s, etapa={tele.get('estado')}): {str(resp).strip()}\n")


if __name__ == "__main__":
    asyncio.run(main())
