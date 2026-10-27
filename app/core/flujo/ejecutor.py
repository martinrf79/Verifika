"""EL EJECUTOR — la agenda del interprete y el estado entran, los hechos y el estado nuevo salen (20-oct-2026).

La agenda es la de `agenda.py`: una pregunta por cada cosa que pidio el cliente, con una accion del menu. Cada
pregunta se cumple con UNA funcion de `Turno`, y termina en uno de estos estados:

  respondida    tiene sus hechos: lo que la fuente o la calculadora dijeron.
  repreguntada  falta un dato del cliente y se le pregunta; queda en `estado.abiertas` para el turno siguiente.
  no_aplica     dependia de otra pregunta —"si no hay"— y la condicion no se cumplio.
  nada          no pedia nada: un saludo, un dato de si mismo, lo que corrigio.

EL CANDADO: una pregunta que termina sin estado no se pierde en silencio, se le repregunta al cliente con su cita.
No se vuelve a leer el mensaje del cliente: lo que el interprete no puso en la agenda no existe para el codigo. Lo que
el modelo senala con un numero de la libreta —M-2, L-1— se resuelve con `interprete.numeros`, lo mismo que vio el modelo.
Los montos salen de la calculadora, por `agente.h_cuenta` y `agente.h_envio`.

Un hecho es un dict con "tipo" y "n", la pregunta que lo pidio. `redaccion.texto` los pasa a palabras en ese orden.
"""
import re
from app.core import agente, fuente
from app.logger import get_logger

from . import agenda as A
from . import borrador as B
from . import catalogo as K
from .estado import mostrar
from .normal import normalizar
from app.core.calculadora import _money as _plata

log = get_logger(__name__)


def _lista(x) -> list:
    return x if isinstance(x, list) else ([x] if x not in (None, "", {}) else [])


def _si(v) -> bool:
    return v is True or (isinstance(v, str) and K.n(v) in ("true", "si"))


def _modelo(nombre: str, tienda_id: str) -> str:
    """El modelo que nombra un candidato, para contar si una referencia apunta a uno o a varios: dos colores del
    mismo modelo son uno solo. Lo que no es un producto cuenta por su texto."""
    p = K.identificar(nombre, "", tienda_id).get("producto") or {}
    return p.get("modelo") or K.n(nombre)


def _modelo_de(p: dict) -> tuple:
    return (p.get("marca"), p.get("modelo") or p.get("id"))


def _no_achica(filas: list, entre: list, rubro: str, tienda_id: str) -> bool:
    """Las condiciones no dejan afuera nada de lo mostrado del rubro: entre lo mostrado no eligieron nada."""
    del_rubro = {_modelo_de(p) for p in (K.por_id(i, tienda_id) for i in entre) if not rubro or p.get("categoria") == rubro}
    return {_modelo_de(p) for p in filas} >= del_rubro


