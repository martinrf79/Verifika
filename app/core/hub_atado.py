"""
HUB ATADO — el turno completo con los DOS atados y SIN la pila de guardas.

Camino:
  1. INTERPRETE (Gemini, schema estricto): entiende y devuelve datos.
  2. SOLVER (solver_gemini): LLAMA las tools de area; el dato duro sale de la
     tool, no de la cabeza del modelo.
  3. ESTAMPADO por codigo del numero sellado y el producto real.
  4. MEMORIA: se persiste el estado esencial para que la charla recuerde entre
     turnos (history, resumen largo, productos vistos, carrito, destinos,
     criterio, provincia).

NO corre ninguna de las ~40 guardas/parches de interprete_libre. Reusa solo las
funciones PURAS de estado y estampado. Es candidato a reemplazar interprete_libre
en el camino vivo una vez medido en la bateria; hoy convive solo para medirse,
el orchestrator sigue en interprete_libre hasta que el numero lo justifique.
"""
import re
import time

from app.core.interpretador import interpretar_mensaje
from app.core import solver_gemini
from app.core.estado_venta import (
    construir_estado, set_current_estado,
    productos_de_meta, carrito_de_meta, envio_de_meta, merge_productos,
    detectar_criterio, criterio_del_interprete, get_envio_localidades)
from app.core.tools_context import set_current_tienda
from app.core.interprete_libre import (
    _presupuesto_de_meta, _sustituir_o_acoplar_presupuesto, _estampar_productos)
from app.config import get_settings
from app.logger import get_logger
from app.storage.firestore_client import (
    get_conversation, save_conversation, get_config, get_product_by_id)

log = get_logger(__name__)
settings = get_settings()

_RE_PROD = re.compile(r"\[\[PROD:([A-Za-z0-9_\-]+)\]\]")
_RE_PRESUP_SOBRANTE = re.compile(r"\s*\[\[PRESUPUESTO\]\]\s*")
# El solver a veces FILTRA el id interno del catalogo en el texto al cliente
# ("Genius KB-110X (id: TEC0019)"). El cliente no debe verlo. Limpieza del
# estampado, no una guarda; lo ideal es que el prompt del solver no lo emita.
_RE_ID_FILTRADO = re.compile(
    r"[\s,]*\(\s*(?:(?:id|sku|codigo)\s*[:=]?\s*)?"
    r"[A-Z]{2,5}\d{2,}(?:\s*/\s*[A-Z]{2,5}\d{2,})*\s*\)"
    r"|[\s,]*\b(?:id|sku|codigo)\s*[:=]\s*[A-Z]{2,5}\d{2,}",
    re.IGNORECASE)
_RE_TOTAL = re.compile(r"[Tt]otal:\s*\$?\s*([\d.]+)")


def _tools_traza(meta) -> list[str]:
    """Resumen COMPACTO de las tools que llamo el solver, con el arg clave: es
    la costura donde se ve un envio sin cotizar o un producto equivocado que se
    le mando a la calculadora."""
    out: list[str] = []
    for tc in (meta or {}).get("tools_called", []) or []:
        n = tc.get("name")
        a = tc.get("args") or {}
        r = tc.get("result")
        if n == "cotizar_envio":
            costo = r.get("costo") if isinstance(r, dict) else None
            out.append(f"cotizar_envio(loc={a.get('localidad')},costo={costo})")
        elif n == "calculate_total":
            items = a.get("items") or []
            its = ",".join(f"{i.get('product_id')}x{i.get('cantidad')}"
                           for i in items if isinstance(i, dict))
            out.append(f"calculate_total([{its}])")
        else:
            out.append(str(n))
    return out


def _carrito_traza(carrito) -> list:
    return [(c.get("nombre"), c.get("cantidad"))
            for c in (carrito or []) if isinstance(c, dict)]


