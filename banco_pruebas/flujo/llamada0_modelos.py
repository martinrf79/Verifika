"""LA LLAMADA 0 CON OTROS PROMPTS Y OTROS MODELOS, SOBRE LAS 140 (16-nov-2026).

Orden de Martin del 16-nov, FICHA 99 seccion 6, paso 1: primero el prompt con Gemini por la gratis, despues otros
modelos de costo parecido. La vara es `llamada0_vara.py`, por mensaje, escrita antes de correr. La salida de cada corrida
se graba por mensaje en `llamada0_modelos.jsonl`; los nexos corren despues sobre lo grabado, sin gasto.

LAS CORRIDAS, una por modelo y prompt. La base, Gemini con el prompt de hoy, es `flujo_nuevo_llamada0.jsonl`.
  gemini-lite   gemini-3.1-flash-lite, el de produccion, razonamiento bajo, clave gratis.
  gemini-38     gemini-3.8-flash, razonamiento bajo, clave gratis.
  haiku         claude-haiku-5-5, razonamiento alto, clave de Anthropic.
  deepseek      deepseek-flash, la V4.1, razonamiento max, el mas alto, clave de DeepSeek.
  luna          openai/gpt-6-luna por OpenRouter, razonamiento bajo por la latencia.
  qwen          qwen/qwen3.8-flash por OpenRouter, sin razonamiento: con el bajo piensa igual, hasta 16 mil tokens y
                210 segundos en un mensaje, medido en el piloto como qwen-low, y se corto.
  luna-medio    lo mismo que luna con razonamiento medio, para ver cuanto agrega pensar.
EL GASTO: OpenRouter tiene un tope de 20 centavos entre luna y qwen, orden de Martin; cada corrida corta en su tope.
`--piloto` corre 10 mensajes y estima las 140 con lo medido.

    python3 banco_pruebas/flujo/llamada0_modelos.py --correr gemini-lite v2 [--piloto]
    python3 banco_pruebas/flujo/llamada0_modelos.py                 # califica todo lo grabado, sin gasto
    python3 banco_pruebas/flujo/llamada0_modelos.py --ver luna v2   # el detalle de las fallas de una corrida
"""
import collections
import json
import os
import re
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entorno import GRABADO  # noqa: E402

import engranaje0 as E  # noqa: E402
import flujo_nuevo as F  # noqa: E402
import llamada0_vara as V  # noqa: E402

SALIDA = os.path.join(GRABADO, "llamada0_modelos.jsonl")
OPENROUTER = "https://openrouter.ai/api/v1"
# (proveedor, modelo, razonamiento, dolares por millon de entrada y de salida, tope en dolares de la corrida)
MODELOS = {
    "gemini-lite": ("gemini", "gemini-3.1-flash-lite", "low", 0.25, 1.50, 0.0),
    "gemini-38": ("gemini", "gemini-3.8-flash", "low", 0.75, 3.75, 0.0),
    "haiku": ("anthropic", "claude-haiku-5-5", "high", 0.10, 0.50, 0.20),
    "deepseek": ("deepseek", "deepseek-flash", "max", 0.15, 0.60, 0.20),
    # Como se uso en el banco, `engranaje0`: deepseek-chat, sin razonamiento, temperatura 0. Y Haiku con el bajo.
    "deepseek-chat": ("deepseek", "deepseek-chat", "none", 0.15, 0.60, 0.10),
    "haiku-bajo": ("anthropic", "claude-haiku-5-5", "low", 0.10, 0.50, 0.15),
    # La elegida por Martin el 16-nov, FICHA 100. Desde el 16-nov por la clave directa de OpenAI: por OpenRouter queda
    # poco saldo. Lo grabado hasta el 16-nov vino por OpenRouter; es el mismo modelo. El tope, el ultimo numero, es lo
    # gastado con este modelo en todo el banco: 12 centavos hasta el 16-nov, con 11 ya usados; Martin lo sube a un dolar
    # el 16-nov para los nexos, la memoria y la segunda llamada, y a 1,35 el 18-nov para grabar las 26 charlas con la
    # llamada 0 v7: lo gastado en todo el banco ya era 1,29 contando la segunda llamada, y la grabacion cuesta 2 centavos.
    "luna": ("openai", "gpt-6-luna", "low", 0.10, 0.50, 1.35),
    "qwen": ("openrouter", "qwen/qwen3.8-flash", "none", 0.15, 0.47, 0.06),
    "qwen-low": ("openrouter", "qwen/qwen3.8-flash", "low", 0.15, 0.47, 0.02),
    "luna-medio": ("openrouter", "openai/gpt-6-luna", "medium", 0.10, 0.50, 0.08),
}
TOPE_OPENROUTER = 0.20

# v1, el de hoy: el engranaje 0 mas el destino. v2, lo que la FICHA 99 le pide a la llamada 0: la condicion en cada
# linea, tambien la del mensaje entero; una linea por producto y por variante; lo corregido no cuenta; nada se pierde.
PROMPTS = {"v1": F.PROMPT}
# La v2, la del bot del 17 al 18-nov. Desde el 18-nov el bot usa la v7, FICHA 102: la v2 queda aca, para lo grabado.
PROMPTS["v2"] = 'Sos el primer paso de un sistema que atiende clientes de una tienda online. Del mensaje del cliente,\ndevolve una linea por cada cosa que pide o pregunta, sin dejar ninguna afuera aunque el mensaje sea largo:\n- fragmento: la parte del mensaje que lo dice, con las palabras del cliente.\n- busqueda: lo que escribirias en el buscador de una tienda online para encontrarlo, con el producto primero y despues\n  todo lo que el cliente pide de el: marca, modelo, medida, capacidad, color, tipo, precio o tope por unidad. Lo que\n  dice para varios productos o para todo el mensaje, como "todo inalambrico" o "lo mas barato posible", va repetido\n  en la busqueda de cada linea a la que se aplica. Vacio si no busca un producto.\n- destino: el lugar a donde hay que enviarlo, solo si el cliente lo dijo; si no, vacio.\nUn producto por linea: si pide dos productos, o dos variantes del mismo, como uno negro y uno rojo, van en lineas\nseparadas. Si el cliente se corrige, vale lo ultimo que dijo.\nNo contestes ni decidas nada. Tu unica fuente es lo que escribio el cliente.'

