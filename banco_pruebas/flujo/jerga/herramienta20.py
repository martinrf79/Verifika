"""LUNA CON LA BUSQUEDA DE JERGA COMO HERRAMIENTA, SOBRE LAS 20 FILAS DE `prueba20.py` (28-nov-2026).

Orden de Martin: que Luna maneje los embeddings por su cuenta. Recibe el mensaje y la fila; tiene la herramienta
`buscar_jerga(texto)`, que devuelve los cinco conceptos mas cercanos de la base con la expresion que trajo a cada uno.
Luna decide que buscar, puede buscar hasta tres veces con otras palabras, y contesta el concepto, vago o ninguno. El
codigo controla que lo que contesta haya salido de alguna busqueda. Razonamiento bajo y medio. Latencia y costo:
lo de Luna y lo de los embeddings, aparte. El juicio es a mano.

    python3 herramienta20.py [--correr]
"""
import json, os, sys, time

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(AQUI, "..", "..", ".."))
sys.path[:0] = [AQUI, REPO]
import elegir as E  # noqa: E402
from prueba20 import CASOS  # noqa: E402

GRABADO = os.path.join(AQUI, "herramienta20.jsonl")
MODOS = {"luna-bajo": "low", "luna-medio": "medium"}
SISTEMA = E.SISTEMA.replace(
    "decir cual de los candidatos expresa", "decir que concepto de la tienda expresa") + """
Tenes la herramienta buscar_jerga: le pasas un texto y te devuelve los conceptos de la tienda mas parecidos, con la
expresion que trajo a cada uno. Buscá con las palabras de la fila o con otras que digan lo mismo; podes buscar hasta
tres veces. Al final contestá solo con un concepto que te haya devuelto la herramienta, o vago, o ninguno."""
HERRAMIENTA = [{"type": "function", "function": {
    "name": "buscar_jerga", "description": "Busca en la base de jerga de la tienda los conceptos mas parecidos a un texto.",
    "parameters": {"type": "object", "properties": {"texto": {"type": "string"}}, "required": ["texto"],
                   "additionalProperties": False}}}]
FINAL = {"type": "json_schema", "json_schema": {"name": "eleccion", "strict": True, "schema": {
    "type": "object", "properties": {"elegido": {"type": "string"}}, "required": ["elegido"], "additionalProperties": False}}}


def uno(ix, motor, msg, fila, ctx):
    """Por la puerta Responses de OpenAI: la de chat no acepta herramientas con razonamiento para este modelo."""
    from openai import OpenAI
    cli = OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=120, max_retries=2)
    usuario = f"MENSAJE DEL CLIENTE: {msg}\nFILA: {fila}" + (f"\nEL CLIENTE YA DIJO EL PRODUCTO: {ctx}" if ctx else "")
    entrada = [{"role": "user", "content": usuario}]
    herr = [{"type": "function", "name": "buscar_jerga", "strict": True,
             "description": "Busca en la base de jerga de la tienda los conceptos mas parecidos a un texto.",
             "parameters": {"type": "object", "properties": {"texto": {"type": "string"}}, "required": ["texto"],
                            "additionalProperties": False}}]
    formato = {"format": {"type": "json_schema", "name": "eleccion", "strict": True,
                          "schema": FINAL["json_schema"]["schema"]}}
    vistos, busquedas, seg_luna, seg_emb, e, s = set(), [], 0.0, 0.0, 0, 0
    el = ""
    for vuelta in range(6):
        t0 = time.time()
        r = cli.responses.create(model="gpt-6-luna", instructions=SISTEMA, input=entrada, tools=herr, text=formato,
                                 reasoning={"effort": MODOS[motor]},
                                 tool_choice="auto" if len(busquedas) < 3 else "none")
        seg_luna += time.time() - t0
        e += r.usage.input_tokens or 0
        s += r.usage.output_tokens or 0
        llamadas = [o for o in r.output if o.type == "function_call"]
        if not llamadas:
            txt = r.output_text or "{}"
            el = json.loads(txt[txt.find("{"):txt.rfind("}") + 1]).get("elegido", "")
            break
        entrada += [o.model_dump(exclude_none=True) for o in r.output]
        for tc in llamadas:
            q = json.loads(tc.arguments).get("texto", "")
            t1 = time.time()
            cs = ix.candidatos(q, 5)
            seg_emb += time.time() - t1
            vistos |= {c["concepto"] for c in cs}
            busquedas.append(q)
            res = [{"concepto": c["concepto"], "significa": E.significado(c["concepto"]), "por": c["expresion"]} for c in cs]
            entrada.append({"type": "function_call_output", "call_id": tc.call_id,
                            "output": json.dumps(res, ensure_ascii=False)})
    valido = el in vistos or el in E.SIN
    return {"elegido": el, "valido": valido, "busquedas": busquedas, "vueltas": vuelta + 1,
            "seg_luna": round(seg_luna, 2), "seg_embeddings": round(seg_emb, 2), "seg_total": round(seg_luna + seg_emb, 2),
            "entrada": e, "salida": s, "dolares": round((e * 0.10 + s * 0.50) / 1e6, 7)}


def correr():
    import vectores as V
    ix = V.Indice()
    hechos = {(r["id"], r["motor"]) for r in map(json.loads, open(GRABADO))} if os.path.exists(GRABADO) else set()
    with open(GRABADO, "a") as f:
        for cid, msg, fila, ctx in CASOS:
            for motor in MODOS:
                if (cid, motor) in hechos:
                    continue
                f.write(json.dumps({"id": cid, "motor": motor, "fila": fila, **uno(ix, motor, msg, fila, ctx)},
                                   ensure_ascii=False) + "\n")
                f.flush()


def ver():
    rs = [json.loads(l) for l in open(GRABADO)]
    for cid, _m, fila, _c in CASOS:
        a = {r["motor"]: r for r in rs if r["id"] == cid}
        print(f"{cid:13} {fila[:40]!r:44}")
        for m in MODOS:
            r = a.get(m)
            if r:
                print(f"   {m:10} {r['elegido']:28} {'' if r['valido'] else 'NO SALIO DE LA BUSQUEDA '}"
                      f"{r['seg_total']} s, busco {r['busquedas']}")
    for m in MODOS:
        x = [r for r in rs if r["motor"] == m]
        if x:
            t = sorted(r["seg_total"] for r in x)
            print(f"{m}: mediana {t[len(t) // 2]} s, maximo {t[-1]} s; Luna {sorted(r['seg_luna'] for r in x)[len(x) // 2]} s, "
                  f"embeddings {sorted(r['seg_embeddings'] for r in x)[len(x) // 2]} s; busquedas por fila "
                  f"{sum(len(r['busquedas']) for r in x) / len(x):.1f}; costo {sum(r['dolares'] for r in x) * 100:.3f} centavos")


if __name__ == "__main__":
    if "--correr" in sys.argv:
        correr()
    ver()
