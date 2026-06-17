"""
PROVIDER — motor determinista total: el codigo calcula en TODOS los turnos.

Inversion definitiva del control. Hoy los numeros finales nacen solo cuando el
Solver decide llamar la calculadora (ahi esta la grieta: a veces suma a mano).
El Provider es el paso post-interpretador que calcula SIEMPRE, aunque nadie lo
pida:

  - PRODUCTO EN FOCO: el producto al que se refiere el cliente, resuelto del
    registro de sesion por codigo (resolver_pedido), cotizado con calculate_total
    (reusa cotizar_codigo entero: envio y transferencia incluidos). Si la
    referencia matchea DOS productos, cotiza ambos (A/B).
  - PEDIDO VIGENTE: el carrito ya presupuestado, recalculado este turno con sus
    ids reales (mas envio y transferencia si aplican).
  - ENVIO: con la localidad conocida (del turno o de la memoria), la tarifa real
    de la tabla CP/provincia. Sin localidad, la directiva es UNA: pedir el CP.
    Los CPs no los arma nadie: son tabla que el codigo consulta (app/core/envio).
  - CATALOGO: si el interpretador detecto intencion de producto, la busqueda
    corre por codigo y los resultados entran como evidencia (absorbe
    BUSQUEDA_POR_CODIGO dentro del contrato).

Todo eso se entrega al Solver en UN solo contrato por turno (hoy las 4-5
inyecciones de texto compiten entre si en charlas largas). El Solver solo decide
cuales numeros pegar y vende alrededor; jamas calcula.

Cada calculo del Provider se registra como tool sintetica (con su proof) para
que el verificador y la compuerta respalden los numeros que el Solver cite.

Detras del flag PROVIDER (default off). Funcion testeable offline con catalogo
y FAQ monkeypatcheados, igual que cotizar_codigo.
"""
import json
import re
from typing import Optional

from app.core.cotizar_codigo import (
    quiere_cotizar, cotizar_pedido, cotizar_pedido_ab, presentacion_ab,
    _menciona_envio, _menciona_transferencia, _concepto_transferencia,
    _zona_clara,
)
from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()


def _record(name: str, args: dict, result: dict) -> dict:
    """Registro sintetico con la misma forma que un tool call real, para que
    _build_evidence_from_tools y la telemetria respalden estos numeros."""
    return {"name": name, "args": args, "result": result,
            "proof": (result or {}).get("proof"),
            "result_keys": list((result or {}).keys())}


def _cotizar_items(items: list[dict], mensaje: str, tienda_id: str,
                   localidad: str, registros: list,
                   trace_id: Optional[str] = None) -> Optional[dict]:
    """calculate_total sobre items arbitrarios (el carrito), componiendo los
    mismos extras que cotizar_pedido: envio si el cliente lo nombra y la zona es
    clara, transferencia si la nombra y la tienda la tiene. Reintenta sin el
    extra que falle: el presupuesto nunca se pierde por un extra."""
    from app.core.tools import calculate_total, cotizar_envio
    from app.core.tools_context import set_current_tienda
    set_current_tienda(tienda_id)

    # El envio entra al calculo SIEMPRE que la zona sea conocida, la nombre o
    # no este turno: si el cliente ya dio su localidad, "el total final" es con
    # envio. Sin el total cerrado, el modelo suma producto+envio a mano (clase
    # cazada por el atacante caotico: cifra correcta pero sin respaldo).
    extras: list[dict] = []
    if _zona_clara(localidad):
        try:
            env = cotizar_envio(localidad=localidad, subtotal=0)
            if env.get("ok") and env.get("concepto"):
                extras.append({"faq_tema": "costo_envio",
                               "concepto": env["concepto"]})
        except Exception as e:
            log.warning("provider_envio_carrito_error", trace_id=trace_id,
                        error=str(e)[:120])
    if settings.COTIZA_TRANSFERENCIA and _menciona_transferencia(mensaje):
        concepto_t = _concepto_transferencia(tienda_id)
        if concepto_t:
            extras.append({"faq_tema": "descuento_transferencia",
                           "concepto": concepto_t})

    intentos = [extras] + ([[]] if extras else [])
    for ex in intentos:
        try:
            calc = calculate_total(items=items, items_extra=ex or None)
        except Exception as e:
            log.warning("provider_carrito_error", trace_id=trace_id,
                        error=str(e)[:160])
            return None
        if isinstance(calc, dict) and calc.get("ok"):
            registros.append(_record(
                "calculate_total",
                {"items": items, "items_extra": ex or None}, calc))
            return calc
    return None


# Atributos del producto que entran a la FICHA, en orden de salida. La etiqueta
# es como la lee el Solver. Lo que el producto no tenga, no aparece: la ficha es
# TODO lo que la tienda sabe, ni mas ni menos.
_CAMPOS_FICHA = (
    ("garantia_detalle", "garantia"),
    ("origen", "origen"),
    ("material", "material"),
    ("contenido_caja", "contenido de la caja"),
    ("color", "color"),
    ("dimensiones", "dimensiones"),
    ("peso_gramos", "peso en gramos"),
    ("uso_recomendado", "uso recomendado"),
    ("caracteristicas_extra", "caracteristicas"),
    ("stock", "stock en unidades"),
)


