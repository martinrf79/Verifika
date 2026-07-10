"""
ESTADO DE VENTA — fuente unica de verdad del turno, accesible por todas las etapas.

Hasta ahora el estado de la venta vivia disperso: seis campos sueltos en el
documento de la conversacion (productos vistos, carrito, ultimo total, ultima
localidad, proofs) MAS los datos del cliente en un documento de lead aparte. Cada
etapa leia un pedazo distinto: el solver el bloque de venta, el cierre el lead, las
herramientas nada. Esa fragmentacion fue la causa de bugs como pedir la direccion
dos veces (el solver y el cierre no compartian la misma verdad).

Este modulo consolida todo en UN objeto `estado` que se construye una sola vez por
turno (desde la conversacion + el lead) y viaja por una contextvar, igual que la
tienda y el destino. Asi el interprete, el compositor, las herramientas
deterministas y el cierre leen la MISMA verdad sin recibirla por parametro.

Regla de escritura (una sola por dato): el significado lo escribe el interprete;
los numeros las herramientas con su PROOF; la redaccion el compositor. El estado
es de LECTURA para todos; cada dato lo actualiza solo su dueno.
"""
import re
from contextvars import ContextVar
from typing import Any

# Criterio de eleccion que el cliente deja dicho: "lo mas barato". Se detecta con
# codigo (no con el LLM) para que sea determinista y viaje por el estado. La raiz
# 'barat' cubre barato/barata/baratos/baratito; 'econom' cubre economico/economica.
_CRITERIO_BARATO_RE = re.compile(r"barat|econ[oó]mic", re.IGNORECASE)


def detectar_criterio(mensaje: str) -> str:
    """Criterio de precio que el cliente dejo dicho en el mensaje. Hoy uno solo:
    'más barato'. Devuelve '' si el mensaje no trae ninguno. Determinista: el
    mismo texto siempre da el mismo criterio, sin llamar a ningun modelo."""
    if _CRITERIO_BARATO_RE.search(mensaje or ""):
        return "más barato"
    return ""


def criterio_del_interprete(interp) -> bool:
    """El SEGUNDO interprete del criterio: la lectura del LLM. El regex de arriba
    no entiende 'eco' ni abreviaturas ni modismos; el interprete si (campo
    'criterio' del schema). True si el LLM leyo que el cliente quiere lo mas
    barato."""
    if not isinstance(interp, dict):
        return False
    return str(interp.get("criterio") or "").strip() == "mas_barato"


def concordancia_criterio(mensaje: str, interp) -> str:
    """DOS interpretes del criterio 'lo mas barato' (decision de Martin, 9-jul):
    el CODIGO (regex determinista) y el LLM (entiende 'eco', 'lo mas conveniente'
    y typos que el regex no cubre). Regla:
      - ambos lo ven      -> 'actuar'    (se arma sin preguntar)
      - solo uno lo ve    -> 'confirmar' (pregunta corta '¿los mas baratos?')
      - ninguno           -> ''          (no es un turno de criterio)
    Asi 'eco' se entiende sin listar sinonimos a mano, pero un disparo dudoso de
    UN solo interprete se confirma en vez de sellar un total que el cliente
    quiza no pidio. Generar > confirmar antes de comprometer plata."""
    cod = bool(detectar_criterio(mensaje))
    llm = criterio_del_interprete(interp)
    if cod and llm:
        return "actuar"
    if cod or llm:
        return "confirmar"
    return ""

_current_estado: ContextVar[dict | None] = ContextVar("current_estado", default=None)

# Localidades que cotizar_envio clasifico con exito en este turno, EN ORDEN. Es el
# puente entre las dos herramientas mellizas de envio: cotizar_envio (UNICA que
# calcula el costo) las escribe, y calculate_total las lee para pedirle a
# cotizar_envio el monto de CADA destino con el subtotal real, sin recalcular zona
# ni tarifa por su cuenta. Es una LISTA y no una sola: un pedido multi-destino
# cotiza varias localidades en el mismo turno y cada una cobra SU tarifa (antes se
# guardaba solo la ultima y dos destinos distintos cobraban dos veces la misma).
_envio_localidades: ContextVar[list | None] = ContextVar(
    "envio_localidades", default=None)

