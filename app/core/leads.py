"""
LEADS - captura automatica de leads de venta, modo hibrido dos niveles.

Detecta dos tipos de intencion.

Intencion FUERTE, el cliente ya decidio. Frases como lo quiero, lo llevo,
dale cerrado. El bot pide nombre y telefono y avisa al dueno con prioridad.

Intencion TIBIA, el cliente esta evaluando. Frases como hacen envios,
como pago, tienen stock. El bot sigue conversando normal, el dueno recibe
aviso informativo en silencio.

"""
import os
import re
import time
from google.cloud import firestore
from app.config import get_settings
from app.logger import get_logger
from app.storage.firestore_client import _tienda_ref
from app.core.notificador import notificar_lead

log = get_logger(__name__)
settings = get_settings()


LEAD_VENTANA_SEGUNDOS = 24 * 60 * 60

UMBRAL_LEAD_FUERTE = float(os.getenv("INTERPRETER_UMBRAL_ALTA", "0.85"))

# UN SOLO JUEZ: la decision de cierre la toma el interpretador (decision_compra
# con confianza alta). Se borraron los dos jueces que se pisaban con el: el regex
# de "pedir link" (_RE_PIDE_LINK) y el detector legacy por palabras
# (detectar_intencion). Cuando el interprete ve interes pero NO una decision
# confirmada y recien se mostro un precio, el bot hace UNA pregunta suave de
# cierre; un "si" a esa pregunta vuelve como decision_compra y cierra. Asi todo
# conflicto cae en la pregunta, no en un juez paralelo.
PREGUNTA_CIERRE = "¿Seguimos adelante con tu pedido así te lo dejo preparado?"

# Respuesta cuando el cliente dice que no a la pregunta de cierre: se cierra suave
# y lo toma un humano, sin insistir (arreglo D).
MENSAJE_NO_INTERESADO = (
    "Perfecto, sin problema. Cuando quieras retomar, acá estoy. "
    "Igual le paso el dato a una persona del equipo por si te puede dar una mano."
)

RE_TELEFONO = re.compile(
    r"(?:\+?54\s?9?\s?)?(?:11|2\d{2}|3\d{2})\s?\d{3,4}\s?\d{4}"
)
RE_TELEFONO_GENERICO = re.compile(r"\b\d{8,13}\b")


# SWITCH DE VERSION DEL BOT (A/B), un solo lugar para prenderla. Las dos versiones
# del producto se eligen con una config simple: "A" o "B" (o los nombres largos).
#   Version A = lead fuerte: el bot capta el interes y avisa, cierra un humano.
#   Version B = venta: el bot cierra la venta y manda el cobro (link o CBU).
# Los nombres internos (lead/venta/off) siguen valiendo para no romper lo que andaba.
_ALIAS_MODO = {
    "a": "lead", "version_a": "lead", "opcion_a": "lead", "lead": "lead",
    "b": "venta", "version_b": "venta", "opcion_b": "venta", "venta": "venta",
    "off": "off",
}


def _normalizar_modo(v: str) -> str:
    """Traduce el valor de config al modo interno: acepta 'A'/'B' (el switch de
    version) o los nombres largos. '' si el valor no se reconoce, para que el
    llamador caiga al default sin inventar un modo."""
    clave = (v or "").strip().lower().replace(" ", "_")
    return _ALIAS_MODO.get(clave, "")


def modo_cierre(tienda_id: str) -> str:
    """Modalidad del cierre para la tienda. La config por tienda en Firestore
    ('modo_cierre') pisa el default de config.py. Se setea con el switch de version:
      A o 'lead'  = version A: capta el lead y avisa al usuario, cierra un humano.
      B o 'venta' = version B: el bot cierra y manda el cobro (link de Mercado Pago
                    o CBU segun la forma de pago).
      off         = el cierre no actua; el bot vende igual, sin captar lead."""
    try:
        from app.storage.firestore_client import get_config
        v = get_config("modo_cierre", tienda_id=tienda_id)
        m = _normalizar_modo(v)
        if m:
            return m
    except Exception as e:
        log.warning("modo_cierre_read_error", error=str(e)[:100])
    return _normalizar_modo(settings.MODO_CIERRE) or settings.MODO_CIERRE


