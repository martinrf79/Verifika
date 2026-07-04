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


# ── Envio gratis por umbral en multi-destino: POR DESTINO, no por la suma ────
# Bug real (2-jul): 4 destinos chicos que SUMADOS superan el umbral salian
# "todo gratis". El umbral de envio gratis debe mirarse por destino: como los
# items no declaran a que destino van, se usa el promedio (suma/destinos), que
# es conservador: solo libera el envio si el reparto claramente supera el umbral.

def _producto_para_umbral(min_precio, cantidad):
    from app.core.tools import get_all_products
    return next(p for p in sorted(get_all_products(),
                                  key=lambda x: x.get("precio_ars", 0))
                if p.get("precio_ars", 0) > min_precio
                and p.get("stock", 0) >= cantidad)


def test_multidestino_no_regala_envio_por_la_suma(firestore_doble):
    """4 destinos cuya SUMA supera el umbral pero cada destino no: el envio se
    COBRA (4 tarifas), no sale gratis por mirar la suma."""
    from app.core.tools import calculate_total
    from app.core import estado_venta

    p = _producto_para_umbral(min_precio=250000 // 4, cantidad=4)
    estado_venta.set_envio_localidad("Cordoba, provincia de Cordoba")
    r = calculate_total(
        items=[{"product_id": p["id"], "cantidad": 4}],
        items_extra=[{"faq_tema": "costo_envio", "concepto": "x"}],
        destinos=4,
    )
    assert r.get("ok")
    envio = next(e for e in r["extras"] if e["faq_tema"] == "costo_envio")
    assert envio.get("monto", 0) > 0, (
        "Con 4 destinos chicos el envio se cobra por destino; la suma de los "
        "destinos no libera el envio gratis.")


def test_un_destino_sobre_el_umbral_sigue_gratis(firestore_doble):
    """Lock del camino que ya andaba: UN destino cuya compra supera el umbral
    mantiene el envio gratis."""
    from app.core.tools import calculate_total
    from app.core import estado_venta

    p = _producto_para_umbral(min_precio=250000 // 4, cantidad=4)
    estado_venta.set_envio_localidad("Cordoba, provincia de Cordoba")
    r = calculate_total(
        items=[{"product_id": p["id"], "cantidad": 4}],
        items_extra=[{"faq_tema": "costo_envio", "concepto": "x"}],
        destinos=1,
    )
    assert r.get("ok")
    envio = next(e for e in r["extras"] if e["faq_tema"] == "costo_envio")
    assert envio.get("monto") == 0, (
        "Una compra de un destino que supera el umbral va con envio gratis.")


# ── Destinos DISTINTOS cobran cada uno SU tarifa (bug real: se cobraba la ────
# ultima tarifa por todos). Cordoba 7500 + Santa Fe 6000 = 13500, no 12000.

def test_multidestino_tarifas_distintas_suman_cada_una(firestore_doble):
    """Dos destinos en provincias distintas cotizados el mismo turno: el envio
    del total es la SUMA de las dos tarifas reales, no dos veces la ultima."""
    from app.core.tools import calculate_total, cotizar_envio, get_all_products
    from app.core import estado_venta

    estado_venta.set_current_estado({})  # arranca el turno sin arrastre
    q1 = cotizar_envio(localidad="Cordoba, provincia de Cordoba", subtotal=0)
    q2 = cotizar_envio(localidad="Rosario, Santa Fe", subtotal=0)
    assert q1.get("ok") and q2.get("ok")
    esperado = int(q1["monto"]) + int(q2["monto"])
    assert q1["monto"] != q2["monto"], "el caso exige tarifas distintas"

    barato = sorted(get_all_products(), key=lambda p: p.get("precio_ars", 0))[0]
    r = calculate_total(
        items=[{"product_id": barato["id"], "cantidad": 2}],
        items_extra=[{"faq_tema": "costo_envio", "concepto": "x"}],
        destinos=2,
    )
    estado_venta.set_current_estado({})  # no arrastrar localidades a otro test
    assert r.get("ok")
    envio = next(e for e in r["extras"] if e["faq_tema"] == "costo_envio")
    assert envio.get("monto") == esperado, (
        "Cada destino cobra su tarifa real; hoy se cobra la ultima por todos.")
