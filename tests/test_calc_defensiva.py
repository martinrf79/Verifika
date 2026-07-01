"""
Regresion de la calculadora defensiva, normalizacion de inputs de calculate_total.

  E5  Varios envios a destinos distintos se colapsan en uno solo. normalizar_inputs
      deja un unico extra costo_envio y descarta el resto, asi un pedido a dos
      direcciones distintas pierde un envio.
"""
from app.core import calc_defensiva


def test_e5_no_colapsa_envios_a_destinos_distintos():
    """E5: dos envios con conceptos distintos (destinos distintos) deben
    sobrevivir la normalizacion, no fusionarse en uno."""
    items = [{"product_id": "A", "cantidad": 1}]
    extras = [
        {"faq_tema": "costo_envio", "concepto": "env_cordoba"},
        {"faq_tema": "costo_envio", "concepto": "env_salta"},
    ]
    _items, extras_norm, err = calc_defensiva.normalizar_inputs(items, extras)
    assert err is None
    envios = [e for e in (extras_norm or []) if e["faq_tema"] == "costo_envio"]
    assert len(envios) == 2, (
        "Dos destinos distintos deben quedar como dos envios; hoy se colapsan.")
