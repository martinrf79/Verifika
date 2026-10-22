"""Calibrar cuanto trae Jev desde el MENSAJE LIMPIO (la pregunta ya traducida por produccion).
Por nivel: rubros top k, regla top k, campos top k dentro del rubro, productos top k dentro del rubro.
Lo correcto: lo que la pregunta pide, resuelto con el codigo de la tienda (identificar, atar)."""
import json, os, sys, collections
from concurrent.futures import ThreadPoolExecutor
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
import indice_jev as I
from fuente import PS, K, n, REPO
from sondas2 import llamar, GASTO
from sondas import rank
TOPE = 0.06
def gastado(): return sum(json.loads(l)["usd"] for l in open(GASTO))
INICIO = gastado()
def jev(qs, st, et):
    if gastado() - INICIO > TOPE: raise SystemExit("tope")
    return llamar({"state": st, "model": "jev-latest", "questions": qs}, et)["answers"]
TID = "verifika_prod"
def oro(p):
    a = p.get("accion"); g = {"rubro": None, "tema": None, "campos": set(), "prods": None}
    if a == "politica": g["tema"] = p.get("tema")
    if a == "buscar" and p.get("rubro") in I.RUBROS: g["rubro"] = p["rubro"]
    if a in ("producto", "compatibilidad") and isinstance(p.get("producto"), str) and p["producto"][:2] not in ("M-", "L-"):
        r = K.identificar(p["producto"], p.get("color") or "", TID)
        if r["veredicto"] == "exists": g["rubro"] = r["producto"]["categoria"]; g["prods"] = {str(v["id"]) for v in r["variantes"]}
        elif p["producto"] in I.RUBROS: g["rubro"] = p["producto"]
    if g["rubro"]:
        uni = [x for x in PS if x["categoria"] == g["rubro"]]
        for c in (p.get("condiciones") or []):
            f = K.atar(str(c), uni, TID)
            for x in ([f] + f.get("todas", []) + f.get("ninguno_de", [])):
                if "campo" in x and x["campo"] in I.valores(g["rubro"]): g["campos"].add(x["campo"])
    return g
def limpio(p):
    return json.dumps({k: v for k, v in p.items() if k not in ("n",)}, ensure_ascii=False)
CASOS = {}
for l in open(os.path.join(REPO, "banco_pruebas/traduccion58_corridas.jsonl")):
    x = json.loads(l)
    if (x.get("modelo") or "prod") != "prod" or x.get("rep") or not x["bien"]: continue
    for p in (x["agenda"] or {}).get("preguntas") or []:
        g = oro(p)
        if g["rubro"] or g["tema"]:
            key = json.dumps({k: v for k, v in p.items() if k not in ("n", "cita")}, ensure_ascii=False, sort_keys=True)
            CASOS.setdefault(key, (p, g))
CASOS = list(CASOS.values())
def uno(c):
    p, g = c; txt = limpio(p); out = {"g": {**g, "campos": sorted(g["campos"]), "prods": sorted(g["prods"]) if g["prods"] else None}}
    q = {f"r_{r}": {"type": "noul", "instructions": f"La PREGUNTA LIMPIA pide o nombra productos del rubro {I.NOMBRE.get(r, r)}?"} for r in I.RUBROS}
    q["tema"] = {"type": "choice", "criteria": {f["tema"]: I.desc_tema(f) for f in I.FAQ} | {"ninguno": "no pregunta una regla de la tienda"}, "instructions": "Que regla de la tienda pregunta la PREGUNTA LIMPIA?"}
    a = jev(q, I.nivel1() + f"\n\nPREGUNTA LIMPIA DEL CLIENTE: {txt}", "calibrar_n1")
    out["rubros"] = sorted(I.RUBROS, key=lambda r: -a[f"r_{r}"]["noul"]); out["rp"] = [round(a[f"r_{r}"]["noul"], 2) for r in out["rubros"][:4]]
    out["temas"] = rank(a["tema"])
    if g["rubro"]:
        r = g["rubro"]; vs = I.valores(r)
        q2 = {f"c_{k}": {"type": "noul", "instructions": f"La PREGUNTA LIMPIA pide, pregunta o pone como condicion {(I.SPECS.get(k) or {}).get('etiqueta', k.replace('_', ' '))}?"} for k in vs}
        q2["prod"] = {"type": "choice", "criteria": {str(x["id"]): f"{x['nombre']} ${K.entero(x.get('precio_ars'))}" for x in PS if x["categoria"] == r},
                      "instructions": "Que producto de la tienda nombra o le conviene a la PREGUNTA LIMPIA?"}
        b = jev(q2, I.nivel2(r) + f"\n\nPREGUNTA LIMPIA DEL CLIENTE: {txt}", "calibrar_n2")
        out["campos"] = sorted(vs, key=lambda k: -b[f"c_{k}"]["noul"]); out["prods"] = rank(b["prod"])
    return out
if __name__ == "__main__":
    print(len(CASOS), "preguntas limpias distintas", flush=True)
    with ThreadPoolExecutor(6) as ex: R = list(ex.map(uno, CASOS))
    json.dump(R, open(os.path.join(D, "calibrar_resp.json"), "w"), ensure_ascii=False)
    print(f"gasto Jev: {gastado() - INICIO:.4f} USD")
