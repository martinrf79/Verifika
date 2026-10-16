"""LOS CASOS GRABADOS SON LA META, Y LA META ES UN TEST — 16-oct-2026, pedido de Martin.

POR QUE. Cada sesion armaba su panorama leyendo textos y media con otra vara:
DeepSeek una, Gemini otra, reproduciendo la tercera. Lo que quedaba a medias era
una frase, y la sesion siguiente no lo veia. Aca la vara es fija: charlas que
el modelo ya contesto, grabadas, que se vuelven a pasar por el codigo de hoy
SIN MODELO, y se califican con las casillas de la vara de las 58 sobre lo que
recibe el cliente. Si una falla aca, la falla es del codigo: se arregla sin
gastar y sin depender del modelo.

LO QUE FALTA ES UN XFAIL ESTRICTO con su motivo. Si alguien lo arregla y no saca
la marca, se pone rojo. `grabadas_techo.json` solo baja.

Las grabaciones: `gp_montos_1`, las 20 de memoria con Gemini pago y el redactor
de la FICHA 69; `gp_pedido_1`, K11 y K21 despues del arreglo del pedido.
"""
import json
import os
import subprocess
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRABACIONES = {"gp_montos_1": 20, "gp_pedido_1": 2}
FALTA = {
    ("gp_montos_1", "C35"): "PLAN: 'pasame otras opciones' no excluye lo ya mostrado, y el interprete pierde la "
                            "condicion gamer. HOY vuelven los mismos cuatro Logitech. OBJETIVO mostrar otros mouse "
                            "gamer que no se mostraron.",
}


@pytest.fixture(scope="module")
def resultados():
    out = {}
    for et in GRABACIONES:
        r = subprocess.run([sys.executable, os.path.join(RAIZ, "tests", "grabadas_reproducir.py"), et],
                           capture_output=True, text=True, timeout=900, cwd=RAIZ)
        for ln in r.stdout.splitlines():
            if ln.startswith("GRABADA "):
                d = json.loads(ln[8:])
                out[(et, d["id"])] = d
        assert any(k[0] == et for k in out), f"{et} no reprodujo nada:\n{r.stderr[-2000:]}"
    return out


def _casos():
    from banco_pruebas.sonda_charlas import SALIDA
    vistos = []
    for x in open(os.path.join(RAIZ, SALIDA), encoding="utf-8"):
        for et in GRABACIONES:
            if f'"{et}"' in x[:300]:
                d = json.loads(x)
                if d["etiqueta"] == et:
                    vistos.append((et, d["id"]))
    return vistos


CASOS = _casos()


@pytest.mark.parametrize("caso", [pytest.param(c, marks=pytest.mark.xfail(strict=True, reason=FALTA[c]))
                                  if c in FALTA else c for c in CASOS], ids=[f"{e}-{i}" for e, i in CASOS])
def test_la_charla_grabada_sale_bien(resultados, caso):
    d = resultados[caso]
    assert not d["sin_grabacion"], f"el codigo llamo al modelo en un paso que no estaba grabado: {d}"
    assert not d["mal"], d["mal"]


def test_cuantas_charlas_se_corrieron():
    """Cuantas, no solo que pasaron: si alguien borra una grabacion, esto avisa."""
    por = {et: sum(1 for e, _ in CASOS if e == et) for et in GRABACIONES}
    assert por == GRABACIONES


def test_lo_que_falta_solo_baja():
    techo = json.load(open(os.path.join(RAIZ, "tests", "grabadas_techo.json"), encoding="utf-8"))["falta"]
    assert len(FALTA) <= techo, f"{len(FALTA)} casos marcados contra un techo de {techo}"
    assert all(r.startswith(("A MEDIAS:", "PLAN:")) for r in FALTA.values())
