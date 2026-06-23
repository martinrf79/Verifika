"""
INTERPRETE_LIBRE — modo de prueba del intérprete (sesión 23-jun-2026).

Objetivo de Martín para esta etapa: dejar UNA sola cosa andando para poder
PROBAR la interpretación en real, apagando los ~70 flags y los cuatro caminos
paralelos del orchestrator. Acá no hay provider, ni verificadores, ni gate, ni
las catorce capas. Solo:

  1. INTERPRETE (LLM 1, interpretador.interpretar_mensaje): entiende el mensaje
     en el contexto de la charla. Es lo único que se está probando.
  2. SOLVER LIBRE (LLM 2, agent.run_agent con el prompt corto de modo_libre):
     redacta y vende libre, con las herramientas atadas a Firestore (catálogo y
     FAQs reales) y con la MEMORIA de la conversación. Recibe como guía lo que
     entendió el intérprete, pero no calcula nada que no salga de las tools.
  3. ECO DE INTERPRETACIÓN (flag INTERPRETE_DEBUG): al final de la respuesta, el
     bot muestra en una línea QUÉ entendió el intérprete, para que Martín juzgue
     la interpretación chateando, sin leer logs. Se apaga con INTERPRETE_DEBUG=false.

Es el interruptor maestro SOLO_INTERPRETE (default on). Mientras está prendido,
el orchestrator delega todo el turno acá y NINGÚN otro flag importa. Para volver
al sistema viejo: SOLO_INTERPRETE=false. Nada se borra; es reversible.
"""
import time

from app.core.agent import run_agent
from app.core.interpretador import interpretar_mensaje
from app.core.modo_libre import _PROMPT_LIBRE, _business_name, _schema_acotado
from app.config import get_settings
from app.logger import get_logger
from app.storage.firestore_client import (
    get_conversation, save_conversation, log_message,
)

log = get_logger(__name__)
settings = get_settings()


def _guia_para_solver(interp: dict) -> str:
    """Inyecta al solver libre lo que entendió el intérprete, como GUÍA de qué
    quiere el cliente. No trae datos del catálogo: eso lo sacan las tools."""
    if not isinstance(interp, dict):
        return ""
    partes = []
    intencion = interp.get("intencion")
    if intencion:
        partes.append(f"intención={intencion}")
    if interp.get("producto_resuelto"):
        partes.append(f"se refiere a={interp['producto_resuelto']}")
    cands = interp.get("candidatos") or []
    if cands:
        partes.append("posibles=" + ", ".join(str(c) for c in cands[:3]))
    if interp.get("respondiendo_a"):
        partes.append(f"responde a={interp['respondiendo_a']}")
    if interp.get("ofrecer_opciones"):
        partes.append(f"ofrecer opción A o B={interp['ofrecer_opciones']}")
    if not partes:
        return ""
    return ("\n\n[El intérprete leyó este mensaje así: " + "; ".join(partes)
            + ". Usalo como guía de qué quiere el cliente. Los precios, specs y "
            "datos de la tienda salen SOLO de las herramientas, no los inventes.]")


def _eco_interpretacion(interp: dict) -> str:
    """Línea legible para que Martín vea qué entendió el intérprete mientras
    chatea. Sin esto no se puede juzgar la interpretación sin mirar logs."""
    if not isinstance(interp, dict):
        return ""
    intencion = interp.get("intencion", "?")
    confianza = interp.get("confianza", 0)
    estado = interp.get("estado_conversacion", "?")
    prod = interp.get("producto_resuelto") or "ninguno"
    resp_a = interp.get("respondiendo_a") or "nada"
    cands = interp.get("candidatos") or []
    cand_txt = (", candidatos: " + ", ".join(str(c) for c in cands[:3])
                if cands else "")
    return (f"\n\n———\nInterpretación (modo prueba): intención {intencion}, "
            f"confianza {confianza}, estado {estado}, producto {prod}, "
            f"responde a {resp_a}{cand_txt}.")


async def procesar_interprete_libre(user_id: str, raw_message: str,
                                    tienda_id: str, canal: str,
                                    trace_id: str) -> str:
    """Maneja el turno entero: intérprete + solver libre + memoria. Devuelve la
    respuesta, con el eco de interpretación al final si INTERPRETE_DEBUG está on."""
    t0 = time.time()

    conv = get_conversation(user_id, tienda_id=tienda_id)
    history = conv.get("history", []) or []
    estado_anterior = conv.get("estado_conversacion", "saludo") or "saludo"
    carrito_memoria = conv.get("carrito_vigente", []) or []

    # ── PASO 1: INTERPRETE ──────────────────────────────────────────────
    interp = {}
    try:
        interp = await interpretar_mensaje(
            raw_message, history, trace_id,
            estado_anterior=estado_anterior, tienda_id=tienda_id,
            carrito_actual=carrito_memoria)
    except Exception as e:
        log.error("interprete_libre_interp_error", trace_id=trace_id,
                  error=str(e)[:200])

    estado_nuevo = (interp.get("estado_conversacion")
                    or estado_anterior) if isinstance(interp, dict) else estado_anterior

    # ── PASO 2: SOLVER LIBRE (con la guía del intérprete) ───────────────
    system_prompt = _PROMPT_LIBRE.format(business_name=_business_name(tienda_id))
    tools_schema = _schema_acotado()
    mensaje_enriquecido = raw_message + _guia_para_solver(interp)

    log.info("interprete_libre_inicio", trace_id=trace_id,
             intencion=interp.get("intencion") if isinstance(interp, dict) else None,
             tools=len(tools_schema), hist=len(history))

    meta = {}
    try:
        respuesta, meta = await run_agent(
            mensaje_enriquecido, history, trace_id,
            tienda_id=tienda_id, user_id=user_id,
            system_prompt=system_prompt, tools_schema=tools_schema)
    except Exception as e:
        log.error("interprete_libre_solver_error", trace_id=trace_id,
                  error=str(e)[:200])
        respuesta = settings.FALLBACK_MESSAGE

    # ── PASO 3: ECO DE INTERPRETACIÓN (para probar la interpretación) ───
    respuesta_final = respuesta
    if settings.INTERPRETE_DEBUG and respuesta != settings.FALLBACK_MESSAGE:
        respuesta_final = respuesta + _eco_interpretacion(interp)

    # ── MEMORIA: guardar el turno (el solver siempre recuerda la charla) ──
    # Se guarda la respuesta SIN el eco de debug, para que el historial que ve
    # el modelo el próximo turno sea limpio.
    history = history + [
        {"role": "user", "content": raw_message},
        {"role": "assistant", "content": respuesta},
    ]
    history = history[-(settings.HISTORY_LIMIT * 2):]

    latency_ms = int((time.time() - t0) * 1000)
    try:
        save_conversation(user_id, history, conv.get("summary", ""),
                          tienda_id=tienda_id,
                          estado_conversacion=estado_nuevo)
    except Exception as e:
        log.warning("interprete_libre_save_failed", trace_id=trace_id,
                    error=str(e)[:120])
    try:
        log_message(user_id, raw_message, respuesta_final,
                    meta.get("tools_called", []),
                    latency_ms, trace_id, tienda_id=tienda_id)
    except Exception as e:
        log.warning("interprete_libre_log_failed", trace_id=trace_id,
                    error=str(e)[:120])

    log.info("interprete_libre_ok", trace_id=trace_id, ms=latency_ms)
    return respuesta_final
