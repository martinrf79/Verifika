"""LA CALIFICACION — lo que devolvio el modelo contra las fichas, sin modelo (22-oct-2026).

Dos partes, por separado:
  1. LA TRADUCCION: si el Python dice, en palabras, lo que dice la ficha: la accion, la clase de producto, la cantidad,
     el destino, el color, el orden, el tope, el pago, las condiciones, lo que senala de la memoria y si depende de otro
     pedido. Se mira con las palabras que acepta la ficha, sin la fuente.
  2. EL CODIGO: si con esas palabras el codigo de hoy encuentra lo correcto en la fuente: el rubro, el producto, el
     lugar, el campo de cada condicion, el orden, el tema de la politica.

Por turno, uno de tres: BIEN, todo lo de la ficha esta y bien dicho; PREGUNTO, falta o esta mal algo pero el modelo
pregunta; MAL SIN AVISAR, falta o esta mal algo y no pregunta nada.
Ademas: lo que se olvido, lo que se dijo mal y en que dato, el Python que no se pudo leer, si la memoria quedo nombrada
en lenguaje comun, y los cortes del mensaje contra la barra de la ficha, del modelo y de Jev.

    python3 banco_pruebas/pregunta_razonada/calificar.py [--ver] [--forma A]
"""
import ast
import collections
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, REPO)
sys.path.insert(0, AQUI)
os.chdir(REPO)
os.environ.pop("GEMINI_API_KEY_PROD", None)
from banco_pruebas import clon_produccion as C  # noqa: E402
C.preparar_entorno()
C.instalar()
from app.core.flujo import catalogo as K, marcador  # noqa: E402
from app.core.flujo.normal import lugares  # noqa: E402
from fichas import CHARLAS  # noqa: E402

TID = "verifika_prod"
PS = K.productos(TID)
POR_ID = {str(p["id"]): p for p in PS}

SIG = {"buscar": ["que", "cantidad", "condiciones", "orden", "tope"], "producto": ["cual", "quiere_saber"],
       "comparar": ["cuales", "por"], "compatibilidad": ["cual", "con"], "envio": ["destino"],
       "cuenta": ["tope", "reparto", "destino"], "politica": ["sobre"],
       "agregar": ["que", "cantidad", "destino", "color", "condiciones", "orden"], "sacar": ["cual"],
       "cambiar": ["cual", "que", "cantidad", "destino", "color", "condiciones", "orden"], "explicar": ["pregunta"],
       "cliente": ["nombre", "localidad", "es"], "preguntar": ["que"], "nada": []}
PRINCIPAL = {"buscar": "que", "agregar": "que", "producto": "cual", "comparar": "cuales", "compatibilidad": "cual",
             "cambiar": "cual", "sacar": "cual"}
FUNCS = {"B": ["buscar", "agregar"], "AG": ["agregar"], "CA": ["cambiar"], "SA": ["sacar"], "P": ["producto"],
         "CMP": ["comparar"], "CO": ["compatibilidad"], "E": ["envio", "cuenta"], "CU": ["cuenta"], "PO": ["politica"],
         "EX": ["explicar"], "CL": ["cliente"], "NADA": ["nada"], "ORD": ["cambiar", "buscar", "agregar"]}
ALT = {"CU": ["cuenta"], "E": ["envio"], "CA": ["cambiar"]}
RUBRO_PAL = {"auriculares": ["auricular", "headset", "vincha", "casco"], "mouse": ["mouse", "raton", "mause"],
             "teclado": ["teclado"], "memoria ram": ["memoria", "ram"], "webcam": ["webcam", "camara"],
             "microfono": ["microfono", "micro"], "monitor": ["monitor", "pantalla"], "parlante": ["parlante", "altavoz"],
             "router": ["router", "wifi", "mesh", "repetidor"], "silla gamer": ["silla"], "cargador": ["cargador"],
             "almacenamiento externo": ["pendrive", "almacenamiento", "usb", "disco externo", "memoria externa"]}
NIEGA = ["no ", "sin ", "evitar", "fuera de", "excepto", "distint", "menos", "salvo", "ningun", "que no"]
BARATO = ["barat", "econom", "menor precio", "mas bajo", "precio bajo", "minimo precio"]
RESTO = ["demas", "otros", "resto", "restante", "lo que queda"]


