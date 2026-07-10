"""
GUIA DETERMINISTA DE PEDIDO (8-jul) — el CODIGO arma el presupuesto cuando el
pedido esta definido; el solver no elige ids ni suma a mano.

Cierra el hueco visto en el caso real de multi-envio: el cliente nombro los
tres productos con cantidades y el solver llamo la calculadora con ids
EQUIVOCADOS (TEC0011/MOU0049 por el K120/DX-110 pedidos) y despues tipeo la
cuenta a mano, con renglones sin multiplicar y un solo envio sumado de tres.

El camino nuevo, mismo patron que guia_mas_barato / guia_memoria:
  1. El INTERPRETE (constrained: el campo `pedido` esta atado por enum a los
     productos MOSTRADOS) extrae que productos y cuantos pidio el cliente.
  2. Este modulo reconcilia cada nombre con UN id de los productos vistos
     (match exacto normalizado; el enum ya garantiza el texto) y llama
     calculate_total con esos items, los destinos cotizados y el envio.
  3. El resultado entra a meta.tools_called como una llamada mas: el marcador
     [[PRESUPUESTO]] se estampa con la presentacion sellada, el proof respalda
     los montos en el verificador y el cierre usa el total real.

Conservador como todo: ante CUALQUIER duda (confianza baja, un nombre que no
reconcilia, cantidad rara, la calculadora devuelve error) devuelve None y el
turno sigue por el camino de siempre. Todo o nada: no se calcula un pedido a
medias.
"""
import re
import unicodedata

from app.logger import get_logger

log = get_logger(__name__)

# "total con envio a La Plata": la localidad pedida en el MISMO mensaje se
# cotiza ANTES de sellar, asi el bloque ya trae el flete (visto 8-jul: el
# sellado salio sin envio ni descuento aunque el cliente pidio ambos).
_RE_ENVIO_A = re.compile(
    r"env[ií]o?s?\s+(?:a|hasta|para)\s+([a-zñ][a-zñ .'-]{2,40}?)"
    r"(?=\s+(?:pagando|por|con|y\s)|[?.!,]|$)")
# Pago 100% transferencia dicho en el mensaje; un reparto (mitad/porcentajes/
# dos medios) lo maneja el solver con su propia llamada, la guia no adivina.
_RE_PAGO_TRANSF = re.compile(r"\btransferencia\b")
_RE_PAGO_MIXTO = re.compile(
    r"\bmitad\b|\bpor\s*ciento\b|%|\bcuota\w*\b"
    r"|\bmercado\s*pago\b.{0,60}\btransferencia\b"
    r"|\btransferencia\b.{0,60}\bmercado\s*pago\b")

# Confianza minima del interprete para que el codigo se anime a armar el
# pedido solo. Umbral operativo (config en codigo, no flag).
_CONF_MIN = 0.6
# Techo sano de cantidad por item: un numero disparatado no arma pedido.
_MAX_CANTIDAD = 99


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def items_de_pedido(interp: dict | None,
                    productos_vistos: list[dict] | None) -> list[dict] | None:
    """[{product_id, cantidad}] si el pedido del interprete reconcilia ENTERO
    con los productos vistos (cada nombre matchea UN id). None ante cualquier
    duda: un item que no reconcilia invalida todo el pedido."""
    if not isinstance(interp, dict):
        return None
    try:
        conf = float(interp.get("confianza") or 0)
    except (TypeError, ValueError):
        return None
    if conf < _CONF_MIN:
        return None
    pedido = interp.get("pedido")
    if not isinstance(pedido, list) or not pedido:
        return None
    por_nombre: dict[str, str] = {}
    for pv in (productos_vistos or []):
        if isinstance(pv, dict) and pv.get("nombre") and pv.get("id"):
            por_nombre[_norm(pv["nombre"])] = str(pv["id"]).upper()
    if not por_nombre:
        return None
    items: list[dict] = []
    for it in pedido:
        if not isinstance(it, dict):
            return None
        pid = por_nombre.get(_norm(it.get("producto")))
        try:
            cant = int(it.get("cantidad"))
        except (TypeError, ValueError):
            return None
        if not pid or not (1 <= cant <= _MAX_CANTIDAD):
            return None
        # Un id repetido en el pedido es un artefacto del modelo, no un pedido
        # real ("3 mouse" dos veces): todo-o-nada, no se suma dos veces.
        if any(i["product_id"] == pid for i in items):
            return None
        items.append({"product_id": pid, "cantidad": cant})
    return items or None


