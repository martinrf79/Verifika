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
CAMPOS_FICHA = ["procedencia", "garantia", "material", "descripcion"]

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
    # producto resuelto por el interprete
    if interp and interp.get("producto_resuelto"):
        from app.core.pedido_helpers import _resolver_nombre_a_producto
        from app.storage.firestore_client import get_all_products
        _add(_resolver_nombre_a_producto(
            interp["producto_resuelto"], get_all_products(tienda_id=tienda_id)))
    # CONTACTOR: los campos ESTRUCTURADOS del interprete alimentan el universo,
    # no solo el texto del mensaje. Asi la categoria pedida aun no mostrada
    # (solicitud_nueva, atada al enum de categorias) y los productos del pedido o
    # consultados (atados al enum de lo visto) SIEMPRE entran al enum, aunque el
    # detector de categorias del mensaje no los pesque. Reemplaza por atadura las
    # guias de texto que el hub le pasaba al solver viejo.
    if isinstance(interp, dict):
        for s in (interp.get("solicitud_nueva") or []):
            if isinstance(s, dict) and s.get("categoria"):
                cat = str(s["categoria"])
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
                    from app.core.pedido_helpers import _resolver_nombre_a_producto
                    from app.storage.firestore_client import get_all_products
                    _todos = get_all_products(tienda_id=tienda_id)
                _add(_resolver_nombre_a_producto(nom, _todos))
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


def _schema(ids, temas, criterios):
    ids_o = ids + [None]
    return {
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


def _prompt(mensaje, historial, universo, temas, estado, presupuesto_pre=None,
            criterios_menu="", prefs=None, nota_no_vendida="", faq_menu=""):
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
    hist = ("\n".join(f"{h.get('role')}: {str(h.get('content'))[:160]}"
                      for h in (historial or [])[-4:]))
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
        "(procedencia/garantia/material/descripcion).\n"
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
        f"{car_txt}{dest_txt}{prefs_txt}\n\n"
        + (f"\n\nPRESUPUESTO YA ARMADO por el sistema (ponelo con un "
           f"fragmento tipo 'presupuesto'):\n{presupuesto_pre}" if presupuesto_pre else "")
        + f"\n\nCharla:\n{hist}\n\nMensaje del cliente:\n{mensaje}\n\n"
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
    from openai import OpenAI
    import os
    key = (settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
           or os.environ.get("GEMINI_APY_KEY"))
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
                     criterios_menu, prefs, nota_no_vendida, faq_menu)
    schema = _schema(ids, temas, criterios)

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
        if isinstance(frags, list) and frags:
            log.info("generador_v2_ok", trace_id=trace_id, n=len(frags))
            return frags[:_MAX_FRAGMENTOS], universo, presu_txt, presu_tools
    except Exception as e:
        log.warning("generador_v2_error", trace_id=trace_id, error=str(e)[:150])
    return None, universo, presu_txt, presu_tools


# ── 3. RENDER: el codigo estampa cada dato desde la fuente ───────────────────
_RE_DIGITO = re.compile(r"\d")


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


def _specs_preguntables():
    """[(regex, etiqueta, claves)] desde el config, cacheado; fallback al codigo."""
    global _SPECS_CACHE
    if _SPECS_CACHE is not None:
        return _SPECS_CACHE
    entradas = None
    try:
        import json
        import os
        ruta = os.path.join(os.path.dirname(__file__), "..", "..", "data",
                            "clientes", "verifika_prod", "specs_preguntables.json")
        with open(ruta, encoding="utf-8") as f:
            data = json.load(f)
        entradas = [(s.get("claves") or [], s.get("etiqueta") or "")
                    for s in (data.get("specs") or []) if s.get("etiqueta")]
    except Exception:
        entradas = None
    compiladas = []
    for claves, etiqueta in (entradas or _SPECS_FALLBACK):
        cl = [_norm(c) for c in claves if c]
        pat = "|".join(r"\b" + re.escape(c) + r"\b" for c in cl)
        if pat and etiqueta:
            compiladas.append((re.compile(pat), etiqueta, cl))
    _SPECS_CACHE = compiladas
    return _SPECS_CACHE


