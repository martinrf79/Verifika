"""PASO 0 DE LA FICHA 93: ¿CABEN LAS COMPLEJAS EN LA FORMA DE RESPUESTA, Y LAS LLEVA LA PRIMERA TRADUCCION? (10-nov-2026)

Orden de Martin del 10-nov: antes de gastar cuota, ver con unas cien preguntas complejas si el diseño de dos pasadas
alcanza. Sin modelo. Los casos son las J, las K y las C que traen condicion, charla, varios pedidos, tope o pago: cada
turno con su agenda a mano, `agendas58.py`.

Mide dos cosas:

  1. CABE. Cada cosa que pide el cliente, pasada a una forma de la lista con sus casillas. Se mide contra la lista de la
     FICHA 93, punto 5, tal cual se escribio, y contra la lista con lo que falto sumado. Lo que no cabe es una forma o una
     casilla que falta.
  2. LA LLEVA. Por cada casilla, si la primera traduccion grabada, `separar_charlas.jsonl` etiqueta `base`, trae ese
     dato en alguna linea: la segunda pasada solo puede anexar lo que la primera no perdio. Mide el dato, no la forma.

    python3 banco_pruebas/paso0_formas.py            el informe
    python3 banco_pruebas/paso0_formas.py --ver      con cada turno que no cabe o pierde un dato
"""
import collections
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.dirname(AQUI)]
ARGS = sys.argv[1:]
TID = "verifika_prod"

# ══ LA FORMA DE RESPUESTA ═════════════════════════════════════════════════════
# forma: (casillas obligatorias, casillas que puede llevar). "si" la lleva cualquiera: depende de otra linea.
FICHA93 = {
    "ver opciones de un rubro": ({"rubro"}, {"cantidad", "orden", "condiciones"}),
    "ver la tienda entera ordenada": ({"orden"}, {"cantidad"}),
    "preguntar por un producto": ({"producto"}, {"quiere_saber"}),
    "si anda con algo": ({"producto", "con"}, set()),
    "llevar": ({"producto"}, {"cantidad", "color", "destino"}),
    "sacar": ({"renglon"}, set()),
    "cambiar un renglon": ({"renglon"}, {"cantidad", "color", "destino"}),
    "cambiar el destino del pedido": ({"destino"}, set()),
    "cuanto sale el envio": ({"destino"}, set()),
    "una regla de la tienda": ({"tema"}, set()),
    "sumar o presupuesto": (set(), {"tope", "si_pasa", "reparto"}),
    "un dato suyo": (set(), {"nombre", "localidad"}),
    "saber general": ({"pregunta"}, set()),
    "preguntar cual": ({"candidatos"}, set()),
}
# Lo que el paso 0 encontro que falta, sumado. Cada linea dice que caso lo pidio.
NUEVA = {k: (set(o), set(p)) for k, (o, p) in FICHA93.items()}
NUEVA["ver opciones de un rubro"][1].add("entre_lo_mostrado")        # C27, K10, K17: "de esos, el mas barato"
NUEVA["preguntar por un producto"][1].update({"color", "afirma"})    # C28, C53: "en negro"; C04, C39: "es inalambrico, no?"
NUEVA["una regla de la tienda"][1].add("afirma")                     # C12, C40, K13, K14: "tienen 50 off en todo"
NUEVA["cambiar un renglon"][1].add("producto")                       # K20: "el teclado era una memoria"
NUEVA["un dato suyo"][1].update({"es", "equipo"})                    # C13, C41: revendedor, jubilado; C30, C37: su equipo
NUEVA["llevar el resto de la lista"] = (set(), {"cantidad", "destino"})   # K02, K07, K08, K09: "los otros dos a Posadas"
NUEVA["rehacer el pedido"] = ({"lineas"}, set())                     # K21: "son 7, va asi"
NUEVA["otro orden para todo el pedido"] = ({"orden"}, set())         # AR12 de la plantilla; ninguna de estas lo usa
NUEVA["corrige lo que dijo"] = (set(), set())                        # C33, C55, K11: normal.lo_corregido lo usa
NUEVA["saludo o charla sin pedido"] = (set(), set())                 # K07, K09, K10, K11, C58
NUEVA["que vende la tienda"] = (set(), set())                        # K19
NUEVA["fuera de tema"] = (set(), set())                              # C57
NUEVA["hablar con una persona"] = (set(), set())


