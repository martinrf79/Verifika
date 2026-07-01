"""
Regresion de la guardia de promesas prohibidas (deteccion determinista de texto).

  E3  Deja pasar una fecha de entrega dicha por numero y mes, 'el 25 de junio':
      el patron de dia solo ve formatos tipo 25/6, no el mes en palabra.
  E4  Dispara en falso sobre las negaciones honestas de la propia tienda:
      'no hacemos retiro por local' o 'no hacemos instalacion' se marcan como si
      fueran la promesa, cuando son justo lo contrario.
"""
from app.core import guardia_promesas


def test_e3_detecta_fecha_por_numero_y_mes():
    """E3: 'el 25 de junio' con contexto de llegada es una fecha prometida."""
    clases = guardia_promesas.detectar("te llega el 25 de junio a tu casa")
    assert "dia_entrega" in clases, (
        "Prometer 'el 25 de junio' es prometer una fecha exacta de entrega.")


def test_e4_no_dispara_en_negacion_de_retiro():
    """E4: negar el retiro por local es honesto, no debe marcarse."""
    clases = guardia_promesas.detectar(
        "No tenemos retiro por local, somos solo online")
    assert clases == [], (
        "Negar el retiro es la politica correcta, no una promesa prohibida.")


def test_e4_no_dispara_en_negacion_de_servicio():
    """E4: negar un servicio que no se ofrece es honesto, no debe marcarse."""
    clases = guardia_promesas.detectar(
        "No hacemos instalacion a domicilio, disculpa")
    assert clases == [], (
        "Negar la instalacion es honesto, no una promesa prohibida.")
