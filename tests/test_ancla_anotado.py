"""
AREA: Ancla de producto anotado (11-jul, falla madre del banco de charlas).

El cliente elige un producto y pide guardarlo; muchos turnos despues cierra
con "el que te mencione al principio". Cubre las tres piezas de
estado_venta: aplicar_ancla_producto (mutacion del turno),
producto_anotado_actualizado (persistencia) y el paso por construir_estado.
Logica pura, sin LLM.
"""
from app.core.estado_venta import (aplicar_ancla_producto,
                                   producto_anotado_actualizado,
                                   construir_estado)

_CATALOGO = [
    {"id": "MOU0009", "nombre": "Mouse Logitech M170 Negro", "precio_ars": 12000},
    {"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro", "precio_ars": 8500},
    {"id": "AUR0001", "nombre": "Auriculares HyperX Cloud II Negro",
     "precio_ars": 125500},
]

_ANCLA_M170 = {"id": "MOU0009", "nombre": "Mouse Logitech M170 Negro",
               "precio": 12000}


def test_anotar_con_candidato_unico_resuelve_producto():
    # Caso real del banco (guion 28 turno 2): "me interesa, anotalo" con UN
    # candidato dejaba producto_resuelto vacio y el turno caia al fallback.
    interp = {"intencion": "exploracion", "producto_resuelto": None,
              "candidatos": ["Logitech M170 negro"], "confianza": 0.6}
    ev = aplicar_ancla_producto(
        interp, "el mouse Logitech M170 negro me interesa, anotalo", {},
        _CATALOGO)
    assert ev == "anotado"
    assert interp["producto_resuelto"] == "Mouse Logitech M170 Negro"


def test_anotar_ambiguo_no_adivina():
    interp = {"producto_resuelto": None,
              "candidatos": ["M170", "DX-110"], "confianza": 0.6}
    ev = aplicar_ancla_producto(interp, "me gusta, anotalo", {}, _CATALOGO)
    assert ev == ""
    assert not interp["producto_resuelto"]


def test_referencia_al_anotado_resuelve_y_arma_pedido():
    # Caso real (guion 28 turno 10): "cerrame la compra con el mouse que te
    # mencione al principio" listaba todos los mouse de nuevo.
    interp = {"intencion": "decision_compra", "producto_resuelto": None,
              "candidatos": [], "confianza": 0.5, "pedido": []}
    estado = {"producto_anotado": dict(_ANCLA_M170)}
    ev = aplicar_ancla_producto(
        interp, "cerrame la compra con el mouse que te mencione al "
        "principio, pasame el total final con envio", estado, _CATALOGO)
    assert ev == "referencia"
    assert interp["producto_resuelto"] == "Mouse Logitech M170 Negro"
    assert interp["pedido"] == [{"producto": "Mouse Logitech M170 Negro",
                                 "cantidad": 1, "destino": None}]
    assert interp["confianza"] >= 0.7


def test_referencia_sin_cierre_solo_resuelve():
    interp = {"producto_resuelto": None, "candidatos": [], "pedido": []}
    estado = {"producto_anotado": dict(_ANCLA_M170)}
    ev = aplicar_ancla_producto(
        interp, "che, y el que te dije antes tiene garantia?", estado,
        _CATALOGO)
    assert ev == "referencia"
    assert interp["producto_resuelto"] == "Mouse Logitech M170 Negro"
    assert not interp.get("pedido")


def test_referencia_no_pisa_lo_que_el_interprete_resolvio():
    interp = {"producto_resuelto": "Mouse Genius DX-110 Negro",
              "candidatos": [], "pedido": []}
    estado = {"producto_anotado": dict(_ANCLA_M170)}
    ev = aplicar_ancla_producto(
        interp, "dale, cerremos con el que te dije", estado, _CATALOGO)
    assert ev == ""
    assert interp["producto_resuelto"] == "Mouse Genius DX-110 Negro"


def test_persistencia_ancla_nueva_por_eleccion():
    interp = {"intencion": "aporta_dato",
              "producto_resuelto": "Mouse Logitech M170 Negro"}
    a = producto_anotado_actualizado({}, interp, "me quedo con el M170",
                                     _CATALOGO)
    assert a == _ANCLA_M170


def test_pregunta_sobre_otro_producto_no_pisa_el_ancla():
    interp = {"intencion": "pregunta_especifica",
              "producto_resuelto": "Mouse Genius DX-110 Negro"}
    a = producto_anotado_actualizado(dict(_ANCLA_M170), interp,
                                     "cuanto sale el DX-110?", _CATALOGO)
    assert a == _ANCLA_M170


def test_negacion_que_nombra_al_ancla_la_limpia():
    interp = {"intencion": "otra", "producto_resuelto": None}
    a = producto_anotado_actualizado(dict(_ANCLA_M170), interp,
                                     "el m170 no lo quiero, sacalo", _CATALOGO)
    assert a == {}


def test_negacion_de_otro_producto_no_limpia_el_ancla():
    # Caso real (guion 09 turno 11): "los auriculares dejalos" no debe tocar
    # el mouse anotado.
    interp = {"intencion": "otra", "producto_resuelto": None}
    a = producto_anotado_actualizado(dict(_ANCLA_M170), interp,
                                     "los auriculares dejalos, no me "
                                     "convencen", _CATALOGO)
    assert a == _ANCLA_M170


def test_intencion_otra_no_ancla():
    interp = {"intencion": "otra",
              "producto_resuelto": "Mouse Genius DX-110 Negro"}
    a = producto_anotado_actualizado(dict(_ANCLA_M170), interp,
                                     "jaja no, me gusta joder nomas", _CATALOGO)
    assert a == _ANCLA_M170


def test_construir_estado_pasa_el_ancla():
    conv = {"producto_anotado": dict(_ANCLA_M170)}
    estado = construir_estado(conv, None)
    assert estado["producto_anotado"] == _ANCLA_M170
    assert construir_estado({}, None)["producto_anotado"] == {}
