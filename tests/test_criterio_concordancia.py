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


# --- Criterio INTERMEDIO (11-jul, caso real del banco: "economicos pero no
# lo mas barato que haya" armaba los MAS baratos, lo contrario de lo pedido) ---

from app.core.estado_venta import criterio_llm


def test_detectar_intermedio_gana_sobre_barato():
    # La negacion contiene 'barato': el orden de chequeo importa.
    assert detectar_criterio(
        "que sean economicos pero no lo mas barato que haya, algo intermedio"
    ) == "intermedio"
    assert detectar_criterio("algo de gama media") == "intermedio"
    assert detectar_criterio("ni el mas barato ni el mas caro") == "intermedio"
    assert detectar_criterio("no lo más barato") == "intermedio"


def test_criterio_llm_valores():
    assert criterio_llm({"criterio": "intermedio"}) == "intermedio"
    assert criterio_llm({"criterio": "mas_barato"}) == "mas_barato"
    assert criterio_llm({"criterio": "cualquier_cosa"}) == ""
    assert criterio_llm(None) == ""


def test_concordancia_intermedio_manda():
    # Cualquiera de los dos que lea intermedio: jamas 'actuar' con baratos.
    assert concordancia_criterio(
        "economicos pero no lo mas barato, algo intermedio",
        {"criterio": "mas_barato"}) == "intermedio"
    assert concordancia_criterio(
        "quiero teclados", {"criterio": "intermedio"}) == "intermedio"


def test_concordancia_barato_sigue_igual():
    assert concordancia_criterio("los mas baratos",
                                 {"criterio": "mas_barato"}) == "actuar"
    assert concordancia_criterio("Lo mas eco",
                                 {"criterio": "mas_barato"}) == "confirmar"
    assert concordancia_criterio("quiero un mouse", {"criterio": None}) == ""


def test_intermedio_con_stock_elige_el_del_medio(firestore_doble):
    from app.core.tools_context import set_current_tienda
    from app.core.guia_compra import (intermedio_con_stock,
                                      mas_barato_con_stock)
    set_current_tienda("verifika_prod")
    barato = mas_barato_con_stock("mouse")
    medio = intermedio_con_stock("mouse")
    assert medio and medio.get("stock", 0) > 0
    # El del medio nunca es el minimo que el cliente rechazo (catalogo real
    # de mouse tiene mas de dos precios distintos).
    assert medio["precio_ars"] >= barato["precio_ars"]
    assert medio["id"] != barato["id"]
