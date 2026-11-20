"""LOS EMBEDDINGS ANTES DE LA LLAMADA 0: QUE VOCABULARIO DE LA TIENDA LE ARMAMOS A LUNA (20-nov-2026).

Orden de Martin del 20-nov: medir, sin modelo de lenguaje, que aportan los embeddings del mensaje del cliente antes de la
llamada 0, para armarle a Luna una ficha con los nombres de rubros, campos y temas que le sirven a traducir. Tres formas
de consultar, sobre las 200 y los 100 negativos:

  entero    el mensaje entero, los 5, 8 y 10 primeros de cada seccion.
  trozos    el mensaje partido por codigo en comas, puntos, punto y coma, " y ", tambien, ademas, pero y signos de pregunta;
            los 3 primeros de cada seccion por trozo, unidos sin repetir.
  ventanas  ventanas de 7 palabras con paso de 4; los 3 primeros por ventana y seccion, unidos.

Las secciones, los mismos documentos que la busqueda por seccion de la FICHA 103, `busqueda_fuente.py`:
  rubros    el documento de rubro del indice de la tienda, "rubro: alias, alias" (sin lo que no se vende).
  temas     cada alias de cada tema de la FAQ como documento; el puntaje del tema es el de su alias mas parecido.
  campos    cada alias de cada campo de `alias.json` y el nombre del campo, un documento cada uno; igual que los temas.
Lo esperado sale de las mismas varas: las 200 como `busqueda_fuente.main`, los negativos de `bancos/negativos100.py`.
El tamano de la ficha cuenta cada nombre con sus 3 primeros alias, "nombre: a, b, c", y cuatro caracteres por token.

Los vectores de los alias de campos y de las consultas quedan en `grabado/embeddings_antes_cache.*`; la segunda corrida no
pide nada. Con la clave gratis, con pausa ante 429; la paga solo con MARTIN_AUTORIZO_LA_PAGA=<fecha>, por `embeddings.pedir`.
Resultado por mensaje en `grabado/embeddings_antes.jsonl`.

    python3 banco_pruebas/flujo/embeddings_antes.py
"""
import collections
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from entorno import GRABADO  # noqa: E402

os.environ.setdefault("EMB_CACHE", os.path.join(GRABADO, "embeddings_antes_cache"))
SALIDA = os.path.join(GRABADO, "embeddings_antes.jsonl")
SALTO = re.compile(r"[,.;:?¿!¡]+|\b(?:y|tambien|también|ademas|además|pero)\b", re.I)
LARGOS = [("hasta 15", 0, 15), ("16 a 40", 16, 40), ("mas de 40", 41, 10 ** 9)]
FORMAS = [("entero5", 5), ("entero8", 8), ("entero10", 10), ("trozos3", 3), ("ventanas3", 3)]


def trozos(t):
    return [x.strip() for x in SALTO.split(t) if x and re.search(r"\w", x)] or [t]


def ventanas(t, n=7, paso=4):
    ws = t.split()
    out, i = [], 0
    while True:
        out.append(" ".join(ws[i:i + n]))
        if i + n >= len(ws):
            return out
        i += paso


def consultas(forma, t):
    return [t] if forma.startswith("entero") else trozos(t) if forma.startswith("trozos") else ventanas(t)


def mensajes():
    """[(banco, id, texto, {rubros esperados}, [alternativas de tema])] de las 200 y los 100 negativos."""
    import flujo_nuevo as F
    import reales as RE
    from negativos100 import CASOS
    rub, tem = {}, {}
    for b, cid, _, cs, _ in F.bancos():
        rub[(b, cid)] = {r for _, r in cs if r and r != "ninguno"}
    for c in RE.CASOS:
        rub[("reales", c[0])] = set(c[2].get("rubros") or [])
    for cid, _, x in RE.casos_525()[0]:
        rub[("reales525", cid)] = set(x.get("rubros") or [])
        tem[("reales525", cid)] = [set(t) for t in x.get("temas") or []]
    c200 = [(c["banco"], c["id"], c["texto"]) for c in json.load(open(os.path.join(AQUI, "bancos", "las200.json")))["casos"]]
    out = [("200", b, i, t, rub.get((b, i), set()), tem.get((b, i), [])) for b, i, t in c200]
    out += [("neg100", "neg100", cid, t, set(e["rubros"]), [set(a) for a in e["temas"]]) for cid, t, e in CASOS]
    return out


