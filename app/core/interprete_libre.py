"""
INTERPRETE_LIBRE — modo de prueba del intérprete (sesión 23-jun-2026).

Objetivo de Martín para esta etapa: dejar UNA sola cosa andando para poder
PROBAR la interpretación en real, apagando los ~70 flags y los cuatro caminos
paralelos del orchestrator. Acá no hay provider, ni verificadores, ni gate, ni
las catorce capas. Solo:

  1. INTERPRETE (LLM 1, interpretador.interpretar_mensaje): entiende el mensaje
     en el contexto de la charla. Es lo único que se está probando.
  2. SOLVER LIBRE (LLM 2, agent.run_agent con el prompt corto de modo_libre):
     redacta y vende libre, con las herramientas atadas a Firestore (catálogo y
     FAQs reales) y con la MEMORIA de la conversación. Recibe como guía lo que
     entendió el intérprete, pero no calcula nada que no salga de las tools.
La interpretación de cada turno se LOGUEA (evento interprete_libre_interpretacion)
para diagnosticar, pero NO se muestra al cliente: el cartel era solo de la etapa
de prueba y se quitó.

Es el ÚNICO camino del bot: el orchestrator delega acá todo el turno, sin flags.
"""
import time

from app.core.agent import run_agent
from app.core.interpretador import interpretar_mensaje
from app.core.leads import (
    procesar_mensaje_para_lead, descartar_leads_activos, get_lead_activo)
from app.core.estado_venta import (
    construir_estado, set_current_estado, bloque_para_solver,
    productos_de_meta, carrito_de_meta, envio_de_meta, merge_productos)
from app.core.tools import get_tools_schema
from app.config import get_settings
from app.logger import get_logger
from app.storage.firestore_client import (
    get_conversation, save_conversation, log_message, reset_conversation,
    get_config,
)

log = get_logger(__name__)
settings = get_settings()


# Prompt corto de venta del solver libre. SIN las mega-reglas defensivas: el
# modelo vende libre; lo unico firme es que los datos salen de las herramientas
# (atadas a Firestore). El filtro determinista y autofix son la red de despues.
_PROMPT_LIBRE = """Sos un vendedor de {business_name}, una tienda online argentina de tecnologia y gaming. Hablas en espanol argentino, tuteando, con calidez y ganas de ayudar a comprar.

Tu objetivo es VENDER bien: entender que necesita el cliente, mostrarle las mejores opciones, sacarle las dudas y avanzar hacia la compra. Sos libre en como lo decis y como ordenas la venta.

Lo unico que NO inventas son los datos reales de la tienda. Para eso tenes herramientas:
- search_products, get_product_details, list_catalog: precios, stock, specs y modelos del catalogo real.
- query_faq: formas de pago, garantia, devoluciones y demas politicas.
- calculate_total: cualquier total, subtotal, descuento o cuenta con cantidades.
- cotizar_envio: el costo de envio. Pasale lo que dijo el cliente (codigo postal, localidad o provincia) tal cual; el codigo determina la zona y la tarifa. NO elijas vos la zona ni inventes el costo. Si pide envio y no dio la zona, pedile el CP o la localidad.
Usalas cuando necesites un dato o un numero concreto, en vez de adivinarlo. Si necesitas varias cosas, pedilas juntas en un solo paso.

DATOS DUROS CON MARCADOR: cuando muestres un dato que salio de una herramienta, escribi el marcador en una linea sola y NO tipees vos el dato; el codigo lo reemplaza por el bloque real de la fuente:
- {{PRESUPUESTO}} para un total, subtotal o lista de precios de calculate_total.
- {{ENVIO}} para el costo de envio de cotizar_envio.
- {{FAQ}} para una politica o respuesta de query_faq (pago, garantia, devoluciones, plazos, etc.).
El resto (saludo, recomendacion, pregunta) lo escribis normal. Un precio suelto de UN producto podes decirlo; el presupuesto armado, el envio y las politicas van SIEMPRE con su marcador.

El interprete ya entendio al cliente y te pasa el ESTADO de la charla. Respetalo, no lo cambies vos:
- explorando: mostra productos o precios con las tools.
- esperando_confirmacion: ayudalo a decidir, no reabras el catalogo.
- esperando_datos: pedi o confirma el dato que falta (direccion, pago, contacto), sin volver a ofrecer productos.
- derivar_humano: cerra cordial, una persona del equipo lo contacta.
- saludo: devolve el saludo y ofrece ayuda corta.
- posventa: responde con query_faq, sin forzar una venta nueva.
Si el interprete te marca dos opciones (A o B), presenta las dos con su detalle y pregunta cual prefiere; nunca elijas vos ni promedies.

Estilo: espanol argentino, tuteo. Conciso y natural. Texto plano sin markdown. Precios en formato $280.000.
"""


