"""Cliente LLM de Sparring. DeepSeek por default, interfaz mínima.

Producto independiente de Verifika: no importa nada de app/.
"""
import json
import os

from openai import OpenAI

_MODELO = os.environ.get("SPARRING_MODELO", "deepseek-chat")
_BASE = os.environ.get("SPARRING_LLM_BASE", "https://api.deepseek.com")


def _cliente() -> OpenAI:
    return OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url=_BASE)


def _parsear(crudo: str) -> dict:
    """Tolera cercos de markdown, texto alrededor y saltos de línea crudos."""
    texto = crudo.strip()
    if texto.startswith("```"):
        texto = texto.strip("`")
        if texto.startswith("json"):
            texto = texto[4:]
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio == -1 or fin <= inicio:
        raise ValueError(f"sin JSON en la respuesta: {crudo[:120]!r}")
    texto = texto[inicio : fin + 1]
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        # último recurso: saltos de línea crudos dentro de strings
        return json.loads(texto.replace("\n", " ").replace("\r", " "))


def charla_json(system: str, mensajes: list[dict], temperatura: float = 0.7) -> dict:
    """Llama al modelo y devuelve el dict parseado.

    El modo json_object de DeepSeek a veces devuelve contenido vacío; la
    escalera es: dos intentos con modo JSON y un tercero sin forzarlo,
    confiando en la instrucción del prompt más el extractor de _parsear.
    """
    ultimo_error: Exception | None = None
    intentos = (
        {"response_format": {"type": "json_object"}},
        {"response_format": {"type": "json_object"}},
        {},
    )
    for extra in intentos:
        resp = _cliente().chat.completions.create(
            model=_MODELO,
            temperature=temperatura,
            messages=[{"role": "system", "content": system}, *mensajes],
            **extra,
        )
        try:
            return _parsear(resp.choices[0].message.content or "")
        except (ValueError, json.JSONDecodeError) as e:
            ultimo_error = e
    raise ultimo_error
