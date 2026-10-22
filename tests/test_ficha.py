"""LA FICHA NATIVA Y SU PASO A LA AGENDA — sin modelo (22-oct-2026, FICHA 76).

  1. la bateria: las 48 fichas que devolvio el modelo en `pedido_documento/ficha_vivo.jsonl`, por el adaptador y el
     ejecutor de verdad, calificadas por el pedido que queda con la vara de `medir_ficha`. El techo solo baja.
  2. cada regla del adaptador, por su clase: lo que define, no un caso.
  3. lo que queda a medias, como xfail estricto.
"""
import asyncio
import json
import os
import sys

import pytest

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
DOC = os.path.join(REPO, "banco_pruebas", "pedido_documento")
TECHO = os.path.join(AQUI, "ficha_techo.json")
TIENDA = "verifika_prod"


@pytest.fixture(scope="module")
def M():
    cwd = os.getcwd()
    sys.path.insert(0, DOC)
    import medir_pedido
    os.chdir(cwd)
    return medir_pedido


@pytest.fixture(scope="module")
def F(M):
    from app.core.flujo import ficha
    return ficha


def _estado(renglones=(), mostrados=(), criterios=None, **b):
    from app.core.flujo import borrador as B
    from app.core.flujo import catalogo as K
    bo = B.leer({})
    for i, (que, cant, dest) in enumerate(renglones, 1):
        bo["renglones"].append({"L": f"L-{i}", "que": que, "cantidad": cant, "color": "", "destino": dest,
                                "condicion": "", "cita": "", "confirmado": True})
    bo["criterios"].update(criterios or {})
    bo.update(b)
    bo["siguiente"] = len(bo["renglones"]) + 1
    ms = [{"id": pid, "nombre": K.por_id(pid, TIENDA)["nombre"], "precio": 0} for pid in mostrados]
    return {"mostrados": ms, "pedido": [], "busqueda": {}, "abiertas": [], "borrador": bo}


def _ficha(pedido=(), consultas=(), pago=None, **k):
    return {"pedido": list(pedido), "preferencias": {"condiciones": [], "orden": "nada"},
            "pago": pago or {"medios": [{"medio": "sin decir", "porcentaje": 100}], "tope_total": None},
            "consultas": list(consultas), "cliente": {"nombre": "sin decir", "localidad": "sin decir"}, "dudas": [], **k}


def _item(producto, rubro="ninguno", cantidad=1, renglon="nuevo", **k):
    return {"producto": producto, "rubro": rubro, "cantidad": cantidad, "color": "sin decir", "condiciones": [],
            "orden": "nada", "renglon": renglon, **k}


def _acciones(agenda):
    return [(p["accion"], p.get("rubro") or p.get("tema") or p.get("destino") or p.get("producto") or "")
            for p in agenda["preguntas"]]


# ══ 1. LA BATERIA ════════════════════════════════════════════════════════════

def test_las_fichas_grabadas_dejan_el_pedido_bien(M, F):
    from fichas import CHARLAS
    grabadas = {(r["charla"], r["turno"]): r["salida"] for r in
                map(json.loads, open(os.path.join(DOC, "ficha_vivo.jsonl"), encoding="utf-8"))}
    from app.core.flujo import interprete
    cuenta, malas = {"BIEN": 0, "DUDO": 0, "MAL SIN AVISAR": 0}, []
    for ch in CHARLAS:
        for i, tu in enumerate(ch["turnos"]):
            crudo = grabadas[(ch["id"], i)]

            async def agenda_de(msg, historial, estado, _c=crudo):
                return F.a_agenda(interprete._json(_c), estado, TIENDA, msg)
            r = asyncio.run(M.turno(tu, agenda_de))
            c = M.M.calificar(tu, json.dumps(r["ficha"], ensure_ascii=False))
            cuenta[c["veredicto"]] += 1
            if c["veredicto"] != "BIEN":
                malas.append(f"{ch['id']} t{i} {c['veredicto']}: {c['fallas']}")
    techo = json.load(open(TECHO, encoding="utf-8"))["no_bien"]
    no_bien = cuenta["DUDO"] + cuenta["MAL SIN AVISAR"]
    print(f"\nFICHA: {cuenta['BIEN']} de {sum(cuenta.values())} turnos bien, {cuenta['DUDO']} con duda, "
          f"{cuenta['MAL SIN AVISAR']} mal sin avisar; techo de los que no estan bien: {techo}")
    assert no_bien <= techo, "\n".join(malas)


