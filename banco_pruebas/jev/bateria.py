"""Jev sobre el MENSAJE CRUDO, antes del modelo: que pedazos de la fuente trae. 105 turnos x 5 formas, y repeticiones.
Vara: la agenda a mano de cada turno (agendas58), resuelta contra el catalogo con catalogo.identificar."""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
from fuente import PS, FAQ, FUENTE, K, llamar, REPO
from app.core.flujo.agenda import preguntas
SPECS = json.load(open(os.path.join(REPO, "data/clientes/verifika_prod/specs_preguntables.json")))["specs"]
RUBROS = sorted({p["categoria"] for p in PS})
T = {(t["charla"], t["turno"]): t for t in map(json.loads, open(os.path.join(D, "turnos.jsonl")))}
TEXTOS = {}
for l in open(os.path.join(REPO, "banco_pruebas/traduccion58_corridas.jsonl")):
    r = json.loads(l)
    if (r.get("modelo") or "prod") == "prod" and not r.get("rep"):
        TEXTOS[(r["charla"], r["turno"], r["forma"])] = r["texto"]

def oro(t):
    rub, tem, prods = set(), set(), []
    for p in preguntas(t["agenda"]):
        a = p["accion"]
        if a == "buscar" and p.get("rubro") in RUBROS: rub.add(p["rubro"])
        if a == "politica" and p.get("tema"): tem.add(p["tema"])
        nombres = []
        if a in ("producto", "compatibilidad"): nombres.append((p.get("producto"), p.get("color")))
        if a == "comprar": nombres += [(x.get("producto"), x.get("color")) for x in p.get("agrega") or [] if isinstance(x, dict)]
        for nm, col in nombres:
            if not isinstance(nm, str) or nm[:2] in ("M-", "L-") or nm in RUBROS: 
                if nm in RUBROS: rub.add(nm)
                continue
            r = K.identificar(nm, col or "", "verifika_prod")
            if r["veredicto"] == "exists":
                prods.append({str(v["id"]) for v in r["variantes"]}); rub.add(r["producto"]["categoria"])
    return rub, tem, prods

def uno(job):
    (ch, tu, forma, rep) = job; t = T[(ch, tu)]; texto = TEXTOS[(ch, tu, forma)]
    st = FUENTE + f"\n\n{t['libreta']}\n\nULTIMO MENSAJE DEL CLIENTE: {texto}"
    q = {f"r_{r}": {"type": "noul", "instructions": f"El ultimo mensaje del cliente pide, nombra o pregunta por productos del rubro {r}?"} for r in RUBROS}
    q.update({f"f_{f['tema']}": {"type": "noul", "instructions": f"El ultimo mensaje del cliente pregunta algo que responde la regla de la tienda \"{f['tema']}\"?"} for f in FAQ})
    q.update({f"s_{s['id']}": {"type": "noul", "instructions": f"El ultimo mensaje del cliente pregunta o pone como condicion {s['etiqueta']}?"} for s in SPECS})
    t0 = time.time()
    a1 = llamar({"state": st, "model": "jev-latest", "questions": q})
    pr = {r: a1["answers"][f"r_{r}"]["noul"] for r in RUBROS}
    top = [r for r in sorted(RUBROS, key=lambda r: -pr[r]) if pr[r] >= 0.3][:3]
    q2 = {}
    for r in top:
        q2[f"p_{r}"] = {"type": "choice", "criteria": {str(p["id"]): f"{p['nombre']} ${K.entero(p.get('precio_ars'))} stock {K.entero(p.get('stock'))}" for p in PS if p["categoria"] == r},
                        "instructions": f"Que producto de {r} del CATALOGO nombra, senala o le conviene mostrar segun el ultimo mensaje del cliente?"}
    rank, tok = {}, a1["usage"]["input_tokens"]
    if q2:
        a2 = llamar({"state": st, "model": "jev-latest", "questions": q2}); tok += a2["usage"]["input_tokens"]
        rank = {r: [k for k, _ in sorted(a2["answers"][f"p_{r}"]["probabilities"].items(), key=lambda kv: -kv[1])][:10] for r in top}
    return {"charla": ch, "turno": tu, "forma": forma, "rep": rep, "texto": texto, "pr": pr,
            "pf": {f["tema"]: a1["answers"][f"f_{f['tema']}"]["noul"] for f in FAQ},
            "ps": {s["id"]: a1["answers"][f"s_{s['id']}"]["noul"] for s in SPECS}, "rank": rank, "tok": tok, "ms": int((time.time() - t0) * 1000)}

if __name__ == "__main__":
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    jobs = [(c, t, f, 0) for (c, t, f) in TEXTOS if (c, t) in T]
    jobs += [(c, t, "original", k) for k in range(1, reps) for (c, t, f) in TEXTOS if f == "original" and (c, t) in T]
    out = os.path.join(D, "bateria_resp.jsonl")
    hechos = {(x["charla"], x["turno"], x["forma"], x["rep"]) for x in map(json.loads, open(out))} if os.path.exists(out) else set()
    jobs = [j for j in jobs if j not in hechos]; print(len(jobs), "llamadas a correr", flush=True)
    def seguro(j):
        try: return uno(j)
        except Exception as e: print("ERROR", j, str(e)[:200], flush=True)
    with ThreadPoolExecutor(6) as ex, open(out, "a") as f:
        for i, x in enumerate(ex.map(seguro, jobs)):
            if x: f.write(json.dumps(x, ensure_ascii=False) + "\n"); f.flush()
            if i % 50 == 0: print(i, flush=True)
    print("listo")