# Product_id que las tools DEVOLVIERON este turno (search, details, catalogo,
# calculadora): son los ids CERTIFICADOS del turno. La calculadora los usa para
# aplicar la regla cero mecanicamente: con un pedido vigente, un id que no sale
# ni del carrito, ni de lo ya mostrado, ni de una tool del turno es un id
# INFERIDO de memoria y muta la identidad del pedido en silencio.
_ids_certificados: ContextVar[set | None] = ContextVar(
    "ids_certificados", default=None)


def set_current_estado(estado: dict | None):
    """Setea el estado de venta del request. Lo llama el camino vivo al arrancar
    el turno, despues de cargar la conversacion y el lead. Limpia las localidades
    de envio del turno anterior para no arrastrar una cotizacion vieja."""
    _current_estado.set(estado)
    _envio_localidades.set([])
    _ids_certificados.set(set())


def set_envio_localidad(localidad: str | None):
    """Suma la localidad que cotizar_envio clasifico bien este turno. Re-cotizar la
    misma localidad (el cliente corrige o el solver repite) no crea otro destino:
    se deduplica por texto y queda al final como la mas reciente."""
    loc = (localidad or "").strip()
    if not loc:
        return
    locs = [l for l in (_envio_localidades.get() or [])
            if l.lower() != loc.lower()]
    locs.append(loc)
    _envio_localidades.set(locs)


def get_envio_localidad() -> str | None:
    """Ultima localidad cotizada este turno, o None. Compatibilidad para quien
    necesita UNA sola (pedido de un destino)."""
    locs = _envio_localidades.get() or []
    return locs[-1] if locs else None


def get_envio_localidades() -> list[str]:
    """Todas las localidades cotizadas con exito este turno, en orden. Las lee
    calculate_total para cobrar cada destino de un multi-destino con su tarifa."""
    return list(_envio_localidades.get() or [])


def certificar_ids_de_resultado(result):
    """Registra los product_id que una tool devolvio este turno. Lo llama el
    loop del agente despues de CADA tool: un solo lugar cubre search, details,
    catalogo y calculadora (mismas claves que lee productos_de_meta)."""
    if not isinstance(result, dict):
        return
    ids = _ids_certificados.get()
    if ids is None:
        ids = set()
        _ids_certificados.set(ids)
    cands = list(result.get("productos") or [])
    if isinstance(result.get("producto"), dict):
        cands.append(result["producto"])
    cands += list(result.get("detalle") or [])
    for p in cands:
        if isinstance(p, dict) and p.get("id"):
            ids.add(str(p["id"]).upper())


def get_ids_certificados() -> set:
    """Los product_id certificados por tools en este turno (copia)."""
    return set(_ids_certificados.get() or set())


def get_current_estado() -> dict:
    """Devuelve el estado de venta del request, o un dict vacio si no se seteo
    (ej tests que llaman una tool suelta). Nunca None, para leer sin guardas."""
    return _current_estado.get() or {}


