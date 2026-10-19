"""LAS 58 POR EL FLUJO VIVO, SIN MODELO — la vara fija desde el 19-oct-2026, pedido de Martin.

Cada charla de las 58 de `vara_58.json`, mas las complejas de varios rubros a varios destinos que ya entraron
—`cableado58.COMPLEJAS`—, pasa por el webhook entero del clon, turno por turno, con la traduccion del
interprete escrita a mano en `banco_pruebas/traducciones58.py`, y se califica con sus casillas. Es lo mismo que
`python3 -m banco_pruebas.cableado58`. Corre en cada push, antes del deploy: una charla que se rompe frena el deploy.

Ninguna llamada al modelo: si alguna pieza del camino lo intenta, el test falla aunque esa pieza se trague el error.
"""
import pytest

from banco_pruebas import cableado58 as R
from banco_pruebas.traducciones58 import EXPLICAR, T

CHARLAS = R.charlas()


@pytest.fixture(scope="module")
def interprete():
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    it = R.instalar()
    yield it
    llm_reintento._cliente = puerta


def test_son_las_58_y_las_complejas_y_cada_turno_tiene_su_traduccion():
    assert len(CHARLAS) == 58 + len(R.COMPLEJAS)
    for c in CHARLAS:
        assert len(T[c["id"]]) == len(c["turnos"]), c["id"]
    print(f"\nCABLEADO: {len(CHARLAS)} charlas, {sum(len(c['turnos']) for c in CHARLAS)} turnos")


@pytest.mark.parametrize("charla", CHARLAS, ids=[c["id"] for c in CHARLAS])
def test_la_charla_sale_bien(interprete, charla):
    antes = len(R.LLAMADAS_AL_MODELO)
    turnos = R.correr(charla, T[charla["id"]], interprete, EXPLICAR)
    malas = [n for t in turnos for n, ok in t["casillas"] if ok is not True]
    assert len(R.LLAMADAS_AL_MODELO) == antes, "algo intento llamar al modelo"
    assert not malas, f"{charla['id']}: {malas}\n" + "\n".join(t["respuesta"] for t in turnos)
