"""
Regresion del veto de negacion del interpretador.

  E14  El filtro de negacion quedo como codigo muerto: contiene_negacion y
       FRASES_NEGACION_NUCLEO existen pero no se llaman desde el camino vivo.
       Una decision_compra que trae una negacion nucleo ('no lo quiero') no se
       veta por codigo; queda todo librado al LLM.

El arreglo esperado es una funcion determinista aplicar_veto_negacion que el
interpretador use para vetar una decision_compra cuando hay negacion nucleo.
Este test define ese contrato y HOY falla porque la funcion no existe.
"""
import pytest


def test_e14_veto_negacion_se_aplica():
    from app.core.interpretador import aplicar_veto_negacion  # no existe hoy
    entrada = {"intencion": "decision_compra", "confianza": 0.9}
    r = aplicar_veto_negacion(entrada, "no lo quiero, mejor lo pienso")
    assert r.get("intencion") != "decision_compra", (
        "Una negacion nucleo debe vetar la decision_compra por codigo, no "
        "depender solo del LLM.")


def test_e14_no_veta_afirmacion_limpia():
    from app.core.interpretador import aplicar_veto_negacion
    entrada = {"intencion": "decision_compra", "confianza": 0.9}
    r = aplicar_veto_negacion(entrada, "dale, lo llevo, cerramos")
    assert r.get("intencion") == "decision_compra", (
        "Sin negacion, la decision_compra queda intacta.")
