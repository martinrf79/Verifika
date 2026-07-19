"""
OBSERVADOR — los MISMOS eventos que en produccion se leen en Cloud Logging,
capturados en memoria durante una corrida del banco.

El camino vivo ya loguea cada engranaje con structlog y trace_id (regla de
observabilidad del CLAUDE.md). En produccion esos eventos se consultan en Cloud
Logging; en el banco se imprimian crudos y nadie los juzgaba: un radar que
disparaba (destino fantasma, checker sin respaldo, criterio sin bloque) pasaba
invisible y el banco predecia menos que prod. Este modulo cierra ese hueco:

- ``instalar()`` configura structlog en el PROCESO del banco con un processor
  de captura. NO toca ``app/logger.py`` ni el logging de produccion.
- ``turno()`` es un context manager que corta el buffer por turno de charla:
  al salir, ``t.eventos`` tiene todo lo logueado en ese turno y
  ``t.radares()`` lo que salio en warning o peor (los radares).

Sin casos hardcodeados: captura TODO evento, la clasificacion es por nivel.
"""
import contextlib
import logging
import os

import structlog

# Niveles que cuentan como RADAR: en produccion son los que se consultan con
# severity>=WARNING en Cloud Logging.
NIVELES_RADAR = ("warning", "error", "critical")

# Buffer global del proceso del banco. Se limpia con limpiar().
_eventos: list[dict] = []


def _capturar(logger, method_name, event_dict):
    # Copia superficial ANTES de que el renderer consuma el dict.
    _eventos.append(dict(event_dict))
    return event_dict


def instalar(consola: bool = True) -> None:
    """Configura structlog con el processor de captura. Llamar ANTES de
    procesar el primer mensaje. ``consola=False`` silencia la impresion
    (para tests), la captura sigue igual."""
    salida = None if consola else open(os.devnull, "w")  # noqa: SIM115
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            _capturar,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(default=str),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(salida)
        if salida else structlog.PrintLoggerFactory(),
        # False: la captura aplica aunque un modulo ya haya logueado antes
        # de instalar() (los loggers no quedan atados a la config vieja).
        cache_logger_on_first_use=False,
    )


def limpiar() -> None:
    _eventos.clear()


class Turno:
    """Los eventos logueados dentro de un ``with turno() as t``."""

    def __init__(self):
        self.eventos: list[dict] = []

    def radares(self) -> list[dict]:
        return [e for e in self.eventos
                if e.get("level") in NIVELES_RADAR]

    def nombres(self, solo_radar: bool = False) -> list[str]:
        fuente = self.radares() if solo_radar else self.eventos
        return [str(e.get("event")) for e in fuente]


@contextlib.contextmanager
def turno():
    t = Turno()
    inicio = len(_eventos)
    try:
        yield t
    finally:
        t.eventos = list(_eventos[inicio:])


def resumen_radares(turnos: list[Turno]) -> dict[str, int]:
    """Conteo total por nombre de evento radar en toda la corrida."""
    conteo: dict[str, int] = {}
    for t in turnos:
        for nombre in t.nombres(solo_radar=True):
            conteo[nombre] = conteo.get(nombre, 0) + 1
    return dict(sorted(conteo.items(), key=lambda kv: -kv[1]))
