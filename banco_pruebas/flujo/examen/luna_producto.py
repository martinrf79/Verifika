"""LUNA COPIA APARTE LO PEDIDO (25-nov-2026). Ver el plan 5 de lab/plan.md.

El prompt v14f1b de hoy, igual, mas un parrafo: en cada fila, `lo_pedido` copia tal cual las palabras con que el cliente
nombra lo que pide. Se mide si la copia es literal, la capa existe y la capa producto con eso, y la latencia.

    python3 examen/luna_producto.py 3          # tres, para ver que la entrada llega bien
    python3 examen/luna_producto.py            # las 97, retoma lo grabado
    python3 examen/luna_producto.py --informe  # sin gasto
"""
import collections, json, os, statistics, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(AQUI, "..", "lab"), os.path.join(AQUI, "..")]
_argv, sys.argv = sys.argv, ["x"]
import llamada0_modelos as L  # noqa: E402
sys.argv = _argv

SALIDA = os.path.join(AQUI, "luna_producto.jsonl")
TOPE = 0.10
PROMPT = "v14f1p"  # empieza con v14f1 para que `luna_ficha` le de la ficha f1
L.PROMPTS[PROMPT] = L.PROMPTS["v14f1b"] + """

ADEMAS, en cada fila, en lo_pedido: copia tal cual, sin corregir ni agregar nada, las palabras del mensaje con que el
cliente nombra lo que pide en esa fila, con sus caracteristicas, marca y modelo. Sin el destino, la forma de pago, nombres
de personas ni preguntas de envio. Si la fila no pide ni pregunta por un producto, lo_pedido va vacio."""
L.ESQUEMAS[PROMPT] = {"type": "object", "additionalProperties": False, "required": ["filas"], "properties": {
    "filas": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                         "required": ["texto", "lo_pedido"],
                                         "properties": {"texto": {"type": "string"}, "lo_pedido": {"type": "string"}}}}}}


def grabado():
    return {json.loads(x)["id"]: json.loads(x) for x in open(SALIDA)} if os.path.exists(SALIDA) else {}


def ids():
    return [json.loads(x)["id"] for x in open(os.path.join(AQUI, "luna_conceptos.jsonl"))]


def informe():
    import existe as E
    import busqueda as B
    X = E.X
    ex = {e["id"]: e for e in json.load(open(os.path.join(AQUI, "examen.json"), encoding="utf-8"))}
    g = grabado()
    n, fallas = collections.Counter(), []
    filas = []
    for i, r in g.items():
        e = ex[i]
        fs = [f for f in ((r["salida"] or {}).get("filas") or []) if f.get("lo_pedido", "").strip()]
        n["frases"] += 1
        for f in fs:
            lp = f["lo_pedido"].strip()
            n["filas con producto"] += 1
            # Si el cliente lo dijo en partes, Luna las junta con coma: cada parte tiene que estar literal.
            literal = all(x.strip().lower() in e["texto"].lower() for x in lp.split(",") if x.strip())
            n["copia literal" if literal else "copia no literal"] += 1
            if not literal:
                fallas.append(f"    copia {i:11} {lp[:60]!r}")
            filas.append((i, e, lp))
    print(f"frases {n['frases']}, filas con producto {n['filas con producto']}: copia literal {n['copia literal']},"
          f" no literal {n['copia no literal']}")
    # capa existe, contado por frase como la medida con la fila entera
    m = collections.Counter()
    for i, e, lp in filas:
        v, raz = E.existe(lp, aislado=True)
        todos_no = all(("no_hay" in p["esperados"]) and not X.aceptables(p) for p in e["pedidos"])
        k = ("no hay bien" if v == "no_hay" else "no hay perdido") if todos_no else ("falsa alarma" if v == "no_hay" else "hay bien")
        m[k] += 1
        if k in ("falsa alarma", "no hay perdido"):
            fallas.append(f"    existe {k:14} {i:11} {lp[:55]!r} {v} {raz}")
    print(f"  capa existe con lo_pedido aislado: no hay bien {m['no hay bien']}, perdido {m['no hay perdido']};"
          f" hay bien {m['hay bien']}, falsa alarma {m['falsa alarma']}")
    # capa producto, en las frases de un pedido con aceptables y sin orden
    lim = [(i, e, lp) for i, e, lp in filas if len(e["pedidos"]) == 1 and X.aceptables(e["pedidos"][0])
           and not any(c["tipo"] == "orden" for c in e["pedidos"][0]["cas"])]
    primeras = {}
    for i, e, lp in lim:
        primeras.setdefault(i, (e, lp))
    v = B.vectores([(lp, "RETRIEVAL_QUERY") for e, lp in primeras.values()])
    ia = B.indice_a()
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))
    ok = 0
    for i, (e, lp) in primeras.items():
        top = max(ia, key=lambda k: dot(v[(lp, "RETRIEVAL_QUERY")], ia[k]))
        ok += top in set(X.aceptables(e["pedidos"][0]))
        if top not in set(X.aceptables(e["pedidos"][0])):
            fallas.append(f"    producto {i:11} {lp[:55]!r} -> {top[2]}")
    print(f"  capa producto con lo_pedido: el primero sirve en {ok} de {len(primeras)} frases de un pedido sin orden")
    s = sorted(r["seg_luna"] for r in g.values())
    print(f"  Luna: mediana {statistics.median(s):.1f} s, p90 {s[int(len(s) * .9) - 1]:.1f};"
          f" tokens medios entrada {statistics.mean(r['entrada'] for r in g.values()):.0f},"
          f" salida {statistics.mean(r['salida_tokens'] for r in g.values()):.0f};"
          f" gasto {sum(r['dolares'] for r in g.values()):.3f} dolares")
    if "--ver" in sys.argv:
        for x in fallas:
            print(x)


if __name__ == "__main__":
    if "--informe" in sys.argv:
        informe()
        sys.exit()
    ex = {e["id"]: e for e in json.load(open(os.path.join(AQUI, "examen.json"), encoding="utf-8"))}
    todos = ids()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else len(todos)
    for i in todos[:n]:
        if i in grabado():
            continue
        if sum(r["dolares"] for r in grabado().values()) >= TOPE:
            raise SystemExit(f"tope de {TOPE} dolares de la corrida")
        salida, ent, sal, seg, dol, crudo = L.pedir("luna", PROMPT, ex[i]["texto"])
        with open(SALIDA, "a") as f:
            f.write(json.dumps({"id": i, "salida": salida, "crudo": None if salida else crudo, "entrada": ent,
                                "salida_tokens": sal, "seg_luna": seg, "dolares": dol}, ensure_ascii=False) + "\n")
        print(i, seg, ent, sal, flush=True)