def _ficha_producto(producto_id: str, tienda_id: str,
                    trace_id: Optional[str] = None) -> Optional[str]:
    """FICHA REAL del producto: los atributos que la fuente tiene (garantia,
    origen, material, contenido de caja...), en una linea por atributo. El
    Solver responde garantia/procedencia/materiales DESDE aca, y lo que no
    esta aca no existe: lo dice honesto en vez de inventarlo."""
    try:
        from app.core.tools import get_product_by_id
        p = get_product_by_id(producto_id, tienda_id=tienda_id)
    except Exception as e:
        log.warning("provider_ficha_error", trace_id=trace_id,
                    error=str(e)[:120])
        return None
    if not isinstance(p, dict):
        return None
    lineas = []
    for campo, etiqueta in _CAMPOS_FICHA:
        v = p.get(campo)
        if v in (None, "", [], {}):
            continue
        if campo == "garantia_detalle":
            lineas.append(f"- garantia: {v}")
        elif campo == "stock":
            lineas.append(f"- stock en unidades: {v}")
        else:
            lineas.append(f"- {etiqueta}: {v}")
    # garantia_meses como respaldo si no hay detalle.
    if not any(ln.startswith("- garantia") for ln in lineas) \
            and p.get("garantia_meses"):
        lineas.insert(0, f"- garantia: {p['garantia_meses']} meses")
    if not lineas:
        return None
    return "\n".join(lineas)


# Muletillas que NO describen producto: si la query es el mensaje crudo del
# cliente, se filtran antes de buscar ("estoy buscando 3 teclados blancos los
# mas economicos con envio a villa rumipal" matcheaba 0 y degradaba a TODO el
# catalogo: la evidencia salia basura).
_STOP_QUERY = frozenset((
    "hola", "buenas", "buenos", "dia", "dias", "tarde", "tardes", "noche",
    "noches", "estoy", "buscando", "busco", "quiero", "queria", "necesito",
    "necesitaria", "tenes", "tienen", "tiene", "tendras", "hay", "algun",
    "alguna", "algunos", "algunas", "uno", "una", "unos", "unas", "los",
    "las", "del", "para", "por", "con", "sin", "mas", "muy", "que", "cual",
    "cuales", "como", "donde", "cuanto", "cuanta", "cuestan", "cuesta",
    "sale", "salen", "vale", "valen", "precio", "precios", "economico",
    "economica", "economicos", "economicas", "barato", "barata", "baratos",
    "baratas", "mejor", "mejores", "bueno", "buena", "oferta", "ofertas",
    "gustaria", "interesa", "llevar", "llevo", "comprar", "compra", "ando",
    "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas",
))

# QUERY_PLATA_FUERA: palabras que hablan del TOTAL o del PEDIDO, no de un
# producto. Visto 12-jun: "cuanto era el total de mi pedido?" limpiaba a
# "era total pedido", la busqueda relajada matcheo 14 productos cualquiera y
# el Solver fabrico un total de $142.000 con un producto al azar (numero
# verdadero en cajon equivocado). Tambien los articulos de dos letras: antes
# los tapaba la regla de longitud, que de paso mataba productos reales como
# "tv" o "pc".
_STOP_PLATA = frozenset((
    "era", "eran", "fue", "total", "totales", "pedido", "pedidos", "orden",
    "presupuesto", "presupuestos", "carrito", "monto", "montos", "costo",
    "costos", "pago", "pagos", "pagar", "dame", "decime", "pasame",
    "el", "la", "lo", "le", "me", "te", "se", "mi", "tu", "su", "un",
    "al", "de", "en", "es", "ya", "no", "si",
))


# PEDIDO_PENDIENTE: frases con las que el cliente elige CRITERIO para cerrar
# el pedido a medio armar ("los baratos", "cualquiera", "armame la lista").
# Conservador a proposito: un "dale" o "si" pelado NO alcanza, porque no dice
# nada de la eleccion; ahi el Solver sigue preguntando.
_PIDE_ARMAR = re.compile(
    r"(?i)barat|econom|m[aá]s\s+bajo|cualquier|indistint|que\s+sea"
    r"|arm[aá](?:me|la|lo)?\s+(?:la\s+|el\s+)?(?:lista|pedido|presupuesto)"
    r"|hace(?:me)?\s+la\s+lista")


def _pide_armar(mensaje: str) -> bool:
    """El cliente da el criterio para completar el pedido pendiente."""
    return bool(_PIDE_ARMAR.search(mensaje or ""))


def _limpiar_query(mensaje: str) -> str:
    """Reduce el mensaje crudo a las palabras que describen PRODUCTO: corta la
    cola de envio/localidad, saca muletillas y numeros, singulariza. Si no
    queda nada, devuelve ''."""
    m = re.sub(r"(?i)\b(con\s+)?env[ií]os?\s+(a|para|hasta)\b.*$", " ",
               str(mensaje or ""))
    # Con el flag, las palabras cortas reales ("tv", "pc") sobreviven y los
    # articulos caen por lista, no por longitud.
    min_largo = 1 if settings.QUERY_PLATA_FUERA else 2
    palabras = []
    for w in re.findall(r"[a-záéíóúñü]+", m.lower()):
        if len(w) <= min_largo or w in _STOP_QUERY \
                or (settings.QUERY_PLATA_FUERA and w in _STOP_PLATA):
            continue
        palabras.append(w[:-1] if len(w) > 3 and w.endswith("s") else w)
    return " ".join(palabras[:6])


