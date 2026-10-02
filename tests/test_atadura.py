"""LA ATADURA — el vocabulario de la tienda lo garantiza el codigo, con cualquier modelo.

Hasta el 2-oct-2026 la lista cerrada la garantizaba el esquema estricto del
proveedor. Un modelo que da JSON a secas podia nombrar un rubro, un campo o un
tema que la tienda no tiene, y un "no" en texto contaba como si. Aca se mide
`tablero.atar` sin modelo, y el turno con un modelo de mentira sin esquema.
"""
import asyncio
import json
from types import SimpleNamespace as NS

import pytest

from app.core import agente as A
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


def _atar(piezas):
    return T.atar(piezas, TIENDA)


def test_lo_que_ya_esta_en_la_lista_pasa_igual():
    pz = [{"n": 1, "tipo": "buscar", "texto": "mouse baratos", "rubro": "mouse", "cantidad": 2,
           "condiciones": [{"campo": "color", "operador": "contiene", "valor": "negro"}],
           "orden": {"campo": "precio_ars", "direccion": "min"}}]
    out, errores, corregidos = _atar(pz)
    assert out == pz and errores == [] and corregidos == []


def test_lo_mal_escrito_se_lleva_al_valor_de_la_lista():
    out, errores, corregidos = _atar([{"n": "1", "tipo": "Buscar", "texto": "x", "rubro": "Auricular",
                                       "cantidad": "2",
                                       "condiciones": [{"campo": "pais fabricacion", "operador": "Evita",
                                                        "valor": "china"}],
                                       "orden": {"campo": "precio", "direccion": "MIN"}}])
    p = out[0]
    assert (p["n"], p["tipo"], p["rubro"], p["cantidad"]) == (1, "buscar", "auriculares", 2)
    assert p["condiciones"] == [{"campo": "pais_fabricacion", "operador": "evita", "valor": "china"}]
    assert p["orden"] == {"campo": "precio_ars", "direccion": "min"}
    assert errores == [] and len(corregidos) == 6


def test_lo_que_no_existe_se_descarta_y_se_dice():
    out, errores, _ = _atar([{"n": 1, "tipo": "buscar", "texto": "drones", "rubro": "drones",
                              "condiciones": [{"campo": "autonomia_vuelo", "operador": "mayor", "valor": "20"}]},
                             {"n": 2, "tipo": "adivinar", "texto": "?"}])
    assert len(out) == 1, "la pieza sin tipo valido no corre"
    p = out[0]
    assert "rubro" not in p and p["producto"] == "drones", "sin rubro la busqueda va por el texto"
    assert p["condiciones"] == []
    assert len(errores) == 3 and all("no existe en la tienda" in e for e in errores)
    assert "mouse" in errores[0], "el error lleva los valores que valen"


def test_el_tema_que_no_existe_se_saca_y_la_politica_va_por_el_texto():
    out, errores, _ = _atar([{"n": 1, "tipo": "politica", "texto": "hacen factura A?", "tema": "zzz_qqq"}])
    assert "tema" not in out[0] and len(errores) == 1
    assert T.a_herramienta(out[0]) == ("politica", {"pregunta": "hacen factura A?"})


def test_los_numeros_en_texto_se_leen_y_el_entero_queda_entero():
    out, errores, _ = _atar([{"n": 1, "tipo": "cuenta", "texto": "total",
                              "items": [{"producto": "K120", "cantidad": "3"}, {"producto": ""}, "basura"],
                              "reparto_pago": [{"medio": "transferencia", "porcentaje": "70%"},
                                               {"medio": "tarjeta", "porcentaje": 30.5}],
                              "destinos": "Rosario", "depende_de": ["2", "x"]}])
    p = out[0]
    assert p["items"] == [{"producto": "K120", "cantidad": 3}]
    assert p["reparto_pago"] == [{"medio": "transferencia", "porcentaje": 70},
                                 {"medio": "tarjeta", "porcentaje": 30.5}]
    assert p["destinos"] == ["Rosario"] and p["depende_de"] == [2] and errores == []


def test_las_piezas_se_leen_con_o_sin_la_clave_y_con_texto_alrededor():
    assert T.piezas_de('{"piezas": [{"n": 1, "tipo": "charla"}]}') == [{"n": 1, "tipo": "charla"}]
    assert T.piezas_de('[{"n": 1, "tipo": "charla"}]') == [{"n": 1, "tipo": "charla"}]
    assert T.piezas_de('aca va: {"piezas": [{"tipo": "charla"}]} listo') == [{"tipo": "charla"}]
    assert T.piezas_de("no es json") == []


def test_un_no_en_texto_es_falso():
    b = T.banderas_de('{"pide_total": "no", "condicional": "si", "afirma_algo": true, "referencia_ambigua": "false"}')
    assert b["pide_total"] is False and b["condicional"] is True and b["afirma_algo"] is True
    assert b["referencia_ambigua"] is False and set(b) == set(T.BANDERAS)


class _SinEsquema:
    """Un modelo que da JSON a secas: el paso se reconoce por el prompt."""

    def __init__(self, primeras, corregidas):
        self.primeras, self.corregidas, self.pedidos = primeras, corregidas, []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.pedidos.append(kw)
        sis, ultimo = kw["messages"][0]["content"], kw["messages"][-1]["content"]
        if sis.startswith("Sos el interprete") and "partis" in sis:
            cont = json.dumps({"piezas": self.corregidas if ultimo.startswith("ATADURA") else self.primeras})
        elif sis.startswith("Sos el interprete"):
            cont = json.dumps({k: "no" for k in T.BANDERAS})
        else:
            cont = "listo"
        return NS(choices=[NS(message=NS(content=cont))],
                  usage=NS(prompt_tokens=100, completion_tokens=10, prompt_tokens_details=None))


def _turno_sin_esquema(monkeypatch, m, mensaje):
    monkeypatch.setattr(T, "_formato", lambda nombre, esquema: {"type": "json_object"})
    monkeypatch.setattr("app.core.llm_reintento._cliente", lambda: m)
    return asyncio.run(T.turno([], mensaje, TIENDA, trace_id="t"))


def test_sin_esquema_estricto_las_listas_van_en_el_prompt_y_lo_roto_vuelve_una_vez(monkeypatch):
    rota = [{"n": 1, "tipo": "buscar", "texto": "drones", "rubro": "drones"}]
    buena = [{"n": 1, "tipo": "buscar", "texto": "mouse", "rubro": "mouse"}]
    m = _SinEsquema(rota, buena)
    r = _turno_sin_esquema(monkeypatch, m, "tenes mouse?")
    interpretar = m.pedidos[0]["messages"][0]["content"]
    assert '"enum"' in interpretar and "memoria ram" in interpretar, "sin esquema estricto el vocabulario va al prompt"
    assert [u["paso"] for u in r["uso"]].count("atadura") == 1
    assert [x["args"].get("rubro") for x in r["llamadas"] if x["herramienta"] == "buscar"] == ["mouse"]


def test_si_sigue_roto_se_descarta_y_no_se_insiste(monkeypatch):
    rota = [{"n": 1, "tipo": "adivinar", "texto": "?"}]
    m = _SinEsquema(rota, rota)
    r = _turno_sin_esquema(monkeypatch, m, "hola")
    assert [u["paso"] for u in r["uso"]].count("atadura") == 1 and r["llamadas"] == []


def test_con_esquema_estricto_el_prompt_no_cambia():
    esquema = T.esquema_piezas(TIENDA)
    assert T._con_esquema("X", {"type": "json_schema"}, esquema) == "X"
