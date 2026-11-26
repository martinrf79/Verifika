"""LA CONDICION SOBRE LA RUEDA (26-nov-2026). FICHA 109, capa 3: condicion y orden. Plan 6 de `lab/plan.md`.

Por pedido de la rueda, `cadena.leer`, el codigo ata cada condicion a la fuente, sin modelo:
  - lo que tiene nombre, con el lexico del habla argentina de `reglas/base.py`, que apunta a campos de `fuente.VISTA`;
  - los numeros, con `conceptos/numeros.leer`: tope de plata, capacidad, ram, potencia, hz, pulgadas;
  - la marca, contra las marcas del catalogo; el codigo de modelo, contra los codigos del catalogo;
  - la negacion, "que no sea", "sin", "nada de", saca en vez de exigir; "no importa" anula;
  - la correccion, "Redragon, no, mejor Logitech": vale lo ultimo;
  - el orden, "el mas barato", corre sobre todo lo que cumple en el rubro.
Las reglas de clase, ninguna por caso:
  - una condicion sobre un campo que la tienda no trae para ese rubro no filtra: queda como sin dato;
  - la preferencia de uso filtra solo si deja algo;
  - si nada cumple, no hay, con lo que cumple todo menos lo minimo como alternativa, nunca ofrecido como si cumpliera;
  - lo que Luna marca como condicion y no se ata queda como sin dato, y no filtra; el color que la tienda no tiene si
    filtra, y deja no hay;
  - el precio sin numero ni pregunta, "que no sea carisimo", ordena del mas barato;
  - la fila sin producto que solo trae orden va a todos los pedidos de la frase; con otra condicion, al pedido anterior;
  - sin rubro, con orden, el orden corre sobre toda la tienda.

    python3 primeros/condicion.py --atar [--ver]      # capa sola: lo que filtra la capa contra lo que filtra la etiqueta
    python3 primeros/condicion.py --casos             # los casos escritos a mano, para revisar el guion
    python3 primeros/condicion.py [--examen|--reales|--muestras] [--ver]   # de punta a punta, con el orden aplicado
"""
import collections, difflib, json, os, re, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
FL = os.path.join(AQUI, "..")
sys.path[:0] = [AQUI, os.path.join(FL, "conceptos"), os.path.join(FL, "reglas"), os.path.join(FL, "examen")]
sys.dont_write_bytecode = True
_argv, sys.argv = sys.argv, ["x"] + [a for a in sys.argv[1:] if a in ("--examen", "--reales", "--muestras")]
import cadena as C  # noqa: E402
sys.argv = _argv
import fuente as F  # noqa: E402
import numeros as N  # noqa: E402
import base as RB  # noqa: E402
import conceptos as CO  # noqa: E402

X, nrm, M = C.X, F.nrm, C.M
CONC = X.CONC

# El lexico: (expresion, tipo, condiciones u orden). Las expresiones con cifras sueltas las lee `numeros`.
ORDEN_BASE = {"barato": ("precio", "asc"), "caro": ("precio", "desc"), "liviano": ("peso", "asc")}
# El uso y el origen son preferencia: filtran solo si deja algo. La tienda fabrica casi todo en China: "lo menos chino
# posible" no deja la tienda vacia, lo contesta la ficha.
PREF = {"gamer", "oficina", "streaming", "chino"}
# Inalambrico es tambien por wifi: un router o una impresora sin cable.
CAMBIA = {"inalambrico": [("conecta_por", "alguno", ["bluetooth", "receptor_usb", "wifi"])]}
# "Plata" sola es la ciudad o la plata de pagar: como color solo con "color" o "en" antes.
SACA = {"plata"}
LEX = []
for concepto, conds, exprs in RB.BASE:
    conds = CAMBIA.get(concepto, conds)
    for x in exprs:
        if re.fullmatch(r"[\d ]+(hz)?", nrm(x)) or nrm(x) in SACA:
            continue
        if concepto in ORDEN_BASE:
            LEX.append((nrm(x), "orden", ORDEN_BASE[concepto]))
        elif concepto in PREF:
            LEX.append((nrm(x), "pref", conds))
        else:
            LEX.append((nrm(x), "color" if conds[0][0] == "color" else "atributo", conds))
# Los ordenes de `conceptos.json` que el lexico de base no dice, con su nombre: "el mas pesado", "el de mas ram".
for o, (campo, sentido) in CO.ORDENES.items():
    if campo in ("precio", "peso") and sentido == "asc":
        continue
    pal = o.replace("mas_", "").replace("_w", "")
    for x in (f"mas {pal}", f"el de mas {pal}", f"con mas {pal}", f"el mas {pal}"):
        LEX.append((x, "orden", (campo, sentido)))
