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
    async def falso(historial, mensaje, tienda_id, trace_id="", memoria=""):
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
