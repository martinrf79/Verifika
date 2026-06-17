"""
Cliente de Firestore para acceder al catálogo, FAQ, conversaciones y mensajes.

Estructura de la base:
    tiendas/{tienda_id}/
        config/                          (datos del negocio)
        productos/{producto_id}          (catálogo + embedding)
        faq/{tema_id}                    (preguntas frecuentes)
        conversaciones/{user_id}         (historial corto + resumen largo)
        mensajes/{auto_id}               (logs de mensajes para análisis)

Diseño:
- Una sola tienda por ahora (TIENDA_ID="tienda_principal").
- Multi-tenant queda preparado para revender el bot a otras tiendas mañana.
- Cache en memoria del catálogo completo: 5 minutos.
- Embeddings se almacenan junto con cada producto.
"""
import time
from typing import Any
from google.cloud import firestore
from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

_db: firestore.Client | None = None
# Caches por tienda: {tienda_id: {...}}
_catalog_cache: dict[str, dict] = {}
_catalog_cache_ts: dict[str, float] = {}
_faq_cache: dict[str, dict] = {}
_faq_cache_ts: dict[str, float] = {}
# Cache de resolución phone_id → tienda_id (no expira; se invalida al alta)
_phone_to_tienda: dict[str, str] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutos


def _get_db() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client(project=settings.GCP_PROJECT)
    return _db


def _tienda_ref(tienda_id: str | None = None):
    """Referencia a una tienda. Si no se pasa, usa la del settings (default)."""
    tid = tienda_id or settings.TIENDA_ID
    return _get_db().collection("tiendas").document(tid)


# ────────────────────────────────────────────────────────────
# RESOLUCIÓN DE TIENDA POR PHONE_NUMBER_ID (multi-tenant WhatsApp)
# ────────────────────────────────────────────────────────────

def get_tienda_by_phone_id(phone_number_id: str) -> dict | None:
    """
    Dado un phone_number_id de WhatsApp, devuelve {tienda_id, token, ...} si existe.
    Se cachea en memoria para evitar lecturas repetidas.

    Estructura esperada en Firestore:
        tiendas_index/{phone_number_id} = {tienda_id: "...", token: "...", ...}
    """
    if phone_number_id in _phone_to_tienda:
        tid = _phone_to_tienda[phone_number_id]
        # Releemos el documento para obtener token actualizado
        doc = _get_db().collection("tiendas_index").document(phone_number_id).get()
        if doc.exists:
            data = doc.to_dict()
            data["tienda_id"] = tid
            return data
        return None

    doc = _get_db().collection("tiendas_index").document(phone_number_id).get()
    if not doc.exists:
        log.warning("tienda_not_found_for_phone_id", phone_id=phone_number_id)
        return None
    data = doc.to_dict()
    tid = data.get("tienda_id")
    if not tid:
        log.error("tienda_index_missing_tienda_id", phone_id=phone_number_id)
        return None
    _phone_to_tienda[phone_number_id] = tid
    data["tienda_id"] = tid
    return data


def register_tienda(tienda_id: str, phone_number_id: str, whatsapp_token: str,
                    nombre: str = "", verify_token: str = ""):
    """
    Da de alta una tienda nueva. Crea el índice phone_id→tienda y la config base.
    Se llama desde el script de onboarding.
    """
    _get_db().collection("tiendas_index").document(phone_number_id).set({
        "tienda_id": tienda_id,
        "whatsapp_token": whatsapp_token,
        "verify_token": verify_token,
        "nombre": nombre,
        "creado_en": firestore.SERVER_TIMESTAMP,
    })
    # Invalidar cache local
    _phone_to_tienda.pop(phone_number_id, None)
    log.info("tienda_registered", tienda_id=tienda_id, phone_id=phone_number_id)


# ────────────────────────────────────────────────────────────
# CATÁLOGO
# ────────────────────────────────────────────────────────────

def get_all_products(force_refresh: bool = False, tienda_id: str | None = None) -> list[dict]:
    """
    Devuelve todos los productos. Cachea en memoria 5 minutos para evitar
    leer Firestore en cada mensaje.
    """
    global _catalog_cache, _catalog_cache_ts
    tid = tienda_id or settings.TIENDA_ID
    now = time.time()
    if not force_refresh and tid in _catalog_cache and (now - _catalog_cache_ts.get(tid, 0)) < _CACHE_TTL_SECONDS:
        return list(_catalog_cache[tid].values())

    productos_ref = _tienda_ref(tid).collection("productos")
    docs = productos_ref.stream()
    productos = {}
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        productos[doc.id] = data

    _catalog_cache[tid] = productos
    _catalog_cache_ts[tid] = now
    log.info("catalog_loaded_from_firestore", tienda_id=tid, count=len(productos))
    return list(productos.values())


