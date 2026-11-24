"""EL POZO DEL EXAMEN FIJO, FICHA 106 paso 2 (24-nov-2026): las frases reales del repo y de produccion que ninguna
prueba ni ningun ajuste uso todavia.

Fuentes reales: los mensajes de clientes de produccion, vivos y archivados, bajados el 24-nov con la cuenta de solo
lectura, solo el texto y con telefonos, CUIT, tarjetas y mails tapados, en `produccion_bruto.json`; la cosecha de produccion y `reales/`; las charlas del examen real.
Quedan fuera: las 48 de la FICHA 105, muestra2 y muestra3, sus casos base, y toda frase con la que se ajusto e5 en
`reglas/datos_e5.py`. Se compara normalizado: minusculas, sin tildes ni signos.

    python3 examen/pozo.py      # escribe examen/pozo.json y cuenta por fuente
"""
import json, os, re, sys, unicodedata
AQUI = os.path.dirname(os.path.abspath(__file__))
FL = os.path.join(AQUI, "..")
BP = os.path.join(FL, "..")
sys.path[:0] = [FL, os.path.join(FL, "reglas"), os.path.join(FL, "traductor")]
sys.dont_write_bytecode = True


def n(s):
    s = "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def fuentes():
    out = [("prod", t) for t in json.load(open(os.path.join(AQUI, "produccion_bruto.json"), encoding="utf-8"))]
    for l in open(os.path.join(BP, "cosecha_produccion.jsonl"), encoding="utf-8"):
        out += [("cosecha", x["texto"]) for x in json.loads(l)["turnos"]]
    for f in sorted(os.listdir(os.path.join(BP, "reales"))):
        if f.endswith(".json"):
            out += [("reales", x.get("mensaje") or "") for x in json.load(open(os.path.join(BP, "reales", f)))["turnos"]]
    for c in json.load(open(os.path.join(BP, "examen_real", "charlas.json"), encoding="utf-8")):
        out += [("examen", t) for t in c["mensajes"]]
    return [(f, t.strip()) for f, t in out if t and t.strip()]


def usadas():
    from muestra import M
    from muestra2 import M2
    from muestra3 import M3
    import datos_e5 as DE
    u = {n(m[2]) for m in M} | {n(m[1]) for m in M2} | {n(m[1]) for m in M3}
    tr, ho, _ = DE.pares()
    u |= {n(j) for j, _ in tr + ho}
    return u


if __name__ == "__main__":
    import collections
    U = usadas()
    pozo, visto = [], set()
    cuenta = collections.Counter()
    for f, t in fuentes():
        k = n(t)
        if not k or k in visto:
            continue
        visto.add(k)
        if k in U:
            cuenta[f + " usada"] += 1
            continue
        cuenta[f] += 1
        pozo.append({"fuente": f, "texto": t})
    json.dump(pozo, open(os.path.join(AQUI, "pozo.json"), "w"), ensure_ascii=False, indent=0)
    print(dict(cuenta), "pozo:", len(pozo))
