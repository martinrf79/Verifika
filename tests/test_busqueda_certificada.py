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


# ── CERTIFICADOR DE MODELO PUNTUAL (19-jul, guiones 39/40) ───────────────────

def _mp(msg):
    from app.core.guia_compra import modelo_puntual
    from app.core.tools_context import set_current_tienda
    set_current_tienda("verifika_prod")
    return modelo_puntual(msg, "verifika_prod")


def test_marca_ajena_ofrece_lo_mas_parecido_real(firestore_doble):
    """'Asus ROG Strix G15': no hay Asus, pero existe la Dell G15 ->
    cercanos con la Dell, exactos vacio (la politica inventada muere aca)."""
    r = _mp("Prefiero Asus. ¿Tienen en stock el modelo ROG Strix G15?")
    assert r is not None and r["exactos"] == []
    assert any("G15" in p["nombre"] for p in r["cercanos"])


def test_variante_real_se_confirma_con_el_catalogo(firestore_doble):
    """'monitor Samsung Odyssey G5 de 27': existe el Odyssey G5 32 ->
    exactos con el real (el turno hueco muere aca)."""
    r = _mp("Hola, ¿tienen disponibilidad del monitor Samsung Odyssey G5 "
            "de 27 pulgadas?")
    assert r is not None
    assert any("Odyssey G5" in p["nombre"] for p in r["exactos"])


def test_decision_sobre_modelo_real_va_al_flujo_normal(firestore_doble):
    """'quiero la notebook hp 245 g9' es un pedido, no una duda: None."""
    assert _mp("quiero la notebook hp 245 g9") is None


def test_medidas_y_unidades_no_son_modelo(firestore_doble):
    """'algo en 4K' no dispara el certificador."""
    assert _mp("busco una notebook para edición de video pesado, "
               "algo en 4K") is None


def test_modelo_inexistente_sin_familia_da_categoria(firestore_doble):
    """Modelo sin ningun pariente en catalogo -> exactos y cercanos vacios,
    la categoria nombrada viaja para ofrecer opciones."""
    r = _mp("¿tienen el teclado Ducky One3 SF? busco un teclado")
    assert r is not None
    assert r["exactos"] == [] and r["cercanos"] == []
    assert r["categoria"] and r["categoria"].lower().startswith("teclado")