def main():
    import numpy as np
    import embeddings as EMB
    import nexo_rubro as NR
    import nexo_tema as NT
    _, alias, rubros, _ = NR.fuente()
    voc = json.load(open(os.path.join(NR._A.DATOS, NR.TID, "alias.json"), encoding="utf-8"))
    cache = EMB.cargar()
    # Los documentos de cada seccion: (nombre, texto). Rubros y temas son los del indice del repo.
    docs = {"rubros": [(r, NR.doc_rubro(r, alias)) for r in rubros],
            "temas": [(t, a) for t, a in NT.docs(*NT.fuente())],
            "campos": [(c, x) for c, al in voc["campos"].items() for x in [c.replace("_", " ")] + al]}
    docs_vec = {}
    for sec, ds in docs.items():
        docs_vec[sec] = np.array(EMB.pedir([t for _, t in ds], EMB.DOCUMENTO, cache, callado=True), dtype=np.float32)
    nombres = {s: list(dict.fromkeys(n for n, _ in ds)) for s, ds in docs.items()}
    fila = {s: np.array([nombres[s].index(n) for n, _ in ds]) for s, ds in docs.items()}
    # La ficha de un nombre: "nombre: alias1, alias2, alias3".
    al = {"rubros": voc["rubros"], "temas": voc["temas"], "campos": voc["campos"]}

    def ficha_txt(sec, n):
        return f"{n}: {', '.join(al[sec].get(n, [])[:3])}"
    hay_r = set(nombres["rubros"])
    msgs = mensajes()
    # Todas las consultas de las tres formas, pedidas de una vez.
    todas = list(dict.fromkeys(q for m in msgs for f, _ in FORMAS for q in consultas(f, m[3])))
    q = dict(zip(todas, EMB.pedir(todas, EMB.CONSULTA, cache)))

    def top(texto, sec, n):
        s = docs_vec[sec] @ np.array(q[texto], dtype=np.float32)
        mejor = np.full(len(nombres[sec]), -9.0, dtype=np.float32)
        np.maximum.at(mejor, fila[sec], s)
        return [nombres[sec][i] for i in np.argsort(-mejor, kind="stable")[:n]]

    def ficha(forma, n, t):
        f = {}
        for sec in docs:
            f[sec] = list(dict.fromkeys(x for c in consultas(forma, t) for x in top(c, sec, n)))
        return f
    res = collections.defaultdict(list)
    with open(SALIDA, "w", encoding="utf-8") as fh:
        for banco, b, cid, t, rs, ts in msgs:
            rs = rs & hay_r
            for forma, n in FORMAS:
                f = ficha(forma, n, t)
                toks = {s: sum(len(ficha_txt(s, x)) for x in f[s]) // 4 + len(f[s]) for s in f}
                r = {"conjunto": banco, "banco": b, "id": cid, "palabras": len(t.split()), "forma": forma,
                     "rubros_esp": sorted(rs), "rubros_ok": sorted(rs & set(f["rubros"])),
                     "temas_esp": [sorted(a) for a in ts],
                     "temas_ok": [sorted(a) for a in ts if a & set(f["temas"])],
                     "ficha": f, "nombres": {s: len(f[s]) for s in f}, "tokens": toks}
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                res[(banco, forma)].append(r)
    informe(res)


def informe(res):
    print("EMBEDDINGS ANTES DE LA LLAMADA 0, sin modelo. Referencia de la FICHA 103, por fila y por seccion: rubros 239 de 239, temas 14 de 14.")
    for banco, nom in (("200", "LAS 200"), ("neg100", "LOS 100 NEGATIVOS")):
        print(f"\n{nom}")
        for forma, _ in FORMAS:
            rs = res[(banco, forma)]
            cr = [r for r in rs if r["rubros_esp"]]
            ct = [r for r in rs if r["temas_esp"]]
            ok_r = sum(len(r["rubros_ok"]) for r in cr)
            tot_r = sum(len(r["rubros_esp"]) for r in cr)
            ok_t = sum(len(r["temas_ok"]) for r in ct)
            tot_t = sum(len(r["temas_esp"]) for r in ct)
            nom_m = sum(sum(r["nombres"].values()) for r in rs) / len(rs)
            tok = sum(sum(r["tokens"].values()) for r in rs) / len(rs)
            sec = {s: sum(r["nombres"][s] for r in rs) / len(rs) for s in ("rubros", "campos", "temas")}
            print(f"  {forma:10} rubros todos {sum(len(r['rubros_ok']) == len(r['rubros_esp']) for r in cr)} de {len(cr)} mensajes, "
                  f"{ok_r} de {tot_r} rubros · temas todos {sum(len(r['temas_ok']) == len(r['temas_esp']) for r in ct)} de {len(ct)}, "
                  f"{ok_t} de {tot_t} · ficha {nom_m:.1f} nombres (rub {sec['rubros']:.1f}, cam {sec['campos']:.1f}, tem {sec['temas']:.1f}), "
                  f"{tok:.0f} tokens")
            partes = []
            for nl, lo, hi in LARGOS:
                a = [r for r in cr if lo <= r["palabras"] <= hi]
                b = [r for r in ct if lo <= r["palabras"] <= hi]
                partes.append(f"{nl}: rubros {sum(len(r['rubros_ok']) == len(r['rubros_esp']) for r in a)}/{len(a)}"
                              f" temas {sum(len(r['temas_ok']) == len(r['temas_esp']) for r in b)}/{len(b)}")
            print("             por largo, " + " · ".join(partes))


if __name__ == "__main__":
    main()
