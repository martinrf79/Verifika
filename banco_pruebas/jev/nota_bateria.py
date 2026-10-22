import json, os, sys, collections
D = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, D)
from bateria import T, oro, RUBROS
R = [json.loads(l) for l in open(os.path.join(D, "bateria_resp.jsonl"))]
B = [r for r in R if r["rep"] == 0]
def nota(r, ur=0.5):
    rub, tem, prods = oro(T[(r["charla"], r["turno"])])
    pred = {k for k, v in r["pr"].items() if v >= ur}
    top3f = sorted(r["pf"], key=lambda k: -r["pf"][k])[:3]
    predf = {k for k, v in r["pf"].items() if v >= 0.5}
    allrank = [i for v in r["rank"].values() for i in v[:5]]
    return dict(rub=len(rub), rub_ok=len(rub & pred), rub_mas=len(pred - rub), tem=len(tem), tem_t3=len(tem & set(top3f)), tem_mas=len(predf - tem),
                prod=len(prods), prod_t5=sum(bool(g & set(allrank)) for g in prods), vacio=not rub and not tem and not prods)
print(f"casos {len(B)}, tokens Jev mediana {sorted(r['tok'] for r in B)[len(B)//2]}, ms mediana {sorted(r['ms'] for r in B)[len(B)//2]}")
for forma in ("original", "plano", "whatsapp", "redactada", "coloquial", None):
    S = [r for r in B if forma is None or r["forma"] == forma]
    if not S: continue
    c = collections.Counter()
    for r in S:
        for k, v in nota(r).items(): c[k] += v
    print(f"{forma or 'TODAS':10} n={len(S):3} | rubros dados {c['rub_ok']}/{c['rub']} de mas {c['rub_mas']} | reglas en top3 {c['tem_t3']}/{c['tem']} de mas(>=.5) {c['tem_mas']} | producto nombrado en top5 {c['prod_t5']}/{c['prod']}")
for ur in (0.3, 0.7):
    c = collections.Counter()
    for r in B:
        for k, v in nota(r, ur).items(): c[k] += v
    print(f"umbral rubro {ur}: dados {c['rub_ok']}/{c['rub']} de mas {c['rub_mas']}")
# estabilidad
por = collections.defaultdict(list)
for r in R:
    if r["forma"] == "original": por[(r["charla"], r["turno"])].append(r)
igual = tot = 0
for v in por.values():
    if len(v) < 2: continue
    tot += 1
    sig = lambda r: (tuple(sorted(k for k, p in r["pr"].items() if p >= .5)), tuple(sorted(k for k, p in r["pf"].items() if p >= .5)), tuple(tuple(x[:3]) for x in r["rank"].values()))
    igual += len({sig(r) for r in v}) == 1
print(f"estabilidad: {igual}/{tot} turnos con la misma seleccion en todas las repeticiones")
print("\nFALLAS (forma: falta):")
for r in B:
    rub, tem, prods = oro(T[(r["charla"], r["turno"])])
    pred = {k for k, v in r["pr"].items() if v >= 0.5}; top3f = sorted(r["pf"], key=lambda k: -r["pf"][k])[:3]
    allrank = [i for v in r["rank"].values() for i in v[:5]]
    f = [f"rubro {x}" for x in rub - pred] + [f"regla {x} (Jev {top3f[0]})" for x in tem - set(top3f)] + ["producto" for g in prods if not g & set(allrank)]
    if f: print(f"  {r['charla']} T{r['turno']} {r['forma']}: {', '.join(f)} | «{r['texto'][:90]}»")
