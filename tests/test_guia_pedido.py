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