def extraer_telefono(texto: str) -> str:
    if not texto:
        return ""
    match = RE_TELEFONO.search(texto)
    if match:
        return re.sub(r"\D", "", match.group(0))
    match = RE_TELEFONO_GENERICO.search(texto)
    if match:
        return match.group(0)
    return ""


def extraer_nombre(texto: str) -> str:
    if not texto:
        return ""
    patrones = [
        r"soy\s+([A-Z\u00c1\u00c9\u00cd\u00d3\u00da\u00d1][a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]+(?:\s+[A-Z\u00c1\u00c9\u00cd\u00d3\u00da\u00d1][a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]+)?)",
        r"me llamo\s+([A-Z\u00c1\u00c9\u00cd\u00d3\u00da\u00d1][a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]+(?:\s+[A-Z\u00c1\u00c9\u00cd\u00d3\u00da\u00d1][a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]+)?)",
        r"mi nombre es\s+([A-Z\u00c1\u00c9\u00cd\u00d3\u00da\u00d1][a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]+(?:\s+[A-Z\u00c1\u00c9\u00cd\u00d3\u00da\u00d1][a-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]+)?)",
    ]
    for pat in patrones:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            return m.group(1).strip().title()
    return ""


def get_lead_activo(user_id: str, canal: str, tienda_id: str) -> dict | None:
    try:
        leads_ref = _tienda_ref(tienda_id).collection("leads")
        cutoff_ts = time.time() - LEAD_VENTANA_SEGUNDOS
        query = (leads_ref
                 .where(filter=firestore.FieldFilter("user_id", "==", user_id))
                 .where(filter=firestore.FieldFilter("canal", "==", canal))
                 .order_by("creado_en_ts", direction=firestore.Query.DESCENDING)
                 .limit(1))
        docs = list(query.stream())
        if not docs:
            return None
        data = docs[0].to_dict()
        data["lead_id"] = docs[0].id
        if data.get("creado_en_ts", 0) < cutoff_ts:
            return None
        # Un lead descartado (por "nueva compra") o ya cerrado no se reusa: si no,
        # un pedido viejo se completa con datos de una compra nueva (visto en prod
        # 16-jun: cierre con "javier rojas" y 2 gabinetes sobre una compra de RAM).
        if data.get("estado") in ("descartado", "cerrado", "completado"):
            return None
        return data
    except Exception as e:
        log.warning("lead_query_failed", error=str(e)[:500])
        return None


def descartar_leads_activos(user_id: str, canal: str, tienda_id: str) -> int:
    """Marca como 'descartado' los leads recientes del usuario en este canal.
    Lo usa "nueva compra": sin esto, un lead viejo a medio llenar sobrevive al
    reset de la conversacion y se completa con la direccion nueva, mezclando
    nombre, pedido y pago de otra compra. Devuelve cuantos descarto."""
    try:
        leads_ref = _tienda_ref(tienda_id).collection("leads")
        cutoff_ts = time.time() - LEAD_VENTANA_SEGUNDOS
        query = (leads_ref
                 .where(filter=firestore.FieldFilter("user_id", "==", user_id))
                 .where(filter=firestore.FieldFilter("canal", "==", canal))
                 .order_by("creado_en_ts", direction=firestore.Query.DESCENDING)
                 .limit(10))
        n = 0
        for doc in query.stream():
            d = doc.to_dict()
            if d.get("creado_en_ts", 0) < cutoff_ts:
                break
            if d.get("estado") in ("descartado", "cerrado", "completado"):
                continue
            doc.reference.update({"estado": "descartado",
                                  "actualizado_en": firestore.SERVER_TIMESTAMP})
            n += 1
        return n
    except Exception as e:
        log.warning("descartar_leads_failed", error=str(e)[:300])
        return 0


