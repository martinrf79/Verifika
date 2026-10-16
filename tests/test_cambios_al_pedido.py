"""LO QUE EL CLIENTE CAMBIA DEL PEDIDO LO APLICA EL CODIGO — 16-oct-2026.

K11 con Gemini pago: "uy no, mejor 2, y mandalos a Rosario". El interprete
devolvio TEC0020 por 2 a Rosario y el codigo armo la cuenta con los 3 del
pedido guardado. La regla: sobre el pedido se aplica solo lo que se puede
certificar, cantidad y destino de lo que ya esta; un producto que no esta en
el pedido no entra por aca, porque el interprete a veces repite el pedido con
otro producto (K21, 9-oct).
"""
from app.core import tablero as T

T_ = "verifika_prod"
UNO = [{"destino": "", "items": [{"producto": "TEC0020", "cantidad": 3}]}]
TRES = [{"destino": "Córdoba capital", "items": [{"producto": "AUR0019", "cantidad": 1},
                                                 {"producto": "MOU0023", "cantidad": 1}]},
        {"destino": "Concordia", "items": [{"producto": "TEC0020", "cantidad": 1},
                                           {"producto": "MOU0023", "cantidad": 1}]},
        {"destino": "Posadas", "items": [{"producto": "AUR0019", "cantidad": 1},
                                         {"producto": "RAM0001", "cantidad": 2}]}]


def test_mejor_2_y_a_rosario(firestore_doble):
    out = T._cambios_al_pedido(UNO, [{"producto": "TEC0020", "cantidad": 2, "destino": "Rosario"}], T_)
    assert out == [{"destino": "Rosario", "items": [{"producto": "TEC0020", "cantidad": 2}]}]
    assert UNO[0]["items"][0]["cantidad"] == 3, "el pedido guardado no se toca"


def test_por_nombre_que_da_uno_solo_del_pedido(firestore_doble):
    out = T._cambios_al_pedido(TRES, [{"producto": "memoria kingston fury", "cantidad": 3}], T_)
    assert out[2]["items"][1] == {"producto": "RAM0001", "cantidad": 3}


def test_un_producto_que_no_esta_en_el_pedido_no_entra(firestore_doble):
    """K21, ds_mem_base_2: el interprete repitio el pedido con MOU0009 y AUR0045."""
    items = [{"producto": "MOU0009", "cantidad": 1, "destino": "Concordia"},
             {"producto": "AUR0045", "cantidad": 1, "destino": "Posadas"},
             {"producto": "RAM0001", "cantidad": 2, "destino": "Posadas"}]
    assert T._cambios_al_pedido(TRES, items, T_) == TRES


def test_lo_que_esta_en_dos_destinos_no_se_adivina(firestore_doble):
    out = T._cambios_al_pedido(TRES, [{"producto": "MOU0023", "cantidad": 5}], T_)
    assert out == TRES


def test_un_articulo_cambia_de_destino_y_el_resto_queda(firestore_doble):
    out = T._cambios_al_pedido(TRES, [{"producto": "TEC0020", "cantidad": 1, "destino": "Rosario"}], T_)
    assert [b["destino"] for b in out] == ["Córdoba capital", "Concordia", "Posadas", "Rosario"]
    assert out[1]["items"] == [{"producto": "MOU0023", "cantidad": 1}]
    assert out[3]["items"] == [{"producto": "TEC0020", "cantidad": 1}]


def test_la_pieza_sobre_el_pedido_lleva_el_cambio_a_la_cuenta(firestore_doble):
    memoria = "EN EL PEDIDO, tal como se conto: 3x TEC0020 Teclado Genius KB-110X Blanco\n"
    piezas = [{"n": 1, "tipo": "cuenta", "sobre_el_pedido": True,
               "items": [{"producto": "TEC0020", "cantidad": 2, "destino": "Rosario"}]}]
    out = T._sobre_el_pedido(piezas, memoria, T_)
    assert [p["items"] for p in out] == [[{"producto": "TEC0020", "cantidad": 2, "destino": "Rosario"}]]
    assert out[0]["destinos"] == ["Rosario"]


def test_el_resto_conserva_su_nombre_al_normalizar_de_nuevo():
    from app.core.agente import CLIENTE_DIJO
    CLIENTE_DIJO.set("70 por ciento transferencia")
    rep = T._reparto(T._reparto([{"medio": "transferencia", "porcentaje": 70}]))
    assert [r["medio"] for r in rep] == ["transferencia", "el resto"]


def test_siete_casos_corridos():
    """Cuantos, no solo que pasaron."""
    nombres = [n for n in globals() if n.startswith("test_") and n != "test_siete_casos_corridos"]
    assert len(nombres) == 7
