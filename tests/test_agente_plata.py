"""EL PRESUPUESTO, EL REPARTO Y EL COBRO DEL AGENTE — lo que fallo en WhatsApp el 30-oct, despues del deploy (FICHA 83).

  "Teclado (a definir)"    un renglon que no es un producto exacto trababa el pedido entero: sin envios, sin total,
                           sin el 70/30, y el cliente leia "¿Cuáles son Teclado (a definir)?".
  "setenta treinta"        el modelo le ponia transferencia y Mercado Pago, y la transferencia llevaba un descuento que
                           nadie eligio. Ahora el reparto se muestra sin medio y el medio se pregunta.
  "no tengo MP"            el cobro salia con el link de Mercado Pago por defecto y no habia como cambiarlo.
"""
import asyncio
import re

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


def test_el_mismo_producto_con_y_sin_destino_no_traba(A):
    """30-oct, despues del deploy: el modelo mando cada producto dos veces, sin destino y con destino, y el ejecutor
    preguntaba "¿A dónde va...?" sin armar nada."""
    a = {"renglones": [{"producto": p["producto"], "cantidad": 2} for p in PEDIDO] + PEDIDO, "pago": "70, 30"}
    cliente, nota = A.presupuesto(a, A.memoria_de({}), C.TIENDA, None, "")
    assert "Total general" in cliente and "(70%)" in cliente and "¿A dónde va" not in cliente
    assert "ya iban con destino" in nota


def test_el_medio_que_ofrecio_el_bot_vale_como_dicho(A):
    """ "¿Transferencia o Mercado Pago?" y "no tengo mp" es transferencia; un solo pago sin medio no es un reparto."""
    assert A._reparto("100 transferencia", "no tengo mp ¿preferis transferencia o mercado pago?") == \
        [{"medio": "transferencia", "porcentaje": 100}]
    assert A._reparto("100 transferencia", "no tengo mp") == []


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


def test_lo_ambiguo_del_pedido_se_resuelve_por_lo_mostrado(A):
    """K18, 1-nov: "sumame uno de cada uno" con "Notebook Asus ROG Strix G16", que es la Core i7 o la Ryzen 7. La charla
    mostro la Core i7, y el bot contestaba "no me figura en el sistema". Sin lo que la distingue dicho, sigue afuera."""
    a = {"renglones": [{"producto": "Notebook Asus ROG Strix G16", "destino": "Posadas"}]}
    visto = "la notebook asus rog strix g16, con procesador core i7, 16gb de ram y 1tb de ssd, a $3.100.500"
    cliente, nota = A.presupuesto(a, A.memoria_de({}), C.TIENDA, visto, "")
    assert "Notebook Asus ROG Strix G16 Core i7 16GB 1TB SSD" in cliente and "afuera" not in nota
    cliente, nota = A.presupuesto(a, A.memoria_de({}), C.TIENDA, "la notebook asus rog strix g16", "")
    assert not cliente and "afuera" in nota


# ── LO QUE FALLABA EN EL EXAMEN REAL, 3-nov: medido con `examen_real/examen.py --codigo corrida_31oct.jsonl` ──

def test_la_oferta_del_bot_elige_solo_si_el_cliente_la_contesta(A):
    """fe67b4 y b8df72: "Mi nombre es Julio" e "Y 1 teclado" anotaban transferencia y Mercado Pago que nadie eligio;
    815c0c: "dale" a "ya te anote el pago 100% transferencia" si la elige. 4 casos."""
    assert A.de_la_oferta("Joaquin no tengo mp", "¿Preferís transferencia o Mercado Pago?") == ["transferencia"]
    assert A.de_la_oferta("dale", "Ya te anoté el G305 con pago 100% transferencia.\n¿Me pasás tu nombre?") == \
        ["transferencia"]
    assert A.de_la_oferta("Mi nombre es Julio", "- transferencia (70%): $1\n¿Con qué medio pagás cada parte?\n"
                                                "La parte con pago por transferencia bancaria lleva 10% de descuento.") == []
    assert A.de_la_oferta("Y 1 teclado", "confirmame si pagás por transferencia o mercado pago") == []


def test_un_medio_que_la_tienda_no_toma_no_se_cobra(A):
    """7f8cd4: "tarjeta naranja" se cobraba con el link; la tienda toma Visa, Mastercard y Amex."""
    m = A.memoria_de({})
    m["pedido"] = PEDIDO
    cliente, nota = asyncio.run(A.cobrar({"nombre": "Juan", "pago": "100 tarjeta naranja"}, m, "u", "telegram",
                                         C.TIENDA, "t", "tarjeta naranja"))
    assert not cliente and "no toma tarjeta naranja" in nota
    assert A._reparto("100 tarjeta visa", "con visa", C.TIENDA) == [{"medio": "tarjeta visa", "porcentaje": 100}]


