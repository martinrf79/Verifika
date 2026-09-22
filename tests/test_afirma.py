"""
AREA: LO QUE EL CLIENTE DA POR SENTADO — una casilla para dos cosas que
parecian distintas.

LAS DOS, y lo unico que cambia es contra que se puede verificar:

  LA PREMISA FALSA   "el teclado K120 inalambrico ese". Hay ficha, asi que se
                     verifica. La FICHA 57 §5.1 la llama el unico vector que
                     hoy pasaria por todos los candados: la alucinacion no la
                     trae el modelo, la trae el CLIENTE, y aceptarla es mentir
                     con sus palabras.
  EL DATO DEL CLIENTE "mi notebook tiene 8 giga". No hay ficha contra que
                     cotejar, y eso NO es un error: es una fuente de verdad
                     que el cliente aporta y vale para el resto de la charla.

AL MODELO NO SE LE PIDE QUE ELIJA CUAL DE LAS DOS ES. Anota lo que el cliente
dijo y el CODIGO decide, que es la regla 10.0 aplicada a las afirmaciones.

EL CASO ESTA MEDIDO: los cuatro turnos del K120 en produccion —fbc6dcc5,
77973e25, b4ebea69, 753eba43— pasaron sin declarar la premisa, porque hasta hoy
no habia donde escribirla.

Y LOS DATOS DEL CATALOGO DEL REPO, que son los que hacen que esto se mida sin
credenciales: el K120 son DOS fichas —negra y blanca—, las dos con
`conexion: con cable USB`, y "inalambrico" es uno de los 17 valores que ese
mismo campo usa. O sea que la premisa del cliente se puede verificar.
"""
import pytest

from app.core import motor as MT

TIENDA = "verifika_prod"


@pytest.fixture(autouse=True)
def _doble(firestore_doble):
    from app.core.contexto_turno import set_current_tienda
    from app.core.filtros_catalogo import limpiar_cache
    set_current_tienda(TIENDA)
    limpiar_cache()
    return firestore_doble


def _todo() -> list:
    from app.storage.firestore_client import get_all_products
    return get_all_products(tienda_id=TIENDA) or []


def _uno(sobre, dice) -> dict:
    return MT._una_afirmacion({"sobre": sobre, "dice": dice}, _todo(), TIENDA)


# ── LA PREMISA FALSA ────────────────────────────────────────────────────────

def test_la_premisa_falsa_vuelve_con_el_dato_real():
    """El cliente afirma que el G203 es inalambrico y la ficha dice `conexion:
    con cable USB`. Eso es lo que hay que decirle, con esas palabras."""
    r = _uno("Mouse Logitech G203 Lightsync Negro", "inalambrico")
    assert r["veredicto"] == "contradice"
    assert "cable" in r["dato_real"].lower()
    assert "no le repitas la suya" in r["motivo"]


def test_el_k120_de_produccion_se_atrapa():
    """EL CASO MEDIDO, entero. Los cuatro turnos del 22-sep pasaron sin
    declarar la premisa porque no habia casilla, y el bot termino diciendo "no
    lo vendemos" sobre un teclado que SI vende. El K120 tiene
    `conexion: con cable USB`, asi que la afirmacion del cliente se contradice
    con el dato real al lado."""
    r = _uno("teclado K120", "inalambrico")
    assert r["veredicto"] == "contradice"
    assert "cable" in r["dato_real"].lower()
    assert "None" not in r["dato_real"], "el dato real salio vacio"


def test_lo_que_la_ficha_SI_dice_se_confirma():
    r = _uno("Teclado Logitech K120 Negro", "logitech")
    assert r["veredicto"] == "confirma"
    assert r["id"] == "TEC0029"


def test_por_ausencia_no_se_niega_nada():
    """Si NADIE en el catalogo usa esa palabra, no se puede confirmar ni negar.
    Confundir ausencia de evidencia con evidencia de ausencia es el mismo
    defecto que el campo muerto diciendo 'no lo vendemos'."""
    r = _uno("Teclado Logitech K120 Negro", "sumergible")
    assert r["veredicto"] == "no_consta"
    assert "NI negarlo" in r["motivo"]


# ── EL DATO QUE APORTA EL CLIENTE ───────────────────────────────────────────

def test_lo_del_cliente_no_es_un_error_es_una_fuente():
    r = _uno("mi notebook", "8 giga de ram")
    assert r["veredicto"] == "del_cliente"
    assert "tomalo como cierto" in r["motivo"]


def test_lo_del_cliente_vale_aunque_nombre_un_rubro_que_vendemos():
    """"Mi PS5" no es una ficha nuestra aunque vendamos consolas: lo que
    decide es si UNA ficha se llama todo eso, no si la palabra nos suena."""
    r = _uno("mi ps5", "esta en el living")
    assert r["veredicto"] == "del_cliente"


# ── LOS BORDES ──────────────────────────────────────────────────────────────

def test_una_afirmacion_vacia_no_inventa_un_veredicto():
    assert _uno("teclado K120", "")["veredicto"] == "no_consta"
    assert _uno("", "")["veredicto"] == "no_consta"


def test_sin_sobre_es_del_cliente_y_no_se_cae():
    assert _uno("", "tengo 8 giga")["veredicto"] == "del_cliente"


def test_la_ambiguedad_de_identidad_no_impide_verificar():
    """El K120 son DOS fichas y las dos dicen lo mismo sobre la conexion. Preguntar cual solo hace falta si difieren: exigir identidad
    unica para verificar seria dejar la premisa falsa pasar por un detalle que
    no cambia la respuesta."""
    r = _uno("teclado K120", "inalambrico")
    assert r["veredicto"] != "ambiguo"


def test_cuando_las_fichas_difieren_se_pregunta():
    """El K120 negro y el blanco difieren en el COLOR. Ahi el veredicto sobre
    'negro' no puede ser uno solo: es la regla 10.0, ante ambiguo se pregunta
    en vez de elegir."""
    r = _uno("teclado K120", "negro")
    assert r["veredicto"] == "ambiguo"
    assert "pregunta cual" in r["motivo"]
    assert "TEC0029" in r["motivo"] and "TEC0030" in r["motivo"]


# ── EL CABLE: LA BOCA ESTA ENCHUFADA A LA PUERTA ────────────────────────────

def test_la_boca_viaja_en_el_tablero_y_vuelve_en_el_retorno():
    esquema = MT.esquema(TIENDA)
    props = esquema["function"]["parameters"]["properties"]
    assert "afirma" in props, "el campo no esta en el tablero"
    r = MT.buscar([], TIENDA, afirma=[{"sobre": "teclado K120",
                                       "dice": "inalambrico"}])
    assert r.get("afirma"), "la caja no vuelve en el retorno"
    assert r["afirma"][0]["veredicto"] == "contradice"


def test_sin_afirmaciones_la_caja_no_viaja():
    """Una clave vacia en cada turno es ruido adentro de la caja donde todo lo
    demas es dato certificado."""
    assert "afirma" not in MT.buscar([], TIENDA)


def test_una_afirmacion_rota_no_tumba_la_busqueda():
    r = MT.buscar([{"categoria": "teclado"}], TIENDA,
                  afirma=[{"sobre": None, "dice": None}])
    assert r["resultados"], "se llevo puesta la busqueda"
    assert r["afirma"][0]["veredicto"] == "no_consta"


def test_el_tope_corta_en_cuatro():
    pedidos = [{"sobre": f"cosa {i}", "dice": "algo"} for i in range(9)]
    r = MT.buscar([], TIENDA, afirma=pedidos)
    assert len(r["afirma"]) == MT.TOPE_AFIRMA == 4
