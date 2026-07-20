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
    from app.core.guia_compra import mas_barato_con_stock
    return _calcular_categorias_criterio(
        cats_pedido, estado, tienda_id, trace_id, mensaje,
        elegir=mas_barato_con_stock)


def calcular_categorias_intermedias(cats_pedido: list, estado: dict | None,
                                    tienda_id: str,
                                    trace_id: str | None = None,
                                    mensaje: str = "") -> list[dict] | None:
    """Criterio INTERMEDIO confirmado (11-jul): mismo camino sellado que los
    baratos pero eligiendo la opcion del medio por precio de cada categoria."""
    from app.core.guia_compra import intermedio_con_stock
    return _calcular_categorias_criterio(
        cats_pedido, estado, tienda_id, trace_id, mensaje,
        elegir=intermedio_con_stock)


def _calcular_categorias_criterio(cats_pedido: list, estado: dict | None,
                                  tienda_id: str, trace_id: str | None,
                                  mensaje: str, elegir) -> list[dict] | None:
    if not cats_pedido:
        return None
    from app.core.tools_context import set_current_tienda
    set_current_tienda(tienda_id)
    items = []
    for n, cat in cats_pedido:
        p = elegir(cat)
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
    # Reparto EXPLICITO entre medios dicho en el mensaje ("mitad y mitad",
    # "70 y 30"): la cuenta la sella pago_split (charla real 11-jul 17:22).
    from app.core.pago_split import pago_de_mensaje
    pago = pago_de_mensaje(mensaje or "")
    if not pago and _RE_PAGO_TRANSF.search(msg) and not _RE_PAGO_MIXTO.search(msg):
        pago = [{"medio": "transferencia", "porcentaje": 100}]
    _grupos = grupos_para_calculo(mensaje or "", locs, tienda_id)
    args = {"items": items, "destinos": destinos,
            **({"items_extra": extra} if extra else {}),
            **({"grupos": _grupos} if _grupos else {}),
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
        cats: dict[str, str] = {}
        for c in (get_categories(tienda_id=tienda_id) or []):
            cn = _norm(c)
            # Todas las variantes singulares castellanas como clave:
            # 'auriculares' responde por 'auriculares', 'auriculare' y
            # 'auricular' (el singular real; sin esto 'un auricular' no
            # matcheaba y el reparto por destino salia mal, 11-jul).
            claves = {cn}
            if cn.endswith("s"):
                claves.add(cn[:-1])
            if cn.endswith("es") and len(cn) > 4:
                claves.add(cn[:-2])
            for k in claves:
                cats.setdefault(k, str(c))
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


def categorias_nombradas(mensaje: str, tienda_id: str) -> list[str]:
    """Categorias REALES de la tienda nombradas en el mensaje, con o sin
    cantidad ('el mas barato de esos auriculares' -> ['auriculares']).
    Tolera plural/singular naive y categorias de varias palabras. Sirve para
    saber de QUE esta hablando el cliente en este turno (13-jul: un pendiente
    de categorias de MEMORIA no debe sellarse si el mensaje habla de otra
    categoria)."""
    from app.storage.firestore_client import get_categories
    try:
        categorias = get_categories(tienda_id=tienda_id) or []
    except Exception:
        return []
    msg = _norm(mensaje)
    out: list[str] = []
    for c in categorias:
        cn = _norm(c)
        if not cn:
            continue
        variantes = {cn}
        if cn.endswith("s"):
            variantes.add(cn[:-1])
        else:
            variantes.add(cn + "s")
        if cn.endswith("es") and len(cn) > 4:
            variantes.add(cn[:-2])
        partes = cn.split()
        if len(partes) > 1:
            p0, resto = partes[0], " ".join(partes[1:])
            variantes.add((p0[:-1] if p0.endswith("s") else p0 + "s")
                          + " " + resto)
        if any(re.search(r"\b" + re.escape(v) + r"\b", msg)
               for v in variantes):
            out.append(str(c))
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
    r"\b(?:van?|vaya|iran?|env[ií]os?|mandar?|mandal[oa]s?|envial[oa]s?"
    r"|enviad[oa]s?|con\s+env[ií]o)\s+(?:todos?\s+)?(?:junt[oa]s?\s+)?a\s+"
    r"([a-zñ][a-zñ .'-]{2,30}?)"
    r"(?=\s+(?:una?|un|todos?|lo|los|las|el|dime|decime|pasame|pagando|y|e"
    r"|cuanto|dame|es|son|seran?|sera|lleva|va)\b|[,.?!]|$)")