LEX.append(("mas pesado", "orden", ("peso", "desc")))
LEX.append(("mas caro", "orden", ("precio", "desc")))
LEX += [("color plata", "color", [("color", "tiene", ["plata"])]), ("en plata", "color", [("color", "tiene", ["plata"])])]
# Los atributos de `conceptos.json` que la base no trae, por su nombre y la forma corta de decirlo.
_YA = {c for c, _, _ in RB.BASE}
for _cid, _c in CONC.items():
    if _c["tipo"] == "atributo" and _cid.split(":")[1] not in _YA | {"con_luces", "panel_ips", "panel_oled", "panel_va"}:
        _n = _c["nombre"]
        for x in {_n, _n.replace("cancelacion ", "cancelacion de "), _n.replace("microfono", "mic"),
                  _n.replace("usb c", "tipo c"), _n.replace("resistente agua", "resistente al agua")}:
            LEX.append((nrm(x), "atributo", [tuple(y) for y in _c["cond"]]))
# Los colores que la tienda no tiene tambien se atan: filtran y dejan no hay, nunca se ignoran.
for c in ("verde", "amarillo", "violeta", "lila", "naranja", "celeste", "dorado", "marron", "beige", "morado",
          "fucsia", "turquesa", "bordo"):
    LEX.append((c, "color", [("color", "tiene", [c])]))
LEX.sort(key=lambda e: -len(e[0]))

MARCAS = {}
for _k in F.VISTA:
    MARCAS[nrm(_k[1])] = _k[1]
    MARCAS[nrm(_k[1]).replace(" ", "")] = _k[1]
    if len(nrm(_k[1]).split()) > 1:  # las iniciales de una marca de dos palabras: "wd" es Western Digital
        MARCAS["".join(w[0] for w in nrm(_k[1]).split())] = _k[1]
for _x in ("cm",):  # centimetros, no Cooler Master
    MARCAS.pop(_x, None)

# Las palabras de la tienda, de los alias: "micro" es microfono, no Microsoft.
_A = json.load(open(os.path.join(F.D, "alias.json"), encoding="utf-8"))
RUBRO_PAL = {w for k, xs in _A["rubros"].items() for x in xs + [k] for w in nrm(x).split() if len(w) > 3} | \
            {w for r in F.RUBROS for w in nrm(r).split()}
PALABRAS_TIENDA = {w for sec in ("rubros", "campos") for k, xs in _A[sec].items() for x in xs + [k]
                   for w in nrm(x).split()} | {w for r in F.RUBROS for w in nrm(r).split()}
NIEGA = re.compile(r"\b(que no sean?|no|sin|nada de|evitar|excepto|salvo|menos|ni)\s+(?:\w+\s+){0,2}$")
NO_NIEGA = re.compile(r"\bno\s+(se|sabes|sabia|tenes|tienen|tendras|hay|venden|importa|me importa|me interesa)\b[^|]*$")
ANULA = re.compile(r"\b(no importa|no me importa|da igual|me da lo mismo|cualquier|cualquiera)\s+(?:\w+\s+){0,3}$")
DUDA = re.compile(r"\b(indistinto|el que sea|no importa|da igual|cualquier|cualquiera|lo mismo|no se|mismo|que colores?|cuales?|colores)\b")
CORRIGE = re.compile(r"\b(mejor|perdon|en realidad|me equivoque|cambio|no no|ah no|bueno no)\b")
# Una cifra sola, sin unidad ni signo, es plata solo con una palabra de plata antes: "hasta 50000". Sin eso es un
# modelo, "rtx 4080", "l5590", o una direccion, "Colon 1500".
PLATA_ANTES = re.compile(r"\b(hasta|menos de|mas de|maximo|max|tope|presupuesto|gastar|pagar|pago|tengo|alrededor de|unos|por)\s*\$?\s*$")


# "Capaz inalambricos", "si es Logitech, mejor": lo que el cliente prefiere y no exige.
PREFIERE = re.compile(r"\b(capaz|quizas?|tal vez|si es posible|preferentemente|de preferencia|ojala|si puede ser)\s+(?:\w+\s+){0,2}$")


def _modo(antes, despues=""):
    if ANULA.search(antes):
        return "anulado"
    if PREFIERE.search(antes) or (re.search(r"\bsi es\s+(?:\w+\s+){0,1}$", antes) and re.match(r"\W*mejor\b", despues)):
        return "pref"
    m = NIEGA.search(antes)
    if m and not NO_NIEGA.search(antes) and not CORRIGE.search(antes[max(0, m.start() - 4):]):
        return "no"
    return ""


