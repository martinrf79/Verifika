"""LA LLAMADA 0: EL MODELO SEPARA EL MENSAJE EN LINEAS Y TRADUCE CADA UNA (16-nov-2026; en app/ el 17-nov).

La elegida por Martin el 16-nov, FICHA 100: el prompt v2 con el modelo de `FLUJO_MODELO`, razonamiento bajo, por la clave
de OpenAI. Tres campos por linea: el fragmento con las palabras del cliente, la busqueda como la escribiria en el buscador
de una tienda, y el destino si lo dijo. Recibe el mensaje solo: no contesta ni decide nada. El banco mide con este mismo
prompt, `banco_pruebas/flujo/llamada0_modelos.py`.
"""
import json
import re

_S = {"type": "string"}
ESQUEMA = {"type": "object", "additionalProperties": False, "required": ["lineas"], "properties": {"lineas": {
    "type": "array", "items": {"type": "object", "additionalProperties": False,
                               "required": ["fragmento", "busqueda", "destino"],
                               "properties": {"fragmento": _S, "busqueda": _S, "destino": _S}}}}}
PROMPT = 'Sos el primer paso de un sistema que atiende clientes de una tienda online. Del mensaje del cliente,\ndevolve una linea por cada cosa que pide o pregunta, sin dejar ninguna afuera aunque el mensaje sea largo:\n- fragmento: la parte del mensaje que lo dice, con las palabras del cliente.\n- busqueda: lo que escribirias en el buscador de una tienda online para encontrarlo, con el producto primero y despues\n  todo lo que el cliente pide de el: marca, modelo, medida, capacidad, color, tipo, precio o tope por unidad. Lo que\n  dice para varios productos o para todo el mensaje, como "todo inalambrico" o "lo mas barato posible", va repetido\n  en la busqueda de cada linea a la que se aplica. Vacio si no busca un producto.\n- destino: el lugar a donde hay que enviarlo, solo si el cliente lo dijo; si no, vacio.\nUn producto por linea: si pide dos productos, o dos variantes del mismo, como uno negro y uno rojo, van en lineas\nseparadas. Si el cliente se corrige, vale lo ultimo que dijo.\nNo contestes ni decidas nada. Tu unica fuente es lo que escribio el cliente.'


def valida(x):
    return isinstance(x, dict) and isinstance(x.get("lineas"), list) and all(
        isinstance(l, dict) and "fragmento" in l and "busqueda" in l for l in x["lineas"])


def leer(crudo):
    """La salida del modelo como dict, o None."""
    t = re.sub(r"^```(?:json)?|```$", "", (crudo or "").strip(), flags=re.M).strip()
    try:
        x = json.loads(t[t.find("{"):t.rfind("}") + 1])
    except ValueError:
        return None
    return x if valida(x) else None


def pedir(texto):
    """(lineas, tokens de entrada, tokens de salida). Levanta si el modelo no contesta una salida valida."""
    from openai import OpenAI
    from app.config import get_settings
    s = get_settings()
    cli = OpenAI(api_key=(s.OPENAI_API_KEY or "").split()[0], timeout=float(s.LLM_TIMEOUT_SECONDS), max_retries=1)
    r = cli.chat.completions.create(
        model=s.FLUJO_MODELO, reasoning_effort=s.FLUJO_RAZONAMIENTO,
        messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": f"MENSAJE DEL CLIENTE: {texto}"}],
        response_format={"type": "json_schema", "json_schema": {"name": "lineas", "strict": True, "schema": ESQUEMA}})
    x = leer(r.choices[0].message.content)
    if x is None:
        raise ValueError("la llamada 0 no devolvio lineas validas")
    return x["lineas"], r.usage.prompt_tokens, r.usage.completion_tokens
