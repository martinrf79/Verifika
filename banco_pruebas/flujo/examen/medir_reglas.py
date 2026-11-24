"""LA LINEA DE BASE: EL RESOLVEDOR POR REGLAS CONTRA EL EXAMEN FIJO (24-nov-2026). Ver plan.md.
Corre en el entorno aparte del modelo chico, con torch y transformers, desde banco_pruebas/flujo:

    <venv>/bin/python examen/medir_reglas.py        # escribe examen/base_reglas.jsonl y el informe
"""
import collections, json, os, statistics, subprocess, sys, time
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [AQUI, os.path.join(AQUI, "..", "reglas")]
sys.dont_write_bytecode = True
import examen as X  # noqa: E402

subprocess.run([sys.executable, os.path.join(AQUI, "examen.py"), "--verificar"], check=True)
import resolver as RV  # noqa: E402

EX = json.load(open(os.path.join(AQUI, "examen.json"), encoding="utf-8"))
CORTES = json.load(open(RV.CORTES))


def cuenta(xs):
    c = collections.Counter(xs)
    return {k: c[k] for k in ("acierta", "repregunta", "erra") if c[k]}


def casillero(e, info, tipo, clave):
    esp, dijo = X.etiquetado(e, tipo), set(info[clave])
    return {"bien": len(esp & dijo), "de_mas": len(dijo - esp), "de_menos": len(esp - dijo)}


if __name__ == "__main__":
    out, seg = [], []
    for e in EX:
        t = time.time()
        dec, of, info = RV.resolver(e["texto"], CORTES["alto"], CORTES["bajo"], RV.topes(e["texto"]))
        seg.append(time.time() - t)
        o = {"id": e["id"], "texto": e["texto"], "dudosa": e["dudosa"], "varios": len(e["pedidos"]) > 1,
             "dec": dec, "of": [list(k) for k in of], "c": X.corregir(e, dec, of),
             "repreguntar_valia": any("repreguntar" in p["esperados"] for p in e["pedidos"]),
             "cas": {t: casillero(e, info, t, k) for t, k in (("rubro", "rubros"), ("marca", "marcas"), ("modelo", "modelos"))},
             **{k: v for k, v in info.items() if k != "amarillos"}}
        out.append(o)
    with open(os.path.join(AQUI, "base_reglas.jsonl"), "w") as f:
        for o in out:
            f.write(json.dumps(o, ensure_ascii=False, default=list) + "\n")
    grupos = {"un pedido, sin dudosas": [o for o in out if not o["varios"] and not o["dudosa"]],
              "un pedido, dudosas": [o for o in out if not o["varios"] and o["dudosa"]],
              "varios pedidos": [o for o in out if o["varios"]]}
    print("cortes", CORTES["alto"], CORTES["bajo"], "frases", len(out))
    for g, os_ in grupos.items():
        print(f"{g}: {len(os_)}", cuenta([o['c'] for o in os_]))
    print("todas:", cuenta([o["c"] for o in out]))
    rep = [o for o in out if o["c"] == "repregunta"]
    print(f"repreguntas que la etiqueta admitia: {sum(o['repreguntar_valia'] for o in rep)} de {len(rep)}")
    for t in ("rubro", "marca", "modelo"):
        s = collections.Counter()
        for o in out:
            s.update(o["cas"][t])
        print(f"casillero {t}:", dict(s))
    seg.sort()
    print(f"tiempo por frase: mediana {statistics.median(seg) * 1000:.0f} ms, p90 {seg[int(len(seg) * .9) - 1] * 1000:.0f} ms")
