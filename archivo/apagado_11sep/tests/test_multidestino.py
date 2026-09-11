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
                                  pregunta_destinos_pendientes)
from app.core.contexto_turno import set_current_tienda

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


# calcular_categorias_baratas del snapshot importa mas_barato_con_stock, que
# salio de app/ con esta ficha. Esos tests del sello salieron con ella.

# --- REPARTO DE ENVIOS POR GRUPO (charla real de Martin, 11-jul 10:42) ---

def test_reparto_charla_real_de_martin(firestore_doble):
    from app.core.contexto_turno import set_current_tienda
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
    from app.core.contexto_turno import set_current_tienda
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
    from app.core.calculadora import cotizar_envio
    from app.core.contexto_turno import set_current_tienda
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
    from app.core.calculadora import calculate_total, cotizar_envio
    from app.core.contexto_turno import set_current_tienda
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






def test_reparto_detalle_gratis_por_grupo_consistente(firestore_doble):
    """El detalle del reparto cotiza cada tramo con el subtotal de SU paquete:
    los grupos que superan el umbral dicen gratis, el chico dice su tarifa.
    Asi el reparto y el total del presupuesto cuentan la misma plata."""
    from app.core.guia_pedido import reparto_envios_detalle
    from app.core.contexto_turno import set_current_tienda
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


# ── EL UMBRAL POR PAQUETE, RECONECTADO (10-ago) ──────────────────────────────
def test_el_envio_gratis_se_decide_por_paquete_y_no_por_el_promedio(
        firestore_doble):
    """LA PIEZA QUE ESTABA DESENCHUFADA, y es plata en cada venta repartida.

    `calculate_total` sabe desde el 19-jul decidir el envio gratis con el
    subtotal REAL de cada paquete, pero pide los `grupos` y `armar_presupuesto`
    -la herramienta que el hub llama de verdad- nunca se los pasaba. La pieza
    quedo inalcanzable y el envio volvio a decidirse por el PROMEDIO.

    Medido: una notebook de $727.500 a Cordoba y un mouse de $37.500 a Rosario
    dan un promedio que pasa el umbral, asi que la tienda regalaba los DOS
    envios. Con el umbral por paquete el mouse paga el suyo.
    """
    from app.core import herramientas as H
    from app.core.estado_venta import set_current_estado
    from app.storage.firestore_client import get_all_products
    set_current_tienda("verifika_prod")
    set_current_estado({})

    prods = get_all_products(tienda_id="verifika_prod")
    con_stock = [p for p in prods if int(p.get("stock") or 0) > 0]
    cara = next(p for p in con_stock
                if p["categoria"] == "notebook" and int(p["precio_ars"]) > 600000)
    barata = next(p for p in con_stock
                  if p["categoria"] == "mouse" and int(p["precio_ars"]) < 50000)

    items = [H.ItemPedido(product_id=cara["id"], cantidad=1, destino="Cordoba"),
             H.ItemPedido(product_id=barata["id"], cantidad=1, destino="Rosario")]

    # 1. El codigo arma los grupos desde el reparto YA declarado, en el orden
    #    en que se cotiza. Sin esto la cuenta le pone un paquete al otro envio.
    grupos = H._grupos_de_los_items(items, ["Cordoba", "Rosario"],
                                    "verifika_prod")
    assert [g["destino"] for g in grupos] == ["Cordoba", "Rosario"]
    assert grupos[0]["cats"] == [{"n": 1, "cat": "notebook"}]
    assert grupos[1]["cats"] == [{"n": 1, "cat": "mouse"}]

    # 2. Y el envio del paquete chico se COBRA.
    r = H.armar_presupuesto(H.ArmarPresupuesto(items=items), "verifika_prod")
    assert r["estado"] == "ok", r
    assert "gratis" not in r["bloque"].lower(), (
        "el envio del paquete chico se regalo otra vez:\n" + r["bloque"])


