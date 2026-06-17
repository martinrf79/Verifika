"""
LLM ADAPTER — interfaz única para llamar a cualquier modelo.

Permite que Solver, Proposer y Checker elijan modelo independientemente
sin tocar el resto del código. Si mañana cambiamos de DeepSeek a Claude
en el Checker, se cambia una variable de entorno y listo.

Providers soportados:
- deepseek (default)
- groq
- anthropic (cuando haya cliente pagando)
- openai (cuando haya cliente pagando)

USO:
    from app.verifika.llm_adapter import llm_complete

    response = llm_complete(
        messages=[{"role": "user", "content": "Hola"}],
        role="solver",  # o "proposer" o "checker"
        temperature=0.2,
    )
"""
import os
import httpx
from typing import Optional
from openai import OpenAI, APITimeoutError, APIConnectionError, RateLimitError, InternalServerError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging

from app.logger import get_logger

log = get_logger(__name__)
_tenacity_log = logging.getLogger("verifika.llm.retry")

# ────────────────────────────────────────────────────────────
# Configuración por rol — cada rol puede usar modelo distinto
# ────────────────────────────────────────────────────────────

# Por defecto TODO va con DeepSeek (barato).
# Cuando haya cliente pagando, se puede cambiar Checker a Claude
# simplemente seteando VERIFIKA_CHECKER_PROVIDER=anthropic en .env

_ROLE_CONFIG = {
    "solver": {
        "provider": os.getenv("VERIFIKA_SOLVER_PROVIDER", "deepseek"),
        "model": os.getenv("VERIFIKA_SOLVER_MODEL", "deepseek-chat"),
    },
    "proposer": {
        "provider": os.getenv("VERIFIKA_PROPOSER_PROVIDER", "deepseek"),
        "model": os.getenv("VERIFIKA_PROPOSER_MODEL", "deepseek-chat"),
    },
    "checker": {
        "provider": os.getenv("VERIFIKA_CHECKER_PROVIDER", "deepseek"),
        "model": os.getenv("VERIFIKA_CHECKER_MODEL", "deepseek-chat"),
    },
    # Corrector anclado: segunda pasada stateless que aterriza la respuesta del
    # Solver a la evidencia del turno. Default DeepSeek (centavos). Para probar
    # con gpt-4-mini: VERIFIKA_CORRECTOR_PROVIDER=openai + VERIFIKA_CORRECTOR_MODEL=gpt-4o-mini
    "corrector": {
        "provider": os.getenv("VERIFIKA_CORRECTOR_PROVIDER", "deepseek"),
        "model": os.getenv("VERIFIKA_CORRECTOR_MODEL", "deepseek-chat"),
    },
}


# ────────────────────────────────────────────────────────────
# Cache de clientes (uno por provider)
# ────────────────────────────────────────────────────────────

_clients: dict[str, object] = {}


def _get_client(provider: str):
    """Devuelve el cliente correcto según provider. Cacheado."""
    if provider in _clients:
        return _clients[provider]

    _timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY no configurada")
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1",
            timeout=_timeout,
        )

    elif provider == "groq":
        from groq import Groq
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY no configurada")
        client = Groq(api_key=api_key, timeout=_timeout)

    elif provider == "anthropic":
        try:
            from anthropic import Anthropic
        except ImportError:
            raise RuntimeError(
                "anthropic no instalado. Agregalo a requirements.txt si vas a usarlo."
            )
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY no configurada")
        client = Anthropic(api_key=api_key)

    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY no configurada")
        client = OpenAI(api_key=api_key)

    elif provider == "nemotron":
        # Nemotron via NIM de NVIDIA: OpenAI-compatible, otra base_url. API gratis.
        api_key = os.getenv("NEMOTRON_API_KEY", "")
        if not api_key:
            raise RuntimeError("NEMOTRON_API_KEY no configurada")
        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("NEMOTRON_BASE_URL",
                               "https://integrate.api.nvidia.com/v1"),
            timeout=_timeout,
        )

    elif provider == "openrouter":
        # OpenRouter: OpenAI-compatible, una clave (sk-or-) para cientos de modelos.
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY no configurada")
        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("OPENROUTER_BASE_URL",
                               "https://openrouter.ai/api/v1"),
            timeout=_timeout,
        )

    elif provider == "kimi":
        # Kimi (Moonshot) via NIM de NVIDIA: OpenAI-compatible, API gratis, obediente
        # y con tool calling real. Misma clave nvapi- que Nemotron, asi que si no hay
        # KIMI_API_KEY propia, cae a NEMOTRON_API_KEY. La base_url default es la de
        # NVIDIA; si tu clave fuera de Moonshot directo u OpenRouter, solo cambia
        # KIMI_BASE_URL en el .env (no toca codigo).
        api_key = os.getenv("KIMI_API_KEY", "") or os.getenv("NEMOTRON_API_KEY", "")
        if not api_key:
            raise RuntimeError("KIMI_API_KEY (o NEMOTRON_API_KEY) no configurada")
        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("KIMI_BASE_URL",
                               "https://integrate.api.nvidia.com/v1"),
            timeout=_timeout,
        )

    else:
        raise RuntimeError(f"Provider desconocido: {provider}")

    _clients[provider] = client
    return client


