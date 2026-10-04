"""CAMINO A, de punta a punta sin intermediario.
1. El modelo pide en LINEAS (pocas casillas fijas, palabras libres).
2. El codigo traduce cada linea a una consulta y la cumple: datos, ambiguo, no existe o NO SE PUDO.
3. El codigo arma los envios y suma.
4. El modelo redacta solo con eso.
"""
import csv, difflib, json, os, re, sys, unicodedata
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from necesita import llamar, G, D, EXP

C = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "clientes", "verifika_prod", "")
P = [dict(r, precio=int(float(r["precio_ars"])), stock=int(float(r["stock"] or 0)), peso=float(r["peso_gramos"] or 0))
     for r in csv.DictReader(open(C + "productos.csv"))]
SPECS = {(r["marca"], r["modelo"]): r for r in csv.DictReader(open(C + "specs_por_modelo.csv"))}
FAQ = json.load(open(C + "faq.json"))
RUBROS = sorted({p["categoria"] for p in P})
MARCAS = sorted({p["marca"] for p in P})


def n(t):
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c)).strip()


def plata(x):
    return f"${x:,}".replace(",", ".")


# ══ 1. EL PEDIDO EN LINEAS ═══════════════════════════════════════════════════

PIDE = """Sos el vendedor de una tienda online de tecnologia de Argentina. Abajo esta la charla con un cliente. TODAVIA NO LE CONTESTES.
No tenes acceso al catalogo: el sistema de la tienda te va a pasar los datos que pidas, y nada mas. Pedi lo que necesitas para contestar bien y completo el ULTIMO mensaje del cliente, una linea por pedido, con esta forma exacta, casillas separadas por |:

D<n> | buscar | <rubro, o "toda la tienda"> | <cuantos articulos> | <criterio con tus palabras: mas barato, mas caro, mas liviano, buena calidad, o nada> | <condiciones con tus palabras: marca, color, conexion, que no sea tal marca, o nada>
D<n> | producto | <el producto con el nombre que tiene en la charla, con color si se sabe> | <cuantos>
D<n> | rubros | que rubros vende la tienda
D<n> | politica | <el tema con tus palabras: medios de pago, cuotas, descuentos, mayoristas, garantia, factura...>
D<n> | envio | <destino> | lleva <Dk> x<cantidad>, <Dk> x<cantidad>
D<n> | cuenta | <Dk> <Dk> ...            (el total de esos envios o productos; el sistema suma, vos no)
D<n> | preguntar | <lo que falta saber del cliente y no se puede deducir>

Reglas:
- "lleva" apunta a tus lineas buscar o producto: D1 x2 son 2 unidades de lo que devuelva D1. Si un buscar pide 2 articulos distintos, "lleva D1 x1" es uno de ellos y el sistema los reparte en orden.
- "Ese", "el otro", "lo demas", "los que faltan": resolvelos vos con la charla y escribi el producto o el reparto concreto.
- Una condicion que el cliente puso antes sigue valiendo hasta que la cambie.
- No escribas precios ni datos: solo pedis. Si no hace falta ningun dato (un saludo, algo fuera de tema), una sola linea: D1 | nada
Solo las lineas, nada mas."""

TIPOS = ("buscar", "producto", "rubros", "politica", "envio", "cuenta", "preguntar", "nada")


def parsear(texto):
    out, malas = [], []
    for linea in texto.splitlines():
        linea = linea.strip().strip("`").strip("-* ").strip()
        if not linea:
            continue
        c = [x.strip() for x in linea.split("|")]
        if len(c) < 2 or not re.fullmatch(r"D\d+", c[0]) or n(c[1]) not in TIPOS:
            malas.append(linea)
            continue
        out.append({"id": c[0], "tipo": n(c[1]), "c": c[2:]})
    return out, malas


# ══ 2. EL CODIGO CUMPLE CADA LINEA ═══════════════════════════════════════════