class Turno:
    def __init__(self, estado: dict, tienda_id: str):
        self.estado, self.tienda = estado, tienda_id
        self.hechos, self.preguntas, self.llamadas = [], [], []
        self.listas, self.pedidas = {}, {}  # lo buscado en este turno: filas y unidades pedidas, por rubro
        self.n, self.de = 0, {}  # la pregunta que se esta cumpliendo, y de que pregunta es cada repregunta
        self.resultados, self.estados = {}, {}  # por pregunta: si dio que si, para "si no hay"; y como termino
        self.nums, self.agenda, self.destinos, self.cambio, self.explicar = {}, [], [], False, None
        self.res, self.compra, self.derivado = [], None, False  # el borrador resuelto, y la compra que lo cambio
        self.lecturas, self.elegida = [], ""  # las lecturas que cierran para que elija el modelo, y la que eligio
        self.previos = None  # los renglones de antes de un reemplazo, por si saca lo que el cliente no nombro
        self.propuesta = {}  # lo propuesto con que llego el turno: vale solo para este
        self.sueltas = []  # lo que el candado no pudo resolver: lo puede contestar el vendedor, controlado
        self.normal = []  # las reglas de la forma normal que se aplicaron a la agenda
        self.esperas = {}  # lo que espera cada pregunta del bot: queda con ella en `estado.abiertas`

    def herramienta(self, nombre: str, **args) -> dict:
        r = agente.ejecutar(nombre, args, self.tienda)
        self.llamadas.append({"herramienta": nombre, "args": args, "vuelve": r})
        return r

    def preguntar(self, texto: str, espera: dict = None) -> None:
        if texto not in self.preguntas:
            self.preguntas.append(texto)
            self.de[texto] = self.n
        if espera:
            self.esperas[texto] = espera

    # ── productos ────────────────────────────────────────────────────────────

    def producto(self, nombre: str, quiere_saber: str = "", color: str = ""):
        """El producto y lo que pregunto de el. Devuelve si dio que si —hay, en ese color, y cumple lo que pregunto—,
        para lo que depende de esto: "si no hay en negro". None si no se sabe."""
        idt = K.identificar(nombre, color, self.tienda)
        if idt["veredicto"] == "not_found":
            self.hechos.append({"tipo": "no_existe", "nombre": nombre})
            return False
        if idt["veredicto"] == "ambiguous":
            opciones = [p["nombre"] for p in idt["opciones"]]
            self.preguntar("¿Cuál de estos decís: " + " o ".join(opciones) + "?", espera={
                "tipo": "cual", "opciones": opciones,
                "hace": [{"accion": "producto", "producto": "{eleccion}", "quiere_saber": quiere_saber, "color": color}]})
            return None
        p = idt["producto"]
        self.hechos.append({"tipo": "producto", "producto": p, "variantes": idt["variantes"],
                            "dato": self.dato(p, quiere_saber), "pide": quiere_saber,
                            "falta_color": bool(idt.get("falta_color"))})
        mostrar(self.estado, [p])
        ok = K.con_stock(p) and not idt.get("no_hay_color")
        q = K.n(quiere_saber)
        if ok and q and q not in ("todo", "precio", "stock", "disponibilidad", "precio y stock", "existencia"):
            f = K.atar(quiere_saber, [x for x in K.productos(self.tienda) if x.get("categoria") == p.get("categoria")],
                       self.tienda)
            ok = K.cumple(p, f) if "sin_campo" not in f else None
        return ok

    def dato(self, p: dict, quiere_saber: str) -> dict:
        """El dato que pregunto, del producto. Cada campo del catalogo es un dato —el registro sale del catalogo vivo,
        `filtros_catalogo.campos_filtrables`—, y se lo reconoce por su nombre o por como lo llaman los clientes, el
        alias de la tienda. Despues, por el campo donde vive la palabra —"inalambrico" vive en conexion—. Si no esta,
        {"valor": None} y, de la descripcion, solo la oracion que habla de eso: el codigo dice que no tiene el dato."""
        q = K.n(quiere_saber)
        if q in ("", "todo", "precio", "stock", "disponibilidad", "precio y stock", "existencia") \
                or "tope" in K.atar(quiere_saber, [], self.tienda):
            return {}  # un tope de plata se contesta con el precio, que ya va
        propias = set(K.n(p.get("nombre")).split())
        pedidas = [w for w in q.split() if len(w) > 2 and w not in propias and w not in K._RELLENO]
        clave = _campo_de(p, set(pedidas), self.tienda)
        if clave:
            return {"campo": clave, "valor": _valor_de(p, clave)}
        universo = [x for x in K.productos(self.tienda) if x.get("categoria") == p.get("categoria")]
        for parte in [q] + pedidas:
            f = K.atar(parte, universo, self.tienda)
            if "campo" in f and f["campo"] not in NO_SON_DATOS:
                return {"campo": f["campo"], "valor": _valor_de(p, f["campo"]) or None}
        return {"campo": quiere_saber, "valor": None, "dice": _oracion(p.get("descripcion"), pedidas)}

    # ── busquedas ────────────────────────────────────────────────────────────

    def busqueda(self, b: dict):
        nombre = str(b.get("rubro") or "")
        if K.n(nombre) == "el pedido":
            # OTRO ORDEN PARA TODO LO PEDIDO: el modelo dice una busqueda y el codigo la reparte a cada rubro del pedido,
            # que es la lista que se olvidaba. Sin pedido no hay nada que reordenar.
            b_ = self.estado["borrador"]
            rubros = dict.fromkeys(r for r in [*b_["lista"], *(K.solo_rubro(x["que"], self.tienda)
                                                                for x in b_["renglones"])] if r)
            # Reordena el catalogo entero de cada rubro: "entre lo mostrado" no vale para un orden nuevo de lo pedido.
            return all([self.busqueda({**b, "rubro": r, "cantidad": None, "entre_lo_mostrado": False})
                        for r in rubros]) if rubros else False
        toda = K.n(nombre) in ("toda la tienda", "todo", "")
        rub = "" if toda else K.rubro(nombre, self.tienda)
        if not toda and not rub:
            self.hechos.append({"tipo": "no_vende", "que": nombre})
            return False
        conds = [str(c) for c in _lista(b.get("condiciones"))]
        if toda and conds and all("sin_campo" in K.atar(c, K.productos(self.tienda), self.tienda) for c in conds):
            # EN TODA LA TIENDA, LO QUE NINGUNA FICHA NOMBRA ES ALGO QUE LA TIENDA NO TIENE: "drones" no trae mouses.
            self.hechos.append({"tipo": "no_vende", "que": ", ".join(conds)})
            return False
        orden = str(b.get("orden") or "nada")
        cuantos = K.entero(b.get("cantidad"), 1) if K.n(orden) not in ("nada", "") else 5
        entre = [m["id"] for m in self.estado["mostrados"]] if _si(b.get("entre_lo_mostrado")) else None
        r = K.buscar(rub, conds, orden, cuantos, self.tienda, entre)
        aviso = ""
        if entre is not None and conds and (not r["filas"] or r["vacio_por"]):
            # ENTRE LO MOSTRADO NO HAY LO QUE PIDE: se busca en la tienda, que es lo que quiere saber, y se dice.
            afuera = K.buscar(rub, conds, orden, cuantos, self.tienda)
            if afuera["filas"] and not afuera["vacio_por"]:
                r, entre, aviso = afuera, None, "fuera"
        elif (entre is None or not conds or _no_achica(r["filas"], entre, rub, self.tienda)) \
                and K.n(orden) in ("nada", "") and r["filas"]:
            # LO MISMO DE NUEVO NO ES UNA RESPUESTA: si todo lo que trae ya lo vio, van los que no vio. Entre lo mostrado
            # y sin condicion tampoco elige nada: es pedir otras opciones.
            vistos = {_modelo_de(K.por_id(m["id"], self.tienda)) for m in self.estado["mostrados"]}
            if all(_modelo_de(p) in vistos for p in r["filas"]):
                ids = [str(p["id"]) for p in K.productos(self.tienda) if (not rub or p.get("categoria") == rub)
                       and _modelo_de(p) not in vistos]
                otros = K.buscar(rub, conds, orden, cuantos, self.tienda, ids)
                if otros["filas"] and not otros["vacio_por"]:
                    r, aviso = otros, "otros"
        self.hechos.append({"tipo": "lista", "rubro": rub or "la tienda", "aviso": aviso, **r})
        if rub:
            self.listas[rub] = {"filas": r["filas"], "orden": orden}
            self.pedidas[rub] = self.pedidas.get(rub, 0) + max(1, K.entero(b.get("cantidad"), 1))
        mostrar(self.estado, r["filas"])
        self.estado["busqueda"] = {"rubro": rub, "condiciones": conds, "orden": orden}
        if rub:
            # Un orden sin dato en las fichas —"el mas vendido"— no cambia lo que ya se eligio para el pedido.
            vale = orden if not r["orden_desconocido"] else \
                (self.estado["borrador"]["criterios"].get(rub) or {}).get("orden") or "nada"
            B.anotar_busqueda(self.estado["borrador"], rub, conds, vale, entre)
        return bool(r["filas"]) and not r["vacio_por"]

    # ── la plata ─────────────────────────────────────────────────────────────

    def cuenta(self, articulos: list, reparto: list, tope=None, si_pasa: str = "") -> None:
        """Una cuenta por destino. Con mas de un destino, el total general es la suma de los totales y el reparto
        del pago se calcula una sola vez, sobre ese total."""
        grupos, nombre = {}, {}  # por destino sin mayusculas ni tildes, con el nombre como lo escribio primero
        for a in articulos:
            d = nombre.setdefault(K.n(a.get("destino")), a.get("destino") or "")
            grupos.setdefault(d, []).append({"id": a["id"], "cantidad": a["cantidad"]})
        varios = len(grupos) > 1
        tope = K.entero(tope)
        bloques = []
        for destino, items in grupos.items():
            r = self.herramienta("cuenta", items=items, destinos=[destino] if destino else [],
                                 reparto_pago=None if varios else (reparto or None))
            # Un envio que no se pudo cotizar no se calla: el total sin el no es el total, 27-oct, K09.
            sin_envio = any(f.get("sin_dato") for f in (r.get("envio") or {}).get("filas") or [])
            if (r.get("cuenta") or {}).get("total_ars") is not None and not sin_envio:
                bloques.append({"destino": destino, **r["cuenta"]})
            else:
                # Una cuenta a medias no se muestra como entera: se pregunta lo que falta.
                self.preguntar(f"No pude calcular el envío a {destino}: ¿me pasás la provincia o el código postal?"
                               if destino else "No pude armar la cuenta: ¿me confirmás los productos?")
                return
        general = self.general(bloques, reparto) if varios else None
        total = (general or {}).get("total_final_ars") or (general or {}).get("total_ars") \
            or int(bloques[0].get("total_final_ars") or bloques[0]["total_ars"])
        if tope and total > tope and si_pasa:
            idt = K.identificar(si_pasa, "", self.tienda)
            saca = {str(v["id"]) for v in idt.get("variantes") or []}
            quedan = [a for a in articulos if str(a["id"]) not in saca]
            if saca and quedan and len(quedan) < len(articulos):
                self.hechos.append({"tipo": "pasa_tope", "tope": tope, "saca": idt["producto"]["nombre"]})
                if articulos is self.estado["pedido"]:
                    # Lo dijo el cliente: si pasa, sale. Sale del borrador, y el pedido es lo que queda.
                    b = self.estado["borrador"]
                    fuera = {x["L"] for x in self.res for a in x.get("articulos") or [] if str(a["id"]) in saca}
                    b["renglones"] = [r for r in b["renglones"] if r["L"] not in fuera]
                    self.estado["pedido"] = quedan
                return self.cuenta(quedan, reparto)
        if tope and total > tope:
            # Sin decir que saca, un total que pasa el tope no se da por bueno: se le pregunta.
            self.preguntar(f"El total pasa tu tope de {_plata(tope)}. ¿Saco algo o cambio algún producto?")
        self.hechos.append({"tipo": "cuenta", "bloques": bloques, "general": general,
                            **({"tope": tope, "total": total} if tope and total <= tope else {})})

    def general(self, bloques: list, reparto: list) -> dict:
        """El total general de varios destinos y, si reparte el pago, el reparto sobre ese total: lo calcula
        `pago_split`, el mismo de la calculadora."""
        from app.core.calculadora import _money
        from app.core.pago_split import calcular_split, descuento_de, render_split
        base = sum(int(b["total_ars"]) for b in bloques)
        out = {"total_ars": base, "detalle": f"Total general: {_money(base)}"}
        if reparto:
            split = calcular_split(base, reparto, *descuento_de(self.tienda))
            if split.get("ok"):
                out["total_final_ars"] = split["total_final_ars"]
                out["detalle"] += "\n\n" + render_split(split)
        return out

    def derivar(self) -> None:
        """EL BORRADOR, re-derivado entero: lo que falta y lo supuesto se preguntan desde ahi; el pedido es lo resuelto."""
        b, antes = self.estado["borrador"], self.estado["pedido"]
        B.elegir(b, self.elegida, self.tienda)
        self.res = B.resolver(b, self.tienda, self.lecturas)
        falta = B.faltantes(b, self.res)
        arts = B.articulos(self.res, falta)
        # Lo que todavia falta elegir sigue en el pedido: un renglon con varios modelos no saca su rubro.
        presentes = [a for x in self.res for a in x.get("articulos") or []] + [
            {"id": str(K.identificar(x["opciones"][0], "", self.tienda).get("producto", {}).get("id") or ""),
             "nombre": x["opciones"][0], "destino": (x.get("renglon") or {}).get("destino") or ""}
            for x in falta if x.get("falta") == "modelo" and x.get("opciones")]
        perdidos = _perdidos(antes, presentes, self.tienda) if self.previos is not None and antes else []
        if perdidos:
            # NUNCA SE PIERDE EL PEDIDO EN SILENCIO: un reemplazo que deja afuera rubros o destinos que estaban no se
            # aplica de una. Queda propuesto, con lo que saldria dicho, hasta que el cliente lo acepte.
            b["propuesta"] = {"renglones": b["renglones"], "texto": "Con ese cambio saco del pedido "
                              + B._y(perdidos) + "."}
            b["renglones"] = self.previos
            self.res = B.resolver(b, self.tienda, self.lecturas)
            falta = B.faltantes(b, self.res)
            arts = B.articulos(self.res, falta)
        self.estado["pedido"] = arts
        self.n = self.compra or self.n
        esperas = B.esperas(b, falta)
        for q in B.preguntas(b, falta):
            self.preguntar(q, esperas.get(q))
        if not arts and falta:
            # Lo que ya quedo claro se muestra una vez; lo elegido de un rubro no, que su lista ya esta en el mensaje.
            de_lista = {str(p["id"]) for x in self.listas.values() for p in x["filas"]}
            claros = [a for x in self.res if not x.get("falta") for a in x.get("articulos") or []]
            for pid in dict.fromkeys(a["id"] for a in claros if a["id"] not in de_lista):
                self.hechos.append({"tipo": "producto", "producto": K.por_id(pid, self.tienda), "variantes": [],
                                    "dato": {}, "pide": ""})
            mostrar(self.estado, [{"id": a["id"], "nombre": a["nombre"], "precio_ars": a["precio"]} for a in claros])
            return
        # LO SUPUESTO SE DICE mientras no lo acepte: la pregunta de si se deja asi no queda sin su contexto.
        self.hechos += [{"tipo": "supuesto", "texto": x["supuesto"]["texto"], "n": self.n} for x in self.res
                        if x.get("supuesto")]
        # UN PEDIDO QUE CAMBIO se dice, lo haya cambiado una compra o un criterio nuevo: "todo con lo mejor".
        if B.huella(arts) != B.huella(antes) and (self.compra or antes):
            elegidos = {r: {"nombre": nom, "orden": (b["criterios"].get(r) or {}).get("orden") or "nada"}
                        for x in self.res for r, nom in (x.get("elegidos") or {}).items()}
            # SE DICE LO ELEGIDO DE UNA LISTA DE ESTE TURNO, y lo que el cliente nunca vio ni estaba en su pedido: el
            # teclado pedido sin buscar entraba como la primera opcion, el de 512 mil, sin aviso.
            vistos = {m["nombre"] for m in self.estado["mostrados"]} | {a["nombre"] for a in antes}
            elegidos = {r: e for r, e in elegidos.items() if r in self.listas or e["nombre"] not in vistos}
            if elegidos:
                self.hechos.append({"tipo": "elegidos", "rubros": elegidos, "n": self.n})
            self.hechos.append({"tipo": "pedido", "articulos": arts, "n": self.n} if arts
                               else {"tipo": "pedido_vacio", "n": self.n})
            self.cambio = True


