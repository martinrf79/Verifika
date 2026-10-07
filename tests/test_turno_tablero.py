"""EL TABLERO — `app/core/tablero.py`, el turno vivo desde el 30-sep-2026.

Sin modelo de verdad: un modelo de mentira contesta segun lo que se le pide
—las piezas, las preguntas de si o no, o la redaccion— y lo que se mide es lo
que hace el codigo. El modelo real se mide por el clon:
`sonda_charlas --vara todas`. FICHA 65, seccion 17.
"""
import asyncio
import json
from types import SimpleNamespace as NS

import pytest

from app.core import agente as A
from app.core import respuesta as R
from app.core import tablero as T

TIENDA = "verifika_prod"


@pytest.fixture(autouse=True)
def _doble(firestore_doble):
    from app.core.contexto_turno import set_current_tienda
    from app.core.filtros_catalogo import limpiar_cache
    set_current_tienda(TIENDA)
    limpiar_cache()
    A.CLIENTE_DIJO.set("")
    return firestore_doble


class _Modelo:
    """Contesta por lo que se le pide: el nombre del esquema dice que paso es."""

    def __init__(self, piezas, banderas=None, texto="listo"):
        self.piezas, self.banderas, self.texto, self.pedidos = piezas, banderas or {}, texto, []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.pedidos.append(kw)
        nombre = ((kw.get("response_format") or {}).get("json_schema") or {}).get("name")
        cont = {"piezas": json.dumps({"piezas": self.piezas}),
                "banderas": json.dumps({k: bool(self.banderas.get(k)) for k in T.BANDERAS})}.get(nombre, self.texto)
        return NS(choices=[NS(message=NS(content=cont))],
                  usage=NS(prompt_tokens=100, completion_tokens=10, prompt_tokens_details=None))


def _con(monkeypatch, m):
    monkeypatch.setattr("app.core.llm_reintento._cliente", lambda: m)
    return m


def _turno(mensaje, historial=None, memoria=""):
    return asyncio.run(T.turno(historial or [], mensaje, TIENDA, trace_id="t", memoria=memoria))


def test_el_turno_corre_las_piezas_y_el_redactor_ve_solo_lo_que_volvio(monkeypatch):
    m = _con(monkeypatch, _Modelo([{"n": 1, "tipo": "producto", "texto": "cuanto sale el K120 negro",
                                    "producto": "K120 negro"}], texto="Sale $14.500."))
    r = _turno("cuanto sale el K120 negro?")
    assert [x["herramienta"] for x in r["llamadas"]] == ["producto"]
    assert {u["paso"] for u in r["uso"]} == {"interpretar", "banderas", "redactar"}
    redactor = m.pedidos[-1]["messages"]
    assert "tools" not in m.pedidos[-1] and "HECHOS" in redactor[-1]["content"]
    assert "14.500" in redactor[-1]["content"]


def test_una_consulta_repetida_lleva_su_resultado_al_redactor():
    pz = [{"n": 1, "tipo": "envio", "texto": "a Rosario", "destinos": ["Rosario"]}]
    ctx = {"mensaje": "a Rosario", "historial": [], "memoria": "", "pide_total": False}
    llamadas = []
    T.correr_piezas(pz, TIENDA, llamadas, 1, ctx)
    segunda = T.correr_piezas(pz, TIENDA, llamadas, 2, ctx)
    assert len(llamadas) == 1 and "resultado" in segunda[0]


def test_la_identidad_se_certifica_solo_si_la_fila_nombra_todo():
    assert T._certificado("MX Master 3S negro", TIENDA, []) == "MOU0007"
    assert T._certificado("K120 blanco", TIENDA, []) == "TEC0030"
    assert T._certificado("G305", TIENDA, []) == "G305"  # dos colores: la cuenta pregunta


def test_la_cuenta_suma_lo_que_el_cliente_eligio_no_lo_que_el_bot_mostro():
    A.CLIENTE_DIJO.set("quiero el G305 negro\ncuanto es todo?")
    items = [{"producto": "MOU0029", "cantidad": 1}, {"producto": "AUR0013", "cantidad": 1}]
    assert T._elegidos(items, [], "", TIENDA) == [{"producto": "MOU0029", "cantidad": 1}]


def test_el_reparto_en_fraccion_se_pasa_a_porcentaje():
    r = T._reparto([{"medio": "transferencia", "porcentaje": 0.7}, {"medio": "mp", "porcentaje": 0.3}])
    assert [x["porcentaje"] for x in r] == [70.0, 30.0]


def test_el_destino_dicho_antes_sigue_valiendo():
    hist = [{"role": "user", "content": "hola, soy de Mendoza"}, {"role": "assistant", "content": "hola"}]
    assert "Mendoza" in T._destino({}, [], "y con envio cuanto seria?", hist, "")


def test_los_ids_internos_no_llegan_al_cliente():
    t = T._sin_ids("El **MOU0001** o el negro (MOU0029)", TIENDA)
    assert "MOU0" not in t and "G203" in t


def test_la_condicion_que_no_se_pudo_filtrar_se_rotula():
    r = T._para_redactar({"veredicto": "existe", "filas": [], "no_aplicado": [{"campo": "bluetooth", "motivo": "x"}]})
    assert r["no_se_pudo_filtrar_por"] == ["bluetooth"] and "no_aplicado" not in r


def test_si_falta_un_dato_del_cliente_el_codigo_pide_la_repregunta(monkeypatch):
    m = _con(monkeypatch, _Modelo([{"n": 1, "tipo": "compatibilidad", "texto": "le sirve a mi pc?"}],
                                  banderas={"falta_dato_cliente": True}))
    _turno("le sirve a mi pc?")
    assert "pregunta_al_cliente" in m.pedidos[-1]["messages"][-1]["content"]


