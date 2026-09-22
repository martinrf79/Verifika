"""EL COTEJO QUE MIDIO LA TANDA DE CHARLAS (22-sep-2026) — secciones 6 y 7
de `app/core/cotejo.py`."""
from app.core import cotejo as CO


def _afirma(dice, sobre="TEC0029"):
    return [{"sobre": sobre, "dice": dice}]


# ── 6 · la pregunta no es una afirmacion ───────────────────────────────────

def test_es_inalambrico_con_signo_es_PREGUNTA():
    """CH14: la boca lo contesto como premisa y el cliente leyo 'lo tomamos
    como una caracteristica del uso que le das'."""
    a = _afirma("inalambrico")
    assert CO.afirmas_que_preguntan(a, "el teclado es inalambrico?")
    assert a == []


def test_la_premisa_de_M13_se_QUEDA():
    """'el K120 inalambrico ese cuanto sale?' da el dato por sentado: el
    adjetivo va pegado al nombre, no despues de un verbo que pregunta."""
    a = _afirma("inalambrico")
    assert not CO.afirmas_que_preguntan(
        a, "hola el teclado K120 inalambrico ese cuanto sale? creo que se "
           "llama asi")
    assert len(a) == 1


def test_una_afirmacion_sin_signo_se_queda():
    a = _afirma("inalambrico")
    CO.afirmas_que_preguntan(a, "como el teclado es inalambrico lo quiero")
    assert len(a) == 1


def test_tiene_bluetooth_y_viene_en_blanco_son_preguntas():
    for msj, dice in (("el G203 tiene bluetooth?", "bluetooth"),
                      ("y viene en blanco?", "blanco")):
        a = _afirma(dice)
        CO.afirmas_que_preguntan(a, msj)
        assert a == [], msj


# ── 7 · el producto que el renglon nombra se busca ─────────────────────────

VISTOS = [{"id": "TEC0029", "nombre": "Teclado Logitech K120 Negro",
           "modelo": "K120"},
          {"id": "MOU0001", "nombre": "Mouse Logitech G203 Lightsync Negro",
           "modelo": "G203 Lightsync"}]


def test_el_renglon_que_nombra_un_visto_trae_su_consulta():
    """CH22: 'cuanta garantia tiene el teclado K120 negro' con solo el tema
    `garantia` en el pedido: sin la ficha no hay garantia_meses."""
    pedido = {"temas": ["garantia"], "consultas": []}
    ids = CO.rescatar_nombrados(
        ["cuanta garantia tiene el teclado K120 negro"], pedido, VISTOS)
    assert ids == ["TEC0029"]
    assert pedido["consultas"] == [{"ids": ["TEC0029"], "busco": "uno"}]


def test_si_ya_lo_pide_no_se_duplica():
    pedido = {"consultas": [{"ids": ["TEC0029"]}]}
    assert CO.rescatar_nombrados(["el K120"], pedido, VISTOS) == []


def test_un_modelo_que_no_se_vio_no_se_rescata():
    """No puede traer algo que el cliente no conoce: solo lo ya mostrado."""
    pedido = {"consultas": []}
    assert CO.rescatar_nombrados(["y el G502?"], pedido, VISTOS) == []


def test_la_clave_no_aparea_adentro_de_otra_palabra():
    pedido = {"consultas": []}
    assert CO.rescatar_nombrados(["el k1200 pro"], pedido, VISTOS) == []
