"""
REGISTRAR WHATSAPP — recrea el mapeo phone_number_id -> tienda en Firestore.

El webhook multi-tenant resuelve la tienda leyendo tiendas_index/{phone_number_id}.
Si ese documento falta (visto 11-jun: whatsapp_unknown_phone_id tras la limpieza
de verifika_demo), Meta entrega el mensaje pero el bot lo descarta.

Uso (con el venv del repo, via correr_local para heredar credenciales):
    .\\correr_local.ps1 py scripts\\registrar_whatsapp.py <phone_number_id> <tienda_id> <meta_token>
Ejemplo:
    .\\correr_local.ps1 py scripts\\registrar_whatsapp.py 997686753425456 verifika_prod EAAG...

El token es el de acceso permanente de la app de Meta (WhatsApp > API setup).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.storage.firestore_client import _get_db  # noqa: E402


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    phone_id, tienda_id, token = sys.argv[1], sys.argv[2], sys.argv[3]

    db = _get_db()
    ref = db.collection("tiendas_index").document(phone_id)
    previo = ref.get()
    if previo.exists:
        print(f"Ya existia: {previo.to_dict().get('tienda_id')} — se actualiza.")
    ref.set({"tienda_id": tienda_id, "whatsapp_token": token}, merge=True)

    confirmado = ref.get().to_dict()
    print(f"OK: tiendas_index/{phone_id} -> tienda {confirmado['tienda_id']}, "
          f"token {'cargado' if confirmado.get('whatsapp_token') else 'VACIO'}")


if __name__ == "__main__":
    main()
