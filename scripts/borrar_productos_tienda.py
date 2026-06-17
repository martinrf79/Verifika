"""
Borra TODOS los productos de una tienda en Firestore. Pensado para dar de baja
el catalogo de una tienda de prueba (ej verifika_demo, desacoplada el 10-jun-2026
porque medir contra 50 productos no representa la escala real). Los datos
locales en data/clientes/<tienda>/ NO se tocan: con scripts/crear_cliente.py se
recargan cuando haga falta.

Uso (pide el nombre EXACTO de la tienda como confirmacion):
    python scripts/borrar_productos_tienda.py verifika_demo
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.storage.firestore_client import _tienda_ref, get_all_products

if len(sys.argv) != 2:
    print("Uso: python scripts/borrar_productos_tienda.py <tienda_id>")
    sys.exit(1)

tienda = sys.argv[1]
productos = get_all_products(tienda_id=tienda, force_refresh=True)
print(f"Tienda {tienda}: {len(productos)} productos en Firestore")
if not productos:
    print("Nada que borrar.")
    sys.exit(0)

ref = _tienda_ref(tienda).collection("productos")
borrados = 0
for doc in ref.stream():
    doc.reference.delete()
    borrados += 1
print(f"Borrados {borrados} productos de {tienda}. "
      f"Recargables desde data/clientes/{tienda}/ con crear_cliente.py")