# v4, 17-nov, orden de Martin: la v2 separa bien pero escribe de mas en la busqueda, la cantidad, comentarios y signos,
# y el nexo de condicion los toma por condiciones. Las mismas tres cosas por linea; la busqueda atada a producto y
# condiciones, con una sola linea de lo que no va; la jerga que no entiende, tal cual; el fragmento, donde nombra la cosa;
# dos iguales en una linea salvo que vayan a destinos distintos. Sin ejemplo: con ejemplo, la v3 copiaba en vez de traducir.
PROMPTS["v4"] = """Sos el primer paso de un sistema que atiende clientes de una tienda online. Del mensaje del cliente,
devolve una linea por cada cosa que pide o pregunta, sin dejar ninguna afuera aunque el mensaje sea largo:
- fragmento: la parte del mensaje que nombra esa cosa, con las palabras del cliente.
- busqueda: lo que escribirias en el buscador de una tienda online para encontrarlo: el producto primero y despues solo
  lo que el cliente pide de como tiene que ser: marca, modelo, medida, capacidad, color, tipo, origen, tope por unidad o
  el mas barato. Lo que dice para varios productos o para todo el mensaje, como "todo inalambrico" o "lo mas barato
  posible", va repetido en la busqueda de cada linea a la que se aplica. Escribilo como lo diria la tienda; lo que no
  sepas que quiere decir, dejalo con las palabras del cliente, corrigiendo solo la ortografia. En la busqueda no va: la
  cantidad, el destino, el pago, el total, comentarios ni signos de puntuacion. Vacio si no busca un producto.
- destino: el lugar a donde hay que enviarlo, solo si el cliente lo dijo; si no, vacio.
Un producto por linea: si pide dos productos, o dos variantes del mismo, como uno negro y uno rojo, van en lineas
separadas. Varias unidades iguales van en una linea, salvo que vayan a destinos distintos: una linea por destino. Si el
cliente se corrige, vale lo ultimo que dijo. No contestes ni decidas nada. Tu unica fuente es lo que escribio el cliente."""

# v5, 17-nov, orden de Martin, por lo medido de la v4: limpia la busqueda, 0 signos y 0 cantidades, pero pierde
# condiciones por dos causas. La jerga: "lo que no sepas" la volvio literal, "eso que se pone adentro de la pc para que
# corran los jueguitos"; ahora traduce siempre al producto y deja las palabras del cliente solo si no sabe que producto
# es. La lista de lo que va era corta y perdia el uso, "para la oficina", la compatibilidad, "con fuente de 550 watts", y
# el tope, "menos de 200 mil"; ahora estan, con los numeros en cifras.
PROMPTS["v5"] = """Sos el primer paso de un sistema que atiende clientes de una tienda online. Del mensaje del cliente,
devolve una linea por cada cosa que pide o pregunta, sin dejar ninguna afuera aunque el mensaje sea largo:
- fragmento: la parte del mensaje que nombra esa cosa, con las palabras del cliente.
- busqueda: lo que escribirias en el buscador de una tienda online para encontrarlo: primero el producto, con el nombre
  que usaria la tienda, y despues todo lo que el cliente pide de como tiene que ser o para que lo quiere: marca, modelo,
  medida, capacidad, color, tipo, origen, uso, compatibilidad, precio o tope, el mas barato. Lo que dice para varios
  productos o para todo el mensaje, como "todo inalambrico" o "lo mas barato posible", va repetido en la busqueda de
  cada linea a la que se aplica. Los numeros, en cifras. Si no sabes que producto es, deja las palabras del cliente,
  corrigiendo solo la ortografia. En la busqueda no va: la cantidad de unidades, el destino, el pago, comentarios que
  no dicen como tiene que ser el producto, ni signos de puntuacion. Vacio si no busca un producto.
- destino: el lugar a donde hay que enviarlo, solo si el cliente lo dijo; si no, vacio.
Un producto por linea: si pide dos productos, o dos variantes del mismo, como uno negro y uno rojo, van en lineas
separadas. Varias unidades iguales van en una linea, salvo que vayan a destinos distintos: una linea por destino. Si el
cliente se corrige, vale lo ultimo que dijo. No contestes ni decidas nada. Tu unica fuente es lo que escribio el cliente."""

# v6, 17-nov, propuesta medida con el ok de Martin: los mismos pedidos que la v5, pero el producto y lo que pide de el en
# dos campos. Hoy una funcion de codigo corta de la busqueda que parte es el producto, y esa funcion pisaba a los
# embeddings; con los dos campos, el producto va a la busqueda cero y las condiciones a la segunda busqueda, sin cortar.
# Sin ejemplo, que en la v3 hacia copiar. Para la vara, que lee la busqueda, la busqueda es producto y condiciones juntos.
PROMPTS["v6"] = """Sos el primer paso de un sistema que atiende clientes de una tienda online. Del mensaje del cliente,
devolve una linea por cada cosa que pide o pregunta, sin dejar ninguna afuera aunque el mensaje sea largo:
- fragmento: la parte del mensaje que nombra esa cosa, con las palabras del cliente.
- producto: que tipo de producto busca, con el nombre que usaria la tienda. Si no sabes que producto es, deja las
  palabras del cliente, corrigiendo solo la ortografia. Vacio si no busca un producto.
- condiciones: todo lo que el cliente pide de como tiene que ser ese producto o para que lo quiere: marca, modelo,
  medida, capacidad, color, tipo, origen, uso, compatibilidad, precio o tope, el mas barato. Lo que dice para varios
  productos o para todo el mensaje, como "todo inalambrico" o "lo mas barato posible", va repetido en cada linea a la
  que se aplica. Los numeros, en cifras, y sin signos de puntuacion. No va: la cantidad de unidades, el destino, el pago
  ni comentarios que no dicen como tiene que ser el producto. Vacio si no pide nada de eso.
- destino: el lugar a donde hay que enviarlo, solo si el cliente lo dijo; si no, vacio.
Un producto por linea: si pide dos productos, o dos variantes del mismo, como uno negro y uno rojo, van en lineas
separadas. Varias unidades iguales van en una linea, salvo que vayan a destinos distintos: una linea por destino. Si el
cliente se corrige, vale lo ultimo que dijo. No contestes ni decidas nada. Tu unica fuente es lo que escribio el cliente."""

# v7, 18-nov, orden de Martin: la v6 con una sola diferencia. Cuando Luna traduce, su producto es la verdad; cuando no
# sabe que producto es, lo dice: escribe "?" en el producto, y ahi los embeddings del fragmento traen 8 candidatos y elige
# Jev. El codigo no puede adivinar cuando Luna no tradujo: "mouse" tambien son las palabras del cliente.
PROMPTS["v7"] = PROMPTS["v6"].replace(
    """- producto: que tipo de producto busca, con el nombre que usaria la tienda. Si no sabes que producto es, deja las
  palabras del cliente, corrigiendo solo la ortografia. Vacio si no busca un producto.""",
    """- producto: que tipo de producto busca, con el nombre que usaria la tienda. Si busca un producto pero no sabes cual
  es, escribi solo un signo de pregunta: ?. Vacio si no busca un producto.""")
