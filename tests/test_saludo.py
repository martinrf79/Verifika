"""
AREA: Saludo inicial — el PRIMER mensaje de la charla lleva saludo cordial con
el aviso de herramienta automatica, determinista (pedido de Martin 8-jul).
Cubre _con_saludo_inicial de app/core/interprete_libre.py. Logica pura.
"""
from app.core.interprete_libre import _con_saludo_inicial


def test_agrega_saludo_y_aviso_de_bot():
    out = _con_saludo_inicial("Tenemos varios mouse disponibles.", "Tienda Tecno")
    assert out.startswith("¡Hola! Soy el asistente automático de Tienda Tecno.")
    assert "Tenemos varios mouse disponibles." in out


def test_recorta_saludo_duplicado_del_solver():
    out = _con_saludo_inicial("¡Hola! ¿En qué te puedo ayudar?", "Tienda Tecno")
    assert out.count("Hola") == 1
    assert "¿En qué te puedo ayudar?" in out


def test_recorta_buenas_tardes_del_solver():
    out = _con_saludo_inicial("Buenas tardes, tenemos teclados.", "Tienda Tecno")
    assert out.count("uenas") == 0  # el 'Buenas tardes' del solver se recorto
    assert "Tenemos teclados." in out


def test_no_se_come_buenas_noticias():
    # 'Buenas' pelado NO es saludo: "Buenas noticias..." queda intacto.
    out = _con_saludo_inicial("Buenas noticias, llegó stock.", "Tienda Tecno")
    assert "Buenas noticias, llegó stock." in out


def test_respuesta_vacia_sale_solo_el_saludo():
    out = _con_saludo_inicial("", "Tienda Tecno")
    assert out == ("¡Hola! Soy el asistente automático de Tienda Tecno. "
                   "Te ayudo con precios, stock y envíos al instante.")