# Lo que nombra al producto o lo vende, no lo describe: no es un dato que se pregunta.
NO_SON_DATOS = ("nombre", "modelo", "descripcion", "tags", "precio_ars", "stock", "categoria", "id")


def _valor_de(p: dict, campo: str) -> str:
    from app.core.filtros_catalogo import _valor_crudo
    if campo == "garantia_meses" and p.get("garantia_meses"):
        return f"{p['garantia_meses']} meses"
    v = _valor_crudo(p, campo)
    return str(v).strip() if v not in (None, "") else ""


def _campo_de(p: dict, palabras: set, tienda_id: str) -> str:
    """El campo con valor en este producto que nombra la pregunta: por la raiz de su nombre —"peso" es peso_gramos—, o
    por una frase entera de como lo llaman los clientes —"cuanto dura la carga" es bateria—. Las frases van enteras: de
    a una palabra, "compacto" llevaba "compatibilidad" a las dimensiones."""
    from app.core.filtros_catalogo import campos_filtrables
    if not palabras:
        return ""
    raices = {w[:5] for w in palabras if len(w) > 3}
    frases = _frases_de_campos(tienda_id)
    puntos = {}
    for c in dict.fromkeys(list(campos_filtrables(tienda_id)) + list((p.get("specs") or {}).keys())):
        if c in NO_SON_DATOS or not _valor_de(p, c):
            continue
        n_ = 2 * len({w[:5] for w in K.n(c).replace("_", " ").split() if len(w) > 3} & raices)
        n_ += sum(1 for f in frases.get(c, ()) if f <= palabras)
        if n_:
            puntos[c] = n_
    if not puntos:
        return ""
    # Si dos campos empatan —garantia_meses y garantia_detalle—, el de valor mas corto: es la respuesta directa.
    tope = max(puntos.values())
    return min((c for c, n_ in puntos.items() if n_ == tope), key=lambda c: len(_valor_de(p, c)))


