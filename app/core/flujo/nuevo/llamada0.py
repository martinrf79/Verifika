"""LA LLAMADA 0: EL MODELO SEPARA EL MENSAJE EN LINEAS Y TRADUCE CADA UNA (16-nov-2026; en app/ el 17-nov; v7 el 18-nov).

La definida por Martin el 18-nov, FICHA 102: el prompt v7 con el modelo de `FLUJO_MODELO`, razonamiento bajo, por la
clave de OpenAI. Cuatro campos por linea: el fragmento con las palabras del cliente; el producto, traducido al nombre de
la tienda, o "?" si busca un producto pero el modelo no sabe cual es; las condiciones, lo que pide de como tiene que ser;
y el destino si lo dijo. Recibe el mensaje solo: no contesta ni decide nada. El banco mide con este mismo prompt,
`banco_pruebas/flujo/llamada0_modelos.PROMPTS["v7"]`.
"""
import json
import re

_S = {"type": "string"}
ESQUEMA = {"type": "object", "additionalProperties": False, "required": ["lineas"], "properties": {"lineas": {
    "type": "array", "items": {"type": "object", "additionalProperties": False,
                               "required": ["fragmento", "producto", "condiciones", "destino"],
                               "properties": {"fragmento": _S, "producto": _S, "condiciones": _S, "destino": _S}}}}}
# El producto que el modelo no supo: los embeddings del fragmento traen los candidatos y elige Jev.
NO_SABE = "?"
PROMPT = 'Sos el primer paso de un sistema que atiende clientes de una tienda online. Del mensaje del cliente,\ndevolve una linea por cada cosa que pide o pregunta, sin dejar ninguna afuera aunque el mensaje sea largo:\n- fragmento: la parte del mensaje que nombra esa cosa, con las palabras del cliente.\n- producto: que tipo de producto busca, con el nombre que usaria la tienda. Si busca un producto pero no sabes cual\n  es, escribi solo un signo de pregunta: ?. Vacio si no busca un producto.\n- condiciones: todo lo que el cliente pide de como tiene que ser ese producto o para que lo quiere: marca, modelo,\n  medida, capacidad, color, tipo, origen, uso, compatibilidad, precio o tope, el mas barato. Lo que dice para varios\n  productos o para todo el mensaje, como "todo inalambrico" o "lo mas barato posible", va repetido en cada linea a la\n  que se aplica. Los numeros, en cifras, y sin signos de puntuacion. No va: la cantidad de unidades, el destino, el pago\n  ni comentarios que no dicen como tiene que ser el producto. Vacio si no pide nada de eso.\n- destino: el lugar a donde hay que enviarlo, solo si el cliente lo dijo; si no, vacio.\nUn producto por linea: si pide dos productos, o dos variantes del mismo, como uno negro y uno rojo, van en lineas\nseparadas. Varias unidades iguales van en una linea, salvo que vayan a destinos distintos: una linea por destino. Si el\ncliente se corrige, vale lo ultimo que dijo. No contestes ni decidas nada. Tu unica fuente es lo que escribio el cliente.'


def busqueda(l):
    """La busqueda de una linea: el producto y sus condiciones juntos, como la mide el banco. Con "?", el fragmento en
    lugar del producto; vacia si no busca un producto."""
    pr = str(l.get("producto") or "").strip()
    if not pr:
        return ""
    pr = str(l.get("fragmento") or "").strip() if pr == NO_SABE else pr
    return f"{pr} {str(l.get('condiciones') or '').strip()}".strip()


def valida(x):
    return isinstance(x, dict) and isinstance(x.get("lineas"), list) and all(
        isinstance(l, dict) and "fragmento" in l and "producto" in l for l in x["lineas"])


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
