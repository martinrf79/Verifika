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


if __name__ == "__main__":
    main()
