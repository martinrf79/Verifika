"""
GENERADOR v2 (11-jul) — la arquitectura nueva EN EL BANCO, sin cablear al
camino vivo. El MODELO compone la respuesta entera; el CODIGO estampa cada
dato y verifica. Reemplaza selector + compositor + redactor por UNA llamada.

Como funciona:
  1. El codigo pre-selecciona un UNIVERSO ACOTADO de productos disponibles
     (mostrados + carrito + los baratos/intermedios de las categorias en
     juego). El modelo solo puede referenciar ids de ESE universo: el enum
     es chico y siempre real.
  2. Gemini emite una lista ordenada de FRAGMENTOS (structured outputs,
     atado por enum): prosa libre de venta, o referencias a datos
     (calculo, ficha, opciones, faq, envio, cierre).
  3. El codigo RENDER-iza cada fragmento desde la fuente: el precio, la
     garantia, el material, el total NACEN del codigo, no del modelo. La
     prosa se poda de cualquier dato colado.

Garantia: el modelo elige QUE y en que ORDEN y con que TONO; jamas escribe
un numero ni una spec. Imposible inventar (enum) y imposible cruzar un
precio (el codigo lo pone desde el id).
"""
import asyncio
import json
import re
import zlib

from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

_TIMEOUT_S = 12
_MAX_FRAGMENTOS = 8
CAMPOS_FICHA = ["procedencia", "garantia", "material", "descripcion",
                # 27-jul: sin estos campos la ficha NO podia contestar una spec
                # ("cuanto disco tiene", "cuanto pesa", "que trae la caja") y la
                # repregunta se caia o la contestaba el modelo de memoria. El
                # dato sigue saliendo de la fuente, estampado por el codigo.
                "caracteristicas", "medidas", "contenido_caja", "uso",
                # 28-jul: la ficha no llegaba al mapa `specs` de la fuente, asi
                # que thunderbolt, lector de huella, hercios o puertos no tenian
                # por donde salir aunque estuvieran cargados.
                "specs",
                # 29-jul: con QUE anda. Era el unico eje grande que no tenia
                # dato y lo contestaba el modelo de memoria (de ahi salio "es
                # compatible con cualquier notebook" sobre una RAM de
                # escritorio). Lo estampa el codigo desde compatibilidad.csv.
                "compatibilidad"]

def _criterios_del_turno(mensaje, universo=None, interp=None):
    """El enum del fragmento criterio para ESTE turno: (ids jurados relevantes,
    menu con su texto para groundear). El modelo redacta la frase para el
    cliente apoyandose en estos textos y cita el id; el codigo NO copia verbatim
    (leia a manual), el verificador de cita chequea que el id sea real. Sumar un
    tema es cargar texto en GUIA_VENTA, no tocar aca.

    DOS fuentes, ambas atadas al mismo enum de ids de GUIA_VENTA:
    1) CONTACTOR: las CATEGORIAS que el interprete DECLARO (atadas al enum de las
       76 de base_conocimiento) traen su criterio DIRECTO. Asi objecion,
       compatibilidad, financiacion, garantia, regalo -cualquiera de las 76-
       razona desde SU fuente cuando el interprete la ve, sin depender del RAG.
    2) RAG del corpus (recuperar) sobre el mensaje + las categorias del universo:
       la red que pesca el tema aunque el interprete no lo declare (ej 'el mas
       barato sirve para la oficina?' sin nombrar producto ni categoria).
    Sin match por ninguna via, no hay criterio: el turno se responde con prosa/faq."""
    from app.core.guia_venta_prosa import recuperar, texto_de
    menu_items: dict[str, str] = {}
    # 1) las categorias declaradas por el interprete (enum de la fuente)
    cats_interp = (interp or {}).get("categorias") if isinstance(interp, dict) else None
    for cat in (cats_interp or [])[:5]:
        cid = str(cat).strip()
        t = texto_de(cid)
        if t and cid not in menu_items:
            menu_items[cid] = t
    # 2) el RAG sobre mensaje + categorias del universo
    cats_uni = " ".join(str(p.get("categoria") or "") for p in (universo or []))
    for b in recuperar((mensaje or "") + " " + cats_uni, k=4):
        if b["id"] not in menu_items:
            menu_items[b["id"]] = b["texto"]
    if not menu_items:
        return ["_ninguno_"], ""
    ids = list(menu_items)
    menu = "\n".join(f"  [{cid}] {txt}" for cid, txt in menu_items.items())
    return ids, menu


def _faq_del_turno(mensaje, interp, tienda_id):
    """GROUNDING de FAQ del turno: la respuesta_curada YA estampada (con los
    numeros reales) de los temas que el interprete ruteo -categorias que son temas
    de FAQ- mas los que pesca el ruteo por keywords del mensaje. El solver REDACTA
    la politica desde este texto en su voz y con memoria; NO se pega la curada
    (eso robotizaba, 2500 pruebas). El numero que teje sale de aca y el
    verificador lo chequea contra los mismos valores. Devuelve (menu, temas)."""
    from app.storage.firestore_client import get_all_faq
    from app.core.tools import _faq_temas_multi
    from app.core.curadas import estampar_valores
    faq = get_all_faq(tienda_id=tienda_id) or {}
    if not faq:
        return "", []
    temas: list[str] = []
    cats = (interp or {}).get("categorias") if isinstance(interp, dict) else None
    for c in (cats or []):
        cid = str(c).strip()
        if cid in faq and cid not in temas:
            temas.append(cid)
    for t in _faq_temas_multi(mensaje or "", faq):
        if t not in temas:
            temas.append(t)
    lineas = []
    for t in temas[:5]:
        d = faq.get(t) or {}
        txt = str(d.get("respuesta_curada") or d.get("respuesta") or "").strip()
        if not txt:
            continue
        lineas.append(f"  [{t}] {estampar_valores(txt, d) or txt}")
    return "\n".join(lineas), [t for t in temas[:5] if faq.get(t)]


# Grupos cuyas categorias se contestan con PROSA (no producto ni conversacion):
# son las que, si el solver las saltea, dan whiff en una pregunta simple/media.
_PROSE_GRUPOS = {"politica_faq", "objeciones", "comparacion_compatibilidad",
                 "asesoramiento", "postventa", "seguridad", "casos_borde",
                 "identidad_dato"}


def _cats_obligatorias(interp, faq_ground) -> list:
    """Las categorias ruteadas que DEBEN contestarse con prosa este turno: grupo
    de prosa (no producto/conversacion) y con grounding disponible (criterio o
    FAQ). Son los slots requeridos del schema. Tope de 5 para no inflar el JSON."""
    from app.core.guia_venta_prosa import meta_categoria, texto_de
    faqset = set(faq_ground or [])
    out: list = []
    cats = (interp or {}).get("categorias") if isinstance(interp, dict) else None
    for c in (cats or []):
        cid = str(c).strip()
        if cid in out:
            continue
        if meta_categoria(cid).get("grupo", "") not in _PROSE_GRUPOS:
            continue
        if not (texto_de(cid) or cid in faqset):
            continue
        out.append(cid)
        if len(out) >= 5:
            break
    return out


