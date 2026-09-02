"""
EL ANCLA DEL PRODUCTO ELEGIDO — "el que te dije al principio".

Es la referencia que la prioridad 3 nombra con todas las letras: el cliente
elige algo, pasan turnos, y despues lo referencia sin nombrarlo. Tiene que
resolver.

POR QUE ESTE ARCHIVO SE REESCRIBIO ENTERO (12-ago). La version anterior probaba
`aplicar_ancla_producto` y `producto_anotado_actualizado`, que recibian el
`interp` del INTERPRETE, la etapa que el hub reemplazo el 1-ago. Desde entonces
no las llamaba nadie en el camino vivo y el campo `producto_anotado` no lo
escribia nadie: el ancla NUNCA existio en produccion, con estos tests en verde.
Es exactamente lo que advierte CLAUDE.md — un test que no corre sobre el codigo
de produccion no vale— y por eso ahora se prueba `ancla_al_dia`, que es la que
llama el hub, y ademas hay un candado que compara los campos que el estado LEE
contra los que el hub GUARDA (`tests/test_hub_venta.py`).
"""
from app.core.estado_venta import ancla_al_dia, construir_estado

_M170 = {"id": "MOU0009", "nombre": "Mouse Logitech M170 Negro", "precio": 12000}
_DX110 = {"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro", "precio": 8500}


def test_el_cliente_elige_y_queda_anclado():
    a = ancla_al_dia({}, "me quedo con ese, anotalo", [_M170])
    assert a["id"] == "MOU0009"
    assert a["precio"] == 12000


def test_con_dos_candidatos_no_adivina_cual():
    """Un ancla que se pone sola sobre el producto equivocado es peor que no
    tener ancla: el cliente pide 'el que te dije' y le llega otro."""
    assert ancla_al_dia({}, "me gusta", [_M170, _DX110]) == {}
    assert ancla_al_dia(dict(_M170), "me gusta", [_M170, _DX110]) == _M170


def test_un_turno_que_habla_de_otra_cosa_no_mueve_el_ancla():
    for m in ("y como es el tema de la garantia?",
              "hacen envios a cordoba?",
              "cuanto sale el DX-110?"):
        assert ancla_al_dia(dict(_M170), m, [_DX110]) == _M170


def test_sacar_el_anotado_lo_limpia_y_solo_a_ese():
    assert ancla_al_dia(dict(_M170), "el mouse sacalo", []) == {}
    # Rechazar OTRO producto no toca el ancla.
    assert ancla_al_dia(dict(_M170), "los auriculares sacalos", []) == _M170


def test_el_ancla_persistida_vuelve_por_el_estado():
    """La otra mitad: lo guardado tiene que volver a leerse en el turno
    siguiente. Sin esto el ancla se escribe y se pierde."""
    estado = construir_estado({"producto_anotado": dict(_M170)}, None)
    assert estado["producto_anotado"]["nombre"] == "Mouse Logitech M170 Negro"


def test_el_ancla_llega_al_prompt():
    """Y la tercera mitad, que es la que faltaba de verdad: si el ancla no
    entra en la memoria que ve el modelo, guardarla no sirve de nada."""
    from app.core.hub_venta import _memoria_texto
    texto = _memoria_texto({"producto_anotado": dict(_M170)}, [])
    assert "Mouse Logitech M170 Negro" in texto
    assert "MOU0009" in texto
    assert "el que te dije al principio" in texto.lower()
