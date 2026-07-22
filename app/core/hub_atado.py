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
from app.core.interprete_libre import _presupuesto_de_meta
from app.config import get_settings
from app.logger import get_logger
from app.storage.firestore_client import (
    get_conversation, save_conversation, get_config, get_product_by_id)

log = get_logger(__name__)
settings = get_settings()

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
            rd = meta_lead.get("respuesta_directa")
            if rd:
                # CONTINUIDAD: el cierre se SUMA a la respuesta del solver, no la
                # reemplaza (antes el enlatado pisaba la respuesta y se comia la
                # pregunta que venia en el mismo mensaje: T3 "sirve para PS5", T9
                # "confirmame que va a cada ciudad"). PERO el path pregunta_suave
                # arma respuesta_directa = respuesta_solver + pregunta, o sea ya
                # trae el cuerpo entero: sumarlo duplicaba TODA la respuesta
                # (banco guion 59 T2 y 60 T2). Si rd ya reconstruyo el cuerpo, se
                # REEMPLAZA; si aporta solo su parte (datos de pago, linea de
                # cierre), se SUMA. Sin cuerpo sustancial, rd manda.
                base = (texto or "").strip()
                rd_s = rd.strip()
                sustancial = base and base != settings.VERIFIKA_FALLBACK_MESSAGE
                if not sustancial:
                    texto, modo = rd_s, "reemplazo"
                elif base[:80] and base[:80] in rd_s:
                    texto, modo = rd_s, "reemplazo_dedup"
                else:
                    texto, modo = base + "\n\n" + rd_s, "suma"
                log.info("hub_atado_cierre", trace_id=trace_id,
                         accion=meta_lead.get("accion"), modo=modo)
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

    # El anclado del pedido, la categoria pedida no mostrada y los consultados
    # ya NO viajan como guia de texto al solver: generador_v2 los ata por
    # construccion al armar el universo del turno desde los campos estructurados
    # del interprete (universo_productos consume solicitud_nueva, pedido y
    # productos_consultados). Un solo mecanismo de atadura, el enum, no dos.

    # ── SOLVER ATADO POR ENUM: generador_v2 (salida estructurada) ───────
    # El modelo emite FRAGMENTOS atados a enums de la fuente -ids del universo
    # del turno, temas de FAQ, bloques de criterio- por responseSchema strict,
    # el MISMO mecanismo que el interprete. El CODIGO estampa cada dato al
    # renderizar: precio, stock, total NACEN de la fuente, no del modelo.
    # Reemplaza al solver de prosa libre, cuya salida sin schema dejaba pasar la
    # alucinacion (stock inventado, banco guion 59). renderizar ya devuelve el
    # texto final estampado; el unico texto libre es el pegamento, podado de dato.
    from app.core import generador_v2
    _primer_turno = not (estado.get("productos_vistos") or estado.get("carrito"))
    frags, universo, presu_txt, presu_tools = await generador_v2.generar_fragmentos(
        raw_message, history, estado, tienda_id, interp, trace_id)
    if frags:
        texto, _tools_called = generador_v2.renderizar(
            frags, universo, estado, tienda_id, trace_id,
            presupuesto_pre=presu_txt, presupuesto_tools=presu_tools,
            mensaje=raw_message, primer_turno=_primer_turno)
        meta = {"tools_called": _tools_called, "secciones": [],
                "prosa_citada": [], "turno_criterio": False}
        log.info("hub_atado_generador_v2", trace_id=trace_id,
                 fragmentos=len(frags), tools=len(_tools_called))
    else:
        texto, meta = settings.VERIFIKA_FALLBACK_MESSAGE, {"tools_called": []}
        log.warning("hub_atado_generador_v2_sin_fragmentos", trace_id=trace_id)

    # ── GARANTIA del "no" honesto (categoria no vendida, fuente no_vendidas.json).
    # El solver ya ofrece la alternativa real (nota + universo), pero el "no" no
    # puede depender de que el modelo lo diga: el CODIGO lo estampa al frente si el
    # texto no declino claro. La CASUISTICA vive en config; esto es el mecanismo.
    try:
        from app.core.guia_compra import categoria_no_vendida
        _cnv = categoria_no_vendida(raw_message, tienda_id)
        _declina = any(k in (texto or "").lower() for k in
                       ("no vend", "no trabaj", "no manej", "no tenemos",
                        "no lo tenemos", "no contamos", "no comerci",
                        "no ofrecemos", "no dispon"))
        if _cnv and not _declina:
            texto = (f"Te soy honesto: {_cnv[0]} no trabajamos, nuestro rubro es "
                     f"tecnología e informática.\n\n" + (texto or "")).strip()
            log.info("hub_atado_no_vendida_estampada", trace_id=trace_id,
                     pedida=_cnv[0])
    except Exception as e:
        log.warning("hub_atado_no_vendida_error", trace_id=trace_id,
                    error=str(e)[:120])

    # ── El dato ya lo estampo renderizar desde la fuente. Aca solo se leen el
    # presupuesto y los productos mostrados para el cierre y la memoria; NO se
    # re-inyecta (renderizar no deja marcadores [[PROD]] ni [[PRESUPUESTO]]).
    present = presu_txt or _presupuesto_de_meta(meta)
    ids_mostrados = [str(p.get("id")).upper()
                     for p in productos_de_meta(meta) if p.get("id")]
    texto = _RE_ID_FILTRADO.sub("", texto).strip()

    # ── CIERRE Y COBRO ──────────────────────────────────────────────────
    # Reusa la logica del camino vivo: entrega datos de pago a pedido, capta el
    # lead en la decision de compra, pregunta suave de cierre. Puede pisar el
    # texto (ej "pasame los datos para transferir" -> CBU + link). Corre sobre el
    # texto YA estampado y antes de guardarlo en la memoria.
    texto, datos_cli_parciales, pregunta_cierre_hecha, presupuesto_str = \
        await _aplicar_cierre(conv, user_id, canal, tienda_id, raw_message, texto,
                              trace_id, interp, present)

    # ── FILTRO ANTI-DUPLICADO (refuerzo final, determinista) ────────────
    # Ultima red antes de mandar y de guardar en memoria: saca cualquier
    # duplicado exacto y contiguo que se haya colado en algun paso. Conservador,
    # no toca lo legitimo.
    from app.core.dedup import deduplicar_respuesta
    _antes = texto
    texto = deduplicar_respuesta(texto)
    if texto != _antes:
        log.info("hub_atado_dedup", trace_id=trace_id,
                 quito=len(_antes) - len(texto))

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
             # 2. SEÑALES DE ATADURA que alimentan el ENUM del universo
             i_solicitud_nueva=[s.get("categoria")
                                for s in (interp.get("solicitud_nueva") or [])
                                if isinstance(s, dict)],
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
