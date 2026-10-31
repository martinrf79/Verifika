"""HUECOS DE FUENTE — cada dato que el cliente pide y la fuente no tiene, al log, para verlo con `produccion.py`.

El 31-oct se saco el anillo en memoria y su resumen: nadie los leia, ni el bot, ni los tests, ni el banco."""
from app.logger import get_logger

log = get_logger(__name__)


def anotar(tienda_id: str, tipo: str, campo: str, pidio: str) -> None:
    """Deja la marca de un hueco. Nunca lanza: un contador no puede voltear una venta."""
    try:
        log.info("hueco_de_fuente", tienda_id=str(tienda_id or ""), tipo=str(tipo or ""), campo=str(campo or ""),
                 pidio=str(pidio or "")[:120])
    except Exception:
        pass
