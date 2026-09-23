"""PASO 7 — EL LEAD, EL COBRO O LA RESERVA NUNCA SALEN DE LA FICHA SOLA.

`banco_pruebas/memoria.py:compuerta`. Comprar se hace en dos turnos: el codigo
propone un pedido certificado, y solo el turno siguiente, con un si y sin
cambios, lo confirma. Estos tests no llaman a ningun modelo: las fichas estan
escritas a mano, y varias mienten a proposito diciendo `comprar`.
"""
import pytest

from banco_pruebas import memoria as M
from banco_pruebas import traductor as T


@pytest.fixture
def tab(firestore_doble):
    return T.tablero()


def _parte(dice, **k):
    p = {"dice": dice, "quiere": "precio", "origen": "tienda",
         "rubro": "ninguno", "producto": "", "criterios": [], "cantidad": 0,
         "destino": "", "refiere": "no", "posiciones": [], "para": ""}
    p.update(k)
    return p


def _charla(tab, turnos):
    estado, fuera = M.estado_nuevo(), []
    for texto, partes in turnos:
        ficha = {"partes": partes, "afirma": [], "reescrita": texto,
                 "criterios_generales": [], "reparto": []}
        r, estado = M.turno(texto, estado, tab, lambda _t, _f=ficha: _f)
        fuera.append(r["pedido"]["comercial"])
    return fuera


_K120 = ("cuanto sale el teclado K120 negro?",
         [_parte("cuanto sale el teclado K120 negro?", rubro="teclado",
                 producto="K120 negro")])
_LO_QUIERO = ("dale, lo quiero",
              [_parte("dale, lo quiero", quiere="comprar", refiere="ese",
                      cantidad=1)])
_SI = ("si", [_parte("si", quiere="charla")])


def test_lo_quiero_propone_y_no_cierra(tab):
    c = _charla(tab, [_K120, _LO_QUIERO])
    assert c[1]["accion"] == "proponer"
    assert c[1]["items"] and all(ids for ids, _n in c[1]["items"])


def test_el_si_del_turno_siguiente_confirma_lo_propuesto(tab):
    c = _charla(tab, [_K120, _LO_QUIERO, _SI])
    assert c[2]["accion"] == "confirmado"
    assert c[2]["items"] == c[1]["items"]


def test_un_si_sin_propuesta_no_confirma_nada(tab):
    c = _charla(tab, [_K120, _SI])
    assert c[1]["accion"] is None


def test_la_propuesta_se_vence_si_habla_de_otra_cosa(tab):
    c = _charla(tab, [_K120, _LO_QUIERO,
                      ("aceptan mercado pago?",
                       [_parte("aceptan mercado pago?", quiere="pago")]),
                      _SI])
    assert c[3]["accion"] != "confirmado"


def test_otra_cantidad_es_otra_propuesta(tab):
    c = _charla(tab, [_K120, _LO_QUIERO,
                      ("mejor que sean 3",
                       [_parte("mejor que sean 3", quiere="comprar",
                               refiere="ese", cantidad=3)])])
    assert c[2]["accion"] == "proponer"
    assert [n for _ids, n in c[2]["items"]] == [3]


def test_lo_quiero_despues_de_una_lista_falta_saber_cual(tab):
    c = _charla(tab, [
        ("mostrame 3 mouse logitech",
         [_parte("mostrame 3 mouse logitech", quiere="buscar", rubro="mouse",
                 criterios=[{"concepto": "marca", "valor": "logitech",
                             "fuerza": "debe"}], cantidad=3)]),
        _LO_QUIERO])
    assert c[1]["accion"] == "falta"
    assert not c[1]["items"]


def test_comprar_un_producto_que_no_existe_no_propone(tab):
    c = _charla(tab, [("quiero comprar el iphone 15",
                       [_parte("quiero comprar el iphone 15",
                               quiere="comprar", producto="iphone 15")])])
    assert c[0]["accion"] == "falta"


def test_la_ficha_mentirosa_nunca_cierra_en_un_turno(tab):
    """Veinte fichas que dicen `comprar` sobre un producto real, cada una en
    una charla nueva: ninguna sale confirmada, todas proponen."""
    import csv
    with open(M.CATALOGO, encoding="utf-8") as f:
        prods = [p for p in csv.DictReader(f)][::44][:20]
    acciones = []
    for p in prods:
        texto = f"quiero comprar el {p['marca']} {p['modelo']} {p['color']}"
        c = _charla(tab, [(texto, [_parte(texto, quiere="comprar",
                                          rubro=p["categoria"],
                                          producto=f"{p['modelo']} {p['color']}",
                                          cantidad=1)])])
        acciones.append(c[0]["accion"])
    assert len(acciones) == 20
    assert "confirmado" not in acciones
    assert acciones.count("proponer") >= 15, acciones
