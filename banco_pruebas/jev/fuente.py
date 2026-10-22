"""Jev con la fuente de verdad entera: elige el producto y la regla que responden cada parte de un mensaje complejo."""
import json, os, re, sys, time, urllib.request, urllib.error, unicodedata
from concurrent.futures import ThreadPoolExecutor
REPO = "/home/user/Verifika"; sys.path.insert(0, REPO); os.chdir(REPO)
from banco_pruebas import cableado58 as R
R.instalar()
from app.core.flujo import catalogo as K
from app.core.flujo.agenda import preguntas
AQUI = os.path.dirname(os.path.abspath(__file__))
T = [json.loads(l) for l in open(os.path.join(AQUI, "turnos.jsonl"))]
PS = K.productos("verifika_prod"); POR_ID = {str(p["id"]): p for p in PS}
FAQ = json.load(open("data/clientes/verifika_prod/faq.json"))
def n(t): return "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")
def linea(p): return f"{p['id']} | {p['categoria']} | {p['nombre']} | ${K.entero(p.get('precio_ars'))} | stock {K.entero(p.get('stock'))}"
FUENTE = ("CATALOGO, id | rubro | nombre | precio | stock:\n" + "\n".join(linea(p) for p in PS)
          + "\n\nREGLAS DE LA TIENDA, tema: respuesta:\n" + "\n".join(f"{f['tema']}: {f['respuesta']}" for f in FAQ))
# Lo bien respondido de produccion: la respuesta que paso la vara, forma original.
BIEN = {}
for l in open(os.path.join(REPO, "banco_pruebas/traduccion58_corridas.jsonl")):
    r = json.loads(l)
    if (r.get("modelo") or "prod") == "prod" and r["forma"] == "original" and r["bien"] and r.get("rep", 0) == 0:
        BIEN[(r["charla"], r["turno"])] = r["respuesta"]
def nombrados(texto):
    t = n(texto); return [p for p in sorted(PS, key=lambda p: -len(p["nombre"])) if n(p["nombre"]) in t]

def casos():
    out = []
    for t in T:
        ps = preguntas(t["agenda"]); resp = BIEN.get((t["charla"], t["turno"]))
        if len(ps) < 3 or not resp: continue
        prods = nombrados(resp)
        rubros = sorted({p["rubro"] for p in ps if p["accion"] == "buscar" and p.get("rubro") not in (None, "el pedido")})
        oro_rub = {r: [str(p["id"]) for p in prods if p["categoria"] == r] for r in rubros}
        temas = sorted({p["tema"] for p in ps if p["accion"] == "politica"})
        out.append({"t": t, "rubros": {r: v for r, v in oro_rub.items() if v}, "temas": temas})
    return out

def preguntas_jev(c):
    q = {}
    for r in c["rubros"]:
        crit = {str(p["id"]): f"{p['nombre']} ${K.entero(p.get('precio_ars'))} stock {K.entero(p.get('stock'))}"
                for p in PS if p["categoria"] == r and K.entero(p.get("stock")) > 0}
        q[f"p_{r}"] = {"type": "choice", "criteria": crit, "instructions":
            f"Segun lo que pide el cliente en su ultimo mensaje —marca, precio, orden, color, condiciones—, que producto de {r} del CATALOGO le corresponde mostrarle primero?"}
    for f in FAQ:
        q[f"f_{f['tema']}"] = {"type": "noul", "instructions":
            f"El ultimo mensaje del cliente pregunta algo que responde la regla de la tienda \"{f['tema']}\"?"}
    return q

def llamar(body):
    req = urllib.request.Request("https://api.typesafe.ai/v1/systemone", data=json.dumps(body).encode(), headers={
        "Authorization": "Bearer " + os.environ["TYPESAFE_API_KEY"].strip(), "Content-Type": "application/json",
        "TypeSafe-Danger-Zone-Long-Context": "true"})
    for i in range(5):
        try: return json.load(urllib.request.urlopen(req, timeout=180))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < 4: time.sleep(3 * 2 ** i); continue
            raise RuntimeError(f"{e.code} {e.read()[:300]!r}")

def uno(c):
    t = c["t"]; t0 = time.time()
    st = FUENTE + f"\n\n{t['libreta']}\n\nULTIMO MENSAJE DEL CLIENTE: {t['mensaje']}"
    try: r = llamar({"state": st, "model": "jev-latest", "questions": preguntas_jev(c)}); err = None
    except Exception as e: r, err = {"answers": {}, "usage": {}}, str(e)[:300]
    return {"charla": t["charla"], "turno": t["turno"], "mensaje": t["mensaje"], "rubros": c["rubros"], "temas": c["temas"],
            "ans": r["answers"], "tok": r["usage"].get("input_tokens"), "ms": int((time.time() - t0) * 1000), "err": err}

if __name__ == "__main__":
    cs = casos(); print(len(cs), "turnos complejos;", len(FUENTE), "caracteres de fuente", flush=True)
    with ThreadPoolExecutor(4) as ex, open(os.path.join(AQUI, "fuente_resp.jsonl"), "w") as f:
        for x in ex.map(uno, cs): f.write(json.dumps(x, ensure_ascii=False) + "\n"); print(x["charla"], x["turno"], x["tok"], x["ms"], x["err"] or "", flush=True)
