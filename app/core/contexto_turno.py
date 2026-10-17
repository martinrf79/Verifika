"""Context-var para multi-tenant: el orchestrator setea la tienda actual antes de llamar al agente, y todas las
tools/búsquedas la leen sin recibirla por parámetro."""
import os
from contextvars import ContextVar

from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
_settings = get_settings()

_current_tienda: ContextVar[str | None] = ContextVar("current_tienda", default=None)

# Destino del envio del request, ya categorizado (caba_gba | interior | None).
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


def tienda_por_defecto() -> str:
    """La tienda que este proceso sirve cuando todavia no hay contexto de turno: al importar un modulo, en tests
    sin turno, en scripts de banco o de ingesta."""
    configurada = _settings.TIENDA_ID
    base = os.path.join(os.path.dirname(__file__), "..", "..", "data", "clientes")
    try:
        carpetas = sorted(d for d in os.listdir(base)
                          if os.path.isdir(os.path.join(base, d)))
    except OSError as e:
        log.warning("data_clientes_ilegible", base=base,
                   error=f"{type(e).__name__}: {str(e)[:120]}")
        carpetas = []
    if configurada in carpetas:
        return configurada
    if len(carpetas) == 1:
        return carpetas[0]
    return configurada
