"""
AREA: Envio y zona (codigo postal / provincia).

Herramienta del bot cubierta: cotizar_envio (app/core/tools.py), que clasifica la
zona desde el codigo postal o la localidad y devuelve la tarifa de la tienda.

Esta area NO nacio de un error confirmado: son casos de camino feliz que FIJAN el
contrato de la herramienta, para que un arreglo del multi-destino (E5/E13) u otro
cambio no rompa la cotizacion que hoy funciona. Es el modelo de como crece cada
area: los bugs son las primeras semillas, los locks protegen lo que anda.

Corre sobre el doble local (catalogo + FAQ reales), sin LLM ni Google.
"""


def test_cotiza_tarifa_fija_por_provincia(firestore_doble):
    """Lock: con la provincia clara, la tarifa sale exacta y fija, no en rango.
    Cordoba esta sembrada en el doble en 7500."""
    from app.core.tools import cotizar_envio
    q = cotizar_envio(localidad="Cordoba, provincia de Cordoba", subtotal=1000)
    assert q.get("ok") is True
    assert q.get("modalidad") == "fijo"
    assert q.get("monto") == 7500


def test_envio_gratis_por_umbral(firestore_doble):
    """Lock: si el subtotal supera el umbral, el envio es gratis (monto 0)."""
    from app.core.tools import cotizar_envio
    q = cotizar_envio(localidad="Cordoba, provincia de Cordoba",
                      subtotal=99_999_999)
    assert q.get("ok") is True
    assert q.get("monto") == 0
    assert q.get("concepto") == "envio_gratis"


def test_zona_indeterminable_pide_dato_no_inventa(firestore_doble):
    """Lock: sin un dato que permita clasificar la zona, NO se inventa tarifa;
    se devuelve ok False y se pide el codigo postal o la provincia."""
    from app.core.tools import cotizar_envio
    q = cotizar_envio(localidad="qwerty zxcvb", subtotal=1000)
    assert q.get("ok") is False
    assert q.get("zona") is None


# ── C: la provincia que el cliente ya dio VIAJA por el estado ─────────────────
# En la charla real el cliente dijo "son pueblos de cordoba" y el bot le siguio
# pidiendo el codigo postal de cada pueblo. La provincia se detecta determinista
# (clasificar_provincia, ya existe) pero no viajaba: no se cacheaba ni se
# aplicaba a todos los destinos. Estos tests fijan ese viaje. HOY fallan (rojo).

def test_c_detecta_provincia_de_los_pueblos():
    """El dato de la provincia se saca con codigo del mensaje del cliente, no con
    el modelo. 'son pueblos de cordoba' -> cordoba, para todos los destinos."""
    from app.core.envio import clasificar_provincia
    assert clasificar_provincia("son pueblos de cordoba") == "cordoba"


def test_c_estado_persiste_provincia():
    """construir_estado levanta la provincia guardada, asi sobrevive entre turnos
    y no hay que volver a pedirla."""
    from app.core import estado_venta
    estado = estado_venta.construir_estado({"provincia_envio": "cordoba"}, None)
    assert estado.get("provincia_envio") == "cordoba"


def test_c_bloque_inyecta_provincia_y_prohibe_repedir_cp():
    """El bloque del solver lleva la provincia Y la orden de no repedir el CP:
    es lo que evita el 'ya te dije pueblo y provincia'. Debe cubrir TODOS los
    destinos con esa provincia."""
    from app.core import estado_venta
    bloque = estado_venta.bloque_para_solver({"provincia_envio": "cordoba"})
    assert "cordoba" in bloque.lower()
    assert "NO" in bloque
    assert "cp" in bloque.lower() or "codigo postal" in bloque.lower()
