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
La interpretación de cada turno se LOGUEA (evento interprete_libre_interpretacion)
para diagnosticar, pero NO se muestra al cliente: el cartel era solo de la etapa
de prueba y se quitó.

Es el ÚNICO camino del bot: el orchestrator delega acá todo el turno, sin flags.
"""
import time

from app.core.agent import run_agent
from app.core.interpretador import interpretar_mensaje
from app.core.leads import procesar_mensaje_para_lead, descartar_leads_activos
from app.core.tools import get_tools_schema
from app.config import get_settings
from app.logger import get_logger
from app.storage.firestore_client import (
    get_conversation, save_conversation, log_message, reset_conversation,
    get_config,
)

log = get_logger(__name__)
settings = get_settings()


# Prompt corto de venta del solver libre. SIN las mega-reglas defensivas: el
# modelo vende libre; lo unico firme es que los datos salen de las herramientas
# (atadas a Firestore). El filtro determinista y autofix son la red de despues.
_PROMPT_LIBRE = """Sos un vendedor de {business_name}, una tienda online argentina de tecnologia y gaming. Hablas en espanol argentino, tuteando, con calidez y ganas de ayudar a comprar.

Tu objetivo es VENDER bien: entender que necesita el cliente, mostrarle las mejores opciones, sacarle las dudas y avanzar hacia la compra. Sos libre en como lo decis y como ordenas la venta.

Lo unico que NO inventas son los datos reales de la tienda. Para eso tenes herramientas:
- search_products, get_product_details, list_catalog: precios, stock, specs y modelos del catalogo real.
- query_faq: formas de pago, garantia, devoluciones y demas politicas.
- calculate_total: cualquier total, subtotal, descuento o cuenta con cantidades.
- cotizar_envio: el costo de envio. Pasale lo que dijo el cliente (codigo postal, localidad o provincia) tal cual; el codigo determina la zona y la tarifa. NO elijas vos la zona ni inventes el costo. Si pide envio y no dio la zona, pedile el CP o la localidad.
Usalas cuando necesites un dato o un numero concreto, en vez de adivinarlo. Si necesitas varias cosas, pedilas juntas en un solo paso.

