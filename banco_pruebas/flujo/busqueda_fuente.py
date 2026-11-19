"""LA BUSQUEDA SOBRE LAS FILAS DE LA LLAMADA 0: CUANTOS CANDIDATOS Y DE QUE PARTE DE LA FUENTE (19-nov-2026).

Orden de Martin del 19-nov: Luna solo separa y corrige la ortografia, v13, y los embeddings de cada fila traen candidatos
de la fuente de la tienda para que elija Jev. Mide, sobre las 200, si lo que el cliente pide esta entre los candidatos de
alguna fila del mensaje: el rubro, el tema de la FAQ y lo que la tienda declara que no vende. Sin gasto de modelo: los
documentos ya estan en el indice de la tienda y las filas se piden con la clave gratis.

  toda la fuente    una sola lista con rubros, productos y temas, los N primeros.
  por seccion       los N primeros productos y, aparte, los T primeros temas.

    python3 banco_pruebas/flujo/busqueda_fuente.py [--prompt v13]
"""
import collections
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from entorno import GRABADO  # noqa: E402

PROMPT = sys.argv[sys.argv.index("--prompt") + 1] if "--prompt" in sys.argv else "v13"


def main():
    import embeddings as EMB
    import flujo_nuevo as F
    import nexo_rubro as NR
    import nexo_tema as NT
    import reales as RE
    from app.core.flujo.nuevo import vectores as VV
    _, alias, rubros, modelos = NR.fuente()
    pos, vec, dim = VV.indice(NR.TID)

    def v(d):
        return vec[pos[d] * dim:(pos[d] + 1) * dim]
    rub = [(("no_vende", r[len(NR.NO_SE_VENDE):]) if r.startswith(NR.NO_SE_VENDE) else ("rubro", r), v(d))
           for r, d in NR.indice_rubros(rubros, alias)]
    prod = [(("rubro", k[0]), v(NR.doc_producto(k, modelos[k], alias))) for k in modelos]
    tema = [(("tema", t), v(a)) for t, a in NT.docs(*NT.fuente())]
    # Lo esperado de cada mensaje, de las varas de cada banco.
    esp = {}
    for b, cid, _, cs, _ in F.bancos():
        esp[(b, cid)] = {("rubro", r) for _, r in cs if r and r != "ninguno"}
    for c in RE.CASOS:
        esp[("reales", c[0])] = {("rubro", r) for r in c[2].get("rubros") or []}
    for cid, _, x in RE.casos_525()[0]:
        esp[("reales525", cid)] = ({("rubro", r) for r in x.get("rubros") or []}
                                   | {("tema", frozenset(t)) for t in x.get("temas") or []}
                                   | {("no_vende", r) for r in x.get("no_vende") or []})
    casos = [(c["banco"], c["id"]) for c in json.load(open(os.path.join(AQUI, "bancos", "las200.json")))["casos"]]
    sal = {(r["banco"], r["id"]): r["salida"]["textos"] for r in map(json.loads, open(os.path.join(GRABADO, "llamada0_modelos.jsonl")))
           if r.get("prompt") == PROMPT and r.get("salida")}
    textos = [t for k in casos for t in sal[k]]
    q = dict(zip(textos, EMB.pedir(textos, EMB.CONSULTA, EMB.cargar(), callado=True)))
    hay = {l for l, _ in rub + prod + tema}

    def top(t, idx, n):
        s = sorted(((sum(a * b for a, b in zip(q[t], x)), i) for i, (_, x) in enumerate(idx)), reverse=True)[:n]
        return {idx[i][0] for _, i in s}

    def esta(x, s):
        return any(("tema", y) in s for y in x[1]) if x[0] == "tema" else x in s
    modos = [("toda la fuente, 15", lambda t: top(t, rub + prod + tema, 15)),
             ("por seccion, 15 productos y 3 temas", lambda t: top(t, prod, 15) | top(t, rub, 3) | top(t, tema, 3))]
    print(f"LAS 200, filas del {PROMPT}: lo pedido entre los candidatos de alguna fila del mensaje")
    for nombre, f in modos:
        c, faltan = collections.Counter(), []
        for k in casos:
            tops = [f(t) for t in sal[k]]
            for x in esp.get(k, set()):
                if x[0] != "tema" and x not in hay:
                    continue
                c[(x[0], "total")] += 1
                if any(esta(x, s) for s in tops):
                    c[(x[0], "bien")] += 1
                else:
                    faltan.append((k[1], x[1] if x[0] != "tema" else sorted(x[1])))
        print(f"  {nombre:36} " + " · ".join(f"{t} {c[(t, 'bien')]} de {c[(t, 'total')]}" for t in ("rubro", "tema", "no_vende")))
        print(f"    faltan: {faltan}")


