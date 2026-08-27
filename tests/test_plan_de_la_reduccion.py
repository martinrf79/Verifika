"""
LOS DOS TERMOMETROS DE LA REDUCCION.

HOY app/ tiene 604 funciones y 24355 lineas, medido leyendo el arbol, no
copiado de un markdown. OBJETIVO el 30%: 181 funciones y 7306 lineas.

Cierran en la FICHA 36, cuando lo apagado ya no esta en app/. Las fichas 34
y 35 los bajan; no se les saca la marca antes a menos que ya pasen.

Prioridad uno manda: si para llegar al numero hay que sacar certificacion,
calculadora o el contrato, el corte esta mal y se revierte. El 25% (151
funciones, 6089 lineas) es piso si entra solo, no vara para forzar.
"""
import ast
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
_APP = _RAIZ / "app"

_OBJETIVO_FUNCIONES = 181
_OBJETIVO_LINEAS = 7306


def _funciones() -> int:
    n = 0
    for f in _APP.rglob("*.py"):
        if "__pycache__" in str(f):
            continue
        arbol = ast.parse(f.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not nodo.name.startswith("__"):
                    n += 1
    return n


def _lineas() -> int:
    n = 0
    for f in _APP.rglob("*.py"):
        if "__pycache__" in str(f):
            continue
        n += len(f.read_text(encoding="utf-8").splitlines())
    return n


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: FICHA 36. app/ queda en el 30% de funciones. HOY 604 funciones en "
    "app/, medido por ast. OBJETIVO 181 (el 30%). Relato y que se queda vs "
    "que va a archivo/ en arquitectura/PLAN_REDUCCION.md. No se cierra "
    "borrando certificacion ni calculadora."))
def test_app_tiene_a_lo_sumo_ciento_ochenta_funciones():
    hoy = _funciones()
    assert hoy <= _OBJETIVO_FUNCIONES, (
        f"app/ todavia tiene {hoy} funciones; el 30% es {_OBJETIVO_FUNCIONES}")


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: FICHA 36. app/ queda en el 30% de lineas. HOY 24355 lineas en "
    "app/**/*.py. OBJETIVO 7306 (el 30%). El 25% son 6089 y es piso si el "
    "corte lo da, no una vara para forzar. Misma ficha que el termometro "
    "de funciones: arquitectura/PLAN_REDUCCION.md."))
def test_app_pesa_a_lo_sumo_siete_mil_trescientas_lineas():
    hoy = _lineas()
    assert hoy <= _OBJETIVO_LINEAS, (
        f"app/ todavia pesa {hoy} lineas; el 30% es {_OBJETIVO_LINEAS}")
