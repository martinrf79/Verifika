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


def cosas():
    """[(id, rubro esperado, fragmento, busqueda)] de las 140, con la llamada 0 de produccion y el prompt v2."""
    import llamada0_modelos as L
    l0 = L.corridas()[CORRIDA]
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


if __name__ == "__main__":
    if "--reales" in sys.argv:
        medir_reales()
        sys.exit()
    if "--informe" in sys.argv:
        informe(json.load(open(RANGOS, encoding="utf-8")), "--ver" in sys.argv)
    else:
        informe(medir(), "--ver" in sys.argv)
