"""EL AGENTE Y EL TURNO NUEVO — `app/core/agente.py` y `respuesta.procesar_turno`.

La vara del camino que reemplazo al interprete el 26-sep-2026. Sin modelo de
verdad: un modelo de mentira devuelve llamadas y textos fijos, y lo que se mide
es lo que hace el codigo con eso. El modelo real se mide en el banco con
`sonda_charlas.py --vara 58 --camino agente`.
"""
import asyncio
import json
from types import SimpleNamespace as NS

import pytest

from app.core import agente as A
from app.core import respuesta as R

TIENDA = "verifika_prod"


@pytest.fixture(autouse=True)
def _doble(firestore_doble):
    from app.core.contexto_turno import set_current_tienda
    from app.core.filtros_catalogo import limpiar_cache
    set_current_tienda(TIENDA)
    limpiar_cache()
    return firestore_doble


# ── EL MODELO DE MENTIRA ─────────────────────────────────────────────────────

def _llamada(herr, **args):
    return NS(id=f"c_{herr}", function=NS(name=herr, arguments=json.dumps(args)),
              model_dump=lambda n=herr, a=args: {"id": f"c_{n}", "type": "function",
                                                   "function": {"name": n, "arguments": json.dumps(a)}})


def _resp(texto="", llamadas=None):
    return NS(choices=[NS(message=NS(content=texto, tool_calls=llamadas or None))],
              usage=NS(prompt_tokens=100, prompt_tokens_details=None))


class Modelo:
    """Devuelve en orden las respuestas del guion y anota lo que recibio."""

    def __init__(self, guion):
        self.guion, self.pedidos = list(guion), []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.pedidos.append(kw)
        return self.guion.pop(0) if self.guion else _resp("listo")


@pytest.fixture
def modelo(monkeypatch):
    def poner(guion):
        m = Modelo(guion)
        monkeypatch.setattr("app.core.llm_reintento._cliente", lambda: m)
        return m
    return poner


def _turno(historial, mensaje, memoria=""):
    return asyncio.run(A.turno(historial, mensaje, TIENDA, "t", memoria=memoria))


# ── EL INDICE Y LAS HERRAMIENTAS ─────────────────────────────────────────────

def test_el_indice_ubica_la_jerga_por_los_alias():
    assert A.ubicar("el coso de internet", "rubros", TIENDA)[0] == "router"
    assert A.ubicar("disco externo", "rubros", TIENDA)[0] == "almacenamiento externo"
    assert A.ubicar("me vino roto", "temas", TIENDA)[0] == "defectuoso"


def test_un_filtro_con_el_dato_en_otro_campo_se_repite_donde_vive():
    """DDR5 no esta en `ram` sino en el nombre. Un vacio el modelo lo lee como
    'no tenemos', y habia nueve."""
    r = A.h_buscar(TIENDA, rubro="memoria ram",
                   condiciones=[{"campo": "ram", "operador": "contiene", "valor": "DDR5"}])
    assert r["veredicto"] != "no_existe"
    assert all("DDR5" in f["nombre"] for f in r["filas"])
    assert "nota" in r


def test_varias_condiciones_que_juntas_dan_cero_se_buscan_por_separado():
    """'G305' y 'G203' en el nombre a la vez no lo cumple nadie: el modelo dijo
    que no tenia ninguno de los dos."""
    r = A.h_buscar(TIENDA, rubro="mouse", condiciones=[
        {"campo": "nombre", "operador": "contiene", "valor": "G305"},
        {"campo": "nombre", "operador": "contiene", "valor": "G203"}])
    assert "aviso" in r and len(r["por_condicion"]) == 2


def test_la_cuenta_suma_el_envio_y_la_hace_la_calculadora():
    r = A.h_cuenta(TIENDA, items=[{"producto": "G305 negro", "cantidad": 1}], destino="Rosario")
    assert r["cuenta"]["total_ars"] == 87500
    assert r["envio"]["filas"][0]["monto_ars"] == 7000


def test_reservar_certifica_el_producto_y_pide_el_nombre():
    r = A.h_reservar(TIENDA, producto="G203 negro", cantidad=1)
    assert r["veredicto"] == "listo_para_cerrar" and r["id"] == "MOU0001"
    assert "nombre" in r["falta"]


def test_el_prompt_no_crece_con_el_catalogo():
    """Lo que viaja fijo son las reglas, las herramientas y los rubros: ningun
    producto, ninguna marca, ningun precio."""
    s = A.sistema(TIENDA) + json.dumps(A.esquema(TIENDA))
    assert "G305" not in s and "$" not in s
    assert len(s) < 9000


# ── EL LOOP ──────────────────────────────────────────────────────────────────

def test_el_agente_consulta_lee_y_contesta(modelo):
    m = modelo([_resp(llamadas=[_llamada("producto", nombre="K120 negro")]),
                _resp("El K120 negro sale $14.500.")])
    r = _turno([], "cuanto sale el K120 negro?")
    assert r["texto"] == "El K120 negro sale $14.500."
    assert [x["herramienta"] for x in r["llamadas"]] == ["producto"]
    assert m.pedidos[1]["messages"][-1]["role"] == "tool"