def crear_lead(user_id: str, canal: str, tienda_id: str,
               ultimo_mensaje: str, frase_disparadora: str,
               nivel: str,
               estado_inicial: str,
               orden: str = "") -> str:
    leads_ref = _tienda_ref(tienda_id).collection("leads")
    doc_ref = leads_ref.document()
    doc_ref.set({
        "tienda_id": tienda_id,
        "canal": canal,
        "user_id": user_id,
        "nombre": "",
        "telefono": "",
        "direccion": "",
        "forma_pago": "",
        "orden": orden[:1500],
        "estado": estado_inicial,
        "nivel": nivel,
        "ultimo_mensaje": ultimo_mensaje[:500],
        "frase_disparadora": frase_disparadora,
        "creado_en": firestore.SERVER_TIMESTAMP,
        "creado_en_ts": time.time(),
        "actualizado_en": firestore.SERVER_TIMESTAMP,
    })
    log.info("lead_created", lead_id=doc_ref.id, tienda_id=tienda_id,
             user_id=user_id, canal=canal, nivel=nivel,
             estado=estado_inicial)
    return doc_ref.id


def actualizar_lead(lead_id: str, tienda_id: str, cambios: dict):
    cambios["actualizado_en"] = firestore.SERVER_TIMESTAMP
    _tienda_ref(tienda_id).collection("leads").document(lead_id).update(cambios)


async def _finalizar_cierre(lead_id: str, merged: dict, tienda_id: str,
                            user_id: str, canal: str, mensaje: str,
                            presupuesto: str, trace_id: str,
                            modo: str = "venta") -> dict:
    """Cierra la venta con un lead que ya tiene los cuatro datos: avisa al
    dueño, arma la confirmacion y, SOLO en modo 'venta', agrega el link de pago
    real. Devuelve el meta con accion lead_capturado. Mismo camino que el
    cierre normal (Caso uno), reusado cuando el mensaje disparador ya trajo
    todo."""
    log.info("lead_capturado_completo", lead_id=lead_id, tienda_id=tienda_id,
             user_id=user_id, trace_id=trace_id)
    try:
        await notificar_lead(
            tienda_id=tienda_id, user_id=user_id, canal=canal,
            estado="capturado", nombre=merged.get("nombre", ""),
            telefono=merged.get("telefono", ""),
            direccion=merged.get("direccion", ""),
            forma_pago=merged.get("forma_pago", ""),
            orden=merged.get("orden", ""), ultimo_mensaje=mensaje,
        )
    except Exception as e:
        log.warning("notificar_lead_failed", error=str(e)[:120])
    from app.core import cierre
    respuesta_cierre = cierre.mensaje_confirmacion(
        merged, merged.get("orden", ""))
    # Link de pago SOLO en modo 'venta': total verificado de la calculadora. En
    # modo 'lead' cierra avisando al usuario, sin link. Si no hay total unico o
    # falta el token de Mercado Pago, cierra igual sin link.
    if modo == "venta":
        try:
            from app.core.pago import instruccion_cobro
            cobro = await instruccion_cobro(
                presupuesto or merged.get("orden", ""), merged, tienda_id, trace_id)
            if cobro:
                respuesta_cierre += "\n" + cobro
        except Exception as e:
            log.warning("cobro_error", trace_id=trace_id, error=str(e)[:160])
    return {"accion": "lead_capturado", "lead_id": lead_id,
            "respuesta_directa": respuesta_cierre}


def _contacto_del_canal(user_id: str, canal: str) -> str:
    """En WhatsApp/Telegram el contacto del cliente ES el id del canal: su numero
    de WhatsApp o su chat de Telegram. El cliente NO tipea su telefono, asi que
    exigirselo lo manda a un loop de 'me falta un telefono' que nunca completa,
    aunque ya haya dado nombre y direccion. Se usa el user_id como contacto."""
    return (user_id or "").strip()


