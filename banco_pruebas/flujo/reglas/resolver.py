"""EL RESOLVEDOR: de la frase del cliente a filas del catalogo con la base de conocimiento y codigo (24-nov-2026).
Ver plan.md. Corre en el entorno aparte del modelo chico, con torch y transformers.

    venv/bin/python resolver.py validar    # fija los cortes en la validacion, las frases de Luna
    venv/bin/python resolver.py probar     # las 48 de la FICHA 105 con esos cortes
    venv/bin/python resolver.py "frase"    # una frase, para mirar
"""
import difflib, json, os, re, statistics, sys, time
AQUI = os.path.dirname(os.path.abspath(__file__))
TR = os.path.join(AQUI, "..", "traductor")
sys.path[:0] = [AQUI, TR]
sys.dont_write_bytecode = True
import numpy as np, torch  # noqa: E402
from transformers import AutoModel, AutoTokenizer  # noqa: E402
import base as B, catalogo as K  # noqa: E402
import decidir_verif as DV  # noqa: E402

E5 = os.environ.get("E5", "intfloat/multilingual-e5-small")
CORTES = os.path.join(AQUI, "cortes.json")
torch.set_num_threads(4)
_tok = AutoTokenizer.from_pretrained(E5)
_mod = AutoModel.from_pretrained(E5).eval()


@torch.no_grad()
def emb(textos):
    out = []
    for i in range(0, len(textos), 256):
        x = _tok(["query: " + t for t in textos[i:i + 256]], padding=True, truncation=True, max_length=32, return_tensors="pt")
        h = _mod(**x).last_hidden_state
        m = x["attention_mask"].unsqueeze(-1)
        v = (h * m).sum(1) / m.sum(1)
        out.append(torch.nn.functional.normalize(v, dim=-1).numpy())
    return np.vstack(out)


# ── la base embebida: rubros de alias.json y las caracteristicas de base.py ─────────────────────────────────────
ALIAS = json.load(open(os.path.join(AQUI, "../../../data/clientes/verifika_prod/alias.json"), encoding="utf-8"))
RUBROS = {k[0] for k in K.MOD}
ENT = []  # (tipo, concepto, expresion)
for r, al in ALIAS["rubros"].items():
    if r in RUBROS:
        for e in [r] + al:
            ENT.append(("rubro", r, B.nrm(e)))
for c, _, ex in B.BASE:
    for e in ex:
        ENT.append(("cond", c, B.nrm(e)))
EV = emb([e for _, _, e in ENT])
CONDS = {c: conds for c, conds, _ in B.BASE}
VISTA = {k: B.vista(k) for k in K.MOD}
MEMO = {}

# ── marcas y modelos, por codigo ────────────────────────────────────────────────────────────────────────────
MARCAS = {B.nrm(k[1]): k[1] for k in K.MOD}
MODELOS = {}  # token o nombre normalizado -> claves
for k in K.MOD:
    n = B.nrm(k[2])
    MODELOS.setdefault(n, set()).add(k)
    t0 = n.split()[0]
    if re.search(r"\d", t0) or len(t0) >= 5:
        MODELOS.setdefault(t0, set()).add(k)
UNIDAD = re.compile(r"^\d+(gb|tb|hz|mm|w|mah|k|p|lucas?|mil)?$")
VACIAS = set(B.nrm("""hola buenas buen dia che tenes tenez tienen tienes tendras hay quiero quisiera queria busco buscando
necesito dame decime pasame poneme agrega agregame sumale sumame me te le lo la los las el un una unos unas de del para pa
por con y o a que q cual cuales cuanto cuanta sale salen cuesta precio precios valor stock disponible algo algun alguna
mas muy bien bueno buena copado copada gracias porfa favor saber ver mirar sobre en es son esta este ese esa eso tu su mi
tengo tiene si ya hace hacen tenes? ahi aca otro otra uno dos tres cuatro cinco""").split())


def tokens(fr):
    return B.nrm(fr).split()


def trozos(ts):
    out = []
    for n in range(1, 5):
        for i in range(len(ts) - n + 1):
            w = ts[i:i + n]
            if all(t in VACIAS for t in w):
                continue
            out.append((i, i + n, " ".join(w)))
    return out