# ══ 2. LAS REGLAS DEL ADAPTADOR ═══════════════════════════════════════════════

def test_el_rubro_cerrado_manda_sobre_las_palabras(F):
    """El rubro que el modelo eligio de la lista del esquema es el que se busca: "senal wifi" no se adivina."""
    ag = F.a_agenda(_ficha(consultas=[{"tipo": "buscar", "sobre": "algo para que llegue la senal wifi a la pieza",
                                       "rubro": "router", "condiciones": [], "orden": "nada", "si": ""}]),
                    _estado(), TIENDA)
    assert _acciones(ag) == [("buscar", "router")]


def test_un_rubro_nuevo_se_busca_y_se_agrega_por_su_rubro(F):
    ag = F.a_agenda(_ficha(pedido=[{"destino": "Rosario", "items": [
        _item("mouse inalambrico", "mouse", 2, condiciones=["inalambrico"], orden="mas barato")]}]), _estado(), TIENDA)
    buscar, comprar = ag["preguntas"]
    assert (buscar["accion"], buscar["rubro"], buscar["cantidad"], buscar["condiciones"], buscar["orden"]) == \
        ("buscar", "mouse", 2, ["inalambrico"], "mas barato")
    assert comprar["accion"] == "comprar" and comprar["agrega"][0]["producto"] == "mouse"
    assert comprar["agrega"][0]["destino"] == "Rosario" and not comprar.get("reemplaza")


def test_el_pedido_igual_al_borrador_no_es_un_cambio(F):
    """La ficha trae el pedido entero en cada turno: lo que ya estaba igual no se vuelve a comprar."""
    e = _estado([("mouse", 1, "Rosario")], criterios={"mouse": {"condiciones": [], "orden": "nada"}})
    ag = F.a_agenda(_ficha(pedido=[{"destino": "Rosario", "items": [_item("mouse", "mouse", 1, "L-1")]}],
                           consultas=[{"tipo": "regla de la tienda", "sobre": "factura", "tema": "factura",
                                       "rubro": "ninguno", "condiciones": [], "orden": "nada", "si": ""}]), e, TIENDA)
    assert _acciones(ag) == [("politica", "factura")]


def test_un_pedido_distinto_reemplaza_entero(F):
    e = _estado([("mouse", 1, "Rosario"), ("teclado", 1, "Rosario")])
    ag = F.a_agenda(_ficha(pedido=[{"destino": "Rosario", "items": [_item("mouse", "mouse", 1, "L-1")]}]), e, TIENDA)
    comprar = next(p for p in ag["preguntas"] if p["accion"] == "comprar")
    assert comprar["reemplaza"] is True and [a["producto"] for a in comprar["agrega"]] == ["mouse"]


def test_un_envio_por_lugar_y_el_plazo_por_su_regla(F):
    """"Cuanto sale y cuanto tarda a Ushuaia y a Salta": dos cotizaciones, y el plazo, que la cotizacion no dice."""
    ag = F.a_agenda(_ficha(consultas=[{"tipo": "envio", "sobre": "cuanto tarda el envio", "lugar": "Ushuaia y Salta",
                                       "tema": "plazo_envio", "rubro": "ninguno", "condiciones": [], "orden": "nada",
                                       "si": ""}]), _estado(), TIENDA)
    assert _acciones(ag) == [("envio", "Ushuaia"), ("envio", "Salta"), ("politica", "plazo_envio")]


def test_un_envio_sin_lugar_va_a_los_destinos_del_pedido(F):
    e = _estado([("mouse", 1, "Neuquén")])
    ag = F.a_agenda(_ficha(pedido=[{"destino": "Neuquén", "items": [_item("mouse", "mouse", 1, "L-1")]}],
                           consultas=[{"tipo": "envio", "sobre": "tiempo de entrega", "tema": "ninguno",
                                       "rubro": "ninguno", "condiciones": [], "orden": "nada", "si": ""}]), e, TIENDA)
    assert ("envio", "Neuquén") in _acciones(ag)


