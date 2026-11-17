"""EL NEXO DE CONDICION: LO QUE EL CLIENTE PIDE DEL PRODUCTO, ATADO A LA FUENTE O REPREGUNTADO.

Pasado de `banco_pruebas/flujo/nexo_condicion.py` el 17-nov-2026, orden de Martin, tal cual: el banco importa de aca. Le
llega la busqueda que escribio la llamada 0 sobre el rubro que eligieron producto o nombrado. Cuatro piezas: el producto,
lo seguro por codigo, la segunda busqueda por embeddings sobre los campos del rubro, y Jev en lo dudoso. Veredictos:
ata, no hay, no se ata, orden y tope.
"""
import collections
import functools
import re

from . import rubro as NR

# Calibrados en el banco, `banco_pruebas/flujo/embeddings.py` NEXOS: tres campos candidatos.
CANDIDATOS = 3


# Lo que no es un campo de la ficha: plomeria, prosa o lo que ya tiene su propia puerta, el precio y el peso del orden.
_NO_CAMPO = {"id", "stock", "categoria", "precio_ars", "peso_gramos", "descripcion", "descripcion_rica",
             "garantia_detalle", "garantia", "dimensiones", "contenido_caja", "origen", "compat", "specs", "embedding",
             "nombre", "modelo", "tags"}
TEXTO = ("modelo", "nombre", "tags")
SOLO_PRODUCTO = "solo_producto"
NINGUNO = "ninguno"


def _catalogo():
    from app.core.flujo import catalogo as C
    return C


def variantes(v):
    """El plural y el genero del cliente, como `catalogo.atar`: "baratas" es "barato", "roja" es "rojo"."""
    sing = [v[:-len(f)] for f in ("es", "s") if v.endswith(f) and len(v) > 4]
    out = [v] + sing
    out += [x[:-1] + {"o": "a", "a": "o"}[x[-1]] for x in [v] + sing if x[-1:] in ("o", "a") and len(x) >= 4]
    return list(dict.fromkeys(out))


# ══ LA FUENTE DE CADA RUBRO ══════════════════════════════════════════════════
class Fuente:
    def __init__(self, tid):
        self.tid = tid
        C = _catalogo()
        from app.core.filtros_catalogo import DERIVADOS, _valor_crudo, _si_no, campos_filtrables
        from app.core.fuente_producto import specs_config
        self.C, self._valor_crudo, self._si_no = C, _valor_crudo, _si_no
        self.prods = C.productos(tid)
        self.alias = NR.fuente(tid)[1]
        self.tipos = campos_filtrables(tid)
        self.specs = {s["id"]: s for s in specs_config(tid)}
        self.etiquetas = dict(DERIVADOS, **{k: s["etiqueta"] for k, s in self.specs.items()})
        self.por_rubro = collections.defaultdict(list)
        for p in self.prods:
            self.por_rubro[p["categoria"]].append(p)
        self.campos, self.unidades, self.producto, self.busca, self.si_no, self.rubro_ws = {}, {}, {}, {}, {}, {}
        for r, ps in self.por_rubro.items():
            claves = set().union(*(set(p) | set(p.get("specs") or {}) for p in ps)) | set(DERIVADOS)
            campos = {}
            for c in sorted(claves - _NO_CAMPO):
                vs = collections.Counter(C._valores(p, c) for p in ps)
                vs.pop("", None)
                if vs:
                    campos[c] = [v for v, _ in vs.most_common()]
            orden = [c for c in C.PRIORIDAD if c in campos] + [c for c in campos if c not in C.PRIORIDAD]
            self.campos[r] = {c: campos[c] for c in orden}
            # Donde se busca un valor: los campos de texto. Los de si o no se atan por su clave, nunca por su prosa:
            # "color" no es el "si, pantalla tactil color" de una impresora.
            self.busca[r] = [c for c in self.campos[r] if self.tipos.get(c) != "si_no"]
            self.si_no[r] = [c for c in self.campos[r] if self.tipos.get(c) == "si_no" and c in self.specs
                             and any(_si_no(_valor_crudo(p, c)) for p in ps)]
            # Las unidades con que mide cada campo del rubro, de sus propios valores: "2tb", "650w de potencia".
            un = collections.defaultdict(list)
            for c in self.busca[r]:
                for v in self.campos[r][c]:
                    for _, u in re.findall(r"(\d+(?:[.,]\d+)?)\s?([a-z]+)", v):
                        if c not in un[u]:
                            un[u].append(c)
            self.unidades[r] = dict(un)
            # Las palabras que nombran el producto: las del rubro, siempre, y la cabeza de cada alias si no es un valor.
            # "Placa" en "la placa de graficos"; "cooler" en el rubro cooler aunque haya una marca Cooler Master.
            self.rubro_ws[r] = set(C.n(r).split())
            cab = set()
            for a in self.alias.get(r, []):
                ws = [w for w in C.n(a).split() if w not in C._RELLENO]
                if ws and not re.search(r"\d", ws[0]):
                    cab.add(ws[0])
            self.producto[r] = {w for w in cab if not self.es_valor(w, r)}

    def es_valor(self, w, r):
        """Si la palabra es un valor de un campo de texto del rubro, no del nombre ni de las etiquetas."""
        return any(self.C._contiene(" | ".join(self.campos[r][c]), v) for c in self.busca[r] for v in variantes(w))

    def con_stock(self, r):
        return [p for p in self.por_rubro[r] if self.C.con_stock(p)]