def n(t) -> str:
    return K.n(t if isinstance(t, str) else json.dumps(t, ensure_ascii=False))


# ══ EL PYTHON, LEIDO SIN EJECUTARLO ═════════════════════════════════════════

def leer(src: str):
    """[(funcion, args, condicional)] y si hubo que arreglarlo para leerlo: "", "arreglado" o "ilegible"."""
    estado = ""
    try:
        arbol = ast.parse(src or "")
    except SyntaxError:
        try:
            arbol, estado = ast.parse(re.sub(r";\s*", "\n", src)), "arreglado"
        except SyntaxError:
            return [], "ilegible"
    llamadas, variables = [], {}

    def valor(x):
        if isinstance(x, ast.Constant):
            return x.value
        if isinstance(x, (ast.List, ast.Tuple, ast.Set)):
            return [valor(e) for e in x.elts]
        if isinstance(x, ast.Dict):
            pares = [[valor(k), valor(v)] for k, v in zip(x.keys, x.values)]
            # Una clave repetida —"sin decir" dos veces— no se pierde: queda la lista de pares.
            return pares if len({str(k) for k, _ in pares}) < len(pares) else {str(k): v for k, v in pares}
        if isinstance(x, ast.Name):
            return variables.get(x.id, x.id)
        if isinstance(x, ast.Call):
            return llamada(x, False)
        return ast.unparse(x)

    def llamada(c, cond):
        f = c.func.id if isinstance(c.func, ast.Name) else (c.func.attr if isinstance(c.func, ast.Attribute) else "")
        args = {}
        for i, a in enumerate(c.args):
            args[(SIG.get(f) or [])[i] if i < len(SIG.get(f) or []) else f"_{i}"] = valor(a)
        for kw in c.keywords:
            args[kw.arg or "_"] = valor(kw.value)
        if f in SIG:
            llamadas.append((f, args, cond))
        return args.get(PRINCIPAL.get(f, ""), args.get("_0", f))

    def recorrer(cuerpo, cond):
        for s in cuerpo:
            if isinstance(s, ast.If):
                for c in ast.walk(s.test):
                    if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id in SIG:
                        llamada(c, cond)
                recorrer(s.body, True)
                recorrer(s.orelse, True)
            elif isinstance(s, ast.Assign) and isinstance(s.value, ast.Call):
                v = llamada(s.value, cond)
                for t in s.targets:
                    if isinstance(t, ast.Name):
                        variables[t.id] = v
            elif isinstance(s, ast.Expr) and isinstance(s.value, ast.Call):
                llamada(s.value, cond)
            elif isinstance(s, (ast.For, ast.While, ast.With)):
                recorrer(s.body, True if isinstance(s, ast.While) else cond)
    recorrer(arbol.body, False)
    return llamadas, estado


# ══ LA FICHA CONTRA LO QUE DIJO ═════════════════════════════════════════════

def _lista(x) -> list:
    return x if isinstance(x, list) else ([x] if x not in (None, "") else [])


def producto_de(ref: str, mem: dict) -> dict:
    if re.fullmatch(r"M\d+", ref or ""):
        i = int(ref[1:]) - 1
        return POR_ID.get((mem.get("M") or [None] * (i + 1))[i] or "", {}) if i < len(mem.get("M") or []) else {}
    if re.fullmatch(r"L\d+", ref or ""):
        i = int(ref[1:]) - 1
        ls = mem.get("L") or []
        return POR_ID.get(ls[i][2] or "", {"categoria": ls[i][1]}) if i < len(ls) else {}
    return POR_ID.get(ref or "", {})


def mismo_producto(dicho, ref: str, mem: dict) -> tuple:
    """(p1, p2): dicho es el numero de la memoria o un nombre que lo nombra; p2, si el codigo lo identifica."""
    d = str(dicho or "").strip()
    if d == ref:
        return True, True
    p = producto_de(ref, mem)
    if not p or re.fullmatch(r"[ML]\d+", d):
        return False, False
    modelo = n(p.get("modelo")).split()
    p1 = bool(modelo) and modelo[0] in n(d)
    idt = K.identificar(d, "", TID)
    cand = [idt["producto"]] if idt["veredicto"] == "exists" else []
    return p1, any(c.get("modelo") == p.get("modelo") for c in cand)


