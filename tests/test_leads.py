"""
Regresion de la captura de telefono en leads.

  E11  El regex generico captura cualquier numero de 8 a 13 digitos, asi un DNI
       o un numero de comprobante se guardan como si fueran un telefono.
"""
from app.core import leads


def test_e11_dni_no_es_telefono():
    """E11: un DNI de 8 digitos no debe capturarse como telefono."""
    assert leads.extraer_telefono("mi dni es 12345678") == "", (
        "Un DNI no es un telefono de contacto.")


def test_e11_comprobante_no_es_telefono():
    """E11: un numero de comprobante largo tampoco es un telefono."""
    assert leads.extraer_telefono("el comprobante numero 4837261900") == "", (
        "Un numero de comprobante no es un telefono de contacto.")
