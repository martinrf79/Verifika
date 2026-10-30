"""Cliente de Firestore para acceder al catálogo, FAQ, conversaciones y mensajes."""
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
# UNA HORA, no cinco minutos. Medido en la charla REAL de Martin del 29-jul (trace a2d0a5dc): el turno tardo
# 12,9 segundos y adentro de esos segundos se releyeron los 880 productos de Firestore y se reconstruyo el
# indice de recall.
_CACHE_TTL_SECONDS = 3600  # 1 hora


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

def get_tienda_by_phone_id(phone_number_id: str) -> dict | None:
    """Dado un phone_number_id de WhatsApp, devuelve {tienda_id, token, ...} si existe."""
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
    """Da de alta una tienda nueva. Crea el índice phone_id→tienda y la config base."""
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

def get_all_products(force_refresh: bool = False, tienda_id: str | None = None) -> list[dict]:
    """Devuelve todos los productos. Cachea en memoria 5 minutos para evitar leer Firestore en cada mensaje."""
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

    # FUENTE COMPLETA: al producto que viene sin el mapa `specs` se lo completa aca, una sola vez por refresco
    # de cache (880 productos = milisegundos).
    try:
        from app.core.fuente_producto import enriquecer
        enriquecer(list(productos.values()), tienda_id=tid)
    except Exception as e:
        log.warning("catalog_enriquecer_failed", tienda_id=tid, error=str(e)[:150])

    if not productos:
        # UNA LECTURA VACIA NO SE CACHEA. Ver `get_all_faq`: es la misma linea
        # y la misma media hora de silencio.
        log.error("catalogo_vacio_en_firestore", tienda_id=tid,
                  ruta=f"tiendas/{tid}/productos")
        return []

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


def upsert_products_batch(productos: list, tienda_id: str | None = None,
                          tam_lote: int = 200, progreso=None) -> int:
    """Carga el catalogo por LOTES. Devuelve cuantos se escribieron. 880 escrituras de a una son 880 viajes de
    red: lento y, si se corta la conexion a la mitad, queda medio catalogo cargado sin que nadie lo sepa."""
    col = _tienda_ref(tienda_id).collection("productos")
    escritos = 0
    for i in range(0, len(productos), tam_lote):
        lote = productos[i:i + tam_lote]
        for intento in (1, 2):
            try:
                batch = _get_db().batch()
                for prod in lote:
                    ref = col.document(str(prod["id"]).strip())
                    batch.set(ref, {"specs": firestore.DELETE_FIELD},
                              merge=True)
                    batch.set(ref, prod, merge=True)
                batch.commit()
                break
            except Exception as e:
                if intento == 2:
                    log.error("catalog_batch_failed", tienda_id=tienda_id,
                              desde=i, error=str(e)[:200])
                    raise
                log.warning("catalog_batch_retry", tienda_id=tienda_id,
                            desde=i, error=str(e)[:150])
        escritos += len(lote)
        if progreso:
            progreso(escritos, len(productos))
    invalidate_cache(tienda_id)
    log.info("catalog_batch_upserted", tienda_id=tienda_id, count=escritos)
    return escritos


def delete_all_products(tienda_id: str | None = None) -> int:
    """Borra TODOS los productos de una tienda."""
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
    # LO QUE SE DERIVA DEL CATALOGO MUERE CON EL CATALOGO, y esta linea es la unica que lo garantiza.
    try:
        from app.core.filtros_catalogo import limpiar_cache
        limpiar_cache(tienda_id)
    except Exception as e:  # noqa: BLE001 — invalidar de mas nunca rompe nada
        log.warning("invalidate_cache_derivados_error", error=str(e)[:150])


# ────────────────────────────────────────────────────────────


def get_all_faq(force_refresh: bool = False, tienda_id: str | None = None) -> dict:
    """La FAQ de la tienda. Una lectura VACIA no se cachea y se grita."""
    global _faq_cache, _faq_cache_ts
    tid = tienda_id or settings.TIENDA_ID
    now = time.time()
    if not force_refresh and tid in _faq_cache and (now - _faq_cache_ts.get(tid, 0)) < _CACHE_TTL_SECONDS:
        return _faq_cache[tid]

    docs = _tienda_ref(tid).collection("faq").stream()
    faq = {}
    for doc in docs:
        faq[doc.id] = doc.to_dict()

    if not faq:
        log.error("faq_vacia_en_firestore", tienda_id=tid,
                  ruta=f"tiendas/{tid}/faq")
        return {}

    _faq_cache[tid] = faq
    _faq_cache_ts[tid] = now
    log.info("faq_loaded_from_firestore", tienda_id=tid, count=len(faq))
    return faq