assert PROMPTS["v7"] != PROMPTS["v6"]
# Desde el 18-nov la v7 es la del bot, `app/core/flujo/nuevo/llamada0.py`: tiene que ser la misma que se midio.
from app.core.flujo.nuevo import llamada0 as _L0  # noqa: E402
assert _L0.PROMPT == PROMPTS["v7"], "el prompt del bot no es la v7 medida"

# v8, 18-nov, orden de Martin: la v7 igual en separar, traducir y el destino; lo unico distinto es lo que Luna no traduce.
# En vez de "?", que borraba las palabras del cliente, las deja entre corchetes, corrigiendo solo la ortografia. Lo que
# esta entre corchetes lo buscan los embeddings contra los productos de la tienda y elige Jev, `llamada0_jerga.py`.
PROMPTS["v8"] = PROMPTS["v7"].replace(
    """Si busca un producto pero no sabes cual
  es, escribi solo un signo de pregunta: ?. Vacio si no busca un producto.""",
    """Si busca un producto pero no sabes cual
  es, o no sabes como se llama, escribi las palabras del cliente entre corchetes, corrigiendo solo la ortografia:
  [asi]. Vacio si no busca un producto.""")
assert PROMPTS["v8"] != PROMPTS["v7"]

# v9, 19-nov, orden de Martin, por la entrevista a Luna del 19-nov: cada fila es una parte del mensaje con su nexo, y las
# partes de una misma cosa llevan el mismo numero de pedido. La fuente de verdad es el mensaje: no agrega, no inventa, no
# elige y no resuelve lo que el cliente no dijo. Lo que no sabe, entre corchetes. La cantidad en su campo, que es lo que
# Luna pidio: sin ella duplicaba lineas. Sin ejemplo armado, que en la v3 hacia copiar.
PROMPTS["v9"] = """Sos el primer paso de una tienda online. No contestas ni decidis nada: anotas lo que pide el cliente, en filas.
La unica fuente de verdad es el mensaje del cliente. No agregues, no inventes, no completes, no elijas entre
opciones y no resuelvas lo que el cliente no dijo.

Cada fila es una parte del mensaje con su nexo:
- producto: el tipo de producto que busca.
- nombrado: la marca o el modelo que nombra.
- condicion: como tiene que ser o para que lo quiere: medida, color, tipo, origen, uso, compatibilidad, precio,
  tope, el mas barato.
- tema: una pregunta sobre la tienda y no sobre un producto: pago, cuotas, envios, garantia, factura, descuentos.
- destino: el lugar a donde lo manda.
- otro: lo que no es nada de eso: saludos, comentarios, preguntas que no son de la tienda.

Campos de cada fila:
- pedido: el numero de la cosa que pide; las filas de una misma cosa llevan el mismo numero. Tema y otro, 0.
- dijo y texto: en dijo, la parte del mensaje que corresponde a esa fila, copiada del mensaje. En texto, esa misma
  parte lista para buscar: con la ortografia corregida y los numeros en cifras; en producto, el nombre comun del
  producto, traducido si es jerga. Si no sabes que es o a que se refiere, en texto van las palabras del cliente
  entre corchetes: [asi].
- cantidad: las unidades, si las dijo; si no, vacio.

Reglas:
- Si nombra opciones para elegir, como dos modelos y "el que no tenga cable", van las dos en una fila nombrado, sin elegir.
- Si pregunta por cualquier producto de la tienda, como "el articulo mas caro", el texto del producto es: toda la tienda.
- Lo que dice para todo el mensaje, como "todo inalambrico", va en cada pedido al que se aplica.
- Un pedido por cosa y por destino. Si no dice que cosa va a cada lugar, no lo repartas: anota lo que dijo, como
  "[los otros dos articulos]", con su destino.
- Si se corrige, vale lo ultimo que dijo."""
NEXOS9 = ["producto", "nombrado", "condicion", "tema", "destino", "otro"]

# v10, 19-nov, orden de Martin, por la latencia del v9: lo mas sencillo. Cada linea es un solo texto, la parte del
# mensaje con las palabras del cliente, la ortografia corregida y la jerga traducida; lo que no sabe, entre corchetes.
# El destino queda adentro del texto y lo saca el nexo de destino; Luna solo separa por lugar.
PROMPTS["v10"] = """Sos el primer paso de una tienda online. No contestas ni decidis nada. La unica fuente de verdad es el mensaje
del cliente.
Separa el mensaje en lineas: una por cada cosa que pide o pregunta, sin dejar ninguna afuera. Si la misma cosa va
a lugares distintos, una linea por lugar.
Cada linea es la parte del mensaje con las palabras del cliente: corregi la ortografia, escribi los numeros en
cifras y traduci la jerga a como se dice en una tienda argentina. Lo que no sepas que es, dejalo entre corchetes.
Lo que dice para todo el mensaje, como "todo inalambrico", va en cada linea a la que se aplica.
No agregues, no elijas entre opciones y no resuelvas lo que el cliente no dijo."""

# v11, 19-nov, orden de Martin, por lo leido del v10: la misma base, con cuatro frases. Los corchetes con las palabras
# exactas del cliente; nada que el cliente no escribio; el pago y lo que no es de un producto en su linea; nunca dos
# productos distintos en una linea.
PROMPTS["v11"] = """Sos el primer paso de una tienda online. No contestas ni decidis nada. La unica fuente de verdad es el mensaje
del cliente.
Separa el mensaje en lineas: una por cada cosa que pide o pregunta, sin dejar ninguna afuera. Nunca dos productos
distintos en la misma linea. Si la misma cosa va a lugares distintos, una linea por lugar.
Cada linea es la parte del mensaje con las palabras del cliente: corregi la ortografia, escribi los numeros en
cifras y traduci la jerga a como se dice en una tienda argentina. Lo que no sepas que es, copialo entre corchetes
con las palabras exactas del cliente, sin cambiarlas.
Lo que dice para todo el mensaje, como "todo inalambrico", va en cada linea a la que se aplica. El pago, el
presupuesto y lo que no es de un producto van en su propia linea, no en la del producto.
No agregues tipo, marca ni nada que el cliente no escribio, no elijas entre opciones y no resuelvas lo que el
cliente no dijo."""


