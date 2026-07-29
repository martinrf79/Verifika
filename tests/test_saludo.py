"""
AREA: Saludo inicial — el PRIMER mensaje de la charla lleva saludo cordial con
el aviso de herramienta automatica, determinista (pedido de Martin 8-jul).
Cubre con_saludo_inicial de app/core/interprete_libre.py. Logica pura.
"""
from app.core.guardas_salida import con_saludo_inicial


def test_agrega_saludo_y_aviso_de_bot():
    out = con_saludo_inicial("Tenemos varios mouse disponibles.", "Tienda Tecno")
    assert out.startswith("¡Hola! Soy el asistente automático de Tienda Tecno.")
    assert "Tenemos varios mouse disponibles." in out


def test_recorta_saludo_duplicado_del_solver():
    out = con_saludo_inicial("¡Hola! ¿En qué te puedo ayudar?", "Tienda Tecno")
    assert out.count("Hola") == 1
    assert "¿En qué te puedo ayudar?" in out


def test_recorta_buenas_tardes_del_solver():
    out = con_saludo_inicial("Buenas tardes, tenemos teclados.", "Tienda Tecno")
    assert out.count("uenas") == 0  # el 'Buenas tardes' del solver se recorto
    assert "Tenemos teclados." in out


def test_no_se_come_buenas_noticias():
    # 'Buenas' pelado NO es saludo: "Buenas noticias..." queda intacto.
    out = con_saludo_inicial("Buenas noticias, llegó stock.", "Tienda Tecno")
    assert "Buenas noticias, llegó stock." in out


def test_respuesta_vacia_sale_solo_el_saludo():
    out = con_saludo_inicial("", "Tienda Tecno")
    assert out == ("¡Hola! Soy el asistente automático de Tienda Tecno. "
                   "Te ayudo con precios, stock y envíos al instante.")


# ── Honestidad de bot: gatillo determinista sobre "sos un robot?" ────────────
def test_pregunta_bot_sin_respuesta_honesta_se_antepone():
    from app.core.guardas_salida import asegurar_honestidad_bot
    out = asegurar_honestidad_bot(
        "sos un robot vos?", "Entiendo que prefieras hablar con una persona.",
        "Tienda Tecno")
    assert out.startswith("Sí, te lo digo derecho: soy el asistente automático")
    assert "hablar con una persona" in out


def test_respuesta_ya_honesta_no_se_toca():
    from app.core.guardas_salida import asegurar_honestidad_bot
    r = "Sí, soy el asistente automático de la tienda, decime en qué te ayudo."
    assert asegurar_honestidad_bot("sos un bot?", r, "Tienda") == r


def test_mensaje_sin_pregunta_de_bot_no_se_toca():
    from app.core.guardas_salida import asegurar_honestidad_bot
    r = "El mouse sale $8.500."
    assert asegurar_honestidad_bot("cuanto sale el mouse?", r, "Tienda") == r


def test_variantes_de_la_pregunta_disparan():
    from app.core.guardas_salida import asegurar_honestidad_bot
    for msg in ["sos humano?", "eres un bot?", "hablo con una persona?",
                "con quien estoy hablando?", "me atiende un robot?"]:
        out = asegurar_honestidad_bot(msg, "Hola, decime.", "Tienda")
        assert "asistente automático" in out, msg


# El "destino unico" por regex ("mandalo todo a Salta") se BORRO con el camino
# viejo, a proposito: nadie en el camino vivo leia el flag que dejaba, y el
# interprete ya resuelve el mismo pedido mejor, poniendo la localidad en CADA
# renglon del pedido por schema (regla dura del destino, mas la tabla de CP).
# Era una regla de texto compitiendo con una atadura estructural.