def test_procesar_turno_llama_al_tablero(monkeypatch):
    async def falso(historial, mensaje, tienda_id, trace_id="", memoria="", pedido=None):
        return {"texto": "desde el tablero", "llamadas": [], "uso": []}
    monkeypatch.setattr(T, "turno", falso)
    assert "desde el tablero" in asyncio.run(R.procesar_turno("t_tab", "hola", TIENDA, "whatsapp", "t")).lower()


# ══ LA SEGUNDA VUELTA (1-oct): la cuenta sale de lo que busco el turno ══════

def test_buscar_elegir_y_sumar_en_el_mismo_mensaje(monkeypatch):
    """K03 del banco: el interprete arma dos busquedas y una cuenta con items
    genericos. La cuenta suma la primera fila con stock de cada busqueda, con
    la cantidad pedida, y el envio del destino."""
    _con(monkeypatch, _Modelo([
        {"n": 1, "tipo": "buscar", "texto": "dos auriculares, los mas baratos", "rubro": "auriculares",
         "orden": {"campo": "precio_ars", "direccion": "min"}},
        {"n": 2, "tipo": "buscar", "texto": "dos mouse, los mas baratos", "rubro": "mouse",
         "orden": {"campo": "precio_ars", "direccion": "min"}},
        {"n": 3, "tipo": "cuenta", "texto": "sumame todo", "depende_de": [1, 2], "falta": "destino: Cordoba",
         "items": [{"producto": "auriculares", "cantidad": 2}, {"producto": "mouse", "cantidad": 2}]}],
        banderas={"pide_total": True}))
    r = _turno("dos auriculares y dos mouse, los mas baratos, sumame todo con envio a Cordoba capital")
    cuenta = next(x for x in r["llamadas"] if x["herramienta"] == "cuenta")
    assert [(i["producto"], i["cantidad"]) for i in cuenta["args"]["items"]] == [("AUR0019", 2), ("MOU0023", 2)]
    assert cuenta["vuelve"]["cuenta"]["total_ars"] == 139500
    # el destino que el cliente dijo no se le vuelve a preguntar
    assert not any(h.get("pregunta_al_cliente") for h in r["hechos"])


def test_un_rubro_escrito_como_producto_se_busca_y_la_condicion_suelta_vale_para_todos():
    piezas = T._normalizar([
        {"n": 1, "tipo": "producto", "producto": "auriculares"},
        {"n": 2, "tipo": "producto", "producto": "memorias"},
        {"n": 3, "tipo": "buscar", "condiciones": [{"campo": "pais_fabricacion", "operador": "evita",
                                                    "valor": "China"}]},
        {"n": 4, "tipo": "cuenta", "items": []},
        {"n": 5, "tipo": "producto", "producto": "K120", "reparto_pago": [{"medio": "x", "porcentaje": 70}]}],
        TIENDA)
    assert [(p["tipo"], p.get("rubro")) for p in piezas[:2]] == [("buscar", "auriculares"), ("buscar", "memoria ram")]
    assert all(p["condiciones"][0]["campo"] == "pais_fabricacion" for p in piezas[:2])
    assert 3 not in [p["n"] for p in piezas]
    assert piezas[-1]["tipo"] == "cuenta" and piezas[-1]["reparto_pago"]


def test_cada_cuenta_lleva_su_destino_y_una_sola_lleva_todos():
    envio = {"tipo": "envio", "destinos": ["Rosario", "Concordia"]}
    sola = {"tipo": "cuenta", "texto": "sumame todo"}
    assert T._destinos_del_turno(sola, [sola, envio]) == ["Rosario", "Concordia"]
    a = {"tipo": "cuenta", "destinos": ["Rosario"]}
    b = {"tipo": "cuenta", "texto": "una memoria y un mouse a Concordia"}
    assert T._destinos_del_turno(a, [a, b, envio]) == ["Rosario"]
    assert "Concordia" in T._destinos_del_turno(b, [a, b, envio])[0]


def test_el_medio_que_el_cliente_no_nombro_no_se_inventa():
    A.CLIENTE_DIJO.set("dividi el presupuesto en setenta treinta")
    rep = T._reparto([{"medio": "efectivo", "porcentaje": 70}, {"medio": "tarjeta", "porcentaje": 30}])
    assert [r["medio"] for r in rep] == ["parte 1", "parte 2"]
    A.CLIENTE_DIJO.set("pago 70 por ciento transferencia y 30 por ciento Mercado Pago")
    rep = T._reparto([{"medio": "transferencia", "porcentaje": 70}, {"medio": "Mercado Pago", "porcentaje": 30}])
    assert [r["medio"] for r in rep] == ["transferencia", "Mercado Pago"]


def test_la_cuenta_suma_un_envio_por_destino():
    r = A.h_cuenta(TIENDA, items=[{"producto": "MOU0023", "cantidad": 1}], destinos=["Rosario", "Concordia"])
    assert r["cuenta"]["total_ars"] == 8500 + 7000 + 6500


# ══ LOS ARTICULOS SE CONSERVAN (1-oct, K20): lo pedido cierra con lo repartido ═

K20 = ("Dame precio de dos auriculares, dos mouse y dos memorias. Un auricular y un mouse a Cordoba capital. "
       "Un teclado y un mouse a Concordia. Los otros dos a Posadas. Divide el presupuesto en setenta treinta")


