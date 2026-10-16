"""LAS ONCE CAPAS DE CORRECCION — el plan 3 de CLAUDE.md, como test (16-oct-2026, pedido de Martin).

POR QUE. Las once capas de `app/core/tablero.py` que corrigen la salida del interprete estaban escritas en
CLAUDE.md y en ningun otro lado: ninguna sesion las veia caer, y el plan se olvidaba. Ahora cada una es un xfail
estricto. `pytest` dice cuantas quedan; la que se saca da XPASS y el test se pone rojo hasta que se borre su renglon
de aca, en el mismo commit que la saca. El criterio para sacarla es el de CLAUDE.md, seccion 1: una por commit,
medida con `banco_pruebas/puerta.py`.
"""
import pytest

from app.core import tablero as T

# (lo que vive en tablero, lo que hace). Banderas y GUIAS son la misma capa: la tercera llamada al modelo.
CAPAS = [
    ("_reparto_leido", "relee el reparto del pago en el mensaje"),
    ("_sobre_el_pedido", "rearma el pedido guardado"),
    ("_envios_juntos", "junta los envios en una pieza"),
    ("_normalizar", "ajusta las piezas al vocabulario"),
    ("_sobre_lo_buscado", "suma las condiciones de la busqueda anterior"),
    ("_heredar_exclusiones", "copia las exclusiones de la memoria"),
    ("_conservar", "compara los articulos contra lo repartido"),
    ("_resolver_items", "elige que producto es cada articulo"),
    ("_elegidos", "elige que producto es cada articulo, por lo que dijo el cliente"),
    ("_cuenta_del_codigo", "arma la cuenta que el interprete no pidio"),
    ("_revision", "segunda llamada al modelo para corregir"),
    ("GUIAS", "tercera llamada al modelo, con preguntas de si o no"),
]


@pytest.mark.parametrize("nombre,que_hace", CAPAS, ids=[c[0] for c in CAPAS])
@pytest.mark.xfail(strict=True, reason="PLAN: la capa sale con su arreglo en la causa, CLAUDE.md seccion 1, plan 3")
def test_la_capa_ya_no_esta(nombre, que_hace):
    assert not hasattr(T, nombre), f"{nombre} sigue en tablero: {que_hace}"


def test_cuantas_capas_quedan():
    """Cuantas, no solo que estan: once capas, doce nombres."""
    quedan = [n for n, _ in CAPAS if hasattr(T, n)]
    print(f"\nCAPAS DE CORRECCION: quedan {len(quedan)} de {len(CAPAS)} nombres")
    assert len(CAPAS) == 12
