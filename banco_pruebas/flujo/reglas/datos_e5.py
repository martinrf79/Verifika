"""LOS PARES PARA AJUSTAR EL MODELO DE EMBEDDINGS CHICO CON LA FUENTE Y LA JERGA (24-nov-2026). Corre con python3.

Tres grupos, todos del repo, ninguno escrito por un modelo:
  documento  lo que es cada cosa en la fuente: el rubro con productos reales, la caracteristica con su campo y valor,
             el campo de la ficha y el tema de la FAQ. Grupos 2 y 3.
  jerga      como lo dice el cliente: los alias de alias.json, las expresiones de base.py, los nombres de los productos
             y las frases reales del repo con su rubro etiquetado. Grupo 1.
Cada par es (jerga, documento). Quedan fuera las frases de las tres muestras de prueba y las variantes de sus casos.
Un 10% de los alias, al azar, queda aparte para medir si el ajuste generaliza a jerga que no vio.
"""
import json, os, random, re, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
FL = os.path.join(AQUI, "..")
sys.path[:0] = [AQUI, FL, os.path.join(FL, "traductor")]
sys.dont_write_bytecode = True
import base as B, catalogo as K  # noqa: E402
from muestra import M  # noqa: E402
from muestra2 import M2  # noqa: E402
from muestra3 import M3  # noqa: E402

ALIAS = json.load(open(os.path.join(AQUI, "../../../data/clientes/verifika_prod/alias.json"), encoding="utf-8"))
n = lambda s: re.sub(r"\W+", " ", s.lower()).strip()


def docs():
    d = {}
    por = {}
    for k in K.MOD:
        por.setdefault(k[0], []).append(K.MOD[k][0]["nombre"])
    for r, ps in por.items():
        d[("rubro", r)] = f"rubro {r}: " + "; ".join(ps[:4])
    for c, conds, _ in B.BASE:
        d[("cond", c)] = f"{c.replace('_', ' ')}: " + "; ".join(f"{a} {o} {v if isinstance(v, (str, int)) else ' o '.join(v)}" for a, o, v in conds)
    for c in ALIAS["campos"]:
        d[("campo", c)] = f"dato de la ficha: {c.replace('_', ' ')}"
    for t in ALIAS["temas"]:
        d[("tema", t)] = f"pregunta sobre {t.replace('_', ' ')}"
    return d


def prueba_textos():
    ts = {n(m[2]) for m in M} | {n(m[1]) for m in M2} | {n(m[1]) for m in M3}
    bases = {m[0].split(":")[1] for m in M2 + M3 if m[0].startswith("525:")}
    return ts, bases


def pares():
    D = docs()
    ts, bases = prueba_textos()
    rnd = random.Random(2411)
    alias, otros = [], []
    for sec, tipo in (("rubros", "rubro"), ("campos", "campo"), ("temas", "tema")):
        for k, al in ALIAS[sec].items():
            if (tipo, k) in D:
                for a in al:
                    alias.append((a, D[(tipo, k)]))
    for c, _, ex in B.BASE:
        otros += [(e, D[("cond", c)]) for e in ex]
    for k in K.MOD:
        otros.append((f"{k[1]} {k[2]}", D[("rubro", k[0])]))
    import embeddings_antes as EA, reales as RE
    reales = []
    for c in EA.mensajes():
        if c[0] != "neg100" and len(c[4]) == 1:
            reales.append((c[3], sorted(c[4])[0], c[2]))
    for cid, t, x in RE.casos_525()[0]:
        if len(x.get("rubros") or []) == 1:
            reales.append((t, sorted(x["rubros"])[0], cid))
    vistos = set()
    for t, r, cid in reales:
        if n(t) in ts or cid.split(".")[0] in bases or n(t) in vistos or ("rubro", r) not in D:
            continue
        vistos.add(n(t))
        otros.append((t, D[("rubro", r)]))
    rnd.shuffle(alias)
    corte = len(alias) // 10
    return alias[corte:] + otros, alias[:corte], D


if __name__ == "__main__":
    tr, ho, D = pares()
    json.dump({"train": tr, "holdout": ho, "docs": list(D.values())}, open(os.path.join(AQUI, "pares_e5.json"), "w"), ensure_ascii=False)
    print("documentos", len(D), "pares de entrenamiento", len(tr), "alias aparte", len(ho))
