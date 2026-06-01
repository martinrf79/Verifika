"""
Script de carga inicial a Firestore.

Uso:
    cd ~/agente-firestore
    python scripts/cargar_firestore.py

Carga:
- 100 productos desde data/productos.json
- 8 temas de FAQ
- Genera embeddings de cada producto (opcional, controlado por env var)

Idempotente: podés correrlo varias veces, sobrescribe sin duplicar.
"""
import json
import os
import sys
import time

# Importar desde el paquete app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.storage.firestore_client import (
    upsert_product,
    upsert_faq,
    set_config,
)
from app.storage.embeddings import generate_product_embedding


GENERATE_EMBEDDINGS = os.getenv("GENERATE_EMBEDDINGS", "false").lower() == "true"


# ────────────────────────────────────────────────────────────
# FAQ — 8 temas iniciales
# ────────────────────────────────────────────────────────────

FAQ = {
    "envios": {
        "keywords": ["envío", "envio", "envían", "envian", "mandan", "interior",
                     "ciudad", "domicilio", "entrega", "llega", "correo"],
        "respuesta": (
            "Hacemos envíos a todo el país por correo (Andreani / OCA). "
            "Capital y GBA: 24-48hs hábiles. Interior: 3-7 días hábiles. "
            "El costo se calcula al confirmar la compra."
        ),
    },
    "pago": {
        "keywords": ["pago", "pagar", "tarjeta", "efectivo", "transferencia",
                     "mercado pago", "mercadopago", "cuotas", "débito", "crédito"],
        "respuesta": (
            "Aceptamos: transferencia bancaria, Mercado Pago (tarjetas crédito/débito), "
            "y efectivo en local con cita. Hasta 3 cuotas sin interés con tarjetas seleccionadas."
        ),
    },
    "garantia": {
        "keywords": ["garantía", "garantia", "rotura", "falla", "defecto", "se rompe"],
        "respuesta": (
            "Todos nuestros productos tienen 6 meses de garantía oficial. "
            "Ante cualquier falla, contactanos."
        ),
    },
    "devolucion": {
        "keywords": ["devolución", "devolucion", "devolver", "cambio",
                     "arrepentido", "arrepentir"],
        "respuesta": (
            "Tenés 10 días corridos desde la recepción para devolver el producto, "
            "siempre que esté en empaque original sin uso. "
            "Reintegro por el mismo medio de pago."
        ),
    },
    "horarios": {
        "keywords": ["horario", "horarios", "abren", "atienden", "disponible",
                     "atención", "atencion"],
        "respuesta": (
            "Atendemos por chat de lunes a viernes de 9 a 19 hs. "
            "Sábados de 9 a 13 hs."
        ),
    },
    "ubicacion": {
        "keywords": ["dirección", "direccion", "local", "dónde están", "donde estan",
                     "sucursal", "ubicación", "ubicacion", "retirar"],
        "respuesta": (
            "Trabajamos online con envío a todo el país. "
            "Para retirar en persona, coordinamos un punto en CABA con cita."
        ),
    },
    "factura": {
        "keywords": ["factura", "comprobante", "iva", "responsable inscripto"],
        "respuesta": (
            "Emitimos factura A o B según corresponda. "
            "Indicanos tus datos fiscales al confirmar la compra."
        ),
    },
    "stock": {
        "keywords": ["disponibilidad general", "tenes stock", "tenés stock"],
        "respuesta": (
            "Sí, tenemos stock disponible. "
            "Para confirmar unidades exactas, consultá por el modelo que te interesa."
        ),
    },
}


def cargar_faq():
    print("\n=== Cargando FAQ ===")
    for tema_id, data in FAQ.items():
        upsert_faq(tema_id, data)
        print(f"  ✓ {tema_id}")
    print(f"FAQ cargada: {len(FAQ)} temas")


def cargar_productos(productos_path: str):
    print(f"\n=== Cargando productos desde {productos_path} ===")
    with open(productos_path, "r", encoding="utf-8") as f:
        productos = json.load(f)

    total = len(productos)
    print(f"Total a cargar: {total}")
    if GENERATE_EMBEDDINGS:
        print("Generando embeddings (puede tardar varios minutos)...")
    else:
        print("Sin embeddings (usar GENERATE_EMBEDDINGS=true para activar)")

    cargados = 0
    embeddings_ok = 0
    for i, p in enumerate(productos, 1):
        # Generar embedding si está activado
        if GENERATE_EMBEDDINGS:
            try:
                emb = generate_product_embedding(p)
                if emb:
                    p["embedding"] = emb
                    embeddings_ok += 1
            except Exception as e:
                print(f"  ! Error embedding {p['id']}: {str(e)[:60]}")

        # Cargar a Firestore
        try:
            upsert_product(p["id"], p)
            cargados += 1
            if i % 10 == 0:
                print(f"  {i}/{total} cargados...")
        except Exception as e:
            print(f"  ! Error cargando {p['id']}: {str(e)[:60]}")

    print(f"\n  ✓ Productos cargados: {cargados}/{total}")
    if GENERATE_EMBEDDINGS:
        print(f"  ✓ Con embeddings: {embeddings_ok}/{total}")


def cargar_config():
    print("\n=== Configuración inicial del negocio ===")
    set_config("nombre", "Tienda Tecno")
    set_config("contacto_humano", "Si necesitás hablar con un humano, escribinos a contacto@tiendatecno.com")
    print("  ✓ config básica cargada")


def main():
    productos_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "productos.json"
    )

    print("══════════════════════════════════════════")
    print("  CARGA INICIAL FIRESTORE")
    print("══════════════════════════════════════════")
    print(f"Tienda: {os.getenv('TIENDA_ID', 'tienda_principal')}")
    print(f"Proyecto GCP: {os.getenv('GCP_PROJECT', 'memory-engine-v1')}")
    print(f"Embeddings: {'SÍ' if GENERATE_EMBEDDINGS else 'NO'}")

    t0 = time.time()
    cargar_config()
    cargar_faq()
    cargar_productos(productos_path)
    elapsed = time.time() - t0

    print(f"\n✓ Carga completada en {elapsed:.1f}s")


if __name__ == "__main__":
    main()