def _norm_nombre(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def _guia_pedido_anclado(interp, productos_vistos) -> str:
    """Ata cada renglon del pedido al id REAL del producto que el cliente YA
    vio, para que el solver use EXACTAMENTE ese en calculate_total y no re-elija
    otro modelo al armar el total (fue el nudo del multidestino: el interprete
    leia DX-110 pero el solver cargaba el M170). Config, no calculo: mapea el
    nombre que el interprete resolvio (enum-atado a lo visto) a su id de
    productos_vistos. '' si no hay pedido o no se puede anclar."""
    pedido = (interp or {}).get("pedido") or []
    if not pedido:
        return ""
    idx = {}
    for p in (productos_vistos or []):
        if isinstance(p, dict) and p.get("nombre") and p.get("id"):
            idx[_norm_nombre(p["nombre"])] = str(p["id"])
    lineas = []
    for it in pedido:
        if not isinstance(it, dict):
            continue
        pid = idx.get(_norm_nombre(it.get("producto")))
        if not pid:
            return ""  # un renglon sin anclar: no se fuerza a medias, red del solver
        cant = it.get("cantidad") or 1
        dest = str(it.get("destino") or "").strip()
        lineas.append(f"{cant}x [[PROD:{pid}]]" + (f" a {dest}" if dest else ""))
    return ("\n\n[GUIA DETERMINISTA del pedido, calculada desde lo que el cliente "
            "YA eligio: usa EXACTAMENTE estos productos e ids en calculate_total "
            "y para mostrarlos, NO cambies el modelo ni elijas otro: "
            + "; ".join(lineas) + ". Usa el marcador [[PROD:id]] tal cual.]")


def _guia_consultado(interp, productos_vistos) -> str:
    """ANCLA del producto CONSULTADO: cierra el hueco de "el interprete resuelve X
    y el solver contesta sobre Y". El interprete ya certifico contra que producto
    VISTO pregunta el cliente (producto_resuelto / productos_consultados, atados al
    enum de lo mostrado); aca se le pasa al solver el id REAL de esos, para que
    conteste la ficha de EXACTAMENTE ese y NO re-busque otro modelo. El dato de la
    ficha sigue saliendo de la tool; esto solo fija CUAL. '' si no hay consulta
    puntual o no se puede anclar (ahi el solver busca como siempre)."""
    nombres = []
    pr = (interp or {}).get("producto_resuelto")
    if isinstance(pr, str) and pr.strip():
        nombres.append(pr)
    for c in ((interp or {}).get("productos_consultados") or []):
        if isinstance(c, dict) and isinstance(c.get("producto"), str) and c["producto"].strip():
            nombres.append(c["producto"])
    if not nombres:
        return ""
    idx = {}
    for p in (productos_vistos or []):
        if isinstance(p, dict) and p.get("nombre") and p.get("id"):
            idx[_norm_nombre(p["nombre"])] = (str(p["id"]), p["nombre"])
    lineas, vistos = [], set()
    for nom in nombres:
        par = idx.get(_norm_nombre(nom))
        if not par or par[0] in vistos:
            continue
        vistos.add(par[0])
        lineas.append(f"{par[1]}: [[PROD:{par[0]}]]")
    if not lineas:
        return ""
    return ("\n\n[GUIA DETERMINISTA: el cliente pregunta por ESTOS productos que YA "
            "vio; contesta la ficha de EXACTAMENTE estos ids con get_product_details, "
            "NO busques ni elijas otro modelo: " + "; ".join(lineas)
            + ". Usa el marcador [[PROD:id]] tal cual al nombrarlos.]")


def _guia_solicitud_nueva(interp, tienda_id) -> str:
    """El cliente pidio una CATEGORIA aun no mostrada (campo solicitud_nueva,
    atado al enum de categorias reales): el codigo trae la opcion de esa
    categoria desde el catalogo y la inyecta para que el solver la MUESTRE, asi
    entra a vistos y del turno siguiente se puede pedir/anclar. Cierra el lado B
    de la atadura: la categoria pedida ya no se pierde. '' si no hay solicitud."""
    sols = (interp or {}).get("solicitud_nueva") or []
    if not sols:
        return ""
    from app.core.guia_compra import mas_barato_con_stock, intermedio_con_stock
    lineas = []
    for s in sols:
        if not isinstance(s, dict) or not s.get("categoria"):
            continue
        cat = str(s["categoria"])
        crit = s.get("criterio")
        try:
            p = (intermedio_con_stock(categoria=cat) if crit == "intermedio"
                 else mas_barato_con_stock(categoria=cat))
        except Exception:
            p = None
        if p and p.get("id"):
            cant = s.get("cantidad")
            q = f"{cant}x " if cant else ""
            etiqueta = "intermedio" if crit == "intermedio" else "mas barato"
            lineas.append(f"{q}{cat} ({etiqueta}): [[PROD:{p['id']}]]")
    if not lineas:
        return ""
    return ("\n\n[GUIA DETERMINISTA, categorias que el cliente pidio y que hay "
            "que MOSTRAR ahora, calculadas desde el catalogo real: "
            + "; ".join(lineas) + ". Ofrece EXACTAMENTE esos con el marcador "
            "[[PROD:id]] tal cual, para que queden a la vista.]")


def _guia_categorias(interp) -> str:
    """EL CONTACTOR abarcativo: por cada categoria que el interprete DECLARO
    (atada al enum de la fuente de verdad), engancha su CRITERIO de prosa desde
    base_conocimiento y lo adjunta para que el solver razone desde la fuente
    correcta, no de memoria. Cubre la pregunta compleja multi-tema: si el mensaje
    toca precio + objecion + envio, viajan los tres criterios. Solo ADJUNTA el
    dato de la fuente, nunca reescribe la prosa (condicion 2 del Contactor). '' si
    no hay categoria o ninguna trae criterio (esas se apoyan en su tool)."""
    from app.core.guia_venta_prosa import consultar_guia_venta
    cats = (interp or {}).get("categorias") or []
    if not isinstance(cats, list) or not cats:
        return ""
    lineas = []
    vistas = set()
    for cat in cats[:5]:  # tope contra sobre-declaracion; multi-tema real no pasa
        c = str(cat).strip()
        if not c or c in vistas:
            continue
        vistas.add(c)
        r = consultar_guia_venta(tema=c)
        txt = str((r or {}).get("texto") or "").strip()
        if txt:
            lineas.append(f"- {c}: {txt}")
    if not lineas:
        return ""
    return ("\n\n[CRITERIO DE LA FUENTE que aplica a este turno, razona la prosa "
            "DESDE aca y no de memoria; el dato duro sigue saliendo de las tools:\n"
            + "\n".join(lineas) + "]")


async def _aplicar_cierre(conv, user_id, canal, tienda_id, raw_message, texto,
                          trace_id, interp, present):
    """Cablea el CIERRE y COBRO al hub reusando la MISMA funcion del camino vivo
    (leads.procesar_mensaje_para_lead), no la duplica: entrega los datos de pago
    cuando el cliente los pide, capta el lead en la decision de compra y hace la
    pregunta suave de cierre. Arma los mismos insumos que interprete_libre. Devuelve
    (texto posiblemente pisado por el cierre, datos acumulados, flag de pregunta de
    cierre, presupuesto string) para persistir."""
    from app.core.leads import procesar_mensaje_para_lead
    presupuesto = present or (conv.get("ultimo_presupuesto") or "")
    presupuesto_nuevo = bool(present)
    _intent = interp.get("intencion") if isinstance(interp, dict) else None
    datos_previos = conv.get("datos_cliente_parciales") or {}
    datos_turno: dict = {}
    try:
        from app.core.cierre import extraer_determinista, extraer_datos_cliente
        from app.core.interprete_libre import _parece_aportar_dato
        datos_turno.update(extraer_determinista(raw_message))
        if (_intent in ("aporta_dato", "decision_compra")
                or _parece_aportar_dato(raw_message)):
            for k, v in extraer_datos_cliente(raw_message, trace_id).items():
                if v:
                    datos_turno[k] = v
    except Exception as e:
        log.warning("hub_atado_extractor_error", trace_id=trace_id,
                    error=str(e)[:120])
    datos_acumulados = {**datos_previos, **datos_turno}
    pregunta_cierre_previa = bool(conv.get("pregunta_cierre_hecha"))
    meta_lead: dict = {}
    # No se cierra sobre el fallback: no hay respuesta real que confirmar.
    if texto and texto != settings.VERIFIKA_FALLBACK_MESSAGE:
        try:
            _, meta_lead = await procesar_mensaje_para_lead(
                user_id, canal, tienda_id, raw_message, texto, trace_id,
                interpretacion=interp if isinstance(interp, dict) else None,
                presupuesto=presupuesto, datos_turno=datos_turno,
                datos_previos=datos_acumulados,
                presupuesto_nuevo=presupuesto_nuevo,
                pregunta_cierre_hecha=pregunta_cierre_previa)
            if meta_lead.get("respuesta_directa"):
                texto = meta_lead["respuesta_directa"]
                log.info("hub_atado_cierre", trace_id=trace_id,
                         accion=meta_lead.get("accion"))
        except Exception as e:
            log.warning("hub_atado_lead_error", trace_id=trace_id,
                        error=str(e)[:160])
    pregunta_cierre_hecha = (meta_lead.get("accion")
                             in ("pregunta_cierre", "pregunta_pendiente_cierre"))
    return texto, datos_acumulados, pregunta_cierre_hecha, presupuesto


async def procesar_atado(user_id: str, raw_message: str, tienda_id: str,
                         canal: str, trace_id: str) -> str:
    """Un turno del bot por el flujo atado. Devuelve el texto para el cliente."""
    t0 = time.time()
    conv = get_conversation(user_id, tienda_id=tienda_id)
    history = conv.get("history", []) or []
    estado_anterior = conv.get("estado_conversacion", "saludo") or "saludo"

    estado = construir_estado(conv, None)
    from app.core.envio import clasificar_provincia
    _prov_msg = clasificar_provincia(raw_message) or ""
    if _prov_msg:
        estado["provincia_envio"] = _prov_msg
    set_current_tienda(tienda_id)
    set_current_estado(estado)

    # ── INTERPRETE ──────────────────────────────────────────────────────
    resumen = estado.get("resumen_charla") or ""
    interp = await interpretar_mensaje(
        raw_message, history, trace_id, estado_anterior=estado_anterior,
        tienda_id=tienda_id, productos_vistos=estado.get("productos_vistos"),
        resumen=resumen)
    estado_nuevo = (interp.get("estado_conversacion") or estado_anterior
                    if isinstance(interp, dict) else estado_anterior)
    log.info("hub_atado_interp", trace_id=trace_id,
             intencion=interp.get("intencion"),
             producto=interp.get("producto_resuelto"),
             consultados=interp.get("productos_consultados"))

    # ── GUIA DETERMINISTA que viaja al solver (config, no calculo) ──────
    # Prioridad 1: si el interprete leyo un PEDIDO concreto, se atan sus
    # renglones al id real de lo que el cliente vio, asi el solver no re-elige
    # otro modelo al armar el total (nudo del multidestino). Prioridad 2: si no
    # hay pedido pero el criterio es "mas barato", viaja el minimo con stock por
    # categoria. Elegir el producto es un problema cerrado; lo ata el codigo y
    # el solver ofrece EXACTAMENTE ese, sin adivinar.
    try:
        _bloques, _tipos = [], []
        _ga = _guia_pedido_anclado(interp, estado.get("productos_vistos"))
        if _ga:
            _bloques.append(_ga)
            _tipos.append("pedido_anclado")
        else:
            # Sin pedido, si el cliente PREGUNTA por un producto visto, se ancla el
            # consultado para que el solver no re-elija otro modelo (hueco de T3).
            _gcon = _guia_consultado(interp, estado.get("productos_vistos"))
            if _gcon:
                _bloques.append(_gcon)
                _tipos.append("consultado_anclado")
        _gs = _guia_solicitud_nueva(interp, tienda_id)
        if _gs:
            _bloques.append(_gs)
            _tipos.append("solicitud_nueva")
        _gc = _guia_categorias(interp)
        if _gc:
            _bloques.append(_gc)
            _tipos.append("categorias")
        if not _bloques and (detectar_criterio(raw_message) == "más barato"
                             or criterio_del_interprete(interp)):
            from app.core.guia_compra import guia_mas_barato
            _gb = guia_mas_barato(raw_message, estado.get("productos_vistos"))
            if _gb:
                _bloques.append(_gb)
                _tipos.append("mas_barato")
        if _bloques:
            estado["guia_determinista"] = "\n".join(_bloques)
            log.info("hub_atado_guia", trace_id=trace_id, tipos=_tipos)
    except Exception as e:
        log.warning("hub_atado_guia_error", trace_id=trace_id,
                    error=str(e)[:120])

    # ── SOLVER atado a las tools ────────────────────────────────────────
    business = (get_config("business_name", tienda_id=tienda_id)
                or settings.BUSINESS_NAME)
    texto, meta = await solver_gemini.generar_respuesta(
        raw_message, interp, estado, tienda_id, trace_id, history, business)
    if not texto:
        texto, meta = settings.VERIFIKA_FALLBACK_MESSAGE, (meta or {})

    # ── ESTAMPADO por codigo ────────────────────────────────────────────
    ids_mostrados = [m.upper() for m in _RE_PROD.findall(texto or "")]
    present = _presupuesto_de_meta(meta)
    if present:
        texto = _sustituir_o_acoplar_presupuesto(texto, present)
    texto = _estampar_productos(texto, tienda_id, trace_id)
    # Si el modelo puso [[PRESUPUESTO]] sin un total que sellar, se saca prolijo
    # para no filtrar el marcador (limpieza del estampado, no una guarda).
    texto = _RE_PRESUP_SOBRANTE.sub(" ", texto).strip()
    texto = _RE_ID_FILTRADO.sub("", texto)

    # ── CIERRE Y COBRO ──────────────────────────────────────────────────
    # Reusa la logica del camino vivo: entrega datos de pago a pedido, capta el
    # lead en la decision de compra, pregunta suave de cierre. Puede pisar el
    # texto (ej "pasame los datos para transferir" -> CBU + link). Corre sobre el
    # texto YA estampado y antes de guardarlo en la memoria.
    texto, datos_cli_parciales, pregunta_cierre_hecha, presupuesto_str = \
        await _aplicar_cierre(conv, user_id, canal, tienda_id, raw_message, texto,
                              trace_id, interp, present)

    # ── MEMORIA ─────────────────────────────────────────────────────────
    history = history + [
        {"role": "user", "content": raw_message},
        {"role": "assistant", "content": texto}]
    resumen_charla = conv.get("summary", "") or ""
    descartados = history[:-(settings.HISTORY_LIMIT * 2)]
    if descartados:
        try:
            from app.core.memoria_larga import actualizar_resumen
            resumen_charla = await actualizar_resumen(
                resumen_charla, descartados, trace_id)
        except Exception as e:
            log.warning("hub_atado_memoria_error", trace_id=trace_id,
                        error=str(e)[:120])
    history = history[-(settings.HISTORY_LIMIT * 2):]

    mostrados: list[dict] = []
    for pid in {i.upper() for i in ids_mostrados}:
        try:
            pp = get_product_by_id(pid, tienda_id=tienda_id)
        except Exception:
            pp = None
        if (isinstance(pp, dict) and pp.get("nombre")
                and isinstance(pp.get("precio_ars"), (int, float))):
            mostrados.append({"id": pid, "nombre": pp["nombre"],
                              "precio": int(pp["precio_ars"])})
    productos_vistos = merge_productos(
        conv.get("productos_vistos") or [], productos_de_meta(meta) + mostrados)
    _intent = interp.get("intencion") if isinstance(interp, dict) else None
    carrito_vigente = ((carrito_de_meta(meta) if _intent not in ("otra",) else [])
                       or (conv.get("carrito_vigente") or []))
    ultima_localidad = envio_de_meta(meta) or (conv.get("ultima_localidad") or "")
    ultimas_localidades = get_envio_localidades() or (
        conv.get("ultimas_localidades") or [])
    criterio_cliente = (
        detectar_criterio(raw_message)
        or ("más barato" if criterio_del_interprete(interp) else "")
        or (conv.get("criterio_cliente") or ""))
    provincia_envio = _prov_msg or (conv.get("provincia_envio") or "")

    try:
        save_conversation(
            user_id, history, resumen_charla, tienda_id=tienda_id,
            estado_conversacion=estado_nuevo,
            productos_vistos=productos_vistos, carrito_vigente=carrito_vigente,
            ultima_localidad=ultima_localidad,
            ultimas_localidades=ultimas_localidades,
            criterio_cliente=criterio_cliente, provincia_envio=provincia_envio,
            datos_cliente_parciales=datos_cli_parciales,
            pregunta_cierre_hecha=pregunta_cierre_hecha,
            ultimo_presupuesto=(presupuesto_str or None))
    except Exception as e:
        log.warning("hub_atado_save_error", trace_id=trace_id, error=str(e)[:150])

    # ── TRAZA POR COSTURA (modalidad de diagnostico) ────────────────────
    # UNA linea por turno con el dato en cada juntura del flujo, para ver de una
    # DONDE se corto: que leyo el interprete, si viajo la guia, que tools llamo
    # el solver y con que, el total que quedo sellado, y el carrito antes->despues.
    _tot = _RE_TOTAL.search(texto or "")
    log.info("hub_atado_traza", trace_id=trace_id,
             # 1. INTERPRETE
             i_intencion=interp.get("intencion"),
             i_producto=interp.get("producto_resuelto"),
             i_consultados=[c.get("producto")
                            for c in (interp.get("productos_consultados") or [])
                            if isinstance(c, dict)],
             i_pedido=[(it.get("producto"), it.get("cantidad"),
                        it.get("destino"))
                       for it in (interp.get("pedido") or [])
                       if isinstance(it, dict)],
             i_criterio=interp.get("criterio"),
             i_categorias=interp.get("categorias"),
             # 2. GUIA / SEÑALES DE ATADURA
             guia_mas_barato=bool(estado.get("guia_determinista")),
             destinos_forzados=solver_gemini._destinos_de_interp(interp),
             # 3. SOLVER: tools que llamo, con el arg clave
             tools=_tools_traza(meta),
             # 4. SELLADO
             total_sellado=(_tot.group(1) if _tot else None),
             # 5. MEMORIA: carrito antes -> despues
             carrito_prev=_carrito_traza(conv.get("carrito_vigente")),
             carrito_nuevo=_carrito_traza(carrito_vigente))

    log.info("hub_atado_ok", trace_id=trace_id,
             latency_ms=int((time.time() - t0) * 1000),
             tools=len((meta or {}).get("tools_called", [])))
    return texto
