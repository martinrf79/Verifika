"""LA FORMA NORMAL — lo que dijo el modelo, llevado a la forma que el ejecutor cumple (21-oct-2026, FICHA 74).

Medido sobre las traducciones grabadas de seis modelos: cuando fallan, casi siempre entendieron bien y lo dijeron de otra
forma que la agenda a mano. "Cuanto me sale con envio" llega como producto y envio, sin cuenta; un "si" con el pedido
completo llega como confirmar renglones que no esperaban nada. Esto no corrige al modelo: define que quiere decir cada
una de esas formas, y la lleva a la que el ejecutor ya cumple.

Lo que hace cada regla:
  - Lee la agenda, el estado de la charla y la fuente de la tienda. Nunca el mensaje: de lo dicho, solo la cita que el
    modelo le puso a esa pregunta, y solo para buscar ahi un lugar o un producto de la fuente.
  - Cubre una forma de decir, no un caso. No usa listas de palabras.
  - Entra si, sobre las traducciones grabadas, arregla alguna y no rompe ninguna en ningun modelo:
    `banco_pruebas/camino_grabadas.py` y `banco_pruebas/capa_buscar.py`.

`normalizar` es pura: devuelve una agenda nueva y los nombres de las reglas que aplico, para el log del turno.
"""
import copy
import re

from . import agenda as A
from . import borrador as B
from . import catalogo as K

_CAMBIA = ("agrega", "saca", "cambia", "total", "reemplaza", "reparto")
_PRECIO = ("", "precio", "stock", "disponibilidad", "precio y stock", "todo", "existencia")


def _lista(x) -> list:
    return x if isinstance(x, list) else ([x] if x not in (None, "", {}) else [])


def _es(ref, letra: str) -> bool:
    return isinstance(ref, str) and re.fullmatch(rf"{letra}-\d+", ref.strip()) is not None


def lugares(texto: str) -> list:
    """Los lugares a los que se envia que nombra un texto, segun el padron de localidades: [(como lo nombra el padron,
    provincia)]. Se corta en las comas y en "y": cada pedazo es un lugar si el padron lo ubica. Un pedazo con numeros es
    la direccion del lugar anterior, y una ciudad seguida de su provincia es un solo lugar: "Posadas, Misiones". Desde
    el 26-oct, FICHA 82, la direccion es una palabra con su altura, "Belgrano 1234": antes cualquier numero tapaba el
    lugar, y "un G203 a Rosario" perdia Rosario por el modelo."""
    from app.core import geo_cp
    from app.core.envio import clasificar_provincia
    out = []
    for parte in re.split(r"[,;]|\by\b|\be\b", str(texto or "")):
        parte = parte.strip()
        if not parte or re.search(r"[^\W\d]\s+\d{2,5}\b", parte):
            continue
        prov = clasificar_provincia(parte)
        if not prov:
            continue
        palabras, hits = geo_cp._localidades_en_texto(geo_cp._norm(parte))
        hits = sorted(h for h in [(i, f, loc) for loc, i, f in hits] if prov in geo_cp._LOC.get(h[2], {}))
        nombre = " ".join(palabras[hits[0][0]:hits[0][1]]) if hits else prov if prov in K.n(parte) else K.n(parte).strip()
        plano, i = K.n(parte), K.n(parte).find(K.n(nombre))
        if i >= 0 and len(plano) == len(parte):
            nombre = parte[i:i + len(nombre)]  # como lo escribio el cliente: "Posadas", no "posadas"
        if out and out[-1][1] == prov and (K.n(nombre) == K.n(prov) or not hits):
            continue
        out.append((nombre, prov))
    return out


class _Ctx:
    def __init__(self, agenda: dict, estado: dict, tienda_id: str, nums: dict):
        self.agenda, self.estado, self.tienda, self.nums = agenda, estado, tienda_id, nums
        self.b = B.leer(estado.get("borrador"))
        self._res = None

    @property
    def ps(self) -> list:
        return A.preguntas(self.agenda)

    def res(self) -> tuple:
        if self._res is None:
            res = B.resolver(self.b, self.tienda) if self.b["renglones"] else []
            self._res = (res, B.faltantes(self.b, res))
        return self._res

    def nuevo_n(self) -> int:
        return max([K.entero(p.get("n")) for p in self.ps] + [0]) + 1

    def acciones(self, *nombres) -> list:
        return [p for p in self.ps if p.get("accion") in nombres]


# ══ LAS REGLAS: cada una mira una forma y la reescribe; devuelve si la aplico ══