def rubro_de(dicho, mem: dict) -> str:
    d = str(dicho or "")
    if re.fullmatch(r"[ML]\d+", d.strip()):
        return producto_de(d.strip(), mem).get("categoria", "")
    return K.solo_rubro(d, TID) or K.rubro(d, TID) or ""


def _monto(v) -> int:
    if isinstance(v, (int, float)):
        return int(v)
    m = re.search(r"([\d.,]+)\s*(millones|millon|mil|k|lucas)?", n(v))
    return K._monto(m.group(1), m.group(2) or "") if m else 0


def _reparto(v) -> list:
    if isinstance(v, dict):
        return [(K.entero(p), n(m)) for m, p in v.items()]
    out = []
    for x in _lista(v):
        if isinstance(x, dict):
            pct = next((K.entero(y) for y in x.values() if isinstance(y, (int, float))), 0)
            out.append((pct, n(" ".join(str(y) for y in x.values() if isinstance(y, str)))))
        elif isinstance(x, (list, tuple)) and len(x) == 2:
            a, b = x
            out.append((K.entero(a), n(b)) if isinstance(a, (int, float)) else (K.entero(b), n(a)))
    return out


def slots(oro: dict, f: str, a: dict, cond: bool, mem: dict, todas: list) -> list:
    """[(dato, p1, p2)]: p2 None si el dato no se ata en la fuente."""
    out = []
    texto = n(" ".join(json.dumps(v, ensure_ascii=False) for v in a.values()))
    rub = oro.get("rubro")
    if rub:
        que = a.get("que") if f != "cambiar" else (a.get("que") or "")
        p1 = any(w in n(que) for w in RUBRO_PAL.get(rub, [rub])) or rubro_de(que, mem) == rub \
            or (oro.get("resto") and any(w in n(que) for w in RESTO))
        out.append(("clase de producto", p1, rubro_de(que, mem) == rub or bool(oro.get("resto"))))
    if oro.get("que"):
        out.append(("producto de la memoria", *mismo_producto(a.get("que") or a.get("cual"), oro["que"], mem)))
    if oro.get("cual") and oro["tipo"] != "CA":
        dichos = [str(x) for x in _lista(a.get("cual") or a.get("cuales") or a.get("que"))]
        res = [max((mismo_producto(d, r, mem) for d in dichos), default=(False, False)) for r in _lista(oro["cual"])]
        out.append(("lo que senala", all(r[0] for r in res), all(r[1] for r in res)))
    if oro.get("cant") is not None:
        out.append(("cantidad", K.entero(a.get("cantidad"), 1) == oro["cant"], None))
    if oro.get("dest") and not oro.get("opt_dest"):
        d = str(a.get("destino") or "")
        gl = lugares(oro["dest"])
        dl = lugares(d)
        p1 = n(oro["dest"]).split()[0] in n(d)
        p2 = bool(gl and dl) and n(dl[0][0]) == n(gl[0][0])
        out.append(("destino", p1, p2))
    if oro.get("color"):
        out.append(("color", n(oro["color"]) in texto, None))
    if oro.get("orden") == "barato":
        o = a.get("orden")
        p1 = any(w in n(o) for w in BARATO) or any(w in n(a.get("condiciones")) for w in BARATO)
        out.append(("orden", p1, K.ORDEN.get(n(o), (0, 0))[1] == 1))
    if oro.get("tope"):
        out.append(("tope", _monto(a.get("tope")) == oro["tope"], None))
    if oro.get("reparto"):
        dicho = _reparto(a.get("reparto"))
        ok = all(any(p == pct and (medio is None or n(medio) in m) for p, m in dicho) for pct, medio in oro["reparto"])
        out.append(("pago", ok, None))
    if oro.get("conds") and not oro.get("opt_conds"):
        # Las condiciones de una clase de producto pueden ir en su busqueda o en su compra.
        conds = [str(c) for c in _lista(a.get("condiciones"))] + [str(a.get("que") or "")]
        if rub:
            conds += [str(c) for g, b, _ in todas if g in ("buscar", "agregar") and rubro_de(b.get("que"), mem) == rub
                      for c in _lista(b.get("condiciones")) + [b.get("que") or ""]]
        univ_rub = rub or (producto_de(_lista(oro.get("cual"))[0], mem).get("categoria") if oro.get("cual") else "")
        univ = [p for p in PS if p.get("categoria") == univ_rub]
        for c in oro["conds"]:
            dichas = [x for x in conds if any(w in n(x) for w in c["pal"])]
            p1 = bool(dichas) and (not c["niega"] or any(any(w in " " + n(x) for w in NIEGA) for x in dichas))
            p2 = None
            if c["campos"] and dichas:
                f2 = K.atar(dichas[0], univ, TID)
                p2 = f2.get("campo") in c["campos"] or any(x.get("campo") in c["campos"] for x in f2.get("todas", []))
            elif c["campos"]:
                p2 = False
            out.append(("condicion: " + c["pal"][0], p1, p2))
    if oro.get("pal"):
        out.append(("lo que pregunta", any(w in texto for w in oro["pal"]), None))
    if oro.get("tema"):
        temas = {t for ts in marcador._temas(" ".join(str(v) for v in a.values() if isinstance(v, str)), TID).values()
                 for t in ts}
        out.append(("tema de la politica", True, bool(temas & set(oro["tema"]))))
    if oro.get("libre"):
        out.append(("lo que nombra", any(w in texto for w in oro["libre"]), None))
    if oro.get("si"):
        out.append(("depende de otro", cond, None))
    return [(d, bool(p1), None if p2 is None else bool(p2)) for d, p1, p2 in out]