def casos() -> list:
    """Los turnos complejos: todas las J y las K, y las C con algo mas que una sola pregunta simple."""
    from banco_pruebas.agendas58 import AGENDAS
    out = []
    for cid, ags in AGENDAS.items():
        for n, ag in enumerate(ags):
            if cid[0] in "JK" or complejidad(ag) >= 1:
                out.append((cid, n, ag))
    return out


def complejidad(ag: dict) -> int:
    ps, s = ag["preguntas"], 0
    s += len(ps) >= 2
    for p in ps:
        s += sum(bool(p.get(k)) for k in ("si", "tope", "reparto", "saca", "cambia", "entre_lo_mostrado", "afirma",
                                          "reemplaza"))
        s += p.get("orden", "nada") != "nada"
        prods = [p.get("producto")] + [x.get("producto") for x in p.get("agrega") or []]
        s += any(str(v).startswith(("M-", "L-", "['M")) for v in prods)
    return s + bool(ag.get("cliente"))


# ══ DE LA AGENDA A MANO A LA FORMA ════════════════════════════════════════════

def formas(ag: dict) -> list:
    """[{forma, casillas, obj, modos}]: lo que pide el cliente en el turno, en la forma de respuesta. "obj" es lo que
    tiene que reconocerse en una linea de la primera traduccion, en el formato de `separar_charlas._es`."""
    out = []
    todos = {"ver", "pregunta", "llevar", "dato"}
    for p in ag.get("preguntas") or []:
        a, si = p.get("accion"), ({"si": p["si"]} if p.get("si") else {})
        if a == "buscar":
            c = {k: p[k] for k in ("cantidad", "orden", "condiciones") if p.get(k) not in (None, "nada", [], 1)}
            if p.get("entre_lo_mostrado") is True:
                c["entre_lo_mostrado"] = True
            if p.get("orden_cita"):
                c["orden_cita"] = p["orden_cita"]
            if p["rubro"] == "toda la tienda":
                out.append({"forma": "ver la tienda entera ordenada", "casillas": {**c, **si}, "obj": "tienda",
                            "modos": {"ver", "pregunta", "llevar"}})
            elif p["rubro"] == "el pedido":
                out.append({"forma": "otro orden para todo el pedido", "casillas": {**c, **si}, "obj": "",
                            "modos": todos})
            else:
                out.append({"forma": "ver opciones de un rubro", "casillas": {"rubro": p["rubro"], **c, **si},
                            "obj": p["rubro"], "modos": {"ver", "pregunta", "llevar"}})
        elif a == "producto":
            xs = p["producto"] if isinstance(p["producto"], list) else [p["producto"]]
            if len(xs) > 1:
                out.append({"forma": "preguntar cual", "casillas": {"candidatos": xs}, "obj": "lista:" + ",".join(xs),
                            "modos": {"pregunta", "ver", "llevar"}})
                continue
            c = {"producto": xs[0], **si}
            if p.get("quiere_saber") not in (None, "precio"):
                c["quiere_saber"] = p["quiere_saber"]
            c.update({k: p[k] for k in ("color", "afirma") if p.get(k)})
            out.append({"forma": "preguntar por un producto", "casillas": c, "obj": str(xs[0]),
                        "modos": {"pregunta", "ver", "llevar"}})
        elif a == "compatibilidad":
            out.append({"forma": "si anda con algo", "casillas": {"producto": p["producto"], "con": p["con"]},
                        "obj": str(p["producto"]), "modos": {"pregunta", "llevar"}})
        elif a == "comprar":
            if p.get("reemplaza"):
                out.append({"forma": "rehacer el pedido", "casillas": {"lineas": len(p.get("agrega") or [])},
                            "obj": "", "modos": {"llevar"}})
            for x in p.get("agrega") or []:
                prods = x["producto"] if isinstance(x["producto"], list) else [x["producto"]]
                for pr in prods:
                    c = {k: x[k] for k in ("cantidad", "color", "destino") if x.get(k) not in (None, 1)}
                    if str(pr).startswith("los otros"):
                        out.append({"forma": "llevar el resto de la lista", "casillas": {**c, **si},
                                    "obj": "", "modos": {"llevar", "ver", "pregunta"}})
                    else:
                        out.append({"forma": "llevar", "casillas": {"producto": pr, **c, **si}, "obj": str(pr),
                                    "modos": {"llevar", "ver", "pregunta"}})
            for x in p.get("saca") or []:
                out.append({"forma": "sacar", "casillas": {"renglon": x}, "obj": x, "modos": {"llevar"}})
            for x in p.get("cambia") or []:
                c = {k: v for k, v in x.items() if k != "es"}
                out.append({"forma": "cambiar un renglon", "casillas": {"renglon": x["es"], **c}, "obj": x["es"],
                            "modos": {"llevar"}})
            if p.get("reparto"):
                out.append({"forma": "sumar o presupuesto", "casillas": {"reparto": p["reparto"]}, "obj": "",
                            "modos": todos})
        elif a == "cuenta":
            c = {k: p[k] for k in ("tope", "si_pasa", "reparto") if p.get(k)}
            out.append({"forma": "sumar o presupuesto", "casillas": c, "obj": "", "modos": todos})
        elif a == "politica":
            c = {"tema": p["tema"], **({"afirma": p["afirma"]} if p.get("afirma") else {})}
            out.append({"forma": "una regla de la tienda", "casillas": c, "obj": f"tema:{p['tema']}",
                        "modos": {"pregunta", "dato"}})
        elif a == "envio":
            out.append({"forma": "cuanto sale el envio", "casillas": {"destino": p["destino"]}, "obj": "",
                        "modos": {"pregunta", "llevar", "ver"}})
        elif a == "explicar":
            out.append({"forma": "saber general", "casillas": {"pregunta": p["pregunta"]}, "obj": "",
                        "modos": {"pregunta"}})
        elif a == "otro":
            que = p.get("que")
            if que == "dato":
                continue                       # lo que dice de si va en "cliente", abajo
            f = {"saludo": "saludo o charla sin pedido", "corrige": "corrige lo que dijo", "catalogo":
                 "que vende la tienda", "fuera_de_tema": "fuera de tema", "humano": "hablar con una persona"}[que]
            out.append({"forma": f, "casillas": {}, "obj": "", "modos": todos})
    if ag.get("cliente"):
        out.append({"forma": "un dato suyo", "casillas": dict(ag["cliente"]), "obj": "", "modos": {"dato"}})
    return out