# "Mandalo a DONDE TE DIJE" no es una localidad: referencias y pronombres
# que el regex de destinos captura pero jamas hay que tratar como lugar
# (visto 11-jul: "para el envio a Donde Te Dije necesito la provincia").
_RE_DESTINO_PRONOMBRE = re.compile(
    r"^(?:a\s+)?(?:donde|adonde|ahi|alla|alli|casa|mi casa|tu casa|su casa"
    r"|el mismo|la misma|ese lugar|este lugar|la otra|el otro|otra direccion"
    r"|otro destino|la direccion|la misma direccion)\b")


def _es_destino_real(cand: str) -> bool:
    """Doble puerta (charla real 19-jul: 'la otra direccion' y 'san francisco
    es' cotizaron como destinos): ni referencia/pronombre, ni texto que NO
    nombre un lugar de la tabla geo. La provincia sticky ya no puede
    completar basura, porque la basura no llega a cotizar."""
    c = (cand or "").strip()
    if not c or _RE_DESTINO_PRONOMBRE.match(c):
        return False
    from app.core.geo_cp import es_lugar_conocido
    return es_lugar_conocido(c)


def _mismo_destino_ya_visto(cand: str, vistos: list[str]) -> bool:
    """'san francisco' despues de 'san francisco cordoba' es el MISMO lugar
    (el cliente lo re-nombra al detallar el grupo): dedup por subconjunto de
    palabras, en cualquier direccion."""
    pc = set(cand.split())
    for v in vistos:
        pv = set(v.split())
        if pc <= pv or pv <= pc:
            return True
    return False


def pregunta_destinos_pendientes(mensaje: str) -> str:
    """COMPLETITUD del multi-destino: si el cliente declaro destinos que no
    resolvieron zona (localidad ambigua, ej. Isla Verde existe en tres
    provincias), el mensaje lo DICE y pide el dato, en vez de cobrar menos
    envios en silencio (charla real 10-jul). '' si todo resolvio."""
    declarados = []
    for m in list(_RE_DESTINOS_MSG.finditer(_norm(mensaje or "")))[:4]:
        cand = m.group(1).strip(" .,-")
        if len(cand) >= 3 and cand not in declarados and _es_destino_real(cand):
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
    for m in list(_RE_DESTINOS_MSG.finditer(_norm(mensaje or "")))[:6]:
        cand = m.group(1).strip(" .,-")
        if (len(cand) < 3 or not _es_destino_real(cand)
                or _mismo_destino_ya_visto(cand, ok)):
            continue
        try:
            q = cotizar_envio(localidad=cand)
        except Exception:
            continue
        if q.get("ok"):
            ok.append(cand)
        if len(ok) >= 4:
            break
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


def mensaje_presupuesto_sellado(presentacion: str, reparto: str = "",
                                titulo: str | None = None,
                                pago_conocido: bool = False) -> str:
    """El MENSAJE ENTERO del turno sellado: plantilla fija del codigo
    + bloque sellado de la calculadora. Cero prosa del LLM (en real la prosa
    listaba OTROS productos y contradecia al bloque). `reparto` (opcional): el
    detalle de que items van a cada destino, ANTES del cierre (charla real de
    Martin 11-jul). `titulo` pisa la primera linea (default: la de los mas
    economicos, que es el flujo de categorias; un pedido puntual o editado
    usa un titulo neutral para no mentir el criterio)."""
    # CIERRE consciente del pago: si la presentacion YA trae el pago aplicado
    # (bloque 'Pago dividido' / 'Total final', el cliente lo eligio este turno),
    # NO se le vuelve a pedir la forma de pago (bug real: pedia el dato que el
    # cliente acababa de dar). Ahi el cierre avanza al siguiente paso.
    pago_ya_elegido = (pago_conocido
                       or "Pago dividido" in presentacion
                       or "Total final" in presentacion)
    if pago_ya_elegido:
        # Frase que AVANZA, sin re-pedir el pago y SIN pregunta (asi no choca
        # con la pregunta de cierre del lead, '¿Seguimos adelante...?', ni
        # repite su 'te lo dejo preparado').
        cierre = ("Si me pasás la localidad, coordino el envío y lo dejamos "
                  "listo.")
    else:
        cierre = ("¿Lo dejamos confirmado? Decime la forma de pago: "
                  "transferencia (10% de descuento) o Mercado Pago.")
    return ((titulo or "Listo, te armé el pedido con los más económicos de "
             "cada categoría:") + "\n\n" + presentacion.strip()
            + (("\n" + reparto.strip("\n") + "\n") if reparto else "")
            + "\n\nEnvío orientativo, puede variar al confirmar la compra.\n"
            + cierre)


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