def comparar_oro(oro: dict, todas: list, mem: dict) -> dict:
    """La mejor llamada para un pedido de la ficha: {"esta", "p1", "p2", "malos", "codigo", "cual"}."""
    if oro["tipo"] == "ORD":
        baratas = [x for x in todas if x[0] in FUNCS["ORD"] and any(w in n(x[1].get("orden")) for w in BARATO)]
        todo = any(len(_lista(x[1].get("cual"))) > 1 or any(w in n(x[1].get("que") or x[1].get("cual"))
                                                             for w in ("todo", "pedido")) for x in baratas)
        ok = bool(baratas) and (todo or len(baratas) > 1)
        return {"esta": bool(baratas), "p1": ok, "p2": True, "malos": [] if ok else ["orden de todo"], "codigo": [],
                "cual": baratas[0] if baratas else None}
    funcs = FUNCS[oro["tipo"]] + (ALT.get(oro.get("alt"), []))
    mejor = None
    # LA CUENTA ES UNA SOLA aunque la diga en varias llamadas: el tope en una y el pago en otra.
    cuentas = [x for x in todas if x[0] == "cuenta"]
    junta = [("cuenta", {k: v for x in cuentas for k, v in x[1].items() if v not in (None, "", [], {})},
              any(x[2] for x in cuentas))] if len(cuentas) > 1 else []
    for x in todas + junta:
        if x[0] not in funcs:
            continue
        if oro["tipo"] == "CA" and oro.get("cual"):
            if not set(_lista(oro["cual"])) <= {str(c) for c in _lista(x[1].get("cual"))} and x[0] == "cambiar":
                continue
        s = slots(oro, x[0], x[1], x[2], mem, todas)
        puntos = sum(p1 for _, p1, _ in s)
        if mejor is None or puntos > mejor[0]:
            mejor = (puntos, x, s)
    if mejor is None:
        return {"esta": False, "p1": False, "p2": False, "malos": ["falta entero"], "codigo": [], "cual": None}
    _, x, s = mejor
    malos = [d for d, p1, _ in s if not p1]
    codigo = [d for d, p1, p2 in s if p1 and p2 is False]
    esta = not s or any(p1 for _, p1, _ in s) or oro["tipo"] in ("CU", "EX", "NADA", "CL", "PO")
    return {"esta": esta, "p1": not malos, "p2": not malos and not codigo, "malos": malos if esta else ["falta entero"],
            "codigo": codigo, "cual": x}


def expandir(oro: list) -> list:
    """Un cambio a varios renglones de la ficha es un pedido por renglon: cada uno tiene que estar."""
    out = []
    for o in oro:
        if o["tipo"] in ("CA", "SA") and isinstance(o.get("cual"), list):
            out += [{**o, "cual": c} for c in o["cual"]]
        else:
            out.append(o)
    return out


