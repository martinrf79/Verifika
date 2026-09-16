"""LA GUARDA DE ESTADO — el bot niega datos que la fuente TIENE.

EL CASO, MEDIDO DOS VECES EN WHATSAPP, el 15 y el 16-sep-2026: el bot contesto
que no tiene el pais de fabricacion. El campo esta cargado en 880 de 880
productos y viaja en el tablero, en la leyenda, con sus cinco valores. No lo
consulto y contesto igual.

POR QUE NO LA ATAJA LA GUARDA QUE YA HAY. `numeros` mira CIFRAS, y "no tenemos
ese dato" no lleva ninguna. La cifra inventada tiene candado desde el 11-sep;
la afirmacion inventada no tenia ninguno.

LA CONDICION ES DE ESTADO Y NO DE VOCABULARIO, que es la regla 4 de la FICHA 55
§5. No se persigue la frase: eso ya fracaso tres veces en este repo —4 nodos,
despues 18, despues 46—. Lo que se mira es un NOMBRE DE CAMPO, que es un token
verificable igual que una cifra, y la lista sale de la fuente viva.

NACE MUDA, y estos tests miden eso tambien: que devuelva el renglon y que NO
toque la respuesta. El dia que frene, el test de abajo se da vuelta a proposito
y con el numero de la pelicula en la mano.
"""
import pytest

from app.core import guardas_salida as gs

TIENDA = "verifika_prod"


@pytest.fixture(autouse=True)
def _doble(firestore_doble):
    from app.core.contexto_turno import set_current_tienda
    from app.core.filtros_catalogo import limpiar_cache
    set_current_tienda(TIENDA)
    limpiar_cache()
    return firestore_doble


def test_el_caso_medido_el_pais_de_fabricacion_negado_sin_consultarlo():
    """El turno no toco `pais_fabricacion` y la respuesta lo nombra."""
    sin = gs.afirmo_sin_mirar(
        "No tenemos cargado el país de fabricación de los teclados.",
        {"categoria", "precio_ars"}, TIENDA, "t")
    assert "pais_fabricacion" in sin


def test_el_campo_que_el_turno_SI_miro_no_se_cuenta():
    """La contracara, y es la que evita que esto sea un generador de ruido: si
    la consulta uso el campo, el modelo tuvo el dato o el motivo delante."""
    sin = gs.afirmo_sin_mirar(
        "No tenemos cargado el país de fabricación de los teclados.",
        {"pais_fabricacion"}, TIENDA, "t")
    assert "pais_fabricacion" not in sin


def test_una_respuesta_que_no_nombra_ningun_campo_esta_limpia():
    sin = gs.afirmo_sin_mirar(
        "Te paso tres opciones de teclados y me decís cuál te gusta.",
        set(), TIENDA, "t")
    assert sin == []


def test_el_campo_se_reconoce_escrito_como_lo_escribe_un_vendedor():
    """`pais_fabricacion` sale como "país de fabricación": con acentos, con
    minusculas y con la preposicion en el medio. Los conectores son un conjunto
    cerrado de cinco, no una lista de frases que crece."""
    campos = {"pais_fabricacion", "garantia_meses"}
    assert gs.campos_nombrados("el país de fabricación es China", campos) \
        == ["pais_fabricacion"]
    assert gs.campos_nombrados("la garantía en meses", campos) \
        == ["garantia_meses"]
    assert gs.campos_nombrados("pais fabricacion", campos) \
        == ["pais_fabricacion"]


def test_no_aparea_por_palabras_compartidas():
    """LA ENFERMEDAD QUE EL MAPA_CABLEADO YA TIENE NUMERADA CUATRO VECES —D3,
    D4, D6 y D16—: aparear por una palabra en comun. Nombrar la garantia no es
    nombrar `garantia_meses`, que es otro campo; y una palabra suelta del medio
    de un campo no lo trae."""
    campos = {"pais_fabricacion", "memoria_video"}
    assert gs.campos_nombrados("tiene memoria de sobra", campos) == []
    assert gs.campos_nombrados("es de fabricación nacional", campos) == []


def test_la_guarda_NACE_MUDA_y_no_toca_la_respuesta(firestore_doble, caplog):
    """LO QUE MAS IMPORTA DE ESTA VUELTA. La pieza escribe su renglon y no
    cambia una sola respuesta: hoy un campo de una palabra —`color`, `marca`—
    aparece en cualquier respuesta legitima, y "te lo puedo buscar por color"
    no es una afirmacion sobre la fuente. Frenar con eso adentro seria cambiar
    un defecto por otro mas caro.

    El dia que frene, este test cambia a proposito y con el numero de la
    pelicula en la mano. Mientras tanto sostiene la regla 2 de la FICHA 55 §5:
    la pieza nace muda.
    """
    texto = "No tenemos cargado el país de fabricación."
    sin = gs.afirmo_sin_mirar(texto, set(), TIENDA, "t")
    assert sin, "la guarda tiene que VER el caso"
    # y no hay forma de que lo tape: devuelve una lista, no un texto.
    assert isinstance(sin, list)