# ── REPARTO DE ENVIOS POR GRUPO (charla real de Martin, 11-jul 10:42) ────────
# "Un mouse y un teclado a Rosario, un teclado y un auricular a Concordia y
# lo demas a Rio Cuarto": la plata salia bien (una tarifa por destino) pero
# la respuesta NO mostraba el reparto, y el cliente no ve que el bot entendio
# la distribucion. Parser DETERMINISTA todo-o-nada: si los grupos del mensaje
# no reconcilian exactos con las cantidades del pedido, no se muestra nada
# (la plata ya esta bien; el detalle solo sale cuando es seguro).

_RE_RESTO_GRUPO = re.compile(
    r"lo demas|el resto|lo restante|lo que queda|que faltan|lo que falta"
    r"|faltantes")

# Grupo NOMBRADO por su destino, DESPUES de declararlo ("el envio de Jujuy es
# una notebook y un auricular", charla real 19-jul). La referencia puede ser
# un pedazo del destino (la provincia sola, la localidad sin provincia).
_RE_GRUPO_NOMBRADO = re.compile(
    r"env[ií]os?\s+(?:de|a|para)\s+([a-zñ][a-zñ .'-]{2,30}?)\s+"
    r"(?:es|son|seran?|sera|lleva|va con|va)\s+")

# Corte del segmento de un grupo: donde arranca otro envio, el resto, o el
# cliente cambia de tema.
_RE_CORTE_GRUPO = re.compile(
    r"\benv[ií]os?\b|" + _RE_RESTO_GRUPO.pattern +
    r"|\bdime\b|\bdecime\b|\bdame\b|\bpasame\b|\bcuanto\b")


def _hitos_destinos(m_norm: str) -> list[tuple]:
    """[(destino, inicio, fin)] validados por la doble puerta y dedupeados
    por subconjunto ('san francisco' tras 'san francisco cordoba' es el
    mismo lugar)."""
    hitos: list[tuple] = []
    for h in _RE_DESTINOS_MSG.finditer(m_norm):
        cand = h.group(1).strip(" .,-")
        if (len(cand) >= 3 and _es_destino_real(cand)
                and not _mismo_destino_ya_visto(cand, [x[0] for x in hitos])):
            hitos.append((cand, h.start(), h.end()))
    return hitos[:4]