async def procesar_mensaje_para_lead(
    user_id: str,
    canal: str,
    tienda_id: str,
    mensaje: str,
    respuesta_solver: str,
    trace_id: str,
    interpretacion: dict | None = None,
    presupuesto: str = "",
    datos_turno: dict | None = None,
    datos_previos: dict | None = None,
    presupuesto_nuevo: bool = False,
    pregunta_cierre_hecha: bool = False,
) -> tuple[str | None, dict]:
    """
    Logica del cierre (aditivo). Juez UNICO: el interpretador.

    Caso uno, hay lead esperando datos, completamos y cerramos.
    Caso dos, decision de compra confirmada (interpretador), captamos el lead.
    Caso tres, hay interes y recien se mostro un precio: una pregunta suave de
        cierre. Un "si" vuelve como decision_compra y cae en el Caso dos.
    Caso cuatro, nada que hacer.

    El modo de la tienda manda: 'off' no actua, 'lead' capta sin link, 'venta'
    capta y manda el link de Mercado Pago.
    """
    meta = {"accion": "ninguna"}
    modo = modo_cierre(tienda_id)
    if modo == "off":
        return None, meta
    lead_activo = get_lead_activo(user_id, canal, tienda_id)

    # Caso uno, lead activo esperando datos
    if lead_activo and lead_activo.get("estado") == "datos_solicitados":
        from app.core import cierre
        # Si el cliente PIVOTEA a una pregunta nueva (precio, info de producto) en
        # vez de aportar datos, hay que CONTESTARLE, no seguir empujando el cierre
        # ni extraer datos de una consulta. Ej: "cuanto sale el X con envio a
        # Cordoba" no es un domicilio, es una cotizacion. El cierre se retoma
        # cuando el cliente realmente aporta datos o confirma.
        _intent = (interpretacion or {}).get("intencion")
        if _intent in ("pregunta_especifica", "exploracion") and \
                not extraer_telefono(mensaje):
            log.info("cierre_pausado_pregunta_nueva", trace_id=trace_id,
                     intencion=_intent)
            return None, {"accion": "ninguna"}
        datos = dict(datos_turno or {})
        cambios = {k: v for k, v in datos.items() if v}
        if not cambios:
            # El cliente no aporto ningun dato este turno, lo dejamos al Solver.
            return None, {"accion": "ninguna"}
        # Datos acumulados de turnos anteriores: se guardan junto con los de este
        # turno, asi el lead queda completo y no se re-pregunta lo ya dicho.
        prev = {k: v for k, v in (datos_previos or {}).items()
                if v and k in cierre.CAMPOS_REQUERIDOS}
        cambios = {**prev, **cambios}
        cambios["ultimo_mensaje"] = mensaje[:500]
        # El telefono es el contacto del canal, no un dato que el cliente tipea.
        if not str(lead_activo.get("telefono", "")).strip():
            cambios.setdefault("telefono", _contacto_del_canal(user_id, canal))
        merged = {**lead_activo, **cambios}
        falt = cierre.faltantes(merged)
        if falt:
            actualizar_lead(lead_activo["lead_id"], tienda_id, cambios)
            log.info("lead_pidiendo_datos", lead_id=lead_activo["lead_id"],
                     faltan=falt, trace_id=trace_id)
            return None, {"accion": "pidiendo_datos",
                          "lead_id": lead_activo["lead_id"],
                          "respuesta_directa": cierre.mensaje_pedir_datos(falt)}
        cambios["estado"] = "capturado"
        actualizar_lead(lead_activo["lead_id"], tienda_id, cambios)
        log.info("lead_capturado_completo", lead_id=lead_activo["lead_id"],
                 tienda_id=tienda_id, user_id=user_id, trace_id=trace_id)
        try:
            await notificar_lead(
                tienda_id=tienda_id, user_id=user_id, canal=canal,
                estado="capturado", nombre=merged.get("nombre", ""),
                telefono=merged.get("telefono", ""),
                direccion=merged.get("direccion", ""),
                forma_pago=merged.get("forma_pago", ""),
                orden=merged.get("orden", ""), ultimo_mensaje=mensaje,
            )
        except Exception as e:
            log.warning("notificar_lead_failed", error=str(e)[:120])
        respuesta_cierre = cierre.mensaje_confirmacion(
            merged, merged.get("orden", ""))
        # Link de pago SOLO en modo 'venta': total verificado de la calculadora.
        # En modo 'lead' cierra avisando al usuario, sin link. Si no hay total
        # unico o falta el token de Mercado Pago, la venta cierra igual sin link.
        if modo == "venta":
            try:
                from app.core.pago import instruccion_cobro
                merged["lead_id"] = lead_activo["lead_id"]
                cobro = await instruccion_cobro(
                    presupuesto or merged.get("orden", ""), merged,
                    tienda_id, trace_id)
                if cobro:
                    respuesta_cierre += "\n" + cobro
            except Exception as e:
                log.warning("cobro_error", trace_id=trace_id,
                            error=str(e)[:160])
        return None, {
            "accion": "lead_capturado",
            "lead_id": lead_activo["lead_id"],
            "respuesta_directa": respuesta_cierre,
        }

    # JUEZ UNICO: el interpretador. Dispara fuerte SOLO con decision_compra
    # confirmada y confianza alta. No hay jueces paralelos (se borraron el regex
    # de link y el detector legacy por palabras).
    intencion_llm = (interpretacion or {}).get("intencion")
    confianza_llm = (interpretacion or {}).get("confianza", 0.0)
    if intencion_llm == "decision_compra" and confianza_llm >= UMBRAL_LEAD_FUERTE:
        nivel = "fuerte"
        frase = f"interpretador_decision_compra_{confianza_llm:.2f}"
    else:
        nivel = "ninguna"
        frase = ""
    log.info("lead_decision_via_interpretador", trace_id=trace_id,
             intencion_llm=intencion_llm, confianza_llm=confianza_llm,
             nivel_mapeado=nivel)

    # GATILLO DETERMINISTA DE CIERRE (arreglo D). Si el turno PASADO se hizo la
    # pregunta de cierre, la respuesta del cliente decide sin depender de la
    # confianza del LLM: un no lo toma un humano y cerramos suave; cualquier otra
    # respuesta dispara el lead fuerte. Es el gatillo acordado: una sola pregunta,
    # y con la respuesta ya hay decision.
    if pregunta_cierre_hecha and nivel != "fuerte":
        from app.core import cierre as _cierre
        if _cierre.es_no_interesado(mensaje):
            log.info("cierre_respuesta_no_interesado", trace_id=trace_id)
            try:
                await notificar_lead(
                    tienda_id=tienda_id, user_id=user_id, canal=canal,
                    estado="intencion_tibia", nombre="", telefono="",
                    ultimo_mensaje=mensaje)
            except Exception as e:
                log.warning("notificar_lead_failed", error=str(e)[:120])
            return None, {"accion": "no_interesado",
                          "respuesta_directa": MENSAJE_NO_INTERESADO}
        # El cliente PREGUNTA o DUDA en vez de confirmar (ej "estas seguro que el
        # envio llega a Santa Ana?"): NO se cierra. El solver le contesta la duda y
        # la oferta de cierre sigue PENDIENTE para el proximo turno. Sin esto el bot
        # se apura y salta a pedir datos sobre una pregunta (apuro visto 1-jul).
        if (_cierre.parece_pregunta(mensaje)
                or intencion_llm in ("pregunta_especifica", "exploracion", "posventa")):
            log.info("cierre_gatillo_pausado_pregunta", trace_id=trace_id,
                     intencion_llm=intencion_llm)
            return None, {"accion": "pregunta_pendiente_cierre"}
        nivel = "fuerte"
        frase = "respuesta_afirmativa_pregunta_cierre"
        log.info("cierre_gatillo_determinista_fuerte", trace_id=trace_id)

    # Caso tres, PREGUNTA SUAVE DE CIERRE. Cuando NO hay decision confirmada pero
    # recien se mostro un precio nuevo y el interprete ve interes (no exploracion
    # ni posventa), el bot suma una pregunta suave a la respuesta del Solver. Es
    # la red ante la duda: un "si" en el turno siguiente vuelve como
    # decision_compra y cae en el Caso dos. Solo cuando hay presupuesto NUEVO,
    # asi no se repite turno a turno.
    if (nivel == "ninguna" and presupuesto_nuevo
            and intencion_llm in ("pregunta_especifica", "aporta_dato",
                                  "decision_compra")):
        log.info("cierre_pregunta_suave", trace_id=trace_id,
                 intencion_llm=intencion_llm, confianza_llm=confianza_llm)
        base = (respuesta_solver or "").rstrip()
        pregunta = (base + "\n\n" + PREGUNTA_CIERRE) if base else PREGUNTA_CIERRE
        return None, {"accion": "pregunta_cierre",
                      "respuesta_directa": pregunta}

    # Caso dos, intencion fuerte
    if nivel == "fuerte":
        # Regla de orden: no cerrar sin precio mostrado. Si todavia no hay
        # presupuesto, registramos el interes en silencio y dejamos que el
        # Solver responda el precio. El cierre queda para el turno siguiente.
        if not str(presupuesto).strip():
            lead_id = crear_lead(
                user_id=user_id, canal=canal, tienda_id=tienda_id,
                ultimo_mensaje=mensaje, frase_disparadora=frase,
                nivel="tibia", estado_inicial="intencion_tibia",
            )
            log.info("intencion_fuerte_sin_precio", lead_id=lead_id,
                     tienda_id=tienda_id, user_id=user_id,
                     frase=frase, trace_id=trace_id)
            try:
                await notificar_lead(
                    tienda_id=tienda_id, user_id=user_id, canal=canal,
                    estado="intencion_tibia", nombre="", telefono="",
                    ultimo_mensaje=mensaje,
                )
            except Exception as e:
                log.warning("notificar_lead_failed", error=str(e)[:120])
            return None, {"accion": "tibia_registrada", "lead_id": lead_id}
        lead_id = crear_lead(
            user_id=user_id, canal=canal, tienda_id=tienda_id,
            ultimo_mensaje=mensaje, frase_disparadora=frase,
            nivel="fuerte", estado_inicial="datos_solicitados",
            orden=presupuesto,
        )
        log.info("intencion_fuerte_detectada", lead_id=lead_id,
                 tienda_id=tienda_id, user_id=user_id,
                 frase=frase, trace_id=trace_id)

        # Siembra inicial (unico camino, sin flag): el mensaje que dispara el
        # cierre suele traer datos ya ("envio a Los Condores medio de pago
        # mercado pago"). Sin esto se piden de cero y el cliente repite lo que ya
        # dijo. Se siembra el lead con lo presente; si estan los cuatro, cierra
        # ya; si falta algo, pide SOLO lo que falta.
        from app.core import cierre
        # Siembra con TODO lo acumulado en turnos anteriores mas lo de este turno,
        # asi una direccion o un pago dados ANTES de la decision de compra ya estan
        # y no se vuelven a pedir.
        prev = {k: v for k, v in (datos_previos or {}).items()
                if v and k in cierre.CAMPOS_REQUERIDOS}
        sembrados = {**prev, **{k: v for k, v in (datos_turno or {}).items() if v}}
        # El telefono es el contacto del canal: se siembra siempre, asi el cierre
        # no lo pide aparte (ver _contacto_del_canal).
        sembrados.setdefault("telefono", _contacto_del_canal(user_id, canal))
        if sembrados:
            actualizar_lead(lead_id, tienda_id, sembrados)
            merged = {"orden": presupuesto, "lead_id": lead_id, **sembrados}
            falt = cierre.faltantes(merged)
            log.info("cierre_siembra_inicial", lead_id=lead_id,
                     sembrados=list(sembrados.keys()), faltan=falt,
                     trace_id=trace_id)
            if not falt:
                actualizar_lead(lead_id, tienda_id, {"estado": "capturado"})
                return None, await _finalizar_cierre(
                    lead_id, merged, tienda_id, user_id, canal,
                    mensaje, presupuesto, trace_id, modo=modo)
            try:
                await notificar_lead(
                    tienda_id=tienda_id, user_id=user_id, canal=canal,
                    estado="intencion_fuerte",
                    nombre=sembrados.get("nombre", ""),
                    telefono=sembrados.get("telefono", ""),
                    ultimo_mensaje=mensaje)
            except Exception as e:
                log.warning("notificar_lead_failed", error=str(e)[:120])
            return None, {"accion": "pidiendo_datos", "lead_id": lead_id,
                          "respuesta_directa": cierre.mensaje_pedir_datos(falt)}
        try:
            await notificar_lead(
                tienda_id=tienda_id, user_id=user_id, canal=canal,
                estado="intencion_fuerte", nombre="", telefono="",
                ultimo_mensaje=mensaje,
            )
        except Exception as e:
            log.warning("notificar_lead_failed", error=str(e)[:120])
        meta["accion"] = "handoff_humano"
        meta["lead_id"] = lead_id
        meta["respuesta_directa"] = (
            "Buenisimo, gracias por la decision. En un momento te contacta "
            "una persona del equipo para coordinar tu compra. Para que pueda "
            "hablarte directo, pasame por favor tu nombre y un telefono "
            "donde ubicarte."
        )
        return None, meta

    return None, {"accion": "ninguna"}