def test_un_renglon_a_dos_lugares_vuelve_al_modelo(A):
    """b5ddaa y 83e58a: "Córdoba capital y Posadas" salia como un destino con un solo envio."""
    a = {"renglones": [{"producto": PEDIDO[1]["producto"], "cantidad": 2, "destino": "Córdoba capital y Posadas"},
                       PEDIDO[0]]}
    cliente, nota = A.presupuesto(a, A.memoria_de({}), C.TIENDA, None, "")
    assert "Posadas" not in cliente and "Envio a Concordia" in cliente and "mas de un lugar" in nota


def test_el_color_dicho_gana_al_del_nombre(A):
    """e993ae: "Mouse Logitech M170 Negro" con color blanco volvia a preguntar el color; con rojo salia negro."""
    def con(color):
        a = {"renglones": [{"producto": "Mouse Logitech M170 Negro", "cantidad": 3, "color": color}]}
        return A.presupuesto(a, A.memoria_de({}), C.TIENDA, None, "")[0]
    assert "3x Mouse Logitech M170 Blanco" in con("blanco")
    assert "no viene en rojo" in con("rojo")


def test_el_medio_se_lee_como_lo_escriba_el_cliente(A):
    """Martin, 3-nov: una mayuscula, un guion o una letra de menos no pueden tirar una venta. 14 formas."""
    formas = {"TRANSFERENCIA": "transferencia", "Transf.": "transferencia", "tranferencia": "transferencia",
              "x transfe": "transferencia", "por MP": "mercado pago", "Mercado-Pago": "mercado pago",
              "MercadoPago": "mercado pago", "«mp»": "mercado pago", "Débito": "tarjeta", "con VISA": "tarjeta visa",
              "Master": "tarjeta mastercard", "efvo": "efectivo", "tarjeta de crédito visa": "tarjeta visa",
              "transporte": None}
    for texto, medio in formas.items():
        assert [m for m, _ in A.menciones(texto)] == ([medio] if medio else []), texto
    assert A.menciones("la transferencia no, mejor mp") == [("transferencia", True), ("mercado pago", False)]
    assert A.menciones("mp no tengo") == [("mercado pago", True)]


def test_el_criterio_del_cliente_se_controla_en_el_presupuesto(A):
    """d29c5a: "dame el mouse más liviano" y el presupuesto con el G502 X, el tercero. Entre lo mostrado no aplica."""
    def aviso(producto, mensaje):
        m = A.memoria_de({})
        m["_ultimo"] = {"mostrado": [{"producto": producto}]}
        return A.omitidos(mensaje, m, [{"herramienta": "presupuesto"}], C.TIENDA)
    assert aviso("Mouse Logitech G502 X Negro", "dame el mouse más liviano")
    assert not aviso("Mouse Logitech G Pro Wireless Blanco", "dame el mouse más liviano")
    assert not aviso("Mouse Logitech G502 X Negro", "de esos, el más liviano")
    assert not aviso("Mouse Logitech G502 X Negro", "quiero un mouse")


def test_lo_que_el_cliente_no_cambio_queda_y_se_avisa(A):
    """Las cuatro del pedido del examen real. d0c439: "2 auriculares" sin destino vuelve al reparto de antes. 6740e0:
    "3 a toledo" sin renglon a Toledo. b8df72: "Y 1 teclado" con uno ya en el pedido. 83e58a: las memorias de 2 a 3 sin
    que el cliente las nombre. Y lo que no avisa: "sumame un Redragon Cobra" nombra el mouse; "partes de Estados Unidos"
    no es un envio."""
    m = A.memoria_de({})
    m["mostrado"] = [{"producto": PEDIDO[1]["producto"], "cantidad": 1, "destino": "Córdoba"},
                     {"producto": PEDIDO[1]["producto"], "cantidad": 1, "destino": "Posadas"}]
    cliente, _ = A.presupuesto({"renglones": [{"producto": PEDIDO[1]["producto"], "cantidad": 2}]}, m, C.TIENDA)
    assert "Envio a Córdoba" in cliente and "Envio a Posadas" in cliente

    def avisos(mensaje, antes, ahora):
        mm = A.memoria_de({})
        mm["mostrado"], mm["_ultimo"] = antes, {"mostrado": ahora}
        return " ".join(A.omitidos(mensaje, mm, [{"herramienta": "presupuesto"}], C.TIENDA))
    teclado = {"producto": "Teclado Logitech K120 Negro", "cantidad": 1, "destino": "Concordia"}
    memoria = {"producto": "Memoria ram Kingston Fury Beast DDR4 3200 8GB Negro", "cantidad": 2, "destino": "Posadas"}
    assert "toledo" in avisos("2 a villa maria y 3 a toledo", [], [{**memoria, "destino": "Villa Maria"}])
    assert "otro mas" in avisos("Y 1 teclado", [teclado], [{**teclado, "cantidad": 2}])
    assert "eran 2 y quedan 3" in avisos("son 7, los mas baratos", [memoria], [{**memoria, "cantidad": 3}])
    assert not avisos("sumame también un Redragon Cobra", [{"producto": "Mouse Logitech M170 Negro"}],
                      [{"producto": "Mouse Logitech M170 Negro"}, {"producto": "Mouse Redragon Cobra M711"}])
    assert not avisos("las menos partes de estados unidos", [], [memoria])


