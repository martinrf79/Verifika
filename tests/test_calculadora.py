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

def test_e13_destinos_sin_cotizar_ni_se_capan_ni_se_duplican(firestore_doble):
    """E13 v2 (8-jul): con 4 destinos declarados y UNA sola localidad cotizada,
    antes se rellenaba duplicando la ultima tarifa; eso COBRO DE MAS en real
    (caso mudanza: "mandalo todo a Salta" + destinos=2 del solver = dos envios
    de $9.000). Ahora la calculadora ni capa en silencio ni inventa: devuelve
    ok False pidiendo cotizar cada destino."""
    from app.core.tools import calculate_total, get_all_products
    from app.core import estado_venta

    prods = sorted(get_all_products(), key=lambda p: p.get("precio_ars", 0))
    barato = prods[0]
    estado_venta._envio_localidades.set([])
    estado_venta.set_envio_localidad("Cordoba, provincia de Cordoba")
    try:
        r = calculate_total(
            items=[{"product_id": barato["id"], "cantidad": 1}],
            items_extra=[{"faq_tema": "costo_envio", "concepto": "x"}],
            destinos=4,
        )
        assert r.get("ok") is False
        assert "cotiza" in r["mensaje_para_llm"].lower()
        assert "4" in r["mensaje_para_llm"]
    finally:
        estado_venta._envio_localidades.set([])


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
    estado_venta._envio_localidades.set([])
    for loc in ("Cordoba, provincia de Cordoba", "Rio Tercero, cordoba",
                "Tancacha, cordoba", "Los Condores, cordoba"):
        estado_venta.set_envio_localidad(loc)
    try:
        r = calculate_total(
            items=[{"product_id": p["id"], "cantidad": 4}],
            items_extra=[{"faq_tema": "costo_envio", "concepto": "x"}],
            destinos=4,
        )
        assert r.get("ok")
        envio = next(e for e in r["extras"] if e["faq_tema"] == "costo_envio")
        assert envio.get("monto", 0) > 0, (
            "Con 4 destinos chicos el envio se cobra por destino; la suma de "
            "los destinos no libera el envio gratis.")
    finally:
        estado_venta._envio_localidades.set([])


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


def test_multidestino_recuerda_destinos_de_turnos_anteriores(firestore_doble):
    """'Y el total de todo?' UN TURNO DESPUES de cotizar dos destinos: las
    localidades ya cotizadas viajan en el estado (memoria del pedido) y
    calculate_total las usa sin volver a pedir el CP. Visto en el banco: el bot
    re-pedia el codigo postal de Cordoba que el cliente ya habia dado."""
    from app.core.tools import calculate_total, cotizar_envio, get_all_products
    from app.core import estado_venta

    # Turno 1: se cotizan los dos destinos (esto llena las localidades del turno).
    estado_venta.set_current_estado({})
    q1 = cotizar_envio(localidad="Cordoba, provincia de Cordoba", subtotal=0)
    q2 = cotizar_envio(localidad="Rosario, Santa Fe", subtotal=0)
    assert q1.get("ok") and q2.get("ok")
    esperado = int(q1["monto"]) + int(q2["monto"])
    locs_memoria = estado_venta.get_envio_localidades()
    assert len(locs_memoria) == 2

    # Turno 2: contexto NUEVO (set_current_estado limpia las localidades del
    # turno), pero el estado trae los destinos persistidos de la conversacion.
    estado_venta.set_current_estado({"localidades_envio": locs_memoria})
    assert estado_venta.get_envio_localidades() == []
    barato = sorted(get_all_products(), key=lambda p: p.get("precio_ars", 0))[0]
    r = calculate_total(
        items=[{"product_id": barato["id"], "cantidad": 2}],
        items_extra=[{"faq_tema": "costo_envio", "concepto": "x"}],
        destinos=2,
    )
    estado_venta.set_current_estado({})
    assert r.get("ok"), "con destinos en memoria no puede pedir el CP de nuevo"
    envio = next(e for e in r["extras"] if e["faq_tema"] == "costo_envio")
    assert envio.get("monto") == esperado



def test_carrito_vigente_rechaza_id_inferido_de_memoria(firestore_doble):
    """REGLA CERO mecanica: con pedido vigente, un product_id que no sale del
    carrito, ni de lo mostrado, ni de una tool del turno se rechaza con la
    instruccion del pedido real (banco: el solver pidio el total con el
    NX-7000 cuando el carrito era el DX-110)."""
    from app.core.tools import calculate_total
    from app.core import estado_venta

    estado_venta.set_current_estado({"carrito": [
        {"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro", "cantidad": 2}]})
    r = calculate_total(items=[{"product_id": "MOU0049", "cantidad": 2}])
    estado_venta.set_current_estado({})
    assert r.get("ok") is False
    assert "MOU0049" in r["mensaje_para_llm"]
    assert "MOU0023" in r["mensaje_para_llm"]


