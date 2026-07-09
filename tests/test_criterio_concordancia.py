"""
AREA: Dos interpretes del criterio "lo mas barato" (decision de Martin, 9-jul).

El regex del codigo (detectar_criterio) no entiende "eco" ni abreviaturas; el
LLM si (campo 'criterio' del schema). concordancia_criterio los cruza:
  - ambos coinciden -> 'actuar'    (se arma el total sin preguntar)
  - solo uno lo ve  -> 'confirmar' (pregunta corta '¿los mas baratos?')
  - ninguno         -> ''          (no es turno de criterio)
Y _es_afirmacion_barato resuelve la confirmacion del turno siguiente. Logica
pura, sin LLM.
"""
from app.core.estado_venta import (detectar_criterio, criterio_del_interprete,
                                    concordancia_criterio)
from app.core.interprete_libre import _es_afirmacion_barato


def test_regex_no_entiende_eco():
    # El nucleo del caso real: "lo mas eco" no lo caza el regex.
    assert detectar_criterio("Lo mas eco") == ""
    assert detectar_criterio("los mas baratos") == "más barato"


def test_llm_lee_el_criterio():
    assert criterio_del_interprete({"criterio": "mas_barato"}) is True
    assert criterio_del_interprete({"criterio": None}) is False
    assert criterio_del_interprete({}) is False
    assert criterio_del_interprete(None) is False


def test_ambos_coinciden_actuar():
    # "los mas baratos": regex SI + LLM SI -> se arma directo.
    assert concordancia_criterio("los mas baratos",
                                 {"criterio": "mas_barato"}) == "actuar"


def test_solo_llm_confirmar():
    # "lo mas eco": regex NO + LLM SI -> confirmar (no sellar a ciegas).
    assert concordancia_criterio("Lo mas eco",
                                 {"criterio": "mas_barato"}) == "confirmar"


def test_solo_codigo_confirmar():
    # Divergencia inversa: el LLM no lo marco pero el regex si -> confirmar.
    assert concordancia_criterio("los mas baratos",
                                 {"criterio": None}) == "confirmar"


def test_ninguno_vacio():
    assert concordancia_criterio("quiero un mouse", {"criterio": None}) == ""
    assert concordancia_criterio("hola", {}) == ""


def test_afirmacion_confirma_barato():
    assert _es_afirmacion_barato("si dale", {}) is True
    assert _es_afirmacion_barato("eso", {}) is True
    assert _es_afirmacion_barato("los mas baratos", {}) is True
    # el LLM re-lee el criterio en la respuesta: tambien cuenta.
    assert _es_afirmacion_barato("ponele", {"criterio": "mas_barato"}) is True


def test_negacion_cancela_barato():
    assert _es_afirmacion_barato("no, mejor los mejores", {}) is False
    assert _es_afirmacion_barato("no gracias", {}) is False
    # una negacion explicita manda sobre el criterio que lea el LLM.
    assert _es_afirmacion_barato("no", {"criterio": "mas_barato"}) is False