def test_sin_reparto_declarado_no_se_inventan_grupos(firestore_doble):
    """TODO-O-NADA. Un item sin destino deja el reparto incompleto, y un grupo
    incompleto miente el subtotal de su paquete: peor que el promedio. Ahi no
    se manda ningun grupo y la cuenta sigue como siempre."""
    from app.core import herramientas as H
    set_current_tienda("verifika_prod")
    items = [H.ItemPedido(product_id="MOU0001", cantidad=1, destino="Cordoba"),
             H.ItemPedido(product_id="MOU0002", cantidad=1)]
    assert H._grupos_de_los_items(items, ["Cordoba", "Rosario"],
                                  "verifika_prod") == []
    # Y con un solo destino tampoco: no hay paquetes que separar.
    uno = [H.ItemPedido(product_id="MOU0001", cantidad=1, destino="Cordoba")]
    assert H._grupos_de_los_items(uno, ["Cordoba"], "verifika_prod") == []


# ── EL REPARTO NO SE VUELVE A PEDIR (charla real del 12-ago) ─────────────────
def _items_de_la_charla_del_12ago():
    """Los tres productos de la charla real: 2 auriculares, 2 mouse, 2 memorias,
    repartidos de a dos entre Cordoba Capital, Concordia y Posadas."""
    from app.core import herramientas as H
    return [H.ItemPedido(product_id="AUR0020", cantidad=2),
            H.ItemPedido(product_id="MOU0023", cantidad=2),
            H.ItemPedido(product_id="RAM0001", cantidad=2)]


_DESTINOS_12AGO = ["Córdoba Capital", "Concordia", "Posadas"]
_MEMORIA_12AGO = [
    {"destino": "Córdoba Capital",
     "cats": [{"n": 1, "cat": "auriculares"}, {"n": 1, "cat": "mouse"}]},
    {"destino": "Concordia",
     "cats": [{"n": 1, "cat": "memoria ram"}, {"n": 1, "cat": "mouse"}]},
    {"destino": "Posadas",
     "cats": [{"n": 1, "cat": "auriculares"}, {"n": 1, "cat": "memoria ram"}]},
]


def test_el_reparto_ya_cerrado_no_se_vuelve_a_pedir(firestore_doble):
    """LA FALLA REAL, medida en produccion el 12-ago sobre la charla de Martin.

    Turno 14: el modelo declara el reparto entero y la cuenta sale con su
    bloque escrito, destino por destino. Turno 16: MISMO carrito, el modelo se
    olvida de repetir el destino de cada item, y el bloque salio 'me faltan 6
    de 6 unidades sin asignar: decime que va a cada uno'. Le pidio al cliente
    un dato que el cliente ya habia dado dos turnos antes.

    Con el reparto en la memoria de la charla, la cuenta lo repone sola.
    """
    from app.core import herramientas as H
    from app.core.estado_venta import set_current_estado
    set_current_tienda("verifika_prod")
    set_current_estado({"grupos_envio": _MEMORIA_12AGO})
    try:
        r = H.armar_presupuesto(
            H.ArmarPresupuesto(items=_items_de_la_charla_del_12ago(),
                               destinos=_DESTINOS_12AGO),
            "verifika_prod")
        assert r["estado"] == "ok", r
        bloque = r["bloque"]
        assert "sin asignar" not in bloque, (
            "volvio a pedir el reparto que la charla ya cerro:\n" + bloque)
        for d in _DESTINOS_12AGO:
            assert d in bloque, f"falta el destino {d} en el reparto:\n{bloque}"
    finally:
        set_current_estado(None)


def test_el_reparto_repuesto_manda_los_grupos_al_umbral_por_paquete(
        firestore_doble):
    """No es solo texto: el reparto repuesto es el que decide el envio gratis
    por paquete. Si se repusiera solo para escribirlo, la plata seguiria
    saliendo del promedio."""
    from app.core import herramientas as H
    from app.core.estado_venta import set_current_estado
    set_current_tienda("verifika_prod")
    set_current_estado({"grupos_envio": _MEMORIA_12AGO})
    try:
        repuestos = H._items_con_destino_de_memoria(
            _items_de_la_charla_del_12ago(), _DESTINOS_12AGO, "verifika_prod")
        assert repuestos, "no repuso el reparto"
        grupos = H._grupos_de_los_items(repuestos, _DESTINOS_12AGO,
                                        "verifika_prod")
        assert [g["destino"] for g in grupos] == _DESTINOS_12AGO
        assert sum(c["n"] for g in grupos for c in g["cats"]) == 6
    finally:
        set_current_estado(None)


