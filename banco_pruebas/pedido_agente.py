"""EL PEDIDO DEL AGENTE — sus llamadas, en la forma que puntuan las varas (27-sep-2026).

POR QUE EXISTE. Las varas de interpretacion —`vara_interpretacion.json`, las
`vara_charlas*.json`— puntuan un PEDIDO: `consultas`, `envios`, `temas`,
`cuenta`, `reparto_pago`. Ese pedido lo escribia el interprete y salia en el
log `motor_pedido`. El 26-sep el agente reemplazo al interprete y ese evento
dejo de existir: `tanda_charlas.py` y `leer_interpretacion.py` quedaron leyendo
un evento que nadie emite, o sea midiendo cero sin avisar.

LO QUE HACE. El agente no declara un pedido: llama herramientas. Sus llamadas
SON la interpretacion —que busco, con que rubro, que condicion, a que destino,
que sumo, que compro—. Este modulo las traduce UNA vez a la forma vieja, y las
casillas de `leer_interpretacion.CASILLA` siguen siendo la unica definicion de
correcto. No se escribe un segundo puntaje.

Y MIDE LAS 58 POR LAS PIEZAS. Las piezas correctas de cada una ya estan
escritas a mano en `desmenuzar.CASOS`. `nota_piezas` exige que cada pieza tenga
su llamada: la herramienta que corresponde a su tipo, con lo que la pieza
nombra en los argumentos, el rubro o el tema de la tienda correcto, la
condicion traducida, y si depende de otra, en una vuelta posterior.

La traduccion del rubro y del tema la hace el MISMO codigo de produccion:
`agente._rubro` y `agente.temas_de`. Por eso necesita el doble de Firestore del
clon, pero no el modelo: se puede recalificar lo guardado sin gastar cuota.
"""
import contextlib
import csv
import json
import re
from pathlib import Path

from banco_pruebas.sonda_modelo import _n

RAIZ = Path(__file__).resolve().parent.parent
TIENDA = "verifika_prod"
CATALOGO = list(csv.DictReader(open(RAIZ / "data" / "clientes" / TIENDA / "productos.csv", encoding="utf-8")))


# ══ LA LLAMADA, VENGA DE DONDE VENGA ════════════════════════════════════════

def llamadas_de(crudo) -> list:
    """[{vuelta, herramienta, args, vuelve}] desde lo que haya: el resultado de
    `agente.turno`, o lo guardado en `sonda_charlas_corridas.jsonl` como texto
    `nombre{json}`, que no trae la vuelta ni lo que volvio."""
    out = []
    for x in crudo or []:
        if isinstance(x, dict):
            out.append({"vuelta": x.get("vuelta"), "herramienta": x.get("herramienta"),
                        "args": x.get("args") or {}, "vuelve": x.get("vuelve")})
            continue
        m = re.match(r"\s*(\w+)\s*(\{.*)", str(x), re.S)
        if not m:
            continue
        try:
            args = json.loads(m.group(2))
        except ValueError:
            args = {}
        out.append({"vuelta": None, "herramienta": m.group(1), "args": args, "vuelve": None})
    return out


def llamadas_del_log(pedidos: list) -> list:
    """Los `pedidos` de `agente_turno` en Cloud Run: "herramienta {json}",
    cortados a 240. Un json cortado se lee hasta donde se pueda: la
    herramienta se cuenta igual, con los argumentos que entren."""
    out = []
    for s in pedidos or []:
        nombre, _, resto = str(s).partition(" ")
        try:
            args = json.loads(resto)
        except ValueError:
            args = {"_cortado": resto}
        out.append({"vuelta": None, "herramienta": nombre, "args": args, "vuelve": None})
    return out


@contextlib.contextmanager
def espiar():
    """Junta las llamadas de cada `agente.turno` que corre adentro, tambien
    por el clon entero. `respuesta` llama `agente.turno` por el modulo, asi
    que alcanza con envolverlo ahi."""
    from app.core import agente
    visto: list = []
    orig = agente.turno

    async def envuelto(*a, **k):
        r = await orig(*a, **k)
        visto.extend(r.get("llamadas") or [])
        return r
    agente.turno = envuelto
    try:
        yield visto
    finally:
        agente.turno = orig


# ══ LO QUE LA TIENDA ENTIENDE DE CADA LLAMADA ═══════════════════════════════