def _norm(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


# El cliente pide el CATALOGO / que se vende, SIN nombrar una categoria puntual.
# Ahi el universo queda vacio y el solver no lista nada (bug real: "catalogo",
# "pasame catalogo", "que productos tenes" quedaban sin respuesta util). El codigo
# le pasa las categorias reales para que el solver presente que hay e invite.
_RE_CATALOGO = re.compile(
    r"\bcatalogos?\b"
    r"|\bque\s+(?:productos|cosas|articulos|rubros|categor)"
    r"|\bque\s+(?:tenes|tienen|venden|vendes|vendan|manejan|ofrecen|hay|comercializan)\b"
    r"|\bque\s+(?:se\s+)?puede[ns]?\s+comprar"
    r"|\bque\s+puedo\s+comprar"
    r"|\bmostrame\s+(?:el\s+catalogo|todo|lo\s+que\s+ten|los\s+productos)"
    r"|\blista\s+de\s+productos"
    r"|\bque\s+onda\s+el?\s+catalogo")


def nota_catalogo(mensaje, tienda_id):
    """Si el cliente pide el catalogo/que vendemos SIN nombrar una categoria real,
    devuelve la nota con las CATEGORIAS reales (fuente de verdad) para que el
    solver las presente e invite a elegir. '' si no aplica."""
    m = _norm(mensaje or "")
    if not m or not _RE_CATALOGO.search(m):
        return ""
    from app.storage.firestore_client import get_categories
    cats = [str(c) for c in (get_categories(tienda_id=tienda_id) or [])]
    if not cats:
        return ""
    # Si ademas nombra una categoria REAL ("que tenes de mouse"), no es un pedido
    # de catalogo entero: el flujo normal muestra esa categoria.
    if any(_norm(c) in m or _norm(c).rstrip("s") in m for c in cats):
        return ""
    return ("EL CLIENTE PIDE EL CATALOGO / que vendemos, sin una categoria puntual. "
            "Presentale con tu voz las categorias reales que tenemos e invitalo a "
            "elegir una para mostrarle modelos y precios. Categorias (usá SOLO estas, "
            "no inventes): " + ", ".join(cats) + ".\n")


# ── 1. UNIVERSO de productos disponibles (el enum del turno) ─────────────────
def universo_productos(mensaje, estado, tienda_id, interp=None):
    """Conjunto ACOTADO de productos que el modelo puede referenciar este
    turno: los ya mostrados, el carrito, y los mas baratos + el intermedio de
    cada categoria mencionada en el mensaje. Devuelve lista de dicts REALES
    del catalogo (id, nombre, precio_ars, stock, ...). Capado a ~16."""
    from app.core.tools_context import set_current_tienda
    from app.core.guia_pedido import cantidades_por_categoria, opciones_por_categoria
    from app.core.guia_compra import intermedio_con_stock
    from app.storage.firestore_client import get_product_by_id
    set_current_tienda(tienda_id)
    estado = estado if isinstance(estado, dict) else {}
    por_id = {}

    def _add(p):
        if isinstance(p, dict) and p.get("id") and p.get("nombre"):
            por_id.setdefault(str(p["id"]).upper(), p)

    # mostrados y carrito (por id, releidos vivos para precio/stock actual)
    for src in ((estado.get("productos_vistos") or [])
                + (estado.get("carrito") or [])):
        if isinstance(src, dict) and src.get("id"):
            _add(get_product_by_id(str(src["id"]).upper(), tienda_id=tienda_id))
    # producto resuelto por el interprete. Entran TODAS sus variantes: el
    # cliente dice "la zenbook 14" y en el catalogo hay nueve entre CPU y
    # colores. Con el resolutor viejo eso daba None, el universo quedaba sin la
    # notebook y el modelo le contestaba al cliente que NO la teniamos, teniendo
    # nueve en stock (charla real del 28-jul, turno 2).
    if interp and interp.get("producto_resuelto"):
        from app.core.pedido_helpers import certificar_producto
        from app.storage.firestore_client import get_all_products
        _v, _hits = certificar_producto(interp["producto_resuelto"],
                                        get_all_products(tienda_id=tienda_id))
        for _p in _hits[:8]:
            _add(_p)
    # CONTACTOR: los campos ESTRUCTURADOS del interprete alimentan el universo,
    # no solo el texto del mensaje. Asi la categoria pedida aun no mostrada
    # (solicitud_nueva, atada al enum de categorias) y los productos del pedido o
    # consultados (atados al enum de lo visto) SIEMPRE entran al enum, aunque el
    # detector de categorias del mensaje no los pesque. Reemplaza por atadura las
    # guias de texto que el hub le pasaba al solver viejo.
    # ORDEN pedido por el cliente ("la que mas capacidad", "la mas liviana").
    # Antes el universo era SIEMPRE las 4 mas baratas mas el intermedio, con lo
    # cual un superlativo del otro lado terminaba mostrando lo mas barato: el
    # cliente pidio la de mas capacidad y le ofrecimos cuatro de $693.000
    # teniendo 57 de 1TB, hasta $3.100.500 (charla real 28-jul).
    _orden = interp.get("orden") if isinstance(interp, dict) else None
    _orden = _orden if isinstance(_orden, dict) and _orden.get("atributo") else None

    def _cabeza_de_categoria(cat):
        """Los productos de la categoria que encabezan el orden pedido."""
        from app.core.fuente_producto import ordenar_por
        from app.storage.firestore_client import get_all_products
        dela = [p for p in get_all_products(tienda_id=tienda_id)
                if str(p.get("categoria", "")).lower() == str(cat).lower()
                and int(p.get("stock") or 0) > 0]
        return ordenar_por(dela, _orden["atributo"], _orden.get("direccion"))[:4]

    # la categoria sobre la que ordenar, cuando el cliente NO la nombra. "y la
    # mas liviana cual es" no dice notebook: viene del contexto. Sin esto el
    # orden se interpretaba bien y no corria sobre nada (charla real 28-jul).
    _cats_orden = []
    if _orden and isinstance(interp, dict):
        _cats_orden = [str(s["categoria"]) for s in (interp.get("solicitud_nueva") or [])
                       if isinstance(s, dict) and s.get("categoria")]
        if not _cats_orden:
            _cats_orden = list(dict.fromkeys(
                str(p.get("categoria")) for p in por_id.values()
                if p.get("categoria")))
        if not _cats_orden:
            from app.storage.firestore_client import get_categories
            _reales = {str(c).lower() for c in (get_categories(tienda_id=tienda_id) or [])}
            _cats_orden = [str(c) for c in (interp.get("categorias") or [])
                           if str(c).lower() in _reales]

    if isinstance(interp, dict):
        for s in (interp.get("solicitud_nueva") or []):
            if isinstance(s, dict) and s.get("categoria"):
                cat = str(s["categoria"])
                if _orden:
                    for p in _cabeza_de_categoria(cat):
                        _add(p)
                for p in opciones_por_categoria(cat, tienda_id, k=4):
                    _add(p)
                _add(intermedio_con_stock(cat))
        _todos = None
        for campo in ("pedido", "productos_consultados"):
            for it in (interp.get(campo) or []):
                nom = it.get("producto") if isinstance(it, dict) else None
                if not nom:
                    continue
                if _todos is None:
                    from app.storage.firestore_client import get_all_products
                    _todos = get_all_products(tienda_id=tienda_id)
                from app.core.pedido_helpers import certificar_producto
                _v, _hits = certificar_producto(nom, _todos)
                for _p in _hits[:8]:
                    _add(_p)
    # CONTEXTO MANDA sobre las palabras sueltas del mensaje (27-jul, charla real
    # del 24-jul 16:43). Si el cliente PREGUNTA por algo YA mostrado -el
    # interprete resolvio el producto o lo puso en productos_consultados- y NO
    # pidio ninguna categoria nueva (solicitud_nueva y pedido vacios), el rastreo
    # de categorias POR PALABRA del mensaje NO corre. Sin esto, "cuanta memoria
    # ram y espacio de disco tiene" -pregunta por la tablet del turno anterior-
    # metia los modulos de MEMORIA RAM al enum y el solver terminaba ofreciendo
    # RAM en vez de contestar por la tablet. El disparo es mutuamente excluyente
    # -seguimiento de lo mostrado vs pedido nuevo- y lo decide el INTERPRETE
    # (Contactor), no un regex sobre el texto.
    # ... salvo que pida un ORDEN. "y la mas liviana cual es" sigue hablando de
    # notebooks pero compara contra TODO el catalogo, no contra lo mostrado: si
    # se corta aca, el universo queda con la unica notebook del turno anterior y
    # el bot contesta "la que estamos trabajando es esta" esquivando el peso
    # (charla real 28-jul, turnos 3 y 4).
    if (isinstance(interp, dict) and not _orden
            and (interp.get("producto_resuelto")
                 or interp.get("productos_consultados"))
            and not (interp.get("solicitud_nueva") or [])
            and not (interp.get("pedido") or [])):
        return list(por_id.values())[:16]

    # ORDEN sobre la categoria del contexto. Va PRIMERO en la lista: el modelo
    # lee de arriba hacia abajo y, si la cabeza del orden queda al final, elige
    # el producto del turno anterior y contesta al lado de la pregunta. No
    # alcanza con que este en el universo, tiene que encabezarlo.
    if _orden and _cats_orden:
        cabeza = []
        for cat in _cats_orden:
            cabeza += _cabeza_de_categoria(cat)
        vistos, ordenados = set(), []
        for p in cabeza + list(por_id.values()):
            pid = str(p.get("id", "")).upper()
            if pid and pid not in vistos:
                vistos.add(pid)
                ordenados.append(p)
        return ordenados[:16]

    # categorias mencionadas: 4 mas baratas + el intermedio de cada una
    cats = cantidades_por_categoria(mensaje or "", tienda_id)
    cats_nombres = {c for _, c in cats}
    # tambien las categorias sueltas nombradas sin cantidad. Con tolerancia a
    # TYPOS del cliente ('mause', 'auris'): difuso por token (cutoff alto) o
    # prefijo largo; sin esto el universo quedaba VACIO y el modelo sin
    # productos que ofrecer (visto en la consigna 44).
    from difflib import get_close_matches
    from app.storage.firestore_client import get_categories
    m = _norm(mensaje)
    toks = [t for t in re.findall(r"\w+", m) if len(t) >= 5]
    for c in (get_categories(tienda_id=tienda_id) or []):
        cn = _norm(c)
        sing = cn[:-1] if cn.endswith("s") else cn
        if sing in m or cn in m:
            cats_nombres.add(str(c))
            continue
        for t in toks:
            if (get_close_matches(t, [sing], n=1, cutoff=0.75)
                    or sing.startswith(t[:4]) or cn.startswith(t[:4])):
                cats_nombres.add(str(c))
                break
    for cat in cats_nombres:
        # el orden pedido manda: primero la cabeza de ESE orden, despues las
        # baratas como referencia de precio.
        if _orden:
            for p in _cabeza_de_categoria(cat):
                _add(p)
        for p in opciones_por_categoria(cat, tienda_id, k=4):
            _add(p)
        _add(intermedio_con_stock(cat))
    return list(por_id.values())[:16]


# ── 1-bis. PREFERENCIAS del cliente: filtran el universo POR CONSTRUCCION ────
_RE_PAIS_MARCA = re.compile(r"marca .+? de ([a-z ]+?)(?:[.,]|$)")


def _pais_de_marca(prod):
    """El pais de la MARCA desde el campo origen ('Marca Logitech de Suiza.
    Fabricado en China.' -> 'suiza'). Casi todo se fabrica en China; cuando el
    cliente dice 'sin marcas chinas' habla de la marca, no de la fabrica."""
    m = _RE_PAIS_MARCA.search(_norm(prod.get("origen")))
    return m.group(1).strip() if m else ""


def filtrar_por_preferencias(universo, prefs):
    """Aplica exclusiones (origen/marca) y tope de presupuesto al universo del
    turno. Prevencion por construccion: lo excluido ni entra al enum, el modelo
    no puede ofrecerlo. Si el filtro vaciara el universo, se devuelve el
    original: mejor que el modelo explique honesto (con las preferencias en el
    prompt) a que se quede sin productos que mostrar."""
    prefs = prefs if isinstance(prefs, dict) else {}
    exclusiones = [e for e in (prefs.get("exclusiones") or [])
                   if isinstance(e, dict) and e.get("valor")]
    tope = prefs.get("tope_presupuesto")
    if not exclusiones and not tope:
        return universo

    def _pasa(p):
        for e in exclusiones:
            stem = _norm(e["valor"])[:4]
            if not stem:
                continue
            if e.get("tipo") == "marca" and stem in _norm(p.get("marca")):
                return False
            if e.get("tipo") == "origen":
                pais = _pais_de_marca(p) or _norm(p.get("origen"))
                if stem in pais:
                    return False
        if tope:
            try:
                if float(p.get("precio_ars") or 0) > float(tope):
                    return False
            except (TypeError, ValueError):
                pass
        return True

    filtrado = [p for p in universo if _pasa(p)]
    return filtrado if filtrado else universo


_RE_INTERMEDIO = re.compile(
    r"termino medio|intermedio|gama media|ni el mas barato ni|algo mejor(cito)?"
    r"|un escalon (mas )?arriba")


def bloque_intermedio(mensaje, estado, tienda_id):
    """Fila 15 de la matriz en el camino del generador (caso real 17-jul,
    20:47: 'dame un termino medio asi elijo' salio criterio sin productos ni
    precios). Elegir el intermedio es problema CERRADO: si el cliente pide
    termino medio y hay pedido vigente, el CODIGO arma el menu con el
    intermedio REAL de cada categoria del carrito, precio estampado.
    Devuelve (texto, tools) o (None, [])."""
    if not _RE_INTERMEDIO.search(_norm(mensaje)):
        return None, []
    carrito = (estado or {}).get("carrito") or []
    if not carrito:
        return None, []
    from app.core.tools_context import set_current_tienda
    from app.core.guia_compra import intermedio_con_stock
    from app.storage.firestore_client import get_product_by_id
    from app.core.pedido_helpers import _linea_producto
    set_current_tienda(tienda_id)
    cats, lineas, tools = [], [], []
    for c in carrito:
        p = get_product_by_id(str(c.get("id") or "").upper(), tienda_id=tienda_id)
        cat = (p or {}).get("categoria")
        if cat and cat not in cats:
            cats.append(cat)
    for cat in cats:
        inter = intermedio_con_stock(cat)
        if inter:
            lineas.append("- " + _linea_producto(inter))
            tools.append({"name": "get_product_details",
                          "result": {"encontrado": True, "producto": inter}})
    if not lineas:
        return None, []
    return ("Para que elijas, el término medio de cada categoría, con "
            "precio y stock reales:\n" + "\n".join(lineas)
            + "\nDecime cuáles cambiás y te rearmo el total al instante."), tools


# ── 2. SCHEMA de fragmentos (atado por enum) ─────────────────────────────────
def presupuesto_precalculado(mensaje, estado, tienda_id, interp=None):
    """Lo CERRADO al codigo: si el pedido es determinable (cantidades por
    categoria con criterio barato, o carrito vigente con total/split), el
    codigo calcula el presupuesto SELLADO. Devuelve (texto, tools) o
    (None, []). El modelo NO arma la cuenta: solo la posiciona."""
    from app.core.tools_context import set_current_tienda
    from app.core.estado_venta import set_current_estado
    set_current_tienda(tienda_id)
    # inicio_turno=False: el turno YA arranco en interprete_libre; este
    # re-seteo es solo para las tools y no debe borrar las localidades
    # cotizadas del turno (agujero del 12-jul, cerrado 20-jul).
    set_current_estado(estado if isinstance(estado, dict) else {},
                       inicio_turno=False)
    estado = estado if isinstance(estado, dict) else {}
    try:
        from app.core.guia_pedido import (
            cantidades_por_categoria, calcular_categorias_baratas,
            _calcular_items_sellados, reparto_envios_detalle,
            mensaje_presupuesto_sellado)
        from app.core.pago_split import pago_de_mensaje
        # a) carrito vigente + reparto/total pedido en el mensaje
        carrito = estado.get("carrito") or []
        pago = pago_de_mensaje(mensaje or "")
        # "y el presupuesto?" / "seguis sin mandarme precios" (caso real
        # WhatsApp 17-jul): el cliente pidio el presupuesto TRES veces y el
        # regex no lo disparaba; el modelo relataba "aca te lo armo" sin
        # armarlo. La palabra presupuesto y "precios" en plural re-sirven el
        # calculo SELLADO del codigo.
        quiere_total = bool(re.search(
            r"\btotal\b|como queda|cuanto (queda|es|sale)|precio final|"
            r"\bpresupuesto\b|\bprecios\b|"
            r"mitad|transferencia|mercado pago|pagando", _norm(mensaje)))
        if carrito and (pago or quiere_total):
            items = [{"product_id": str(c.get("id") or "").upper(),
                      "cantidad": int(c.get("cantidad") or 1)}
                     for c in carrito if c.get("id")]
            tools = _calcular_items_sellados(
                items, estado, tienda_id, None, mensaje) or []
            if tools:
                return (tools[0]["result"]["presentacion"].strip(), tools)
        # b) cantidades por categoria + criterio barato -> los mas baratos
        cats = cantidades_por_categoria(mensaje or "", tienda_id)
        if cats and re.search(r"barat|econ[oó]mic|mas conveniente|precio",
                              _norm(mensaje)):
            tools = calcular_categorias_baratas(
                cats, estado, tienda_id, None, mensaje) or []
            if tools:
                rep, rep_tools = reparto_envios_detalle(
                    mensaje, cats, tienda_id,
                    detalle_items=tools[0]["result"].get("detalle"))
                bloque = tools[0]["result"]["presentacion"].strip()
                if rep:
                    bloque += "\n" + rep.strip()
                return (bloque, tools + rep_tools)
    except Exception as e:
        log.warning("presupuesto_precalculado_error", error=str(e)[:120])
    return None, []


def _schema(ids, temas, criterios, cats_obligatorias=None):
    ids_o = ids + [None]
    cats_obligatorias = cats_obligatorias or []
    base = {
        "type": "object", "additionalProperties": False,
        "properties": {"fragmentos": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "tipo": {"type": "string", "enum": [
                    "prosa", "producto", "opciones", "calculo", "presupuesto",
                    "ficha", "faq", "envio", "criterio", "cierre"]},
                "texto": {"type": ["string", "null"]},
                "producto_id": {"type": ["string", "null"], "enum": ids_o},
                "criterio_id": {"type": ["string", "null"],
                                "enum": criterios + [None]},
                "categoria": {"type": ["string", "null"]},
                "items": {"type": ["array", "null"], "items": {
                    "type": "object", "additionalProperties": False,
                    "properties": {
                        "producto_id": {"type": "string", "enum": ids},
                        "cantidad": {"type": "integer"},
                        "destino": {"type": ["string", "null"]}},
                    "required": ["producto_id", "cantidad", "destino"]}},
                "campos": {"type": ["array", "null"],
                           "items": {"type": "string", "enum": CAMPOS_FICHA}},
                "tema": {"type": ["string", "null"], "enum": temas + [None]},
                "destino": {"type": ["string", "null"]},
                "pago": {"type": ["array", "null"], "items": {
                    "type": "object", "additionalProperties": False,
                    "properties": {
                        "medio": {"type": "string",
                                  "enum": ["transferencia", "mercado pago"]},
                        "porcentaje": {"type": "number"}},
                    "required": ["medio", "porcentaje"]}},
            },
            "required": ["tipo", "texto", "producto_id", "criterio_id",
                         "categoria", "items", "campos", "tema", "destino",
                         "pago"]}}},
        "required": ["fragmentos"]}
    # ATADURA ESTRUCTURAL DE COBERTURA (propuesta de Martin): un slot REQUERIDO por
    # categoria ruteada de prosa. Al ser propiedades required de un objeto, el
    # schema strict OBLIGA al solver a emitir un texto por cada una -a diferencia de
    # un array, donde no se puede forzar un item por enum-. El whiff se vuelve
    # imposible por construccion, no por medicion.
    if cats_obligatorias:
        base["properties"]["respuestas_por_categoria"] = {
            "type": "object", "additionalProperties": False,
            "properties": {c: {
                "type": "object", "additionalProperties": False,
                "properties": {"texto": {"type": "string"},
                               "cita_id": {"type": ["string", "null"]}},
                "required": ["texto", "cita_id"]} for c in cats_obligatorias},
            "required": list(cats_obligatorias)}
        base["required"] = ["fragmentos", "respuestas_por_categoria"]
    return base