# ══ PIEZAS 1 Y 2: EL PRODUCTO Y LO SEGURO ════════════════════════════════════
def _palabra_producto(w, cab):
    return any(w == p or (min(len(w), len(p)) >= 4 and (w.startswith(p) or p.startswith(w))) for p in cab)


def _unidad(u, r, fx):
    """La unidad de la tienda que el cliente dijo: igual, o la misma inicial si en el rubro hay una sola unidad corta con
    esa letra: "teras" es tb, "gigas" es gb, "watts" es w."""
    un = fx.unidades.get(r, {})
    if not u:
        return ""
    if u in un:
        return u
    cortas = [x for x in un if len(x) <= 3 and x[0] == u[0] and not x.isdigit()]
    return cortas[0] if len(cortas) == 1 else ""


def _hallar(frase, r, fx, campos=None):
    """El primer campo del rubro cuyos valores traen la frase, con plural y genero: (campo, valor) o None."""
    C = fx.C
    orden = list(campos or fx.busca[r]) + ([] if campos else list(TEXTO))
    for c in orden:
        vs = fx.campos[r].get(c) if c in fx.campos[r] else [C._valores(p, c) for p in fx.por_rubro[r]]
        junto = " | ".join(vs or [])
        for v in variantes(frase):
            if C._contiene(junto, v):
                return c, v
    return None


_NIEGA_PREVIA = re.compile(r"^(?:no|sin|ni|excepto|salvo|menos)$")
_GRAMATICA = {"que", "sea", "sean", "si", "mas"}


def _si_no_por_clave(frase, r, fx):
    """El campo de si o no del rubro que la frase nombra entera por una de sus claves: "sumergible", "rgb"."""
    for c in fx.si_no[r]:
        m = fx.specs[c]["rx_pregunta"].search(frase)
        if m and m.group(0).strip() == frase:
            return c
    return ""


def _niega(tokens, i, usados):
    """Si la parte que empieza en i esta negada: "no chinos", "sin cable", "que no sea genius", "-redragon". Devuelve los
    indices de las palabras de la negacion."""
    if tokens[i].startswith("-"):
        return [], True
    j, neg = i - 1, []
    while j >= 0 and j not in usados and tokens[j] in ("sea", "sean", "que"):
        neg.append(j)
        j -= 1
    if j >= 0 and j not in usados and _NIEGA_PREVIA.match(tokens[j]):
        return neg + [j], True
    return [], False