def _lista(*rubros):
    return [{"n": i, "tipo": "buscar", "texto": r, "rubro": r, "cantidad": 2} for i, r in enumerate(rubros, 1)]


def test_una_cuenta_con_items_a_varios_destinos_es_una_cuenta_por_destino():
    p = {"tipo": "cuenta", "items": [{"producto": "mouse", "cantidad": 1, "destino": "Cordoba"},
                                     {"producto": "auriculares", "cantidad": 1, "destino": "Posadas"},
                                     {"producto": "memoria ram", "cantidad": 1, "destino": "Cordoba"}]}
    partes = T._por_destino(p)
    assert [(x["destinos"], len(x["items"])) for x in partes] == [(["Cordoba"], 2), (["Posadas"], 1)]


def test_lo_que_no_estaba_en_la_lista_se_cambia_por_lo_que_quedo_sin_destino():
    cuentas = [{"n": 4, "tipo": "cuenta", "texto": "a Cordoba", "items": [{"producto": "auriculares", "cantidad": 1},
                                                                          {"producto": "mouse", "cantidad": 1}]},
               {"n": 5, "tipo": "cuenta", "texto": "a Concordia", "items": [{"producto": "teclado", "cantidad": 1},
                                                                            {"producto": "mouse", "cantidad": 1}]},
               {"n": 6, "tipo": "cuenta", "texto": "a Posadas", "items": [{"producto": "auriculares", "cantidad": 1},
                                                                          {"producto": "memoria ram", "cantidad": 1}]}]
    piezas = _lista("auriculares", "mouse", "memoria ram") + cuentas
    inf = T._conservar(piezas, TIENDA, K20)
    assert inf["reemplazo"][0]["dijo"] == "teclado" and inf["reemplazo"][0]["se_tomo"] == "memoria ram"
    assert cuentas[1]["items"][0]["producto"] == "memoria ram" and "sin_destino" not in inf


def test_lo_que_queda_sin_destino_se_informa_y_lo_nombrado_fuera_de_la_lista_tambien():
    cuentas = [{"n": 4, "tipo": "cuenta", "items": [{"producto": "auriculares", "cantidad": 1}]},
               {"n": 5, "tipo": "cuenta", "items": [{"producto": "mouse", "cantidad": 2}]}]
    inf = T._conservar(_lista("auriculares", "mouse") + cuentas, TIENDA, "dos auriculares y dos mouse")
    assert inf["sin_destino"] == ["1 auriculares"]
    cerradas = [{"n": 4, "tipo": "cuenta", "items": [{"producto": "auriculares", "cantidad": 2}]},
                {"n": 5, "tipo": "cuenta", "items": [{"producto": "mouse", "cantidad": 2}]}]
    inf = T._conservar(_lista("auriculares", "mouse") + cerradas, TIENDA, "y un teclado a Concordia")
    assert "teclado" in inf["nombro_fuera_de_la_lista"][0]
    assert T._conservar(_lista("auriculares", "mouse") + cerradas, TIENDA, "dos auriculares y dos mouse") == {}


def test_el_item_descripto_con_el_rubro_adentro_es_de_ese_rubro():
    """K06 y K07, 7-oct: "teclado mas barato" es del rubro teclado. Sin esto el
    reparto que cerraba se contaba sin destino y el turno frenaba a confirmar."""
    cuentas = [{"n": 4, "tipo": "cuenta", "items": [{"producto": "teclado más barato", "cantidad": 1, "destino": "Rosario"},
                                                    {"producto": "auricular más barato", "cantidad": 1, "destino": "Rosario"}]},
               {"n": 5, "tipo": "cuenta", "items": [{"producto": "teclado más barato", "cantidad": 1, "destino": "Salta"},
                                                    {"producto": "auricular más barato", "cantidad": 1, "destino": "Salta"}]}]
    assert T._conservar(_lista("teclado", "auriculares") + cuentas, TIENDA, "dos teclados y dos auriculares") == {}
    assert T._rubro_de("teclado más barato", TIENDA) == "teclado"
    assert T._rubro_de("teclado y mouse", TIENDA) == ""


def test_con_varios_destinos_hay_un_total_general_y_el_reparto_va_sobre_el(monkeypatch):
    """K20: el 70/30 se pide una vez y es sobre todo. Cada destino sale sin el
    suyo; el total general es la suma de los bloques, y el reparto, sobre ella."""
    A.CLIENTE_DIJO.set(K20)
    piezas = [{"n": 1, "tipo": "cuenta", "texto": "a Rosario", "destinos": ["Rosario"],
               "items": [{"producto": "MOU0023", "cantidad": 1}],
               "reparto_pago": [{"medio": "x", "porcentaje": 70}, {"medio": "y", "porcentaje": 30}]},
              {"n": 2, "tipo": "cuenta", "texto": "a Concordia", "destinos": ["Concordia"],
               "items": [{"producto": "MOU0023", "cantidad": 1}]}]
    ctx = {"mensaje": K20, "historial": [], "memoria": "", "pide_total": True}
    llamadas = []
    hechos = T.correr_piezas(piezas, TIENDA, llamadas, 1, ctx)
    cuentas = [x for x in llamadas if x["herramienta"] == "cuenta"]
    assert len(cuentas) == 2 and not any(x["args"]["reparto_pago"] for x in cuentas)
    tg = next(x for x in llamadas if x["herramienta"] == "total_general")["vuelve"]
    assert tg["total_ars"] == (8500 + 7000) + (8500 + 6500)
    assert [p["monto_ars"] for p in tg["split_pago"]["partes"]] == [21350, 9150]
    assert hechos[-1]["tipo"] == "total_general"
    assert not A.faltantes(K20, llamadas).get("reparto")


