"""EL PRESUPUESTO, EL REPARTO Y EL COBRO DEL AGENTE — lo que fallo en WhatsApp el 30-oct, despues del deploy (FICHA 83).

  "Teclado (a definir)"    un renglon que no es un producto exacto trababa el pedido entero: sin envios, sin total,
                           sin el 70/30, y el cliente leia "¿Cuáles son Teclado (a definir)?".
  "setenta treinta"        el modelo le ponia transferencia y Mercado Pago, y la transferencia llevaba un descuento que
                           nadie eligio. Ahora el reparto se muestra sin medio y el medio se pregunta.
  "no tengo MP"            el cobro salia con el link de Mercado Pago por defecto y no habia como cambiarlo.
"""
import asyncio

import pytest

from banco_pruebas import clon_produccion as C

PEDIDO = [{"producto": "Mouse Logitech M220 Silent Negro", "destino": "Concordia"},
          {"producto": "Auriculares HyperX Cloud Stinger 2 Negro", "destino": "Posadas"}]


@pytest.fixture(scope="module")
def A():
    C.instalar()
    from app.core.flujo import agente
    return agente


def test_un_renglon_que_no_es_producto_no_traba_el_pedido(A):
    a = {"renglones": PEDIDO + [{"producto": "Teclado (a definir)", "destino": "Concordia"}]}
    cliente, nota = A.presupuesto(a, A.memoria_de({}), C.TIENDA, None, "")
    assert "Total general" in cliente and "Envio a Posadas" in cliente
    assert "a definir" not in cliente and "Teclado (a definir)" in nota


def test_el_reparto_no_inventa_medios_y_se_muestra(A):
    a = {"renglones": PEDIDO, "pago": "70 transferencia, 30 mercado pago"}
    cliente, _ = A.presupuesto(a, A.memoria_de({}), C.TIENDA, None, "dividilo en setenta treinta")
    assert "(70%)" in cliente and "(30%)" in cliente and "descuento =" not in cliente
    assert "¿Con qué medio pagás cada parte" in cliente
    dicho, _ = A.presupuesto(a, A.memoria_de({}), C.TIENDA, None, "70 por transferencia y 30 con mercado pago")
    assert "transferencia (70%)" in dicho and "descuento =" in dicho


def test_sin_medio_no_se_cobra_y_el_medio_dicho_si(A):
    m = A.memoria_de({})
    m["pedido"] = PEDIDO
    cliente, nota = asyncio.run(A.cobrar({"nombre": "Joaquin"}, m, "u", "telegram", C.TIENDA, "t", "joaquin"))
    assert not cliente and "medio" in nota
    cliente, _ = asyncio.run(A.cobrar({"nombre": "Joaquin", "pago": "100 transferencia"}, m, "u", "telegram", C.TIENDA,
                                      "t", "no tengo mp, pago por transferencia"))
    assert "transferencia" in cliente.lower() and m["pago"] == "100 transferencia"
    pegado = A.pegar("Listo Joaquin.", [{"herramienta": "cobrar", "devuelve": cliente, "al_cliente": cliente}], m,
                     C.TIENDA)
    assert cliente in pegado