def calcular_pedido(interp: dict | None, estado: dict | None,
                    tienda_id: str, trace_id: str | None = None,
                    mensaje: str = "") -> list[dict] | None:
    """Corre calculate_total con el pedido extraido por el interprete. Devuelve
    la lista de entradas estilo tools_called (para mergear en meta) o None si
    la guia no aplica o la calculadora no pudo (stock, envio sin zona, etc.)."""
    estado = estado if isinstance(estado, dict) else {}
    items = items_de_pedido(interp, estado.get("productos_vistos"))
    if not items:
        # Visibilidad: si el interprete SI trajo un pedido pero no reconcilio
        # con los vistos, eso es un hueco a mirar (nombre distinto, visto sin
        # id). Un pedido vacio del interprete es el caso normal y no se loguea.
        if isinstance(interp, dict) and interp.get("pedido"):
            log.warning("guia_pedido_no_reconcilia", trace_id=trace_id,
                        pedido=interp.get("pedido"),
                        vistos=[str((p or {}).get("nombre"))[:40]
                                for p in (estado.get("productos_vistos") or [])[:8]])
        return None
    # Nucleo compartido con las categorias baratas: envio de memoria o del
    # mensaje, pago del mensaje, calculadora sellada.
    return _calcular_items_sellados(items, estado, tienda_id, trace_id, mensaje)


def calcular_categorias_baratas(cats_pedido: list, estado: dict | None,
                                tienda_id: str, trace_id: str | None = None,
                                mensaje: str = "") -> list[dict] | None:
    """'Los mas baratos' sobre un pedido por CATEGORIAS pendiente (caso real
    de Martin, 8-jul): problema CERRADO. El codigo elige el mas barato CON
    stock de cada categoria, arma los items con las cantidades pedidas y sella
    el presupuesto con la misma maquinaria de calcular_pedido. None si alguna
    categoria no tiene producto con stock o la calculadora rechaza (ej. stock
    insuficiente para la cantidad): el turno sigue por el camino normal."""
    if not cats_pedido:
        return None
    from app.core.tools_context import set_current_tienda
    from app.core.guia_compra import mas_barato_con_stock
    set_current_tienda(tienda_id)
    items = []
    for n, cat in cats_pedido:
        p = mas_barato_con_stock(cat)
        if not isinstance(p, dict) or not p.get("id"):
            return None
        items.append({"product_id": str(p["id"]).upper(), "cantidad": int(n)})
    # Reusa el camino sellado: envio de la memoria/mensaje, pago del mensaje.
    return _calcular_items_sellados(items, estado, tienda_id, trace_id, mensaje)


def _calcular_items_sellados(items: list[dict], estado: dict | None,
                             tienda_id: str, trace_id: str | None,
                             mensaje: str) -> list[dict] | None:
    """Nucleo compartido: corre calculate_total sellado para unos items ya
    decididos por el CODIGO (de calcular_pedido o de las categorias baratas)."""
    estado = estado if isinstance(estado, dict) else {}
    from app.core.tools_context import set_current_tienda
    from app.core.tools import calculate_total
    set_current_tienda(tienda_id)
    msg = _norm(mensaje or "")
    # MULTI-DESTINO (charla real 10-jul, dos veces: "un teclado y un mouse a
    # Rio Tercero, un auricular y un teclado a Isla Verde y el resto a
    # Serodino" cobro UN envio de $7.500): se cotizan TODOS los destinos del
    # mensaje, no el primero; calculate_total ya cobra una tarifa por destino
    # con la tarifa de cada localidad cotizada.
    locs = cotizar_destinos_del_mensaje(mensaje or "")
    if not locs:
        locs = [l for l in (estado.get("localidades_envio") or []) if l]
    if not locs:
        _menv = _RE_ENVIO_A.search(msg)
        if _menv:
            from app.core.tools import cotizar_envio
            _q = cotizar_envio(localidad=_menv.group(1).strip())
            if _q.get("ok"):
                from app.core.estado_venta import get_envio_localidades
                locs = get_envio_localidades() or [_menv.group(1).strip()]
    destinos = max(1, len(locs))
    extra = ([{"faq_tema": "costo_envio", "concepto": "envio"}]
             if locs else None)
    pago = None
    if _RE_PAGO_TRANSF.search(msg) and not _RE_PAGO_MIXTO.search(msg):
        pago = [{"medio": "transferencia", "porcentaje": 100}]
    args = {"items": items, "destinos": destinos,
            **({"items_extra": extra} if extra else {}),
            **({"pago": pago} if pago else {})}
    try:
        res = calculate_total(**args)
    except Exception as e:
        log.warning("guia_pedido_calc_error", trace_id=trace_id,
                    error=str(e)[:120])
        return None
    if not isinstance(res, dict) or not res.get("ok") or not res.get("presentacion"):
        log.info("guia_pedido_no_aplica", trace_id=trace_id,
                 motivo=str((res or {}).get("mensaje_para_llm"))[:120])
        return None
    log.info("guia_pedido_calculado", trace_id=trace_id,
             items=len(items), destinos=destinos)
    entrada = {"name": "calculate_total", "args": args, "result": res}
    if res.get("proof"):
        entrada["proof"] = res["proof"]
    return [entrada]


