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

    def herramienta(self, nombre: str, **args) -> dict:
        r = agente.ejecutar(nombre, args, self.tienda)
        self.llamadas.append({"herramienta": nombre, "args": args, "vuelve": r})
        return r

    def preguntar(self, texto: str) -> None:
        if texto not in self.preguntas:
            self.preguntas.append(texto)
            self.de[texto] = self.n

    # ── productos ────────────────────────────────────────────────────────────

    def producto(self, nombre: str, quiere_saber: str = "", color: str = ""):
        """El producto y lo que pregunto de el. Devuelve si dio que si —hay, en ese color, y cumple lo que pregunto—,
        para lo que depende de esto: "si no hay en negro". None si no se sabe."""
        idt = K.identificar(nombre, color, self.tienda)
        if idt["veredicto"] == "not_found":
            self.hechos.append({"tipo": "no_existe", "nombre": nombre})
            return False
        if idt["veredicto"] == "ambiguous":
            self.preguntar("¿Cuál de estos decís: " + " o ".join(p["nombre"] for p in idt["opciones"]) + "?")
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
        """El dato que pregunto, del producto: por el nombre del campo, o por el campo del rubro donde vive esa
        palabra —"inalambrico" vive en conexion—. Primero la frase entera, despues palabra por palabra, sin las del
        nombre del producto. Si no esta en ningun campo, lo dice."""
        q = K.n(quiere_saber)
        if q in ("", "todo", "precio", "stock", "disponibilidad", "precio y stock", "existencia") \
                or "tope" in K.atar(quiere_saber, [], self.tienda):
            return {}  # un tope de plata se contesta con el precio, que ya va
        datos = {**(p.get("specs") or {}), "garantia": (p.get("specs") or {}).get("garantia")
                 or (f"{p['garantia_meses']} meses" if p.get("garantia_meses") else None)}
        propias = set(K.n(p.get("nombre")).split())
        universo = [x for x in K.productos(self.tienda) if x.get("categoria") == p.get("categoria")]
        for parte in [q] + [w for w in q.split() if len(w) > 2 and w not in propias and w not in K._RELLENO]:
            palabras = set(parte.split())
            clave = next((k for k in datos if datos[k] and set(K.n(k).replace("_", " ").split()) & palabras), None)
            if clave:
                return {"campo": clave, "valor": datos[clave]}
            f = K.atar(parte, universo, self.tienda)
            if "campo" in f and f["campo"] not in ("nombre", "modelo", "descripcion", "tags", "marca"):
                return {"campo": f["campo"], "valor": K._valores(p, f["campo"]) or "no figura"}
        return {"campo": quiere_saber, "valor": None, "descripcion": p.get("descripcion") or ""}

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
        orden = str(b.get("orden") or "nada")
        cuantos = K.entero(b.get("cantidad"), 1) if K.n(orden) not in ("nada", "") else 5
        entre = [m["id"] for m in self.estado["mostrados"]] if _si(b.get("entre_lo_mostrado")) else None
        conds = [str(c) for c in _lista(b.get("condiciones"))]
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
            if (r.get("cuenta") or {}).get("total_ars") is not None:
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
        self.hechos.append({"tipo": "cuenta", "bloques": bloques, "general": general})

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
        perdidos = _perdidos(antes, arts, self.tienda) if self.previos is not None and antes else []
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
        for q in B.preguntas(b, falta):
            self.preguntar(q)
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
        if v:
            out.append(v)
    return out


def _uno(t: Turno, x) -> str:
    """El unico producto que nombra, o "" despues de preguntar cual si puede ser varios."""
    nombres = _nombres(t, x)
    if len({_modelo(n, t.tienda) for n in nombres}) > 1:
        t.preguntar("¿Cuál decís: " + " o ".join(nombres) + "?" if len(nombres) <= 4
                    else "¿Cuál de los que te mostré decís?")
        return ""
    return nombres[0] if nombres else ""


def _producto(t: Turno, p: dict):
    nombre = _uno(t, p.get("producto"))
    if nombre:
        return t.producto(nombre, str(p.get("afirma") or p.get("quiere_saber") or ""), str(p.get("color") or ""))


def _buscar(t: Turno, p: dict):
    return t.busqueda(p)


def _compatibilidad(t: Turno, p: dict):
    if _si(p.get("falta_modelo")):
        t.preguntar(f"¿Qué modelo es tu {p.get('con')}? Con eso te confirmo qué le sirve.")
        return None
    nombre = _uno(t, p.get("producto"))
    idt = K.identificar(nombre, "", t.tienda) if nombre else {"veredicto": ""}
    if idt["veredicto"] != "exists":
        if nombre:
            t.preguntar(f"¿Qué {nombre} decís, el modelo exacto?")
        return None
    r = t.herramienta("compatibilidad", producto=str(idt["producto"]["id"]), con=str(p.get("con") or ""))
    vs = [v for v in _lista(r.get("compatibilidad")) if isinstance(v, dict)]
    t.hechos += [{"tipo": "compat", **v} for v in vs]
    veredictos = {v.get("veredicto") for v in vs}
    return True if "compatible" in veredictos else (False if "incompatible" in veredictos else None)


def _politica(t: Turno, p: dict):
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
# Lo que dice un "si" y nada mas: si es lo unico que contesta a "¿Lo dejo así?", acepta lo supuesto sin modelo.
AFIRMA = set("si sii dale ok oka okey listo perfecto bueno va joya correcto exacto asi esta bien dejalo deja genial "
             "barbaro de una seguro claro buenisimo".split())


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
    palabras = [w for p in t.agenda for w in A.palabras(p.get("cita"))]
    return bool(palabras) and all(w in AFIRMA or w in A._VACIAS for w in palabras) and not _cambia(t)


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
        t.preguntar("¿Cuál querés: " + " o ".join(si) + "?")
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
        nombre = _uno(t, a.get("producto"))
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
    for h in dudosos:
        t.preguntar(f"¿El {h['producto'].get('modelo')} en qué color? Cambia el precio.")
    destino = next(iter(t.destinos), "")
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
    estado["abiertas"] = [{"texto": q, "cita": citas.get(t.de.get(q), "")} for q in t.preguntas]
    return t


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
