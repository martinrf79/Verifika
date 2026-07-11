"""
AREA: Schema del interprete para constrained generation dura (Structured Outputs).

Cubre _schema_interprete (app/core/interpretador.py): el schema estricto que ata
intencion y estado a su enum y producto_resuelto al enum de los productos
mostrados (o null). Logica pura, sin LLM.
"""
from app.core.interpretador import (_schema_interprete, INTENCIONES_VALIDAS,
                                     ESTADOS_VALIDOS)


def test_producto_resuelto_atado_a_mostrados():
    s = _schema_interprete(["Mouse A", "Mouse B"])
    pr = s["properties"]["producto_resuelto"]
    assert pr["enum"] == [None, "Mouse A", "Mouse B"]
    assert "null" in pr["type"]


def test_intencion_y_estado_son_enum():
    s = _schema_interprete([])
    assert s["properties"]["intencion"]["enum"] == sorted(INTENCIONES_VALIDAS)
    assert s["properties"]["estado_conversacion"]["enum"] == ESTADOS_VALIDOS


def test_sin_productos_solo_null():
    s = _schema_interprete([])
    assert s["properties"]["producto_resuelto"]["enum"] == [None]


def test_dedup_nombres_conserva_orden():
    s = _schema_interprete(["X", "X", "Y", ""])
    assert s["properties"]["producto_resuelto"]["enum"] == [None, "X", "Y"]


def test_strict_todos_los_campos_requeridos():
    # OpenAI strict: additionalProperties false y todo campo en required.
    s = _schema_interprete(["A"])
    assert s["additionalProperties"] is False
    assert set(s["required"]) == set(s["properties"])


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
