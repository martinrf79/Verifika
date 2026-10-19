"""EL EJECUTOR — la agenda del interprete y el estado entran, los hechos y el estado nuevo salen (20-oct-2026).

La agenda es la de `agenda.py`: una pregunta por cada cosa que pidio el cliente, con una accion del menu. Cada
pregunta se cumple con UNA funcion de `Turno`, y termina en uno de estos estados:

  respondida    tiene sus hechos: lo que la fuente o la calculadora dijeron.
  repreguntada  falta un dato del cliente y se le pregunta; queda en `estado.abiertas` para el turno siguiente.
  no_aplica     dependia de otra pregunta —"si no hay"— y la condicion no se cumplio.
  nada          no pedia nada: un saludo, un dato de si mismo, lo que corrigio.

EL CANDADO: una pregunta que termina sin estado no se pierde en silencio, se le repregunta al cliente con su cita.
No se vuelve a leer el mensaje del cliente: lo que el interprete no puso en la agenda no existe para el codigo. Lo que
el modelo senala con un numero de la libreta —M-2, P-1— se resuelve con `interprete.numeros`, lo mismo que vio el modelo.
Los montos salen de la calculadora, por `agente.h_cuenta` y `agente.h_envio`.

Un hecho es un dict con "tipo" y "n", la pregunta que lo pidio. `redaccion.texto` los pasa a palabras en ese orden.
"""
from app.core import agente, fuente
from app.logger import get_logger

from . import agenda as A
from . import catalogo as K
from .estado import mostrar

log = get_logger(__name__)


def _lista(x) -> list:
    return x if isinstance(x, list) else ([x] if x not in (None, "", {}) else [])


def _si(v) -> bool:
    return v is True or (isinstance(v, str) and K.n(v) in ("true", "si"))


def _destino(d) -> str:
    d = str(d or "").strip()
    return "" if K.n(d) in ("", "null", "none", "nada", "sin destino", "sin definir", "a definir") else d


def _modelo(nombre: str, tienda_id: str) -> str:
    """El modelo que nombra un candidato, para contar si una referencia apunta a uno o a varios: dos colores del
    mismo modelo son uno solo. Lo que no es un producto cuenta por su texto."""
    p = K.identificar(nombre, "", tienda_id).get("producto") or {}
    return p.get("modelo") or K.n(nombre)


