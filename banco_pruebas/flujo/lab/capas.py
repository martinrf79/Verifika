"""LAS CAPAS CON LA ENTRADA PERFECTA: PRODUCTO, EXISTE Y DATO 2 (25-nov-2026). Ver el plan 3 de lab/plan.md.

La entrada de cada pedido sale de `examen/tramos.py`. Sin modelo; embeddings con la clave gratis, guardados en lab/.

    python3 lab/capas.py          # las tres medidas
    python3 lab/capas.py --ver    # ademas, cada falla
"""
import collections, json, os, re, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
_argv, sys.argv = sys.argv, ["x"]
import busqueda as B  # noqa: E402
import tramos as TR  # noqa: E402
import jev_filas as JF  # noqa: E402
from app.core.flujo.nuevo.rubro import etiquetas  # noqa: E402
sys.argv = _argv

X, F, NR = B.X, B.F, B.NR
Q, D = "RETRIEVAL_QUERY", "RETRIEVAL_DOCUMENT"
VER = "--ver" in sys.argv

# Medida 3: un documento por opcion generica del dato 2, escrito el 25-nov antes de medir. No se toca despues.
GENERICOS = {
    "ofrecer": "que productos tienen, busco, mostrame opciones, que me recomendas",
    "precio": "cuanto sale, cuanto cuesta, dame el precio",
    "stock": "lo tienen, hay disponible, esta en stock",
    "comprar": "lo quiero comprar, agregalo al pedido, sumalo, me lo llevo",
    "caracteristicas": "que caracteristicas tiene, la descripcion completa, la ficha tecnica",
    "comparar": "que diferencia hay, cual es mejor, cual me conviene entre estos",
    "compat": "si es compatible, si anda con, si sirve para conectarlo a",
}


def pedidos():
    """[(id, frase, j, pedido, tramos, consulta, dato2, consulta del dato 2)]."""
    out = []
    for e in json.load(open(os.path.join(B.FL, "examen", "examen.json"), encoding="utf-8")):
        t = TR.T[e["id"]]
        for j, p in enumerate(e["pedidos"]):
            trs, d2 = t["p"][j]
            q2 = " ".join(tr for tr, tipo, ap in t.get("g", []) if tipo == "dato2" and j in ap) or " ".join(trs)
            out.append((e["id"], e, j, p, trs, TR.consulta(e["texto"], t, j), d2, q2))
    return out


def opciones():
    sp = json.load(open(os.path.join(TR.DATOS, "specs_preguntables.json"), encoding="utf-8"))["specs"]
    out = dict(GENERICOS)
    for s in sp:
        out["campo:" + s["id"]] = f"{s['etiqueta']}: {', '.join(s['claves'])}"
    return out


# Medida 2, E2: los codigos de modelo que la tienda no tiene.
UNIDAD = r"(gb|tb|gigas?|teras?|w|hz|mhz|pulgadas|mil|lucas|pesos|metros|m|meses|anos|años|k|mm|cm|%|unidades)"


def vocabulario():
    vs = set()
    for k, fs in B.MODELOS.items():
        for x in [k[0], k[1], k[2]] + [f["nombre"] for f in fs] + etiquetas(fs):
            vs |= set(re.findall(r"[a-z0-9]+", F.nrm(x)))
    for r, al in B.ALIAS.items():
        for x in [r] + al:
            vs |= set(re.findall(r"[a-z0-9]+", F.nrm(x)))
    return vs


VOC = None


def codigos_ajenos(texto):
    global VOC
    if VOC is None:
        VOC = vocabulario()
    s = F.nrm(texto)
    out = []
    for m in re.finditer(r"[a-z0-9]+", s):
        w = m.group(0)
        if not re.search(r"\d", w):
            continue
        sigue = s[m.end():m.end() + 12].strip()
        if re.fullmatch(r"\d+" + UNIDAD, w) or re.match(UNIDAD + r"\b", sigue):
            continue
        if w.isdigit() and (len(w) < 3 or len(w) >= 5):
            continue
        if w not in VOC:
            out.append(w)
    return out


