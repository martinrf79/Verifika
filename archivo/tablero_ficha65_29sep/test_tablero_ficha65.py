"""EL TABLERO — `app/core/tablero.py`, FICHA 65.

La traduccion se valida contra el vocabulario de la tienda antes de ejecutarse.
Sin modelo de verdad: lo que se mide es lo que hace el codigo con las piezas.
El modelo real se mide en el banco, la vara de las 58 por el clon.
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
    T._TABLEROS.clear()
    A.CLIENTE_DIJO.set("")
    return firestore_doble


def _errores(piezas, mensaje="x"):
    return T.validar(piezas, mensaje, TIENDA)


# ── EL VOCABULARIO DE LA TIENDA ──────────────────────────────────────────────

def test_las_fichas_dicen_la_clase_de_cada_dato():
    f = A.indice(TIENDA)["fichas"]
    assert f["resistencia_agua"]["tipo"] == "si_no"
    assert f["precio_ars"]["tipo"] == "magnitud"
    assert f["switch_teclado"]["tipo"] == "lista"
    # "8GB GDDR6" en placas de video no hace de caracteristicas_extra una medida
    assert f["caracteristicas_extra"]["tipo"] == "texto"
    assert "dimensiones" not in A.ordenables(TIENDA)
    assert "peso_gramos" in A.ordenables(TIENDA)


def test_el_tablero_trae_rubros_temas_y_datos():
    t = T.tablero(TIENDA)
    assert "RUBROS:" in t and "TEMAS" in t and "DATOS DE CADA PRODUCTO" in t
    assert "- defectuoso:" in t
    assert "resistencia_agua (si o no)" in t


# ── VALIDAR ──────────────────────────────────────────────────────────────────

def test_una_traduccion_que_cierra_no_da_errores():
    assert _errores([{"n": 1, "accion": "buscar", "rubro": "parlante",
                      "condiciones": [{"campo": "resistencia_agua", "operador": "igual", "valor": "si"}]}]) == []


def test_un_rubro_que_no_existe_se_devuelve():
    e = _errores([{"n": 1, "accion": "buscar", "rubro": "heladera"}])
    assert len(e) == 1 and "heladera" in e[0]


def test_ordenar_por_una_etiqueta_se_devuelve_con_lo_que_si_ordena():
    """"El monitor mas grande" ordenaba por dimensiones y afirmaba 32 pulgadas
    con uno de 49."""
    e = _errores([{"n": 1, "accion": "buscar", "rubro": "monitor",
                   "orden": {"campo": "dimensiones", "direccion": "max"}}])
    assert len(e) == 1 and "no se puede ordenar" in e[0] and "precio_ars" in e[0]


def test_un_valor_fuera_de_la_lista_cerrada_es_no_tengo():
    """"Que las teclas hagan click" con un solo switch en la tienda."""
    e = _errores([{"n": 1, "accion": "buscar", "rubro": "teclado",
                   "condiciones": [{"campo": "switch_teclado", "operador": "igual", "valor": "switch blue"}]}])
    assert any("los unicos son" in x and "no_tengo" in x for x in e)


def test_un_valor_que_el_rubro_no_escribe_se_devuelve_con_como_lo_escribe():
    """"SSD de 1 tera": el modelo copio "1tb ssd", que es como lo escriben las
    notebooks, y volvieron dos de cinco."""
    e = _errores([{"n": 1, "accion": "buscar", "rubro": "ssd",
                   "condiciones": [{"campo": "almacenamiento", "operador": "igual", "valor": "1tb ssd"}]}])
    assert len(e) == 1 and "la fuente escribe" in e[0] and "1tb" in e[0]


def test_un_tema_que_no_existe_se_devuelve():
    e = _errores([{"n": 1, "accion": "politica", "tema": "roturas"}])
    assert len(e) == 1 and "roturas" in e[0]


def test_un_rubro_no_es_un_producto():
    """"El mouse tiene garantia?" elegia un mouse cualquiera como si fuera el
    del cliente."""
    e = _errores([{"n": 1, "accion": "dato", "producto": "mouse", "dato": "garantia_meses"}])
    assert len(e) == 1 and "preguntar" in e[0]


def test_el_reparto_en_fracciones_se_pasa_a_porcentaje():
    """Mitad y mitad llego como 0.5 y el bot invento que no se puede dividir."""
    p = [{"n": 1, "accion": "sumar", "items": [{"producto": "G203"}],
          "reparto": [{"medio": "transferencia", "porcentaje": 0.5}, {"medio": "mercado pago", "porcentaje": 0.5}]}]
    assert _errores(p, "mitad transferencia y mitad mercado pago") == []
    assert [x["porcentaje"] for x in p[0]["reparto"]] == [50, 50]


def test_un_reparto_que_no_suma_cien_se_devuelve():
    p = [{"n": 1, "accion": "sumar", "items": [{"producto": "G203"}],
          "reparto": [{"medio": "transferencia", "porcentaje": 70}, {"medio": "mercado pago", "porcentaje": 20}]}]
    assert any("suma 90" in x for x in _errores(p))


def test_una_marca_excluida_en_el_mensaje_tiene_que_viajar():
    """"Que no sea Logitech ni Redragon": el modelo perdio las dos y el bot
    dijo que solo trabaja con Logitech."""
    msg = "quiero un mouse que no sea logitech ni redragon"
    assert T._excluidas(msg, TIENDA) == ["Logitech", "Redragon"]
    e = _errores([{"n": 1, "accion": "buscar", "rubro": "mouse"}], msg)
    assert len(e) == 2
    ok = [{"n": 1, "accion": "buscar", "rubro": "mouse", "condiciones": [
        {"campo": "marca", "operador": "no_contiene", "valor": "logitech"},
        {"campo": "marca", "operador": "no_contiene", "valor": "redragon"}]}]
    assert _errores(ok, msg) == []


def test_un_destino_del_mensaje_sin_pieza_que_lo_mande_se_devuelve():
    e = _errores([{"n": 1, "accion": "nombrar", "producto": "G203"}], "cuanto sale el G203 mandado a Rosario")
    assert any("Rosario" in x for x in e)


# ── EJECUTAR ─────────────────────────────────────────────────────────────────

def test_un_nombre_trae_marca_o_modelo():
    assert T._es_un_nombre("teclado redragon kumara", TIENDA)
    assert T._es_un_nombre("G203", TIENDA)
    assert not T._es_un_nombre("teclado", TIENDA)


def test_la_cuenta_toma_lo_que_encontro_otra_pieza_y_el_nombre_gana():
    por_n = {1: {"filas": [{"id": "MOU0023"}]}}
    p = {"accion": "sumar", "items": [{"de_pieza": 1, "producto": "mouse"},
                                      {"de_pieza": 1, "producto": "mouse g203", "cantidad": 2}]}
    items = T._resolver_items(p, por_n, TIENDA)["items"]
    assert items == [{"producto": "MOU0023", "cantidad": 1}, {"producto": "mouse g203", "cantidad": 2}]


def test_dio_lee_el_veredicto():
    assert T._dio({"veredicto": "existe", "filas": [{"id": "x"}]})
    assert not T._dio({"veredicto": "no_existe", "filas": []})
    assert not T._dio({"compatibilidad": {"veredicto": "incompatible"}})


# ── EL TURNO, con un modelo de mentira ───────────────────────────────────────

def _llamada(piezas):
    args = json.dumps({"piezas": piezas})
    return NS(id="c1", function=NS(name="traducir", arguments=args),
              model_dump=lambda: {"id": "c1", "type": "function",
                                  "function": {"name": "traducir", "arguments": args}})


def _resp(texto="", llamadas=None):
    return NS(choices=[NS(message=NS(content=texto, tool_calls=llamadas))],
              usage=NS(prompt_tokens=100, prompt_tokens_details=None))


class Modelo:
    def __init__(self, guion):
        self.guion, self.pedidos = list(guion), []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.pedidos.append(kw)
        return self.guion.pop(0)


def _turno(monkeypatch, guion, mensaje):
    m = Modelo(guion)
    monkeypatch.setattr("app.core.llm_reintento._cliente", lambda: m)
    return m, asyncio.run(T.turno([], mensaje, TIENDA, "t"))


def test_la_primera_llamada_solo_puede_traducir_y_la_ultima_solo_redactar(monkeypatch):
    m, r = _turno(monkeypatch, [_resp(llamadas=[_llamada([{"n": 1, "accion": "politica", "tema": "defectuoso"}])]),
                                _resp("Lo cambiamos sin costo.")], "si me llega roto que hago")
    assert m.pedidos[0]["tool_choice"] == "required"
    assert m.pedidos[-1]["tool_choice"] == "none"
    assert r["texto"] == "Lo cambiamos sin costo."
    assert r["llamadas"][0]["herramienta"] == "politica"
    assert "defectuoso" in json.dumps(r["llamadas"][0]["vuelve"], ensure_ascii=False)


def test_lo_que_no_cierra_vuelve_al_modelo_una_vez(monkeypatch):
    mala = _llamada([{"n": 1, "accion": "buscar", "rubro": "monitor",
                      "orden": {"campo": "dimensiones", "direccion": "max"}}])
    buena = _llamada([{"n": 1, "accion": "buscar", "rubro": "monitor"}])
    m, r = _turno(monkeypatch, [_resp(llamadas=[mala]), _resp(llamadas=[buena]), _resp("ok")],
                  "el monitor mas grande")
    assert len(m.pedidos) == 3
    assert "no se puede ordenar" in m.pedidos[1]["messages"][-1]["content"]
    assert r["piezas"][0].get("orden") is None


def test_no_tengo_lo_confirma_el_catalogo(monkeypatch):
    """"No lo tenemos" es un veredicto del codigo, regla 10.0: si el catalogo
    lo tiene, la pieza pasa a ser la busqueda."""
    m, r = _turno(monkeypatch, [_resp(llamadas=[_llamada([{"n": 1, "accion": "no_tengo", "texto": "G305"}])]),
                                _resp("ok")], "tenes el G305?")
    assert r["llamadas"] and r["llamadas"][0]["herramienta"] == "buscar"
    m, r = _turno(monkeypatch, [_resp(llamadas=[_llamada([{"n": 1, "accion": "no_tengo", "texto": "heladeras"}])]),
                                _resp("ok")], "vendes heladeras?")
    assert r["llamadas"] == []


def test_una_pieza_dependiente_no_corre_si_la_otra_dio_al_reves(monkeypatch):
    piezas = [{"n": 1, "accion": "nombrar", "producto": "G203"},
              {"n": 2, "accion": "nombrar", "producto": "G305", "depende_de": 1, "si": "no_hay"}]
    m, r = _turno(monkeypatch, [_resp(llamadas=[_llamada(piezas)]), _resp("ok")],
                  "si no hay G203 pasame el G305")
    assert [x["args"]["nombre"] for x in r["llamadas"]] == ["G203"]
    assert "no_corrio" in m.pedidos[-1]["messages"][-1]["content"] or \
        "no_corrio" in json.dumps(m.pedidos[-1]["messages"], ensure_ascii=False)