_FRASES = {}


def _frases_de_campos(tienda_id: str) -> dict:
    """{campo: [palabras de cada frase del alias, sin relleno]}, de `alias.json` de la tienda."""
    if tienda_id not in _FRASES:
        from app.core import agente
        al = agente._alias(tienda_id).get("campos") or {}
        _FRASES[tienda_id] = {c: [set(w for w in K.n(f).split() if w not in K._RELLENO and len(w) > 2) - {""}
                                  for f in fs] for c, fs in al.items()}
        _FRASES[tienda_id] = {c: [f for f in fs if f] for c, fs in _FRASES[tienda_id].items()}
    return _FRASES[tienda_id]


def _oracion(descripcion, palabras: list) -> str:
    """De la descripcion, la oracion que nombra lo que pregunto. Si ninguna lo nombra, la descripcion entera: puede
    decirlo con otras palabras —"sirve para jugar" y "Ideal para Gaming"—, y lo conciso no vale una respuesta."""
    raices = {w[:5] for w in palabras if len(w) > 3}
    for o in re.split(r"(?<=[.!?])\s+", str(descripcion or "")):
        if raices & {w[:5] for w in re.findall(r"[a-z0-9]+", K.n(o))}:
            return o.strip()
    return str(descripcion or "").strip()


def _perdidos(antes: list, arts: list, tienda_id: str) -> list:
    """Los rubros y los destinos que estaban en el pedido y ya no estan, dichos para el cliente."""
    rubro = lambda a: K.por_id(a["id"], tienda_id).get("categoria") or a["nombre"]  # noqa: E731
    rubros = [r for r in dict.fromkeys(map(rubro, antes)) if r not in set(map(rubro, arts))]
    destinos = [d for d in dict.fromkeys(K.n(a.get("destino")) for a in antes if a.get("destino"))
                if d not in {K.n(a.get("destino")) for a in arts}]
    nombre = {K.n(a.get("destino")): a["destino"] for a in antes if a.get("destino")}
    return [f"{r}" for r in rubros] + [f"todo lo que iba a {nombre[d]}" for d in destinos]


# ══ LAS ACCIONES: una funcion por accion del menu ═════════════════════════════

def _nombres(t: Turno, x) -> list:
    """Lo que nombra el modelo, en nombres que entiende `identificar`: un numero de la libreta es lo que senala."""
    out = []
    for v in _lista(x):
        v = str(v).strip()
        ref = t.nums.get(v)
        if v[:1] == "M" and ref:
            v = K.por_id(ref, t.tienda).get("nombre") or v
        elif v[:1] == "L" and isinstance(ref, dict):
            v = ref["que"]
        elif A._REF.match(v):
            continue  # un numero que no esta en la libreta no se le muestra al cliente: "M-2" no es un producto
        if v:
            out.append(v)
    return out


def _uno(t: Turno, x, hace: dict = None) -> str:
    """El unico producto que nombra, o "" despues de preguntar cual si puede ser varios. `hace` es la pregunta que
    sigue con el que elija, con "{eleccion}" en su lugar: la respuesta corta la retoma, `atar_esperas`."""
    nombres = _nombres(t, x)
    if len({_modelo(n, t.tienda) for n in nombres}) > 1:
        t.preguntar("¿Cuál decís: " + " o ".join(nombres) + "?" if len(nombres) <= 4
                    else "¿Cuál de los que te mostré decís?",
                    espera={"tipo": "cual", "opciones": nombres, "hace": [hace]} if hace else None)
        return ""
    return nombres[0] if nombres else ""


def _sin_n(p: dict) -> dict:
    return {k: v for k, v in p.items() if k not in ("n", "responde", "si")}


def _producto(t: Turno, p: dict):
    nombre = _uno(t, p.get("producto"), hace={**_sin_n(p), "producto": "{eleccion}"})
    if nombre:
        ok = t.producto(nombre, str(p.get("afirma") or p.get("quiere_saber") or ""), str(p.get("color") or ""))
        if p.get("ofrece") and ok and not t.estado["pedido"]:
            # ELEGIDO POR EL DATO, de una lista: el vendedor ofrece el que cumple, asi la venta sigue.
            prod = K.identificar(nombre, str(p.get("color") or ""), t.tienda)["producto"]
            t.preguntar(f"¿Te reservo el {prod.get('modelo') or nombre}?", espera={
                "tipo": "si_no", "hace": [{"accion": "comprar", "agrega": [{"producto": prod["nombre"], "cantidad": 1}]}]})
        return ok


def _buscar(t: Turno, p: dict):
    return t.busqueda(p)


def _compatibilidad(t: Turno, p: dict):
    from app.core.compatibilidad import conectores_del_mensaje, plataformas_del_mensaje, va_adentro
    from app.core.guia_venta_prosa import mensaje
    con = str(p.get("con") or "")
    nombres = _nombres(t, p.get("producto"))
    unico = nombres[0] if len({_modelo(n, t.tienda) for n in nombres}) == 1 else ""
    idt = K.identificar(unico, "", t.tienda) if unico else {"veredicto": ""}
    existe = idt["veredicto"] == "exists"
    # LO QUE VA ADENTRO DEL EQUIPO PIDE SU MODELO: una memoria depende de la ranura de la placa, no de "PC". Salvo que
    # el cliente ya haya dicho la ranura o el zocalo.
    adentro = existe and va_adentro(idt["producto"], t.tienda) and not conectores_del_mensaje(con, t.tienda)
    # EL EQUIPO DEL VOCABULARIO NO PIDE MODELO: "mi iPad" ya dice con que juzgar un teclado Bluetooth. Se pregunta el
    # modelo si el equipo no esta en el vocabulario, si el producto no es uno o si la tabla no alcanza para decir que
    # si, que no o entre cuales.
    conocido = existe and plataformas_del_mensaje(con, t.tienda) \
        and _veredicto(t, idt["producto"], con) in ("compatible", "incompatible", "ambiguo")
    if adentro or (_si(p.get("falta_modelo")) and not conocido):
        t.preguntar(f"¿Qué modelo es tu {con}? Con eso te confirmo qué le sirve.",
                    espera={"tipo": "equipo", "producto": unico, "con": con, "opciones": []})
        return None
    nombre = _uno(t, p.get("producto"))
    if nombre != unico:
        idt = K.identificar(nombre, "", t.tienda) if nombre else {"veredicto": ""}
    if idt["veredicto"] != "exists":
        if nombre:
            t.preguntar(f"¿Qué {nombre} decís, el modelo exacto?")
        return None
    prod = idt["producto"]
    r = t.herramienta("compatibilidad", producto=str(prod["id"]), con=con)
    vs = [v for v in _lista(r.get("compatibilidad")) if isinstance(v, dict)]
    for v in [v for v in vs if v.get("veredicto") == "ambiguo"]:
        # UN EQUIPO QUE PUEDE SER VARIOS SE PREGUNTA, y la pregunta espera uno de ellos: "mi tablet", Android o iPad.
        t.preguntar(mensaje("compat_cual_equipo", "¿Tu {equipo} es {opciones}? Con eso te confirmo si el {producto} "
                            "le sirve.", equipo=con, opciones=" o ".join(v.get("candidatos") or []),
                            producto=prod["nombre"]),
                    espera={"tipo": "equipo", "producto": prod["nombre"], "con": con,
                            "opciones": plataformas_del_mensaje(con, t.tienda)})
    t.hechos += [{"tipo": "compat", **v} for v in vs if v.get("veredicto") != "ambiguo"]
    # El cliente leyo el producto, en la respuesta o en la pregunta: "ese" lo senala despues.
    mostrar(t.estado, [prod])
    veredictos = {v.get("veredicto") for v in vs}
    return True if "compatible" in veredictos else (False if "incompatible" in veredictos else None)


