"""EL BORRADOR — lo dicho entra, lo resuelto sale, sin modelo y con el catalogo real (FICHA 71, paso 1).

Cada test es una clase de las 58 o de las charlas reales, no un caso: la confirmacion de un renglon fuera de la lista,
"lo demas como te dije", "son 7", dos del mismo rubro a dos destinos, el cambio de lo que es un renglon, el pago
partido y la etapa del cierre.
"""
import pytest

from app.core.flujo import borrador as B

TIENDA = "verifika_prod"
SIETE = [{"producto": "auriculares", "cantidad": 1, "destino": "Córdoba capital"},
         {"producto": "mouse", "cantidad": 1, "destino": "Córdoba capital"},
         {"producto": "teclado", "cantidad": 1, "destino": "Concordia"},
         {"producto": "mouse", "cantidad": 1, "destino": "Concordia"},
         {"producto": "los otros", "cantidad": 2, "destino": "Posadas"}]
LISTA = {"auriculares": 2, "mouse": 2, "memoria ram": 2}


@pytest.fixture(autouse=True)
def _catalogo(firestore_doble):
    yield


def _turno(b):
    res = B.resolver(b, TIENDA)
    falta = B.faltantes(b, res)
    return res, falta, B.articulos(res, falta), B.preguntas(b, falta)


def _real_t1():
    b = B.leer({})
    B.aplicar(b, {"agrega": SIETE}, pedidas=LISTA)
    return b


def test_un_rubro_fuera_de_la_lista_se_confirma_y_los_otros_esperan():
    _, falta, arts, qs = _turno(_real_t1())
    assert {x["falta"] for x in falta} == {"confirmar", "otros"}
    assert arts == []
    # Una sola pregunta: "los otros" depende de la respuesta sobre el teclado.
    assert len(qs) == 1 and qs[0].startswith("Pediste teclado para Concordia"), qs


def test_lo_demas_como_te_dije_confirma_sin_duplicar():
    b = _real_t1()
    B.aplicar(b, {"agrega": SIETE, "responde": "R-1"})
    assert [r["L"] for r in b["renglones"]] == ["L-1", "L-2", "L-3", "L-4", "L-5"]
    _, falta, arts, qs = _turno(b)
    assert [x["falta"] for x in falta] == ["otros"] and arts == []
    assert len(qs) == 1 and "Pediste" not in qs[0] and "1 auriculares, 2 memoria ram" in qs[0], qs


def test_son_siete_recuenta_los_otros_y_cierra_el_pedido():
    b = _real_t1()
    B.aplicar(b, {"total": 7})
    res, falta, arts, qs = _turno(b)
    assert falta == [] and qs == []
    assert sum(a["cantidad"] for a in arts) == 7
    assert {a["destino"] for a in arts} == {"Córdoba capital", "Concordia", "Posadas"}
    assert sum(a["cantidad"] for a in arts if a["destino"] == "Posadas") == 3
    assert B.etapa(b, falta, arts) == "falta_nombre"


def test_dos_del_mismo_rubro_a_dos_destinos_son_el_mismo_modelo():
    b = B.leer({})
    B.anotar_busqueda(b, "auriculares", [], "mas barato")
    B.aplicar(b, {"agrega": [{"producto": "auriculares", "cantidad": 1, "destino": "Rosario"},
                             {"producto": "auriculares", "cantidad": 1, "destino": "Salta"}]})
    _, falta, arts, _ = _turno(b)
    assert falta == [] and len(arts) == 2 and len({a["id"] for a in arts}) == 1


def test_el_criterio_nuevo_re_resuelve_todos_los_renglones_del_rubro():
    b = B.leer({})
    B.anotar_busqueda(b, "mouse", [], "mas caro")
    B.aplicar(b, {"agrega": [{"producto": "mouse", "destino": "Rosario"}, {"producto": "mouse", "destino": "Salta"}]})
    caro = _turno(b)[2]
    B.anotar_busqueda(b, "mouse", [], "mas barato")
    barato = _turno(b)[2]
    assert len({a["id"] for a in caro}) == 1 and len({a["id"] for a in barato}) == 1
    assert barato[0]["precio"] < caro[0]["precio"]


def test_cambiar_lo_que_es_un_renglon_lo_resuelve_de_nuevo():
    b = _real_t1()
    B.aplicar(b, {"cambia": [{"es": "L-3", "producto": "memoria ram"}]})
    _, falta, arts, _ = _turno(b)
    assert falta == [], falta
    assert sum(a["cantidad"] for a in arts) == 6


def test_sacar_un_renglon_no_renumera_los_demas():
    b = _real_t1()
    B.aplicar(b, {"saca": ["L-2"]})
    B.aplicar(b, {"agrega": [{"producto": "G203", "cantidad": 1, "destino": "Rosario"}]})
    assert [r["L"] for r in b["renglones"]] == ["L-1", "L-3", "L-4", "L-5", "L-6"]


def test_el_pago_partido_pide_el_medio_y_que_sume_cien():
    casos = [([{"medio": "sin decir", "porcentaje": 70}, {"medio": "sin decir", "porcentaje": 30}], "medio"),
             ([{"medio": "transferencia", "porcentaje": 70}, {"medio": "efectivo", "porcentaje": 20}], "pago"),
             ([{"medio": "transferencia", "porcentaje": 70}, {"medio": "Mercado Pago", "porcentaje": 30}], None)]
    for reparto, tipo in casos:
        b = B.leer({})
        B.aplicar(b, {"agrega": [{"producto": "G203", "cantidad": 1, "color": "negro"}], "reparto": reparto})
        _, falta, arts, qs = _turno(b)
        assert [x["falta"] for x in falta] == ([tipo] if tipo else []), (reparto, falta)
        assert bool(arts) == (tipo is None)
    print(f"\nPAGO: {len(casos)} casos")