# ── PEDIDO POR CATEGORIAS (prioridad 1 de Martin, caso real WhatsApp 8-jul) ──
# "4 notebooks, 3 teclados y 5 mouse" SIN modelos: el bot NO puede inventar un
# presupuesto 1x-de-cada (eso hizo en real, con un teclado al precio de una
# notebook). La lectura correcta es CERRADA: cantidades + categorias reales de
# la tienda -> mostrar opciones con stock por categoria y preguntar modelos.

_NUM_PAL = {"un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4,
            "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
            "diez": 10, "docena": 12}


def _singular(w: str) -> str:
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


def cantidades_por_categoria(mensaje: str, tienda_id: str) -> list[tuple]:
    """[(cantidad, categoria_real)] extraidos del mensaje: un numero (cifra o
    palabra) pegado a una categoria REAL de la tienda, plural tolerante. Se
    queda con la PRIMERA mencion de cada categoria (en el fraseo natural las
    cantidades totales van primero y la distribucion despues). [] si nada."""
    from app.storage.firestore_client import get_categories
    try:
        cats = {_singular(_norm(c)): str(c) for c in
                (get_categories(tienda_id=tienda_id) or [])}
    except Exception:
        return []
    if not cats:
        return []
    out: list[tuple] = []
    vistas: set[str] = set()
    for m in re.finditer(
            r"\b(\d{1,2}|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|"
            r"nueve|diez|docena)\s+([a-zñ]+)", _norm(mensaje)):
        tok = m.group(1)
        n = int(tok) if tok.isdigit() else _NUM_PAL.get(tok, 0)
        cat = cats.get(_singular(m.group(2)))
        if cat and 1 <= n <= 99 and cat not in vistas:
            vistas.add(cat)
            out.append((n, cat))
    return out


def opciones_por_categoria(categoria: str, tienda_id: str,
                           k: int = 3) -> list[dict]:
    """Las k opciones mas baratas CON stock de una categoria, del catalogo
    real. Determinista: mismo orden siempre."""
    from app.storage.firestore_client import get_all_products
    cat = _norm(categoria)
    prods = [p for p in get_all_products(tienda_id=tienda_id)
             if _norm(p.get("categoria", "")) == cat
             and p.get("stock", 0) > 0
             and isinstance(p.get("precio_ars"), (int, float))]
    prods.sort(key=lambda p: p["precio_ars"])
    return prods[:k]


# Destinos declarados en el MISMO mensaje del pedido ("va a tancacha", "con
# envio a los condores"). El CODIGO los cotiza en el acto: no se depende de
# que el solver llame cotizar_envio (en real a veces no lo hace y el total
# sale SIN envio, visto 8-jul).
_RE_DESTINOS_MSG = re.compile(
    r"\b(?:van?|vaya|env[ií]os?|mandar?|enviad[oa]s?|con\s+env[ií]o)\s+a\s+"
    r"([a-zñ][a-zñ .'-]{2,30}?)"
    r"(?=\s+(?:una?|un|todos?|lo|los|las|el|dime|decime|pasame|pagando|y|e"
    r"|cuanto|dame)\b|[,.?!]|$)")


def pregunta_destinos_pendientes(mensaje: str) -> str:
    """COMPLETITUD del multi-destino: si el cliente declaro destinos que no
    resolvieron zona (localidad ambigua, ej. Isla Verde existe en tres
    provincias), el mensaje lo DICE y pide el dato, en vez de cobrar menos
    envios en silencio (charla real 10-jul). '' si todo resolvio."""
    declarados = []
    for m in list(_RE_DESTINOS_MSG.finditer(_norm(mensaje or "")))[:4]:
        cand = m.group(1).strip(" .,-")
        if len(cand) >= 3 and cand not in declarados:
            declarados.append(cand)
    if not declarados:
        return ""
    from app.core.estado_venta import get_envio_localidades
    resueltos = {str(l).lower() for l in (get_envio_localidades() or [])}
    pendientes = [d for d in declarados if d.lower() not in resueltos]
    if not pendientes:
        return ""
    lista = " y ".join(p.title() for p in pendientes)
    return (f"\n\nOjo: para el envío a {lista} necesito la provincia o el "
            f"código postal, porque hay más de una localidad con ese nombre. "
            f"Pasámelo y te ajusto el total con ese envío incluido.")


