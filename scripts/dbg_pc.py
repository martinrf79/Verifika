import asyncio, os, sys
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
from app.core.interpretador import interpretar_mensaje
from app.core.certificador import certificar
TIENDA = "verifika_prod"
MSGS = [
    "tenes una impresora 3d marca Zyltech rara que casi nadie trae?",
    "y la RTX 5070 la tenes?",
    "que caracteristicas tiene el teclado Logitech K380?",
]
async def main():
    hist = [{"role":"user","content":"hola"},{"role":"assistant","content":"Hola, en que te ayudo?"}]
    for m in MSGS:
        r = await interpretar_mensaje(m, hist, "dbg", estado_anterior="explorando", tienda_id=TIENDA, carrito_actual=[])
        pc = r.get("producto_consultado")
        print(f"\nMSG: {m}")
        print(f"  intencion={r.get('intencion')}  producto_consultado={pc!r}")
        if pc:
            c = certificar(pc, TIENDA)
            print(f"  certificar({pc!r}) -> {c.get('status')}")
asyncio.run(main())
