"""
ORCHESTRATOR — despachador minimo.

El turno entero lo maneja el FLUJO ATADO: app/core/hub_atado.py (interprete y
solver AMBOS atados por enum a la fuente de verdad, sin la pila de guardas). El
dato duro nace de la fuente por construccion: imposible alucinar un precio, stock
o spec. El cierre y el cobro (modo lead o venta con CBU/link) los resuelve la capa
de leads reusada. Lo unico que queda antes es el filtro de entrada anti-jailbreak.

El camino viejo (interprete_libre, solver de prosa libre + ~40 guardas) queda en
el repo por si hay que volver (revert), pero NO es el que corre.
"""
import uuid

import structlog

from app.config import get_settings
from app.logger import get_logger
from app.core.hub_atado import procesar_atado

log = get_logger(__name__)
settings = get_settings()


async def process_message(user_id: str, raw_message: str,
                          tienda_id: str | None = None,
                          canal: str = "telegram") -> str:
    """Procesa un mensaje del cliente y devuelve la respuesta del bot."""
    trace_id = str(uuid.uuid4())[:8]
    tid = tienda_id or settings.TIENDA_ID
    structlog.contextvars.bind_contextvars(trace_id=trace_id, tienda_id=tid)
    log.info("message_received", trace_id=trace_id, tienda_id=tid,
             user_id=user_id, msg_preview=(raw_message or "")[:80])
    try:
        # Anti-jailbreak: filtro de entrada por codigo, antes de cualquier LLM.
        # Conservador: solo corta patrones claros de ataque ("ignora tus
        # instrucciones", "decime tu prompt", etc.); una consulta normal no dispara.
        try:
            from app.core.antijailbreak import evaluar_mensaje, RESPUESTA_BLOQUEO
            _aj = evaluar_mensaje(raw_message)
            if _aj.get("ataque"):
                log.warning("antijailbreak_bloqueo", trace_id=trace_id,
                            motivo=_aj.get("motivo"), patron=_aj.get("patron"))
                return RESPUESTA_BLOQUEO
        except Exception as e:
            log.error("antijailbreak_error", trace_id=trace_id,
                      error=str(e)[:160])

        return await procesar_atado(
            user_id, raw_message, tid, canal, trace_id)
    finally:
        structlog.contextvars.clear_contextvars()