def grupos_envio_del_mensaje(mensaje: str, cats_pedido: list,
                             tienda_id: str) -> list[tuple]:
    """[(destino, [(n, cat)])] cuando el cliente dijo QUE va a cada destino.
    TODO-O-NADA: si los grupos no reconcilian exactos con las cantidades del
    pedido, devuelve [] y el que llama cae al comportamiento sin grupos.
    Entiende las dos formas naturales:
      - items ANTES del destino: "un mouse y un teclado a Rosario"
      - grupo nombrado DESPUES: "el envio de Jujuy es una notebook y un
        auricular" (charla real 19-jul)
      - resto: "lo demas / los que faltan van a X" cierra con lo sobrante."""
    try:
        totales = {cat: int(n) for n, cat in (cats_pedido or [])}
    except (TypeError, ValueError):
        return []
    if not totales:
        return []
    m = _norm(mensaje or "")
    hitos = _hitos_destinos(m)
    if len(hitos) < 2:
        return []

    asignado: dict[str, list] = {}
    limites = sorted(h[1] for h in hitos)

    # 1) Grupos NOMBRADOS por destino ("el envio de jujuy es ...").
    for g in _RE_GRUPO_NOMBRADO.finditer(m):
        ref = set(g.group(1).strip(" .,-").split())
        duenos = [d for d, _, _ in hitos
                  if ref <= set(d.split()) or set(d.split()) <= ref]
        if len(duenos) != 1:
            continue
        fin = min([l for l in limites if l > g.end()] + [len(m)])
        seg = m[g.end():fin]
        corte = _RE_CORTE_GRUPO.search(seg)
        if corte:
            seg = seg[:corte.start()]
        items = cantidades_por_categoria(seg, tienda_id)
        if not items:
            continue
        if duenos[0] in asignado:
            return []  # dos grupos para el mismo destino: ambiguo
        asignado[duenos[0]] = items

    # 2) Items PEGADOS ANTES del destino, y el marcador de resto.
    resto_destino = None
    prev_fin = 0
    for destino, ini, fin in hitos:
        segmento = m[prev_fin:ini]
        prev_fin = fin
        ventana = segmento[-70:]
        if len(segmento) > 70 and " " in ventana:
            ventana = ventana[ventana.find(" ") + 1:]
        if _RE_RESTO_GRUPO.search(ventana):
            if resto_destino:
                return []  # dos "lo demas": ambiguo
            resto_destino = destino
            continue
        if destino in asignado:
            continue
        items = cantidades_por_categoria(ventana, tienda_id)
        if items:
            asignado[destino] = items

    # 3) El resto: lo sobrante va al destino del marcador, o al UNICO destino
    #    sin grupo ("los dos que faltan van a la otra direccion", donde 'la
    #    otra direccion' es referencia y el destino real ya fue nombrado).
    restantes = dict(totales)
    for items in asignado.values():
        for n, cat in items:
            restantes[cat] = restantes.get(cat, 0) - int(n)
    if any(n < 0 for n in restantes.values()):
        return []  # un grupo pide mas de lo que hay: no reconcilia
    sobrante = {c: n for c, n in restantes.items() if n > 0}
    sin_grupo = [d for d, _, _ in hitos if d not in asignado
                 and d != resto_destino]
    if resto_destino is None and len(sin_grupo) == 1 and sobrante \
            and _RE_RESTO_GRUPO.search(m):
        resto_destino = sin_grupo[0]
        sin_grupo = []
    grupos = [(d, items) for d, items in asignado.items()]
    if resto_destino:
        if not sobrante:
            return []
        grupos.append((resto_destino,
                       [(n, c) for c, n in sorted(sobrante.items())]))
    elif sobrante or sin_grupo:
        return []  # quedo pedido sin destino o destino sin grupo: incompleto
    orden = {d: i for i, (d, _, _) in enumerate(hitos)}
    grupos.sort(key=lambda g: orden.get(g[0], 99))
    return grupos


def grupos_para_calculo(mensaje: str, locs: list,
                        tienda_id: str) -> list | None:
    """Los grupos en el formato que consume calculate_total ([{destino,
    cats}]), SOLO si mapean uno a uno con las localidades cotizadas. Salen
    del MENSAJE o, si este turno no los repite ('dale, confirmalo'), de la
    MEMORIA de la charla: sin eso el reprecio de la confirmacion perdia el
    umbral por paquete y el promedio regalaba los envios (guion 48, 20-jul).
    Los grupos computados quedan en el estado para persistir."""
    if len(locs or []) <= 1:
        return None
    g = None
    if (mensaje or "").strip():
        cats_msg = cantidades_por_categoria(mensaje, tienda_id)
        gg = grupos_envio_del_mensaje(mensaje, cats_msg, tienda_id)
        if gg and len(gg) == len(locs):
            # cats como DICTS, no pares-lista: Firestore rechaza arrays
            # anidados y el save entero abortaba en silencio (mismo bug de
            # la amnesia del 8-jul, reproducido por el doble el 20-jul).
            g = [{"destino": d,
                  "cats": [{"n": int(n), "cat": str(c)} for n, c in it]}
                 for d, it in gg]
    if g is None:
        try:
            from app.core.estado_venta import get_current_estado
            gmem = (get_current_estado() or {}).get("grupos_envio") or []
            if gmem and len(gmem) == len(locs):
                g = gmem
        except Exception:
            g = None
    if g:
        try:
            from app.core.estado_venta import get_current_estado
            est = get_current_estado()
            if isinstance(est, dict):
                est["grupos_envio"] = g
        except Exception:
            pass
    return g


