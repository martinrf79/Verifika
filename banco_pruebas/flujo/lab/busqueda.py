"""EL LABORATORIO DE LA BUSQUEDA, DATO 1 (25-nov-2026). Ver lab/plan.md.

Compara como se redacta cada producto para los embeddings, el documento de hoy contra uno armado desde la ficha, y que
se le pregunta, el mensaje crudo contra las filas que separo Luna. Mide en que puesto quedan los aceptables del examen.

    python3 lab/busqueda.py               # pide lo que falta con la clave gratis y mide
    python3 lab/busqueda.py --ver         # ademas, frase por frase
    python3 lab/busqueda.py --doc <rubro> <modelo>   # los dos documentos de un producto
"""
import collections, gzip, json, math, os, re, sys, time, urllib.error, urllib.request
AQUI = os.path.dirname(os.path.abspath(__file__))
FL = os.path.join(AQUI, "..")
sys.path[:0] = [os.path.join(FL, "..", ".."), FL, os.path.join(FL, "bancos"), os.path.join(FL, "conceptos"),
                os.path.join(FL, "examen")]
sys.dont_write_bytecode = True
_argv, sys.argv = sys.argv, ["x"]
import nexo_rubro as NR  # noqa: E402
import examen as X  # noqa: E402
from app.core.flujo.nuevo import vectores as VV  # noqa: E402
sys.argv = _argv

F = X.F
CACHE = os.path.join(AQUI, "vectores.json.gz")
URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"
_, ALIAS, _, MODELOS = NR.fuente()
KS = [k for k in MODELOS if k in F.VISTA]
CAMPOS = [("conecta_por", "conexion"), ("switch_teclado", "tipo de teclado"), ("retroiluminacion", "luces"),
          ("panel", "panel"), ("resolucion", "resolucion"), ("bateria", "bateria"), ("microfono", "microfono"),
          ("cancelacion_ruido", "cancelacion de ruido"), ("resistencia_agua", "agua"), ("pulgadas", "pulgadas"),
          ("hz", "hz"), ("capacidad_gb", "capacidad gb"), ("ram_gb", "ram gb"), ("potencia_w", "potencia w"),
          ("plataformas", "anda con"), ("uso", "uso"), ("color", "colores")]


def doc_a(k):
    return NR.doc_producto(k, MODELOS[k], ALIAS)


def doc_b(k):
    """Lo que dice la ficha, y nada que no diga."""
    v = F.VISTA[k]
    nombre = MODELOS[k][0]["nombre"]
    partes = [f"{k[0]}: {nombre}", f"{k[1]} {k[2]}"]
    if v.get("extra"):
        partes.append(v["extra"])
    for c, nom in CAMPOS:
        x = v.get(c)
        if x in (None, "", []):
            continue
        x = ", ".join(str(i).replace("_", " ") for i in x) if isinstance(x, list) else str(x).replace("_", " ")
        partes.append(f"{nom}: {x}")
    return ". ".join(partes)


def _cache():
    return json.load(gzip.open(CACHE, "rt")) if os.path.exists(CACHE) else {}


def vectores(pedido):
    """{(texto, tarea): vector}. Pide a la clave gratis lo que no esta guardado, de a 100."""
    c = _cache()
    falta = [p for p in dict.fromkeys(pedido) if f"{p[1]}|{p[0]}" not in c]
    clave = os.environ["GEMINI_API_KEY"].split()[0]
    for i in range(0, len(falta), 100):
        lote = falta[i:i + 100]
        body = json.dumps({"requests": [{"model": "models/gemini-embedding-001", "content": {"parts": [{"text": t}]},
                                         "taskType": k} for t, k in lote]}).encode()
        for intento in range(6):
            try:
                r = json.load(urllib.request.urlopen(urllib.request.Request(URL, data=body, headers={
                    "x-goog-api-key": clave, "Content-Type": "application/json"}), timeout=120))
                break
            except urllib.error.HTTPError as e:
                if e.code != 429 or intento == 5:
                    json.dump(c, gzip.open(CACHE, "wt"))
                    raise SystemExit(f"embeddings: {e.code} {e.read()[:300]}")
                time.sleep(20 * (intento + 1))
        for (t, k), x in zip(lote, r["embeddings"]):
            n = math.sqrt(sum(v * v for v in x["values"])) or 1
            c[f"{k}|{t}"] = [round(v / n, 6) for v in x["values"]]
        json.dump(c, gzip.open(CACHE, "wt"))
        print(f"  embeddings pedidos: {i + len(lote)} de {len(falta)}", flush=True)
    return {p: c[f"{p[1]}|{p[0]}"] for p in pedido}


