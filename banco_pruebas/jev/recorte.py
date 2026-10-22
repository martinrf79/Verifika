"""Desde la pregunta ya traducida por produccion, Jev elige pedazos de la fuente: rubro, reglas y productos rankeados."""
import json, os, sys, time, random
from concurrent.futures import ThreadPoolExecutor
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
from fuente import PS, FAQ, FUENTE, K, n, llamar, nombrados, REPO
RUBROS = sorted({p["categoria"] for p in PS})
FILAS = [json.loads(l) for l in open(os.path.join(REPO, "banco_pruebas/traduccion58_corridas.jsonl"))]
def casos():
    out = []
    for r in FILAS:
        if (r.get("modelo") or "prod") != "prod" or r.get("rep", 0) or not r["bien"] or r["forma"] not in ("redactada", "coloquial"): continue
        prods = nombrados(r["respuesta"])
        for p in (r["agenda"] or {}).get("preguntas") or []:
            acc = p.get("accion")
            if acc == "buscar" and p.get("rubro") in RUBROS:
                oro = [str(x["id"]) for x in prods if x["categoria"] == p["rubro"]]
                if oro: out.append({"r": r, "p": p, "rubro": p["rubro"], "oro": oro})
            elif acc == "producto" and not str(p.get("producto", "")).startswith(("M-", "L-")):
                oro = [x for x in prods if n(p.get("producto", "")) and any(w in n(x["nombre"]) for w in n(p["producto"]).split() if len(w) > 3)]
                if oro: out.append({"r": r, "p": p, "rubro": oro[0]["categoria"], "oro": [str(x["id"]) for x in oro]})
            elif acc == "politica":
                out.append({"r": r, "p": p, "tema": p.get("tema")})
    return out
def estado(c):
    p = {k: v for k, v in c["p"].items() if k not in ("n",)}
    return FUENTE + f"\n\nPREGUNTA DEL CLIENTE, YA TRADUCIDA: {json.dumps(p, ensure_ascii=False)}"
def uno(c):
    st = estado(c); t0 = time.time(); tok = 0
    q = {f"r_{r}": {"type": "noul", "instructions": f"Para responder la PREGUNTA TRADUCIDA hace falta mirar productos del rubro {r}?"} for r in RUBROS}
    q.update({f"f_{f['tema']}": {"type": "noul", "instructions": f"Para responder la PREGUNTA TRADUCIDA hace falta la regla de la tienda \"{f['tema']}\"?"} for f in FAQ})
    a1 = llamar({"state": st, "model": "jev-latest", "questions": q}); tok += a1["usage"]["input_tokens"]
    rub = sorted(RUBROS, key=lambda r: -a1["answers"][f"r_{r}"]["noul"])
    tem = sorted(FAQ, key=lambda f: -a1["answers"][f"f_{f['tema']}"]["noul"])
    out = {"forma": c["r"]["forma"], "charla": c["r"]["charla"], "cita": c["p"].get("cita"), "accion": c["p"]["accion"],
           "rubro_top": rub[:3], "rubro_p": [round(a1["answers"][f"r_{r}"]["noul"], 2) for r in rub[:3]],
           "temas_top": [f["tema"] for f in tem[:3]], "temas_p": [round(a1["answers"][f"f_{f['tema']}"]["noul"], 2) for f in tem[:3]]}
    if "oro" in c:
        cands = [p for p in PS if p["categoria"] == rub[0] and K.entero(p.get("stock")) > 0]
        crit = {str(p["id"]): f"{p['nombre']} ${K.entero(p.get('precio_ars'))}" for p in cands}
        a2 = llamar({"state": st, "model": "jev-latest", "questions": {"p": {"type": "choice", "criteria": crit,
             "instructions": "Que producto del CATALOGO responde mejor la PREGUNTA TRADUCIDA, con su orden, marca y condiciones?"}}})
        tok += a2["usage"]["input_tokens"]
        rank = sorted(a2["answers"]["p"]["probabilities"].items(), key=lambda kv: -kv[1])
        ids = [k for k, _ in rank]
        out.update(rubro_oro=c["rubro"], oro=c["oro"], pos=min([ids.index(o) + 1 for o in c["oro"] if o in ids] or [999]),
                   top5=[next(p["nombre"] for p in PS if str(p["id"]) == i) for i in ids[:5]], conf=a2["answers"]["p"]["confidence"])
    else:
        out["tema_oro"] = c["tema"]
    out.update(tok=tok, ms=int((time.time() - t0) * 1000))
    return out
if __name__ == "__main__":
    cs = casos(); random.Random(7).shuffle(cs)
    prod = [c for c in cs if "oro" in c][:45]; pol = [c for c in cs if "tema" in c][:15]
    print(len(cs), "preguntas traducidas; corro", len(prod), "de producto y", len(pol), "de reglas", flush=True)
    with ThreadPoolExecutor(4) as ex, open(os.path.join(D, "recorte_resp.jsonl"), "w") as f:
        for x in ex.map(uno, prod + pol): f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print("listo")
