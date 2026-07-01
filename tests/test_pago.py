"""
AREA: Cobro del cierre — CBU (transferencia) o link de Mercado Pago.

Herramienta del bot cubierta: app/core/pago.py. En modo 'venta' el bot cobra solo:
si el cliente eligio transferencia manda el CBU/alias de la tienda; si eligio
Mercado Pago manda el link. El medio lo decide la FORMA DE PAGO que el cliente ya
dio, no el modelo.

El error que fija esta area: antes el cierre solo sabia mandar el link de Mercado
Pago, asi que un cliente que pagaba por transferencia se quedaba sin datos para
pagar y la venta se demoraba. Estos tests estan escritos para el comportamiento
CORRECTO, asi que HOY fallan (rojo).
"""
import pytest

from app.core import pago


# ── El medio de cobro sale de la forma de pago elegida ───────────────────────
CASOS_MEDIO = [
    ("transferencia", "cbu"),
    ("lo pago por transferencia bancaria", "cbu"),
    ("mercado pago", "mp"),
    ("mp", "mp"),
    ("efectivo", "efectivo"),
    ("", ""),
]


@pytest.mark.parametrize("forma_pago, esperado", CASOS_MEDIO)
def test_elegir_medio_de_cobro(forma_pago, esperado):
    assert pago.elegir_medio_pago(forma_pago) == esperado


# ── El mensaje de transferencia lleva los datos reales de la tienda ──────────

def test_transferencia_arma_mensaje_con_cbu():
    """Con CBU y alias configurados, el cierre por transferencia manda esos datos,
    no se queda mudo demorando la venta."""
    datos = {"cbu": "0000003100010000000001", "alias": "verifika.ventas",
             "titular_cuenta": "Martin Rivero"}
    msg = pago.mensaje_transferencia(datos, monto=1_247_400)
    assert "0000003100010000000001" in msg
    assert "verifika.ventas" in msg
    assert "Martin Rivero" in msg
    assert "1.247.400" in msg  # el monto a transferir, formato argentino


def test_transferencia_sin_datos_no_inventa():
    """El formateador puro sin CBU ni alias devuelve '': no arma un dato falso."""
    assert pago.mensaje_transferencia({}, monto=1000) == ""


def test_transferencia_usa_demo_si_tienda_sin_datos(firestore_doble):
    """Demo: si la tienda no cargo CBU ni alias, datos_transferencia cae a los
    datos de demostracion, asi el bot igual manda la modalidad de transferencia.
    La config real de la tienda los pisa cuando existan."""
    datos = pago.datos_transferencia("verifika_prod")
    assert datos.get("alias"), "debe haber datos de cobro (demo) para mandar la via"
    assert pago.mensaje_transferencia(datos, monto=1000), "el bot manda la modalidad"
