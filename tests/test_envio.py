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


# ── CP PELADO: el cliente responde el codigo postal solo, sin la palabra "CP" ──
# Hallado en el estres (2-jul): cuando el bot pide el codigo postal y el cliente
# contesta el numero pelado ('5000', '1414'), el clasificador daba None y el bot
# lo volvia a pedir. Estaba detras de un flag muerto (CP_COMPLETO, que ni existia
# en config): funcion real inalcanzable. Se hizo vivo el camino. El regex es
# full-match del texto entero, asi un numero suelto en una frase no se confunde.

# (texto del cliente, zona esperada)
CASOS_CP_PELADO = [
    ("1414", "caba"),
    ("mi cp es 1425", "caba"),
    ("1832", "gba"),
    ("5000", "interior"),
    ("X5000", "interior"),
    ("2000", "interior"),
]


import pytest


@pytest.mark.parametrize("texto, zona", CASOS_CP_PELADO)
def test_cp_pelado_clasifica_zona(texto, zona, firestore_doble):
    from app.core.envio import clasificar_zona
    assert clasificar_zona(texto) == zona, (
        f"'{texto}' es un CP pelado, deberia dar zona '{zona}'.")


def test_cp_pelado_cotiza_provincia_exacta(firestore_doble):
    """Un CP pelado del interior deduce la provincia y da la tarifa EXACTA de esa
    provincia, no el rango generico. 5000 = Cordoba capital -> 7500 (sembrado)."""
    from app.core.tools import cotizar_envio
    q = cotizar_envio(localidad="5000", subtotal=1000)
    assert q.get("ok") is True
    assert q.get("zona") == "interior"
    assert q.get("provincia") == "cordoba"
    assert q.get("monto") == 7500


def test_numero_suelto_en_frase_no_es_cp(firestore_doble):
    """El regex del CP pelado es full-match: un numero dentro de una frase (altura
    de calle, cantidad) NO se toma como codigo postal. Sin esto, '5000 unidades'
    o 'calle falsa 1414' inventarian una zona."""
    from app.core.envio import clasificar_zona
    assert clasificar_zona("quiero 5000 unidades") is None
    assert clasificar_zona("calle falsa 1414") is None


# ── GUARDA DE CALLE: nombre + numero suelto NO es la localidad ────────────────
# Hallado en el mega-estres (2-jul): 'san martin 1234' sin provincia caia en GBA
# por la lista de partidos a mano, tomando una altura de calle como el partido
# General San Martin. Ahora un nombre inmediatamente seguido de un numero no
# clasifica zona (es una direccion): ante la duda se pide el dato, no se adivina.

def test_nombre_seguido_de_numero_no_clasifica(firestore_doble):
    from app.core.envio import clasificar_zona
    assert clasificar_zona("san martin 1234") is None
    assert clasificar_zona("belgrano 850") is None
    assert clasificar_zona("lomas de zamora 1234") is None


def test_guarda_calle_no_rompe_lo_legitimo(firestore_doble):
    """La guarda NO debe frenar los casos con provincia o sin altura pegada."""
    from app.core.envio import clasificar_zona
    assert clasificar_zona("san martin, mendoza") == "interior"   # provincia desambigua
    assert clasificar_zona("lomas de zamora") == "gba"            # partido sin numero
    assert clasificar_zona("Palermo") == "caba"                    # barrio sin numero
    # La ciudad real gana a la calle homonima: 'san martin 45, rio tercero'.
    assert clasificar_zona("calle san martin 45, rio tercero") == "interior"
