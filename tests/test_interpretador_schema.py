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
