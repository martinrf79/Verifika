"""
MOTOR DE ENTRADA — el pequeño motor, base de Verifika mejorado.

Encadena los tres pasos que son los cimientos del sistema:

  1. comprender  (LLM)    estructura la pregunta del cliente en campos.
  2. resolver    (codigo) resuelve cada campo contra la fuente; ambiguo => pregunta.
  3. responder   (codigo) arma la respuesta simple que cierra en lo determinista.

El LLM contribuye en la PREGUNTA; el codigo manda en el DATO y en la RESPUESTA.
Sin verificador ni compuerta ni redactor: esa capa pesada se suma despues, encima
de esta base, cuando el camino simple este solido.

procesar() siempre devuelve el mismo contrato: {comprension, respuesta}. La
comprension viene completa (esqueleto garantizado) y con la resolucion de cada
aspecto colgada adentro; respuesta es {tipo, texto, cierra} o None si por esta via
simple no hay nada que responder (cae al flujo normal de arriba).

Detras del flag MOTOR_ENTRADA. Funcion pura salvo la llamada al LLM del paso 1.
"""
from typing import Optional

from app.core.comprension import comprender
from app.core.resolver_aspectos import resolver_aspectos
from app.core.responder_simple import responder_simple
from app.logger import get_logger

log = get_logger(__name__)


def procesar(mensaje: str, *, contexto: str = "",
             trace_id: Optional[str] = None) -> dict:
    """Corre los tres pasos sobre un mensaje. Contrato fijo de salida."""
    comp = comprender(mensaje, contexto, trace_id=trace_id)
    comp = resolver_aspectos(comp)
    resp = responder_simple(comp)
    log.info("motor_entrada", trace_id=trace_id,
             intencion=comp.get("intencion"),
             respondio=bool(resp), cierra=(resp or {}).get("cierra"),
             tipo=(resp or {}).get("tipo"))
    return {"comprension": comp, "respuesta": resp}
