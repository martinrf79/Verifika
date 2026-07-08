"""
AREA: Guia determinista de pedido — el interprete extrae el pedido (atado por
enum a lo mostrado) y el CODIGO llama la calculadora y sella el presupuesto.

Cubre app/core/guia_pedido.py. Cierra el caso real de multi-envio (8-jul): el
solver llamaba calculate_total con ids equivocados y tipeaba la cuenta a mano.
"""
from app.core.guia_pedido import items_de_pedido, calcular_pedido


_VISTOS = [
    {"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro", "precio": 8500},
    {"id": "TEC0030", "nombre": "Teclado Logitech K120 Blanco", "precio": 14500},
]


def _interp(**kw):
    base = {"intencion": "decision_compra", "confianza": 0.9, "pedido": []}
    base.update(kw)
    return base


# ── items_de_pedido: reconciliacion todo-o-nada ──────────────────────────────
def test_pedido_completo_reconcilia_ids():
    interp = _interp(pedido=[
        {"producto": "Mouse Genius DX-110 Negro", "cantidad": 3},
        {"producto": "Teclado Logitech K120 Blanco", "cantidad": 2},
    ])
    items = items_de_pedido(interp, _VISTOS)
    assert items == [{"product_id": "MOU0023", "cantidad": 3},
                     {"product_id": "TEC0030", "cantidad": 2}]


def test_un_nombre_que_no_reconcilia_invalida_todo():
    interp = _interp(pedido=[
        {"producto": "Mouse Genius DX-110 Negro", "cantidad": 3},
        {"producto": "Notebook Fantasma X", "cantidad": 1},
    ])
    assert items_de_pedido(interp, _VISTOS) is None


def test_confianza_baja_no_arma_pedido():
    interp = _interp(confianza=0.4, pedido=[
        {"producto": "Mouse Genius DX-110 Negro", "cantidad": 3}])
    assert items_de_pedido(interp, _VISTOS) is None


def test_cantidad_invalida_no_arma_pedido():
    for cant in (0, -1, 500, "muchas", None):
        interp = _interp(pedido=[
            {"producto": "Mouse Genius DX-110 Negro", "cantidad": cant}])
        assert items_de_pedido(interp, _VISTOS) is None, cant


def test_sin_pedido_o_sin_vistos_devuelve_none():
    assert items_de_pedido(_interp(pedido=[]), _VISTOS) is None
    assert items_de_pedido(_interp(pedido=[
        {"producto": "Mouse Genius DX-110 Negro", "cantidad": 1}]), []) is None
    assert items_de_pedido(None, _VISTOS) is None


def test_match_tolera_mayusculas_y_acentos():
    interp = _interp(pedido=[
        {"producto": "mouse genius dx-110 negro", "cantidad": 1}])
    items = items_de_pedido(interp, _VISTOS)
    assert items and items[0]["product_id"] == "MOU0023"


# ── calcular_pedido: el codigo llama la calculadora y devuelve la entrada ───
def test_calcula_presupuesto_sellado(firestore_doble):
    from app.core.estado_venta import set_current_estado
    estado = {"productos_vistos": _VISTOS, "localidades_envio": [], "carrito": []}
    set_current_estado(estado)
    try:
        interp = _interp(pedido=[
            {"producto": "Mouse Genius DX-110 Negro", "cantidad": 2}])
        entradas = calcular_pedido(interp, estado, "verifika_prod")
        assert entradas and entradas[0]["name"] == "calculate_total"
        res = entradas[0]["result"]
        assert res["ok"] is True
        assert res["total_ars"] == 17000  # 2 x 8500, dato real del catalogo
        assert "presentacion" in res
    finally:
        set_current_estado({})


def test_calcula_con_envio_multidestino(firestore_doble):
    from app.core.estado_venta import set_current_estado
    estado = {"productos_vistos": _VISTOS, "carrito": [],
              "localidades_envio": ["Tancacha, cordoba", "Rio Tercero, cordoba"]}
    set_current_estado(estado)
    try:
        interp = _interp(pedido=[
            {"producto": "Mouse Genius DX-110 Negro", "cantidad": 2},
            {"producto": "Teclado Logitech K120 Blanco", "cantidad": 1}])
        entradas = calcular_pedido(interp, estado, "verifika_prod")
        assert entradas and entradas[0]["result"]["ok"] is True
        # dos destinos: el envio se cobra por destino (la calculadora manda)
        assert entradas[0]["args"]["destinos"] == 2
    finally:
        set_current_estado({})


def test_stock_insuficiente_cae_al_camino_normal(firestore_doble):
    from app.core.estado_venta import set_current_estado
    estado = {"productos_vistos": _VISTOS, "localidades_envio": [], "carrito": []}
    set_current_estado(estado)
    try:
        interp = _interp(pedido=[
            {"producto": "Mouse Genius DX-110 Negro", "cantidad": 99}])
        assert calcular_pedido(interp, estado, "verifika_prod") is None
    finally:
        set_current_estado({})


