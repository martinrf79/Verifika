"""LUNA TRADUCE A LA LISTA CERRADA, EL CODIGO ELIGE (25-nov-2026). Ver el cuarto plan de chico/plan.md.

Luna separa el mensaje en filas, como la v14f1b, y por cada fila devuelve los ids de conceptos.json, la marca, el
modelo, los numeros, el orden y lo que pide que no esta en la lista. No ve ninguna fila de producto. El codigo convierte
eso a casilleros y decide con `chico/reparto.resolver`: exacto contra la ficha, y el modelo chico solo para lo abierto.
Candidatos: los que grabo la llamada unica, sin gastar embeddings.

    E5=... PYTHONPATH=... python3 examen/luna_conceptos.py 3          # tres, para ver que la entrada llega bien
    E5=... PYTHONPATH=... python3 examen/luna_conceptos.py            # las grabadas por la llamada unica, retoma
    E5=... PYTHONPATH=... python3 examen/luna_conceptos.py --informe  # sin gasto
"""
import collections, json, os, statistics, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "chico"))
_argv, sys.argv = sys.argv, ["x"]
import llamada_unica as LU  # noqa: E402
import reparto as R  # noqa: E402
sys.argv = _argv

L, X, F, CONC = LU.L, R.X, R.F, R.CONC
SALIDA = os.path.join(AQUI, "luna_conceptos.jsonl")
TOPE = 0.10
PROMPT = "v14f1c"  # empieza con v14f1 para que `luna_ficha` le de la ficha f1, la misma de la llamada unica
FILTRAN = [k for k, c in CONC.items() if c["tipo"] in ("rubro", "atributo", "plataforma", "color", "origen", "preferencia")]
NUMEROS = ["precio", "pulgadas", "capacidad_gb", "ram_gb", "disco_gb", "memoria_video_gb", "hz", "potencia_w",
           "nucleos", "peso", "fuente_recomendada_w"]
LISTA = "\n".join(f"{t.upper()}: " + ", ".join(f"{k} ({c['nombre']})" for k, c in CONC.items() if c["tipo"] == t)
                  for t in ("rubro", "atributo", "plataforma", "color", "origen", "preferencia"))

L.PROMPTS[PROMPT] = L.PROMPTS["v14f1b"].split("En cada fila van")[0] + """En cada fila va el texto: las palabras del cliente de esa fila, con solo la ortografia corregida.
Despues traduci la fila a la LISTA DE CONCEPTOS de la tienda, que va abajo. Solo traducis: no decidis que producto le
sirve ni si la tienda lo tiene.
- conceptos: los ids de la lista que el cliente pide para esa fila: el producto, y las caracteristicas que exige. Si dice
  "auris", es rubro:auriculares; si dice "sin cable", atributo:inalambrico. Un id solo si el cliente lo dice o lo da a
  entender sin duda.
- negados: los ids que el cliente pide que NO tenga, como "que no tenga luces".
- preguntas: los ids por los que solo pregunta si el producto lo tiene, sin exigirlo, como "tiene luces?".
- marca y modelo: tal como los nombra el cliente, corregidos; vacios si no nombra. marca_negada: la marca que no quiere.
- numeros: lo que el cliente exige con un numero: campo, igual, min o max, y el valor como numero. "hasta 30 lucas" es
  precio max 30000; "de 27 pulgadas" es pulgadas igual 27; "1 tera" es capacidad_gb igual 1000. Ofrecer plata por un
  producto que ya eligio no es un tope.
- orden: si pide el mas barato, el mas liviano, el mas grande, etc.; si no, ninguno.
- abiertas: lo que el cliente exige del producto y no esta en la lista ni es un numero, con sus palabras, como "que
  titile con la musica" o "pantalla tactil". El envio, el pago y la cantidad no van aca.
- no_vende: verdadero si pide algo que una tienda de tecnologia no vende o un servicio que no da, como alquilar.
- producto: falso si la fila no pide ni pregunta por ningun producto, como el envio o el pago.

LISTA DE CONCEPTOS
""" + LISTA + "\n\nVOCABULARIO DE LA TIENDA\n{ficha}"
L.ESQUEMAS[PROMPT] = {"type": "object", "additionalProperties": False, "required": ["filas"], "properties": {
    "filas": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": [
        "texto", "producto", "no_vende", "conceptos", "negados", "preguntas", "marca", "marca_negada", "modelo",
        "numeros", "orden", "abiertas"], "properties": {
        "texto": {"type": "string"}, "producto": {"type": "boolean"}, "no_vende": {"type": "boolean"},
        "conceptos": {"type": "array", "items": {"type": "string", "enum": FILTRAN}},
        "negados": {"type": "array", "items": {"type": "string", "enum": FILTRAN}},
        "preguntas": {"type": "array", "items": {"type": "string", "enum": FILTRAN}},
        "marca": {"type": "string"}, "marca_negada": {"type": "string"}, "modelo": {"type": "string"},
        "numeros": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                               "required": ["campo", "op", "valor"], "properties": {
            "campo": {"type": "string", "enum": NUMEROS}, "op": {"type": "string", "enum": ["igual", "min", "max"]},
            "valor": {"type": "number"}}}},
        "orden": {"type": "string", "enum": LU.ORDENES},
        "abiertas": {"type": "array", "items": {"type": "string"}}}}}}}

