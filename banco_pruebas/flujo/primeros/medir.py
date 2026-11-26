"""LA MEDIDA DE LOS PRIMEROS MENSAJES NUEVOS: capas 0, 1 y 2 encadenadas, contra la etiqueta (25-nov-2026). FICHA 108.

Entrada: lo que separo Luna, `luna.jsonl`, con `lo_pedido` por fila; la etiqueta congelada, `examen.json`.
Por fila de Luna con lo pedido: la funcion de existe, y si dice hay, el primero de la busqueda.

Se cuenta, con el criterio de Martin, aparte lo que pierde una venta y lo que dice algo falso:
  por pedido etiquetado que vale ofrecer: alguna fila de Luna trae un aceptable primero, entre los 3, entre los 5, o
    ninguna; o existe dijo no hay en la fila que lo traia, falsa alarma. Pierde venta.
  por pedido que solo vale no hay: existe lo dijo en alguna fila, o una fila ofrece algo. Ofrecer es alucinar.
  por fila de Luna que ofrece: su primero no sirve para ningun pedido de la frase. Oferta equivocada, dice algo falso.
Los pedidos con orden se cuentan aparte: el primero de la busqueda no ordena, eso es de la capa de condicion.
El orden de los aceptables no se usa: no se mira la respuesta para ordenar.

    python3 primeros/medir.py            # la tabla
    python3 primeros/medir.py --ver      # y cada falla, para clasificarla contra lo grabado
"""
import collections, hashlib, json, os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(AQUI, "..", "lab"), os.path.join(AQUI, "..", "examen"), os.path.join(AQUI, "..")]
sys.dont_write_bytecode = True
import existe as EX  # noqa: E402
import busqueda as B  # noqa: E402
X = EX.X


def cargar():
    ex = json.load(open(os.path.join(AQUI, "examen.json")))
    h = hashlib.sha256(json.dumps(ex, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    if h != open(os.path.join(AQUI, "hash.txt")).read().strip():
        raise SystemExit("el hash no coincide: la etiqueta cambio")
    luna = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(AQUI, "luna.jsonl"))}
    return ex, luna


NO_OFRECE = ("no_hay", "sin rubro")  # sin rubro: la cadena no reconocio un producto de la tienda y no ofrece


def _filas(res):
    return [(lp[:35], vr, t[0][2] if t else "") for lp, vr, t in res]


def contar(e, res, n, fallas):
    """res: por fila con producto, (consulta, veredicto, top5). Suma al contador n y anota las fallas."""
    i = e["id"]
    acs = [set(X.aceptables(p)) for p in e["pedidos"]]
    for p, ac in zip(e["pedidos"], acs):
        grupo = "con orden" if any(c["tipo"] == "orden" for c in p["cas"]) else "sin orden"
        if "ofrecer" in p["esperados"] and ac:
            pos = [next((j for j, k in enumerate(top) if k in ac), None) for _, _, top in res]
            hay = [(q, vr) for q, (_, vr, _) in zip(pos, res) if q is not None]
            if any(q == 0 and vr not in NO_OFRECE for q, vr in hay):
                k = "primero sirve"
            elif any(q == 0 for q, vr in hay):
                k = "falsa alarma de existe"
            elif any(q is not None and q < 3 for q, _ in hay):
                k = "entre los 3"
            elif hay:
                k = "entre los 5"
            else:
                k = "no lo trae"
            n[("ofrecer", grupo, k)] += 1
            if k != "primero sirve":
                fallas.append(f"{i} pierde [{k}] {e['texto'][:70]!r} filas={_filas(res)}")
        elif set(p["esperados"]) == {"no_hay"}:
            k = "no hay dicho" if any(vr in NO_OFRECE for _, vr, _ in res) else "no hay perdido"
            n[("no hay", "", k)] += 1
            if k != "no hay dicho":
                fallas.append(f"{i} alucina [{k}] {e['texto'][:70]!r} filas={_filas(res)}")
    todos = set().union(*acs) if acs else set()
    for lp, vr, top in res:
        if vr in NO_OFRECE:
            continue
        n[("fila", "", "ofrece")] += 1
        if top[0] not in todos:
            n[("fila", "", "oferta equivocada")] += 1
            fallas.append(f"{i} alucina [oferta equivocada] {lp[:45]!r} -> {top[0][0]}: {top[0][2]}")


def main(ver):
    ex, luna = cargar()
    filas = {e["id"]: [f["lo_pedido"].strip() for f in (luna[e["id"]]["salida"] or {}).get("filas") or []
                       if f.get("lo_pedido", "").strip()] for e in ex}
    v = B.vectores([(lp, "RETRIEVAL_QUERY") for fs in filas.values() for lp in fs])
    ia = B.indice_a()
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))
    n, fallas = collections.Counter(), []
    for e in ex:
        i = e["id"]
        res = []  # por fila: (lo pedido, veredicto, top5)
        for lp in filas[i]:
            ver_, raz = EX.existe(lp, aislado=True)
            top = sorted(ia, key=lambda k: -dot(v[(lp, "RETRIEVAL_QUERY")], ia[k]))[:5]
            res.append((lp, ver_, top))
        contar(e, res, n, fallas)
    print(f"frases {len(ex)}, dudosas {sum(e['dudosa'] for e in ex)}, filas de Luna con producto "
          f"{sum(len(f) for f in filas.values())}")
    for (a, g, k), c in sorted(n.items()):
        print(f"  {a:8} {g:10} {k:24} {c}")
    if ver:
        print()
        for f in sorted(fallas):
            print(f)


if __name__ == "__main__":
    main("--ver" in sys.argv)