TODA = ("toda la tienda", "todo", "tienda", "catalogo", "cualquiera", "todos", "general", "")
_RUBRO_ALIAS = {"auricular": "auriculares", "memoria": "memoria ram", "memorias": "memoria ram", "ram": "memoria ram",
                "teclados": "teclado", "notebooks": "notebook", "monitores": "monitor", "mouses": "mouse",
                "microfonos": "microfono", "tablets": "tablet", "parlantes": "parlante", "webcams": "webcam",
                "disco externo": "almacenamiento externo", "silla": "silla gamer", "placa": "placa de video"}


def rubro(t):
    t = n(t)
    if t in TODA or "toda la tienda" in t:
        return None, ""
    if t in RUBROS:
        return t, ""
    for k, v in _RUBRO_ALIAS.items():
        if t == k or t.startswith(k + " "):
            return v, ""
    cerca = difflib.get_close_matches(t, RUBROS, 1, 0.75)
    if cerca:
        return cerca[0], ""
    return "NO", f"la tienda no vende '{t}'. Rubros que vende: {', '.join(RUBROS)}"


def conexion(p):
    s = SPECS.get((p["marca"], p["modelo"])) or {}
    return n(f"{s.get('conexion', '')} {s.get('bluetooth', '')} {p['caracteristicas_extra']} {p['nombre']}")


def condiciones(t, ps):
    t, notas = n(t), []
    if t in ("", "nada", "ninguna", "-"):
        return ps, notas
    if re.search(r"parecid|similar|tipo de|como un|reemplaz", t):
        return ps, ["NO SE PUDO aplicar la condicion '" + t + "': no es un dato de la ficha; pedi un rubro concreto"]
    excl = [m for m in MARCAS if re.search(r"(no sea|sin|excepto|ni|menos|no)\s+(?:\w+\s+){0,3}?" + n(m), t)]
    incl = [m for m in MARCAS if n(m) in t and m not in excl]
    if excl:
        ps = [p for p in ps if p["marca"] not in excl]
        notas.append("sin marcas " + ", ".join(excl))
    if incl:
        ps = [p for p in ps if p["marca"] in incl]
        notas.append("marca " + ", ".join(incl))
    for color in ("negro", "blanco", "gris", "plata", "azul", "rojo", "rosa"):
        if re.search(r"\b" + color, t):
            ps = [p for p in ps if n(p["color"]).startswith(color)]
            notas.append("color " + color)
    if re.search(r"inalambric|bluetooth|sin cable", t):
        ps = [p for p in ps if re.search(r"inalambric|bluetooth|wireless|lightspeed|2\.4", conexion(p))]
        notas.append("inalambrico")
    if re.search(r"chin|origen|fabric", t):
        notas.append("NO SE PUDO filtrar por origen: casi todo el catalogo dice fabricado en China o en Asia segun "
                     "linea; el origen de la marca si figura en cada articulo")
    return ps, notas


def criterio(t):
    t = n(t)
    if re.search(r"barat|econom|crisis|menor precio|accesible|ajustad", t):
        return "precio", 1, ""
    if re.search(r"liviano|ligero", t):
        return "peso", 1, ""
    if re.search(r"car[oa]|premium|gama alta|mejor|calidad|potente|top", t):
        aviso = "" if re.search(r"car[oa]", t) else "calidad no es un dato de la ficha: se toma la gama alta por precio"
        return "precio", -1, aviso
    return None, 0, ""


def rubro_en(texto):
    t = n(texto)
    for r in sorted(RUBROS, key=len, reverse=True):
        if re.search(r"\b" + re.escape(r), t):
            return r
    for k, v in _RUBRO_ALIAS.items():
        if re.search(r"\b" + re.escape(k) + r"\b", t):
            return v
    return None


