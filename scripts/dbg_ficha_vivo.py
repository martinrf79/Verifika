"""Prueba viva: ¿el bot responde un atributo DESDE la ficha o inventa?
El dato real (ficha TEC0001): origen 'Logitech de Suiza, fabricado en China',
garantia 24 meses, material aluminio. Si el bot dice eso, la ficha llega al
redactor. Si dice otra cosa o 'no se', no llega."""
import asyncio, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
for raw in (ROOT / os.getenv("BANCO_PRESET", "config/camino_nuevo.env")).read_text(encoding="utf-8-sig").splitlines():
    l = raw.strip()
    if l and not l.startswith("#") and "=" in l:
        k, v = l.split("=", 1); os.environ[k.strip()] = v.strip()
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
import structlog, logging
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))
from app.core.orchestrator import process_message

TIENDA = "verifika_prod"
TURNOS = [
    "que teclados tenes?",
    "el Logitech G915 TKL negro, de donde es? es importado? que garantia tiene y de que material es?",
]

async def main():
    user = f"dbgficha_{int(time.time())}"
    for i, m in enumerate(TURNOS, 1):
        r = await process_message(user_id=user, raw_message=m, tienda_id=TIENDA, canal="telegram")
        print(f"\n[{i}] CLIENTE: {m}")
        print(f"    BOT: {str(r).strip()}")

if __name__ == "__main__":
    asyncio.run(main())
