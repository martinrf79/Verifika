"""EL CODIGO CON LA TRADUCCION PERFECTA, SOBRE CHARLAS SINTETICAS NUEVAS — 12-nov-2026, pedido de Martin.

Pregunta: si la primera traduccion sale bien, ¿el codigo contesta bien cualquier charla, o solo las 138 grabadas?

Arma charlas al azar con productos, rubros, destinos, temas y referencias reales de la tienda, mezclando lo que hay en las
58, las J y las K: preguntar, buscar con condiciones y orden, llevar, sacar, cambiar, cotizar, pagar partido, tope y
memoria de varios turnos. Cada turno lleva la agenda que daria una traduccion perfecta y un texto que la dice.

La vara NO usa el codigo del bot: sale de `productos.csv`, `faq.json` y la tabla de tarifas de la tienda, y lleva su
propio pedido turno por turno. Controla precios, nombres, condiciones, orden, renglones, envios, subtotales, totales,
descuento, tope y que no haya errores ni pedazos sin resolver.

  python3 banco_pruebas/fragil_fijo.py                 300 charlas, semilla 1
  python3 banco_pruebas/fragil_fijo.py --n 500 --semilla 7
  python3 banco_pruebas/fragil_fijo.py --ver 5         muestra las 5 primeras fallas enteras
"""
import collections
import csv
import json
import os
import random
import re
import sys
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
sys.path[:0] = [REPO]
os.chdir(REPO)
TIENDA_DIR = os.path.join(REPO, "data", "clientes", "verifika_prod")


