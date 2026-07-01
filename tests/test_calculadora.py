"""
AREA: Calculadora y total del pedido.

Herramientas del bot cubiertas: calculate_total (app/core/tools.py) y su capa
defensiva de normalizacion (app/core/calc_defensiva.py).

Casos sembrados desde errores reales confirmados:
  E5   Varios envios a destinos distintos se colapsan en uno solo.
  E13  calculate_total capa los destinos a 3 en silencio; el cuarto viaja gratis.

Ambos comparten raiz: el sistema no modela varios envios a zonas distintas,
multiplica una sola tarifa por una cantidad. Se apagan cuando se rehace el
multi-destino de verdad.
"""
from app.core import calc_defensiva


# ── E5: normalizacion de inputs ─────────────────────────────────────────────

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


# ── Camino feliz: lo que SI funciona, para que un arreglo no lo rompa ────────

def test_normaliza_fusiona_mismo_producto_dos_lineas():
    """Lock: el mismo product_id en dos lineas se fusiona sumando cantidades.
    Comportamiento correcto de hoy; este test lo protege."""
    items = [{"product_id": "A", "cantidad": 1}, {"product_id": "A", "cantidad": 2}]
    items_norm, _extra, err = calc_defensiva.normalizar_inputs(items, None)
    assert err is None
    assert len(items_norm) == 1 and items_norm[0]["cantidad"] == 3


def test_normaliza_rechaza_cantidad_cero():
    """Lock: una cantidad cero o negativa se rechaza con error claro."""
    items = [{"product_id": "A", "cantidad": 0}]
    _i, _e, err = calc_defensiva.normalizar_inputs(items, None)
    assert err is not None


# ── E13: multi-destino, corre sobre el doble local (sin LLM ni Google) ───────

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
