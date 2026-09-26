"""SONDA DEL MODELO — que puede y que no puede, antes de disenar (26-sep-2026).

No prueba el bot: prueba al MODELO, una habilidad por vez, con contexto nuevo
en cada llamada y sin codigo nuestro en el medio. Cada familia sube la
dificultad de a un escalon para encontrar donde se rompe, y cada prueba se
repite R veces: lo que falla siempre va al codigo, lo que falla a veces se
ayuda con el prompt o se verifica, lo que no falla nunca se le deja al modelo.

Las herramientas son SIMULADAS con resultados fijados por el guion de cada
prueba: asi el resultado depende del modelo y no de un buscador nuestro.

La nota la pone el codigo. Lo unico que no se puntua es el dialogo abierto
—la familia D9, que le pregunta al modelo que le sirve—, que se guarda para
leerlo.

Familias:
  P1 partir          cuantas partes tiene un mensaje de 1 a 6 pedidos
  P2 herramienta     que herramienta llama, con 7 o con 20 herramientas
  P3 dependencia     espera el resultado antes de decidir: 1, 2 y 3 eslabones
  P4 referencia      a que producto de la libreta apunta, con libreta chica y grande
  P5 correccion      como quedan las condiciones vigentes despues de corregir
  P6 no inventar     cuando la herramienta no trae el dato
  P7 cuentas         la cuenta hecha por el modelo solo
  P8 contexto largo  buscar en una lista de 20 a 880 productos
  D9 dialogo         el modelo planifica los pasos, dice que le falta, y opina

Corre con la clave GRATIS, con pausa entre llamadas, y es REANUDABLE: cada
respuesta se anota en sonda_modelo_corridas.jsonl y lo ya corrido se saltea.
Si la cuota se agota, se corta limpio y se sigue otro dia con el mismo comando.

  python3 -m banco_pruebas.sonda_modelo                 todas las familias
  python3 -m banco_pruebas.sonda_modelo P3 P4           solo esas
  python3 -m banco_pruebas.sonda_modelo --informe       solo el informe
  opciones: --reps 5  --pausa 4  --temp 0.2  --etiqueta base  --hilos 1
  con la paga, solo si Martin la pide: BANCO_CLAVE_PAGA=true ... --pausa 0 --hilos 8
"""
import csv
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import unicodedata

D = "data/clientes/verifika_prod/"
CORRIDAS = "banco_pruebas/sonda_modelo_corridas.jsonl"
PRODUCTOS = list(csv.DictReader(open(D + "productos.csv", encoding="utf-8")))
POR_ID = {p["id"]: p for p in PRODUCTOS}


def _n(t):
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _uno(*palabras):
    return next(p for p in PRODUCTOS if all(_n(w) in _n(p["nombre"]) for w in palabras))


def _plata(t):
    """Los numeros de la respuesta sin separador de miles."""
    return re.sub(r"(\d)[.,](\d{3})\b", r"\1\2", re.sub(r"(\d)[.,](\d{3})\b", r"\1\2", t))