def _n(t):
    import re
    import unicodedata
    return re.sub(r"[^a-z0-9 ]", " ", unicodedata.normalize("NFKD", str(t).lower()).encode("ascii", "ignore").decode())


def _filas_con(palabras, filas):
    """Las filas que traen todas las palabras, por sus primeras cinco letras: "joysticks" toma "joystick"."""
    ws = [w[:5] for w in _n(palabras).split()]
    return [f for f in filas if all(any(x.startswith(w) for x in _n(f).split()) for w in ws)]


def negativos():
    """Los 100 negativos y mixtos del 19-nov, `bancos/negativos100.py`, con el v13, contra las 200 de control: lo que trae
    la fila de lo que la tienda no vende y la de lo que la FAQ no cubre, y los puntajes de unos contra otros."""
    import statistics
    import embeddings as EMB
    import flujo_nuevo as F
    import nexo_rubro as NR
    import nexo_tema as NT
    import reales as RE
    from negativos100 import CASOS
    from app.core.flujo.nuevo import vectores as VV
    _, alias, rubros, modelos = NR.fuente()
    pos, vec, dim = VV.indice(NR.TID)

    def v(d):
        return vec[pos[d] * dim:(pos[d] + 1) * dim]
    rub = [(r, v(d)) for r, d in NR.indice_rubros(rubros, alias)]
    prod = [(k[0], v(NR.doc_producto(k, modelos[k], alias))) for k in modelos]
    tema = [(t, v(a)) for t, a in NT.docs(*NT.fuente())]
    filas = collections.defaultdict(dict)
    for r in map(json.loads, open(os.path.join(GRABADO, "llamada0_modelos.jsonl"))):
        if r.get("prompt") in ("v13", "v13#2") and r.get("salida"):
            filas[r["prompt"]][(r["banco"], r["id"])] = r["salida"]["textos"]
    textos = [t for p in filas.values() for fs in p.values() for t in fs]
    q = dict(zip(textos, EMB.pedir(textos, EMB.CONSULTA, EMB.cargar(), callado=True)))

    def orden(t, idx):
        return sorted(((round(sum(a * b for a, b in zip(q[t], x)), 4), l) for l, x in idx), reverse=True)

    def rubro_en(t, r):
        """El puntaje del mejor producto del rubro r y si r esta entre los candidatos por seccion de la fila."""
        o = orden(t, prod)
        return max(s for s, l in o if l == r), r in {l for _, l in o[:15]} | {l for _, l in orden(t, rub)[:3]}

    # Lo positivo: las 200 de control, las dos corridas del v13.
    esp = {}
    for b, cid, _, cs, _ in F.bancos():
        esp[(b, cid)] = ({r for _, r in cs if r and r != "ninguno"}, [])
    for c in RE.CASOS:
        esp[("reales", c[0])] = (set(c[2].get("rubros") or []), [])
    for cid, _, x in RE.casos_525()[0]:
        esp[("reales525", cid)] = (set(x.get("rubros") or []), [set(t) for t in x.get("temas") or []])
    casos200 = [(c["banco"], c["id"]) for c in json.load(open(os.path.join(AQUI, "bancos", "las200.json")))["casos"]]
    hay = {k[0] for k in modelos}
    p_prod, p_tema, c = [], [], collections.Counter()
    for corrida in ("v13", "v13#2"):
        for k in casos200:
            rs, ts = esp.get(k, (set(), []))
            fs = filas[corrida][k]
            for r in rs & hay:
                mejor = max(rubro_en(t, r) for t in fs)
                c[(corrida, "rubro")] += 1
                c[(corrida, "rubro bien")] += mejor[1]
                p_prod.append(mejor[0])
            for alt in ts:
                s = max(max(sc for sc, l in orden(t, tema) if l in alt) for t in fs)
                bien = any(l in alt for t in fs for _, l in orden(t, tema)[:3])
                c[(corrida, "tema")] += 1
                c[(corrida, "tema bien")] += bien
                p_tema.append(s)
    print("LAS 200 DE CONTROL, por seccion: 15 productos, 3 rubros y 3 temas por fila")
    for corrida in ("v13", "v13#2"):
        print(f"  {corrida:6} rubro {c[(corrida, 'rubro bien')]} de {c[(corrida, 'rubro')]} · tema {c[(corrida, 'tema bien')]} de {c[(corrida, 'tema')]}")
    # Lo negativo y lo mixto.
    fs_n = filas["v13"]
    n_prod, n_tema, robo, declarado, trampas, fuera_mal, sin_fila = [], [], [], collections.Counter(), [], [], []
    cn = collections.Counter()
    for cid, texto, e in CASOS:
        fs = fs_n[("neg100", cid)]
        for r in e["rubros"]:
            cn["rubro"] += 1
            cn["rubro bien"] += max(rubro_en(t, r)[1] for t in fs)
        for alt in e["temas"]:
            cn["tema"] += 1
            cn["tema bien"] += any(l in alt for t in fs for _, l in orden(t, tema)[:3])
        for w in e["no_vende"]:
            mias = _filas_con(w, fs)
            if not mias:
                sin_fila.append((cid, w))
                continue
            t = mias[0]
            o = orden(t, prod)
            n_prod.append(o[0][0])
            primero = orden(t, rub)[0][1]
            dice_no = primero.startswith(NR.NO_SE_VENDE)
            decl = any(_n(x) in _n(w) or _n(w) in _n(x) for x in json.load(open(os.path.join(NR._A.DATOS, NR.TID, "no_vendidas.json")))["no_vendidas"])
            declarado[("declarado" if decl else "no declarado", "no se vende primero" if dice_no else "un rubro primero")] += 1
            trampas.append((cid, w, o[0][1], o[0][0], primero))
            if o[0][1] in e["rubros"]:
                robo.append((cid, w, o[0][1]))
        for w in e["fuera"]:
            mias = _filas_con(w, fs)
            if not mias:
                sin_fila.append((cid, w))
                continue
            o = orden(mias[0], tema)
            n_tema.append(o[0][0])
            if o[0][1] not in e["tolera"]:
                fuera_mal.append((cid, w, o[0][1], o[0][0]))
    print(f"\nLOS 100 NEGATIVOS Y MIXTOS, v13 · rubro vendido {cn['rubro bien']} de {cn['rubro']} · tema de la FAQ {cn['tema bien']} de {cn['tema']}")
    print("  lo que no vende, el primero de los 3 rubros:", dict(declarado))
    print(f"  lo que no vende y su fila se queda con un producto del mismo mensaje: {len(robo)} {robo}")
    print(f"  sin fila propia, la palabra no quedo en ninguna fila: {sin_fila}")
    print("  lo que no vende, el primer producto que trae:")
    for x in trampas:
        print(f"    {x[0]:4} {x[1]:20} -> {x[2]:16} {x[3]:.3f}  rubros: {x[4]}")
    print(f"  fuera de la FAQ, el primer tema no es de los tolerados: {len(fuera_mal)} de {len(n_tema)}")
    for x in fuera_mal:
        print(f"    {x[0]:4} {x[1]:20} -> {x[2]:22} {x[3]:.3f}")

    def p(xs):
        xs = sorted(xs)
        return " ".join(f"p{q_}={xs[int(len(xs) * q_ / 100) - (1 if q_ == 100 else 0)]:.3f}" for q_ in (5, 10, 50, 90))
    print("\nLOS PUNTAJES, el coseno del mejor candidato")
    print(f"  producto correcto, las 200 · {p(p_prod)}  ({len(p_prod)})")
    print(f"  primer producto de lo que no vende · {p(n_prod)}  ({len(n_prod)})")
    print(f"  tema correcto, las 200 · {p(p_tema)}  ({len(p_tema)})")
    print(f"  primer tema de lo que la FAQ no cubre · {p(n_tema)}  ({len(n_tema)})")
    corte = sorted(p_prod)[int(len(p_prod) * .05)]
    print(f"  lo que no vende con puntaje sobre el p5 de los correctos, {corte:.3f}: {sum(x >= corte for x in n_prod)} de {len(n_prod)}")
    corte = sorted(p_tema)[int(len(p_tema) * .05)] if p_tema else 1
    print(f"  lo fuera de la FAQ con puntaje sobre el p5 de los temas correctos, {corte:.3f}: {sum(x >= corte for x in n_tema)} de {len(n_tema)}")


if __name__ == "__main__":
    negativos() if "--negativos" in sys.argv else main()