def _veredicto(t: Turno, p: dict, con: str) -> str:
    """Lo que diria la tabla, sin anotarlo: para saber si hace falta preguntar el modelo."""
    vs = [v for v in _lista(agente.ejecutar("compatibilidad", {"producto": str(p["id"]), "con": con}, t.tienda)
                            .get("compatibilidad")) if isinstance(v, dict)]
    return vs[0].get("veredicto") if len(vs) == 1 else ""


def _politica(t: Turno, p: dict):
    # SOLO UN TEMA DE LA FAQ: un texto suelto encontraba por parecido otra regla —"instalacion a domicilio" daba la de
    # cambio de direccion—. Lo que la FAQ no tiene, el codigo dice que no tiene informacion escrita.
    if str(p["tema"]) not in agente.indice(t.tienda)["temas"]:
        t.hechos.append({"tipo": "sin_politica"})
        return
    pols = fuente.politicas_de([str(p["tema"])], t.tienda, con_base=True).get("politicas") or []
    # Solo las politicas: el criterio de la FAQ es una instruccion para el que redacta, no texto para el cliente.
    t.hechos += [{"tipo": "politica", "tema": x.get("tema"), "texto": x.get("texto"), "base": x.get("base")}
                 for x in pols]
    if not pols:
        t.hechos.append({"tipo": "sin_politica"})


def _reparto(t: Turno, p: dict) -> bool:
    """El pago dicho va al borrador. Sin medio no se cuenta —"sin decir (70%)" no es un cobro—: lo pregunta el borrador."""
    reparto = [r for r in _lista(p.get("reparto")) if isinstance(r, dict) and r.get("porcentaje")]
    if not reparto:
        return False
    B.aplicar(t.estado["borrador"], {"reparto": reparto})
    completo = bool(B.pago_listo(t.estado["borrador"]))
    if not completo and not t.estado["borrador"]["renglones"]:
        t.preguntar("¿Con qué medio pagás cada parte: " + " y ".join(f"el {K.entero(r['porcentaje'])}%"
                                                                    for r in reparto) + "?")
    return completo


CAMBIAN = ("agrega", "saca", "cambia", "reemplaza", "total")


def _supuestos(t: Turno) -> list:
    return [x["L"] for x in B.resolver(t.estado["borrador"], t.tienda) if x.get("supuesto")]


def _acepta(t: Turno, p: dict) -> list:
    """Lo supuesto que acepta esta pregunta, aunque el modelo no haya escrito "acepta": confirmar lo supuesto es
    aceptarlo, y contestar que si a "¿Lo dejo así?" sin cambiar nada tambien."""
    acepta = _lista(p.get("acepta"))
    sup = _supuestos(t) if p.get("confirma") or p.get("responde") else []
    acepta += [r for r in _lista(p.get("confirma")) if r in sup]
    r = t.nums.get(str(p.get("responde") or "").strip())
    # Contestar "¿Lo dejo así?" es aceptar si el mensaje no cambia nada: "el teclado va aparte" la contesta corrigiendo.
    if isinstance(r, dict) and r.get("texto") == B.LO_DEJO and not _cambia(t):
        acepta += sup
    return list(dict.fromkeys(acepta))


def _cambia(t: Turno) -> bool:
    return any(_lista(p.get(k)) for p in t.agenda for k in CAMBIAN)


def _solo_si(t: Turno) -> bool:
    """El mensaje entero es un "si", y lo unico abierto es "¿Lo dejo así?"."""
    if [a["texto"] for a in t.estado["abiertas"]] != [B.LO_DEJO]:
        return False
    # Lo que dice un "si" y nada mas, con las palabras de la tienda: acepta lo supuesto sin modelo.
    from .marcador import vocabulario_respuestas
    afirma = {w for f in vocabulario_respuestas(t.tienda)["si"] for w in f.split()}
    palabras = [w for p in t.agenda for w in A.palabras(p.get("cita"))]
    return bool(palabras) and all(w in afirma or w in A._VACIAS for w in palabras) and not _cambia(t)


def _el_que_cumple(t: Turno, a: dict, cond: str):
    """LA COMPRA CON CONDICION —"si sale menos de 10 mil llevo dos", "de estos dos, el inalambrico", "me lo llevo si
    anda con Mac"—: el codigo mira cada producto contra la condicion, y queda el que la cumple. Devuelve su nombre,
    "" si ninguno la cumple, None si no se pudo saber, o False si la cumplen varios, y ahi pregunta cual."""
    from app.core.compatibilidad import plataformas_del_mensaje
    nombres = _nombres(t, a.get("producto"))
    juicios = []
    for nombre in nombres:
        if plataformas_del_mensaje(cond, t.tienda):
            juicios.append((nombre, _compatibilidad(t, {"producto": nombre, "con": cond})))
        else:
            juicios.append((nombre, t.producto(nombre, cond, str(a.get("color") or ""))))
    si = [n for n, ok in juicios if ok]
    if len(si) == 1:
        return si[0]
    if len(si) > 1:
        sin_cond = {k: v for k, v in a.items() if k != "si_cumple"}
        t.preguntar("¿Cuál querés: " + " o ".join(si) + "?", espera={
            "tipo": "cual", "opciones": si, "hace": [{"accion": "comprar", "agrega": [{**sin_cond, "producto": "{eleccion}"}]}]})
        return False
    if any(ok is None for _, ok in juicios):
        return None
    t.hechos.append({"tipo": "no_cumple", "que": cond, "varios": len(nombres) > 1})
    return ""