def test_no_se_repone_el_reparto_si_el_pedido_cambio(firestore_doble):
    """TODO-O-NADA, igual que el resto del reparto. Si el pedido ya no es el
    mismo -se sumo un producto- la memoria no cuadra y no se repone nada:
    inventarle al cliente a donde va lo que agrego seria peor que preguntarle.
    """
    from app.core import herramientas as H
    from app.core.estado_venta import set_current_estado
    set_current_tienda("verifika_prod")
    set_current_estado({"grupos_envio": _MEMORIA_12AGO})
    try:
        items = _items_de_la_charla_del_12ago() + [
            H.ItemPedido(product_id="TEC0020", cantidad=1)]
        assert H._items_con_destino_de_memoria(
            items, _DESTINOS_12AGO, "verifika_prod") == []
        # Y si el modelo SI declaro un destino, manda el modelo: el cliente
        # puede estar cambiando el reparto justo en este turno.
        propios = _items_de_la_charla_del_12ago()
        propios[0].destino = "Rosario"
        assert H._items_con_destino_de_memoria(
            propios, _DESTINOS_12AGO, "verifika_prod") == []
    finally:
        set_current_estado(None)


def test_la_cuenta_deja_el_reparto_en_el_estado_para_persistir(firestore_doble):
    """El reparto que declara el MODELO item por item -el camino vivo desde el
    5-ago- no lo guardaba nadie: `grupos_envio` solo lo escribia el parser del
    mensaje. Por eso el turno siguiente arrancaba sin memoria del reparto."""
    from app.core import herramientas as H
    from app.core.estado_venta import set_current_estado, get_current_estado
    set_current_tienda("verifika_prod")
    set_current_estado({})
    try:
        items = [H.ItemPedido(product_id="AUR0020", cantidad=1,
                              destino="Córdoba Capital"),
                 H.ItemPedido(product_id="MOU0023", cantidad=1,
                              destino="Concordia")]
        r = H.armar_presupuesto(
            H.ArmarPresupuesto(items=items,
                               destinos=["Córdoba Capital", "Concordia"]),
            "verifika_prod")
        assert r["estado"] == "ok", r
        guardado = get_current_estado().get("grupos_envio")
        assert [g["destino"] for g in guardado] == ["Córdoba Capital",
                                                    "Concordia"]
    finally:
        set_current_estado(None)


# ── "AGREGA UN TECLADO A ESE PRESUPUESTO" (charla real del 12-ago, turno 8) ──
_MSG_AGREGAR = ("Sí agrega a ese presupuesto que detallaste al último con los "
                "seis artículos agrega un teclado con envío a Córdoba")

_CARRITO_12AGO = [
    {"id": "AUR0020", "nombre": "Auriculares Redragon Zeus X Blanco",
     "cantidad": 2},
    {"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro", "cantidad": 2},
    {"id": "RAM0001",
     "nombre": "Memoria ram Kingston Fury Beast DDR4 3200 8GB Negro",
     "cantidad": 2},
]


