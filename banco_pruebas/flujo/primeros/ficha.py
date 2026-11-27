"""LA FICHA DEL PEDIDO, SIN BORRADO (27-nov-2026). Paso 1 del Plan 7 de `lab/plan.md`.

Cada pedazo del mensaje que Luna escribio es un tramo con su lugar: la fila, las palabras literales, lo que Luna le puso
y los usos que le anotan las funciones. Ninguna funcion saca un tramo; solo le agrega usos. Al final, cada tramo tiene
por lo menos un uso, y si ninguna funcion lo tomo, queda dicho: sin dato, o no reconocido si el pedido no tiene producto.

Usa la cadena del banco tal cual, `condicion.pedidos`, y despues le devuelve lo que perdia:
  1. la fila que ningun pedido tomo se pega al pedido anterior, o a uno sin producto, y se ata como condicion;
  2. la marca o el modelo que Luna escribio sin marcar entra al nombre que va a existe, si el catalogo lo conoce o es un
     codigo con letras y cifras;
  3. lo que queda, sin dato o no reconocido.
La condicion, la busqueda y existe no cambian: si mejoran, cambia lo que anotan en los usos, no la ficha.

Los papeles son la lista que despues llena Luna, Plan 7, paso 2. Hoy se deducen de lo que Luna marca.
"""
import os, re, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [AQUI, os.path.join(AQUI, "..", "lab")]
import condicion as K  # noqa: E402
import existe as EX  # noqa: E402

C, nrm = K.C, K.nrm
PAPELES = ("producto", "marca", "modelo", "exige", "excluye", "prefiere", "orden", "pregunta", "tema", "destino", "pago",
           "cantidad", "referencia", "relleno", "sin_marca")
USOS = ("rubro", "nombre", "condicion", "pregunta", "sin_dato", "no_reconocido", "relleno")


def _contenido(t):
    return [w for w in re.findall(r"[a-z0-9]+", nrm(t)) if len(w) > 2 or re.search(r"\d", w)]


def _papel(n):
    if not n:
        return "sin_marca"
    if n in ("marca", "modelo"):
        return n
    sec = C.SECCION.get(n)
    if sec == "PRODUCTOS":
        return "producto"
    if sec == "PREGUNTAS":
        return "tema"
    return "exige"


def _nombra_catalogo(p):
    """El tramo nombra una marca o un modelo: una marca del catalogo, un modelo del catalogo, o un codigo con letras y
    cifras, "K380", "i9-14900K", aunque la tienda no lo traiga: eso lo decide existe, no la ficha."""
    t = nrm(p)
    ws = set(EX.PALABRA.findall(t))
    return bool(ws & EX.MARCAS) or any(EX._frase(t, m) for m in EX.MODELOS) or any(C._codigo(w) for w in ws)


def _pregunta(p, n):
    if not n:
        return False
    if C.SECCION.get(n) == "PREGUNTAS":
        return True
    return C.dato2("{" + p + "}[" + n + "]")[0] != ["ofrecer"]


def armar(textos):
    """(pedidos, tramos). Los pedidos son los de `condicion.pedidos` con lo que perdian devuelto; los tramos, cada pedazo
    con `fila`, `texto`, `luna`, `papel`, `pedido` y `usos`."""
    tramos = []
    for fi, t in enumerate(textos):
        for p, n in C.partes(t):
            tramos.append({"fila": fi, "texto": p, "luna": n, "papel": _papel(n), "pedido": None, "usos": []})
    peds = K.pedidos(textos)
    for g in peds:
        g.setdefault("no_reconocido", [])
        g["nombre"] = g.get("nombre") or ""

    def anotar(tr, i, g):
        p, n = tr["texto"], tr["luna"]
        pn = nrm(p)
        junto = lambda x: re.sub(r"\s+", "", nrm(x))
        if tr["pedido"] is None:
            tr["pedido"] = i
        if n and g["rubro"] and n == nrm(g["rubro"]):
            tr["usos"].append("rubro")
        if pn and pn in nrm(g["nombre"]):
            tr["usos"].append("nombre")
        if pn and any(d.get("texto") and (junto(d["texto"]) in junto(p) or junto(p) in junto(d["texto"])) for d in g["atadas"]):
            tr["usos"].append("condicion")
        if p in g["sin_dato"]:
            tr["usos"].append("sin_dato")
        if _pregunta(p, n):
            tr["usos"].append("pregunta")

    for i, g in enumerate(peds):
        textos_g = {nrm(p) for p, _ in g["partes"]}
        for tr in tramos:
            if nrm(tr["texto"]) in textos_g:
                anotar(tr, i, g)

    # 1. Lo que ningun pedido tomo: al pedido de la fila, al anterior, o a uno sin producto.
    for tr in tramos:
        if tr["pedido"] is not None:
            continue
        if not peds:
            peds.append({"rubro": None, "consulta": "", "dato2": [], "caracts": [], "identifica": False, "nombra": False,
                         "partes": [], "nombre": "", "atadas": [], "sin_dato": [], "no_reconocido": []})
        antes = [t2["pedido"] for t2 in tramos if t2["pedido"] is not None and t2["fila"] <= tr["fila"]]
        i = antes[-1] if antes else 0
        g = peds[i]
        g["partes"] = g["partes"] + [(tr["texto"], tr["luna"])]
        if tr["luna"] and not _pregunta(tr["texto"], tr["luna"]):
            at, sin = K.atar({"partes": [(tr["texto"], tr["luna"])], "rubro": g["rubro"]},
                             "{" + tr["texto"] + "}[" + tr["luna"] + "]")
            g["atadas"] = g["atadas"] + at
            g["sin_dato"] = g["sin_dato"] + sin
        anotar(tr, i, g)

    # 2. La marca o el modelo sin marcar, al nombre que va a existe, aunque la condicion ya lo haya tomado para filtrar.
    for tr in tramos:
        g = peds[tr["pedido"]]
        if "nombre" not in tr["usos"] and not tr["luna"] and _nombra_catalogo(tr["texto"]):
            g["nombre"] = (g["nombre"] + " " + tr["texto"]).strip()
            tr["usos"].append("nombre")

    # 3. Lo que queda, dicho.
    for tr in tramos:
        if tr["usos"]:
            continue
        g = peds[tr["pedido"]]
        if not _contenido(tr["texto"]):
            tr["usos"].append("relleno")
        elif not (g["rubro"] or g["identifica"] or g["nombre"]):
            g["no_reconocido"].append(tr["texto"])
            tr["usos"].append("no_reconocido")
        else:
            g["sin_dato"] = g["sin_dato"] + [tr["texto"]]
            tr["usos"].append("sin_dato")
    return peds, tramos