Estilo: espanol argentino, tuteo. Conciso y natural. Texto plano sin markdown. Precios en formato $280.000.
"""


def _business_name(tienda_id: str | None) -> str:
    name = settings.BUSINESS_NAME
    if tienda_id:
        try:
            stored = get_config("business_name", tienda_id=tienda_id)
            if stored:
                name = stored
        except Exception:
            pass
    return name


def _schema_acotado() -> list:
    """El schema de tools recortado a las que ve el solver libre (MODO_LIBRE_TOOLS:
    catalogo, FAQ, calculadora, envio). Si la lista queda vacia o no matchea, cae
    al schema completo para no dejar al modelo sin herramientas."""
    permitidas = {
        t.strip() for t in (settings.MODO_LIBRE_TOOLS or "").split(",")
        if t.strip()
    }
    full = get_tools_schema()
    if not permitidas:
        return full
    acotado = [s for s in full
               if s.get("function", {}).get("name") in permitidas]
    return acotado or full


def _presupuesto_de_meta(meta: dict) -> str:
    """Saca el presupuesto YA VERIFICADO (campo presentacion de calculate_total)
    del meta del solver, para que el cierre y el link de pago usen el total real
    de la calculadora, nunca uno inventado. "" si el solver no calculo este turno."""
    for tc in reversed((meta or {}).get("tools_called", []) or []):
        if tc.get("name") == "calculate_total":
            pres = (tc.get("result") or {}).get("presentacion")
            if pres:
                return pres
    return ""


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


async def procesar_interprete_libre(user_id: str, raw_message: str,
                                    tienda_id: str, canal: str,
                                    trace_id: str) -> str:
    """Maneja el turno entero: intérprete + solver libre + memoria. La
    interpretación se loguea para diagnosticar, no se muestra al cliente."""
    t0 = time.time()

    conv = get_conversation(user_id, tienda_id=tienda_id)
    history = conv.get("history", []) or []
    estado_anterior = conv.get("estado_conversacion", "saludo") or "saludo"
    # PROOF de turnos anteriores: respaldan un total que el cliente confirma y el
    # bot repite sin recalcular, asi el filtro determinista no bloquea en falso.
    proofs_memoria = conv.get("proofs_recientes", []) or []

    # ── RESET_CODE: palabra clave de PRUEBA para arrancar de cero ────────
    # El bot mantiene CONTINUIDAD siempre. NO resetea con frases naturales como
    # "nueva compra" (un cliente real las usa para seguir comprando, no para
    # borrar todo). Para las pruebas hay una palabra clave dedicada (RESET_CODE,
    # ej "verifika2026"): si el mensaje es EXACTAMENTE esa, se borra la conversacion
    # entera y se confirma. Con clientes reales no hace falta; es solo para testear
    # desde el mismo numero sin tocar el entorno.
    _rc = (settings.RESET_CODE or "").strip().lower()
    if _rc and (raw_message or "").strip().lower() == _rc:
        try:
            reset_conversation(user_id, tienda_id=tienda_id)
            descartar_leads_activos(user_id, canal, tienda_id)
        except Exception as e:
            log.warning("interprete_libre_reset_error", trace_id=trace_id,
                        error=str(e)[:120])
        log.info("interprete_libre_reset_code", trace_id=trace_id, user_id=user_id)
        return "Listo, conversacion reiniciada. Empezamos de cero."

    # ── PASO 1: INTERPRETE ──────────────────────────────────────────────
    interp = {}
    try:
        interp = await interpretar_mensaje(
            raw_message, history, trace_id,
            estado_anterior=estado_anterior, tienda_id=tienda_id)
    except Exception as e:
        log.error("interprete_libre_interp_error", trace_id=trace_id,
                  error=str(e)[:200])

    estado_nuevo = (interp.get("estado_conversacion")
                    or estado_anterior) if isinstance(interp, dict) else estado_anterior

    # La interpretacion va al LOG para diagnosticar (reemplaza el cartel que antes
    # se mostraba al cliente). Asi se juzga la interpretacion sin molestar la charla.
    if isinstance(interp, dict):
        log.info("interprete_libre_interpretacion", trace_id=trace_id,
                 intencion=interp.get("intencion"), confianza=interp.get("confianza"),
                 estado=interp.get("estado_conversacion"),
                 producto=interp.get("producto_resuelto"),
                 responde_a=interp.get("respondiendo_a"),
                 candidatos=interp.get("candidatos"))

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

    # ── PASO 2a: FILTRO DETERMINISTA en MODO OBSERVACION ────────────────
    # Chequea que cada cifra de dinero salga de una fuente real (catalogo, FAQ, o
    # PROOF de la calculadora de este turno o de turnos recientes). HOY solo LOGUEA
    # lo que marcaria; NO bloquea ni reintenta. El bloqueo+autofix sumaba una
    # llamada extra al modelo (mas lento) y cortaba respuestas legitimas a fallback.
    # Se afina sobre estos logs (evento ..._shadow) antes de volver a enforce.
    proofs_turno = [t["proof"] for t in (meta.get("tools_called") or [])
                    if t.get("proof")]
    if respuesta != settings.FALLBACK_MESSAGE:
        try:
            from app.core.evidencia import build_evidence_from_tools
            from app.core.verificador import verificar_respuesta
            evidencia = build_evidence_from_tools(
                meta.get("tools_called", []) or [], tienda_id)
            evidencia += [{"tipo": "proof", "proof": p} for p in proofs_memoria]
            veredicto = verificar_respuesta(respuesta, evidencia, trace_id)
            if not veredicto["ok"]:
                log.warning("interprete_libre_numero_no_respaldado_shadow",
                            trace_id=trace_id,
                            no_respaldados=veredicto["numeros_no_respaldados"][:8],
                            respuesta_preview=respuesta[:220])
        except Exception as e:
            log.warning("interprete_libre_verif_error", trace_id=trace_id,
                        error=str(e)[:160])
    proofs_recientes = (proofs_memoria + proofs_turno)[-settings.VERIFICADOR_PROOF_MEMORY:]

    # ── PASO 2b: CIERRE (codigo) — capta el lead, pide datos, manda el link ──
    # El codigo toma el control SOLO cuando hay que cerrar: detecta la decision de
    # compra por la interpretacion, junta nombre/telefono/direccion/forma de pago y
    # genera el link de Mercado Pago con el total VERIFICADO de la calculadora (de
    # presentacion, nunca un monto del modelo). Si no hay cierre, la respuesta libre
    # del solver queda intacta. El presupuesto sale del turno o de la memoria.
    presupuesto = _presupuesto_de_meta(meta) or (conv.get("ultimo_presupuesto") or "")
    if respuesta != settings.FALLBACK_MESSAGE:
        try:
            _, meta_lead = await procesar_mensaje_para_lead(
                user_id, canal, tienda_id, raw_message, respuesta, trace_id,
                interpretacion=interp if isinstance(interp, dict) else None,
                presupuesto=presupuesto)
            if meta_lead.get("respuesta_directa"):
                respuesta = meta_lead["respuesta_directa"]
                log.info("interprete_libre_cierre", trace_id=trace_id,
                         accion=meta_lead.get("accion"))
        except Exception as e:
            log.warning("interprete_libre_lead_error", trace_id=trace_id,
                        error=str(e)[:160])

    # El cliente recibe la respuesta limpia: el cartel de interpretacion se quito
    # (ahora va al log). La interpretacion se sigue viendo en interprete_libre_interpretacion.
    respuesta_final = respuesta

    # ── MEMORIA: guardar el turno (el solver siempre recuerda la charla) ──
    history = history + [
        {"role": "user", "content": raw_message},
        {"role": "assistant", "content": respuesta},
    ]
    history = history[-(settings.HISTORY_LIMIT * 2):]

    latency_ms = int((time.time() - t0) * 1000)
    try:
        save_conversation(user_id, history, conv.get("summary", ""),
                          tienda_id=tienda_id,
                          estado_conversacion=estado_nuevo,
                          ultimo_presupuesto=presupuesto,
                          proofs_recientes=proofs_recientes)
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
