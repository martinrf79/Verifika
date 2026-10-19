"""REINTENTO DE LLAMADA LLM — red comun contra el hipo transitorio del proveedor."""
import asyncio
import re

from app.logger import get_logger

log = get_logger(__name__)

# Marcas de error que SI conviene reintentar: cuota momentanea, 5xx, saturacion, timeout.
_TRANSITORIO = ("429", "500", "502", "503", "504", "overloaded",
                "unavailable", "timeout", "timed out", "quota", "rate limit")


# ── LA LLAMADA NEGADA, PARA QUE UNA MEDICION NO MIENTA ─────────────────────
_cupo: dict = {"veces": 0, "ultimo": ""}


def anotar_llamada_negada(e: BaseException) -> None:
    if es_transitorio(e):
        _cupo["veces"] += 1
        _cupo["ultimo"] = (str(e)[:160] or f"{type(e).__name__} sin detalle")


def sin_cupo() -> dict:
    """Cuantas veces la llamada al modelo se cayo sin recuperarse, y con que texto."""
    return dict(_cupo)


def reiniciar_cupo() -> None:
    _cupo["veces"], _cupo["ultimo"] = 0, ""


def es_transitorio(e: BaseException) -> bool:
    if isinstance(e, (asyncio.TimeoutError, TimeoutError)):
        return True
    s = str(e).lower()
    return any(t in s for t in _TRANSITORIO)


_RE_ESPERA = re.compile(r"retry(?:Delay)?[\"'\s:]*in?[\"'\s:]*([\d.]+)\s*s",
                        re.IGNORECASE)


def espera_sugerida(e: BaseException) -> float | None:
    """Los segundos que el PROVEEDOR pide esperar, si los dice."""
    m = _RE_ESPERA.search(str(e) or "")
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


async def llamar_con_reintento(fn, *, timeout_s: float | None = None,
                               intentos: int = 3, base_s: float = 0.6,
                               trace_id: str = "") -> str:
    """Corre fn() (bloqueante) en un thread; si falla con error transitorio, reintenta con backoff exponencial
    (base_s, 2*base_s, ...)."""
    from app.config import get_settings
    tope = float(get_settings().LLM_ESPERA_MAX_S)
    ultimo: BaseException | None = None
    for i in range(intentos):
        try:
            tarea = asyncio.to_thread(fn)
            if timeout_s is not None:
                return await asyncio.wait_for(tarea, timeout_s)
            return await tarea
        except Exception as e:  # noqa: BLE001 — se re-lanza abajo si no es transitorio
            ultimo = e
            pedida = espera_sugerida(e)
            if pedida is not None and pedida > tope:
                log.warning("llm_espera_muy_larga", trace_id=trace_id,
                            pedida_s=pedida, tope_s=tope)
                anotar_llamada_negada(e)
                raise
            if i < intentos - 1 and es_transitorio(e):
                espera = pedida if pedida is not None else base_s * (2 ** i)
                log.warning("llm_reintento", intento=i + 1, espera_s=espera,
                            error=str(e)[:80], trace_id=trace_id)
                await asyncio.sleep(espera)
                continue
            # Se anota SOLO cuando los reintentos se agotaron: una rafaga de 429 que el backoff absorbe no
            # ensucia nada y no tiene que invalidar una medicion que salio bien.
            anotar_llamada_negada(e)
            raise
    assert ultimo is not None
    raise ultimo


def _settings():
    from app.config import get_settings
    return get_settings()


# ══════════════════════════════════════════════════════════════════════════ LA PUERTA AL MODELO
# ══════════════════════════════════════════════════════════════════════════ VIVE ACA DESDE QUE SE APAGO EL
# HUB (3-sep-2026), y la mudanza saca tres ciclos de import de un movimiento.


def _cliente():
    """La UNICA puerta al modelo. Sin clave devuelve None y el turno cae al
    mensaje de fallback en vez de romperse."""
    import os
    from openai import OpenAI
    settings = _settings()
    if settings.LLM_PROVIDER == "deepseek":
        key = (settings.DEEPSEEK_API_KEY or os.environ.get("DEEPSEEK_API_KEY") or "").strip()
        return OpenAI(api_key=key, base_url=settings.DEEPSEEK_BASE_URL) if key else None
    key = (settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY") or "")
    key = key.split()[0] if key else ""
    if not key:
        return None
    return OpenAI(api_key=key, base_url=settings.GEMINI_BASE_URL)


def _modelo() -> str:
    s = _settings()
    if s.LLM_PROVIDER == "deepseek":
        return s.DEEPSEEK_MODEL or "deepseek-chat"
    return s.GEMINI_MODEL or "gemini-3.1-flash-lite"
