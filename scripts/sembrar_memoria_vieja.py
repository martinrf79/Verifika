"""
Siembra el doc de conversacion de un usuario de prueba con MEMORIA VIEJA
(pedido de otra venta + direccion + updated_at de hace dias) para reproducir
el caso del 12-jun: cierre con pedido viejo y direccion fantasma.

Uso: .\\venv-win\\Scripts\\python.exe scripts\\sembrar_memoria_vieja.py <tienda> <user_id>
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("GCP_PROJECT", "memory-engine-v1")

from app.storage.firestore_client import _tienda_ref

TIENDA = sys.argv[1] if len(sys.argv) > 1 else "verifika_prod"
USER = sys.argv[2] if len(sys.argv) > 2 else "charla_local_user"

PRESUPUESTO_VIEJO = (
    "Presupuesto:\n"
    "- 1x Mouse Genius DX-110 Negro: $8.500 c/u = $8.500\n"
    "- 2x Almacenamiento externo Kingston DataTraveler Exodia 1TB Negro: "
    "$13.500 c/u = $27.000\n"
    "Subtotal: $35.500\nEnvio: $7.500\nTotal: $43.000")

ref = _tienda_ref(TIENDA).collection("conversaciones").document(USER)
ref.set({
    "history": [
        {"role": "user", "content": "soy carlos, lo llevo con envio a "
                                    "calle arenales 200 corralito cordoba"},
        {"role": "assistant", "content": "Listo Carlos, tomamos tu pedido por "
                                         "$43.000 a Calle Arenales 200, "
                                         "Corralito, Cordoba."},
    ],
    "summary": "",
    "estado_conversacion": "esperando_datos",
    "ultimo_presupuesto": PRESUPUESTO_VIEJO,
    "carrito_vigente": [
        {"id": "MOU0001", "nombre": "Mouse Genius DX-110 Negro", "cantidad": 1},
        {"id": "ALM0001", "nombre": "Kingston DataTraveler Exodia 1TB",
         "cantidad": 2},
    ],
    "ultima_localidad": "calle arenales 200 corralito cordoba",
    "updated_at": datetime.now(timezone.utc) - timedelta(days=2),
})
print(f"[ok] memoria vieja sembrada: tienda={TIENDA} user={USER} "
      f"(pedido $43.000, direccion Arenales, hace 2 dias)")