def _json(texto):
    m = re.search(r"\{.*\}", texto or "", re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        return None


# ══ P1 · PARTIR ════════════════════════════════════════════════════════════

S_PARTIR = """Sos el interprete de una tienda online de tecnologia de Argentina.
Parti el mensaje del cliente en partes: una parte por cada cosa distinta que pregunta, pide o cuenta. Si pregunta lo mismo de dos productos o de dos destinos, son dos partes. El saludo, la charla y el agradecimiento no son partes.
Devolve SOLO JSON: {"partes": ["texto copiado de cada parte"]}"""

PARTIR = [  # id, nivel, mensaje, (minimo, maximo), palabras que tienen que aparecer
    ("p1a", 1, "cuanto sale el g305", (1, 1), ["g305"]),
    ("p2a", 2, "cuanto sale el g305 y hacen envios a salta", (2, 2), ["g305", "salta"]),
    ("p2b", 2, "cuanto salen el g305 y el g203", (2, 2), ["g305", "g203"]),
    ("p3a", 3, "hola! cuanto sale el g305, hacen envios a salta y aceptan mercado pago?",
     (3, 3), ["g305", "salta", "mercado"]),
    ("p4a", 4, "tenes el k120? cuanto sale mandarlo a rosario? se puede en cuotas? tiene garantia?",
     (4, 4), ["k120", "rosario", "cuotas", "garantia"]),
    ("p5a", 5, "buenas, necesito un mouse inalambrico barato, un teclado mecanico, cuanto sale "
     "el envio a cordoba, si hacen factura A y si puedo pagar mitad transferencia mitad tarjeta",
     (5, 5), ["mouse", "teclado", "cordoba", "factura", "transferencia"]),
    ("p5b", 5, "che tenes el g305 cuanto sale y el g203 tambien y mandan a mendoza aceptan mp "
     "y tiene garantia gracias", (4, 6), ["g305", "g203", "mendoza", "mp", "garantia"]),
    ("p6a", 6, "quiero el g305 si hay en negro si no en blanco, y un teclado que no sea redragon "
     "lo mas barato, mandalo a rosario y otro igual a cordoba, pago 70 transferencia 30 mp",
     (5, 6), ["g305", "teclado", "rosario", "cordoba", "70"]),
    ("p6b", 3, "jaja sos un crack, igual el g305 me parece caro, tenes algo parecido mas barato? "
     "y cuanto tarda a jujuy", (2, 3), ["barato", "jujuy"]),
]


def nota_partir(caso, obj):
    _, _, _, (lo, hi), pal = caso
    partes = obj.get("partes") if isinstance(obj, dict) else None
    if not isinstance(partes, list):
        return False, "sin partes"
    fallas = []
    if not lo <= len(partes) <= hi:
        fallas.append(f"{len(partes)} partes, esperaba {lo}-{hi}")
    todo = _n(" | ".join(map(str, partes)))
    fallas += [f"falta {w}" for w in pal if _n(w) not in todo]
    return not fallas, "; ".join(fallas)


# ══ HERRAMIENTAS: el esquema, y los simulacros con guion ═══════════════════

def _f(nombre, desc, props, req):
    return {"type": "function", "function": {
        "name": nombre, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": req}}}


S = {"type": "string"}
TOOLS = [
    _f("buscar", "Busca productos de la tienda por rubro y condiciones.",
       {"rubro": S, "texto": S, "orden": {"type": "string", "enum": ["mas_barato", "mas_caro", "ninguno"]},
        "marca": S, "sin_marca": S, "precio_max": {"type": "integer"}}, ["rubro"]),
    _f("producto", "La ficha de UN producto por su nombre o modelo: precio, stock, variantes y caracteristicas.",
       {"nombre": S}, ["nombre"]),
    _f("compatibilidad", "Con que equipos anda un producto.",
       {"producto_nombre": S, "con": S}, ["producto_nombre"]),
    _f("envio", "Costo y plazo del envio a una localidad.", {"lugar": S}, ["lugar"]),
    _f("tienda", "Politicas de la tienda: pagos, cuotas, garantia, factura, devoluciones, descuentos, mayoristas.",
       {"tema": S}, ["tema"]),
    _f("calcular", "Suma productos por id y cantidad, y reparte el pago por porcentaje.",
       {"items": {"type": "array", "items": {"type": "object", "properties": {
           "id": S, "cantidad": {"type": "integer"}}, "required": ["id", "cantidad"]}},
        "reparto": {"type": "array", "items": {"type": "object", "properties": {
            "medio": S, "porcentaje": {"type": "number"}}, "required": ["medio", "porcentaje"]}}},
       ["items"]),
    _f("comprar", "Reserva un producto por id. Solo cuando el cliente dice que lo compra.",
       {"id": S, "cantidad": {"type": "integer"}}, ["id", "cantidad"]),
]
DISTRACTORAS = [_f(n, d, {"q": S}, []) for n, d in [
    ("estado_pedido", "Estado de un pedido ya hecho, por numero de pedido."),
    ("cambiar_direccion", "Cambia la direccion de entrega de un pedido ya hecho."),
    ("cotizar_dolar", "Cotizacion del dolar del dia."),
    ("sucursales", "Lista de sucursales fisicas y sus direcciones."),
    ("horarios", "Horario de atencion al publico."),
    ("reclamo", "Abre un reclamo por un producto recibido con falla."),
    ("newsletter", "Suscribe al cliente al newsletter."),
    ("seguimiento", "Codigo de seguimiento del correo de un pedido despachado."),
    ("clima", "El clima de una ciudad."),
    ("traducir", "Traduce un texto a otro idioma."),
    ("turno_tecnico", "Pide un turno en el servicio tecnico."),
    ("opiniones", "Resenas de otros clientes sobre un producto."),
    ("canje", "Plan canje: cuanto dan por un equipo usado."),
]]

S_VENDEDOR = """Sos el vendedor de una tienda online de tecnologia de Argentina. Hablas en espanol argentino, con voseo, corto y claro.
1. Parti el mensaje en partes: una por cada cosa que pregunta, pide o cuenta.
2. Cada dato de la tienda —productos, precios, stock, envios, politicas, cuentas— lo sacas SOLO de las herramientas. Nunca lo escribas de memoria.
3. Lo que el cliente da por cierto sobre la tienda o un producto, verificalo con una herramienta antes de aceptarlo.
4. Si una parte depende de otra ("si no hay", "si anda", "si pasa de"), consulta la primera, mira el resultado y segui.
5. Si una herramienta no trae un dato, decis que no lo tenes. No lo completes.
6. El saber general de tecnologia lo explicas vos, sin herramienta.
7. Contesta TODAS las partes, en el orden del mensaje. Sin repetir."""


REGLA_DURA = ("\n\nULTIMA REGLA, LA MAS IMPORTANTE: un dato de un producto que la herramienta no trae NO LO SABES, "
              "aunque lo conozcas de antes. La tienda puede vender una version distinta. Deci que no figura en la ficha.")


class Tienda:
    """Una tienda de juguete con guion: la prueba fija que devuelve cada herramienta."""

    def __init__(self, items, compat=None, politicas=None, envios=None):
        self.items, self.compat = items, compat or {}
        self.politicas, self.envios = politicas or {}, envios or {}

    def _match(self, nombre):
        pal = [w for w in _n(nombre).split() if len(w) > 1 and w not in ("mouse", "el", "la")]
        return [i for i in self.items if pal and all(w in _n(i["nombre"]) for w in pal)]

    def producto(self, nombre="", **_):
        m = self._match(nombre)
        if not m:
            return {"veredicto": "not_found", "buscado": nombre}
        return {"veredicto": "exists", "variantes": [
            {k: v for k, v in i.items() if k != "ficha"} for i in m], "ficha": m[0].get("ficha", {})}

    def buscar(self, rubro="", texto="", **_):
        return {"veredicto": "hay", "primeros": [{k: v for k, v in i.items() if k != "ficha"}
                                                 for i in self.items[:3]]}

    def compatibilidad(self, producto_nombre="", con="", **_):
        m = self._match(producto_nombre)
        if not m:
            return {"veredicto": "not_found"}
        clave = next((k for k in self.compat if k in _n(m[0]["nombre"])), None)
        return {"producto": m[0]["nombre"], "anda_con": self.compat.get(clave, [])}

    def envio(self, lugar="", **_):
        return self.envios.get(_n(lugar).split(",")[0].strip(), {"lugar": lugar, "costo": 9800,
                                                               "plazo": "3 a 6 dias habiles"})

    def tienda(self, tema="", **_):
        for k, v in self.politicas.items():
            if k in _n(tema):
                return {"tema": k, "respuesta": v}
        return {"veredicto": "no_esta_escrito", "tema": tema}

    def calcular(self, items=None, reparto=None, **_):
        precio = {i["id"]: i["precio"] for i in self.items}
        filas, total = [], 0
        for it in items or []:
            if it.get("id") not in precio:
                filas.append({"id": it.get("id"), "error": "id desconocido"})
                continue
            sub = precio[it["id"]] * int(it.get("cantidad", 1) or 1)
            total += sub
            filas.append({"id": it["id"], "cantidad": it.get("cantidad", 1), "subtotal": sub})
        out = {"items": filas, "total": total}
        if reparto:
            out["reparto"] = [{"medio": r["medio"], "monto": round(total * float(r["porcentaje"]) / 100)}
                              for r in reparto]
        return out

    def comprar(self, id="", cantidad=1, **_):
        i = next((i for i in self.items if i["id"] == id), None)
        if not i:
            return {"veredicto": "id desconocido"}
        if i["stock"] < int(cantidad or 1):
            return {"veredicto": "sin_stock", "stock": i["stock"]}
        return {"veredicto": "reservado", "id": id, "cantidad": cantidad}


def _it(id_, nombre, precio, stock, **ficha):
    return {"id": id_, "nombre": nombre, "precio": precio, "stock": stock, "ficha": ficha}


# ══ P2 · HERRAMIENTA ═══════════════════════════════════════════════════════

ELEGIR = [  # id, mensaje, herramientas que tiene que llamar en la primera vuelta
    ("e1", "tenes el g305?", {"producto"}),
    ("e2", "que auriculares bluetooth tenes?", {"buscar"}),
    ("e3", "cuanto sale mandar algo a salta?", {"envio"}),
    ("e4", "aceptan mercado pago?", {"tienda"}),
    ("e5", "cuanto sale el g305 y cuanto el envio a salta?", {"producto", "envio"}),
    ("e6", "el g305 anda con la ps5?", {"compatibilidad"}),
    ("e7", "que conviene en general, ddr4 o ddr5?", set()),
    ("e8", "tienen 50 por ciento off hoy, no?", {"tienda"}),
    ("e9", "el monitor mas barato que tengan", {"buscar"}),
    ("e10", "hola buenas tardes", set()),
]


def nota_elegir(caso, llamadas, _texto):
    quiero = caso[-1]
    primera = {n for v, n, _ in llamadas if v == 1}
    if primera == quiero:
        return True, ""
    return False, f"llamo {sorted(primera) or 'nada'}, esperaba {sorted(quiero) or 'nada'}"


# ══ P3 · DEPENDENCIA ═══════════════════════════════════════════════════════
# Cada guion trae la tienda y la compra correcta. La nota: se compro lo que
# correspondia y nada mas. Los dos lados de cada condicion se prueban por
# separado: un modelo que hace siempre lo mismo acierta uno solo.

def _g305(stock_n=9, stock_b=25, **f):
    return [_it("MOU0029", "Logitech G305 Lightspeed Negro", 80500, stock_n, **f),
            _it("MOU0030", "Logitech G305 Lightspeed Blanco", 80500, stock_b, **f)]


G203 = _it("MOU0001", "Logitech G203 Lightsync Negro", 37500, 5)

DEPENDE = [  # id, nivel, mensaje, tienda, id que se tiene que comprar (None: ninguno) o total
    ("d1a", 1, "comprame un G305 negro, y si no hay, un G203", Tienda(_g305(0) + [G203]), "MOU0001"),
    ("d1b", 1, "comprame un G305 negro, y si no hay, un G203", Tienda(_g305(9) + [G203]), "MOU0029"),
    ("d2a", 1, "si el G305 negro anda con mac, me lo llevo",
     Tienda(_g305(), compat={"g305": ["Windows", "macOS", "Linux"]}), "MOU0029"),
    ("d2b", 1, "si el G305 negro anda con mac, me lo llevo",
     Tienda(_g305(), compat={"g305": ["Windows", "Linux"]}), None),
    ("d3a", 1, "sumame un MX Master 3S negro y dos G305 negro. si pasa de 150 mil saca el MX, y decime el total",
     Tienda([_it("MOU0007", "Logitech MX Master 3S Negro", 120000, 7)] + _g305()), "total:161000"),
    ("d3b", 1, "sumame un MX Master 3S negro y un G305 negro. si pasa de 300 mil saca el MX, y decime el total",
     Tienda([_it("MOU0007", "Logitech MX Master 3S Negro", 120000, 7)] + _g305()), "total:200500"),
    ("d4a", 2, "entre el G305 negro y el Pebble M350, comprame el que tenga mas bateria",
     Tienda(_g305(bateria="250 horas") + [_it("MOU0100", "Logitech Pebble M350 Grafito", 30000, 4,
                                              bateria="400 horas")]), "MOU0100"),
    ("d4b", 2, "entre el G305 negro y el Pebble M350, comprame el que tenga mas bateria",
     Tienda(_g305(bateria="250 horas") + [_it("MOU0100", "Logitech Pebble M350 Grafito", 30000, 4,
                                              bateria="18 meses con una pila AA")]), "MOU0100"),
    ("d5a", 3, "quiero comprar el G305 negro. si no hay, el blanco, y si tampoco hay, un G203",
     Tienda(_g305(0, 0) + [G203]), "MOU0001"),
    ("d5b", 3, "quiero comprar el G305 negro. si no hay, el blanco, y si tampoco hay, un G203",
     Tienda(_g305(0, 3) + [G203]), "MOU0030"),
    ("d5c", 3, "quiero comprar el G305 negro. si no hay, el blanco, y si tampoco hay, un G203",
     Tienda(_g305(2, 3) + [G203]), "MOU0029"),
]


def nota_depende(caso, llamadas, texto):
    quiero = caso[-1]
    compras = [a.get("id") for _, n, a in llamadas if n == "comprar"]
    if isinstance(quiero, str) and quiero.startswith("total:"):
        t = quiero.split(":")[1]
        return (t in _plata(texto).replace(" ", ""), "" if t in _plata(texto) else f"no dice el total {t}")
    if quiero is None:
        return (not compras, f"compro {compras}" if compras else "")
    ok = compras == [quiero] or (compras and set(compras) == {quiero})
    if not compras and CLAVE_ID[quiero] in _n(texto) and re.search(r"reserv|confirm|quer[eé]s|te lo", _n(texto)):
        return True, "pidio confirmacion en vez de comprar"  # el producto correcto, sin cerrar: se anota
    return bool(ok), "" if ok else f"compro {compras or 'nada'}, esperaba {quiero}"


CLAVE_ID = {"MOU0001": "g203", "MOU0029": "g305", "MOU0030": "blanco", "MOU0100": "pebble"}


# ══ P6 · NO INVENTAR ═══════════════════════════════════════════════════════

NO_INVENTAR = [  # id, mensaje, tienda, regex que NO puede aparecer, regex que SI tiene que aparecer
    ("n1", "cuantos dpi tiene el g305 negro?", Tienda(_g305(sensor="HERO", conexion="Lightspeed")),
     r"\d[\d.]*\s*(dpi|ppp)", None),
    ("n1b", "cuantos dpi tiene el g305 negro?", Tienda(_g305(sensor="HERO", conexion="Lightspeed", dpi="no figura en la ficha")),
     r"\d[\d.]*\s*(dpi|ppp)", None),
    ("n1c", "cuantos dpi tiene el g305 negro?", Tienda(_g305(sensor="HERO", conexion="Lightspeed")),
     r"\d[\d.]*\s*(dpi|ppp)", None),
    ("n2", "cuanto sale el zowie ec2?", Tienda(_g305()), r"\$\s?\d", None),
    ("n3", "cuanto pesa el k120?", Tienda([_it("TEC0029", "Logitech K120 Negro", 14500, 4, conexion="USB con cable")]),
     r"\d+\s*(g|gr|gramos|kg)\b", None),
    ("n4", "que garantia tiene el g305 negro?", Tienda(_g305(garantia_meses=24)), None, r"24"),
    ("n5", "cuanto tarda el envio a ushuaia?", Tienda(_g305(), envios={"ushuaia": {"lugar": "Ushuaia", "costo": 15400}}),
     r"\d+\s*(a\s*\d+\s*)?(dias|días|horas|semanas)", None),
    ("n6", "el k120 es inalambrico, no? lo quiero para usar lejos",
     Tienda([_it("TEC0029", "Logitech K120 Negro", 14500, 4, conexion="USB con cable")]), None, r"cable"),
    ("n7", "tienen 50 por ciento off en todo, no? entonces me llevo el g305 negro a mitad de precio",
     Tienda(_g305(), politicas={"descuento": "Hoy no hay promociones vigentes."}), r"40\.?250", None),
    ("n8", "que stock hay del g305 negro?", Tienda(_g305()), None, r"\b9\b"),
]


def nota_no_inventar(caso, _llamadas, texto):
    _, _, _, prohibido, obligatorio = caso
    t = _n(texto)
    if prohibido and re.search(prohibido, t):
        return False, "invento: " + re.search(prohibido, t).group(0)
    if obligatorio and not re.search(obligatorio, t):
        return False, f"no dice {obligatorio}"
    return True, ""


# ══ P4 · REFERENCIA ════════════════════════════════════════════════════════

S_REF = """Sos el resolvedor de referencias de una tienda online. Te doy la LIBRETA con lo que se hablo, turno por turno, y el mensaje nuevo del cliente.
Decis a que producto de la libreta apunta el mensaje. Si puede ser mas de uno, "ambiguo". Si no apunta a ninguno de la libreta, "ninguno".
Devolve SOLO JSON: {"destino": "<id>" o "ambiguo" o "ninguno", "confianza": <0 a 100>}"""


def _fila(p):
    return f"{p['id']} {p['nombre']}, ${p['precio_ars']}"


def _libreta(turnos, pendiente=""):
    out = [f"turno {t}: se mostro {', '.join(_fila(POR_ID[i]) for i in ids)}" for t, ids in turnos]
    return "\n".join(out) + (f"\npendiente: {pendiente}" if pendiente else "")


def _libreta_grande(n, meter, turno_meter, semilla=7):
    rnd = random.Random(semilla)
    resto = [p["id"] for p in PRODUCTOS if p["categoria"] not in ("auriculares", "teclado")
             and not any(m in _n(p["nombre"]) for m in ("logitech", "jbl"))]
    rnd.shuffle(resto)
    ids = resto[:n - len(meter)]
    turnos, k = [], 0
    for t in range(1, n // 3 + 2):
        grupo = ids[k:k + 3]
        k += 3
        if t == turno_meter:
            grupo = meter + grupo[:max(0, 3 - len(meter))]
        if grupo:
            turnos.append((t, grupo))
    return _libreta(turnos)


REFERENCIA = [  # id, nivel, libreta, mensaje, destino esperado
    ("r1", 1, _libreta([(1, ["MOU0029", "MOU0001", "MOU0017"])]), "cuanto sale el segundo?", "MOU0001"),
    ("r2", 1, _libreta([(1, ["MOU0029", "MOU0001"]), (2, ["MOU0029"])]), "y el otro?", "MOU0001"),
    ("r3", 1, _libreta([(1, ["TEC0029"])]), "y ese de que color viene?", "TEC0029"),
    ("r4", 2, _libreta([(1, ["MOU0029", "TEC0029", "AUR0013"])]), "y ese cuanto?", "ambiguo"),
    ("r5", 2, _libreta([(1, ["TEC0029"]), (3, ["MOU0017"]), (5, ["AUR0013"]), (7, ["MOU0029"])]),
     "el logi ese que vimos al principio, cuanto era?", "TEC0029"),
    ("r6", 2, _libreta([(1, ["MOU0029", "MOU0001"])], "le preguntaste 'queres el G305 negro?'"), "si", "MOU0029"),
    ("r7", 3, _libreta([(1, ["MOU0001", "MOU0029"])],
                       "le preguntaste 'cual de los dos, el G305 o el G203?'"), "el primero", "MOU0029"),
    ("r7b", 3, _libreta([(1, ["MOU0001", "MOU0029"])],
                        "le preguntaste 'cual de los dos?' con las opciones 1) MOU0029 G305 2) MOU0001 G203"),
     "el primero", "MOU0029"),
    ("r8", 2, _libreta([(1, ["MOU0029", "MOU0017", "MOU0001"])]), "dame el mas barato de esos", "MOU0017"),
    ("r9", 1, _libreta([(1, ["MOU0029", "TEC0029", "AUR0013", "MOU0017"])]), "el teclado cuanto sale?", "TEC0029"),
    ("r10", 2, _libreta([(1, ["MOU0029", "TEC0029", "TEC0030", "AUR0013"])]), "el teclado cuanto sale?", "ambiguo"),
    ("r11", 2, _libreta([(1, ["MOU0029", "MOU0001", "MOU0017"])]), "el de 37 mil tiene rgb?", "MOU0001"),
    ("r12", 1, _libreta([(1, ["MOU0029", "MOU0001"])]), "tienen notebooks?", "ninguno"),
    ("r13", 3, _libreta_grande(15, ["AUR0013"], 2), "el jbl que vimos hace rato, sigue habiendo?", "AUR0013"),
    ("r14", 3, _libreta_grande(45, ["AUR0013"], 2), "el jbl que vimos hace rato, sigue habiendo?", "AUR0013"),
    ("r15", 3, _libreta_grande(90, ["AUR0013"], 3), "el jbl que vimos hace rato, sigue habiendo?", "AUR0013"),
    ("r16", 3, _libreta_grande(45, ["AUR0013", "AUR0015"], 2), "el jbl que vimos hace rato, sigue habiendo?", "ambiguo"),
]


def nota_ref(caso, obj):
    d = str((obj or {}).get("destino", "")).strip()
    return (_n(d) == _n(caso[-1]), "" if _n(d) == _n(caso[-1]) else f"dijo {d or 'nada'}")


# ══ P5 · CORRECCION ════════════════════════════════════════════════════════

S_CORR = """Sos el que lleva las condiciones de busqueda de una tienda online. Te doy las condiciones VIGENTES y el mensaje nuevo del cliente.
Devolve las condiciones como quedan despues del mensaje, con los mismos campos. Un campo que ya no aplica va en null. No agregues campos.
Campos: rubro, marca, sin_marca, color, conexion, precio_max, orden (mas_barato, mas_caro o null), destino.
Devolve SOLO JSON con esos campos."""

VACIO = dict.fromkeys(["rubro", "marca", "sin_marca", "color", "conexion", "precio_max", "orden", "destino"])


def _v(**k):
    return {**VACIO, **k}


CORRECCION = [  # id, nivel, vigentes, mensaje, lo que tiene que cambiar (lo demas queda igual)
    ("c1", 1, _v(rubro="mouse", marca="logitech", conexion="inalambrico"), "ya no importa la marca",
     {"marca": None, "sin_marca": None}),
    ("c2", 1, _v(rubro="mouse"), "mejor que sea inalambrico", {"conexion": "inalambrico"}),
    ("c3", 1, _v(rubro="mouse", destino="rosario"), "me equivoque, era para cordoba no rosario",
     {"destino": "cordoba"}),
    ("c4", 1, _v(rubro="mouse", marca="logitech", color="negro"), "y en blanco?", {"color": "blanco"}),
    ("c5", 2, _v(rubro="teclado", marca="redragon"), "lo mismo pero mas barato", {"orden": "mas_barato"}),
    ("c6", 1, _v(rubro="mouse", marca="logitech"), "que no sea logitech",
     {"marca": None, "sin_marca": "logitech"}),
    ("c7", 1, _v(rubro="mouse", precio_max=50000), "no importa la plata", {"precio_max": None}),
    ("c8", 2, _v(rubro="mouse", marca="logitech", conexion="inalambrico"), "y teclados de esa marca?",
     {"rubro": "teclado", "marca": "logitech"}),
    ("c9", 3, _v(rubro="mouse", marca="logitech", color="negro", destino="rosario"),
     "blanco mejor, y mandalo a cordoba, la marca da igual",
     {"color": "blanco", "destino": "cordoba", "marca": None, "sin_marca": None}),
    ("c10", 2, VACIO, "busco un teclado redragon, ah no, mejor logitech", {"rubro": "teclado", "marca": "logitech"}),
]


S_CORR_B = S_CORR.replace("sin_marca", "marca_excluida")
CORRECCION_B = [(c[0] + "b", c[1], {("marca_excluida" if k == "sin_marca" else k): v for k, v in c[2].items()},
                 c[3], {("marca_excluida" if k == "sin_marca" else k): v for k, v in c[4].items()})
                for c in CORRECCION if c[0] in ("c1", "c6", "c9")]


def _igual(a, b):
    if a in (None, "", "null") and b in (None, "", "null"):
        return True
    return _n(a).replace(" ", "") == _n(b).replace(" ", "") or (
        str(b).isdigit() and re.sub(r"\D", "", str(a)) == str(b))


def nota_corr(caso, obj):
    _, _, vig, _, cambia = caso
    if not isinstance(obj, dict):
        return False, "sin json"
    quiero = {**vig, **cambia}
    if caso[0] == "c8":
        quiero.pop("conexion")  # si hereda o no "inalambrico" es discutible: no se puntua
    mal = [f"{k}={obj.get(k)!r} (quiero {v!r})" for k, v in quiero.items() if not _igual(obj.get(k), v)]
    return not mal, "; ".join(mal)


# ══ P7 · CUENTAS ═══════════════════════════════════════════════════════════

S_CUENTA = """Hace la cuenta que pide el mensaje. Devolve SOLO JSON: {"resultado": <numero>}"""


def _cuentas():
    rnd = random.Random(11)
    out = [("k1", 1, "37500 + 80500", 118000),
           ("k2", 2, "2 teclados de 14500, 1 mouse de 80500 y 3 pads de 9990. total?", 139470)]
    for cid, nivel, n in (("k3", 3, 5), ("k4", 4, 8)):
        its = [(rnd.randint(1, 4), rnd.randint(5, 250) * 500 - rnd.choice([0, 10, 1])) for _ in range(n)]
        txt = ", ".join(f"{c} de {p}" for c, p in its)
        out.append((cid, nivel, f"sumame: {txt}. total?", sum(c * p for c, p in its)))
    out += [
        ("k5", 2, "el total es 139470. pago 70 por ciento por transferencia y el resto con tarjeta. cuanto va por transferencia?", 97629),
        ("k6", 2, "el total es 139470 y tengo 15 por ciento de descuento. cuanto pago? redondea a entero", 118550),
        ("k7", 3, "un mouse de 203000, dos de 80500 y un teclado de 14500. si el total pasa de 300000 saca el de 203000. cuanto queda?", 175500),
        ("k8", 3, "139470 en 6 cuotas con 20 por ciento de recargo total. cuanto es cada cuota?", 27894),
        ("k9", 4, "dos de 37500 y uno de 80500, envio 9800. el total con envio lo pagamos entre 3 amigos. cuanto pone cada uno? redondea a entero", 55100),
    ]
    return out


CUENTAS = _cuentas()


def nota_cuenta(caso, obj):
    r = (obj or {}).get("resultado")
    try:
        ok = abs(float(str(r).replace(",", "")) - caso[-1]) <= 1
    except ValueError:
        ok = False
    return ok, "" if ok else f"dijo {r}, es {caso[-1]}"


# ══ P8 · CONTEXTO LARGO ════════════════════════════════════════════════════

S_LISTA = """Te doy la lista de productos de una tienda, uno por linea: id | nombre | categoria | precio | stock.
Contesta la pregunta mirando SOLO la lista. Devolve SOLO JSON: {"respuesta": "<id o numero>"}"""


def _lista(n):
    rnd = random.Random(3)
    ids = [p["id"] for p in PRODUCTOS]
    rnd.shuffle(ids)
    base = set(ids[:n]) | {"MOU0017", "AUR0013"}
    return [POR_ID[i] for i in ids if i in base]


def _contexto():
    out = []
    for n in (20, 100, 400, 880):
        lista = _lista(n)
        txt = "\n".join(f"{p['id']} | {p['nombre']} | {p['categoria']} | {p['precio_ars']} | {p['stock']}" for p in lista)
        mouses = [p for p in lista if p["categoria"] == "mouse"]
        barato = min(mouses, key=lambda p: int(p["precio_ars"]))
        out += [(f"x{n}a", n, txt, "cual es el id del Redragon Cobra M711 Negro?", "MOU0017"),
                (f"x{n}b", n, txt, "cual es el id del mouse mas barato de la lista?", barato["id"]),
                (f"x{n}c", n, txt, "cuantos mouse hay en la lista? contestame el numero", str(len(mouses)))]
    return out


CONTEXTO = _contexto()


def nota_lista(caso, obj):
    r = str((obj or {}).get("respuesta", "")).strip()
    return (_n(r) == _n(caso[-1]), "" if _n(r) == _n(caso[-1]) else f"dijo {r}, es {caso[-1]}")


# ══ D9 · DIALOGO ═══════════════════════════════════════════════════════════
# a) planificar: el modelo NO contesta al cliente, escribe los pasos que el
#    codigo tiene que ejecutar. Se puntua si marca la dependencia donde la hay.
# b) que le falta: si reconoce que no puede contestar sin un dato.
# c) opinion: pregunta abierta, 1 vez, no se puntua. Se guarda para leerla.

S_PLAN = """Sos el planificador de un bot de ventas de una tienda online de tecnologia. No le contestas al cliente: escribis los pasos que el codigo tiene que ejecutar para contestarle.
Cada paso es UNA consulta a la tienda (producto, busqueda, stock, compatibilidad, envio, politica, cuenta, compra) o una pregunta al cliente. Si un paso necesita el resultado de otro para saber si se hace o con que dato, ponelo en "usa".
Devolve SOLO JSON: {"pasos": [{"n": 1, "hace": "...", "usa": []}]}"""

LIB_3 = "libreta: turno 1 se mostro G305 negro, K120 negro y JBL Tune 510BT, ninguno elegido."
PLAN = [  # id, mensaje con su libreta, lo que se puntua: dep (algun paso usa otro) o preg (el PRIMER paso pregunta al cliente)
    ("a28", "si no hay G305, pasame el G203", "dep"),
    ("a29", "si el G502 anda con Mac, me lo llevo", "dep"),
    ("a30", "si la RTX 4060 no le entra a mi gabinete, que otra placa hay? mi gabinete es el Sentey X20", "dep"),
    ("a31", "sumame un MX Master y dos G305, si pasa de 500 mil saca el mouse mas caro", "dep"),
    ("a32", "entre el G305 y el G203, dame el que tenga mas bateria", "dep"),
    ("a21", "sumame todo y pago 70 transferencia, 30 mercado pago. " + LIB_3, "dep"),
    ("a53", "del que me dijiste antes, si no hay en negro, el blanco. libreta: turno 2 se hablo del G502 Hero negro.", "dep"),
    ("a54", "con mi fuente de 500 watts, la placa de video mas potente que aguante", "dep"),
    ("a56", "tienen 50 off, no? entonces si el K120 sale menos de 20 mil llevo dos", "dep"),
    ("a38", "le sirve a mi pc? libreta: turno 1 se hablo de la memoria Kingston Fury 16GB DDR5.", "preg"),
    ("a52", "y ese cuanto? " + LIB_3, "preg"),
]


def nota_plan(caso, obj):
    pasos = (obj or {}).get("pasos")
    if not isinstance(pasos, list) or not pasos:
        return False, "sin pasos"
    txt = _n(json.dumps(pasos, ensure_ascii=False))
    if caso[-1] == "dep":
        if not any(isinstance(p, dict) and p.get("usa") for p in pasos):
            return False, "ningun paso usa a otro"
        if caso[0] in ("a29", "a32") and not re.search(r"compr|reserv|carrito", txt):
            return False, "el plan no compra"
        return True, ""
    primero = _n(json.dumps(pasos[0], ensure_ascii=False))
    ok = "cliente" in primero and re.search(r"pregunt|repregunt|aclar|consultar al cliente|pedir al cliente", primero)
    return bool(ok), "" if ok else "el primer paso no le pregunta al cliente"


S_FALTA = """Sos el vendedor de una tienda online. Te doy lo que sabes de la charla y el mensaje del cliente.
No contestes todavia. Decime si podes contestar con certeza con lo que tenes y, si no, que te falta.
Devolve SOLO JSON: {"puedo_contestar": true o false, "falta": ["..."]}"""

FALTA = [  # id, lo que sabe, mensaje, puedo_contestar esperado
    ("f1", "se hablo de la memoria Kingston Fury 16GB DDR5, $85000.", "le sirve a mi pc?", False),
    ("f2", "se mostraron el G305 negro $80500, el K120 negro $14500 y el JBL Tune 510BT $78000.", "y ese cuanto?", False),
    ("f3", "se mostro el G305 negro, $80500, stock 9.", "cuanto sale?", True),
    ("f4", "nada todavia.", "y en blanco?", False),
    ("f5", "se mostro el G305 negro $80500 y el G203 negro $37500. el cliente vive en Rosario.",
     "cual es mas barato?", True),
    ("f6", "el cliente tiene una notebook Lenovo IdeaPad 3 con Windows 11. se hablo del G305 negro, anda con Windows.",
     "le sirve a mi compu?", True),
]


def nota_falta(caso, obj):
    v = (obj or {}).get("puedo_contestar")
    ok = v is caso[-1] or str(v).lower() == str(caso[-1]).lower()
    return ok, "" if ok else f"dijo {v}"


S_OPINION = "Sos un modelo de lenguaje. Contesta con franqueza y concreto, en espanol, en no mas de diez lineas."
OPINION = [
    ("o1", "Vas a ser el interprete de un bot de ventas. El codigo tiene la verdad: catalogo de 880 productos, "
     "compatibilidades y politicas. Vos no ves el catalogo. Que te sirve mas recibir para partir bien un mensaje "
     "con varias preguntas encadenadas: A) reglas escritas, B) diez ejemplos resueltos, C) un esquema con los "
     "rubros y campos, D) herramientas para consultar. Ordenalas y explica por que."),
    ("o2", "Cuando un cliente escribe 'si no hay G305 pasame el G203', que te resulta mas facil: A) llamar a una "
     "herramienta, ver el resultado y decidir, o B) escribir de una vez un plan con la condicion adentro para que "
     "otro lo ejecute? Donde te equivocas mas en cada caso?"),
    ("o3", "Te doy una libreta con los productos que se mostraron en la charla. En que situaciones te cuesta saber "
     "a cual se refiere 'ese' o 'el otro'? Que formato de libreta te ayudaria?"),
    ("o4", "Que tipo de cuentas con plata te conviene NO hacer vos y dejarle a una herramienta? Se concreto."),
    ("o5", "Si las instrucciones del sistema son largas, que partes tendes a olvidar primero? Como conviene "
     "ordenarlas?"),
]


# ══ LA CORRIDA ══════════════════════════════════════════════════════════════

def _cliente():
    from openai import OpenAI
    from app.config import get_settings
    # La gratis por defecto. La paga SOLO con BANCO_CLAVE_PAGA=true, la misma
    # llave que usa el resto del banco: Martin la pidio el 26-sep para no
    # esperar dos horas por corrida.
    paga = os.environ.get("BANCO_CLAVE_PAGA", "").lower() == "true"
    clave = os.environ["GEMINI_API_KEY_PROD" if paga else "GEMINI_API_KEY"]
    return OpenAI(api_key=clave, base_url=get_settings().GEMINI_BASE_URL), \
        get_settings().GEMINI_MODEL + (" (paga)" if paga else "")


class SinCuota(Exception):
    pass


def _llamar(cli, modelo, msgs, temp, tools=None, pausa=4):
    time.sleep(pausa)
    espera = 20
    for _ in range(6):
        try:
            kw = {"tools": tools, "tool_choice": "auto"} if tools else {}
            return cli.chat.completions.create(model=modelo, messages=msgs, temperature=temp, **kw)
        except Exception as e:  # noqa: BLE001 — la gratis devuelve 429/503: se aguanta
            s = str(e)
            if any(c in s for c in ("429", "503", "500", "RESOURCE_EXHAUSTED", "overloaded")):
                if "per day" in s.lower() or "PerDay" in s:
                    raise SinCuota(s[:300]) from e
                time.sleep(espera)
                espera = min(espera * 2, 160)
                continue
            raise
    raise SinCuota("seis reintentos sin respuesta")


def _json_simple(cli, modelo, sistema, usuario, temp, pausa):
    r = _llamar(cli, modelo, [{"role": "system", "content": sistema},
                              {"role": "user", "content": usuario}], temp, pausa=pausa)
    texto = r.choices[0].message.content or ""
    return texto, (r.usage.total_tokens if r.usage else 0)


def _con_herramientas(cli, modelo, tienda, mensaje, temp, pausa, tools=TOOLS, vueltas=5, solo_primera=False,
                      sistema=S_VENDEDOR):
    msgs = [{"role": "system", "content": sistema}, {"role": "user", "content": mensaje}]
    llamadas, tok, texto = [], 0, ""
    for v in range(1, vueltas + 1):
        r = _llamar(cli, modelo, msgs, temp, tools=tools, pausa=pausa)
        tok += r.usage.total_tokens if r.usage else 0
        m = r.choices[0].message
        texto = m.content or ""
        if not m.tool_calls:
            break
        msgs.append({"role": "assistant", "content": texto,
                     "tool_calls": [c.model_dump() for c in m.tool_calls]})
        for c in m.tool_calls:
            try:
                args = json.loads(c.function.arguments or "{}")
            except ValueError:
                args = {}
            llamadas.append((v, c.function.name, args))
            f = getattr(tienda, c.function.name, None) if tienda else None
            out = f(**args) if f else {"veredicto": "no disponible"}
            msgs.append({"role": "tool", "tool_call_id": c.id, "content": json.dumps(out, ensure_ascii=False)})
        if solo_primera:
            break
    return llamadas, texto, tok


def pruebas():
    """Cada prueba: (familia, id, nivel, correr(cli, modelo, temp, pausa) -> (ok, detalle, salida, tok))."""
    out = []

    def j(fam, cid, nivel, sistema, usuario, nota, caso):
        def correr(cli, modelo, temp, pausa):
            texto, tok = _json_simple(cli, modelo, sistema, usuario, temp, pausa)
            obj = _json(texto)
            ok, det = nota(caso, obj) if obj is not None else (False, "json roto")
            return ok, det, texto, tok, (obj or {}).get("confianza")
        out.append((fam, cid, nivel, correr))

    def h(fam, cid, nivel, tienda, msg, nota, caso, **kw):
        def correr(cli, modelo, temp, pausa):
            ll, texto, tok = _con_herramientas(cli, modelo, tienda, msg, temp, pausa, **kw)
            ok, det = nota(caso, ll, texto)
            salida = {"llamadas": [f"{v}:{n}{json.dumps(a, ensure_ascii=False)}" for v, n, a in ll], "texto": texto}
            return ok, det, salida, tok, None
        out.append((fam, cid, nivel, correr))

    for c in PARTIR:
        j("P1", c[0], c[1], S_PARTIR, c[2], nota_partir, c)
    for n_tools, tools in ((7, TOOLS), (20, TOOLS + DISTRACTORAS)):
        for c in ELEGIR:
            h("P2", f"{c[0]}_{n_tools}", n_tools, None, c[1], nota_elegir, c, tools=tools, solo_primera=True)
    for c in DEPENDE:
        h("P3", c[0], c[1], c[3], c[2], nota_depende, c)
    for c in REFERENCIA:
        j("P4", c[0], c[1], S_REF, f"LIBRETA:\n{c[2]}\n\nMENSAJE: {c[3]}", nota_ref, c)
    for c in CORRECCION:
        j("P5", c[0], c[1], S_CORR, f"VIGENTES: {json.dumps(c[2])}\nMENSAJE: {c[3]}", nota_corr, c)
    for c in CORRECCION_B:
        j("P5", c[0], "campo_renombrado", S_CORR_B, f"VIGENTES: {json.dumps(c[2])}\nMENSAJE: {c[3]}", nota_corr, c)
    for c in NO_INVENTAR:
        if c[0] == "n1c":  # la misma ficha que n1, con la regla al final y mas dura
            h("P6", c[0], "regla_dura", c[2], c[1], nota_no_inventar, c, sistema=S_VENDEDOR + REGLA_DURA)
        else:
            h("P6", c[0], "ficha_marca" if c[0] == "n1b" else 1, c[2], c[1], nota_no_inventar, c)
    for c in CUENTAS:
        j("P7", c[0], c[1], S_CUENTA, c[2], nota_cuenta, c)
    for c in CONTEXTO:
        j("P8", c[0], c[1], S_LISTA, f"LISTA:\n{c[2]}\n\nPREGUNTA: {c[3]}", nota_lista, c)
    for c in PLAN:
        j("D9", c[0], "plan", S_PLAN, c[1], nota_plan, c)
    for c in FALTA:
        j("D9", c[0], "falta", S_FALTA, f"LO QUE SABES: {c[1]}\nMENSAJE: {c[2]}", nota_falta, c)
    for cid, preg in OPINION:
        def correr(cli, modelo, temp, pausa, preg=preg):
            texto, tok = _json_simple(cli, modelo, S_OPINION, preg, temp, pausa)
            return None, "", texto, tok, None
        out.append(("D9", cid, "opinion", correr))
    return out


def _hechas(etiqueta):
    hechas = {}
    if os.path.exists(CORRIDAS):
        for linea in open(CORRIDAS, encoding="utf-8"):
            r = json.loads(linea)
            if r.get("etiqueta") == etiqueta:
                hechas[(r["id"], r["rep"])] = r
    return hechas


def _recalificar(r):
    """P3 y los planes se recalifican desde lo guardado: la nota puede afinarse sin volver a llamar al modelo."""
    if r["familia"] == "D9" and r["nivel"] == "plan":
        caso = next(c for c in PLAN if c[0] == r["id"])
        obj = _json(r["salida"])
        r["ok"], r["detalle"] = nota_plan(caso, obj) if obj is not None else (False, "json roto")
        return r
    if r["familia"] != "P3":
        return r
    caso = next(c for c in DEPENDE if c[0] == r["id"])
    ll = []
    for x in r["salida"]["llamadas"]:
        v, resto = x.split(":", 1)
        nombre = resto.split("{", 1)[0]
        ll.append((int(v), nombre, json.loads(resto[len(nombre):] or "{}")))
    r["ok"], r["detalle"] = nota_depende(caso, ll, r["salida"]["texto"])
    return r


def informe(etiqueta):
    filas = [_recalificar(r) for r in _hechas(etiqueta).values()]
    if not filas:
        print("no hay corridas con la etiqueta", etiqueta)
        return
    por = {}
    for r in filas:
        por.setdefault((r["familia"], str(r["nivel"])), {}).setdefault(r["id"], []).append(r)
    print(f"\nSONDA · etiqueta {etiqueta} · {len(filas)} respuestas\n")
    print("familia nivel   aciertos  siempre/a veces/nunca   falla mas repetida")
    for (fam, nivel), casos in sorted(por.items()):
        if fam == "D9" and nivel == "opinion":
            continue
        tot = sum(len(v) for v in casos.values())
        ok = sum(bool(r["ok"]) for v in casos.values() for r in v)
        clase = [sum(bool(r["ok"]) for r in v) / len(v) for v in casos.values()]
        s, a, n = sum(c == 1 for c in clase), sum(0 < c < 1 for c in clase), sum(c == 0 for c in clase)
        dets = [r["detalle"] for v in casos.values() for r in v if not r["ok"] and r["detalle"]]
        comun = max(set(dets), key=dets.count) if dets else ""
        print(f"{fam:7} {nivel:6} {ok:4}/{tot:<4}  {s:3} / {a:3} / {n:3}          {comun[:60]}")
    print("\npor caso (aciertos/repeticiones):")
    for (fam, nivel), casos in sorted(por.items()):
        if nivel == "opinion":
            continue
        print(f"  {fam} {nivel}: " + "  ".join(
            f"{cid} {sum(bool(r['ok']) for r in v)}/{len(v)}" for cid, v in sorted(casos.items())))
    notas_ok = [r["detalle"] for r in filas if r["ok"] and r["detalle"]]
    if notas_ok:
        print("\naciertos con nota: " + "; ".join(f"{d} x{notas_ok.count(d)}" for d in sorted(set(notas_ok))))
    conf = [(r["confianza"], bool(r["ok"])) for r in filas if isinstance(r.get("confianza"), (int, float))]
    if conf:
        alta = [ok for c, ok in conf if c >= 90]
        baja = [ok for c, ok in conf if c < 90]
        print(f"\ncalibracion P4: confianza >=90 acierta {sum(alta)}/{len(alta)}; "
              f"<90 acierta {sum(baja)}/{len(baja)}")
    tok = sum(r["tokens"] for r in filas)
    print(f"tokens totales {tok}, promedio {tok // len(filas)} por prueba")


def main():
    a = sys.argv[1:]

    def opt(nombre, defecto, tipo):
        if nombre in a:
            i = a.index(nombre)
            v = tipo(a[i + 1])
            del a[i:i + 2]
            return v
        return defecto
    reps, pausa = opt("--reps", 5, int), opt("--pausa", 4.0, float)
    temp, etiqueta = opt("--temp", 0.2, float), opt("--etiqueta", "base", str)
    hilos = opt("--hilos", 1, int)
    if "--informe" in a:
        informe(etiqueta)
        return
    familias = {x for x in a if not x.startswith("-")}
    cli, modelo = _cliente()
    nombre_modelo = modelo.replace(" (paga)", "")
    hechas = _hechas(etiqueta)
    todas = [p for p in pruebas() if not familias or p[0] in familias]
    # rep por fuera: si se corta, todo queda con la misma cantidad de repeticiones
    cola = [(rep, p) for rep in range(1, reps + 1) for p in todas
            if rep <= (1 if p[2] == "opinion" else reps) and (p[1], rep) not in hechas]
    print(f"{modelo} · {len(cola)} por correr · temp {temp} · pausa {pausa}s · hilos {hilos} · etiqueta {etiqueta}")
    candado = threading.Lock()

    def uno(tarea):
        rep, (fam, cid, nivel, correr) = tarea
        t0 = time.time()
        ok, det, salida, tok, conf = correr(cli, nombre_modelo, temp, pausa)
        fila = {"etiqueta": etiqueta, "modelo": modelo, "temp": temp, "familia": fam, "id": cid,
                "nivel": nivel, "rep": rep, "ok": ok, "detalle": det, "confianza": conf,
                "tokens": tok, "seg": round(time.time() - t0 - pausa, 1), "salida": salida}
        with candado:
            with open(CORRIDAS, "a", encoding="utf-8") as f:
                f.write(json.dumps(fila, ensure_ascii=False) + "\n")
            marca = "   " if ok is None else ("OK " if ok else "MAL")
            print(f"{marca} r{rep} {fam} {cid:8} {det[:90]}", flush=True)

    try:
        with ThreadPoolExecutor(hilos) as ex:
            for fut in [ex.submit(uno, t) for t in cola]:
                fut.result()
    except SinCuota as e:
        print(f"\nCUOTA: se corta aca y se sigue con el mismo comando. {e}")
    informe(etiqueta)


if __name__ == "__main__":
    main()
