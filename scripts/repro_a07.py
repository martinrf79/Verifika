"""Repro a07: que devuelve query_faq para 'envio gratis' y que FAQs hay."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.tools_context import set_current_tienda
from app.storage.firestore_client import get_all_faq
from app.core.tools import query_faq

set_current_tienda("verifika_prod")
faq = get_all_faq(tienda_id="verifika_prod") or {}
for tema, data in faq.items():
    kws = data.get("keywords", [])
    print(f"- {tema} [{data.get('tipo')}] kw={kws}")
    if "envio" in tema or "gratis" in str(kws):
        print(f"    respuesta: {str(data.get('respuesta'))[:200]}")
        for v in data.get("valores", []) or []:
            print(f"    valor: {json.dumps(v, ensure_ascii=False)[:160]}")

print("\nquery_faq('envio gratis'):")
print(json.dumps(query_faq("envio gratis"), ensure_ascii=False)[:800])