def _modelos():
    por = []
    for p in CATALOGO:
        for k in {_n(p["modelo"])} | {w for w in _n(p["modelo"]).split()
                                       if len(w) >= 3 and any(c.isdigit() for c in w)}:
            if len(k) >= 3:
                por.append((k, p))
    return sorted(por, key=lambda x: -len(x[0]))


_MODELOS = _modelos()


def categoria_de(nombre: str) -> str:
    """El rubro de un producto nombrado por id o por modelo, del catalogo."""
    t = _n(nombre)
    for p in CATALOGO:
        if p["id"].lower() and p["id"].lower() in t:
            return p["categoria"]
    for k, p in _MODELOS:
        if re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", t):
            return p["categoria"]
    return ""


def rubro_de(texto: str) -> str:
    from app.core import agente
    return agente._rubro(texto, TIENDA)[0] or "" if texto else ""


def temas_de(pregunta: str) -> list:
    from app.core import agente
    return agente.temas_de(pregunta, TIENDA) if pregunta else []


def _categoria_llamada(x: dict) -> str:
    """El rubro que la tienda entendio: el de las filas que volvieron si las
    hay, si no el del producto nombrado o el del rubro que escribio."""
    for f in ((x.get("vuelve") or {}).get("filas") or []) if isinstance(x.get("vuelve"), dict) else []:
        c = categoria_de(str(f.get("id") or ""))
        if c:
            return c
    a = x["args"]
    if x["herramienta"] == "buscar":
        return rubro_de(a.get("rubro") or "") or categoria_de(json.dumps(a, ensure_ascii=False)) \
            or rubro_de(a.get("que") or "")
    return categoria_de(str(a.get("nombre") or a.get("producto") or ""))


# ══ EL PEDIDO EN LA FORMA VIEJA ═════════════════════════════════════════════

def pedido(llamadas: list) -> dict:
    """Las llamadas del turno como el pedido que puntua `leer_interpretacion`.

    buscar          consulta varios: texto, categoria, condiciones, orden
    producto        consulta uno
    reservar        consulta uno con cantidad, y `compra`
    envio           envios
    cuenta          cuenta.items, pedir_total, reparto_pago, y el destino como envio que va con todo
    politica        temas: los que ubica el codigo, como en produccion
    compatibilidad  compatibilidad
    afirma          lo que se VERIFICO: una ficha, una politica o una compatibilidad consultada.
                    El agente no declara la premisa, la consulta; la casilla mide lo mismo.
    """
    p: dict = {"consultas": [], "envios": [], "temas": [], "compatibilidad": [], "afirma": [],
               "compra": [], "reparto_pago": [], "politicas_pedidas": 0}
    for x in llamadas_de(llamadas):
        h, a = x["herramienta"], x["args"]
        if h == "buscar":
            q = {"texto": a.get("que") or "", "busco": "varios", "categoria": _categoria_llamada(x),
                 "condiciones": [c for c in a.get("condiciones") or [] if isinstance(c, dict)]}
            o = a.get("orden")
            if isinstance(o, dict) and o.get("campo"):
                q["ordenar_por"] = {"campo": o["campo"], "direccion": o.get("direccion") or "min"}
            p["consultas"].append(q)
        elif h in ("producto", "reservar"):
            nombre = str(a.get("nombre") or a.get("producto") or "")
            q = {"texto": nombre, "busco": "uno", "categoria": _categoria_llamada(x)}
            if h == "reservar":
                q["cantidad"] = int(a.get("cantidad") or 1)
                p["compra"].append({"producto": nombre, "cantidad": q["cantidad"]})
            else:
                p["afirma"].append({"sobre": nombre, "dice": "ficha"})
            p["consultas"].append(q)
        elif h == "envio":
            p["envios"] += [{"destino": str(d)} for d in a.get("destinos") or []]
        elif h == "cuenta":
            its = [{"id": str(i.get("producto") or ""), "cantidad": int(i.get("cantidad") or 1)}
                   for i in a.get("items") or [] if isinstance(i, dict)]
            c = p.setdefault("cuenta", {"items": []})
            c["items"] += its
            p["pedir_total"] = True
            p["reparto_pago"] += [r for r in a.get("reparto_pago") or [] if isinstance(r, dict)]
            if a.get("destino"):
                p["envios"].append({"destino": str(a["destino"]), "va": "todo"})
        elif h == "politica":
            preg = str(a.get("pregunta") or "")
            p["politicas_pedidas"] += 1
            p["temas"] += [{"tema": t, "dicho": preg} for t in temas_de(preg)]
            p["afirma"].append({"sobre": "politica", "dice": preg})
        elif h == "compatibilidad":
            p["compatibilidad"].append({"producto": a.get("producto"), "con": a.get("con")})
            p["afirma"].append({"sobre": str(a.get("producto") or ""), "dice": str(a.get("con") or "")})
    return p