def escanear(texto, rubro, marcadas=frozenset()):
    """[{"tipo", "cond" u "orden", "modo", "texto", "pos"}] de lo que el texto dice como condicion, por codigo.
    marcadas: las palabras que Luna marco como marca o modelo; solo en ellas se busca una marca aproximada."""
    s = nrm(texto)
    out, tomado = [], []

    def libre(a, b):
        return not any(a < y and x < b for x, y in tomado)

    for expr, tipo, datos in LEX:
        if expr.endswith(("o", "a")):
            patron = re.escape(expr[:-1]) + r"(?:o|a|os|as|isimo|isima|isimos|isimas|ito|ita|itos|itas)"
        else:
            patron = re.escape(expr) + r"(?:s|es)?"
        for m in re.finditer(r"\b" + patron + r"\b", s):
            if not libre(*m.span()):
                continue
            tomado.append(m.span())
            d = {"tipo": tipo, "modo": _modo(s[:m.start()], s[m.end():]), "texto": expr, "pos": m.start()}
            d["orden" if tipo == "orden" else "cond"] = datos
            if tipo == "orden" and d["modo"] == "no":  # "que no sea caro" ordena del mas barato
                d["orden"], d["modo"] = (datos[0], "asc" if datos[1] == "desc" else "desc"), ""
            if d["modo"] == "pref":
                d["tipo"], d["modo"] = ("orden" if tipo == "orden" else "pref"), ""
            out.append(d)
    for marca_n, marca in MARCAS.items():
        for m in re.finditer(r"\b" + re.escape(marca_n) + r"\b", s):
            if libre(*m.span()):
                tomado.append(m.span())
                d = {"tipo": "marca", "cond": marca, "modo": _modo(s[:m.start()], s[m.end():]), "texto": marca_n,
                     "pos": m.start()}
                if d["modo"] == "pref":
                    d["tipo"], d["modo"] = "pref", ""
                out.append(d)
    # La marca abreviada o mal escrita, "logi", "kingstn", donde Luna marco una marca: prefijo de una sola marca, o casi
    # igual a una.
    for m in re.finditer(r"\b[a-z]{4,}\b", s):
        w = m.group(0)
        if not libre(*m.span()) or w in PALABRAS_TIENDA or w not in marcadas:
            continue
        pre = {MARCAS[b] for b in MARCAS if b.startswith(w) and len(w) * 2 >= len(b)}
        cerca = difflib.get_close_matches(w, list(MARCAS), 1, 0.85)
        marca = pre.pop() if len(pre) == 1 else MARCAS[cerca[0]] if cerca and not pre else None
        if marca:
            tomado.append(m.span())
            out.append({"tipo": "marca", "cond": marca, "modo": _modo(s[:m.start()], s[m.end():]), "texto": w,
                        "pos": m.start()})
    for w in set(s.replace("-", " ").split()):
        if C._codigo(w) and not re.fullmatch(r"\d+(gb|tb|w|hz|mah|mm|k)", w) and w in C.CODIGOS and (rubro is None or rubro in C.CODIGOS[w]):
            out.append({"tipo": "modelo", "cond": w, "modo": "", "texto": w, "pos": s.find(w)})
    for o in N.leer(texto, rubro):
        if o["tipo"] == "cantidad":
            continue
        campo = o["campo"]
        i = N.nrm(texto).find(o["texto"])
        if o["tipo"] == "plata" and re.fullmatch(r"\d+(\.\d+)?", o["texto"]) and not PLATA_ANTES.search(
                N.nrm(texto)[:max(i, 0)]):
            continue
        out.append({"tipo": "numero", "cond": [(campo, o["op"], o["valor"])], "modo": "", "texto": o["texto"],
                    "pos": max(i, 0)})
    # Un numero solo, "monitor 27", "ssd 500", "fuente 650": el campo del rubro donde algun producto tiene ese valor, si
    # es uno solo. No la cantidad, "10 mouse", "2 unidades", ni un codigo, "rtx 4080", ni lo que ya leyo otro lector.
    if rubro:
        sn = N.nrm(texto)
        leidos = {o["texto"] for o in N.leer(texto, rubro) if o["tipo"] != "cantidad"}
        for m in re.finditer(r"(?<![\w.])(\d{1,4})(?![\w.])", sn):
            n, despues, antes = float(m.group(1)), sn[m.end():m.end() + 14], sn[:m.start()]
            if any(m.group(1) in t.split() or t.startswith(m.group(1) + " ") for t in leidos):
                continue
            sig = (despues.split() or [""])[0]
            if re.match(r"\s*(unidades?|piezas?|u\b|x\b|de es)", despues) or any(
                    sig.startswith(w[:4]) for w in RUBRO_PAL if len(sig) > 3):
                continue
            if re.search(r"\b(llevo|quiero|necesito|dame|x|por|son|serian)\s*$", antes):
                continue
            # La cifra que es parte del nombre de un modelo del rubro, "flip 6", "legion 5", no es una condicion.
            prev = (antes.split() or [""])[-1]
            if prev and any(f"{prev} {m.group(1)}" in nrm(k[2]) for k in F.VISTA if nrm(k[0]) == rubro):
                continue
            campos = [c for c in NUMERICOS if any(F.VISTA[k].get(c) == n for k in F.VISTA if nrm(k[0]) == rubro)]
            if len(campos) == 1:
                out.append({"tipo": "numero", "cond": [(campos[0], "igual", n)], "modo": "", "texto": m.group(1),
                            "pos": m.start()})
    # La correccion del cliente: de dos marcas o colores afirmados con "mejor", "perdon" en el medio, vale lo ultimo.
    def eje(d):  # lo que se corrige: la marca, el color, o el campo de la caracteristica, "sin cable" por "con cable"
        return d["tipo"] if d["tipo"] in ("marca", "color") else ("campo", d["cond"][0][0])
    for e in {eje(d) for d in out if d["tipo"] in ("marca", "color", "atributo")}:
        xs = sorted((d for d in out if d["tipo"] in ("marca", "color", "atributo") and eje(d) == e and d["modo"] == ""),
                    key=lambda d: d["pos"])
        for a, b in zip(xs, xs[1:]):
            if CORRIGE.search(s[a["pos"]:b["pos"]]):
                a["modo"] = "anulado"
    return out