def _comprar(t: Turno, p: dict):
    """El cambio de este mensaje sobre lo dicho: va al borrador, que re-deriva el pedido entero."""
    cambio = _reparto(t, p)
    agrega = []
    items = [a for a in _lista(p.get("agrega")) if isinstance(a, dict) and a.get("producto")]
    if p.get("si_cumple") and len(items) > 1 and not any(isinstance(a["producto"], list) for a in items):
        # "De estos dos, dame el inalambrico" escrito como dos articulos con una condicion: son candidatos de uno.
        items = [{**items[0], "producto": [a["producto"] for a in items]}]
    for a in items:
        cond = str(a.get("si_cumple") or p.get("si_cumple") or "").strip()
        if cond:
            nombre = _el_que_cumple(t, a, cond)
            if nombre is False:
                continue
            if nombre is None:
                a = {**a, "producto": _nombres(t, a.get("producto"))[0]}
                p = {**p, "condicion": "sin_saber"}
            elif not nombre:
                continue
            else:
                agrega.append({**a, "producto": nombre, "cita": p.get("cita") or "", "condicion": ""})
                continue
        nombre = _uno(t, a.get("producto"), hace={"accion": "comprar", "agrega": [{**a, "producto": "{eleccion}"}]})
        if not nombre:
            return None
        agrega.append({**a, "producto": nombre, "cita": p.get("cita") or "", "condicion": p.get("condicion") or ""})
    if p.get("reemplaza") and t.previos is None:
        t.previos = [dict(r) for r in t.estado["borrador"]["renglones"]]
    B.aplicar(t.estado["borrador"], {**{k: p.get(k) for k in ("saca", "cambia", "confirma", "total", "reemplaza",
                                                                "responde")}, "agrega": agrega},
              pedidas=t.pedidas if agrega else None)
    t.compra = t.compra or t.n
    t.cambio = t.cambio or cambio
    return True


def _cuenta(t: Turno, p: dict):
    _reparto(t, p)
    if any(h["tipo"] == "cuenta" for h in t.hechos):
        # UNA CUENTA POR TURNO: "el 70 transferencia" y "armame presupuestos" piden la misma, con todo lo dicho, y
        # esa cuenta las contesta a las dos.
        t.estados[t.n] = "respondida"
        return True
    # El tope y lo que sale si pasa valen dichos en cualquiera de las preguntas de plata del mensaje.
    cuentas = [x for x in t.agenda if x.get("accion") == "cuenta"]
    tope = next((x["tope"] for x in cuentas if K.entero(x.get("tope"))), None)
    # EL TOPE DICHO VALE HASTA QUE DIGA OTRO: queda en el borrador, que guarda lo dicho.
    if tope:
        t.estado["borrador"]["tope"] = K.entero(tope)
    tope = tope or t.estado["borrador"].get("tope") or None
    si_pasa = next((_uno(t, x["si_pasa"]) for x in cuentas if x.get("si_pasa")), "")
    if t.estado["pedido"]:
        t.cuenta(t.estado["pedido"], B.pago_listo(t.estado["borrador"]), tope, si_pasa)
        return True
    compras = {x["n"] for x in t.agenda if x.get("accion") == "comprar"}
    if t.estado["borrador"]["renglones"]:
        # La cuenta de un pedido a medias espera lo que le falta: no se muestra una cuenta parcial.
        t.estados[t.n] = "repreguntada"
        return None
    if compras and all(t.estados.get(n) == "no_aplica" for n in compras):
        t.estados[t.n] = "no_aplica"
        return None
    # UN TOTAL SIN PEDIDO: lo que pregunto en este mensaje, una unidad de cada uno, al destino que dijo.
    productos = [h for h in t.hechos if h["tipo"] == "producto"]
    # Sin color elegido vale el precio del modelo solo si todos sus colores salen lo mismo.
    dudosos = [h for h in productos if h.get("falta_color")
               and len({v.get("precio_ars") for v in h["variantes"] if K.con_stock(v)}) > 1]
    destino = next(iter(t.destinos), "")
    for h in dudosos:
        # Con un solo producto, la respuesta corta retoma la cuenta: el producto en ese color, el envio y la cuenta.
        colores = list(dict.fromkeys(v["color"] for v in h["variantes"] if K.con_stock(v) and v.get("color")))
        hace = [{"accion": "producto", "producto": h["producto"]["nombre"], "color": "{eleccion}"}] \
            + ([{"accion": "envio", "destino": destino}] if destino else []) + [{"accion": "cuenta"}]
        t.preguntar(f"¿El {h['producto'].get('modelo')} en qué color? Cambia el precio.",
                    espera={"tipo": "color", "opciones": colores, "hace": hace} if len(productos) == 1 else None)
    items = [{"id": str(h["producto"]["id"]), "cantidad": 1, "destino": destino} for h in productos]
    if items and not dudosos:
        t.cuenta(items, B.pago_listo(t.estado["borrador"]))
    elif not items:
        t.preguntar("¿De qué productos querés la cuenta?")


def _envio(t: Turno, p: dict):
    """Los envios se cotizan juntos al final, los que no entraron en una cuenta."""
    t.destinos.append(B._destino(p.get("destino")))


def _explicar(t: Turno, p: dict):
    t.hechos.append({"tipo": "explicar", "texto": t.explicar(str(p.get("pregunta") or "")) if t.explicar else ""})


def _otro(t: Turno, p: dict):
    que = K.n(p.get("que"))
    if que == "catalogo":
        t.hechos.append({"tipo": "catalogo", "rubros": sorted({x.get("categoria") for x in K.productos(t.tienda)})})
    elif que in ("humano", "fuera_de_tema"):
        t.hechos.append({"tipo": que})
    else:
        t.estados[t.n] = "nada"


ACCIONES = {"buscar": _buscar, "producto": _producto, "compatibilidad": _compatibilidad, "politica": _politica,
            "explicar": _explicar, "otro": _otro, "envio": _envio, "comprar": _comprar, "cuenta": _cuenta}
# LO QUE SE CONSULTA VA PRIMERO, en el orden del cliente; lo que cambia el pedido y la plata despues, porque usa lo
# buscado en el mismo mensaje: "dos mouse, los mas baratos, uno a Rosario" anota el que encontro la busqueda.
DESPUES = {"envio": 1, "comprar": 2, "cuenta": 3}


def _cumplir(t: Turno, p: dict) -> None:
    t.n = p["n"]
    antes = len(t.hechos)
    si = p.get("si") if isinstance(p.get("si"), dict) else None
    if si:
        r = t.resultados.get(K.entero(si.get("de")))
        if r is None and p["accion"] == "comprar":
            # Lo que depende de algo que no se pudo saber se anota a confirmar: el borrador lo pregunta.
            p["condicion"] = "sin_saber"
        elif r is not None and r != (K.n(si.get("da")) != "no"):
            t.estados[t.n] = "no_aplica"
            return
    acepta = _acepta(t, p)
    if acepta:
        # Lo que acepto de lo supuesto pasa a lo dicho antes que lo demas, aunque venga anotado como un dato.
        B.aplicar(t.estado["borrador"], B.aceptar(t.estado["borrador"], acepta, t.tienda))
        t.compra = t.compra or t.n
    t.resultados[t.n] = ACCIONES[p["accion"]](t, p)
    for h in t.hechos[antes:]:
        h.setdefault("n", t.n)


