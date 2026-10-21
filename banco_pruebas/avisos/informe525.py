"""Las 525 con el metodo de comandos, la segunda vuelta, contra produccion y contra la tabla mejorada de ayer, forma por forma y caso por caso."""
import collections
import json
import os

D = os.path.dirname(os.path.abspath(__file__))
rows = [json.loads(l) for l in open("/home/user/Verifika/banco_pruebas/traduccion58_corridas.jsonl")]
prod = {(r["charla"], r["turno"], r["forma"]): r["bien"] for r in rows if r.get("modelo", "gemini") == "gemini" and r["rep"] == 0}
tabla = {(r["charla"], r["turno"], r["forma"]): r["bien"] for r in rows if r.get("modelo") == "gemini_or+tabla"}
ayer = {k: tabla.get(k, v) for k, v in prod.items()}
r2 = {(x["charla"], x["turno"], x["forma"]): x for x in map(json.loads, open(f"{D}/comandos525.jsonl"))}
ks = sorted(r2)
print(f"corridas: {len(ks)} de 525")
print("forma       prod  ayer  hoy  de")
for f in ("original", "plano", "whatsapp", "redactada", "coloquial", "TOTAL"):
    kk = [k for k in ks if f == "TOTAL" or k[2] == f]
    print(f"{f:10} {sum(prod[k] for k in kk):5} {sum(ayer[k] for k in kk):5} {sum(r2[k]['bien'] for k in kk):4} {len(kk):4}")
rompe = [k for k in ks if prod[k] and not r2[k]["bien"]]
arregla = [k for k in ks if not prod[k] and r2[k]["bien"]]
print(f"\narregla {len(arregla)} y rompe {len(rompe)} contra produccion")
por_turno = collections.defaultdict(list)
for k in rompe:
    por_turno[(k[0], k[1])].append(k[2])
for t, fs in sorted(por_turno.items()):
    print(f"  ROMPE {t[0]} T{t[1]}: {', '.join(fs)} | {r2[(t[0], t[1], fs[0])]['malas'][:2]}")
mal = [k for k in ks if not r2[k]["bien"]]
print(f"\nsiguen mal: {len(mal)}")
por_turno = collections.defaultdict(list)
for k in mal:
    por_turno[(k[0], k[1])].append(k[2])
for t, fs in sorted(por_turno.items()):
    print(f"  {t[0]} T{t[1]}: {', '.join(fs)} | {r2[(t[0], t[1], fs[0])]['malas'][:2]}")
