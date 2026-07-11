"""
MULTI-DESTINO (las dos charlas reales del 10-jul): un pedido repartido entre
varias localidades cobraba UN solo envio. Locks:
1. cotizar_destinos_del_mensaje saca y cotiza TODOS los destinos del mensaje,
   incluida la forma "sera enviado a X".
2. El camino sellado (_calcular_items_sellados) cobra un envio por destino.
3. Un destino AMBIGUO (Isla Verde existe en tres provincias) no se adivina ni
   se calla: el mensaje sellado pide la provincia (completitud).
"""
import pytest

from app.core.guia_pedido import (cotizar_destinos_del_mensaje,
                                  pregunta_destinos_pendientes,
                                  calcular_categorias_baratas)
from app.core.tools_context import set_current_tienda

_M_1215 = ("Dame precio de dos teclados dos Mouse y dos auriculares los mas "
           "baratos que tengas de colores en distinto un teclado y un mouse "
           "envio a Rio tercero un auricular y un teclado envio a Isla Verde "
           "y el resto envio a serodino dime cuanto tiempo demora")
_M_1516 = ("Hola quisiera preguntar precio por dos Mouse dos teclados y dos "
           "auriculares los mas baratos que tengan el un Mouse y un teclado "
           "es envio a Rosario un teclado y un auricular es envio a Concordia "
           "y lo demas sera enviado a Rio cuarto Pasame los precios y Cuales "
           "serian las modalidades de pagos")


@pytest.fixture(autouse=True)
def _doble(firestore_doble):
    set_current_tienda("verifika_prod")
    yield


def test_extrae_y_cotiza_los_tres_destinos_de_la_charla_1516():
    assert cotizar_destinos_del_mensaje(_M_1516) == [
        "rosario", "concordia", "rio cuarto"]


def test_charla_1215_cotiza_dos_y_pide_la_provincia_del_ambiguo():
    locs = cotizar_destinos_del_mensaje(_M_1215)
    assert locs == ["rio tercero", "serodino"]
    pregunta = pregunta_destinos_pendientes(_M_1215)
    assert "Isla Verde" in pregunta
    assert "provincia" in pregunta


def test_camino_sellado_cobra_un_envio_por_destino():
    # El nucleo sellado con el mensaje de las 15:16: tres destinos -> el
    # calculate_total sale con destinos=3 y el envio del proof suma los tres.
    entradas = calcular_categorias_baratas(
        [(2, "mouse"), (2, "teclado"), (2, "auriculares")],
        {}, "verifika_prod", "test-md", mensaje=_M_1516)
    assert entradas, "la guia no calculo"
    args = entradas[0]["args"]
    res = entradas[0]["result"]
    assert args["destinos"] == 3
    assert res.get("ok") is True
    # Tres envios cobrados: el detalle de extras trae tres montos de envio o
    # un monto agregado mayor que el de UN envio interior ($6.000-9.500).
    present = res.get("presentacion") or ""
    assert "Envio" in present or "envio" in present.lower()
    total = res.get("total_ars") or 0
    subtotal = res.get("subtotal_productos_ars") or 0
    assert total - subtotal >= 3 * 5000, (
        f"envio total {total - subtotal}: no parece cobrar 3 destinos")


def test_un_solo_destino_no_regresiona():
    entradas = calcular_categorias_baratas(
        [(2, "mouse")], {}, "verifika_prod", "test-md2",
        mensaje="dame 2 mouse los mas baratos con envio a cordoba capital")
    assert entradas and entradas[0]["args"]["destinos"] == 1
    assert pregunta_destinos_pendientes(
        "dame 2 mouse con envio a cordoba capital") == ""


# --- REPARTO DE ENVIOS POR GRUPO (charla real de Martin, 11-jul 10:42) ---

def test_reparto_charla_real_de_martin(firestore_doble):
    from app.core.tools_context import set_current_tienda
    from app.core.estado_venta import set_current_estado
    from app.core.guia_pedido import reparto_envios_detalle
    set_current_tienda("verifika_prod")
    set_current_estado({})
    msg = ("Hola quisiera preguntar precio por dos Mouse dos teclados y dos "
           "auriculares los más baratos que tengan el un Mouse y un teclado "
           "es envío a Rosario un teclado y un auricular es envío a "
           "Concordia y lo demás será enviado a Río cuarto Pásame los "
           "precios y Cuáles serían las modalidades de pagos")
    texto, tools = reparto_envios_detalle(
        msg, [(2, "mouse"), (2, "teclado"), (2, "auriculares")],
        "verifika_prod")
    assert "A Rosario: 1 mouse y 1 teclado" in texto
    assert "A Concordia: 1 teclado y 1 auricular" in texto
    assert "A Rio Cuarto: 1 auricular y 1 mouse" in texto
    # cada tramo con su proof para el verificador
    assert len(tools) == 3
    assert all(t["name"] == "cotizar_envio" for t in tools)


def test_reparto_que_no_reconcilia_no_sale(firestore_doble):
    from app.core.tools_context import set_current_tienda
    from app.core.estado_venta import set_current_estado
    from app.core.guia_pedido import reparto_envios_detalle
    set_current_tienda("verifika_prod")
    set_current_estado({})
    # un grupo pide MAS de lo que hay: todo o nada, sin detalle
    t, _ = reparto_envios_detalle(
        "un mouse va a Rosario y tres teclados a Salta",
        [(2, "mouse"), (2, "teclado")], "verifika_prod")
    assert t == ""
    # un solo destino: no es reparto
    t, _ = reparto_envios_detalle(
        "2 mouse y 2 teclados con envio a Cordoba",
        [(2, "mouse"), (2, "teclado")], "verifika_prod")
    assert t == ""
