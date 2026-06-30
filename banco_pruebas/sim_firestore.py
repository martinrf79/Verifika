"""
SIMULADOR DE FIRESTORE — doble local cargado con los DATOS REALES del repo.

No reimplementa nada del bot: parchea SOLO la capa de almacenamiento
(firestore_client) para que lea del catalogo real (data/clientes/verifika_prod/
productos.csv, 880 productos) y la FAQ real (faq.json, 44 temas). Todo el codigo
de produccion -interprete, solver, calculate_total, cotizar_envio, query_faq,
verificador, guardia- corre TAL CUAL encima, con DeepSeek vivo.

Asi se puede probar el camino completo de punta a punta sin credenciales de
Google. La memoria de conversacion vive en un dict en RAM (se borra al salir).

install() debe llamarse ANTES de procesar el primer mensaje.

LIMITES honestos del doble:
- tarifas_envio por provincia: NO esta en el repo (vive solo en Firestore real).
  Se siembra abajo un valor ASUMIDO (cordoba=7500) para reproducir lo visto en
  prod; confirmalo contra Firestore. Si lo dejas vacio, cotizar_envio cae al
  rango de la FAQ, que es el comportamiento honesto sin esa tabla.
- El cierre/lead (link de Mercado Pago) se stubea a no-op: este doble apunta a la
  INTERPRETACION y la anti-alucinacion, no al pago.
"""
import csv
import json
import time
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
_DATA = _RAIZ / "data" / "clientes" / "verifika_prod"

_INT_FIELDS = ("precio_ars", "stock", "peso_gramos", "garantia_meses")

# Memoria de conversacion en RAM: {(tid, user_id): doc}
_CONV: dict = {}

# Config simulada de la tienda. tarifas_envio: ver LIMITES arriba.
_CONFIG = {
    "business_name": "Verifika",
    "modo_cierre": "off",
    "mp_access_token": "",
    "tarifas_envio": {
        "provincias": {
            "cordoba": 7500,        # ASUMIDO, confirmar contra Firestore real
        }
    },
}


def _cargar_productos() -> dict:
    prods = {}
    with open(_DATA / "productos.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for k in _INT_FIELDS:
                v = (row.get(k) or "").strip()
                if v:
                    try:
                        row[k] = int(float(v))
                    except ValueError:
                        pass
            pid = row.get("id")
            if pid:
                prods[pid] = row
    return prods


def _cargar_faq() -> dict:
    faq = {}
    data = json.loads((_DATA / "faq.json").read_text(encoding="utf-8"))
    for tema in data:
        tid = tema.get("tema")
        if tid:
            faq[tid] = {
                "respuesta": tema.get("respuesta", ""),
                "tipo": tema.get("tipo", "informativo"),
                "valores": tema.get("valores", []),
                "keywords": tema.get("keywords", []),
            }
    return faq


def install():
    """Parchea firestore_client y reengancha los nombres en cada consumidor."""
    productos = _cargar_productos()
    faq = _cargar_faq()

    import app.storage.firestore_client as fc

    def get_all_products(force_refresh=False, tienda_id=None):
        return list(productos.values())

    def get_product_by_id(product_id, tienda_id=None):
        return productos.get(str(product_id).strip())

    def get_categories(tienda_id=None):
        return sorted({p.get("categoria", "") for p in productos.values() if p.get("categoria")})

    def get_all_faq(force_refresh=False, tienda_id=None):
        return faq

    def get_config(key, default=None, tienda_id=None):
        return _CONFIG.get(key, default)

    def set_config(key, value, tienda_id=None):
        _CONFIG[key] = value

    def get_conversation(user_id, tienda_id=None):
        doc = _CONV.get((tienda_id, user_id))
        if doc:
            return doc
        return {"history": [], "summary": "", "estado_conversacion": "saludo", "updated_at": None}

    def save_conversation(user_id, history, summary="", tienda_id=None, **kw):
        doc = _CONV.setdefault((tienda_id, user_id), {})
        doc["history"] = history
        doc["summary"] = summary
        for k, v in kw.items():
            if v is not None:
                doc[k] = v

    def reset_conversation(user_id, tienda_id=None):
        _CONV.pop((tienda_id, user_id), None)

    def log_message(*a, **k):
        return None

    def already_processed(message_id):
        return False

    def invalidate_cache(tienda_id=None):
        return None

    _patches = {
        "get_all_products": get_all_products, "get_product_by_id": get_product_by_id,
        "get_categories": get_categories, "get_all_faq": get_all_faq,
        "get_config": get_config, "set_config": set_config,
        "get_conversation": get_conversation, "save_conversation": save_conversation,
        "reset_conversation": reset_conversation, "log_message": log_message,
        "already_processed": already_processed, "invalidate_cache": invalidate_cache,
    }
    for nombre, fn in _patches.items():
        setattr(fc, nombre, fn)

    # Reenganche en los consumidores que importaron los nombres ARRIBA (mantienen
    # su propia referencia; un setattr en fc no los alcanza).
    import app.core.tools as tools
    for n in ("get_all_products", "get_product_by_id", "get_categories", "get_all_faq"):
        setattr(tools, n, _patches[n])
    import app.storage.search as search
    search.get_all_products = get_all_products
    import app.core.evidencia as evidencia
    evidencia.get_all_faq = get_all_faq
    import app.core.interprete_libre as il
    for n in ("get_conversation", "save_conversation", "reset_conversation", "get_config"):
        setattr(il, n, _patches[n])

    # Stub del cierre/lead (no toca el pago): este doble prueba interpretacion +
    # anti-alucinacion, no el link de Mercado Pago.
    async def _procesar_lead_noop(*a, **k):
        return "", {}

    il.get_lead_activo = lambda *a, **k: None
    il.descartar_leads_activos = lambda *a, **k: 0
    il.procesar_mensaje_para_lead = _procesar_lead_noop

    return {"productos": len(productos), "faq": len(faq)}
