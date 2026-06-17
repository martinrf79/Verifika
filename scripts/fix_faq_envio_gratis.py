"""Fix a07 del arnes: la consulta 'envio gratis' caia al tema generico envios
(sin el umbral). Se agregan keywords al tema costo_envio, que SI tiene el
umbral de envio gratis en su respuesta y valores. Aditivo e idempotente."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.storage.firestore_client import _tienda_ref

TIENDA = sys.argv[1] if len(sys.argv) > 1 else "verifika_prod"
NUEVAS = ["envio gratis", "envio sin costo", "envio bonificado"]

ref = _tienda_ref(TIENDA).collection("faq").document("costo_envio")
doc = ref.get()
if not doc.exists:
    raise SystemExit(f"No existe faq/costo_envio en {TIENDA}")
data = doc.to_dict()
kws = list(data.get("keywords") or [])
faltantes = [k for k in NUEVAS if k not in kws]
if not faltantes:
    print("Ya estaban todas las keywords, nada que hacer.")
else:
    ref.update({"keywords": kws + faltantes})
    print(f"Agregadas a costo_envio de {TIENDA}: {faltantes}")
