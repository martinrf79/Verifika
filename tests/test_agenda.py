"""LO QUE RECIBE EL INTERPRETE Y LO QUE CUMPLE EL EJECUTOR — sin modelo (20-oct-2026).

El 22-oct el requisito cambio, FICHA 76: el modelo llena la ficha nativa y ya no escribe la agenda. Se fueron los seis
ejemplos de la consigna, el control de lo que faltaba citar, la tabla del marcador al modelo y la suficiencia, que
median la agenda escrita por el modelo. Quedan:
  1. el candado: una pregunta que el ejecutor no puede cumplir no se pierde;
  2. las agendas a mano, dentro del menu.
El peso de lo que recibia la lectura se saco el 30-oct con la lectura: el turno lo contesta el agente, FICHA 83.
"""
import pytest

from banco_pruebas import cableado58 as CB
from banco_pruebas.agendas58 import AGENDAS

TIENDA = "verifika_prod"


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
