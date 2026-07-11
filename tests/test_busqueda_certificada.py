"""
AREA: Busqueda certificada del candidato unico + not_found honesto (11-jul).

Dos fallas reales del banco (guiones 28 y 09): "sumame el HyperX Cloud II"
caia al fallback porque el enum del interprete solo referencia lo mostrado,
y "tenes joysticks?" caia al fallback en vez de un no honesto. Corre sobre
el compositor con el catalogo REAL del doble.
"""
from app.core.compositor import componer


def test_candidato_unico_se_certifica_y_sale_ficha(firestore_doble):
    # El interprete no puede resolver por enum un producto nunca mostrado,
    # pero deja el candidato: el codigo lo reconcilia contra el catalogo.
    interp = {"intencion": "aporta_dato", "producto_resuelto": None,
              "candidatos": ["HyperX Cloud II"], "confianza": 0.7}
    texto, meta = componer("bueno dale, sumame el HyperX Cloud II a la compra",
                           interp, {}, "verifika_prod")
    # El catalogo real tiene 4 variantes (Cloud II/III en dos colores):
    # AMBIGUO pregunta con las opciones reales, jamas elige ni cae al
    # fallback (regla 0).
    assert "HyperX Cloud II" in texto
    assert "$" in texto  # las lineas traen el precio real
    assert "¿Cuál preferís?" in texto
    assert "no te terminé de entender" not in texto


def test_candidato_unico_exacto_sale_ficha(firestore_doble):
    interp = {"intencion": "aporta_dato", "producto_resuelto": None,
              "candidatos": ["HyperX Cloud II Negro"], "confianza": 0.7}
    texto, meta = componer("sumame el HyperX Cloud II negro",
                           interp, {}, "verifika_prod")
    assert "HyperX Cloud II Negro" in texto
    assert "$" in texto
    tools = [t["name"] for t in meta.get("tools_called", [])]
    assert "get_product_details" in tools


def test_candidato_vago_no_se_certifica(firestore_doble):
    # 'mouse' matchea medio catalogo: no reconcilia unico y no sale ficha
    # inventada; el turno sigue por categoria (que si responde).
    interp = {"producto_resuelto": None, "candidatos": ["mouse"],
              "confianza": 0.6}
    texto, _ = componer("quiero un mouse", interp, {}, "verifika_prod")
    # responde la seccion de categoria con opciones reales, no una ficha unica
    assert "De mouse tengo" in texto


def test_joysticks_da_no_honesto(firestore_doble):
    interp = {"intencion": "exploracion", "producto_resuelto": None,
              "candidatos": ["joysticks"], "confianza": 0.6}
    texto, _ = componer("tenes joysticks?", interp, {}, "verifika_prod")
    assert "no trabajamos" in texto
    assert "no te terminé de entender" not in texto
    # ofrece lo que si hay (las primeras categorias reales)
    assert "auriculares" in texto.lower()


def test_pregunta_conceptual_no_dispara_not_found(firestore_doble):
    # 'diferencia entre membrana y mecanico' no es disponibilidad: jamas
    # 'membrana no trabajamos'.
    interp = {"producto_resuelto": None,
              "candidatos": ["membrana", "mecanico"], "confianza": 0.5}
    texto, _ = componer("cual es la diferencia entre membrana y mecanico?",
                        interp, {}, "verifika_prod")
    assert "no trabajamos" not in texto


def test_categoria_real_no_dispara_not_found(firestore_doble):
    interp = {"producto_resuelto": None, "candidatos": ["auriculares"],
              "confianza": 0.6}
    texto, _ = componer("tenes auriculares?", interp, {}, "verifika_prod")
    assert "no trabajamos" not in texto
    assert "De auriculares tengo" in texto