def _buscar_catalogo(interpretacion: dict, mensaje: str, tienda_id: str,
                     registros: list,
                     trace_id: Optional[str] = None) -> Optional[dict]:
    """Busqueda por codigo (la del flag BUSQUEDA_POR_CODIGO, absorbida): si el
    interpretador detecto intencion de producto, el catalogo relevante entra al
    contrato como evidencia, sin depender de que el modelo llame tools."""
    intencion_prod = (interpretacion or {}).get("intencion") in (
        "exploracion", "pregunta_especifica")
    ref_prod = ((interpretacion or {}).get("producto_resuelto")
                or (interpretacion or {}).get("candidatos"))
    if not (intencion_prod or ref_prod):
        return None
    try:
        from app.core.tools import search_products
        from app.core.tools_context import set_current_tienda
        set_current_tienda(tienda_id)
        q = ((interpretacion or {}).get("producto_resuelto")
             or ((interpretacion or {}).get("candidatos") or [None])[0])
        if not q:
            # Sin producto resuelto: el mensaje crudo se limpia por codigo
            # antes de buscar (frase entera = 0 match = catalogo entero).
            q = _limpiar_query(mensaje)
            if not q:
                if settings.QUERY_PLATA_FUERA:
                    # Nada en el mensaje describe un producto ("cuanto era el
                    # total de mi pedido?"): buscar con el crudo es sembrar
                    # evidencia basura para que el Solver fabrique un total.
                    log.info("provider_busqueda_sin_producto",
                             trace_id=trace_id)
                    return None
                q = mensaje
        res = search_products(query=q)
        if not (res.get("productos") or []):
            # El plural mata el match ("teclados blancos" = 0 resultados;
            # "teclado blanco" = 10). Reintento singularizado por codigo
            # antes de rendirse: una letra no puede costar una venta.
            q_sing = " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w
                              for w in str(q).split())
            if q_sing != q:
                res_sing = search_products(query=q_sing)
                if res_sing.get("productos"):
                    res, q = res_sing, q_sing
                    log.info("provider_busqueda_singular", trace_id=trace_id,
                             query=q_sing[:60])
        prods_all = [p for p in (res.get("productos") or [])
                     if isinstance(p, dict)]
        # "el mas barato / economico": la evidencia se ordena por PRECIO
        # ascendente antes de recortar, no por relevancia (12-jun: pidieron
        # teclados economicos y la busqueda mostro $55.000 y $512.500
        # habiendo uno de $12.000 en catalogo).
        if re.search(r"(?i)barat|econom|menor precio|mas bajo", mensaje or ""):
            def _precio(p):
                v = p.get("precio_ars", p.get("precio"))
                return v if isinstance(v, (int, float)) else float("inf")
            prods_all.sort(key=_precio)
        prods = prods_all[:5]
        claves = ("id", "nombre", "precio", "precio_ars", "stock",
                  "stock_unidades", "categoria", "marca", "modelo")
        prods = [{k: p[k] for k in claves if k in p}
                 for p in prods if isinstance(p, dict)]
        compacto = {"encontrados": res.get("encontrados", len(prods)),
                    "productos": prods}
        if res.get("mensaje_para_llm"):
            compacto["mensaje_para_llm"] = res["mensaje_para_llm"]
        registros.append(_record("search_products", {"query": q}, res))
        log.info("provider_busqueda", trace_id=trace_id, query=str(q)[:60],
                 encontrados=compacto["encontrados"])
        return {"query": q, "compacto": compacto}
    except Exception as e:
        log.warning("provider_busqueda_error", trace_id=trace_id,
                    error=str(e)[:160])
        return None