def calificar_turno(turno: dict, fila: dict) -> dict:
    pedidos = [p for p in fila.get("pedidos") or [] if isinstance(p, dict)]
    todas, ilegibles, arreglados = [], 0, 0
    for p in pedidos:
        ll, est = leer(str(p.get("python") or ""))
        ilegibles += est == "ilegible"
        arreglados += est == "arreglado"
        todas += ll
    pregunta = any(f == "preguntar" for f, _, _ in todas)
    res = []
    for o in expandir(turno["oro"]):
        r = comparar_oro(o, todas, turno["mem"])
        if o.get("preg") and pregunta and not r["p1"]:
            r = {**r, "p1": True, "p2": True, "malos": [], "pregunto": True}
        res.append((o, r))
    cuentan = [(o, r) for o, r in res if not o.get("opt") or r["p1"]]
    olvidos = [o for o, r in cuentan if not r["esta"]]
    errores = [(o, r["malos"]) for o, r in cuentan if r["esta"] and not r["p1"]]
    codigo = [(o, r["codigo"]) for o, r in cuentan if r["p1"] and r["codigo"]]
    bien = not olvidos and not errores
    usadas = {id(r["cual"]) for _, r in res if r.get("cual")}
    rubros = {o.get("rubro") for o in turno["oro"]}
    sobran = [x for x in todas if id(x) not in usadas and x[0] not in ("nada", "preguntar", "cliente")
              and not (x[0] in ("buscar", "agregar") and rubro_de(x[1].get("que"), turno["mem"]) in rubros)]
    # LA MEMORIA EN LENGUAJE COMUN: lo que senala de lo mostrado tiene que quedar nombrado.
    memo = []
    for o, r in res:
        for ref in [o.get("que")] + _lista(o.get("cual")):
            if isinstance(ref, str) and re.fullmatch(r"M\d+", ref) and r["p1"]:
                p = producto_de(ref, turno["mem"])
                comun = n(" ".join(str(x.get("en_comun") or "") for x in pedidos))
                memo.append(bool(p) and (n(p.get("modelo")).split()[0] in comun or ref.lower() in comun))
    return {"veredicto": "BIEN" if bien else ("PREGUNTO" if pregunta else "MAL SIN AVISAR"),
            "olvidos": olvidos, "errores": errores, "codigo": codigo, "sobran": sobran, "ilegibles": ilegibles,
            "arreglados": arreglados, "memoria_nombrada": memo, "n_oro": len(cuentan)}


# ══ LOS CORTES DEL MENSAJE ══════════════════════════════════════════════════

def palabras(t: str) -> list:
    return re.findall(r"[a-z0-9]+", n(t))


def cortes_oro(msg: str) -> set:
    out, i = set(), 0
    for k, trozo in enumerate(msg.split("|")):
        if k:
            out.add(i)
        i += len(palabras(trozo))
    return out


def cortes_citas(msg: str, citas: list) -> set:
    ws, out, desde = palabras(msg.replace("|", "")), set(), 0
    for c in citas:
        cw = palabras(c)[:3]
        if not cw:
            continue
        for i in range(desde, len(ws)):
            if ws[i:i + len(cw)] == cw:
                if i:
                    out.add(i)
                desde = i + 1
                break
    return out


def cerca(a: set, b: set) -> int:
    """Cuantos cortes de a tienen uno de b a una palabra o menos."""
    return sum(any(abs(x - y) <= 1 for y in b) for x in a)


# ══ EL INFORME ══════════════════════════════════════════════════════════════