def test_la_misma_consulta_dos_veces_no_se_vuelve_a_ejecutar(modelo):
    ll = _llamada("envio", destinos=["Rosario"])
    modelo([_resp(llamadas=[ll]), _resp(llamadas=[ll]), _resp("A Rosario sale $7.000.")])
    r = _turno([], "cuanto a rosario?")
    assert "aviso" in r["llamadas"][1]["vuelve"]


def test_la_ultima_vuelta_obliga_a_contestar(modelo):
    """Un modelo que no para de consultar no deja al bot mudo: la ultima vuelta
    va sin herramientas habilitadas."""
    m = modelo([_resp(llamadas=[_llamada("politica", pregunta=f"p{i}")]) for i in range(A.MAX_VUELTAS)]
               + [_resp("te cuento")])
    r = _turno([], "hola")
    assert r["texto"] == "te cuento"
    assert m.pedidos[-1]["tool_choice"] == "none"


def test_lo_fijo_va_adelante_y_lo_que_cambia_atras(modelo):
    """El caché del proveedor reusa el comienzo idéntico: el sistema primero,
    después la memoria, la charla y el mensaje."""
    m = modelo([_resp("dale")])
    _turno([{"role": "user", "content": "hola"}, {"role": "assistant", "content": "que tal"}],
           "y el G305?", memoria="Envia a: Rosario")
    msgs = m.pedidos[0]["messages"]
    assert msgs[0]["content"] == A.sistema(TIENDA)
    assert "Rosario" in msgs[1]["content"]
    assert msgs[-1] == {"role": "user", "content": "y el G305?"}


# ── EL TURNO ENTERO ──────────────────────────────────────────────────────────

def _agente_fijo(monkeypatch, texto, llamadas):
    async def falso(historial, mensaje, tienda_id, trace_id="", memoria=""):
        return {"texto": texto, "llamadas": llamadas, "uso": []}
    monkeypatch.setattr(A, "turno", falso)


def _procesar(uid, msg):
    return asyncio.run(R.procesar_turno(uid, msg, TIENDA, "whatsapp", "t"))


def test_la_plata_que_ninguna_herramienta_devolvio_no_sale(monkeypatch):
    _agente_fijo(monkeypatch, "El K120 sale $99.999.",
                 [{"herramienta": "producto", "args": {}, "vuelve": {"filas": [
                     {"id": "TEC0029", "nombre": "Teclado Logitech K120 Negro", "precio": "$14.500"}]}}])
    from app.config import get_settings
    texto = _procesar("t_agente_plata", "cuanto sale el k120?")
    assert get_settings().VERIFIKA_FALLBACK_MESSAGE in texto and "99.999" not in texto


def test_sin_texto_del_modelo_el_bot_no_queda_mudo(monkeypatch):
    _agente_fijo(monkeypatch, "", [])
    assert _procesar("t_agente_mudo", "hola").strip()


def test_la_cuenta_y_el_destino_quedan_en_la_charla(monkeypatch):
    cuenta = A.h_cuenta(TIENDA, items=[{"producto": "G305 negro", "cantidad": 1}], destino="Rosario")
    _agente_fijo(monkeypatch, "Con el envio a Rosario, el total es $87.500.",
                 [{"herramienta": "cuenta", "args": {}, "vuelve": cuenta}])
    _procesar("t_agente_cuenta", "mandamelo a rosario, cuanto seria?")
    from app.storage.firestore_client import get_conversation
    conv = get_conversation("t_agente_cuenta", tienda_id=TIENDA)
    assert "87.500" in (conv.get("ultimo_presupuesto") or "")
    assert conv.get("ultima_localidad")
    assert conv["carrito_vigente"][0]["id"] == "MOU0029"


def test_reservar_es_la_señal_de_compra_para_el_cierre():
    assert R._senal([{"herramienta": "reservar", "vuelve": {"veredicto": "listo_para_cerrar"}}],
                    "dale")["intencion"] == "decision_compra"
    assert R._senal([{"herramienta": "buscar", "vuelve": {}}], "que teclados hay?")["intencion"] == "exploracion"


def test_lo_que_el_cliente_vio_queda_en_la_memoria(monkeypatch):
    _agente_fijo(monkeypatch, "El G203 negro sale $37.500.",
                 [{"herramienta": "producto", "args": {}, "vuelve": {"filas": [
                     {"id": "MOU0001", "nombre": "Mouse Logitech G203 Lightsync Negro", "precio": "$37.500"}]}}])
    _procesar("t_agente_vistos", "cuanto sale el g203 negro?")
    from app.storage.firestore_client import get_conversation
    conv = get_conversation("t_agente_vistos", tienda_id=TIENDA)
    assert [p["id"] for p in conv["productos_vistos"]] == ["MOU0001"]
    assert "MOU0001" in R._memoria_texto(conv)
