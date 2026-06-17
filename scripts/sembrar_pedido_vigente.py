"""
Siembra el doc de conversacion de un usuario de prueba con un pedido VIGENTE
(updated_at de ahora, asi el TTL de 12h NO lo borra) para probar el reset por
"nueva compra". Reproduce el caso Esteban del 12-jun: 2 mouse + 2 tablets,
$447.000, y el bot re-vendia el pedido ante dos "nueva compra" seguidos.

Uso: .\\venv-win\\Scripts\\python.exe scripts\\sembrar_pedido_vigente.py <tienda> <user_id>
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("GCP_PROJECT", "memory-engine-v1")

from app.storage.firestore_client import _tienda_ref

TIENDA = sys.argv[1] if len(sys.argv) > 1 else "verifika_prod"
USER = sys.argv[2] if len(sys.argv) > 2 else "prueba_nueva_compra"

PRESUPUESTO = (
    "Presupuesto:\n"
    "- 2x Mouse Logitech M170 Negro: $12.000 c/u = $24.000\n"
    "- 2x Tablet Samsung Galaxy Tab A9 Gris: $211.500 c/u = $423.000\n"
    "Subtotal: $447.000\nEnvio: gratis\nTotal: $447.000")

ref = _tienda_ref(TIENDA).collection("conversaciones").document(USER)
ref.set({
    "history": [
        {"role": "user", "content": "soy esteban, quiero 2 mouse y 2 tablets, "
                                    "lo mas barato, envio a san agustin cordoba"},
        {"role": "assistant", "content": "Hola Esteban! Aca va el presupuesto: "
                                         "2x Mouse Logitech M170 Negro $24.000 + "
                                         "2x Tablet Samsung Galaxy Tab A9 Gris "
                                         "$423.000. Total: $447.000 con envio "
                                         "gratis a San Agustin, Cordoba."},
    ],
    "summary": "",
    "estado_conversacion": "esperando_datos",
    "ultimo_presupuesto": PRESUPUESTO,
    "carrito_vigente": [
        {"id": "MOU0002", "nombre": "Mouse Logitech M170 Negro", "cantidad": 2},
        {"id": "TAB0001", "nombre": "Tablet Samsung Galaxy Tab A9 Gris",
         "cantidad": 2},
    ],
    "ultima_localidad": "san agustin cordoba",
    "updated_at": datetime.now(timezone.utc),
})
print(f"[ok] pedido vigente sembrado: tienda={TIENDA} user={USER} "
      f"(2 mouse + 2 tablets, $447.000, updated_at ahora)")
