"""EL EJECUTOR — la traduccion del interprete y el estado entran, los hechos y el estado nuevo salen (19-oct-2026).

La traduccion es la ficha 10 llena: las casillas de `banco_pruebas/nexos/ficha10.py`, con una sola casilla de mas,
`entre_lo_mostrado` en una busqueda, porque la ficha 10 define "de esos" como una busqueda entre lo mostrado y no
tenia donde decirlo.

Cada casilla tiene UN lugar en `ejecutar` y no se vuelve a leer el mensaje del cliente: lo que el interprete no
tradujo, no existe para el codigo. Los montos salen de la calculadora, por `agente.h_cuenta` y `agente.h_envio`.

Un hecho es un dict con "tipo". `redaccion.texto` los pasa a palabras.
"""
from app.core import agente, fuente

from . import catalogo as K
from .estado import mostrar


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

    def herramienta(self, nombre: str, **args) -> dict:
        r = agente.ejecutar(nombre, args, self.tienda)
        self.llamadas.append({"herramienta": nombre, "args": args, "vuelve": r})
        return r

    def preguntar(self, texto: str) -> None:
        if texto not in self.preguntas:
            self.preguntas.append(texto)

    # ── productos ────────────────────────────────────────────────────────────

    def producto(self, nombre: str, quiere_saber: str = "", color: str = "") -> None:
        idt = K.identificar(nombre, color, self.tienda)
        if idt["veredicto"] == "not_found":
            self.hechos.append({"tipo": "no_existe", "nombre": nombre})
        elif idt["veredicto"] == "ambiguous":
            self.preguntar("¿Cuál de estos decís: " + " o ".join(p["nombre"] for p in idt["opciones"]) + "?")
        else:
            p = idt["producto"]
            self.hechos.append({"tipo": "producto", "producto": p, "variantes": idt["variantes"],
                                "dato": self.dato(p, quiere_saber), "pide": quiere_saber,
                                "falta_color": bool(idt.get("falta_color"))})
            mostrar(self.estado, [p])

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
            clave = next((k for k in datos if datos[k] and (K.n(k) in parte or parte in K.n(k))), None)
            if clave:
                return {"campo": clave, "valor": datos[clave]}
            f = K.atar(parte, universo, self.tienda)
            if "campo" in f and f["campo"] not in ("nombre", "modelo", "descripcion", "tags", "marca"):
                return {"campo": f["campo"], "valor": K._valores(p, f["campo"]) or "no figura"}
        return {"campo": quiere_saber, "valor": None, "descripcion": p.get("descripcion") or ""}

    # ── busquedas ────────────────────────────────────────────────────────────

    def busqueda(self, b: dict) -> None:
        nombre = str(b.get("rubro") or "")
        toda = K.n(nombre) in ("toda la tienda", "todo", "")
        rub = "" if toda else K.rubro(nombre, self.tienda)
        if not toda and not rub:
            self.hechos.append({"tipo": "no_vende", "que": nombre})
            return
        orden = str(b.get("orden") or "nada")
        cuantos = K.entero(b.get("cantidad"), 1) if K.n(orden) not in ("nada", "") else 5
        entre = [m["id"] for m in self.estado["mostrados"]] if _si(b.get("entre_lo_mostrado")) else None
        conds = [str(c) for c in _lista(b.get("condiciones"))]
        r = K.buscar(rub, conds, orden, cuantos, self.tienda, entre)
        self.hechos.append({"tipo": "lista", "rubro": rub or "la tienda", **r})
        mostrar(self.estado, r["filas"])
        self.estado["busqueda"] = {"rubro": rub, "condiciones": conds, "orden": orden}

    # ── la plata ─────────────────────────────────────────────────────────────

    def cuenta(self, articulos: list, reparto: list, tope=None, si_pasa: str = "") -> None:
        """Una cuenta por destino. Con mas de un destino, el total general es la suma de los totales."""
        grupos = {}
        for a in articulos:
            grupos.setdefault(a.get("destino") or "", []).append({"id": a["id"], "cantidad": a["cantidad"]})
        tope = K.entero(tope)
        bloques = []
        for destino, items in grupos.items():
            r = self.herramienta("cuenta", items=items, destinos=[destino] if destino else [],
                                 reparto_pago=reparto or None)
            if (r.get("cuenta") or {}).get("total_ars") is not None:
                bloques.append({"destino": destino, **r["cuenta"]})
        if not bloques:
            return
        total = sum(int(b.get("total_final_ars") or b["total_ars"]) for b in bloques)
        if tope and total > tope and si_pasa:
            idt = K.identificar(si_pasa, "", self.tienda)
            saca = {str(v["id"]) for v in idt.get("variantes") or []}
            quedan = [a for a in articulos if str(a["id"]) not in saca]
            if saca and quedan and len(quedan) < len(articulos):
                self.hechos.append({"tipo": "pasa_tope", "tope": tope, "saca": idt["producto"]["nombre"]})
                if articulos is self.estado["pedido"]:
                    self.estado["pedido"] = quedan
                return self.cuenta(quedan, reparto)
        self.hechos.append({"tipo": "cuenta", "bloques": bloques, "total": total if len(bloques) > 1 else None})

    def pedido(self, ped: dict, condicionado: bool) -> list:
        """Los articulos resueltos. Si alguno no se puede resolver, pregunta y el pedido no cambia."""
        resueltos, falta = [], False
        for a in _lista(ped.get("articulos")):
            if not isinstance(a, dict) or not a.get("producto"):
                continue
            idt = K.identificar(str(a["producto"]), str(a.get("color") or ""), self.tienda)
            if idt["veredicto"] == "not_found":
                self.hechos.append({"tipo": "no_existe", "nombre": a["producto"]})
                falta = True
            elif idt["veredicto"] == "ambiguous":
                self.preguntar("¿Cuál de estos querés: " + " o ".join(p["nombre"] for p in idt["opciones"]) + "?")
                falta = True
            elif a.get("cantidad") not in (None, "") and K.entero(a["cantidad"]) < 1:
                # Una cantidad que no es un numero no se adivina.
                self.preguntar(f"¿Cuántos {idt['producto'].get('modelo') or a['producto']} querés?")
                falta = True
            elif idt.get("falta_color"):
                colores = [v["color"] for v in idt["variantes"] if K.con_stock(v) and v.get("color")]
                self.preguntar(f"¿El {idt['producto'].get('modelo') or a['producto']} en qué color: "
                               + " o ".join(colores) + "?")
                falta = True
            else:
                p = idt["producto"]
                resueltos.append({"id": str(p["id"]), "nombre": p["nombre"], "precio": p.get("precio_ars"),
                                  "cantidad": K.entero(a.get("cantidad"), 1),
                                  "destino": _destino(a.get("destino"))})
        if falta or condicionado:
            for a in resueltos:
                self.hechos.append({"tipo": "producto", "producto": K.por_id(a["id"], self.tienda), "variantes": [],
                                    "dato": {}, "pide": ""})
            mostrar(self.estado, [{"id": a["id"], "nombre": a["nombre"], "precio": a["precio"]} for a in resueltos])
            return []
        return resueltos


