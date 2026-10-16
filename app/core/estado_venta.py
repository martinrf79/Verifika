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
from contextvars import ContextVar
from typing import Any

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


def set_current_estado(estado: dict | None, inicio_turno: bool = True):
    """Setea el estado de venta del request. Al ARRANCAR el turno (default)
    limpia las localidades cotizadas del turno anterior. Un re-seteo a mitad
    de turno (el generador lo hace para sus tools) va con inicio_turno=False:
    antes borraba las cotizadas del propio turno y la memoria de destinos
    nunca persistia — el envio se caia del total al confirmar (agujero del
    12-jul, cerrado 20-jul con el guion 48)."""
    _current_estado.set(estado)
    if inicio_turno:
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


def get_envio_localidades() -> list[str]:
    """Todas las localidades cotizadas con exito este turno, en orden. Las lee
    calculate_total para cobrar cada destino de un multi-destino con su tarifa."""
    return list(_envio_localidades.get() or [])


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
        # MEMORIA NEGATIVA (5-ago): lo que el cliente saco del pedido. Los
        # demas campos guardan lo que quiere; este es el unico que guarda lo
        # que dijo que NO, para que un producto retractado no reaparezca
        # cuando la charla se comprime y la negacion se pierde.
        "descartados": conv.get("descartados") or [],
        "presupuesto": (conv.get("ultimo_presupuesto") or "").strip(),
        "localidad_envio": (conv.get("ultima_localidad") or "").strip(),
        "localidades_envio": conv.get("ultimas_localidades") or [],
        "provincia_envio": (conv.get("provincia_envio") or "").strip(),
        "criterio": (conv.get("criterio_cliente") or "").strip(),
        "datos_cliente": datos_cliente,
        # Memoria larga: el resumen acumulado de la charla que ya salio del
        # historial vivo (turnos viejos fundidos). Contexto, no fuente de datos.
        "resumen_charla": (conv.get("summary") or "").strip(),
        # ANCLA del producto que el cliente eligio y pidio guardar ("me gusta
        # X, anotalo"). {id, nombre, precio} o {}. Resuelve "el que te dije
        # al principio" sin adivinar (falla madre del banco 11-jul).
        "producto_anotado": (conv.get("producto_anotado")
                             if isinstance(conv.get("producto_anotado"), dict)
                             else {}) or {},
        # PREFERENCIAS del cliente (16-jul): exclusiones por origen/marca, tope
        # de presupuesto y uso previsto, leidas por el interprete y STICKY entre
        # turnos como la provincia. Las consume el generador para filtrar el
        # universo por construccion.
        "preferencias": (conv.get("preferencias_cliente")
                         if isinstance(conv.get("preferencias_cliente"), dict)
                         else {}) or {},
        # GRUPOS DE ENVIO declarados por el cliente (que item va a cada
        # destino): memoria de la charla, el reprecio del cierre los reusa
        # para el umbral de gratis por paquete (20-jul, guion 48).
        "grupos_envio": (conv.get("grupos_envio")
                         if isinstance(conv.get("grupos_envio"), list)
                         else []) or [],
    }
