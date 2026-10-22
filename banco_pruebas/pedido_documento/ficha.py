"""LA FICHA NATIVA — el pedido como documento, con los nombres que eligio el modelo (23-oct-2026).

Del paso libre, `medir_libre.py`: en JSON el modelo repite pedido, producto, cantidad, destino, consulta y metodo de
pago, y cuando reparte bien arma una lista de envios, cada uno con su destino y sus articulos. En lenguaje natural
conserva mas y duda mas. La ficha toma esa forma, con los valores en palabras y un lugar para la duda. El pedido va
entero, como queda despues del mensaje: no los pasos para llegar.

El prompt no lleva menu de funciones, ejemplos ni fuente. Corre los 48 turnos de `pregunta_razonada/fichas.py`, con
su memoria. Con la paga y la marca de Martin, freno a los 10 centavos:
    [MARTIN_AUTORIZO_LA_PAGA=<fecha>] python3 banco_pruebas/pedido_documento/ficha.py [--v2 | --v3 | --v4] [--reps 3]
Sin la marca corre con la gratis; con `--gratis` lo devuelto va a su propio archivo, `ficha_v4_gratis.jsonl`.
Lo que devuelve queda en `ficha.jsonl`, o en `ficha_v2.jsonl` con la duda ajustada; `medir_ficha.py` lo compara con las fichas.
"""
import asyncio
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "banco_pruebas", "pregunta_razonada"))
os.chdir(REPO)
# LA PAGA SOLO CON LA MARCA DE MARTIN; sin ella corre con la gratis, que es el default para medir.
if os.environ.get("MARTIN_AUTORIZO_LA_PAGA"):
    os.environ["BANCO_CLAVE_PAGA"] = "true"
    os.environ["PAGA"] = "1"  # `experimento` saca la paga del entorno si no la ve pedida

from banco_pruebas import clon_produccion as C  # noqa: E402
C.preparar_entorno()
C.instalar()
from app.core import llm_reintento  # noqa: E402
from banco_pruebas import costo  # noqa: E402
from experimento import memoria, limpio  # noqa: E402
from fichas import CHARLAS  # noqa: E402
from app.core.flujo import catalogo as K  # noqa: E402

VERSIONES = ("v2", "v3", "v4", "v5")
SALIDA = os.path.join(AQUI, next((f"ficha_{v}.jsonl" for v in VERSIONES if f"--{v}" in sys.argv), "ficha.jsonl"))
if "--gratis" in sys.argv:
    SALIDA = SALIDA.replace(".jsonl", "_gratis.jsonl")

TOPE_USD = 0.12

FICHA = """Sos parte del sistema de una tienda online de tecnologia de Argentina. No le contestas al cliente. Con la
MEMORIA y el ULTIMO MENSAJE, llena esta ficha en JSON. Los valores van en palabras, claros y completos, como los
entenderia alguien que no leyo la charla. No agregues nada que no este en el mensaje o en la memoria: los precios y los
datos de la tienda los pone otro programa. Lo que senala de la memoria —"ese", "el segundo"— va con su nombre y su
numero, M2 o L1.

{
  "pedido": como queda el pedido ENTERO despues de este mensaje: lo que ya estaba y sigue, con lo que cambio. Solo lo
    que el cliente decidio llevar; lo que solo pregunta va en consultas.
    [{"destino": "...", "items": [{"producto": "...", "cantidad": 1, "color": "...", "condiciones": "...",
                                    "renglon": "L1 si ya estaba"}]}]
    Lo que todavia no tiene destino va con "destino": "sin decir".
  "preferencias": lo que pide para todo el pedido, ["..."],
  "pago": {"medios": [{"medio": "... o sin decir", "porcentaje": 100}], "tope_total": pesos o null},
  "consultas": lo que pregunta o pide saber, en su orden:
    [{"tipo": "buscar | producto | comparar | compatibilidad | envio | cuenta | regla de la tienda | saber general",
      "sobre": "...", "si": "de que depende, si depende de otra cosa"}],
  "cliente": lo que dice de si mismo: nombre, localidad,
  "dudas": lo que no se puede saber sin preguntarle, ["..."]
}"""

# LA DUDA AJUSTADA, v2: en la v1 salia en 31 de 38 turnos que estaban bien, con "nombre del cliente" o "localidad".
FICHA_V2 = FICHA.replace(
    '"dudas": lo que no se puede saber sin preguntarle, ["..."]',
    '"dudas": solo lo que impide cumplir algo de ESTE mensaje y hay que preguntarle al cliente, ["..."]; no lo que\n'
    '    falta para cerrar la venta, como el nombre o la localidad, ni lo que el programa resuelve con la tienda.\n'
    '    Si no hay, []')
