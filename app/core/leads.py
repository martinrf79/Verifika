"""LEADS - captura automatica de leads de venta, modo hibrido dos niveles."""
import os
import re
import time
from google.cloud import firestore
from app.config import get_settings
from app.logger import get_logger
from app.storage.firestore_client import _tienda_ref
from app.core.notificador import notificar_lead
from app.core.guia_venta_prosa import mensaje as _msj

log = get_logger(__name__)
settings = get_settings()


LEAD_VENTANA_SEGUNDOS = 24 * 60 * 60

UMBRAL_LEAD_FUERTE = float(os.getenv("INTERPRETER_UMBRAL_ALTA", "0.85"))

# UN SOLO JUEZ: la decision de cierre la toma el interpretador (decision_compra con confianza alta).
def _pregunta_cierre() -> str:
    from app.core.guia_venta_prosa import mensaje
    return mensaje("cierre_pregunta_seguimos",
                   "¿Seguimos adelante con tu pedido así te lo dejo preparado?")


PREGUNTA_CIERRE = _pregunta_cierre()

# EL TEXTO YA NO VIVE ACA. Estas tres respuestas las emite el CODIGO cuando el flujo lo decide -el cliente
# dice que no, el pedido ya estaba tomado, se deriva a una persona- y hasta hoy eran constantes sueltas de
# este modulo que salian al cliente sin pasar por ninguna puerta.
MENSAJE_NO_INTERESADO = _msj(
    "no_interesado",
    "Perfecto, sin problema. Cuando quieras retomar, acá estoy. Igual le paso "
    "el dato a una persona del equipo por si te puede dar una mano.")
MENSAJE_PEDIDO_YA_TOMADO = _msj(
    "pedido_ya_tomado",
    "Tu pedido ya quedó tomado. Una persona del equipo te contacta a la "
    "brevedad para coordinar el pago y el envío. ¿Te ayudo con algo más?")
MENSAJE_HANDOFF_HUMANO = _msj(
    "handoff_humano",
    "Buenísimo, gracias por la decisión. En un momento te contacta una persona "
    "del equipo para cerrar el pago y el envío.")

# El cliente pide explicitamente el link o los datos para pagar.
_RE_PIDE_COBRO = re.compile(
    r"(?i)\b(?:pasa(?:me)?|manda(?:me)?|dame|envia(?:me)?|necesito|quiero)\b"
    r"[^.\n]{0,40}\b(?:links?|enlaces?|cbu|alias)\b"
    r"|\b(?:links?|enlaces?)\s+de\s+pago"
    r"|\bdatos\s+(?:para|de)\s+(?:pagar|pago|transferir|transferencia)"
    r"|\bcu[aá]l\s+es\s+el\s+(?:cbu|alias|link)\b")

RE_TELEFONO = re.compile(
    r"(?:\+?54\s?9?\s?)?(?:11|2\d{2}|3\d{2})\s?\d{3,4}\s?\d{4}"
)
RE_TELEFONO_GENERICO = re.compile(r"\b\d{8,13}\b")


# SWITCH DE VERSION DEL BOT (A/B), un solo lugar para prenderla.
_ALIAS_MODO = {
    "a": "lead", "version_a": "lead", "opcion_a": "lead", "lead": "lead",
    "b": "venta", "version_b": "venta", "opcion_b": "venta", "venta": "venta",
    "off": "off",
}


def _normalizar_modo(v: str) -> str:
    """Traduce el valor de config al modo interno: acepta 'A'/'B' (el switch de version) o los nombres largos."""
    clave = (v or "").strip().lower().replace(" ", "_")
    return _ALIAS_MODO.get(clave, "")


def _insistencia(lead: dict, falt: list) -> int:
    """Veces que ya se pidieron EXACTAMENTE estos campos en turnos anteriores."""
    previos = list(lead.get("datos_pedidos_campos") or [])
    if previos != list(falt):
        return 0
    try:
        return max(0, int(lead.get("datos_pedidos_veces") or 0))
    except (TypeError, ValueError):
        return 0


