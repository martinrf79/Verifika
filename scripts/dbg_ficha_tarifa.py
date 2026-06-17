import os, sys, json
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
from app.core.tools_context import set_current_tienda
from app.core.tools import get_product_details, cotizar_envio, search_products
set_current_tienda("verifika_prod")
pid = (search_products(query="teclado").get("productos") or [{}])[0].get("id")
print("=== FICHA cruda de", pid, "===")
print(json.dumps(get_product_details(pid), ensure_ascii=False, indent=1)[:1800])
print("\n=== COTIZAR_ENVIO Cordoba subtotal 100000 ===")
print(json.dumps(cotizar_envio(localidad="Cordoba capital", subtotal=100000), ensure_ascii=False, indent=1)[:1400])
print("\n=== COTIZAR_ENVIO CABA subtotal 50000 ===")
print(json.dumps(cotizar_envio(localidad="CABA", subtotal=50000), ensure_ascii=False, indent=1)[:1400])