# ══ LA MEMORIA GUARDA LO QUE BUSCO EL CLIENTE (1-oct, K17, K18, M03) ════════

def test_lo_que_busco_el_cliente_sobrevive_al_turno_y_va_a_la_memoria():
    b = [({"rubro": "", "orden": {"campo": "precio_ars", "direccion": "max"}}, {}),
         ({"rubro": "mouse", "condiciones": [{"campo": "marca", "operador": "no_contiene", "valor": "Genius"}]}, {})]
    v = T.busqueda_vigente(b)
    assert v.splitlines() == ["buscar toda la tienda, orden precio_ars max",
                              "buscar mouse, marca no_contiene Genius"]
    assert "toda la tienda" in R._memoria_texto({"criterio_cliente": v})


def test_un_modelo_en_dos_colores_es_uno_si_el_cliente_no_nombro_el_color():
    A.CLIENTE_DIJO.set("sumame uno de cada uno")
    items = [{"producto": "MOU0023", "cantidad": 1}, {"producto": "MOU0024", "cantidad": 1}]
    assert T._un_color_por_modelo(items, TIENDA) == [items[0]]
    A.CLIENTE_DIJO.set("uno negro y uno blanco")
    assert T._un_color_por_modelo(items, TIENDA) == items


def test_el_orden_suelto_vale_para_las_busquedas_que_no_traen_el_suyo():
    piezas = T._normalizar([
        {"n": 1, "tipo": "buscar", "rubro": "auriculares", "cantidad": 2},
        {"n": 2, "tipo": "buscar", "rubro": "mouse", "cantidad": 2},
        {"n": 3, "tipo": "buscar", "texto": "los mas baratos", "orden": {"campo": "precio_ars", "direccion": "min"}}],
        TIENDA)
    assert [p["orden"]["direccion"] for p in piezas] == ["min", "min"]
    sola = T._normalizar([{"n": 1, "tipo": "buscar", "orden": {"campo": "precio_ars", "direccion": "max"}}], TIENDA)
    assert len(sola) == 1


def test_en_el_esquema_la_cantidad_va_antes_que_el_orden():
    """Medido el 1-oct: con la cantidad despues del orden, el interprete
    llenaba la cantidad y dejaba el orden afuera. "Los 3 mas baratos" salia
    sin orden."""
    props = list(T.esquema_piezas(TIENDA)["properties"]["piezas"]["items"]["properties"])
    assert props.index("cantidad") < props.index("orden")


def test_la_pieza_repetida_de_un_rubro_no_duplica_lo_pedido():
    piezas = _lista("auriculares") + _lista("auriculares") + [
        {"n": 4, "tipo": "cuenta", "items": [{"producto": "auriculares", "cantidad": 1}]},
        {"n": 5, "tipo": "cuenta", "items": [{"producto": "auriculares", "cantidad": 1}]}]
    assert T._conservar(piezas, TIENDA, "dos auriculares") == {}


def test_un_rubro_que_la_tienda_no_vende_es_no_existe_y_no_se_busca():
    """K12: con la lista cerrada, "celulares" salia como notebook."""
    pz = [{"n": 1, "tipo": "buscar", "texto": "tenes celulares samsung", "rubro": T.NO_LO_VENDE}]
    ctx = {"mensaje": "tenes celulares samsung?", "historial": [], "memoria": "", "pide_total": False}
    llamadas = []
    hechos = T.correr_piezas(pz, TIENDA, llamadas, 1, ctx)
    assert llamadas == [] and hechos[0]["resultado"]["veredicto"] == "no_existe"
    assert T.NO_LO_VENDE in T.esquema_piezas(TIENDA)["properties"]["piezas"]["items"]["properties"]["rubro"]["enum"]
    assert "celulares" in T.busqueda_vigente(ctx["no_vende"])


def test_el_reparto_nuevo_sobre_los_presupuestos_por_destino_de_la_memoria(monkeypatch):
    """K07: tres destinos en un turno y en el siguiente "mitad transferencia y
    mitad mercado pago". La memoria trae los bloques y el codigo los rearma con
    el reparto nuevo, sobre el total general."""
    conv = {"grupos_envio": [{"destino": "Rosario", "items": [{"producto": "MOU0023", "cantidad": 1}]},
                             {"destino": "Concordia", "items": [{"producto": "MOU0023", "cantidad": 1}]}]}
    memoria = R._memoria_texto(conv)
    assert [g["destino"] for g in T.bloques_en_memoria(memoria)] == ["Rosario", "Concordia"]
    _con(monkeypatch, _Modelo([{"n": 1, "tipo": "cuenta", "texto": "mitad y mitad", "items": [],
                                "reparto_pago": [{"medio": "transferencia", "porcentaje": 50},
                                                 {"medio": "mercado pago", "porcentaje": 50}]}],
                              banderas={"pide_total": True}))
    r = asyncio.run(T.turno([], "Decime mitad transferencia y mitad mercado pago como quedaria", TIENDA,
                            trace_id="t", memoria=memoria))
    tg = next(x for x in r["llamadas"] if x["herramienta"] == "total_general")["vuelve"]
    assert tg["total_ars"] == (8500 + 7000) + (8500 + 6500)
    assert [p["medio"] for p in tg["split_pago"]["partes"]] == ["transferencia", "mercado pago"]
    assert len(r["bloques"]) == 2