def buscar(c):
    r, aviso = rubro(c[0] if c else "")
    otro = rubro_en(" ".join(c[2:]))  # el rubro escrito en el criterio o las condiciones
    if otro and r in (None, "NO"):
        r, aviso = otro, ""
    if r == "NO":
        return {"no_existe": aviso}
    cant = int(re.sub(r"\D", "", c[1]) or 1) if len(c) > 1 else 1
    campo, signo, aviso_c = criterio(c[2] if len(c) > 2 else "")
    ps = [p for p in P if p["stock"] > 0 and (r is None or p["categoria"] == r)]
    ps, notas = condiciones(c[3] if len(c) > 3 else "", ps)
    if campo:
        ps = sorted(ps, key=lambda p: signo * p[campo])
    elegidos, modelos = [], set()
    for p in ps:  # articulos distintos: un color por modelo
        if (p["marca"], p["modelo"]) in modelos:
            continue
        modelos.add((p["marca"], p["modelo"]))
        elegidos.append(p)
    tope = cant if campo else max(cant, 6)
    out = {"alcance": r or "toda la tienda", "filas": elegidos[:tope]}
    if notas:
        out["filtros"] = notas
    if aviso_c:
        out["aviso"] = aviso_c
    if not elegidos:
        out["no_existe"] = "no hay articulos con stock que cumplan eso"
    return out


def producto(c):
    q = n(c[0] if c else "")
    if q in RUBROS or q in _RUBRO_ALIAS:
        out = buscar([q, c[1] if len(c) > 1 else "1", "", ""])
        out["aviso"] = "el cliente no nombro un modelo: estas son opciones del rubro, sin criterio de orden"
        return out
    qt = set(re.findall(r"[a-z0-9]+", q))
    puntos = []
    for p in P:
        nt = set(re.findall(r"[a-z0-9]+", n(p["nombre"])))
        s = len(qt & nt) / max(1, len(qt))
        puntos.append((s, p))
    puntos.sort(key=lambda x: -x[0])
    mejor = puntos[0][0]
    if mejor < 0.6:
        return {"no_existe": f"no hay un producto que sea '{c[0]}'"}
    top = [p for s, p in puntos if s == mejor]
    modelos = {(p["marca"], p["modelo"]) for p in top}
    if len(modelos) > 1:
        return {"ambiguo": "hay mas de un producto que coincide; preguntale cual", "filas": top[:6]}
    con = [p for p in top if p["stock"] > 0] or top
    if len(con) > 1 and not any(n(p["color"]) in q for p in con):
        return {"filas": con, "aviso": "el modelo viene en varios colores; si el color importa, preguntalo"}
    return {"filas": [p for p in con if n(p["color"]) in q] or con[:1]}


def politica(c):
    q = set(re.findall(r"[a-z]+", n(" ".join(c))))
    mejor = []
    for t in FAQ:
        kw = set(re.findall(r"[a-z]+", n(" ".join(t["keywords"]) + " " + t["tema"].replace("_", " "))))
        s = len(q & kw)
        if s:
            mejor.append((s, t))
    mejor.sort(key=lambda x: -x[0])
    if not mejor:
        return {"no_se_pudo": f"no hay una politica escrita sobre '{' '.join(c)}'"}
    top = mejor[0][0]
    return {"politicas": [f"{t['tema']}: {t['respuesta']}" for s, t in mejor if s == top][:2]}


def costo_envio(destino):
    from app.core.calculadora import cotizar_envio
    r = cotizar_envio(destino)
    return r.get("monto") if r.get("ok") else None


