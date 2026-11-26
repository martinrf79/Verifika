"""LO QUE DICE ALGO FALSO, POR MENSAJE (26-nov-2026). FICHA 110.

Por mensaje, con la rueda y la capa de condicion: dice algo falso, contesta todo bien, o no contesta algo y
repregunta.

    python3 primeros/falsos.py [--examen|--reales|--muestras]

Falso: ofrece un producto que no sirve, ofrece cuando no hay, dice no hay cuando hay, o da como el mas
barato uno que no lo es. Repregunta: lo que la cadena no ofrece por no reconocer el producto."""
import collections, os, sys
FL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
os.chdir(FL)
conj = sys.argv[1] if len(sys.argv) > 1 else ""
sys.argv = ["x"] + ([conj] if conj else [])
sys.path[:0] = [os.path.join(FL, "primeros")]
sys.dont_write_bytecode = True
import condicion as K
C, nrm, F = K.C, K.nrm, K.F

ex, luna = C.cargar()
ps = {e["id"]: K.pedidos((luna[e["id"]]["salida"] or {}).get("textos") or []) for e in ex}
v = C.B.vectores([(f["consulta"], "RETRIEVAL_QUERY") for fs in ps.values() for f in fs])
ia = C.B.indice_a()
dot = lambda a, b: sum(x * y for x, y in zip(a, b))
FALSO = {"oferta equivocada", "no hay perdido", "falsa alarma de existe", "sirve, mal ordenado", "nada cumple de mas"}
tot = collections.Counter()
for e in ex:
    res, vistos = [], set()
    for f in ps[e["id"]]:
        clave = (f["rubro"], nrm(f["consulta"]), tuple(sorted(str(d.get("orden")) for d in f["atadas"])))
        if clave in vistos:
            continue
        vistos.add(clave)
        q = v[(f["consulta"], "RETRIEVAL_QUERY")]
        orden = any(d["tipo"] == "orden" for d in f["atadas"])
        if f["rubro"]:
            pool = [k for k in ia if nrm(k[0]) == f["rubro"]] or list(ia)
        elif f["identifica"] or (orden and K.TODA.search(nrm(f["consulta"]))):
            pool = list(ia)
        else:
            res.append((f["consulta"], "sin rubro", []))
            continue
        vr, _ = C.EX.existe(f["nombre"] or f["consulta"], aislado=True)
        vr = "no_hay" if vr == "no_hay" else "hay"
        pool = sorted(pool, key=lambda k: -dot(q, ia[k]))
        if vr != "no_hay":
            primero = pool[0]
            vr2, pool, _ = K.resolver(f["atadas"], pool)
            vr = "nada cumple" if vr2 == "nada cumple" else vr
            nombrado = any(n == "modelo" for _, n in f["partes"]) or any(d["tipo"] == "modelo" for d in f["atadas"])
            if nombrado and vr2 == "ofrece" and primero not in pool:
                vr, pool = "nada cumple", [primero] + pool
        res.append((f["consulta"], vr, pool[:5]))
    n, fallas = collections.Counter(), []
    K.contar(e, res, n, fallas)
    ks = {k for (_, _, k) in n}
    tot["mensajes"] += 1
    if ks & FALSO:
        tot["dice algo falso"] += 1
    elif {"no lo trae", "entre los 5"} & ks:
        tot["no contesta algo, repregunta"] += 1
    else:
        tot["todo bien"] += 1
    tot["pedidos"] += sum(c for (a, _, _), c in n.items() if a in ("ofrecer", "no hay"))
    tot["pedidos con algo falso"] += sum(c for (a, _, k), c in n.items() if a != "fila" and k in FALSO)
    tot["filas que ofrecen"] += n[("fila", "", "ofrece")]
    tot["ofertas equivocadas"] += n[("fila", "", "oferta equivocada")]
print(conj or "--sinteticas", dict(tot))
