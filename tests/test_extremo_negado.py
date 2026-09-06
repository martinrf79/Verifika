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


# EL VERBO DEL CLIENTE LLEGA AL CAMPO desde el 6-sep-2026. Estaba como `PLAN`
# desde el 2-sep: "el que menos pesa" devolvia None y el turno salia sin orden,
# mientras "el de menor peso" andaba. El puente nuevo es una flexion —mismo
# largo, todo igual menos la ultima letra— y por eso NO revive el caso que el
# puente de cinco letras vino a prohibir: `cara` contra `caracteristicas` son
# largos distintos y "la mas cara" sigue ordenando por precio, que lo cuida
# `DERECHAS` de arriba.
VERBOS = [
    ("el que menos pesa", "peso_gramos", "min"),
    ("el que mas pesa", "peso_gramos", "max"),
]


@pytest.mark.parametrize("frase,campo,esperado", VERBOS)
def test_el_verbo_del_cliente_tambien_llega_al_campo(
        frase, campo, esperado, firestore_doble):
    o = FC.resolver_orden(frase, TIENDA)
    assert o is not None, f"{frase!r} no resolvio a ningun campo"
    assert o["campo"] == campo, f"{frase!r} resolvio a {o['campo']}"
    assert o["direccion"] == esperado, \
        f"{frase!r} da {o['direccion']} y tiene que dar {esperado}"


def test_cuantos_verbos_se_probaron():
    assert len(VERBOS) == 2, f"se probaron {len(VERBOS)} verbos, esperaba 2"
