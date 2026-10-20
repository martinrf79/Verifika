"""ESTADO DE VENTA — fuente unica de verdad del turno, accesible por todas las etapas."""
from contextvars import ContextVar

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