nrm = F.nrm
MARCAS = sorted({v["marca"] for v in F.VISTA.values()})


def _marca(t):
    t = nrm(t)
    return next((m for m in MARCAS if t and (nrm(m) == t or nrm(m).replace(" ", "") == t.replace(" ", ""))), None)


def _modelos(t, marca):
    t = nrm(t).replace(" ", "")
    if not t:
        return None
    return [v["modelo"] for v in F.VISTA.values() if (not marca or v["marca"] == marca)
            and (t in nrm(v["modelo"]).replace(" ", "") or nrm(v["modelo"]).replace(" ", "") in t)]


def casilleros(f):
    """Una fila de Luna como un pedido del examen, para `reparto.resolver`."""
    cas = []
    c = lambda tipo, valor, modo="", palabras="": cas.append({"tipo": tipo, "valor": valor, "modo": modo, "palabras": palabras})
    if f["no_vende"]:
        c("fuera", "no_vende")
    rub = [i for i in f["conceptos"] if i.startswith("rubro:")]
    if rub:
        c("rubro", rub)
    for i in f["conceptos"]:
        if not i.startswith("rubro:"):
            c(i.split(":")[0], i)
    for i in f["negados"]:
        c(i.split(":")[0], i, "no")
    m = _marca(f["marca"]) if f["marca"] else None
    if f["marca"]:
        c("marca", m or f["marca"])
    if f["marca_negada"]:
        c("marca", _marca(f["marca_negada"]) or f["marca_negada"], "no")
    mods = _modelos(f["modelo"], m)
    if mods is not None:
        c("modelo", mods)
    for n in f["numeros"]:
        c("numero", [n["campo"], n["op"], n["valor"]])
    if f["orden"] != "ninguno":
        c("orden", "orden:" + f["orden"])
    for a in f["abiertas"]:
        c("fuera", "sin_dato", "", a)
    return {"cas": cas}


def decidir(f, cand):
    if not f["producto"]:
        return "no_hay", [], "no producto"
    return R.resolver(casilleros(f), cand)


def grabado():
    return {json.loads(x)["id"]: json.loads(x) for x in open(SALIDA)} if os.path.exists(SALIDA) else {}


def informe(ver=False):
    ex = {e["id"]: e for e in json.load(open(os.path.join(AQUI, "examen.json"), encoding="utf-8"))}
    cand = {r["id"]: r["cand"] for r in map(json.loads, open(LU.SALIDA))}
    g = grabado()
    cuenta = collections.defaultdict(list)
    for i, r in g.items():
        e = ex[i]
        filas = [f for f in ((r["salida"] or {}).get("filas") or []) if f.get("producto")]
        res = [(f, *decidir(f, cand[i])) for f in filas]
        if len(e["pedidos"]) > 1:
            cuenta["varios pedidos, por linea"] += [X.corregir(e, d, o) for _, d, o, _ in res]
            continue
        f, d, o, n = res[0] if res else (None, "no_hay", [], "sin filas")
        nota = X.corregir(e, d, o)
        cuenta["un pedido, dudosas" if e["dudosa"] else "un pedido, sin dudosas"].append(nota)
        if ver and nota != "acierta":
            luna = {k: v for k, v in (f or {}).items() if v not in ("", [], False, "ninguno") and k != "texto"}
            print(f"  {nota:10} {i:11} {d:10} {[k[2] for k in o]} {n}\n             {e['texto'][:110]}\n             luna: {luna}")
    print(f"frases {len(g)}, Luna traduce a la lista cerrada, el codigo elige")
    for k in ("un pedido, sin dudosas", "un pedido, dudosas", "varios pedidos, por linea"):
        n = collections.Counter(cuenta[k])
        print(f"  {k}: {len(cuenta[k])} · acierta {n['acierta']}, repregunta {n['repregunta']}, erra {n['erra']}")
    if g:
        s = sorted(r["seg_luna"] for r in g.values())
        print(f"  Luna: mediana {statistics.median(s):.1f} segundos, p90 {s[int(len(s) * .9) - 1]:.1f};"
              f" tokens medios entrada {statistics.mean(r['entrada'] for r in g.values()):.0f},"
              f" salida {statistics.mean(r['salida_tokens'] for r in g.values()):.0f};"
              f" gasto {sum(r['dolares'] for r in g.values()):.3f} dolares")


if __name__ == "__main__":
    if "--informe" in sys.argv:
        informe("--ver" in sys.argv)
        sys.exit()
    ids = [json.loads(x)["id"] for x in open(LU.SALIDA)]
    n = int(sys.argv[1]) if len(sys.argv) > 1 else len(ids)
    ex = {e["id"]: e for e in json.load(open(os.path.join(AQUI, "examen.json"), encoding="utf-8"))}
    for i in ids[:n]:
        if i in grabado():
            continue
        if sum(r["dolares"] for r in grabado().values()) >= TOPE:
            raise SystemExit(f"tope de {TOPE} dolares de la corrida")
        salida, ent, sal, seg, dol, crudo = L.pedir("luna", PROMPT, ex[i]["texto"])
        with open(SALIDA, "a") as f:
            f.write(json.dumps({"id": i, "salida": salida, "crudo": None if salida else crudo, "entrada": ent,
                                "salida_tokens": sal, "seg_luna": seg, "dolares": dol}, ensure_ascii=False) + "\n")
        print(i, seg, ent, sal, flush=True)
    informe()