def _money(n: Any) -> str:
    """Entero a formato argentino con separador de miles: 48000 -> '48.000'."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def productos_de_meta(meta: dict) -> list[dict]:
    """Productos que las tools mostraron este turno (id, nombre, precio REAL), desde
    el catalogo y el detalle de la calculadora. El precio sale verbatim de la tool,
    nunca del texto del solver. Lo escribe la herramienta, no el modelo."""
    vistos: dict[str, dict] = {}
    for tc in (meta or {}).get("tools_called", []) or []:
        res = tc.get("result")
        if not isinstance(res, dict):
            continue
        cands = list(res.get("productos") or [])
        if isinstance(res.get("producto"), dict):
            cands.append(res["producto"])
        cands += list(res.get("detalle") or [])
        for p in cands:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("id") or "").upper()
            precio = p.get("precio_ars")
            if precio is None:
                precio = p.get("precio_unitario")
            nombre = p.get("nombre")
            if pid and nombre and isinstance(precio, (int, float)):
                vistos[pid] = {"id": pid, "nombre": nombre, "precio": int(precio)}
    return list(vistos.values())


def carrito_de_meta(meta: dict) -> list[dict]:
    """Items del ultimo calculate_total que cerro bien (id, nombre, cantidad), para
    que el pedido no pierda identidad entre turnos."""
    for tc in reversed((meta or {}).get("tools_called", []) or []):
        if tc.get("name") != "calculate_total":
            continue
        res = tc.get("result")
        if not isinstance(res, dict) or res.get("ok") is False or not res.get("detalle"):
            continue
        items = [{"id": d["id"], "nombre": d.get("nombre", ""),
                  "cantidad": d.get("cantidad", 1)}
                 for d in res["detalle"] if isinstance(d, dict) and d.get("id")]
        if items:
            return items
    return []


def envio_de_meta(meta: dict) -> str:
    """Zona/provincia y costo del ultimo cotizar_envio que cerro bien, como texto
    listo para el estado. '' si no se cotizo nada valido este turno."""
    for tc in reversed((meta or {}).get("tools_called", []) or []):
        if tc.get("name") != "cotizar_envio":
            continue
        res = tc.get("result")
        if not isinstance(res, dict) or not res.get("ok"):
            continue
        zona = res.get("provincia") or res.get("zona") or "esa zona"
        zona = str(zona).replace("_", " ")
        if res.get("modalidad") == "rango":
            costo = (f"entre ${_money(res.get('monto_min'))} y "
                     f"${_money(res.get('monto_max'))}")
        else:
            m = res.get("monto", 0)
            costo = "gratis" if m in (0, None) else f"${_money(m)}"
        return f"{zona}: {costo}"
    return ""


def merge_productos(memoria: list[dict], turno: list[dict],
                    tope: int = 60) -> list[dict]:
    """Une los productos vistos en memoria con los del turno, deduplicando por id (el
    dato del turno pisa al viejo) y dejando los ultimos `tope`.

    Tope 60 (era 20): un solo turno de tres busquedas trae 30 productos y el tope
    viejo TIRABA la primera categoria entera (visto 8-jul: las notebooks caian de
    la memoria y el enum del interprete no podia referenciarlas, asi que el pedido
    extraido salia sin notebook y con el mouse duplicado)."""
    por_id: dict[str, dict] = {}
    for p in (memoria or []) + (turno or []):
        pid = str(p.get("id") or "").upper()
        if pid:
            por_id[pid] = p
    return list(por_id.values())[-tope:]


def construir_estado(conv: dict | None, lead: dict | None) -> dict:
    """Arma el objeto estado del turno desde la conversacion persistida y el lead
    activo. Consolida en un solo lugar lo que antes se leia de seis campos sueltos
    mas el documento de lead. Defensivo: tolera dicts vacios o None."""
    conv = conv or {}
    datos_cliente = {}
    if lead:
        for campo in ("nombre", "telefono", "direccion", "forma_pago"):
            v = str(lead.get(campo, "") or "").strip()
            if v:
                datos_cliente[campo] = v
    return {
        "productos_vistos": conv.get("productos_vistos") or [],
        "carrito": conv.get("carrito_vigente") or [],
        "presupuesto": (conv.get("ultimo_presupuesto") or "").strip(),
        "localidad_envio": (conv.get("ultima_localidad") or "").strip(),
        "localidades_envio": conv.get("ultimas_localidades") or [],
        "provincia_envio": (conv.get("provincia_envio") or "").strip(),
        "criterio": (conv.get("criterio_cliente") or "").strip(),
        "datos_cliente": datos_cliente,
        # Memoria larga: el resumen acumulado de la charla que ya salio del
        # historial vivo (turnos viejos fundidos). Contexto, no fuente de datos.
        "resumen_charla": (conv.get("summary") or "").strip(),
    }

