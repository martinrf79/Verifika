"""
ENVIO EN PARTES — lock del corte de la respuesta.

Pedido de Martin el 30-jul: que el bot no largue todo el bloque de golpe, para
bajar la espera percibida. WhatsApp no tiene streaming, asi que se manda en 2 o 3
mensajes cortos cortando por los bloques que YA arma el render.

Lo que este test protege es lo unico que puede salir mal: que se parta el
presupuesto y el cliente vea precios sueltos sin el total, o que la respuesta
salga en goteo de una linea por mensaje.
"""
import asyncio

from app.connectors.base import partir_respuesta, enviar_respuesta

PRESU = """¡Hola! Qué bueno que escribas, te armo el presupuesto con lo que tenemos en stock ahora mismo.

Presupuesto:
- 2x Memoria ram Kingston Fury Beast DDR4 3200 8GB Negro: $34.500 c/u = $69.000
- 2x Auriculares Redragon Zeus X Negro: $57.500 c/u = $115.000
Total: $184.000

Para que no tengas sorpresas, las memorias dependen de la ranura de tu placa.

¿Te parece bien así?"""


def test_el_presupuesto_no_se_parte():
    """La regla dura: el detalle y su Total viajan en el MISMO mensaje."""
    partes = partir_respuesta(PRESU)
    con_detalle = [p for p in partes if "c/u" in p]
    assert len(con_detalle) == 1, "el detalle quedo repartido en varios mensajes"
    assert "Total: $184.000" in con_detalle[0]


def test_sale_en_varias_pero_sin_goteo():
    partes = partir_respuesta(PRESU)
    assert 2 <= len(partes) <= 3
    # ninguna parte suelta de una linea: la ultima puede ser corta porque es el
    # cierre, las demas tienen cuerpo.
    assert all(len(p) > 60 for p in partes)


def test_un_solo_bloque_va_entero():
    assert partir_respuesta("Hola, gracias por escribir.") == [
        "Hola, gracias por escribir."]
    assert partir_respuesta("") == []
    assert partir_respuesta(None) == []


def test_nunca_se_pierde_contenido():
    """Lo que se manda tiene que ser TODO lo que se compuso: partir el envio no
    puede comerse un bloque."""
    unido = "\n\n".join(partir_respuesta(PRESU))
    assert unido == PRESU.strip()


def test_se_envia_en_orden_y_espera_cada_una():
    """Desordenadas serian peor que lentas: se mandan de a una, esperando."""
    enviados = []

    class _Falso:
        async def send_message(self, user_id, text):
            enviados.append(text)
            return True

    ok = asyncio.run(enviar_respuesta(_Falso(), "u1", PRESU))
    assert ok and enviados == partir_respuesta(PRESU)


def test_si_falla_una_parte_se_corta_y_avisa():
    class _Falla:
        def __init__(self):
            self.n = 0

        async def send_message(self, user_id, text):
            self.n += 1
            return self.n == 1

    f = _Falla()
    assert asyncio.run(enviar_respuesta(f, "u1", PRESU)) is False
    assert f.n == 2, "tenia que cortar en la parte que fallo, no seguir"