def ejecutar(agenda: dict, estado: dict, tienda_id: str, explicar=None, elegida: str = "") -> Turno:
    """La agenda entera, pregunta por pregunta. `elegida` es la huella de la lectura que eligio el modelo entre las que
    dejo `t.lecturas` una pasada anterior: ver `turno.procesar_turno`."""
    from .interprete import numeros
    t = Turno(estado, tienda_id)
    t.elegida = elegida
    # Los numeros de la libreta se toman antes de cumplir nada: son los que vio el modelo.
    estado["borrador"] = B.leer(estado.get("borrador"))
    t.propuesta = estado["borrador"]["propuesta"]
    t.nums, t.explicar = numeros(estado), explicar
    # LA FORMA NORMAL: lo que dijo el modelo, en la forma que se cumple aca. Ver `normal.py`.
    atar_esperas(agenda, t)
    agenda, t.normal = normalizar(agenda, estado, tienda_id, t.nums)
    cliente = agenda.get("cliente") if isinstance(agenda.get("cliente"), dict) else {}
    estado["borrador"]["cliente"].update({k: v for k, v in cliente.items() if v and k in ("localidad", "nombre", "es")})
    preguntas = t.agenda = A.preguntas(agenda)
    for i, p in enumerate(preguntas, 1):
        p.setdefault("n", i)
    if _solo_si(t):
        B.aplicar(estado["borrador"], B.aceptar(estado["borrador"], _supuestos(t), tienda_id))
        t.compra = preguntas[0]["n"]
    # CADA COMPRA SE APLICA AL BORRADOR EN SU ORDEN: "los otros" lo cuenta el borrador con todo lo dicho, asi que no hace
    # falta juntarlas. Juntarlas perdia lo que no era agrega, saca o cambia: la confirmacion y el total.
    # Una accion fuera del menu no se cumple: la agarra el candado de abajo.
    for p in sorted(preguntas, key=lambda p: DESPUES.get(p.get("accion"), 0)):
        if DESPUES.get(p.get("accion"), 0) >= 3 and not t.derivado:
            _derivar(t)
        if p.get("accion") in ACCIONES:
            _cumplir(t, p)
    if not t.derivado:
        _derivar(t)
    # UN PEDIDO QUE CAMBIO SE CUENTA aunque no lo haya pedido: el cliente ve como queda.
    if t.cambio and t.estado["pedido"] and not any(h["tipo"] == "cuenta" for h in t.hechos):
        t.n = max(p["n"] for p in preguntas if p["accion"] == "comprar") if any(
            p["accion"] == "comprar" for p in preguntas) else t.n
        antes = len(t.hechos)
        t.cuenta(t.estado["pedido"], B.pago_listo(t.estado["borrador"]))
        for h in t.hechos[antes:]:
            h.setdefault("n", t.n)
    # CON EL PEDIDO ARMADO, LA FAQ VA LLANA: la curada termina invitando a elegir un producto, y ya lo eligio. Se decide
    # al final porque la politica se cumple antes que la compra del mismo mensaje.
    if t.estado["pedido"]:
        for h in t.hechos:
            if h["tipo"] == "politica" and h.get("base"):
                h["texto"] = h["base"]
    # LOS ENVIOS que no entraron en una cuenta, en una sola cotizacion.
    cotizados = {K.n(b["destino"]) for h in t.hechos if h["tipo"] == "cuenta" for b in h["bloques"]}
    destinos = list(dict.fromkeys(d for d in t.destinos if d and K.n(d) not in cotizados))
    envios = [p for p in preguntas if p["accion"] == "envio"]
    if destinos:
        r = t.herramienta("envio", destinos=destinos)
        t.hechos.append({"tipo": "envio", "n": envios[0]["n"], **r})
    con_hechos = {h.get("n") for h in t.hechos}
    repreguntadas = set(t.de.values())
    # Las compras terminan como termino el borrador: lo que falta se pregunto desde la primera.
    for p in preguntas:
        if p.get("accion") == "comprar" and p["n"] not in t.estados and t.compra:
            t.estados[p["n"]] = "repreguntada" if t.compra in repreguntadas else "respondida"
    for p in preguntas:
        n = p["n"]
        if n in t.estados:
            continue
        if n in repreguntadas:
            t.estados[n] = "repreguntada"
        elif n in con_hechos or (p.get("accion") == "envio" and any(h["tipo"] in ("envio", "cuenta") for h in t.hechos)):
            t.estados[n] = "respondida"
        else:
            # EL CANDADO: ninguna pregunta se pierde en silencio.
            log.warning("flujo_pregunta_sin_estado", accion=p.get("accion"), cita=str(p.get("cita") or "")[:120])
            t.n = n
            q = (f"No llegué a resolver \"{p['cita']}\". ¿Me lo decís de otra forma?" if p.get("cita")
                 else "No llegué a resolver una parte de tu mensaje. ¿Me la decís de otra forma?")
            t.preguntar(q)
            t.sueltas.append({"cita": str(p.get("cita") or ""), "pregunta": q})
            t.estados[n] = "sin_estado"
    t.hechos.sort(key=lambda h: h.get("n", 0))
    citas = {p["n"]: str(p.get("cita") or "") for p in preguntas}
    estado["abiertas"] = [{"texto": q, "cita": citas.get(t.de.get(q), ""),
                           **({"espera": t.esperas[q]} if q in t.esperas else {})} for q in t.preguntas]
    return t


# Lo que puede ser una respuesta corta: lo que cambia el pedido o la plata no contesta una pregunta del bot.
_CORTAS = ("buscar", "producto", "otro", "compatibilidad", "explicar")


def _palabras_de(p: dict) -> str:
    return " ".join(str(v) for k in ("cita", "rubro", "producto", "con", "quiere_saber", "condiciones", "que")
                    for v in _lista(p.get(k)) if not A._REF.match(str(v)))


def atar_esperas(agenda: dict, t: Turno) -> None:
    """LA RESPUESTA CORTA SE ATA A LO QUE ESPERA LA PREGUNTA DEL BOT, y se controla contra la fuente antes de seguir.
    El equipo, `_atar_equipo`. Lo demas —el color, si o no, cual de varios, el nombre— solo si el modelo dice que el
    mensaje contesta esa pregunta y no tradujo ningun cambio: la respuesta se lee contra la lista cerrada de la espera,
    `marcador.respuesta`, y pasa a lo que la pregunta dejo dicho que hace. Lo que no se lee de una sola forma queda
    como lo tradujo el modelo."""
    abiertas = [(r, a) for r, a in t.nums.items() if r[:1] == "R" and (a.get("espera") or {}).get("tipo")]
    ps = A.preguntas(agenda)
    cortas = [p for p in ps if p.get("accion") in _CORTAS]
    if not abiertas or not cortas or not isinstance(agenda, dict):
        return
    responde = str(agenda.get("responde") or next((p.get("responde") for p in ps if p.get("responde")), "") or "")
    if (dict(abiertas).get(responde) or {}).get("espera", {}).get("tipo") not in (None, "equipo"):
        return _atar_respuesta(agenda, t, responde, dict(abiertas)[responde], ps, cortas)
    equipos = [(r, a) for r, a in abiertas if a["espera"]["tipo"] == "equipo"]
    if equipos:
        _atar_equipo(agenda, t, responde, equipos, ps, cortas)