def indice_a():
    pos, v, dim = VV.indice(NR.TID)
    return {k: list(v[pos[doc_a(k)] * dim:(pos[doc_a(k)] + 1) * dim]) for k in KS}


def trozos(texto):
    t = [x.strip() for x in re.split(r"[.,;?!\n]|//|\by\b", texto) if len(x.strip()) > 3]
    return [texto] + (t if len(t) > 1 else [])


def top(qs, idx, n=15):
    """Como la llamada unica: los 15 de la primera consulta y 5 mas por cada otra, sin repetir."""
    out = []
    for j, q in enumerate(qs):
        orden = sorted(idx, key=lambda k: -sum(a * b for a, b in zip(q, idx[k])))
        out += [k for k in orden if k not in out][:15 if j == 0 else 5]
    return out[:30]


def casos():
    ex = {e["id"]: e for e in json.load(open(os.path.join(FL, "examen", "examen.json"), encoding="utf-8"))}
    luna = {json.loads(x)["id"]: json.loads(x) for x in open(os.path.join(FL, "examen", "luna_conceptos.jsonl"))}
    out = []
    for i, r in luna.items():
        e = ex[i]
        if len(e["pedidos"]) > 1 or e["dudosa"]:
            continue
        ac = set(X.aceptables(e["pedidos"][0]))
        if not ac:
            continue
        filas = [f["texto"] for f in ((r["salida"] or {}).get("filas") or []) if f.get("producto")]
        out.append((i, e["texto"], filas, ac))
    return out


def medir(nombre, cs, idx, consultas, ver):
    n = collections.Counter()
    for i, texto, filas, ac in cs:
        lista = top(consultas[i], idx)
        pos = next((j for j, k in enumerate(lista) if k in ac), None)
        n["frases"] += 1
        n["primero"] += pos == 0
        n["entre 3"] += pos is not None and pos < 3
        n["entre 15"] += pos is not None and pos < 15
        n["en lista"] += pos is not None
        n["aceptables en los 5 primeros"] += sum(k in ac for k in lista[:5])
        n["posibles en los 5 primeros"] += min(5, len(ac))
        if ver and (pos is None or pos > 2):
            print(f"    {nombre:28} {i:10} puesto {pos} | {texto[:80]}")
    print(f"  {nombre:28} {n['frases']} frases: primero {n['primero']}, entre 3 {n['entre 3']}, entre 15 {n['entre 15']},"
          f" en la lista {n['en lista']}; aceptables en los 5 primeros {n['aceptables en los 5 primeros']}"
          f" de {n['posibles en los 5 primeros']}")


def main():
    if "--doc" in sys.argv:
        r, m = sys.argv[sys.argv.index("--doc") + 1:][:2]
        k = next(k for k in KS if k[0] == r and m.lower() in k[2].lower())
        print("A:", doc_a(k), "\n\nB:", doc_b(k))
        return
    ver = "--ver" in sys.argv
    cs = casos()
    crudo = {i: trozos(t) for i, t, _, _ in cs}
    luna = {i: (f or [t]) for i, t, f, _ in cs}
    pedido = [(doc_b(k), "RETRIEVAL_DOCUMENT") for k in KS]
    pedido += [(t, "RETRIEVAL_QUERY") for qs in list(crudo.values()) + list(luna.values()) for t in qs]
    v = vectores(pedido)
    ia, ib = indice_a(), {k: v[(doc_b(k), "RETRIEVAL_DOCUMENT")] for k in KS}
    qc = {i: [v[(t, "RETRIEVAL_QUERY")] for t in qs] for i, qs in crudo.items()}
    ql = {i: [v[(t, "RETRIEVAL_QUERY")] for t in qs] for i, qs in luna.items()}
    print(f"frases de un pedido, sin dudosas, con aceptables: {len(cs)}")
    medir("documento A, mensaje crudo", cs, ia, qc, ver)
    medir("documento B, mensaje crudo", cs, ib, qc, ver)
    medir("documento A, filas de Luna", cs, ia, ql, ver)
    medir("documento B, filas de Luna", cs, ib, ql, ver)


if __name__ == "__main__":
    main()
