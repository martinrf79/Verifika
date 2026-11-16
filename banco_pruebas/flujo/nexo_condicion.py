"""EL NEXO DE CONDICION: LO QUE EL CLIENTE PIDE DEL PRODUCTO, ATADO A LA FUENTE O REPREGUNTADO (16-nov-2026).

Orden de Martin del 16-nov, FICHA 98 seccion 4, el ultimo de los cinco nexos. Le llega la busqueda que tradujo la
llamada 0, "mouse inalambrico barato", "monitor 27 pulgadas 144hz", sobre el rubro que ya eligio el nexo de producto o el
nombrado. Devuelve, por cada parte de la busqueda que no es el producto, uno de los tres veredictos que decidio Martin:

  ata         es un valor de un campo de la tienda en ese rubro: filtra, y la linea se presupuesta.
  no hay      el campo existe en el rubro y ningun producto trae ese valor: se dice, con lo mas cercano.
  no se ata   ningun campo de la fuente lo dice: se repregunta.
Y lo que el codigo ya sabe hacer: orden, de `catalogo.ORDEN`, y tope de plata, de `catalogo._TOPE`.

CUATRO PIEZAS, cada una hace una sola cosa:

  PIEZA 1, EL PRODUCTO. La primera palabra es el producto pedido, como en `nexo_rubro`, salvo que sea un valor de la
  tienda, "epson tinta continua", o un numero. Tambien son producto las palabras del nombre del rubro y la cabeza de
  cada alias: "placa" en "la placa de graficos". Lo demas es condicion.

  PIEZA 2, LO SEGURO, EL CODIGO. Sin modelo:
    - el tope de plata, con el patron de produccion;
    - un numero con su unidad se compara contra los campos del rubro que traen esa unidad: "2 teras" es 2tb en el
      almacenamiento; si el campo existe y el valor no, no hay; si ningun campo del rubro mide en esa unidad, "24
      pulgadas" en un monitor, no se ata;
    - una palabra o frase que es valor de un campo del rubro ata ahi, con plural y genero, en el orden de
      `catalogo.PRIORIDAD`; despues el modelo, el nombre y las etiquetas. Negada si la precede "no", "sin" o un guion;
    - un campo de si o no nombrado por una de sus claves de `specs_preguntables`, "sumergible", ata por su veredicto;
    - una palabra de las que `catalogo.ORDEN` sabe ordenar, "barata", "liviano", es ese orden.

  PIEZA 3, LA SEGUNDA BUSQUEDA, EMBEDDINGS. Lo que el codigo no ato, "economico", "con luces", "que no haga ruido", contra
  los campos de ese rubro: un documento por campo con su etiqueta y sus valores, y los dos ordenes. Salen los campos
  candidatos. Los embeddings no eligen el valor: "24" y "27 pulgadas" les dan casi lo mismo.

  PIEZA 4, JEV EN LO DUDOSO. Una pregunta de lista cerrada por parte, todas las de un mensaje en una llamada: los valores
  reales de los campos candidatos, los ordenes, "solo nombra el producto", o "ninguno". Ninguno es no se ata. Sin Jev
  grabado, lo dudoso es no se ata.

EL BORDE CON EL NOMBRADO: si el nombrado dio exists, manda el nombrado y este nexo no corre. Si dio ambiguo o no hay,
corre sobre el rubro. Si el producto no se vende, no corre.

    python3 banco_pruebas/flujo/nexo_condicion.py --base           # la base: `catalogo.atar` de produccion, sin embeddings
    python3 banco_pruebas/flujo/nexo_condicion.py --embeddings     # los vectores que falten, con la gratis
    python3 banco_pruebas/flujo/nexo_condicion.py --calibrar       # las variantes de la busqueda, con Jev perfecto
    python3 banco_pruebas/flujo/nexo_condicion.py --correr-jev     # Jev en lo dudoso, grabado
    python3 banco_pruebas/flujo/nexo_condicion.py [--ver] [--sin-jev]   # califica los tres bancos, sin gasto
"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entorno import filas_llamada0, grabado  # noqa: E402

import nexo_rubro as NR  # noqa: E402
import embeddings as EMB  # noqa: E402
from embeddings import NEXOS as _B  # noqa: E402

TID = NR.TID
PUNTAJES = grabado("nexo_condicion_puntajes.json")
JEV = grabado("nexo_condicion_jev.jsonl")
_CONF = _B["condicion"]
CANDIDATOS = _CONF["candidatos"].get("campos", 3)
VARIANTE = _CONF.get("variante", "segmento con rubro, documento por campo")

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
    def __init__(self):
        NR.instalar()
        C = _catalogo()
        from app.core.filtros_catalogo import DERIVADOS, _valor_crudo, _si_no, campos_filtrables
        from app.core.fuente_producto import specs_config
        self.C, self._valor_crudo, self._si_no = C, _valor_crudo, _si_no
        self.prods = C.productos(TID)
        self.alias = NR.fuente()[1]
        self.tipos = campos_filtrables(TID)
        self.specs = {s["id"]: s for s in specs_config(TID)}
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
    """Los puntajes grabados: {variante: {rubro: {consulta: [(clave, puntaje)]}}}."""

    def __init__(self):
        self.p = json.load(open(PUNTAJES, encoding="utf-8")) if os.path.exists(PUNTAJES) else {}

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


def jev_grabado():
    out = {}
    if os.path.exists(JEV):
        for x in map(json.loads, open(JEV, encoding="utf-8")):
            out.update({(x["rubro"], x["busqueda"], p): e for p, e in x["partes"].items()})
    return out


# ══ EL NEXO ══════════════════════════════════════════════════════════════════
class Nexo:
    def __init__(self, variante=VIVA, k=CANDIDATOS, jev=True):
        self.fx = Fuente()
        self.pt = Puntajes()
        self.variante, self.k = variante, k
        self.jev = jev_grabado() if jev else {}
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


# ══ LA BASE: `catalogo.atar` DE PRODUCCION, SIN EMBEDDINGS NI JEV ════════════
def base(busqueda, r, fx):
    """Lo que hace hoy produccion con la busqueda entera menos el producto: `catalogo.atar` sobre lo que queda."""
    C = fx.C
    tokens = C.n(busqueda).split()
    cab = fx.producto[r]
    resto = [w for i, w in enumerate(tokens) if not (i == 0 or _palabra_producto(w, cab))]
    if not resto:
        return []
    f = C.atar(" ".join(resto), fx.por_rubro[r], TID)
    if "tope" in f:
        return [{"parte": " ".join(resto), "veredicto": "tope", "lado": f["tope"][0], "valor": f["tope"][1]}]
    if "sin_campo" in f:
        return [{"parte": " ".join(resto), "veredicto": "no se ata"}]
    partes = f.get("todas") or f.get("ninguno_de") or [f]
    out = []
    for x in partes:
        hay = any(C.cumple(p, x) for p in fx.con_stock(r))
        out.append({"parte": " ".join(resto), "veredicto": "ata" if hay else "no hay", "campo": x["campo"],
                    "valor": x["valor"], "niega": x.get("niega", False) or "ninguno_de" in f, "si_no": x.get("si_no")})
    return out


# ══ LOS BANCOS ═══════════════════════════════════════════════════════════════
def _lineas_flujo(l0, idx, por_id, jev_tema, jev_prod):
    """[(clave, linea, rubro o None, motivo)] de un banco: el rubro que decidieron el nexo de producto y el nombrado."""
    import flujo_nuevo as F
    out = []
    for clave, ls in l0.items():
        lineas = [F.Linea(l.fragmento, l.busqueda, l.destino) for l in ls]
        frags, busqs = [l.fragmento for l in lineas], [l.busqueda for l in lineas]
        lineas, _, _ = F.flujo(lineas, idx, por_id, lambda f: jev_tema(clave, frags.index(f)),
                               lambda b: jev_prod(clave, busqs.index(b), b))
        for l in lineas:
            if not l.busqueda:
                continue
            out.append((clave, l) + rubro_de(l, por_id))
    return out


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


def banco_140():
    import flujo_nuevo as F
    import nexo_tema as NT
    idx = F.Indice()
    por_id = {f["id"]: f for f in idx.filas}
    vd, vp = NT.veredictos("jev", "1"), NR.veredictos_jev()
    return _lineas_flujo(F.llamada0(), idx, por_id, lambda c, i: vd.get((c[0], c[1], i)),
                         lambda c, i, b: vp.get((c[0], "flujo", c[1], b)))


def banco_reales(suf):
    """Las lineas de `reales.py`, "reales" o "reales525", con sus grabaciones."""
    import flujo_nuevo as F
    idx = F.Indice()
    p = json.load(open(grabado(f"{suf}_puntajes.json"), encoding="utf-8"))
    idx.q = dict(idx.q, **p["producto"])
    idx.temas.q = dict(idx.temas.q, **p["tema"])
    por_id = {f["id"]: f for f in idx.filas}
    l0 = {}
    for r in filas_llamada0(f"{suf}_llamada0.jsonl", (suf,)):
        l0[r["id"]] = [F.Linea(str(x.get("fragmento") or ""), str(x.get("busqueda") or "").strip(),
                               str(x.get("destino") or "").strip()) for x in r["salida"]["lineas"]]
    jp = grabado(f"{suf}_jev.jsonl")
    jv = {r["id"]: r["respuestas"] for r in map(json.loads, open(jp))} if os.path.exists(jp) else {}
    return _lineas_flujo(l0, idx, por_id, lambda c, i: jv.get(c, {}).get(f"t{i}"),
                         lambda c, i, b: jv.get(c, {}).get(f"p{i}"))


def esperado_525():
    """{id: {rubro: [condicion]}} de las 365, por la agenda a mano."""
    import nexo_condicion_vara as V
    import reales as RE
    casos, _ = RE.casos_525()
    out = {}
    for cid, _, _ in casos:
        c, t, _ = cid.split(".")
        esp = collections.defaultdict(list)
        for p in RE.preguntas_525(c, t):
            if p["accion"] != "buscar" or p["rubro"] == "toda la tienda" or p.get("entre_lo_mostrado"):
                continue
            esp[p["rubro"]] += [V.DE_LA_AGENDA[x] for x in p.get("condiciones", [])]
            if p.get("orden") and p["orden"] != "nada":
                esp[p["rubro"]].append(V.ORDEN_DE_LA_AGENDA[p["orden"]])
        out[cid] = dict(esp)
    return out


# ══ LA VARA ══════════════════════════════════════════════════════════════════
def acepta(alt, it, r, nx):
    v = it["veredicto"]
    pal = alt.split()
    if alt == "trivial":
        return v == "no se ata" or no_filtra(it, r, nx)
    if alt == "no se ata":
        return v == "no se ata"
    if pal[0] == "ata":
        return v == "ata" and not it.get("niega") and it["campo"] in pal[1:]
    if pal[0] == "niega":
        return v == "ata" and it.get("niega") and it["campo"] in pal[1:]
    if alt.startswith("no hay"):
        return v == "no hay" and it["campo"] in pal[2:]
    if pal[0] == "orden":
        return v == "orden" and it["valor"] == " ".join(pal[1:])
    if pal[0] == "tope":
        return v == "tope" and it["lado"] == pal[1]
    return False


def comparar(esperado, items, r, nx):
    """Cuenta de una linea: condiciones bien y perdidas; filtros inventados y repreguntas de mas."""
    c = collections.Counter()
    hechas = [False] * len(esperado)
    malos = []
    for it in items:
        # Primero la condicion que no es trivial: "sonido envolvente" no se ata es la de envolvente, no la de gamer. Una
        # repregunta cubre todas las partes que no se atan de la misma tira: "ninos antigolpes".
        libres = sorted((j for j, e in enumerate(esperado) if not hechas[j] and any(acepta(a, it, r, nx) for a in e)),
                        key=lambda j: "trivial" in esperado[j])
        if libres and it["veredicto"] == "no se ata":
            for j in [x for x in libres if "trivial" not in esperado[x]] or libres[:1]:
                hechas[j] = True
            continue
        k = libres[0] if libres else None
        if k is None:
            k = next((j for j, e in enumerate(esperado) if any(acepta(a, it, r, nx) for a in e)), None)
        if k is not None:
            hechas[k] = True
            continue
        if it["veredicto"] == "no se ata":
            c["repregunta de mas"] += 1
            malos.append(f"repregunta de mas '{it['parte']}'")
        else:
            c["filtro inventado"] += 1
            malos.append(f"inventa {it['veredicto']} {it.get('campo') or ''} {it.get('valor')} por '{it['parte']}'")
    for j, e in enumerate(esperado):
        c["condiciones"] += 1
        if hechas[j] or "trivial" in e:
            c["condiciones bien"] += 1
        else:
            c["condiciones perdidas"] += 1
            malos.append(f"pierde {' / '.join(e)}")
    return c, malos


def _resumen(it):
    v = it["veredicto"]
    if v in ("ata", "no hay"):
        return f"{v}{' no' if it.get('niega') else ''} {it['campo']}={it['valor']}"
    if v in ("orden", "tope"):
        return f"{v} {it.get('lado', '')}{it['valor']}"
    return f"no se ata '{it['parte']}'"


def calificar(nx=None, ver=False, callado=False, motor="nexo"):
    import nexo_condicion_vara as V
    nx = nx or Nexo()
    tot = collections.Counter()
    salida = {}

    def correr(b, r, esp):
        nx.actual = (r, esp)
        if motor == "base":
            return {"items": base(b, r, nx.fx), "dudosas": []}
        return nx.condicion(b, r)

    # LAS 140, por busqueda.
    c, fallas = collections.Counter(), []
    for clave, l, r, motivo in banco_140():
        esp = V.LAS_140.get(l.busqueda, "fuera")
        if esp == "fuera":
            continue
        c["lineas"] += 1
        if r is None:
            c[f"no corre: {motivo}"] += 1
            if esp:
                c["no corre y la vara tiene condiciones"] += 1
            continue
        if esp is None:
            c["corre sobre algo que no se vende"] += 1
            continue
        c["lineas donde corre"] += 1
        res = correr(l.busqueda, r, esp)
        cc, malos = comparar(esp, res["items"], r, nx)
        c.update(cc)
        c["lineas sin falla"] += not malos
        c["dudosas"] += len(res["dudosas"])
        salida[f"140 {clave[0]} {clave[1]} {l.busqueda}"] = {"rubro": r, "items": res["items"], "dudosas": res["dudosas"]}
        if malos or ver:
            fallas.append((f"{clave[1]} '{l.busqueda}' [{r}]", [_resumen(x) for x in res["items"]], malos))
    tot.update({f"140 {k}": v for k, v in c.items()})
    if not callado:
        _imprimir("LAS 140, nuevas70 y nuevas70b, con la vara por busqueda", c, fallas, ver)

    # LOS REALES Y LAS 365, por mensaje y rubro.
    for nombre, suf, esperado in (("LOS 40 REALES", "reales", V.REALES), ("LAS 365 DE traduccion58", "reales525",
                                                                         esperado_525())):
        c, fallas = collections.Counter(), []
        por_msj = collections.defaultdict(list)
        for clave, l, r, motivo in banco_reales(suf):
            por_msj[clave].append((l, r))
        for cid, esp in esperado.items():
            for rub, conds in esp.items():
                ls = [(l, r) for l, r in por_msj.get(cid, []) if r == rub]
                c["rubros"] += 1
                if not ls:
                    c["rubro sin linea que corra"] += 1
                    continue
                items = []
                for l, r in ls:
                    res = correr(l.busqueda, r, conds)
                    items += res["items"]
                    c["dudosas"] += len(res["dudosas"])
                cc, malos = comparar(conds, items, rub, nx)
                if cc["condiciones perdidas"] and not any(sum(map(len, seguro(l.busqueda, r, nx.fx))) for l, r in ls):
                    # La busqueda trae solo el producto: la condicion se perdio en la llamada 0, antes del nexo.
                    c["perdidas en la llamada 0"] += cc["condiciones perdidas"]
                c.update(cc)
                c["rubros sin falla"] += not malos
                if malos or ver:
                    fallas.append((f"{cid} [{rub}] {[l.busqueda for l, _ in ls]}", [_resumen(x) for x in items], malos))
        tot.update({f"{suf} {k}": v for k, v in c.items()})
        if not callado:
            _imprimir(nombre + ", con la vara por mensaje y rubro", c, fallas, ver)
    if not callado and motor == "nexo":
        json.dump(salida, open(grabado("nexo_condicion_respuestas.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1, default=str)
    return tot


def _imprimir(titulo, c, fallas, ver):
    print(f"\n{titulo}")
    claves = [k for k in ("lineas", "lineas donde corre", "lineas sin falla", "rubros", "rubros sin falla", "condiciones", "condiciones bien",
                          "condiciones perdidas", "perdidas en la llamada 0", "filtro inventado", "repregunta de mas", "dudosas") if k in c]
    print("  " + " · ".join(f"{k} {c[k]}" for k in claves))
    otros = sorted(k for k in c if k not in claves)
    if otros:
        print("  " + " · ".join(f"{k} {c[k]}" for k in otros))
    for t, its, malos in fallas:
        print(f"    {t}: {its}")
        if malos:
            print(f"      {'; '.join(malos)}")


# ══ LOS VECTORES, LA CALIBRACION Y JEV ═══════════════════════════════════════
def _todas_las_lineas():
    out = [("140", l.busqueda, r) for _, l, r, _ in banco_140() if r]
    for suf in ("reales", "reales525"):
        out += [(suf, l.busqueda, r) for _, l, r, _ in banco_reales(suf) if r]
    return list(dict.fromkeys(out))


def embeddings(variantes_=None):
    fx = Fuente()
    cache = EMB.cargar()
    lineas = _todas_las_lineas()
    p = json.load(open(PUNTAJES, encoding="utf-8")) if os.path.exists(PUNTAJES) else {}
    for nombre in variantes_ or [x for x in sys.argv[2:] if x in VARIANTES] or list(VARIANTES):
        v = VARIANTES[nombre]
        docs = {r: v["docs"](r, fx) for r in fx.campos}
        consultas = collections.defaultdict(set)
        for _, b, r in lineas:
            for parte in seguro(b, r, fx)[1]:
                consultas[r].add(v["consulta"](parte, r, b))
        textos_d = [d for ds in docs.values() for _, d in ds]
        textos_q = sorted({q for qs in consultas.values() for q in qs})
        for tarea, ts in ((EMB.DOCUMENTO, textos_d), (EMB.CONSULTA, textos_q)):
            EMB.pedir(ts, tarea, cache)
        p[nombre] = {}
        for r, qs in consultas.items():
            dv = [(k, cache[f"RETRIEVAL_DOCUMENT|{d}"]) for k, d in docs[r]]
            p[nombre][r] = {}
            for q in sorted(qs):
                x = cache[f"RETRIEVAL_QUERY|{q}"]
                pts = sorted(((k, round(sum(a * b for a, b in zip(x, d)), 4)) for k, d in dv), key=lambda t: -t[1])
                p[nombre][r][q] = pts[:12]
    json.dump(p, open(PUNTAJES, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"puntajes: {', '.join(p)}")


def calibrar():
    """Cada variante de la busqueda con Jev perfecto: la parte dudosa sale bien si algun candidato es un campo que la
    vara acepta. Es el techo de cada busqueda, sin gastar en Jev."""
    print("\nLA CALIBRACION DEL NEXO DE CONDICION · misma vara, mismo codigo, Jev perfecto sobre los candidatos")
    print("  variante                                       k   140 sin falla   reales   365   perdidas  inventados")
    for nombre in VARIANTES:
        for k in (1, 2, 3, 5):
            nx = Nexo(nombre, k, jev=False)
            if not nx.pt.p.get(nombre):
                continue
            nx.oraculo = _oraculo(nx)
            t = calificar(nx, callado=True)
            print(f"  {nombre:46} {k}   {t['140 lineas sin falla']:3} de {t['140 lineas']:3}   "
                  f"{t['reales rubros sin falla']:2} de {t['reales rubros']:2}   "
                  f"{t['reales525 rubros sin falla']:3} de {t['reales525 rubros']:3}   "
                  f"{t['140 condiciones perdidas'] + t['reales condiciones perdidas'] + t['reales525 condiciones perdidas']:4}"
                  f"      {t['140 filtro inventado'] + t['reales filtro inventado'] + t['reales525 filtro inventado']:3}")


def _oraculo(nx):
    """Jev perfecto: entre los candidatos, el item que la vara acepta para alguna condicion de la linea; si ninguno, no
    se ata si la vara lo pide, o solo producto."""
    def elegir(parte, cands):
        r, esp = nx.actual
        for cl in cands:
            for op in opciones(r, [cl], nx.fx):
                if op in (SOLO_PRODUCTO, NINGUNO):
                    continue
                it = de_jev(parte, op, r, nx.fx)
                if it and any(acepta(a, it, r, nx) and a != "trivial" for e in esp for a in e):
                    return it
        if any("no se ata" in e and "trivial" not in e for e in esp):
            return {"parte": parte, "veredicto": "no se ata", "por": "oraculo"}
        return None
    return elegir


def correr_jev():
    """Jev en lo dudoso de los tres bancos: una llamada por busqueda con todas sus partes. Lo grabado no se repite."""
    import jev as J
    nx = Nexo(jev=False)
    hechas = jev_grabado()
    for _, b, r in _todas_las_lineas():
        _, partes = seguro(b, r, nx.fx)
        falta = [p for p in partes if (r, b, p) not in hechas]
        if not falta:
            continue
        qs = {}
        for i, parte in enumerate(falta):
            q = VARIANTES[nx.variante]["consulta"](parte, r, b)
            cands = nx.pt.candidatos(nx.variante, r, q, nx.k) or []
            qs[f"p{i}"] = {"type": "choice", "criteria": opciones(r, cands, nx.fx),
                           "instructions": f"El cliente busca {r} y escribio \"{b}\". En la parte \"{parte}\", que pide "
                                           f"de como tiene que ser el producto?"}
        res, tok = J.llamar_jev(f"BUSQUEDA DEL CLIENTE: {b}\nPRODUCTO: {r}", qs, "nexo_condicion")
        fila = {"rubro": r, "busqueda": b, "tokens": tok, "partes": {p: res.get(f"p{i}") for i, p in enumerate(falta)}}
        with open(JEV, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(fila, ensure_ascii=False) + "\n")
        hechas.update({(r, b, p): e for p, e in fila["partes"].items()})
        print(f"  [{r}] {b}: {fila['partes']}", flush=True)


if __name__ == "__main__":
    if "--base" in sys.argv:
        calificar(Nexo(jev=False), "--ver" in sys.argv, motor="base")
    elif "--embeddings" in sys.argv:
        embeddings([v for v in VARIANTES if any(v.startswith(a + " ") for a in sys.argv[2:])] or None)
    elif "--calibrar" in sys.argv:
        calibrar()
    elif "--correr-jev" in sys.argv:
        correr_jev()
    else:
        calificar(Nexo(jev="--sin-jev" not in sys.argv), "--ver" in sys.argv)
