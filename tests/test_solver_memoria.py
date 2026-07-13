"""
AREA: Bloque de MEMORIA del solver Gemini (13-jul).

El solver recibe la historia corta (últimos turnos) y no veía ni el resumen de
memoria larga ni el estado sellado: a diez turnos re-preguntaba el destino ya
dado o perdía el producto anotado. El bloque _bloque_memoria le inyecta al
prompt lo ya establecido (resumen, ancla, pedido vigente, destino, criterio,
datos del cliente) como CONTEXTO, con la orden explícita de que los números
salen de las tools.
"""
from app.core.solver_gemini import _bloque_memoria


def test_estado_vacio_no_genera_bloque():
    assert _bloque_memoria({}) == ""
    assert _bloque_memoria(None) == ""
    assert _bloque_memoria({"carrito": [], "resumen_charla": ""}) == ""


def test_bloque_completo_lleva_todo_lo_establecido():
    estado = {
        "resumen_charla": "El cliente busca mouse de oficina y dio su nombre.",
        "producto_anotado": {"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro"},
        "carrito": [{"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro",
                     "cantidad": 2}],
        "localidades_envio": ["Rosario"],
        "localidad_envio": "Rosario",
        "provincia_envio": "Santa Fe",
        "criterio": "mas_barato",
        "datos_cliente": {"nombre": "Marta"},
    }
    b = _bloque_memoria(estado)
    assert "MEMORIA DE LA CHARLA" in b
    assert "mouse de oficina" in b
    assert "Mouse Genius DX-110 Negro (id MOU0023)" in b
    assert "2x Mouse Genius DX-110 Negro" in b
    assert "Rosario" in b and "Santa Fe" in b
    assert "mas_barato" in b
    assert "Marta" in b
    # La orden de que el dato duro sigue saliendo de las tools viaja siempre.
    assert "sale de las tools" in b
    assert "calculate_total" in b and "cotizar_envio" in b


def test_localidad_suelta_sin_duplicar():
    b = _bloque_memoria({"localidades_envio": ["Rosario"],
                         "localidad_envio": "Rosario"})
    assert b.count("Rosario") == 1
    b2 = _bloque_memoria({"localidades_envio": ["Rosario"],
                          "localidad_envio": "Córdoba"})
    assert "Rosario" in b2 and "Córdoba" in b2


def test_carrito_sin_nombre_no_rompe():
    b = _bloque_memoria({"carrito": [{"id": "X"}, "basura", None]})
    assert b == ""