def _prompt(mensaje, historial, universo, temas, estado, presupuesto_pre=None,
            criterios_menu="", prefs=None, nota_no_vendida="", faq_menu="",
            cats_obligatorias=None, interp=None):
    def _linea(p):
        base = (f"  {p['id']} = {p['nombre']} | "
                f"${int(p.get('precio_ars',0)):,}".replace(",", ".")
                + f" | stock {p.get('stock','?')}")
        pais = _pais_de_marca(p)
        if p.get("marca"):
            base += f" | marca {p['marca']}" + (f" de {pais}" if pais else "")
        if p.get("uso_recomendado"):
            base += f" | para {p['uso_recomendado']}"
        return base
    prods = "\n".join(_linea(p) for p in universo)
    # FICHA TECNICA del producto en foco. Sin esto el modelo veia nombre,
    # precio y stock, nada mas: ante "tiene thunderbolt?" no podia mas que
    # prometer chequearlo o negar el producto. El dato existe en la fuente y
    # ahora lo VE, ademas de que el codigo se lo estampa al renderizar.
    ficha_txt = ""
    try:
        from app.core.fuente_producto import consenso_specs, specs_config
        _etq = {s["id"]: s["etiqueta"] for s in specs_config()}
        _foco = [p for p in universo if isinstance(p.get("specs"), dict)][:6]
        if _foco:
            comunes, difieren = consenso_specs(_foco)
            lineas = [f"  {_etq.get(k, k)}: {v}" for k, v in sorted(comunes.items())]
            for k, opciones in sorted(difieren.items()):
                det = "; ".join(f"{v} en {n[0]}" for v, n in opciones[:3])
                lineas.append(f"  {_etq.get(k, k)}: depende de la version -> {det}")
            if lineas:
                nom = _foco[0].get("nombre", "")
                ficha_txt = (
                    f"\n\nFICHA TECNICA de {nom}"
                    + (f" y sus {len(_foco)} variantes" if len(_foco) > 1 else "")
                    + " (dato REAL de la fuente, contestá con esto, NO prometas "
                      "chequearlo ni digas que no lo tenemos):\n"
                    + "\n".join(lineas))
    except Exception as e:
        log.warning("generador_v2_ficha_prompt_error", error=str(e)[:120])
    # COMPATIBILIDAD del turno: la fila de la tabla de cada producto del universo
    # mas el veredicto YA RESUELTO contra los equipos que declaro el cliente. Va
    # al prompt para que el modelo REDACTE desde el dato en vez de deducirlo; el
    # veredicto que sale al cliente igual lo estampa el codigo en el hub.
    compat_txt = ""
    try:
        from app.core.compatibilidad import (bloque_prompt,
                                             plataformas_de_interp,
                                             plataformas_del_mensaje)
        _plats = plataformas_de_interp(interp) or plataformas_del_mensaje(mensaje)
        compat_txt = bloque_prompt(universo, _plats)
    except Exception as e:
        log.warning("generador_v2_compat_prompt_error", error=str(e)[:120])
    prefs = prefs if isinstance(prefs, dict) else {}
    pref_lineas = []
    if prefs.get("tope_presupuesto"):
        pref_lineas.append("presupuesto maximo "
                           + f"${int(prefs['tope_presupuesto']):,}".replace(",", "."))
    for e in (prefs.get("exclusiones") or []):
        pref_lineas.append(f"NO quiere {e.get('tipo')} {e.get('valor')}")
    if prefs.get("uso_previsto"):
        pref_lineas.append("lo va a usar para " + str(prefs["uso_previsto"]))
    prefs_txt = ("\nPREFERENCIAS que el cliente ya dio (respetalas en TODA la "
                 "respuesta; si nada del listado las cumple, decilo honesto "
                 "sin inventar): " + "; ".join(pref_lineas)) if pref_lineas else ""
    faq_list = ", ".join(temas)
    carrito = estado.get("carrito") or []
    car_txt = ("\nPedido vigente: " + ", ".join(
        f"{c.get('cantidad',1)}x {c.get('nombre')}" for c in carrito)) if carrito else ""
    dest = estado.get("localidades_envio") or []
    dest_txt = ("\nDestinos ya dados: " + ", ".join(dest)) if dest else ""
    # MEMORIA del solver (27-jul). Antes solo veia 4 mensajes recortados a 160
    # caracteres: ni el resumen largo de la charla, ni que productos ya habia
    # mostrado, ni a QUE producto se referia el mensaje. Por eso una repregunta
    # ("cuanta memoria ram tiene") quedaba huerfana y el modelo la contestaba
    # contra el listado en vez de contra el producto en foco. Ahora la charla
    # llega entera: resumen acumulado, mostrados, foco resuelto por el interprete
    # e historial mas ancho.
    hist = ("\n".join(f"{h.get('role')}: {str(h.get('content'))[:300]}"
                      for h in (historial or [])[-8:]))
    resumen = str(estado.get("resumen_charla") or "").strip()
    res_txt = ("\nDe lo que ya hablaron antes (memoria de la charla): "
               + resumen) if resumen else ""
    _vistos = [str(p.get("nombre")) for p in (estado.get("productos_vistos") or [])
               if isinstance(p, dict) and p.get("nombre")]
    vis_txt = ("\nProductos que YA le mostraste en esta charla: "
               + ", ".join(dict.fromkeys(_vistos[-8:]))) if _vistos else ""
    foco_txt = ""
    if isinstance(interp, dict):
        _pr = str(interp.get("producto_resuelto") or "").strip()
        _cons = [f"{c.get('producto')} (quiere saber: {c.get('consulta')})"
                 for c in (interp.get("productos_consultados") or [])
                 if isinstance(c, dict) and c.get("producto")]
        if _pr or _cons:
            foco = _pr or ", ".join(_cons)
            foco_txt = (
                f"\n\nFOCO DEL MENSAJE (ya resuelto por el sistema, no lo "
                f"discutas): el cliente esta preguntando por {foco}. Toda "
                f"referencia suelta del mensaje ('tiene', 'ese', 'cuanto pesa', "
                f"'cuanta memoria') es sobre ESE producto, aunque nombre una "
                f"palabra que suene a otra categoria. Contestale sobre EL con "
                f"un fragmento ficha o producto; NO le ofrezcas otra categoria "
                f"si no la pidio."
                + (f"\nLo que pregunto de cada uno: " + "; ".join(_cons)
                   if _cons else ""))
    return (
        "Sos el vendedor por WhatsApp de Verifika Tech, tienda argentina de "
        "tecnologia. Voseo, calido, directo, vendedor de verdad. Tu meta es "
        "VENDER y responder TODO lo que el cliente pregunto.\n\n"
        "NO escribis datos duros. Componés la respuesta como una lista de "
        "FRAGMENTOS en el orden en que el cliente los va a leer. El sistema "
        "estampa cada dato real. Tipos:\n"
        "- prosa: PEGAMENTO corto y adaptativo. Un eco de lo que dijo el "
        "cliente, un puente, un nexo natural. PROHIBIDO poner numeros o precios "
        "aca (eso va por su fragmento). SI podes nombrar un producto del "
        "listado para opinar o comparar. NO metas el criterio de venta largo "
        "aca: para eso esta el fragmento criterio.\n"
        "- criterio: cuando das consejo, comparas, el cliente duda cual llevar "
        "u OBJETA. Escribi VOS la frase para el cliente en el campo texto, "
        "corta, en voseo, natural, hablandole a el; APOYATE en el criterio "
        "jurado de la lista de abajo, no lo copies palabra por palabra, "
        "adaptalo. Poné en criterio_id el id del bloque que usaste. SIN "
        "numeros. Elegi el bloque por lo que el cliente QUIERE: si dice que "
        "algo es caro va objecion_precio, si no sabe cual, asesoramiento_metodo. "
        "En un pedido directo (ej. 'quiero el mouse mas barato') NO metas "
        "criterio: solo satura. Si NINGUN bloque de la lista aplica a lo que "
        "pregunta el cliente, IGUAL respondele con un fragmento criterio: "
        "razona desde los datos del listado (marca, pais de la marca, uso, "
        "precio relativo) y deja criterio_id en null. Nunca dejes la pregunta "
        "sin responder por falta de bloque; lo que no sepas, decilo honesto.\n"
        "- producto: mostrar la linea (nombre+precio+stock) de UN producto "
        "-> producto_id.\n"
        "- opciones: mostrar las opciones con stock de una categoria -> "
        "categoria.\n"
        "- presupuesto: el sistema YA calculo el presupuesto del pedido. "
        "Usa este fragmento (sin datos) donde quieras que aparezca el "
        "presupuesto ya armado. Si te paso un PRESUPUESTO YA ARMADO abajo, "
        "usa SIEMPRE este fragmento y NO el de calculo.\n"
        "- calculo: armar el presupuesto desde cero -> items [{producto_id, "
        "cantidad, destino}] y opcional pago. Solo si NO hay presupuesto ya "
        "armado.\n"
        "- ficha: datos reales de un producto -> producto_id + campos "
        "(procedencia/garantia/material/descripcion/caracteristicas/medidas/"
        "contenido_caja/uso/compatibilidad). ES EL FRAGMENTO PARA CONTESTAR UNA "
        "SPEC: si el cliente pregunta cuanto pesa, cuanta memoria o disco tiene, "
        "que trae, de que material es o para que sirve, va ficha con ese "
        "producto_id y los campos que lo respondan; el sistema estampa el dato "
        "de la fuente. TAMBIEN es el fragmento de la COMPATIBILIDAD: si pregunta "
        "si algo le sirve para su equipo, si se conecta, si anda con la Mac o "
        "con la consola, va ficha con el campo compatibilidad, NUNCA tu opinion "
        "en prosa. NO escribas vos la spec en prosa.\n"
        "- faq: politica de la tienda (envio, pago, garantia, factura, IVA, "
        "cuotas, seguimiento, etc). REDACTA VOS la respuesta en el campo texto, "
        "en tu voz, con el contexto de la charla, apoyandote en el bloque de FAQ "
        "de abajo (NO lo copies palabra por palabra, adaptalo). Poné en tema el "
        "id del bloque que usaste. Los numeros que menciones salen de ese bloque, "
        "no los inventes.\n"
        "- envio: cotizar un destino -> destino.\n"
        "- cierre: invitar a avanzar. Escribi VOS la frase en el campo texto, en "
        "tu voz y variada (no repitas la misma en turnos seguidos). Si hay un "
        "TOTAL sobre la mesa, pedi la forma de pago (transferencia con 10% de "
        "descuento o Mercado Pago). Si NO hay total, invita suave a elegir. Un "
        "solo cierre por respuesta.\n\n"
        f"{nota_no_vendida}"
        f"PRODUCTOS disponibles (usa SOLO estos ids):\n{prods}\n\n"
        f"TEMAS de FAQ disponibles: {faq_list}\n"
        + (f"FAQ para REDACTAR (para el fragmento faq: adapta esto a tu voz con "
           f"el contexto de la charla, cita el id entre corchetes, NO lo copies "
           f"literal; los numeros salen de aca):\n{faq_menu}\n" if faq_menu else "")
        + f"CRITERIO jurado para apoyarte (para el fragmento criterio: adapta "
        f"esto a tu frase y cita el id entre corchetes):\n{criterios_menu}\n"
        f"{car_txt}{dest_txt}{vis_txt}{res_txt}{prefs_txt}{ficha_txt}{compat_txt}\n\n"
        + (f"\n\nPRESUPUESTO YA ARMADO por el sistema (ponelo con un "
           f"fragmento tipo 'presupuesto'):\n{presupuesto_pre}" if presupuesto_pre else "")
        + (("\n\nOBLIGATORIO — respuestas_por_categoria: DEBÉS escribir un texto "
            "para CADA UNA de estas categorías que el cliente tocó, redactado en "
            "tu voz desde su bloque de criterio/FAQ de arriba, citando el id en "
            "cita_id (o null). NO podés dejar ninguna vacía ni saltearla; es tu "
            "respuesta a lo que preguntó. Categorías: "
            + ", ".join(cats_obligatorias)) if cats_obligatorias else "")
        + f"\n\nCharla:\n{hist}{foco_txt}\n\nMensaje del cliente:\n{mensaje}\n\n"
        "Reglas: responde TODAS las cosas que pregunto el cliente, cada una "
        "por su fragmento; NUNCA dejes una pregunta sin responder. Si el "
        "cliente pide tu OPINION o consejo (si un producto le sirve para algo, "
        "si le conviene, comparaciones), mostra el fragmento producto y dá el "
        "criterio con un fragmento criterio, no lo improvises en prosa. Si el "
        "pide el PRECIO o TOTAL de varios productos, o da cantidades (ej. "
        "'2 mouse y 2 teclados'), USA un fragmento calculo con todos los "
        "items, NO productos sueltos: el cliente quiere el total armado. Si "
        "pide 'los mas baratos', elegi vos los de menor precio del listado. Si "
        "un dato no esta disponible, decilo en prosa sin inventar. Cerra "
        "siempre invitando a avanzar. Devolve SOLO el JSON de fragmentos.")


