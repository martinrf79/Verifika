"""
AREA: Schema del interprete para constrained generation dura (Structured Outputs).

Cubre _schema_interprete (app/core/interpretador.py): el schema estricto que ata
intencion y estado a su enum y producto_resuelto al enum de los productos
mostrados (o null). Logica pura, sin LLM.
"""
from app.core.interpretador import (_schema_interprete, INTENCIONES_VALIDAS,
                                     ESTADOS_VALIDOS, FUERA_DE_LISTA)


def test_producto_resuelto_atado_a_mostrados():
    s = _schema_interprete(["Mouse A", "Mouse B"])
    pr = s["properties"]["producto_resuelto"]
    assert pr["enum"] == [None, FUERA_DE_LISTA, "Mouse A", "Mouse B"]
    assert "null" in pr["type"]


def test_intencion_y_estado_son_enum():
    s = _schema_interprete([])
    assert s["properties"]["intencion"]["enum"] == sorted(INTENCIONES_VALIDAS)
    assert s["properties"]["estado_conversacion"]["enum"] == ESTADOS_VALIDOS


def test_sin_productos_queda_la_valvula_de_escape():
    """Sin nada que ofrecerle, el interprete igual puede DECLARAR que el
    cliente nombro algo que no estaba en la lista corta. Sin esa valvula, un
    candidato que la recuperacion no pesco se volvia un "no lo tenemos" falso."""
    s = _schema_interprete([])
    assert s["properties"]["producto_resuelto"]["enum"] == [None, FUERA_DE_LISTA]


def test_dedup_nombres_conserva_orden():
    s = _schema_interprete(["X", "X", "Y", ""])
    assert s["properties"]["producto_resuelto"]["enum"] == [
        None, FUERA_DE_LISTA, "X", "Y"]


def test_strict_todos_los_campos_requeridos():
    # OpenAI strict: additionalProperties false y todo campo en required.
    s = _schema_interprete(["A"])
    assert s["additionalProperties"] is False
    assert set(s["required"]) == set(s["properties"])


def test_productos_consultados_atado_a_mostrados():
    # Consulta MULTIPLE (dos o mas productos en un mensaje): cada item es un
    # producto mostrado (enum) mas que pide de el (consulta, enum cerrado).
    s = _schema_interprete(["Mouse A", "Teclado B"])
    pc = s["properties"]["productos_consultados"]["items"]
    assert pc["properties"]["producto"]["enum"] == [
        None, FUERA_DE_LISTA, "Mouse A", "Teclado B"]
    assert pc["properties"]["consulta"]["enum"] == [
        "precio", "ficha", "stock", "opinion", "comparacion", "envio", "otra"]
    assert set(pc["required"]) == {"producto", "consulta"}


def test_solicitud_nueva_atada_a_categorias():
    # El cliente pide una CATEGORIA aun no mostrada: se ata al enum de las
    # categorias reales (lista cerrada), no al de productos. Asi no se pierde
    # ni se inventa (lado B de la atadura por enum).
    s = _schema_interprete([], ["mouse", "teclado", "monitor"])
    sn = s["properties"]["solicitud_nueva"]["items"]
    assert sn["properties"]["categoria"]["enum"] == ["mouse", "teclado", "monitor"]
    assert sn["properties"]["criterio"]["enum"] == ["mas_barato", "intermedio", None]
    assert set(sn["required"]) == {"categoria", "cantidad", "criterio"}
    assert "solicitud_nueva" in s["required"]


def test_datos_pedido_ya_no_esta():
    # Campo muerto retirado (21-jul): no lo lee ningun consumidor.
    s = _schema_interprete(["A"])
    assert "datos_pedido" not in s["properties"]
    assert "datos_pedido" not in s["required"]


def test_pedido_atado_al_enum_de_mostrados():
    # El campo pedido (guia determinista de pedido) tambien queda atado por
    # enum a lo mostrado: el interprete no puede pedir un producto no visto.
    # destino (multi-envio, 10-jul): renglon PLANO con su localidad o null,
    # nunca grupos anidados (Firestore los prohibe).
    s = _schema_interprete(["Mouse A", "Teclado B"])
    item = s["properties"]["pedido"]["items"]
    assert item["properties"]["producto"]["enum"] == [None, "Mouse A", "Teclado B"]
    assert item["properties"]["cantidad"]["type"] == "integer"
    assert item["properties"]["destino"]["type"] == ["string", "null"]
    assert set(item["required"]) == {"producto", "cantidad", "destino"}


# --- Reparacion del JSON truncado por max_tokens (caso real del banco 11-jul:
# el schema estricto obliga el campo destino, gpt-4o-mini prefiere cerrar el
# objeto y llena la salida de espacios hasta el tope; el JSON queda sin
# cerrar y el turno caia al fallback intencion otra confianza 0) ---

from app.core.interpretador import parsear_respuesta_llm, _reparar_json_truncado

_RAW_TRUNCADO_REAL = (
    '{\n  "intencion": "decision_compra",\n'
    '  "producto_resuelto": "Mouse Genius DX-110 Blanco",\n'
    '  "candidatos": [],\n  "confianza": 0.9,\n  "datos_pedido": null,\n'
    '  "respondiendo_a": "el cliente pide el blanco",\n'
    '  "estado_conversacion": "esperando_confirmacion",\n'
    '  "ofrecer_opciones": null,\n  "criterio": null,\n'
    '  "pedido": [\n    {\n      "producto": "Mouse Genius DX-110 Blanco",\n'
    '      "cantidad": 1\n    \n    \n    \n    \n    \n    \n')


