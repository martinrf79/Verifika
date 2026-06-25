"""
MODO_LIBRE — el experimento de Martin (16-jun).

El modelo LLM responde LIBRE, sin ninguna de las ~14 capas del pipeline
(interprete, nucleo, faq directo, provider, verificadores, corrector, gate,
leads). Lo unico que lo ata a la realidad es que las tools que ve leen de
Firestore: catalogo (search_products, get_product_details, list_catalog,
calculate_total) y FAQs (query_faq). Prompt corto de venta, sin los parrafos
defensivos del prompt pesado.

La idea de Martin: primero VER al modelo vender bien y libre, leyendo el texto
crudo, y recien despues filtrar o editar SOLO cuando alucine. Esto es el piso
del experimento: cero filtros, salida cruda.

Reversible: vive detras del flag MODO_LIBRE. En off este modulo no se importa ni
corre, y el bot actual queda intacto.

Se prende con: MODO_LIBRE=true + LLM_PROVIDER=gemini + GEMINI_API_KEY.
"""
import time

from app.core.agent import run_agent
from app.core.tools import get_tools_schema
from app.config import get_settings
from app.logger import get_logger
from app.storage.firestore_client import (
    get_conversation, save_conversation, log_message, get_config,
)

log = get_logger(__name__)
settings = get_settings()


# Prompt corto de venta. SIN las 9 mega-reglas defensivas: el modelo vende libre
# y honesto. Lo unico firme es que los datos de producto y de tienda salen de las
# herramientas (estan atadas a Firestore), no de su cabeza. No hay verificador ni
# corrector despues: esto es a proposito, para ver al modelo crudo.
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
    """El schema de tools recortado a las que ve el modo libre (catalogo + FAQs).
    Si la lista de env queda vacia o no matchea nada, cae al schema completo para
    no dejar al modelo sin herramientas."""
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


async def procesar_modo_libre(user_id: str, raw_message: str,
                              tienda_id: str, canal: str,
                              trace_id: str) -> str:
    """Maneja el turno entero con el modelo libre. Devuelve la respuesta cruda."""
    t0 = time.time()

    conv = get_conversation(user_id, tienda_id=tienda_id)
    history = conv.get("history", []) or []

    system_prompt = _PROMPT_LIBRE.format(business_name=_business_name(tienda_id))
    tools_schema = _schema_acotado()

    log.info("modo_libre_inicio", trace_id=trace_id,
             provider=settings.LLM_PROVIDER,
             tools=len(tools_schema), hist=len(history))

    try:
        respuesta, meta = await run_agent(
            raw_message, history, trace_id,
            tienda_id=tienda_id, user_id=user_id,
            system_prompt=system_prompt, tools_schema=tools_schema)
    except Exception as e:
        log.error("modo_libre_error", trace_id=trace_id, error=str(e)[:200])
        return settings.FALLBACK_MESSAGE

    # Historial: mismo formato que el pipeline viejo ({role, content}). Se capa
    # por el HISTORY_LIMIT al guardar para no crecer sin fin.
    history = history + [
        {"role": "user", "content": raw_message},
        {"role": "assistant", "content": respuesta},
    ]
    history = history[-(settings.HISTORY_LIMIT * 2):]

    latency_ms = int((time.time() - t0) * 1000)
    try:
        save_conversation(user_id, history, conv.get("summary", ""),
                          tienda_id=tienda_id,
                          estado_conversacion=conv.get(
                              "estado_conversacion", "explorando"))
    except Exception as e:
        log.warning("modo_libre_save_failed", trace_id=trace_id,
                    error=str(e)[:120])
    try:
        log_message(user_id, raw_message, respuesta,
                    meta.get("tools_called", []), latency_ms, trace_id,
                    tienda_id=tienda_id)
    except Exception as e:
        log.warning("modo_libre_log_failed", trace_id=trace_id,
                    error=str(e)[:120])

    log.info("modo_libre_ok", trace_id=trace_id, ms=latency_ms,
             tools_called=len(meta.get("tools_called", [])),
             iterations=meta.get("iterations"))
    return respuesta