NUMERICOS = ("pulgadas", "capacidad_gb", "ram_gb", "disco_gb", "potencia_w", "hz")


def preguntadas(fila):
    """Los nombres de caracteristica que la fila pregunta: no filtran, son dato 2. Una caracteristica se pregunta si
    sus propias palabras preguntan, "es inalambrico", "cuanta ram tiene"; no por un "?" de la fila: "tenes
    inalambricos?" pide el stock de los inalambricos, y "inalambrico" es como tiene que ser el producto. `cadena.dato2`
    da las condiciones que Luna marco, para saber cuales no se atan."""
    _, conds = C.dato2(fila)
    out = set()
    for m in re.finditer(r"\{([^}]*)\}\s*\[([^\]]*)\]", fila):
        palabras, nombre = m.group(1), nrm(m.group(2))
        sec = C.SECCION.get(nombre)
        if (nombre in C.PRODUCTO_D2 or sec == "CARACTERISTICAS" and nombre not in ("precio ars", "marca", "modelo")) \
                and C.INTERROGA.search(nrm(palabras)):
            out.add(nombre)
    return out, conds


def atar(f, fila):
    """Las condiciones de un pedido de la rueda: (atadas, sin dato). Lee las partes del pedido que no son preguntas
    de la ficha; lo que Luna marco como condicion y no se ato queda como sin dato."""
    preg, conds = preguntadas(fila)
    if len(C.leer(fila)) == 1:
        # La fila es un solo pedido: se lee entera, tambien lo que Luna dejo fuera de las llaves, "HyperX [marca]".
        texto = re.sub(r"\{([^}]*)\}\s*\[([^\]]*)\]", lambda m: " " if nrm(m.group(2)) in preg else " " + m.group(1) + " ",
                       fila)
        texto = re.sub(r"\[[^\]]*\]", " | ", texto).replace("{", " ").replace("}", " ")
    else:
        texto = " | ".join(p for p, n in f["partes"] if not (n and n in preg))
    marcadas = {w for p, n in f["partes"] if n in ("marca", "modelo") for w in nrm(p).split()}
    marcadas |= {w for m in re.finditer(r"([^{}\[\]]+?)\s*\[\s*(marca|modelo)\s*\]", fila) for w in nrm(m.group(1)).split()}
    todas = escanear(texto, f["rubro"], marcadas)
    at = [d for d in todas if d["modo"] != "anulado"]
    sin = []
    for pal, nombre in conds:
        if nombre in ("marca", "modelo"):
            continue
        pn = nrm(pal)
        if any(d["texto"] and (d["texto"] in pn or N.nrm(pal).find(d["texto"]) >= 0) for d in todas):
            continue
        if nombre == "precio ars":
            # "Que no sea carisimo" ordena del mas barato; una cifra que el cliente cita, "en la web dice 237.000", no.
            if not any(d["tipo"] == "orden" for d in at) and not re.search(r"\d", pn):
                at.append({"tipo": "orden", "orden": ("precio", "asc"), "modo": "", "texto": pn, "pos": 0})
            continue
        if nombre == "color" and DUDA.search(pn):
            continue
        if nombre == "color":
            ws = [w for w in pn.split() if w not in ("de", "en", "color", "que", "sea", "el", "la", "los", "las")]
            if len(ws) == 1:
                at.append({"tipo": "color", "cond": [("color", "tiene", [" ".join(ws)])], "modo": _modo(""),
                           "texto": pn, "pos": 0})
                continue
        sin.append(pal)
    return at, sin


def _texto(v):
    return nrm(" ".join([v["nombre"], v["modelo"], v["extra"]]))


