"""
CONTACTOR ABARCATIVO — lock del enum de categorias de la fuente de verdad.

Ata el interprete a las 76 categorias de base_conocimiento (una sola fuente, sin
duplicar): el modelo DECLARA cual/cuales toca el mensaje, atado por enum a nivel
token, y el hub engancha el criterio de cada una desde la fuente. Cubre la
pregunta compleja multi-tema y el honesto "ninguna" sin cortar la venta.
"""
from app.core.guia_venta_prosa import categorias_conocimiento, meta_categoria
from app.core.interpretador import _schema_interprete, validar_schema
from app.core.generador_v2 import universo_productos


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


# ── EL ENUM DEL SOLVER: universo_productos consume los campos ESTRUCTURADOS ──
# del interprete (no solo el texto). Reemplaza a las guias de texto del hub: el
# anclado ya no es prosa que viaja al solver, es el ENUM de ids que el solver
# puede referenciar, atado por construccion. Asi el dato es imposible de inventar.

def test_universo_incluye_solicitud_nueva_no_nombrada_en_el_mensaje(firestore_doble):
    # el cliente pide una categoria que el MENSAJE no nombra (el interprete la
    # leyo en solicitud_nueva): igual entra al enum, la categoria no se pierde.
    u = universo_productos(
        "necesito algo para la oficina", {}, "verifika_prod",
        {"solicitud_nueva": [{"categoria": "teclado", "cantidad": 2,
                              "criterio": "mas_barato"}]})
    tecs = [p for p in u if "teclado" in (p.get("categoria", "")
                                          + p.get("nombre", "")).lower()]
    assert tecs, "la categoria pedida en solicitud_nueva no entro al universo"


def test_universo_incluye_producto_del_pedido(firestore_doble):
    # el producto del pedido entra al enum por su nombre, atado al id real.
    u = universo_productos(
        "dale", {}, "verifika_prod",
        {"pedido": [{"producto": "Mouse Genius DX-110 Negro", "cantidad": 1,
                     "destino": None}]})
    assert any(p["id"] == "MOU0023" for p in u)


def test_universo_incluye_producto_consultado(firestore_doble):
    u = universo_productos(
        "y ese sirve para oficina?", {}, "verifika_prod",
        {"productos_consultados": [{"producto": "Mouse Genius DX-110 Negro",
                                    "consulta": "opinion"}]})
    assert any(p["id"] == "MOU0023" for p in u)


def test_universo_sin_interp_no_rompe(firestore_doble):
    # sin campos del interprete el universo sale de mostrados/carrito/mensaje.
    u = universo_productos("tenes mouse?", {}, "verifika_prod", {})
    assert any("mouse" in p.get("nombre", "").lower() for p in u)


# ── CONTACTOR DEL DESTINO al CP (multidestino robusto 2/3/4) ─────────────────
from app.core.interpretador import _canonizar_destinos_cp


def test_destino_concatenado_se_parte_por_localidad():
    r = {"pedido": [{"producto": "Auric", "cantidad": 2, "destino": "Mendoza y Neuquen"}]}
    _canonizar_destinos_cp(r)
    dests = [i["destino"] for i in r["pedido"]]
    assert "mendoza" in dests and "neuquen" in dests
    assert len(r["pedido"]) == 2


def test_destino_una_localidad_queda_intacto():
    # una sola localidad: NO se toca, conserva su provincia si la trae
    r = {"pedido": [{"producto": "Mouse", "cantidad": 1, "destino": "Cordoba capital"}]}
    _canonizar_destinos_cp(r)
    assert len(r["pedido"]) == 1
    assert r["pedido"][0]["destino"] == "Cordoba capital"


def test_destino_tres_localidades_escala():
    r = {"pedido": [{"producto": "Kit", "cantidad": 3, "destino": "Rosario, Cordoba y Salta"}]}
    _canonizar_destinos_cp(r)
    assert len(r["pedido"]) == 3
    assert {"rosario", "cordoba", "salta"} <= {i["destino"] for i in r["pedido"]}


def test_destino_null_no_toca():
    r = {"pedido": [{"producto": "Mouse", "cantidad": 1, "destino": None}]}
    _canonizar_destinos_cp(r)
    assert r["pedido"][0]["destino"] is None
