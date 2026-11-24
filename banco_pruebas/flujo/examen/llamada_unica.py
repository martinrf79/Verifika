"""LA LLAMADA UNICA: LUNA SEPARA, TRADUCE Y ELIGE LA FILA EN UNA SOLA VUELTA (24-nov-2026). Ver plan.md.

Antes de Luna, los embeddings del mensaje y sus trozos traen hasta 30 filas de la tienda. Luna, con el prompt v14f1b y
la ficha f1, separa y traduce como la llamada 0, y en la misma llamada elige, por fila, las filas de la tienda que sirven y
las dudosas, como el verificador podado de la FICHA 105. El codigo aplica el tope de plata y decide.

    python3 examen/llamada_unica.py 3          # los tres primeros, para ver que la entrada llega bien
    python3 examen/llamada_unica.py            # todo el examen, retoma lo grabado
    python3 examen/llamada_unica.py --informe  # sin gasto, sobre lo grabado
"""
import collections, json, math, os, re, statistics, sys, time, urllib.error, urllib.request
AQUI = os.path.dirname(os.path.abspath(__file__))
FL = os.path.join(AQUI, "..")
sys.path[:0] = [os.path.join(FL, "..", ".."), FL, os.path.join(FL, "bancos"), os.path.join(FL, "traductor"), AQUI]
sys.dont_write_bytecode = True
_argv, sys.argv = sys.argv, ["x"]
import llamada0_modelos as L  # noqa: E402
import jev_filas as JF  # noqa: E402
import podado as PD  # noqa: E402
import decidir_verif as DV  # noqa: E402
import examen as X  # noqa: E402
sys.argv = _argv

SALIDA = os.path.join(AQUI, "llamada_unica.jsonl")  # la corrida 1, con las dos fallas del guion, en llamada_unica_c1.jsonl
TOPE = 0.15
PROMPT = "v14f1u"
CONC = json.load(open(os.path.join(FL, "conceptos", "conceptos.json"), encoding="utf-8"))
ORDENES = ["ninguno"] + [k.split(":")[1] for k, c in CONC.items() if c["tipo"] == "orden"]
L.PROMPTS[PROMPT] = L.PROMPTS["v14f1b"] + """

DESPUES DE SEPARAR, ELEGI. Al final del mensaje vienen las FILAS DE LA TIENDA, numeradas. Por cada fila tuya que pide un
producto, deci que filas de la tienda cumplen todo lo que esa fila pide, en sirven, y cuales cumplirian pero les falta
un dato, en dudosas, con el dato que falta. Mira solo lo que dicen las filas de la tienda: no supongas datos que no
traen. El precio y lo que el cliente prefiere sin exigir no cuentan para elegir. Si ninguna fila de la tienda es lo que
pide, sirven y dudosas van vacias. Todas las filas de la tienda estan en stock. Si la fila pide un orden, como el mas
barato o el mas liviano, ponelo en orden; si no, ninguno. Preguntar por un producto, por sus caracteristicas, si
lo tienen o si anda con algo, tambien es pedir un producto: va con producto en verdadero. Solo va con producto en falso
la fila que no nombra ni pide ningun producto, como una pregunta por el envio o el pago."""
L.ESQUEMAS[PROMPT] = {"type": "object", "additionalProperties": False, "required": ["filas"], "properties": {
    "filas": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                         "required": ["texto", "producto", "orden", "sirven", "dudosas"], "properties": {
        "texto": {"type": "string"}, "producto": {"type": "boolean"}, "orden": {"type": "string", "enum": ORDENES},
        "sirven": {"type": "array", "items": {"type": "integer"}},
        "dudosas": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                               "required": ["fila", "falta"],
                                               "properties": {"fila": {"type": "integer"}, "falta": {"type": "string"}}}}}}}}}

URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
FU = JF._fuente()


def embed(t):
    for k in range(4):
        body = json.dumps({"model": "models/gemini-embedding-001", "content": {"parts": [{"text": t}]},
                           "taskType": "RETRIEVAL_QUERY"}).encode()
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(URL, data=body, headers={
                "x-goog-api-key": os.environ["GEMINI_API_KEY"].split()[0], "Content-Type": "application/json"}), timeout=60))
            x = r["embedding"]["values"]
            n = math.sqrt(sum(v * v for v in x)) or 1
            return [v / n for v in x]
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(8 * (k + 1))
    raise SystemExit("429 de la gratis sin ceder")


def top(q, n):
    return [k for _, k in sorted(((sum(a * b for a, b in zip(q, v)), k) for k, v in FU.prod), key=lambda z: -z[0])[:n]]


def candidatos(texto):
    trozos = [t.strip() for t in re.split(r"[.,;?!\n]|//|\by\b", texto) if len(t.strip()) > 3]
    out = list(top(embed(texto), 15))
    for t in trozos if len(trozos) > 1 else []:
        out += [k for k in top(embed(t), 5) if k not in out]
    return out[:30]