# ══ LAS 58 POR LAS PIEZAS DE `desmenuzar.CASOS` ═════════════════════════════

# El tipo de la pieza y las herramientas que la cumplen. `explicar` y `charla`
# no necesitan herramienta; `repreguntar` se cumple preguntando y sin comprar.
POR_TIPO = {
    "producto": {"producto", "buscar", "cuenta", "reservar"},
    "buscar": {"buscar", "producto"},
    "envio": {"envio", "cuenta"},
    "politica": {"politica"},
    "compatibilidad": {"compatibilidad"},
    "cuenta": {"cuenta"},
    "comprar": {"reservar"},
    "verificar": {"producto", "buscar", "politica", "compatibilidad"},
}
SIN_HERRAMIENTA = {"explicar", "charla", "repreguntar"}

# LA PIEZA CONDICIONAL QUE NO TIENE QUE CORRER. Una compra que depende de una
# condicion solo se llama si la condicion se cumple, y eso lo dice el catalogo,
# no la vara. Se escribe caso por caso con la cuenta a la vista.
NO_CORRE = {
    ("C56", "comprar"): "el K120 negro sale 14.500: no baja de 10 mil y no se compra",
}


_POR_ID = {p["id"].lower(): p for p in CATALOGO}

# Lo que se hace con el resultado. Una pieza de ACCION tiene que estar en el
# turno del mensaje; una de CONSULTA puede venir de un turno anterior de la
# charla: "si no hay en negro, el blanco" con el stock ya visto antes no
# obliga a pedir la ficha otra vez.
ACCION = {"comprar", "cuenta", "envio"}


def _texto_llamada(x: dict) -> str:
    """Los argumentos como texto, con el NOMBRE de cada id que aparezca: por
    el clon el modelo pide "MOU0029" y la pieza dice "g305"."""
    t = _n(x["herramienta"] + " " + json.dumps(x["args"], ensure_ascii=False))
    nombres = [_n(_POR_ID[i]["nombre"]) for i in re.findall(r"[a-z]{3}\d{4}", t) if i in _POR_ID]
    return t + " " + " ".join(nombres)


def _cumple(e: dict, x: dict) -> bool:
    """La llamada `x` cubre la pieza `e`: herramienta, lo que nombra, y el
    destino de un envio aunque viaje dentro de la cuenta."""
    h = x["herramienta"]
    if not any(h in POR_TIPO.get(t, ()) for t in e["tipos"]):
        return False
    if h == "cuenta" and "envio" in e["tipos"] and "cuenta" not in e["tipos"] \
            and not (x["args"].get("destino")):
        return False
    t = _texto_llamada(x)
    claves = list(e["claves"])
    # LA FICHA VERIFICA EL DATO. "El K120 es inalambrico?" se contesta pidiendo
    # la ficha del K120: trae la conexion, la garantia y los colores. Una
    # clave que no nombra un producto no tiene por que viajar en el pedido.
    # Pero una pieza de la casa —"tienen 50 off?"— no la verifica una ficha.
    # Igual una busqueda por el nombre de un producto: sus filas traen los datos.
    if h == "producto" or (h == "buscar" and categoria_de(t)):
        if e["tema"]:
            return False
        claves = [c for c in claves if any(categoria_de(o) for o in c.split("|"))]
    # LA CUENTA NO TIENE CAMPO PARA UN TOPE. "Si pasa de 300 mil" se cumple
    # sumando y mirando el total; el numero no viaja.
    if h == "cuenta":
        claves = [c for c in claves if not c.isdigit()]
    return all(any(_n(o) in t for o in c.split("|")) for c in claves)