def resolver(lineas):
    hechos = {}
    for l in lineas:
        t, c = l["tipo"], l["c"]
        try:
            if t == "buscar":
                hechos[l["id"]] = buscar(c)
            elif t == "producto":
                hechos[l["id"]] = producto(c)
            elif t == "rubros":
                hechos[l["id"]] = {"rubros": RUBROS}
            elif t == "politica":
                hechos[l["id"]] = politica(c)
            elif t == "preguntar":
                hechos[l["id"]] = {"preguntar": " ".join(c)}
            elif t == "nada":
                hechos[l["id"]] = {}
        except Exception as e:  # noqa: BLE001
            hechos[l["id"]] = {"no_se_pudo": f"{type(e).__name__}: {e}"}
    # ══ 3. EL CODIGO ARMA LOS ENVIOS Y SUMA ══
    usados = {}
    bloques = {}
    for l in lineas:
        if l["tipo"] != "envio":
            continue
        destino = l["c"][0] if l["c"] else ""
        monto = costo_envio(destino)
        items, faltas = [], []
        for ref, q in re.findall(r"(D\d+)\s*x\s*(\d+)", " ".join(l["c"][1:])):
            filas = (hechos.get(ref) or {}).get("filas") or []
            if not filas:
                faltas.append(f"{ref} no trajo articulos")
                continue
            if (hechos.get(ref) or {}).get("ambiguo"):
                faltas.append(f"{ref} es ambiguo")
                continue
            # un buscar de varios articulos distintos se reparte en orden; uno solo se repite
            i = usados.get(ref, 0)
            p = filas[i % len(filas)] if len(filas) > 1 else filas[0]
            if len(filas) > 1:
                usados[ref] = i + 1
            items.append((p, int(q)))
        sub = sum(p["precio"] * q for p, q in items)
        b = {"destino": destino, "items": items, "subtotal": sub}
        if monto is None:
            b["no_se_pudo"] = f"no se reconoce el destino '{destino}'"
            b["envio"] = None
        else:
            b["envio"] = 0 if sub > 250000 else monto
            b["envio_lista"] = monto
        if faltas:
            b["faltas"] = faltas
        b["total"] = None if (faltas or not items) else sub + (b["envio"] or 0)
        bloques[l["id"]] = b
        hechos[l["id"]] = b
    for l in lineas:
        if l["tipo"] != "cuenta":
            continue
        refs = re.findall(r"D\d+", " ".join(l["c"]))
        bs = [bloques[r] for r in refs if r in bloques] or list(bloques.values())
        en_envio = {ref for b in bs for ref in re.findall(r"D\d+", " ".join(
            next(x for x in lineas if x["id"] == [k for k, v in bloques.items() if v is b][0])["c"][1:]))}
        sueltos = [r for r in refs if r not in bloques and r not in en_envio and (hechos.get(r) or {}).get("filas")
                   and not hechos[r].get("ambiguo")]
        cant = {x["id"]: int(re.sub(r"\D", "", x["c"][1]) or 1) if len(x["c"]) > 1 and x["tipo"] == "producto" else 1
                for x in lineas}
        extra = sum(hechos[r]["filas"][0]["precio"] * cant.get(r, 1) for r in sueltos)
        if any(b["total"] is None for b in bs):
            hechos[l["id"]] = {"no_se_pudo": "no se puede dar el total: a un envio le falta un articulo"}
            continue
        hechos[l["id"]] = {"cuenta_de": refs, "total_general": sum(b["total"] for b in bs) + extra,
                           "productos": sum(b["subtotal"] for b in bs) + extra,
                           "envios": sum(b["envio"] or 0 for b in bs)}
    return hechos


def hechos_texto(lineas, hechos):
    out = []
    for l in lineas:
        h = hechos.get(l["id"])
        if h is None:
            continue
        cab = f"{l['id']} ({l['tipo']} {' | '.join(l['c'])}):"
        if "destino" in h:
            r = [f"{cab} ENVIO A {h['destino']}"]
            r += [f"  {q}x {p['nombre']} {plata(p['precio'])} c/u = {plata(p['precio'] * q)}" for p, q in h["items"]]
            r.append(f"  subtotal {plata(h['subtotal'])}")
            if h.get("no_se_pudo"):
                r.append("  NO SE PUDO: " + h["no_se_pudo"])
            elif h["envio"] == 0:
                r.append(f"  envio GRATIS, el subtotal supera $250.000 (tarifa {plata(h['envio_lista'])})")
            else:
                r.append(f"  envio {plata(h['envio'])}")
            r.append(f"  TOTAL {plata(h['total'])}" if h["total"] is not None else "  SIN TOTAL: falta un articulo")
            for f in h.get("faltas", []):
                r.append("  FALTA: " + f)
            out.append("\n".join(r))
        elif "total_general" in h:
            out.append(f"{cab} productos {plata(h['productos'])} + envios {plata(h['envios'])} = TOTAL GENERAL "
                       f"{plata(h['total_general'])}. 10 por ciento de descuento pagando por transferencia.")
        else:
            r = [cab]
            for k in ("no_existe", "ambiguo", "no_se_pudo", "aviso", "preguntar"):
                if h.get(k):
                    r.append(f"  {k.upper()}: {h[k]}")
            if h.get("filtros"):
                r.append("  filtros aplicados: " + "; ".join(h["filtros"]))
            for p in h.get("filas", []):
                r.append(f"  - {p['nombre']} — {plata(p['precio'])} — stock {p['stock']}")
            if h.get("rubros"):
                r.append("  rubros: " + ", ".join(h["rubros"]) + ". No hay catalogo en PDF ni link.")
            for x in h.get("politicas", []):
                r.append("  " + x)
            out.append("\n".join(r))
    return "\n\n".join(out)


