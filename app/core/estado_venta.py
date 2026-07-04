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
tienda y el destino. Asi el interprete, el solver, las herramientas deterministas y
el cierre leen la MISMA verdad sin recibirla por parametro.

Regla de escritura (una sola por dato): el significado lo escribe el interprete; los
numeros las herramientas con su PROOF; la identidad el certificador; la redaccion el
solver. El estado es de LECTURA para todos; cada dato lo actualiza solo su dueno.
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


def set_current_estado(estado: dict | None):
    """Setea el estado de venta del request. Lo llama el camino vivo al arrancar
    el turno, despues de cargar la conversacion y el lead. Limpia las localidades
    de envio del turno anterior para no arrastrar una cotizacion vieja."""
    _current_estado.set(estado)
    _envio_localidades.set([])


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
                    tope: int = 20) -> list[dict]:
    """Une los productos vistos en memoria con los del turno, deduplicando por id (el
    dato del turno pisa al viejo) y dejando los ultimos `tope`."""
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
        "provincia_envio": (conv.get("provincia_envio") or "").strip(),
        "criterio": (conv.get("criterio_cliente") or "").strip(),
        "datos_cliente": datos_cliente,
    }


def bloque_para_solver(estado: dict | None) -> str:
    """Resume el estado en un bloque compacto para inyectar al solver: productos ya
    mostrados con su precio REAL, carrito, total verificado, envio cotizado y datos
    del cliente ya capturados. Asi el solver no re-pregunta ni re-inventa un dato que
    ya salio de una herramienta. Se arma desde el estado, no desde el texto del solver.
    '' si no hay nada que aportar."""
    estado = estado or {}
    partes: list[str] = []

    prods = estado.get("productos_vistos") or []
    if prods:
        items = "; ".join(
            f"{p.get('nombre')} (id {p.get('id')}) ${_money(p.get('precio'))}"
            for p in prods[-8:] if p.get("nombre"))
        if items:
            partes.append("Productos ya mostrados con su precio real: " + items)

    carrito = estado.get("carrito") or []
    if carrito:
        items = ", ".join(f"{c.get('cantidad', 1)}x {c.get('nombre')}"
                          for c in carrito if c.get("nombre"))
        if items:
            partes.append("Carrito actual: " + items)

    presup = (estado.get("presupuesto") or "").strip()
    if presup:
        partes.append("Total ya calculado y verificado: " + presup)

    loc = (estado.get("localidad_envio") or "").strip()
    if loc:
        partes.append("Envio ya cotizado a " + loc)

    prov = (estado.get("provincia_envio") or "").strip()
    if prov:
        partes.append(f"Provincia YA dada por el cliente (NO repidas el CP ni la "
                      f"localidad): {prov}. Cotiza TODOS los destinos del pedido "
                      f"con esa provincia.")

    criterio = (estado.get("criterio") or "").strip()
    if criterio:
        partes.append(f"Preferencia YA dada por el cliente (NO la vuelvas a "
                      f"preguntar): quiere {criterio}. Elegi el {criterio} con "
                      f"stock y segui; no repreguntes modelo ni color.")

    datos = estado.get("datos_cliente") or {}
    if datos:
        etiquetas = {"nombre": "nombre", "telefono": "telefono",
                     "direccion": "direccion", "forma_pago": "forma de pago"}
        dichos = [f"{etiquetas[k]} {v}" for k, v in datos.items()
                  if k in etiquetas and v]
        if dichos:
            partes.append("Datos del cliente YA dados (NO los vuelvas a pedir): "
                          + "; ".join(dichos))

    if not partes:
        return ""
    return ("\n\n[ESTADO DE LA VENTA, establecido en turnos anteriores. Usalo, no lo "
            "vuelvas a pedir ni recalcular:\n- " + "\n- ".join(partes)
            + "\nSi el cliente cambia un producto o una cantidad, volve a llamar las "
            "herramientas; los precios y el envio salen SIEMPRE de las tools, nunca "
            "los inventes.]")
