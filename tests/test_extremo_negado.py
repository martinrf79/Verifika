"""EL EXTREMO NEGADO NO SE LEE AL REVES.

`resolver_orden` decide la direccion mirando UNA sola cosa: si aparece una
palabra de `_MENOR` —menos, menor, minim, barat, economic, accesible, livian,
ligero—. La negacion no la mira nadie.

Consecuencia medida el 2-sep-2026 sobre la fuente real, 8 de 10 formas al reves:

    'que no sean tan caros'   daba max, o sea el MAS CARO
    'que no sea caro'         daba max
    'que no sea muy caro'     daba max
    'nada caro'               daba max
    'sin que sea caro'        daba max
    'que no salga tan caro'   daba max
    'que no sea tan cara'     daba max
    'que no sea barato'       daba min, o sea el MAS BARATO

"que no sea caro" es de las formas mas comunes en que un cliente argentino pone
su presupuesto, y el bot le ordenaba la busqueda del mas caro al mas barato.

Estaba TAPADO por otro defecto: mientras `orden = orden or extremo` se quedaba
con el primer extremo del turno, un 'que sea barato' declarado antes lo pisaba.
Al juntar los extremos en una lista el defecto quedo a la vista. Los dos son de
la misma familia: la direccion de un extremo se decidia por accidente.

POR QUE NO SE REUSA `tiene_negacion`: su vocabulario incluye "menos", "menor",
"minima" y "minimo", que para la EXCLUSION son negacion —"el que menos partes
chinas tenga"— pero en un extremo SON el extremo. Darlas vuelta convertiria "el
que menos pesa" en el mas pesado. Por eso la constante del giro sale de
`_NEGACIONES` restandole lo que `_MENOR` ya consume: una sola fuente, dos usos.

Cada test dice sobre cuantos casos corrio (regla 10.6 de CLAUDE.md).
"""
import pytest

from app.core import filtros_catalogo as FC

TIENDA = "verifika_prod"

# frase, direccion correcta
NEGADAS = [
    ("que no sean tan caros", "min"),
    ("que no sea caro", "min"),
    ("que no sea muy caro", "min"),
    ("nada caro", "min"),
    ("sin que sea caro", "min"),
    ("que no salga tan caro", "min"),
    ("que no sea tan cara", "min"),
    ("que no sea barato", "max"),
]

# Las que NO llevan negacion y ya andaban: no se pueden mover.
DERECHAS = [
    ("que sea barato", "min"),
    ("el mas caro", "max"),
    ("el mas barato de toda la tienda", "min"),
    ("el mas caro de toda la tienda", "max"),
    ("la mas economica", "min"),
]

# EL CASO QUE PROHIBE EL ARREGLO FACIL. "menos" es negacion para la exclusion y
# es el extremo para el orden: si el giro usara `tiene_negacion`, estas se darian
# vuelta y el cliente que pide el mas liviano recibiria el mas pesado.
COMPARATIVAS = [
    ("el de menor peso", "min"),
    ("el mas liviano", "min"),
    ("el que mas garantia tenga", "max"),
]


@pytest.mark.parametrize("frase,esperado", NEGADAS)
def test_la_negacion_da_vuelta_el_extremo(frase, esperado, firestore_doble):
    o = FC.resolver_orden(frase, TIENDA)
    assert o is not None, f"{frase!r} dejo de resolver a un extremo"
    assert o["direccion"] == esperado, \
        f"{frase!r} da {o['direccion']} y tiene que dar {esperado}"


def test_cuantas_formas_negadas_se_probaron():
    assert len(NEGADAS) == 8, f"se probaron {len(NEGADAS)} formas, esperaba 8"


@pytest.mark.parametrize("frase,esperado", DERECHAS)
def test_lo_que_no_niega_no_se_mueve(frase, esperado, firestore_doble):
    o = FC.resolver_orden(frase, TIENDA)
    assert o is not None and o["direccion"] == esperado, \
        f"{frase!r} se movio: {o}"


@pytest.mark.parametrize("frase,esperado", COMPARATIVAS)
def test_el_comparativo_no_es_una_negacion_que_se_da_vuelta(
        frase, esperado, firestore_doble):
    o = FC.resolver_orden(frase, TIENDA)
    assert o is not None and o["direccion"] == esperado, \
        f"{frase!r} se dio vuelta y no debia: {o}"


def test_cuantas_no_negadas_se_probaron():
    total = len(DERECHAS) + len(COMPARATIVAS)
    assert total == 8, f"se probaron {total} frases sin negacion, esperaba 8"


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: el verbo no llega al campo. HOY 'el que menos pesa' devuelve None y "
    "no ordena por nada: `_RE_SUPERLATIVO` matchea 'menos', pero despues el "
    "campo se busca por raiz del NOMBRE -'peso' de `peso_gramos`- y la palabra "
    "del cliente es el VERBO, 'pesa', que no empieza con 'peso' ni llega a las "
    "cinco letras del puente al reves; el mapa `_ADJETIVOS_DE_ORDEN` tiene "
    "'pesad' y tampoco pega. OBJETIVO min. Lo destapo la vara del extremo "
    "negado del 2-sep, NO es una regresion: 'el de menor peso' anda hoy y sigue "
    "andando. Es un agujero de la traduccion verbo a campo, hermano del que ya "
    "tiene 'cara' contra `caracteristicas_extra`, y se arregla en la ficha de "
    "la derivacion, no aca."))
def test_el_verbo_del_cliente_tambien_llega_al_campo(firestore_doble):
    o = FC.resolver_orden("el que menos pesa", TIENDA)
    assert o is not None and o["direccion"] == "min"
