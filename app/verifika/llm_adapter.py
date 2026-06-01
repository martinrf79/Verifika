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
def _call_openai_compatible(client, model: str, messages: list,
                             temperature: float, max_tokens: int,
                             tools: Optional[list] = None) -> dict:
    """Para deepseek, groq, openai (todos OpenAI-compatible)."""
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    response = client.chat.completions.create(**kwargs)
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

    if provider in ("deepseek", "groq", "openai"):
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
