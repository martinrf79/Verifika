"""LA MEMORIA DEL CAMINO NUEVO — `banco_pruebas/memoria.py`, paso 6 del plan
del 23-sep.

El traductor marca COMO apunta el cliente a algo de antes; el codigo decide A
QUE, contra lo que se mostro. Estos tests no llaman a ningun modelo: las fichas
son las grabadas de diez corridas reales, o escritas a mano para una regla.
"""
import json

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
    """[(texto, partes)] por el camino nuevo; devuelve los pedidos."""
    estado, pedidos = M.estado_nuevo(), []
    for texto, partes in turnos:
        ficha = {"partes": partes, "afirma": [], "reescrita": texto,
                 "criterios_generales": [], "reparto": []}
        r, estado = M.turno(texto, estado, tab, lambda _t, _f=ficha: _f)
        pedidos.append(r["pedido"])
    return pedidos


def _ids(pedido):
    return [c.get("ids") for c in pedido["consultas"]]


def test_las_diez_corridas_grabadas_pasan_enteras(tab):
    """Seis de DeepSeek y cuatro de Gemini, 53 casillas cada una. El numero
    se dice: diez corridas, 530 casillas."""
    with open(M.GRABADAS, encoding="utf-8") as f:
        corridas = json.load(f)["corridas"]
    assert len(corridas) == 10
    charlas = M.charlas_de_la_vara()
    fallas, total = [], 0
    for k, cor in enumerate(corridas, 1):
        ok, de, _na, _ = M.correr(
            charlas, tab, lambda t, c, n, _f=cor["fichas"]: _f[c][n - 1],
            ver=lambda *_a: None)
        total += de
        if ok != de:
            fallas.append(f"corrida {k} {cor['modelo']}: {ok} de {de}")
    assert total == 530
    assert not fallas, fallas


def test_el_segundo_es_el_segundo_de_lo_que_se_mostro(tab):
    p = _charla(tab, [
        ("precio del teclado K120 negro y del mouse G203 negro",
         [_parte("teclado K120 negro", rubro="teclado", producto="K120 negro"),
          _parte("mouse G203 negro", rubro="mouse", producto="G203 negro")]),
        ("el segundo", [_parte("el segundo", refiere="posicion",
                               posiciones=[2])])])
    assert _ids(p[1]) == [["MOU0001"]]


def test_el_otro_es_el_que_acompanaba_al_foco(tab):
    p = _charla(tab, [
        ("precio del teclado K120 negro y del mouse G203 negro",
         [_parte("teclado K120 negro", rubro="teclado", producto="K120 negro"),
          _parte("mouse G203 negro", rubro="mouse", producto="G203 negro")]),
        ("el teclado es inalambrico?",
         [_parte("el teclado es inalambrico?", quiere="caracteristica",
                 rubro="teclado")]),
        ("y el otro?", [_parte("y el otro?", refiere="el_otro")])])
    assert _ids(p[1]) == [["TEC0029"]], "'el teclado' es el K120 de antes"
    assert _ids(p[2]) == [["MOU0001"]]


def test_ese_despues_de_una_lista_repregunta_con_la_lista(tab):
    """Despues de mostrar varios, "ese" no tiene a quien apuntar: se pregunta
    cual, y las opciones son las que se mostraron."""
    p = _charla(tab, [
        ("mostrame auriculares", [_parte("mostrame auriculares",
                                         quiere="buscar",
                                         rubro="auriculares")]),
        ("cuanto sale ese?", [_parte("cuanto sale ese?", refiere="ese")])])
    assert p[1]["consultas"] == []
    (rep,) = p[1]["repreguntar"]
    assert len(rep["opciones"]) >= 2


def test_el_rubro_nombrado_manda_sobre_la_busqueda_de_antes(tab):
    p = _charla(tab, [
        ("busco una notebook", [_parte("busco una notebook", quiere="buscar",
                                       rubro="notebook")]),
        ("quise decir un monitor",
         [_parte("quise decir un monitor", quiere="buscar", rubro="monitor",
                 refiere="la_busqueda")])])
    assert [c.get("categoria") for c in p[1]["consultas"]] == ["monitor"]


def test_la_exclusion_sobre_la_lista_refina_y_no_repite_la_lista(tab):
    """"Los redragon no me gustan, que otros tenes?" apunta a lo mostrado para
    EXCLUIR: no son esos ids, es la busqueda de antes sin redragon."""
    p = _charla(tab, [
        ("mostrame auriculares", [_parte("mostrame auriculares",
                                         quiere="buscar",
                                         rubro="auriculares")]),
        ("no, los redragon no me gustan. que otros tenes?",
         [_parte("no, los redragon no me gustan. que otros tenes?",
                 quiere="buscar", refiere="esos",
                 criterios=[{"concepto": "marca", "valor": "redragon",
                             "fuerza": "evita"}])])])
    (c,) = p[1]["consultas"]
    assert c["categoria"] == "auriculares" and not c.get("ids")
    assert any(x["operador"] == "no_contiene"
               and "redragon" in x["valor"].lower()
               for x in c["condiciones"])


def test_lo_pendiente_vuelve_cuando_contesta_la_repregunta(tab):
    p = _charla(tab, [
        ("cuanto sale el logitech?",
         [_parte("cuanto sale el logitech?", producto="logitech")]),
        ("el mouse", [_parte("el mouse", quiere="buscar", rubro="mouse")])])
    assert p[0].get("repreguntar"), "logitech es de varios rubros"
    (c,) = p[1]["consultas"]
    assert c["categoria"] == "mouse" and "logitech" in c["texto"].lower()


def test_el_nombre_de_un_rubro_no_es_un_producto(tab):
    from banco_pruebas.compilador import validar
    limpia, avisos = validar(
        {"partes": [_parte("el teclado es inalambrico?", producto="teclado")]},
        "el teclado es inalambrico?", tab)
    assert limpia["partes"][0]["producto"] == ""
    assert limpia["partes"][0]["rubro"] == "teclado"


def test_el_producto_corregido_del_audio_pasa_y_el_inventado_no():
    from banco_pruebas.compilador import _escrito
    msg = "ola kiero saver el presio del teclao logitec k 120"
    assert _escrito("logitech", msg) and _escrito("k120", msg)
    assert not _escrito("g502", msg)


def test_las_corridas_de_las_tandas_nuevas_siguen_enteras(tab):
    """Tres corridas de Gemini por cada tanda nueva del 23-sep. Son de
    regresion, no de validacion: las tandas se arreglaron mirandolas. El
    numero se dice: doce corridas, 549 casillas."""
    import os
    with open(os.path.join(os.path.dirname(M.GRABADAS),
                           "fichas_tandas_nuevas.json"),
              encoding="utf-8") as f:
        corridas = json.load(f)["corridas"]
    assert len(corridas) == 12
    fallas, total = [], 0
    for k, cor in enumerate(corridas, 1):
        ok, de, _na, _ = M.correr(
            M.charlas_de_la_vara("", cor["vara"]), tab,
            lambda t, c, n, _f=cor["fichas"]: _f[c][n - 1],
            ver=lambda *_a: None)
        total += de
        if ok != de:
            fallas.append(f"corrida {k} {cor['vara']}: {ok} de {de}")
    assert total == 549
    assert not fallas, fallas
