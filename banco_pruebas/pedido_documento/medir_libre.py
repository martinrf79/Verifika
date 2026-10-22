"""LO QUE CONSERVA EL PASO LIBRE — por lengua, sin modelo (23-oct-2026).

Lo importante de un pedido no son las palabras sueltas sino lo que va junto: que esos dos mouse van a Rosario, que el
auricular no tiene que ser chino. Por eso se mide por PARES: lo que pide, con su cantidad, su destino, su condicion, su
color o su orden. Un par se conserva si hay una unidad de la salida que tiene las dos cosas y ningun otro destino del
mensaje: un renglon en lenguaje natural, con el titulo que lo encabeza; un objeto en JSON o un diccionario o una llamada
en Python, con lo que hereda de los que lo contienen.

Lo correcto sale de las fichas de `pregunta_razonada` y, para las 58 y las K, de las agendas a mano de `agendas58.py`.
Ademas: los precios o modelos que la salida trae y el mensaje y la memoria no, cuantas veces marca una duda, los nombres
que mas repite en JSON y en Python, y los tokens.

    python3 banco_pruebas/pedido_documento/medir_libre.py [--ver]
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
sys.path.insert(0, os.path.join(REPO, "banco_pruebas", "pregunta_razonada"))
os.chdir(REPO)
os.environ.pop("GEMINI_API_KEY_PROD", None)
from calificar import n, RUBRO_PAL, BARATO, producto_de, PS  # noqa: E402
from fichas import CHARLAS  # noqa: E402
from banco_pruebas.agendas58 import AGENDAS  # noqa: E402
from app.core.flujo import agenda as A  # noqa: E402

NUMEROS = {1: ["1", "un", "una", "uno"], 2: ["2", "dos"], 3: ["3", "tres"], 4: ["4", "cuatro"], 5: ["5", "cinco"],
           6: ["6", "seis"], 7: ["7", "siete"]}
DUDA = ["pregunt", "aclar", "confirm", "duda", "ambig", "no especific", "no queda claro", "no indica", "no dice",
        "consultar al cliente", "verificar con el cliente"]


# ══ LO CORRECTO, EN PARES ═══════════════════════════════════════════════════

def que_palabras(o: dict, mem: dict) -> list:
    if o.get("rubro"):
        return RUBRO_PAL.get(o["rubro"], [o["rubro"]])
    ref = o.get("que") if isinstance(o.get("que"), str) else None
    ref = ref or (o["cual"] if isinstance(o.get("cual"), str) else None)
    if ref and re.fullmatch(r"[ML]\d+", ref):
        p = producto_de(ref, mem)
        palabras = [n(p.get("modelo")).split()[0]] if p.get("modelo") else []
        return palabras + RUBRO_PAL.get(p.get("categoria"), [])
    return []


def pares_fichas(tu: dict) -> list:
    """[(tipo, palabras de lo que pide, palabras del otro dato)]."""
    out = []
    for o in tu["oro"]:
        if o["tipo"] not in ("AG", "CA", "B") or o.get("opt"):
            continue
        refs = o["cual"] if isinstance(o.get("cual"), list) else [None]
        for r in refs:
            oo = {**o, "cual": r} if r else o
            q = que_palabras(oo, tu["mem"])
            if not q:
                continue
            if o.get("dest"):
                out.append(("destino", q, [n(o["dest"]).replace(" capital", "")]))
            if o.get("cant") is not None:
                out.append(("cantidad", q, NUMEROS.get(o["cant"], [str(o["cant"])])))
            for c in o.get("conds") or []:
                out.append(("condicion", q, c["pal"]))
            if o.get("color"):
                out.append(("color", q, [n(o["color"])]))
            if o.get("orden") == "barato":
                out.append(("orden", q, BARATO))
    return out


def pares_agenda(ag) -> list:
    out = []
    for p in A.preguntas(ag):
        if p.get("accion") == "buscar" and p.get("rubro") in RUBRO_PAL:
            q = RUBRO_PAL[p["rubro"]]
            if p.get("cantidad"):
                out.append(("cantidad", q, NUMEROS.get(int(p["cantidad"]), [str(p["cantidad"])])))
            for c in p.get("condiciones") or []:
                ws = [w for w in n(c).split() if len(w) > 3 and w not in ("sea", "que", "sean")]
                if ws:
                    out.append(("condicion", q, ws[-1:]))
            if "barat" in n(p.get("orden")):
                out.append(("orden", q, BARATO))
        if p.get("accion") == "comprar":
            for a in p.get("agrega") or []:
                if not isinstance(a, dict) or not isinstance(a.get("producto"), str):
                    continue
                prod = a["producto"]
                if re.fullmatch(r"[MLR]-\d+", prod) or "otro" in n(prod):
                    continue
                q = RUBRO_PAL.get(prod) or [w for w in n(prod).split() if len(w) > 2][:1]
                if not q:
                    continue
                if a.get("destino"):
                    out.append(("destino", q, [n(a["destino"]).split(",")[0].replace(" capital", "").strip()]))
                if a.get("cantidad"):
                    out.append(("cantidad", q, NUMEROS.get(int(a["cantidad"]), [str(a["cantidad"])])))
    return out


# ══ LAS UNIDADES DE CADA SALIDA ═════════════════════════════════════════════

def _sin_cerco(t: str) -> str:
    return re.sub(r"^```\w*\s*|\s*```\s*$", "", t.strip())


def unidades_comun(t: str) -> list:
    out, titulo = [], ""
    for linea in t.splitlines():
        l = linea.strip()
        if not l:
            titulo = ""
            continue
        if l.endswith(":") or l.startswith("#") or re.fullmatch(r"\*\*[^*]+\*\*:?", l):
            titulo = l
            continue
        out += [f"{titulo} {s}" for s in re.split(r"(?<=[.;])\s+", l)]
    return out


def unidades_json(t: str) -> list:
    try:
        d = json.loads(_sin_cerco(t))
    except ValueError:
        return unidades_comun(t)
    out = []

    def propio(x) -> str:
        if isinstance(x, dict):
            return " ".join(f"{k} {v}" if not isinstance(v, (dict, list)) else
                            (k + " " + " ".join(str(e) for e in v if not isinstance(e, (dict, list))))
                            for k, v in x.items())
        return ""

    def recorrer(x, herencia: str):
        if isinstance(x, dict):
            u = f"{herencia} {propio(x)}"
            out.append(u)
            for v in x.values():
                recorrer(v, u)
        elif isinstance(x, list):
            for e in x:
                recorrer(e, herencia) if isinstance(e, (dict, list)) else None
    recorrer(d, "")
    return out


def unidades_python(t: str) -> list:
    try:
        arbol = ast.parse(_sin_cerco(t))
    except SyntaxError:
        return unidades_comun(t)
    out = []

    def propio(nodo) -> str:
        hijos = list(nodo.keys) + list(nodo.values) if isinstance(nodo, ast.Dict) else \
            list(nodo.args) + [k.value for k in nodo.keywords] + [ast.Constant(k.arg) for k in nodo.keywords if k.arg]
        if isinstance(nodo, ast.Call):
            hijos.append(ast.Constant(ast.unparse(nodo.func)))
        partes = []
        for h in hijos:
            if h is None:
                continue
            if isinstance(h, (ast.Constant, ast.Name, ast.Attribute)):
                partes.append(str(getattr(h, "value", None) if isinstance(h, ast.Constant) else ast.unparse(h)))
            elif isinstance(h, (ast.List, ast.Tuple)):
                partes += [ast.unparse(e) for e in h.elts if not isinstance(e, (ast.Dict, ast.Call))]
        return " ".join(partes)

    def recorrer(nodo, herencia: str):
        if isinstance(nodo, (ast.Dict, ast.Call)):
            u = f"{herencia} {propio(nodo)}"
            out.append(u)
            herencia = u
        for h in ast.iter_child_nodes(nodo):
            recorrer(h, herencia)
    recorrer(arbol, "")
    return out


UNIDADES = {"comun": unidades_comun, "json": unidades_json, "python": unidades_python}


def tiene(u: str, palabras: list) -> bool:
    return any(re.search(rf"(?<![a-z0-9]){re.escape(n(w))}", u) for w in palabras)


def conserva(unidades: list, par: tuple, destinos: list) -> bool:
    tipo, q, otro = par
    for u in map(n, unidades):
        if tiene(u, q) and tiene(u, otro):
            if tipo == "destino" and any(tiene(u, [d]) for d in destinos if d not in otro):
                continue
            return True
    return False


# ══ INVENTO, DUDA Y NOMBRES ═════════════════════════════════════════════════

MODELOS = {w for p in PS for w in n(p.get("modelo")).split() if re.search(r"\d", w) and len(w) > 2}


def plata(t: str) -> set:
    t = re.sub(r"(\d+)\s*(mil|lucas|k)\b", lambda m: str(int(m.group(1)) * 1000), n(t))
    return {int(x.replace(".", "")) for x in re.findall(r"\d{1,3}(?:\.\d{3})+|\d{4,}", t)}


def invento(salida: str, base: str) -> list:
    sale = n(salida)
    otros = [m for m in MODELOS if re.search(rf"\b{re.escape(m)}\b", sale) and not re.search(rf"\b{re.escape(m)}\b", n(base))]
    return sorted(plata(salida) - plata(base)) + otros


def nombres(t: str, lengua: str) -> list:
    if lengua == "json":
        try:
            d = json.loads(_sin_cerco(t))
        except ValueError:
            return []
        out = []

        def r(x):
            if isinstance(x, dict):
                out.extend(x.keys())
                [r(v) for v in x.values()]
            elif isinstance(x, list):
                [r(e) for e in x]
        r(d)
        return out
    if lengua == "python":
        try:
            arbol = ast.parse(_sin_cerco(t))
        except SyntaxError:
            return []
        return [x.name for x in ast.walk(arbol) if isinstance(x, ast.FunctionDef)] + \
               [ast.unparse(x.func) for x in ast.walk(arbol) if isinstance(x, ast.Call)]
    return []


def main(ver: bool = False) -> None:
    filas = [r for r in map(json.loads, open(os.path.join(AQUI, "libre.jsonl"), encoding="utf-8")) if not r.get("error")]
    oro = {}
    for ch in CHARLAS:
        for t, tu in enumerate(ch["turnos"]):
            oro[f"{ch['id']}-t{t}"] = pares_fichas(tu)
    for cid, ags in AGENDAS.items():
        for t, ag in enumerate(ags):
            oro.setdefault(f"{cid}-t{t}", pares_agenda(ag))
    for lengua in ("comun", "json", "python"):
        fs = [r for r in filas if r["lengua"] == lengua]
        cuenta, por_tipo = collections.Counter(), collections.defaultdict(lambda: [0, 0])
        inventos, dudas, vocab, ilegible = [], 0, collections.Counter(), 0
        for r in fs:
            pares = oro.get(r["id"], [])
            destinos = sorted({d for tp, _, ds in pares if tp == "destino" for d in ds})
            us = UNIDADES[lengua](r["salida"])
            if lengua != "comun" and us == unidades_comun(r["salida"]):
                ilegible += 1
            perdidos = [p for p in pares if not conserva(us, p, destinos)]
            for p in pares:
                por_tipo[p[0]][1] += 1
                por_tipo[p[0]][0] += p not in perdidos
            cuenta["pares"] += len(pares)
            cuenta["conservados"] += len(pares) - len(perdidos)
            cuenta["turnos con pares"] += bool(pares)
            cuenta["turnos enteros"] += bool(pares) and not perdidos
            inv = invento(r["salida"], r["memoria"] + " " + r["mensaje"])
            inventos += [(r["id"], inv)] if inv else []
            dudas += any(w in n(r["salida"]) for w in DUDA)
            vocab.update(set(nombres(r["salida"], lengua)))
            cuenta["sale"] += r["sale"]
            cuenta["ms"] += r["ms"]
            if ver and perdidos:
                print(f"--- {lengua} {r['id']}: {r['mensaje'][:160]}")
                for p in perdidos:
                    print(f"    perdio {p[0]}: {p[1][0]} + {p[2][0]}")
        print(f"\n{lengua.upper()} · {len(fs)} salidas")
        print(f"  pares conservados {cuenta['conservados']} de {cuenta['pares']}; turnos con todo conservado "
              f"{cuenta['turnos enteros']} de {cuenta['turnos con pares']}")
        print("  por tipo: " + " · ".join(f"{k} {a} de {b}" for k, (a, b) in sorted(por_tipo.items())))
        print(f"  con un precio o un modelo que no estaba: {len(inventos)}" +
              (f", p. ej. {inventos[:3]}" if inventos else ""))
        print(f"  marca una duda o algo a confirmar: {dudas} de {len(fs)}")
        if lengua != "comun":
            print(f"  no se pudo leer como {lengua}: {ilegible}")
            print(f"  nombres mas repetidos, en cuantas salidas: {vocab.most_common(15)}")
        print(f"  tokens de salida por mensaje {cuenta['sale'] // max(1, len(fs))}, tiempo {cuenta['ms'] // max(1, len(fs))} ms")


if __name__ == "__main__":
    main("--ver" in sys.argv)