def test_la_busqueda_sin_orden_hereda_el_orden_comun_del_mensaje():
    o = {"campo": "precio_ars", "direccion": "min"}
    piezas = T._normalizar([{"n": 1, "tipo": "buscar", "rubro": "mouse", "orden": o},
                            {"n": 2, "tipo": "buscar", "rubro": "teclado", "orden": o},
                            {"n": 3, "tipo": "producto", "producto": "Auriculares"},
                            {"n": 4, "tipo": "buscar", "rubro": "monitor"}], TIENDA)
    assert piezas[2]["rubro"] == "auriculares" and piezas[2]["orden"] == o and piezas[3]["orden"] == o
    # con uno solo, o con dos distintos, no se hereda
    una = T._normalizar([{"n": 1, "tipo": "buscar", "rubro": "mouse", "orden": o},
                         {"n": 2, "tipo": "buscar", "rubro": "teclado"}], TIENDA)
    assert not una[1].get("orden")


def test_el_singular_de_un_rubro_plural_es_el_rubro():
    assert T._es_rubro("auricular", TIENDA) == "auriculares"
    assert T._es_rubro("mouse", TIENDA) == "mouse"


def test_la_cuenta_con_un_rubro_que_nadie_busca_pide_revision():
    piezas = [{"n": 1, "tipo": "cuenta", "items": [{"producto": "notebook", "cantidad": 2}]}]
    assert "notebook" in T._revision(piezas, {}, [], "dos notebooks", [], TIENDA)


def test_dos_mitades_son_un_reparto():
    assert A._pide_reparto("Decime mitad transferencia y mitad mercado pago como quedaria")
    assert not A._pide_reparto("la mitad de precio?")


# ══ PRIMERO SE CONFIRMA, DESPUES SE CALCULA (1-oct, K20) ═════════════════════

def _k20_piezas():
    return (_lista("mouse", "memoria ram") + [
        {"n": 4, "tipo": "cuenta", "texto": "a Rosario", "destinos": ["Rosario"],
         "items": [{"producto": "mouse", "cantidad": 1}, {"producto": "memoria ram", "cantidad": 1}],
         "reparto_pago": [{"medio": "x", "porcentaje": 70}, {"medio": "y", "porcentaje": 30}]},
        {"n": 5, "tipo": "cuenta", "texto": "a Concordia", "destinos": ["Concordia"],
         "items": [{"producto": "teclado", "cantidad": 1}, {"producto": "mouse", "cantidad": 1}]}])


def test_si_lo_repartido_no_cierra_se_confirma_antes_de_calcular(monkeypatch):
    msg = "dos mouse y dos memorias. un mouse y una memoria a Rosario, un teclado y un mouse a Concordia. 70/30"
    m = _con(monkeypatch, _Modelo(_k20_piezas(), banderas={"pide_total": True}))
    r = _turno(msg)
    assert not any(x["herramienta"] in ("cuenta", "total_general", "buscar") for x in r["llamadas"])
    assert r["hechos"][0]["tipo"] == "confirmar_pedido"
    assert r["pedido"]["piezas"] and r["pedido"]["avisos"]["reemplazo"][0]["dijo"] == "teclado"
    assert "confirmar_pedido" in m.pedidos[-1]["messages"][-1]["content"]
    # el si del cliente: corre lo guardado, con el reparto sobre el total, y borra el pedido
    _con(monkeypatch, _Modelo([{"n": 1, "tipo": "charla", "texto": "si"}],
                              banderas={"confirma_resumen": True}))
    r2 = asyncio.run(T.turno([{"role": "user", "content": msg}, {"role": "assistant", "content": "¿esta bien?"}],
                             "si, dale", TIENDA, trace_id="t", pedido=r["pedido"]))
    cuentas = [x for x in r2["llamadas"] if x["herramienta"] == "cuenta"]
    assert len(cuentas) == 2 and any(x["herramienta"] == "total_general" for x in r2["llamadas"])
    assert r2["pedido"] == {}


def test_un_mensaje_de_otra_cosa_deja_el_pedido_esperando(monkeypatch):
    _con(monkeypatch, _Modelo([{"n": 1, "tipo": "politica", "texto": "hacen factura A?", "tema": "facturacion"}]))
    from app.core import pedido as PD
    guardado = PD.guardar(_k20_piezas(), {"sin_destino": ["1 mouse"]})
    r = asyncio.run(T.turno([], "hacen factura A?", TIENDA, trace_id="t", pedido=guardado))
    assert not any(x["herramienta"] == "cuenta" for x in r["llamadas"]) and r["pedido"] is None


# ══ LO GRABADO: las charlas de `grab_1` que el codigo resolvia mal (2-oct) ══

def _filas(r):
    return [f.get("id") for f in r.get("filas") or []]


def test_el_id_que_resolvio_el_interprete_es_la_identidad():
    """M06, M10: "la segunda", "el primero" llegan como id y se buscaban como texto."""
    r = A.ejecutar("producto", {"nombre": "WEB0002"}, TIENDA)
    assert r["veredicto"] == "existe" and _filas(r) == ["WEB0002"]


def test_el_id_con_un_color_es_el_mismo_modelo_en_ese_color():
    """M01: "volviendo al mouse del principio, lo tenes en negro?" llega como id y color."""
    from app.storage.firestore_client import get_all_products
    negro = next(p["id"] for p in get_all_products(tienda_id=TIENDA)
                 if "G305" in p.get("nombre", "") and p.get("color", "").lower() == "negro")
    r = A.ejecutar("producto", {"nombre": "MOU0030 negro"}, TIENDA)
    assert _filas(r) == [negro]
    assert _filas(A.ejecutar("producto", {"nombre": "MOU0030"}, TIENDA)) == ["MOU0030"]