def test_el_equipo_nombrado_filtra_y_el_color_dicho_se_usa(A):
    """La corrida con la gratis del 3-nov. 58b5a1: "auriculares PS5" listaba primero el Zeus X, que no anda con la PS5,
    y el modelo lo daba por compatible. "notebook asus", "tablets" y "tablet samsung" piden productos, no filtran.
    b8bb00: "el mas eco en negro" y el Pandora sin color volvia a preguntar el color."""
    assert "solo los que andan" in A.buscar("auriculares PS5", C.TIENDA)
    assert "Zeus X" not in A.buscar("auriculares PS5", C.TIENDA).split("\n")[1]
    for q in ("notebook asus", "tablets", "tablet samsung"):
        assert "solo los que andan" not in A.buscar(q, C.TIENDA), q
    a = {"renglones": [{"producto": "Redragon Pandora", "destino": "Posadas"}]}
    assert "Pandora Negro" in A.presupuesto(a, A.memoria_de({}), C.TIENDA, None, "si el mas eco en negro")[0]
    assert "¿en qué color" in A.presupuesto(a, A.memoria_de({}), C.TIENDA, None, "uno negro y otro blanco")[0]


def test_un_lugar_dicho_como_destino_no_es_un_color(A):
    """6740e0, el examen real, roto desde el 3-nov: "envio de los dos primeros a la plata" le ponia color plata a la
    notebook HP 245 G9 Gris, y el presupuesto de los siete articulos salia como "¿en qué color: Gris o Plata?". Cuenta
    la clase: cada lugar con un color en el nombre, dicho como destino, y el color dicho aparte sigue valiendo."""
    nb = {"renglones": [{"producto": "Notebook HP 245 G9 Core i5 16GB 512GB SSD Gris", "cantidad": 2, "destino": "La Plata"}]}
    assert "Total: $1.386.000" in A.presupuesto(nb, A.memoria_de({}), C.TIENDA, None,
                                                "2 notebooks envio de los dos a la plata")[0]
    pandora = {"renglones": [{"producto": "Redragon Pandora", "destino": "Bahia Blanca"}]}
    casos = [("mandalo a bahia blanca", "¿en qué color"), ("lo quiero en negro, va para bahia blanca", "Pandora Negro"),
             ("quiero el negro, va a rio negro", "Pandora Negro")]
    bien = sum(esperado in A.presupuesto(pandora, A.memoria_de({}), C.TIENDA, None, dijo)[0] for dijo, esperado in casos)
    print(f"\nLUGAR NO ES COLOR: {bien} de {len(casos)}")
    assert bien == len(casos)


def test_el_cobro_usa_el_pedido_anotado_en_el_mismo_turno(A):
    """96b39f, la corrida con SQL del 5-nov: el modelo anoto el pedido nuevo con presupuesto y cobro en el mismo turno, y
    el cobro salia con el monto del pedido del turno anterior. Se cobra lo que el cliente acaba de leer."""
    m = A.memoria_de({})
    m["pedido"], m["pago"] = PEDIDO[:1], "100 transferencia"
    nuevo = {"renglones": PEDIDO, "pago": "100 transferencia", "anotar": True}
    leido, _ = A.presupuesto(nuevo, m, C.TIENDA, None, "pago por transferencia")
    cliente, _ = asyncio.run(A.cobrar({"nombre": "Joaquin"}, m, "u", "telegram", C.TIENDA, "t", "pago por transferencia"))
    final = re.search(r"Total final: (\$[\d.]+)", leido).group(1)
    assert f"Monto: {final}" in cliente, (final, cliente)


def test_el_medio_dicho_para_una_parte_no_vale_para_otra_ni_la_pregunta_elige(A):
    """La corrida con SQL del 5-nov. fe67b4 t8: "70 por ciento transferencia" y el 30 tambien salia por transferencia,
    con descuento. 781919 t2: "tenes descuento con tarjeta o transferencia, que me conviene" se tomaba como elegido."""
    casos = [("70 transferencia, 30 transferencia", "color indistinto 70 por ciento transferencia. blancos", ["transferencia", ""]),
             ("70 transferencia, 30 transferencia", "decime si tenes descuento con tarjeta o transferencia", ["", ""]),
             ("100 transferencia", "no me preguntaste, era por transferencia", ["transferencia"]),
             ("50 transferencia, 50 tarjeta mastercard", "mitad con transferencia y mitad con mastercard",
              ["transferencia", "tarjeta mastercard"])]
    bien = sum([x["medio"] for x in A._reparto(p, d, C.TIENDA)] == esperado for p, d, esperado in casos)
    print(f"\nMEDIO POR PARTE: {bien} de {len(casos)}")
    assert bien == len(casos)
