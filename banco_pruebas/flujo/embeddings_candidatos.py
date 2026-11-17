"""CUANTOS CANDIDATOS HACEN FALTA PARA QUE LOS EMBEDDINGS TRAIGAN EL CORRECTO, CON LAS PALABRAS DEL CLIENTE (16-nov-2026).

Pregunta de Martin del 16-nov, despues de comparar modelos en la llamada 0: lo que fallan todos es la jerga sin traducir,
"plaqueta madre", "pantallita tactil". La estrategia que propone: los embeddings de lo que dijo el cliente traen 8 o 10
candidatos, y el modelo elige entre ellos y lo que sabe. Sirve si el correcto esta entre los primeros k. Esto lo mide,
sin modelo, antes de decidir.

LA VARA, escrita antes de correr. Por cada cosa de las 140 que la tienda vende, con su rubro esperado de `nuevas70` y
`nuevas70b`, la linea de la llamada 0 de produccion con el prompt v2 cuyo fragmento trae una de sus raices. Tres consultas:
  fragmento   las palabras del cliente, tal cual las copio el modelo: la estrategia de Martin.
  busqueda    lo que tradujo el modelo: lo de hoy.
  las dos     el fragmento y la busqueda juntos.
Contra dos indices, los mismos documentos de `nexo_rubro`:
  productos   cada modelo de la tienda con los alias de su rubro y sus etiquetas. Acierta en k si alguno de los k
              primeros es del rubro esperado.
  rubros      cada rubro con sus alias, mas lo que la tienda declara que no vende.
Se cuenta en k = 1, 3, 5, 8, 10, 15 y 20. Lo que la tienda no vende no entra: es otra pregunta.

    python3 banco_pruebas/flujo/embeddings_candidatos.py [--ver]   # pide los vectores que falten con la gratis
    MARTIN_AUTORIZO_LA_PAGA=<fecha> python3 banco_pruebas/flujo/embeddings_candidatos.py   # si la gratis se traba
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entorno import GRABADO  # noqa: E402

import embeddings as EMB  # noqa: E402
import engranaje0 as E  # noqa: E402
import flujo_nuevo as F  # noqa: E402
import nexo_rubro as NR  # noqa: E402

# Los vectores pesan megas: en el cache de la sesion, `embeddings.py`. En el repo quedan los rangos.
RANGOS = os.path.join(GRABADO, "embeddings_candidatos_rangos.json")
KS = (1, 3, 5, 8, 10, 15, 20)
CORRIDA = ("gemini-lite", "v2")


def cosas(corrida=CORRIDA):
    """[(id, rubro esperado, fragmento, busqueda)] de las 140, con la llamada 0 de esa corrida."""
    import llamada0_modelos as L
    l0 = L.corridas()[corrida]
    out = []
    for _, cid, _, cs, _ in F.bancos():
        lineas = (l0.get(cid) or {}).get("salida", {}).get("lineas", [])
        for raices, rubro in cs:
            if rubro in (None, "ninguno"):
                continue
            l = next((l for l in lineas if any(E.n(r) in E.n(l.get("fragmento")) for r in raices)), None) or \
                next((l for l in lineas if any(E.n(r) in E.n(l.get("busqueda")) for r in raices)), None)
            out.append((cid, rubro, str(l["fragmento"]) if l else "", str(l["busqueda"]) if l else ""))
    return out


def vectores(textos, tarea, cache):
    EMB.pedir([t for t in textos if t], tarea, cache)


def medir():
    _, alias, rubros, modelos = NR.fuente()
    ms = list(modelos)
    docs_p = [NR.doc_producto(k, modelos[k], alias) for k in ms]
    ir = NR.indice_rubros(rubros, alias)
    docs_r = [d for _, d in ir]
    cs = cosas()
    consultas = {"fragmento": [c[2] for c in cs], "busqueda": [c[3] for c in cs],
                 "las dos": [f"{c[2]}. {c[3]}" if c[2] and c[3] else c[2] or c[3] for c in cs]}
    cache = EMB.cargar()
    vectores(docs_p + docs_r, "RETRIEVAL_DOCUMENT", cache)
    vectores([q for qs in consultas.values() for q in qs], "RETRIEVAL_QUERY", cache)
    vp = [cache[f"RETRIEVAL_DOCUMENT|{d}"] for d in docs_p]
    vr = [cache[f"RETRIEVAL_DOCUMENT|{d}"] for d in docs_r]

    def dot(a, b):
        return sum(x * y for x, y in zip(a, b))
    rangos = []
    for j, (cid, rubro, frag, busq) in enumerate(cs):
        fila = {"id": cid, "rubro": rubro, "texto": frag, "traduccion": busq}
        for tipo, qs in consultas.items():
            q = qs[j]
            if not q:
                fila[tipo] = {"producto": None, "rubro": None}
                continue
            x = cache[f"RETRIEVAL_QUERY|{q}"]
            orden_p = sorted(range(len(ms)), key=lambda i: -dot(x, vp[i]))
            orden_r = sorted(range(len(ir)), key=lambda i: -dot(x, vr[i]))
            fila[tipo] = {"producto": next((p + 1 for p, i in enumerate(orden_p) if ms[i][0] == rubro), None),
                          "rubro": next((p + 1 for p, i in enumerate(orden_r) if ir[i][0] == rubro), None),
                          "primero": f"{ms[orden_p[0]][0]} {ms[orden_p[0]][1]} {ms[orden_p[0]][2]}"}
        rangos.append(fila)
    json.dump(rangos, open(RANGOS, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return rangos


def informe(rangos, ver=False):
    n = len(rangos)
    print(f"\nCUANTOS CANDIDATOS HACEN FALTA · {n} cosas que la tienda vende, de las 140, llamada 0 {' '.join(CORRIDA)}")
    print(f"  {'consulta':10} {'indice':10} " + " ".join(f"{'k=' + str(k):>6}" for k in KS))
    for tipo in ("fragmento", "busqueda", "las dos"):
        for indice in ("producto", "rubro"):
            rs = [r[tipo][indice] for r in rangos]
            print(f"  {tipo:10} {indice:10} " + " ".join(f"{sum(1 for x in rs if x and x <= k):>6}" for k in KS))
    print("\n  donde la busqueda traducida no trae primero el rubro: rango en productos de fragmento, busqueda y las dos")
    for r in rangos:
        if (r["busqueda"]["producto"] or 99) > 1 or ver:
            rk = " ".join(f"{str(r[t]['producto']):>4}" for t in ("fragmento", "busqueda", "las dos"))
            print(f"    {r['id']:4} {r['rubro'][:16]:16} {rk}  {r['texto'][:40]!r} / {r['traduccion'][:32]!r}")


# ══ LOS 40 REALES Y LAS 365, POR MENSAJE Y RUBRO (16-nov) ═════════════════════
# Pedido de Martin: con la llamada 0 que repite la condicion en cada linea, si cada linea llega al producto. Por cada
# rubro que el mensaje pide, `reales.py`, el mejor rango entre sus lineas del primer producto de ese rubro.
def medir_reales(corridas=(("gemini-lite", "v1"), ("luna", "v2"))):
    import llamada0_modelos as L
    import reales as RE
    _, alias, rubros, modelos = NR.fuente()
    ms = list(modelos)
    docs_p = [NR.doc_producto(k, modelos[k], alias) for k in ms]
    cache = EMB.cargar()
    vectores(docs_p, "RETRIEVAL_DOCUMENT", cache)
    vp = [cache[f"RETRIEVAL_DOCUMENT|{d}"] for d in docs_p]
    esperado = {c[0]: c[2].get("rubros", set()) for c in RE.CASOS}
    esperado.update({c[0]: c[2]["rubros"] for c in RE.casos_525()[0]})
    out = {}
    for banco in ("reales", "reales525"):
        cs = L.corridas_reales(banco)
        for corrida in corridas:
            rs = cs[corrida]
            qs = {}
            for cid, r in rs.items():
                for l in (r.get("salida") or {}).get("lineas", []):
                    f, b = str(l.get("fragmento") or ""), str(l.get("busqueda") or "")
                    if b:
                        qs[(cid, b)] = {"fragmento": f, "busqueda": b, "las dos": f"{f}. {b}" if f else b}
            vectores([q for d in qs.values() for q in d.values() if q], "RETRIEVAL_QUERY", cache)
            filas = []
            for cid, rubs in esperado.items():
                if cid not in rs or not rubs or not ((cid.startswith("R") and banco == "reales") or
                                                     ("." in cid and banco == "reales525")):
                    continue
                for rubro in rubs:
                    fila = {"id": cid, "rubro": rubro}
                    for tipo in ("fragmento", "busqueda", "las dos"):
                        rangos = []
                        for (c2, _), d in qs.items():
                            if c2 != cid or not d[tipo]:
                                continue
                            x = cache[f"RETRIEVAL_QUERY|{d[tipo]}"]
                            orden = sorted(range(len(ms)), key=lambda i: -sum(a * b for a, b in zip(x, vp[i])))
                            rangos.append(next(p + 1 for p, i in enumerate(orden) if ms[i][0] == rubro))
                        fila[tipo] = min(rangos) if rangos else None
                    filas.append(fila)
            out[f"{banco} {' '.join(corrida)}"] = filas
    json.dump(out, open(RANGOS.replace(".json", "_reales.json"), "w", encoding="utf-8"), ensure_ascii=False)
    for nombre, filas in out.items():
        print(f"\n{nombre}: {len(filas)} rubros pedidos; entre los k primeros de alguna de sus lineas")
        print(f"  {'consulta':10} " + " ".join(f"{'k=' + str(k):>6}" for k in KS) + f" {'sin linea':>10}")
        for tipo in ("fragmento", "busqueda", "las dos"):
            rs_ = [f[tipo] for f in filas]
            print(f"  {tipo:10} " + " ".join(f"{sum(1 for x in rs_ if x and x <= k):>6}" for k in KS)
                  + f" {sum(1 for x in rs_ if x is None):>10}")


# ══ LA BUSQUEDA CERO: LA TRADUCCION DE LUNA CONTRA LOS CANDIDATOS DEL FRAGMENTO (17-nov) ══════════════════════════════
# Orden de Martin del 17-nov, antes de tocar el prompt: los embeddings buscan sobre el fragmento que separo la llamada 0,
# las palabras del cliente, y traen 8 productos; la traduccion de Luna, la busqueda, da su rubro por su cuenta. Una funcion
# de codigo cruza las dos. Tres casos por linea:
#   1 coincide     el rubro de la traduccion esta entre los rubros de los 8 candidatos del fragmento.
#   2 distinto     tradujo, y su rubro no esta entre los candidatos.
#   3 tal cual     no tradujo: las palabras de la busqueda son todas del fragmento.
# Por cada caso, quien tiene razon contra la vara: la traduccion, el primer candidato del fragmento o el de los dos juntos.
# La vara: en las 140, el rubro de cada cosa de `nuevas70`; en los reales y las 365, los rubros del mensaje, y una linea de
# un mensaje que pide algo que la tienda no vende, que cae fuera de esos rubros, no se cuenta.
TRES = os.path.join(GRABADO, "busqueda_cero_luna.json")
K0 = 8


def _palabras(t):
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in E.n(t).split()}


def lineas_luna(corrida=("luna", "v2")):
    """[(banco, id, fragmento, busqueda, rubros que valen, hay algo que no vende)] con esa corrida de la llamada 0."""
    import llamada0_modelos as L
    import reales as RE
    out = [("140", cid, f, b, {r}, False) for cid, r, f, b in cosas(corrida) if b]
    esperado = {c[0]: (set(c[2].get("rubros", ())), bool(c[2].get("no_vende"))) for c in RE.CASOS}
    esperado.update({c[0]: (set(c[2]["rubros"]), bool(c[2].get("no_vende"))) for c in RE.casos_525()[0]})
    for banco in ("reales", "reales525"):
        for cid, r in L.corridas_reales(banco)[corrida].items():
            rubs, nv = esperado.get(cid, (set(), False))
            if not rubs or (banco == "reales") != cid.startswith("R"):
                continue
            for l in (r.get("salida") or {}).get("lineas", []):
                f, b = str(l.get("fragmento") or ""), str(l.get("busqueda") or "")
                if b:
                    out.append((banco, cid, f, b, rubs, nv))
    return out


def tres_casos(prompt="v2"):
    _, alias, rubros, modelos = NR.fuente()
    ms = list(modelos)
    docs_p = [NR.doc_producto(k, modelos[k], alias) for k in ms]
    ir = NR.indice_rubros(rubros, alias)
    ls = lineas_luna(("luna", prompt))
    cache = EMB.cargar()
    vectores(docs_p + [d for _, d in ir], "RETRIEVAL_DOCUMENT", cache)
    vectores(sorted({q for _, _, f, b, _, _ in ls for q in (f, b, f"{f}. {b}" if f else b)}), "RETRIEVAL_QUERY", cache)
    vp = [cache[f"RETRIEVAL_DOCUMENT|{d}"] for d in docs_p]
    vr = [cache[f"RETRIEVAL_DOCUMENT|{d}"] for _, d in ir]

    def orden(q, vs):
        x = cache[f"RETRIEVAL_QUERY|{q}"]
        return sorted(range(len(vs)), key=lambda i: -sum(a * c for a, c in zip(x, vs[i])))
    filas, c = [], collections.defaultdict(collections.Counter)
    for banco, cid, f, b, rubs, nv in ls:
        rt = ir[orden(b, vr)[0]][0]
        trad = "ninguno" if rt.startswith(NR.NO_SE_VENDE) else rt
        cand = [ms[i][0] for i in orden(f or b, vp)[:K0]]
        dos = ms[orden(f"{f}. {b}" if f else b, vp)[0]][0]
        caso = "3 tal cual" if _palabras(b) <= _palabras(f) else ("1 coincide" if trad in cand else "2 distinto")
        ok = {"traduccion": trad in rubs, "fragmento": cand[0] in rubs, "las dos": dos in rubs}
        if nv and not any(ok.values()):
            c[caso]["fuera: pide algo que no se vende"] += 1
            continue
        c[caso]["lineas"] += 1
        for k, v in ok.items():
            c[caso][f"acierta {k}"] += v
        c[caso]["ninguno acierta"] += not any(ok.values())
        filas.append({"banco": banco, "id": cid, "fragmento": f, "busqueda": b, "rubros": sorted(rubs), "caso": caso,
                      "traduccion": trad, "candidatos": cand, "las dos": dos, **{f"ok {k}": v for k, v in ok.items()}})
    json.dump(filas, open(TRES if prompt == "v2" else TRES.replace(".json", f"_{prompt}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    return filas, c


def informe_tres(filas, c, ver=False):
    print(f"\nLA BUSQUEDA CERO CON LA LLAMADA 0 ELEGIDA · {len(filas)} lineas de las 140, los reales y las 365 · "
          f"{K0} candidatos del fragmento")
    for caso in sorted(c):
        x = c[caso]
        print(f"  {caso:11} lineas {x['lineas']:4} · acierta la traduccion {x['acierta traduccion']:4} · el primer "
              f"candidato del fragmento {x['acierta fragmento']:4} · los dos juntos {x['acierta las dos']:4} · "
              f"ninguno {x['ninguno acierta']:3}" + (f" · fuera {x['fuera: pide algo que no se vende']}"
                                                   if x["fuera: pide algo que no se vende"] else ""))
    print("\n  LAS REGLAS, sobre esas lineas: bien, mal y repreguntas")
    reglas = {
        "A: 1 la traduccion, 2 repregunta, 3 el fragmento": lambda r: r["ok traduccion"] if r["caso"][0] == "1" else (
            None if r["caso"][0] == "2" else r["ok fragmento"]),
        "B: 1 la traduccion, 2 los dos juntos, 3 el fragmento": lambda r: r["ok traduccion"] if r["caso"][0] == "1"
        else (r["ok las dos"] if r["caso"][0] == "2" else r["ok fragmento"]),
        "C: 1 la traduccion, 2 y 3 los dos juntos": lambda r: r["ok traduccion"] if r["caso"][0] == "1" else r["ok las dos"],
        "D: hoy, la traduccion sola": lambda r: r["ok traduccion"],
        "E: los dos juntos siempre": lambda r: r["ok las dos"],
    }
    for nombre, f in reglas.items():
        rs = [f(r) for r in filas]
        print(f"    {nombre:52} bien {sum(1 for x in rs if x is True):4} · mal {sum(1 for x in rs if x is False):3} · "
              f"repregunta {sum(1 for x in rs if x is None):3}")
    for r in filas:
        if ver or r["caso"][0] != "1" or not r["ok traduccion"]:
            print(f"    {r['caso'][:1]} {r['banco']:9} {r['id']:20} {r['rubros']} trad {r['traduccion']}"
                  f"{'' if r['ok traduccion'] else ' X'} · frag {r['candidatos'][0]}{'' if r['ok fragmento'] else ' X'} "
                  f"· dos {r['las dos']}{'' if r['ok las dos'] else ' X'} · {r['fragmento'][:50]!r} / {r['busqueda'][:40]!r}")


if __name__ == "__main__":
    if "--tres-casos" in sys.argv:
        p_ = next((x for x in sys.argv[2:] if x.startswith("v")), "v2")
        informe_tres(*tres_casos(p_), "--ver" in sys.argv)
        sys.exit()
    if "--reales" in sys.argv:
        medir_reales()
        sys.exit()
    if "--informe" in sys.argv:
        informe(json.load(open(RANGOS, encoding="utf-8")), "--ver" in sys.argv)
    else:
        informe(medir(), "--ver" in sys.argv)