# ══ 4. EL MODELO REDACTA ═════════════════════════════════════════════════════

REDACTA = ("Sos el vendedor de una tienda online de tecnologia de Argentina. Hablas en espanol argentino, con voseo, claro "
           "y sin repetir. Abajo van los DATOS que el sistema consulto para el ultimo mensaje del cliente, y la charla. "
           "Contesta usando SOLO esos datos. No sumes ni calcules: los totales ya vienen hechos; copialos. Si un dato dice "
           "NO SE PUDO, NO_EXISTE, AMBIGUO o FALTA, decilo con naturalidad y pregunta solo eso. Si un filtro no se pudo "
           "aplicar, decilo. No nombres las lineas D1, D2. Los DATOS son lo vigente: si contradicen algo que el vendedor "
           "dijo antes en la charla, mandan los DATOS, y si el vendedor se habia equivocado, decilo y corregilo.")


def correr_uno(k, m, charla):
    pedido = llamar(m, [{"role": "system", "content": PIDE}, {"role": "user", "content": charla}], temp=0.0)
    lineas, malas = parsear(pedido)
    hechos = resolver(lineas)
    datos = hechos_texto(lineas, hechos)
    resp = llamar(m, [{"role": "system", "content": REDACTA},
                      {"role": "user", "content": "DATOS:\n" + datos + "\n\nLA CHARLA:\n" + charla}])
    return {"caso": k, "modelo": m, "pedido": pedido, "lineas": len(lineas), "malas": malas,
            "no_se_pudo": sum(1 for h in hechos.values() if isinstance(h, dict) and (h.get("no_se_pudo") or h.get("faltas"))),
            "datos": datos, "respuesta": resp}


if __name__ == "__main__":
    from banco_pruebas import clon_produccion as CP
    CP.preparar_entorno(); CP.instalar()
    from app.core.contexto_turno import set_current_tienda
    set_current_tienda(CP.TIENDA)
    ped = json.load(open(f"{EXP}/pedidos.json"))
    solo = sys.argv[1:]
    out = []
    with ThreadPoolExecutor(6) as ex:
        futs = [ex.submit(correr_uno, k, m, ped[k]["charla"]) for k in ped for m in (G, D) if not solo or k in solo]
        for f in futs:
            r = f.result()
            out.append(r)
            print(f"listo {r['caso']} {r['modelo'][:6]} lineas {r['lineas']} malas {len(r['malas'])} no_se_pudo {r['no_se_pudo']}", flush=True)
    json.dump(out, open(f"{EXP}/camino_a.json", "w"), ensure_ascii=False, indent=1, default=str)
    with open(f"{EXP}/camino_a.txt", "w") as f:
        for r in out:
            f.write(f"######## {r['caso']} {r['modelo'][:6]}\n--- PIDIO:\n{r['pedido']}\n--- MALAS: {r['malas']}\n"
                    f"--- EL CODIGO DEVOLVIO:\n{r['datos']}\n--- RESPUESTA:\n{r['respuesta']}\n\n")


# ══ v3: LA RED Y LO QUE SIGUE VALIENDO ═══════════════════════════════════════

_NUM = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8}


def pedidos_del_cliente(texto):
    """Cuantos de cada rubro dijo el cliente con un numero pegado al rubro: 'dos mouse', '2 notebooks'."""
    t = n(texto)
    out = {}
    pal = sorted(list(RUBROS) + list(_RUBRO_ALIAS), key=len, reverse=True)
    for m in re.finditer(r"\b(\d+|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho)\s+(" + "|".join(map(re.escape, pal)) + r")", t):
        q = int(m.group(1)) if m.group(1).isdigit() else _NUM[m.group(1)]
        r = m.group(2)
        r = _RUBRO_ALIAS.get(r, r)
        out[r] = max(out.get(r, 0), q)  # el numero mayor dicho para ese rubro: los envios lo reparten
    return out