class Turno:
    def __init__(self, estado: dict, tienda_id: str):
        self.estado, self.tienda = estado, tienda_id
        self.hechos, self.preguntas, self.llamadas = [], [], []
        self.listas, self.pedidas = {}, {}  # lo buscado en este turno: filas y unidades pedidas, por rubro
        self.n, self.de = 0, {}  # la pregunta que se esta cumpliendo, y de que pregunta es cada repregunta
        self.resultados, self.estados = {}, {}  # por pregunta: si dio que si, para "si no hay"; y como termino
        self.nums, self.agenda, self.destinos, self.cambio, self.explicar = {}, [], [], False, None
        self.sin_anotar = ""  # la compra que no se pudo anotar, en palabras, para el turno siguiente

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
        if q in ("", "todo", "precio", "stock", "disponibilidad", "precio y stock", "existencia"):
            return {}
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
        self.hechos.append({"tipo": "lista", "rubro": rub or "la tienda", **r})
        if rub:
            self.listas[rub] = {"filas": r["filas"], "orden": orden}
            self.pedidas[rub] = self.pedidas.get(rub, 0) + max(1, K.entero(b.get("cantidad"), 1))
        mostrar(self.estado, r["filas"])
        self.estado["busqueda"] = {"rubro": rub, "condiciones": conds, "orden": orden}
        return bool(r["filas"]) and not r["vacio_por"]

    # ── la plata ─────────────────────────────────────────────────────────────

    def cuenta(self, articulos: list, reparto: list, tope=None, si_pasa: str = "") -> None:
        """Una cuenta por destino. Con mas de un destino, el total general es la suma de los totales y el reparto
        del pago se calcula una sola vez, sobre ese total."""
        grupos = {}
        for a in articulos:
            grupos.setdefault(a.get("destino") or "", []).append({"id": a["id"], "cantidad": a["cantidad"]})
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
                    self.estado["pedido"] = quedan
                return self.cuenta(quedan, reparto)
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

    def pedido(self, ped: dict) -> list:
        """Los articulos resueltos, o [] si falta algo: entonces se pregunta y el pedido no cambia.

        Un articulo nombra un modelo, un rubro o "los otros". El modelo se identifica. El rubro —"un auricular a
        Cordoba"— sale de la busqueda de ese rubro, su primera fila, que es la mas barata si la pidio asi. "Los otros"
        —"los otros dos a Posadas"— son lo que queda de lo pedido por rubro, contado por el codigo. Un rubro que no
        estaba en la lista del cliente, o un resto que no cierra, se pregunta: no se adivina."""
        pedidas = {**self.estado["por_rubro"], **self.pedidas} if self.pedidas else dict(self.estado["por_rubro"])
        resueltos, de_rubro, otros, falta = [], [], [], False
        for a in _lista(ped.get("articulos")):
            if not isinstance(a, dict) or not a.get("producto"):
                continue
            nombre = str(a["producto"])
            if a.get("cantidad") not in (None, "") and K.entero(a["cantidad"]) < 1:
                # Una cantidad que no es un numero no se adivina.
                self.preguntar(f"¿Cuántos {nombre} querés?")
                falta = True
                continue
            idt = K.identificar(nombre, str(a.get("color") or ""), self.tienda)
            rub = "" if idt["veredicto"] == "exists" and not idt.get("falta_color") else K.solo_rubro(nombre, self.tienda)
            if rub:
                de_rubro.append((rub, a))
            elif idt["veredicto"] == "not_found":
                otros.append(a)
            elif idt["veredicto"] == "ambiguous":
                self.preguntar("¿Cuál de estos querés: " + " o ".join(p["nombre"] for p in idt["opciones"][:4]) + "?")
                falta = True
            elif idt.get("falta_color"):
                colores = [v["color"] for v in idt["variantes"] if K.con_stock(v) and v.get("color")]
                modelo = idt["producto"].get("modelo") or nombre
                antes = f"El {modelo} no viene en {idt['no_hay_color']}. " if idt.get("no_hay_color") else ""
                # Es un paso de la compra, y lo dice: "para reservarte" y no una pregunta suelta.
                self.preguntar(f"{antes}Para reservarte el {modelo}, ¿en qué color: " + " o ".join(colores) + "?")
                falta = True
            elif not K.con_stock(idt["producto"]):
                self.hechos.append({"tipo": "producto", "producto": idt["producto"], "variantes": idt["variantes"],
                                    "dato": {}, "pide": ""})
                self.preguntar(f"El {idt['producto']['nombre']} no tiene stock: ¿te sirve otro color u otro modelo?")
                falta = True
            else:
                resueltos.append(self._articulo(idt["producto"], a))
        # UN RUBRO FUERA DE LA LISTA DEL CLIENTE se pregunta: "dos auriculares, dos mouse y dos memorias" y despues
        # "un teclado a Concordia" (K20). Sin lista, cualquier rubro vale.
        fuera = [(r, a) for r, a in de_rubro if pedidas and r not in pedidas]
        for r, a in fuera:
            destino = _destino(a.get("destino"))
            self.preguntar(f"Pediste {r}" + (f" para {destino}" if destino else "") + ", pero en la lista había "
                           + ", ".join(pedidas) + ": ¿lo sumo o era otra cosa de la lista?")
            falta = True
        # LOS OTROS: lo pedido por rubro menos lo ya asignado, en el orden de la lista.
        if otros:
            usadas = {}
            for r, a in de_rubro:
                usadas[r] = usadas.get(r, 0) + K.entero(a.get("cantidad"), 1)
            for x in resueltos:
                c = K.por_id(x["id"], self.tienda).get("categoria")
                usadas[c] = usadas.get(c, 0) + x["cantidad"]
            quedan = [(r, n - usadas.get(r, 0)) for r, n in pedidas.items() if n - usadas.get(r, 0) > 0]
            if len(otros) == 1 and otros[0].get("cantidad") in (None, ""):
                # "Lo demas a Posadas", sin numero: es todo lo que queda de la lista.
                otros = [{**otros[0], "cantidad": sum(n for _, n in quedan)}]
            unidades = sum(K.entero(a.get("cantidad"), 1) for a in otros)
            if fuera or not quedan or unidades != sum(n for _, n in quedan):
                cuales = " y ".join(str(a["producto"]) for a in otros)
                self.preguntar(f"¿Cuáles son {cuales}?" + (" De la lista quedan " + ", ".join(
                    f"{n} {r}" for r, n in quedan) + "." if quedan else ""))
                falta = True
            else:
                pendientes = [r for r, n in quedan for _ in range(n)]
                for a in otros:
                    for _ in range(K.entero(a.get("cantidad"), 1)):
                        de_rubro.append((pendientes.pop(0), {**a, "cantidad": 1}))
        # EL RUBRO SE CUMPLE CON SU BUSQUEDA: la de este turno, o una nueva sin condiciones.
        elegidos = {}
        for r, a in de_rubro:
            if (r, a) in fuera:
                continue
            lista = self.listas.get(r) or {"filas": K.buscar(r, [], "nada", 1, self.tienda)["filas"], "orden": "nada"}
            if not lista["filas"]:
                self.preguntar(f"No tengo {r} con stock: ¿te sirve otra cosa?")
                falta = True
                continue
            p = lista["filas"][0]
            elegidos[r] = {"nombre": p["nombre"], "orden": lista["orden"]}
            resueltos.append(self._articulo(p, a))
        if de_rubro or otros:
            self.estado["por_rubro"] = pedidas
        if falta:
            # Lo que ya quedo claro se muestra una vez; lo elegido de un rubro no, que su lista ya esta en el mensaje.
            de_lista = {str(p["id"]) for x in self.listas.values() for p in x["filas"]}
            for pid in dict.fromkeys(a["id"] for a in resueltos if a["id"] not in de_lista):
                self.hechos.append({"tipo": "producto", "producto": K.por_id(pid, self.tienda), "variantes": [],
                                    "dato": {}, "pide": ""})
            mostrar(self.estado, [{"id": a["id"], "nombre": a["nombre"], "precio_ars": a["precio"]} for a in resueltos])
            return []
        if elegidos:
            self.hechos.append({"tipo": "elegidos", "rubros": elegidos})
        return _juntar(resueltos)

    @staticmethod
    def _articulo(p: dict, a: dict) -> dict:
        return {"id": str(p["id"]), "nombre": p["nombre"], "precio": p.get("precio_ars"),
                "cantidad": K.entero(a.get("cantidad"), 1), "destino": _destino(a.get("destino"))}


