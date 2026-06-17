"""
LEADS - captura automatica de leads de venta, modo hibrido dos niveles.

Detecta dos tipos de intencion.

Intencion FUERTE, el cliente ya decidio. Frases como lo quiero, lo llevo,
dale cerrado. El bot pide nombre y telefono y avisa al dueno con prioridad.

Intencion TIBIA, el cliente esta evaluando. Frases como hacen envios,
como pago, tienen stock. El bot sigue conversando normal, el dueno recibe
aviso informativo en silencio.

Feature flag: USE_LEADS=true para activarlo. False por default.
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

USE_LEADS = os.getenv("USE_LEADS", "false").lower() == "true"

LEAD_VENTANA_SEGUNDOS = 24 * 60 * 60

UMBRAL_LEAD_FUERTE = float(os.getenv("INTERPRETER_UMBRAL_ALTA", "0.85"))

# Pedido explicito del link de pago: señal de cierre determinista (con
# CIERRE_CONTRATO). Misma familia de patrones que el handoff del orchestrator.
_RE_PIDE_LINK = re.compile(
    r"(?i)\blink\b|mercado\s*pago|\bmp\b|donde\s+pago|como\s+pago")
UMBRAL_LEAD_TIBIA = float(os.getenv("INTERPRETER_UMBRAL_BAJA", "0.6"))

# Intencion FUERTE, el cliente ya decidio comprar
PALABRAS_INTENCION_FUERTE = [
    "lo quiero", "la quiero", "los quiero", "las quiero",
    "lo llevo", "la llevo", "los llevo", "las llevo",
    "me lo guardas", "me la guardas", "me lo reservas", "me la reservas",
    "lo voy a llevar", "la voy a llevar",
    "ok cerrado", "cerramos", "dale cerrado", "dale lo llevo",
    "pasame el link", "mandame el link",
    "como hago para comprar", "como hago para llevarlo",
    "lo compro", "la compro",
]

# Intencion TIBIA, el cliente esta evaluando, pregunta previa a comprar
PALABRAS_INTENCION_TIBIA = [
    "hacen envio", "hacen envios", "mandan a", "mandas a",
    "cuanto sale el envio", "cuanto cuesta el envio",
    "tenes stock", "hay stock", "tienen stock",
    "como pago", "como compro", "donde pago", "donde compro",
    "lo necesito", "la necesito",
    "me sirve", "me conviene",
    "que medios de pago",
    "aceptan tarjeta", "aceptan transferencia",
]

RE_TELEFONO = re.compile(
    r"(?:\+?54\s?9?\s?)?(?:11|2\d{2}|3\d{2})\s?\d{3,4}\s?\d{4}"
)
RE_TELEFONO_GENERICO = re.compile(r"\b\d{8,13}\b")


def detectar_intencion(mensaje: str) -> tuple[str, str]:
    """
    Devuelve tupla con nivel y frase disparadora.
    Nivel puede ser fuerte, tibia o ninguna.
    """
    if not mensaje:
        return "ninguna", ""
    msg_lower = mensaje.lower()
    for frase in PALABRAS_INTENCION_FUERTE:
        if frase in msg_lower:
            return "fuerte", frase
    for frase in PALABRAS_INTENCION_TIBIA:
        if frase in msg_lower:
            return "tibia", frase
    return "ninguna", ""


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
                            presupuesto: str, trace_id: str) -> dict:
    """Cierra la venta con un lead que ya tiene los cuatro datos: avisa al
    dueño, arma la confirmacion y, si hay total unico, agrega el link de pago
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
    if settings.LINK_PAGO:
        try:
            from app.core.pago import link_pago_para_lead
            _url = await link_pago_para_lead(
                presupuesto or merged.get("orden", ""), merged,
                tienda_id, trace_id)
            if _url:
                respuesta_cierre += f"\nPodes pagar aca: {_url}"
        except Exception as e:
            log.warning("link_pago_error", trace_id=trace_id, error=str(e)[:160])
    return {"accion": "lead_capturado", "lead_id": lead_id,
            "respuesta_directa": respuesta_cierre}


