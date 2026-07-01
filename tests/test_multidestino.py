"""
Regresion del multi-destino en calculate_total.

  E13  calculate_total capa los destinos a 3 en silencio (min(destinos, 3)). Un
       pedido a 4 direcciones distintas cobra solo 3 envios; el cuarto viaja
       gratis sin avisar. Comparte raiz con E1 y E5: el sistema no modela varios
       envios a zonas distintas, multiplica una sola tarifa por una cantidad.

Corre offline sobre el doble local (catalogo + FAQ reales), sin LLM ni Google.
"""


def test_e13_no_capa_destinos_en_silencio(firestore_doble):
    """E13: con 4 destinos, el envio se cobra 4 veces, no 3. Hoy se capa en 3
    sin avisar (22500 en vez de 30000 a Cordoba, tarifa fija 7500)."""
    from app.core.tools import calculate_total, get_all_products
    from app.core import estado_venta

    prods = sorted(get_all_products(), key=lambda p: p.get("precio_ars", 0))
    barato = prods[0]
    estado_venta.set_envio_localidad("Cordoba, provincia de Cordoba")

    r = calculate_total(
        items=[{"product_id": barato["id"], "cantidad": 1}],
        items_extra=[{"faq_tema": "costo_envio", "concepto": "x"}],
        destinos=4,
    )
    assert r.get("ok")
    envio = next(e for e in r["extras"] if e["faq_tema"] == "costo_envio")
    assert envio.get("destinos") == 4, (
        "Cuatro destinos deben cobrar 4 envios; hoy se capa a 3 en silencio.")
    assert envio.get("monto") == 7500 * 4, (
        "El envio a 4 destinos a Cordoba es 7500x4=30000; hoy da 7500x3=22500.")
