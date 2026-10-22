"""LO QUE RECIBE EL INTERPRETE Y LO QUE CUMPLE EL EJECUTOR — sin modelo (20-oct-2026).

El 22-oct el requisito cambio, FICHA 76: el modelo llena la ficha nativa y ya no escribe la agenda. Se fueron los seis
ejemplos de la consigna, el control de lo que faltaba citar, la tabla del marcador al modelo y la suficiencia, que
median la agenda escrita por el modelo. Quedan:
  1. el candado: una pregunta que el ejecutor no puede cumplir no se pierde;
  2. las agendas a mano, dentro del menu;
  3. el peso: lo que recibe el modelo en cada turno de las 58 y las K entra en tres mil tokens.
La ficha y su paso a la agenda se prueban en `test_ficha.py`.
"""
import asyncio
import copy

import pytest

from banco_pruebas import cableado58 as CB
from banco_pruebas import clon_produccion as C
from banco_pruebas.agendas58 import AGENDAS

TIENDA = "verifika_prod"


def _vistas() -> list:
    """[(charla, turno, mensaje, estado, historial)] de las 58 y las K, antes de cada turno, con las agendas a mano."""
    interprete = CB.instalar()
    from banco_pruebas.agendas58 import EXPLICAR
    out = []
    for charla in CB.charlas():
        uid = f"peso_{charla['id']}"
        C.reiniciar_cliente(uid)
        cola = list(AGENDAS[charla["id"]])

        async def _interpretar(mensaje, historial, estado, *a, _c=charla["id"], _cola=cola, **k):
            out.append((_c, len([x for x in out if x[0] == _c]), mensaje, copy.deepcopy(estado), list(historial)))
            return _cola.pop(0) if _cola else {}

        async def _explicar(pregunta, *a, **k):
            return EXPLICAR.get(pregunta, "")
        interprete.interpretar, interprete.explicar = _interpretar, _explicar
        for t in charla["turnos"]:
            asyncio.run(C.turno(uid, t["texto"]))
    return out


@pytest.fixture(scope="module")
def vistas():
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    v = _vistas()
    yield v
    llm_reintento._cliente = puerta


def test_el_candado_no_deja_una_pregunta_sin_estado():
    """Una pregunta que el ejecutor no puede cumplir no se pierde en silencio: se repregunta con su cita."""
    from app.core.flujo import estado as E
    from app.core.flujo.ejecutor import ejecutar
    t = ejecutar({"preguntas": [{"n": 1, "cita": "y me lo envolves para regalo?", "accion": "envolver"}]},
                 E.leer({}), TIENDA)
    assert t.estados == {1: "sin_estado"}
    assert any("y me lo envolves para regalo?" in q for q in t.preguntas), t.preguntas


def test_una_agenda_a_mano_por_turno_y_dentro_del_menu():
    from app.core.flujo import agenda as A
    charlas = CB.charlas()
    preguntas = 0
    for c in charlas:
        assert len(AGENDAS[c["id"]]) == len(c["turnos"]), c["id"]
        for ag in AGENDAS[c["id"]]:
            for p in A.preguntas(ag):
                preguntas += 1
                assert p["accion"] in A.ACCIONES, (c["id"], p)
                if p["accion"] in A.OBLIGATORIO:
                    assert p.get(A.OBLIGATORIO[p["accion"]]), (c["id"], p)
    print(f"\nAGENDAS: {len(charlas)} charlas, {sum(len(c['turnos']) for c in charlas)} turnos, {preguntas} preguntas")


def test_lo_que_recibe_el_modelo_entra_en_tres_mil_tokens(vistas):
    from app.core.flujo import ficha as F
    pesos = [(sum(len(m["content"].encode()) for m in F.mensajes(msj, h, e, TIENDA)) // 4, cid, t + 1)
             for cid, t, msj, e, h in vistas]
    mayor = max(pesos)
    assert mayor[0] <= 3000, f"{mayor[1]} T{mayor[2]}: {mayor[0]} tokens"
    print(f"\nPESO: {len(pesos)} turnos, el mayor {mayor[0]} tokens en {mayor[1]} T{mayor[2]}, "
          f"el promedio {sum(p[0] for p in pesos) // len(pesos)}")