def lineas_de_filas(filas):
    """Las filas de la v9 como las lineas que leen la vara y los nexos de hoy: una por pedido, la busqueda con el producto,
    lo nombrado y las condiciones, sin corchetes; el fragmento, lo que dijo el cliente. Tema y otro, una linea cada uno."""
    por, out = {}, []
    for f in filas:
        if f.get("nexo") in ("tema", "otro") or not f.get("pedido"):
            out.append({"fragmento": f.get("dijo", ""), "busqueda": "", "destino": "", "producto": "", "condiciones": ""})
            continue
        por.setdefault(f["pedido"], []).append(f)
    for p, fs in por.items():
        de = lambda nx: " ".join(str(f.get("texto") or "") for f in fs if f.get("nexo") == nx).replace("[", "").replace("]", "").strip()
        pr, cond = de("producto"), " ".join(x for x in (de("nombrado"), de("condicion")) if x)
        out.append({"fragmento": " ".join(str(f.get("dijo") or "") for f in fs), "producto": pr, "condiciones": cond,
                    "busqueda": f"{pr} {cond}".strip(), "destino": de("destino")})
    return out

# v3, 16-nov, orden de Martin: lo que falla la v2 es la estructura, partir un producto en dos lineas y perder
# condiciones, sobre todo las del mensaje entero. Todo dentro de la llamada: primero la lista de productos distintos,
# despues una linea por cada uno con sus condiciones en una lista, y un ejemplo inventado que no esta en ningun banco.
PROMPTS["v3"] = """Sos el primer paso de un sistema que atiende clientes de una tienda online. Del mensaje del cliente:
1. productos: la lista de los productos distintos que pide. Dos del mismo producto con distinta caracteristica, como
   uno negro y uno rojo, son dos productos. Una caracteristica no es un producto.
2. lineas: una por cada producto de la lista, y una por cada pregunta que no es un producto, sin dejar ninguna afuera
   aunque el mensaje sea largo:
- fragmento: la parte del mensaje que lo dice, con las palabras del cliente.
- condiciones: todo lo que el cliente pide de ese producto: marca, modelo, medida, capacidad, color, tipo, precio o
  tope por unidad. Lo que dice para varios productos o para todo el mensaje va repetido en cada linea a la que se
  aplica. Nada que el cliente no haya dicho. Vacia si no pide nada de eso.
- busqueda: lo que escribirias en el buscador de una tienda online: el producto y todas sus condiciones. Vacio si no
  busca un producto.
- destino: el lugar a donde hay que enviarlo, solo si el cliente lo dijo; si no, vacio.
Si el cliente se corrige, vale lo ultimo que dijo. No contestes ni decidas nada. Tu unica fuente es lo que escribio el
cliente.

Ejemplo. Mensaje: "quiero dos lamparas de escritorio y un velador, todo en blanco y que no pase los 20 mil cada uno, el
velador mandalo a Lujan"
{"productos": ["lampara de escritorio", "velador"], "lineas": [
{"fragmento": "dos lamparas de escritorio", "condiciones": ["blanco", "hasta 20 mil cada uno"],
 "busqueda": "lampara de escritorio blanca hasta 20000", "destino": ""},
{"fragmento": "un velador", "condiciones": ["blanco", "hasta 20 mil cada uno"],
 "busqueda": "velador blanco hasta 20000", "destino": "Lujan"}]}"""
_S = {"type": "string"}
ESQUEMAS = {"v3": {"type": "object", "additionalProperties": False, "required": ["productos", "lineas"], "properties": {
    "productos": {"type": "array", "items": _S},
    "lineas": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["fragmento", "condiciones", "busqueda", "destino"],
        "properties": {"fragmento": _S, "condiciones": {"type": "array", "items": _S}, "busqueda": _S,
                       "destino": _S}}}}}}

ESQUEMAS["v6"] = {"type": "object", "additionalProperties": False, "required": ["lineas"], "properties": {
    "lineas": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["fragmento", "producto", "condiciones", "destino"],
        "properties": {"fragmento": _S, "producto": _S, "condiciones": _S, "destino": _S}}}}}
ESQUEMAS["v7"] = _L0.ESQUEMA
assert ESQUEMAS["v7"] == ESQUEMAS["v6"]
ESQUEMAS["v8"] = ESQUEMAS["v6"]
ESQUEMAS["v9"] = {"type": "object", "additionalProperties": False, "required": ["filas"], "properties": {
    "filas": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["pedido", "nexo", "dijo", "texto", "cantidad"],
        "properties": {"pedido": {"type": "integer"},
                       "nexo": {"type": "string", "enum": ["producto", "nombrado", "condicion", "tema", "destino", "otro"]},
                       "dijo": _S, "texto": _S, "cantidad": _S}}}}}
ESQUEMAS["v10"] = {"type": "object", "additionalProperties": False, "required": ["textos"], "properties": {
    "textos": {"type": "array", "items": _S}}}
ESQUEMAS["v11"] = ESQUEMAS["v10"]


# ══ LAS CORRIDAS ═════════════════════════════════════════════════════════════
def _clave(nombre):
    return os.environ[nombre].split()[0]