def si_sin_efecto(c: _Ctx) -> bool:
    """UN SI QUE NO CAMBIA NADA, con el pedido completo, pide ver como queda: la cuenta. Llega como confirmar renglones
    que no esperaban nada, aceptar sin decir que, o un dato sin datos."""
    res, falta = c.res()
    if not c.estado.get("pedido") or falta or not c.ps:
        return False
    pendientes = {x["L"] for x in res if x.get("falta") or x.get("supuesto")}
    for p in c.ps:
        acc = p.get("accion")
        if acc == "comprar":
            refs = _lista(p.get("confirma")) + _lista(p.get("acepta"))
            if any(_lista(p.get(k)) for k in _CAMBIA) or any(not _es(r, "L") or r in pendientes for r in refs):
                return False
        elif not (acc == "otro" and K.n(p.get("que")) == "dato" and not any((c.agenda.get("cliente") or {}).values())):
            return False
    citas = " ".join(str(p.get("cita") or "") for p in c.ps).strip()
    c.agenda["preguntas"] = [{"n": 1, "cita": citas, "accion": "cuenta"}]
    return True


def precio_con_envio(c: _Ctx) -> bool:
    """PRECIO Y ENVIO EN EL MISMO MENSAJE, sin pedido: lo que pregunta es cuanto le sale todo, y va la cuenta."""
    if c.acciones("cuenta", "comprar") or c.b["renglones"] or not c.acciones("envio"):
        return False
    prods = [p for p in c.acciones("producto") if K.n(p.get("quiere_saber")) in _PRECIO]
    if not prods or len(prods) != len(c.acciones("producto")):
        return False
    c.agenda["preguntas"].append({"n": c.nuevo_n(), "cita": "", "accion": "cuenta"})
    return True


def politica_de_envio_con_lugar(c: _Ctx) -> bool:
    """LA REGLA DE ENVIOS PREGUNTADA CON UN LUGAR es el costo de mandar ahi: un envio por cada lugar. El lugar sale de la
    cita de esa pregunta o de los destinos del pedido de este mensaje."""
    hizo = False
    destinos = [a.get("destino") for p in c.acciones("comprar") for a in _lista(p.get("agrega"))
                if isinstance(a, dict) and B._destino(a.get("destino"))]
    nuevas = []
    # Sin lugar en el mensaje, el del cliente: "cuanto me sale con envio" de alguien que ya dijo que es de Posadas.
    suyo = [B._destino(c.b["cliente"].get("localidad"))] if B._destino(c.b["cliente"].get("localidad")) else []
    for p in c.ps:
        # Solo la regla del costo: "cuanto tarda a Neuquen" es el plazo, y la cotizacion no lo dice.
        if p.get("accion") == "politica" and K.n(p.get("tema")) in ("envios", "envio", "costo_envio"):
            ds = [f for f, _ in lugares(p.get("cita"))] or list(dict.fromkeys(destinos)) or suyo
            if ds:
                nuevas += [{"n": p.get("n") if i == 0 else None, "cita": p.get("cita") or "", "accion": "envio",
                            "destino": d} for i, d in enumerate(ds)]
                hizo = True
                continue
        nuevas.append(p)
    if hizo:
        c.agenda["preguntas"] = _numerar(nuevas)
    return hizo


def envio_a_varios(c: _Ctx) -> bool:
    """UN ENVIO A UN DESTINO QUE NOMBRA VARIOS LUGARES —"Rosario y Mendoza"— es un envio por cada uno."""
    hizo, nuevas = False, []
    for p in c.ps:
        ls = lugares(p.get("destino")) if p.get("accion") == "envio" else []
        if len(ls) > 1 and len({pr for _, pr in ls}) > 1:
            nuevas += [{**p, "n": p.get("n") if i == 0 else None, "destino": f} for i, (f, _) in enumerate(ls)]
            hizo = True
        else:
            nuevas.append(p)
    if hizo:
        c.agenda["preguntas"] = _numerar(nuevas)
    return hizo


