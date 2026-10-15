"""EL TECHO DEL CODIGO — que `app/` no crezca (15-oct-2026, pedido de Martin).

POR QUE. El codigo ya es demasiado grande para revisarlo o auditarlo, y cada
linea de mas es un lugar mas donde puede vivir una falla. La interpretacion de
la ficha 9 entra REEMPLAZANDO la lectura de `tablero.py`, no al lado: este
candado lo hace cumplir.

Cuenta todas las lineas de los `.py` de `app/`. El techo SOLO BAJA, como los de
`A MEDIAS` y `PLAN`: subirlo es una decision de Martin, en su propio commit y
con las cuentas escritas. Si el codigo bajo mas de cien lineas, el techo se baja
al numero nuevo, tambien en su propio commit.
"""
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TECHO = os.path.join(RAIZ, "tests", "lineas_techo.json")
HOLGURA = 100


def lineas_app() -> int:
    total = 0
    for base, _, archivos in os.walk(os.path.join(RAIZ, "app")):
        for a in archivos:
            if a.endswith(".py"):
                with open(os.path.join(base, a), encoding="utf-8") as f:
                    total += sum(1 for _ in f)
    return total


def techo() -> int:
    return json.load(open(TECHO, encoding="utf-8"))["lineas_app"]


def test_el_codigo_no_crece():
    n = lineas_app()
    assert n <= techo(), (
        f"app/ tiene {n} lineas contra un techo de {techo()}: {n - techo()} de mas. "
        "Lo nuevo entra reemplazando lo viejo, no al lado.")
    print(f"\nCODIGO: {n} lineas en app/, techo {techo()}")


def test_el_techo_esta_al_dia():
    """Si el codigo bajo y el techo no, lo borrado puede volver a crecer gratis."""
    n = lineas_app()
    assert techo() - n <= HOLGURA, (
        f"el techo quedo {techo() - n} lineas por encima del codigo real ({n}): "
        "bajalo en su propio commit")