def reparto_envios_detalle(mensaje: str, cats_pedido: list,
                           tienda_id: str,
                           detalle_items: list | None = None) -> tuple[str, list]:
    """(bloque de texto 'Reparto de envios', tools de cotizar_envio con su
    proof) o ("", []). El texto detalla que items van a cada destino con la
    tarifa REAL de cada tramo; los proofs respaldan cada monto ante el
    verificador. Los grupos los parsea grupos_envio_del_mensaje.

    detalle_items: el detalle del calculate_total ya corrido ([{id,
    precio_unitario, ...}]). Con el, cada tramo cotiza con el subtotal REAL
    de su paquete y el gratis por umbral sale IGUAL que en el total (19-jul:
    el total decia $7.500 y el reparto mostraba las tarifas crudas)."""
    from app.core.tools import cotizar_envio
    grupos = grupos_envio_del_mensaje(mensaje, cats_pedido, tienda_id)
    if not grupos:
        return "", []

    sub_por_destino: dict[str, int] = {}
    if detalle_items:
        from app.storage.firestore_client import get_product_by_id
        cat_precios: dict[str, set] = {}
        try:
            for it in detalle_items:
                p = get_product_by_id(str(it.get("id")), tienda_id=tienda_id)
                precio = it.get("precio_unitario") or (p or {}).get("precio_ars")
                if p and precio:
                    cat_precios.setdefault(
                        _norm(p.get("categoria", "")), set()).add(int(precio))
        except Exception:
            cat_precios = {}
        for destino, items in grupos:
            sub = 0
            for n, cat in items:
                precios = cat_precios.get(_norm(cat)) or set()
                if len(precios) != 1:
                    sub = 0
                    break
                sub += int(n) * next(iter(precios))
            if sub > 0:
                sub_por_destino[destino] = sub

    lineas = []
    tools = []
    for destino, items in grupos:
        q = cotizar_envio(localidad=destino,
                          subtotal=sub_por_destino.get(destino))
        if not q.get("ok"):
            return "", []
        entrada = {"name": "cotizar_envio",
                   "args": {"localidad": destino}, "result": q}
        if isinstance(q, dict) and q.get("proof"):
            entrada["proof"] = q["proof"]
        tools.append(entrada)
        monto = q.get("monto")
        costo = ("gratis" if monto in (0, None)
                 else f"${monto:,}".replace(",", "."))

        def _label(n, cat):
            c = str(cat)
            if int(n) == 1:  # singular para leerse natural ("1 auricular")
                if c.endswith("es") and len(c) > 4:
                    return c[:-2]
                if c.endswith("s") and len(c) > 3:
                    return c[:-1]
            return c
        det = " y ".join(f"{n} {_label(n, c)}" for n, c in items)
        lineas.append(f"- A {destino.title()}: {det} — envío {costo}")
    if not lineas:
        return "", []
    return ("\nReparto de envíos, como lo pediste:\n"
            + "\n".join(lineas)), tools


# ── EJECUTOR DE LA PRIMITIVA calcular_pedido (selector v2, 11-jul) ───────────
# El selector elige ARGUMENTOS (items editados, destinos, reparto de pago) y
# aca se validan TODOS contra la fuente antes de sellar: nombres que
# reconcilian con carrito/vistos, cantidades sanas, porcentajes que suman
# cien, destinos que resuelven zona. Cualquier argumento que no valida ->
# (None, []) y el turno cae a la cascada: el selector jamas inventa un valor,
# porque ningun valor sale de el.