def cabe(f: dict, lista: dict) -> list:
    """Lo que falta en la lista para esta forma: [] si cabe."""
    if f["forma"] not in lista:
        return [f"forma: {f['forma']}"]
    obl, puede = lista[f["forma"]]
    tiene = set(f["casillas"]) - {"si", "orden_cita"}
    return ([f"casilla: {f['forma']} · {c}" for c in sorted(tiene - obl - puede)]
            + [f"obligatoria vacia: {f['forma']} · {c}" for c in sorted(obl - set(f["casillas"]))])


# ══ ¿LA PRIMERA TRADUCCION LLEVA CADA DATO? ═══════════════════════════════════

_VACIAS = set("que sea sean los las del para con mas menos posible posibles una uno unos todo toda".split())


def _raices(t: str) -> list:
    """Las palabras que cargan el dato, cortadas a cinco letras. Las cortas cuentan si son siglas o numeros: JBL, 50."""
    from app.core.flujo import catalogo as K
    return [w[:5] for w in K.n(t).split() if (len(w) >= 3 or any(ch.isdigit() for ch in w)) and w not in _VACIAS]


# Como dice el cliente cada porcentaje del pago, para que la vara lea "setenta treinta" o "mitad y mitad".
_PORC = {50: ("50", "mitad", "cincuenta"), 70: ("70", "setenta"), 30: ("30", "treinta"), 100: ("100", "todo", "total")}


def _reparto(v: list, t: str) -> bool:
    """El pago partido esta si estan los medios y los porcentajes; el que completa el cien puede no decirse."""
    medios = all(any(r in t for r in _raices(x["medio"])) for x in v)
    dichos = [any(re.search(rf"\b{w}\b", t) for w in _PORC.get(x["porcentaje"], (str(x["porcentaje"]),))) for x in v]
    return medios and sum(dichos) >= len(v) - 1 if len(v) > 1 else any(r in t for r in _raices(v[0]["medio"]))


def lleva(f: dict, salida: dict, texto: str) -> dict:
    """{casilla: nivel} por cada dato de la forma: "linea" si esta en la linea que nombra la cosa; "turno" si esta en
    otra parte de la traduccion del turno; "no" si el cliente lo dijo y la traduccion lo perdio; "otra" si el cliente no
    lo dijo con esas palabras —un tema, un rubro dicho por rodeo, lo de un turno anterior—, que es trabajo de la segunda
    pasada o de la memoria, no de la primera. "objeto" es lo que la linea nombra; "modo", si lo nombra con el modo que
    lleva a esa forma. Lo que senala de la libreta es siempre de la primera: tiene la libreta delante."""
    en_linea = _lleva(f, salida, True)
    en_turno = _lleva(f, salida, False)
    dijo = _lleva(f, {"lineas": [{"texto": texto, "cosa": texto, "modo": next(iter(f["modos"]))}], "todo": texto}, False)
    if re.match(r"^(lista:)?[MLR]-\d+", f["obj"]):
        dijo["objeto"] = True
    dijo["modo"] = dijo.get("objeto", True)
    return {c: "linea" if en_linea[c] else "turno" if en_turno.get(c) else "no" if dijo.get(c) else "otra"
            for c in en_linea}


