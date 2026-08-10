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


# ── EL ERROR DE PLATA DEL 10-AGO: SE COBRABA EL TOTAL POR CADA MEDIO ─────────
# Leido del WhatsApp real de Martin. Pidio el pago 65% transferencia y 35%
# Mercado Pago, la cuenta lo repartio bien, y abajo -en los datos para
# transferir- el bot le puso "Monto: $225.000". Le pidio el TOTAL ENTERO por
# transferencia: 71% de mas sobre lo que le correspondia, y ademas mas que el
# total final de $210.375.
#
# La causa no era el reparto, que estaba bien calculado: era que el cobro se
# armaba con `extraer_total_verificado`, que lee la ultima linea "Total" y no
# sabe nada del reparto. Dos modulos correctos y nadie mirando al otro.

CUENTA_CON_SPLIT = (
    "Presupuesto:\n"
    "- 2x Auriculares Redragon Zeus X Blanco: $57.500 c/u = $115.000\n"
    "- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000\n"
    "- 2x Memoria ram Kingston Fury Beast: $34.500 c/u = $69.000\n"
    "Subtotal: $201.000\n"
    "Envio (3 envios): $24.000\n"
    "Total: $225.000\n"
    "\n"
    "Pago dividido:\n"
    "- transferencia (65%): $146.250 - 10% descuento = $131.625\n"
    "- mercado pago (35%): $78.750\n"
    "Total final: $210.375"
)


def test_la_transferencia_cobra_SU_parte_y_no_el_total():
    """El caso exacto de Martin: $131.625, no $225.000."""
    from app.core.pago import monto_a_cobrar

    assert monto_a_cobrar(CUENTA_CON_SPLIT, "cbu") == 131625


def test_el_link_de_mercado_pago_cobra_SU_parte():
    """El mismo error, del otro lado del reparto."""
    from app.core.pago import monto_a_cobrar

    assert monto_a_cobrar(CUENTA_CON_SPLIT, "mp") == 78750


def test_lo_que_se_cobra_por_los_dos_medios_SUMA_el_total_final():
    """LA INVARIANTE QUE IMPORTA, y la que estaba rota: la plata que se le pide
    al cliente tiene que ser exactamente la que dice la cuenta. Antes se le
    pedia $225.000 por cada via, o sea $450.000 por un pedido de $210.375."""
    from app.core.pago import extraer_total_verificado, monto_a_cobrar

    cobrado = (monto_a_cobrar(CUENTA_CON_SPLIT, "cbu")
               + monto_a_cobrar(CUENTA_CON_SPLIT, "mp"))
    assert cobrado == extraer_total_verificado(CUENTA_CON_SPLIT) == 210375


def test_con_descuento_se_cobra_lo_de_DESPUES_del_descuento():
    """El renglon trae dos numeros: $146.250 antes y $131.625 despues. Se cobra
    el de despues; cobrar el de antes es no darle el descuento prometido."""
    from app.core.pago import montos_por_medio

    assert montos_por_medio(CUENTA_CON_SPLIT)["transferencia"] == 131625


def test_sin_pago_dividido_no_cambia_nada():
    """La salvaguarda: sin reparto se sigue cobrando el total, como siempre."""
    from app.core.pago import monto_a_cobrar

    simple = ("Presupuesto:\n- 1x Mouse Genius: $8.500 c/u = $8.500\n"
              "Envio: $7.000\nTotal: $15.500")
    assert monto_a_cobrar(simple, "cbu") == 15500
    assert monto_a_cobrar(simple, "mp") == 15500


def test_el_total_FINAL_le_gana_al_total_de_arriba():
    """Cuando hay descuento hay dos totales. El que se cobra es el final: el de
    arriba es el de antes del descuento y cobrarlo es cobrar de mas."""
    from app.core.pago import extraer_total_verificado

    assert extraer_total_verificado(CUENTA_CON_SPLIT) == 210375


def test_un_total_en_rango_sigue_sin_cobrarse():
    """No se adivina el monto de un cobro: es la regla vieja y no se afloja."""
    from app.core.pago import monto_a_cobrar

    rango = "Presupuesto:\n- 1x Mouse: $8.500\nTotal: entre $15.500 y $18.000"
    assert monto_a_cobrar(rango, "cbu") is None