def test_sin_pedido_el_tope_acota_lo_que_se_busca(F):
    """"Mostrame hasta 300 mil" sin nada pedido: no hay que contar, el tope va a la busqueda."""
    ag = F.a_agenda(_ficha(consultas=[{"tipo": "buscar", "sobre": "sillas", "rubro": "silla gamer", "condiciones": [],
                                       "orden": "nada", "si": ""}],
                           pago={"medios": [], "tope_total": 300000}), _estado(), TIENDA)
    assert _acciones(ag) == [("buscar", "silla gamer")]
    assert ag["preguntas"][0]["condiciones"] == ["hasta $300.000"]


def test_el_tope_ya_dicho_no_se_vuelve_a_contar(F):
    e = _estado([("mouse", 1, "Rosario")], tope=600000)
    ag = F.a_agenda(_ficha(pedido=[{"destino": "Rosario", "items": [_item("mouse", "mouse", 1, "L-1")]}],
                           pago={"medios": [], "tope_total": 600000},
                           consultas=[{"tipo": "regla de la tienda", "sobre": "garantia", "tema": "garantia",
                                       "rubro": "ninguno", "condiciones": [], "orden": "nada", "si": ""}]), e, TIENDA)
    assert _acciones(ag) == [("politica", "garantia")]


def test_lo_que_no_cambia_ni_consulta_ve_la_cuenta(F):
    """"No mas de 600 entre todos", ya dicho: la respuesta es como queda, no "en que te puedo ayudar"."""
    e = _estado([("mouse", 1, "Rosario")], tope=600000)
    ag = F.a_agenda(_ficha(pedido=[{"destino": "Rosario", "items": [_item("mouse", "mouse", 1, "L-1")]}],
                           pago={"medios": [], "tope_total": 600000}), e, TIENDA)
    assert _acciones(ag) == [("cuenta", "")]


def test_son_siete_lo_controla_el_borrador(F):
    e = _estado([("mouse", 1, "Rosario")])
    ag = F.a_agenda(_ficha(pedido=[{"destino": "Rosario", "items": [_item("mouse", "mouse", 1, "L-1")]}], son=7),
                    e, TIENDA)
    assert next(p for p in ag["preguntas"] if p["accion"] == "comprar")["total"] == 7


def test_una_consulta_de_producto_sin_producto_no_pregunta_por_la_palabra(F):
    """"precio" no es un producto: sin producto nombrado, si dice un rubro es una busqueda; si no, nada."""
    ag = F.a_agenda(_ficha(consultas=[{"tipo": "producto", "sobre": "precio", "rubro": "mouse", "producto": "",
                                       "condiciones": [], "orden": "nada", "si": ""},
                                      {"tipo": "producto", "sobre": "precio", "rubro": "ninguno", "producto": "",
                                       "condiciones": [], "orden": "nada", "si": ""}]), _estado(), TIENDA)
    assert _acciones(ag) == [("buscar", "mouse")]


def test_el_numero_de_la_libreta_es_el_producto(F):
    """"M2" y "M-2" son el mismo numero de la libreta."""
    e = _estado(mostrados=["MOU0009", "MOU0035"])
    ag = F.a_agenda(_ficha(consultas=[{"tipo": "producto", "sobre": "si es inalambrico", "producto": "M2",
                                       "rubro": "mouse", "condiciones": [], "orden": "nada", "si": ""}]), e, TIENDA)
    assert _acciones(ag) == [("producto", "M-2")]


def test_un_renglon_que_pasa_a_un_modelo_nombrado(F):
    """"El negro" sobre el renglon de teclado, con el K120 a la vista: el renglon ahora es ese modelo."""
    from app.core.flujo import catalogo as K
    k120 = next(p["id"] for p in K.productos(TIENDA) if "K120" in p["nombre"])
    e = _estado([("teclado", 3, "")], mostrados=[k120], criterios={"teclado": {"condiciones": [], "orden": "nada"}})
    ag = F.a_agenda(_ficha(pedido=[{"destino": "sin decir", "items": [
        _item("Teclado Logitech K120", "teclado", 3, "L-1")]}]), e, TIENDA, "el negro, son tres")
    comprar = next(p for p in ag["preguntas"] if p["accion"] == "comprar")
    assert comprar["agrega"][0]["producto"] == "Teclado Logitech K120"