def _lleva(f: dict, salida: dict, linea: bool) -> dict:
    from banco_pruebas import separar_charlas as S
    from app.core.flujo import catalogo as K
    ls, todo = salida.get("lineas") or [], str(salida.get("todo") or "")
    txt = lambda l: K.n(" ".join(str(l.get(k) or "") for k in ("texto", "cosa", "tema", "destino", "si", "senala")))  # noqa: E731
    obj = f["obj"]
    if obj == "tienda":
        suyas = [l for l in ls if not K.rubro(str(l.get("cosa") or ""), TID)]
    elif obj:
        suyas = [l for l in ls if S._es({"modo": {"ver", "pregunta", "llevar", "dato"}, "que": obj}, l, todo)]
    else:
        suyas = list(ls)
    if f["forma"] == "llevar el resto de la lista" and f["casillas"].get("destino"):
        d = K.n(f["casillas"]["destino"]).split()[0][:5]
        suyas = [l for l in ls if re.search(rf"\b{d}", K.n(f"{l.get('destino')} {l.get('texto')}"))]
    if not suyas and f["forma"] == "cuanto sale el envio":
        suyas = list(ls)
    out = {}
    if obj:
        out["objeto"] = bool(suyas)
    out["modo"] = any(l.get("modo") in f["modos"] for l in suyas) if suyas else False
    todo_txt = " ".join(txt(l) for l in ls) + " " + K.n(todo)
    alla = (" ".join(txt(l) for l in suyas) + " " + K.n(todo)) if linea else todo_txt
    for c, v in f["casillas"].items():
        if c in ("rubro", "producto", "renglon", "tema", "candidatos", "lineas"):
            continue                                            # ya los mide "objeto"
        if c == "cantidad":
            cs = [l.get("cantidad") for l in suyas if l.get("cantidad")]
            out[c] = v in cs or sum(cs) == v or bool(re.search(rf"\b{v}\b", alla)) or (
                K.n({2: "dos", 3: "tres", 4: "cuatro"}.get(v, "#")) in alla.split())
        elif c in ("destino", "color", "con", "nombre", "localidad"):
            out[c] = K.n(str(v)).split()[0][:5] in alla
        elif c == "orden":
            cita = f["casillas"].get("orden_cita")
            raiz = _raices(cita) if cita else [K.n(v).split()[-1][:5]]
            out[c] = any(r in alla for r in raiz)
        elif c == "condiciones":
            out[c] = all(any(r in alla for r in _raices(x)) for x in v)
        elif c in ("afirma", "quiere_saber", "es", "equipo", "pregunta"):
            out[c] = any(r in alla for r in _raices(str(v)))
        elif c == "reparto":
            out[c] = _reparto(v, todo_txt)
        elif c == "tope":
            nums = re.findall(r"\d+", str(v))
            limpio = todo_txt.replace(".", "")
            out[c] = all(re.search(rf"\b{n}\b", limpio) or (len(n) > 3 and n[:-3] in limpio) for n in nums)
        elif c == "si_pasa":
            out[c] = any(r in alla for r in _raices(str(v)))
        elif c == "si":
            out[c] = any(str(l.get("si") or "").strip() for l in ls) or " si " in f" {K.n(todo)} "
        elif c == "entre_lo_mostrado":
            out[c] = any(str(l.get("senala") or "").upper().startswith("M") for l in suyas) or any(
                w in alla.split() for w in ("esos", "estos", "esas", "estas", "mostraste", "pasaste"))
    return out


# ══ EL INFORME ════════════════════════════════════════════════════════════════