def _cliente_gemini():
    """EL cliente del camino vivo. Lo usan el solver, el juez, las reescrituras
    de las guardias y el resumen de memoria: una sola puerta, para que un cambio
    de provider no pueda dejar a uno apuntando al anterior. Devuelve None sin
    clave, y cada consumidor degrada a no-op."""
    from openai import OpenAI
    import os
    key = (settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
           or os.environ.get("GEMINI_APY_KEY") or "")
    key = key.split()[0] if key else ""
    if not key:
        return None
    return OpenAI(api_key=key, base_url=settings.GEMINI_BASE_URL)


async def generar_fragmentos(mensaje, historial, estado, tienda_id,
                             interp=None, trace_id=None,
                             presupuesto_externo=None):
    """La llamada a Gemini que compone la respuesta como fragmentos atados.
    Devuelve (fragmentos, universo) o (None, universo) ante error.
    presupuesto_externo: (texto, tools) de un presupuesto YA SELLADO por el
    codigo (guia de pedido). Si viene, manda sobre el precalculo interno: el
    modelo lo posiciona y responde ALREDEDOR el resto del mensaje (caso real
    21:32: el sellado ignoraba dia de entrega, regalo y la localidad dicha)."""
    universo = universo_productos(mensaje, estado, tienda_id, interp)
    # PREFERENCIAS efectivas del turno: las sticky del estado mas lo que el
    # interprete leyo AHORA (todavia no persistido). Filtran el universo por
    # construccion: lo excluido ni entra al enum.
    from app.core.estado_venta import preferencias_actualizadas
    prefs = preferencias_actualizadas(
        (estado or {}).get("preferencias") if isinstance(estado, dict) else {},
        interp, mensaje)
    universo = filtrar_por_preferencias(universo, prefs)
    ids = [p["id"] for p in universo]
    from app.storage.firestore_client import get_all_faq
    temas = sorted((get_all_faq(tienda_id=tienda_id) or {}).keys())
    if not ids:
        # sin universo el modelo no tiene con que; igual puede faq/prosa/cierre
        ids = ["_none_"]
    # El enum del CRITERIO de venta: los bloques jurados relevantes al turno. El
    # modelo redacta la frase apoyandose en ellos y cita el id que uso.
    criterios, criterios_menu = _criterios_del_turno(mensaje, universo, interp)
    # GROUNDING de FAQ: la curada estampada de los temas ruteados, para que el
    # SOLVER redacte la politica en su voz (no se pega la curada, que robotizaba).
    faq_menu, _faq_ground = _faq_del_turno(mensaje, interp, tienda_id)
    # OBLIGACION ESTRUCTURAL DE COBERTURA: las categorias ruteadas que se contestan
    # con PROSA (politica/objecion/compatibilidad/asesoramiento/postventa/etc, no
    # las de producto ni conversacion) y que tienen grounding entran como SLOTS
    # REQUERIDOS en el schema. El solver queda obligado a nivel API a redactar un
    # texto por cada una; el render appendea el que haya salteado. Asi el whiff se
    # vuelve imposible por construccion, no por medicion.
    cats_obligatorias = _cats_obligatorias(interp, _faq_ground)
    # Lo CERRADO al codigo: presupuesto pre-calculado si el pedido es
    # determinable. El modelo solo lo POSICIONA (fragmento presupuesto).
    if presupuesto_externo and presupuesto_externo[0]:
        presu_txt, presu_tools = presupuesto_externo
    else:
        presu_txt, presu_tools = presupuesto_precalculado(
            mensaje, estado, tienda_id, interp)
    if not presu_txt:
        # Termino medio pedido con carrito vigente: el menu de intermedios lo
        # arma el CODIGO (mismo mecanismo de posicionado + red que el
        # presupuesto; el cliente SIEMPRE lo recibe).
        presu_txt, presu_tools = bloque_intermedio(mensaje, estado, tienda_id)
    # CERTIFICADOR DE CATEGORIA NO VENDIDA (fuente de verdad no_vendidas.json):
    # si el cliente pide una categoria que NO vendemos, el CODIGO lo decide -no el
    # modelo- y le pasa el hecho + la alternativa REAL para que redacte el "no"
    # honesto en su voz, sin caer la venta. La alternativa entra al universo asi
    # sus opciones son ids reales que el solver puede ofrecer.
    nota_no_vendida = ""
    try:
        from app.core.guia_compra import categoria_no_vendida
        from app.core.guia_pedido import opciones_por_categoria
        _cnv = categoria_no_vendida(mensaje or "", tienda_id)
        if _cnv:
            _pedida, _alt = _cnv
            if _alt:
                for p in opciones_por_categoria(_alt, tienda_id, k=4):
                    if isinstance(p, dict) and p.get("id") and p["id"] not in ids:
                        universo.append(p)
                        ids.append(p["id"])
                nota_no_vendida = (
                    f"OJO, HONESTIDAD: el cliente pide '{_pedida}', que NO "
                    f"vendemos (nuestro rubro es tecnologia e informatica). "
                    f"Decilo claro y sin vueltas, y ofrecele la alternativa real "
                    f"de {_alt} que esta en el listado. NO digas ni sugieras que "
                    f"tenemos '{_pedida}'.\n")
            else:
                nota_no_vendida = (
                    f"OJO, HONESTIDAD: el cliente pide '{_pedida}', que NO "
                    f"vendemos (nuestro rubro es tecnologia e informatica). "
                    f"Decilo claro y sin vueltas. NO digas ni sugieras que lo "
                    f"tenemos ni inventes una alternativa que no este en el "
                    f"listado; invitalo a ver lo que si tenemos.\n")
            log.info("generador_v2_no_vendida", trace_id=trace_id,
                     pedida=_pedida, alt=_alt)
    except Exception as e:
        log.warning("generador_v2_no_vendida_error", trace_id=trace_id,
                    error=str(e)[:120])
    # CATALOGO: pedido general "que vendes / catalogo" sin categoria puntual -> el
    # universo queda vacio; el codigo le pasa las categorias reales para que el
    # solver presente que hay (bug real: "catalogo" quedaba sin respuesta util).
    try:
        _nc = nota_catalogo(mensaje or "", tienda_id)
        if _nc:
            nota_no_vendida = (nota_no_vendida + _nc) if nota_no_vendida else _nc
            log.info("generador_v2_catalogo", trace_id=trace_id)
    except Exception as e:
        log.warning("generador_v2_catalogo_error", trace_id=trace_id,
                    error=str(e)[:120])
    prompt = _prompt(mensaje, historial, universo, temas, estado, presu_txt,
                     criterios_menu, prefs, nota_no_vendida, faq_menu,
                     cats_obligatorias, interp)
    schema = _schema(ids, temas, criterios, cats_obligatorias)

    def _call():
        c = _cliente_gemini()
        r = c.chat.completions.create(
            model=(settings.GEMINI_MODEL or "gemini-3.1-flash-lite"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6, max_tokens=1500,
            extra_body={"reasoning_effort": "none"},
            response_format={"type": "json_schema", "json_schema": {
                "name": "respuesta", "strict": True, "schema": schema}})
        return r.choices[0].message.content or ""
    try:
        from app.core.llm_reintento import llamar_con_reintento
        raw = await llamar_con_reintento(_call, timeout_s=_TIMEOUT_S,
                                         trace_id=trace_id)
        data = json.loads(raw)
        frags = data.get("fragmentos")
        rpc = data.get("respuestas_por_categoria") or {}
        if isinstance(frags, list) and frags:
            log.info("generador_v2_ok", trace_id=trace_id, n=len(frags),
                     obligatorias=len(cats_obligatorias),
                     # los TIPOS que emitio: sin esto, cuando el render descarta
                     # un fragmento no hay forma de saber cual se perdio
                     tipos=[f.get("tipo") for f in frags
                            if isinstance(f, dict)][:_MAX_FRAGMENTOS])
            return (frags[:_MAX_FRAGMENTOS], universo, presu_txt, presu_tools,
                    rpc if isinstance(rpc, dict) else {})
    except Exception as e:
        log.warning("generador_v2_error", trace_id=trace_id, error=str(e)[:150])
    return None, universo, presu_txt, presu_tools, {}


# ── 3. RENDER: el codigo estampa cada dato desde la fuente ───────────────────
_RE_DIGITO = re.compile(r"\d")
# PLATA en la prosa: precio, total, monto o porcentaje. Un numero de 4 o mas
# digitos (con o sin puntos) es plata en este catalogo; uno chico (12 meses,
# 128GB, 2 unidades) no lo es y se deja pasar.
_RE_PLATA = re.compile(
    r"\$|%|\bpesos\b|\bd[oó]lares\b|\b\d[\d.]{3,}\b|\b\d+\s*(?:mil|lucas|palos)\b",
    re.IGNORECASE)


def _texto_ficha_limpio(texto, tope=220):
    """Descripcion apta cliente: sin cortes a mitad de palabra ('Uso rec',
    caso real 19-jul) y sin la duplicacion que a veces trae el CSV
    ('Core i5..., Core i5...'). El corte cierra en oracion completa."""
    t = str(texto or "").strip()
    if not t:
        return ""
    t = re.sub(r"([^,.\n]{8,}?)\s*[,.]\s*\1(?=[,.\s]|$)", r"\1", t)
    if len(t) <= tope:
        return t
    corte = t[:tope]
    p = corte.rfind(". ")
    if p >= 40:
        return corte[:p + 1]
    p = corte.rfind(" ")
    return (corte[:p] if p > 0 else corte).rstrip(",;: ") + "…"


def _campo_ficha(prod, campo):
    if campo == "procedencia":
        return str(prod.get("origen") or "").strip()
    if campo == "garantia":
        return str(prod.get("garantia_detalle") or "").strip()
    if campo == "material":
        m = re.search(r"[Mm]aterial ([A-Za-zÁÉÍÓÚáéíóúñ ]+?)[.\n]",
                      prod.get("descripcion") or "")
        return ("Material " + m.group(1).strip()) if m else ""
    if campo == "descripcion":
        return _texto_ficha_limpio(prod.get("descripcion"))
    if campo == "caracteristicas":
        v = str(prod.get("caracteristicas_extra") or "").strip()
        if not v:
            return ""
        # el catalogo repite la misma spec por unidad ("8GB, 8GB"): se dedup.
        v = ", ".join(dict.fromkeys(x.strip() for x in v.split(",") if x.strip()))
        return ("Características: " + v) if v else ""
    if campo == "medidas":
        partes = []
        if prod.get("peso_gramos"):
            partes.append(f"Peso {prod['peso_gramos']} g")
        if prod.get("dimensiones"):
            partes.append(f"Medidas {str(prod['dimensiones']).strip()}")
        return ". ".join(partes)
    if campo == "contenido_caja":
        v = str(prod.get("contenido_caja") or "").strip()
        return ("Viene con: " + v) if v else ""
    if campo == "specs":
        mapa = prod.get("specs")
        if not isinstance(mapa, dict) or not mapa:
            return ""
        from app.core.fuente_producto import specs_config
        etq = {s["id"]: s["etiqueta"] for s in specs_config()}
        partes = []
        for sid, valor in mapa.items():
            if not valor:
                continue
            nombre = re.sub(r"^(?:el|la|los|las|si)\s+", "", etq.get(sid, sid))
            partes.append(f"{nombre}: {valor}")
        return ". ".join(partes[:8])
    if campo == "compatibilidad":
        from app.core.compatibilidad import bloque_ficha
        return bloque_ficha(prod)
    if campo == "uso":
        v = str(prod.get("uso_recomendado") or "").strip()
        return ("Recomendado para " + v) if v else ""
    return ""


# Specs que los clientes preguntan y que la ficha puede no traer. FUENTE DE
# VERDAD: data/clientes/verifika_prod/specs_preguntables.json (claves + etiqueta).
# Sumar una spec es una entrada en ESE json, no tocar codigo. Si la pregunta esta
# en el mensaje y el dato NO figura en la ficha, el CODIGO estampa el honesto y
# saca la afirmacion del modelo: nunca un volcado que no contesta (guion 39) ni
# una spec afirmada sin respaldo (guion 62). El fallback cubre si el archivo falta.
_SPECS_FALLBACK = [
    (["hz", "hercios", "refresco", "refresh"], "los hercios de la pantalla"),
    (["thunderbolt"], "el puerto Thunderbolt"),
    (["ram ampliable", "ampliar la ram", "ram expandible", "slot de ram"],
     "si la RAM se puede ampliar"),
    (["puerto", "puertos", "usb", "hdmi", "displayport"], "los puertos exactos"),
    (["bateria", "autonomia"], "la autonomia de bateria"),
    (["retroilumin"], "la retroiluminacion"),
    (["lector de huella", "huella digital", "huella dactilar", "fingerprint"],
     "el lector de huella"),
]
_SPECS_CACHE = None


# _specs_preguntables se borro: duplicaba el cache de fuente_producto.specs_config,
# que es la fuente unica de las specs preguntables. Nadie la llamaba.

def _specs_del_turno(mensaje, prod, variantes=None, declaradas=None):
    """(respondidas, faltantes) de las specs que el cliente PREGUNTO este turno.

    respondidas: [(etiqueta, valor, rx_pregunta, rx_ficha)] con el valor tal
    como lo dice la FUENTE (mapa `specs` que estampa fuente_producto).
    faltantes:   [(etiqueta, rx_pregunta)] las que la fuente no responde.

    El mapa `specs` es la atadura: antes esto se resolvia por substring sobre
    la prosa de la ficha y daba las dos fallas juntas -el 'gb' de la RAM hacia
    pasar por respondido el almacenamiento (falso positivo: el modelo quedaba
    libre de inventarlo) y una spec escrita distinto se daba por ausente-.
    Si el producto viene SIN mapa (doc viejo, dict de test) se cae a la
    deteccion por substring de siempre, sin valor y sin estampado.

    QUIEN DECIDE QUE PREGUNTO EL CLIENTE: el INTERPRETE. `declaradas` son los
    ids que el modelo tradujo desde el mensaje, atados al enum de la fuente. El
    modelo entiende "resiste que se me caiga el cafe" y una lista de palabras
    escrita a mano no, por mas larga que se haga: cada redaccion nueva la
    rompia. La red de palabras queda SOLO para cuando el interprete no declaro
    nada (`declaradas is None`, provider sin schema estricto o fallo la
    llamada). Una lista vacia NO es lo mismo que None: significa que el modelo
    leyo el mensaje y dice que no pregunta ninguna spec, y eso manda.
    """
    m = _norm(mensaje or "")
    if not m or not isinstance(prod, dict):
        return [], []
    ids_declarados = None
    if declaradas is not None:
        ids_declarados = {str(s) for s in declaradas}
    from app.core.fuente_producto import (aplica, consenso_specs, extraer_specs,
                                          specs_config, texto_ficha)
    mapa = prod.get("specs")
    if not isinstance(mapa, dict):
        # doc viejo o dict de test: se estampa el mapa al vuelo, misma fuente.
        mapa = extraer_specs(prod)
    # VARIANTES del mismo modelo: se contesta lo que todas comparten, y lo que
    # cambia entre versiones se dice como tal en vez de callarlo.
    difieren = {}
    if variantes and len(variantes) > 1:
        mapa, difieren = consenso_specs(variantes)
    base = _norm(texto_ficha(prod))
    categoria = prod.get("categoria") or ""
    respondidas, faltantes = [], []
    for spec in specs_config():
        rx = spec["rx_pregunta"]
        pregunto = (spec["id"] in ids_declarados if ids_declarados is not None
                    else bool(rx.search(m)))
        if not pregunto or not aplica(spec, categoria):
            continue
        valor = mapa.get(spec["id"])
        if not valor and spec["id"] in difieren:
            # cambia segun la version: se dice cual trae que, no se calla
            partes = [f"{v} en {n[0]}" for v, n in difieren[spec['id']][:3]]
            valor = "depende de la version: " + "; ".join(partes)
        if valor:
            respondidas.append((spec["etiqueta"], str(valor), rx,
                                spec["rx_ficha"]))
        elif not spec["rx_ficha"].search(base):
            faltantes.append((spec["etiqueta"], rx))
    return respondidas, faltantes


def _specs_faltantes(mensaje, prod, variantes=None, declaradas=None):
    """[(etiqueta, regex)] de las specs que el cliente PREGUNTO y la fuente NO
    responde. Vacio si no pregunto o si el dato esta."""
    return _specs_del_turno(mensaje, prod, variantes, declaradas)[1]


def _honesto_specs_faltantes(mensaje, prod, variantes=None, declaradas=None):
    """La frase honesta cuando el cliente pregunto una spec que la ficha NO trae."""
    faltan = [et for et, _rx in _specs_faltantes(mensaje, prod, variantes,
                                                 declaradas)]
    if not faltan:
        return ""
    lista = " ni ".join(faltan[:3])
    return (f"Sobre {lista}: la ficha no lo especifica y prefiero no "
            "inventarte el dato. Si lo necesitás, lo consulto con el equipo "
            "y te lo confirmo.")


def estampar_honestidad_specs(texto, mensaje, prod, variantes=None,
                              declaradas=None):
    """La spec preguntada la contesta la FUENTE, no el modelo. Por turno:

    - spec que la fuente SI responde: se sacan las lineas que la afirman con
      otro valor y se ESTAMPA el valor real ('La memoria RAM: 16GB').
    - spec que la fuente NO responde: se sacan las lineas que la afirman y se
      estampa el honesto 'la ficha no lo especifica'.

    Idempotente. Las lineas con plata ($) no se tocan: las audita el
    verificador de montos."""
    respondidas, faltan = _specs_del_turno(mensaje, prod, variantes,
                                           declaradas)
    if not (respondidas or faltan) or not (texto or "").strip():
        return texto
    honesto = _honesto_specs_faltantes(mensaje, prod, variantes, declaradas)
    honesto_n = _norm(honesto)[:40]
    # una linea "habla" de una spec respondida si la nombra; es FIEL si ademas
    # trae alguna parte del valor de la fuente ('512GB SSD' -> '512gb' o 'ssd').
    def _tokens_clave(valor):
        """Lo que hace RECONOCIBLE al valor. Si tiene numero, manda el numero:
        con 'meses' alcanzaba para dar por buena una linea que decia 6 cuando la
        ficha dice 12, y la mentira pasaba (charla real 28-jul)."""
        toks = [t for t in re.split(r"[^a-z0-9]+", _norm(valor)) if t]
        numericos = [t for t in toks if any(c.isdigit() for c in t)]
        return numericos or toks

    tokens_ok = [(rx_p, rx_f, _tokens_clave(valor))
                 for _et, valor, rx_p, rx_f in respondidas]
    out = []
    for linea in texto.split("\n"):
        n = _norm(linea)
        if honesto_n and honesto_n in n:
            out.append(linea)
            continue
        if "$" in linea:
            out.append(linea)
            continue
        if any(rx.search(n) for _et, rx in faltan):
            continue
        infiel = False
        for rx_p, rx_f, toks in tokens_ok:
            if (rx_p.search(n) or rx_f.search(n)) and toks and \
                    not any(t in n for t in toks):
                infiel = True
                break
        if infiel:
            continue
        out.append(linea)
    nuevo = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    pendientes = []
    for etiqueta, valor, _rx_p, _rx_f in respondidas:
        toks = _tokens_clave(valor)
        if toks and not all(t in _norm(nuevo) for t in toks):
            et = re.sub(r"^(?:el|la|los|las|si)\s+", "", etiqueta).strip()
            pendientes.append(f"{et[0].upper()}{et[1:]}: {valor}.")
    if pendientes:
        # el dato va ANTES del cierre, no colgado al final. Estampado despues de
        # "¿avanzamos?" quedaba como una posdata suelta (charla real 28-jul).
        lineas = [x for x in nuevo.split("\n")] if nuevo else []
        corte = len(lineas)
        for i in range(len(lineas) - 1, -1, -1):
            if lineas[i].strip():
                corte = i if "?" in lineas[i] else i + 1
                break
        nuevo = "\n".join(lineas[:corte] + pendientes + lineas[corte:]).strip()
    if honesto and honesto_n not in _norm(nuevo):
        nuevo = (nuevo + "\n\n" + honesto).strip() if nuevo else honesto
    return nuevo


def _poda_prosa(texto, nombres_universo=None):
    """La prosa no puede traer PLATA: precio, total, porcentaje o monto se
    descartan (van por su fragmento, estampados desde la fuente). SI puede
    nombrar un producto para opinar, aconsejar o comparar, y SI puede llevar un
    numero chico que no es plata ('12 meses de garantia', '128GB', '2 unidades'):
    la poda por CUALQUIER digito borraba en silencio la respuesta entera a una
    repregunta de spec y dejaba solo el cierre -charla real del 24-jul: el
    cliente pregunto memoria y disco y le volvio una sola linea suelta-. El
    numero que queda lo audita _verificar_montos contra la evidencia del turno."""
    t = str(texto or "").strip()
    if not t or _RE_PLATA.search(t):
        return ""
    return t


def _cat_real(nombre, tienda_id):
    """Mapea lo que diga el modelo (plural, idioma) a una categoria REAL de la
    tienda. None si no matchea ninguna.

    El match EXACTO por singular no alcanzaba, y fallaba en silencio: el modelo
    emite "tablets Samsung" o "mouse gamer" -la categoria con un adjetivo
    pegado- y el fragmento de opciones se renderizaba VACIO. En el banco del
    29-jul eso dejo el turno 1 sin un solo producto, y como no se mostro nada,
    el turno 2 quedo sin contexto y el bot le contesto con modulos de memoria
    RAM a alguien que preguntaba por la RAM de una tablet. Una palabra de mas
    del modelo tumbaba la charla entera.
    """
    from app.storage.firestore_client import get_categories
    n = _norm(nombre)
    if not n:
        return None
    ns = n[:-1] if n.endswith("s") else n
    reales = [str(c) for c in (get_categories(tienda_id=tienda_id) or [])]
    for c in reales:
        cn = _norm(c)
        cs = cn[:-1] if cn.endswith("s") else cn
        if cn == n or cs == ns or cs == n or cn == ns:
            return c
    # la categoria REAL nombrada adentro de la etiqueta del modelo. Se toma la
    # mas larga, asi "memoria ram" le gana a "memoria" si las dos existen.
    palabras = set(re.findall(r"\w+", n))
    candidatas = []
    for c in reales:
        cn = _norm(c)
        cs = cn[:-1] if cn.endswith("s") else cn
        toks = set(re.findall(r"\w+", cn))
        if toks <= palabras or cs in palabras or cn in n:
            candidatas.append((len(cn), c))
    if candidatas:
        return max(candidatas)[1]
    return None




def _destino_respaldado(destino: str, mensaje: str, estado: dict) -> bool:
    """Un destino que emite el MODELO en un fragmento calculo solo vale si el
    cliente lo dijo: en el mensaje ACTUAL o en la memoria de destinos del
    estado. Espejo de coercionar_destinos del interpretador (bug 'Rosario',
    17-jul), aplicado al generador: en la corrida del 19-jul el modelo invento
    un destino y el turno 1 cobro $9.000 de envio a una provincia que el
    cliente jamas nombro. Si se cae, el render cae a la memoria legitima de
    localidades_envio, nunca inventa."""
    d = _norm(destino)
    if not d:
        return False
    if d in _norm(mensaje or ""):
        return True
    memoria = list(estado.get("localidades_envio") or [])
    memoria.append(estado.get("localidad_envio") or "")
    memoria.append(estado.get("provincia_envio") or "")
    for m in memoria:
        mn = _norm(m)
        if mn and (d in mn or mn in d):
            return True
    return False


def renderizar(fragmentos, universo, estado, tienda_id, trace_id=None,
               presupuesto_pre=None, presupuesto_tools=None, mensaje=None,
               primer_turno=False, respuestas_cat=None):
    """(texto final, tools_called con proof). El texto lo arma el codigo desde
    los fragmentos; cada dato nace de la fuente."""
    from app.core.tools_context import set_current_tienda
    from app.core.tools import calculate_total, cotizar_envio
    from app.core.guia_pedido import opciones_por_categoria
    from app.core.pedido_helpers import _linea_producto
    from app.storage.firestore_client import get_product_by_id, get_all_faq
    from app.core.curadas import estampar_valores
    from app.core.guia_venta_prosa import texto_de
    from app.core.estado_venta import set_current_estado
    set_current_tienda(tienda_id)
    # Resetea las localidades del turno (sin esto la calculadora arrastra
    # envios cotizados de un turno anterior y falla, visto 11-jul).
    # inicio_turno=False: el turno YA arranco en interprete_libre; este
    # re-seteo es solo para las tools y no debe borrar las localidades
    # cotizadas del turno (agujero del 12-jul, cerrado 20-jul).
    set_current_estado(estado if isinstance(estado, dict) else {},
                       inicio_turno=False)
    estado = estado if isinstance(estado, dict) else {}
    nombres = [p.get("nombre") for p in universo if p.get("nombre")]
    ids_validos = {str(p["id"]).upper() for p in universo}
    faq = get_all_faq(tienda_id=tienda_id) or {}
    partes, tools = [], []
    faqs_pegadas = 0
    presu_usado = False
    # Si YA salio un total (por el fragmento presupuesto o por un calculo del
    # modelo), la red de seguridad del final NO reinyecta el pre-armado: sin
    # esto el presupuesto salia DUPLICADO cuando el modelo usaba calculo en vez
    # de presupuesto (visto en el banco, caso ficha mixta).
    total_mostrado = False

    def _prod(pid):
        if pid and str(pid).upper() in ids_validos:
            return get_product_by_id(str(pid).upper(), tienda_id=tienda_id)
        return None

    for f in (fragmentos or []):
        t = f.get("tipo")
        if t == "prosa":
            p = _poda_prosa(f.get("texto"), nombres)
            if p:
                partes.append(p)
            elif str(f.get("texto") or "").strip():
                # RADAR: la prosa podada se perdia en silencio y el cliente
                # recibia una respuesta a medias sin que quedara rastro.
                log.warning("generador_v2_prosa_podada", trace_id=trace_id,
                            texto=str(f.get("texto"))[:140])
        elif t == "producto":
            p = _prod(f.get("producto_id"))
            if p:
                partes.append(_linea_producto(p))
                tools.append({"name": "get_product_details",
                              "result": {"encontrado": True, "producto": p}})
        elif t == "opciones" and f.get("categoria"):
            cat = _cat_real(str(f["categoria"]), tienda_id)
            ops = opciones_por_categoria(cat, tienda_id, k=4) if cat else []
            if ops:
                partes.append(f"De {f['categoria']} tengo, de lo más "
                              "económico para arriba:\n"
                              + "\n".join("- " + _linea_producto(p) for p in ops))
                tools.append({"name": "search_products",
                              "result": {"encontrados": len(ops), "productos": ops}})
        elif t == "presupuesto":
            if presupuesto_pre and not presu_usado:
                partes.append(presupuesto_pre)
                for e in (presupuesto_tools or []):
                    tools.append(e)
                presu_usado = True
                total_mostrado = True
        elif t == "calculo" and f.get("items"):
            items, destinos, destinos_fantasma = [], [], []
            for it in f["items"]:
                pid = str(it.get("producto_id") or "").upper()
                if pid not in ids_validos:
                    continue
                try:
                    items.append({"product_id": pid,
                                  "cantidad": int(it.get("cantidad") or 1)})
                except (TypeError, ValueError):
                    pass
                if it.get("destino"):
                    d = str(it["destino"]).strip()
                    if _destino_respaldado(d, mensaje or "", estado):
                        destinos.append(d)
                    else:
                        destinos_fantasma.append(d)
            if destinos_fantasma:
                log.warning("generador_v2_destino_fantasma",
                            trace_id=trace_id,
                            destinos=destinos_fantasma[:4])
            if not items and (estado.get("carrito") or []):
                # El modelo pidio calcular (ej. split) sin re-listar los items:
                # se usa el pedido VIGENTE del carrito.
                items = [{"product_id": str(c.get("id") or "").upper(),
                          "cantidad": int(c.get("cantidad") or 1)}
                         for c in estado["carrito"] if c.get("id")]
            if not items:
                continue
            # Los destinos cotizados por el CODIGO en este turno mandan sobre
            # los que re-escribe el modelo (19-jul: el modelo re-emitia los
            # destinos del mensaje mal recortados y perdia uno); despues el
            # modelo, ultimo la memoria. Dedup por subconjunto: 'san
            # francisco' tras 'san francisco cordoba' es el mismo lugar.
            from app.core.estado_venta import get_envio_localidades
            from app.core.guia_pedido import (_mismo_destino_ya_visto,
                                              grupos_para_calculo)
            locs_turno = [l for l in (get_envio_localidades() or []) if l]
            locs = (locs_turno or destinos
                    or [l for l in (estado.get("localidades_envio") or []) if l])
            _dedup: list = []
            for l in dict.fromkeys(locs):
                if not _mismo_destino_ya_visto(
                        _norm(l), [_norm(x) for x in _dedup]):
                    _dedup.append(l)
            locs = _dedup
            grupos_arg = grupos_para_calculo(mensaje or "", locs, tienda_id)
            for l in locs:
                q = cotizar_envio(localidad=l)
                if q.get("ok"):
                    e = {"name": "cotizar_envio", "args": {"localidad": l},
                         "result": q}
                    if q.get("proof"):
                        e["proof"] = q["proof"]
                    tools.append(e)
            pago = None
            if f.get("pago"):
                try:
                    if abs(sum(float(x.get("porcentaje") or 0)
                               for x in f["pago"]) - 100) <= 1:
                        pago = [{"medio": x["medio"],
                                 "porcentaje": float(x["porcentaje"])}
                                for x in f["pago"]]
                except (TypeError, ValueError, KeyError):
                    pago = None
            args = {"items": items, "destinos": max(1, len(locs)),
                    **({"items_extra": [{"faq_tema": "costo_envio",
                                         "concepto": "envio"}]} if locs else {}),
                    **({"grupos": grupos_arg} if grupos_arg else {}),
                    **({"pago": pago} if pago else {})}
            res = calculate_total(**args)
            if res.get("ok") and res.get("presentacion"):
                partes.append(res["presentacion"])
                total_mostrado = True
                e = {"name": "calculate_total", "args": args, "result": res}
                if res.get("proof"):
                    e["proof"] = res["proof"]
                tools.append(e)
        elif t == "ficha":
            p = _prod(f.get("producto_id"))
            if p:
                linea = [p.get("nombre") + ":"]
                for c in (f.get("campos") or []):
                    v = _campo_ficha(p, c)
                    if v:
                        linea.append("  " + v)
                if len(linea) > 1:
                    partes.append("\n".join(linea))
                # La ficha CONTESTA: si la spec preguntada no figura en la
                # ficha, sale el honesto estampado por el codigo, no el
                # volcado mudo (caso real guion 39: Hz y Thunderbolt).
                _hon = _honesto_specs_faltantes(mensaje, p)
                if _hon:
                    partes.append(_hon)
                    log.info("generador_v2_ficha_spec_honesta",
                             trace_id=trace_id)
        elif t == "faq":
            # El SOLVER redacta la politica en su voz (con memoria/contexto) desde
            # el grounding de FAQ que se le paso; el codigo YA NO pega la curada
            # (robotizaba, 2500 pruebas). Los numeros que teje NO se podan aca -son
            # legitimos- los protege _verificar_montos contra los valores de la FAQ
            # (que entran enteros a la evidencia). Fallback a la curada estampada
            # SOLO si el solver no redacto (transicional). Tope de dos por turno.
            if faqs_pegadas >= 2:
                log.info("generador_v2_faq_excedente", trace_id=trace_id,
                         tema=f.get("tema"))
                continue
            _txt_faq = str(f.get("texto") or "").strip()
            if not _txt_faq and f.get("tema"):
                data = faq.get(f["tema"]) or {}
                txt = str(data.get("respuesta_curada")
                          or data.get("respuesta") or "").strip()
                _txt_faq = (estampar_valores(txt, data) or txt) if txt else ""
            if _txt_faq:
                from app.core.curadas import podar_muletillas_contra_estado
                _txt_faq = podar_muletillas_contra_estado(_txt_faq, estado)
            if _txt_faq:
                partes.append(_txt_faq)
                faqs_pegadas += 1
                tools.append({"name": "query_faq",
                              "result": {"encontrada": True,
                                         "tema": f.get("tema"),
                                         "respuesta": _txt_faq, "ok": True}})
        elif t == "envio" and f.get("destino"):
            q = cotizar_envio(localidad=str(f["destino"]))
            if q.get("ok"):
                monto = q.get("monto")
                costo = ("gratis" if monto in (0, None)
                         else f"${monto:,}".replace(",", "."))
                zona = str(q.get("provincia") or q.get("zona") or "tu zona")
                partes.append(f"El envío a {zona.replace('_',' ')} sale {costo}. "
                              "Superando los $250.000 va gratis. Orientativo, "
                              "puede variar al confirmar.")
                e = {"name": "cotizar_envio", "args": {"localidad": f["destino"]},
                     "result": q}
                if q.get("proof"):
                    e["proof"] = q["proof"]
                tools.append(e)
        elif t == "criterio":
            # El razonamiento de venta ATADO por grounding mas cita: el modelo
            # redacta la frase para el cliente (natural, no verbatim) apoyado en
            # un bloque jurado, y cita su id. El codigo poda cualquier numero y
            # deja el bloque jurado como evidencia; el verificador de cita
            # chequea que el id exista. Sin numero falso posible; la frase lee
            # natural en vez de recitar el manual.
            # VALVULA (16-jul): sin bloque jurado que aplique, el criterio IGUAL
            # sale, razonado desde los datos del listado (marca, pais, uso) que
            # el prompt le dio; la poda de digitos sigue. El warning es el RADAR
            # de huecos del corpus: cada uno es un bloque de prosa por escribir.
            cid = str(f.get("criterio_id") or "").strip()
            jurado = texto_de(cid) if cid else None
            txt = _poda_prosa(f.get("texto"), nombres)
            if not txt:
                continue
            partes.append(txt)
            if jurado is not None:
                tools.append({"name": "consultar_guia_venta",
                              "result": {"id": cid, "tema": cid,
                                         "texto": jurado, "ok": True}})
                log.info("generador_v2_criterio", trace_id=trace_id, id=cid)
            else:
                log.warning("generador_v2_criterio_sin_bloque",
                            trace_id=trace_id, id=cid or None,
                            texto=txt[:120])
        elif t == "cierre":
            # Sin doble cierre: si la ultima parte ya cerro con una pregunta
            # (la prosa del modelo ya invito a avanzar), no se pega el enlatado.
            ya_pregunta = bool(partes) and partes[-1].rstrip().endswith("?")
            if not ya_pregunta:
                # Pedir la forma de pago SOLO con un total sobre la mesa
                # (queja real de Martin: preguntaba el medio de pago de
                # entrada, en desacorde con saber vender). Sin total, la
                # invitacion es suave y sigue la charla. Y SLOT LLENO NO SE
                # RE-PREGUNTA (caso real 17-jul: el cliente dio el split dos
                # veces y el cierre le volvio a pedir la forma de pago): si
                # la forma de pago ya se conoce o este turno salio un pago
                # dividido, solo se pide la confirmacion.
                pago_conocido = bool(
                    (estado.get("datos_cliente") or {}).get("forma_pago")
                    or any("pago dividido" in p.lower() for p in partes))
                # El SOLVER redacta el cierre en su voz (campo texto del fragmento):
                # se usa TAL CUAL, variado, sin poda de digitos (el "10%" es dato de
                # la fuente, lo protege _verificar_montos). Las lineas fijas de abajo
                # son solo FALLBACK si el solver no escribio el cierre. Sin total, NO
                # se pega nada enlatado: la prosa del solver ya cierra. Se borraron
                # las coletillas rotativas; la repeticion se mide con banco_nrun.
                _cierre_solver = str(f.get("texto") or "").strip()
                if _cierre_solver:
                    partes.append(_cierre_solver)
                elif total_mostrado and primer_turno:
                    partes.append(
                        "¿Cómo lo ves? Cualquier ajuste de modelos, "
                        "cantidades o destinos me decís y lo dejamos a tu "
                        "medida.")
                elif total_mostrado and pago_conocido:
                    partes.append("¿Lo dejamos confirmado así?")
                elif total_mostrado:
                    partes.append(
                        "¿Lo dejamos confirmado? Decime la forma de pago: "
                        "transferencia (10% de descuento) o Mercado Pago.")
    # COBERTURA ESTRUCTURAL (schema required de Martin): toda categoria obligatoria
    # que el solver NO ubico en un fragmento se appendea desde
    # respuestas_por_categoria -que el schema lo OBLIGO a escribir-. Asi el whiff es
    # imposible: o la ordeno el solver en su fragmento, o la pone el codigo aca. Se
    # inserta ANTES del cierre (ultima pregunta) para que lea natural.
    if respuestas_cat:
        _cub = set()
        for f in (fragmentos or []):
            for _k in ("criterio_id", "tema", "categoria"):
                if f.get(_k):
                    _cub.add(str(f[_k]))
        faltantes = [t for c, r in respuestas_cat.items()
                     if c not in _cub
                     and (t := re.sub(r"\s*\[[a-z_]+\]", "",
                                      str((r or {}).get("texto") or "")).strip())]
        if faltantes:
            _pos = len(partes) - (1 if partes and partes[-1].rstrip()
                                  .endswith("?") else 0)
            partes[_pos:_pos] = faltantes
            log.info("generador_v2_cobertura_append", trace_id=trace_id,
                     faltantes=len(faltantes))
    if presupuesto_pre and not total_mostrado:
        # red: el pre-armado va si o si aunque el modelo no lo posiciono, pero
        # solo si NINGUN total salio ya (evita el presupuesto duplicado).
        partes.append(presupuesto_pre)
        for e in (presupuesto_tools or []):
            tools.append(e)
    texto = "\n\n".join(x for x in partes if x)
    log.info("generador_v2_render", trace_id=trace_id,
             fragmentos=len(fragmentos or []), partes=len(partes))
    # RADAR de fragmento PERDIDO. Hasta hoy la unica pista de que un fragmento
    # se habia rendido vacio era comparar dos numeros de la linea de arriba, y
    # nadie los compara. Un fragmento que el modelo emitio y el render descarto
    # es contenido que el cliente NO recibio: tiene que gritar, no susurrar.
    # `presupuesto` y `cierre` son POSICIONALES: le dicen al render donde va el
    # total precalculado o la invitacion, y si no hay total no rinden nada. Eso
    # es correcto, no es contenido perdido, y contarlos dejaba el radar lleno de
    # falsas alarmas -que es como se muere un radar-.
    _CONTENIDO = {"prosa", "producto", "opciones", "ficha", "faq", "envio",
                  "criterio", "calculo"}
    _esperados = [f.get("tipo") for f in (fragmentos or [])
                  if f and f.get("tipo") in _CONTENIDO]
    if len(partes) < len(_esperados):
        log.warning("generador_v2_fragmento_perdido", trace_id=trace_id,
                    emitidos=[f.get("tipo") for f in (fragmentos or []) if f],
                    esperados=len(_esperados), partes=len(partes),
                    categorias=[f.get("categoria") for f in (fragmentos or [])
                                if f and f.get("categoria")])
    return texto, tools
