"""LA CUENTA SOBREVIVE AL TURNO — el carrito y el presupuesto, de ida y vuelta.

DE DONDE SALE, medido en WhatsApp el 15-sep-2026 sobre UN pedido de dos
auriculares, dos mouse y dos memorias:

    turno 2   cuenta AUR0001 x1, MOU0001 x1, RAM0001 x1   total 207.500
    turno 3   cuenta AUR0003 x2, MOU0001 x2, RAM0001 x2   total 284.000
    turno 4   cuenta AUR0001 x2, MOU0001 x2, RAM0001 x2   total 395.000

Ninguna de las tres estaba mal SUMADA. Cada turno eligio productos y
cantidades por su cuenta, porque lo unico que sobrevivia al turno eran los
nombres de lo que se habia mostrado. Y el cuarto turno no llego al cliente: el
modelo escribio $250.000, la guarda de procedencia no lo encontro en ningun
lado y tiro la respuesta entera.

LO QUE ESTA VARA CUIDA son los tres eslabones, porque si se corta uno el
defecto vuelve entero y en silencio: que la cuenta diga QUE hay adentro, que el
turno lo GUARDE, y que el turno siguiente lo VEA.
"""
import asyncio

import pytest

from app.core import motor as MT
from app.core import respuesta as R

TIENDA = "verifika_prod"


@pytest.fixture(autouse=True)
def _doble(firestore_doble):
    from app.core.contexto_turno import set_current_tienda
    from app.core.filtros_catalogo import limpiar_cache
    set_current_tienda(TIENDA)
    limpiar_cache()
    return firestore_doble


def _cuenta(items: list) -> dict:
    return MT.buscar([], TIENDA, "t_carrito",
                     cuenta={"items": items}).get("cuenta") or {}


def test_la_cuenta_dice_que_hay_adentro_del_total():
    """Una cifra suelta no se puede verificar ni volver a pedir. El total viaja
    con sus ids y sus cantidades."""
    c = _cuenta([{"id": "MOU0001", "cantidad": 2}])
    assert c["total_ars"]
    assert c["items"] == [{"id": "MOU0001", "cantidad": 2,
                           "nombre": "Mouse Logitech G203 Lightsync Negro"}]


def test_la_cantidad_del_pedido_no_se_pierde():
    """El cliente pidio DOS. El turno siguiente cotizo UNO. La cantidad tiene
    que viajar con el carrito, no volver a decidirse."""
    c = _cuenta([{"id": "MOU0001", "cantidad": 2},
                 {"id": "RAM0001", "cantidad": 2}])
    assert [i["cantidad"] for i in c["items"]] == [2, 2]


def test_el_turno_siguiente_ve_el_carrito_y_no_el_presupuesto_viejo():
    """El carrito se muestra CON el id, que es con lo que el modelo vuelve a
    pedir la misma cuenta. El presupuesto viejo ya no viaja desde la FICHA 69:
    copiarlo es como salio Posadas con un envio que ya no se cobraba."""
    conv = {"ultimo_presupuesto": "Presupuesto:\n- 2x Mouse: $37.500 c/u = "
                                  "$75.000\nTotal: $75.000",
            "carrito_vigente": [{"id": "MOU0001", "cantidad": 2,
                                 "nombre": "Mouse Logitech G203"}]}
    t = __import__("app.core.ficha_charla", fromlist=["texto"]).texto(conv, "verifika_prod")
    assert "2x MOU0001" in t
    assert "$75.000" not in t
    assert "pedi la cuenta" in t.lower()


def test_el_presupuesto_viejo_no_es_fuente():
    """La otra mitad: un total de antes copiado a mano no llega al cliente. Si
    el cliente lo pide, la cuenta se hace de nuevo en este turno."""
    from app.core import numeros as N
    conv = {"ultimo_presupuesto": "Total: $395.000"}
    texto, informe = N.llenar("Te confirmo el pedido por $395.000.", [], "t",
                              fuente_texto=__import__("app.core.ficha_charla", fromlist=["texto"]).texto(conv, "verifika_prod"))
    assert informe["inventada"] and "395.000" not in texto


def test_una_cuenta_que_no_se_pudo_hacer_no_pisa_la_anterior():
    """`sin_total` no trae `items` ni `total_ars`, asi que el turno no tiene
    con que sobreescribir: lo ultimo que el cliente VIO sigue siendo lo
    ultimo que el modelo ve."""
    c = _cuenta([{"id": "auriculares", "cantidad": 2}])
    assert c.get("sin_total")
    assert "items" not in c and "total_ars" not in c


