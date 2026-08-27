"""
Context-var para multi-tenant: el orchestrator setea la tienda actual antes
de llamar al agente, y todas las tools/búsquedas la leen sin recibirla por parámetro.

Esto evita modificar las firmas de las funciones (que el LLM ve via JSON schema).
El LLM nunca elige la tienda — el backend la resuelve por phone_number_id.
"""
import os
from contextvars import ContextVar

from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
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
    """Devuelve la tienda actual; si no se seó, la default del settings."""
    tid = _current_tienda.get()
    if tid:
        return tid
    return _settings.TIENDA_ID


def tienda_por_defecto() -> str:
    """La tienda que este proceso sirve cuando todavia no hay contexto de
    turno: al importar un modulo, en tests sin turno, en scripts de banco o
    de ingesta. Prioridad: la que dice la configuracion (`TIENDA_ID`, que
    cada deploy fija por secreto -regla #2 de CLAUDE.md, el LLM nunca elige
    tienda-); si esa carpeta no existe -pasa en local/tests sin la variable
    seteada-, la UNICA carpeta que haya bajo data/clientes, que es
    exactamente lo que hoy corre en produccion. Si hay mas de una y la
    configurada no matchea ninguna, se devuelve la configurada igual: el
    archivo faltante lo cuenta el log de quien arma el corpus, no un nombre
    pisado a mano aca.

    UNICO lugar del repo que auto-detecta la tienda por defecto -antes cada
    modulo (`guia_venta_prosa.py`, `compatibilidad.py`, `fuente_producto.py`,
    `coherencia_datos.py`) llevaba su propia copia con un nombre de tienda
    literal escrito a mano; FICHA 25, 26-ago-2026."""
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