def n(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def plata(x):
    return "$" + f"{int(round(x)):,}".replace(",", ".")


# ── LA FUENTE, LEIDA SIN EL CODIGO DEL BOT ─────────────────────────────────────
FILAS = list(csv.DictReader(open(os.path.join(TIENDA_DIR, "productos.csv"), encoding="utf-8")))
for f in FILAS:
    f["precio"], f["stk"] = int(f["precio_ars"]), int(f["stock"] or 0)
POR_NOMBRE = {n(f["nombre"]): f for f in FILAS}
FAQ = {f["tema"]: f for f in json.load(open(os.path.join(TIENDA_DIR, "faq.json"), encoding="utf-8"))}
RUBROS = sorted({f["categoria"] for f in FILAS})
VARIANTES = collections.defaultdict(list)  # (marca, modelo) -> filas por color
for f in FILAS:
    VARIANTES[(f["marca"], f["modelo"])].append(f)

SPECS = {(r["marca"], r["modelo"]): r for r in csv.DictReader(open(os.path.join(TIENDA_DIR, "specs_por_modelo.csv"),
                                                                     encoding="utf-8"))}


def spec(f, campo):
    return n((SPECS.get((f["marca"], f["modelo"])) or {}).get(campo) or "")


# Condicion de ficha: (rubros, frases del cliente, la verdad segun specs_por_modelo; None si la ficha no lo dice)
FICHA = [
    (("mouse", "teclado", "auriculares"), ["inalambrico", "sin cable", "wireless", "que no tenga cable"],
     lambda f: None if not spec(f, "conexion") else ("inalambric" in spec(f, "conexion") or "bluetooth" in spec(f, "conexion"))),
    (("mouse", "teclado", "auriculares"), ["con cable", "cableado"],
     lambda f: None if not spec(f, "conexion") else ("cable" in spec(f, "conexion") and "inalambric" not in spec(f, "conexion"))),
    (("teclado",), ["mecanico", "de switches mecanicos"],
     lambda f: None if not spec(f, "switch_teclado") else "mecanico" in spec(f, "switch_teclado")),
    (("mouse", "teclado"), ["con luces RGB", "con retroiluminacion", "que tenga luces"],
     lambda f: None if not spec(f, "retroiluminacion") else spec(f, "retroiluminacion").startswith("si")),
]

CIUDADES = {"Rosario": "santa fe", "Cordoba": "cordoba", "Rio Cuarto": "cordoba", "Villa Maria": "cordoba",
            "Concordia": "entre rios", "Parana": "entre rios", "Posadas": "misiones", "Mendoza": "mendoza",
            "Salta": "salta", "Neuquen": "neuquen", "Bariloche": "rio negro", "Ushuaia": "tierra del fuego",
            "Corrientes": "corrientes", "Resistencia": "chaco", "Mar del Plata": "buenos_aires",
            "Comodoro Rivadavia": "chubut", "Rio Gallegos": "santa cruz", "San Juan": "san juan",
            "Bahia Blanca": "buenos_aires", "Tandil": "buenos_aires", "CABA": None}
UMBRAL_GRATIS = 250000
DESCUENTO_TRANSF = 10


def tarifa(ciudad, tabla):
    prov = CIUDADES[ciudad]
    return 3000 if prov is None else int(tabla[prov])


# ── EL ORACULO DEL ESTADO: el pedido y lo ultimo mostrado, llevados aparte ─────
class Charla:
    def __init__(self, rng):
        self.rng = rng
        self.pedido = []        # [{"fila", "cant", "destino"}]
        self.mostrado = []      # filas, en el orden en que se mostraron
        self.turnos = []        # [{"texto", "agenda", "esperas"}]


def frase_producto(rng, fila, con_color):
    modelo = fila["modelo"]
    dicho = rng.choice([modelo, f"{fila['marca']} {modelo}", modelo.lower()])
    return dicho, (fila["color"].lower() if con_color else None)


def es_ambiguo(dicho):
    """Cuantos productos distintos, sin contar el color, nombra lo que dijo el cliente."""
    d = n(dicho).split()
    hits = {k for k, fs in VARIANTES.items() if all(t in n(f"{k[0]} {k[1]} {fs[0]['nombre']}").split() for t in d)}
    return len(hits)


def con_stock(fs):
    return [f for f in fs if f["stk"] > 0]


def producto_al_azar(rng, solo_stock=True):
    while True:
        fs = rng.choice(list(VARIANTES.values()))
        cands = con_stock(fs) if solo_stock else fs
        if cands:
            return rng.choice(cands), fs


# ── LAS PIEZAS DE AGENDA, CADA UNA CON SU TEXTO Y SU ESPERA ───────────────────
def p_producto(ch):
    rng = ch.rng
    fila, fs = producto_al_azar(rng, solo_stock=False)
    quiere = rng.choice(["precio", "stock", "garantia"])
    con_color = len(fs) > 1 and rng.random() < 0.7
    dicho, color = frase_producto(rng, fila, con_color)
    texto = {"precio": f"cuanto sale el {dicho}" + (f" {color}" if color else ""),
             "stock": f"tenes el {dicho}" + (f" {color}" if color else "") + " en stock",
             "garantia": f"que garantia tiene el {dicho}"}[quiere]
    p = {"accion": "producto", "producto": dicho, "quiere_saber": quiere}
    if color:
        p["color"] = color
    return texto, p, {"tipo": "producto", "fila": fila, "variantes": fs, "quiere": quiere, "dicho": dicho,
                      "con_color": bool(color)}


CONDS = {
    "marca": lambda m: (rng_choice(["de {m}", "marca {m}", "que sea {m}"]).format(m=m), lambda f: f["marca"] == m),
    "no_marca": lambda m: (rng_choice(["que no sea {m}", "nada de {m}", "sin {m}"]).format(m=m),
                           lambda f: f["marca"] != m),
    "tope": lambda t: (rng_choice(["de menos de {k} mil", "que no pase los {k} mil", "por debajo de {k} lucas"])
                       .format(k=t // 1000), lambda f: f["precio"] < t),
}
_RNG = random.Random(0)


def rng_choice(xs):
    return _RNG.choice(xs)


ORDENES = {"mas barato": ["el mas barato", "lo mas barato", "los mas baratos", "el mas economico"],
           "mas caro": ["el mas caro", "lo mas caro", "los mas caros"]}


def p_buscar(ch, rubro=None, orden=None, cantidad=None, sin_cond=False):
    rng = ch.rng
    rubro = rubro or rng.choice(RUBROS)
    filas = con_stock([f for f in FILAS if f["categoria"] == rubro])
    marcas = sorted({f["marca"] for f in filas})
    conds, filtros, partes = [], [], []
    fichas = [x for x in FICHA if rubro in x[0]]
    if not sin_cond and fichas and rng.random() < 0.5:
        _r, frases, verdad = rng.choice(fichas)
        frase = rng.choice(frases)
        conds.append(frase), partes.append(frase)
        filtros.append(lambda f, v=verdad: v(f) is True)
    elif not sin_cond and rng.random() < 0.6 and len(marcas) > 1:
        tipo = rng.choice(["marca", "no_marca", "tope"])
        if tipo == "tope":
            precios = sorted(f["precio"] for f in filas)
            t = ((precios[len(precios) // 2] // 10000) + 1) * 10000
            frase, filtro = CONDS["tope"](t)
        else:
            frase, filtro = CONDS[tipo](rng.choice(marcas))
        conds.append(frase), filtros.append(filtro), partes.append(frase)
    if orden is None:
        orden = rng.choice(["nada", "nada", "mas barato", "mas caro"])
    if cantidad is None:
        cantidad = rng.choice([1, 1, 2, 3]) if orden != "nada" else 1
    dicho_orden = rng.choice(ORDENES[orden]) if orden != "nada" else ""
    plural = rubro if rubro.endswith("s") else rubro + ("es" if rubro[-1] in "rl" else "s")
    if cantidad > 1:
        texto = f"pasame los {cantidad} {plural} {dicho_orden.replace('el ', 'mas ').replace('lo ', '').replace('los ', '')}"
        texto = f"pasame {cantidad} {plural}, {dicho_orden}"
    elif orden != "nada":
        texto = f"cual es {dicho_orden} en {rubro}"
    else:
        texto = rng.choice([f"que {plural} tenes", f"tenes {plural}", f"mostrame {plural}"])
    if partes:
        texto += " " + " ".join(partes)
    p = {"accion": "buscar", "rubro": rubro, "cantidad": cantidad, "orden": orden, "condiciones": conds}
    ok = [f for f in filas if all(fl(f) for fl in filtros)]
    return texto, p, {"tipo": "buscar", "rubro": rubro, "orden": orden, "cantidad": cantidad, "validas": ok,
                      "conds": conds}


def p_envio(ch):
    c = ch.rng.choice(list(CIUDADES))
    return (ch.rng.choice([f"cuanto sale el envio a {c}", f"cuanto me cobras mandarlo a {c}", f"envias a {c}?"]),
            {"accion": "envio", "destino": c}, {"tipo": "envio", "ciudad": c})


TEMAS = {"cuotas": ["en cuantas cuotas puedo pagar", "tienen cuotas sin interes?"],
         "descuento_transferencia": ["si pago por transferencia me hacen descuento?", "hay descuento por transferencia"],
         "plazo_envio": ["cuanto tarda en llegar", "en cuantos dias llega"],
         "factura": ["hacen factura A?", "me das factura"],
         "garantia": ["que garantia tienen los productos", "tienen garantia?"],
         "formas_pago": ["como puedo pagar", "que medios de pago aceptan"],
         "devoluciones": ["si no me gusta lo puedo devolver?"],
         "retiro_local": ["puedo retirar en el local?"]}


def p_politica(ch):
    tema = ch.rng.choice(list(TEMAS))
    return ch.rng.choice(TEMAS[tema]), {"accion": "politica", "tema": tema}, {"tipo": "politica", "tema": tema}


def p_llevar(ch, k=None, destinos=None):
    """Agrega de 1 a 3 productos con stock, cada uno con color si tiene varios, y destino si se pide."""
    rng = ch.rng
    k = k or rng.choice([1, 1, 2, 3])
    agrega, textos, lineas = [], [], []
    usados = set()
    for _ in range(k):
        while True:
            fila, fs = producto_al_azar(rng)
            if (fila["marca"], fila["modelo"]) not in usados and es_ambiguo(fila["modelo"]) == 1:
                break
        usados.add((fila["marca"], fila["modelo"]))
        cant = rng.choice([1, 1, 1, 2, 3])
        cant = min(cant, fila["stk"])
        dicho = rng.choice([fila["modelo"], f"{fila['marca']} {fila['modelo']}"])
        color = fila["color"].lower() if len(fs) > 1 else None
        destino = rng.choice(destinos) if destinos else None
        a = {"producto": dicho, "cantidad": cant}
        if color:
            a["color"] = color
        if destino:
            a["destino"] = destino
        agrega.append(a)
        textos.append(f"{'un' if cant == 1 else cant} {dicho}" + (f" {color}" if color else "")
                      + (f" a {destino}" if destino else ""))
        lineas.append({"fila": fila, "cant": cant, "destino": destino})
    texto = rng.choice(["sumame ", "quiero ", "anotame ", "dame "]) + ", ".join(textos[:-1]) \
        + (" y " if len(textos) > 1 else "") + textos[-1]
    return texto, {"accion": "comprar", "agrega": agrega}, {"tipo": "llevar", "lineas": lineas}


def p_cuenta(ch, reparto=False, tope=None):
    p = {"accion": "cuenta"}
    texto = ch.rng.choice(["cuanto es todo", "pasame el total", "cuanto me sale todo junto"])
    if reparto:
        tr = ch.rng.choice([50, 60, 70, 100])
        p["reparto"] = [{"medio": "transferencia", "porcentaje": tr}] + (
            [{"medio": "Mercado Pago", "porcentaje": 100 - tr}] if tr < 100 else [])
        texto += f", pago {tr} por ciento por transferencia" + (" y el resto con Mercado Pago" if tr < 100 else "")
    if tope:
        p["tope"] = tope
        texto += f", tengo {tope // 1000} mil, me alcanza?"
    return texto, p, {"tipo": "cuenta", "reparto": p.get("reparto"), "tope": tope}


AFIRMA = [("costo_envio", "envio gratis a todo el pais", "me dijeron que el envio es gratis a todo el pais", "250000",
           ["envio gratis a todo el pais", "si, el envio es gratis"]),
          ("cuotas", "18 cuotas sin interes", "es cierto que tienen 18 cuotas sin interes?", "6", ["18 cuotas sin interes"]),
          ("descuento_transferencia", "30 por ciento por transferencia", "por transferencia me hacen 30% no?", "10",
           ["30%", "30 por ciento"])]


def p_afirma(ch):
    tema, afirma, texto, real, prohibidas = ch.rng.choice(AFIRMA)
    return texto, {"accion": "politica", "tema": tema, "afirma": afirma}, {"tipo": "afirma", "real": real,
                                                                           "prohibidas": prohibidas, "tema": tema}


def p_llevar_raro(ch, que):
    """Llevar sin decir el color de uno que tiene varios con stock, o uno que no tiene stock en ese color."""
    rng = ch.rng
    while True:
        fs = rng.choice(list(VARIANTES.values()))
        if es_ambiguo(fs[0]["modelo"]) != 1:
            continue
        if que == "sin_color" and len(con_stock(fs)) > 1:
            fila, color = None, None
            break
        if que == "sin_stock" and len(fs) > 1 and any(f["stk"] == 0 for f in fs):
            fila = next(f for f in fs if f["stk"] == 0)
            color = fila["color"].lower()
            break
    dicho = fs[0]["modelo"]
    a = {"producto": dicho, "cantidad": 1}
    if color:
        a["color"] = color
    return (f"dame un {dicho}" + (f" {color}" if color else ""), {"accion": "comprar", "agrega": [a]},
            {"tipo": que, "variantes": fs, "fila": fila})


# ── LOS GUIONES: de uno a cinco turnos, mezclados ──────────────────────────────
def turno(ch, piezas):
    textos, ps, esperas = [], [], []
    for t, p, e in piezas:
        textos.append(t), ps.append(p), esperas.append(e)
    texto = ". ".join(textos)
    ch.turnos.append({"texto": texto, "agenda": {"preguntas": [{"n": i, **p} for i, p in enumerate(ps, 1)]},
                      "esperas": esperas})


def guion(ch):
    rng = ch.rng
    tipo = rng.choice(["suelto", "suelto", "mixto", "buscar_y_llevar", "llevar_y_tocar", "llevar_y_tocar",
                       "baratos_por_rubro", "memoria_larga", "sin_color", "sin_stock", "afirma", "cierre"])
    ch.tipo = tipo
    if os.environ.get("SOLO_FICHA"):
        ch.tipo = "ficha"
        rubro = rng.choice(["mouse", "teclado", "auriculares"])
        _r, frases, verdad = rng.choice([x for x in FICHA if rubro in x[0]])
        t, p, e = p_buscar(ch, rubro=rubro, sin_cond=True, orden=rng.choice(["nada", "mas barato"]))
        frase = rng.choice(frases)
        p["condiciones"] = [frase]
        e["conds"] = [frase]
        e["validas"] = [f for f in e["validas"] if verdad(f) is True]
        e["sin_dato"] = [f["nombre"] for f in FILAS if f["categoria"] == rubro and verdad(f) is None]
        turno(ch, [(t + " " + frase, p, e)])
        return
    if tipo == "suelto":
        turno(ch, [rng.choice([p_producto, p_buscar, p_envio, p_politica])(ch)])
    elif tipo == "mixto":
        piezas = [f(ch) for f in rng.sample([p_producto, p_buscar, p_envio, p_politica], rng.choice([2, 3]))]
        turno(ch, piezas)
    elif tipo == "buscar_y_llevar":
        t, p, e = p_buscar(ch, orden="nada", cantidad=1, sin_cond=rng.random() < 0.5)
        turno(ch, [(t, p, e)])
        ch.turnos[-1]["despues"] = "elegir"
    elif tipo == "llevar_y_tocar":
        dest = rng.sample(list(CIUDADES), rng.choice([0, 1, 1, 2]))
        turno(ch, [p_llevar(ch, k=rng.choice([2, 3]), destinos=dest or None), p_cuenta(ch)])
        accion = rng.choice(["saca", "cantidad", "destino", "pago", "tope", "suma"])
        ch.turnos[-1]["despues"] = accion
    elif tipo == "baratos_por_rubro":
        rubros = rng.sample(["mouse", "teclado", "auriculares", "memoria ram", "parlante", "webcam", "microfono"], 2)
        dest = rng.choice(list(CIUDADES))
        piezas = [p_buscar(ch, rubro=r, orden="mas barato", cantidad=1, sin_cond=True) for r in rubros]
        texto = f"pasame el mas barato de {rubros[0]} y de {rubros[1]}, sumalos con envio a {dest} y decime el total"
        agrega = [{"producto": r, "destino": dest} for r in rubros]
        ps = [p for _, p, _ in piezas] + [{"accion": "comprar", "agrega": agrega}, {"accion": "cuenta"}]
        esperas = [e for _, _, e in piezas] + [{"tipo": "llevar_rubros", "rubros": rubros, "destino": dest},
                                                {"tipo": "cuenta", "reparto": None, "tope": None}]
        ch.turnos.append({"texto": texto, "agenda": {"preguntas": [{"n": i, **p} for i, p in enumerate(ps, 1)]},
                          "esperas": esperas})
    elif tipo in ("sin_color", "sin_stock"):
        turno(ch, [p_llevar_raro(ch, tipo), p_cuenta(ch)])
    elif tipo == "afirma":
        turno(ch, [p_afirma(ch)] + ([p_producto(ch)] if rng.random() < 0.5 else []))
    elif tipo == "cierre":
        turno(ch, [p_llevar(ch, k=rng.choice([1, 2]), destinos=[rng.choice(list(CIUDADES))]), p_cuenta(ch)])
        ch.turnos[-1]["despues"] = "nombre"
    elif tipo == "memoria_larga":
        turno(ch, [p_producto(ch)])
        turno(ch, [p_politica(ch)])
        dest = [rng.choice(list(CIUDADES))]
        turno(ch, [p_llevar(ch, k=2, destinos=dest), p_cuenta(ch)])
        turno(ch, [p_envio(ch)])
        ch.turnos[-1]["despues"] = rng.choice(["saca", "cantidad", "pago"])


# ── EL TURNO QUE DEPENDE DE LO QUE PASO: se arma con lo que el oraculo lleva ──
def turno_siguiente(ch, accion):
    rng = ch.rng
    if accion == "elegir":
        k = rng.randint(1, max(1, min(len(ch.mostrado), 4)))
        dest = rng.choice(list(CIUDADES))
        fila = ch.mostrado[k - 1]
        cant = 1
        ps = [{"accion": "comprar", "agrega": [{"producto": f"M-{k}", "cantidad": cant, "destino": dest}]},
              {"accion": "cuenta"}]
        texto = rng.choice([f"me llevo el {['primero', 'segundo', 'tercero', 'cuarto'][k - 1]}, mandalo a {dest}, cuanto es",
                            f"dame el numero {k} con envio a {dest} y pasame el total"])
        esperas = [{"tipo": "llevar", "lineas": [{"fila": fila, "cant": cant, "destino": dest}]},
                   {"tipo": "cuenta", "reparto": None, "tope": None}]
        ch.turnos.append({"texto": texto, "agenda": {"preguntas": [{"n": i, **p} for i, p in enumerate(ps, 1)]},
                          "esperas": esperas})
        return
    if accion == "nombre":
        nombre = rng.choice(["Julio", "Carla", "Martina Lopez", "Pedro", "Sofia"])
        ch.turnos.append({"texto": rng.choice([f"soy {nombre}", f"a nombre de {nombre}", nombre]),
                          "agenda": {"preguntas": [{"n": 1, "accion": "otro", "que": "dato"}], "cliente": {"nombre": nombre}},
                          "esperas": [{"tipo": "nombre", "nombre": nombre}]})
        return
    L = rng.randint(1, len(ch.pedido))
    nombre = ch.pedido[L - 1]["fila"]["modelo"]
    if accion == "saca":
        texto, p, e = f"sacame el {nombre}", {"accion": "comprar", "saca": [f"L-{L}"]}, {"tipo": "saca", "L": L}
    elif accion == "cantidad":
        c = rng.choice([2, 3, 4])
        texto, p, e = (f"del {nombre} poneme {c}", {"accion": "comprar", "cambia": [{"es": f"L-{L}", "cantidad": c}]},
                       {"tipo": "cambia", "L": L, "cantidad": c})
    elif accion == "destino":
        d = rng.choice(list(CIUDADES))
        texto, p, e = (f"el {nombre} mandalo a {d}", {"accion": "comprar", "cambia": [{"es": f"L-{L}", "destino": d}]},
                       {"tipo": "cambia", "L": L, "destino": d})
    elif accion == "suma":
        texto, p, e = p_llevar(ch, k=1, destinos=None)
    else:
        texto, p, e = None, None, None
    piezas = ([(texto, p, e)] if p else [])
    if accion == "pago":
        piezas.append(p_cuenta(ch, reparto=True))
    elif accion == "tope":
        total = sum(l["fila"]["precio"] * l["cant"] for l in ch.pedido)
        piezas.append(p_cuenta(ch, tope=int(total * rng.choice([0.7, 1.3])) // 1000 * 1000))
    else:
        piezas.append(p_cuenta(ch))
    turno(ch, piezas)


# ── LA LECTURA DE LA RESPUESTA ─────────────────────────────────────────────────
RE_LISTA = re.compile(r"^- (?!\d+x )(.+?): \$([\d.]+)", re.M)
RE_SUELTO = re.compile(r"^(?!- )(.+?): \$([\d.]+), (hay stock|sin stock|no hay stock|no tengo stock|.*?)", re.M)
RE_RENGLON = re.compile(r"^- (\d+)x (.+?): \$([\d.]+) c/u = \$([\d.]+)", re.M)
num = lambda s: int(s.replace(".", ""))  # noqa: E731


def bloques(resp):
    out = []
    for parte in resp.split("Presupuesto:")[1:]:
        b = {"renglones": [(int(c), n(nm), num(p), num(t)) for c, nm, p, t in RE_RENGLON.findall(parte)]}
        m = re.search(r"Subtotal: \$([\d.]+)", parte)
        b["subtotal"] = num(m.group(1)) if m else None
        m = re.search(r"Env[ií]o a (.+?): (\$[\d.]+|gratis|GRATIS|sin cargo)", parte)
        b["envio"] = (m.group(1), num(m.group(2)[1:]) if m.group(2).startswith("$") else 0) if m else None
        m = re.search(r"^Total: \$([\d.]+)", parte, re.M)
        b["total"] = num(m.group(1)) if m else None
        out.append(b)
    return out


def bloques_renglones(resp):
    return [(int(c), n(nm), num(p), num(t)) for c, nm, p, t in RE_RENGLON.findall(resp)]


def mostrados(resp):
    """Lo que la respuesta muestra, en orden, como lo numeraria la libreta."""
    filas = []
    for nm, _ in RE_LISTA.findall(resp):
        f = POR_NOMBRE.get(n(nm))
        if f:
            filas.append(f)
    for linea in resp.splitlines():
        m = re.match(r"^([^-].+?): \$[\d.]+, ", linea)
        if m and POR_NOMBRE.get(n(m.group(1))):
            filas.append(POR_NOMBRE[n(m.group(1))])
    return filas


# ── LA VARA ────────────────────────────────────────────────────────────────────
def controlar(ch, t, resp, tabla, previa=""):
    malas = []
    r = resp or ""
    if not r.strip():
        return ["vacia"]
    if "ERROR DEL" in r:
        return ["error del codigo: " + r[:160]]
    if "No llegué a resolver" in r:
        malas.append("pedazo sin resolver")
    # Todo precio pegado a un nombre de la tienda es el de la tienda.
    for nm, p in RE_LISTA.findall(r) + [(a, b) for a, b, *_ in RE_SUELTO.findall(r)]:
        f = POR_NOMBRE.get(n(nm))
        if f and f["precio"] != num(p):
            malas.append(f"precio mal: {nm} {p} y la tienda dice {plata(f['precio'])}")
    for c, nm, p, tot in RE_RENGLON.findall(r):
        f = POR_NOMBRE.get(n(nm))
        if not f:
            malas.append(f"renglon con producto que no existe: {nm}")
        elif f["precio"] != num(p) or num(tot) != int(c) * f["precio"]:
            malas.append(f"renglon mal: {c}x {nm} {p} = {tot}")
    lineas = [x for x in r.splitlines() if x.strip() and not x.startswith("- ") and "Presupuesto" not in x]
    rep = [x for x, k in collections.Counter(lineas).items() if k > 1 and len(x) > 25]
    if rep:
        malas.append(f"repite: {rep[0][:60]}")
    pide_algo = "?" in r
    # Lo que el cliente ya dijo no se vuelve a preguntar: el color que dio.
    for e in t["esperas"]:
        for l in e.get("lineas") or []:
            if len(l["fila"].get("_variantes", VARIANTES[(l["fila"]["marca"], l["fila"]["modelo"])])) > 1:
                m = re.search(rf"reservarte el {re.escape(l['fila']['modelo'])}, ¿en qué color", r)
                if m:
                    malas.append(f"color: pregunta el color de {l['fila']['nombre']} y el cliente dijo {l['fila']['color']}")
    # Lo que no pidio en este turno no se pega: una ficha suelta que ya se dio y que este turno no pregunta.
    pedidos = {n(e["fila"]["nombre"]) for e in t["esperas"] if e["tipo"] == "producto"} | \
              {n(f["nombre"]) for e in t["esperas"] if e["tipo"] == "producto" for f in e["variantes"]}
    for linea in r.splitlines():
        m = re.match(r"^([^-].+?): \$[\d.]+, ", linea)
        if m and n(m.group(1)) not in pedidos and linea in (previa or ""):
            malas.append(f"pega: repite la ficha de {m.group(1)} que no pidio")
    for e in t["esperas"]:
        tp = e["tipo"]
        if tp == "producto":
            fs = e["variantes"]
            nombres = [f["nombre"] for f in fs]
            if pide_algo and es_ambiguo(e["dicho"]) > 1:
                continue
            if not any(n(x) in n(r) for x in nombres):
                if not (pide_algo and es_ambiguo(e["dicho"]) > 1):
                    malas.append(f"producto: no nombra {e['fila']['nombre']}")
                continue
            if e["quiere"] == "garantia" and e["fila"]["garantia_meses"] not in r and not pide_algo:
                malas.append(f"garantia: falta {e['fila']['garantia_meses']} meses")
            if e["quiere"] == "stock" and e["con_color"]:
                linea = next((x for x in r.splitlines() if n(e["fila"]["nombre"]) in n(x)), "")
                m = re.search(r"\$[\d.]+, ([^,;.]+)", linea)
                dice = n(m.group(1)) if m else ""
                if e["fila"]["stk"] == 0 and dice.startswith("hay stock"):
                    malas.append(f"stock: dice que hay de {e['fila']['nombre']} y la tienda tiene 0")
                if e["fila"]["stk"] > 0 and (dice.startswith("sin stock") or dice.startswith("no hay")):
                    malas.append(f"stock: dice que no hay de {e['fila']['nombre']} y la tienda tiene {e['fila']['stk']}")
        elif tp == "buscar":
            sec = r.split(f"En {e['rubro']} tengo:")
            trozo = re.split(r"\n\n|\nEn [^\n]+ tengo:|\nPresupuesto:", sec[1])[0] if len(sec) > 1 else ""
            listados = [POR_NOMBRE.get(n(nm)) for nm, _ in RE_LISTA.findall(trozo)]
            listados = [f for f in listados if f]
            validas = e["validas"]
            if not validas:
                if listados:
                    malas.append(f"buscar {e['rubro']} {e['conds']}: lista y no hay ninguno que cumpla")
                continue
            if not listados:
                malas.append(f"buscar {e['rubro']} {e['conds']} {e['orden']}: no lista nada y hay {len(validas)}")
                continue
            fuera = [f["nombre"] for f in listados if f not in validas]
            if fuera:
                malas.append(f"buscar {e['rubro']} {e['conds']}: muestra uno que no cumple, {fuera[0]}")
            if e["orden"] != "nada":
                clave = (lambda f: f["precio"]) if e["orden"] == "mas barato" else (lambda f: -f["precio"])

                def por_modelo(fs):
                    m = {}
                    for f in fs:
                        k = (f["marca"], f["modelo"])
                        m[k] = min(m.get(k, clave(f)), clave(f))
                    return sorted(m.values())
                mejores = por_modelo(validas)[:e["cantidad"]]
                dados = por_modelo(listados)[:e["cantidad"]]
                if dados != mejores:
                    malas.append(f"orden {e['orden']} en {e['rubro']} {e['conds']}: da "
                                 f"{[plata(abs(x)) for x in dados]} y lo de la tienda es {[plata(abs(x)) for x in mejores]}")
                if len(listados) < min(e["cantidad"], len(validas)):
                    malas.append(f"cantidad: pidio {e['cantidad']} de {e['rubro']} y muestra {len(listados)}")
        elif tp == "envio":
            m = re.search(rf"Env[ií]o a {re.escape(e['ciudad'])}: \$([\d.]+)", r, re.I)
            gratis = re.search(rf"Env[ií]o a {re.escape(e['ciudad'])}: gratis", r, re.I)
            if gratis and any((b["subtotal"] or 0) > UMBRAL_GRATIS for b in bloques(r)):
                continue
            if not m:
                if not pide_algo:
                    malas.append(f"envio a {e['ciudad']}: no da la tarifa")
            elif num(m.group(1)) != tarifa(e["ciudad"], tabla):
                malas.append(f"envio a {e['ciudad']}: {m.group(1)} y la tabla dice {plata(tarifa(e['ciudad'], tabla))}")
        elif tp == "politica":
            faq = FAQ[e["tema"]]
            for v in faq.get("valores") or []:
                monto = v.get("monto")
                if isinstance(monto, (int, float)) and monto and str(int(monto)) not in r.replace(".", ""):
                    malas.append(f"politica {e['tema']}: falta {v['concepto']} {monto}")
            if len(r.strip()) < 20:
                malas.append(f"politica {e['tema']}: sin respuesta")
        elif tp == "cuenta":
            malas += controlar_cuenta(ch, e, r, tabla)
        elif tp == "afirma":
            if e["real"] not in r.replace(".", ""):
                malas.append(f"afirma {e['tema']}: no da lo real, {e['real']}")
            if any(x in n(r) for x in map(n, e["prohibidas"])) and "no" not in n(r).split():
                malas.append(f"afirma {e['tema']}: confirma lo falso")
            cuerpo = r.split("Verifika Tech.")[-1].strip()
            if re.match(r"^s[ií][,.! ]", cuerpo, re.I):
                malas.append(f"afirma {e['tema']}: arranca con un si a lo falso")
        elif tp == "sin_color":
            colores = {n(f["color"]) for f in con_stock(e["variantes"])}
            if not (pide_algo and any(c in n(r) for c in colores)):
                malas.append("sin_color: no pregunta el color")
            if any(n(f["nombre"]) in nm for f in e["variantes"] for _c, nm, *_ in bloques_renglones(r)):
                malas.append("sin_color: lo suma sin saber el color")
        elif tp == "sin_stock":
            if any(n(e["fila"]["nombre"]) == nm for _c, nm, *_ in bloques_renglones(r)):
                malas.append(f"sin_stock: suma {e['fila']['nombre']} que tiene 0")
            if "stock" not in n(r):
                malas.append("sin_stock: no avisa que no hay")
        elif tp == "nombre":
            if not re.search(rf"listo {n(e['nombre']).split()[0]}", n(r)):
                malas.append("cierre: no toma el pedido con el nombre")
    return malas


def controlar_cuenta(ch, e, r, tabla):
    malas = []
    bs = bloques(r)
    if not ch.pedido:
        return []
    if not bs:
        return [] if "?" in r else ["cuenta: no hay presupuesto"]
    # Lo que tiene que estar: cada renglon del pedido del oraculo, con su cantidad, en el bloque de su destino.
    esperado = collections.Counter((l["fila"]["nombre"], l["destino"]) for l in ch.pedido for _ in range(1))
    cant = collections.defaultdict(int)
    for l in ch.pedido:
        cant[(n(l["fila"]["nombre"]), l["destino"])] += l["cant"]
    dados = collections.defaultdict(int)
    for b in bs:
        dest = b["envio"][0] if b["envio"] else None
        for c, nm, p, tot in b["renglones"]:
            dados[(nm, dest)] += c
    for (nm, dest), c in cant.items():
        hay = dados.get((nm, dest)) or (dados.get((nm, None)) if dest is None else 0)
        if hay != c:
            alla = {d: k for (x, d), k in dados.items() if x == nm}
            malas.append(f"cuenta: {nm} a {dest} va {c} y el presupuesto dice {alla or 'nada'}")
    for (nm, dest), c in dados.items():
        if not any(x == nm for (x, _d) in cant):
            malas.append(f"cuenta: el presupuesto suma {nm} que no esta en el pedido")
    general = 0
    for b in bs:
        sub = sum(t for *_x, t in b["renglones"])
        if b["subtotal"] is not None and b["subtotal"] != sub:
            malas.append(f"cuenta: subtotal {plata(b['subtotal'])} y los renglones suman {plata(sub)}")
        env = 0
        if b["envio"]:
            ciudad = next((c for c in CIUDADES if n(c) == n(b["envio"][0])), None)
            if ciudad:
                debe = 0 if sub > UMBRAL_GRATIS else tarifa(ciudad, tabla)
                if b["envio"][1] != debe:
                    malas.append(f"cuenta: envio a {ciudad} {plata(b['envio'][1])} y va {plata(debe)}")
            env = b["envio"][1]
        if b["total"] is not None and b["total"] != sub + env:
            malas.append(f"cuenta: total {plata(b['total'])} y es {plata(sub + env)}")
        general += sub + env
    m = re.search(r"Total general: \$([\d.]+)", r)
    if m and num(m.group(1)) != general:
        malas.append(f"cuenta: total general {m.group(1)} y es {plata(general)}")
    if e.get("reparto"):
        m = re.search(r"Total final: \$([\d.]+)", r)
        tr = sum(x["porcentaje"] for x in e["reparto"] if x["medio"] == "transferencia")
        debe = general * (1 - tr / 100 * DESCUENTO_TRANSF / 100)
        if not m:
            malas.append("pago partido: no da el total final")
        elif abs(num(m.group(1)) - debe) > 2:
            malas.append(f"pago partido {tr}% transferencia: total final {m.group(1)} y es {plata(debe)}")
    if e.get("tope"):
        alcanza = general <= e["tope"]
        dice_no = re.search(r"no te alcanza|te pasas|se pasa|no alcanza|pasaba de|pasa tu tope", n(r)) is not None
        dice_si = "te alcanza" in n(r) and not dice_no
        if alcanza and not dice_si:
            malas.append(f"tope {plata(e['tope'])}: alcanza, {plata(general)}, y no lo dice")
        if not alcanza and not dice_no:
            malas.append(f"tope {plata(e['tope'])}: no alcanza, {plata(general)}, y no lo dice")
    return malas


# ── EL ORACULO AVANZA CON LO QUE EL CLIENTE PIDIO, NO CON LO QUE HIZO EL BOT ───
def avanzar(ch, t, resp):
    for e in t["esperas"]:
        if e["tipo"] == "llevar":
            for l in e["lineas"]:
                ch.pedido.append(dict(l))
        elif e["tipo"] == "llevar_rubros":
            for rubro in e["rubros"]:
                fila = min(con_stock([f for f in FILAS if f["categoria"] == rubro]), key=lambda f: f["precio"])
                ch.pedido.append({"fila": fila, "cant": 1, "destino": e["destino"]})
        elif e["tipo"] == "saca":
            ch.pedido.pop(e["L"] - 1)
        elif e["tipo"] == "cambia":
            l = ch.pedido[e["L"] - 1]
            l.update({k: e[k] for k in ("cantidad", "destino") if k in e})
            if "cantidad" in e:
                l["cant"] = e["cantidad"]
    vistos = mostrados(resp)
    if vistos:
        ch.mostrado = vistos


def correr_charla(i, rng, tabla):
    from banco_pruebas import camino_fijo as F
    from banco_pruebas import clon_produccion as C
    import asyncio
    ch = Charla(rng)
    guion(ch)
    uid = f"fragil_{i}"
    C.reiniciar_cliente(uid)
    F.ESTADOS[uid], F.PRESUPUESTOS[uid], F.REGLAS[uid] = None, None, []
    F.PRESUPUESTOS.pop(uid, None)
    salida, k = [], 0
    while k < len(ch.turnos):
        t = ch.turnos[k]
        for q in t["agenda"]["preguntas"]:
            # La pieza "llevar_rubros" agrega por rubro: la traduccion perfecta lo pone asi, como en K03.
            pass
        F.COLA[uid] = [t["agenda"]]
        resp = "\n".join(asyncio.run(C.turno(uid, t["texto"])))
        malas = controlar(ch, t, resp, tabla, salida[-1]["respuesta"] if salida else "")
        avanzar(ch, t, resp)
        # El control de la cuenta corre con el pedido ya avanzado: se recontrola la cuenta.
        if any(e["tipo"] == "cuenta" for e in t["esperas"]):
            malas = [m for m in malas if not m.startswith("cuenta") and not m.startswith("pago") and not m.startswith("tope")]
            for e in t["esperas"]:
                if e["tipo"] == "cuenta":
                    malas += controlar_cuenta(ch, e, resp, tabla)
        salida.append({"texto": t["texto"], "agenda": t["agenda"], "respuesta": resp, "malas": malas,
                       "reglas": (F.REGLAS.get(uid) or [[]])[-1]})
        if t.get("despues") and ch.pedido or t.get("despues") == "elegir" and ch.mostrado:
            turno_siguiente(ch, t["despues"])
        k += 1
    return {"id": f"S{i:03d}", "tipo": ch.tipo, "turnos": salida}


def clase(m):
    return m.split(":")[0].split(" ")[0]


def main():
    args = sys.argv[1:]
    N = int(args[args.index("--n") + 1]) if "--n" in args else 300
    semilla = int(args[args.index("--semilla") + 1]) if "--semilla" in args else 1
    ver = int(args[args.index("--ver") + 1]) if "--ver" in args else 0
    import logging
    logging.disable(logging.CRITICAL)
    from banco_pruebas import camino_fijo as F
    F.instalar()
    import structlog
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))
    from banco_pruebas import sim_firestore as S
    tabla = S._CONFIG["tarifas_envio"]["provincias"]
    global _RNG
    _RNG = random.Random(semilla * 7919)
    rng = random.Random(semilla)
    res = [correr_charla(i, random.Random(rng.random()), tabla) for i in range(1, N + 1)]
    out = os.path.join(AQUI, f"fragil_fijo_s{semilla}.json")
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    turnos = [(c, i, t) for c in res for i, t in enumerate(c["turnos"], 1)]
    bien_t = sum(not t["malas"] for _, _, t in turnos)
    bien_c = sum(all(not t["malas"] for t in c["turnos"]) for c in res)
    print(f"{N} charlas, {len(turnos)} turnos · bien: {bien_c} charlas de {N}, {bien_t} turnos de {len(turnos)}")
    por_tipo = collections.defaultdict(lambda: [0, 0])
    for c in res:
        por_tipo[c["tipo"]][0] += all(not t["malas"] for t in c["turnos"])
        por_tipo[c["tipo"]][1] += 1
    print("por guion: " + ", ".join(f"{k} {a} de {b}" for k, (a, b) in sorted(por_tipo.items())))
    por_n = collections.defaultdict(lambda: [0, 0])
    for c, i, t in turnos:
        por_n[i][0] += not t["malas"]
        por_n[i][1] += 1
    print("por numero de turno: " + ", ".join(f"T{k} {a} de {b}" for k, (a, b) in sorted(por_n.items())))
    cl = collections.Counter(clase(m) for _, _, t in turnos for m in t["malas"])
    print("fallas por clase: " + ", ".join(f"{k} {v}" for k, v in cl.most_common()))
    vistas = 0
    for c, i, t in turnos:
        if t["malas"] and vistas < ver:
            vistas += 1
            print(f"\n=== {c['id']} {c['tipo']} T{i}: {t['texto']}\n agenda: {json.dumps(t['agenda']['preguntas'], ensure_ascii=False)}"
                  f"\n MALAS: {t['malas']}\n" + "  " + t["respuesta"].replace("\n", "\n  "))
    print(f"\nguardado en {out}")


if __name__ == "__main__":
    main()
