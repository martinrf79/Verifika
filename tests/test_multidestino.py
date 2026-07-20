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


# ── CHARLA REAL 19-jul (trace 8507a0b6): 6 productos, TRES destinos con grupos.
# El bot cobro "2 envios gratis": destinos basura del regex ("san francisco
# es", "la otra direccion"), dos destinos reales perdidos ("iran a" no estaba
# en el regex) y el umbral de gratis aplicado al subtotal TOTAL. Estos locks
# fijan la cadena entera del arreglo.

_MSG_REAL_3DEST = (
    "Hola Quiero precio de dos Notebook 2 teclados y dos auriculares los "
    "cuales van a ser enviados a tres destinos unos irán a palpalá Jujuy el "
    "otro irá a Correa Santa Fe y el otro irá a San Francisco Córdoba el "
    "envío de Jujuy es una Notebook y un auricular el envío a San Francisco "
    "es un auricular y un teclado y los dos productos que faltan van a la "
    "otra dirección Dime O dame precio de los de buena calidad Confío en tu "
    "elección")


def test_extraccion_destinos_charla_real_3_destinos(firestore_doble):
    """Los 3 destinos reales salen CON provincia; la basura no entra y el
    mismo lugar re-nombrado no duplica."""
    from app.core.guia_pedido import _hitos_destinos, _norm
    hitos = [h[0] for h in _hitos_destinos(_norm(_MSG_REAL_3DEST))]
    assert hitos == ["palpala jujuy", "correa santa fe",
                     "san francisco cordoba"]


def test_destino_referencia_y_no_lugar_no_valen(firestore_doble):
    from app.core.guia_pedido import _es_destino_real
    assert not _es_destino_real("la otra direccion")
    assert not _es_destino_real("tres destinos")
    assert _es_destino_real("san francisco es")  # nombra un lugar real
    assert _es_destino_real("palpala")


def test_provincia_sticky_no_completa_basura(firestore_doble):
    """'la otra direccion' + provincia en memoria ya NO cotiza."""
    from app.core.tools import cotizar_envio
    from app.core.tools_context import set_current_tienda
    from app.core.estado_venta import set_current_estado
    set_current_tienda("verifika_prod")
    set_current_estado({"provincia_envio": "santa fe"})
    try:
        assert not cotizar_envio(localidad="la otra direccion").get("ok")
        assert cotizar_envio(localidad="correa").get("ok")
    finally:
        set_current_estado(None)


def test_grupos_del_mensaje_charla_real(firestore_doble):
    """El fraseo 'el envio de Jujuy es una notebook y un auricular' + 'los
    que faltan van a la otra direccion' parsea los TRES grupos exactos."""
    from app.core.guia_pedido import grupos_envio_del_mensaje
    cats = [(2, "notebook"), (2, "teclado"), (2, "auriculares")]
    grupos = grupos_envio_del_mensaje(_MSG_REAL_3DEST, cats, "verifika_prod")
    assert dict(grupos) == {
        "palpala jujuy": [(1, "notebook"), (1, "auriculares")],
        "san francisco cordoba": [(1, "auriculares"), (1, "teclado")],
        "correa santa fe": [(1, "notebook"), (1, "teclado")],
    }


def test_grupos_que_no_reconcilian_devuelven_vacio(firestore_doble):
    """Un grupo que pide mas de lo que hay -> [] (todo-o-nada)."""
    from app.core.guia_pedido import grupos_envio_del_mensaje
    cats = [(1, "notebook")]
    msg = ("una notebook, el envio de jujuy es dos notebook "
           "y lo demas va a rosario")
    assert grupos_envio_del_mensaje(msg, cats, "verifika_prod") == []


def test_umbral_de_gratis_por_grupo_charla_real(firestore_doble):
    """La plata del caso real: Jujuy ($750.500) y Correa ($705.000) superan
    el umbral de $250.000 y van gratis; San Francisco ($69.500) NO lo supera
    y paga la tarifa de Cordoba. Antes el promedio regalaba los tres."""
    from app.core.tools import calculate_total, cotizar_envio
    from app.core.tools_context import set_current_tienda
    from app.core.estado_venta import set_current_estado
    set_current_tienda("verifika_prod")
    set_current_estado({})  # resetea las localidades del turno
    for loc in ("palpala jujuy", "correa santa fe", "san francisco cordoba"):
        assert cotizar_envio(localidad=loc).get("ok")
    grupos = [
        {"destino": "palpala jujuy", "cats": [(1, "notebook"), (1, "auriculares")]},
        {"destino": "correa santa fe", "cats": [(1, "notebook"), (1, "teclado")]},
        {"destino": "san francisco cordoba", "cats": [(1, "auriculares"), (1, "teclado")]},
    ]
    res = calculate_total(
        items=[{"product_id": "NOT0019", "cantidad": 2},
               {"product_id": "TEC0020", "cantidad": 2},
               {"product_id": "AUR0019", "cantidad": 2}],
        items_extra=[{"faq_tema": "costo_envio", "concepto": "envio"}],
        destinos=3, grupos=grupos)
    set_current_estado(None)
    assert res.get("ok"), res
    envio = next(e for e in res["extras"]
                 if e.get("faq_tema") == "costo_envio")
    assert envio["monto"] == 7500, envio
    assert res["total_ars"] == 1_525_000 + 7500


