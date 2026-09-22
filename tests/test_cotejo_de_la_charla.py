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


# ── 8 · "de esos" es entre los que el cliente leyo ─────────────────────────

RECIEN = [("TEC0001", "teclado"), ("TEC0005", "teclado"),
          ("TEC0007", "teclado")]


def test_de_esos_restringe_a_lo_ultimo_nombrado():
    """CH10: 'de esos cual es el mas barato?' busco en el catalogo entero y
    presento como 'de los que te mencione' uno que nunca menciono."""
    consultas = [{"categoria": "teclado",
                  "ordenar_por": {"campo": "precio_ars", "direccion": "min"}}]
    CO.restringir_a_esos("de esos cual es el mas barato?", consultas, RECIEN)
    assert consultas[0]["ids"] == ["TEC0001", "TEC0005", "TEC0007"]
    assert consultas[0]["ordenar_por"]["campo"] == "precio_ars"


def test_sin_la_marca_no_se_restringe():
    consultas = [{"categoria": "teclado"}]
    CO.restringir_a_esos("cual es el teclado mas barato?", consultas, RECIEN)
    assert "ids" not in consultas[0]


def test_otro_rubro_no_se_toca():
    consultas = [{"categoria": "mouse"}]
    CO.restringir_a_esos("de esos, cual va con un mouse?", consultas, RECIEN)
    assert "ids" not in consultas[0]


def test_el_motor_ordena_ADENTRO_de_los_ids(firestore_doble):
    """Con ids el orden se ignoraba, asi que 'el mas barato de esos' no se
    podia pedir sin salir al catalogo."""
    from app.core import motor as MT
    ids = ["TEC0011", "TEC0029", "TEC0001"]
    r = MT.buscar([{"ids": ids, "ordenar_por": {"campo": "precio_ars",
                                                 "direccion": "min"}}],
                  "verifika_prod")
    precios = [f["precio_ars"] for f in MT.fichas_de(r)]
    assert precios == sorted(precios), precios
    assert {f["id"] for f in MT.fichas_de(r)} == set(ids)


# ── el orden plano ─────────────────────────────────────────────────────────

def test_el_orden_plano_se_traduce_para_el_motor():
    from app.core import motor as MT
    c = MT.orden_plano({"categoria": "mouse", "orden": "precio_ars_min"})
    assert c["ordenar_por"] == {"campo": "precio_ars", "direccion": "min"}


def test_ninguno_no_ordena():
    from app.core import motor as MT
    assert "ordenar_por" not in MT.orden_plano({"orden": MT.SIN_ORDEN})


def test_el_lector_de_la_vara_lee_las_dos_formas():
    from banco_pruebas.leer_interpretacion import _c_barato
    assert _c_barato({}, {"consultas": [{"orden": "precio_ars_min"}]})
    assert _c_barato({}, {"consultas": [{"ordenar_por": {
        "campo": "precio_ars", "direccion": "min"}}]})
    assert not _c_barato({}, {"consultas": [{"orden": "ninguno"}]})


# ── 9 · "lo tenes en rosa?" con un solo modelo delante ─────────────────────

G203S = [{"id": "MOU0001", "modelo": "G203 Lightsync", "turno": 1},
         {"id": "MOU0002", "modelo": "G203 Lightsync", "turno": 1}]


def test_el_pronombre_con_un_solo_modelo_trae_ese_modelo():
    """CH15: contesto con los colores de TODOS los mouses."""
    pedido = {"consultas": [{"categoria": "mouse", "condiciones": [
        {"campo": "color", "operador": "igual", "valor": "rosa"}]}]}
    ids = CO.rescatar_anafora("lo tenes en rosa?", pedido, G203S)
    assert ids == ["MOU0001", "MOU0002"]
    assert pedido["consultas"][-1] == {"ids": ids, "busco": "uno"}


def test_con_dos_modelos_delante_no_se_elige():
    """Ahi la ambiguedad es real: la regla 10.0 manda preguntar."""
    dos = G203S + [{"id": "MOU0003", "modelo": "G502 Hero", "turno": 1}]
    assert CO.rescatar_anafora("lo tenes en rosa?", {"consultas": []},
                               dos) == []


def test_sin_pronombre_no_se_toca():
    assert CO.rescatar_anafora("tenes mouses rosa?", {"consultas": []},
                               G203S) == []


def test_el_mismo_pero_en_blanco_tambien():
    assert CO.rescatar_anafora("tenes el mismo pero en blanco?",
                               {"consultas": []}, G203S)


# ── "igual G203" contra "G203 Lightsync" ───────────────────────────────────

def test_igual_a_medias_aterriza_y_no_niega_el_producto(firestore_doble):
    """CH5: 'modelo igual G203' no pegaba con 'G203 Lightsync' y el cliente
    leyo 'el G203 no lo tenemos'."""
    from app.core import motor as MT
    r = MT.buscar([{"categoria": "mouse", "busco": "uno", "condiciones": [
        {"campo": "modelo", "operador": "igual", "valor": "G203"},
        {"campo": "color", "operador": "igual", "valor": "negro"}]}],
        "verifika_prod")
    ids = [f["id"] for f in MT.fichas_de(r)]
    assert ids and ids[0] == "MOU0001", ids


def test_igual_exacto_sigue_siendo_exacto(firestore_doble):
    from app.core.filtros_catalogo import aplicar
    from app.core.motor import _Cond
    from app.storage.firestore_client import get_all_products
    prods = [p for p in get_all_products(tienda_id="verifika_prod")
             if p.get("categoria") == "mouse"]
    r = aplicar(prods, [_Cond({"campo": "color", "operador": "igual",
                               "valor": "negro"})], "verifika_prod")
    assert r["aplicados"][0]["operador"] == "igual"
    assert "nota" not in r["aplicados"][0]