def test_producto_duplicado_en_pedido_invalida_todo():
    interp = _interp(pedido=[
        {"producto": "Mouse Genius DX-110 Negro", "cantidad": 3},
        {"producto": "mouse genius dx-110 negro", "cantidad": 3},
    ])
    assert items_de_pedido(interp, _VISTOS) is None


def test_pedido_sellado_rechaza_items_agregados(firestore_doble):
    # Con el pedido del turno sellado por la guia, un calculate_total del solver
    # que AGREGA un producto no pedido (el microfono fantasma del banco) se
    # rechaza; el mismo pedido o un subconjunto pasa.
    from app.core.estado_venta import set_current_estado
    from app.core.tools import calculate_total
    from app.core.tools_context import set_current_tienda
    set_current_tienda("verifika_prod")
    set_current_estado({"carrito": [], "productos_vistos": _VISTOS,
                        "pedido_sellado_turno": ["MOU0023"]})
    try:
        con_extra = calculate_total(items=[
            {"product_id": "MOU0023", "cantidad": 1},
            {"product_id": "MIC0019", "cantidad": 1}])
        assert con_extra["ok"] is False
        assert "MIC0019" in con_extra["mensaje_para_llm"]
        mismo = calculate_total(items=[{"product_id": "MOU0023", "cantidad": 1}])
        assert mismo["ok"] is True
    finally:
        set_current_estado({})


# ── Pedido por CATEGORIAS sin modelos (prioridad 1, caso real 8-jul) ────────
def test_cantidades_por_categoria_extrae_el_pedido(firestore_doble):
    from app.core.guia_pedido import cantidades_por_categoria
    msg = ("Hola necesito precio de 4 notebooks tres teclados y 5 Mouse de los "
           "cuales una Notebook y un teclado va a tancacha una Notebook y un "
           "mouse va a Rio tercero lo demas va con envio a los condores")
    cats = cantidades_por_categoria(msg, "verifika_prod")
    # La PRIMERA mencion de cada categoria manda (los totales van primero).
    assert (4, "notebook") in cats and (3, "teclado") in cats and (5, "mouse") in cats
    assert len(cats) == 3


def test_cantidades_sin_categoria_no_extrae(firestore_doble):
    from app.core.guia_pedido import cantidades_por_categoria
    assert cantidades_por_categoria("cuanto sale el mouse?", "verifika_prod") == []
    assert cantidades_por_categoria("tengo 3 hijos", "verifika_prod") == []


def test_opciones_por_categoria_son_reales_y_con_stock(firestore_doble):
    from app.core.guia_pedido import opciones_por_categoria
    ops = opciones_por_categoria("mouse", "verifika_prod")
    assert 1 <= len(ops) <= 3
    assert all(p["stock"] > 0 for p in ops)
    # ordenadas por precio: la primera es la mas barata
    assert ops[0]["precio_ars"] <= ops[-1]["precio_ars"]


def test_guarda_reemplaza_presupuesto_inventado(firestore_doble):
    from app.core.interprete_libre import _forzar_opciones_si_presupuesto
    r = ("Aqui tienes el presupuesto detallado:\n"
         "- 1x Notebook HP: $693.000\nTotal: $2.179.500")
    out = _forzar_opciones_si_presupuesto(
        r, [(4, "notebook"), (3, "teclado"), (5, "mouse")], "verifika_prod")
    assert out is not None
    assert "modelos" in out.lower() or "modelo" in out.lower()
    assert "opciones con stock" in out
    assert "$2.179.500" not in out


def test_guarda_no_toca_respuesta_sin_presupuesto(firestore_doble):
    from app.core.interprete_libre import _forzar_opciones_si_presupuesto
    r = "Te muestro opciones de notebooks para que elijas modelos."
    assert _forzar_opciones_si_presupuesto(
        r, [(4, "notebook")], "verifika_prod") is None


def test_sello_con_envio_y_transferencia_del_mensaje(firestore_doble):
    # "total con envio a Rosario por transferencia": el sello ya trae flete y
    # descuento (antes salia el total pelado aunque el cliente pidio ambos).
    from app.core.estado_venta import set_current_estado
    from app.core import estado_venta
    estado = {"productos_vistos": _VISTOS, "localidades_envio": [], "carrito": []}
    estado_venta._envio_localidades.set([])
    set_current_estado(estado)
    try:
        interp = _interp(pedido=[
            {"producto": "Mouse Genius DX-110 Negro", "cantidad": 2}])
        entradas = calcular_pedido(
            interp, estado, "verifika_prod",
            mensaje="dale, pasame el total con envio a Rosario pagando por transferencia")
        assert entradas and entradas[0]["result"]["ok"] is True
        args = entradas[0]["args"]
        assert args.get("pago") == [{"medio": "transferencia", "porcentaje": 100}]
        assert args.get("items_extra")  # el envio entro al sello
    finally:
        estado_venta._envio_localidades.set([])
        set_current_estado({})
