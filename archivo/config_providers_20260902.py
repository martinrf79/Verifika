# SNAPSHOT 2-sep-2026 — Recorte 2. No corre. app/ no importa este archivo.
#
# El zoologico de proveedores que vivia en app/config.py junto a las cinco
# funciones *_thinking_off / *_extra_body. El camino vivo habla solo con
# Gemini por hub_venta._cliente(). GROQ_API_KEY se quedo en config.py porque
# la transcripcion de audio (transcriber.py) la usa de verdad.

# DeepSeek
DEEPSEEK_API_KEY = ""
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_THINKING = False

# Groq (el modelo; la clave de Whisper sigue en app/config.py)
GROQ_MODEL = "llama-3.3-70b-versatile"

# OpenAI nativo
OPENAI_API_KEY = ""
OPENAI_MODEL = "gpt-4o-mini"

# Anthropic Claude via endpoint compatible con OpenAI
ANTHROPIC_API_KEY = ""
ANTHROPIC_MODEL = "claude-haiku-4-5"
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"

# NVIDIA Nemotron via NIM
NEMOTRON_API_KEY = ""
NEMOTRON_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
NEMOTRON_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Kimi (Moonshot) via NIM de NVIDIA
KIMI_API_KEY = ""
KIMI_MODEL = "moonshotai/kimi-k2.6"
KIMI_BASE_URL = "https://integrate.api.nvidia.com/v1"

# OpenRouter
OPENROUTER_API_KEY = ""
OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# El interprete tipado ya no corre. El default era gemini.
INTERPRETER_PROVIDER = "gemini"


def deepseek_extra_body(model_name, think=None):
    """extra_body para DeepSeek v4. Snapshot; no se llama."""
    if "v4" not in (model_name or "").lower():
        return {}
    if think:
        return {}
    return {"thinking": {"type": "disabled"}}


def nvidia_thinking_off(provider, model_name):
    """extra_body para NVIDIA NIM. Snapshot; no se llama."""
    if (provider or "").lower() not in ("nemotron", "kimi"):
        return {}
    m = (model_name or "").lower()
    razona = (("v4" in m and "deepseek" in m) or "qwen3" in m
              or "nemotron" in m or "gpt-oss" in m)
    return {"chat_template_kwargs": {"thinking": False}} if razona else {}


def openrouter_reasoning_off(provider, model_name):
    """extra_body para OpenRouter. Snapshot; no se llama."""
    if (provider or "").lower() != "openrouter":
        return {}
    m = (model_name or "").lower()
    razona = ("gemini-2.5" in m or "qwen3" in m or "gpt-oss" in m
              or ("deepseek" in m and ("v4" in m or "r1" in m))
              or "thinking" in m)
    return {"reasoning": {"enabled": False}} if razona else {}


def gemini_thinking_off(provider, model_name):
    """extra_body para Gemini directo. Snapshot; no se llama.
    El vivo manda reasoning_effort desde REDACTOR_REASONING / DECISOR_REASONING."""
    if (provider or "").lower() != "gemini":
        return {}
    m = (model_name or "").lower()
    return {} if "2.0" in m else {"reasoning_effort": "none"}


def deepseek_pensando(model_name):
    """True si el v4 iba en modo razonador. Snapshot; no se llama."""
    return "v4" in (model_name or "").lower()