def test_con_varios_destinos_cada_renglon_lleva_el_suyo():
    b = B.leer({})
    B.aplicar(b, {"agrega": [{"producto": "G203", "cantidad": 1, "color": "negro", "destino": "Rosario"},
                             {"producto": "K120", "cantidad": 1, "color": "negro"}]})
    _, falta, arts, qs = _turno(b)
    assert [(x["L"], x["falta"]) for x in falta] == [("L-2", "destino")] and arts == []
    assert qs == ["¿A dónde va K120?"]


def test_identidad_ambigua_o_sin_color_queda_en_su_renglon():
    b = B.leer({})
    B.aplicar(b, {"agrega": [{"producto": "Logitech", "cantidad": 1}, {"producto": "G305", "cantidad": 1}]})
    res, falta, arts, qs = _turno(b)
    tipos = {x["L"]: x["falta"] for x in falta}
    assert tipos.get("L-2") == "color", falta
    assert arts == [] and any("color" in q for q in qs)


def test_la_etapa_se_deriva_y_el_cierre_no_se_repite():
    b = B.leer({})
    assert B.etapa(b, [], []) == "vacio"
    B.aplicar(b, {"agrega": [{"producto": "G203", "cantidad": 1, "color": "negro"}]})
    _, falta, arts, _ = _turno(b)
    assert B.etapa(b, falta, arts) == "falta_nombre"
    b["cliente"]["nombre"] = "Julio"
    assert B.etapa(b, falta, arts) == "completo"
    b["cierre"]["huella"] = B.huella(arts)
    assert B.etapa(b, falta, arts) == "cerrado"
    B.aplicar(b, {"cambia": [{"es": "L-1", "cantidad": 2}]})
    _, falta, arts, _ = _turno(b)
    assert B.etapa(b, falta, arts) == "completo"


def test_lo_guardado_vuelve_igual():
    b = _real_t1()
    otra = B.leer(dict(b))
    assert otra == b
    assert B.leer(None) == B.leer({}) and B.leer({})["renglones"] == []


def test_la_libreta_muestra_cada_renglon_con_lo_que_le_falta():
    b = _real_t1()
    res = B.resolver(b, TIENDA)
    lineas = B.libreta(b, res, B.faltantes(b, res))
    assert lineas[0] == "- BORRADOR:" and len([x for x in lineas if x.startswith("  L-")]) == 5
    assert any("L-3" in x and "FALTA confirmar" in x for x in lineas), lineas


def test_la_cantidad_se_controla_contra_el_stock_sumando_los_destinos():
    b = B.leer({})
    B.aplicar(b, {"agrega": [{"producto": "G203", "cantidad": 500, "color": "negro", "destino": "Rosario"},
                             {"producto": "G203", "cantidad": 1, "color": "negro", "destino": "Salta"}]})
    _, falta, arts, qs = _turno(b)
    assert [x["falta"] for x in falta] == ["cantidad_stock"] and arts == []
    assert "pediste 501" in qs[0], qs


def test_el_color_de_un_renglon_de_rubro_entra_en_su_busqueda():
    b = B.leer({})
    B.aplicar(b, {"agrega": [{"producto": "mouse", "color": "blanco", "destino": "Rosario"}]})
    _, falta, arts, _ = _turno(b)
    assert falta == [] and "blanco" in arts[0]["nombre"].lower(), arts
    B.aplicar(b, {"cambia": [{"es": "L-1", "color": "fucsia"}]})
    _, falta, arts, qs = _turno(b)
    assert [x["falta"] for x in falta] == ["stock"] and "fucsia" in qs[0], qs


def test_un_pedido_que_cambia_despues_del_cierre_actualiza_el_mismo_lead(monkeypatch):
    import asyncio
    from app.core import leads
    from app.core.flujo import cierre
    creados, actualizados = [], []
    monkeypatch.setattr(leads, "crear_lead", lambda *a, **k: creados.append(1) or f"lead-{len(creados)}")
    monkeypatch.setattr(leads, "actualizar_lead", lambda lid, *a, **k: actualizados.append(lid))

    async def _avisar(**k):
        return None
    monkeypatch.setattr(leads, "notificar_lead", _avisar)
    monkeypatch.setattr(leads, "modo_cierre", lambda t: "pedido")
    b = B.leer({})
    b["cliente"]["nombre"] = "Julio"
    estado = {"borrador": b}
    textos = []
    for cantidad in (1, 1, 2):
        B.aplicar(b, {"agrega": [{"producto": "G203", "cantidad": 1, "color": "negro"}]} if not b["renglones"]
                  else {"cambia": [{"es": "L-1", "cantidad": cantidad}]})
        res = B.resolver(b, TIENDA)
        estado["pedido"] = B.articulos(res, B.faltantes(b, res))
        textos.append(asyncio.run(cierre.cerrar(estado, "549", "whatsapp", TIENDA, "Presupuesto: x", "t")))
    # Cierra, no repite lo cerrado, y con la cantidad cambiada actualiza el mismo lead.
    assert bool(textos[0]) and textos[1] == "" and bool(textos[2]), textos
    assert creados == [1] and actualizados == ["lead-1", "lead-1"]
