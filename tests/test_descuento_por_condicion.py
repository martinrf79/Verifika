"""EL DESCUENTO LO DECIDE LA CONDICION DE LA TIENDA, NO UNA LISTA (27-sep-2026).

MEDIDO EN WHATSAPP. "Tarjeta naranja" salio con 10% de descuento, y en la
pregunta compleja el 30% de tarjeta tambien se desconto. La regla vieja de
`pago_split` era "todo lo que no es Mercado Pago lleva el descuento", de cuando
la tienda cobraba solo por transferencia o Mercado Pago. La FAQ dice otra cosa:
el descuento es por "pago por transferencia bancaria".

EL ARREGLO Y NO EL PARCHE. Sumar "naranja" a una lista de excepciones arregla
esa tarjeta y deja la proxima. Ahora el medio lleva descuento si nombra lo que
dice la condicion del descuento en la FAQ de la tienda. Otra tienda que
descuente por efectivo anda sin tocar codigo. Cambio de regla aprobado por
Martin el 27-sep.
"""
import pytest

from app.core.pago_split import calcular_split

TRANSF = "pago por transferencia bancaria"


def _final(pago, condicion=TRANSF):
    r = calcular_split(100000, pago, 10, condicion)
    assert r["ok"]
    return {p["medio"]: p["monto_final_ars"] for p in r["partes"]}, r["total_final_ars"]


@pytest.mark.parametrize("medio", ["Tarjeta Naranja", "tarjeta", "Visa", "Mercado Pago",
                                   "mercado_pago", "Uala", "cripto"])
def test_lo_que_no_es_la_condicion_no_lleva_descuento(medio):
    assert _final([{"medio": medio, "porcentaje": 100}])[1] == 100000


@pytest.mark.parametrize("medio", ["transferencia", "Transferencia bancaria", "Efectivo/Transferencia"])
def test_lo_que_nombra_la_condicion_lleva_descuento(medio):
    assert _final([{"medio": medio, "porcentaje": 100}])[1] == 90000


def test_el_setenta_treinta_con_tarjeta_descuenta_solo_la_transferencia():
    partes, total = _final([{"medio": "transferencia", "porcentaje": 70},
                            {"medio": "Tarjeta", "porcentaje": 30}])
    assert partes == {"transferencia": 63000, "Tarjeta": 30000} and total == 93000


def test_otra_tienda_con_otra_condicion_no_toca_codigo():
    partes, _ = _final([{"medio": "efectivo", "porcentaje": 50},
                        {"medio": "transferencia", "porcentaje": 50}], "pago en efectivo en el local")
    assert partes == {"efectivo": 45000, "transferencia": 50000}


def test_sin_condicion_escrita_no_se_inventa_un_descuento():
    assert _final([{"medio": "transferencia", "porcentaje": 100}], "")[1] == 100000


def test_la_cuenta_del_agente_con_tarjeta_naranja_no_descuenta(firestore_doble):
    from app.core import agente as A
    from app.core.contexto_turno import set_current_tienda
    set_current_tienda("verifika_prod")
    c = A.h_cuenta("verifika_prod", [{"producto": "GPU0001", "cantidad": 1}],
                   reparto_pago=[{"medio": "Tarjeta Naranja", "porcentaje": 100}])["cuenta"]
    assert c["total_final_ars"] == c["total_ars"]