def main():
    from banco_pruebas.plantilla_venta import llenar as LL
    from banco_pruebas.agendas58 import AGENDAS  # noqa: F401
    LL.entorno()
    grab = {}
    for r in map(json.loads, open(os.path.join(AQUI, "separar_charlas.jsonl"), encoding="utf-8")):
        if r["etiqueta"] == "base" and "error" not in r["salida"]:
            grab[(r["charla"], r["turno"])] = r
    cs = casos()
    print(f"PASO 0 · {len(cs)} turnos complejos: {sum(c[0][0] == 'K' for c in cs)} K, {sum(c[0][0] == 'J' for c in cs)} J, "
          f"{sum(c[0][0] == 'C' for c in cs)} C. Sin modelo.\n")

    nf = 0
    falta93, faltaN = collections.Counter(), collections.Counter()
    cabe93 = cabeN = 0
    lleva_c, lleva_n = collections.Counter(), collections.Counter()
    turnos_llevan = turnos_linea = turnos_primera = 0
    pierde_turno = []
    por_forma = collections.Counter()
    for cid, n, ag in cs:
        fs = formas(ag)
        nf += len(fs)
        g93 = [x for f in fs for x in cabe(f, FICHA93)]
        gN = [x for f in fs for x in cabe(f, NUEVA)]
        falta93.update(set(g93))
        faltaN.update(set(gN))
        cabe93 += not g93
        cabeN += not gN
        por_forma.update(f["forma"] for f in fs)
        r = grab.get((cid, n))
        perdidas = []
        if r:
            for f in fs:
                for c, nivel in lleva(f, r["salida"], r["texto"]).items():
                    lleva_n[c] += 1
                    lleva_c[(c, nivel)] += 1
                    if nivel != "linea":
                        perdidas.append(f"{ {'turno': 'EN OTRA LINEA', 'no': 'PIERDE', 'otra': 'NO LO DIJO ASI'}[nivel]} "
                                        f"{f['forma']} · {c} = "
                                        f"{f['casillas'].get(c, f['obj'])}")
            turnos_llevan += not any(p.startswith("PIERDE") for p in perdidas)
            turnos_linea += not any(p.startswith(("PIERDE", "EN OTRA")) for p in perdidas)
            turnos_primera += not any(p.startswith(("PIERDE", "EN OTRA", "NO LO")) for p in perdidas)
            if perdidas:
                pierde_turno.append((cid, n, r, perdidas))
        if "--ver" in ARGS and g93:
            print(f"  NO CABE {cid} T{n + 1}: {'; '.join(sorted(set(g93)))}")

    print(f"1. CABE · {nf} cosas pedidas en {len(cs)} turnos")
    print(f"   con la lista de la FICHA 93 tal cual: {cabe93} de {len(cs)} turnos caben enteros")
    for k, v in falta93.most_common():
        print(f"     falta {k}: {v} turnos")
    print(f"   con lo que falto sumado, {len(NUEVA)} formas: {cabeN} de {len(cs)}")
    for k, v in faltaN.most_common():
        print(f"     falta {k}: {v} turnos")
    print("   las formas que se usan: " + ", ".join(f"{k} {v}" for k, v in por_forma.most_common()))

    print(f"\n2. LA LLEVA · la primera traduccion grabada, base, {sum(1 for c in cs if (c[0], c[1]) in grab)} turnos")
    print(f"   turnos sin perder nada de lo que dijo el cliente: {turnos_llevan}; ademas con cada dato en su linea: "
          f"{turnos_linea}; y sin nada que pida la segunda pasada o la memoria: {turnos_primera}")
    print(f"     {'casilla':18} {'en su linea':>11} {'en otra':>8} {'perdido':>8} {'no lo dijo asi':>15}")
    for c in sorted(lleva_n, key=lambda c: (lleva_c[(c, 'linea')] / lleva_n[c], c)):
        print(f"     {c:18} {lleva_c[(c, 'linea')]:11} {lleva_c[(c, 'turno')]:8} {lleva_c[(c, 'no')]:8} "
              f"{lleva_c[(c, 'otra')]:15}   de {lleva_n[c]}")
    if "--ver" in ARGS:
        for cid, n, r, ps in pierde_turno:
            print(f"\n  {cid} T{n + 1}: {r['texto'][:200]}")
            for p in ps:
                print(f"    {p}")
            for l in r["salida"].get("lineas") or []:
                print(f"    · {l.get('modo'):8} {l.get('texto')} | cosa {l.get('cosa')} | tema {l.get('tema')} | "
                      f"{l.get('cantidad')} | {l.get('destino')} | si {l.get('si')} | senala {l.get('senala')}")
            if r["salida"].get("todo"):
                print(f"    todo: {r['salida']['todo']}")


if __name__ == "__main__":
    main()
