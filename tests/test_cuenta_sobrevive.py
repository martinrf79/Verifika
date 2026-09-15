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


def test_el_turno_siguiente_ve_el_presupuesto_y_el_carrito():
    """El otro eslabon: guardado no alcanza si no se muestra. Y se muestra CON
    el id, que es lo unico con lo que el modelo puede volver a pedir la misma
    cuenta."""
    conv = {"ultimo_presupuesto": "Presupuesto:\n- 2x Mouse: $37.500 c/u = "
                                  "$75.000\nTotal: $75.000",
            "carrito_vigente": [{"id": "MOU0001", "cantidad": 2,
                                 "nombre": "Mouse Logitech G203"}]}
    t = R._memoria_texto(conv)
    assert "$75.000" in t
    assert "2x MOU0001" in t
    # LA REGLA DE FRESCURA VA PEGADA AL DATO: sin ella el modelo corrige el
    # total a mano cuando el pedido cambia, que es como vuelve a aparecer una
    # cifra sin procedencia.
    assert "pedi la cuenta de nuevo" in t.lower()


def test_el_presupuesto_viaja_como_FUENTE_y_no_como_invento():
    """La otra mitad del arreglo, y es la que hizo que el cliente se quedara
    sin respuesta: el modelo copia el total del turno anterior y la guarda de
    procedencia tiene que encontrarlo. Si este test se cae, el bot vuelve a
    contestar con el mensaje de sobrecarga."""
    from app.core import numeros as N
    conv = {"ultimo_presupuesto": "Total: $395.000"}
    texto, informe = N.llenar("Te confirmo el pedido por $395.000.", [], "t",
                              fuente_texto=R._memoria_texto(conv))
    assert not informe["inventada"], informe


def test_una_cuenta_que_no_se_pudo_hacer_no_pisa_la_anterior():
    """`sin_total` no trae `items` ni `total_ars`, asi que el turno no tiene
    con que sobreescribir: lo ultimo que el cliente VIO sigue siendo lo
    ultimo que el modelo ve."""
    c = _cuenta([{"id": "auriculares", "cantidad": 2}])
    assert c.get("sin_total")
    assert "items" not in c and "total_ars" not in c


def test_EL_TURNO_ENTERO_deja_el_presupuesto_en_la_charla(firestore_doble,
                                                          monkeypatch):
    """EL ESLABON DEL MEDIO, de punta a punta. Los dos de arriba pueden estar
    sanos y el defecto vivir igual si el turno no llama al save con los
    campos: fue exactamente asi durante meses, con los dos campos en la
    memoria y nadie escribiendolos."""
    cuenta = {"total_ars": 75000, "total": "$75.000",
              "detalle": "Presupuesto:\n- 2x Mouse: $37.500 c/u = $75.000\n"
                         "Total: $75.000",
              "items": [{"id": "MOU0001", "cantidad": 2, "nombre": "Mouse"}]}
    monkeypatch.setattr(
        R, "_preguntar",
        lambda *a, **k: asyncio.sleep(
            0, result=({"tipo": "precio_multiple", "texto": "Son $75.000."},
                       [], {}, cuenta, R._informe_en_blanco())))
    asyncio.run(R.procesar_turno("sonda_carrito", "dos mouse cuanto sale",
                                 TIENDA, "telegram", "trace_carrito"))
    from app.storage.firestore_client import get_conversation
    conv = get_conversation("sonda_carrito", tienda_id=TIENDA) or {}
    assert "$75.000" in (conv.get("ultimo_presupuesto") or "")
    assert conv.get("carrito_vigente") == cuenta["items"]
    # Y LA VUELTA COMPLETA: lo guardado es lo que el turno siguiente lee.
    assert "2x MOU0001" in R._memoria_texto(conv)