def proveer(mensaje: str, *, tienda_id: str,
            registro: Optional[list[dict]] = None,
            carrito: Optional[list[dict]] = None,
            localidad_memoria: str = "",
            estado: Optional[str] = None,
            interpretacion: Optional[dict] = None,
            pedido_pendiente: Optional[dict] = None,
            delta_aplicado: bool = False,
            identidad_no_existe: bool = False,
            trace_id: Optional[str] = None) -> dict:
    """Calcula todo lo calculable del turno, sin que nadie lo pida.

    identidad_no_existe: el CERTIFICADOR ya dictamino que el producto que el
        cliente nombro NO existe. El provider NO adivina identidad: saltea todo el
        matcheo especulativo (foco, ab, multi, catalogo, ficha) y solo cotiza el
        carrito real y el envio. Asi la unica autoridad de identidad es el
        certificador, y el provider obedece en vez de inventar una Epson.

    Returns:
        {"foco", "ab", "carrito_calc", "envio", "catalogo", "quiere_cotizar",
         "registros"}; cada seccion es None si no hay con que calcularla.
        registros: tool calls sinteticas para sumar a tools_called (evidencia).
    """
    registro = registro or []
    carrito = carrito or []
    registros: list[dict] = []

    # Localidad efectiva: el turno gana, la memoria sostiene.
    localidad = mensaje if _zona_clara(mensaje) else (localidad_memoria or "")

    # ── PRODUCTO EN FOCO (especulativo: corre aunque no pida precio) ──
    foco = None
    ab = None
    if registro and not identidad_no_existe:
        try:
            foco = cotizar_pedido(mensaje, registro, tienda_id,
                                  localidad=localidad, trace_id=trace_id)
        except Exception as e:
            log.warning("provider_foco_error", trace_id=trace_id,
                        error=str(e)[:160])
        if foco:
            registros.append(_record(
                "calculate_total",
                {"items": [{"product_id": foco["producto_id"],
                            "cantidad": foco["cantidad"]}]},
                foco.get("calc") or {}))
        else:
            try:
                ab = cotizar_pedido_ab(mensaje, registro, tienda_id,
                                       localidad=localidad, trace_id=trace_id)
            except Exception as e:
                log.warning("provider_ab_error", trace_id=trace_id,
                            error=str(e)[:160])
            if ab:
                for cot in ab.get("opciones") or []:
                    registros.append(_record(
                        "calculate_total",
                        {"items": [{"product_id": cot["producto_id"],
                                    "cantidad": cot["cantidad"]}]},
                        cot.get("calc") or {}))

    # ── FOCO SIN ZONA: el cliente pide envio pero no hay zona conocida. ──
    # cotizar_pedido se rinde entero (no da un total a medias), pero el
    # presupuesto del PRODUCTO solo se puede cerrar igual: el contrato lleva
    # "producto $X" + la directiva de pedir el CP. La venta no queda muda.
    if (foco is None and ab is None and registro and not identidad_no_existe
            and _menciona_envio(mensaje) and not _zona_clara(localidad)):
        try:
            from app.core.resolver_pedido import resolver_pedido
            hit = resolver_pedido(mensaje, registro)
            if not hit and len(registro) == 1 and registro[0].get("id"):
                p = registro[0]
                hit = {"producto_id": p["id"], "nombre": p.get("nombre"),
                       "precio_ars": p.get("precio_ars"), "cantidad": 1,
                       "motivo": "unico_en_registro"}
            if hit:
                calc = _cotizar_items(
                    [{"product_id": hit["producto_id"],
                      "cantidad": hit["cantidad"]}],
                    mensaje, tienda_id, "", registros, trace_id=trace_id)
                if calc:
                    foco = {"producto_id": hit["producto_id"],
                            "nombre": hit["nombre"],
                            "cantidad": hit["cantidad"],
                            "con_envio": False, "calc": calc}
        except Exception as e:
            log.warning("provider_foco_sin_zona_error", trace_id=trace_id,
                        error=str(e)[:160])

    # ── FOCO CON ENVIO: total cerrado cuando la zona ya se conoce ──
    # cotizar_pedido solo compone el envio si el mensaje lo nombra. Si el foco
    # salio sin envio pero la localidad es conocida, el codigo cierra TAMBIEN
    # el total con envio: el Solver tiene los dos numeros y no suma a mano.
    foco_envio_calc = None
    if (foco and not foco.get("con_envio") and _zona_clara(localidad)):
        foco_envio_calc = _cotizar_items(
            [{"product_id": foco["producto_id"], "cantidad": foco["cantidad"]}],
            mensaje, tienda_id, localidad, registros, trace_id=trace_id)
        # Si dio lo mismo que el foco pelado (ej. envio gratis por umbral ya
        # incluido), no aporta: afuera.
        if (foco_envio_calc and foco_envio_calc.get("total_ars")
                == (foco.get("calc") or {}).get("total_ars")
                and not foco_envio_calc.get("extras")):
            foco_envio_calc = None

    # ── PEDIDO COMBINADO NUEVO (flag PEDIDO_MULTI): "2 mouses y 2 tablets" ──
    # El Provider lee el pedido del mensaje por codigo y lo cierra entero; sin
    # esto el contrato viaja sin total y el Solver cae a su respaldo (llamar
    # la calculadora el mismo y redactar), el costado debil del sistema.
    multi = None
    # Si el carrito_delta YA mutó el carrito este turno, el mensaje era una
    # MODIFICACION del pedido ('mejor que sean 2 teclados'), no un pedido nuevo:
    # no se vuelve a extraer por multi, que lo leeria como '2 teclados' ambiguo
    # y pisaria el delta ya aplicado con una pregunta A/B falsa.
    if (settings.PEDIDO_MULTI and not foco and not ab and not delta_aplicado
            and not identidad_no_existe):
        try:
            from app.core.pedido_multi import extraer_pedido
            ped = extraer_pedido(mensaje, tienda_id,
                                 interpretacion=interpretacion,
                                 trace_id=trace_id)
            if ped and ped["items"]:
                calc_multi = _cotizar_items(
                    [{"product_id": i["product_id"], "cantidad": i["cantidad"]}
                     for i in ped["items"]],
                    mensaje, tienda_id, localidad, registros,
                    trace_id=trace_id)
                if calc_multi:
                    multi = {"items": ped["items"], "calc": calc_multi,
                             "ambiguos": ped["ambiguos"]}
            elif ped and ped["ambiguos"]:
                multi = {"items": [], "calc": None,
                         "ambiguos": ped["ambiguos"]}
        except Exception as e:
            log.warning("provider_pedido_multi_error", trace_id=trace_id,
                        error=str(e)[:160])

    # ── PEDIDO PENDIENTE (flag): el pedido a medio armar de turnos anteriores ──
    # Caso real (charla Martin 12-jun noche): "2 mauses y dos teclados" quedo
    # ambiguo, el bot pregunto cuales, el cliente contesto "los baratos, armame
    # la lista" y NADIE junto las dos mitades: sin carrito ni total, cierre
    # pidiendo datos sin precio y fallback. Aca el pedido a medio armar se
    # recuerda, y la eleccion del turno siguiente lo completa POR CODIGO (el
    # mas barato con stock por termino), nunca por el LLM.
    pendiente_nuevo = None
    pendiente_consumido = False
    if settings.PEDIDO_PENDIENTE:
        try:
            if multi and multi.get("ambiguos"):
                pendiente_nuevo = {
                    "items": [{"product_id": i["product_id"],
                               "nombre": i.get("nombre"),
                               "cantidad": i["cantidad"]}
                              for i in (multi.get("items") or [])],
                    "ambiguos": [{"termino": a["termino"],
                                  "cantidad": a["cantidad"]}
                                 for a in (multi.get("ambiguos") or [])],
                }
                log.info("pedido_pendiente_guardado", trace_id=trace_id,
                         ambiguos=[a["termino"]
                                   for a in pendiente_nuevo["ambiguos"]])
            elif pedido_pendiente and not multi and _pide_armar(mensaje):
                from app.core.pedido_multi import completar_pedido
                ped2 = completar_pedido(pedido_pendiente, tienda_id,
                                        trace_id=trace_id)
                if ped2 and ped2["items"]:
                    calc2 = _cotizar_items(
                        [{"product_id": i["product_id"],
                          "cantidad": i["cantidad"]} for i in ped2["items"]],
                        mensaje, tienda_id, localidad, registros,
                        trace_id=trace_id)
                    if calc2:
                        multi = {"items": ped2["items"], "calc": calc2,
                                 "ambiguos": [], "desde_pendiente": True}
                        pendiente_consumido = True
                        log.info("pedido_pendiente_completado",
                                 trace_id=trace_id,
                                 items=[(i["product_id"], i["cantidad"])
                                        for i in ped2["items"]])
            if (pedido_pendiente and not pendiente_consumido
                    and multi and multi.get("calc")):
                # Un pedido nuevo cerrado entero reemplaza al pendiente viejo:
                # el cliente cambio de idea, lo de antes no puede resucitar.
                pendiente_consumido = True
        except Exception as e:
            log.warning("pedido_pendiente_error", trace_id=trace_id,
                        error=str(e)[:160])

    # ── PEDIDO VIGENTE (el carrito recalculado con sus ids reales) ──
    carrito_calc = None
    items_carrito = [{"product_id": it["id"], "cantidad": it.get("cantidad", 1)}
                     for it in carrito if it.get("id")]
    # Si el foco ES el unico item del carrito, el calculo seria el mismo: no se
    # duplica. En cualquier otro caso el pedido vigente se recalcula entero.
    _foco_es_carrito = (foco and len(items_carrito) == 1
                        and items_carrito[0]["product_id"] == foco["producto_id"]
                        and items_carrito[0]["cantidad"] == foco["cantidad"])
    # Con DIRECTOR_LLM el carrito es la fuente UNICA (el orchestrator anula el
    # foco): se cotiza SIEMPRE, aunque coincida con el foco. Sin esto, un carrito
    # de 1 item == foco quedaba sin carrito_calc y el total perdia respaldo.
    if items_carrito and (not _foco_es_carrito or get_settings().DIRECTOR_LLM):
        carrito_calc = _cotizar_items(items_carrito, mensaje, tienda_id,
                                      localidad, registros, trace_id=trace_id)

    # ── ENVIO (tabla CP/provincia -> tarifa; sin zona, pedir el CP) ──
    envio = None
    try:
        from app.core.tools import cotizar_envio
        from app.core.tools_context import set_current_tienda
        if _zona_clara(localidad):
            set_current_tienda(tienda_id)
            _sub = 0
            for c in (carrito_calc, (foco or {}).get("calc")):
                if isinstance(c, dict) and c.get("subtotal_productos_ars"):
                    _sub = c["subtotal_productos_ars"]
                    break
            env = cotizar_envio(localidad=localidad, subtotal=_sub)
            if env.get("ok"):
                envio = {"estado": "cotizado", "detalle": env}
                registros.append(_record(
                    "cotizar_envio",
                    {"localidad": localidad[:80], "subtotal": _sub}, env))
        elif _menciona_envio(mensaje):
            envio = {"estado": "pedir_cp"}
    except Exception as e:
        log.warning("provider_envio_error", trace_id=trace_id,
                    error=str(e)[:160])

    # ── FICHA del producto en foco: atributos reales de la fuente ──
    ficha = None
    if foco:
        ficha = _ficha_producto(foco["producto_id"], tienda_id,
                                trace_id=trace_id)

    # ── STOCK: el stock REAL de cada item del pedido, leido de la fuente ──
    # Doble proposito (caso teclados 12-jun): (a) si falta stock, el contrato
    # ordena NO vender (la calculadora rechaza el calculo pero sin directiva el
    # Solver improvisa); (b) si alcanza, el contrato lleva las unidades reales
    # para que el modelo no INVENTE un stock ("tenemos 0 unidades" con 11 en
    # Firestore — nadie lo frenaba porque no es un numero de plata).
    stock_falta: list[dict] = []
    stock_info: list[dict] = []
    if settings.STOCK_GATE:
        try:
            from app.core.tools import get_product_by_id
            pedidos = []
            if foco:
                pedidos.append((foco["producto_id"], foco.get("cantidad", 1)))
            for d in ((carrito_calc or {}).get("detalle") or []):
                if d.get("id"):
                    pedidos.append((d["id"], d.get("cantidad", 1)))
            for i in ((multi or {}).get("items") or []):
                pedidos.append((i["product_id"], i.get("cantidad", 1)))
            # El carrito CRUDO tambien: si la calculadora rechazo el calculo
            # (p. ej. por stock), el detalle no existe pero el pedido si.
            for it in carrito:
                if it.get("id"):
                    pedidos.append((it["id"], it.get("cantidad", 1)))
            vistos = set()
            for pid, cant in pedidos:
                pid = str(pid).upper()
                if pid in vistos:
                    continue
                vistos.add(pid)
                p = get_product_by_id(pid, tienda_id=tienda_id)
                st = (p or {}).get("stock")
                if not isinstance(st, (int, float)):
                    continue
                fila = {"producto_id": pid, "nombre": (p or {}).get("nombre"),
                        "stock": int(st), "pedido": cant}
                stock_info.append(fila)
                if st < cant:
                    stock_falta.append(fila)
            if stock_falta:
                log.info("provider_stock_insuficiente", trace_id=trace_id,
                         faltantes=[(f["producto_id"], f["stock"], f["pedido"])
                                    for f in stock_falta])
        except Exception as e:
            log.warning("provider_stock_error", trace_id=trace_id,
                        error=str(e)[:120])

    # ── CATALOGO (busqueda por codigo absorbida) ──
    catalogo = None
    if not foco and not ab and not identidad_no_existe:
        catalogo = _buscar_catalogo(interpretacion, mensaje, tienda_id,
                                    registros, trace_id=trace_id)

    cotiza = quiere_cotizar(mensaje, estado)

    # "Armame la lista" ES pedir el presupuesto: el pedido completado desde el
    # pendiente va activo (actualiza carrito y ultimo presupuesto), no
    # especulativo.
    if multi and multi.get("desde_pendiente"):
        cotiza = True

    # CIERRE_CONTRATO: dar la direccion o la zona ES señal de compra. Sin esto,
    # el cliente que contesta el pedido de CP con su direccion pelada deja el
    # calculo del turno como especulativo, la memoria conserva un pedido viejo
    # y el cierre (resumen + link de pago) sale con ese pedido equivocado.
    if (not cotiza and settings.CIERRE_CONTRATO
            and (foco or carrito_calc) and _zona_clara(mensaje)):
        cotiza = True
        log.info("provider_cotiza_por_direccion", trace_id=trace_id)

    # Marca de especulativo: un calculo que el cliente NO pidio respalda numeros
    # (evidencia) pero NO debe pisar el carrito vigente ni el ultimo presupuesto
    # (si no, preguntar la garantia del Samsung convertiria al Samsung en el
    # pedido). Solo la cotizacion ACTIVA (cliente cotizando + foco o carrito
    # resuelto) actualiza la memoria de compra. El A/B queda especulativo
    # siempre: el cliente todavia no eligio.
    _activos = set()
    if cotiza:
        if foco:
            _activos.add(id((foco.get("calc") or {})))
            if foco_envio_calc:
                _activos.add(id(foco_envio_calc))
        if carrito_calc:
            _activos.add(id(carrito_calc))
        if multi and multi.get("calc"):
            _activos.add(id(multi["calc"]))
    for r in registros:
        if r.get("name") == "calculate_total":
            r["speculativo"] = id(r.get("result")) not in _activos
        else:
            r["speculativo"] = True

    log.info("provider_turno", trace_id=trace_id,
             foco=bool(foco), ab=bool(ab), carrito=bool(carrito_calc),
             envio=(envio or {}).get("estado"), catalogo=bool(catalogo),
             quiere_cotizar=cotiza, registros=len(registros))
    return {"foco": foco, "ab": ab, "foco_envio_calc": foco_envio_calc,
            "carrito_calc": carrito_calc, "ficha": ficha, "multi": multi,
            "stock_falta": stock_falta or None,
            "stock_info": stock_info or None,
            "envio": envio, "catalogo": catalogo, "quiere_cotizar": cotiza,
            "pendiente_nuevo": pendiente_nuevo,
            "pendiente_consumido": pendiente_consumido,
            "registros": registros}


