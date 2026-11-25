"""LA FUNCION QUE DICE QUE HAY Y QUE NO HAY (25-nov-2026). Ver el plan 4 de lab/plan.md.

`existe(tramo)` -> ("hay" | "no_hay" | "dudoso", razon). Todo sale de la fuente de la tienda: el vocabulario del catalogo,
los alias de los rubros y `no_vendidas.json`. Dudoso sigue como hay: no se dice que no hay sin una razon de la fuente.

    python3 lab/existe.py         # mide sobre los pedidos etiquetados
    python3 lab/existe.py --ver   # ademas, cada falla
"""
import collections, json, os, re, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
_argv, sys.argv = sys.argv, ["x"]
import busqueda as B  # noqa: E402
import tramos as TR  # noqa: E402
sys.argv = _argv

X, F = B.X, B.F
nrm = F.nrm
PALABRA = re.compile(r"[a-z0-9]+")
UNIDAD = (r"(gb|tb|gigas?|teras?|w|hz|mhz|pulgadas|mil|lucas|pesos|metros|mts|m|meses|anos|años|k|mm|cm|unidades|"
          r"articulos|artículos)")


def _vocabulario():
    vs = set()
    for k, fs in B.MODELOS.items():
        for f in fs:
            for v in f.values():
                vs |= set(PALABRA.findall(nrm(str(v))))
    for k, v in F.VISTA.items():
        for x in v.values():
            vs |= set(PALABRA.findall(nrm(" ".join(map(str, x)) if isinstance(x, list) else str(x))))
    for r, al in B.ALIAS.items():
        for x in [r] + al:
            vs |= set(PALABRA.findall(nrm(x)))
    return vs


VOC = _vocabulario()
RUBROS = sorted({nrm(x) for r, al in B.ALIAS.items() for x in [r] + al} | {nrm(k[0]) for k in B.MODELOS}, key=len,
                reverse=True)
MARCAS = {nrm(k[1]) for k in B.MODELOS}
MODELOS = sorted({nrm(k[2]) for k in B.MODELOS} | {w for k in B.MODELOS for w in PALABRA.findall(nrm(k[2]))
                                                    if re.search(r"\d", w) and len(w) >= 3}, key=len, reverse=True)
NO_VENDIDAS = sorted(json.load(open(os.path.join(TR.DATOS, "no_vendidas.json"), encoding="utf-8"))["no_vendidas"],
                     key=len, reverse=True)


def _distancia(a, b, tope):
    if abs(len(a) - len(b)) > tope:
        return tope + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > tope:
            return tope + 1
        prev = cur
    return prev[-1]


def conocida(w):
    """Si la palabra es de la tienda, o difiere en una o dos letras de una que lo es: un error de tipeo."""
    if w in VOC:
        return True
    if re.search(r"\d", w):
        return False  # en un codigo, una cifra distinta es otro modelo: 5070 no es 4070
    tope = 1 if len(w) < 6 else 2
    return len(w) > 3 and any(_distancia(w, v, tope) <= tope for v in VOC if abs(len(v) - len(w)) <= tope)


def _frase(t, f):
    return re.search(r"(?<![a-z0-9])" + re.escape(f) + r"(?![a-z0-9])", t) is not None


def lo_pedido(tramo):
    """Regla 1: lo que sigue a "para" describe el uso, no lo que se pide."""
    return re.split(r"\b(?:para|pa)\b", tramo, maxsplit=1, flags=re.I)[0]


