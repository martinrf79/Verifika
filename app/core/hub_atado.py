"""
HUB ATADO — el turno completo. Es EL camino vivo: el orchestrator entra aca y
no hay otro. El camino viejo (interprete_libre + solver de prosa libre) se
borro el 29-jul, con todo lo que colgaba de el.

Camino del turno:
  1. INTERPRETE (`interpretador`, Gemini con schema estricto): traduce el
     mensaje a estructura atada a enums de la fuente. Lo que puede nombrar sale
     del recall de `recall_modelos`.
  2. SOLVER (`generador_v2`): emite FRAGMENTOS atados a enums del universo del
     turno; el CODIGO estampa cada dato -precio, stock, total- desde la fuente.
  3. RED DE VERIFICADORES (`_red_de_verificadores`): montos, stock, FAQ
     numerica, intencion, cita, promesas y el juez de prosa, en ese orden.
  4. GUARDAS DE SALIDA (`guardas_salida`): presupuesto sin modelos, respuesta
     hueca, honestidad de bot y saludo con aviso.
  5. MEMORIA: se persiste el estado esencial para que la charla recuerde entre
     turnos (history, resumen largo, productos vistos, carrito, destinos,
     criterio, provincia, preferencias, ancla y grupos de envio).

REGLA que este archivo aprendio a la mala: si un modulo deja de estar en este
camino, no queda "al lado por las dudas". Entre el corte al hub y el 29-jul,
5.429 lineas -el juez, cinco verificadores y cinco guardas- quedaron escritas,
con sus tests en verde, sin que las llamara nadie. Verde sobre codigo muerto es
peor que rojo: da confianza falsa.
"""
import re
import time

from app.core.interpretador import interpretar_mensaje
from app.core.pedido_helpers import _destinos_de_interp
from app.core.estado_venta import (
    construir_estado, set_current_estado,
    productos_de_meta, carrito_de_meta, envio_de_meta, merge_productos,
    detectar_criterio, criterio_del_interprete, get_envio_localidades)
from app.core.tools_context import set_current_tienda
from app.core.pedido_helpers import _presupuesto_de_meta
from app.config import get_settings
from app.logger import get_logger
from app.storage.firestore_client import (
    get_conversation, save_conversation, get_product_by_id)

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


def _evidencia_del_texto(texto: str, meta: dict, estado: dict,
                         tienda_id: str, trace_id: str) -> list:
    """La EVIDENCIA del turno: tools llamadas, productos vistos releidos vivos,
    productos nombrados en el texto y la FAQ con sus valores. Es la fuente
    contra la que juzga TODA la red determinista de abajo.

    Se arma UNA sola vez y se comparte. Antes vivia adentro del verificador de
    montos, y cada verificador que se enchufaba la re-armaba: tres recorridas
    del catalogo por turno y, peor, tres versiones de "la verdad" que podian
    diferir entre si."""
    from app.core.evidencia import (build_evidence_from_tools,
                                    productos_nombrados_en)
    from app.storage.firestore_client import get_product_by_id
    vistos = []
    for p in (estado.get("productos_vistos") or []):
        if not isinstance(p, dict):
            continue
        vivo = None
        pid = str(p.get("id") or "").upper()
        if pid:
            try:
                vivo = get_product_by_id(pid, tienda_id=tienda_id)
            except Exception:
                vivo = None
        vistos.append(vivo if isinstance(vivo, dict) and vivo.get("precio_ars")
                      is not None else
                      {**p, "precio_ars": p.get("precio_ars", p.get("precio"))})
    evidencia = build_evidence_from_tools(
        meta.get("tools_called", []) or [], tienda_id, productos_vistos=vistos)
    _ids = {str(i.get("id") or "").upper() for i in evidencia
            if i.get("tipo") == "producto"}
    for pn in productos_nombrados_en(texto, tienda_id):
        if str(pn.get("id") or "").upper() not in _ids:
            evidencia.append({"tipo": "producto", **pn})
    for i in evidencia:
        if (i.get("tipo") == "producto" and i.get("precio_ars") is None
                and isinstance(i.get("precio"), (int, float))):
            i["precio_ars"] = i["precio"]
    return evidencia


