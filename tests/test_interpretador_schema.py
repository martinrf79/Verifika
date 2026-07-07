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