def seguro(busqueda, r, fx):
    """PIEZAS 1 Y 2. [(parte, item)] de lo que el codigo ata solo, y las partes que quedan para la busqueda: [texto]."""
    C = fx.C
    texto = C.n(busqueda)
    items = []
    t = C._TOPE.search(texto)
    if t:
        items.append({"parte": t.group(0), "veredicto": "tope", "lado": "min" if t.group(1) in ("mas de", "desde", "minimo")
                      else "max", "valor": C._monto(t.group(2), t.group(3)), "por": "codigo"})
        texto = (texto[:t.start()] + " " + texto[t.end():]).strip()
    tokens = texto.split()
    usados = set()
    # PIEZA 1: el producto.
    cab = fx.producto[r]
    if tokens and not re.search(r"\d", tokens[0]) and not fx.es_valor(tokens[0].lstrip("-"), r):
        usados.add(0)
    for i, w in enumerate(tokens):
        if _palabra_producto(w, fx.rubro_ws[r] | cab):
            usados.add(i)
    relleno = {i for i, w in enumerate(tokens) if w in C._RELLENO}
    # PIEZA 2a: los numeros.
    for i, w in enumerate(tokens):
        if i in usados:
            continue
        m = re.fullmatch(r"(\d+(?:[.,]\d+)?)([a-z]*)", w)
        if not m:
            continue
        num, u = m.group(1), m.group(2)
        sig = i + 1 if not u and i + 1 < len(tokens) and i + 1 not in usados and tokens[i + 1].isalpha() \
            and tokens[i + 1] not in C._RELLENO else None
        if sig is not None:
            u = tokens[sig]
        unidad = _unidad(u, r, fx)
        partes = [i] + ([sig] if sig is not None else [])
        if unidad:
            v = f"{num}{unidad}"
            campos = fx.unidades[r][unidad]
            hit = _hallar(v, r, fx, campos)
            if hit:
                items.append({"parte": " ".join(tokens[k] for k in partes), "veredicto": "ata", "campo": hit[0],
                              "valor": hit[1], "niega": False, "por": "codigo"})
            else:
                items.append({"parte": " ".join(tokens[k] for k in partes), "veredicto": "no hay", "campo": campos[0],
                              "valor": v, "por": "codigo"})
            usados.update(partes)
            continue
        if u:
            # Una medida en una unidad que ningun campo del rubro usa: "24 pulgadas" en un monitor.
            items.append({"parte": " ".join(tokens[k] for k in partes), "veredicto": "no se ata", "por": "codigo"})
            usados.update(partes)
            continue
        # Un numero solo, pegado a la palabra de antes: "ryzen 5", "wifi 6".
        j = i - 1
        if j >= 0 and j not in usados and tokens[j].isalpha():
            hit = _hallar(f"{tokens[j]} {num}", r, fx)
            if hit:
                items.append({"parte": f"{tokens[j]} {num}", "veredicto": "ata", "campo": hit[0], "valor": hit[1],
                              "niega": False, "por": "codigo"})
                usados.update([i, j])
                continue
            # El campo dice la palabra con otro numero de las mismas cifras: "wifi 6" donde dice "wifi 5" no hay.
            rx = re.compile(rf"(?<![a-z0-9]){re.escape(tokens[j])}\s?\d{{{len(num.split('.')[0])}}}(?![\d])")
            otro = next((c for c, vs in fx.campos[r].items() if any(rx.search(v) for v in vs)), None)
            if otro:
                items.append({"parte": f"{tokens[j]} {num}", "veredicto": "no hay", "campo": otro,
                              "valor": f"{tokens[j]} {num}", "por": "codigo"})
                usados.update([i, j])
                continue
            hit = _hallar(tokens[j], r, fx)
            if hit:
                items.append({"parte": f"{tokens[j]} {num}", "veredicto": "ata", "campo": hit[0], "valor": hit[1],
                              "niega": False, "por": "codigo"})
                usados.update([i, j])
    # PIEZA 2b: el orden, con las palabras de lo que `catalogo.ORDEN` sabe ordenar.
    ordenes = {k.split()[-1]: k for k in C.ORDEN}
    for i, w in enumerate(tokens):
        if i in usados:
            continue
        k = next((ordenes[x] for x in variantes(w) if x in ordenes), None)
        if k:
            # "el mas barato", "lo mas liviano": la gramatica del orden va con el.
            ks = [i]
            while ks[0] > 0 and ks[0] - 1 not in usados and tokens[ks[0] - 1] in ("mas", "el", "la", "lo", "los", "las"):
                ks.insert(0, ks[0] - 1)
            items.append({"parte": " ".join(tokens[x] for x in ks), "veredicto": "orden", "valor": k, "por": "codigo"})
            usados.update(ks)
    # PIEZA 2c: los valores de la tienda, la frase mas larga primero; y los campos de si o no por su clave.
    for largo in (3, 2, 1):
        for i in range(len(tokens) - largo + 1):
            ks = list(range(i, i + largo))
            if any(k in usados for k in ks) or ks[0] in relleno or ks[-1] in relleno \
                    or tokens[ks[0]] in _GRAMATICA or _NIEGA_PREVIA.match(tokens[ks[0]]):
                continue
            frase = " ".join(tokens[k] for k in ks).lstrip("-")
            if not frase or frase.isdigit():
                continue
            neg_ks, niega = _niega(tokens, i, usados)
            si_no = _si_no_por_clave(frase, r, fx)
            hit = _hallar(frase, r, fx)
            if hit and not (si_no and hit[0] in TEXTO):
                items.append({"parte": " ".join(tokens[k] for k in neg_ks[::-1] + ks), "veredicto": "ata",
                              "campo": hit[0], "valor": hit[1], "niega": niega, "por": "codigo"})
            elif si_no:
                hay = any(fx._si_no(fx._valor_crudo(p, si_no)) == "si" for p in fx.por_rubro[r])
                items.append({"parte": " ".join(tokens[k] for k in neg_ks[::-1] + ks),
                              "veredicto": "ata" if hay else "no hay", "campo": si_no, "valor": "si", "niega": niega,
                              "si_no": True, "por": "codigo"})
            else:
                continue
            usados.update(ks + neg_ks)
    # Lo que queda: las tiras seguidas de palabras sin atar, para la busqueda.
    resto, tira = [], []
    for i, w in enumerate(tokens):
        if i in usados:
            if tira:
                resto.append(tira)
            tira = []
        else:
            tira.append(i)
    if tira:
        resto.append(tira)
    partes = []
    for tira in resto:
        ws = [tokens[k] for k in tira]
        while ws and ws[0] in C._RELLENO:
            ws = ws[1:]
        while ws and ws[-1] in C._RELLENO:
            ws = ws[:-1]
        # Una palabra que nombra un campo junto a otra ya atada, "ram" en "16gb ram", no pide nada mas.
        atados = {it.get("campo") for it in items}
        if ws and all(w in C._RELLENO or w == (c or "").replace("_", " ")
                      or (c in fx.specs and fx.specs[c]["rx_pregunta"].search(w)) for w in ws for c in atados
                      if c) and atados - {None}:
            continue
        if ws:
            partes.append(" ".join(ws))
    return items, partes


