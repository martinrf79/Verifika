"""
AREA: Cierre — captura de datos del cliente por regex (forma de pago, direccion).

Herramientas del bot cubiertas: extraer_forma_pago y extraer_direccion
(app/core/cierre.py).

PATRON DE ESTA AREA (plantilla del proyecto): los casos viven en una TABLA, no en
funciones repetidas. Agregar una forma nueva vista en WhatsApp es agregar una
FILA, no un archivo. Cada fila es (mensaje, esperado, id). Las que hoy fallan son
los errores confirmados; las que hoy pasan son locks que protegen lo que anda.

Errores sembrados:
  E8   Captura la forma de pago RECHAZADA en vez de la elegida.
  E9   'mp' de megapixeles se toma como Mercado Pago.
  E10  La direccion agarra 'mandar a 4 cuotas' como domicilio.
"""
import pytest

from app.core import cierre


# ── Forma de pago: (mensaje, forma esperada) ────────────────────────────────
CASOS_FORMA_PAGO = [
    # Errores confirmados (hoy ROJO):
    ("no quiero pagar con transferencia, prefiero efectivo", "efectivo"),  # E8
    ("la camara tiene 48 mp de resolucion", ""),                          # E9
    # Locks de camino feliz (hoy VERDE): protegen lo que funciona.
    ("lo pago con transferencia", "transferencia"),
    ("pago en efectivo", "efectivo"),
    ("con mercado pago", "mercado pago"),
]


@pytest.mark.parametrize("mensaje, esperado", CASOS_FORMA_PAGO)
def test_forma_pago(mensaje, esperado):
    assert cierre.extraer_forma_pago(mensaje) == esperado


# ── Direccion: (mensaje, fragmento esperado o "" si no debe capturar) ────────
CASOS_DIRECCION = [
    # Error confirmado (hoy ROJO): 'cuotas' no es un domicilio.
    ("me lo podes mandar a 4 cuotas?", ""),  # E10
    # Locks de camino feliz (hoy VERDE): una direccion real se captura.
    ("envio a la calle San Martin 1234, Cordoba", "1234"),
    ("mi casa es Av Colon 850", "850"),
]


@pytest.mark.parametrize("mensaje, fragmento", CASOS_DIRECCION)
def test_direccion(mensaje, fragmento):
    r = cierre.extraer_direccion(mensaje)
    if fragmento == "":
        assert r == "", "No debe capturar un domicilio donde no lo hay."
    else:
        assert fragmento in r, f"Debe capturar la direccion (contiene {fragmento})."
