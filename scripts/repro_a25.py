"""Repro puntual del caso a25: cotizar_envio + calculate_total a La Plata."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.tools_context import set_current_tienda
from app.core.tools import cotizar_envio, calculate_total, search_products

set_current_tienda("verifika_prod")

env = cotizar_envio(localidad="La Plata", subtotal=171000)
print("cotizar_envio:", json.dumps(env, ensure_ascii=False, default=str)[:600])

prods = search_products(query="mouse genius dx-110")
pid = None
for p in prods.get("productos", []) or prods.get("resultados", []) or []:
    pid = p.get("id")
    break
print("producto:", pid)
if pid:
    calc = calculate_total(
        items=[{"product_id": pid, "cantidad": 1}],
        items_extra=[{"faq_tema": "costo_envio", "concepto": "envio_buenos_aires"}])
    print("calculate_total:", json.dumps(calc, ensure_ascii=False, default=str)[:900])
