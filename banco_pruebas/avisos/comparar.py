"""Cada variante contra lo ya medido en produccion, turno por turno y forma por forma."""
import collections
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = "/home/user/Verifika/banco_pruebas/traduccion58_corridas.jsonl"


def leer(p):
    return [json.loads(x) for x in open(p, encoding="utf-8")] if os.path.exists(p) else []


def main(variantes):
    base = collections.defaultdict(list)
    for r in leer(BASE):
        if r.get("modelo", "gemini") == "gemini":
            base[(r["charla"], r["turno"], r["forma"])].append(r["bien"])
    for v in variantes:
        filas = leer(os.path.join(AQUI, f"corridas_{v}.jsonl"))
        por = collections.defaultdict(list)
        for r in filas:
            por[(r["charla"], r["turno"], r["forma"])].append(r)
        print(f"\n== {v}: {len(filas)} corridas")
        arregla, rompe, bien_v, bien_b = [], [], 0, 0
        for k in sorted(por):
            rs = por[k]
            bv = all(r["bien"] for r in rs)
            bb = all(base.get(k, [False]))
            bien_v += bv
            bien_b += bb
            marca = "ARREGLA" if bv and not bb else "ROMPE" if bb and not bv else ""
            (arregla if marca == "ARREGLA" else rompe if marca == "ROMPE" else []).append(k)
            print(f"  {k[0]} T{k[1]} {k[2]:9} {''.join('B' if r['bien'] else 'm' for r in rs):3} base "
                  f"{sum(base.get(k, []))}/{len(base.get(k, []))} {marca:8} {'; '.join(rs[-1]['malas'])[:70]}")
        print(f"  bien en todas sus repeticiones: {bien_v} de {len(por)}; produccion {bien_b}")
        print(f"  arregla {len(arregla)}, rompe {len(rompe)}")
        uso = leer(os.path.join(AQUI, f"uso_{v}.jsonl"))
        if uso:
            ent = sum(u["entrada"] for u in uso) / max(1, len(por))
            seg = sum(u["seg"] for u in uso) / max(1, len(por))
            print(f"  por turno: {ent:.0f} tokens de entrada, {seg:.1f} segundos de modelo, {len(uso) / len(por):.1f} llamadas")


if __name__ == "__main__":
    main(sys.argv[1:] or ["V1"])