def ejecutar(llena: dict, estado: dict, tienda_id: str, explicar=None) -> Turno:
    """La traduccion entera, casilla por casilla, en un orden fijo."""
    t = Turno(estado, tienda_id)
    llena = llena or {}

    cliente = llena.get("cliente") if isinstance(llena.get("cliente"), dict) else {}
    estado["cliente"].update({k: v for k, v in cliente.items() if v and k in ("localidad", "nombre", "es")})

    # LAS REFERENCIAS: una que puede apuntar a varios modelos se pregunta; el resto es el producto que nombra.
    nombrados = {K.n(p.get("producto")) for p in _lista(llena.get("productos")) if isinstance(p, dict)}
    nombrados |= {K.n(a.get("producto")) for a in _lista((llena.get("pedido") or {}).get("articulos"))
                  if isinstance(a, dict)}
    dudosas = set()
    for r in _lista(llena.get("referencias")):
        if not isinstance(r, dict):
            continue
        cand = [c for c in _lista(r.get("candidatos")) if str(c).strip()]
        modelos = {_modelo(str(c), tienda_id) for c in cand}
        if len(modelos) > 1 and K.n(r.get("es")) not in {K.n(c) for c in cand}:
            t.preguntar(f"¿A cuál te referís con \"{r.get('dijo')}\": " + " o ".join(map(str, cand)) + "?")
            dudosas |= {K.n(r.get("es")), K.n(r.get("dijo"))}
        elif r.get("es") and K.n(r["es"]) not in nombrados:
            t.producto(str(r["es"]))

    for p in _lista(llena.get("productos")):
        p = p if isinstance(p, dict) else {"producto": p}
        if p.get("producto") and K.n(p["producto"]) not in dudosas:
            t.producto(str(p["producto"]), str(p.get("quiere_saber") or ""))

    # LO QUE EL CLIENTE DA POR CIERTO: si es de un producto, se mira en su ficha; si no, en la politica del tema.
    for a in _lista(llena.get("afirma")):
        if not isinstance(a, dict):
            continue
        sobre = [str(a["sobre"])] if K.identificar(str(a.get("sobre") or ""), "", tienda_id)["veredicto"] == "exists" \
            else K.nombrados(str(a.get("dice") or ""), tienda_id)
        if sobre:
            for nombre in sobre:
                t.producto(nombre, str(a.get("dice") or ""))
        elif a.get("tema"):
            llena["politicas"] = _lista(llena.get("politicas")) + [a["tema"]]

    for b in _lista(llena.get("busquedas")):
        if isinstance(b, dict):
            t.busqueda(b)

    for x in _lista(llena.get("no_vende")):
        t.hechos.append({"tipo": "no_vende", "que": str(x)})

    for c in _lista(llena.get("compatibilidad")):
        if not isinstance(c, dict):
            continue
        if _si(c.get("falta_modelo")):
            t.preguntar(f"¿Qué modelo es tu {c.get('con')}? Con eso te confirmo qué le sirve.")
            continue
        idt = K.identificar(str(c.get("producto") or ""), "", tienda_id)
        if idt["veredicto"] != "exists":
            t.preguntar(f"¿Qué {c.get('producto')} decís, el modelo exacto?")
            continue
        r = t.herramienta("compatibilidad", producto=str(idt["producto"]["id"]), con=str(c.get("con") or ""))
        for v in _lista(r.get("compatibilidad")):
            t.hechos.append({"tipo": "compat", **v})

    temas = list(dict.fromkeys(str(x) for x in _lista(llena.get("politicas")) if str(x).strip()))
    if temas:
        # Solo las politicas: el criterio de la FAQ es una instruccion para el que redacta, no texto para el cliente.
        for p in fuente.politicas_de(temas, tienda_id).get("politicas") or []:
            t.hechos.append({"tipo": "politica", "tema": p.get("tema"), "texto": p.get("texto")})

    # EL PEDIDO
    ped = llena.get("pedido") if isinstance(llena.get("pedido"), dict) else {}
    tot = dict(llena.get("total")) if isinstance(llena.get("total"), dict) else {}
    # UNA CONDICION SOBRE EL TOTAL la cumple el codigo: "si pasa de 300 mil saca el MX" es un tope y que sacar.
    condiciones = []
    for c in _lista(llena.get("condiciones")):
        tope = K.tope_del_total(str(c.get("si") or "")) if isinstance(c, dict) else None
        saca = K.nombrados(str(c.get("entonces") or ""), tienda_id) if tope else []
        if tope and saca:
            tot.update(pide=True, tope=tope, si_pasa=saca[0])
        else:
            condiciones.append(c)
    condicionado = bool(condiciones)
    reparto = [r for r in _lista(ped.get("reparto_pago")) if isinstance(r, dict) and r.get("porcentaje")]
    cambio = False
    if reparto:
        estado["reparto"] = reparto
        cambio = True
    if _si(ped.get("cambia")) and _lista(ped.get("articulos")):
        nuevo = t.pedido(ped, condicionado)
        if nuevo:
            estado["pedido"] = nuevo
            t.hechos.append({"tipo": "pedido", "articulos": nuevo})
            cambio = True
    elif _si(ped.get("cambia")) and isinstance(ped.get("articulos"), list) and not reparto and estado["pedido"]:
        # El pedido entero como queda es una lista vacia: el cliente saco todo.
        estado["pedido"] = []
        t.hechos.append({"tipo": "pedido_vacio"})
    if estado["pedido"] and (cambio or _si(tot.get("pide"))):
        t.cuenta(estado["pedido"], estado["reparto"], tot.get("tope"), str(tot.get("si_pasa") or ""))
    elif _si(tot.get("pide")) and not estado["pedido"]:
        # Un total sin pedido: lo que pregunto, una unidad de cada uno, al destino que dijo.
        destinos = [d for d in map(_destino, _lista(llena.get("envios"))) if d]
        productos = [h for h in t.hechos if h["tipo"] == "producto"]
        # Sin color elegido vale el precio del modelo solo si todos sus colores salen lo mismo.
        dudosos = [h for h in productos if h.get("falta_color")
                   and len({v.get("precio_ars") for v in h["variantes"] if K.con_stock(v)}) > 1]
        for h in dudosos:
            t.preguntar(f"¿El {h['producto'].get('modelo')} en qué color? Cambia el precio.")
        items = [{"id": str(h["producto"]["id"]), "cantidad": 1, "destino": destinos[0] if destinos else ""}
                 for h in productos]
        if items and not dudosos:
            t.cuenta(items, estado["reparto"])

    # LOS ENVIOS que no entraron en una cuenta
    cotizados = {K.n(b["destino"]) for h in t.hechos if h["tipo"] == "cuenta" for b in h["bloques"]}
    destinos = [d for d in map(_destino, _lista(llena.get("envios"))) if d and K.n(d) not in cotizados]
    if destinos:
        r = t.herramienta("envio", destinos=destinos)
        t.hechos.append({"tipo": "envio", **r})

    if condicionado:
        # Lo que depende de una condicion no se anota solo: el cliente lo confirma viendo el resultado.
        t.preguntar("¿Te lo confirmo así?")
    for x in _lista(llena.get("explicar")):
        t.hechos.append({"tipo": "explicar", "texto": explicar(str(x)) if explicar else ""})
    if _si(llena.get("catalogo")):
        t.hechos.append({"tipo": "catalogo", "rubros": sorted({p.get("categoria") for p in K.productos(tienda_id)})})
    if _si(llena.get("fuera_de_tema")):
        t.hechos.append({"tipo": "fuera_de_tema"})
    if _si(llena.get("humano")):
        t.hechos.append({"tipo": "humano"})
    for x in _lista(llena.get("preguntar")):
        t.preguntar(f"¿Me decís {x}?")
    return t