def existe(tramo, aislado=True):
    """`aislado`: el tramo trae solo lo pedido. Si trae mas, destinos, nombres o la frase entera, la regla de los nombres
    propios no se aplica: medido el 25-nov, sobre las filas enteras de Luna da 27 falsas alarmas."""
    # 237.000 y 3,1415 son plata o decimales: se juntan las cifras antes de leer, y quedan fuera de los codigos.
    pedido = re.sub(r"(?<=\d)[.,](?=\d)", "", lo_pedido(tramo))
    t = nrm(pedido)
    nombra_rubro = any(_frase(t, r) for r in RUBROS)
    for nv in NO_VENDIDAS:
        if _frase(t, nrm(nv)) and not nombra_rubro:
            return "no_hay", f"no se vende: {nv}"
    for m in PALABRA.finditer(t):
        w = m.group(0)
        if not re.search(r"\d", w):
            continue
        sigue = t[m.end():m.end() + 12].strip()
        if re.fullmatch(r"\d+" + UNIDAD, w) or re.match(UNIDAD + r"(?![a-z])", sigue):
            continue
        if w.isdigit() and not 3 <= len(w) <= 4:
            continue
        if not conocida(w):
            return "no_hay", f"codigo que la tienda no trae: {w}"
    for i, m in enumerate(re.finditer(r"[\wÁÉÍÓÚÑáéíóúñ]+", pedido) if aislado else []):
        w = m.group(0)
        if i == 0 or not any(c.isupper() for c in w) or re.search(r"\d", w):
            continue
        if re.fullmatch(UNIDAD, w.lower()) and re.search(r"\d\s*$", pedido[:m.start()]):
            continue  # la unidad suelta despues de un numero, "2 TB", es unidad
        if not any(conocida(x) for x in PALABRA.findall(nrm(w))):
            return "no_hay", f"nombre que la tienda no trae: {w}"
    if nombra_rubro or MARCAS & set(PALABRA.findall(t)) or any(_frase(t, m) for m in MODELOS):
        return "hay", ""
    return "dudoso", ""


def medir(ver):
    n, fallas = collections.Counter(), []
    for e in json.load(open(os.path.join(B.FL, "examen", "examen.json"), encoding="utf-8")):
        t = TR.T[e["id"]]
        for j, p in enumerate(e["pedidos"]):
            hay = bool(X.aceptables(p))
            espera_no = "no_hay" in p["esperados"] and not hay
            if not hay and not espera_no:
                continue
            condicion = espera_no and any(c["tipo"] in ("color", "numero", "atributo") for c in p["cas"]) and \
                not any(c["tipo"] == "fuera" for c in p["cas"]) and not any(c["tipo"] in ("modelo", "marca") for c in p["cas"])
            tramo = " ".join(t["p"][j][0]) or TR.consulta(e["texto"], t, j)
            v, razon = existe(tramo)
            dice_no = v == "no_hay"
            if condicion:
                n["condicion que nada cumple, " + ("la caza" if dice_no else "no la caza")] += 1
                continue
            if espera_no:
                n["no hay bien" if dice_no else "no hay perdido, alucina"] += 1
            else:
                n["falsa alarma, pierde venta" if dice_no else "hay bien"] += 1
            n["veredicto " + v] += 1
            n[f"{v} cuando {'no hay' if espera_no else 'hay'}"] += 1
            if dice_no != espera_no:
                fallas.append(f"    {'PERDIDO' if espera_no else 'ALARMA '} {e['id']:11} p{j} {tramo[:55]!r} {v} {razon}")
    print(f"  no hay bien {n['no hay bien']}, no hay perdido {n['no hay perdido, alucina']};"
          f" hay bien {n['hay bien']}, falsa alarma {n['falsa alarma, pierde venta']}")
    print(f"  veredictos: hay {n['veredicto hay']}, dudoso {n['veredicto dudoso']}, no hay {n['veredicto no_hay']}")
    print(f"  dudoso cuando hay {n['dudoso cuando hay']}, dudoso cuando no hay {n['dudoso cuando no hay']}")
    print(f"  aparte, condiciones que nada cumple: {n['condicion que nada cumple, la caza']} cazadas,"
          f" {n['condicion que nada cumple, no la caza']} no")
    if ver:
        for x in fallas:
            print(x)


if __name__ == "__main__":
    medir("--ver" in sys.argv)