def un_destino_para_el_pedido(c: _Ctx) -> bool:
    """UN SOLO DESTINO EN EL MENSAJE Y NADA DEL PEDIDO CON DESTINO: ese es el destino del pedido. "El envio es a
    Rosario, cuanto queda" con el pedido armado, o "sumame todo con envio a Cordoba" con lo que agrega este mensaje."""
    destinos = list(dict.fromkeys(K.n(p.get("destino")) for p in c.acciones("envio") if B._destino(p.get("destino"))))
    if len(destinos) != 1:
        return False
    destino = next(p["destino"] for p in c.acciones("envio") if K.n(p.get("destino")) == destinos[0])
    agrega = [a for p in c.acciones("comprar") for a in _lista(p.get("agrega")) if isinstance(a, dict)]
    cambia = [x for p in c.acciones("comprar") for x in _lista(p.get("cambia")) if isinstance(x, dict)]
    if any(B._destino(a.get("destino")) for a in agrega + cambia) or any(B._destino(r["destino"])
                                                                         for r in c.b["renglones"]):
        return False
    if not agrega and not c.b["renglones"]:
        return False
    for a in agrega:
        a["destino"] = destino
    sacados = {str(r) for p in c.acciones("comprar") for r in _lista(p.get("saca"))}
    quedan = [r for r in c.b["renglones"] if r["L"] not in sacados]
    if quedan and not any(p.get("reemplaza") for p in c.acciones("comprar")):
        c.agenda["preguntas"].append({"n": c.nuevo_n(), "cita": "", "accion": "comprar",
                                      "cambia": [{"es": r["L"], "destino": destino} for r in quedan]})
    return True


def cuenta_de_lo_buscado(c: _Ctx) -> bool:
    """LA CUENTA SIN PEDIDO, DE LO QUE BUSCA ESTE MENSAJE —"dos mouse, los mas baratos, sumame todo"—: lo buscado entra
    al pedido con sus cantidades, como en la agenda a mano, y la cuenta lo suma."""
    if not c.acciones("cuenta") or c.acciones("comprar") or c.b["renglones"] or c.estado.get("pedido"):
        return False
    busquedas = [p for p in c.acciones("buscar") if K.rubro(str(p.get("rubro") or ""), c.tienda)
                 and not p.get("si")]
    if not busquedas or c.acciones("producto"):
        return False
    destinos = list(dict.fromkeys(B._destino(p.get("destino")) for p in c.acciones("envio", "cuenta")
                                  if B._destino(p.get("destino"))))
    destino = destinos[0] if len(destinos) == 1 else ""
    agrega = [{"producto": p["rubro"], "cantidad": max(1, K.entero(p.get("cantidad"), 1)),
               **({"destino": destino} if destino else {})} for p in busquedas]
    cuenta = c.acciones("cuenta")[0]
    i = c.agenda["preguntas"].index(cuenta)
    c.agenda["preguntas"].insert(i, {"n": None, "cita": "", "accion": "comprar", "agrega": agrega})
    c.agenda["preguntas"] = _numerar(c.agenda["preguntas"])
    return True


def cuenta_de_lo_nombrado(c: _Ctx) -> bool:
    """LA CUENTA SIN PEDIDO DE PRODUCTOS NOMBRADOS CON SU CANTIDAD —"dos G305 negros y tres K120, cuanto es"—: lo nombrado
    entra al pedido con esa cantidad, como en la agenda a mano, y la cuenta lo suma."""
    if not c.acciones("cuenta") or c.acciones("comprar") or c.b["renglones"] or c.estado.get("pedido"):
        return False
    prods = c.acciones("producto")
    # La cantidad en su campo, o en lo que afirma si es solo eso: "2", o "cantidad 2", 9-nov, C25.
    cant = {id(p): K.entero(p.get("cantidad")) or (K.entero(m.group(1)) if (m := re.fullmatch(
            r"\s*(?:cantidad\s*:?\s*)?(\d+)\s*", K.n(p.get("afirma") or ""))) else 0) for p in prods}
    if not prods or not any(v > 1 for v in cant.values()) or any(isinstance(p.get("producto"), list) for p in prods):
        return False
    agrega = [{"producto": p["producto"], "cantidad": cant[id(p)] or 1, **({"color": p["color"]} if p.get("color")
              else {})} for p in prods]
    cuenta = c.acciones("cuenta")[0]
    c.agenda["preguntas"].insert(c.agenda["preguntas"].index(cuenta),
                                 {"n": None, "cita": "", "accion": "comprar", "agrega": agrega})
    c.agenda["preguntas"] = _numerar(c.agenda["preguntas"])
    return True