def _specs_faltantes(mensaje, prod):
    """[(etiqueta, regex)] de las specs que el cliente PREGUNTO y que la ficha del
    producto NO trae. Vacio si no pregunto o si el dato figura en la ficha."""
    m = _norm(mensaje or "")
    if not m or not isinstance(prod, dict):
        return []
    base = _norm(" ".join(str(prod.get(c) or "") for c in
                          ("nombre", "descripcion", "garantia_detalle",
                           "origen", "modelo")))
    return [(etiqueta, rx) for rx, etiqueta, _cl in _specs_preguntables()
            if rx.search(m) and not rx.search(base)]


def _honesto_specs_faltantes(mensaje, prod):
    """La frase honesta cuando el cliente pregunto una spec que la ficha NO trae."""
    faltan = [et for et, _rx in _specs_faltantes(mensaje, prod)]
    if not faltan:
        return ""
    lista = " ni ".join(faltan[:3])
    return (f"Sobre {lista}: la ficha no lo especifica y prefiero no "
            "inventarte el dato. Si lo necesitás, lo consulto con el equipo "
            "y te lo confirmo.")


def estampar_honestidad_specs(texto, mensaje, prod):
    """Refuerzo de honestidad por turno: si el cliente pregunto una spec AUSENTE
    de la ficha, SACA las lineas de prosa que la afirman (el modelo no puede
    asegurar lo que la fuente no dice) y ESTAMPA el honesto. Idempotente. Las
    lineas con dato duro ($) y la propia linea honesta se conservan."""
    faltan = _specs_faltantes(mensaje, prod)
    if not faltan or not (texto or "").strip():
        return texto
    honesto = _honesto_specs_faltantes(mensaje, prod)
    honesto_n = _norm(honesto)[:40]
    out = []
    for linea in texto.split("\n"):
        n = _norm(linea)
        if honesto_n and honesto_n in n:
            out.append(linea)
            continue
        if "$" not in linea and any(rx.search(n) for _et, rx in faltan):
            continue
        out.append(linea)
    nuevo = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    if honesto and honesto_n not in _norm(nuevo):
        nuevo = (nuevo + "\n\n" + honesto).strip() if nuevo else honesto
    return nuevo


def _poda_prosa(texto, nombres_universo=None):
    """La prosa no puede traer DATOS DUROS: si tiene un digito se descarta el
    fragmento (todo numero/precio/spec va por su fragmento, estampado desde la
    fuente). SI puede nombrar un producto para opinar, aconsejar o comparar: el
    nombre no es un dato que pueda salir mal (el universo esta atado al enum, el
    modelo no puede inventar uno). Sin esto, una pregunta de consejo ('¿el mas
    barato sirve para la oficina?') perdia toda la respuesta razonada."""
    t = str(texto or "").strip()
    if not t or _RE_DIGITO.search(t):
        return ""
    return t


def _cat_real(nombre, tienda_id):
    """Mapea lo que diga el modelo (plural, idioma) a una categoria REAL de la
    tienda por singular normalizado. None si no matchea ninguna."""
    from app.storage.firestore_client import get_categories
    n = _norm(nombre)
    ns = n[:-1] if n.endswith("s") else n
    for c in (get_categories(tienda_id=tienda_id) or []):
        cn = _norm(c)
        cs = cn[:-1] if cn.endswith("s") else cn
        if cn == n or cs == ns or cs == n or cn == ns:
            return str(c)
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
               primer_turno=False):
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
    if presupuesto_pre and not total_mostrado:
        # red: el pre-armado va si o si aunque el modelo no lo posiciono, pero
        # solo si NINGUN total salio ya (evita el presupuesto duplicado).
        partes.append(presupuesto_pre)
        for e in (presupuesto_tools or []):
            tools.append(e)
    texto = "\n\n".join(x for x in partes if x)
    log.info("generador_v2_render", trace_id=trace_id,
             fragmentos=len(fragmentos or []), partes=len(partes))
    return texto, tools
