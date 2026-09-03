"""
ORCHESTRATOR — despachador minimo.

El turno entero lo maneja el HUB DE VENTA: app/core/hub_venta.py. Dos llamadas
al modelo -que buscar, y redactar con el dato delante- y las herramientas
corriendo en paralelo en el medio. El dato duro sale de la fuente porque lo trae
una herramienta; lo que la herramienta no trajo, no existe para el modelo. El
cierre y el cobro los resuelve la capa de leads reusada. Lo unico que queda antes
es el filtro de entrada anti-jailbreak.

El camino atado -interprete de veinte campos, solver de fragmentos, render, juez,
red de verificadores y guardas de salida- se BORRO el 2-ago. No convive apagado
al lado: la red para volver atras es git.
"""
import uuid

import structlog

from app.config import get_settings
from app.logger import get_logger
from app.core.turno import procesar_turno

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

        # ── RESET_CODE: palabra clave de PRUEBA para arrancar de cero ────────
        # Vive ACA, en el orchestrator, para que funcione con CUALQUIER camino.
        # El bot mantiene continuidad siempre; solo el RESET_CODE
        # exacto (ej "verifika2026") borra la conversacion y descarta los leads,
        # para testear desde el mismo numero sin tocar el entorno.
        _rc = (settings.RESET_CODE or "").strip().lower()
        if _rc and (raw_message or "").strip().lower() == _rc:
            try:
                from app.storage.firestore_client import reset_conversation
                from app.core.leads import descartar_leads_activos
                reset_conversation(user_id, tienda_id=tid)
                descartar_leads_activos(user_id, canal, tid)
            except Exception as e:
                log.warning("reset_code_error", trace_id=trace_id,
                            error=str(e)[:120])
            log.info("reset_code", trace_id=trace_id, user_id=user_id)
            from app.core.guia_venta_prosa import mensaje
            return mensaje("conversacion_reiniciada",
                           "Listo, conversacion reiniciada. Empezamos de cero.")

        return await procesar_turno(
            user_id, raw_message, tid, canal, trace_id)
    finally:
        structlog.contextvars.clear_contextvars()
