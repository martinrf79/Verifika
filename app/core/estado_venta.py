"""ESTADO DE VENTA — fuente unica de verdad del turno, accesible por todas las etapas."""
from contextvars import ContextVar
from typing import Any

_current_estado: ContextVar[dict | None] = ContextVar("current_estado", default=None)

# Localidades que cotizar_envio clasifico con exito en este turno, EN ORDEN.
_envio_localidades: ContextVar[list | None] = ContextVar(
    "envio_localidades", default=None)

# Product_id que las tools DEVOLVIERON este turno (search, details, catalogo, calculadora): son los ids
# CERTIFICADOS del turno.
_ids_certificados: ContextVar[set | None] = ContextVar(
    "ids_certificados", default=None)


def set_current_estado(estado: dict | None, inicio_turno: bool = True):
    """Setea el estado de venta del request. Al ARRANCAR el turno (default) limpia las localidades cotizadas del
    turno anterior."""
    _current_estado.set(estado)
    if inicio_turno:
        _envio_localidades.set([])
        _ids_certificados.set(set())


def set_envio_localidad(localidad: str | None):
    """Suma la localidad que cotizar_envio clasifico bien este turno."""
    loc = (localidad or "").strip()
    if not loc:
        return
    locs = [l for l in (_envio_localidades.get() or [])
            if l.lower() != loc.lower()]
    locs.append(loc)
    _envio_localidades.set(locs)


def get_envio_localidades() -> list[str]:
    """Todas las localidades cotizadas con exito este turno, en orden."""
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
    """Arma el objeto estado del turno desde la conversacion persistida y el lead activo."""
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
        # MEMORIA NEGATIVA (5-ago): lo que el cliente saco del pedido.
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
        # ANCLA del producto que el cliente eligio y pidio guardar ("me gusta X, anotalo"). {id, nombre,
        # precio} o {}.
        "producto_anotado": (conv.get("producto_anotado")
                             if isinstance(conv.get("producto_anotado"), dict)
                             else {}) or {},
        # PREFERENCIAS del cliente (16-jul): exclusiones por origen/marca, tope de presupuesto y uso previsto,
        # leidas por el interprete y STICKY entre turnos como la provincia.
        "preferencias": (conv.get("preferencias_cliente")
                         if isinstance(conv.get("preferencias_cliente"), dict)
                         else {}) or {},
        # GRUPOS DE ENVIO declarados por el cliente (que item va a cada destino): memoria de la charla, el
        # reprecio del cierre los reusa para el umbral de gratis por paquete (20-jul, guion 48).
        "grupos_envio": (conv.get("grupos_envio")
                         if isinstance(conv.get("grupos_envio"), list)
                         else []) or [],
    }