def test_un_id_en_las_condiciones_de_una_busqueda_va_por_id():
    """C44: "el otro" llego como condicion modelo igual MOU0001."""
    r = A.ejecutar("buscar", {"rubro": "mouse", "condiciones": [
        {"campo": "modelo", "operador": "igual", "valor": "MOU0001"}]}, TIENDA)
    assert r["veredicto"] == "existe" and _filas(r)[0] in ("MOU0001", "MOU0002")


_MEMORIA_EXCLUYE = "LO ULTIMO QUE BUSCO EL CLIENTE:\nbuscar mouse, marca no_contiene Genius, marca no_contiene Logitech"


def test_la_exclusion_sigue_valiendo_en_otro_rubro():
    """K17: "que no sea Genius ni Logitech" y despues "y teclados?"."""
    pz = T._heredar_exclusiones([{"n": 1, "tipo": "buscar", "texto": "y teclados?", "rubro": "teclado"}],
                                _MEMORIA_EXCLUYE, "y teclados?")
    assert {c["valor"] for c in pz[0]["condiciones"]} == {"Genius", "Logitech"}


def test_la_exclusion_se_suelta_si_el_cliente_la_suelta_o_vuelve_a_nombrar_la_marca():
    pz = [{"n": 1, "tipo": "buscar", "texto": "x", "rubro": "teclado"}]
    assert "condiciones" not in T._heredar_exclusiones(pz, _MEMORIA_EXCLUYE, "y teclados, cualquier marca")[0]
    vale = T._heredar_exclusiones(pz, _MEMORIA_EXCLUYE, "y teclados logitech?")[0]["condiciones"]
    assert [c["valor"] for c in vale] == ["Genius"]


def test_lo_que_elige_una_busqueda_no_se_hereda():
    """M10: "auriculares JBL" y despues "un mouse barato" no es un mouse JBL."""
    memoria = "buscar auriculares, marca igual JBL"
    pz = T._heredar_exclusiones([{"n": 1, "tipo": "buscar", "texto": "y un mouse", "rubro": "mouse"}],
                                memoria, "y un mouse")
    assert "condiciones" not in pz[0]


def test_la_revision_no_pierde_lo_que_el_mensaje_excluia(monkeypatch):
    """K17, primer turno: la correccion paso las exclusiones a una pieza verificar."""
    excluye = [{"campo": "marca", "operador": "no_contiene", "valor": "Genius"}]
    m = _con(monkeypatch, _Modelo([{"n": 1, "tipo": "buscar", "texto": "un mouse que no sea Genius",
                                    "rubro": "mouse", "condiciones": excluye}], banderas={"afirma_algo": True}))
    corregidas = [{"n": 1, "tipo": "verificar", "texto": "x", "condiciones": excluye},
                  {"n": 2, "tipo": "buscar", "texto": "un mouse", "rubro": "mouse"}]
    pedidos = []

    def create(**kw):
        pedidos.append(kw)
        if kw["messages"][-1]["content"].startswith("REVISION"):
            return T_resp(json.dumps({"piezas": corregidas}))
        return m._create(**kw)
    m.chat.completions.create = create
    r = _turno("busco un mouse que no sea Genius")
    ultima = [x for x in r["llamadas"] if x["herramienta"] == "buscar"][-1]
    assert excluye[0] in ultima["args"]["condiciones"]


def T_resp(cont):
    return NS(choices=[NS(message=NS(content=cont))],
              usage=NS(prompt_tokens=100, completion_tokens=10, prompt_tokens_details=None))


def test_saber_general_y_lo_que_no_se_vende_llevan_lo_que_vende_la_tienda(monkeypatch):
    """K19 "que tipo de productos venden?" y K12 "y algo parecido?" despues de celulares."""
    _con(monkeypatch, _Modelo([{"n": 1, "tipo": "explicar", "texto": "que venden?"},
                               {"n": 2, "tipo": "buscar", "texto": "celulares", "rubro": T.NO_LO_VENDE}]))
    r = _turno("que venden? tenes celulares?")
    vende = [h.get("la_tienda_vende") for h in r["hechos"] if h.get("tipo") in ("explicar", "buscar")]
    assert len(vende) == 2 and all("tablet" in v and "mouse" in v for v in vende)


def test_lo_que_respondio_el_mas_caro_es_lo_elegido_y_el_resto_de_la_lista_no():
    """K18: "el mas caro" mostro cinco notebooks; "sumame uno de cada uno" suma el primero."""
    busq = [({"tipo": "buscar", "orden": {"campo": "precio_ars", "direccion": "max"}},
             {"filas": [{"id": "NOT0160", "variantes": [{"id": "NOT0160"}, {"id": "NOT0162"}]}, {"id": "NOT0157"}]}),
            ({"tipo": "buscar", "rubro": "mouse"}, {"filas": [{"id": "MOU0009"}]})]
    assert T.respondidos(busq) == ["NOT0160", "NOT0162"]
    from app.core.respuesta import RESPUESTA
    memoria = (f"- NOT0160: Notebook Asus, $3.100.500{RESPUESTA}\n- NOT0157: Notebook Asus Ryzen, $2.827.000\n"
               f"1. MOU0023: Mouse Genius DX-110 Negro, $8.500{RESPUESTA} / MOU0024: Mouse Genius DX-110 Blanco")
    items = [{"producto": i, "cantidad": 1} for i in ("NOT0160", "NOT0157", "NOT0124", "MOU0023")]
    assert [i["producto"] for i in T._elegidos(items, [], memoria, TIENDA)] == ["NOT0160", "MOU0023"]


