"""EL v14f1b DE ANTES CONTRA EL v14f1p DE AYER, en las 300 primeras, contra la etiqueta (26-nov-2026, pedido de Martin).

Martin vio la separacion de ayer peor que la de antes. El v14f1p es el v14f1b mas el parrafo de lo pedido, y cambia la
salida: de una lista de textos a filas con texto y lo pedido. Se mide como `luna_ficha.py`, por corchetes:
  rubros     de los pedidos etiquetados con rubro, cuantos quedan entre corchetes en alguna fila
  de mas     rubros entre corchetes que ningun pedido de la frase pide
  no vende   pedidos que solo valen no hay con algun rubro entre corchetes: lo metio en un producto de la tienda
  filas      filas de mas o de menos contra los pedidos de producto etiquetados
Y aparte, solo el v14f1p, lo pedido: si nombra el rubro o el modelo del pedido.

    python3 primeros/comparar.py [--ver]
"""
import collections, json, os, re, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(AQUI, "..", "examen"), os.path.join(AQUI, "..", "conceptos")]
sys.dont_write_bytecode = True
import examen as X  # noqa: E402

ALIAS = json.load(open(os.path.join(AQUI, "..", "..", "..", "data", "clientes", "verifika_prod", "alias.json")))["rubros"]
nrm = X.nrm


def textos(r):
    s = r["salida"] or {}
    return [f["texto"] for f in s.get("filas") or []] if "filas" in s else [str(t) for t in s.get("textos") or []]


def corchetes(ts):
    return {nrm(c) for t in ts for c in re.findall(r"\[([^\]]+)\]", t)}


def medir(nombre, archivo, ex, ver):
    g = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(AQUI, archivo))}
    n, malas = collections.Counter(), []
    for e in ex:
        ts = textos(g[e["id"]])
        cs = corchetes(ts)
        pedidos_rubro = set()
        prod = 0
        for p in e["pedidos"]:
            rs = {X.CONC[i]["nombre"] for c in p["cas"] if c["tipo"] == "rubro" for i in X._ids(c)}
            if set(p["esperados"]) == {"no_hay"}:
                n["no vende"] += 1
                if any(c["tipo"] == "fuera" and c["valor"] == "no_vende" for c in p["cas"]) and cs & set(ALIAS):
                    n["no vende metido en un rubro"] += 1
                    malas.append(f"{e['id']} no vende en rubro {sorted(cs & set(ALIAS))} {e['texto'][:60]!r}")
            if rs:
                prod += 1
                n["pedidos con rubro"] += 1
                pedidos_rubro |= rs
                if rs & cs:
                    n["rubro entre corchetes"] += 1
                else:
                    malas.append(f"{e['id']} falta {sorted(rs)} {e['texto'][:60]!r} -> {[t[:70] for t in ts]}")
        de_mas = (cs & set(ALIAS)) - pedidos_rubro
        if de_mas:
            n["frases con rubro de mas"] += 1
            malas.append(f"{e['id']} de mas {sorted(de_mas)} {e['texto'][:60]!r}")
        n["filas"] += len(ts)
        n["frases con mas filas que pedidos de producto"] += len(ts) > max(prod, 1)
    seg = sorted(r["seg_luna"] for r in g.values())
    print(f"{nombre}: rubro pedido entre corchetes {n['rubro entre corchetes']} de {n['pedidos con rubro']};"
          f" frases con rubro de mas {n['frases con rubro de mas']}; no vende metido en un rubro"
          f" {n['no vende metido en un rubro']} de {n['no vende']}; filas {n['filas']}, frases con filas de mas"
          f" {n['frases con mas filas que pedidos de producto']}; mediana {seg[len(seg) // 2]:.1f} s,"
          f" gasto {sum(r['dolares'] for r in g.values()):.3f}")
    if ver:
        for m in malas:
            print("   ", m)
    return {m.split()[0] + m.split()[1] for m in malas}


if __name__ == "__main__":
    ex = json.load(open(os.path.join(AQUI, "examen.json")))
    a = medir("v14f1b de antes", "luna_b.jsonl", ex, "--ver" in sys.argv)
    b = medir("v14f1p de ayer", "luna.jsonl", ex, "--ver" in sys.argv)
    print(f"fallas solo del de antes {len(a - b)}, solo del de ayer {len(b - a)}, de los dos {len(a & b)}")