def _business_name(tienda_id: str | None) -> str:
    name = settings.BUSINESS_NAME
    if tienda_id:
        try:
            stored = get_config("business_name", tienda_id=tienda_id)
            if stored:
                name = stored
        except Exception:
            pass
    return name


def _schema_acotado() -> list:
    """El schema de tools recortado a las que ve el solver libre (MODO_LIBRE_TOOLS:
    catalogo, FAQ, calculadora, envio). Si la lista queda vacia o no matchea, cae
    al schema completo para no dejar al modelo sin herramientas."""
    permitidas = {
        t.strip() for t in (settings.MODO_LIBRE_TOOLS or "").split(",")
        if t.strip()
    }
    full = get_tools_schema()
    if not permitidas:
        return full
    acotado = [s for s in full
               if s.get("function", {}).get("name") in permitidas]
    return acotado or full


def _presupuesto_de_meta(meta: dict) -> str:
    """Saca el presupuesto YA VERIFICADO (campo presentacion de calculate_total)
    del meta del solver, para que el cierre y el link de pago usen el total real
    de la calculadora, nunca uno inventado. "" si el solver no calculo este turno."""
    for tc in reversed((meta or {}).get("tools_called", []) or []):
        if tc.get("name") == "calculate_total":
            pres = (tc.get("result") or {}).get("presentacion")
            if pres:
                return pres
    return ""


def _faq_de_meta(meta: dict) -> str:
    """Respuesta VERBATIM del ultimo query_faq (texto cargado en Firestore) + las
    relacionadas, para estampar una politica tal cual la fuente, sin que el solver
    la parafrasee mal. "" si no hubo consulta de FAQ valida este turno."""
    for tc in reversed((meta or {}).get("tools_called", []) or []):
        if tc.get("name") != "query_faq":
            continue
        res = tc.get("result")
        if not isinstance(res, dict) or not res.get("encontrada"):
            continue
        partes = [str(res.get("respuesta", "")).strip()]
        for rel in res.get("relacionadas", []) or []:
            r = str((rel or {}).get("respuesta", "")).strip()
            if r:
                partes.append(r)
        return "\n".join(p for p in partes if p)
    return ""


def _guia_para_solver(interp: dict) -> str:
    """Inyecta al solver libre lo que entendió el intérprete, como GUÍA de qué
    quiere el cliente. No trae datos del catálogo: eso lo sacan las tools."""
    if not isinstance(interp, dict):
        return ""
    partes = []
    estado = interp.get("estado_conversacion")
    if estado:
        partes.append(f"estado={estado}")
    intencion = interp.get("intencion")
    if intencion:
        partes.append(f"intención={intencion}")
    if interp.get("producto_resuelto"):
        partes.append(f"se refiere a={interp['producto_resuelto']}")
    cands = interp.get("candidatos") or []
    if cands:
        partes.append("posibles=" + ", ".join(str(c) for c in cands[:3]))
    if interp.get("respondiendo_a"):
        partes.append(f"responde a={interp['respondiendo_a']}")
    if interp.get("ofrecer_opciones"):
        partes.append(f"ofrecer opción A o B={interp['ofrecer_opciones']}")
    if not partes:
        return ""
    return ("\n\n[El intérprete leyó este mensaje así: " + "; ".join(partes)
            + ". Actuá según el estado y la intención, no vuelvas a interpretar. "
            "Los precios, specs y datos de la tienda salen SOLO de las "
            "herramientas, no los inventes.]")


