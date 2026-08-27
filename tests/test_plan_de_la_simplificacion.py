"""
LA SIMPLIFICACION DE VERDAD — tres pasos que el recorte ya pedia y nunca
fueron un test.

POR QUE EXISTE. PLAN_RECORTE.md, 17-ago, paso 2: nueve herramientas a cuatro,
fusionando por lo que CONSUME cada una. Paso 3: una implementacion por
propiedad. La FICHA 06 escondio las ocho del modelo y dejo los nueve cuerpos.
La FICHA 10 agrupo diecisiete piezas en cuatro puertas y dejo las diecisiete.
El contador del plan no las veia, asi que nadie las hacia.

ESTE ARCHIVO ES EL PLAN. El relato esta en
`arquitectura/FICHA_30_la_simplificacion.md`. Aca van los tres numeros: HOY y
OBJETIVO, con `xfail(strict=True)`, para que no se puedan cerrar en silencio.

TODOS CORREN OFFLINE. Leen tablas del codigo, no llaman al modelo.

Los dos candados de abajo no son pasos: impiden que ARRANQUE.md y pytest
cuenten historias distintas, que es el telefono descompuesto que este repo
ya pago.
"""
import ast
import re
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent


def _cuerpos() -> set:
    from app.core import herramientas as H
    return set(H._CUERPOS)


def _piezas_de(funcion) -> list:
    """Nombres que `salida._pieza` recibe adentro de una puerta, leidos del
    AST. No se pregunta a la puerta: se lee lo que el codigo llama."""
    src = Path(funcion.__code__.co_filename).read_text(encoding="utf-8")
    arbol = ast.parse(src)
    for nodo in arbol.body:
        if isinstance(nodo, ast.FunctionDef) and nodo.name == funcion.__name__:
            nombres = []
            for n in ast.walk(nodo):
                if not isinstance(n, ast.Call):
                    continue
                f = n.func
                if isinstance(f, ast.Name) and f.id == "_pieza" and n.args:
                    arg = n.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        nombres.append(arg.value)
            return nombres
    raise AssertionError(f"no se encontro {funcion.__name__} en su archivo")


# ── FICHA 31 — UNA PUERTA AL CATALOGO ─────────────────────────────────────

_PUERTAS_CATALOGO = (
    "buscar_productos",
    "consultar_catalogo",
    "ficha_producto",
    "ver_compatibilidad",
)


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: FICHA 31. El catalogo tiene UNA puerta interna. HOY hay 4 cuerpos "
    "en `_CUERPOS` que leen el mismo catalogo cambiando la proyeccion: "
    "buscar_productos, consultar_catalogo, ficha_producto, ver_compatibilidad. "
    "El modelo ya no las ve (FICHA 06), pero `_derivar_las_busquedas` sigue "
    "eligiendo entre las cuatro. OBJETIVO 1: un solo cuerpo "
    "`consultar_productos` con un campo de proyeccion. El barrido de "
    "herramientas se reapunta en el MISMO commit: hoy afirma "
    "`len(herramientas()) == 9`."))
def test_el_catalogo_tiene_una_sola_puerta_interna():
    puertas = set(_PUERTAS_CATALOGO) & _cuerpos()
    assert len(puertas) <= 1, (
        f"el catalogo todavia tiene {len(puertas)} puertas internas: "
        + ", ".join(sorted(puertas)))


# ── FICHA 32 — UNA PUERTA A LA PLATA ───────────────────────────────────────

_PUERTAS_PLATA = (
    "cotizar_envio",
    "armar_presupuesto",
    "tomar_pedido",
)


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: FICHA 32. La plata tiene UNA puerta interna. HOY hay 3 cuerpos en "
    "`_CUERPOS` que tocan la cuenta o el cobro: cotizar_envio, "
    "armar_presupuesto, tomar_pedido. Cotizar un envio es un presupuesto con "
    "solo envio, y tomar_pedido no se llamo en los turnos grabados cuando el "
    "modelo elegia: la senal de cobro ya sale por camino_cobro. OBJETIVO 1: "
    "un solo cuerpo `cotizar`. tomar_pedido no queda 'por si acaso'."))
def test_la_plata_tiene_una_sola_puerta_interna():
    puertas = set(_PUERTAS_PLATA) & _cuerpos()
    assert len(puertas) <= 1, (
        f"la plata todavia tiene {len(puertas)} puertas internas: "
        + ", ".join(sorted(puertas)))


# ── FICHA 33 — UN SOLO MUTADOR EN LA HIGIENE ───────────────────────────────

