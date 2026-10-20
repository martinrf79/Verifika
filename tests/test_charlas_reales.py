"""LAS CHARLAS REALES DE WHATSAPP, OTRA VEZ POR EL FLUJO VIVO — sin modelo (20-oct-2026).

Cada charla de `banco_pruebas/reales/` trae lo que mando el cliente y la agenda que devolvio el interprete en
produccion. Se repite turno por turno por el webhook entero del clon, como `cableado58`, con esas agendas, y se
controlan las clases que fallaron en vivo:

  el cierre no repite la cuenta que el cliente acaba de leer, ni deja un titulo suelto;
  con el pedido armado, una pregunta de la FAQ no termina invitando a elegir un producto;
  lo que el codigo elige de un rubro entra al pedido con aviso, se haya buscado el rubro o no.
"""
import json

import pytest

from banco_pruebas import cableado58 as R


def _charla(id_: str) -> dict:
    return json.load(open(f"banco_pruebas/reales/{id_}.json", encoding="utf-8"))


@pytest.fixture(scope="module")
def joaquin():
    """La de los siete articulos a tres destinos del 20-oct, 15:26, que cerro con nombre y pago."""
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    it = R.instalar()
    c = _charla("f95def4b1d")
    charla = {"id": "real_" + c["id"], "turnos": [{"texto": t["mensaje"], "casillas": []} for t in c["turnos"]]}
    turnos = R.correr(charla, [t["agenda"] for t in c["turnos"]], it, {})
    yield [t["respuesta"] for t in turnos]
    llm_reintento._cliente = puerta


def test_el_cierre_no_repite_la_cuenta_recien_leida(joaquin):
    pide_nombre, cierre = joaquin[-2], joaquin[-1]
    assert "Presupuesto:" in pide_nombre and "nombre" in pide_nombre
    assert "tomamos tu pedido" in cierre
    assert "Presupuesto:" not in cierre and "Resumen:" not in cierre, cierre


def test_con_pedido_la_faq_no_invita_a_elegir_producto(joaquin):
    from app.core.flujo import catalogo  # noqa: F401 — el clon ya instalo la FAQ del repo
    from app.storage.firestore_client import get_all_faq
    faq = get_all_faq(tienda_id="verifika_prod")["formas_pago"]
    medios = joaquin[2]
    assert faq["respuesta"] in medios, medios
    assert faq["respuesta_curada"][-60:] not in medios


def test_lo_elegido_sin_buscar_se_avisa(joaquin):
    # El teclado se pidio sin buscar su rubro: entra al pedido como lo eligio el codigo, y se dice.
    con_pedido = next(r for r in joaquin if "Teclado" in r and "Presupuesto:" in r)
    assert "Para el presupuesto tomé" in con_pedido and "teclado" in con_pedido.split("Para el presupuesto tomé")[1]
