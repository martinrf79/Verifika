"""LA PELICULA DEL TURNO — la sonda sobre produccion (19-oct-2026; el agente, 30-oct; el flujo nuevo, 17-nov).

QUE CUIDA ESTA VARA. La pelicula es una funcion PURA sobre los renglones del log: lo que decide QUE se ve del sistema
tiene que poder probarse sin red y sin credencial.

Y cuida la otra mitad, que es la que se rompe sola: los NOMBRES. El flujo escribe `flujo_turno`; la pelicula lo lee.
Si alguien renombra uno de los dos lados, la pelicula se queda muda sin que nadie lo note. Por eso cada evento que la
pelicula pide tiene que estar escrito en `app/`.
"""
import re
from pathlib import Path

from banco_pruebas.produccion import EVENTOS_PELICULA, pelicula


def _evs() -> list:
    """Un turno entero, tal como lo escribe `app/core/flujo/nuevo/turno.py`."""
    return [
        {"event": "message_received", "trace_id": "abc123", "_t": "2026-11-17T15:29:15Z",
         "msg_preview": "me llevo el G305 negro, mandalo a Rosario"},
        {"event": "flujo_llamada0", "trace_id": "abc123", "lineas": [{"fragmento": "el G305 negro", "busqueda": "G305 negro",
                                                                        "destino": "Rosario"}], "entrada": 350, "salida": 60},
        {"event": "flujo_nexos", "trace_id": "abc123", "nexos": [[["nombrado", "coincide", "MOU0001"]]],
         "codigo": "Mouse Logitech G305 Lightspeed Negro a $80.500, quedan 9."},
        {"event": "flujo_segunda", "trace_id": "abc123", "responde": {"texto": "Dale", "pedido": {"agrega": []}},
         "entrada": 900, "salida": 80},
        {"event": "flujo_turno", "trace_id": "abc123", "comandos": ["pedido"], "hallazgos": [["dato", "12000"]], "seg": 6.1},
    ]


def test_la_pelicula_muestra_cada_paso_del_flujo():
    t = "\n".join(pelicula(_evs()))
    assert "me llevo el G305 negro" in t
    assert "TRADUJO   [('G305 negro', 'Rosario')] · 350+60 tokens" in t
    assert "NEXOS     [[['nombrado', 'coincide', 'MOU0001']]]" in t and "CODIGO    Mouse Logitech G305" in t
    assert "RETOCO    {'texto': 'Dale'" in t and "· 900+80 tokens" in t
    assert "HIZO      pedido · 6.1 s" in t
    assert "VERIFICO  [['dato', '12000']] · salio el texto del codigo" in t


def test_un_error_se_ve_como_error():
    evs = _evs() + [{"event": "agente_cobro_error", "trace_id": "abc123", "error": "sin link"}]
    assert "AVISO     agente_cobro_error sin link" in "\n".join(pelicula(evs))


def test_un_turno_que_se_cayo_se_dice():
    """Sin `flujo_turno` el turno no contesto. Decirlo es el dato."""
    evs = [e for e in _evs() if e["event"] != "flujo_turno"] + \
          [{"event": "flujo_segunda_error", "trace_id": "abc123", "error": "RateLimitError"}]
    t = "\n".join(pelicula(evs))
    assert "no llego a `flujo_turno`" in t and "flujo_segunda_error RateLimitError" in t


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
