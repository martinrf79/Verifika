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


def _patron_de_campo(campo: str):
    """El campo del catalogo como lo escribiria un vendedor."""
    partes = [re.escape(p) for p in _norm(campo).split("_") if p]
    if not partes:
        return None
    return re.compile(r"\b" + _UNEN.join(partes) + r"\b")


def campos_nombrados(texto: str, campos) -> list:
    """Los campos del catalogo que el texto nombra."""
    plano = _norm(texto)
    fuera = []
    for campo in campos or ():
        patron = _patron_de_campo(campo)
        if patron and patron.search(plano):
            fuera.append(str(campo))
    return fuera


def afirmo_sin_mirar(texto: str, tocados, tienda_id: str,
                     trace_id: str = "") -> list:
    """Los campos que la respuesta nombra y que el turno NUNCA tuvo delante."""
    try:
        from app.core.filtros_catalogo import campos_filtrables
        campos = set(campos_filtrables(tienda_id) or {})
    except Exception as e:  # noqa: BLE001 — sin registro no se juzga nada
        log.warning("guarda_estado_sin_campos", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")
        return []
    # LOS TOCADOS SE SACAN ANTES DE MIRAR EL TEXTO, y no despues: un campo
    # respaldado no tiene por que costar una busqueda en la respuesta.
    sin_respaldo = sorted(campos_nombrados(
        texto, campos - {str(t) for t in (tocados or ())}))
    if sin_respaldo:
        # EL RENGLON ES LA PIEZA. Sale con el campo y con cuantos campos tuvo el turno en la mano, que es lo
        # que permite leer el falso positivo: un turno que no busco nada y nombra un campo no es lo mismo que
        # uno que trajo diez fichas y nombro el unico que no miro.
        log.warning("afirmo_sin_mirar", trace_id=trace_id,
                    campos=sin_respaldo[:6], tocados=len(tocados or ()))
    return sin_respaldo


# QUE CAMPO SE CORRIGE, Y LA RESPUESTA ES: CUALQUIERA QUE LA FUENTE TENGA.


def para_corregir(sin_respaldo, tienda_id: str) -> tuple:
    """El campo que vale la pena devolverle al modelo, con lo que la fuente dice de el."""
    from app.core.filtros_catalogo import que_dice_la_fuente_de
    for campo in sin_respaldo or ():
        dice = que_dice_la_fuente_de(str(campo), tienda_id)
        if dice:
            return str(campo), dice
    return None, ""


def correccion_de_estado(texto: str, tocados, tienda_id: str,
                         trace_id: str = "") -> str:
    """EL BLOQUE QUE VUELVE AL MODELO cuando afirmo sobre un campo que no miro."""
    sin = afirmo_sin_mirar(texto, tocados, tienda_id, trace_id)
    if not sin:
        return ""
    campo, dice = para_corregir(sin, tienda_id)
    if not campo:
        return ""
    log.warning("correccion_de_estado", trace_id=trace_id, campo=campo)
    return (
        "CORRECCION DEL CODIGO, y es un dato de la fuente, no una opinion.\n"
        f"En lo que escribiste afirmaste sobre `{campo}`, y en este turno no lo "
        "consultaste ni una vez. La fuente SI lo tiene:\n"
        f"  {dice}\n"
        "Contesta con ese dato de la fuente, y si no alcanza para lo que "
        "pidio, deciselo y ofrecele buscarlo con esas palabras. Si volves a "
        "decir que no lo tenemos, le estas mintiendo al cliente.\n"
        "Y el resto del pedido se contesta IGUAL: los precios que ya volvieron, "
        "los envios que ya se cotizaron y la cuenta si la pidio. Una condicion "
        "que no se pueda cumplir se dice en un renglon y no cancela nada.")