def pedir(corrida, prompt, texto):
    """(salida, entrada, salida_tokens, segundos, dolares)."""
    prov, modelo, esfuerzo, pe, ps, _ = MODELOS[corrida]
    # "v3#2" es la segunda corrida del prompt v3: el mismo prompt, otra muestra.
    base = prompt.split("#")[0]
    sistema = PROMPTS[base]
    esquema = ESQUEMAS.get(base, F.ESQUEMA)
    usuario = f"MENSAJE DEL CLIENTE: {texto}"
    fmt = {"type": "json_schema", "json_schema": {"name": "lineas", "strict": True, "schema": esquema}}
    t0 = time.time()
    dol = None
    if prov == "anthropic":
        import anthropic
        cli = anthropic.Anthropic(api_key=_clave("CLAUDE_API_KEY"))
        r = cli.messages.create(model=modelo, max_tokens=16000, system=sistema,
                                messages=[{"role": "user", "content": usuario}],
                                output_config={"effort": esfuerzo, "format": {"type": "json_schema", "schema": esquema}})
        crudo = next((b.text for b in r.content if b.type == "text"), "")
        e, s = r.usage.input_tokens, r.usage.output_tokens
    else:
        from openai import OpenAI
        from app.config import get_settings
        k = {"model": modelo, "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
             "response_format": fmt}
        if prov == "gemini":
            # La gratis; la paga solo con la orden de Martin, mirando el tope del dia y anotada en `libro_paga`.
            paga = bool(os.environ.get("MARTIN_AUTORIZO_LA_PAGA"))
            if paga:
                from banco_pruebas import libro_paga
                libro_paga.puede()
            cli = OpenAI(api_key=_clave("GEMINI_API_KEY_PROD" if paga else "GEMINI_API_KEY"),
                         base_url=get_settings().GEMINI_BASE_URL, timeout=120, max_retries=0)
            k["reasoning_effort"] = esfuerzo
        elif prov == "deepseek":
            # DeepSeek no toma json_schema: el esquema va escrito y el modo es JSON, como en `engranaje0`.
            cli = OpenAI(api_key=_clave("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
            if esfuerzo == "none":
                k["temperature"] = 0
            else:
                k["reasoning_effort"] = esfuerzo
            k["response_format"] = {"type": "json_object"}
            k["messages"][0]["content"] += "\nDevolve solo el JSON, con este esquema: " + json.dumps(esquema)
        elif prov == "openai":
            cli = OpenAI(api_key=_clave("OPENAI_API_KEY"), timeout=120, max_retries=2)
            k["reasoning_effort"] = esfuerzo
        else:
            cli = OpenAI(api_key=_clave("OPENROUTER_API_KEY"), base_url=OPENROUTER)
            k["extra_body"] = {"reasoning": {"enabled": False} if esfuerzo == "none" else {"effort": esfuerzo},
                               "usage": {"include": True}}
        r = cli.chat.completions.create(**k)
        crudo = r.choices[0].message.content or ""
        u = r.usage
        e, s = int(u.prompt_tokens or 0), int(u.completion_tokens or 0)
        if prov == "openrouter":
            dol = float(getattr(u, "cost", None) or (u.model_extra or {}).get("cost") or 0)
        if prov == "gemini" and os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
            from banco_pruebas import libro_paga
            dol = libro_paga.anotar(modelo, e, s)
    seg = round(time.time() - t0, 2)
    if dol is None:
        dol = (e * pe + s * ps) / 1e6
    t = re.sub(r"^```(?:json)?|```$", "", crudo.strip(), flags=re.M).strip()
    try:
        salida = json.loads(t[t.find("{"):t.rfind("}") + 1])
    except Exception:  # noqa: BLE001
        salida = None
    if base in ("v10", "v11") and isinstance(salida, dict) and isinstance(salida.get("textos"), list):
        # Cada texto es su linea: la vara lee la busqueda sin corchetes; el producto lleva el texto entero, para que
        # `llamada0_jerga.py` encuentre lo que quedo entre corchetes.
        salida["lineas"] = [{"fragmento": str(t), "producto": str(t), "condiciones": "", "destino": "",
                             "busqueda": str(t).replace("[", "").replace("]", "")} for t in salida["textos"]]
    if base == "v9" and isinstance(salida, dict) and isinstance(salida.get("filas"), list):
        salida["lineas"] = lineas_de_filas(salida["filas"])
    if base in ("v6", "v7", "v8") and isinstance(salida, dict):
        # La vara lee la busqueda: el producto y las condiciones juntos. Los dos campos quedan grabados. Con la v7, el
        # producto que Luna no supo, "?", es el fragmento: la vara lo cuenta como no traducido. Con la v8, lo que esta
        # entre corchetes, sin los corchetes.
        for l in salida.get("lineas") or []:
            if isinstance(l, dict):
                pr = str(l.get("producto") or "").strip()
                pr = str(l.get("fragmento") or "") if pr == "?" else pr.replace("[", "").replace("]", "").strip()
                l["busqueda"] = f"{pr} {l.get('condiciones') or ''}".strip()
    return salida, e, s, seg, round(dol, 7), crudo


def filas():
    return [json.loads(x) for x in open(SALIDA, encoding="utf-8")] if os.path.exists(SALIDA) else []


def gastado(pred):
    return sum(r.get("dolares") or 0 for r in filas() if pred(r))


def casos_de(banco):
    """[(banco, id, mensaje)]: "140", las de `flujo_nuevo`; "reales" y "reales525", las de `reales.py`."""
    if banco == "140":
        return [(b, cid, t) for b, cid, t, _, _ in F.bancos()]
    if banco == "charlas26":
        # Las 26 charlas de la vara del bot, un mensaje por turno, "charla|turno": las lee `segunda.py`.
        import segunda as SG
        return [(banco, f"{ch}|{g['turno']}", g["mensaje"]) for ch, gs in SG.charlas().items() for g in gs]
    if banco == "200":
        # Las 200 dificiles del 18-nov, `llamada0_jerga.py --armar`: cada una con su banco de origen.
        d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bancos", "las200.json"), encoding="utf-8"))
        return [(c["banco"], c["id"], c["texto"]) for c in d["casos"]]
    if banco == "nombrados38":
        from nombrados38 import CASOS
        return [(banco, cid, t) for cid, t, _ in CASOS]
    import reales as RE
    return [(banco, c[0], c[1]) for c in (RE.CASOS if banco == "reales" else RE.casos_525()[0])]


def correr(corrida, prompt, piloto=False, banco="140"):
    prov = MODELOS[corrida][0]
    # Los ids de los reales, R01 a R40, chocan con los de nuevas70: lo hecho se cuenta por banco.
    hechas = {(r["banco"], r["id"]) for r in filas() if r["corrida"] == corrida and r["prompt"] == prompt and r.get("salida")}
    casos = casos_de(banco)
    if piloto:
        # Diez de los dos bancos, de todos los tipos: los primeros de cada letra.
        casos = [c for c in casos if c[1] in ("M01", "M08", "M15", "R17", "O04", "F03", "A04", "B01", "B59", "B66")]
    falta = [c for c in casos if (c[0], c[1]) not in hechas]
    if "--parte" in sys.argv:
        # "--parte 2/4": este proceso corre uno de cada cuatro, para repartir una corrida lenta.
        i, n = map(int, sys.argv[sys.argv.index("--parte") + 1].split("/"))
        falta = falta[i::n]
    print(f"[{corrida} {prompt}, {MODELOS[corrida][1]}: {len(falta)} por correr]", flush=True)
    for banco, cid, texto in falta:
        if MODELOS[corrida][5] and gastado(lambda r: r["corrida"] == corrida) >= MODELOS[corrida][5]:
            raise SystemExit(f"tope de {MODELOS[corrida][5]} dolares para {corrida}")
        if prov == "openrouter" and gastado(lambda r: MODELOS[r["corrida"]][0] == "openrouter") >= TOPE_OPENROUTER:
            raise SystemExit(f"tope de {TOPE_OPENROUTER} dolares de OpenRouter")
        fila = {"corrida": corrida, "prompt": prompt, "banco": banco, "id": cid, "modelo": MODELOS[corrida][1]}
        for intento in range(5):
            try:
                salida, e, s, seg, dol, crudo = pedir(corrida, prompt, texto)
                fila.update({"entrada": e, "salida_tokens": s, "segundos": seg,
                             "dolares": round((fila.get("dolares") or 0) + dol, 7)})
                if E.valido(salida):
                    fila.update({"salida": salida, "reintentos": intento})
                    fila.pop("error", None)
                    break
                fila["invalida"] = crudo[:300]
            except Exception as ex:  # noqa: BLE001
                fila["error"] = f"{type(ex).__name__}: {str(ex)[:300]}"
                print(f"  {cid} intento {intento}: {fila['error']}", flush=True)
                time.sleep(15 * (intento + 1) if "429" in fila["error"] else 5)
        with open(SALIDA, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
        if prov == "gemini" and not os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
            time.sleep(4)
    rs = [r for r in filas() if r["corrida"] == corrida and r["prompt"] == prompt]
    if rs:
        d = sum(r.get("dolares") or 0 for r in rs)
        print(f"  {len(rs)} grabadas · {d:.4f} dolares · {d / len(rs) * 140:.4f} estimado para las 140 · "
              f"{statistics.mean(r.get('segundos') or 0 for r in rs):.1f} s · "
              f"{statistics.mean(r.get('salida_tokens') or 0 for r in rs):.0f} tokens de salida")


# ══ LA VARA ══════════════════════════════════════════════════════════════════
def _tiene(texto, raices):
    return any(E.n(x) in texto for x in raices)


def _pos(texto, raices):
    """(posicion, -largo) de la primera raiz en la busqueda, o None."""
    ps = [(texto.find(E.n(x)), -len(E.n(x))) for x in raices if E.n(x) and E.n(x) in texto]
    return min(ps) if ps else None


def calificar_mensaje(cid, texto, destinos, lineas):
    c, malos = collections.Counter(), []
    cosas = V.VARA.get(cid, [])
    busq = [E.n(l.get("busqueda")) for l in lineas]
    # Cada linea va a la cosa cuya raiz aparece primero; si empatan, a la de raiz mas larga; si siguen, a todas.
    de = collections.defaultdict(list)
    for i, b in enumerate(busq):
        if not b:
            continue
        cand = [(p, j) for j, cosa in enumerate(cosas)
                if (p := _pos(b, cosa["raices"])) is not None and (not cosa["solo"] or _tiene(b, cosa["solo"]))]
        if cand:
            mejor = min(p for p, _ in cand)
            for p, j in cand:
                if p == mejor:
                    de[j].append(i)
    usadas = collections.Counter(i for js in de.values() for i in js)
    for j, cosa in enumerate(cosas):
        nombre = (cosa["solo"] or cosa["raices"])[0]
        c["cosas"] += 1
        c["condiciones"] += len(cosa["condiciones"])
        mias = de.get(j, [])
        if not mias:
            c["cosas perdidas"] += 1
            c["condiciones perdidas"] += len(cosa["condiciones"])
            malos.append(f"pierde {nombre}")
            continue
        if any(usadas[i] > 1 for i in mias):
            c["cosas juntas"] += 1
            malos.append(f"junta {nombre}")
        for cond in cosa["condiciones"]:
            if all(_tiene(busq[i], cond) for i in mias):
                c["condiciones bien"] += 1
            else:
                c["condiciones perdidas"] += 1
                malos.append(f"pierde '{cond[0]}' en {nombre}")
    msj = E.n(texto)
    esperadas = [r for cosa in cosas for cond in cosa["condiciones"] for r in cond]
    for i, b in enumerate(busq):
        for t in V.INVENTABLES:
            if _tiene(b, t) and not _tiene(msj, t) and not any(_tiene(E.n(r), t) for r in esperadas):
                c["condiciones inventadas"] += 1
                malos.append(f"inventa '{t[0]}' en '{lineas[i].get('busqueda')}'")
        if cid in V.NO and _tiene(b, V.NO[cid]):
            c["sobra"] += 1
            malos.append(f"sobra '{lineas[i].get('busqueda')}'")
        if E.fiel(lineas[i].get("fragmento"), texto) < 0.5:
            c["fragmento inventado"] += 1
            malos.append(f"fragmento inventado '{str(lineas[i].get('fragmento'))[:40]}'")
    # Los destinos, con el codigo de lugares de produccion, como `flujo_nuevo`.
    hallados = {E.n(r.datos["lugar"]) for l in lineas for r in F.nexo_destino(F.Linea("", "", str(l.get("destino") or "")))
                if r.candidatos} if any(l.get("destino") for l in lineas) else set()
    esperados = {E.n(d) for d in destinos}
    bien = {e for e in esperados if any(e in h or h in e for h in hallados)}
    inventa = {h for h in hallados if not any(e in h or h in e for e in esperados)}
    c["destinos"] += len(esperados)
    c["destinos bien"] += len(bien)
    c["destinos inventados"] += len(inventa)
    if esperados - bien:
        malos.append(f"no halla destino {sorted(esperados - bien)}")
    if inventa:
        malos.append(f"inventa destino {sorted(inventa)}")
    c["lineas"] += len(lineas)
    c["mensajes sin falla"] += not malos
    return c, malos


def corridas():
    """{(corrida, prompt): {id: fila}}, con la base de hoy desde `flujo_nuevo_llamada0.jsonl`."""
    out = collections.defaultdict(dict)
    for r in map(json.loads, open(F.LLAMADA0, encoding="utf-8")):
        out[("gemini-lite", "v1")][r["id"]] = r
    for r in filas():
        if r["banco"] not in ("nuevas70", "nuevas70b"):
            continue
        if r.get("salida") or r["id"] not in out[(r["corrida"], r["prompt"])]:
            out[(r["corrida"], r["prompt"])][r["id"]] = r
    return out


def calificar(ver=None):
    bancos = {cid: (t, d) for _, cid, t, _, d in F.bancos()}
    print("\nLA LLAMADA 0 SOBRE LAS 140 · vara por mensaje, `llamada0_vara.py`")
    cab = ("sin falla", "cosas perdidas", "juntas", "condiciones bien", "inventadas", "destinos bien", "dest inventados",
           "frag inventado", "invalidas", "seg medio", "seg p90", "dolares 140")
    print(f"{'corrida':16} " + " ".join(f"{h:>11}" for h in cab))
    for (corrida, prompt), rs in sorted(corridas().items()):
        c, fallas = collections.Counter(), {}
        for cid, r in rs.items():
            if not r.get("salida"):
                c["invalidas"] += 1
                continue
            cc, malos = calificar_mensaje(cid, *bancos[cid], r["salida"]["lineas"])
            c.update(cc)
            if malos:
                fallas[cid] = malos
        segs = sorted(r.get("segundos") or 0 for r in rs.values())
        dol = sum(r.get("dolares") or 0 for r in rs.values())
        val = [f"{c['mensajes sin falla']}/{len(rs)}", c["cosas perdidas"], c["cosas juntas"] + c["sobra"],
               f"{c['condiciones bien']}/{c['condiciones']}", c["condiciones inventadas"], f"{c['destinos bien']}/{c['destinos']}",
               c["destinos inventados"], c["fragmento inventado"], c["invalidas"],
               f"{statistics.mean(segs):.1f}" if segs else "-", f"{segs[int(len(segs) * .9) - 1]:.1f}" if segs else "-",
               f"{dol / len(rs) * 140:.3f}" if dol else "gratis"]
        print(f"{corrida + ' ' + prompt:16} " + " ".join(f"{str(v):>11}" for v in val))
        if ver and (corrida, prompt) == tuple(ver):
            for cid, malos in fallas.items():
                print(f"    {cid}: {bancos[cid][0][:100]}\n      {'; '.join(malos)}")
                for l in rs[cid]["salida"]["lineas"]:
                    print(f"      · {l.get('busqueda')!r} @{l.get('destino') or ''}")



# ══ LOS REALES Y LAS 365: DONDE SE PIERDE CADA CONDICION ═════════════════════
def _sing(t):
    """Sin la s del plural, para que "memorias" y "memoria" sean lo mismo."""
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in E.n(t).split())


def esperado_reales(banco):
    """{id: {rubro: [raices]}}: los reales a mano; las 365 desde la agenda, como `nexo_condicion.esperado_525`."""
    if banco == "reales":
        return V.REALES
    import reales as RE
    out = {}
    for cid, _, _ in RE.casos_525()[0]:
        c, t, _ = cid.split(".")
        esp = collections.defaultdict(list)
        for p in RE.preguntas_525(c, t):
            if p["accion"] != "buscar" or p["rubro"] == "toda la tienda" or p.get("entre_lo_mostrado"):
                continue
            esp[p["rubro"]] += [V.RAICES_AGENDA[x] for x in p.get("condiciones", []) if x in V.RAICES_AGENDA]
            if p.get("orden") and p["orden"] != "nada" and "ORDEN " + p["orden"] in V.RAICES_AGENDA:
                esp[p["rubro"]].append(V.RAICES_AGENDA["ORDEN " + p["orden"]])
        out[cid] = {r: cs for r, cs in esp.items() if cs}
    return out


def donde_se_pierde(texto, lineas, esperado, alias, memoria=False):
    """Cuenta de un mensaje: cada condicion esperada, en la busqueda de cada linea de su rubro, o donde se perdio."""
    c = collections.Counter()
    raices = {r: [_sing(x) for x in [r] + alias.get(r, [])] for r in esperado}
    de = collections.defaultdict(list)
    for l in lineas:
        b = _sing(l.get("busqueda"))
        cand = [(min(b.find(x) for x in xs if x and x in b), r) for r, xs in raices.items() if any(x and x in b for x in xs)]
        if cand:
            de[min(cand)[1]].append(l)
    msj = E.n(texto)
    for rubro, conds in esperado.items():
        for cond in conds:
            c["condiciones"] += 1
            mias = de.get(rubro, [])
            if memoria:
                k = "memoria"
            elif mias and all(_tiene(E.n(l.get("busqueda")), cond) for l in mias):
                k = "en la busqueda"
            elif any(_tiene(E.n(l.get("fragmento")), cond) for l in mias):
                k = "perdida al traducir"
            elif _tiene(msj, cond):
                k = "perdida al separar" if mias else "perdida al separar, sin linea del rubro"
            else:
                k = "no se ve en el mensaje"
            c[k] += 1
    return c


def corridas_reales(banco):
    out = collections.defaultdict(dict)
    for r in map(json.loads, open(os.path.join(GRABADO, f"{banco}_llamada0.jsonl"), encoding="utf-8")):
        out[("gemini-lite", "v1")][r["id"]] = r
    for r in filas():
        if r["banco"] == banco and (r.get("salida") or r["id"] not in out[(r["corrida"], r["prompt"])]):
            out[(r["corrida"], r["prompt"])][r["id"]] = r
    return out


def calificar_reales():
    import nexo_rubro as NR
    alias = NR.fuente()[1]
    claves = ("en la busqueda", "perdida al separar", "perdida al separar, sin linea del rubro", "perdida al traducir",
              "no se ve en el mensaje", "memoria")
    for banco, nombre in (("reales", "LOS 40 REALES"), ("reales525", "LAS 365")):
        textos = {cid: t for _, cid, t in casos_de(banco)}
        esp = esperado_reales(banco)
        print(f"\n{nombre} · donde se pierde cada condicion, `llamada0_vara.py`")
        print(f"  {'corrida':16} {'conds':>6} " + " ".join(f"{k[:22]:>22}" for k in claves) + f" {'seg':>5} {'dolares':>8}")
        for (corrida, prompt), rs in sorted(corridas_reales(banco).items()):
            c = collections.Counter()
            for cid, e in esp.items():
                r = rs.get(cid)
                if not e:
                    continue
                if not r or not r.get("salida"):
                    c["sin salida"] += 1
                    continue
                c.update(donde_se_pierde(textos[cid], r["salida"]["lineas"], e, alias, memoria=".0." not in cid and "." in cid))
            segs = [r.get("segundos") or 0 for r in rs.values()]
            dol = sum(r.get("dolares") or 0 for r in rs.values())
            print(f"  {corrida + ' ' + prompt:16} {c['condiciones']:>6} " + " ".join(f"{c[k]:>22}" for k in claves)
                  + f" {statistics.mean(segs):>5.1f} {dol:>8.4f}" + (f"  sin salida {c['sin salida']}" if c["sin salida"] else ""))



# ══ LO QUE SOBRA Y LO INVENTADO EN LOS REALES Y LAS 365 (16-nov) ═════════════
# Escrito antes de correrlo, con el ok de Martin. Sin las de memoria, los turnos que no son el primero.
#   duplicada        dos lineas con la misma busqueda y el mismo destino.
#   contada dos      una linea sin destino y otra con destino del mismo rubro: el producto se cuenta dos veces.
#   rubro de mas     el primer candidato de los embeddings es de un rubro que el mensaje no pide ni tolera; no se cuenta
#                    en mensajes que piden algo que la tienda no vende o toda la tienda.
#   inventada        una raiz de `INVENTABLES` en la busqueda que no esta en el mensaje ni en lo que la vara espera.
def sobrantes_reales(corridas=(("gemini-lite", "v1"), ("gemini-lite", "v2"), ("luna", "v2"))):
    import embeddings as EMB
    import embeddings_candidatos as EC
    import nexo_rubro as NR
    import reales as RE
    _, alias, _, modelos = NR.fuente()
    ms = list(modelos)
    cache = EMB.cargar()
    vp = [cache[f"RETRIEVAL_DOCUMENT|{NR.doc_producto(k, modelos[k], alias)}"] for k in ms]
    vara = {c[0]: c[2] for c in RE.CASOS}
    vara.update({c[0]: c[2] for c in RE.casos_525()[0]})
    for banco, nombre in (("reales", "LOS 40 REALES"), ("reales525", "LAS 365")):
        textos = {cid: t for _, cid, t in casos_de(banco)}
        esp = esperado_reales(banco)
        cs = corridas_reales(banco)
        print(f"\n{nombre} · lo que sobra y lo inventado, sin las de memoria")
        print(f"  {'corrida':16} {'mensajes':>8} {'lineas':>7} {'duplicada':>10} {'contada dos':>12} {'rubro de mas':>13}"
              f" {'inventada':>10}")
        for corrida in corridas:
            rs = cs[corrida]
            busq = sorted({str(l.get("busqueda")) for r in rs.values() for l in (r.get("salida") or {}).get("lineas", [])
                           if l.get("busqueda")})
            EC.vectores(busq, "RETRIEVAL_QUERY", cache)
            c, ej = collections.Counter(), collections.defaultdict(list)
            for cid, r in rs.items():
                if "." in cid and ".0." not in cid or not r.get("salida"):
                    continue
                ls = [l for l in r["salida"]["lineas"] if l.get("busqueda")]
                c["mensajes"] += 1
                c["lineas"] += len(ls)
                vistas = collections.Counter((E.n(l["busqueda"]), E.n(l.get("destino"))) for l in ls)
                c["duplicada"] += sum(v - 1 for v in vistas.values())
                rub = {}
                for l in ls:
                    x = cache[f"RETRIEVAL_QUERY|{l['busqueda']}"]
                    rub[id(l)] = ms[max(range(len(ms)), key=lambda i: sum(a * b for a, b in zip(x, vp[i])))][0]
                por = collections.defaultdict(list)
                for l in ls:
                    por[rub[id(l)]].append(l)
                for rb, xs in por.items():
                    if any(l.get("destino") for l in xs) and any(not l.get("destino") for l in xs):
                        c["contada dos"] += sum(1 for l in xs if not l.get("destino"))
                        ej["contada dos"].append(cid)
                v = vara.get(cid, {})
                if not v.get("no_vende") and "*" not in v.get("tolerados", set()):
                    pide = set(v.get("rubros", set())) | set(v.get("tolerados", set()))
                    de_mas = [l for l in ls if rub[id(l)] not in pide]
                    c["rubro de mas"] += len(de_mas)
                    ej["rubro de mas"] += [f"{cid} {l['busqueda']!r}->{rub[id(l)]}" for l in de_mas]
                msj = E.n(textos.get(cid, ""))
                esperadas = [x for conds in esp.get(cid, {}).values() for cond in conds for x in cond]
                for l in ls:
                    for t in V.INVENTABLES:
                        if _tiene(E.n(l["busqueda"]), t) and not _tiene(msj, t) and not any(_tiene(E.n(x), t)
                                                                                          for x in esperadas):
                            c["inventada"] += 1
                            ej["inventada"].append(f"{cid} {l['busqueda']!r}")
            print(f"  {' '.join(corrida):16} {c['mensajes']:>8} {c['lineas']:>7} {c['duplicada']:>10} {c['contada dos']:>12}"
                  f" {c['rubro de mas']:>13} {c['inventada']:>10}")
            if "--ver" in sys.argv:
                for k, xs in ej.items():
                    print(f"      {k}: {xs[:12]}")
        EMB.guardar(cache)


# ══ LO QUE ESCRIBE DE MAS EN LA BUSQUEDA (17-nov) ═════════════════════════════
# Escrito antes de correr la v4, orden de Martin: lo que la busqueda trae y no es producto ni condicion. Solo lo que se
# reconoce sin dudas: signos de puntuacion, y una cantidad, "2 unidades", "cantidad 3", "x2". Y las palabras por busqueda.
_CANTIDAD = re.compile(r"\b\d+\s*(?:unidad(?:es)?|u)\b|\bcantidad\s*:?\s*\d+|\bx\s?\d+\b|\b\d+\s?x\b")


def de_mas(corridas_=(("luna", "v2"), ("luna", "v2#2"), ("luna", "v4"), ("luna", "v5"), ("luna", "v5#2"), ("luna", "v6"), ("luna", "v7"))):
    print("\nLO QUE ESCRIBE DE MAS EN LA BUSQUEDA · las 140, los reales y el primer turno de las 365")
    print(f"  {'corrida':12} {'busquedas':>10} {'con signos':>11} {'con cantidad':>13} {'palabras promedio':>18}")
    filas_ = {}
    for corrida in corridas_:
        bs = []
        for rs in [corridas()[corrida]] + [corridas_reales(b)[corrida] for b in ("reales", "reales525")]:
            for cid, r in rs.items():
                if "." in cid and ".0." not in cid:
                    continue
                bs += [str(l.get("busqueda")) for l in (r.get("salida") or {}).get("lineas", []) if l.get("busqueda")]
        filas_[corrida] = bs
        n = len(bs) or 1
        print(f"  {' '.join(corrida):12} {len(bs):>10} {sum(1 for b in bs if re.search(r'[,;:]', b)):>11} "
              f"{sum(1 for b in bs if _CANTIDAD.search(b.lower())):>13} {sum(len(b.split()) for b in bs) / n:>18.1f}")
    return filas_


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--correr" in a:
        i = a.index("--correr")
        correr(a[i + 1], a[i + 2], "--piloto" in a, a[a.index("--banco") + 1] if "--banco" in a else "140")
    elif "--sobra" in a:
        sobrantes_reales(tuple(tuple(x.split(":")) for x in a[a.index("--sobra") + 1:]) or
                         (("gemini-lite", "v1"), ("gemini-lite", "v2"), ("luna", "v2")))
    elif "--de-mas" in a:
        de_mas()
    elif "--reales" in a:
        calificar_reales()
    else:
        calificar(a[a.index("--ver") + 1:a.index("--ver") + 3] if "--ver" in a else None)