# ────────────────────────────────────────────────────────────
# Excepciones que vale la pena reintentar
# ────────────────────────────────────────────────────────────

_RETRYABLE_EXCEPTIONS = (
    APITimeoutError,
    APIConnectionError,
    RateLimitError,
    InternalServerError,
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)


# ────────────────────────────────────────────────────────────
# Llamada al modelo con retry
# ────────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
    before_sleep=before_sleep_log(_tenacity_log, logging.WARNING),
    reraise=True,
)
def _nvidia_thinking_off(client, model: str) -> dict:
    """En el endpoint de NVIDIA NIM, los modelos que razonan por default
    (deepseek v4, qwen3, nemotron, gpt-oss) suman 30-200s de latencia. NVIDIA
    apaga el thinking con chat_template_kwargs. Devuelve el extra_body solo si
    el cliente apunta a NVIDIA y el modelo razona; si no, {}. Otros providers
    (deepseek directo, groq, openai) no reciben este parametro."""
    try:
        base = str(getattr(client, "base_url", "")).lower()
    except Exception:
        base = ""
    if "nvidia" not in base:
        return {}
    m = model.lower()
    razona = (("v4" in m and "deepseek" in m) or "qwen3" in m
              or "nemotron" in m or "gpt-oss" in m)
    if not razona:
        return {}
    return {"extra_body": {"chat_template_kwargs": {"thinking": False}}}


def _openrouter_reasoning_off(client, model: str) -> dict:
    """Gemelo del de arriba para OpenRouter: los modelos que razonan por
    default (gemini-2.5, qwen3, deepseek v4/r1, gpt-oss) suman 10-40s por
    llamada. OpenRouter lo apaga con el parametro unificado reasoning. Solo si
    el cliente apunta a OpenRouter y el modelo razona; si no, {}. Se puede
    desactivar con OPENROUTER_REASONING_OFF=false."""
    import os
    if os.getenv("OPENROUTER_REASONING_OFF", "true").lower() != "true":
        return {}
    try:
        base = str(getattr(client, "base_url", "")).lower()
    except Exception:
        base = ""
    if "openrouter" not in base:
        return {}
    m = model.lower()
    razona = ("gemini-2.5" in m or "qwen3" in m or "gpt-oss" in m
              or ("deepseek" in m and ("v4" in m or "r1" in m))
              or "thinking" in m)
    if not razona:
        return {}
    return {"extra_body": {"reasoning": {"enabled": False}}}


def _gemini_thinking_off(client, model: str) -> dict:
    """Gemelo para la API directa de Gemini (endpoint compat de Google):
    gemini-2.5 piensa por default y el pensamiento consume max_tokens, dejando
    el contenido vacio o cortado. Se apaga con reasoning_effort=none. Solo si
    el cliente apunta a generativelanguage.googleapis.com y el modelo es 2.5+.
    Se desactiva con GEMINI_THINKING_OFF=false."""
    import os
    if os.getenv("GEMINI_THINKING_OFF", "true").lower() != "true":
        return {}
    try:
        base = str(getattr(client, "base_url", "")).lower()
    except Exception:
        base = ""
    if "generativelanguage" not in base:
        return {}
    if "2.5" not in model.lower():
        return {}
    return {"extra_body": {"reasoning_effort": "none"}}