def cotizar_destinos_del_mensaje(mensaje: str) -> list[str]:
    """Cotiza deterministamente cada destino nombrado en el mensaje (max 4).
    Devuelve las localidades que RESOLVIERON zona; quedan ademas en la memoria
    del turno (set_envio_localidad, via cotizar_envio) para que el sello y la
    persistencia las vean. Las que no resuelven se ignoran (el solver pide el
    dato como siempre)."""
    from app.core.tools import cotizar_envio
    ok: list[str] = []
    for m in list(_RE_DESTINOS_MSG.finditer(_norm(mensaje or "")))[:4]:
        cand = m.group(1).strip(" .,-")
        if len(cand) < 3 or cand in {c.lower() for c in ok}:
            continue
        try:
            q = cotizar_envio(localidad=cand)
        except Exception:
            continue
        if q.get("ok"):
            ok.append(cand)
    return ok


def mensaje_opciones_categorias(cats_pedido: list[tuple], tienda_id: str,
                                destinos: list[str] | None = None,
                                business_name: str = "la tienda") -> str | None:
    """El MENSAJE ENTERO del turno de pedido por categorias, armado por el
    CODIGO: opciones reales CON stock por categoria + destinos cotizados +
    pregunta de modelos. Cero prosa del LLM: en real el solver listaba
    productos sin stock y re-pedia la provincia ya dada. None si ninguna
    categoria tiene opciones (el turno cae al camino normal)."""
    from app.core.interprete_libre import _linea_producto
    bloques = []
    for n, cat in cats_pedido:
        ops = opciones_por_categoria(cat, tienda_id)
        if not ops:
            continue
        lineas = "\n".join("- " + _linea_producto(p) for p in ops)
        bloques.append(f"Para {'las' if n > 1 else 'la'} {n} de {cat}, "
                       f"opciones con stock:\n{lineas}")
    if not bloques:
        return None
    partes = ["¡Buena compra la que estás armando! Para pasarte el precio "
              "exacto necesito que elijas los modelos.",
              "\n\n".join(bloques)]
    if destinos:
        partes.append("Los envíos van a: " + ", ".join(destinos)
                      + ". Ya los tengo cotizados.")
    partes.append("¿Qué modelo elegís de cada categoría? Si querés vamos por "
                  "los más económicos: decime \"los más baratos\" y te armo "
                  "el total al instante.")
    return "\n\n".join(partes)


def mensaje_presupuesto_sellado(presentacion: str) -> str:
    """El MENSAJE ENTERO del turno 'los mas baratos': plantilla fija del codigo
    + bloque sellado de la calculadora. Cero prosa del LLM (en real la prosa
    listaba OTROS productos y contradecia al bloque)."""
    return ("Listo, te armé el pedido con los más económicos de cada "
            "categoría:\n\n" + presentacion.strip()
            + "\n\nEnvío orientativo, puede variar al confirmar la compra.\n"
            "¿Lo dejamos confirmado? Decime la forma de pago: transferencia "
            "(10% de descuento) o Mercado Pago.")


def instruccion_categorias(cats_pedido: list[tuple]) -> str:
    """Brief para el solver cuando el pedido es por categorias sin modelos."""
    pedido_txt = ", ".join(f"{n} de {c}" for n, c in cats_pedido)
    return (f"\n\n[PEDIDO POR CATEGORIAS SIN MODELOS: el cliente pide {pedido_txt} "
            "pero NO eligio modelos. PROHIBIDO armar un presupuesto o un total: "
            "todavia no hay pedido cerrado. Mostra 2-3 opciones con stock por "
            "categoria usando [[PROD:id]] y pregunta que modelos quiere de cada "
            "una. Si dio destinos de envio, confirmalos sin cotizar de mas.]")


# Instruccion para el solver cuando la guia calculo el pedido: redacta la
# venta alrededor del bloque sellado, sin tocar un numero.
INSTRUCCION_SOLVER = (
    "\n\n[PEDIDO YA CALCULADO: el código armó el presupuesto EXACTO del pedido "
    "del cliente con la calculadora oficial (productos, cantidades, envío por "
    "destino). Escribí tu respuesta de venta y poné el marcador [[PRESUPUESTO]] "
    "donde va el detalle: el código estampa ahí el bloque real. NO escribas vos "
    "ningún precio, subtotal, total ni costo de envío, ni vuelvas a llamar "
    "calculate_total: ya está hecho.]")
