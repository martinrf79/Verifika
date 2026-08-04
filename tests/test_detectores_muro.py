"""
AREA: LOS DOS DETECTORES QUE MIDEN EL MURO Y LA CUENTA QUE NO LLEGO.

De donde salieron (4-ago-2026). Martin probo produccion por WhatsApp y mando el
guion 76 palabra por palabra: "Dame precio de dos auriculares, dos mouse y dos
memorias... que lleven las menos partes chinas posibles... Divide el presupuesto
en setenta treinta". Recibio una lista de nueve precios unitarios, encabezada
por "no tengo productos que no sean fabricados en China, ya que todo lo que
trabajo es de marcas internacionales pero con produccion en ese origen". Sin
total, sin envios, sin el reparto.

EL BANCO LO DIO POR BUENO. El guion chequeaba ese turno con tres frases
LITERALES que no debian aparecer -"no puedo armarte", "no contamos con
auriculares", "no contamos con productos"-. El modelo dijo el mismo muro con
otras palabras y paso limpio, y por eso la metrica reportaba 96% de completitud
sobre algo que en el telefono estaba roto.

Ademas la afirmacion era FALSA: 91 de los 880 productos no tienen China en el
origen -los 72 de almacenamiento externo y los 19 procesadores-.

Estos tests fijan las dos mitades: que los detectores agarren el muro, y -la
mitad que importa igual o mas- que NO acusen el "no" honesto, que es justo lo
que el sistema hace bien.
"""
import pytest

from banco_pruebas import detectores as D

TIENDA = "verifika_prod"


@pytest.fixture(scope="module")
def catalogo(request):
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    from app.storage.firestore_client import get_all_products
    return get_all_products(tienda_id=TIENDA)


# ── EL UNIVERSAL SOBRE EL CATALOGO ───────────────────────────────────────────
# Ninguna herramienta devuelve el universo: `buscar_productos` trae seis como
# mucho. Entonces toda afirmacion sobre la TOTALIDAD del catalogo no la respalda
# ningun dato que el modelo haya tenido delante. Misma logica que el candado de
# plata: lo que no calculo el codigo, no se dice.
@pytest.mark.parametrize("texto", [
    "no tengo productos que no sean fabricados en China",
    "todo lo que trabajo es de marcas internacionales con produccion alla",
    "no manejo articulos de otro origen",
    "no contamos con productos que cumplan eso",
    "todos los productos que vendemos son importados",
])
def test_el_universal_sobre_el_catalogo_se_marca(texto):
    assert D.detectar_universal_de_catalogo(texto), texto


@pytest.mark.parametrize("texto", [
    # una universal de POLITICA sale de la FAQ, que SI es fuente
    "Todos los productos tienen garantia oficial de 12 meses.",
    "Todos los envios salen por correo con seguimiento.",
    # el no honesto sobre una VARIANTE no es una universal
    "Ese modelo puntual no lo tengo, pero mira estos que si.",
    "No tengo esa memoria de 32GB, tengo de 8 y de 16.",
])
def test_una_universal_legitima_o_un_no_puntual_no_se_marcan(texto):
    assert not D.detectar_universal_de_catalogo(texto), texto


# ── LA NEGACION DE UNA CATEGORIA QUE SI VENDEMOS ─────────────────────────────
def test_negar_pelada_una_categoria_que_tenemos_se_marca(catalogo):
    r = D.detectar_categoria_negada(
        "Lamentablemente no tenemos auriculares. Te ofrezco otra cosa.",
        catalogo)
    assert r and "auriculares" in r[0]


def test_el_no_honesto_sobre_una_variante_NO_se_marca(catalogo):
    """LA MITAD QUE IMPORTA. "no cuento con auriculares bluetooth" es correcto
    -los 46 del catalogo son con cable- y es exactamente el comportamiento que
    queremos. Medido el 4-ago: la primera version de este detector marcaba esa
    respuesta como falla, o sea castigaba lo que el sistema hace bien. Si
    despues de la categoria viene algo que la ACOTA, la negacion es sobre esa
    variante y no sobre el rubro."""
    for texto in (
        "Actualmente no cuento con auriculares bluetooth, son todos cableados.",
        "No tenemos mouse blancos de menos de 80 gramos.",
        "No tengo memoria ram de 32GB en stock ahora.",
    ):
        assert D.detectar_categoria_negada(texto, catalogo) == [], texto


def test_negar_un_rubro_que_de_verdad_no_vendemos_no_se_marca(catalogo):
    assert D.detectar_categoria_negada(
        "No vendemos heladeras, trabajamos tecnologia e informatica.",
        catalogo) == []


# ── LA CUENTA QUE NO LLEGO ───────────────────────────────────────────────────
def test_pedido_concreto_sin_total_se_marca():
    """El caso real: seis items, tres destinos y un reparto 70/30 pedido, y la
    respuesta fue una lista de nueve precios unitarios sin una sola cuenta."""
    msg = ("Dame precio de dos auriculares, dos mouse y dos memorias. "
           "Divide el presupuesto en setenta treinta.")
    resp = "Auriculares: $125.500\nMouse: $37.500\nMemoria: $34.500"
    assert D.precio_pedido_sin_total(msg, resp) is True


def test_con_el_total_puesto_no_se_marca():
    msg = "Dame precio de dos auriculares y dos mouse"
    resp = "Productos:\n- 2x Auriculares\nEnvio: $7.500\nTotal: $260.500"
    assert D.precio_pedido_sin_total(msg, resp) is False


@pytest.mark.parametrize("msg,resp", [
    # EXPLORACION, no pedido: contestar con opciones y sin total es lo correcto.
    # Pedir un total aca obligaria al bot a elegir por el cliente.
    ("cuanto sale un mouse?", "Mouse A: $12.000\nMouse B: $14.000\n¿Cual te gusta?"),
    ("cuanto cuesta el envio a cordoba", "El envio a Cordoba sale $7.500"),
    ("hola que tal", "Hola! ¿En que te ayudo?"),
])
def test_la_exploracion_sin_total_no_se_marca(msg, resp):
    assert D.precio_pedido_sin_total(msg, resp) is False


# ── EL JUEZ, DE PUNTA A PUNTA ────────────────────────────────────────────────
def test_el_juez_pone_en_rojo_la_charla_real_del_4_ago(catalogo):
    """El candado que cierra el agujero de medicion: esta respuesta salio en
    produccion y el banco la dio por limpia."""
    from banco_pruebas.juez import juzgar
    msg = ("Dame precio de dos auriculares, dos mouse y dos memorias. Lo que si "
           "necesito que lleven las menos partes chinas posibles. Divide el "
           "presupuesto en setenta treinta.")
    resp = ("Te cuento que no tengo productos que no sean fabricados en China, "
            "ya que todo lo que trabajo es de marcas internacionales pero con "
            "produccion en ese origen. Te paso las mejores opciones:\n\n"
            "Auriculares HyperX Cloud II Negro: $125.500\n"
            "Mouse Logitech G203 Lightsync Negro: $37.500\n")
    problemas = juzgar(resp, mensaje=msg)
    assert any("universal sobre el catalogo" in p for p in problemas), problemas
    assert any("sin Total" in p for p in problemas), problemas