def test_la_memoria_marca_lo_que_respondio():
    from app.core import respuesta as R
    fichas = [{"id": "NOT0160", "nombre": "Notebook Asus ROG Strix G16", "precio": "$3.100.500"},
              {"id": "NOT0157", "nombre": "Notebook Asus ROG Strix G16 Ryzen", "precio": "$2.827.000"}]
    vistos = R._vistos_al_dia([], fichas, "Te paso.", 1, TIENDA, ["NOT0160"])
    assert [v.get("respuesta", False) for v in vistos] == [True, False]


# ══ LOS GUIONES DE MEMORIA grabados con DeepSeek, `vara_guiones.json` (2-oct) ══

def test_las_palabras_cortas_juntas_nombran_un_modelo():
    """Guion 30: "g pro x" quedaba en "pro" y ganaba una memoria Crucial Pro."""
    r = A.ejecutar("producto", {"nombre": "g pro x"}, TIENDA)
    assert r["veredicto"] == "ambiguo"
    assert {f["id"][:3] for f in r["filas"]} == {"MOU", "AUR"}


def test_el_nombre_exacto_del_catalogo_certifica_aunque_otro_lo_contenga():
    assert T._certificado("Auriculares Logitech G Pro X Negro", TIENDA, []) == "AUR0005"


def test_la_palabra_mas_larga_del_modelo_alcanza_para_nombrarlo():
    """Guion 32: "stinger 2" es el "Cloud Stinger 2" y la cuenta no lo tira."""
    A.CLIENTE_DIJO.set("sumale a cada uno unos auriculares stinger 2 negro")
    items = [{"producto": "MOU0001", "cantidad": 1}, {"producto": "AUR0003", "cantidad": 1},
             {"producto": "TEC0003", "cantidad": 1}]
    assert [i["producto"] for i in T._elegidos(items, [], "", TIENDA)] == ["AUR0003"]


def test_producto_con_cantidad_trae_el_subtotal():
    """Guion 52: "sumame 3 de esos"."""
    pz = {"n": 1, "tipo": "producto", "texto": "sumame 3", "producto": "Teclado Genius KB-110X Blanco", "cantidad": 3}
    h, args = T.a_herramienta(pz)
    r = A.ejecutar(h, args, TIENDA)
    assert r["filas"][0]["subtotal"] == "$36.000"


def test_no_se_pregunta_el_color_entre_lo_que_no_hay():
    """Guion 52: el KB-110X negro no tiene stock; el blanco es el unico."""
    A.CLIENTE_DIJO.set("lo llevo")
    r = A.ejecutar("reservar", {"producto": "TEC0020", "cantidad": 2}, TIENDA)
    assert r["veredicto"] == "listo_para_cerrar"


def test_una_repregunta_con_tema_lleva_lo_que_dice_la_tienda():
    """Guion 32: "como pago" leido como falta el medio de pago."""
    h, args = T.a_herramienta({"n": 1, "tipo": "repreguntar", "texto": "como pago", "tema": "formas_pago",
                               "falta": "medio de pago"})
    assert h == "politica" and "formas pago" in args["pregunta"]


def test_lo_ambiguo_de_la_cuenta_dice_el_precio_de_cada_uno():
    """Guion 28: "sumame el HyperX Cloud II" en dos colores."""
    r = A.ejecutar("cuenta", {"items": [{"producto": "Auriculares HyperX Cloud II", "cantidad": 1}]}, TIENDA)
    assert "125.500" in json.dumps(r, ensure_ascii=False)


# ══ PRODUCCION, 3-oct: "el teclado no figura en nuestro catalogo" ══════════

def test_el_aviso_de_articulos_dice_que_la_tienda_si_vende_lo_que_quedo_fuera(monkeypatch):
    msg = "dos mouse y dos memorias. un mouse y una memoria a Rosario, un teclado y un mouse a Concordia. 70/30"
    _con(monkeypatch, _Modelo(_k20_piezas(), banderas={"pide_total": True}))
    r = _turno(msg)
    aviso = json.dumps(r["hechos"], ensure_ascii=False)
    assert "la tienda si vende teclado" in aviso


def test_no_tenes_teclados_lleva_lo_que_vende_la_tienda(monkeypatch):
    _con(monkeypatch, _Modelo([{"n": 1, "tipo": "verificar", "texto": "no tenes teclados", "tema": "stock_disponibilidad"}],
                              banderas={"afirma_algo": True}))
    r = _turno("me confundi, no tenes teclados")
    assert "teclado" in r["hechos"][0]["la_tienda_vende"]


# ══ 7-oct: los arreglos de la vara compleja grabada en vivo ═════════════════

def test_un_modelo_sin_color_es_la_ficha_que_el_bot_ya_mostro():
    """K18: "la ROG Strix G16" nombra tres colores al mismo precio. La charla
    mostro el Gris primero: es ese. Sin lo mostrado, sigue siendo una duda."""
    nombre = "Notebook Asus ROG Strix G16 Core i7 16GB 1TB SSD"
    assert T._certificado(nombre, TIENDA, []) == nombre
    assert T._certificado(nombre, TIENDA, [], ["MOU0023", "NOT0160", "NOT0162", "NOT0161"]) == "NOT0160"
    assert T._certificado(nombre, TIENDA, [], ["NOT0162"]) == "NOT0162"