# ══ PIEZA 3: LA SEGUNDA BUSQUEDA ═════════════════════════════════════════════
ORDEN_DOCS = {"precio": ("mas barato", "mas caro"), "peso": ("mas liviano", "mas pesado")}


def etiqueta(c, fx):
    return fx.etiquetas.get(c) or c.replace("_", " ")


def docs_campo(r, fx):
    """[(clave, documento)]: un documento por campo del rubro, su etiqueta y sus valores; y uno por orden."""
    out = [(f"campo|{c}", f"{r}, {etiqueta(c, fx)}: {', '.join(vs[:15])}") for c, vs in fx.campos[r].items()]
    out += [(f"orden|{k}", f"{r}, ordenar por {k}: {' o '.join('el ' + x for x in xs)}") for k, xs in ORDEN_DOCS.items()]
    return out


def docs_valor(r, fx):
    """[(clave, documento)]: un documento por valor de cada campo, la otra variante."""
    out = [(f"campo|{c}", f"{r}, {etiqueta(c, fx)}: {v}") for c, vs in fx.campos[r].items() for v in vs[:15]]
    out += [(f"orden|{k}", f"{r}, el {x}") for k, xs in ORDEN_DOCS.items() for x in xs]
    return out


VARIANTES = {
    "V1 segmento solo, documento por campo": {"consulta": lambda s, r, b: s, "docs": docs_campo},
    "V2 segmento con rubro, documento por campo": {"consulta": lambda s, r, b: f"{r}: {s}", "docs": docs_campo},
    "V3 busqueda entera, documento por campo": {"consulta": lambda s, r, b: b, "docs": docs_campo},
    "V4 segmento con rubro, documento por valor": {"consulta": lambda s, r, b: f"{r}: {s}", "docs": docs_valor},
}
VIVA = "V2 segmento con rubro, documento por campo"


