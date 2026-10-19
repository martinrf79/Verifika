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