def _cumple1(v, d, rubro_keys):
    if d["tipo"] == "marca":
        if any(k[1] == d["cond"] for k in rubro_keys):
            return v["marca"] == d["cond"]
        return nrm(d["cond"]) in _texto(v)
    if d["tipo"] == "modelo":
        return d["cond"] in nrm(v["modelo"]).replace("-", " ").split()
    if all(CO.cumple(v, c) for c in d["cond"]):
        return True
    # El atributo que el nombre del producto dice, "Motherboard B650 WiFi", aunque la ficha no lo traiga en su campo.
    return d["tipo"] == "atributo" and not re.match(r"(sin|no|que no)\b", d["texto"]) and d["texto"] in _texto(v).split() \
        or d["tipo"] == "atributo" and len(d["texto"].split()) > 1 and d["texto"] in _texto(v)


def _con_dato(d, keys):
    """Si la tienda trae el campo de esa condicion para alguno de estos productos."""
    if d["tipo"] in ("marca", "modelo"):
        return True
    campos = [c[0] for c in d.get("cond") or []] or [d["orden"][0]]
    return any(F.VISTA[k].get(c) not in (None, "", []) for k in keys for c in campos)


def resolver(at, pool):
    """pool: los productos del rubro, ya ordenados por embeddings. Devuelve (veredicto, productos, sin dato de campo).
    veredicto: ofrece, o nada cumple con la alternativa primero."""
    sin = []
    duras, prefs, orden = [], [], None
    for d in at:
        if not _con_dato(d, pool):
            sin.append(d["texto"])
        elif d["tipo"] == "orden":
            orden = d["orden"]
        elif d["tipo"] == "pref":
            prefs.append(d)
        elif d["tipo"] == "modelo":
            # El modelo nombrado lo elige la capa producto: "c922 pro o brio 100", "i3 o ryzen 5 5500" nombran dos, y
            # filtrar por el codigo de uno sacaba al otro. Aca solo sirve para no cambiar el nombrado por otro.
            continue
        else:
            duras.append(d)
    # Las afirmadas del mismo tipo, color o marca, valen cualquiera: "negro o blanco". Las otras, todas.
    grupos = collections.defaultdict(list)
    for d in duras:
        grupos[(d["tipo"] if d["tipo"] in ("color", "marca", "modelo") and d["modo"] == "" else id(d))].append(d)

    def fallas(k):
        v = F.VISTA[k]
        n = 0
        for g in grupos.values():
            if g[0]["modo"] == "no":
                n += _cumple1(v, g[0], pool)
            else:
                n += not any(_cumple1(v, d, pool) for d in g)
        return n

    quedan = [k for k in pool if fallas(k) == 0]
    if prefs:
        q = [k for k in quedan if all(_cumple1(F.VISTA[k], d, pool) for d in prefs)]
        quedan = q or quedan
    if orden:
        campo, sentido = orden
        con = [k for k in quedan if F.VISTA[k].get(campo) is not None]
        con.sort(key=lambda k: F.VISTA[k][campo], reverse=sentido == "desc")
        quedan = con + [k for k in quedan if k not in con]
    if quedan:
        return "ofrece", quedan, sin
    alt = sorted(pool, key=lambda k: fallas(k))
    return "nada cumple", alt, sin


def pedidos(textos):
    """Los pedidos de un mensaje con sus condiciones atadas, y lo que la rueda deja para esta capa: la fila sin producto
    que solo trae condicion se pega al pedido anterior, o a todos si es orden."""
    out, sueltas = [], []
    for t in textos:
        for f in C.leer(t):
            at, sin = atar(f, t)
            f = dict(f, atadas=at, sin_dato=sin)
            if f["nombra"] and f["consulta"]:
                out.append(f)
            elif at:
                sueltas.append((len(out), f))
    # La fila sin rubro que solo trae condiciones, "dime lo mas barato", es suelta si hay pedidos con producto.
    if any(f["rubro"] or f["identifica"] for f in out):
        for f in [f for f in out if not f["rubro"] and not f["identifica"] and f["atadas"]]:
            sueltas.append((out.index(f), f))
            out.remove(f)
    for i, f in sueltas:
        destino = out if all(d["tipo"] == "orden" for d in f["atadas"]) else out[max(i - 1, 0):max(i, 1)]
        for g in destino:
            g["atadas"] = g["atadas"] + [d for d in f["atadas"] if not (d["tipo"] == "orden" and
                                                                          any(x["tipo"] == "orden" for x in g["atadas"]))]
    # El tope de plata que Luna copio en todos los pedidos de la frase es del total, "no quiero gastar mas de 600 mil":
    # no filtra cada producto, lo controla la cotizacion.
    if len(out) > 1:
        def topes(g):
            return {tuple(d["cond"][0]) for d in g["atadas"] if d["tipo"] == "numero" and d["cond"][0][0] == "precio"}
        comun = set.intersection(*[topes(g) for g in out])
        for g in out:
            g["atadas"] = [d for d in g["atadas"] if not (d["tipo"] == "numero" and tuple(d["cond"][0]) in comun)]
    # Dos ordenes en el mismo pedido, "la mas barata y la mas cara", son dos pedidos.
    final = []
    for g in out:
        ords = [d for d in g["atadas"] if d["tipo"] == "orden"]
        if len({d["orden"] for d in ords}) > 1:
            resto = [d for d in g["atadas"] if d["tipo"] != "orden"]
            vistos = set()
            for d in ords:
                if d["orden"] not in vistos:
                    vistos.add(d["orden"])
                    final.append(dict(g, atadas=resto + [d]))
        else:
            final.append(g)
    return final