def _llenar(x, eleccion: str):
    """La pregunta que deja la espera, con lo elegido en su lugar."""
    if isinstance(x, dict):
        return {k: _llenar(v, eleccion) for k, v in x.items()}
    if isinstance(x, list):
        return [_llenar(v, eleccion) for v in x]
    return eleccion if x == "{eleccion}" else x


def _atar_respuesta(agenda: dict, t: Turno, r: str, a: dict, ps: list, cortas: list) -> None:
    from .marcador import respuesta
    e = a["espera"]
    # Lo que cambia el pedido o la plata lo entendio el modelo: no se le suma otra lectura. La cuenta sin tope ni pago
    # es la de "ve como queda", que pone el paso de la ficha cuando el mensaje no cambia nada.
    if not agenda.get("respuesta") or any(p.get("accion") not in _CORTAS and not (
            p.get("accion") == "cuenta" and not p.get("tope") and not p.get("reparto")) for p in ps):
        return
    dicho = respuesta(str(agenda["respuesta"]), e, t.tienda)
    if dicho is None:
        return
    primera = cortas[0]
    if e["tipo"] == "nombre":
        cliente = agenda["cliente"] if isinstance(agenda.get("cliente"), dict) else {}
        agenda["cliente"] = {**cliente, "nombre": cliente.get("nombre") or dicho}
        nuevas = [{"accion": "otro", "que": "dato"}]
    elif dicho == "no":
        nuevas = [{"accion": "otro", "que": "dato"}]
    else:
        nuevas = [_llenar(h, dicho) for h in e.get("hace") or [] if isinstance(h, dict)]
        nuevas = [{**h, "responde": r} if h.get("accion") == "comprar" else h for h in nuevas]
    if not nuevas:
        return
    tope = max([K.entero(p.get("n")) for p in ps] + [0])
    nuevas = [{**h, "n": primera.get("n") if i == 0 else tope + i, "cita": primera.get("cita")}
              for i, h in enumerate(nuevas)]
    fuera = {id(p) for p in cortas}
    agenda["preguntas"] = [x for p in agenda["preguntas"]
                           for x in (nuevas if p is primera else [] if id(p) in fuera else [p])]


def _atar_equipo(agenda: dict, t: Turno, responde: str, abiertas: list, ps: list, cortas: list) -> None:
    """"¿Tu tablet es Android o iPad?" -> "la ultima de Samsung" es un equipo Android: se juzga la compatibilidad que
    se estaba preguntando, no se buscan tablets Samsung. Si el modelo dice que el mensaje contesta esa pregunta, la
    respuesta es el mensaje, leido solo contra el vocabulario cerrado de la espera; si no lo dice, cada consulta corta
    por sus palabras. Lo que nombra un equipo que no es ninguno de los esperados se dice y se vuelve a preguntar, si
    contesta esa pregunta; si no, es otro tema y la agenda queda."""
    from app.core.compatibilidad import _norm, etiqueta_plataforma, plataformas_del_mensaje
    from app.core.guia_venta_prosa import mensaje
    r, a = next(((r, a) for r, a in abiertas if r == responde), abiertas[-1])
    e = a["espera"]
    if not e.get("producto") or not e.get("con"):
        return
    if r == responde and agenda.get("respuesta"):
        tramos = [(cortas, str(agenda["respuesta"]))]
    elif len(cortas) == len(ps):
        tramos = [([p], _palabras_de(p)) for p in cortas]
    else:
        return
    sobran = []
    for grupo, texto in tramos:
        # El equipo de la pregunta no contesta: "la tablet Samsung" dice Samsung, "tablet" ya estaba.
        dicho = plataformas_del_mensaje(re.sub(r"\b" + re.escape(_norm(e["con"])) + r"s?\b", " ", _norm(texto)),
                                        t.tienda)
        cumple = [x for x in dicho if not e["opciones"] or x in e["opciones"]]
        p = grupo[0]
        n, cita = p.get("n"), p.get("cita")
        if len(cumple) == 1:
            p.clear()
            p.update({"n": n, "cita": cita, "accion": "compatibilidad", "producto": e["producto"], "con": cumple[0]})
        elif dicho and not cumple and r == responde:
            p.clear()
            p.update({"n": n, "cita": cita, "accion": "otro", "que": "dato"})
            t.n = n
            dijo = etiqueta_plataforma(dicho[0], t.tienda)
            t.hechos.append({"tipo": "no_es", "n": n, "texto": mensaje(
                "compat_no_es_el_equipo", "{dicho} no es tu {equipo}.", dicho=dijo[:1].upper() + dijo[1:],
                equipo=e["con"])})
            t.preguntar(a["texto"], espera=e)
        else:
            continue
        sobran += [id(x) for x in grupo[1:]]
    agenda["preguntas"] = [x for x in agenda["preguntas"] if id(x) not in sobran]


def _derivar(t: Turno) -> None:
    """Una vez por turno, despues de lo que cambia lo dicho y antes de la cuenta. Sin renglones no hay nada que
    derivar: la cuenta de lo consultado sigue por su lado."""
    t.derivado = True
    # LO PROPUESTO VALE UN TURNO: si el cliente no lo acepto, se descarta y el pedido queda como lo tenia.
    if t.estado["borrador"]["propuesta"] and t.estado["borrador"]["propuesta"] is t.propuesta:
        t.estado["borrador"]["propuesta"] = {}
        t.hechos.append({"tipo": "supuesto", "texto": "Dejé el pedido como estaba.", "n": t.n})
    # Todo lo dicho entra antes de resolver: el pago de la cuenta tambien, asi su medio se pregunta desde el borrador.
    for p in t.agenda:
        if p.get("accion") == "cuenta" and p.get("reparto") and t.estado["borrador"]["renglones"]:
            B.aplicar(t.estado["borrador"], {"reparto": [r for r in _lista(p["reparto"]) if isinstance(r, dict)]})
    # CON UN TOPE DE PLATA, LO QUE ELIGE EL CODIGO ES LO MAS BARATO: el rubro sin orden dicho no toma la primera opcion,
    # que era el teclado de 512 mil con un tope de 600. El criterio queda en el borrador para los turnos siguientes.
    b = t.estado["borrador"]
    if any(p.get("accion") == "cuenta" and K.entero(p.get("tope")) for p in t.agenda):
        rubros = set(b["criterios"]) | set(b["lista"]) | {K.solo_rubro(r["que"], t.tienda) for r in b["renglones"]}
        for rub in rubros - {""}:
            c = b["criterios"].get(rub) or {"condiciones": [], "orden": "nada"}
            if K.n(c.get("orden") or "nada") == "nada":
                b["criterios"][rub] = {**c, "orden": "mas barato"}
    # Un pedido sin renglones que lo digan no existe: se re-deriva a vacio, tambien el guardado antes del borrador.
    if t.estado["borrador"]["renglones"] or t.compra or t.estado["pedido"]:
        n = t.n
        t.derivar()
        t.n = n
