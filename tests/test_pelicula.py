"""LA PELICULA DEL TURNO — la sonda sobre produccion, para el agente (19-oct-2026; el agente, 30-oct).

QUE CUIDA ESTA VARA. La pelicula es una funcion PURA sobre los renglones del log: lo que decide QUE se ve del sistema
tiene que poder probarse sin red y sin credencial.

Y cuida la otra mitad, que es la que se rompe sola: los NOMBRES. El agente escribe `agente_turno`; la pelicula lo lee.
Si alguien renombra uno de los dos lados, la pelicula se queda muda sin que nadie lo note. Por eso cada evento que la
pelicula pide tiene que estar escrito en `app/`.
"""
import re
from pathlib import Path

from banco_pruebas.produccion import EVENTOS_PELICULA, pelicula


def _evs() -> list:
    """Un turno entero, tal como lo escribe `app/core/flujo/agente.py`."""
    return [
        {"event": "message_received", "trace_id": "abc123", "_t": "2026-10-30T15:29:15Z",
         "msg_preview": "me llevo el G305 negro, mandalo a Rosario"},
        {"event": "agente_turno", "trace_id": "abc123", "herramientas": ["buscar", "presupuesto"],
         "pide": '[{"consulta": "G305"}]', "hallazgos": [["dato", "12000"]], "corregido": True,
         "entrada": 3800, "salida": 160},
    ]


def test_la_pelicula_muestra_lo_que_pidio_y_lo_que_verifico():
    t = "\n".join(pelicula(_evs()))
    assert "me llevo el G305 negro" in t
    assert "HIZO      buscar, presupuesto · 3800+160 tokens" in t
    assert 'PIDIO     [{"consulta": "G305"}]' in t
    assert "VERIFICO  [['dato', '12000']] · corregido" in t


def test_un_error_se_ve_como_error():
    evs = _evs() + [{"event": "agente_cobro_error", "trace_id": "abc123", "error": "sin link"}]
    assert "AVISO     agente_cobro_error sin link" in "\n".join(pelicula(evs))


def test_un_turno_que_se_cayo_se_dice():
    """Sin `agente_turno` el modelo no contesto. Decirlo es el dato."""
    evs = [e for e in _evs() if e["event"] != "agente_turno"] + \
          [{"event": "agente_modelo_error", "trace_id": "abc123", "error": "RateLimitError"}]
    t = "\n".join(pelicula(evs))
    assert "no llego a `agente_turno`" in t and "agente_modelo_error RateLimitError" in t


def test_sin_eventos_no_hay_pelicula():
    """Una ventana sin turnos no imprime un titulo vacio."""
    assert pelicula([]) == []
    assert pelicula([{"event": "otra_cosa", "trace_id": "x"}]) == []


def test_todo_evento_que_la_pelicula_IMPRIME_lo_pide_tambien():
    """Una rama `elif ev == "..."` cuyo evento no esta en la lista no se alcanza nunca."""
    fuente = Path("banco_pruebas/produccion.py").read_text(encoding="utf-8")
    imprime = set(re.findall(r'(?:el)?if ev == "([a-z_]+)"', fuente))
    huerfanos = sorted(imprime - set(EVENTOS_PELICULA))
    assert not huerfanos, f"la pelicula imprime {huerfanos} y no los pide: agregalos a EVENTOS_PELICULA"


def test_todo_evento_que_la_pelicula_PIDE_lo_escribe_app():
    """El telefono descompuesto: un evento que nadie escribe deja la pelicula muda."""
    codigo = "\n".join(p.read_text(encoding="utf-8") for p in Path("app").rglob("*.py"))
    mudos = [e for e in EVENTOS_PELICULA if f'"{e}"' not in codigo]
    assert not mudos, f"la pelicula pide {mudos} y app/ no los escribe"