async def procesar_mensaje_para_lead(
    user_id: str,
    canal: str,
    tienda_id: str,
    mensaje: str,
    respuesta_solver: str,
    trace_id: str,
    interpretacion: dict | None = None,
    presupuesto: str = "",
) -> tuple[str | None, dict]:
    """
    Logica principal hibrida.

    Caso uno, hay lead esperando datos, intentamos extraer nombre y telefono.
    Caso dos, hay intencion fuerte, pedimos datos y notificamos prioritario.
    Caso tres, hay intencion tibia, solo registramos y notificamos silencioso.
    Caso cuatro, sin intencion ni lead activo, no hacemos nada.
    """
    meta = {"accion": "ninguna"}
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
        datos = cierre.extraer_datos_cliente(mensaje, trace_id)
        cambios = {k: v for k, v in datos.items() if v}
        if not cambios:
            # El cliente no aporto ningun dato, lo dejamos al Solver.
            return None, {"accion": "ninguna"}
        cambios["ultimo_mensaje"] = mensaje[:500]
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
        # Link de pago (flag LINK_PAGO): generado por CODIGO desde el total
        # verificado del presupuesto. Si no hay total unico o falta el token de
        # Mercado Pago, la venta cierra igual sin link.
        if settings.LINK_PAGO:
            try:
                from app.core.pago import link_pago_para_lead
                merged["lead_id"] = lead_activo["lead_id"]
                _url = await link_pago_para_lead(
                    presupuesto or merged.get("orden", ""), merged,
                    tienda_id, trace_id)
                if _url:
                    respuesta_cierre += f"\nPodes pagar aca: {_url}"
            except Exception as e:
                log.warning("link_pago_error", trace_id=trace_id,
                            error=str(e)[:160])
        return None, {
            "accion": "lead_capturado",
            "lead_id": lead_activo["lead_id"],
            "respuesta_directa": respuesta_cierre,
        }

    # Interpretador como unica fuente de verdad.
    # Solo dispara fuerte con decision_compra confirmada y confianza alta.
    # Solo dispara tibia con pregunta_especifica mas producto resuelto.
    # Fallback al detector legacy solo si no hay interpretacion.
    if interpretacion and interpretacion.get("intencion"):
        intencion_llm = interpretacion.get("intencion")
        confianza_llm = interpretacion.get("confianza", 0.0)
        if intencion_llm == "decision_compra" and confianza_llm >= UMBRAL_LEAD_FUERTE:
            nivel = "fuerte"
            frase = f"interpretador_decision_compra_{confianza_llm:.2f}"
        elif (settings.CIERRE_CONTRATO
              and _RE_PIDE_LINK.search(mensaje or "")
              and str(presupuesto).strip()):
            # Pedir el link de pago ES decision de compra, la marque o no el
            # interpretador (visto 12-jun: "ok enviame link" quedo en
            # pregunta_especifica, nadie creo el lead y el Solver PROMETIO un
            # link que ningun engranaje iba a mandar). Determinista: con
            # presupuesto mostrado, pedir el link dispara el cierre por codigo.
            nivel = "fuerte"
            frase = "pide_link_pago"
        else:
            nivel = "ninguna"
            frase = ""
        log.info("lead_decision_via_interpretador", trace_id=trace_id,
                 intencion_llm=intencion_llm, confianza_llm=confianza_llm,
                 nivel_mapeado=nivel)
    else:
        nivel, frase = detectar_intencion(mensaje)
        log.info("lead_decision_via_legacy", trace_id=trace_id, nivel=nivel)

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

        # CIERRE_SIEMBRA_INICIAL: el mensaje que dispara el cierre suele traer
        # datos ya ("envio a Los Condores medio de pago mercado pago"). Sin
        # esto se piden de cero y el cliente repite lo que ya dijo (visto en
        # prod 13-jun WhatsApp: forma de pago dicha junto al envio, ignorada,
        # el cliente tuvo que escribir "Mercado pago" de nuevo al final). Se
        # siembra el lead con lo presente; si estan los cuatro, cierra ya; si
        # falta algo, pide SOLO lo que falta.
        if settings.CIERRE_SIEMBRA_INICIAL:
            from app.core import cierre
            sembrados = {k: v for k, v in
                         cierre.extraer_datos_cliente(mensaje, trace_id).items()
                         if v}
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
                        mensaje, presupuesto, trace_id)
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
        if frase == "pide_link_pago":
            # El cliente pidio el link: la respuesta lo reconoce y el codigo
            # lo manda al completarse los datos (LINK_PAGO), sin promesas
            # del Solver.
            meta["respuesta_directa"] = (
                "Dale, te genero el link de pago apenas me pases tu nombre, "
                "un telefono de contacto y la direccion de envio. Pasamelos "
                "y te lo mando al toque."
            )
        else:
            meta["respuesta_directa"] = (
                "Buenisimo, gracias por la decision. En un momento te contacta "
                "una persona del equipo para coordinar tu compra. Para que pueda "
                "hablarte directo, pasame por favor tu nombre y un telefono "
                "donde ubicarte."
            )
        return None, meta

    # Caso tres, intencion tibia
    if nivel == "tibia":
        lead_id = crear_lead(
            user_id=user_id, canal=canal, tienda_id=tienda_id,
            ultimo_mensaje=mensaje, frase_disparadora=frase,
            nivel="tibia", estado_inicial="intencion_tibia",
        )
        log.info("intencion_tibia_detectada", lead_id=lead_id,
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
        meta["accion"] = "tibia_registrada"
        meta["lead_id"] = lead_id
        return None, meta

    return None, {"accion": "ninguna"}
