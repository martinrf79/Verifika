"""
CONTACTOR ABARCATIVO — lock del enum de categorias de la fuente de verdad.

Ata el interprete a las 76 categorias de base_conocimiento (una sola fuente, sin
duplicar): el modelo DECLARA cual/cuales toca el mensaje, atado por enum a nivel
token, y el hub engancha el criterio de cada una desde la fuente. Cubre la
pregunta compleja multi-tema y el honesto "ninguna" sin cortar la venta.
"""
from app.core.guia_venta_prosa import categorias_conocimiento, meta_categoria
from app.core.interpretador import _schema_interprete, validar_schema
from app.core.hub_atado import _guia_categorias


def test_enum_es_la_fuente_de_verdad_completa():
    cats = categorias_conocimiento()
    # las 76 categorias reales de base_conocimiento, ni una inventada ni de menos
    assert len(cats) == 76
    assert len(set(cats)) == len(cats)  # sin duplicados
    for esperada in ("objecion_precio", "compatibilidad", "cuotas_financiacion",
                     "envio_costo", "saludo_apertura", "garantia", "regalo"):
        assert esperada in cats


def test_meta_categoria_trae_grupo_y_pilar_para_enrutar():
    m = meta_categoria("objecion_precio")
    assert m.get("grupo") == "objeciones"
    assert m.get("pilar")
    assert meta_categoria("no_existe") == {}


def test_schema_ata_categorias_al_enum_y_las_exige():
    sch = _schema_interprete(["Mouse X"], ["mouse", "teclado"])
    props = sch["properties"]
    assert "categorias" in props
    enum = props["categorias"]["items"]["enum"]
    assert len(enum) == 76
    assert "objecion_precio" in enum
    # required para el strict de Gemini/OpenAI
    assert "categorias" in sch["required"]


def test_validar_schema_coacciona_string_a_lista():
    r = {"intencion": "pregunta_especifica", "confianza": 0.9,
         "categorias": "objecion_precio"}
    ok, _ = validar_schema(r)
    assert ok and r["categorias"] == ["objecion_precio"]


def test_validar_schema_descarta_categoria_inventada():
    r = {"intencion": "pregunta_especifica", "confianza": 0.9,
         "categorias": ["objecion_precio", "INVENTADA", "envio_costo"]}
    validar_schema(r)
    assert r["categorias"] == ["objecion_precio", "envio_costo"]


def test_validar_schema_ausente_queda_lista_vacia():
    r = {"intencion": "saludo", "confianza": 0.9}
    validar_schema(r)
    assert r["categorias"] == []


def test_hub_engancha_criterio_multi_tema():
    # pregunta compleja con VARIAS categorias -> viajan los criterios de todas
    b = _guia_categorias({"categorias": ["objecion_precio", "compatibilidad",
                                         "envio_costo"]})
    assert "objecion_precio:" in b
    assert "compatibilidad:" in b
    assert "envio_costo:" in b
    assert "el dato duro sigue saliendo de las tools" in b


def test_hub_sin_categorias_no_adjunta_nada():
    assert _guia_categorias({"categorias": []}) == ""
    assert _guia_categorias({}) == ""


def test_hub_dedup_no_repite_criterio():
    b = _guia_categorias({"categorias": ["garantia", "garantia"]})
    assert b.count("garantia:") == 1