def _linea_envio(envio: Optional[dict]) -> str:
    if not envio:
        return ""
    if envio["estado"] == "pedir_cp":
        return ("ENVIO: el cliente quiere envio pero NO hay localidad conocida. "
                "Pedile la localidad o el codigo postal antes de dar un costo "
                "de envio. NO des un numero de envio en este turno.")
    env = envio.get("detalle") or {}
    if env.get("modalidad") == "rango":
        costo = (f"entre ${env.get('monto_min', 0):,.0f} y "
                 f"${env.get('monto_max', 0):,.0f}").replace(",", ".")
    elif env.get("concepto") == "envio_gratis" or env.get("monto") == 0:
        costo = "GRATIS"
    else:
        costo = f"${env.get('monto', 0):,.0f}".replace(",", ".")
    linea = (f"ENVIO a la zona del cliente ({env.get('zona', 'conocida')}): "
             f"{costo}.")
    # La receta exacta de la calculadora: si no hay un presupuesto cerrado
    # arriba que ya incluya el envio, el total con envio se pide a
    # calculate_total con el concepto de la zona. NUNCA suma manual (clase
    # dominante del atacante: producto+envio sumado a mano, cifra sin fuente).
    if env.get("concepto"):
        linea += (" Si el cliente quiere un TOTAL con envio y los presupuestos "
                  "de arriba no lo incluyen, llama calculate_total con TODOS "
                  "los ids del pedido e items_extra {faq_tema: costo_envio, "
                  f"concepto: {env['concepto']}}}. NUNCA sumes producto mas "
                  "envio a mano: el total sale de calculate_total o del "
                  "contrato.")
    return linea


