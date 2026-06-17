"""
CAMINO_NUEVO — la columna limpia de cinco pasos.

Idea de Martin (15-jun): el sistema tiene dos caneras. La principal y la
DETERMINISTA, que se va llenando de datos a medida que la venta avanza
(interprete -> provider -> ficha -> faq -> tarifa -> cp -> cierre) y esos datos
viajan por toda la conversacion. Esas herramientas, aisladas, andan bien. El
problema era que el orchestrator intentaba ACOPLAR y DESACOPLAR esos datos por
codigo, con heuristicas, y eso generaba los conflictos del Solver.

El reparto correcto: asi como el LLM interpreta el mensaje de entrada mejor que el
codigo, tambien decide MEJOR que dato entra y sale de la canera determinista en
cada turno, incluso en los cambios de decision del cliente. Entonces el LLM emite
COMANDOS (acciones sobre el carrito), el CODIGO los ejecuta contra el catalogo y
sigue siendo el unico dueno del HECHO (id, precio, stock, envio, total). El LLM
nunca pone un numero; solo enruta.

Esta es la columna nueva, no un injerto en la vieja. Usa SOLO las piezas verdes
que ya existen y apaga todo lo demas:

  1. interpretar    (LLM 1)  interpretador.interpretar_mensaje -> intencion + acciones_carrito
  2. aplicar comandos         director.aplicar_acciones        -> carrito mutado por codigo
  3. resolver el hecho        provider.proveer                 -> foco/carrito/envio/total
  4. planilla unica           estado_pedido.construir_estado   -> la fuente de verdad del turno
  5. vestir + estampar (LLM 2) redactor + render.renderizar    -> prosa de venta con el numero verificado

Si la planilla pide confirmar, se devuelve la pregunta determinista y no se llama
al redactor. El cierre (captura de datos + link de Mercado Pago) lo maneja la capa
de leads que ya existe. Dos llamadas LLM por mensaje.

Detras del flag CAMINO_NUEVO (default off). En off nadie llama esto y el
orchestrator viejo corre intacto. En on, el orchestrator delega TODO el turno aca.
"""
import os
import re
import time
import uuid
import structlog

from app.config import get_settings
from app.logger import get_logger
from app.storage.firestore_client import (
    get_conversation, save_conversation, log_message, get_all_faq, get_config,
)

log = get_logger(__name__)
settings = get_settings()


def _bloque_faq(faqs: dict, *, max_temas: int = 40, max_chars: int = 220) -> str:
    """Compacta la FAQ de la tienda para aterrizar al redactor en politicas
    reales (envios, pagos, garantia). Es el unico canal de hechos de politica:
    el redactor responde desde aca, no de su memoria. La FAQ es chica y curada."""
    if not isinstance(faqs, dict) or not faqs:
        return ""
    lineas = []
    for tema, data in list(faqs.items())[:max_temas]:
        if not isinstance(data, dict):
            continue
        resp = str(data.get("respuesta", "") or "").strip().replace("\n", " ")
        if not resp:
            continue
        if len(resp) > max_chars:
            resp = resp[:max_chars] + "..."
        lineas.append(f"- {tema}: {resp}")
    if not lineas:
        return ""
    return "POLITICAS DE LA TIENDA (respondé SOLO con esto, no inventes):\n" + \
        "\n".join(lineas)


def _historial_corto(history: list[dict], n: int = 6) -> str:
    """Los ultimos turnos en texto plano para que el redactor tenga el hilo."""
    if not history:
        return "Sin charla previa."
    out = []
    for msg in history[-n:]:
        rol = "Cliente" if msg.get("role") == "user" else "Vos"
        cont = str(msg.get("content", "") or "")
        if len(cont) > 300:
            cont = cont[:300] + "..."
        out.append(f"{rol}: {cont}")
    return "\n".join(out)