# EL CONTRATO, v3: lo que en la fuente es cerrado se le ofrece cerrado. Medido en `atar_ficha.py` sobre la v2: el
# orden no se ataba nunca —"lo mas economico" no es una clave del codigo—, la condicion venia con relleno —"sin
# especificar", el tope total, el medio de pago— y las busquedas vagas llegaban como consulta de un producto.
ORDENES = " | ".join(list(K.ORDEN) + ["nada"])
FICHA_V3 = f"""Sos parte del sistema de una tienda online de tecnologia de Argentina. No le contestas al cliente. Con la
MEMORIA y el ULTIMO MENSAJE, llena esta ficha en JSON. Los valores van en palabras, claros y completos, como los
entenderia alguien que no leyo la charla. No agregues nada que no este en el mensaje o en la memoria: los precios y los
datos de la tienda los pone otro programa. Lo que senala de la memoria —"ese", "el segundo"— va con su nombre y su
numero, M2 o L1.

{{
  "pedido": como queda el pedido ENTERO despues de este mensaje: lo que ya estaba y sigue, con lo que cambio. Solo lo
    que el cliente decidio llevar; lo que solo pregunta va en consultas.
    [{{"destino": "...", "items": [{{"producto": "...", "cantidad": 1, "color": "...", "condiciones": ["..."],
                                     "orden": "...", "renglon": "L1 si ya estaba"}}]}}]
    Lo que todavia no tiene destino va con "destino": "sin decir".
  "preferencias": lo que pide para todo el pedido: {{"condiciones": ["..."], "orden": "..."}},
  "pago": {{"medios": [{{"medio": "... o sin decir", "porcentaje": 100}}], "tope_total": pesos o null}},
  "consultas": lo que pregunta o pide saber, en su orden:
    [{{"tipo": "...", "sobre": "...", "condiciones": ["..."], "orden": "...", "si": "de que depende, si depende"}}],
  "cliente": lo que dice de si mismo: nombre, localidad,
  "dudas": solo lo que impide cumplir algo de ESTE mensaje y hay que preguntarle al cliente, ["..."]; no lo que
    falta para cerrar la venta, como el nombre o la localidad, ni lo que el programa resuelve con la tienda. Si no hay, []
}}

"condiciones": cada una corta, una cosa que pide que tenga el producto: "inalambrico", "no fabricado en China". Si no
pide nada, []. El tope de plata del total va en "pago", y el medio de pago tambien.
"orden": uno de estos, tal cual: {ORDENES}.
"tipo" de consulta, uno de estos:
  buscar              pide opciones de una clase de producto: "que tenes para...", "mostrame..."
  producto            pregunta un dato de un producto ya nombrado o mostrado: precio, stock, si aguanta el agua
  comparar            dos o mas productos por un dato
  compatibilidad      si un producto anda con algo que tiene el cliente
  envio               cuanto sale o cuanto tarda mandar a un lugar
  cuenta              cuanto da el total
  regla de la tienda  como trabaja la tienda: medios de pago, cuotas, garantia, factura, retiro, devoluciones
  saber general       tecnologia en general, que no depende de la tienda"""

# EL ESQUEMA, v4: la forma de la v3 y sus listas cerradas —el orden y el tipo de consulta— las fija la API y no el
# prompt, por `response_format` con `json_schema`. Y el modelo lee antes de llenar: el primer campo, `lectura`, es
# libre, porque atar la forma de la salida empeora el razonamiento si el modelo piensa adentro de la forma atada.
TIPOS = ["buscar", "producto", "comparar", "compatibilidad", "envio", "cuenta", "regla de la tienda", "saber general"]
_TXT, _LISTA = {"type": "string"}, {"type": "array", "items": {"type": "string"}}
_ORDEN = {"type": "string", "enum": list(K.ORDEN) + ["nada"]}
_ITEM = {"type": "object", "properties": {
    "producto": _TXT, "cantidad": {"type": "integer"}, "color": _TXT, "condiciones": _LISTA, "orden": _ORDEN,
    "renglon": _TXT}, "required": ["producto", "cantidad", "color", "condiciones", "orden", "renglon"]}