def _juntar(articulos: list) -> list:
    """El mismo producto al mismo destino es un renglon con la suma de las cantidades."""
    out = {}
    for a in articulos:
        k = (a["id"], a["destino"])
        out[k] = {**a, "cantidad": out[k]["cantidad"] + a["cantidad"]} if k in out else a
    return list(out.values())


# ══ LAS ACCIONES: una funcion por accion del menu ═════════════════════════════

def _nombres(t: Turno, x) -> list:
    """Lo que nombra el modelo, en nombres que entiende `identificar`: un numero de la libreta es lo que senala."""
    out = []
    for v in _lista(x):
        v = str(v).strip()
        ref = t.nums.get(v)
        if v[:1] == "M" and ref:
            v = K.por_id(ref, t.tienda).get("nombre") or v
        elif v[:1] == "P" and isinstance(ref, dict):
            v = ref["nombre"]
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
    pols = fuente.politicas_de([str(p["tema"])], t.tienda).get("politicas") or []
    # Solo las politicas: el criterio de la FAQ es una instruccion para el que redacta, no texto para el cliente.
    t.hechos += [{"tipo": "politica", "tema": x.get("tema"), "texto": x.get("texto")} for x in pols]
    if not pols:
        t.hechos.append({"tipo": "sin_politica"})