def test_agregar_un_producto_no_se_lleva_puesto_el_pedido_de_antes(
        firestore_doble):
    """LA FALLA, del casete `80_charla_real_12ago` turno 8. Sobre un
    presupuesto de seis articulos el cliente pide agregar un teclado; el modelo
    declara UN teclado -que es lo que se le pidio agregar- y la cuenta salia con
    un solo renglon de $12.000 y tres envios de $24.000 encima. Los seis
    articulos no los saco nadie: se cayeron solos, y el envio costaba el doble
    que la compra."""
    from app.core import herramientas as H
    from app.core.estado_venta import set_current_estado
    set_current_tienda("verifika_prod")
    set_current_estado({"carrito": _CARRITO_12AGO,
                        "mensaje_del_turno": _MSG_AGREGAR,
                        "grupos_envio": _MEMORIA_12AGO})
    # El turno busco teclados antes de cotizar, como en la charla real: sin eso
    # la regla cero rechaza el id y la cuenta no se arma, que es correcto.
    from app.core.estado_venta import certificar_ids_de_resultado
    certificar_ids_de_resultado({"productos": [{"id": "TEC0020"}]})
    try:
        r = H.armar_presupuesto(
            H.ArmarPresupuesto(
                items=[H.ItemPedido(product_id="TEC0020", cantidad=1,
                                    destino="Córdoba Capital")],
                destinos=_DESTINOS_12AGO),
            "verifika_prod")
        assert r["estado"] == "ok", r
        ids = {str(d.get("id")).upper() for d in r["detalle"]}
        assert {"AUR0020", "MOU0023", "RAM0001", "TEC0020"} <= ids, (
            f"la cuenta perdio el pedido de antes: {ids}")
        # Y la plata cierra: el subtotal es el de los siete articulos, no el
        # del teclado solo.
        assert r["total_ars"] and int(r["total_ars"]) > 200000, r["bloque"]
    finally:
        set_current_estado(None)


def test_si_el_modelo_ya_redeclaro_el_pedido_no_se_duplica_nada(firestore_doble):
    """El candado que evita cobrar dos veces: la mayoria de las veces el modelo
    RE-DECLARA el pedido entero. Ahi hay ids en comun con el carrito y no se
    suma nada, aunque el mensaje diga 'agrega'."""
    from app.core import herramientas as H
    from app.core.estado_venta import set_current_estado
    set_current_tienda("verifika_prod")
    set_current_estado({"carrito": _CARRITO_12AGO,
                        "mensaje_del_turno": _MSG_AGREGAR})
    try:
        items = [H.ItemPedido(product_id="AUR0020", cantidad=2),
                 H.ItemPedido(product_id="MOU0023", cantidad=2),
                 H.ItemPedido(product_id="RAM0001", cantidad=2),
                 H.ItemPedido(product_id="TEC0020", cantidad=1)]
        salida = H._con_el_carrito_que_ya_estaba(items, "verifika_prod")
        assert len(salida) == 4
        assert sum(i.cantidad for i in salida) == 7
    finally:
        set_current_estado(None)


def test_sacar_no_es_agregar_y_el_carrito_no_se_repone(firestore_doble):
    """El otro lado del candado. 'Sacá el teclado y dejame los dos mouse' es una
    correccion, no un agregado: ahi manda la declaracion completa del modelo y
    el carrito viejo NO se repone. Reponerlo le volveria a cobrar al cliente
    justo lo que acaba de sacar."""
    from app.core import herramientas as H
    from app.core.estado_venta import (set_current_estado,
                                       pide_agregar_al_pedido)
    set_current_tienda("verifika_prod")
    assert not pide_agregar_al_pedido("sacá el teclado y dejame los dos mouse")
    assert not pide_agregar_al_pedido("no agregues nada más")
    assert pide_agregar_al_pedido(_MSG_AGREGAR)
    set_current_estado({"carrito": _CARRITO_12AGO,
                        "mensaje_del_turno": "sacá los auriculares"})
    try:
        items = [H.ItemPedido(product_id="MOU0023", cantidad=2)]
        assert H._con_el_carrito_que_ya_estaba(
            items, "verifika_prod") == items
    finally:
        set_current_estado(None)