def test_carrito_vigente_acepta_id_certificado_del_turno(firestore_doble):
    """El mismo id pasa si una tool del turno lo devolvio (certificado)."""
    from app.core.tools import calculate_total, get_product_details
    from app.core import estado_venta
    from app.core.estado_venta import certificar_ids_de_resultado

    estado_venta.set_current_estado({"carrito": [
        {"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro", "cantidad": 2}]})
    certificar_ids_de_resultado(get_product_details(product_id="MOU0049"))
    r = calculate_total(items=[{"product_id": "MOU0049", "cantidad": 1}])
    estado_venta.set_current_estado({})
    assert r.get("ok") is True


def test_carrito_vigente_acepta_ids_del_propio_carrito(firestore_doble):
    from app.core.tools import calculate_total
    from app.core import estado_venta

    estado_venta.set_current_estado({"carrito": [
        {"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro", "cantidad": 2}]})
    r = calculate_total(items=[{"product_id": "MOU0023", "cantidad": 2}])
    estado_venta.set_current_estado({})
    assert r.get("ok") is True
    assert r["total_ars"] == 17000


def test_sin_carrito_no_se_restringe(firestore_doble):
    """Primer turno sin pedido vigente: el flujo normal no se toca."""
    from app.core.tools import calculate_total
    from app.core import estado_venta

    estado_venta.set_current_estado({})
    r = calculate_total(items=[{"product_id": "MOU0049", "cantidad": 1}])
    estado_venta.set_current_estado({})
    assert r.get("ok") is True


def test_mudanza_destinos_de_mas_no_duplican_tarifa(firestore_doble):
    # Caso mudanza (banco 8-jul): tras "mandalo todo a Salta" la memoria tiene
    # UN destino, pero el solver mando destinos=2 y el total cobro DOS envios
    # de $9.000. Ahora se rechaza pidiendo cotizar; con destinos=1 sale bien.
    from app.core.estado_venta import set_current_estado
    from app.core import estado_venta
    from app.core.tools import calculate_total
    from app.core.tools_context import set_current_tienda
    set_current_tienda("verifika_prod")
    estado_venta._envio_localidades.set([])
    set_current_estado({"carrito": [], "productos_vistos": [],
                        "localidades_envio": ["Salta capital, salta"]})
    try:
        inflado = calculate_total(
            items=[{"product_id": "MOU0023", "cantidad": 1},
                   {"product_id": "TEC0030", "cantidad": 1}],
            items_extra=[{"faq_tema": "costo_envio", "concepto": "envio"}],
            destinos=2)
        assert inflado["ok"] is False
        assert "cotiza" in inflado["mensaje_para_llm"].lower()
        bien = calculate_total(
            items=[{"product_id": "MOU0023", "cantidad": 1},
                   {"product_id": "TEC0030", "cantidad": 1}],
            items_extra=[{"faq_tema": "costo_envio", "concepto": "envio"}],
            destinos=1)
        assert bien["ok"] is True
        assert bien["total_ars"] == 8500 + 14500 + 9000  # UN envio a Salta
    finally:
        set_current_estado({})


def test_destino_unico_no_cobra_el_destino_obsoleto(firestore_doble):
    # Mudanza (banco 8-jul): con destino_unico sticky ("mandalo todo a Salta"),
    # aunque el solver re-cotice Mendoza desde el historial, el envio se cobra
    # UNA vez y al destino de la memoria (Salta), no al obsoleto.
    from app.core.estado_venta import set_current_estado
    from app.core import estado_venta
    from app.core.tools import calculate_total
    from app.core.tools_context import set_current_tienda
    set_current_tienda("verifika_prod")
    estado_venta._envio_localidades.set([])
    set_current_estado({"carrito": [], "productos_vistos": [],
                        "destino_unico": True,
                        "localidades_envio": ["Salta capital, salta"]})
    try:
        # El solver cotizo Salta Y el obsoleto Mendoza en el mismo turno.
        estado_venta.set_envio_localidad("Salta capital, salta")
        estado_venta.set_envio_localidad("Mendoza, mendoza")
        r = calculate_total(
            items=[{"product_id": "MOU0023", "cantidad": 1}],
            items_extra=[{"faq_tema": "costo_envio", "concepto": "envio"}],
            destinos=2)
        assert r["ok"] is True
        assert r["total_ars"] == 8500 + 9000  # UN envio, tarifa de Salta
    finally:
        estado_venta._envio_localidades.set([])
        set_current_estado({})