def _reparto(t: Turno, p: dict) -> bool:
    reparto = [r for r in _lista(p.get("reparto")) if isinstance(r, dict) and r.get("porcentaje")]
    if any(K.n(r.get("medio")) in ("", "sin decir", "none", "null") for r in reparto):
        # Un reparto sin medio no se cuenta: "sin decir (70%)" no es un cobro. Se pregunta con que paga cada parte.
        t.preguntar("¿Con qué medio pagás cada parte: " + " y ".join(f"el {K.entero(r['porcentaje'])}%"
                                                                    for r in reparto) + "?")
        return False
    if reparto:
        t.estado["reparto"] = reparto
    return bool(reparto)


def _comprar(t: Turno, p: dict):
    """El cambio de este mensaje sobre el pedido: lo que agrega, lo que saca y lo que cambia de un renglon."""
    cambio = _reparto(t, p)
    pedido = [] if _si(p.get("reemplaza")) else list(t.estado["pedido"])
    saca = [t.nums[x] for x in _lista(p.get("saca")) if isinstance(t.nums.get(x), dict)]
    pedido = [a for a in pedido if a not in saca]
    for c in _lista(p.get("cambia")):
        viejo = t.nums.get(str((c or {}).get("es"))) if isinstance(c, dict) else None
        if viejo not in pedido:
            continue
        nuevo = {**viejo, **{k: c[k] for k in ("destino",) if c.get(k)}}
        if c.get("cantidad") not in (None, ""):
            nuevo["cantidad"] = K.entero(c["cantidad"], viejo["cantidad"])
        if c.get("color"):
            idt = K.identificar(viejo["nombre"], str(c["color"]), t.tienda)
            if idt["veredicto"] == "exists" and not idt.get("no_hay_color"):
                nuevo = {**nuevo, **Turno._articulo(idt["producto"], nuevo)}
        pedido[pedido.index(viejo)] = nuevo
    articulos = []
    for a in _lista(p.get("agrega")):
        if not isinstance(a, dict):
            continue
        nombre = _uno(t, a.get("producto"))
        if not nombre:
            return None
        articulos.append({**a, "producto": nombre})
    agregados = t.pedido({"articulos": articulos}) if articulos else []
    if articulos and not agregados:
        # LO QUE NO SE PUDO ANOTAR NO SE OLVIDA: queda en lo abierto, y el turno siguiente lo ve entero.
        t.sin_anotar = "; ".join(f"{a.get('cantidad') or 'todo lo que queda de la lista,'} {a['producto']}"
                                 + (f" a {_destino(a.get('destino'))}" if _destino(a.get("destino")) else "")
                                 for a in articulos)
        return None
    nuevo = _juntar(pedido + agregados)
    if nuevo != t.estado["pedido"] or saca:
        t.estado["pedido"] = nuevo
        t.hechos.append({"tipo": "pedido", "articulos": nuevo} if nuevo else {"tipo": "pedido_vacio"})
        cambio = True
    t.cambio = t.cambio or cambio
    return True


def _cuenta(t: Turno, p: dict):
    _reparto(t, p)
    si_pasa = _uno(t, p.get("si_pasa")) if p.get("si_pasa") else ""
    if t.estado["pedido"]:
        t.cuenta(t.estado["pedido"], t.estado["reparto"], p.get("tope"), si_pasa)
        return True
    compras = {x["n"] for x in t.agenda if x.get("accion") == "comprar"}
    if compras & set(t.de.values()):
        # La cuenta de un pedido que todavia no se pudo armar espera la respuesta de esa repregunta.
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
        t.cuenta(items, t.estado["reparto"])
    elif not items:
        t.preguntar("¿De qué productos querés la cuenta?")


def _envio(t: Turno, p: dict):
    """Los envios se cotizan juntos al final, los que no entraron en una cuenta."""
    t.destinos.append(_destino(p.get("destino")))


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
            # Lo que depende de algo que no se pudo saber no se anota solo: el cliente lo confirma viendo el resultado.
            t.preguntar("¿Te lo confirmo así?")
            return
        if r is not None and r != (K.n(si.get("da")) != "no"):
            t.estados[t.n] = "no_aplica"
            return
    t.resultados[t.n] = ACCIONES[p["accion"]](t, p)
    for h in t.hechos[antes:]:
        h.setdefault("n", t.n)