@pytest.mark.xfail(strict=True, reason=(
    "PLAN: FICHA 33. La higiene tiene UN solo mutador. HOY `salida.higiene` "
    "llama a dos `_pieza` que reescriben el texto: componedor y aduana. "
    "mensaje.py, aduana.py e invariantes.py persiguen la repeticion cada uno "
    "por su lado, y esa es la forma de los dos bugs de plata de agosto: "
    "arreglar una pieza rompe la otra. OBJETIVO 1: solo `componer` toca el "
    "texto. La aduana, si queda, mira y no muta."))
def test_la_higiene_tiene_un_solo_mutador():
    from app.core import salida as S
    piezas = _piezas_de(S.higiene)
    assert len(piezas) <= 1, (
        f"la higiene todavia tiene {len(piezas)} mutadores: {piezas}")


# ── FICHA 34 — EL NEXO: EL HUB DEJA DE TENER DOS OPINIONES ───────────────

@pytest.mark.xfail(strict=True, reason=(
    "PLAN: FICHA 34. El hub no llama a reconciliar. HOY `procesar_venta` llama "
    "a `P.reconciliar` despues de derivar las busquedas: es una segunda "
    "opinion sobre el mismo pedido. OBJETIVO 0 llamadas: el resolver arma el "
    "contrato desde lo declarado y no hay nada que reconciliar. Relato en "
    "`arquitectura/FICHA_34_el_nexo.md`."))
def test_el_hub_no_llama_a_reconciliar():
    hub = (_RAIZ / "app" / "core" / "hub_venta.py").read_text(encoding="utf-8")
    assert "reconciliar(" not in hub, (
        "procesar_venta todavia llama al reconciliador: el pedido tiene dos "
        "opiniones")


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: FICHA 34. El hub no llama a reposicion.completar. HOY "
    "`procesar_venta` llama a `R.completar` y reaplica lo declarado. OBJETIVO "
    "0 llamadas: la cuenta y las busquedas las hace `resolver` antes de "
    "redactar, y reposicion.py pasa a archivo/. Relato en "
    "`arquitectura/FICHA_34_el_nexo.md`."))
def test_el_hub_no_llama_a_completar_de_reposicion():
    hub = (_RAIZ / "app" / "core" / "hub_venta.py").read_text(encoding="utf-8")
    assert "R.completar" not in hub, (
        "procesar_venta todavia llama a la reposicion: el codigo reinterpreta "
        "despues de haber derivado")


# ── CANDADOS CONTRA EL TELEFONO DESCOMPUESTO ──────────────────────────────


def _tests_definidos() -> set:
    nombres = set()
    for f in (_RAIZ / "tests").glob("test_*.py"):
        arbol = ast.parse(f.read_text(encoding="utf-8"))
        for n in arbol.body:
            if isinstance(n, ast.FunctionDef) and n.name.startswith("test_"):
                nombres.add(n.name)
    return nombres


def _de_plan() -> list:
    import sys
    tests_dir = str(_RAIZ / "tests")
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    from test_a_medias import _de
    return _de("PLAN:")


def test_arranque_nombra_cada_paso_del_plan():
    """Si pytest muestra un PLAN: y ARRANQUE.md no lo nombra, la sesion nueva
    trabaja la tabla y no el contador. Asi se desincronizaron el 14 y el 11."""
    arranque = (_RAIZ / "ARRANQUE.md").read_text(encoding="utf-8")
    faltan = [nombre for _archivo, nombre, _motivo in _de_plan()
              if nombre not in arranque]
    assert not faltan, (
        "estos pasos del plan no aparecen en ARRANQUE.md:\n  "
        + "\n  ".join(faltan)
        + "\nLa tabla se sincroniza el mismo dia, no se acumula.")


def test_arranque_no_nombra_tests_que_no_existen():
    """FICHA 29 nombro `test_la_cuenta_podada_...` y el test no existia. Un
    nombre entre backticks que no tiene funcion es un paso fantasma: la sesion
    nueva lo busca, no lo encuentra, y o lo reimplementa o lo saltea a ciegas."""
    arranque = (_RAIZ / "ARRANQUE.md").read_text(encoding="utf-8")
    nombrados = re.findall(r"`(test_[a-z0-9_]+)`", arranque)
    definidos = _tests_definidos()
    fantasmas = sorted({n for n in nombrados if n not in definidos})
    assert not fantasmas, (
        "ARRANQUE.md nombra tests que no existen:\n  "
        + "\n  ".join(fantasmas)
        + "\nO se escribe el test, o se saca el nombre. No se trabaja de memoria.")