# ---------------------------------------------------------------- la capa sola, contra la etiqueta

def _rubros_etiqueta(p):
    if "_acept" in p:
        return {nrm(k[0]) for k in p["_acept"]}
    return {nrm(CONC[i]["nombre"]) for c in p["cas"] if c["tipo"] == "rubro" for i in X._ids(c)}


def _filtra_etiqueta(p, rubros):
    """Lo que la etiqueta deja en sus rubros, sin el modelo nombrado, que es de la capa producto: los aceptables, o
    `_acept` de las muestras."""
    ac = {tuple(k) for k in p["_acept"]} if "_acept" in p else set(X.aceptables(
        dict(p, cas=[c for c in p["cas"] if c["tipo"] != "modelo"])))
    return {k for k in ac if nrm(k[0]) in rubros}


def _tiene_condicion(p):
    if "_acept" in p:
        return bool(p.get("_cond"))
    return any(c["tipo"] in X.FILTRAN - {"rubro"} and c["modo"] not in ("pregunta", "anulado") for c in p["cas"])


def medir_atar(ver):
    """Por pedido etiquetado con un rubro: lo que deja el filtro de la capa, sin preferencias ni orden, contra lo que deja
    la etiqueta, en el mismo rubro. Exacto; de mas, la capa saca de mas y pierde venta; de menos, deja lo que no
    cumple y puede ofrecerlo; distinto. El orden: la capa ordena por el mismo campo que la etiqueta."""
    conjs = {"examen": (os.path.join(FL, "examen", "examen.json"), os.path.join(FL, "examen", "luna_b.jsonl")),
             "reales": (os.path.join(AQUI, "reales.json"), os.path.join(AQUI, "luna_reales.jsonl")),
             "muestras": (os.path.join(AQUI, "muestras.json"), os.path.join(AQUI, "luna_muestras.jsonl")),
             "sinteticas": (os.path.join(AQUI, "examen.json"), os.path.join(AQUI, "luna_b.jsonl"))}
    for conj, (et, lu) in conjs.items():
        ex = json.load(open(et, encoding="utf-8"))
        luna = {json.loads(l)["id"]: json.loads(l) for l in open(lu)}
        n, fallas = collections.Counter(), []
        for e in ex:
            ts = (luna[e["id"]]["salida"] or {}).get("textos") or []
            ps = pedidos(ts)
            for p in e["pedidos"]:
                rubros = _rubros_etiqueta(p)
                if "_acept" in p and set(p.get("_cond") or []) & {"modelos"}:
                    n["con modelo nombrado: capa producto"] += 1
                    continue
                if not rubros or "no_hay" in p["esperados"] and len(p["esperados"]) == 1 and not _tiene_condicion(p):
                    continue
                mias = [f for f in ps if f["rubro"] in rubros]
                cond = _tiene_condicion(p) or any(f["atadas"] for f in mias)
                if not cond:
                    continue
                if not mias:
                    n["el pedido no llega con su rubro"] += 1
                    continue
                ords = [c for c in p["cas"] if c["tipo"] == "orden"]
                et_o = tuple(CONC[ords[0]["valor"]]["cond"][0][::2]) if ords else None
                f = next((g for g in mias if any(d.get("orden") == et_o for d in g["atadas"])), mias[0])
                rubros = {f["rubro"]}
                pool = [k for k in F.VISTA if nrm(k[0]) in rubros]
                duras = [d for d in f["atadas"] if d["tipo"] not in ("orden", "pref", "modelo")]
                _, mio, sin = resolver(duras, pool)
                mio = set(mio) if _ != "nada cumple" else set()
                eti = _filtra_etiqueta(p, rubros)
                # Con un modelo nombrado, la etiqueta filtra por el modelo, que es de la capa producto: vale si la capa
                # deja el modelo y saca solo lo que tampoco cumple sin el modelo.
                if "_acept" not in p and any(c["tipo"] == "modelo" for c in p["cas"]):
                    full = {k for k in X.aceptables(p) if nrm(k[0]) in rubros}
                    if full <= mio <= eti:
                        eti = mio
                k = ("exacto" if mio == eti else "saca de mas, pierde venta" if mio < eti else
                     "deja de mas, puede ofrecer mal" if mio > eti else "distinto")
                n["filtro " + k] += 1
                if k != "exacto" or ver == "todo":
                    fallas.append(f"{e['id']} {k}: mio {len(mio)} etiqueta {len(eti)} atadas "
                                  f"{[(d['tipo'], d['texto'], d['modo']) for d in f['atadas']]} sin dato {f['sin_dato'] + sin}"
                                  f" | {e['texto'][:80]!r}")
                mi_orden = next((d["orden"] for d in f["atadas"] if d["tipo"] == "orden"), None)
                if ords or mi_orden:
                    ko = "orden igual" if et_o == mi_orden else "orden falta" if not mi_orden else (
                        "orden de mas" if not et_o else "orden distinto")
                    n[ko] += 1
                    if ko != "orden igual":
                        fallas.append(f"{e['id']} {ko}: mio {mi_orden} etiqueta {et_o} | {e['texto'][:80]!r}")
                if f["sin_dato"] or sin:
                    n["con algo sin dato"] += 1
        print(f"\n{conj}: pedidos con condicion, en la etiqueta o en la capa")
        for k, c in sorted(n.items()):
            print(f"  {k:36} {c}")
        if ver:
            for x in fallas:
                print("   ", x)


