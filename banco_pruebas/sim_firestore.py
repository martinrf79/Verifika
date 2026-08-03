"""
SIMULADOR DE FIRESTORE — doble local cargado con los DATOS REALES del repo.

No reimplementa nada del bot: parchea SOLO la capa de almacenamiento
(firestore_client) para que lea del catalogo real (data/clientes/verifika_prod/
productos.csv, 880 productos) y la FAQ real (faq.json, 50 temas). Todo el codigo
de produccion -interprete, solver, calculate_total, cotizar_envio, query_faq,
verificador, guardia- corre TAL CUAL encima, con el modelo vivo.

Asi se puede probar el camino completo de punta a punta sin credenciales de
Google. La memoria de conversacion vive en un dict en RAM (se borra al salir).

install() debe llamarse ANTES de procesar el primer mensaje.

LA CONFIG DE TIENDA NO SE INVENTA (31-jul-2026). Antes se sembraba a mano
-cordoba=7500 "ASUMIDO", business_name "Verifika", modo_cierre "A"- y el banco
probaba una tienda que no existe: produccion tiene 24 destinos de envio, se
llama "Verifika Tech" y NO tiene doc de modo_cierre, asi que cae al default de
config.py. Ahora la config sale de `fixtures/config_prod.json`, que es el
volcado literal de `tiendas/verifika_prod/config`. Si falta un doc en el
volcado, aca tambien falta, y `get_config` devuelve el mismo default que en la
nube. Para refrescar el volcado y confirmar que no derivo:
    python3 banco_pruebas/verificar_clon.py            # compara
    python3 banco_pruebas/verificar_clon.py --exportar # actualiza el volcado

LIMITE que queda, dicho claro: el cobro real de Mercado Pago no se ejecuta,
porque produccion tampoco tiene `mp_access_token` cargado. El dia que la tienda
lo cargue, el volcado lo va a traer y hay que decidir si el banco cobra de
verdad o corta ahi.
"""
import csv
import json
import time
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
_DATA = _RAIZ / "data" / "clientes" / "verifika_prod"
_FIXTURE_CONFIG = Path(__file__).resolve().parent / "fixtures" / "config_prod.json"

# Memoria de conversacion en RAM: {(tid, user_id): doc}
_CONV: dict = {}


def _cargar_config() -> dict:
    """La coleccion `config` de la tienda, tal cual esta en Firestore real."""
    datos = json.loads(_FIXTURE_CONFIG.read_text(encoding="utf-8"))
    return dict(datos.get("docs") or {})


# Config de la tienda: volcado real, no invento. Ver docstring de arriba.
_CONFIG = _cargar_config()


def _cargar_productos() -> dict:
    """El catalogo del banco entra por la MISMA puerta que produccion
    (fuente_producto.normalizar_producto): mismos tipos, misma ficha depurada y
    el mismo mapa `specs`. Si el banco cargara el CSV crudo probaria un
    producto que el bot vivo no ve nunca."""
    from app.core.fuente_producto import normalizar_producto
    prods = {}
    with open(_DATA / "productos.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = (row.get("id") or "").strip()
            if pid:
                prods[pid] = normalizar_producto(row)
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

    def _validar_como_firestore(valor, campo):
        """El doble impone las MISMAS reglas de tipos que Firestore real. Bug
        real 8-jul: una lista de listas (pedido_categorias_pendiente) pasaba
        el doble pero Firestore la rechaza con 400 'Nested arrays are not
        allowed', el save entero fallaba y el bot quedaba AMNESICO en
        produccion. El doble ahora explota igual que la vida real."""
        if isinstance(valor, tuple):
            raise ValueError(
                f"Firestore no acepta tuplas (campo {campo}): usar lista")
        if isinstance(valor, list):
            for item in valor:
                if isinstance(item, (list, tuple)):
                    raise ValueError(
                        f"400 Nested arrays are not allowed (campo {campo})")
                if isinstance(item, dict):
                    for kk, vv in item.items():
                        _validar_como_firestore(vv, f"{campo}.{kk}")
        elif isinstance(valor, dict):
            for kk, vv in valor.items():
                _validar_como_firestore(vv, f"{campo}.{kk}")

    def save_conversation(user_id, history, summary="", tienda_id=None, **kw):
        doc = _CONV.setdefault((tienda_id, user_id), {})
        _validar_como_firestore(history, "history")
        doc["history"] = history
        doc["summary"] = summary
        for k, v in kw.items():
            if v is not None:
                _validar_como_firestore(v, k)
                doc[k] = v

    def reset_conversation(user_id, tienda_id=None):
        _CONV.pop((tienda_id, user_id), None)

    _vistos: set = set()

    def already_processed(message_id):
        """Idempotencia REAL, como en la nube: el mismo message_id dos veces se
        procesa una sola. Antes devolvia False siempre y el banco no podia ver
        un reintento de Meta, que en produccion pasa."""
        mid = str(message_id or "")
        if not mid:
            return False
        if mid in _vistos:
            return True
        _vistos.add(mid)
        return False

    def invalidate_cache(tienda_id=None):
        return None

    _patches = {
        "get_all_products": get_all_products, "get_product_by_id": get_product_by_id,
        "get_categories": get_categories, "get_all_faq": get_all_faq,
        "get_config": get_config, "set_config": set_config,
        "get_conversation": get_conversation, "save_conversation": save_conversation,
        "reset_conversation": reset_conversation,
        "already_processed": already_processed, "invalidate_cache": invalidate_cache,
    }
    for nombre, fn in _patches.items():
        setattr(fc, nombre, fn)

    # Reenganche en los consumidores que importaron los nombres ARRIBA (mantienen
    # su propia referencia; un setattr en fc no los alcanza).
    import app.core.calculadora as tools
    for n in ("get_all_products", "get_product_by_id", "get_categories", "get_all_faq"):
        setattr(tools, n, _patches[n])
    # hub_venta es el camino VIVO y tambien importa los nombres arriba. Antes de
    # este parche solo funcionaba de casualidad, porque el banco lo importaba
    # DESPUES de install(); un test que lo importe antes -o el orchestrator, que
    # lo trae al colectar- quedaba clavado al Firestore real.
    import app.core.hub_venta as hv
    for n in ("get_conversation", "save_conversation"):
        setattr(hv, n, _patches[n])
    # guia_compra tambien importa los nombres arriba: si alguien lo importo
    # ANTES de install() (un test que lo importa a nivel de modulo), quedaba
    # clavado al Firestore real y media bateria caia con DefaultCredentials.
    import app.core.guia_compra as gc
    for n in ("get_all_products", "get_product_by_id", "get_categories"):
        setattr(gc, n, _patches[n])

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
    # `hub_venta` importa el cierre ADENTRO de la funcion, asi que agarra el
    # doble por si mismo: no hace falta reengancharlo en el modulo.

    return {"productos": len(productos), "faq": len(faq),
            "leads_ram": _leads_ram, "avisos": _avisos}