def _call_openai_compatible(client, model: str, messages: list,
                             temperature: float, max_tokens: int,
                             tools: Optional[list] = None) -> dict:
    """Para deepseek, groq, openai, nemotron, kimi (todos OpenAI-compatible)."""
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    extra = (_nvidia_thinking_off(client, model)
             or _openrouter_reasoning_off(client, model)
             or _gemini_thinking_off(client, model))
    try:
        response = client.chat.completions.create(**kwargs, **extra)
    except Exception:
        # Si el modelo no acepta el extra (chat_template_kwargs o reasoning
        # no soportado), reintentar sin el.
        if extra:
            response = client.chat.completions.create(**kwargs)
        else:
            raise
    msg = response.choices[0].message

    return {
        "content": msg.content or "",
        "tool_calls": msg.tool_calls,
        "raw_message": msg,
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
    before_sleep=before_sleep_log(_tenacity_log, logging.WARNING),
    reraise=True,
)
def _call_anthropic(client, model: str, messages: list,
                    temperature: float, max_tokens: int) -> dict:
    """Para Anthropic Claude. Adapta el formato de mensajes."""
    # Anthropic espera system aparte
    system_msgs = [m for m in messages if m["role"] == "system"]
    other_msgs = [m for m in messages if m["role"] != "system"]
    system_content = "\n\n".join(m["content"] for m in system_msgs) if system_msgs else None

    kwargs = {
        "model": model,
        "messages": other_msgs,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if system_content:
        kwargs["system"] = system_content

    response = client.messages.create(**kwargs)
    content = response.content[0].text if response.content else ""

    return {
        "content": content,
        "tool_calls": None,
        "raw_message": response,
    }


# ────────────────────────────────────────────────────────────
# API PÚBLICA
# ────────────────────────────────────────────────────────────

def llm_complete(
    messages: list[dict],
    role: str = "solver",
    temperature: float = 0.2,
    max_tokens: int = 800,
    tools: Optional[list] = None,
    trace_id: Optional[str] = None,
) -> dict:
    """
    Llama al LLM correspondiente al rol.

    Args:
        messages: lista de {"role": "...", "content": "..."}
        role: "solver" | "proposer" | "checker"
        temperature: temperatura del modelo
        max_tokens: máximo de tokens de salida
        tools: schema de tools (solo OpenAI-compatible por ahora)
        trace_id: para logging correlacionado

    Returns:
        dict con keys: content, tool_calls, raw_message, provider, model

    Raises:
        RuntimeError si el provider está mal configurado
        RetryError si se agotaron los reintentos
    """
    if role not in _ROLE_CONFIG:
        raise ValueError(f"Rol desconocido: {role}. Válidos: {list(_ROLE_CONFIG.keys())}")

    config = _ROLE_CONFIG[role]
    provider = config["provider"]
    model = config["model"]

    log.info("llm_call_start", trace_id=trace_id, role=role,
             provider=provider, model=model)

    client = _get_client(provider)

    if provider in ("deepseek", "groq", "openai", "nemotron", "kimi", "openrouter"):
        result = _call_openai_compatible(
            client, model, messages, temperature, max_tokens, tools
        )
    elif provider == "anthropic":
        if tools:
            log.warning("anthropic_tools_not_implemented", trace_id=trace_id)
        result = _call_anthropic(
            client, model, messages, temperature, max_tokens
        )
    else:
        raise RuntimeError(f"Provider sin handler: {provider}")

    result["provider"] = provider
    result["model"] = model

    log.info("llm_call_ok", trace_id=trace_id, role=role,
             provider=provider, content_len=len(result["content"]))

    return result


def get_role_config(role: str) -> dict:
    """Inspección: qué modelo está usando cada rol."""
    return _ROLE_CONFIG.get(role, {}).copy()


def list_roles_config() -> dict:
    """Inspección: configuración completa."""
    return {role: cfg.copy() for role, cfg in _ROLE_CONFIG.items()}
