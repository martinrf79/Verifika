"""
AREA: Filtro determinista de referencias comparativas del interprete.

Sesgo medido en el banco de interpretacion (8-jul): ante 'el barato no, el
otro' con dos variantes baratas empatadas, el modelo resuelve confiado la OTRA
variante barata. La comparacion de precios es cerrada: la corrige el codigo.
Cubre _corregir_referencia_comparativa (app/core/interpretador.py). Puro.
"""
from app.core.interpretador import _corregir_referencia_comparativa

_VISTOS = [
    {"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro", "precio": 8500},
    {"id": "MOU0024", "nombre": "Mouse Genius DX-110 Blanco", "precio": 8500},
    {"id": "MOU0009", "nombre": "Mouse Logitech M170 Negro", "precio": 12000},
]


def test_barato_negado_se_corrige_al_unico_caro():
    interp = {"producto_resuelto": "Mouse Genius DX-110 Blanco",
              "confianza": 0.9, "candidatos": [],
              "pedido": [{"producto": "Mouse Genius DX-110 Blanco", "cantidad": 1}]}
    out = _corregir_referencia_comparativa(interp, "el barato no, el otro", _VISTOS)
    assert out["producto_resuelto"] == "Mouse Logitech M170 Negro"
    assert out["pedido"][0]["producto"] == "Mouse Logitech M170 Negro"


def test_varios_caros_degrada_a_candidatos():
    vistos = _VISTOS + [{"id": "MOU0049", "nombre": "Mouse Genius NX-7000 Negro",
                         "precio": 14000}]
    interp = {"producto_resuelto": "Mouse Genius DX-110 Negro",
              "confianza": 0.9, "candidatos": [], "pedido": []}
    out = _corregir_referencia_comparativa(interp, "no el barato, el otro", vistos)
    assert out["producto_resuelto"] is None
    assert len(out["candidatos"]) == 2
    assert out["confianza"] <= 0.5


def test_lectura_coherente_no_se_toca():
    interp = {"producto_resuelto": "Mouse Logitech M170 Negro",
              "confianza": 0.9, "candidatos": [], "pedido": []}
    out = _corregir_referencia_comparativa(interp, "el barato no, el otro", _VISTOS)
    assert out["producto_resuelto"] == "Mouse Logitech M170 Negro"
    assert out["confianza"] == 0.9


def test_mensaje_sin_comparativa_no_se_toca():
    interp = {"producto_resuelto": "Mouse Genius DX-110 Blanco",
              "confianza": 0.9, "candidatos": [], "pedido": []}
    out = _corregir_referencia_comparativa(interp, "dame el blanco", _VISTOS)
    assert out["producto_resuelto"] == "Mouse Genius DX-110 Blanco"
