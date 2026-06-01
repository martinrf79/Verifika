"""
Context-var para multi-tenant: el orchestrator setea la tienda actual antes
de llamar al agente, y todas las tools/búsquedas la leen sin recibirla por parámetro.

Esto evita modificar las firmas de las funciones (que el LLM ve via JSON schema).
El LLM nunca elige la tienda — el backend la resuelve por phone_number_id.
"""
from contextvars import ContextVar
from app.config import get_settings

_settings = get_settings()

_current_tienda: ContextVar[str | None] = ContextVar("current_tienda", default=None)

# Destino del envio del request, ya categorizado (caba_gba | interior | None).
# Lo resuelve el backend por keywords del mensaje, igual que la tienda: el LLM
# no lo elige. La calculadora defensiva lo usa para quedarse con un solo envio
# cuando el modelo manda dos conceptos distintos. None = sin destino claro.
_current_destino: ContextVar[str | None] = ContextVar("current_destino", default=None)


def set_current_tienda(tienda_id: str | None):
    """Setea la tienda actual del request. Llamado por el orchestrator."""
    _current_tienda.set(tienda_id)


def get_current_tienda() -> str:
    """Devuelve la tienda actual; si no se seteó, la default del settings."""
    tid = _current_tienda.get()
    if tid:
        return tid
    return _settings.TIENDA_ID


def set_current_destino(categoria: str | None):
    """Setea la categoria de destino del request (caba_gba | interior | None)."""
    _current_destino.set(categoria)


def get_current_destino() -> str | None:
    """Devuelve la categoria de destino actual, o None si no se resolvio."""
    return _current_destino.get()