def main(ver: bool = False, solo_forma: str = "") -> None:
    filas = {}
    for l in open(os.path.join(AQUI, "resultados.jsonl"), encoding="utf-8"):
        r = json.loads(l)
        if not r.get("error"):
            filas[(r["charla"], r["turno"], r["forma"])] = r
    jev = {}
    if os.path.exists(os.path.join(AQUI, "jev_cortes.jsonl")):
        for l in open(os.path.join(AQUI, "jev_cortes.jsonl"), encoding="utf-8"):
            r = json.loads(l)
            jev[(r["charla"], r["turno"])] = set(r["cortes"])
    formas = sorted({k[2] for k in filas} if not solo_forma else {solo_forma})
    turnos = [(ch["id"], t, tu) for ch in CHARLAS for t, tu in enumerate(ch["turnos"])]
    # Solo los turnos que tienen todas las formas: la comparacion es pareja.
    comunes = [(c, t, tu) for c, t, tu in turnos if all((c, t, f) in filas for f in formas)]
    print(f"turnos con todas las formas: {len(comunes)} de {len(turnos)}\n")
    for f in formas:
        cuenta = collections.Counter()
        malos, codigo = collections.Counter(), collections.Counter()
        memo, tok, ms, cort = [], [], [], [0, 0, 0]
        por_turno = collections.Counter()
        for c, t, tu in comunes:
            fila = filas[(c, t, f)]
            r = calificar_turno(tu, fila)
            cuenta[r["veredicto"]] += 1
            por_turno[(t, r["veredicto"])] += 1
            cuenta["olvidos"] += len(r["olvidos"])
            cuenta["errores"] += len(r["errores"])
            cuenta["pedidos de la ficha"] += r["n_oro"]
            cuenta["sobran"] += len(r["sobran"])
            cuenta["python ilegible"] += r["ilegibles"]
            cuenta["python arreglado"] += r["arreglados"]
            for _, ms_ in r["errores"]:
                malos.update(ms_)
            for _, cs in r["codigo"]:
                codigo.update(cs)
            memo += r["memoria_nombrada"]
            tok.append(fila["entrada"] + fila["salida"])
            ms.append(fila["ms"])
            oro_c = cortes_oro(tu["msg"])
            dicho = cortes_citas(tu["msg"], [p.get("cita", "") for p in fila["pedidos"] if isinstance(p, dict)])
            cort[0] += len(oro_c)
            cort[1] += cerca(oro_c, dicho)
            cort[2] += len(dicho) - cerca(dicho, oro_c)
            if ver and r["veredicto"] != "BIEN":
                print(f"--- {c} t{t} {f} {r['veredicto']}: {' '.join(tu['msg'].replace('|', '').split())}")
                for o in r["olvidos"]:
                    print(f"    olvido {o['tipo']} {json.dumps({k: v for k, v in o.items() if k != 'tipo'}, ensure_ascii=False)}")
                for o, m in r["errores"]:
                    print(f"    mal {o['tipo']} en {m}: {json.dumps({k: v for k, v in o.items() if k != 'tipo'}, ensure_ascii=False)}")
                for p in fila["pedidos"]:
                    if isinstance(p, dict):
                        print(f"      · {p.get('en_comun', '')}\n        {p.get('python', '')}")
        n_ = len(comunes)
        print(f"FORMA {f} · {n_} turnos")
        print(f"  BIEN {cuenta['BIEN']} · PREGUNTO {cuenta['PREGUNTO']} · MAL SIN AVISAR {cuenta['MAL SIN AVISAR']}")
        print("  por turno de la charla: " + " · ".join(
            f"t{t}: {por_turno[(t, 'BIEN')]} bien de {sum(v for (tt, _), v in por_turno.items() if tt == t)}" for t in range(3)))
        print(f"  pedidos de la ficha {cuenta['pedidos de la ficha']}: olvidados {cuenta['olvidos']}, dichos mal "
              f"{cuenta['errores']}; llamadas de mas {cuenta['sobran']}")
        print(f"  lo dicho mal, por dato: {dict(malos.most_common())}")
        print(f"  el codigo no lo ata, con la traduccion bien: {dict(codigo.most_common())}")
        print(f"  la memoria nombrada en lenguaje comun: {sum(memo)} de {len(memo)}")
        print(f"  python ilegible {cuenta['python ilegible']}, arreglado para leerlo {cuenta['python arreglado']}")
        print(f"  cortes: {cort[1]} de {cort[0]} de la ficha, {cort[2]} de mas")
        print(f"  tokens por turno {sum(tok) // max(1, n_)}, tiempo por turno {sum(ms) // max(1, n_)} ms\n")
    if jev:
        tot = [0, 0, 0]
        for c, t, tu in turnos:
            if (c, t) in jev:
                oro_c = cortes_oro(tu["msg"])
                tot[0] += len(oro_c)
                tot[1] += cerca(oro_c, jev[(c, t)])
                tot[2] += len(jev[(c, t)]) - cerca(jev[(c, t)], oro_c)
        print(f"JEV, cortes: {tot[1]} de {tot[0]} de la ficha, {tot[2]} de mas")


if __name__ == "__main__":
    a = sys.argv[1:]
    main("--ver" in a, a[a.index("--forma") + 1] if "--forma" in a else "")
