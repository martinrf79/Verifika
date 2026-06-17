"""
RESCATE DE TOOL CALLS EMITIDOS COMO TEXTO — flag RESCATE_TOOLCALL_TEXTO.

Algunos modelos escriben el tool call en el contenido del mensaje en vez del
campo tool_calls de la API: DeepSeek via OpenRouter emite sus tokens crudos
(<tool_call_begin>function<tool_sep>nombre ```json {...} ``` <tool_call_end>),
Gemma y otros usan <tool_call>{"name":...,"arguments":{...}}</tool_call> o un
bloque json suelto. Sin rescate, ese markup llega TAL CUAL al cliente (16 de
100 respuestas en correr_pruebas del 10-jun-2026).

Este modulo es puro (sin red, sin estado): detecta el markup, extrae nombre y
argumentos de cada llamada, y devuelve el texto limpio de markup. El agente
decide ejecutar las llamadas rescatadas y seguir su loop normal.
"""
import json
import re

# Marcadores de inicio de tool call como texto. Cubre los tokens normalizados
# de DeepSeek, sus variantes unicode (｜ y ▁) y el estilo <tool_call> JSON.
_RE_DEEPSEEK = re.compile(
    r"<[|｜]?tool[_▁ ]?calls?[_▁ ]?begin[|｜]?>"  # apertura
    r".*?"
    r"<[|｜]?tool[_▁ ]?sep[|｜]?>"                 # separador
    r"\s*([A-Za-z_][A-Za-z0-9_]*)"                 # nombre de la funcion
    r"(.*?)"                                       # cuerpo con el json
    r"(?:<[|｜]?tool[_▁ ]?calls?[_▁ ]?end[|｜]?>|$)",
    re.DOTALL,
)
_RE_TOOLCALL_TAG = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
# Señal rapida de que hay markup (para no correr regexes en cada respuesta sana).
_RE_SENAL = re.compile(
    r"<[|｜]?tool[_▁ ]?(?:calls?[_▁ ]?begin|sep|call)\b|<tool_call>")


def _json_balanceado(texto: str) -> dict | None:
    """Extrae el primer objeto JSON balanceado de un texto sucio."""
    inicio = texto.find("{")
    if inicio == -1:
        return None
    nivel = 0
    for i in range(inicio, len(texto)):
        if texto[i] == "{":
            nivel += 1
        elif texto[i] == "}":
            nivel -= 1
            if nivel == 0:
                try:
                    obj = json.loads(texto[inicio:i + 1])
                    return obj if isinstance(obj, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def hay_markup(texto: str) -> bool:
    """True si el texto trae señales de tool call escrito como contenido."""
    return bool(texto and _RE_SENAL.search(texto))


def parsear_toolcalls_texto(texto: str) -> tuple[list[dict], str]:
    """
    Devuelve (llamadas, texto_limpio). Cada llamada es {"name":..., "args":{...}}.
    El texto limpio es lo que queda al remover TODO el markup, parseable o no:
    el cliente nunca debe ver tokens crudos.
    """
    if not texto or not hay_markup(texto):
        return [], texto or ""

    llamadas: list[dict] = []
    limpio = texto

    for m in _RE_DEEPSEEK.finditer(texto):
        nombre, cuerpo = m.group(1), m.group(2)
        args = _json_balanceado(cuerpo)
        if nombre:
            llamadas.append({"name": nombre, "args": args or {}})
    limpio = _RE_DEEPSEEK.sub("", limpio)

    for m in _RE_TOOLCALL_TAG.finditer(limpio):
        obj = _json_balanceado(m.group(1))
        if obj and obj.get("name"):
            argumentos = obj.get("arguments") or obj.get("args") or {}
            if isinstance(argumentos, str):
                argumentos = _json_balanceado(argumentos) or {}
            llamadas.append({"name": obj["name"], "args": argumentos})
    limpio = _RE_TOOLCALL_TAG.sub("", limpio)

    # Restos de markers sueltos (aperturas sin cierre, separadores huerfanos).
    limpio = _RE_SENAL.sub("", limpio)
    limpio = re.sub(r"```(?:json)?|```", "", limpio)
    limpio = re.sub(r"\s{2,}", " ", limpio).strip()

    return llamadas, limpio
