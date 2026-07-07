"""
AREA: Ruteo de venta — la columna vertebral que elige la MOVIDA de una pregunta
compleja o manda PREGUNTAR (escape).

Cubre app/core/ruteo_venta.py. Es logica pura, sin LLM ni Firestore: recibe la
lectura del interprete (interp) y el estado, y devuelve una decision
determinista. Conservador como el resto: ante duda, accion 'normal'.
"""
from app.core.ruteo_venta import rutear_venta, CATEGORIAS, _UMBRAL_CONF


def _interp(**kw):
    base = {"intencion": "pregunta_especifica", "confianza": 0.9,
            "producto_resuelto": None, "candidatos": [], "ofrecer_opciones": []}
    base.update(kw)
    return base


# ── B7 ambiguedad: senal estructurada del interprete ────────────────────────
def test_candidatos_multiples_manda_preguntar():
    d = rutear_venta("quiero el DX-110", _interp(candidatos=["DX-110 Negro", "DX-110 Blanco"]), {})
    assert d["categoria"] == "B7" and d["accion"] == "preguntar"


def test_ofrecer_opciones_manda_preguntar():
    d = rutear_venta("cual me conviene", _interp(ofrecer_opciones=["A", "B"]), {})
    assert d["categoria"] == "B7" and d["accion"] == "preguntar"


# ── Deteccion por frase de cada categoria compleja ──────────────────────────
def test_presion_descuento():
    for msg in ["me haces un precio?", "hay descuento si llevo dos?", "un descuentito?"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B4", msg
        assert d["accion"] == "movida"


def test_objecion_precio():
    for msg in ["esta muy caro", "en otro lado sale mas barato"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B5", msg


def test_desconfianza():
    for msg in ["es seguro comprar por aca?", "son originales o truchos?"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B6", msg


def test_postergacion():
    for msg in ["lo pienso y despues vuelvo", "tengo que consultarlo"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B11", msg


def test_cambio_producto():
    for msg in ["no, ese no, mejor el otro", "en vez del negro dame el blanco"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B2", msg


def test_indecision():
    for msg in ["no se cual llevar", "vos que me recomendas?", "confio en tu eleccion"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B1", msg


# ── Escape por confianza baja: una movida floja se degrada a preguntar ───────
def test_confianza_baja_degrada_movida_a_preguntar():
    # B4 (presion_descuento) tiene escape_default 'movida'; con confianza baja
    # NO afirma, pregunta.
    d = rutear_venta("me haces un precio?", _interp(confianza=0.4), {})
    assert d["categoria"] == "B4" and d["accion"] == "preguntar" and d["movida"] is None


def test_confianza_alta_si_afirma_movida():
    d = rutear_venta("me haces un precio?", _interp(confianza=0.9), {})
    assert d["accion"] == "movida" and d["movida"] == "B4"


# ── Conservador: ante duda, camino normal ───────────────────────────────────
def test_mensaje_comun_no_rutea():
    d = rutear_venta("hola, tenes mouse?", _interp(), {})
    assert d["accion"] == "normal" and d["categoria"] is None


def test_interp_vacio_no_rompe():
    assert rutear_venta("cualquier cosa", None, None)["accion"] == "normal"
    assert rutear_venta("", {}, {})["accion"] == "normal"


# ── Registro de categorias: memoria listada pero no ruteada ─────────────────
def test_categorias_memoria_no_se_rutean_por_frase():
    # "el que te dije" es referencia borrosa (C1): el router NO la agarra como
    # movida de venta; la maneja memoria_ref. Debe caer en normal.
    d = rutear_venta("dame el que te dije antes", _interp(), {})
    assert d["accion"] == "normal"


def test_registro_tiene_las_12_complejas_y_las_4_de_memoria():
    complejas = [k for k, v in CATEGORIAS.items() if v["familia"] == "compleja"]
    memoria = [k for k, v in CATEGORIAS.items() if v["familia"] == "memoria"]
    assert len(complejas) == 12
    assert len(memoria) == 4
    assert 0 < _UMBRAL_CONF < 1