def test_juez_envios_perdidos_acusa(firestore_doble):
    """Presupuesto que cobra 2 envios cuando el mensaje declara 3 destinos."""
    from banco_pruebas.juez import juzgar
    r = "Presupuesto:\n- 2x Algo: $10 c/u = $20\nEnvio (2 envios): gratis\nTotal: $20"
    assert any("envios perdidos" in p
               for p in juzgar(r, mensaje=_MSG_REAL_3DEST))


def test_juez_envios_completos_no_acusa(firestore_doble):
    from banco_pruebas.juez import juzgar
    r = "Presupuesto:\n- 2x Algo: $10 c/u = $20\nEnvio (3 envios): $7.500\nTotal: $27.520"
    assert not any("envios perdidos" in p
                   for p in juzgar(r, mensaje=_MSG_REAL_3DEST))


def test_reparto_detalle_gratis_por_grupo_consistente(firestore_doble):
    """El detalle del reparto cotiza cada tramo con el subtotal de SU paquete:
    los grupos que superan el umbral dicen gratis, el chico dice su tarifa.
    Asi el reparto y el total del presupuesto cuentan la misma plata."""
    from app.core.guia_pedido import reparto_envios_detalle
    from app.core.tools_context import set_current_tienda
    from app.core.estado_venta import set_current_estado
    set_current_tienda("verifika_prod")
    set_current_estado({})
    detalle = [
        {"id": "NOT0019", "precio_unitario": 693000, "cantidad": 2},
        {"id": "TEC0020", "precio_unitario": 12000, "cantidad": 2},
        {"id": "AUR0019", "precio_unitario": 57500, "cantidad": 2},
    ]
    cats = [(2, "notebook"), (2, "teclado"), (2, "auriculares")]
    txt, tools = reparto_envios_detalle(_MSG_REAL_3DEST, cats,
                                        "verifika_prod",
                                        detalle_items=detalle)
    set_current_estado(None)
    assert txt, "el reparto no salio"
    assert "A Palpala Jujuy: 1 notebook y 1 auricular — envío gratis" in txt
    assert "A Correa Santa Fe: 1 notebook y 1 teclado — envío gratis" in txt
    assert ("A San Francisco Cordoba: 1 auricular y 1 teclado — envío $7.500"
            in txt)


def test_reseteo_de_mitad_de_turno_no_borra_cotizadas(firestore_doble):
    """Las localidades cotizadas del turno sobreviven al re-seteo del
    generador (inicio_turno=False); el reseteo del arranque si limpia.
    Era el agujero por el que la memoria de destinos no persistia y el
    envio se caia del total al confirmar (guion 48, 20-jul)."""
    from app.core.estado_venta import (set_current_estado,
                                       set_envio_localidad,
                                       get_envio_localidades)
    set_current_estado({})
    set_envio_localidad("palpala jujuy")
    set_current_estado({}, inicio_turno=False)
    assert get_envio_localidades() == ["palpala jujuy"]
    set_current_estado({})
    assert get_envio_localidades() == []


def test_grupos_para_calculo_reusa_la_memoria(firestore_doble):
    """'dale, confirmalo' no repite los grupos: salen de la memoria de la
    charla y el nuevo computo queda en el estado para persistir."""
    from app.core.guia_pedido import grupos_para_calculo
    from app.core.estado_venta import set_current_estado, get_current_estado
    g_mem = [{"destino": "palpala jujuy", "cats": [[1, "notebook"]]},
             {"destino": "correa santa fe", "cats": [[1, "teclado"]]}]
    set_current_estado({"grupos_envio": g_mem})
    g = grupos_para_calculo("dale, confirmalo",
                            ["palpala jujuy", "correa santa fe"],
                            "verifika_prod")
    assert g == g_mem
    assert get_current_estado()["grupos_envio"] == g_mem
    set_current_estado(None)
