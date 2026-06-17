"""
COMPUERTA UNICA — una sola pasada que valida cada hecho contra la fuente.

Reemplaza la pila de ~14 capas defensivas por UN paso. No reinventa: une las
piezas que ya funcionan, los tres verificadores deterministas (plata, servicios,
hechos) y la autocorreccion de montos, en una decision unificada contra la
evidencia del turno, que es la fuente.

Filosofia (el codigo es dueño del HECHO):
  - PLATA: si una cifra no esta respaldada, el codigo intenta corregirla a la
    verdad de la fuente (autocorregir_montos). Si queda bien, pasa corregida.
  - SERVICIOS y HECHOS: una capacidad o una regla inventada no se "recalcula";
    si aparece, la compuerta bloquea (el orchestrator cae a la verdad pelada o
    al fallback). Determinista, sin LLM.

Devuelve una sola decision: {ok, respuesta_final, accion, problemas}. En off no
corre nadie la llama; el flag maestro COMPUERTA_UNICA decide en el orchestrator.

Los verificadores se importan a nivel modulo para poder testear la orquestacion
con dobles, sin depender del detalle interno de cada uno (que ya tiene su test).
"""
import re
from typing import Optional

from app.core.verificador import verificar_respuesta, autocorregir_montos
from app.core.verificador_servicios import verificar_servicios
from app.core.verificador_hechos import verificar_hechos
from app.logger import get_logger

log = get_logger(__name__)

# Tool calls que un modelo flojo (ej. Gemma) escupe como TEXTO en vez de
# ejecutarlas, y que ningun verificador caza porque no son numero/servicio/hecho.
# Es basura que NUNCA debe llegar al cliente. La sacamos por codigo.
_TOOLS = ("search_products", "get_product_details", "calculate_total",
          "query_faq", "find_within_budget", "compare_products",
          "recommend_product", "list_catalog", "cotizar_envio",
          "calcular_entrega")
_RE_TOOL_TEXTO = re.compile(
    r"\[?\b(?:" + "|".join(_TOOLS) + r")\s*\([^\)]*\)?\]?",
    re.IGNORECASE | re.DOTALL)


def quitar_tool_calls_texto(texto: str) -> tuple[str, bool]:
    """Saca de la respuesta cualquier tool call escrita como texto. Devuelve
    (texto_limpio, hubo). hubo=True es senal de que el modelo NO completo la
    accion (la narro en vez de ejecutarla): la respuesta es poco confiable."""
    if not texto:
        return texto, False
    nuevo = _RE_TOOL_TEXTO.sub("", texto)
    if nuevo == texto:
        return texto, False
    # Limpiar espacios y corchetes vacios que quedan tras sacar el fragmento.
    nuevo = re.sub(r"\[\s*\]", "", nuevo)
    nuevo = re.sub(r"[ \t]{2,}", " ", nuevo)
    nuevo = re.sub(r"\s+([.,;:])", r"\1", nuevo).strip()
    return nuevo, True


def evaluar(respuesta: str,
            evidence: list[dict],
            *,
            trace_id: Optional[str] = None,
            precios_validos: Optional[set] = None,
            verdad_turno: Optional[str] = None) -> dict:
    """Corre la compuerta unica sobre la respuesta contra la evidencia.

    Args:
        verdad_turno: el hecho que el codigo SI tiene de este turno, ya verificado
            (ej. el presupuesto que armo el cotizador por codigo). Si la compuerta
            bloquea pero hay verdad_turno, cae a ESE dato real en vez de censurar:
            cierra con el numero verdadero en lugar de aplazar. Es el escalon que
            va antes del puente (el puente es para cuando NO hay dato).

    Returns:
        {
          "ok": bool,                 # True si la respuesta pasa entera
          "respuesta_final": str,     # texto a mandar: corregido, o la verdad del
                                      # turno si cayo, o "" si no hay con que caer
                                      # (ahi el orchestrator usa fallback/puente)
          "accion": "responder"|"caer_verdad"|"bloquear",
          "problemas": {              # solo las clases que fallaron
              "plata": [...], "servicios": [...], "hechos": [...]
          },
          "corrigio_plata": bool,
        }
    """
    texto = respuesta
    problemas: dict = {}
    corrigio_plata = False

    # ── TOOL CALLS COMO TEXTO: basura del modelo que no debe llegar al cliente ──
    # Se saca por codigo. Si habia, el modelo no completo la accion, asi que la
    # respuesta es poco confiable: se marca como problema para que caiga a la
    # verdad del turno o al puente, no se mande mutilada.
    texto, hubo_tool_texto = quitar_tool_calls_texto(texto)
    if hubo_tool_texto:
        log.info("compuerta_tool_texto", trace_id=trace_id)
        problemas["tool_texto"] = True

    # ── PLATA: corregir por codigo contra la fuente ──
    try:
        vr = verificar_respuesta(texto, evidence, trace_id=trace_id)
    except Exception as e:
        log.error("compuerta_plata_error", trace_id=trace_id, error=str(e)[:160])
        vr = {"ok": True}
    if not vr.get("ok", True):
        try:
            ac = autocorregir_montos(
                texto, evidence, trace_id=trace_id,
                precios_validos=precios_validos or set())
        except Exception as e:
            log.error("compuerta_autocorrige_error", trace_id=trace_id,
                      error=str(e)[:160])
            ac = {"cambiada": False, "verificacion": {"ok": False}}
        if ac.get("cambiada") and ac.get("verificacion", {}).get("ok"):
            texto = ac["respuesta"]
            corrigio_plata = True
            log.info("compuerta_plata_corregida", trace_id=trace_id)
        else:
            problemas["plata"] = vr.get("numeros_no_respaldados", [])

    # ── SERVICIOS: capacidad inventada no se recalcula, bloquea ──
    try:
        vs = verificar_servicios(texto, evidence, trace_id=trace_id)
    except Exception as e:
        log.error("compuerta_servicios_error", trace_id=trace_id, error=str(e)[:160])
        vs = {"ok": True}
    if not vs.get("ok", True):
        problemas["servicios"] = vs.get("servicios_inventados", [])

    # ── HECHOS: regla mal narrada, bloquea ──
    try:
        vh = verificar_hechos(texto, evidence, trace_id=trace_id)
    except Exception as e:
        log.error("compuerta_hechos_error", trace_id=trace_id, error=str(e)[:160])
        vh = {"ok": True}
    if not vh.get("ok", True):
        problemas["hechos"] = vh.get("problemas", [])

    ok = not problemas
    if ok:
        return {"ok": True, "respuesta_final": texto, "accion": "responder",
                "problemas": problemas, "corrigio_plata": corrigio_plata}

    # Bloqueo. Antes de censurar, caer a la verdad del turno si el codigo la tiene.
    log.info("compuerta_bloqueo", trace_id=trace_id, clases=list(problemas.keys()))
    if verdad_turno:
        log.info("compuerta_cae_a_verdad", trace_id=trace_id)
        return {"ok": False, "respuesta_final": verdad_turno,
                "accion": "caer_verdad", "problemas": problemas,
                "corrigio_plata": corrigio_plata}
    # Sin verdad con que caer: respuesta vacia -> el orchestrator pone fallback,
    # que los puentes (si estan on) convierten en algo que mantiene la venta.
    return {"ok": False, "respuesta_final": "", "accion": "bloquear",
            "problemas": problemas, "corrigio_plata": corrigio_plata}