async def _red_de_verificadores(texto: str, meta: dict, estado: dict, conv: dict,
                                universo, interp, mensaje: str, tienda_id: str,
                                trace_id: str) -> str:
    """LA RED. Ya no es una cadena: cada verificador OPINA sobre el MISMO texto y
    un solo lugar aplica todo y decide (`app/core/red_verificadores.py`).

    Hasta el 29-jul esto eran siete escalones encadenados, cada uno recibiendo lo
    que dejo el anterior. De ahi salio el bug que cazaron las charlas grabadas:
    el juez REESCRIBE el mensaje entero y corre despues de la guardia de
    promesas, asi que metio "cerremos la operacion hoy mismo" y salio al cliente
    sin que nadie lo volviera a mirar. La guardia estaba bien; el problema era el
    ORDEN. La fase de VEREDICTO de la red nueva vuelve a diagnosticar todo sobre
    el resultado, asi que ese agujero ya no existe para ningun verificador.

    Este hub solo arma el CONTEXTO -la evidencia del turno, que se calcula una
    sola vez y la comparten todos- y llama. La logica vive en un modulo aparte
    porque asi se puede testear sin levantar un turno entero."""
    if not texto or texto == settings.VERIFIKA_FALLBACK_MESSAGE:
        return texto
    try:
        evidencia = _evidencia_del_texto(texto, meta, estado, tienda_id, trace_id)
    except Exception as e:
        log.warning("hub_atado_evidencia_error", trace_id=trace_id,
                    error=str(e)[:150])
        evidencia = []

    def _evidencia_juez():
        """Lo que el codigo le paso al solver, para que el juez mire EXACTAMENTE
        la misma evidencia. Un juez con menos evidencia que el redactor no
        detecta alucinacion: poda prosa fundada, que es peor que no tenerlo."""
        _evidencia_del_turno(meta, universo, interp, mensaje, tienda_id, trace_id)
        _productos_del_turno(texto, meta, universo, tienda_id, trace_id)

    from app.core.red_verificadores import revisar
    return await revisar(texto, {
        "evidencia": evidencia, "meta": meta, "estado": estado, "conv": conv,
        "universo": universo, "interp": interp, "mensaje": mensaje,
        "tienda_id": tienda_id, "trace_id": trace_id,
        "evidencia_juez": _evidencia_juez,
    })


def _productos_del_turno(texto: str, meta: dict, universo, tienda_id,
                         trace_id) -> None:
    """Los ids de los productos que el turno NOMBRO, para que sus fichas entren
    a la evidencia del juez.

    Sin esto, el juez marcaba sin respaldo lineas que habia escrito el CODIGO
    desde el catalogo: "Teclado Logitech K120 Blanco - $14.500 (22 en stock)",
    "garantia: 12 meses", "hercios de la pantalla: 60Hz". Su evidencia solo
    traia los productos que venian de una TOOL, y el camino atado estampa
    mucho mas que eso: la linea de producto, la ficha por campos y la spec
    honesta salen del renderizador o del hub, no de una tool. Medido en el
    banco del 29-jul: 11 de 20 turnos reescritos, y varios de esos "arreglos"
    borraban dato REAL de la fuente."""
    try:
        from app.core.evidencia import productos_nombrados_en
        ids = []
        for pn in productos_nombrados_en(texto, tienda_id):
            pid = str(pn.get("id") or "").upper()
            if pid and pid not in ids:
                ids.append(pid)
        # los del universo que aparezcan por nombre: el render los estampa por
        # id y el detector de arriba puede no pescarlos si el nombre viene
        # cortado.
        for p in (universo or []):
            pid = str((p or {}).get("id") or "").upper()
            nom = str((p or {}).get("nombre") or "")
            if pid and pid not in ids and nom and nom[:28].lower() in (texto or "").lower():
                ids.append(pid)
        if ids:
            meta["productos_evidencia"] = ids[:12]
    except Exception as e:
        log.warning("hub_atado_evidencia_productos_error", trace_id=trace_id,
                    error=str(e)[:120])