def get_product_by_id(product_id: str, tienda_id: str | None = None) -> dict | None:
    productos = get_all_products(tienda_id=tienda_id)
    for p in productos:
        if p["id"].upper() == product_id.upper():
            return p
    return None


def get_categories(tienda_id: str | None = None) -> list[str]:
    productos = get_all_products(tienda_id=tienda_id)
    return sorted({p["categoria"] for p in productos})


def upsert_product(product_id: str, data: dict, tienda_id: str | None = None):
    """Crea o actualiza un producto."""
    _tienda_ref(tienda_id).collection("productos").document(product_id).set(data, merge=True)
    invalidate_cache(tienda_id)


def delete_all_products(tienda_id: str | None = None) -> int:
    """
    Borra TODOS los productos de una tienda. Devuelve cantidad borrada.
    Se usa en upload-catalog modo replace (default).
    Borra en batches de 500 (límite de Firestore batch).
    """
    productos_ref = _tienda_ref(tienda_id).collection("productos")
    total = 0
    while True:
        docs = list(productos_ref.limit(500).stream())
        if not docs:
            break
        batch = _get_db().batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()
        total += len(docs)
        if len(docs) < 500:
            break
    invalidate_cache(tienda_id)
    log.info("products_deleted_all", tienda_id=tienda_id or settings.TIENDA_ID, count=total)
    return total


def delete_all_faq(tienda_id: str | None = None) -> int:
    """Borra todas las FAQ de una tienda. Devuelve cantidad borrada."""
    faq_ref = _tienda_ref(tienda_id).collection("faq")
    total = 0
    while True:
        docs = list(faq_ref.limit(500).stream())
        if not docs:
            break
        batch = _get_db().batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()
        total += len(docs)
        if len(docs) < 500:
            break
    tid = tienda_id or settings.TIENDA_ID
    _faq_cache.pop(tid, None)
    _faq_cache_ts.pop(tid, None)
    log.info("faq_deleted_all", tienda_id=tid, count=total)
    return total


def invalidate_cache(tienda_id: str | None = None):
    """Fuerza recargar el catálogo en la próxima llamada."""
    global _catalog_cache, _catalog_cache_ts
    if tienda_id is None:
        _catalog_cache.clear()
        _catalog_cache_ts.clear()
    else:
        _catalog_cache.pop(tienda_id, None)
        _catalog_cache_ts.pop(tienda_id, None)


# ────────────────────────────────────────────────────────────
# FAQ
# ────────────────────────────────────────────────────────────


def get_all_faq(force_refresh: bool = False, tienda_id: str | None = None) -> dict:
    global _faq_cache, _faq_cache_ts
    tid = tienda_id or settings.TIENDA_ID
    now = time.time()
    if not force_refresh and tid in _faq_cache and (now - _faq_cache_ts.get(tid, 0)) < _CACHE_TTL_SECONDS:
        return _faq_cache[tid]

    docs = _tienda_ref(tid).collection("faq").stream()
    faq = {}
    for doc in docs:
        faq[doc.id] = doc.to_dict()

    _faq_cache[tid] = faq
    _faq_cache_ts[tid] = now
    return faq


def upsert_faq(tema_id: str, data: dict, tienda_id: str | None = None):
    _tienda_ref(tienda_id).collection("faq").document(tema_id).set(data, merge=True)
    tid = tienda_id or settings.TIENDA_ID
    _faq_cache.pop(tid, None)
    _faq_cache_ts.pop(tid, None)


# ────────────────────────────────────────────────────────────
# CONVERSACIONES (historial corto)
# ────────────────────────────────────────────────────────────

def get_conversation(user_id: str, tienda_id: str | None = None) -> dict:
    """
    Devuelve el documento de conversación. Si no existe, devuelve estructura vacía.
    """
    doc = _tienda_ref(tienda_id).collection("conversaciones").document(user_id).get()
    if doc.exists:
        return doc.to_dict()
    return {"history": [], "summary": "", "estado_conversacion": "saludo", "updated_at": None}


