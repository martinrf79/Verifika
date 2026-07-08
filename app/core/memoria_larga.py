"""
MEMORIA LARGA (8-jul) — el resumen acumulativo de la charla vieja.

El historial vivo se corta a HISTORY_LIMIT turnos y lo anterior se PERDIA: el
bot no podia retomar una charla vieja (C2), leer una contradiccion lejana (C3)
ni recuperar un dato dado muchos turnos atras (C4). Los datos DUROS ya
persisten estructurados (carrito, vistos, localidades, datos del cliente,
presupuesto); lo que faltaba es el HILO conversacional.

El arreglo: cuando el recorte del historial descarta turnos, esos turnos se
FUNDEN en el campo `summary` de la conversacion (ya existia, iba vacio). El
resumen es acumulativo: cada actualizacion integra lo nuevo a lo anterior. Lo
redacta el modelo del solver (una llamada corta, SOLO en los turnos donde la
charla desborda el tope); si el LLM falla, una red DETERMINISTA compacta los
turnos descartados en lineas crudas, para que la memoria nunca quede en cero.

El resumen es CONTEXTO, no fuente de datos: precio, stock, total y politica
siguen saliendo sellados del catalogo, la FAQ y la calculadora; los
verificadores auditan el mensaje final como siempre. Por eso un resumen
imperfecto no puede inyectar una alucinacion de valor.
"""
import asyncio

from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

# Tope de tamaño del resumen persistido: acumulativo pero acotado. Si crece de
# mas, se queda con la cola (lo mas reciente pesa mas en una venta).
_MAX_CHARS = 1500


def _compactar_determinista(resumen_previo: str, descartados: list[dict]) -> str:
    """Red sin LLM: los turnos descartados entran como lineas crudas compactas
    al final del resumen previo. Bounded por _MAX_CHARS (se conserva la cola)."""
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
    """Funde los turnos descartados del historial en el resumen acumulado.
    Devuelve el resumen nuevo (o el previo intacto si no hay nada que fundir)."""
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
        from app.core.agent import _get_client, modelo_solver
        from app.config import (deepseek_extra_body, gemini_thinking_off,
                                nvidia_thinking_off, openrouter_reasoning_off)
        modelo = modelo_solver()
        extra = (nvidia_thinking_off(settings.LLM_PROVIDER, modelo)
                 or openrouter_reasoning_off(settings.LLM_PROVIDER, modelo)
                 or gemini_thinking_off(settings.LLM_PROVIDER, modelo)
                 or (deepseek_extra_body(modelo)
                     if settings.LLM_PROVIDER == "deepseek" else {}))
        kwargs = {"model": modelo,
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.2, "max_tokens": 350}
        if extra:
            kwargs["extra_body"] = extra
        try:
            r = _get_client().chat.completions.create(**kwargs)
        except Exception:
            kwargs.pop("extra_body", None)
            r = _get_client().chat.completions.create(**kwargs)
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