# ---------------------------------------------------------------- de punta a punta

NO_OFRECE = ("no_hay", "sin rubro", "nada cumple")
# Lo que se pide a toda la tienda, "los dos articulos mas baratos": sin rubro, con orden y una palabra que no nombra
# ningun producto. "La memoria mas cara" sin rubro marcado no es toda la tienda: queda sin rubro, FICHA 108, seccion 9.
TODA = re.compile(r"\b(productos?|articulos?|cosas?|items?|algo|de la tienda|que tengan|que tengas)\b")


def contar(e, res, n, fallas):
    """Como `medir.contar`, con el orden aplicado: con orden, el primero tiene que ser el mejor de los aceptables por el
    campo de la etiqueta. Nada cumple cuenta como no hay dicho; su alternativa no es una oferta."""
    i = e["id"]
    acs = [{tuple(k) for k in p["_acept"]} if "_acept" in p else set(X.aceptables(p)) for p in e["pedidos"]]
    for p, ac in zip(e["pedidos"], acs):
        ords = [c for c in p["cas"] if c["tipo"] == "orden"]
        grupo = "con orden" if ords else "sin orden"

        def bien(k):
            if k not in ac:
                return False
            for c in ords:
                campo, _, sentido = CONC[c["valor"]]["cond"][0]
                vals = [F.VISTA[x][campo] for x in ac if F.VISTA[x][campo] is not None]
                if vals and F.VISTA[k][campo] != (min(vals) if sentido == "asc" else max(vals)):
                    return False
            return True
        if "ofrecer" in p["esperados"] and ac:
            if any(top and bien(top[0]) and vr not in NO_OFRECE for _, vr, top in res):
                k = "primero sirve"
            elif any(top and top[0] in ac and vr not in NO_OFRECE for _, vr, top in res):
                k = "sirve, mal ordenado"
            elif any(top and top[0] in ac and vr == "nada cumple" for _, vr, top in res):
                k = "nada cumple de mas"
            elif any(top and top[0] in ac for _, vr, top in res):
                k = "falsa alarma de existe"
            elif any(set(top[:5]) & ac for _, _, top in res):
                k = "entre los 5"
            else:
                k = "no lo trae"
            n[("ofrecer", grupo, k)] += 1
            if k != "primero sirve":
                fallas.append(f"{i} pierde [{k}] {e['texto'][:70]!r} filas={M._filas(res)}")
        elif set(p["esperados"]) == {"no_hay"}:
            k = "no hay dicho" if any(vr in NO_OFRECE for _, vr, _ in res) else "no hay perdido"
            n[("no hay", "", k)] += 1
            if k != "no hay dicho":
                fallas.append(f"{i} alucina [{k}] {e['texto'][:70]!r} filas={M._filas(res)}")
    todos = set().union(*acs) if acs else set()
    for lp, vr, top in res:
        if vr in NO_OFRECE:
            continue
        n[("fila", "", "ofrece")] += 1
        if not top or top[0] not in todos:
            n[("fila", "", "oferta equivocada")] += 1
            fallas.append(f"{i} alucina [oferta equivocada] {lp[:45]!r} -> {top[0][2] if top else '-'}")


