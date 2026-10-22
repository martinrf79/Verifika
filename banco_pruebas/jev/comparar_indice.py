"""¿El indice en niveles baja lo que Jev logra con la fuente entera? Mismas varas, mismos casos."""
import json, os, sys, collections
from concurrent.futures import ThreadPoolExecutor
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
import indice_jev as I
from sondas2 import llamar, GASTO, SPECS as SP2, PLAT, hoja
from sondas import rank, STOCK
import bateria as B, redactadas as RD
TOPE_USD = 0.10
def gastado(): return sum(json.loads(l)["usd"] for l in open(GASTO)) if os.path.exists(GASTO) else 0
INICIO = gastado()
def jev(qs, state, et):
    if gastado() - INICIO > TOPE_USD: raise SystemExit("tope de gasto de esta corrida")
    return llamar({"state": state, "model": "jev-latest", "questions": qs}, et)["answers"]
N1 = I.nivel1()
def q1(texto):
    q = {f"r_{r}": {"type": "noul", "instructions": f"Lo que pide el ULTIMO MENSAJE, leido con la charla, incluye productos del rubro {I.NOMBRE.get(r, r)}?"} for r in I.RUBROS}
    q["tema"] = {"type": "choice", "criteria": {f["tema"]: I.desc_tema(f) for f in I.FAQ} | {"ninguno": "no pregunta ninguna regla de la tienda"},
                 "instructions": "Que regla de la tienda pregunta el ULTIMO MENSAJE?"}
    return q
def uno(c):
    st = N1 + f"\n\n{c['libreta']}\n\nULTIMO MENSAJE DEL CLIENTE: {c['texto']}"
    a = jev(q1(c["texto"]), st, "indice_n1")
    return {**c, "rub": {r for r in I.RUBROS if a[f"r_{r}"]["noul"] >= .5}, "temas3": rank(a["tema"])[:3]}

def parte_a():
    casos = []
    for (ch, tu, fo), tx in B.TEXTOS.items():
        if fo in ("original", "coloquial") and (ch, tu) in B.T:
            rub, tem, _ = B.oro(B.T[(ch, tu)]); casos.append({"de": fo, "libreta": B.T[(ch, tu)]["libreta"], "texto": tx, "rub_oro": rub, "tem_oro": [(t,) for t in tem]})
    for tx, rub, reglas, _, _ in RD.CASOS:
        casos.append({"de": "redactadas", "libreta": RD.VACIA, "texto": tx, "rub_oro": rub, "tem_oro": reglas})
    with ThreadPoolExecutor(6) as ex: R = list(ex.map(uno, casos))
    c = collections.defaultdict(collections.Counter)
    for r in R:
        k = c[r["de"]]; k["rub"] += len(r["rub_oro"]); k["rub_ok"] += len(r["rub_oro"] & r["rub"]); k["rub_mas"] += len(r["rub"] - r["rub_oro"])
        k["tem"] += len(r["tem_oro"]); k["tem_ok"] += sum(bool(set(g) & set(r["temas3"])) for g in r["tem_oro"])
        k["ruido"] += (not r["tem_oro"]) and r["temas3"][0] != "ninguno"; k["sin_regla"] += not r["tem_oro"]
    for de, k in c.items():
        print(f"  {de:10} rubros {k['rub_ok']}/{k['rub']} de mas {k['rub_mas']} | reglas en top3 {k['tem_ok']}/{k['tem']} | sin regla pedida y marca una primero: {k['ruido']}/{k['sin_regla']}")

def parte_b():
    """Datos tecnicos y compatibilidad: Jev elige campo=valor del nivel 2 y el codigo filtra."""
    casos = []
    for r in I.RUBROS:
        del_r = [p for p in STOCK if p["categoria"] == r]
        for sid, (f, formal, vaga) in SP2.items():
            b = {str(p["id"]) for p in del_r if (p.get("specs") or {}).get(sid) and f((p.get("specs") or {})[sid])}
            if 0 < len(b) < len([p for p in del_r if (p.get("specs") or {}).get(sid)]):
                casos += [(r, f"busco {r} {formal}", b, "spec formal"), (r, f"quiero {r} {vaga}", b, "spec vaga")]
        con = [(p, I.COMPAT.get((p.get("marca"), p.get("modelo")))) for p in del_r]; con = [(p, x) for p, x in con if x]
        for pl, (formal, vaga) in PLAT.items():
            b = {str(p["id"]) for p, x in con if pl in x["plataformas"].split("|")}
            if 0 < len(b) < len(con): casos += [(r, f"busco {r} {formal}", b, "compat formal"), (r, f"necesito {r} {vaga}", b, "compat vaga")]
    c = collections.Counter(); mal = []
    for r in sorted({x[0] for x in casos}):
        sub = [(i, x) for i, x in enumerate(casos) if x[0] == r]; op = I.opciones2(r)
        a = jev({f"q{i}": {"type": "choice", "criteria": op, "instructions": f"El cliente pide: «{t}». Que dato del rubro pide?"} for i, (_, t, _, _) in sub}, I.nivel2(r), "indice_n2")
        for i, (_, t, b, k) in sub:
            campo, valor = a[f"q{i}"]["choice"].split("=", 1)
            # el codigo junta todos los valores del mismo campo que Jev da por buenos con 0.2 o mas
            vals = [o.split("=", 1)[1] for o, p in a[f"q{i}"]["probabilities"].items() if o.startswith(campo + "=") and p >= .2] or [valor]
            sel = set().union(*(I.productos_con(r, campo, v) for v in vals))
            ok = bool(sel) and sel <= b; c[k + "#"] += 1; c[k] += ok; c[k + "cubre"] += len(sel & b); c[k + "total"] += len(b)
            if not ok: mal.append((t, a[f"q{i}"]["choice"], vals))
    for k in ("spec formal", "spec vaga", "compat formal", "compat vaga"):
        print(f"  {k}: todo lo que trae cumple en {c[k]}/{c[k+'#']}; trae {c[k+'cubre']} de los {c[k+'total']} que cumplen")
    for m in mal[:10]: print("    ", m)

if __name__ == "__main__":
    print("A. nivel 1, rubros y reglas desde el mensaje crudo:"); parte_a()
    print("B. nivel 2, campo y valor, y el codigo filtra:"); parte_b()
    print(f"gasto de esta corrida: {gastado() - INICIO:.4f} USD")
