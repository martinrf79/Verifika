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


# ── ENTREGA DE DATOS DE COBRO A PEDIDO (charla real 20-jul) ──────────────────

def test_pasame_los_enlaces_entrega_el_cobro(monkeypatch, firestore_doble):
    """'Pasame los enlaces' con presupuesto sobre la mesa -> CBU demo + link
    generico de Mercado Pago, en cualquier modo."""
    import asyncio
    from app.core import leads as L
    monkeypatch.setattr(L, "get_lead_activo",
                        lambda user_id, canal, tienda_id: None)
    monkeypatch.setattr(L, "modo_cierre", lambda tid: "lead")
    _, meta = asyncio.new_event_loop().run_until_complete(
        L.procesar_mensaje_para_lead(
            user_id="u1", canal="whatsapp", tienda_id="verifika_prod",
            mensaje="Pasame los enlaces", respuesta_solver="",
            trace_id="t1", interpretacion={"intencion": "aporta_dato",
                                           "confianza": 0.9},
            presupuesto="Presupuesto:\n- 1x Mouse: $8.500\nTotal: $8.500"))
    assert meta["accion"] == "cobro_datos"
    r = meta["respuesta_directa"]
    assert "CBU" in r or "Alias" in r
    assert "mpago" in r or "Mercado Pago" in r


def test_pregunta_de_datos_de_producto_no_entrega_cobro(monkeypatch,
                                                        firestore_doble):
    """'quiero los datos del producto' NO es pedir el cobro."""
    from app.core.leads import _RE_PIDE_COBRO
    assert not _RE_PIDE_COBRO.search("quiero los datos del producto")
    assert _RE_PIDE_COBRO.search("pasame los enlaces")
    assert _RE_PIDE_COBRO.search("dame el cbu")
    assert _RE_PIDE_COBRO.search("mandame el link de pago")
    assert _RE_PIDE_COBRO.search("datos para transferir")
