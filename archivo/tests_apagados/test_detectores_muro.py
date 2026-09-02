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
    # las SIETE redacciones del muro medidas sobre 130 turnos el 4-ago. Ninguna
    # coincide con las tres frases literales que el guion chequeaba: el modelo
    # no repite la frase, repite la conducta.
    "te comento que no contamos con productos que no tengan componentes o fabricacion en China",
    "te comento que no tenemos productos que no tengan partes chinas, ya que trabajamos marcas",
    "te cuento que no tengo productos que no tengan partes chinas, ya que los modelos",
    "te cuento que no tenemos productos que no tengan componentes fabricados en China",
    "asi que no tengo nada que cumpla estrictamente con tu pedido de evitar ese origen",
    "para ser sincero, todos los productos que trabajamos tienen componentes de China",
    "todos los productos que manejamos, aunque pertenezcan a marcas estadounidenses",
])
def test_las_redacciones_reales_del_muro_se_marcan_todas(texto):
    assert D.detectar_universal_de_catalogo(texto), texto


@pytest.mark.parametrize("texto", [
    # una universal de POLITICA sale de la FAQ, que SI es fuente
    "Todos los productos tienen garantia oficial de 12 meses.",
    "Todos los envios salen por correo con seguimiento.",
    # el no honesto sobre una VARIANTE no es una universal
    "Ese modelo puntual no lo tengo, pero mira estos que si.",
    "No tengo esa memoria de 32GB, tengo de 8 y de 16.",
    # EL FALSO POSITIVO REAL, cazado el 4-ago sobre los 130 turnos. La primera
    # version del patron marcaba esta frase como muro por el "no tengo ...
    # ninguno", y es una respuesta honesta, precisa y de las buenas. `ninguno`,
    # `ninguna` y `ningun` son ANAFORICOS: hablan de un conjunto que la charla
    # ya acoto, no del catalogo.
    "el teclado no tengo ninguno en color negro que sea Genius, solo me queda "
    "el Logitech K120",
    "no tengo ninguna memoria de 32GB, tengo de 8 y de 16",
    # y `nada` solo cuenta con un `que` detras: esto es un no acotado
    "no tengo nada en negro de esa marca, pero tengo blanco",
    # EL FALSO POSITIVO DE LA FICHA 18, textual de 62 T2 del corpus regrabado, y
    # es el MISMO de arriba entrando por otra puerta: el demostrativo es tan
    # anaforico como `ninguno`. El cliente pregunto por una PlayStation 5,
    # `buscar_productos` volvio `no_vendemos` y el bot lo dijo bien. Esta linea
    # le costaba un punto al piso y encima tapaba la invencion de verdad, que
    # estaba en la oracion de abajo del mismo mensaje.
    "no trabajamos con ese producto en nuestro catálogo, por lo que no "
    "contamos con stock",
    "no tenemos ese producto, pero mira estos que si",
    "no manejamos esos articulos, te muestro lo que hay",
])
def test_una_universal_legitima_o_un_no_acotado_no_se_marcan(texto):
    assert not D.detectar_universal_de_catalogo(texto), texto


# ── DECIR A QUE SE DEDICA EL NEGOCIO ES LA MISMA UNIVERSAL AL REVES ──────────
# Las formas de arriba NIEGAN el catalogo entero. Esta lo DESCRIBE, y por eso
# no la veia ninguna: el modelo vio CERO productos y de ahi dedujo de que se
# trata la tienda. Medido contra la fuente, "estamos enfocados en tablets" son
# 27 tablets sobre 880, contra 171 notebooks.
@pytest.mark.parametrize("texto", [
    "por ahora estamos enfocados en nuestra linea de tablets y otros accesorios",
    "hoy nos dedicamos a las notebooks y los accesorios de informatica",
    "nuestra linea es la tecnologia de escritorio",
    "estamos especializados en almacenamiento",
])
def test_describir_el_surtido_entero_tambien_se_marca(texto):
    assert D.detectar_universal_de_catalogo(texto), texto


@pytest.mark.parametrize("texto", [
    # LA CONTRACARA: hablar de UN producto o de UN rubro que si se trajo no es
    # describir el surtido. Sin estas, el detector se comeria la venta.
    "esta tablet esta enfocada en el uso liviano y la lectura",
    "el equipo esta pensado para trabajo y estudio",
    "tenemos varias opciones de almacenamiento externo, te paso tres",
])
def test_hablar_de_un_producto_o_un_rubro_no_es_describir_el_surtido(texto):
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