def upsert_faq(tema_id: str, data: dict, tienda_id: str | None = None):
    _tienda_ref(tienda_id).collection("faq").document(tema_id).set(data, merge=True)
    tid = tienda_id or settings.TIENDA_ID
    _faq_cache.pop(tid, None)
    _faq_cache_ts.pop(tid, None)


# ────────────────────────────────────────────────────────────

def get_conversation(user_id: str, tienda_id: str | None = None) -> dict:
    """Devuelve el documento de conversación. Si no existe, devuelve estructura vacía."""
    doc = _tienda_ref(tienda_id).collection("conversaciones").document(user_id).get()
    if doc.exists:
        return doc.to_dict()
    return {"history": [], "summary": "", "estado_conversacion": "saludo", "updated_at": None}


def save_conversation(user_id: str, history: list[dict], summary: str = "",
                      tienda_id: str | None = None,
                      estado_conversacion: str | None = None,
                      ultimo_presupuesto: str | None = None,
                      # Lo mostrado con su id, para que el turno siguiente lo resuelva por id y no por prosa.
                      productos_vistos: list | None = None,
                      ultima_localidad: str | None = None,
                      grupos_envio: list | None = None,
                      # Los items de la ultima cuenta: que el pedido no mute de identidad entre turnos.
                      carrito_vigente: list | None = None,
                      # El pedido esperando el si del cliente. {} = limpiar.
                      pedido_pendiente: dict | None = None,
                      criterio_cliente: str | None = None,
                      pregunta_cierre_hecha: bool | None = None,
                      # Nombre y datos del cliente, aunque todavia no haya lead: no se vuelven a pedir.
                      datos_cliente_parciales: dict | None = None,
                      # EL REPARTO DEL PAGO ES DEL PEDIDO (16-oct, K21): "setenta treinta" dicho una vez vale
                      # hasta que el cliente diga otro. [] = sin reparto.
                      reparto_pago: list | None = None,
                      # La memoria del agente, FICHA 83: el pedido anotado, lo ultimo mostrado, el pago y el tope.
                      memoria_agente: dict | None = None,
                      **extras):
    """None no pisa lo guardado. Los campos que escribian los caminos viejos se sacaron el 16-oct: nadie los
    pasaba."""
    if extras:
        log.warning("save_conversation_kwargs_desconocidos", campos=sorted(extras.keys()))
    campos = {k: v for k, v in locals().items() if k not in ("user_id", "history", "summary", "tienda_id", "extras")}
    datos = {"history": history, "summary": summary, "updated_at": firestore.SERVER_TIMESTAMP,
             **{k: v for k, v in {**campos, **extras}.items() if v is not None}}
    _tienda_ref(tienda_id).collection("conversaciones").document(user_id).set(
        datos, merge=True)


def reset_conversation(user_id: str, tienda_id: str | None = None):
    """El RESET_CODE arranca la charla de cero, pero NO la borra: la ARCHIVA. 27-sep: Martin probo cuatro veces
    seguidas la misma pregunta con un reset entre cada una, y de tres de esas respuestas no quedo nada."""
    ref = _tienda_ref(tienda_id).collection("conversaciones").document(user_id)
    try:
        doc = ref.get()
        if doc.exists:
            _tienda_ref(tienda_id).collection("conversaciones_archivo").document(
                f"{user_id}_{time.strftime('%Y%m%dT%H%M%S', time.gmtime())}").set(
                {**(doc.to_dict() or {}), "usuario": user_id, "archivada_en": firestore.SERVER_TIMESTAMP})
    except Exception as e:  # noqa: BLE001 — el reset se hace igual aunque no se archive
        log.warning("reset_archivo_error", user_id=user_id, error=str(e)[:120])
    ref.delete()


# ────────────────────────────────────────────────────────────

# log_message se borro: escribia una coleccion de mensajes que no lee nadie.

# ────────────────────────────────────────────────────────────

def already_processed(message_id: str) -> bool:
    """Devuelve True si ese message_id ya fue procesado en las últimas 24h."""
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

def get_config(key: str, default: Any = None, tienda_id: str | None = None) -> Any:
    doc = _tienda_ref(tienda_id).collection("config").document(key).get()
    if doc.exists:
        return doc.to_dict().get("value", default)
    return default


def set_config(key: str, value: Any, tienda_id: str | None = None):
    _tienda_ref(tienda_id).collection("config").document(key).set({"value": value})
