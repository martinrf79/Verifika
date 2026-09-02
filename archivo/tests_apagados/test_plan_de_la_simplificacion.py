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


def _nombre_marcado(n: ast.AST) -> str | None:
    """Si la llamada es una de las tres formas de marca, el nombre."""
    if not isinstance(n, ast.Call) or not n.args:
        return None
    f = n.func
    formas = ("_pieza", "paso_datos", "veredicto")
    es = ((isinstance(f, ast.Name) and f.id in formas)
          or (isinstance(f, ast.Attribute) and f.attr in formas))
    if not es:
        return None
    arg = n.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    return None


def _piezas_en(nodo_fn: ast.AST) -> list:
    """Nombres que las tres formas de marca reciben, en orden de fuente.

    ast.walk no sirve: es BFS y visita a los hermanos de un try antes
    que el cuerpo. El orden de la puerta es el de las lineas.
    """
    encontrados = []
    for n in ast.walk(nodo_fn):
        nombre = _nombre_marcado(n)
        if nombre:
            encontrados.append((n.lineno, n.col_offset, nombre))
    encontrados.sort()
    return [nombre for _ln, _col, nombre in encontrados]


def _piezas_de(funcion) -> list:
    """Nombres que una pieza registra adentro de una funcion, leidos del AST.

    Tres formas: `_pieza("x")`, `G.paso_datos("x")`, `G.veredicto("x")`.
    No se pregunta a la puerta: se lee lo que el codigo llama.
    """
    src = Path(funcion.__code__.co_filename).read_text(encoding="utf-8")
    arbol = ast.parse(src)
    for nodo in arbol.body:
        if (isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef))
                and nodo.name == funcion.__name__):
            return _piezas_en(nodo)
    raise AssertionError(f"no se encontro {funcion.__name__} en su archivo")


def _sitios_de_piezas(declarados: set) -> dict:
    """Funciones de app/ con marcas que no son un nodo declarado.

    Filtra los ids de NODOS: `busquedas_derivadas` se registra con
    `G.paso_datos` adentro de `resolver()` y ES un nodo, no una pieza.
    Las cuatro de la cuenta viven en `_aplicar_la_cuenta`.
    `puerta_cobertura` marca con `G.veredicto` en el hub, no en
    `cobertura()`.
    """
    sitios = {}
    for py in (_RAIZ / "app").rglob("*.py"):
        try:
            arbol = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        rel = py.relative_to(_RAIZ).as_posix()
        for nodo in arbol.body:
            if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            nombres = _piezas_en(nodo)
            piezas = tuple(dict.fromkeys(
                x for x in nombres if x not in declarados))
            if piezas:
                sitios[f"{rel}:{nodo.name}"] = piezas
    return sitios


# ── FICHA 31 — UNA PUERTA AL CATALOGO ─────────────────────────────────────

_PUERTAS_CATALOGO = (
    "buscar_productos",
    "consultar_catalogo",
    "ficha_producto",
    "ver_compatibilidad",
)


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


def test_la_plata_tiene_una_sola_puerta_interna():
    puertas = set(_PUERTAS_PLATA) & _cuerpos()
    assert len(puertas) <= 1, (
        f"la plata todavia tiene {len(puertas)} puertas internas: "
        + ", ".join(sorted(puertas)))


# ── FICHA 33/35 — UN SOLO MUTADOR EN LA HIGIENE ────────────────────────────

def test_la_higiene_tiene_un_solo_mutador():
    from app.core import salida as S
    piezas = _piezas_de(S.higiene)
    assert len(piezas) <= 1, (
        f"la higiene todavia tiene {len(piezas)} mutadores: {piezas}")


# ── FICHA 34 — EL NEXO: EL HUB DEJA DE TENER DOS OPINIONES ───────────────

def test_el_hub_no_llama_a_reconciliar():
    hub = (_RAIZ / "app" / "core" / "hub_venta.py").read_text(encoding="utf-8")
    assert "reconciliar(" not in hub, (
        "procesar_venta todavia llama al reconciliador: el pedido tiene dos "
        "opiniones")


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


def _lee_campo_nombre(fn: ast.AST) -> bool:
    """Acceso al campo `nombre` de un pedido: p.get('nombre'), p['nombre']
    o p.nombre. El docstring del modulo no cuenta: vive fuera de la funcion."""
    for n in ast.walk(fn):
        if isinstance(n, ast.Constant) and n.value == "nombre":
            return True
        if isinstance(n, ast.Attribute) and n.attr == "nombre":
            return True
    return False


def test_banco_llamada_uno_puntua_lo_declarado_y_no_el_nombre_de_la_tool():
    """FICHA 40. El banco mira lo que registrar_pedido dejo escrito. Si el
    ok del caso vuelve a salir del nombre de la tool, FICHA 38 queda en
    nada. No corre el banco. No pide clave."""
    src = (_RAIZ / "banco_pruebas" / "banco_llamada_uno.py").read_text(
        encoding="utf-8")
    arbol = ast.parse(src)
    funcs = {n.name: n for n in arbol.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert "_declarado" in funcs and "_evaluar" in funcs and "main" in funcs, (
        "banco_llamada_uno perdio _declarado, _evaluar o main")

    declarado = funcs["_declarado"]
    assert _lee_campo_nombre(declarado), (
        "_declarado ya no busca el pedido por nombre: el banco no apunta "
        "a registrar_pedido")
    constantes = [n.value for n in ast.walk(declarado)
                  if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert "registrar_pedido" in constantes, (
        "_declarado ya no pide registrar_pedido")

    ajenos = sorted(nombre for nombre, fn in funcs.items()
                    if nombre != "_declarado" and _lee_campo_nombre(fn))
    assert not ajenos, (
        "estas funciones leen el nombre de la tool; el resultado del caso "
        f"no puede salir de ahi: {ajenos}")

    asignaciones_ok = []
    for n in ast.walk(funcs["main"]):
        if not isinstance(n, ast.Assign):
            continue
        ids = []
        for t in n.targets:
            if isinstance(t, ast.Name):
                ids.append(t.id)
            elif isinstance(t, ast.Tuple):
                ids += [e.id for e in t.elts if isinstance(e, ast.Name)]
        if "ok" in ids:
            asignaciones_ok.append(n)
    assert len(asignaciones_ok) == 1, (
        f"el ok del caso se asigna {len(asignaciones_ok)} veces; tiene que "
        "salir una sola, de _evaluar")
    val = asignaciones_ok[0].value
    assert (isinstance(val, ast.Call) and isinstance(val.func, ast.Name)
            and val.func.id == "_evaluar"), (
        "el ok del caso ya no sale de _evaluar: el banco volvio a puntuar "
        "otra cosa")