def _prompt_redactor(mensaje: str, *, business_name: str, historial: str,
                     bloque_datos: str, bloque_faq: str, etapa: str,
                     marcador: str) -> str:
    """Prompt del redactor (LLM 2). Escribe la VENTA, no decide hechos. Los
    numeros van como marcador y el codigo los estampa verificados. Libre en la
    FORMA, nunca en el HECHO."""
    datos = bloque_datos.strip() or "Sin datos calculados este turno."
    faq = ("\n\n" + bloque_faq) if bloque_faq else ""
    return f"""Sos un vendedor argentino de {business_name}, claro y cordial, voseo.
Tu trabajo es responder al cliente y vender, escribiendo natural y breve.

REGLA DE ORO: vos NO decidis ni escribis numeros, precios ni totales. El sistema
ya los calculo y te los da abajo. Donde tengas que mostrar un presupuesto, un
total o el detalle de precios, escribi {marcador} en esa linea y el sistema pega
el bloque verificado. Nunca inventes un precio, un producto, un envio ni una
politica que no este en los datos de abajo. Si no tenes el dato, decilo honesto y
ofrece averiguarlo, no lo inventes.

CHARLA RECIENTE:
{historial}

DATOS REALES DEL TURNO, calculados por el sistema (productos, precios, envio,
total). Hablá SOLO de esto:
{datos}{faq}

ETAPA DE LA VENTA: {etapa}

MENSAJE ACTUAL DEL CLIENTE:
{mensaje}

Respondé al cliente, en pocas lineas, vendiendo con naturalidad. Si hay un
presupuesto o total que mostrar, poné {marcador} donde van los numeros. SOLO la
respuesta al cliente, sin preambulo."""


def _texto_ambiguo_director(amb: dict) -> str:
    """Pregunta por las variantes reales cuando el director no pudo resolver un
    agregado (ej la notebook viene en tres colores). Se pregunta con los nombres
    del catalogo en vez de tragarse el pedido en silencio."""
    cands = amb.get("candidatos") or []
    nombres = [c.get("nombre") for c in cands if c.get("nombre")]
    termino = amb.get("termino") or "eso"
    if not nombres:
        return (f"¿Cuál {termino} querés exactamente? Decime el modelo y te lo "
                "agrego.")
    if len(nombres) == 1:
        return f"¿Te referís al {nombres[0]}? Confirmame y te lo agrego."
    opciones = ", ".join(nombres[:-1]) + f" o {nombres[-1]}"
    return (f"Para {termino} tengo estas opciones: {opciones}. ¿Cuál querés que "
            "te agregue?")


async def _redactar(mensaje: str, *, business_name: str, historial: str,
                    bloque_datos: str, bloque_faq: str, etapa: str,
                    marcador: str, trace_id: str) -> str:
    """Llama al redactor (LLM 2). Reusa el cliente del interprete."""
    from app.core.interpretador import _llamar_llm
    prompt = _prompt_redactor(
        mensaje, business_name=business_name, historial=historial,
        bloque_datos=bloque_datos, bloque_faq=bloque_faq, etapa=etapa,
        marcador=marcador)
    raw = await _llamar_llm(prompt)
    return (raw or "").strip()