def ejecutar_calculo_plan(seccion: dict, mensaje: str, estado: dict | None,
                          tienda_id: str,
                          trace_id: str | None = None) -> tuple[str | None, list]:
    """(texto sellado del presupuesto, tools con proof) o (None, [])."""
    estado = estado if isinstance(estado, dict) else {}
    seccion = seccion if isinstance(seccion, dict) else {}
    items_arg = seccion.get("items")
    destinos_arg = seccion.get("destinos")
    pago_arg = seccion.get("pago")

    # 1. ITEMS: nombres del selector reconciliados a ids REALES del carrito
    #    o de lo mostrado. Todo o nada.
    fuentes: dict[str, str] = {}
    for src in ((estado.get("carrito") or [])
                + (estado.get("productos_vistos") or [])):
        if isinstance(src, dict) and src.get("id") and src.get("nombre"):
            fuentes.setdefault(_norm(src["nombre"]), str(src["id"]).upper())
    items: list[dict] = []
    grupos: list[tuple] = []  # (destino, cantidad, nombre) por renglon
    if items_arg:
        for it in items_arg:
            if not isinstance(it, dict):
                return None, []
            nom = _norm(it.get("producto"))
            pid = fuentes.get(nom)
            if not pid and nom:
                hits = {v for k, v in fuentes.items() if nom in k or k in nom}
                pid = hits.pop() if len(hits) == 1 else None
            try:
                cant = int(it.get("cantidad"))
            except (TypeError, ValueError):
                return None, []
            if not pid or not (1 <= cant <= _MAX_CANTIDAD):
                return None, []
            previo = next((x for x in items if x["product_id"] == pid), None)
            if previo:
                previo["cantidad"] += cant
            else:
                items.append({"product_id": pid, "cantidad": cant})
            if it.get("destino"):
                grupos.append((str(it["destino"]).strip(), cant,
                               str(it.get("producto") or "")))
    else:
        items = [{"product_id": str(c.get("id") or "").upper(),
                  "cantidad": int(c.get("cantidad") or 1)}
                 for c in (estado.get("carrito") or []) if c.get("id")]
    if not items:
        return None, []

    # 2. PAGO: porcentajes que suman cien o nada.
    pago = None
    if pago_arg:
        try:
            total_pct = sum(float(p.get("porcentaje") or 0)
                            for p in pago_arg if isinstance(p, dict))
        except (TypeError, ValueError):
            return None, []
        if abs(total_pct - 100) > 1:
            return None, []
        pago = [{"medio": str(p.get("medio") or ""),
                 "porcentaje": float(p.get("porcentaje") or 0)}
                for p in pago_arg if isinstance(p, dict)]

    # 3. DESTINOS: los explicitos (o los de los renglones) tienen que
    #    resolver TODOS; sin explicitos, se re-cotizan los de memoria.
    from app.core.tools import cotizar_envio, calculate_total
    from app.core.tools_context import set_current_tienda
    set_current_tienda(tienda_id)
    tools_env: list[dict] = []
    locs: list[str] = []
    for l in list(destinos_arg or []) + [g[0] for g in grupos]:
        ln = _norm(l)
        if ln and ln not in {_norm(x) for x in locs}:
            locs.append(str(l).strip())
    explicitos = bool(locs)
    if not explicitos:
        locs = [l for l in (estado.get("localidades_envio") or []) if l]
    for l in list(locs):
        q = cotizar_envio(localidad=l)
        if not q.get("ok"):
            if explicitos:
                return None, []  # un destino elegido que no resuelve: escape
            locs.remove(l)
            continue
        e = {"name": "cotizar_envio", "args": {"localidad": l}, "result": q}
        if q.get("proof"):
            e["proof"] = q["proof"]
        tools_env.append(e)

    extra = ([{"faq_tema": "costo_envio", "concepto": "envio"}]
             if locs else None)
    _grupos = grupos_para_calculo(mensaje or "", locs, tienda_id)
    args = {"items": items, "destinos": max(1, len(locs)),
            **({"items_extra": extra} if extra else {}),
            **({"grupos": _grupos} if _grupos else {}),
            **({"pago": pago} if pago else {})}
    try:
        res = calculate_total(**args)
    except Exception as e:
        log.warning("ejecutar_calculo_plan_error", trace_id=trace_id,
                    error=str(e)[:120])
        return None, []
    if not isinstance(res, dict) or not res.get("ok") \
            or not res.get("presentacion"):
        return None, []
    entrada = {"name": "calculate_total", "args": args, "result": res}
    if res.get("proof"):
        entrada["proof"] = res["proof"]
    log.info("ejecutar_calculo_plan_ok", trace_id=trace_id,
             items=len(items), destinos=len(locs), con_pago=bool(pago))
    texto = ("Así queda tu pedido:\n\n" + res["presentacion"].strip()
             + "\n\nEnvío orientativo, puede variar al confirmar la compra."
               "\n¿Lo dejamos confirmado así?")
    return texto, [entrada] + tools_env
