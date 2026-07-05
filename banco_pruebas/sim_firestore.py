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
    # Igual que produccion (config.py MODO_CIERRE default "A"): el camino del
    # cierre/lead corre REAL sobre el doble de leads en RAM de abajo. Antes se
    # simulaba "off" y el cierre no se probaba nunca antes de la charla real.
    "modo_cierre": "A",
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
                "respuesta_curada": tema.get("respuesta_curada", ""),
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

    # LEADS EN RAM: el camino REAL del cierre (procesar_mensaje_para_lead, con
    # sus gatillos, pregunta suave y captura) corre TAL CUAL. Se dobla SOLO el
    # almacenamiento del lead (dict en RAM en vez de la coleccion Firestore) y
    # el aviso al dueño (notificar_lead, que es una llamada HTTP saliente).
    # Antes todo el camino era un no-op y el cierre no se probaba nunca en el
    # banco: los errores del lead se estrenaban en la charla real.
    import app.core.leads as leads

    _leads_ram: dict = {}
    _leads_seq = {"n": 0}
    _avisos: list = []

    def _lead_vivo(d) -> bool:
        cutoff = time.time() - leads.LEAD_VENTANA_SEGUNDOS
        return (d.get("creado_en_ts", 0) >= cutoff
                and d.get("estado") not in ("descartado", "cerrado", "completado"))

    def get_lead_activo(user_id, canal, tienda_id):
        vivos = [d for d in _leads_ram.values()
                 if d.get("user_id") == user_id and d.get("canal") == canal
                 and _lead_vivo(d)]
        if not vivos:
            return None
        return dict(max(vivos, key=lambda d: d.get("creado_en_ts", 0)))

    def descartar_leads_activos(user_id, canal, tienda_id):
        n = 0
        for d in _leads_ram.values():
            if (d.get("user_id") == user_id and d.get("canal") == canal
                    and _lead_vivo(d)):
                d["estado"] = "descartado"
                n += 1
        return n

    def crear_lead(user_id, canal, tienda_id, ultimo_mensaje, frase_disparadora,
                   nivel, estado_inicial, orden=""):
        _leads_seq["n"] += 1
        lid = f"lead{_leads_seq['n']:04d}"
        _leads_ram[lid] = {
            "lead_id": lid, "tienda_id": tienda_id, "canal": canal,
            "user_id": user_id, "nombre": "", "telefono": "", "direccion": "",
            "forma_pago": "", "orden": (orden or "")[:1500],
            "estado": estado_inicial, "nivel": nivel,
            "ultimo_mensaje": (ultimo_mensaje or "")[:500],
            "frase_disparadora": frase_disparadora,
            "creado_en_ts": time.time(),
        }
        print(f"[sim] lead_created {lid} nivel={nivel} estado={estado_inicial}")
        return lid

    def actualizar_lead(lead_id, tienda_id, cambios):
        doc = _leads_ram[lead_id]
        doc.update({k: v for k, v in cambios.items() if k != "actualizado_en"})

    async def notificar_lead(**kw):
        _avisos.append(kw)
        print(f"[sim] AVISO AL DUEÑO (notificar_lead): estado={kw.get('estado')} "
              f"nombre={kw.get('nombre')} orden={str(kw.get('orden'))[:80]}")
        return None

    leads.get_lead_activo = get_lead_activo
    leads.descartar_leads_activos = descartar_leads_activos
    leads.crear_lead = crear_lead
    leads.actualizar_lead = actualizar_lead
    leads.notificar_lead = notificar_lead
    # interprete_libre importo estos nombres arriba: reenganche al doble y al
    # camino REAL del cierre.
    il.get_lead_activo = get_lead_activo
    il.descartar_leads_activos = descartar_leads_activos
    il.procesar_mensaje_para_lead = leads.procesar_mensaje_para_lead

    return {"productos": len(productos), "faq": len(faq),
            "leads_ram": _leads_ram, "avisos": _avisos}