def lista_con_dato(c: _Ctx) -> bool:
    """VARIOS PRODUCTOS EN UNA PREGUNTA CON UN DATO QUE LA TIENDA FILTRA —"el G305 y el G203, cual es inalambrico", "de
    esos, el que no tiene cable"— se resuelven por el dato: si lo cumple uno solo, la pregunta es por ese, y el vendedor
    ofrece reservarlo. Si no, va una pregunta por cada producto nombrado, con su dato. Sin un dato que filtre, la lista de
    la libreta queda como esta: senala sin decir cual, y el codigo pregunta."""
    hizo, nuevas = False, []
    for p in c.ps:
        xs = p.get("producto") if p.get("accion") == "producto" else None
        if not (isinstance(xs, list) and len(xs) > 1) or any(_es(str(x), "L") for x in xs):
            nuevas.append(p)
            continue
        nombres = [K.por_id(c.nums.get(str(x).strip()), c.tienda).get("nombre") if _es(str(x), "M") else str(x)
                   for x in xs]
        idts = [K.identificar(str(x or ""), "", c.tienda) for x in nombres]
        prods = [i.get("producto") for i in idts if i["veredicto"] == "exists"]
        if len(prods) != len(xs) or len({(q.get("marca"), q.get("modelo")) for q in prods}) != len(xs):
            nuevas.append(p)
            continue
        universo = [q for q in K.productos(c.tienda) if q.get("categoria") in {x.get("categoria") for x in prods}]
        f = K.atar(str(p.get("quiere_saber") or ""), universo, c.tienda)
        filtra = "campo" in f and f["campo"] not in ("nombre", "modelo", "descripcion", "tags") or "todas" in f
        cumplen = [x for x, q in zip(xs, prods) if filtra and K.cumple(q, f)]
        if len(cumplen) == 1:
            nuevas.append({**p, "producto": str(cumplen[0]), "ofrece": True})
        elif filtra or not any(_es(str(x), "M") for x in xs):
            nuevas += [{**p, "n": p.get("n") if j == 0 else None, "producto": str(x)} for j, x in enumerate(xs)]
        else:
            nuevas.append(p)
            continue
        hizo = True
    if hizo:
        c.agenda["preguntas"] = _numerar(nuevas)
    return hizo


def rubro_inventado(c: _Ctx) -> bool:
    """UNA BUSQUEDA DE UN RUBRO QUE LA TIENDA NO TIENE Y QUE LA CITA NO NOMBRA —"el precio no es tan importante" como
    buscar "todos"— no es algo que el cliente pidio: sale de la agenda. Si la cita lo nombra, "tienen drones?", queda, y
    el codigo dice que no se vende."""
    fuera = [p for p in c.acciones("buscar") if K.n(p.get("rubro")) not in ("", "todo", "toda la tienda", "el pedido")
             and not K.rubro(str(p.get("rubro")), c.tienda)
             and not set(K.n(p.get("rubro")).split()) & set(K.n(p.get("cita")).split())]
    if not fuera or len(fuera) == len(c.ps):
        return False
    c.agenda["preguntas"] = [p for p in c.ps if p not in fuera]
    return True


def dato_del_producto(c: _Ctx) -> bool:
    """UNA REGLA DE LA TIENDA QUE ES UN DATO DEL PRODUCTO NOMBRADO —"el G305 tiene garantia?"— se contesta con la ficha
    del producto: el tema es un campo suyo. El producto sale de la cita de esa pregunta, o de lo que afirma."""
    from . import marcador
    hizo = False
    for p in c.acciones("politica"):
        nombres = [d for d, e in marcador.marcar(f"{p.get('cita') or ''} {p.get('afirma') or ''}", c.tienda)
                   if e.startswith("el producto")]
        if len(set(map(K.n, nombres))) != 1:
            continue
        prod = K.identificar(nombres[0], "", c.tienda).get("producto") or {}
        if prod and _campo(prod, str(p.get("tema") or "")):
            n, cita = p.get("n"), p.get("cita")
            campo = _campo(prod, str(p.get("tema") or ""))
            p.clear()
            p.update({"n": n, "cita": cita, "accion": "producto", "producto": nombres[0], "quiere_saber": campo})
            hizo = True
    return hizo


def _campo(prod: dict, tema: str):
    datos = {**(prod.get("specs") or {}), **({"garantia": prod["garantia_meses"]} if prod.get("garantia_meses") else {})}
    palabras = set(K.n(tema).replace("_", " ").split())
    return next((k for k in datos if datos[k] and set(K.n(k).replace("_", " ").split()) & palabras), None)