def test_repara_el_truncado_real_del_banco():
    r = parsear_respuesta_llm(_RAW_TRUNCADO_REAL)
    assert r is not None
    assert r["intencion"] == "decision_compra"
    assert r["producto_resuelto"] == "Mouse Genius DX-110 Blanco"
    assert r["pedido"][0]["producto"] == "Mouse Genius DX-110 Blanco"
    assert r["pedido"][0]["cantidad"] == 1


def test_repara_string_sin_cerrar():
    r = _reparar_json_truncado('{"intencion": "consulta", "candidatos": ["Mouse A')
    assert r == {"intencion": "consulta", "candidatos": ["Mouse A"]}


def test_repara_coma_colgante():
    r = _reparar_json_truncado('{"intencion": "consulta", "confianza": 0.8,')
    assert r == {"intencion": "consulta", "confianza": 0.8}


def test_basura_irreparable_devuelve_none():
    assert _reparar_json_truncado("no soy json") is None
    assert _reparar_json_truncado('{"clave truncada a mitad": "v", "otr') is None


def test_no_dict_devuelve_none():
    # Una lista suelta reparada no sirve como interpretacion.
    assert _reparar_json_truncado('["a", "b"') is None


def test_json_valido_no_pasa_por_la_reparacion():
    r = parsear_respuesta_llm('{"intencion": "consulta", "confianza": 1.0}')
    assert r == {"intencion": "consulta", "confianza": 1.0}


# ── DESTINO DE MEMORIA NO ES FANTASMA (cierre del pendiente 18-jul) ──────────

def test_destino_de_memoria_sobrevive_la_confirmacion():
    """'dale, confirmalo' no nombra destinos, pero Palpala esta en la memoria
    de la charla: el guardia NO lo anula (el envio se caia del total al
    confirmar, visto 20-jul en el guion 48)."""
    from app.core.interpretador import coercionar_destinos
    from app.core.estado_venta import set_current_estado
    set_current_estado({"localidades_envio": ["palpala jujuy"]})
    r = {"pedido": [{"producto": "notebook", "cantidad": 1,
                     "destino": "Palpalá, Jujuy"}]}
    coercionar_destinos(r, "dale, confirmalo")
    set_current_estado(None)
    assert r["pedido"][0]["destino"] == "Palpalá, Jujuy"


def test_destino_inventado_sigue_cayendo():
    """Sin memoria ni mencion en el mensaje, el fantasma se anula igual."""
    from app.core.interpretador import coercionar_destinos
    from app.core.estado_venta import set_current_estado
    set_current_estado({})
    r = {"pedido": [{"producto": "mouse", "cantidad": 1,
                     "destino": "Rosario"}]}
    coercionar_destinos(r, "quiero un mouse barato")
    set_current_estado(None)
    assert r["pedido"][0]["destino"] is None


# ── LAS DOS ETAPAS: recuperar candidatos y despues desambiguar ──────────────
# El enum de producto no puede llevar los 482 modelos del catalogo: son 11.000
# caracteres por campo y el limite documentado de structured outputs es 15.000
# en TODO el schema. Se recupera una lista corta y el modelo elige de ahi.

def test_candidatos_recupera_el_modelo_aunque_falte_una_palabra():
    from app.core.interpretador import candidatos_modelo
    modelos = ["Asus TUF Gaming F15 Ryzen 7 16GB 512GB SSD", "Asus TUF VG249Q1A",
               "Lenovo IdeaPad 3 Core i5 16GB 512GB SSD", "JBL Flip 6"]
    # el cliente dice "asus tuf f15" y el catalogo dice "TUF Gaming F15"
    c = candidatos_modelo("la asus tuf f15 tiene thunderbolt", modelos)
    assert "Asus TUF Gaming F15 Ryzen 7 16GB 512GB SSD" in c
    # y no arrastra medio catalogo
    assert "JBL Flip 6" not in c


def test_candidatos_tolera_el_typo():
    from app.core.interpretador import candidatos_modelo
    modelos = ["Asus Zenbook 14 OLED Core i7 16GB 1TB SSD", "JBL Flip 6"]
    assert candidatos_modelo("la zenbok 14 cuanto sale", modelos) == [
        "Asus Zenbook 14 OLED Core i7 16GB 1TB SSD"]


def test_el_schema_con_candidatos_entra_holgado():
    from app.core.interpretador import candidatos_modelo
    import json
    modelos = [f"Marca{i} Modelo Largo De Ejemplo {i}" for i in range(482)]
    cortos = candidatos_modelo("quiero el Modelo Largo 7", modelos)
    s = json.dumps(_schema_interprete([], ["mouse"], cortos, ["ram", "hz"]))
    assert len(s) < 15000, "el schema no puede pasar el limite de enums"


def test_fuera_de_lista_dispara_la_segunda_vuelta(monkeypatch):
    """Si el modelo declara que no estaba en la lista, el codigo busca en el
    catalogo COMPLETO antes de dar por no disponible el producto."""
    from app.core import interpretador as it
    catalogo = [{"id": "N1", "nombre": "Notebook Acer Nitro 5 Core i5",
                 "marca": "Acer", "modelo": "Nitro 5", "categoria": "notebook"}]
    monkeypatch.setattr("app.storage.firestore_client.get_all_products",
                        lambda tienda_id=None: catalogo)
    r = {"producto_resuelto": FUERA_DE_LISTA, "productos_consultados": []}
    it._resolver_fuera_de_lista(r, "tenes la acer nitro 5?", "t1")
    assert r["producto_resuelto"] == "Notebook Acer Nitro 5 Core i5"
    # y si de verdad no existe, queda en None: honesto por dato, no por error
    r2 = {"producto_resuelto": FUERA_DE_LISTA, "productos_consultados": []}
    it._resolver_fuera_de_lista(r2, "tenes la macbook pro?", "t1")
    assert r2["producto_resuelto"] is None