def ejecutar(agenda: dict, estado: dict, tienda_id: str, explicar=None) -> Turno:
    """La agenda entera, pregunta por pregunta."""
    from .interprete import numeros
    t = Turno(estado, tienda_id)
    # Los numeros de la libreta se toman antes de cumplir nada: son los que vio el modelo.
    t.nums, t.explicar = numeros(estado), explicar
    agenda = agenda if isinstance(agenda, dict) else {"preguntas": agenda}
    cliente = agenda.get("cliente") if isinstance(agenda.get("cliente"), dict) else {}
    estado["cliente"].update({k: v for k, v in cliente.items() if v and k in ("localidad", "nombre", "es")})
    preguntas = t.agenda = A.preguntas(agenda)
    for i, p in enumerate(preguntas, 1):
        p.setdefault("n", i)
    # LAS COMPRAS DE UN MENSAJE SON UN SOLO PEDIDO: "un auricular a Cordoba, un mouse a Concordia, los otros dos a
    # Posadas" en tres preguntas se anota junto, o se pregunta y no se anota nada. Asi "los otros" cuenta lo de las
    # tres. Las que dependen de otra pregunta van aparte.
    compras = [p for p in preguntas if p.get("accion") == "comprar" and not p.get("si")]
    juntas = {}
    if len(compras) > 1:
        primera = compras[0]
        for p in compras[1:]:
            for k in ("agrega", "saca", "cambia"):
                primera[k] = _lista(primera.get(k)) + _lista(p.get(k))
            primera["reparto"] = p.get("reparto") or primera.get("reparto")
            primera["reemplaza"] = _si(primera.get("reemplaza")) or _si(p.get("reemplaza"))
            juntas[p["n"]] = primera["n"]
    # Una accion fuera del menu no se cumple: la agarra el candado de abajo.
    for p in sorted(preguntas, key=lambda p: DESPUES.get(p.get("accion"), 0)):
        if p.get("accion") in ACCIONES and p["n"] not in juntas:
            _cumplir(t, p)
    # UN PEDIDO QUE CAMBIO SE CUENTA aunque no lo haya pedido: el cliente ve como queda.
    if t.cambio and t.estado["pedido"] and not any(h["tipo"] == "cuenta" for h in t.hechos):
        t.n = max(p["n"] for p in preguntas if p["accion"] == "comprar") if any(
            p["accion"] == "comprar" for p in preguntas) else t.n
        antes = len(t.hechos)
        t.cuenta(t.estado["pedido"], t.estado["reparto"])
        for h in t.hechos[antes:]:
            h.setdefault("n", t.n)
    # LOS ENVIOS que no entraron en una cuenta, en una sola cotizacion.
    cotizados = {K.n(b["destino"]) for h in t.hechos if h["tipo"] == "cuenta" for b in h["bloques"]}
    destinos = list(dict.fromkeys(d for d in t.destinos if d and K.n(d) not in cotizados))
    envios = [p for p in preguntas if p["accion"] == "envio"]
    if destinos:
        r = t.herramienta("envio", destinos=destinos)
        t.hechos.append({"tipo": "envio", "n": envios[0]["n"], **r})
    con_hechos = {h.get("n") for h in t.hechos}
    repreguntadas = set(t.de.values())
    for n, primera in juntas.items():
        t.estados[n] = t.estados.get(primera) or ("repreguntada" if primera in repreguntadas else "respondida")
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
            t.preguntar(f"No llegué a resolver \"{p['cita']}\". ¿Me lo decís de otra forma?" if p.get("cita")
                        else "No llegué a resolver una parte de tu mensaje. ¿Me la decís de otra forma?")
            t.estados[n] = "sin_estado"
    t.hechos.sort(key=lambda h: h.get("n", 0))
    citas = {p["n"]: str(p.get("cita") or "") for p in preguntas}
    compra = next((p["n"] for p in preguntas if p.get("accion") == "comprar"), None)
    estado["abiertas"] = [{"texto": q, "cita": citas.get(t.de.get(q), "")} for q in t.preguntas]
    # Lo que no se anoto va una vez, en la primera repregunta de la compra.
    for a in estado["abiertas"]:
        if t.sin_anotar and t.de.get(a["texto"]) == compra:
            a["sin_anotar"] = t.sin_anotar
            break
    return t