def _parece_aportar_dato(mensaje: str) -> bool:
    """Heuristica barata: el mensaje parece traer un dato de cierre (numero, pago,
    o cue de domicilio), aunque el interprete no lo haya marcado como aporta_dato.
    Abre el extractor LLM en cotizaciones que ya mencionan direccion o pago."""
    if not mensaje:
        return False
    t = mensaje.lower()
    if any(ch.isdigit() for ch in t):
        return True
    claves = ("transferenc", "mercado pago", "efectivo", "tarjeta", "debito",
              "credito", "calle", "avenida", " av ", "direccion", "domicilio",
              "envio a", "enviar a", "me llamo", "mi nombre")
    return any(k in t for k in claves)


async def procesar_interprete_libre(user_id: str, raw_message: str,
                                    tienda_id: str, canal: str,
                                    trace_id: str) -> str:
    """Maneja el turno entero: intérprete + solver libre + memoria. La
    interpretación se loguea para diagnosticar, no se muestra al cliente."""
    t0 = time.time()

    conv = get_conversation(user_id, tienda_id=tienda_id)
    history = conv.get("history", []) or []
    estado_anterior = conv.get("estado_conversacion", "saludo") or "saludo"
    # PROOF de turnos anteriores: respaldan un total que el cliente confirma y el
    # bot repite sin recalcular, asi el filtro determinista no bloquea en falso.
    proofs_memoria = conv.get("proofs_recientes", []) or []

    # ── RESET_CODE: palabra clave de PRUEBA para arrancar de cero ────────
    # El bot mantiene CONTINUIDAD siempre. NO resetea con frases naturales como
    # "nueva compra" (un cliente real las usa para seguir comprando, no para
    # borrar todo). Para las pruebas hay una palabra clave dedicada (RESET_CODE,
    # ej "verifika2026"): si el mensaje es EXACTAMENTE esa, se borra la conversacion
    # entera y se confirma. Con clientes reales no hace falta; es solo para testear
    # desde el mismo numero sin tocar el entorno.
    _rc = (settings.RESET_CODE or "").strip().lower()
    if _rc and (raw_message or "").strip().lower() == _rc:
        try:
            reset_conversation(user_id, tienda_id=tienda_id)
            descartar_leads_activos(user_id, canal, tienda_id)
        except Exception as e:
            log.warning("interprete_libre_reset_error", trace_id=trace_id,
                        error=str(e)[:120])
        log.info("interprete_libre_reset_code", trace_id=trace_id, user_id=user_id)
        return "Listo, conversacion reiniciada. Empezamos de cero."

    # ── ESTADO DE VENTA: fuente unica del turno, una sola carga ─────────────
    # Se arma desde la conversacion persistida + el lead activo y se setea en la
    # contextvar, asi el interprete, el solver, las herramientas y el cierre leen
    # la MISMA verdad sin recibirla por parametro (igual que tienda y destino).
    lead_activo = None
    try:
        lead_activo = get_lead_activo(user_id, canal, tienda_id)
    except Exception as e:
        log.warning("interprete_libre_lead_lookup_error", trace_id=trace_id,
                    error=str(e)[:120])
    estado = construir_estado(conv, lead_activo)
    set_current_estado(estado)

    # ── PASO 1: INTERPRETE ──────────────────────────────────────────────
    interp = {}
    try:
        interp = await interpretar_mensaje(
            raw_message, history, trace_id,
            estado_anterior=estado_anterior, tienda_id=tienda_id)
    except Exception as e:
        log.error("interprete_libre_interp_error", trace_id=trace_id,
                  error=str(e)[:200])

    estado_nuevo = (interp.get("estado_conversacion")
                    or estado_anterior) if isinstance(interp, dict) else estado_anterior

    # La interpretacion va al LOG para diagnosticar (reemplaza el cartel que antes
    # se mostraba al cliente). Asi se juzga la interpretacion sin molestar la charla.
    if isinstance(interp, dict):
        log.info("interprete_libre_interpretacion", trace_id=trace_id,
                 intencion=interp.get("intencion"), confianza=interp.get("confianza"),
                 estado=interp.get("estado_conversacion"),
                 producto=interp.get("producto_resuelto"),
                 responde_a=interp.get("respondiendo_a"),
                 candidatos=interp.get("candidatos"))

    # ── PASO 2: SOLVER LIBRE (con la guía del intérprete + estado de venta) ──
    # El solver ve, ademas del mensaje y la guia del interprete, el ESTADO DE LA
    # VENTA armado arriba: productos con precio real, carrito, total, envio cotizado
    # y datos del cliente ya capturados. Asi no re-pregunta la direccion ni
    # re-inventa un precio que ya salio de una tool.
    system_prompt = _PROMPT_LIBRE.format(business_name=_business_name(tienda_id))
    tools_schema = _schema_acotado()
    mensaje_enriquecido = (raw_message + _guia_para_solver(interp)
                           + bloque_para_solver(estado))

    log.info("interprete_libre_inicio", trace_id=trace_id,
             intencion=interp.get("intencion") if isinstance(interp, dict) else None,
             tools=len(tools_schema), hist=len(history))

    meta = {}
    try:
        respuesta, meta = await run_agent(
            mensaje_enriquecido, history, trace_id,
            tienda_id=tienda_id, user_id=user_id,
            system_prompt=system_prompt, tools_schema=tools_schema)
    except Exception as e:
        log.error("interprete_libre_solver_error", trace_id=trace_id,
                  error=str(e)[:200])
        respuesta = settings.FALLBACK_MESSAGE

    # ── CLON (ESTAMPA): los datos duros NACEN de la fuente, no del modelo ──
    # El solver pone un marcador donde va cada dato duro; el codigo lo reemplaza por
    # el bloque real renderizado desde la tool/Firestore (precio = presentacion de
    # calculate_total; envio = cotizar_envio; politica = respuesta verbatim de
    # query_faq). Asi ni el presupuesto, ni el envio, ni una politica se re-tipean o
    # se inventan. Marcador sin dato (la tool no corrio) -> se quita, no se inventa.
    # Se loguea cuando el solver dio el presupuesto SIN marcador, para medir.
    from app.core.estado_venta import envio_de_meta
    _env = envio_de_meta(meta)
    _present = _presupuesto_de_meta(meta)
    _marcadores = {
        "{{PRESUPUESTO}}": _present,
        "{{ENVIO}}": (f"Envio a {_env}" if _env else ""),
        "{{FAQ}}": _faq_de_meta(meta),
    }
    _tenia_marcador_presup = "{{PRESUPUESTO}}" in (respuesta or "")
    for _marca, _bloque in _marcadores.items():
        if _marca not in (respuesta or ""):
            continue
        if _bloque:
            respuesta = respuesta.replace(_marca, _bloque)
            log.info("interprete_libre_estampado", trace_id=trace_id, marca=_marca)
        else:
            respuesta = respuesta.replace(_marca, "").strip()
            log.warning("interprete_libre_marcador_sin_dato",
                        trace_id=trace_id, marca=_marca)
    if _present and not _tenia_marcador_presup:
        log.warning("interprete_libre_presupuesto_sin_marcador", trace_id=trace_id)

    # ── PASO 2a: FILTRO DETERMINISTA — CLON DEL MOTOR DE PRECIOS/ENVIO ──────
    # Partida doble de la verdad. Las herramientas deterministas (calculadora,
    # tarifa de envio, ficha del catalogo) le dan los numeros al Solver via
    # tool-call. Su PROOF queda guardado. ACA ese MISMO motor se usa como CLON
    # para auditar la respuesta que el Solver redacto:
    #   - si cada cifra de dinero coincide con el PROOF, la respuesta pasa intacta;
    #   - si el Solver CAMBIO un total y la verdad esta en el PROOF, el codigo
    #     REESCRIBE la cifra mala por la buena, sin llamar a ningun modelo
    #     (autocorregir_montos, conservador: solo un reemplazo INEQUIVOCO).
    # Con AUTOCORRIGE_MONTOS=false vuelve a modo observacion: solo loguea, no toca.
    proofs_turno = [t["proof"] for t in (meta.get("tools_called") or [])
                    if t.get("proof")]
    if respuesta != settings.FALLBACK_MESSAGE:
        try:
            from app.core.evidencia import build_evidence_from_tools
            from app.core.verificador import (
                verificar_respuesta, autocorregir_montos)
            # Productos vistos en turnos anteriores: su precio REAL respalda una
            # cifra que el bot ya mostro y repite, asi el filtro no la marca en
            # falso. El estado los guarda con la clave 'precio'; el verificador
            # lee 'precio_ars', por eso se normaliza al pasarlos.
            prods_vistos = [
                {**p, "precio_ars": p.get("precio_ars", p.get("precio"))}
                for p in (estado.get("productos_vistos") or [])
                if isinstance(p, dict)
            ]
            evidencia = build_evidence_from_tools(
                meta.get("tools_called", []) or [], tienda_id,
                productos_vistos=prods_vistos)
            evidencia += [{"tipo": "proof", "proof": p} for p in proofs_memoria]
            # Precios reales del catalogo: nunca se pisan aunque el filtro no los
            # vea respaldados en este turno (pueden venir de uno anterior).
            precios_validos = {
                int(i["precio_ars"]) for i in evidencia
                if i.get("tipo") == "producto"
                and isinstance(i.get("precio_ars"), (int, float))
            }
            if settings.AUTOCORRIGE_MONTOS:
                fix = autocorregir_montos(
                    respuesta, evidencia, trace_id,
                    precios_validos=precios_validos)
                if fix["cambiada"] and fix["verificacion"].get("ok"):
                    # El Solver habia cambiado el total y se reescribio por el real.
                    log.warning("interprete_libre_monto_corregido",
                                trace_id=trace_id,
                                correcciones=fix["correcciones"][:8],
                                respuesta_preview=fix["respuesta"][:220])
                    respuesta = fix["respuesta"]
                elif fix["cambiada"]:
                    # Se intento corregir pero el texto sigue sin cerrar: no se
                    # arriesga un numero a medias, queda el original (shadow).
                    log.warning("interprete_libre_correccion_descartada",
                                trace_id=trace_id,
                                correcciones=fix["correcciones"][:8])
                elif not fix["verificacion"].get("ok"):
                    # Cifra de plata sin respaldo que no se pudo corregir. Si el
                    # solver NO llamo ni una herramienta en el turno, ese numero es
                    # alucinacion pura: no tiene de donde salir. NO sale al cliente,
                    # va el mensaje seguro. Con herramientas llamadas el residual
                    # suele ser falso positivo, asi que ahi se queda en shadow para
                    # no cortar respuestas legitimas.
                    sin_tools = not (meta.get("tools_called") or [])
                    if sin_tools:
                        log.warning("interprete_libre_numero_bloqueado",
                                    trace_id=trace_id,
                                    no_respaldados=fix["verificacion"]["numeros_no_respaldados"][:8],
                                    respuesta_preview=respuesta[:220])
                        respuesta = settings.VERIFIKA_FALLBACK_MESSAGE
                    else:
                        log.warning("interprete_libre_numero_no_respaldado_shadow",
                                    trace_id=trace_id,
                                    no_respaldados=fix["verificacion"]["numeros_no_respaldados"][:8],
                                    respuesta_preview=respuesta[:220])
            else:
                veredicto = verificar_respuesta(respuesta, evidencia, trace_id)
                if not veredicto["ok"]:
                    log.warning("interprete_libre_numero_no_respaldado_shadow",
                                trace_id=trace_id,
                                no_respaldados=veredicto["numeros_no_respaldados"][:8],
                                respuesta_preview=respuesta[:220])
        except Exception as e:
            log.warning("interprete_libre_verif_error", trace_id=trace_id,
                        error=str(e)[:160])
    proofs_recientes = (proofs_memoria + proofs_turno)[-settings.VERIFICADOR_PROOF_MEMORY:]

    # ── PASO 2a-bis: GUARDIA DE PROMESAS PROHIBIDAS (enforce) ───────────────
    # Linea cero del TEXTO: un conjunto cerrado de afirmaciones que el bot no puede
    # decir aunque el cliente insista (dia exacto de entrega, retiro en local,
    # servicios fuera de la FAQ). Si la deteccion determinista dispara, el codigo
    # reescribe el mensaje sin la promesa antes de mandarlo. Una sola llamada extra
    # al modelo y SOLO en los turnos que disparan, no en todos.
    if respuesta != settings.FALLBACK_MESSAGE:
        try:
            from app.core.guardia_promesas import detectar, reescribir_sin_promesas
            clases = detectar(respuesta)
            if clases:
                log.warning("interprete_libre_promesa_prohibida", trace_id=trace_id,
                            clases=clases, respuesta_preview=respuesta[:200])
                nueva = await reescribir_sin_promesas(respuesta, clases, trace_id)
                if nueva:
                    quedan = detectar(nueva)
                    respuesta = nueva
                    if quedan:
                        log.warning("interprete_libre_promesa_persiste",
                                    trace_id=trace_id, clases=quedan)
                    else:
                        log.info("interprete_libre_promesa_reescrita",
                                 trace_id=trace_id, clases=clases)
        except Exception as e:
            log.warning("interprete_libre_guardia_error", trace_id=trace_id,
                        error=str(e)[:160])

    # ── PASO 2b: CIERRE (codigo) — capta el lead, pide datos, manda el link ──
    # El codigo toma el control SOLO cuando hay que cerrar: detecta la decision de
    # compra por la interpretacion, junta nombre/telefono/direccion/forma de pago y
    # genera el link de Mercado Pago con el total VERIFICADO de la calculadora (de
    # presentacion, nunca un monto del modelo). Si no hay cierre, la respuesta libre
    # del solver queda intacta. El presupuesto sale del turno o de la memoria.
    presupuesto = _presupuesto_de_meta(meta) or (conv.get("ultimo_presupuesto") or "")

    # ── ACUMULAR DATOS DEL CLIENTE turno a turno (raiz del re-pedido) ────────
    # El cliente suele dar la direccion, el pago o el nombre ANTES de la decision
    # de compra, o DENTRO de un mensaje de otra intencion (ej una cotizacion que ya
    # menciona "pago transferencia"). Antes la extraccion estaba atada a la intencion
    # (solo aporta_dato/decision_compra), asi que ese dato se perdia y el cierre lo
    # volvia a pedir. Ahora: (1) la extraccion DETERMINISTA (telefono, pago,
    # direccion por patron) corre SIEMPRE, barata y sin LLM; (2) el extractor LLM
    # corre cuando el interprete sugiere datos O el mensaje trae numeros/cue de dato.
    # El acumulado viaja al cierre y se persiste al final del turno.
    _intent = interp.get("intencion") if isinstance(interp, dict) else None
    datos_previos = conv.get("datos_cliente_parciales") or {}
    datos_turno: dict = {}
    try:
        from app.core.cierre import extraer_determinista, extraer_datos_cliente
        # Determinista, en CADA turno: el codigo manda en los datos.
        datos_turno.update(extraer_determinista(raw_message))
        # LLM, cuando hay senal de dato (intencion o el texto lo parece).
        if _intent in ("aporta_dato", "decision_compra") or _parece_aportar_dato(raw_message):
            for k, v in extraer_datos_cliente(raw_message, trace_id).items():
                if v:
                    datos_turno[k] = v
    except Exception as e:
        log.warning("interprete_libre_extractor_error", trace_id=trace_id,
                    error=str(e)[:120])
    datos_acumulados = {**datos_previos, **datos_turno}
    if datos_turno:
        log.info("interprete_libre_datos_turno", trace_id=trace_id,
                 user_id=user_id, intencion=_intent,
                 campos=sorted(datos_turno.keys()),
                 acumulado=sorted(datos_acumulados.keys()))

    if respuesta != settings.FALLBACK_MESSAGE:
        try:
            _, meta_lead = await procesar_mensaje_para_lead(
                user_id, canal, tienda_id, raw_message, respuesta, trace_id,
                interpretacion=interp if isinstance(interp, dict) else None,
                presupuesto=presupuesto,
                datos_turno=datos_turno, datos_previos=datos_acumulados)
            if meta_lead.get("respuesta_directa"):
                respuesta = meta_lead["respuesta_directa"]
                log.info("interprete_libre_cierre", trace_id=trace_id,
                         accion=meta_lead.get("accion"))
        except Exception as e:
            log.warning("interprete_libre_lead_error", trace_id=trace_id,
                        error=str(e)[:160])

    # El cliente recibe la respuesta limpia: el cartel de interpretacion se quito
    # (ahora va al log). La interpretacion se sigue viendo en interprete_libre_interpretacion.
    respuesta_final = respuesta

    # ── MEMORIA: guardar el turno (el solver siempre recuerda la charla) ──
    history = history + [
        {"role": "user", "content": raw_message},
        {"role": "assistant", "content": respuesta},
    ]
    history = history[-(settings.HISTORY_LIMIT * 2):]

    # ── ESTADO DE VENTA: mergear lo de este turno con la memoria y persistir ──
    # Los datos deterministas (productos con precio real, carrito, envio) que las
    # tools generaron este turno se suman a los de turnos anteriores, asi el bloque
    # del proximo turno los tiene a la vista. Si este turno no llamo una tool, queda
    # lo que ya habia en memoria.
    productos_vistos = merge_productos(
        conv.get("productos_vistos") or [], productos_de_meta(meta))
    carrito_vigente = carrito_de_meta(meta) or (conv.get("carrito_vigente") or [])
    ultima_localidad = envio_de_meta(meta) or (conv.get("ultima_localidad") or "")

    latency_ms = int((time.time() - t0) * 1000)
    try:
        save_conversation(user_id, history, conv.get("summary", ""),
                          tienda_id=tienda_id,
                          estado_conversacion=estado_nuevo,
                          ultimo_presupuesto=presupuesto,
                          proofs_recientes=proofs_recientes,
                          productos_vistos=productos_vistos,
                          carrito_vigente=carrito_vigente,
                          ultima_localidad=ultima_localidad,
                          datos_cliente_parciales=datos_acumulados)
    except Exception as e:
        log.warning("interprete_libre_save_failed", trace_id=trace_id,
                    error=str(e)[:120])
    try:
        log_message(user_id, raw_message, respuesta_final,
                    meta.get("tools_called", []),
                    latency_ms, trace_id, tienda_id=tienda_id)
    except Exception as e:
        log.warning("interprete_libre_log_failed", trace_id=trace_id,
                    error=str(e)[:120])

    log.info("interprete_libre_ok", trace_id=trace_id, ms=latency_ms)
    return respuesta_final