def referencias_cruzadas(c: _Ctx) -> bool:
    """LO MOSTRADO Y LO DEL PEDIDO SE SENALAN CON SU LETRA, y la operacion sale de la letra: confirmar o aceptar un M es
    llevarlo; agregar un L es cambiar ese renglon; cambiar un M que no esta en el pedido es preguntar de nuevo por el."""
    hizo = False
    en_pedido = {str(a["id"]) for a in c.estado.get("pedido") or []}
    for p in c.acciones("comprar"):
        ms = [r for k in ("confirma", "acepta") for r in _lista(p.get(k)) if _es(r, "M")]
        if ms:
            for k in ("confirma", "acepta"):
                if p.get(k):
                    p[k] = [r for r in _lista(p[k]) if not _es(r, "M")]
            p["agrega"] = _lista(p.get("agrega")) + [{"producto": r, "cantidad": 1} for r in ms]
            hizo = True
        # Con "reemplaza", agregar un L es dejarlo como queda: eso ya lo hace el borrador.
        ls = [a for a in _lista(p.get("agrega")) if isinstance(a, dict) and _es(a.get("producto"), "L")]
        if ls and not p.get("reemplaza"):
            p["agrega"] = [a for a in _lista(p.get("agrega")) if a not in ls]
            p["cambia"] = _lista(p.get("cambia")) + [{"es": a["producto"].strip(), **{k: v for k, v in a.items()
                                                     if k in ("destino", "color") and v}} for a in ls]
            hizo = True
    nuevas = []
    for p in c.ps:
        cm = [x for x in _lista(p.get("cambia")) if isinstance(x, dict) and _es(x.get("es"), "M")
              and str(c.nums.get(x["es"].strip())) not in en_pedido]
        if p.get("accion") == "comprar" and cm and not any(_lista(p.get(k)) for k in _CAMBIA if k != "cambia"):
            for x in cm:
                if B._destino(x.get("destino")):
                    nuevas.append({"n": None, "cita": p.get("cita") or "", "accion": "envio", "destino": x["destino"]})
            resto = [x for x in _lista(p.get("cambia")) if x not in cm]
            if resto:
                nuevas.append({**p, "cambia": resto})
            hizo = True
            continue
        nuevas.append(p)
    c.agenda["preguntas"] = _numerar(nuevas)
    return hizo


def el_pedido_sin_pedido(c: _Ctx) -> bool:
    """OTRO ORDEN PARA "EL PEDIDO" SIN PEDIDO es otro orden para lo ultimo que busco."""
    rub = (c.estado.get("busqueda") or {}).get("rubro")
    ps = [p for p in c.acciones("buscar") if K.n(p.get("rubro")) == "el pedido"]
    if not ps or c.b["renglones"] or c.b["lista"] or not rub:
        return False
    for p in ps:
        p["rubro"] = rub
    return True


def color_ajeno(c: _Ctx) -> bool:
    """UN COLOR QUE NINGUN PRODUCTO DE LA TIENDA TIENE no es un color: "indistinto", "el que sea". Sale del cambio, y el
    cambio que solo traia eso tambien."""
    if not any(isinstance(a, dict) and a.get("color") for p in c.acciones("comprar")
               for k in ("agrega", "cambia") for a in _lista(p.get(k))):
        return False
    colores = {K.n(p.get("color")) for p in K.productos(c.tienda) if p.get("color")}
    hizo = False
    for p in c.acciones("comprar"):
        for k in ("agrega", "cambia"):
            items = []
            for a in _lista(p.get(k)):
                if isinstance(a, dict) and a.get("color") and not set(K.n(a["color"]).split()) & colores:
                    a = {kk: vv for kk, vv in a.items() if kk != "color"}
                    hizo = True
                    if k == "cambia" and set(a) <= {"es"}:
                        continue
                items.append(a)
            if k in p:
                p[k] = items
    if hizo:
        c.agenda["preguntas"] = [p for p in c.ps if p.get("accion") != "comprar" or any(
            _lista(p.get(k)) for k in (*_CAMBIA, "confirma", "acepta", "responde"))]
        if not c.agenda["preguntas"]:
            c.agenda["preguntas"] = [{"n": 1, "cita": "", "accion": "otro", "que": "dato"}]
    return hizo


def compatibilidad_de_un_rubro(c: _Ctx) -> bool:
    """LA COMPATIBILIDAD DE UN RUBRO CON ALGO QUE NO ES UN EQUIPO NI UN PRODUCTO —"la placa mas potente que banque mi
    fuente de 550 W"— es una busqueda en el rubro con esa condicion. La herramienta de compatibilidad solo juzga contra
    los equipos de su vocabulario o contra un producto del catalogo; lo demas lo filtra la busqueda, o dice que no
    figura en las fichas."""
    from app.core.compatibilidad import plataformas_del_mensaje
    hizo = False
    for p in c.acciones("compatibilidad"):
        nombre = " ".join(str(x) for x in _lista(p.get("producto")))
        rub, con = K.solo_rubro(nombre, c.tienda), str(p.get("con") or "")
        if not rub or not con or plataformas_del_mensaje(con, c.tienda) \
                or K.identificar(con, "", c.tienda)["veredicto"] != "not_found":
            continue
        n, cita = p.get("n"), p.get("cita")
        p.clear()
        p.update({"n": n, "cita": cita, "accion": "buscar", "rubro": rub, "condiciones": [con], "orden": "nada"})
        hizo = True
    return hizo


