"""EL PASO LIBRE — el modelo anota cada pedido como quiere, sin ficha ni menu ni fuente (23-oct-2026).

Antes de darle al modelo una ficha, se mira como ordena un pedido por su cuenta, en tres lenguas:
  comun    en lenguaje natural, para que otra persona del equipo lo cumpla sin leer la charla;
  json     en JSON, con la forma que le parezca mas clara;
  python   como codigo Python, con las funciones y datos que le parezcan mas claros, sin resolverlo.

El prompt no lleva menu, nombres de campos, ejemplos ni fuente. Solo tres reglas: no le contesta al cliente, anota lo
que pide para que otro lo cumpla, y no agrega nada que no este en el mensaje o en la memoria. Va con la memoria de la
charla cuando el turno la tiene.

Los 100 mensajes: los 48 turnos de las charlas de `pregunta_razonada/fichas.py`, con su memoria, y 52 turnos de las 58
y las K de `jev/turnos.jsonl`, los de mas pedidos y con memoria primero, con la libreta que vio el modelo de produccion.

Va con la paga, con la marca de Martin, y frena a los 30 centavos:
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/pedido_documento/libre.py
Lo que devuelve queda en `libre.jsonl`; `medir_libre.py` lo mide.
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

SALIDA = os.path.join(AQUI, "libre.jsonl")
TOPE_USD = 0.30

BASE = ("Sos parte del sistema de una tienda online de tecnologia de Argentina. No le contestas al cliente. "
        "Anota lo que pide el ULTIMO MENSAJE del cliente {como}, para que {quien} lo cumpla sin leer la charla. "
        "No agregues nada que no este en el mensaje o en la memoria.")
LENGUAS = {
    "comun": BASE.format(como="en lenguaje natural, como te parezca mas claro", quien="otra persona del equipo"),
    "json": BASE.format(como="en JSON, con la forma que te parezca mas clara", quien="un programa") +
            " Devolve solo el JSON.",
    "python": BASE.format(como="como codigo Python, con las funciones y los datos que te parezcan mas claros",
                          quien="un programa") + " No lo resuelvas ni lo ejecutes: solo escribilo. Devolve solo el codigo.",
}


def mensajes() -> list:
    """[{"id", "memoria", "mensaje", "de"}]: los 48 de las fichas y 52 de las 58 y las K."""
    out = [{"id": f"{ch['id']}-t{t}", "memoria": memoria(tu["mem"]), "mensaje": limpio(tu["msg"]), "de": "fichas"}
           for ch in CHARLAS for t, tu in enumerate(ch["turnos"])]
    turnos = [json.loads(l) for l in open(os.path.join(REPO, "banco_pruebas", "jev", "turnos.jsonl"), encoding="utf-8")]
    peso = lambda x: len((x["agenda"] or {}).get("preguntas") or []) + 2 * ("vacia" not in x["libreta"])  # noqa: E731
    turnos.sort(key=lambda x: -peso(x))
    out += [{"id": f"{x['charla']}-t{x['turno']}", "memoria": x["libreta"], "mensaje": x["mensaje"], "de": "58"}
            for x in turnos[:100 - len(out)]]
    return out


GASTO = {"usd": 0.0}


async def una(m: dict, lengua: str, sem) -> dict:
    async with sem:
        if GASTO["usd"] >= TOPE_USD:
            return {**m, "lengua": lengua, "error": "tope de la corrida"}
        cli = llm_reintento._cliente()
        t0 = time.time()
        try:
            r = await llm_reintento.llamar_con_reintento(
                lambda: cli.chat.completions.create(model=llm_reintento._modelo(), temperature=0, messages=[
                    {"role": "system", "content": LENGUAS[lengua]},
                    {"role": "user", "content": f"{m['memoria']}\n\nULTIMO MENSAJE: {m['mensaje']}"}]),
                timeout_s=90, trace_id="pedido_libre")
        except Exception as e:  # noqa: BLE001
            return {**m, "lengua": lengua, "error": f"{type(e).__name__}: {str(e)[:200]}"}
        u = r.usage
        GASTO["usd"] += costo.dolares(u.prompt_tokens, u.completion_tokens, llm_reintento._modelo())
        return {**m, "lengua": lengua, "salida": r.choices[0].message.content or "", "entrada": u.prompt_tokens,
                "sale": u.completion_tokens, "ms": int((time.time() - t0) * 1000), "error": None}


async def main() -> None:
    ms = mensajes()
    ya = set()
    if os.path.exists(SALIDA):
        ya = {(r["id"], r["lengua"]) for r in map(json.loads, open(SALIDA, encoding="utf-8")) if not r.get("error")}
    sem = asyncio.Semaphore(4)
    tareas = [una(m, lg, sem) for m in ms for lg in LENGUAS if (m["id"], lg) not in ya]
    print(f"{len(ms)} mensajes, {len(tareas)} llamadas, modelo {llm_reintento._modelo()}", flush=True)
    with open(SALIDA, "a", encoding="utf-8") as f:
        for i, fut in enumerate(asyncio.as_completed(tareas), 1):
            r = await fut
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            if i % 30 == 0 or r.get("error"):
                print(f"{i}/{len(tareas)} · {GASTO['usd']:.4f} dolares" + (f" · {r['error']}" if r.get("error") else ""),
                      flush=True)
    print(f"gasto de la corrida: {GASTO['usd']:.4f} dolares")


if __name__ == "__main__":
    asyncio.run(main())
