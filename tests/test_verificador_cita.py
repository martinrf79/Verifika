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
from app.core.verificador_cita import (
    citas_de_meta, verificar_cita, verificar_meta)


# Dos ids reales del corpus para no atarse a un tema puntual.
_ID1, _ID2 = list(guia_venta_prosa.GUIA_VENTA)[:2]


def _call(name, result):
    return {"name": name, "args": {}, "result": result}


# ── Ladrillo 1: el Citador ──────────────────────────────────────────────────

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

def test_citas_de_meta_deriva_de_tools_si_no_hay_declaracion():
    meta = {"tools_called": [
        _call("consultar_guia_venta", {"id": _ID1, "texto": "x"})]}
    assert citas_de_meta(meta) == [_ID1]


# El CITADOR (solver_gemini._prosa_citada) y es_turno_criterio se BORRARON con el
# solver viejo. No se perdio la cita: en el camino atado la produce `renderizar`,
# que al emitir un fragmento de criterio deja el bloque jurado en tools_called; de
# ahi la deriva `citas_de_meta`, que es lo que prueban los tests de arriba.