def modo_cierre(tienda_id: str) -> str:
    """Modalidad del cierre para la tienda. La config por tienda en Firestore ('modo_cierre') pisa el default de
    config.py."""
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
    """Marca como 'descartado' los leads recientes del usuario en este canal."""
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
    """Cierra la venta con un lead que ya tiene los cuatro datos: avisa al dueño, arma la confirmacion y, SOLO en
    modo 'venta', agrega el link de pago real."""
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
    # Link de pago SOLO en modo 'venta': total verificado de la calculadora.
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
    """En WhatsApp/Telegram el contacto del cliente ES el id del canal: su numero de WhatsApp o su chat de
    Telegram."""
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
    """Logica del cierre (aditivo). Juez UNICO: el interpretador."""
    meta = {"accion": "ninguna"}
    modo = modo_cierre(tienda_id)
    if modo == "off":
        return None, meta
    lead_activo = get_lead_activo(user_id, canal, tienda_id)

    # ENTREGA DE DATOS DE COBRO A PEDIDO (charla real 20-jul: "Pasame los enlaces" devolvia fichas de
    # producto): si el cliente pide el link o el CBU y hay pedido o presupuesto sobre la mesa, el cobro se
    # entrega directo, en cualquier modo.
    if _RE_PIDE_COBRO.search(mensaje or ""):
        _presu_cobro = (presupuesto or "").strip() or str(
            (lead_activo or {}).get("orden") or "")
        if lead_activo or _presu_cobro.strip():
            try:
                from app.core import pago as P
                bloques = []
                # Acá van las DOS vías, así que cada una cobra SU parte cuando hay pago dividido: si las dos
                # mandaran el total, el cliente veria dos veces el importe entero y pagaria el doble.
                t_transf = P.mensaje_transferencia(
                    P.datos_transferencia(tienda_id),
                    P.monto_a_cobrar(_presu_cobro, "cbu"))
                if t_transf:
                    bloques.append(t_transf)
                url = (await P.link_pago_para_lead(
                    _presu_cobro, lead_activo or {}, tienda_id, trace_id)
                    or get_settings().DEMO_LINK_PAGO)
                if url:
                    from app.core.guia_venta_prosa import mensaje
                    bloques.append(mensaje(
                        "pago_titulo_mercadopago",
                        "Para pagar con Mercado Pago: {url}", url=url))
                if bloques:
                    log.info("cobro_datos_a_pedido", trace_id=trace_id)
                    from app.core.guia_venta_prosa import mensaje
                    bloques.append(mensaje(
                        "cierre_duda_pago",
                        "Cualquier duda con el pago, avisame y te ayudo."))
                    return None, {"accion": "cobro_datos",
                                  "respuesta_directa": "\n\n".join(bloques)}
            except Exception as e:
                log.warning("cobro_datos_error", trace_id=trace_id,
                            error=str(e)[:120])

    # Caso uno, lead activo esperando datos
    if lead_activo and lead_activo.get("estado") == "datos_solicitados":
        from app.core import cierre
        # Si el cliente PIVOTEA a una pregunta nueva (precio, info de producto) en vez de aportar datos, hay
        # que CONTESTARLE, no seguir empujando el cierre ni extraer datos de una consulta.
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
                if v and k in cierre.CAMPOS_EXTRAIBLES}
        cambios = {**prev, **cambios}
        cambios["ultimo_mensaje"] = mensaje[:500]
        # El telefono es el contacto del canal, no un dato que el cliente tipea.
        if not str(lead_activo.get("telefono", "")).strip():
            cambios.setdefault("telefono", _contacto_del_canal(user_id, canal))
        merged = {**lead_activo, **cambios}
        falt = cierre.faltantes(merged)
        if falt:
            # Cuantas veces ya se pidieron ESTOS mismos campos.
            insistencia = _insistencia(lead_activo, falt)
            cambios["datos_pedidos_campos"] = list(falt)
            cambios["datos_pedidos_veces"] = insistencia + 1
            actualizar_lead(lead_activo["lead_id"], tienda_id, cambios)
            log.info("lead_pidiendo_datos", lead_id=lead_activo["lead_id"],
                     faltan=falt, insistencia=insistencia, trace_id=trace_id)
            return None, {"accion": "pidiendo_datos",
                          "lead_id": lead_activo["lead_id"],
                          "respuesta_directa": cierre.mensaje_pedir_datos(
                              falt, insistencia)}
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

    # JUEZ UNICO: el interpretador. Dispara fuerte SOLO con decision_compra confirmada y confianza alta.
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

    # GATILLO DETERMINISTA DE CIERRE (arreglo D).
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
        # ATADO AL ENUM (22-jul). El cierre fuerte lo dispara la INTENCION del interprete (decision_compra),
        # NO un heuristico de texto.
        if intencion_llm != "decision_compra" or _cierre.parece_pregunta(mensaje):
            log.info("cierre_gatillo_pausado_pregunta", trace_id=trace_id,
                     intencion_llm=intencion_llm)
            return None, {"accion": "pregunta_pendiente_cierre"}
        nivel = "fuerte"
        frase = "respuesta_afirmativa_pregunta_cierre"
        log.info("cierre_gatillo_determinista_fuerte", trace_id=trace_id)

    # Caso tres, PREGUNTA SUAVE DE CIERRE. Cuando NO hay decision confirmada pero recien se mostro un precio
    # nuevo y el interprete ve interes (no exploracion ni posventa), el bot suma una pregunta suave a la
    # respuesta del Solver.
    hay_presupuesto = bool(str(presupuesto).strip())
    if (nivel == "ninguna"
            and (presupuesto_nuevo
                 or (intencion_llm == "decision_compra" and hay_presupuesto))
            and intencion_llm in ("pregunta_especifica", "aporta_dato",
                                  "decision_compra")):
        # EL CIERRE LO OWNS EL SOLVER (Martin, 23-jul: "encargar por enum al solver").
        log.info("cierre_pregunta_suave", trace_id=trace_id,
                 intencion_llm=intencion_llm, confianza_llm=confianza_llm)
        return None, {"accion": "pregunta_cierre"}

    # Caso dos, intencion fuerte
    if nivel == "fuerte":
        # PRIMER TURNO SIN APURO (Martin, 23-jul + regla 20-jul).
        if not pregunta_cierre_hecha and frase.startswith("interpretador_decision_compra"):
            log.info("cierre_primer_turno_sin_apuro", trace_id=trace_id,
                     frase=frase)
            return None, {"accion": "pregunta_cierre"}
        # Regla de orden: no cerrar sin precio mostrado.
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

        # VERSION A (modo 'lead'): el lead fuerte YA se logra acá.
        if modo == "lead":
            from app.core import cierre
            # Si ya hay un lead fuerte captado activo, no se re-avisa ni se crea
            # otro: el bot solo sigue la charla, sin spamear al dueño.
            if lead_activo and lead_activo.get("nivel") == "fuerte":
                log.info("lead_fuerte_ya_captado", trace_id=trace_id,
                         lead_id=lead_activo.get("lead_id"))
                # Corta el loop del "si" repetido: responde un cierre corto y
                # distinto en vez de dejar que el solver re-mande el presupuesto.
                return None, {"accion": "lead_fuerte_ya_captado",
                              "respuesta_directa": MENSAJE_PEDIDO_YA_TOMADO}
            prev = {k: v for k, v in (datos_previos or {}).items()
                    if v and k in cierre.CAMPOS_EXTRAIBLES}
            sembrados = {**prev, **{k: v for k, v in (datos_turno or {}).items() if v}}
            sembrados.setdefault("telefono", _contacto_del_canal(user_id, canal))
            lead_id = crear_lead(
                user_id=user_id, canal=canal, tienda_id=tienda_id,
                ultimo_mensaje=mensaje, frase_disparadora=frase,
                nivel="fuerte", estado_inicial="capturado",
                orden=presupuesto,
            )
            actualizar_lead(lead_id, tienda_id, sembrados)
            log.info("lead_fuerte_captado_modo_lead", lead_id=lead_id,
                     tienda_id=tienda_id, user_id=user_id, frase=frase,
                     sembrados=list(sembrados.keys()), trace_id=trace_id)
            try:
                await notificar_lead(
                    tienda_id=tienda_id, user_id=user_id, canal=canal,
                    estado="lead_fuerte_captado",
                    nombre=sembrados.get("nombre", ""),
                    telefono=sembrados.get("telefono", ""),
                    direccion=sembrados.get("direccion", ""),
                    forma_pago=sembrados.get("forma_pago", ""),
                    orden=presupuesto, ultimo_mensaje=mensaje)
            except Exception as e:
                log.warning("notificar_lead_failed", error=str(e)[:120])
            # CIERRE DISTINTO al captar (arreglo del loop Monte Ralo): antes no devolvia respuesta y el solver
            # re-mandaba el presupuesto una y otra vez ante cada "si".
            return None, {"accion": "lead_fuerte_captado", "lead_id": lead_id,
                          "respuesta_directa": cierre.mensaje_confirmacion(
                              {**sembrados, "orden": presupuesto}, presupuesto)}

        # VERSION B (modo 'venta'): el bot cierra y usa los datos para el cobro.
        lead_id = crear_lead(
            user_id=user_id, canal=canal, tienda_id=tienda_id,
            ultimo_mensaje=mensaje, frase_disparadora=frase,
            nivel="fuerte", estado_inicial="datos_solicitados",
            orden=presupuesto,
        )
        log.info("intencion_fuerte_detectada", lead_id=lead_id,
                 tienda_id=tienda_id, user_id=user_id,
                 frase=frase, trace_id=trace_id)

        # Siembra inicial (unico camino, sin flag): el mensaje que dispara el cierre suele traer datos ya
        # ("envio a Los Condores medio de pago mercado pago").
        from app.core import cierre
        # Siembra con TODO lo acumulado en turnos anteriores mas lo de este turno, asi una direccion o un pago
        # dados ANTES de la decision de compra ya estan y no se vuelven a pedir.
        prev = {k: v for k, v in (datos_previos or {}).items()
                if v and k in cierre.CAMPOS_EXTRAIBLES}
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
            actualizar_lead(lead_id, tienda_id,
                            {"datos_pedidos_campos": list(falt),
                             "datos_pedidos_veces": 1})
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
        meta["respuesta_directa"] = MENSAJE_HANDOFF_HUMANO
        return None, meta

    return None, {"accion": "ninguna"}
