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


# ── Categorias nuevas B13-B23 (7-jul) ────────────────────────────────────────
def test_negacion_intraturno():
    for msg in ["quiero el DX-110 pero no el negro",
                "me gusta el Zeus pero sin el cable rojo"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B3", msg
        assert d["accion"] == "movida"


def test_urgencia():
    for msg in ["lo necesito para el viernes", "es urgente, llega manana?",
                "tienen envio express?"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B13", msg


def test_urgencia_no_confunde_postergacion():
    # "lo dejamos para manana" NO es urgencia ni debe rutear como tal.
    d = rutear_venta("lo dejamos para manana", _interp(), {})
    assert d["categoria"] != "B13"


def test_mayorista():
    for msg in ["tienen precio por mayor?", "necesito 50 unidades",
                "venta mayorista hacen?"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B14", msg


def test_mayorista_gana_a_descuento():
    # "me haces precio por mayor" es mayorista (B14), no regateo (B4).
    d = rutear_venta("me haces precio al por mayor?", _interp(), {})
    assert d["categoria"] == "B14"


def test_presupuesto_acotado():
    for msg in ["tengo $50.000, que me alcanza?", "tengo hasta 80 lucas",
                "no quiero gastar mas de 100000"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B15", msg


def test_regalo():
    for msg in ["es para regalar", "es un regalo para mi novia",
                "busco algo para mi hijo de 10"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B16", msg


def test_queja():
    for msg in ["es una verguenza la demora", "pesimo servicio",
                "nadie me responde hace dos dias", "quiero hacer un reclamo"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B17", msg


def test_pedir_humano():
    for msg in ["pasame con una persona", "sos un bot?",
                "quiero hablar con alguien", "con quien estoy hablando?"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B18", msg


def test_cancelacion():
    for msg in ["cancelalo por favor", "quiero cancelar el pedido",
                "no lo quiero mas, olvidalo"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B19", msg


def test_pago_no_ofrecido():
    for msg in ["aceptan cripto?", "puedo pagar en dolares?",
                "hacen contra entrega?"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B20", msg


def test_envio_exterior():
    for msg in ["hacen envios a uruguay?", "mandan al exterior?",
                "llegan a chile?"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B21", msg


def test_pedido_foto():
    for msg in ["mandame fotos reales", "tenes fotos del teclado?",
                "pasame un video"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B22", msg


def test_reclamo_posventa():
    for msg in ["se me rompio el mouse", "vino fallado el teclado",
                "quiero devolverlo, llego roto", "quiero hacer valer la garantia"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B23", msg


def test_queja_gana_a_precio():
    # Una queja con plata adentro sigue siendo queja: primero se atiende el enojo.
    d = rutear_venta("es una verguenza, esta carisimo y nadie responde", _interp(), {})
    assert d["categoria"] == "B17"


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


def test_registro_tiene_las_24_complejas_y_las_4_de_memoria():
    complejas = [k for k, v in CATEGORIAS.items() if v["familia"] == "compleja"]
    memoria = [k for k, v in CATEGORIAS.items() if v["familia"] == "memoria"]
    assert len(complejas) == 24
    assert len(memoria) == 4
    assert 0 < _UMBRAL_CONF < 1


def test_movidas_emocionales_tienen_texto_en_compositor():
    # Coherencia registro <-> compositor (la guia_venta del solver se retiro en
    # la limpieza del 10-jul): las movidas que cortan el turno (queja, humano,
    # cancelacion, indecision) y las de objecion tienen que tener su texto fijo
    # en el compositor; las de politica salen de la FAQ curada del tema.
    from app.core.compositor import _MOVIDAS_FIJAS, _MOVIDAS_FAQ
    for cat in ("B4", "B5", "B11", "B17", "B18", "B19", "B22"):
        assert cat in _MOVIDAS_FIJAS, f"{cat} sin texto fijo en compositor"
    for cat in _MOVIDAS_FAQ:
        assert cat in CATEGORIAS, f"{cat} de FAQ no existe en el registro"


def test_envio_exterior_por_ciudad():
    for msg in ["mandan a montevideo?", "llegan a santiago de chile?"]:
        d = rutear_venta(msg, _interp(), {})
        assert d["categoria"] == "B21", msg
