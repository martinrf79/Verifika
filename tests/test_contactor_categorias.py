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


# ── EL CRITERIO del solver atado a las CATEGORIAS que declaro el interprete ───
from app.core.generador_v2 import _criterios_del_turno


def test_criterio_atado_a_categorias_del_interprete(firestore_doble):
    # el interprete declara categorias que el mensaje no nombra literal: su
    # criterio entra igual al enum del solver, razona desde la fuente correcta.
    ids, menu = _criterios_del_turno(
        "no se, me parece mucho", None,
        {"categorias": ["objecion_precio", "garantia"]})
    assert "objecion_precio" in ids and "garantia" in ids
    assert "[objecion_precio]" in menu


def test_criterio_rag_sigue_como_red_sin_categorias(firestore_doble):
    # sin categorias declaradas, el RAG del mensaje sigue trayendo criterio.
    ids, _ = _criterios_del_turno("puedo pagar en cuotas", None, {})
    assert "cuotas_financiacion" in ids


# ── CATEGORIA NO VENDIDA desde la FUENTE DE VERDAD (no_vendidas.json) ─────────
from app.core.guia_compra import categoria_no_vendida


def test_no_vendida_desde_config_caza_consola_celular_con_puntuacion(firestore_doble):
    # casos que el guion 62 destapo: consola/play/ps con signo pegado.
    assert categoria_no_vendida("tenes ps5?", "verifika_prod")[0] == "ps5"
    assert categoria_no_vendida("y una play 5 tenes?", "verifika_prod")[0] == "play 5"
    p, alt = categoria_no_vendida("tenes celulares?", "verifika_prod")
    assert p == "celulares" and alt == "tablet"


def test_no_vendida_no_dispara_en_categoria_real(firestore_doble):
    assert categoria_no_vendida("tenes una notebook?", "verifika_prod") is None
    assert categoria_no_vendida("dame un mouse", "verifika_prod") is None


# ── PEDIDO DE CATALOGO: presentar las categorias reales de la fuente ──────────
from app.core.generador_v2 import nota_catalogo


def test_catalogo_presenta_categorias_reales(firestore_doble):
    # "catalogo" / "que vendes" sin categoria puntual: la nota trae las categorias
    # reales para que el solver las liste (bug real: quedaba sin respuesta util).
    for m in ("catalogo", "Pasame catalogo", "que productos tenes?", "que vendes?"):
        n = nota_catalogo(m, "verifika_prod")
        assert n and "mouse" in n and "notebook" in n, m


def test_catalogo_no_dispara_con_categoria_puntual(firestore_doble):
    # si nombra una categoria real, el flujo normal la muestra: no es catalogo.
    assert nota_catalogo("que tenes de mouse?", "verifika_prod") == ""
    assert nota_catalogo("hola quiero un mouse", "verifika_prod") == ""


# ── HONESTIDAD DE SPEC desde la FUENTE DE VERDAD (specs_preguntables.json) ────
from app.core.generador_v2 import estampar_honestidad_specs, _specs_faltantes


def test_spec_ausente_saca_afirmacion_del_modelo_y_estampa_honesto(firestore_doble):
    prod = {"nombre": "Notebook X", "descripcion": "Core i5 16GB 512GB SSD"}
    msg = "esa notebook tiene lector de huella digital?"
    assert [e for e, _ in _specs_faltantes(msg, prod)] == ["el lector de huella"]
    t = ("Notebook X: Core i5 16GB.\n"
         "Lamentablemente no incluye lector de huella, igual es equilibrada.\n"
         "¿Avanzamos con alguno?")
    r = estampar_honestidad_specs(t, msg, prod)
    assert "no incluye lector de huella" not in r.lower()
    assert "la ficha no lo especifica" in r.lower()
    assert "¿Avanzamos con alguno?" in r


def test_spec_presente_en_ficha_no_se_estampa(firestore_doble):
    prod = {"nombre": "Notebook Z", "descripcion": "tiene bluetooth y lector de huella"}
    assert _specs_faltantes("tiene bluetooth?", prod) == []
    t = "Sí, tiene Bluetooth integrado."
    assert estampar_honestidad_specs(t, "tiene bluetooth?", prod) == t


def test_spec_no_preguntada_no_toca_el_texto(firestore_doble):
    prod = {"nombre": "Notebook Z", "descripcion": "Core i5"}
    t = "Es una máquina muy equilibrada para tu trabajo."
    assert estampar_honestidad_specs(t, "cuanto sale?", prod) == t


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
