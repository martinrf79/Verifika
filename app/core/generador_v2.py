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

from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

_TIMEOUT_S = 12
_MAX_FRAGMENTOS = 8
CAMPOS_FICHA = ["procedencia", "garantia", "material", "descripcion"]


def _norm(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


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
        from app.core.interprete_libre import _resolver_nombre_a_producto
        from app.storage.firestore_client import get_all_products
        _add(_resolver_nombre_a_producto(
            interp["producto_resuelto"], get_all_products(tienda_id=tienda_id)))
    # categorias mencionadas: 4 mas baratas + el intermedio de cada una
    cats = cantidades_por_categoria(mensaje or "", tienda_id)
    cats_nombres = {c for _, c in cats}
    # tambien las categorias sueltas nombradas sin cantidad
    from app.storage.firestore_client import get_categories
    m = _norm(mensaje)
    for c in (get_categories(tienda_id=tienda_id) or []):
        cn = _norm(c)
        sing = cn[:-1] if cn.endswith("s") else cn
        if sing in m or cn in m:
            cats_nombres.add(str(c))
    for cat in cats_nombres:
        for p in opciones_por_categoria(cat, tienda_id, k=4):
            _add(p)
        _add(intermedio_con_stock(cat))
    return list(por_id.values())[:16]


# ── 2. SCHEMA de fragmentos (atado por enum) ─────────────────────────────────
def presupuesto_precalculado(mensaje, estado, tienda_id, interp=None):
    """Lo CERRADO al codigo: si el pedido es determinable (cantidades por
    categoria con criterio barato, o carrito vigente con total/split), el
    codigo calcula el presupuesto SELLADO. Devuelve (texto, tools) o
    (None, []). El modelo NO arma la cuenta: solo la posiciona."""
    from app.core.tools_context import set_current_tienda
    from app.core.estado_venta import set_current_estado
    set_current_tienda(tienda_id)
    set_current_estado(estado if isinstance(estado, dict) else {})
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
        quiere_total = bool(re.search(
            r"\btotal\b|como queda|cuanto (queda|es|sale)|precio final|"
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
                rep, rep_tools = reparto_envios_detalle(mensaje, cats, tienda_id)
                bloque = tools[0]["result"]["presentacion"].strip()
                if rep:
                    bloque += "\n" + rep.strip()
                return (bloque, tools + rep_tools)
    except Exception as e:
        log.warning("presupuesto_precalculado_error", error=str(e)[:120])
    return None, []


def _schema(ids, temas):
    ids_o = ids + [None]
    return {
        "type": "object", "additionalProperties": False,
        "properties": {"fragmentos": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "tipo": {"type": "string", "enum": [
                    "prosa", "producto", "opciones", "calculo", "presupuesto",
                    "ficha", "faq", "envio", "cierre"]},
                "texto": {"type": ["string", "null"]},
                "producto_id": {"type": ["string", "null"], "enum": ids_o},
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
            "required": ["tipo", "texto", "producto_id", "categoria", "items",
                         "campos", "tema", "destino", "pago"]}}},
        "required": ["fragmentos"]}


def _prompt(mensaje, historial, universo, temas, estado, presupuesto_pre=None):
    prods = "\n".join(
        f"  {p['id']} = {p['nombre']} | ${int(p.get('precio_ars',0)):,}".replace(",", ".")
        + f" | stock {p.get('stock','?')}" for p in universo)
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
        "- prosa: tu texto de venta libre y tu RAZONAMIENTO. PROHIBIDO poner "
        "numeros o precios aca (eso va por su fragmento). SI podes nombrar un "
        "producto del listado para opinar, aconsejar o comparar. Usala para "
        "saludar, hacer puente, decir si un producto sirve para lo que el "
        "cliente quiere, recomendar con criterio, cerrar hablado.\n"
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
        "- faq: politica de la tienda -> tema.\n"
        "- envio: cotizar un destino -> destino.\n"
        "- cierre: invitar a comprar y pedir forma de pago.\n\n"
        f"PRODUCTOS disponibles (usa SOLO estos ids):\n{prods}\n\n"
        f"TEMAS de FAQ disponibles: {faq_list}\n"
        f"{car_txt}{dest_txt}\n\n"
        + (f"\n\nPRESUPUESTO YA ARMADO por el sistema (ponelo con un "
           f"fragmento tipo 'presupuesto'):\n{presupuesto_pre}" if presupuesto_pre else "")
        + f"\n\nCharla:\n{hist}\n\nMensaje del cliente:\n{mensaje}\n\n"
        "Reglas: responde TODAS las cosas que pregunto el cliente, cada una "
        "por su fragmento; NUNCA dejes una pregunta sin responder. Si el "
        "cliente pide tu OPINION o consejo (si un producto le sirve para algo, "
        "si le conviene, comparaciones), mostralo con un fragmento producto y "
        "dá tu recomendacion razonada en prosa (sin numeros). Si el cliente "
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
                             interp=None, trace_id=None):
    """La llamada a Gemini que compone la respuesta como fragmentos atados.
    Devuelve (fragmentos, universo) o (None, universo) ante error."""
    universo = universo_productos(mensaje, estado, tienda_id, interp)
    ids = [p["id"] for p in universo]
    from app.storage.firestore_client import get_all_faq
    temas = sorted((get_all_faq(tienda_id=tienda_id) or {}).keys())
    if not ids:
        # sin universo el modelo no tiene con que; igual puede faq/prosa/cierre
        ids = ["_none_"]
    # Lo CERRADO al codigo: presupuesto pre-calculado si el pedido es
    # determinable. El modelo solo lo POSICIONA (fragmento presupuesto).
    presu_txt, presu_tools = presupuesto_precalculado(
        mensaje, estado, tienda_id, interp)
    prompt = _prompt(mensaje, historial, universo, temas, estado, presu_txt)
    schema = _schema(ids, temas)

    def _call():
        c = _cliente_gemini()
        r = c.chat.completions.create(
            model=(settings.GEMINI_MODEL or "gemini-flash-latest"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6, max_tokens=1500,
            extra_body={"reasoning_effort": "none"},
            response_format={"type": "json_schema", "json_schema": {
                "name": "respuesta", "strict": True, "schema": schema}})
        return r.choices[0].message.content or ""
    try:
        raw = await asyncio.wait_for(asyncio.to_thread(_call), _TIMEOUT_S)
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
        return str(prod.get("descripcion") or "").strip()[:200]
    return ""


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


def renderizar(fragmentos, universo, estado, tienda_id, trace_id=None,
               presupuesto_pre=None, presupuesto_tools=None):
    """(texto final, tools_called con proof). El texto lo arma el codigo desde
    los fragmentos; cada dato nace de la fuente."""
    from app.core.tools_context import set_current_tienda
    from app.core.tools import calculate_total, cotizar_envio
    from app.core.guia_pedido import opciones_por_categoria
    from app.core.interprete_libre import _linea_producto
    from app.storage.firestore_client import get_product_by_id, get_all_faq
    from app.core.curadas import estampar_valores
    from app.core.estado_venta import set_current_estado
    set_current_tienda(tienda_id)
    # Resetea las localidades del turno (sin esto la calculadora arrastra
    # envios cotizados de un turno anterior y falla, visto 11-jul).
    set_current_estado(estado if isinstance(estado, dict) else {})
    estado = estado if isinstance(estado, dict) else {}
    nombres = [p.get("nombre") for p in universo if p.get("nombre")]
    ids_validos = {str(p["id"]).upper() for p in universo}
    faq = get_all_faq(tienda_id=tienda_id) or {}
    partes, tools = [], []
    presu_usado = False

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
        elif t == "calculo" and f.get("items"):
            items, destinos = [], []
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
                    destinos.append(str(it["destino"]).strip())
            if not items and (estado.get("carrito") or []):
                # El modelo pidio calcular (ej. split) sin re-listar los items:
                # se usa el pedido VIGENTE del carrito.
                items = [{"product_id": str(c.get("id") or "").upper(),
                          "cantidad": int(c.get("cantidad") or 1)}
                         for c in estado["carrito"] if c.get("id")]
            if not items:
                continue
            locs = destinos or [l for l in (estado.get("localidades_envio") or []) if l]
            for l in list(dict.fromkeys(locs)):
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
                    **({"pago": pago} if pago else {})}
            res = calculate_total(**args)
            if res.get("ok") and res.get("presentacion"):
                partes.append(res["presentacion"])
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
        elif t == "faq" and f.get("tema"):
            data = faq.get(f["tema"]) or {}
            txt = str(data.get("respuesta_curada") or data.get("respuesta") or "").strip()
            est = estampar_valores(txt, data) if txt else None
            if est or txt:
                partes.append(est or txt)
                tools.append({"name": "query_faq",
                              "result": {"encontrada": True, "tema": f["tema"],
                                         "respuesta": est or txt, "ok": True}})
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
        elif t == "cierre":
            # Sin doble cierre: si la ultima parte ya cerro con una pregunta
            # (la prosa del modelo ya invito a avanzar), no se pega el enlatado.
            ya_pregunta = bool(partes) and partes[-1].rstrip().endswith("?")
            if not ya_pregunta:
                partes.append(
                    "¿Lo dejamos confirmado? Decime la forma de pago: "
                    "transferencia (10% de descuento) o Mercado Pago.")
    if presupuesto_pre and not presu_usado:
        # red: el pre-armado va si o si aunque el modelo no lo posiciono
        partes.append(presupuesto_pre)
        for e in (presupuesto_tools or []):
            tools.append(e)
    texto = "\n\n".join(x for x in partes if x)
    log.info("generador_v2_render", trace_id=trace_id,
             fragmentos=len(fragmentos or []), partes=len(partes))
    return texto, tools
