"""Pregunta informativa por un producto que NO existe: antes ofrecia Epson,
ahora el certificador dice not_found y cae al puente fuera_catalogo. Y un
producto que SI existe debe responderse normal."""
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
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.INFO))
from app.core.orchestrator import process_message

TIENDA = "verifika_prod"
CASOS = [
    [("hola", None),
     ("tenes una impresora 3d marca Zyltech rara que casi nadie trae?", "NO EXISTE -> puente"),
     ("y la RTX 5070 la tenes?", "NO EXISTE -> puente")],
    [("que caracteristicas tiene el teclado Logitech K380?", "EXISTE -> responde ficha")],
]

async def main():
    for conv in CASOS:
        user = f"dbgcert_{int(time.time()*1000)}"
        print("\n" + "="*70)
        for m, nota in conv:
            r = await process_message(user_id=user, raw_message=m, tienda_id=TIENDA, canal="telegram")
            print(f"\nCLIENTE: {m}" + (f"   [{nota}]" if nota else ""))
            print(f"  BOT: {str(r).strip()[:400]}")

if __name__ == "__main__":
    asyncio.run(main())