def contrato(prov: dict, *, estado: Optional[str] = None,
             ofrecer_opciones=None,
             registro: Optional[list[dict]] = None,
             producto_interpretador: Optional[str] = None) -> str:
    """El UNICO bloque por turno que recibe el Solver: estado, datos cerrados y
    reglas de uso. Consolida lo que antes eran 4-5 inyecciones que competian."""
    secciones: list[str] = []

    foco, ab = prov.get("foco"), prov.get("ab")
    carrito_calc = prov.get("carrito_calc")

    if carrito_calc and carrito_calc.get("presentacion"):
        items_txt = "; ".join(
            f"{d.get('cantidad', 1)}x {d.get('nombre')} (id {d.get('id')})"
            for d in (carrito_calc.get("detalle") or []) if d.get("id"))
        secciones.append(
            "PEDIDO VIGENTE (ya presupuestado, ids reales): " + items_txt +
            "\nPresupuesto verificado del pedido:\n"
            + carrito_calc["presentacion"] +
            "\nSi el cliente confirma, saca o cambia cantidades, parti de ESTOS "
            "ids; no los reemplaces por otros productos.")

    if foco and (foco.get("calc") or {}).get("presentacion"):
        _sec_foco = (
            f"PRODUCTO EN FOCO: {foco.get('nombre')} (id {foco.get('producto_id')}, "
            f"cantidad {foco.get('cantidad')}). Presupuesto YA calculado y "
            "verificado:\n" + foco["calc"]["presentacion"])
        _fec = prov.get("foco_envio_calc")
        if _fec and _fec.get("presentacion"):
            _sec_foco += (
                "\nTotal CON envio a la zona del cliente (tambien ya "
                "calculado; si el cliente quiere el total con envio, usa ESTE "
                "tal cual):\n" + _fec["presentacion"])
        ficha = prov.get("ficha")
        if ficha:
            _sec_foco += (
                "\nFICHA REAL del producto (TODO lo que la tienda sabe de el; "
                "responde garantia, origen, materiales y demas atributos DESDE "
                "aca; un atributo que NO figure aca no lo afirmes ni lo "
                "inventes: deci que lo confirmas con el equipo):\n" + ficha)
        secciones.append(_sec_foco)
    elif ab:
        partes = []
        for letra, cot in zip(("A", "B"), ab.get("opciones") or []):
            pres = (cot.get("calc") or {}).get("presentacion", "")
            partes.append(f"OPCION {letra} — {cot.get('nombre')}:\n{pres}")
        secciones.append(
            "El cliente puede referirse a DOS productos. Los dos presupuestos "
            "ya estan calculados. Presentalos como opcion A y opcion B y "
            "termina preguntando cual prefiere; nunca elijas vos:\n"
            + "\n\n".join(partes))
    elif producto_interpretador:
        secciones.append(
            f"El cliente se refiere a: {producto_interpretador}.")

    multi = prov.get("multi")
    if multi:
        if multi.get("calc") and multi["calc"].get("presentacion"):
            items_txt = "; ".join(
                f"{i['cantidad']}x {i['nombre']} (id {i['product_id']})"
                for i in multi["items"])
            _origen = (
                "PEDIDO PENDIENTE completado por el sistema con el criterio "
                "que pidio el cliente (el mas barato con stock de cada uno): "
                if multi.get("desde_pendiente") else
                "PEDIDO COMBINADO leido del mensaje y YA calculado por el "
                "sistema: ")
            _cola = (
                "\nAclarale que elegiste los mas economicos y que puede "
                "cambiar de modelo si prefiere otro."
                if multi.get("desde_pendiente") else "")
            secciones.append(
                _origen + items_txt +
                "\nPresupuesto verificado (usalo TAL CUAL):\n"
                + multi["calc"]["presentacion"] +
                "\nSi el cliente confirma o cambia cantidades, parti de "
                "ESTOS ids." + _cola)
        for amb in multi.get("ambiguos") or []:
            ops = "; ".join(
                f"{c['nombre']} a ${c['precio_ars']:,.0f}".replace(",", ".")
                for c in amb["candidatos"])
            secciones.append(
                f"Para '{amb['termino']}' (cantidad {amb['cantidad']}) hay "
                f"VARIAS opciones reales: {ops}. Pregunta cual prefiere; "
                "no elijas vos ni des un total de ese item todavia.")

    stock_falta = prov.get("stock_falta")
    stock_info = prov.get("stock_info")
    if stock_falta:
        _lineas_st = [
            (f"- {f.get('nombre')} (id {f['producto_id']}): stock "
             f"{f['stock']}, el cliente pide {f['pedido']}")
            for f in stock_falta]
        secciones.insert(0, (
            "STOCK INSUFICIENTE — estos productos NO se pueden vender en la "
            "cantidad pedida:\n" + "\n".join(_lineas_st) +
            "\nDecile claro y sin vueltas que no hay stock suficiente de eso. "
            "NO confirmes la venta, NO ofrezcas link ni datos de pago por "
            "estos items, NO digas frases como 'no hay problema'. Ofrece "
            "buscar una alternativa del catalogo o avisarle cuando vuelva a "
            "haber stock."))
    elif stock_info:
        _lineas_si = [f"- {f.get('nombre')}: {f['stock']} unidades"
                      for f in stock_info]
        secciones.append(
            "STOCK REAL de los items del pedido (fuente de la tienda; si "
            "afirmas disponibilidad o unidades, usa ESTOS numeros, jamas "
            "otros):\n" + "\n".join(_lineas_si))

    linea_env = _linea_envio(prov.get("envio"))
    if linea_env:
        secciones.append(linea_env)

    catalogo = prov.get("catalogo")
    if catalogo:
        secciones.append(
            "CATALOGO (el sistema YA busco por este mensaje; resultado REAL de "
            f"search_products(query='{catalogo['query']}')): "
            + json.dumps(catalogo["compacto"], ensure_ascii=False) +
            "\nPrecios, stock e ids de aca son la fuente. Si necesitas detalle "
            "o un total, llama las tools con estos ids.")

    if registro and not foco and not ab:
        lineas = []
        for p in registro:
            if not p.get("id") or not p.get("nombre"):
                continue
            precio = p.get("precio_ars")
            if isinstance(precio, (int, float)):
                lineas.append(f"- {p['nombre']} (id {p['id']}): "
                              f"${precio:,.0f}".replace(",", "."))
            else:
                lineas.append(f"- {p['nombre']} (id {p['id']})")
        if lineas:
            secciones.append(
                "PRODUCTOS YA MOSTRADOS (id real; si el cliente se refiere a "
                "uno, usa ese id, no lo busques de nuevo):\n" + "\n".join(lineas))

    if ofrecer_opciones:
        secciones.append(
            "El interpretador detecto dos caminos: presentalos como opcion A y "
            f"opcion B y pregunta cual prefiere: {ofrecer_opciones}")

    if not secciones and not estado:
        return ""

    cuerpo = "\n\n".join(secciones)
    encabezado = (
        "\n\n[CONTRATO DEL TURNO — datos cerrados, calculados y verificados "
        "por el sistema. Reglas: toda cifra que des sale de aca o de una tool, "
        "copiada TAL CUAL; NUNCA sumes, restes ni calcules vos; si falta un "
        "dato, pedilo en vez de inventarlo."
        + (f"\nEstado de la conversacion: {estado}." if estado else ""))
    return encabezado + ("\n\n" + cuerpo if cuerpo else "") + "]"