def main():
    ps = pedidos()
    op = opciones()
    pedido = [(c, Q) for *_, c, _, _ in ps] + [(q2, Q) for *_, q2 in ps if q2] + [(t, D) for t in op.values()]
    pedido += [(B.doc_b(k), D) for k in B.KS]
    v = B.vectores(pedido)
    ia = B.indice_a()
    ib = {k: v[(B.doc_b(k), D)] for k in B.KS}
    FU = JF._fuente()
    rub = FU.rub
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))

    # Medida 1
    print("MEDIDA 1, capa producto, con el tramo de cada pedido")
    for nom, idx in (("documento A", ia), ("documento B", ib)):
        n = collections.Counter()
        for i, e, j, p, trs, c, d2, q2 in ps:
            ac = set(X.aceptables(p))
            if not ac:
                continue
            orden = any(x["tipo"] == "orden" for x in p["cas"])
            g = "con orden" if orden else "sin orden"
            l = sorted(idx, key=lambda k: -dot(v[(c, Q)], idx[k]))[:15]
            n[g] += 1
            n[g + " primero"] += l[0] in ac
            n[g + " entre 15"] += any(k in ac for k in l)
            n[g + " en 5"] += sum(k in ac for k in l[:5])
            n[g + " posibles en 5"] += min(5, len(ac))
            if VER and not orden and l[0] not in ac and nom == "documento B":
                print(f"    {i:11} p{j} {c[:60]!r} -> {l[0][2]}")
        for g in ("sin orden", "con orden"):
            print(f"  {nom}, {g}: {n[g]} pedidos; el primero sirve en {n[g + ' primero']}, alguno entre 15 en"
                  f" {n[g + ' entre 15']}; aceptables en los 5 primeros {n[g + ' en 5']} de {n[g + ' posibles en 5']}")

    # Medida 2
    print("\nMEDIDA 2, capa existe")
    forma = {
        "E1 indice de rubros": lambda c: sorted(rub, key=lambda r: -dot(v[(c, Q)], r[1]))[0][0].startswith(NR.NO_SE_VENDE),
        "E2 codigos ajenos": lambda c: bool(codigos_ajenos(c)),
    }
    forma["E3, E1 o E2"] = lambda c: forma["E1 indice de rubros"](c) or forma["E2 codigos ajenos"](c)
    for nom, f in forma.items():
        n, fallas = collections.Counter(), []
        for i, e, j, p, trs, c, d2, q2 in ps:
            hay = bool(X.aceptables(p))
            espera_no = "no_hay" in p["esperados"] and not hay
            if not hay and not espera_no:
                continue
            dice_no = f(c)
            if espera_no:
                n["no hay bien" if dice_no else "no hay perdido, alucina"] += 1
            else:
                n["falsa alarma, pierde venta" if dice_no else "hay bien"] += 1
            if VER and (dice_no != espera_no):
                fallas.append(f"    {'perdido' if espera_no else 'alarma'} {i} p{j} {c[:60]!r} {codigos_ajenos(c)}")
        print(f"  {nom}: no hay bien {n['no hay bien']}, no hay perdido {n['no hay perdido, alucina']};"
              f" hay bien {n['hay bien']}, falsa alarma {n['falsa alarma, pierde venta']}")
        for x in fallas:
            print(x)

    # Medida 3
    print("\nMEDIDA 3, capa dato 2")
    n, fallas = collections.Counter(), []
    for i, e, j, p, trs, c, d2, q2 in ps:
        if not q2 or d2 == ["fuera"]:
            continue
        orden = sorted(op, key=lambda o: -dot(v[(q2, Q)], v[(op[o], D)]))
        campo = any(d.startswith("campo:") for d in d2)
        g = "campos de la ficha" if campo else "genericos"
        n[g] += 1
        n[g + " bien"] += orden[0] in d2
        n[g + " entre 3"] += any(o in d2 for o in orden[:3])
        if orden[0] not in d2:
            fallas.append(f"    {i:11} p{j} {q2[:50]!r} etiqueta {d2} -> {orden[:3]}")
    for g in ("genericos", "campos de la ficha"):
        print(f"  {g}: {n[g]} pedidos; la primera opcion bien en {n[g + ' bien']}, entre las 3 primeras en {n[g + ' entre 3']}")
    if VER:
        for x in fallas:
            print(x)


if __name__ == "__main__":
    main()