class Puntajes:
    """Los puntajes de la segunda busqueda: {variante: {rubro: {consulta: [(clave, puntaje)]}}}, de `vectores`."""

    def __init__(self, p=None):
        self.p = p if p is not None else {}

    def candidatos(self, variante, r, consulta, k):
        xs = self.p.get(variante, {}).get(r, {}).get(consulta)
        if xs is None:
            return None
        vistos = []
        for clave, _ in xs:
            if clave not in vistos:
                vistos.append(clave)
            if len(vistos) == k:
                break
        return vistos


# ══ PIEZA 4: JEV ═════════════════════════════════════════════════════════════
def opciones(r, cands, fx):
    """La lista cerrada de una parte: los valores reales de los campos candidatos, los ordenes, solo el producto o
    ninguno. {clave: descripcion}."""
    out = {}
    for cl in cands:
        tipo, c = cl.split("|", 1)
        if tipo == "orden":
            for x in ORDEN_DOCS[c]:
                out[f"orden|{x}"] = f"que sea el {x}"
        elif fx.tipos.get(c) == "si_no":
            out[f"{c}|si"] = f"{etiqueta(c, fx)}: si"
            out[f"{c}|no"] = f"{etiqueta(c, fx)}: no"
        else:
            for v in fx.campos[r][c][:8]:
                out[f"{c}|{v}"] = f"{etiqueta(c, fx)}: {v}"
    out[SOLO_PRODUCTO] = "esas palabras solo nombran el producto, u otro producto, sin pedir nada de como tiene que ser"
    out[NINGUNO] = "pide algo de como tiene que ser el producto que ninguna de estas opciones dice"
    return out


def de_jev(parte, eleccion, r, fx):
    """Lo que eligio Jev, como item. None si solo nombra el producto."""
    if eleccion in (None, NINGUNO) or "|" not in str(eleccion):
        return None if eleccion == SOLO_PRODUCTO else {"parte": parte, "veredicto": "no se ata",
                                                       "por": "jev" if eleccion else "sin jev"}
    c, v = eleccion.split("|", 1)
    if c == "orden":
        return {"parte": parte, "veredicto": "orden", "valor": v, "por": "jev"}
    if c not in fx.campos[r]:
        return {"parte": parte, "veredicto": "no se ata", "por": "jev"}
    if fx.tipos.get(c) == "si_no":
        hay = any(fx._si_no(fx._valor_crudo(p, c)) == v for p in fx.por_rubro[r])
        return {"parte": parte, "veredicto": "ata" if hay else "no hay", "campo": c, "valor": v, "niega": False,
                "si_no": True, "por": "jev"}
    return {"parte": parte, "veredicto": "ata", "campo": c, "valor": v, "niega": False, "por": "jev"}