# ── EL DESTINO CON DOS LUGARES PEGADOS (charla real 12-ago 18:05) ───────────
def test_un_destino_con_dos_lugares_se_parte_en_dos(firestore_doble):
    """LA FALLA, y es plata: el modelo declaro los dos mouse en un renglon con
    el destino "Córdoba capital y Concordia". El codigo lo trato como UN
    destino —`geo_cp` lo resuelve a Cordoba porque encuentra 'cordoba' adentro—
    asi que ese envio se cobro como un CUARTO destino ademas de "Córdoba
    capital", que ya estaba. El cliente saco un producto y el envio le SUBIO de
    $24.000 a $31.500."""
    from app.core import herramientas as H
    set_current_tienda("verifika_prod")
    items = [H.ItemPedido(product_id="MOU0023", cantidad=2,
                          destino="Córdoba capital y Concordia")]
    salida = H._partir_destinos_compuestos(items)
    assert len(salida) == 2
    assert {i.destino for i in salida} == {"Córdoba capital", "Concordia"}
    assert all(i.cantidad == 1 for i in salida)
    # Y la lista suelta de destinos tampoco puede traer el compuesto: cobraria
    # dos veces el mismo lugar.
    assert H._sin_destinos_compuestos(
        ["Córdoba capital", "Córdoba capital y Concordia", "Posadas"]) == [
        "Córdoba capital", "Concordia", "Posadas"]


def test_si_la_cantidad_no_da_pareja_no_se_reparte(firestore_doble):
    """No se adivina. Tres mouse a dos lugares no se parten 2 y 1: elegir cual
    lugar recibe mas seria decidir por el cliente. Queda como esta y el reparto
    no cierra, que es lo honesto."""
    from app.core import herramientas as H
    set_current_tienda("verifika_prod")
    items = [H.ItemPedido(product_id="MOU0023", cantidad=3,
                          destino="Córdoba capital y Concordia")]
    assert len(H._partir_destinos_compuestos(items)) == 1
    # Un destino normal no se toca nunca.
    uno = [H.ItemPedido(product_id="MOU0023", cantidad=2, destino="Rosario")]
    assert H._partir_destinos_compuestos(uno) == uno


def test_la_cuenta_no_cobra_un_envio_al_lugar_inventado(firestore_doble):
    """De punta a punta: con el destino compuesto, la cuenta cobra DOS envios
    -Cordoba y Concordia- y no tres, y el reparto nombra lugares que existen."""
    from app.core import herramientas as H
    from app.core.estado_venta import set_current_estado
    set_current_tienda("verifika_prod")
    set_current_estado({})
    try:
        r = H.armar_presupuesto(
            H.ArmarPresupuesto(
                items=[H.ItemPedido(product_id="AUR0020", cantidad=1,
                                    destino="Córdoba capital"),
                       H.ItemPedido(product_id="MOU0023", cantidad=2,
                                    destino="Córdoba capital y Concordia")],
                destinos=["Córdoba capital", "Córdoba capital y Concordia"]),
            "verifika_prod")
        assert r["estado"] == "ok", r
        assert "y Concordia:" not in r["bloque"], (
            "escribio un destino que no existe:\n" + r["bloque"])
        assert "3 envios" not in r["bloque"], (
            "cobro un envio al lugar inventado:\n" + r["bloque"])
    finally:
        set_current_estado(None)


def test_el_reparto_junta_las_unidades_del_mismo_producto(firestore_doble):
    """"A Posadas: 1x memoria ram, 1x memoria ram" salio en la charla real del
    12-ago. El modelo declara una fila por unidad -es la forma natural de
    repartir "una a cada destino"- y el reparto las escribia una por una. Es la
    misma cuenta; lo que cambia es que se lee."""
    from app.core import herramientas as H
    from app.core.estado_venta import set_current_estado
    set_current_tienda("verifika_prod")
    set_current_estado({})
    try:
        r = H.armar_presupuesto(
            H.ArmarPresupuesto(
                items=[H.ItemPedido(product_id="AUR0020", cantidad=1,
                                    destino="Córdoba Capital"),
                       H.ItemPedido(product_id="RAM0001", cantidad=1,
                                    destino="Posadas"),
                       H.ItemPedido(product_id="RAM0001", cantidad=1,
                                    destino="Posadas")],
                destinos=["Córdoba Capital", "Posadas"]),
            "verifika_prod")
        assert r["estado"] == "ok", r
        assert "1x memoria ram, 1x memoria ram" not in r["bloque"], r["bloque"]
        assert "2x memoria ram" in r["bloque"], r["bloque"]
    finally:
        set_current_estado(None)
