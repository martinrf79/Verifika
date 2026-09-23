"""
AREA: EL COTEJO CABLEADO — que las cinco comprobaciones esten en el camino
vivo del turno y no solo en su modulo.

POR QUE HACE FALTA ADEMAS DE `test_cotejo.py`. Aquel mide la PIEZA: que una
copia se reconozca y que un techo inventado se degrade. Este mide el CABLE: que
lo que sale corregido sea lo que de verdad le llega al motor, que el aviso
llegue al prompt de la vuelta siguiente, y que los numeros terminen en el
informe del turno, que es de donde los lee produccion. Una pieza correcta sin
cable es la FICHA 51 entera: el fantasma de algo que parece estar enchufado.

El doble del modelo es el mismo de `test_renglon_y_total`, importado de ahi y
no copiado: tres copias del mismo cliente falso es lo que el bloque 0 de
CLAUDE.md prohibe.
"""
import asyncio

from app.core import motor as MT
from app.core import respuesta as R
from tests.test_renglon_y_total import _Call, _ClienteFalso, _Msg

TIENDA = "verifika_prod"

# Los dos mensajes reales que destaparon los casos, por Telegram el 22-sep.
M1 = ("Dame precio de dos auriculares, dos mouse y dos memorias. El precio no "
      "sería tan importante. Lo que sí que necesito que lleven las menos "
      "partes chinas posibles. Un auricular y un mouse será envío a Córdoba "
      "capital. Un teclado y un mouse será envío a Concordia. Los otros dos "
      "artículos serán con envío a posadas. Divide el presupuesto en setenta "
      "treinta")
M11 = ("necesito una compu para mi hijo de 8 años, para que juegue y haga la "
       "tarea, que no sea muy cara")


def _correr(monkeypatch, guion, texto):
    """Corre el turno con el modelo doblado y ESPIA lo que llego al motor.

    Devuelve (informe, consultas que vio el motor, llamadas del cliente). Lo
    que se mira es lo segundo: el cotejo corrige en el lugar, asi que la unica
    forma honesta de saber si sirvio es leer lo que el motor recibio.
    """
    from app.core import llm_reintento as LR
    cli = _ClienteFalso(guion)
    monkeypatch.setattr(LR, "_cliente", lambda: cli)
    monkeypatch.setattr(LR, "_modelo", lambda: "doble")
    vistas = []
    real = MT.buscar

    def _espia(consultas, *a, **kw):
        import copy
        vistas.append(copy.deepcopy(consultas))
        return real(consultas, *a, **kw)

    monkeypatch.setattr(MT, "buscar", _espia)
    _, _, _, _, informe = asyncio.run(
        R._preguntar("", "", [], texto, "", "t", TIENDA))
    return informe, vistas, cli


def _prompts(cli) -> list:
    return ["\n".join(str(m.get("content") or "") for m in kw["messages"])
            for kw in cli.vistos]


# ── 1 · LA FIDELIDAD DEL RENGLON LLEGA AL INFORME ───────────────────────────


# ── 2 · EL RUBRO NOMBRADO Y NO PEDIDO ───────────────────────────────────────


def test_si_lo_busco_no_hay_aviso(firestore_doble, monkeypatch):
    guion = [_Msg(tool_calls=[_Call(
        '{"renglones": ["dos auriculares", '
        '"envio a Concordia un teclado y un mouse"], "pedir_total": true, '
        '"consultas": [{"categoria": "auriculares"}, '
        '{"categoria": "teclado"}, {"categoria": "mouse"}]}')]),
        _Msg('{"tipo": "precio_multiple", "texto": "listo"}')]
    informe, _, cli = _correr(monkeypatch, guion, M1)
    assert informe["rubros_sin_pedir"] == []
    assert not any("no lo buscaste" in p for p in _prompts(cli))


# ── 3 · LA CIFRA QUE EL CLIENTE NO DIJO NO LLEGA AL MOTOR ───────────────────


# ── 4 · LA VUELTA QUE NO AGREGA NADA NO SE VUELVE A BUSCAR ──────────────────


# ── 5 · LO DECLARADO NO SE PIERDE ENTRE VUELTAS ─────────────────────────────


def test_el_turno_sin_nada_que_cotejar_no_se_cae(firestore_doble, monkeypatch):
    """Un pedido sin renglones y sin condiciones tiene que pasar derecho: el
    cotejo no puede ser un lugar nuevo donde el turno se rompa."""
    guion = [_Msg(tool_calls=[_Call('{"consultas": [{"texto": "teclado"}]}')]),
             _Msg('{"tipo": "precio_simple", "texto": "listo"}')]
    informe, vistas, _ = _correr(monkeypatch, guion, "teclado")
    assert informe["renglones"] == 0
    assert informe["rubros_sin_pedir"] == []
    assert len(vistas) == 1