def test_el_mas_barato_de_esos_se_elige_en_la_busqueda_del_cliente(monkeypatch):
    """K17: la busqueda trajo mas teclados que los cuatro mostrados. Con
    sobre_lo_buscado la pieza hereda las condiciones de esa busqueda y el
    buscador da el mas barato de todos, no el modelo mirando la lista."""
    memoria = ("LO ULTIMO QUE BUSCO EL CLIENTE, como se interpreto:\n"
               "buscar teclado, marca no_contiene Genius, marca no_contiene Logitech")
    pz = T._sobre_lo_buscado([{"n": 1, "tipo": "buscar", "texto": "el mas barato de esos", "rubro": "teclado",
                               "orden": {"campo": "precio_ars", "direccion": "min"}, "sobre_lo_buscado": True}],
                             memoria)
    assert {c["valor"] for c in pz[0]["condiciones"]} == {"Genius", "Logitech"}
    sin_marca = T._sobre_lo_buscado([{"n": 1, "tipo": "buscar", "rubro": "teclado"}], memoria)
    assert "condiciones" not in sin_marca[0]
    assert T.busquedas_vigentes("buscar toda la tienda, orden precio_ars max") == [{"rubro": "", "condiciones": []}]


def test_el_renglon_del_envio_dice_a_donde_va(firestore_doble):
    """M10: el cliente leia "Envio: $7.000" sin saber de que envio era."""
    from app.core.calculadora import _label_extra
    assert _label_extra({"concepto": "envio", "modalidad": "fijo", "monto": 7000, "lugar": "Rosario"}) \
        == "Envio a Rosario: $7.000"
    assert _label_extra({"concepto": "envio", "modalidad": "fijo", "monto": 7000, "destinos": 2}) \
        == "Envio (2 envios): $7.000"


def test_sin_pieza_cuenta_no_hay_total_aunque_diga_en_total(monkeypatch):
    """K01: "en total serian cuatro articulos" es cuantos son. El total pedido
    lo dicen las piezas: sin cuenta no se arma una ni se disculpa por ella."""
    _con(monkeypatch, _Modelo([
        {"n": 1, "tipo": "buscar", "texto": "los dos mas baratos", "cantidad": 2,
         "orden": {"campo": "precio_ars", "direccion": "min"}},
        {"n": 2, "tipo": "politica", "texto": "medios de pago", "tema": "formas_pago"}]))
    r = _turno("dame el precio de los dos articulos mas baratos, en total serian dos, despues te digo el envio")
    assert not any(x["herramienta"] in ("cuenta", "total_general") for x in r["llamadas"])


# ══ 7-oct, K21: el pedido lo pone el codigo ═════════════════════════════════

_MULTI = ("LOS PRESUPUESTOS POR DESTINO que ya le pasaste, y un total general:\n"
          "- Córdoba capital: 1x AUR0019 Auriculares Redragon Zeus X Negro, 1x MOU0023 Mouse Genius DX-110 Negro\n"
          "- Posadas: 1x AUR0019 Auriculares Redragon Zeus X Negro, 1x RAM0001 Memoria\n"
          "- Concordia: 1x MOU0023 Mouse Genius DX-110 Negro, 1x RAM0001 Memoria, 1x TEC0020 Teclado\n")


def test_el_pedido_vigente_sale_de_la_memoria():
    assert [(b["destino"], len(b["items"])) for b in T.pedido_vigente(_MULTI)] == \
        [("Córdoba capital", 2), ("Posadas", 2), ("Concordia", 3)]
    uno = "EN EL PEDIDO, tal como se conto: 2x MOU0029 Mouse Logitech G305\nEnvia a: Rosario"
    assert T.pedido_vigente(uno) == [{"destino": "Rosario", "items": [{"producto": "MOU0029", "cantidad": 2}]}]
    assert T.pedido_vigente("") == []


def test_el_nombre_sobre_el_pedido_reserva_todo_y_da_el_total_general(monkeypatch):
    """K21: "mi nombre es Julio" despues del presupuesto. Se reservan los siete
    articulos, no el primero, y el total general es el de los tres destinos."""
    _con(monkeypatch, _Modelo([{"n": 1, "tipo": "comprar", "texto": "da su nombre", "sobre_el_pedido": True}]))
    r = _turno("Mi nombre es Julio", memoria=_MULTI)
    reservas = [x for x in r["llamadas"] if x["herramienta"] == "reservar"]
    assert sum(x["args"]["cantidad"] for x in reservas) == 7
    # el presupuesto aceptado ya le nombro cada color: no se vuelve a preguntar
    assert {x["vuelve"]["veredicto"] for x in reservas} == {"listo_para_cerrar"}
    tg = next(x for x in r["llamadas"] if x["herramienta"] == "total_general")["vuelve"]
    assert tg["total_ars"] == 237000


def test_el_reparto_sobre_el_pedido_va_sobre_el_total_general(monkeypatch):
    """K21: "70 por ciento transferencia" no rearma el pedido: es sobre los tres destinos."""
    _con(monkeypatch, _Modelo([{"n": 1, "tipo": "cuenta", "texto": "70 transferencia", "sobre_el_pedido": True,
                                "items": [{"producto": "MOU0023", "cantidad": 2}],
                                "reparto_pago": [{"medio": "transferencia", "porcentaje": 70},
                                                 {"medio": "mercado pago", "porcentaje": 30}]}]))
    r = _turno("Color indistinto 70 por ciento transferencia", memoria=_MULTI)
    tg = next(x for x in r["llamadas"] if x["herramienta"] == "total_general")["vuelve"]
    assert tg["total_ars"] == 237000
    assert [p["monto_ars"] for p in tg["split_pago"]["partes"]][1] == 71100