# ══ EL NEXO ══════════════════════════════════════════════════════════════════
class Nexo:
    def __init__(self, tid, puntajes=None, jev=None, variante=VIVA, k=CANDIDATOS):
        """`puntajes` de la segunda busqueda y `jev`, {(rubro, busqueda, parte): eleccion}: los dos de `vectores` y
        `jev` en produccion, de lo grabado en el banco."""
        self.fx = fuente(tid)
        self.pt = Puntajes(puntajes)
        self.variante, self.k = variante, k
        self.jev = jev if jev is not None else {}
        self.oraculo = None

    def condicion(self, busqueda, r):
        """{"items", "dudosas": [(parte, candidatos)]} de una busqueda sobre el rubro r."""
        fx = self.fx
        items, partes = seguro(busqueda, r, fx)
        dudosas = []
        for parte in partes:
            q = VARIANTES[self.variante]["consulta"](parte, r, busqueda)
            cands = self.pt.candidatos(self.variante, r, q, self.k) or []
            dudosas.append((parte, cands))
            if self.oraculo:
                it = self.oraculo(parte, cands)
            else:
                it = de_jev(parte, self.jev.get((r, busqueda, parte)), r, fx)
            if it:
                items.append(it)
        return {"items": self.depurar(r, items), "dudosas": dudosas}

    def depurar(self, r, items):
        """Lo atado que vale para todo el rubro no dice nada y se saca: "pc" en "fuente de alimentacion pc", las
        etiquetas que son otra forma de nombrar el producto. Lo atado que no deja ningun producto con stock es no hay:
        "no chinos" donde todo se fabrica en China."""
        out = []
        todos = self.fx.por_rubro[r]
        for it in items:
            if it["veredicto"] == "ata":
                f = _filtro(it)
                n = sum(_cumple(p, f, self.fx) for p in todos)
                if n == len(todos):
                    continue
                if not any(_cumple(p, f, self.fx) for p in self.fx.con_stock(r)):
                    it = dict(it, veredicto="no hay")
            out.append(it)
        return out

    def filas(self, r, items):
        """Los productos con stock que cumplen lo atado, uno por modelo, en el orden pedido."""
        C = self.fx.C
        filtros = [_filtro(it) for it in items if it["veredicto"] in ("ata", "tope")]
        quedan = [p for p in self.fx.con_stock(r) if all(_cumple(p, f, self.fx) for f in filtros)]
        orden = next((it["valor"] for it in items if it["veredicto"] == "orden"), None)
        if orden:
            campo, sentido = C.ORDEN[orden]
            quedan.sort(key=lambda p: sentido * float(p.get(campo) or 0))
        out, vistos = [], set()
        for p in quedan:
            m = (p.get("marca"), p.get("modelo") or p["id"])
            if m not in vistos:
                vistos.add(m)
                out.append(p)
        return out


def _filtro(it):
    if it["veredicto"] == "tope":
        return {"tope": (it["lado"], it["valor"])}
    return {"campo": it["campo"], "valor": it["valor"], "niega": it.get("niega", False), "si_no": it.get("si_no", False)}


def _cumple(p, f, fx):
    if f.get("si_no"):
        hay = fx._si_no(fx._valor_crudo(p, f["campo"])) == f["valor"]
        return not hay if f["niega"] else hay
    return fx.C.cumple(p, f)


def no_filtra(it, r, nx):
    """Un item que no deja afuera ningun producto del rubro: lo que vale para todo el rubro."""
    if it["veredicto"] not in ("ata",):
        return False
    return len(nx.filas(r, [it])) == len(nx.filas(r, []))



def rubro_de(l, por_id):
    """(rubro, motivo): el rubro sobre el que corre la condicion, o None con el motivo por el que no corre."""
    nom = next((x for x in l.nexos if x.nexo == "nombrado"), None)
    if nom and nom.veredicto == "coincide":
        return None, "nombrado exists"
    if nom and nom.veredicto == "ambiguo" and nom.datos:
        return nom.datos[0]["rubro"], ""
    prod = next((x for x in l.nexos if x.nexo == "producto"), None)
    if prod and prod.veredicto == "coincide":
        return por_id[prod.elegido]["categoria"], ""
    return None, "el producto no se vende"


@functools.lru_cache(maxsize=None)
def fuente(tid):
    """La fuente de cada rubro de la tienda, una vez por proceso."""
    return Fuente(tid)

