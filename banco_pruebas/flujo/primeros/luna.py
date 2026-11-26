"""LOS PRIMEROS MENSAJES NUEVOS POR EL CIRCUITO DEL DATO 1 (25-nov-2026, pedido de Martin). FICHA 108, capas 0, 1 y 2.

Las 300 de `sinteticas.jsonl`, que el examen no vio, pasan por lo mismo que el examen el 25-nov: Luna con el v14f1b y el
parrafo de `lo_pedido`, el prompt de `examen/luna_producto.py`, sin cambiar nada; la funcion `lab/existe.py` sobre lo
pedido aislado; y los cinco primeros de la busqueda de embeddings con lo pedido como consulta. Todavia sin etiqueta:
esto muestra como separa y que trae, para mirarlo antes de etiquetar.

    python3 primeros/luna.py 3        # tres, para ver que la entrada llega bien
    python3 primeros/luna.py          # las 300, retoma lo grabado
    python3 primeros/luna.py --b       # las 300 con el v14f1b de antes, en luna_b.jsonl
    python3 primeros/luna.py --examen  # las 138 reales del examen con el v14f1b, en examen/luna_b.jsonl
    python3 primeros/luna.py --ver [S001 ...]   # sin gasto: filas, veredicto de existe y los cinco primeros
"""
import concurrent.futures, json, os, sys, threading
AQUI = os.path.dirname(os.path.abspath(__file__))
FL = os.path.join(AQUI, "..")
sys.path[:0] = [os.path.join(FL, "examen"), os.path.join(FL, "lab"), FL]
_argv, sys.argv = sys.argv, ["x"]
import luna_producto as LP  # noqa: E402  el prompt v14f1p y su esquema quedan cargados en llamada0_modelos
sys.argv = _argv
L = LP.L

FRASES = os.path.join(AQUI, "sinteticas.jsonl")
# --examen: las 138 frases reales del examen fijo, `examen/examen.json`, con el v14f1b, en `examen/luna_b.jsonl`.
EXAMEN = "--examen" in sys.argv
if EXAMEN:
    sys.argv.remove("--examen")
# --b: el v14f1b tal como se midio antes del 25-nov, sin lo pedido y con la salida en lista de textos, para comparar.
B = "--b" in sys.argv
if B:
    sys.argv.remove("--b")
PROMPT = "v14f1b" if B else LP.PROMPT
SALIDA = os.path.join(FL, "examen", "luna_b.jsonl") if EXAMEN else os.path.join(AQUI, "luna_b.jsonl" if B else "luna.jsonl")
if EXAMEN:
    PROMPT = "v14f1b"
TOPE = 0.12  # el 25-nov, 97 frases costaron 2,8 centavos: 300 son unos 9
_lock = threading.Lock()


def frases():
    if EXAMEN:
        return [{"id": e["id"], "texto": e["texto"], "persona": ""} for e in json.load(open(os.path.join(FL, "examen", "examen.json")))]
    return [json.loads(x) for x in open(FRASES, encoding="utf-8")]


def grabado():
    return {json.loads(x)["id"]: json.loads(x) for x in open(SALIDA)} if os.path.exists(SALIDA) else {}


def uno(f):
    salida, ent, sal, seg, dol, crudo = L.pedir("luna", PROMPT, f["texto"])
    with _lock, open(SALIDA, "a") as o:
        o.write(json.dumps({"id": f["id"], "salida": salida, "crudo": None if salida else crudo, "entrada": ent,
                            "salida_tokens": sal, "seg_luna": seg, "dolares": dol}, ensure_ascii=False) + "\n")
    return f["id"], seg


def correr(n):
    hechos = grabado()
    falta = [f for f in frases()[:n] if f["id"] not in hechos]
    if sum(r["dolares"] for r in hechos.values()) >= TOPE:
        raise SystemExit(f"tope de {TOPE} dolares")
    with concurrent.futures.ThreadPoolExecutor(6) as ex:
        for i, seg in ex.map(uno, falta):
            print(i, round(seg, 1), flush=True)
    print("gasto", round(sum(r["dolares"] for r in grabado().values()), 4), "dolares")


def ver(cuales):
    import existe as E
    import busqueda as B
    g, fs = grabado(), {f["id"]: f for f in frases()}
    sel = [i for i in fs if i in g and (not cuales or i in cuales)]
    pares = []
    for i in sel:
        for r in (g[i]["salida"] or {}).get("filas") or []:
            if r.get("lo_pedido", "").strip():
                pares.append((r["lo_pedido"].strip(), "RETRIEVAL_QUERY"))
    v = B.vectores(pares)
    ia = B.indice_a()
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))
    for i in sel:
        print(f"\n{i} {fs[i]['persona']} | {fs[i]['texto']}")
        for r in (g[i]["salida"] or {}).get("filas") or []:
            lp = r.get("lo_pedido", "").strip()
            if not lp:
                print(f"   fila sin producto: {r['texto'][:90]}")
                continue
            ver_, raz = E.existe(lp, aislado=True)
            top = sorted(ia, key=lambda k: -dot(v[(lp, "RETRIEVAL_QUERY")], ia[k]))[:5]
            print(f"   lo pedido: {lp!r}  existe: {ver_} {raz or ''}")
            print("      " + " | ".join(f"{k[2]} {dot(v[(lp, 'RETRIEVAL_QUERY')], ia[k]):.2f}" for k in top))


if __name__ == "__main__":
    if "--ver" in sys.argv:
        ver(set(a for a in sys.argv[1:] if a.startswith("S")))
    else:
        correr(int(sys.argv[1]) if len(sys.argv) > 1 else 10 ** 6)