def save_conversation(user_id: str, history: list[dict], summary: str = "",
                      tienda_id: str | None = None,
                      estado_conversacion: str | None = None,
                      ultima_compra: str | None = None,
                      proofs_recientes: list | None = None,
                      ultimo_presupuesto: str | None = None,
                      productos_vistos: list | None = None,
                      ultima_localidad: str | None = None,
                      carrito_vigente: list | None = None,
                      pedido_pendiente: dict | None = None):
    datos = {
        "history": history,
        "summary": summary,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    if estado_conversacion is not None:
        datos["estado_conversacion"] = estado_conversacion
    if ultima_compra is not None:
        datos["ultima_compra"] = ultima_compra
    # PROOF de calculos recientes, para verificar totales repetidos en la
    # confirmacion sin recalcular. Lista, ya viene capada por el orchestrator.
    if proofs_recientes is not None:
        datos["proofs_recientes"] = proofs_recientes
    if ultimo_presupuesto is not None:
        datos["ultimo_presupuesto"] = ultimo_presupuesto
    # REGISTRO DE SESION: productos mostrados con su product_id, para que en el
    # turno siguiente el Solver tenga el ID real (la prosa solo guarda nombre y
    # precio). Lista {id, nombre, precio}, ya viene capada por el orchestrator.
    if productos_vistos is not None:
        datos["productos_vistos"] = productos_vistos
    # Ultima localidad de envio mencionada, para cotizar el envio en turnos
    # siguientes cuando el cliente dice "el envio ahi" sin repetir la ciudad.
    if ultima_localidad is not None:
        datos["ultima_localidad"] = ultima_localidad
    # CARRITO VIGENTE: items del ultimo calculate_total ok {id, nombre,
    # cantidad}, para que el pedido no mute de identidad entre turnos.
    if carrito_vigente is not None:
        datos["carrito_vigente"] = carrito_vigente
    # PEDIDO PENDIENTE: el pedido a medio armar (items resueltos + terminos
    # ambiguos con cantidad) esperando el criterio del cliente. {} = limpiar.
    if pedido_pendiente is not None:
        datos["pedido_pendiente"] = pedido_pendiente
    _tienda_ref(tienda_id).collection("conversaciones").document(user_id).set(
        datos, merge=True)


def reset_conversation(user_id: str, tienda_id: str | None = None):
    _tienda_ref(tienda_id).collection("conversaciones").document(user_id).delete()


# ────────────────────────────────────────────────────────────
# MENSAJES (log para análisis)
# ────────────────────────────────────────────────────────────

def log_message(user_id: str, mensaje_usuario: str, respuesta_bot: str,
                tools_called: list, latency_ms: int, trace_id: str,
                tienda_id: str | None = None):
    """Guarda cada interacción para análisis posterior."""
    try:
        _tienda_ref(tienda_id).collection("mensajes").add({
            "user_id": user_id,
            "mensaje_usuario": mensaje_usuario[:500],
            "respuesta_bot": respuesta_bot[:500],
            "tools_called": tools_called,
            "latency_ms": latency_ms,
            "trace_id": trace_id,
            "timestamp": firestore.SERVER_TIMESTAMP,
        })
    except Exception as e:
        log.warning("log_message_failed", error=str(e)[:100])


# ────────────────────────────────────────────────────────────
# IDEMPOTENCIA (evitar procesar mismo mensaje 2 veces)
# ────────────────────────────────────────────────────────────

def already_processed(message_id: str) -> bool:
    """
    Devuelve True si ese message_id ya fue procesado en las últimas 24h.
    Usa colección global "mensajes_procesados" con TTL.
    """
    if not message_id:
        return False
    try:
        doc_ref = _get_db().collection("mensajes_procesados").document(message_id)
        doc = doc_ref.get()
        if doc.exists:
            return True
        # Marcar como procesado
        doc_ref.set({"ts": firestore.SERVER_TIMESTAMP})
        return False
    except Exception as e:
        log.warning("idempotency_check_failed", error=str(e)[:100])
        return False  # En caso de error, procesar (mejor responder que no responder)


# ────────────────────────────────────────────────────────────
# CONFIG TIENDA
# ────────────────────────────────────────────────────────────

def get_config(key: str, default: Any = None, tienda_id: str | None = None) -> Any:
    doc = _tienda_ref(tienda_id).collection("config").document(key).get()
    if doc.exists:
        return doc.to_dict().get("value", default)
    return default


def set_config(key: str, value: Any, tienda_id: str | None = None):
    _tienda_ref(tienda_id).collection("config").document(key).set({"value": value})
