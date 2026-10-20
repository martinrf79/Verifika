"""GUARDAS DE SALIDA — las TRES cosas que no pueden depender del prompt."""
import re
import unicodedata

from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def business_name(tienda_id: str | None) -> str:
    """El nombre con el que el bot se presenta: el de la tienda si esta cargado
    en su config, el del entorno si no. Lo usan las dos guardas de identidad."""
    name = settings.BUSINESS_NAME
    if tienda_id:
        try:
            from app.storage.firestore_client import get_config
            stored = get_config("business_name", tienda_id=tienda_id)
            if stored:
                name = stored
        except Exception as e:  # noqa: BLE001 — se registra: con el nombre del
            # entorno en vez del de la tienda, la guarda de identidad se
            # presenta como otro negocio y nadie se entera.
            log.error("business_name_ilegible", tienda_id=str(tienda_id),
                      error=f"{type(e).__name__}: {str(e)[:120]}")
    return name


# ── 2. SALUDO Y AVISO DEL PRIMER MENSAJE ────────────────────────────────────
_RE_SALUDO_SOLVER = re.compile(
    r"^[¡!]*\s*(hola+|buen(as)?\s+(tardes|noches|d[ií]as?))\b[\s,.!:]*",
    re.IGNORECASE)

# Bienvenida REDUNDANTE del modelo en el turno 1: el codigo ya antepone el
# saludo oficial y el modelo ademas abre con "Bienvenido a X, soy tu asistente".
_RE_BIENVENIDA_SOLVER = re.compile(
    r"^(?:[¡!]\s*)?[^.!?\n]{0,80}?"
    r"(?:bienvenid[oa]s?\b|soy\s+(?:tu|su|el|la|un|una)\s+asistente|"
    r"qu[eé]\s+bueno\s+que\s+nos\s+(?:contactes|escribas)|"
    r"gracias\s+por\s+(?:contactarnos|escribirnos))"
    r"[^.!?\n]*[.!?]\s*",
    re.IGNORECASE)


def con_saludo_inicial(respuesta: str, business_name: str) -> str:
    """Primer mensaje de la charla: linea FIJA de saludo con el aviso de que es
    una herramienta automatica, y abajo la respuesta del turno."""
    cuerpo = _RE_SALUDO_SOLVER.sub("", (respuesta or "").strip(), count=1).strip()
    for _ in range(2):
        nuevo = _RE_BIENVENIDA_SOLVER.sub("", cuerpo, count=1).strip()
        if nuevo == cuerpo:
            break
        cuerpo = nuevo
    if cuerpo:
        cuerpo = cuerpo[0].upper() + cuerpo[1:]
    linea = linea_saludo(business_name)
    return linea + ("\n\n" + cuerpo if cuerpo else "")


def linea_saludo(business_name: str) -> str:
    """LA LINEA OBLIGATORIA del primer mensaje, en UNA sola definicion."""
    from app.core.guia_venta_prosa import mensaje
    return mensaje("saludo_inicial",
                   "¡Hola! Soy el asistente automático de {negocio}."
                   ).format(negocio=business_name)


# ── 3. LA GUARDA DE ESTADO — afirmar sobre un campo que el turno no miro ─────

# Los conectores que pueden aparecer entre las palabras de un campo cuando el modelo lo escribe en castellano:
# `pais_fabricacion` sale como "pais de fabricacion".
_UNEN = r"(?:\s+(?:de|del|la|el|en))*\s+"


# QUE CAMPO SE CORRIGE, Y LA RESPUESTA ES: CUALQUIERA QUE LA FUENTE TENGA.