def rubro_de_linea(l, hechos):
    filas = (hechos.get(l["id"]) or {}).get("filas") or []
    return filas[0]["categoria"] if filas else None


def red(lineas, hechos, ultimo):
    """Problemas de reparto que el codigo ve solo. Vuelve una lista de frases para el modelo."""
    envios = [l for l in lineas if l["tipo"] == "envio"]
    if not envios:
        return []
    llevado, por_linea = {}, {}
    for l in envios:
        for ref, q in re.findall(r"(D\d+)\s*x\s*(\d+)", " ".join(l["c"][1:])):
            por_linea[ref] = por_linea.get(ref, 0) + int(q)
            src = next((x for x in lineas if x["id"] == ref), None)
            if src:
                r = rubro_de_linea(src, hechos)
                if r:
                    llevado[r] = llevado.get(r, 0) + int(q)
    problemas = []
    for r, q in pedidos_del_cliente(ultimo).items():
        if llevado.get(r, 0) != q and (llevado or r in llevado):
            problemas.append(f"el cliente pidio {q} de {r} y tus envios llevan {llevado.get(r, 0)}")
    return problemas


def excluidas_antes(charla):
    """Marcas que el cliente excluyo en mensajes anteriores."""
    previos = [x for x in charla.split("\n\n") if x.startswith("CLIENTE:")]
    t = n(" ".join(previos))
    return [m for m in MARCAS if re.search(r"(no sea|sin|excepto|ni)\s+(?:\w+\s+){0,3}?" + n(m) + r"\b", t)]


def avisar_excluidas(lineas, hechos, charla):
    ex = excluidas_antes(charla)
    if not ex:
        return
    for l in lineas:
        h = hechos.get(l["id"]) or {}
        malas = [p for p in h.get("filas") or [] if p["marca"] in ex]
        if malas:
            h["aviso"] = ((h.get("aviso") or "") + f" OJO: el cliente excluyo antes las marcas {', '.join(ex)} y esto "
                          "trae articulos de esas marcas. Esa condicion sigue valiendo salvo que la haya cambiado.").strip()


ULTIMO = re.compile(r"CLIENTE \(ultimo mensaje\): (.+)$", re.S)


def correr_uno(k, m, charla):
    ultimo = ULTIMO.search(charla).group(1)
    msgs = [{"role": "system", "content": PIDE}, {"role": "user", "content": charla}]
    pedido = llamar(m, msgs, temp=0.0)
    lineas, malas = parsear(pedido)
    hechos = resolver(lineas)
    probs = red(lineas, hechos, ultimo)
    reintento = None
    if probs or malas:
        reintento = probs + [f"esta linea no tiene la forma pedida: {x}" for x in malas]
        pedido = llamar(m, msgs + [{"role": "assistant", "content": pedido},
                                   {"role": "user", "content": "El sistema reviso tus lineas y encontro esto: "
                                    + "; ".join(reintento) + ". Volve a escribir TODAS las lineas corregidas."}], temp=0.0)
        lineas, malas = parsear(pedido)
        hechos = resolver(lineas)
        probs = red(lineas, hechos, ultimo)
    avisar_excluidas(lineas, hechos, charla)
    datos = hechos_texto(lineas, hechos)
    if probs:
        datos += ("\n\nCONFIRMAR ANTES DE CALCULAR: " + "; ".join(probs)
                  + ". No des totales: deci lo que entendiste que va a cada destino y pregunta si esta bien.")
    resp = llamar(m, [{"role": "system", "content": REDACTA},
                      {"role": "user", "content": "DATOS:\n" + datos + "\n\nLA CHARLA:\n" + charla}])
    return {"caso": k, "modelo": m, "pedido": pedido, "lineas": len(lineas), "malas": malas, "reintento": reintento,
            "red_final": probs, "datos": datos, "respuesta": resp}
