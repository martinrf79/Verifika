"""
Regresion de la captura de datos del cierre (forma de pago y direccion por regex).

  E8   Captura la forma de pago que el cliente RECHAZO: agarra la primera por
       orden de patron, sin mirar la negacion.
  E9   'mp' de megapixeles se toma como Mercado Pago.
  E10  La direccion agarra 'mandar a 4 cuotas' como domicilio.
"""
from app.core import cierre


def test_e8_forma_pago_ignora_la_rechazada():
    """E8: si el cliente rechaza un medio y prefiere otro, se captura el que
    prefiere, no el rechazado."""
    fp = cierre.extraer_forma_pago(
        "no quiero pagar con transferencia, prefiero efectivo")
    assert fp == "efectivo", (
        "Debe capturar 'efectivo' (el elegido), no 'transferencia' (el rechazado).")


def test_e9_mp_de_megapixeles_no_es_mercado_pago():
    """E9: 'mp' como unidad de megapixeles no debe leerse como forma de pago."""
    fp = cierre.extraer_forma_pago("la camara tiene 48 mp de resolucion")
    assert fp == "", "'48 mp' es megapixeles, no Mercado Pago."


def test_e10_direccion_no_captura_cuotas():
    """E10: 'mandar a 4 cuotas' es forma de pago, no un domicilio."""
    d = cierre.extraer_direccion("me lo podes mandar a 4 cuotas?")
    assert d == "", "'4 cuotas' no es una direccion de envio."