ESQUEMA = {"type": "object", "properties": {
    "lectura": _TXT,
    "pedido": {"type": "array", "items": {"type": "object", "properties": {
        "destino": _TXT, "items": {"type": "array", "items": _ITEM}}, "required": ["destino", "items"]}},
    "preferencias": {"type": "object", "properties": {"condiciones": _LISTA, "orden": _ORDEN},
                     "required": ["condiciones", "orden"]},
    "pago": {"type": "object", "properties": {
        "medios": {"type": "array", "items": {"type": "object", "properties": {
            "medio": _TXT, "porcentaje": {"type": "integer"}}, "required": ["medio", "porcentaje"]}},
        "tope_total": {"type": ["integer", "null"]}}, "required": ["medios", "tope_total"]},
    "consultas": {"type": "array", "items": {"type": "object", "properties": {
        "tipo": {"type": "string", "enum": TIPOS}, "sobre": _TXT, "condiciones": _LISTA, "orden": _ORDEN, "si": _TXT},
        "required": ["tipo", "sobre", "condiciones", "orden", "si"]}},
    "cliente": {"type": "object", "properties": {"nombre": _TXT, "localidad": _TXT}, "required": ["nombre", "localidad"]},
    "dudas": _LISTA},
    "required": ["lectura", "pedido", "preferencias", "pago", "consultas", "cliente", "dudas"]}
FICHA_V4 = FICHA_V3.replace("llena esta ficha en JSON.", "llena esta ficha en JSON. Primero, en \"lectura\", en una o dos\n"
                            "frases, que pide el cliente en este mensaje y que cambia del pedido; despues, el resto.")
# v5: el mismo esquema sin `lectura`, para separar lo que hace el esquema de lo que hace leer antes.
ESQUEMA_V5 = {**ESQUEMA, "properties": {c: v for c, v in ESQUEMA["properties"].items() if c != "lectura"},
              "required": [c for c in ESQUEMA["required"] if c != "lectura"]}
FORMATO = {"v4": {"type": "json_schema", "json_schema": {"name": "ficha", "schema": ESQUEMA}},
           "v5": {"type": "json_schema", "json_schema": {"name": "ficha", "schema": ESQUEMA_V5}}}
VERSION = next((v for v in reversed(VERSIONES) if f"--{v}" in sys.argv), "v1")
REPS = int(sys.argv[sys.argv.index("--reps") + 1]) if "--reps" in sys.argv else 1

GASTO = {"usd": 0.0}


async def una(cid: str, t: int, tu: dict, sem, rep: int = 0) -> dict:
    async with sem:
        base = {"charla": cid, "turno": t, "rep": rep}
        if GASTO["usd"] >= TOPE_USD:
            return {**base, "error": "tope de la corrida"}
        cli = llm_reintento._cliente()
        t0 = time.time()
        try:
            r = await llm_reintento.llamar_con_reintento(
                lambda: cli.chat.completions.create(
                    model=llm_reintento._modelo(), temperature=0,
                    response_format=FORMATO.get(VERSION, {"type": "json_object"}),
                    messages=[{"role": "system", "content": {"v1": FICHA, "v2": FICHA_V2, "v3": FICHA_V3,
                                                             "v4": FICHA_V4, "v5": FICHA_V3}[VERSION]},
                              {"role": "user", "content": f"{memoria(tu['mem'])}\n\nULTIMO MENSAJE: {limpio(tu['msg'])}"}]),
                timeout_s=90, trace_id="ficha_nativa")
        except Exception as e:  # noqa: BLE001
            return {**base, "error": f"{type(e).__name__}: {str(e)[:200]}"}
        u = r.usage
        GASTO["usd"] += costo.dolares(u.prompt_tokens, u.completion_tokens, llm_reintento._modelo())
        return {**base, "salida": r.choices[0].message.content or "", "entrada": u.prompt_tokens,
                "sale": u.completion_tokens, "ms": int((time.time() - t0) * 1000), "error": None}


async def main() -> None:
    ya = set()
    if os.path.exists(SALIDA):
        ya = {(r["charla"], r["turno"], r.get("rep", 0)) for r in map(json.loads, open(SALIDA, encoding="utf-8"))
              if not r.get("error")}
    sem = asyncio.Semaphore(int(os.environ.get("FICHA_A_LA_VEZ", "4")))
    tareas = [una(ch["id"], t, tu, sem, k) for k in range(REPS) for ch in CHARLAS for t, tu in enumerate(ch["turnos"])
              if (ch["id"], t, k) not in ya]
    print(f"{len(tareas)} turnos, modelo {llm_reintento._modelo()}", flush=True)
    with open(SALIDA, "a", encoding="utf-8") as f:
        for fut in asyncio.as_completed(tareas):
            r = await fut
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            if r.get("error"):
                print(r["charla"], r["turno"], r["error"], flush=True)
    print(f"gasto de la corrida: {GASTO['usd']:.4f} dolares")


if __name__ == "__main__":
    asyncio.run(main())