def test_el_modelo_de_lenguaje_no_elige_productos(F):
    """"Arma todo con lo mejor": un modelo que el cliente no nombro ni leyo no entra al pedido; queda el rubro, con el
    orden que pidio."""
    e = _estado([("mouse", 2, "Rosario")], criterios={"mouse": {"condiciones": [], "orden": "mas barato"}})
    ag = F.a_agenda(_ficha(pedido=[{"destino": "Rosario", "items": [
        _item("Mouse Logitech MX Master 3S", "mouse", 2, "L-1", orden="mas caro")]}]), e, TIENDA,
        "arma todo con lo mejor que tengas")
    assert _acciones(ag) == [("buscar", "mouse")] and ag["preguntas"][0]["orden"] == "mas caro"


def test_lo_que_la_tienda_no_sabe_lo_dice_la_busqueda(F):
    """"El mouse mas vendido": es una busqueda con un orden que la tienda no tiene; el codigo contesta que no tiene el
    dato, no el modelo."""
    ag = F.a_agenda(_ficha(consultas=[{"tipo": "producto", "sobre": "cual es el mas vendido", "producto": "mouse",
                                       "rubro": "mouse", "condiciones": [], "orden": "nada", "si": ""}]), _estado(),
                    TIENDA)
    assert _acciones(ag) == [("buscar", "mouse")] and ag["preguntas"][0]["orden"] == "mas vendido"


def test_la_duda_pasa_el_control_del_vendedor():
    """La duda del modelo sale al cliente solo sin montos ni productos que no esten a la vista."""
    from app.core.flujo import interprete
    assert interprete.controlar("¿Para cuantas personas es?", "", TIENDA)
    assert not interprete.controlar("¿Te sirve el G305 a $80.500?", "", TIENDA)


# ══ 3. LO QUE QUEDA A MEDIAS ══════════════════════════════════════════════════

@pytest.mark.xfail(strict=True, reason="A MEDIAS: lo condicional de la ficha va en palabras, `si`, y la agenda necesita "
                                       "{'de': n, 'da': 'si'}. Hoy se cumple sin condicion.")
def test_lo_condicional_se_cumple_con_su_condicion(F):
    e = _estado(mostrados=["MOU0009"])
    ag = F.a_agenda(_ficha(consultas=[{"tipo": "producto", "sobre": "si es inalambrico", "producto": "M-1",
                                       "rubro": "mouse", "condiciones": [], "orden": "nada", "si": ""}],
                           pedido=[{"destino": "Cordoba", "items": [_item("M-1", "mouse", 1, si="si es inalambrico")]}]),
                    e, TIENDA)
    assert any(p.get("si") for p in ag["preguntas"] if p["accion"] == "comprar")


@pytest.mark.xfail(strict=True, reason="A MEDIAS: un rubro tiene un criterio. Dos renglones del mismo rubro con "
                                       "condiciones distintas por destino quedan con la del primero.")
def test_dos_destinos_con_condiciones_distintas_del_mismo_rubro(F):
    e = _estado([("teclado", 1, "Córdoba"), ("teclado", 1, "Río Tercero")],
                criterios={"teclado": {"condiciones": [], "orden": "nada"}})
    ag = F.a_agenda(_ficha(pedido=[
        {"destino": "Córdoba", "items": [_item("teclado", "teclado", 1, "L-1", condiciones=["con cable"])]},
        {"destino": "Río Tercero", "items": [_item("teclado", "teclado", 1, "L-2", condiciones=["inalambrico"])]}]),
        e, TIENDA)
    conds = [p.get("condiciones") for p in ag["preguntas"] if p["accion"] == "buscar"]
    assert ["con cable"] in conds and ["inalambrico"] in conds
