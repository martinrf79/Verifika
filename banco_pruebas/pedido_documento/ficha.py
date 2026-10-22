"""LA FICHA NATIVA — el pedido como documento, con los nombres que eligio el modelo (23-oct-2026).

Del paso libre, `medir_libre.py`: en JSON el modelo repite pedido, producto, cantidad, destino, consulta y metodo de
pago, y cuando reparte bien arma una lista de envios, cada uno con su destino y sus articulos. En lenguaje natural
conserva mas y duda mas. La ficha toma esa forma, con los valores en palabras y un lugar para la duda. El pedido va
entero, como queda despues del mensaje: no los pasos para llegar.

El prompt no lleva menu de funciones, ejemplos ni fuente. Corre los 48 turnos de `pregunta_razonada/fichas.py`, con
su memoria. Con la paga y la marca de Martin, freno a los 10 centavos:
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/pedido_documento/ficha.py [--v2] [--reps 3]
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
os.environ["BANCO_CLAVE_PAGA"] = "true"
os.environ["PAGA"] = "1"  # `experimento` saca la paga del entorno si no la ve pedida

from banco_pruebas import clon_produccion as C  # noqa: E402
C.preparar_entorno()
C.instalar()
from app.core import llm_reintento  # noqa: E402
from banco_pruebas import costo  # noqa: E402
from experimento import memoria, limpio  # noqa: E402
from fichas import CHARLAS  # noqa: E402

SALIDA = os.path.join(AQUI, "ficha_v2.jsonl" if "--v2" in sys.argv else "ficha.jsonl")

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
VERSION = "v2" if "--v2" in sys.argv else "v1"
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
                    model=llm_reintento._modelo(), temperature=0, response_format={"type": "json_object"},
                    messages=[{"role": "system", "content": FICHA_V2 if VERSION == "v2" else FICHA},
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
    sem = asyncio.Semaphore(4)
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
