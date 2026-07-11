"""
AREA: Edicion de pedido por rechazo + asignacion parcial de destino (11-jul).

Fallas reales del banco: "el auricular no, sacalo" re-ofrecia las mismas
opciones (guion 28); "una parte va a Rafaela, un teclado y un mouse van ahi"
pisaba el pedido de 3+2 con uno de 1+1 (guion 29); "los auriculares dejalos"
insistia con las mismas opciones (guion 09).
"""
from app.core.estado_venta import (es_rechazo, rechazados_del_carrito,
                                   es_asignacion_destino,
                                   cantidades_vigentes_por_categoria)
from app.core.compositor import componer

_CATALOGO = [
    {"id": "MOU0009", "nombre": "Mouse Logitech M170 Negro",
     "categoria": "mouse", "precio_ars": 12000},
    {"id": "AUR0001", "nombre": "Auriculares HyperX Cloud II Negro",
     "categoria": "auriculares", "precio_ars": 125500},
    {"id": "TEC0001", "nombre": "Teclado Genius KB-110X Blanco",
     "categoria": "teclado", "precio_ars": 12000},
]

_CARRITO = [
    {"id": "MOU0009", "nombre": "Mouse Logitech M170 Negro", "cantidad": 1},
    {"id": "AUR0001", "nombre": "Auriculares HyperX Cloud II Negro",
     "cantidad": 1},
]


def test_es_rechazo():
    assert es_rechazo("pensandolo mejor el auricular no, sacalo")
    assert es_rechazo("los auriculares dejalos, no me convencen")
    assert not es_rechazo("dejalo anotado que sigo mirando")
    assert not es_rechazo("quiero el mouse")


def test_sacalo_quita_el_item_nombrado():
    quitados, restantes = rechazados_del_carrito(
        _CARRITO, "pensandolo mejor el auricular no, sacalo", _CATALOGO)
    assert [q["id"] for q in quitados] == ["AUR0001"]
    assert [r["id"] for r in restantes] == ["MOU0009"]


def test_rechazo_por_categoria_plural():
    quitados, restantes = rechazados_del_carrito(
        _CARRITO, "los auriculares dejalos, no me convencen", _CATALOGO)
    assert [q["id"] for q in quitados] == ["AUR0001"]


def test_sin_rechazo_carrito_intacto():
    quitados, restantes = rechazados_del_carrito(
        _CARRITO, "cuanto sale todo?", _CATALOGO)
    assert quitados == []
    assert len(restantes) == 2


def test_rechazo_que_no_matchea_no_quita():
    quitados, restantes = rechazados_del_carrito(
        _CARRITO, "la webcam no la quiero", _CATALOGO)
    assert quitados == []


def test_asignacion_destino_detecta():
    assert es_asignacion_destino(
        "no espera, una parte va a Rafaela, un teclado y un mouse van ahi")
    assert es_asignacion_destino("el resto a San Francisco")
    assert not es_asignacion_destino("quiero 2 teclados y 3 mouse")


def test_cantidades_vigentes_desde_carrito():
    carrito = [
        {"id": "TEC0001", "nombre": "Teclado Genius KB-110X Blanco",
         "cantidad": 3},
        {"id": "MOU0009", "nombre": "Mouse Logitech M170 Negro",
         "cantidad": 2},
    ]
    vig = cantidades_vigentes_por_categoria(carrito, [], _CATALOGO)
    assert vig == {"teclado": 3, "mouse": 2}


def test_cantidades_vigentes_desde_pendiente():
    pend = [{"cantidad": 2, "categoria": "teclado"},
            {"cantidad": 3, "categoria": "mouse"}]
    vig = cantidades_vigentes_por_categoria([], pend, _CATALOGO)
    assert vig == {"teclado": 2, "mouse": 3}


def test_compositor_reconoce_rechazo_sin_insistir(firestore_doble):
    # Guion 09 turno 11: con candidatos de auriculares y mensaje de rechazo,
    # NO se re-ofrecen las mismas opciones.
    interp = {"intencion": "otra", "producto_resuelto": None,
              "candidatos": ["Auriculares Redragon Zeus X Negro",
                             "Auriculares Redragon Zeus X Blanco"],
              "confianza": 0.6}
    texto, _ = componer("los auriculares dejalos, no me convencen",
                        interp, {}, "verifika_prod")
    assert "lo dejamos de lado" in texto
    assert "Zeus X" not in texto
    assert "no quiero errarle" not in texto