def un_medio_es_todo(c: _Ctx) -> bool:
    """UN SOLO MEDIO DE PAGO SIN PORCENTAJE —"pago con transferencia"— es el cien por ciento."""
    hizo = False
    for p in c.acciones("cuenta", "comprar"):
        rep = [r for r in _lista(p.get("reparto")) if isinstance(r, dict)]
        if len(rep) == 1 and not K.entero(rep[0].get("porcentaje")) and K.n(rep[0].get("medio")) not in B.SIN_MEDIO:
            p["reparto"] = [{**rep[0], "porcentaje": 100}]
            hizo = True
    return hizo


# ══ LA CAPA BUSCAR, 9-nov, `arquitectura/PLAN_CAPAS.md`: medidas con `banco_pruebas/capa_buscar.py` ══

def _casi(a: str, b: str) -> bool:
    """Iguales, o a una letra sobrante, faltante o dos vecinas cruzadas: la errata de un mensaje. Una letra cambiada no:
    "menor" no es "mejor", es otra palabra."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1 or min(len(a), len(b)) < 4:
        return False
    if len(a) == len(b):
        d = [i for i in range(len(a)) if a[i] != b[i]]
        return len(d) == 2 and d[1] == d[0] + 1 and a[d[0]] == b[d[1]] and a[d[1]] == b[d[0]]
    corto, largo = sorted((a, b), key=len)
    return any(largo[:i] + largo[i + 1:] == corto for i in range(len(largo)))


def _frase_en(frase: list, palabras: list) -> bool:
    """La frase, palabra por palabra seguidas, en lo dicho; la ultima palabra de la frase vale como comienzo, "mas barat"
    es "mas baratos", y cada palabra admite una errata."""
    for i in range(len(palabras) - len(frase) + 1):
        if all(_casi(f, palabras[i + j]) or (j == len(frase) - 1 and len(f) >= 4 and
               (palabras[i + j].startswith(f) or _casi(f, palabras[i + j][:len(f)]) or _casi(f, palabras[i + j][:len(f) + 1])))
               for j, f in enumerate(frase)):
            return True
    return False


def orden_que_no_dijo(c: _Ctx) -> bool:
    """UN ORDEN QUE EL CLIENTE NO DIJO NO ORDENA: "el precio no es tan importante" o "si es Logitech, mejor" llegaban
    como "mas caro", y la busqueda mostraba lo mas caro de la tienda. Vale el orden que la cita nombra, por su nombre o
    por una frase del vocabulario de la tienda. Se mira todo lo que dijo el cliente en el mensaje, las citas juntas: "dos
    mouse y dos teclados, los mas baratos" ordena las dos busquedas. Si la agenda trae el mensaje, `mensaje`, se mira el
    mensaje: hay modelos que cortan la cita y dejan el orden solo en su campo. Una errata de una letra vale, "baartos".
    Si no nombra ninguno, no hay orden. No interpreta: solo comprueba que lo dicho este en lo que dijo.
    EL ORDEN DICHO CON OTRAS PALABRAS, 10-nov, FICHA 92: "dada la crisis" o "de buena calidad" no estan en el
    vocabulario. La llamada 1 trae en `orden_cita` las palabras del cliente de donde lo saco; si estan literales en el
    mensaje, el orden queda. Asi se comprueba lo dicho sin sumar frases a una lista."""
    from . import marcador as MK
    voc = MK.vocabulario_respuestas(c.tienda)["ordenes"]
    frases = {o: [K.n(o)] + [K.n(f) for f in voc.get(o) or []] for o in K.ORDEN}
    dicho = K.n(c.agenda.get("mensaje") or " ".join(str(p.get("cita") or "") for p in c.ps)).split()
    hizo = False
    for p in c.acciones("buscar"):
        orden = K.n(p.get("orden"))
        if orden not in frases or not dicho:
            continue  # sin orden, o uno que el codigo no sabe ordenar: lo dice el ejecutor
        dichos = [o for o, fs in frases.items() if any(_frase_en(f.split(), dicho) for f in fs)]
        if orden in dichos or (K.n(p.get("orden_cita")) and _frase_en(K.n(p.get("orden_cita")).split(), dicho)):
            continue
        p["orden"] = dichos[0] if len(dichos) == 1 else "nada"
        hizo = True
    return hizo


def lo_corregido(c: _Ctx) -> bool:
    """LO QUE EL CLIENTE CORRIGE NO SE BUSCA: "un teclado redragon, ah no, mejor logitech" llegaba como dos busquedas y
    la corrección en el medio. La busqueda de un rubro antes de la correccion sale si despues hay otra del mismo rubro."""
    ps = c.ps
    corr = [i for i, p in enumerate(ps) if p.get("accion") == "otro" and K.n(p.get("que")) == "corrige"]
    if not corr:
        return False
    fuera = [p for i, p in enumerate(ps) if p.get("accion") == "buscar" and i < corr[-1]
             and any(q.get("accion") == "buscar" and K.n(q.get("rubro")) == K.n(p.get("rubro")) for q in ps[corr[-1]:])]
    if not fuera:
        return False
    c.agenda["preguntas"] = [p for p in ps if p not in fuera]
    return True


def rubro_con_marca(c: _Ctx) -> bool:
    """UN RUBRO CON UNA MARCA NO ES UN PRODUCTO: "tenes auriculares jbl?" llegaba como el producto "auriculares jbl", que
    nombra a varios, y el cliente recibia "cual de estos decis". Si lo que sobra del rubro lo ata el catalogo a un campo
    —la marca, la conexion—, es una busqueda del rubro con esa condicion."""
    hizo = False
    for p in c.acciones("producto"):
        nombre = str(p.get("producto") or "")
        if K.identificar(nombre, "", c.tienda).get("veredicto") != "ambiguous":
            continue
        ws = K.n(nombre).split()
        rub, resto = next(((K.solo_rubro(" ".join(ws[:i]), c.tienda), " ".join(ws[i:])) for i in range(len(ws) - 1, 0, -1)
                           if K.solo_rubro(" ".join(ws[:i]), c.tienda)), ("", ""))
        if not rub:
            continue
        universo = [x for x in K.productos(c.tienda) if x.get("categoria") == rub]
        if "campo" not in K.atar(resto, universo, c.tienda):
            continue
        quiere = K.n(p.get("quiere_saber"))
        for k in ("producto", "quiere_saber", "color", "afirma"):
            p.pop(k, None)
        p.update(accion="buscar", rubro=rub, cantidad=1, orden="nada", condiciones=[resto]
                 + ([] if quiere in _PRECIO else [quiere]))
        hizo = True
    return hizo


def alternativa_compatible(c: _Ctx) -> bool:
    """"SI NO VA, QUE OTRA HAY": la busqueda que depende de una compatibilidad que da que no busca la que si va con ese
    equipo. Llegaba sin condicion y mostraba las mismas memorias DDR4 que no entraban. El equipo de la compatibilidad
    pasa a ser la condicion de la busqueda: lo que el catalogo ata a un dato de la ficha —"placa DDR5" es la
    ram DDR5—, sin las palabras sueltas que solo ata a etiquetas, "pc", "escritorio"."""
    por_n = {K.entero(p.get("n")): p for p in c.ps}
    hizo = False
    for p in c.acciones("buscar"):
        si = p.get("si") if isinstance(p.get("si"), dict) else {}
        q = por_n.get(K.entero(si.get("de")))
        if not q or q.get("accion") != "compatibilidad" or K.n(si.get("da")) != "no" or _lista(p.get("condiciones")) \
                or not q.get("con"):
            continue
        f = K.atar(str(q["con"]), K.productos(c.tienda), c.tienda)
        datos = [str(x["valor"]) for x in (f.get("todas") or [f]) if x.get("campo") not in (None, "tags") and not x.get("niega")]
        p["condiciones"] = [" ".join(datos) if datos else str(q["con"])]
        hizo = True
    return hizo


def producto_del_envio(c: _Ctx) -> bool:
    """"CUANTO SALE MANDAR UN G203 A ROSARIO" pregunta el envio y el producto: el modelo dejaba solo el envio, y el cliente
    no sabia el precio de lo que mandaba. Un producto que la tienda certifica en la cita de un envio, y que ninguna otra
    pregunta nombra, se pregunta tambien: su precio."""
    # SE COMPARA POR PRODUCTO, 10-nov: "un g203 a" no esta escrito en "G203", pero es el mismo producto certificado.
    ids = lambda x: {str(v["id"]) for v in K.identificar(str(x), "", c.tienda).get("variantes") or []}  # noqa: E731
    ya = set().union(*[ids(x) for p in c.ps for x in _lista(p.get("producto")) + [
        a.get("producto") for a in _lista(p.get("agrega")) if isinstance(a, dict)]])
    if len(c.acciones("envio")) != 1:
        return False  # "un G203 a Rosario y otro a Mendoza" manda unidades a cada lugar: es una compra, no el precio
    hizo = False
    for p in c.acciones("envio"):
        ws = K.n(p.get("cita")).split()
        for largo in (3, 2, 1):
            # Un numero solo es una cantidad, una altura o un precio, no un producto: "Sabatini 2000" no es la FaceCam 2000X.
            hallado = next((" ".join(ws[i:i + largo]) for i in range(len(ws) - largo + 1)
                            if not all(w.isdigit() for w in ws[i:i + largo])
                            and K.identificar(" ".join(ws[i:i + largo]), "", c.tienda).get("veredicto") == "exists"), "")
            if hallado:
                break
        if hallado and not ids(hallado) & ya:
            c.agenda["preguntas"] = _numerar(c.ps + [{"n": None, "cita": p.get("cita"), "accion": "producto",
                                                      "producto": hallado, "quiere_saber": "precio"}])
            ya |= ids(hallado)
            hizo = True
    return hizo


def compra_si_sale(c: _Ctx) -> bool:
    """"SI EL K120 NEGRO SALE MENOS DE 10 MIL, LLEVO DOS": la compra depende de un dato del producto, su precio. Llegaba
    como una compra atada a otra pregunta, o sin condicion, y se anotaba sin mirar el precio. Si la cita de una compra de
    un solo producto trae un tope de plata que el catalogo ata, se pregunta el producto con esa condicion y la compra
    depende de que de que si: el codigo mira el precio real."""
    hizo = False
    for p in list(c.acciones("comprar")):
        ag = [a for a in _lista(p.get("agrega")) if isinstance(a, dict) and a.get("producto")]
        if len(ag) != 1 or "tope" not in K.atar(str(p.get("cita") or ""), [], c.tienda):
            continue
        si = p.get("si") if isinstance(p.get("si"), dict) else {}
        previa = next((q for q in c.ps if K.entero(q.get("n")) == K.entero(si.get("de"))), None)
        if previa and previa.get("accion") == "producto" and K.n(previa.get("producto")) == K.n(ag[0]["producto"]):
            continue  # ya depende de la pregunta por ese producto
        nueva = {"n": c.nuevo_n(), "cita": p.get("cita"), "accion": "producto", "producto": ag[0]["producto"],
                 "quiere_saber": str(p.get("cita")), **({"color": ag[0]["color"]} if ag[0].get("color") else {})}
        ps = c.ps
        ps.insert(ps.index(p), nueva)
        p["si"] = {"de": nueva["n"], "da": "si"}
        p.pop("condicion", None)
        c.agenda["preguntas"] = ps
        hizo = True
    return hizo


REGLAS = (referencias_cruzadas, color_ajeno, si_sin_efecto, politica_de_envio_con_lugar, envio_a_varios,
          dato_del_producto, compatibilidad_de_un_rubro, el_pedido_sin_pedido, lista_con_dato, rubro_inventado,
          # las capas del 9-nov, `arquitectura/PLAN_CAPAS.md`
          compra_si_sale, producto_del_envio, orden_que_no_dijo, lo_corregido, rubro_con_marca, alternativa_compatible,
          cuenta_de_lo_nombrado, cuenta_de_lo_buscado,
          un_destino_para_el_pedido, precio_con_envio, un_medio_es_todo)


def _numerar(ps: list) -> list:
    """Las preguntas nuevas toman un numero libre; las de antes conservan el suyo, que es el que usan los "si"."""
    usados = {K.entero(p.get("n")) for p in ps if p.get("n") is not None}
    sig = max(usados | {0}) + 1
    for p in ps:
        if p.get("n") is None:
            p["n"], sig = sig, sig + 1
    return ps


def normalizar(agenda, estado: dict, tienda_id: str, nums: dict) -> tuple:
    """(la agenda en forma normal, los nombres de las reglas que aplico)."""
    ag = copy.deepcopy(agenda if isinstance(agenda, dict) else {"preguntas": agenda})
    ag["preguntas"] = [p for p in A.preguntas(ag)]
    for i, p in enumerate(ag["preguntas"], 1):
        p.setdefault("n", i)
    c = _Ctx(ag, estado, tienda_id, nums)
    aplicadas = []
    for regla in REGLAS:
        if regla(c):
            aplicadas.append(regla.__name__)
    return ag, aplicadas