def _evidencia_del_turno(meta: dict, universo, interp, mensaje, tienda_id,
                         trace_id) -> None:
    """Carga en `meta` TODO lo que el codigo le paso al solver este turno, para
    que el juez de abajo mire exactamente la misma evidencia.

    Esto es lo que hace que el juez sirva. Un juez con menos evidencia que el
    redactor no detecta alucinacion: PODA prosa fundada, que es peor. Por eso no
    se recupera nada nuevo aca -no es una busqueda propia del fiscal- sino que se
    llama a las MISMAS funciones de `generador_v2` con las MISMAS entradas. Son
    deterministas, asi que devuelven el mismo paquete que armo el prompt.

    Las fichas de los productos y la FAQ que el modelo SI emitio ya viajan en
    `meta['tools_called']` desde `renderizar`. Lo que falta, y es justo lo que
    hace podar de mas, es el grounding que el modelo tuvo delante y no cito.
    """
    import re as _re
    from app.core import generador_v2
    try:
        _ids, menu = generador_v2._criterios_del_turno(mensaje, universo, interp)
        ya = {t.get("id") for t in (meta.get("prosa_evidencia") or [])}
        bloques = []
        for linea in (menu or "").split("\n"):
            m = _re.match(r"\s*\[([^\]]+)\]\s*(.+)", linea)
            if m and m.group(1) not in ya:
                bloques.append({"id": m.group(1), "texto": m.group(2)})
        if bloques:
            meta["prosa_evidencia"] = (meta.get("prosa_evidencia") or []) + bloques
    except Exception as e:
        log.warning("hub_atado_evidencia_criterio_error", trace_id=trace_id,
                    error=str(e)[:120])
    try:
        menu_faq, _temas = generador_v2._faq_del_turno(mensaje, interp, tienda_id)
        bloques = []
        for linea in (menu_faq or "").split("\n"):
            m = _re.match(r"\s*\[([^\]]+)\]\s*(.+)", linea)
            if m:
                bloques.append({"tema": m.group(1), "texto": m.group(2)})
        if bloques:
            meta["faq_evidencia"] = bloques
    except Exception as e:
        log.warning("hub_atado_evidencia_faq_error", trace_id=trace_id,
                    error=str(e)[:120])


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
        from app.core.pedido_helpers import _parece_aportar_dato
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
    # No se cierra sobre el fallback: no hay respuesta real que confirmar. PERO el
    # PEDIDO DE COBRO ("pasame los datos/enlaces para pagar") es determinista y NO
    # depende del solver: el solver atado no tiene fragmento para el cobro y cae al
    # fallback, y ahi se perdia la entrega del CBU/link (bug real, guion 48 T3 por
    # el flujo atado). Si el cliente pide el cobro, se corre igual y la entrega
    # reemplaza al fallback.
    from app.core.leads import _RE_PIDE_COBRO
    _pide_cobro = bool(_RE_PIDE_COBRO.search(raw_message or ""))
    if (texto and texto != settings.VERIFIKA_FALLBACK_MESSAGE) or _pide_cobro:
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
    # UNA CHARLA EN CURSO NO VUELVE A "SALUDO". El prompt lo dice, pero el
    # prompt solo no alcanza y por eso existe esta correccion determinista: si
    # el interprete lee mal un turno de mitad de charla como saludo -caso real:
    # el cliente putea por el envio en el turno 11-, el estado se reinicia y el
    # bot le contesta "¡Hola! Soy el asistente...". El hub venia guardando el
    # estado del interprete tal cual: la funcion existia y no la llamaba nadie.
    from app.core.interpretador import corregir_estado_regresion
    _corregido = corregir_estado_regresion(estado_nuevo, estado_anterior,
                                           bool(history))
    if _corregido != estado_nuevo:
        log.warning("hub_atado_estado_regresion", trace_id=trace_id,
                    leido=estado_nuevo, corregido=_corregido)
        estado_nuevo = _corregido
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
    frags, universo, presu_txt, presu_tools, respuestas_cat = \
        await generador_v2.generar_fragmentos(
            raw_message, history, estado, tienda_id, interp, trace_id)
    if frags:
        texto, _tools_called = generador_v2.renderizar(
            frags, universo, estado, tienda_id, trace_id,
            presupuesto_pre=presu_txt, presupuesto_tools=presu_tools,
            mensaje=raw_message, primer_turno=_primer_turno,
            respuestas_cat=respuestas_cat, historial=history)
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

    # ── HONESTIDAD DE SPEC (fuente specs_preguntables.json): si el cliente
    # pregunto una spec que la ficha NO trae, el CODIGO saca la afirmacion del
    # modelo y estampa "la ficha no lo especifica". El producto en cuestion sale
    # del que el interprete resolvio o del unico mostrado este turno.
    # se inicializan FUERA del try: los relee el estampado de compatibilidad de
    # abajo, y si el bloque de specs cortara antes de asignarlos quedarian sin
    # definir y se llevarian puesto el turno entero.
    _prod_spec, _variantes = None, []
    try:
        from app.core.generador_v2 import estampar_honestidad_specs
        from app.core.pedido_helpers import certificar_producto
        # el FOCO del turno: lo que el interprete resolvio o lo que el cliente
        # pregunto. Antes solo servia un producto UNICO y, como el catalogo
        # tiene variantes de color y de CPU, casi nunca habia uno solo: el
        # guardia no corria nunca y el modelo contestaba la spec por su cuenta.
        _nombres = []
        if isinstance(interp, dict):
            if interp.get("producto_resuelto"):
                _nombres.append(str(interp["producto_resuelto"]))
            _nombres += [str(c.get("producto")) for c in
                         (interp.get("productos_consultados") or [])
                         if isinstance(c, dict) and c.get("producto")]
        if _nombres:
            from app.storage.firestore_client import get_all_products
            _todos = get_all_products(tienda_id=tienda_id)
            for _n in _nombres:
                _v, _hits = certificar_producto(_n, _todos)
                if _hits:
                    _variantes, _prod_spec = _hits, _hits[0]
                    break
        if not _prod_spec:
            _sh = productos_de_meta(meta)
            if len(_sh) == 1 and _sh[0].get("id"):
                _prod_spec = get_product_by_id(str(_sh[0]["id"]).upper(),
                                               tienda_id=tienda_id)
                _variantes = [_prod_spec] if _prod_spec else []
        if isinstance(_prod_spec, dict):
            _antes_sp = texto
            # las specs que preguntó el cliente las TRADUJO el interprete al
            # enum de la fuente; el regex sobre el mensaje queda solo de red.
            _decl = (interp.get("specs_preguntadas")
                     if isinstance(interp, dict) else None)
            texto = estampar_honestidad_specs(texto, raw_message, _prod_spec,
                                              _variantes, _decl)
            if texto != _antes_sp:
                log.info("hub_atado_spec_honesta", trace_id=trace_id,
                         producto=_prod_spec.get("nombre"),
                         variantes=len(_variantes), declaradas=_decl)
    except Exception as e:
        log.warning("hub_atado_spec_error", trace_id=trace_id,
                    error=str(e)[:120])

    # ── HONESTIDAD DE COMPATIBILIDAD (fuente compatibilidad.csv). Mismo lugar y
    # mismo mecanismo que la spec, porque es el mismo problema: el cliente
    # pregunta si algo le sirve para SU equipo y hasta hoy eso lo contestaba el
    # modelo de memoria. Ahora la tabla dice con que anda cada modelo, el
    # interprete declara que equipo tiene el cliente -atado al enum del
    # vocabulario- y el CODIGO estampa el NO cuando la fuente dice que no entra.
    # El caso que lo pario: "es compatible con cualquier notebook", dicho sobre
    # una memoria RAM de escritorio, que en una notebook no entra.
    try:
        from app.core.compatibilidad import (estampar_veredicto,
                                             plataformas_de_interp,
                                             plataformas_del_mensaje)
        _plats = (plataformas_de_interp(interp)
                  or plataformas_del_mensaje(raw_message, tienda_id))
        if _plats:
            # los productos del turno: el foco resuelto y sus variantes, mas lo
            # que se mostro. Son los unicos sobre los que se puede juzgar.
            _prods_compat = list(_variantes or [])
            if isinstance(_prod_spec, dict) and _prod_spec not in _prods_compat:
                _prods_compat.append(_prod_spec)
            for _p in (universo or [])[:8]:
                if isinstance(_p, dict) and _p not in _prods_compat:
                    _prods_compat.append(_p)
            texto, _ev_compat = estampar_veredicto(texto, _prods_compat, _plats,
                                                   tienda_id)
            if _ev_compat:
                log.warning("hub_atado_compat_negada", trace_id=trace_id,
                            casos=_ev_compat[:6], plataformas=_plats[:3])
            else:
                log.info("hub_atado_compat", trace_id=trace_id,
                         plataformas=_plats[:3])
    except Exception as e:
        log.warning("hub_atado_compat_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")

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

    # ── RED DE NUMEROS: verificacion de montos contra la fuente ─────────
    # Ahora que la FAQ y la venta las REDACTA el solver, el numero lo teje el LLM
    # y se chequea aca contra la evidencia del turno (antes se protegia solo por
    # el estampado). Determinista, conservador: corrige lo inequivoco.
    # La red entera, en orden de dureza: montos, stock, FAQ numerica,
    # intencion, cita, promesas y el juez. Antes del dedup y de la memoria,
    # para que lo que se guarda sea exactamente lo que se manda.
    texto = await _red_de_verificadores(texto, meta, estado, conv, universo,
                                        interp, raw_message, tienda_id, trace_id)

    # ── GUARDAS DE SALIDA (deterministas, sin modelo) ───────────────────
    # Las cinco que vivian en interprete_libre y se perdieron al cortar. Ver
    # app/core/guardas_salida.py: por que existe cada una y cual fue el caso
    # real que la parió.
    from app.core import guardas_salida as _gs
    _negocio = _gs.business_name(tienda_id)

    # PRESUPUESTO SIN MODELOS: se BORRO el 29-jul, despues de romper una charla
    # REAL de Martin por WhatsApp (trace a2d0a5dc).
    #
    # QUE PASO. El cliente escribio "Dame precio de 2 notebooks 2 auriculares y
    # 2 mauses, 1 notebook y un auricular en Concordia...". El sistema lo
    # resolvio BIEN: calculo con seis productos reales del catalogo, dos
    # destinos, el verificador de montos reviso quince numeros sin encontrar uno
    # solo sin respaldo, y el juez paso. Y despues esta guarda tiro todo eso a
    # la basura y lo reemplazo por "necesito que me digas los modelos".
    #
    # POR QUE NO VA MAS. La guarda nacio en el camino viejo, donde el solver
    # elegia productos de su cabeza y podia poner un teclado al precio de una
    # notebook. En el camino atado eso es IMPOSIBLE por construccion: los items
    # de un fragmento calculo son ids del universo del turno y el precio lo
    # estampa el codigo desde la fuente. O sea que la enfermedad que curaba ya
    # no existe, y lo unico que quedaba era el efecto secundario: negarle al
    # cliente un presupuesto correcto que el sistema ya habia armado.
    #
    # Que el modelo ELIJA por el cliente cuando no dijo modelos no es un error:
    # es lo que hace un vendedor. Le muestra una propuesta concreta con precios
    # reales y el cliente ajusta. Negarse es peor venta y peor experiencia.
    #
    # Queda el RADAR, que es lo unico que valia: saber cuando se armo un total
    # sobre categorias que el cliente pidio sin nombrar modelo.
    try:
        from app.core.guia_pedido import cantidades_por_categoria
        _cats_ped = cantidades_por_categoria(raw_message, tienda_id) or []
        if _cats_ped and _RE_TOTAL.search(texto or ""):
            log.info("hub_atado_total_sobre_categorias", trace_id=trace_id,
                     categorias=[c for _n, c in _cats_ped])
    except Exception as e:
        log.warning("hub_atado_total_categorias_error", trace_id=trace_id,
                    error=str(e)[:120])

    # RESPUESTA HUECA: vacia o sin nada que conteste ni mueva la charla. Se le
    # pasa si el turno emitio algun fragmento de DATO: con eso la respuesta
    # contesta algo por construccion y no se la juzga por su largo.
    _hubo_datos = any(
        (f or {}).get("tipo") in ("producto", "opciones", "ficha", "faq",
                                  "criterio", "calculo", "presupuesto", "envio")
        for f in (frags or []))
    try:
        if (_gs.mensaje_con_contenido(raw_message)
                and _gs.sin_sustancia(texto, hubo_datos=_hubo_datos)
                and texto != settings.VERIFIKA_FALLBACK_MESSAGE):
            texto = _gs.fallback_o_curada(raw_message, interp, tienda_id,
                                          trace_id)
            log.warning("hub_atado_respuesta_hueca", trace_id=trace_id)
    except Exception as e:
        log.warning("hub_atado_sustancia_error", trace_id=trace_id,
                    error=str(e)[:120])

    # ANUNCIO SIN CONTENIDO: radar, no poda. La respuesta promete contar algo
    # y no lo cuenta. No es falsa, es incompleta: reemplazarla por el enlatado
    # seria empeorarla, asi que se MARCA para poder medirla en trafico real.
    try:
        if _gs.anuncio_sin_contenido(texto):
            log.warning("hub_atado_anuncio_sin_contenido", trace_id=trace_id,
                        respuesta_preview=texto[:200])
    except Exception as e:
        log.warning("hub_atado_anuncio_error", trace_id=trace_id,
                    error=str(e)[:120])

    # HONESTIDAD DE BOT: preguntan si es una maquina, se dice la verdad. El
    # prompt solo no alcanza; en el banco el solver esquivaba la pregunta.
    try:
        texto = _gs.asegurar_honestidad_bot(raw_message, texto, _negocio)
    except Exception as e:
        log.warning("hub_atado_honestidad_bot_error", trace_id=trace_id,
                    error=str(e)[:120])

    # SALUDO Y AVISO: primer mensaje de la charla, una sola vez. Va al FINAL
    # para que ninguna guarda de arriba se lleve puesto el aviso.
    try:
        if not history:
            texto = _gs.con_saludo_inicial(texto, _negocio)
            log.info("hub_atado_saludo_inicial", trace_id=trace_id)
        else:
            # de acá en adelante no se saluda mas: el saludo del modelo se
            # recorta, para que no abra con "¡Hola!" en el turno 2, 3 y 5.
            _antes_s = texto
            texto = _gs.sin_saludo_del_modelo(texto)
            if texto != _antes_s:
                log.info("hub_atado_saludo_repetido_podado", trace_id=trace_id)
    except Exception as e:
        log.warning("hub_atado_saludo_error", trace_id=trace_id,
                    error=str(e)[:120])

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

    # ── Y LA CONTRADICCION DEL ENVIO, sobre el texto FINAL ──────────────
    # Corre aca y no solo en el render porque despues del render pasan el cierre,
    # el estampado de compatibilidad, la red de verificadores -que REESCRIBE- y
    # las guardas. Podado en el render, la frase volvia a entrar por alguno de
    # esos pasos: medido el 31-jul en los guiones 15, 18 y 19, donde el numero de
    # envio ya estaba estampado y el mensaje igual terminaba diciendo que el
    # costo exacto lo calcula el sistema despues. Es determinista y contra el
    # dato duro; no le pregunta nada al modelo.
    texto = generador_v2._sin_negar_lo_estampado(texto, trace_id)

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

    # MEMORIA STICKY que el camino viejo persistia y el atado NO estaba
    # guardando (27-jul): al pasar produccion al hub, estas tres se leian en
    # construir_estado pero nunca se escribian, asi que se perdian TODOS los
    # turnos. Eran memoria muerta:
    #   - preferencias: "no quiero de China", tope de plata, uso previsto. El
    #     generador filtra el universo con ellas; sin persistir, valian un turno.
    #   - producto_anotado: el ancla de "me gusta ese, anotalo", que resuelve
    #     "el que te dije al principio".
    #   - grupos_envio: que item va a cada destino, que usa el reprecio del cierre.
    try:
        from app.core.estado_venta import (producto_anotado_actualizado,
                                           preferencias_actualizadas,
                                           get_current_estado)
        from app.storage.firestore_client import get_all_products
        producto_anotado = producto_anotado_actualizado(
            conv.get("producto_anotado"), interp, raw_message,
            get_all_products(tienda_id=tienda_id))
        preferencias_cliente = preferencias_actualizadas(
            conv.get("preferencias_cliente"), interp, raw_message)
        grupos_envio = ((get_current_estado() or {}).get("grupos_envio")
                        or conv.get("grupos_envio") or [])
        if preferencias_cliente != (conv.get("preferencias_cliente") or {}):
            log.info("hub_atado_preferencias", trace_id=trace_id,
                     preferencias=preferencias_cliente)
    except Exception as e:
        log.warning("hub_atado_sticky_error", trace_id=trace_id,
                    error=str(e)[:150])
        producto_anotado = conv.get("producto_anotado") or {}
        preferencias_cliente = conv.get("preferencias_cliente") or {}
        grupos_envio = conv.get("grupos_envio") or []

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
            ultimo_presupuesto=(presupuesto_str or None),
            producto_anotado=producto_anotado,
            preferencias_cliente=preferencias_cliente,
            grupos_envio=grupos_envio)
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
             i_orden=interp.get("orden"),
             i_specs=interp.get("specs_preguntadas"),
             i_categorias=interp.get("categorias"),
             # 2. SEÑALES DE ATADURA que alimentan el ENUM del universo
             i_solicitud_nueva=[s.get("categoria")
                                for s in (interp.get("solicitud_nueva") or [])
                                if isinstance(s, dict)],
             destinos_forzados=_destinos_de_interp(interp),
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