def _traduce(e: dict, x: dict) -> list:
    """Lo que falla de la traduccion, o vacio."""
    fallas = []
    if e["rubro"] and x["herramienta"] in ("buscar", "producto", "reservar"):
        cat = _categoria_llamada(x)
        if _n(cat) != _n(e["rubro"]):
            fallas.append(f"rubro {cat or '-'} por {e['rubro']}")
    if e["tema"] and x["herramienta"] == "politica":
        ts = temas_de(str(x["args"].get("pregunta") or ""))
        if not set(_n(t) for t in ts) & {_n(t) for t in e["tema"]}:
            fallas.append(f"tema {(ts or ['-'])[0]} por {e['tema'][0]}")
    if e["cond"]:
        a = x["args"]
        donde = _n(json.dumps([a.get("condiciones"), a.get("orden"), a.get("que"), a.get("rubro")],
                              ensure_ascii=False))
        if not any(_n(o) in donde for o in e["cond"].split("|")):
            fallas.append(f"condicion sin {e['cond']}")
    return fallas


def _pregunta(texto: str) -> bool:
    return "?" in (texto or "") or bool(re.search(r"\b(decime|contame|avisame|pasame|indicame)\b", _n(texto)))


def nota_piezas(caso, llamadas: list, texto: str = "", previas: list = ()) -> dict:
    """La interpretacion de un turno contra sus piezas correctas.

    Devuelve {piezas, bien, traduce_mal, faltan, sobran, detalle}. Una pieza
    esta BIEN si tiene su llamada, esa llamada traduce bien, y si la pieza
    depende de otra, viene en una vuelta posterior. `sobran` son llamadas que
    no cubren ninguna pieza: no restan, se informan. `previas` son las
    llamadas de los turnos anteriores de la charla: cubren solo piezas de
    consulta, nunca de ACCION."""
    esperadas = caso[3]
    ls = llamadas_de(llamadas)
    antes = [{**x, "vuelta": 0} for x in llamadas_de(previas)]
    usadas: set = set()
    bien = 0
    faltan, trad, detalle = [], [], []
    vuelta_de: dict = {}
    for i, e in enumerate(esperadas):
        nombre = f"{e['tipos'][0]}({','.join(e['claves'])})"
        if set(e["tipos"]) & SIN_HERRAMIENTA and not any(_cumple(e, x) for x in ls):
            ok = True
            if "repreguntar" in e["tipos"]:
                ok = _pregunta(texto) and not any(x["herramienta"] in ("reservar", "cuenta") for x in ls)
            if ok:
                bien += not e["opc"]
            elif not e["opc"]:
                faltan.append(nombre)
            continue
        cand = [j for j, x in enumerate(ls) if _cumple(e, x)]
        if not cand and e["tipos"][0] not in ACCION:
            vieja = next((x for x in antes if _cumple(e, x) and not _traduce(e, x)), None)
            if vieja:
                bien += not e["opc"]
                continue
        if (caso[0], e["tipos"][0]) in NO_CORRE:
            if cand:
                faltan.append(f"{nombre} corrio y no tenia que correr")
            else:
                bien += 1
            continue
        if not cand:
            if e["opc"]:
                continue
            faltan.append(nombre)
            continue
        # Entre las que cumplen, la que traduce bien; si ninguna, la primera.
        j = next((j for j in cand if not _traduce(e, ls[j])), cand[0])
        usadas |= set(cand)
        vuelta_de[i] = ls[j]["vuelta"]
        f = _traduce(e, ls[j])
        if e["dep"] and ls[j]["vuelta"] is not None:
            previas = [v for k, v in vuelta_de.items() if k < i and v is not None]
            if previas and ls[j]["vuelta"] <= max(previas):
                f.append(f"{nombre} sin esperar el resultado")
        if f:
            trad += f
            detalle.append(f"{nombre}: {'; '.join(f)}")
        else:
            bien += not e["opc"]
    sobran = [ls[j]["herramienta"] for j in range(len(ls)) if j not in usadas]
    detalle = [f"falta {x}" for x in faltan] + detalle
    return {"piezas": sum(1 for e in esperadas if not e["opc"]), "bien": bien,
            "traduce_mal": trad, "faltan": faltan, "sobran": sobran, "detalle": "; ".join(detalle)}


def preparar_sin_modelo() -> None:
    """El doble de Firestore del clon, para que `_rubro` y `temas_de` lean la
    fuente real. No toca la clave ni llama al modelo."""
    from banco_pruebas import clon_produccion as C
    C.preparar_entorno()
    C.instalar()
    from app.core.contexto_turno import set_current_tienda
    set_current_tienda(TIENDA)