def verdad_del_turno(prov: dict) -> Optional[str]:
    """La verdad a la que cae la compuerta si el Solver rompe las cifras. Solo
    cuando el cliente esta cotizando o cerrando (mismo gate que el cotizador
    por codigo): pisar una respuesta de FAQ con un presupuesto seria peor."""
    foco = prov.get("foco")
    carrito_calc = prov.get("carrito_calc")
    # El carrito ACUMULADO (2+ items) ES el pedido del cliente: gana sobre el
    # foco (un solo producto en foco) Y vale aunque el mensaje no traiga palabra
    # de precio — el cliente lo esta ARMANDO ('sumale un teclado'), su total
    # verificado tiene que existir para que el render lo estampe en vez de
    # confiar en la prosa del Solver. Por eso va ANTES de la compuerta
    # quiere_cotizar. EN SINCRONIA con estado_pedido._pedido_activo (que tampoco
    # gatea por quiere_cotizar para el carrito).
    # Con DIRECTOR_LLM el carrito ES el pedido (lo gobierna el director), aunque
    # tenga 1 solo item y el mensaje no traiga palabra de cotizar: su total tiene
    # que estar respaldado por codigo. En modo normal se mantiene el umbral de 2
    # para no pisar una FAQ con el presupuesto de un foco suelto.
    _min_carrito = 1 if get_settings().DIRECTOR_LLM else 2
    if (carrito_calc and carrito_calc.get("presentacion")
            and len(carrito_calc.get("detalle") or []) >= _min_carrito):
        return carrito_calc["presentacion"]
    if not prov.get("quiere_cotizar"):
        return None
    if foco and (foco.get("calc") or {}).get("presentacion"):
        # Con la zona conocida, la verdad completa es el total CON envio (la
        # presentacion desglosa producto, envio y total: es honesta entera).
        _fec = prov.get("foco_envio_calc")
        if _fec and _fec.get("presentacion"):
            return _fec["presentacion"]
        return foco["calc"]["presentacion"]
    if prov.get("ab"):
        return presentacion_ab(prov["ab"])
    multi = prov.get("multi")
    if multi and (multi.get("calc") or {}).get("presentacion"):
        return multi["calc"]["presentacion"]
    if carrito_calc and carrito_calc.get("presentacion"):
        return carrito_calc["presentacion"]
    return None
