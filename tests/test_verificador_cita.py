"""
AREA: Cita de prosa de venta — los DOS ladrillos del RAG de prosa.

Ladrillo 1 (Citador, solver_gemini._prosa_citada): captura los ids de los
chunks de la guia de venta que el solver consulto en el turno, deja la CITA
declarada en meta['prosa_citada'].

Ladrillo 2 (verificador_cita): resuelve cada id citado contra el corpus jurado
con texto_de(id); marca los que no existen. Es la red que ata la prosa a la
fuente igual que el numero: en el camino sano los ids salen del propio corpus y
siempre validan; una cita invalida se marca, no rompe el turno.
"""
from app.core import guia_venta_prosa
from app.core.solver_gemini import _prosa_citada
from app.core.verificador_cita import (
    citas_de_meta, verificar_cita, verificar_meta)


# Dos ids reales del corpus para no atarse a un tema puntual.
_ID1, _ID2 = list(guia_venta_prosa.GUIA_VENTA)[:2]


def _call(name, result):
    return {"name": name, "args": {}, "result": result}


# ── Ladrillo 1: el Citador ──────────────────────────────────────────────────

def test_citador_captura_ids_de_la_guia():
    tools = [
        _call("search_products", {"tipo": "producto", "id": "MOU1"}),
        _call("consultar_guia_venta", {"tema": _ID1, "id": _ID1, "texto": "x"}),
    ]
    assert _prosa_citada(tools) == [_ID1]


def test_citador_ignora_otras_tools():
    # El 'id' de un producto NO es una cita de prosa: solo cuenta el que sale de
    # consultar_guia_venta.
    tools = [_call("search_products", {"tipo": "producto", "id": "TEC9"})]
    assert _prosa_citada(tools) == []


def test_citador_dedup_en_orden():
    tools = [
        _call("consultar_guia_venta", {"id": _ID2, "texto": "a"}),
        _call("consultar_guia_venta", {"id": _ID1, "texto": "b"}),
        _call("consultar_guia_venta", {"id": _ID2, "texto": "a"}),
    ]
    assert _prosa_citada(tools) == [_ID2, _ID1]


def test_citador_tolera_tools_vacio_o_basura():
    assert _prosa_citada(None) == []
    assert _prosa_citada([{"name": "consultar_guia_venta", "result": None}]) == []


# ── Ladrillo 2: el Verificador de cita ──────────────────────────────────────

def test_verificar_cita_valida():
    r = verificar_cita([_ID1, _ID2])
    assert r["ok"] and r["invalidas"] == [] and r["validas"] == [_ID1, _ID2]


def test_verificar_cita_marca_id_inexistente():
    r = verificar_cita([_ID1, "tema_que_no_existe_jamas"])
    assert not r["ok"]
    assert r["invalidas"] == ["tema_que_no_existe_jamas"]
    assert r["validas"] == [_ID1]


def test_sin_citas_es_ok():
    # No hay nada falso que marcar: una respuesta que no cito prosa no falla.
    r = verificar_cita([])
    assert r["ok"] and r["total"] == 0


def test_todo_id_del_corpus_resuelve():
    # Contrato Citador<->Verificador: cada tema del corpus es una cita valida.
    r = verificar_cita(list(guia_venta_prosa.GUIA_VENTA))
    assert r["ok"] and r["invalidas"] == []


# ── Integracion Citador -> meta -> Verificador (el camino vivo) ─────────────

def test_citas_de_meta_prefiere_prosa_citada():
    meta = {"prosa_citada": [_ID1], "tools_called": [
        _call("consultar_guia_venta", {"id": _ID2, "texto": "x"})]}
    # Manda lo que declaro el citador, no lo que se derive de tools_called.
    assert citas_de_meta(meta) == [_ID1]


def test_citas_de_meta_deriva_de_tools_si_no_hay_declaracion():
    meta = {"tools_called": [
        _call("consultar_guia_venta", {"id": _ID1, "texto": "x"})]}
    assert citas_de_meta(meta) == [_ID1]


def test_verificar_meta_extremo_a_extremo():
    tools = [_call("consultar_guia_venta", {"id": _ID1, "texto": "x"})]
    meta = {"tools_called": tools, "prosa_citada": _prosa_citada(tools)}
    r = verificar_meta(meta)
    assert r["ok"] and r["citas"] == [_ID1] and r["validas"] == [_ID1]