async def procesar_camino_nuevo(user_id: str, raw_message: str,
                                tienda_id: str, canal: str,
                                trace_id: str | None = None) -> str:
    """Procesa un turno por la columna limpia. Devuelve la respuesta al cliente.

    Cada paso esta envuelto: un fallo aislado no tumba el turno, cae al fallback
    de marca en vez de a un numero inventado. El codigo es siempre dueno del hecho.
    """
    trace_id = trace_id or str(uuid.uuid4())[:8]
    t0 = time.time()
    timings: dict[str, int] = {}
    log.info("camino_nuevo_inicio", trace_id=trace_id, tienda_id=tienda_id,
             user_id=user_id, msg_preview=raw_message[:80])

    # ── Estado persistido de la conversacion (la memoria de la canera) ──
    conv = get_conversation(user_id, tienda_id=tienda_id)
    history = conv.get("history", []) or []
    estado_anterior = conv.get("estado_conversacion", "saludo") or "saludo"
    carrito_memoria = conv.get("carrito_vigente", []) or []
    registro_memoria = conv.get("productos_vistos", []) or []
    localidad_memoria = conv.get("ultima_localidad", "") or ""
    pedido_pendiente_memoria = conv.get("pedido_pendiente") or None
    presupuesto_memoria = conv.get("ultimo_presupuesto", "") or ""

    business_name = settings.BUSINESS_NAME
    try:
        business_name = get_config("business_name", tienda_id=tienda_id) or business_name
    except Exception:
        pass

    final_response = None
    interpretacion = None
    estado_conv = estado_anterior
    carrito_actual = carrito_memoria
    presupuesto_actual = presupuesto_memoria
    pedido_pendiente_out = None
    prov = None
    estado_turno = None
    presupuesto_codigo = ""   # la verdad numerica del turno (para telemetria/render)
    short_circuit = False     # True cuando la puerta de confirmacion corto

    # ── ATAJOS DETERMINISTAS: intenciones clarisimas que el CODIGO resuelve mejor
    #    que el redactor, sin gastar LLM, sin puente, sin escalado absurdo:
    #      - "catalogo" / "que venden" -> lista las categorias REALES con conteo.
    #      - "nueva compra" / "empezar de cero" -> reset limpio del pedido.
    #    Visto en Telegram 16-jun: a "catalogo" el redactor improvisaba "buscando
    #    catalogo no encontre..."; a "nueva compra" caia en puente y escalaba.
    _atajo_resp = None
    _atajo_reset = False
    try:
        from app.core.orchestrator import (
            _es_nueva_compra, _respuesta_nueva_compra,
            _pide_catalogo, _respuesta_catalogo)
        if _es_nueva_compra(raw_message):
            _atajo_resp = _respuesta_nueva_compra()
            _atajo_reset = True
        elif _pide_catalogo(raw_message):
            _cat = _respuesta_catalogo(tienda_id)
            if _cat:
                _atajo_resp = _cat
    except Exception as e:
        log.warning("camino_nuevo_atajo_error", trace_id=trace_id,
                    error=str(e)[:120])

    if _atajo_resp is not None:
        log.info("camino_nuevo_atajo", trace_id=trace_id, reset=_atajo_reset)
        history.append({"role": "user", "content": raw_message})
        history.append({"role": "assistant", "content": _atajo_resp})
        cap = settings.HISTORY_LIMIT * 2
        if len(history) > cap:
            history = history[-cap:]
        try:
            if _atajo_reset:
                save_conversation(
                    user_id, history, "", tienda_id=tienda_id,
                    estado_conversacion="explorando", ultimo_presupuesto="",
                    productos_vistos=[], ultima_localidad="",
                    carrito_vigente=[], pedido_pendiente={})
            else:
                save_conversation(
                    user_id, history, conv.get("summary", ""),
                    tienda_id=tienda_id, estado_conversacion=estado_anterior)
        except Exception as e:
            log.warning("camino_nuevo_atajo_save_error", trace_id=trace_id,
                        error=str(e)[:120])
        try:
            log_message(user_id=user_id, mensaje_usuario=raw_message,
                        respuesta_bot=_atajo_resp, tools_called=[],
                        latency_ms=int((time.time() - t0) * 1000),
                        trace_id=trace_id, tienda_id=tienda_id)
        except Exception:
            pass
        return _atajo_resp

    try:
        # ── PASO 1: INTERPRETAR (LLM 1) ──────────────────────────────────
        # El LLM entiende el mensaje crudo y emite los COMANDOS sobre el carrito.
        # acciones_carrito requiere DIRECTOR_LLM on; sin el, la lista viene vacia
        # y el carrito no se mueve (el camino nuevo necesita DIRECTOR_LLM on).
        _ts = time.perf_counter()
        from app.core.interpretador import (
            interpretar_mensaje, corregir_estado_regresion)
        interpretacion = await interpretar_mensaje(
            raw_message, history, trace_id,
            estado_anterior=estado_anterior, tienda_id=tienda_id,
            carrito_actual=carrito_memoria)
        estado_conv = corregir_estado_regresion(
            interpretacion.get("estado_conversacion") or estado_anterior,
            estado_anterior, hay_historial=bool(history))
        timings["interpret_ms"] = int((time.perf_counter() - _ts) * 1000)
        # ── INTENCION VER CATALOGO (clasificada por el interprete) ──
        # El cliente quiere la vista general del inventario, no buscar un producto.
        # Se SACA del flujo comercial y se responde con las categorias reales. Caza
        # todas las formas ("mostrame todo", "que venden", "inventario"), no solo
        # la palabra exacta. Martin 16-jun: clasificar la intencion temprano, no
        # forzar todo a "buscar SKU". El certificador es rigido; el interprete, libre.
        if interpretacion.get("quiere_catalogo"):
            try:
                from app.core.orchestrator import _respuesta_catalogo
                _cat = _respuesta_catalogo(tienda_id)
            except Exception:
                _cat = None
            if _cat:
                history.append({"role": "user", "content": raw_message})
                history.append({"role": "assistant", "content": _cat})
                cap = settings.HISTORY_LIMIT * 2
                if len(history) > cap:
                    history = history[-cap:]
                try:
                    save_conversation(
                        user_id, history, conv.get("summary", ""),
                        tienda_id=tienda_id, estado_conversacion="explorando")
                except Exception as e:
                    log.warning("camino_nuevo_catalogo_save_error",
                                trace_id=trace_id, error=str(e)[:120])
                try:
                    log_message(user_id=user_id, mensaje_usuario=raw_message,
                                respuesta_bot=_cat, tools_called=[],
                                latency_ms=int((time.time() - t0) * 1000),
                                trace_id=trace_id, tienda_id=tienda_id)
                except Exception:
                    pass
                log.info("camino_nuevo_catalogo_intent", trace_id=trace_id)
                return _cat

        log.info("camino_nuevo_interp", trace_id=trace_id,
                 intencion=interpretacion.get("intencion"),
                 acciones=interpretacion.get("acciones_carrito"),
                 carrito_in=len(carrito_memoria),
                 producto_resuelto=interpretacion.get("producto_resuelto"))

        # ── PASO 2: APLICAR COMANDOS (codigo, dueño del hecho) ───────────
        # El director ejecuta las acciones contra el catalogo real: resuelve id,
        # precio y stock. Lista vacia = el turno no toca el carrito (mata el
        # arrastre). Es la unica autoridad del carrito este turno.
        from app.core.director import aplicar_acciones
        _dir = aplicar_acciones(
            interpretacion.get("acciones_carrito") or [],
            carrito_memoria, tienda_id, trace_id=trace_id)
        carrito_actual = _dir["carrito"]
        hubo_cambio_carrito = bool(_dir["cambios"])

        # ── CERTIFICADOR como UNICA autoridad de identidad, ANTES del provider ──
        # El cliente nombra un producto (producto_consultado, lo extrae el
        # interprete). El CERTIFICADOR decide si existe; el provider queda
        # SUBORDINADO. Si el veredicto es not_found, al provider se le dice que NO
        # adivine identidad (identidad_no_existe): no produce foco/ab/multi/
        # catalogo/ficha, no fabrica una Epson para un Zyltech. La pregunta cae al
        # puente fuera_catalogo de forma natural. Una sola autoridad, sin parche.
        _cert_no_existe = False
        _pc = (interpretacion.get("producto_consultado") or "").strip()
        if (_pc and not hubo_cambio_carrito
                and interpretacion.get("intencion")
                in ("pregunta_especifica", "exploracion", "otra", "decision_compra")):
            try:
                from app.core.certificador import certificar
                _cert = certificar(_pc, tienda_id, trace_id=trace_id)
                if _cert["status"] == "not_found":
                    _cert_no_existe = True
                    log.info("camino_nuevo_cert_not_found", trace_id=trace_id,
                             consultado=_pc[:60])
            except Exception as e:
                log.warning("camino_nuevo_cert_error", trace_id=trace_id,
                            error=str(e)[:120])

        # ── PASO 3: RESOLVER EL HECHO (provider, subordinado al certificador) ──
        from app.core.provider import proveer, contrato, verdad_del_turno
        prov = proveer(
            raw_message, tienda_id=tienda_id, registro=registro_memoria,
            carrito=carrito_actual, localidad_memoria=localidad_memoria,
            estado=estado_conv, interpretacion=interpretacion,
            pedido_pendiente=pedido_pendiente_memoria,
            delta_aplicado=hubo_cambio_carrito,
            identidad_no_existe=_cert_no_existe, trace_id=trace_id)
        if prov.get("pendiente_nuevo") is not None:
            pedido_pendiente_out = prov["pendiente_nuevo"]
        elif prov.get("pendiente_consumido"):
            pedido_pendiente_out = {}
        # ¿Hubo FUENTE de producto este turno? (antes de anular las selecciones).
        # Con identidad_no_existe, el provider no produjo producto: _tiene_producto
        # queda False solo y la pregunta cae al puente.
        _tiene_producto = bool(
            prov.get("foco") or prov.get("carrito_calc") or prov.get("catalogo")
            or prov.get("ficha") or prov.get("ab") or prov.get("multi"))

        # El carrito lo gobierna el director (el LLM via comandos). Si el director
        # toco el carrito, ESE carrito es la unica verdad y se anulan TODAS las
        # selecciones alternativas del provider. Y si ya habia un pedido
        # establecido aunque el director no lo tocara este turno, se anula la
        # RELECTURA especulativa del texto (multi/ab): es la heuristica vieja que
        # competia y disparaba una confirmacion que pisaba el carrito (visto:
        # "mejor que sean 2 teclados" re-preguntaba en vez de cambiar cantidad).
        if hubo_cambio_carrito or carrito_memoria:
            for _k in ("foco", "ab", "multi", "foco_envio_calc"):
                prov[_k] = None

        # ── PASO 4: PLANILLA UNICA (la fuente de verdad del turno) ───────
        from app.core.estado_pedido import construir_estado
        estado_turno = construir_estado(
            prov, estado_conv=estado_conv, interpretacion=interpretacion,
            trace_id=trace_id)

        # ── PASO 5: PUERTA DE CONFIRMACION / PUENTE / REDACTOR + RENDER ──
        try:
            faqs = get_all_faq(tienda_id=tienda_id)
        except Exception:
            faqs = {}

        # ¿Hay FUENTE para responder? Producto/carrito enganchado, cambio de
        # carrito, o una FAQ que conteste la pregunta. Si NO hay y el turno es una
        # pregunta, es algo FUERA de las herramientas: ahi entra el puente.
        _es_pregunta = (interpretacion.get("intencion")
                        in ("pregunta_especifica", "otra"))
        _faq_cubre = False
        if _es_pregunta:
            try:
                from app.core.faq_responder import responder_faq_directo
                _faq_cubre = bool(responder_faq_directo(
                    raw_message, faqs, hay_producto=False, trace_id=trace_id))
            except Exception:
                _faq_cubre = False
        _tiene_fuente = bool(
            estado_turno.get("items") or _tiene_producto
            or hubo_cambio_carrito or _faq_cubre)
        # El veredicto del certificador MANDA sobre la FAQ: si el cliente pregunto
        # por un producto puntual que NO existe, la respuesta honesta es "no lo
        # tengo" (puente fuera_catalogo), no un dato tangencial de la FAQ que
        # matcheo de costado. Sin esto el redactor improvisaba y alucinaba stock.
        if _cert_no_existe:
            _tiene_fuente = False
        # Tipo de situacion del puente (por keyword), una sola vez.
        _tipo_sit = "generico"
        try:
            from app.core.puentes import clasificar_situacion
            _tipo_sit = clasificar_situacion(raw_message)
        except Exception:
            pass
        # Pregunta por un SERVICIO que no ofrecemos (alquiler, retiro, armado...):
        # va al puente aunque el provider haya enganchado un producto, salvo que
        # la FAQ lo cubra (ej envoltorio, que la tienda si responde). El producto
        # matcheado NO contesta lo que el cliente pregunta, que es el servicio.
        if _es_pregunta and not _faq_cubre and _tipo_sit == "servicio_inexistente":
            _tiene_fuente = False
        # El puente SOLO aplica ante una pregunta REAL de producto o servicio: el
        # cliente nombro un producto (que el certificador dictamino que no existe)
        # o el mensaje matchea un tipo de hueco concreto. NO aplica al chitchat
        # generico (un "estas apurado", un "nueva compra" mal leido): eso lo
        # maneja el redactor, NO el puente (visto Telegram 16-jun: "nueva compra"
        # caia en puente generico y escalaba a humano por insistencia).
        _puente_aplica = bool(
            _pc or _cert_no_existe or _tipo_sit not in ("generico", "no_entiende"))

        _amb_dir = _dir.get("ambiguos") or []
        if _amb_dir:
            # El director no pudo resolver un agregado (varias variantes reales,
            # ej color de la notebook). Se PREGUNTA con los candidatos reales en
            # vez de tragarse el pedido en silencio.
            final_response = _texto_ambiguo_director(_amb_dir[0])
            short_circuit = True
            log.info("camino_nuevo_ambiguo_director", trace_id=trace_id,
                     termino=_amb_dir[0].get("termino"))
        elif estado_turno["confirmacion"]["necesita"]:
            # Ambiguedad real: el codigo pregunta con datos reales del catalogo.
            # No se gasta el redactor; la pregunta es determinista.
            final_response = estado_turno["confirmacion"]["texto"]
            short_circuit = True
            from app.core.puentes import marcar_resuelto
            marcar_resuelto(user_id)
            log.info("camino_nuevo_confirmacion", trace_id=trace_id,
                     tipo=estado_turno["confirmacion"]["tipo"])
        elif (settings.PUENTES_VENTA and _es_pregunta and not _tiene_fuente
                and _puente_aplica):
            # FUERA de las herramientas (no hay producto ni FAQ que conteste): el
            # PUENTE sostiene la venta sin inventar un hecho, y escala a humano si
            # el cliente insiste con el mismo hueco. No pasa por el redactor para
            # no darle lugar a improvisar un dato que el sistema no tiene.
            from app.core.puentes import elegir_puente
            _p = elegir_puente(raw_message, user_id=user_id)
            final_response = _p["texto"]
            short_circuit = True
            if _p.get("derivar"):
                estado_conv = "derivar_humano"
            log.info("camino_nuevo_puente", trace_id=trace_id,
                     tipo=_p.get("tipo"), derivar=_p.get("derivar"))
        else:
            # El redactor viste la venta. Se le pasa el bloque de datos REALES
            # (contrato) como aterrizaje y la FAQ como unica fuente de politica.
            from app.core.puentes import marcar_resuelto
            marcar_resuelto(user_id)   # respuesta real: corta la racha de insistencia
            _prod_interp = None
            if (interpretacion.get("producto_resuelto")
                    and interpretacion.get("confianza", 0) >= 0.85):
                _prod_interp = interpretacion["producto_resuelto"]
            bloque_datos = contrato(
                prov, estado=estado_conv,
                ofrecer_opciones=interpretacion.get("ofrecer_opciones"),
                registro=registro_memoria,
                producto_interpretador=_prod_interp)
            presupuesto_codigo = (estado_turno.get("presentacion")
                                  or verdad_del_turno(prov) or "")
            from app.core.render import renderizar, MARCADOR
            _ts = time.perf_counter()
            prosa = await _redactar(
                raw_message, business_name=business_name,
                historial=_historial_corto(history),
                bloque_datos=bloque_datos, bloque_faq=_bloque_faq(faqs),
                etapa=estado_turno["etapa"], marcador=MARCADOR,
                trace_id=trace_id)
            timings["redactor_ms"] = int((time.perf_counter() - _ts) * 1000)
            # El codigo estampa el numero verificado: el redactor no lo escribe.
            final_response = renderizar(prosa, presupuesto_codigo)
            if estado_turno.get("presentacion"):
                presupuesto_actual = estado_turno["presentacion"]

    except Exception as e:
        log.error("camino_nuevo_error", trace_id=trace_id, error=str(e)[:200])
        final_response = settings.FALLBACK_MESSAGE

    # ── NO_RESALUDO: el bot saluda en el primer turno, no a mitad de charla. El
    # redactor a veces abre con "¡Buenas!"; con historial previo se lo saca.
    if (settings.NO_RESALUDO and history and final_response
            and final_response != settings.FALLBACK_MESSAGE):
        try:
            from app.core.resaludo import quitar_resaludo
            final_response = quitar_resaludo(final_response)
        except Exception as e:
            log.warning("camino_nuevo_resaludo_error", trace_id=trace_id,
                        error=str(e)[:120])

    # ── LINK INVENTADO: ninguna URL nace del LLM. El unico link lo agrega el
    # codigo en el cierre (leads). Toda URL que llegue hasta aca es fabricada.
    if final_response and re.search(r"https?://", final_response):
        log.warning("camino_nuevo_link_inventado", trace_id=trace_id)
        final_response = re.sub(r"\S*https?://\S+", "", final_response).strip()

    # ── CIERRE / LEADS: captura de datos + link de Mercado Pago por codigo ──
    # Reusa la capa que ya existe. El cliente ve su pedido y total antes de que
    # le pidamos los datos: el pedido de datos se SUMA, no reemplaza la venta.
    if os.getenv("USE_LEADS", "false").lower() == "true" and final_response:
        try:
            from app.core.leads import procesar_mensaje_para_lead
            extra_text, leads_meta = await procesar_mensaje_para_lead(
                user_id=user_id, canal=canal, tienda_id=tienda_id,
                mensaje=raw_message, respuesta_solver=final_response,
                trace_id=trace_id, interpretacion=interpretacion,
                presupuesto=presupuesto_actual)
            if leads_meta.get("respuesta_directa"):
                _accion = leads_meta.get("accion")
                _pide_datos = _accion in ("pidiendo_datos", "handoff_humano")
                _es_fallback = final_response in (
                    settings.FALLBACK_MESSAGE, settings.VERIFIKA_FALLBACK_MESSAGE)
                if _pide_datos and not _es_fallback:
                    if leads_meta["respuesta_directa"] not in final_response:
                        final_response = (final_response + "\n\n"
                                          + leads_meta["respuesta_directa"])
                else:
                    final_response = leads_meta["respuesta_directa"]
            elif extra_text:
                final_response = final_response + extra_text
        except Exception as e:
            log.warning("camino_nuevo_leads_error", trace_id=trace_id,
                        error=str(e)[:160])

    # ── PERSISTIR el estado de la canera para el proximo turno ──
    # El carrito a guardar sale de la planilla (verificado); si no hay items,
    # el del director. La localidad: el turno gana, la memoria sostiene.
    carrito_guardar = carrito_actual
    if estado_turno and estado_turno.get("items"):
        carrito_guardar = [{"id": it["id"], "nombre": it.get("nombre"),
                            "cantidad": it.get("cantidad", 1)}
                           for it in estado_turno["items"] if it.get("id")]
    ultima_localidad_nueva = localidad_memoria
    try:
        from app.core.envio import clasificar_zona
        if clasificar_zona(raw_message):
            ultima_localidad_nueva = raw_message
    except Exception:
        pass
    # Registro de productos vistos: lo que mostro el provider este turno.
    productos_vistos_nuevo = registro_memoria
    try:
        from app.core.orchestrator import (
            _extraer_productos_vistos, _merge_productos_vistos)
        _regs = (prov or {}).get("registros") or []
        _turno = _extraer_productos_vistos(_regs)
        productos_vistos_nuevo = _merge_productos_vistos(
            _turno, registro_memoria, settings.REGISTRO_SESION_MAX)
    except Exception as e:
        log.warning("camino_nuevo_registro_error", trace_id=trace_id,
                    error=str(e)[:120])

    history.append({"role": "user", "content": raw_message})
    history.append({"role": "assistant", "content": final_response})
    cap = settings.HISTORY_LIMIT * 2
    if len(history) > cap:
        history = history[-cap:]
    try:
        save_conversation(
            user_id, history, conv.get("summary", ""), tienda_id=tienda_id,
            estado_conversacion=estado_conv,
            ultimo_presupuesto=presupuesto_actual,
            productos_vistos=productos_vistos_nuevo,
            ultima_localidad=ultima_localidad_nueva,
            carrito_vigente=carrito_guardar,
            pedido_pendiente=pedido_pendiente_out)
    except Exception as e:
        log.warning("camino_nuevo_save_failed", trace_id=trace_id,
                    error=str(e)[:120])

    latency_ms = int((time.time() - t0) * 1000)
    try:
        log_message(
            user_id=user_id, mensaje_usuario=raw_message,
            respuesta_bot=final_response, tools_called=[],
            latency_ms=latency_ms, trace_id=trace_id, tienda_id=tienda_id)
    except Exception:
        pass
    # Telemetria del turno: el banco/molino la lee para saber si hubo total
    # verificado por codigo, si la confirmacion corto y en que etapa quedo.
    if settings.TELEMETRIA_TURNO:
        try:
            from app.core.telemetria import registrar_turno
            _etapa = (estado_turno or {}).get("etapa")
            _outcome = ("bloqueado"
                        if final_response == settings.VERIFIKA_FALLBACK_MESSAGE
                        else "fallback_tecnico"
                        if final_response == settings.FALLBACK_MESSAGE else "ok")
            registrar_turno(
                (prov or {}).get("registros", []) or [], estado=_etapa,
                outcome=_outcome,
                presupuesto_codigo=bool(presupuesto_codigo),
                short_circuit=short_circuit,
                verdad=presupuesto_codigo if isinstance(presupuesto_codigo, str)
                and presupuesto_codigo else None,
                user_id=user_id)
        except Exception as e:
            log.warning("camino_nuevo_telemetria_error", trace_id=trace_id,
                        error=str(e)[:120])

    log.info("camino_nuevo_completado", trace_id=trace_id,
             latency_ms=latency_ms, etapa=(estado_turno or {}).get("etapa"),
             **{f"t_{k}": v for k, v in timings.items()})
    return final_response