def main(ver):
    ex, luna = C.cargar()
    ps = {e["id"]: pedidos((luna[e["id"]]["salida"] or {}).get("textos") or []) for e in ex}
    v = C.B.vectores([(f["consulta"], "RETRIEVAL_QUERY") for fs in ps.values() for f in fs])
    ia = C.B.indice_a()
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))
    for capa in ("sin la capa", "con la capa"):
        n, fallas = collections.Counter(), []
        for e in ex:
            res, vistos = [], set()
            for f in ps[e["id"]]:
                clave = (f["rubro"], nrm(f["consulta"]), tuple(sorted(str(d.get("orden")) for d in f["atadas"])))
                if clave in vistos:
                    continue
                vistos.add(clave)
                q = v[(f["consulta"], "RETRIEVAL_QUERY")]
                orden = any(d["tipo"] == "orden" for d in f["atadas"])
                if f["rubro"]:
                    pool = [k for k in ia if nrm(k[0]) == f["rubro"]] or list(ia)
                elif f["identifica"] or (capa == "con la capa" and orden and TODA.search(nrm(f["consulta"]))):
                    pool = list(ia)
                else:
                    res.append((f["consulta"], "sin rubro", []))
                    continue
                vr, _ = C.EX.existe(f["nombre"] or f["consulta"], aislado=True)
                vr = "no_hay" if vr == "no_hay" else "hay"
                pool = sorted(pool, key=lambda k: -dot(q, ia[k]))
                if capa == "con la capa" and vr != "no_hay":
                    primero = pool[0]
                    vr2, pool, _ = resolver(f["atadas"], pool)
                    vr = "nada cumple" if vr2 == "nada cumple" else vr
                    # El modelo que el cliente nombra y no cumple no se cambia por otro: se dice que no cumple.
                    nombrado = any(n == "modelo" for _, n in f["partes"]) or any(d["tipo"] == "modelo" for d in f["atadas"])
                    if nombrado and vr2 == "ofrece" and primero not in pool:
                        vr, pool = "nada cumple", [primero] + pool
                res.append((f["consulta"], vr, pool[:5]))
            contar(e, res, n, fallas)
        print(f"\n{capa}:")
        for (a, g, k), c in sorted(n.items()):
            print(f"  {a:8} {g:10} {k:24} {c}")
        if ver:
            for x in sorted(fallas):
                print("   " if capa == "con la capa" else "   sin:", x)


CASOS = [  # (fila de Luna, rubro esperado, lo que se tiene que atar como (tipo, texto, modo), sin dato)
    ("{teclado}[teclado] {inalambrico}[conexion]", [("atributo", "inalambrico", "")]),
    ("{mouse}[mouse] {que no sea Genius}[marca]", [("marca", "genius", "no")]),
    ("{auriculares}[auriculares] {con cable}[conexion] {hasta 50 mil}[precio ars]",
     [("atributo", "con cable", ""), ("numero", "50000", "")]),
    ("{el mouse mas liviano}[mouse]", [("orden", "liviano", "")]),
    ("{teclado}[teclado] {en rojo}[color]", [("color", "rojo", "")]),
    ("{teclado}[teclado] {azul}[color]", [("color", "azul", "")]),
    ("{teclado}[teclado] {rosa}[color]", [("color", "rosa", "")]),
    ("{tenes teclados}[teclado] {Redragon}[marca] {no, perdon, mejor Logitech}[marca]", [("marca", "logitech", "")]),
    ("{teclado}[teclado] {no importa el color}[color]", []),
    ("{notebook}[notebook] {64 GB}[ram] {por menos de 200 mil}[precio ars]",
     [("numero", "64 gb", ""), ("numero", "200000", "")]),
    ("{teclado}[teclado] {que no sea carisimo}[precio ars]", [("orden", "que no sea caro", "")]),
    ("{mouse}[mouse] {que no se caliente}[caracteristicas extra]", []),
    ("{tiene luces}[retroiluminacion] {el teclado}[teclado]?", []),
]


def casos():
    mal = 0
    for fila, esp in CASOS:
        f = C.leer(fila)[0]
        at, sin = atar(f, fila)
        got = sorted((d["tipo"], d["texto"] if d["tipo"] != "numero" else str(d["cond"][0][2]) if d["cond"][0][0] == "precio"
                      else d["texto"], d["modo"]) for d in at)
        ok = got == sorted(esp)
        mal += not ok
        pool = [k for k in F.VISTA if nrm(k[0]) == f["rubro"]]
        vr, prods, sd = resolver(at, pool)
        print("ok " if ok else "MAL", fila, "->", got, "sin dato", sin + sd, "|", vr, len(prods),
              [k[2] for k in prods[:2]])
    print(f"{len(CASOS) - mal} de {len(CASOS)} casos")


if __name__ == "__main__":
    if "--casos" in sys.argv:
        casos()
    elif "--atar" in sys.argv:
        medir_atar("todo" if "--todo" in sys.argv else "--ver" in sys.argv)
    else:
        main("--ver" in sys.argv)
