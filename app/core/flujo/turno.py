"""EL TURNO — el mensaje, el agente de la tienda con su memoria, y la respuesta (20-oct-2026; el agente, 30-oct).

Desde el 30-oct, por orden de Martin, el turno lo contesta el agente de la FICHA 83, `agente.py`: el modelo busca con
sus palabras, arma el presupuesto con el ejecutor y escribe; el verificador controla cada afirmacion. La memoria de la
charla es el historial y la del agente, `memoria_agente`, en el documento de la charla.
"""
from app.config import get_settings
from app.core import guardas_salida as gs
from app.core.contexto_turno import set_current_tienda
from app.logger import get_logger
from app.storage import firestore_client as fc

from . import agente

log = get_logger(__name__)
settings = get_settings()


async def procesar_turno(user_id: str, raw_message: str, tienda_id: str, canal: str, trace_id: str) -> str:
    set_current_tienda(tienda_id)
    conv = fc.get_conversation(user_id, tienda_id=tienda_id) or {}
    history = conv.get("history") or []
    memoria = agente.memoria_de(conv)
    r = await agente.responder(raw_message, history, memoria, user_id, canal, tienda_id, trace_id)
    if "respuesta" not in r:
        from app.core.guia_venta_prosa import mensaje
        return mensaje("sobrecarga", "Perdón, estoy con mucha demanda en este momento. "
                                     "Probá de nuevo en un ratito y te respondo. 🙏")
    texto = r["respuesta"].strip() or "¿En qué te puedo ayudar?"
    if not history:
        texto = gs.con_saludo_inicial(texto, gs.business_name(tienda_id))
    history = (history + [{"role": "user", "content": raw_message},
                          {"role": "assistant", "content": texto}])[-(settings.HISTORY_LIMIT * 2):]
    try:
        fc.save_conversation(user_id, history, conv.get("summary") or "", tienda_id=tienda_id,
                             estado_conversacion="en_curso", memoria_agente=memoria,
                             ultimo_presupuesto=(r.get("presupuesto") or "")[-1500:] or None)
    except Exception as e:  # noqa: BLE001 — el cliente recibe su respuesta aunque no se haya guardado
        log.error("flujo_guardar_error", trace_id=trace_id, error=str(e)[:200])
    return texto