def resolver(fr, alto, bajo, topes=None):
    ts = tokens(fr)
    usado = [False] * len(ts)
    marcas, modelos, desconocido = set(), set(), []
    # marcas y modelos por codigo, nombres largos primero
    for n in range(4, 0, -1):
        for i in range(len(ts) - n + 1):
            if any(usado[i:i + n]):
                continue
            w = " ".join(ts[i:i + n])
            if w in MARCAS:
                marcas.add(MARCAS[w]); usado[i:i + n] = [True] * n
            elif w in MODELOS and not (n == 1 and w in VACIAS):
                modelos |= MODELOS[w]; usado[i:i + n] = [True] * n
    for i, t in enumerate(ts):
        if usado[i] or t in VACIAS:
            continue
        if re.match(r"^[a-z]+\d+[a-z0-9]*$", t) and not UNIDAD.match(t):
            parecido = difflib.get_close_matches(t, [m for m in MODELOS if re.search(r"\d", m)], 1, 0.85)
            if parecido:
                modelos |= MODELOS[parecido[0]]; usado[i] = True
            else:
                desconocido.append(t)
    # la plata la lee el codigo: los numeros, sus unidades y "hasta" no van a los embeddings
    if topes:
        for i, t in enumerate(ts):
            if re.match(r"^\d+$", t) or t in DV.UN or t in ("hasta", "maximo", "menos", "pesos", "presupuesto"):
                usado[i] = True
    # el resto contra la base embebida
    tz = [(a, b, w) for a, b, w in trozos(ts) if not any(usado[a:b])]
    sel, amarillos = [], []
    if tz:
        nuevos = [w for _, _, w in tz if w not in MEMO]
        if nuevos:
            MEMO.update(zip(nuevos, emb(nuevos)))
        sim = np.vstack([MEMO[w] for _, _, w in tz]) @ EV.T
        mejor = sim.argmax(1)
        cand = sorted(((float(sim[j, mejor[j]]), j) for j in range(len(tz))), reverse=True)
        tomado = [False] * len(ts)
        for s, j in cand:
            a, b, w = tz[j]
            if s < bajo or any(tomado[a:b]):
                continue
            tipo, conc, ex = ENT[mejor[j]]
            if s >= alto:
                neg = False
                antes = " ".join(ts[max(0, a - 3):a])
                if ts[a] in ("no", "sin") and not ex.split()[0] in ("no", "sin"):
                    neg = True
                elif re.search(r"\b(no|sin|que no sea|que no sean|nada de)$", antes):
                    neg = True
                sel.append((tipo, conc, neg, w, round(s, 3)))
                tomado[a:b] = [True] * (b - a)
            else:
                amarillos.append((tipo, conc, w, round(s, 3)))
        amarillos = [x for x in amarillos if not any(x[2] in s[3] or s[3] in x[2] for s in sel)]
    rubros = {c for t, c, n, _, _ in sel if t == "rubro" and not n}
    conds = [(c, n) for t, c, n, _, _ in sel if t == "cond"]
    info = {"rubros": sorted(rubros), "marcas": sorted(marcas), "modelos": sorted(m[2] for m in modelos), "conds": conds,
            "amarillos": amarillos, "desconocido": desconocido}
    if desconocido:
        return "no_hay", [], info
    if not (rubros or marcas or modelos):
        return ("repregunta" if (conds or amarillos) else "no_hay"), [], info
    # Lo ambiguo se pregunta, regla 7.0: dos rubros en una linea, o una marca sin rubro que esta en varios rubros.
    if len(rubros) > 1 or (not rubros and not modelos and len({k[0] for k in K.MOD if k[1] in marcas}) > 1):
        return "repregunta", [], info
    ks = [k for k in K.MOD if (not rubros or k[0] in rubros) and (not marcas or k[1] in marcas)
          and (not modelos or k in modelos)]
    orden = None
    for c, neg in conds:
        for cond in CONDS[c]:
            if cond[1] == "orden":
                orden = (cond[0], cond[2] == "desc")
                continue
            ks = [k for k in ks if B.cumple(VISTA[k], cond) != neg]
    for d, n in (topes or []):
        ks = [k for k in ks if (VISTA[k]["precio"] <= n if d == "max" else VISTA[k]["precio"] >= n)]
    if not ks:
        return "no_hay", [], info
    if [a for a in amarillos if a[0] == "cond"]:
        return "repregunta", [], info
    campo, desc = orden or ("precio", False)
    ks.sort(key=lambda k: VISTA[k][campo], reverse=desc)
    return "ofrece", ks[:3], info


