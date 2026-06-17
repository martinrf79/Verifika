"""El interprete clasifica VER CATALOGO como intencion, en todas sus formas, y NO
confunde una categoria puntual ('que teclados tenes') con catalogo general."""
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
TIENDA = "verifika_prod"
# (mensaje, esperado quiere_catalogo)
CASOS = [
    ("catalogo", True),
    ("mostrame todo lo que vendan", True),
    ("que venden ustedes", True),
    ("que tienen para ofrecer", True),
    ("quiero ver el inventario completo", True),
    ("que productos hay", True),
    ("pasame el catalogo", True),
    ("que teclados tenes", False),       # categoria puntual -> NO catalogo
    ("tenes el mouse G203 negro", False),# producto -> NO
    ("hacen envios a cordoba", False),   # politica -> NO
    ("hola", False),                     # saludo -> NO
]
async def main():
    ok = 0
    hist = [{"role":"user","content":"hola"},{"role":"assistant","content":"Hola, en que te ayudo?"}]
    for m, esp in CASOS:
        r = await interpretar_mensaje(m, hist, "dbg", estado_anterior="explorando", tienda_id=TIENDA, carrito_actual=[])
        got = bool(r.get("quiere_catalogo"))
        bien = got == esp
        ok += bien
        print(f"[{'OK ' if bien else 'FALLA'}] '{m[:40]}' -> quiere_catalogo={got} (esp {esp}) int={r.get('intencion')}")
    print(f"\n=== {ok}/{len(CASOS)} ===")
asyncio.run(main())