def topes(fr):
    """El tope de plata: un numero con palabra de plata, "30 lucas", "200 mil", "$50.000", o despues de "hasta", "menos de",
    "no pase". Un numero de un modelo, "RTX 4080" o "L5590", no es plata."""
    s = DV.norm(fr)
    out = []
    for m in re.finditer(r"\d[\d.,]*(\s*[a-z]+)?(?![a-z0-9])", s):
        antes = s[max(0, m.start() - 15):m.start()]
        plata = re.search(r"\b(mil|lucas?|luquitas?|k|pesos|palos?|millon(es)?)$", m.group(0)) or "$" in antes[-2:] \
            or re.search(r"\b(hasta|menos de|maximo|no pase|no pasen|por debajo de|tope de|no mas de)\s*$", antes)
        t = DV.tope(m.group(0), fr) if plata else None
        if t:
            out.append(t)
    return out


def decidir(fila, cand):
    sirven = [tuple(cand[n - 1]) for n in fila.get("sirven") or [] if 1 <= n <= len(cand)]
    sirven = [k for k in sirven if PD.precio_ok(k, topes(fila.get("texto") or ""))]
    o = fila.get("orden") or "ninguno"
    if sirven and o != "ninguno":
        campo, _, sentido = CONC["orden:" + o]["cond"][0]
        conv = [k for k in sirven if X.F.VISTA[k][campo] is not None]
        sirven = sorted(conv, key=lambda k: X.F.VISTA[k][campo], reverse=sentido == "desc")[:1] or sirven
    if sirven:
        return "ofrece", sirven[:3]
    return ("repregunta" if fila.get("dudosas") else "no_hay"), []


def una(e):
    t0 = time.time()
    cand = candidatos(e["texto"])
    t_emb = time.time() - t0
    usr = e["texto"] + "\n\nFILAS DE LA TIENDA:\n" + "\n".join(PD.fila(n + 1, k) for n, k in enumerate(cand))
    salida, ent, sal, seg, dol, crudo = L.pedir("luna", PROMPT, usr)
    return {"id": e["id"], "cand": [list(k) for k in cand], "salida": salida, "crudo": None if salida else crudo,
            "entrada": ent, "salida_tokens": sal, "seg_luna": seg, "seg_emb": round(t_emb, 2), "dolares": dol}


def grabado():
    return {json.loads(x)["id"]: json.loads(x) for x in open(SALIDA)} if os.path.exists(SALIDA) else {}


def corregir(e, r):
    """(nota de la frase, [notas por linea de producto]). La frase: su primera linea de producto, como el resolvedor."""
    filas = [f for f in ((r["salida"] or {}).get("filas") or []) if f.get("producto")]
    lineas = []
    for f in filas:
        dec, of = decidir(f, r["cand"])
        lineas.append(X.corregir(e, dec, of))
    if not filas:
        return X.corregir(e, "no_hay", []), []
    dec, of = decidir(filas[0], r["cand"])
    return X.corregir(e, dec, of), lineas


def informe():
    ex = {e["id"]: e for e in json.load(open(os.path.join(AQUI, "examen.json"), encoding="utf-8"))}
    g = grabado()
    c = collections.defaultdict(list)
    for i, r in g.items():
        e = ex[i]
        nota, lineas = corregir(e, r)
        grupo = "varios pedidos, por linea" if len(e["pedidos"]) > 1 else ("un pedido, dudosas" if e["dudosa"] else "un pedido, sin dudosas")
        c[grupo] += lineas if len(e["pedidos"]) > 1 else [nota]
    print(f"frases corridas {len(g)} de {len(ex)}")
    for k in ("un pedido, sin dudosas", "un pedido, dudosas", "varios pedidos, por linea"):
        n = collections.Counter(c[k])
        print(f"  {k}: {len(c[k])} · acierta {n['acierta']}, repregunta {n['repregunta']}, erra {n['erra']}")
    seg = sorted(r["seg_emb"] + r["seg_luna"] for r in g.values())
    luna = sorted(r["seg_luna"] for r in g.values())
    if seg:
        print(f"  segundos de punta a punta: mediana {statistics.median(seg):.1f}, p90 {seg[int(len(seg) * .9) - 1]:.1f};"
              f" solo Luna: mediana {statistics.median(luna):.1f}")
        print(f"  tokens medios: entrada {statistics.mean(r['entrada'] for r in g.values()):.0f},"
              f" salida {statistics.mean(r['salida_tokens'] for r in g.values()):.0f}; gasto {sum(r['dolares'] for r in g.values()):.3f} dolares")


if __name__ == "__main__":
    if "--informe" in sys.argv:
        informe()
        sys.exit()
    ex = json.load(open(os.path.join(AQUI, "examen.json"), encoding="utf-8"))
    hechos = grabado()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else len(ex)
    for e in ex[:n]:
        if e["id"] in hechos:
            continue
        if sum(r["dolares"] for r in grabado().values()) >= TOPE:
            raise SystemExit(f"tope de {TOPE} dolares de la corrida")
        r = una(e)
        with open(SALIDA, "a") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(e["id"], r["seg_emb"], r["seg_luna"], r["entrada"], r["salida_tokens"], flush=True)
    informe()
