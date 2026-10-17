"""MEMORIA LARGA (8-jul) — el resumen acumulativo de la charla vieja."""
import asyncio

from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

# Tope de tamaño del resumen persistido: acumulativo pero acotado.
_MAX_CHARS = 1500


def _compactar_determinista(resumen_previo: str, descartados: list[dict]) -> str:
    """Red sin LLM: los turnos descartados entran como lineas crudas compactas al final del resumen previo."""
    lineas = [resumen_previo.strip()] if (resumen_previo or "").strip() else []
    for t in descartados or []:
        rol = "Cliente" if t.get("role") == "user" else "Bot"
        txt = " ".join(str(t.get("content") or "").split())
        if txt:
            lineas.append(f"{rol}: {txt[:160]}")
    out = "\n".join(lineas)
    return out[-_MAX_CHARS:] if len(out) > _MAX_CHARS else out


async def actualizar_resumen(resumen_previo: str, descartados: list[dict],
                             trace_id: str | None = None) -> str:
    """Funde los turnos descartados del historial en el resumen acumulado."""
    descartados = [t for t in (descartados or [])
                   if isinstance(t, dict) and str(t.get("content") or "").strip()]
    if not descartados:
        return resumen_previo or ""

    viejos = "\n".join(
        ("Cliente: " if t.get("role") == "user" else "Bot: ")
        + " ".join(str(t.get("content") or "").split())[:300]
        for t in descartados)
    prompt = (
        "Sos la memoria de un vendedor. Integra los turnos viejos de la charla "
        "al resumen acumulado, en espanol, maximo 10 lineas. Conserva SOLO lo "
        "que sirve para seguir vendiendo bien: que busca el cliente, productos "
        "elegidos o RECHAZADOS (y por que), datos que ya dio (nombre, "
        "direccion, forma de pago, destinos), decisiones y cambios de opinion, "
        "y pendientes. NO inventes nada; no incluyas precios ni montos (el "
        "sistema los tiene aparte). Devolve SOLO el resumen actualizado.\n\n"
        f"RESUMEN ACUMULADO HASTA AHORA:\n{resumen_previo or '(vacio)'}\n\n"
        f"TURNOS VIEJOS A INTEGRAR:\n{viejos}")

    def _call() -> str:
        # MISMO cliente que el solver VIVO. Colgaba de `agent._get_client`, que seguia el flag LLM_PROVIDER
        # -entonces en openai- mientras el camino vivo entero es Gemini: con la clave de OpenAI vencida esta
        # llamada tiraba 401 y el resumen NUNCA se actualizaba.
        from app.core.llm_reintento import _cliente as _cliente_gemini
        modelo = settings.GEMINI_MODEL or "gemini-3.1-flash-lite"
        kwargs = {"model": modelo,
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.2, "max_tokens": 350,
                  "extra_body": {"reasoning_effort": "none"}}
        try:
            r = _cliente_gemini().chat.completions.create(**kwargs)
        except Exception:
            kwargs.pop("extra_body", None)
            r = _cliente_gemini().chat.completions.create(**kwargs)
        return (r.choices[0].message.content or "").strip()

    try:
        nuevo = await asyncio.to_thread(_call)
    except Exception as e:
        log.warning("memoria_larga_llm_error", trace_id=trace_id,
                    error=str(e)[:120])
        nuevo = ""
    if not nuevo:
        # Red determinista: la memoria nunca queda en cero por una falla del LLM.
        nuevo = _compactar_determinista(resumen_previo, descartados)
        log.info("memoria_larga_fallback_determinista", trace_id=trace_id)
    else:
        log.info("memoria_larga_resumen_actualizado", trace_id=trace_id,
                 turnos_fundidos=len(descartados), chars=len(nuevo))
    return nuevo[-_MAX_CHARS:] if len(nuevo) > _MAX_CHARS else nuevo