def corregir(dec, of, ac, top=None):
    ac = {tuple(a) for a in ac}
    if top is not None and ac and not ac & {tuple(t) for t in top}:
        return "falla_busqueda"
    if dec == "repregunta":
        return "repregunta"
    if dec == "no_hay":
        return "acierta" if not ac else "erra"
    return "acierta" if of and all(tuple(k) in ac for k in of) else "erra"


def topes(fr):
    out = []
    for m in re.finditer(r"\d[\d.,]*\s*[a-z]*", DV.norm(fr)):
        t = DV.tope(m.group(0), fr)
        if t:
            out.append(t)
    return out


def validacion():
    import random
    rs = [json.loads(x) for x in open(os.path.join(AQUI, "..", "chico", "frases.jsonl"))]
    rnd = random.Random(105)
    return [(f, r["acept"]) for r in rs if "modelos" not in r["regla"] for f in rnd.sample(r["frases"], 2)]


def cuenta(cs):
    return {x: cs.count(x) for x in ("acierta", "repregunta", "erra", "falla_busqueda") if cs.count(x)}


def validar():
    vs = validacion()
    mejor = None
    for alto in (0.86, 0.88, 0.9, 0.92, 0.94, 0.95, 0.96, 0.97):
        for bajo in (0.84, 0.86, 0.88, 0.9, 0.92, 0.94):
            if bajo > alto:
                continue
            cs = [corregir(*resolver(f, alto, bajo)[:2], ac) for f, ac in vs]
            v = cs.count("acierta") - 3 * cs.count("erra")
            print(alto, bajo, cuenta(cs), flush=True)
            if mejor is None or v > mejor[0]:
                mejor = (v, alto, bajo, cuenta(cs))
    json.dump({"alto": mejor[1], "bajo": mejor[2], "validacion": mejor[3], "n": len(vs)}, open(CORTES, "w"))
    print("elegido", mejor)


def probar():
    import hashlib
    from muestra import M
    h = hashlib.sha256(open(os.path.join(TR, "muestra.py"), "rb").read()).hexdigest()
    assert h in open(os.path.join(TR, "hash.txt")).read(), "la muestra cambio"
    c = json.load(open(CORTES))
    AC = json.load(open(os.path.join(TR, "aceptables.json")))
    CAND = json.load(open(os.path.join(TR, "cand.json")))
    out, seg = [], []
    for m, ac, cd in zip(M, AC, CAND):
        t = time.time()
        dec, of, info = resolver(m[2], c["alto"], c["bajo"], topes(m[2]))
        seg.append(time.time() - t)
        out.append({"id": m[1], "dudosa": m[4], "frase": m[2], "dec": dec, "of": [k[2] for k in of],
                    "c": corregir(dec, of, ac, cd["top"]), **info})
    with open(os.path.join(AQUI, "prueba.jsonl"), "w") as f:
        for o in out:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    print("cortes", c)
    print("todas", len(out), cuenta([o["c"] for o in out]))
    print("sin dudosas", sum(not o["dudosa"] for o in out), cuenta([o["c"] for o in out if not o["dudosa"]]))
    print("van al verificador", sum(o["dec"] == "repregunta" for o in out))
    seg.sort()
    print(f"tiempo por frase: mediana {statistics.median(seg) * 1000:.0f} ms, p90 {seg[int(len(seg) * .9) - 1] * 1000:.0f} ms")


if __name__ == "__main__":
    q = sys.argv[1]
    if q == "validar":
        validar()
    elif q == "probar":
        probar()
    else:
        print(resolver(q, 0.9, 0.86, topes(q)))
