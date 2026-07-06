"""
AREA: SPLIT DE PAGO — una función genérica cubre cualquier reparto.

Lockea calcular_split: reparte el total entre medios con cualquier porcentaje,
aplica el 10% a todo lo que no es Mercado Pago, y cierra la suma exacta. Verifica
además que reproduce la cuenta CORRECTA de la charla real del 6-jul (donde el bot
la hizo a mano y dio mal). Lógica pura, sin LLM ni Firestore.
"""
from app.core.pago_split import calcular_split, es_mercado_pago, render_split


def test_reproduce_la_cuenta_correcta_de_la_charla():
    # Charla 6-jul: base $1.677.000 (productos, envío gratis), 50% transferencia /
    # 50% MP. El bot dio $1.617.375 a mano (mal, cobró envío). El correcto es:
    s = calcular_split(1_677_000, [
        {"medio": "transferencia", "porcentaje": 50},
        {"medio": "mercado pago", "porcentaje": 50},
    ], pct_descuento=10)
    assert s["ok"]
    transf = s["partes"][0]
    mp = s["partes"][1]
    assert transf["monto_ars"] == 838_500
    assert transf["monto_final_ars"] == 754_650   # con 10% off
    assert mp["monto_ars"] == 838_500
    assert mp["descuento_ars"] == 0               # MP no lleva descuento
    assert s["total_final_ars"] == 1_593_150


def test_cualquier_reparto_70_30():
    s = calcular_split(1_000_000, [
        {"medio": "transferencia", "porcentaje": 70},
        {"medio": "mercado pago", "porcentaje": 30},
    ], pct_descuento=10)
    assert s["partes"][0]["monto_ars"] == 700_000
    assert s["partes"][0]["monto_final_ars"] == 630_000
    assert s["partes"][1]["monto_ars"] == 300_000
    assert s["total_final_ars"] == 1_000_000 - 70_000


def test_tres_medios_suma_cierra_exacta():
    s = calcular_split(1_000_000, [
        {"medio": "transferencia", "porcentaje": 33},
        {"medio": "uala", "porcentaje": 33},
        {"medio": "mercado pago", "porcentaje": 34},
    ], pct_descuento=10)
    assert s["ok"]
    assert sum(p["monto_ars"] for p in s["partes"]) == 1_000_000  # cierra exacto


def test_uala_cuenta_como_transferencia():
    assert not es_mercado_pago("uala")
    assert not es_mercado_pago("transferencia bancaria")
    assert es_mercado_pago("Mercado Pago")
    assert es_mercado_pago("mercadopago")
    s = calcular_split(100_000, [{"medio": "uala", "porcentaje": 100}],
                       pct_descuento=10)
    assert s["partes"][0]["descuento_ars"] == 10_000  # uala lleva descuento


def test_porcentajes_no_suman_100_rechaza():
    s = calcular_split(100_000, [
        {"medio": "transferencia", "porcentaje": 40},
        {"medio": "mercado pago", "porcentaje": 40},
    ], pct_descuento=10)
    assert not s["ok"]


def test_base_invalida_rechaza():
    assert not calcular_split(0, [{"medio": "x", "porcentaje": 100}], 10)["ok"]
    assert not calcular_split(1000, [], 10)["ok"]


def test_render_muestra_descuento_solo_en_transferencia():
    s = calcular_split(1_000_000, [
        {"medio": "transferencia", "porcentaje": 50},
        {"medio": "mercado pago", "porcentaje": 50},
    ], pct_descuento=10)
    txt = render_split(s)
    assert "descuento" in txt.lower()
    assert "Total final: $950.000" in txt


def test_calculate_total_con_split_integrado(firestore_doble):
    """La calculadora dueña TODA la cuenta del pedido real de la charla 6-jul:
    productos + split 50/50, descuento del 10% de la FAQ a la parte que no es
    Mercado Pago. El solver no calcula nada, pasa 'pago' y recibe el bloque."""
    from app.core.tools import calculate_total
    from app.core.estado_venta import set_current_estado, construir_estado
    set_current_estado(construir_estado({}, None))
    items = [{"product_id": "NOT0065", "cantidad": 2},
             {"product_id": "TEC0015", "cantidad": 2},
             {"product_id": "AUR0003", "cantidad": 2}]
    r = calculate_total(items=items, pago=[
        {"medio": "transferencia", "porcentaje": 50},
        {"medio": "mercado pago", "porcentaje": 50}])
    assert r["ok"]
    assert r["total_final_ars"] == 1_593_150   # NO el $1.617.375 que dio a mano
    assert "Total final: $1.593.150" in r["presentacion"]
    assert r["proof"]["tipo"] == "calculo_total_split_pago"


def test_split_no_duplica_descuento_si_solver_pasa_extra(firestore_doble):
    """Si el solver pasa ademas un items_extra de descuento_transferencia junto
    con 'pago', el split lo saca para no aplicar el descuento dos veces."""
    from app.core.tools import calculate_total
    from app.core.estado_venta import set_current_estado, construir_estado
    set_current_estado(construir_estado({}, None))
    items = [{"product_id": "TEC0015", "cantidad": 1}]  # $36.000
    r = calculate_total(
        items=items,
        items_extra=[{"faq_tema": "descuento_transferencia",
                      "concepto": "descuento_transferencia"}],
        pago=[{"medio": "transferencia", "porcentaje": 100}])
    assert r["ok"]
    # 100% transferencia: 36.000 - 10% = 32.400, UNA sola vez.
    assert r["total_final_ars"] == 32_400
