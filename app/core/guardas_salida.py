"""
GUARDAS DE SALIDA — las DOS unicas cosas que no pueden depender del prompt.

De las cinco que vivian aca quedaron dos, y no por recorte de tiempo: con el hub
de herramientas las otras tres perdieron sentido.

  1. HONESTIDAD DE BOT. Si el cliente pregunta si habla con una maquina, la
     respuesta lo dice. El prompt solo no alcanzo nunca -en el banco el modelo
     esquivaba la pregunta-, asi que el codigo antepone la verdad. No es una
     mejora de venta, es lo minimo que le debemos al que escribe.
  2. SALUDO Y AVISO. El primer mensaje de la charla abre con una linea fija que
     avisa que es un asistente automatico. Es una obligacion, no un criterio de
     redaccion, asi que la pone el codigo y va UNA sola vez. Ademas recorta el
     saludo que el modelo escribe por su cuenta, para no saludar dos veces ni
     abrir con "hola" en el turno cinco.

LAS QUE SE BORRARON el 2-ago, con su motivo:
  - RESPUESTA HUECA y ANUNCIO SIN CONTENIDO: juzgaban el texto DESPUES de
    escrito, midiendo largo y coletillas. Eran la capa que corrige al modelo, que
    es justo lo que el diseno nuevo saca: si la herramienta trajo el dato, esta
    en el JSON delante del modelo; si no lo trajo, la respuesta honesta ES corta.
  - PRESUPUESTO SIN MODELOS: ya se habia borrado el 29-jul por romper una charla
    real; su fallback vivia aca.
  - FALLBACK CON CURADA: existia para cuando una guarda bloqueaba el turno. Sin
    guardas que bloqueen, no hay turno que rescatar. La politica curada sale
    ahora por la herramienta `consultar_temas`, que es su lugar.
"""
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
        except Exception:
            pass
    return name


# ── 1. HONESTIDAD DE BOT ────────────────────────────────────────────────────
# Pregunta directa de IDENTIDAD ("sos un robot?", "con quien hablo?").
_RE_PREGUNTA_BOT = re.compile(
    r"\bsos\s+(?:un\s+)?(?:bot|robot|humano|una\s+maquina|una\s+ia|real)\b"
    r"|\beres\s+(?:un\s+)?(?:bot|robot|humano)\b"
    r"|\bhablo\s+con\s+(?:un\s+)?(?:bot|robot|humano|una\s+persona|una\s+maquina)\b"
    r"|\bcon\s+quien\s+(?:hablo|estoy\s+hablando)\b"
    r"|\bme\s+atiende\s+(?:un\s+)?(?:bot|robot|una\s+maquina)\b",
    re.IGNORECASE)


def asegurar_honestidad_bot(mensaje: str, respuesta: str,
                            business_name: str) -> str:
    """Si preguntan si es un bot y la respuesta no lo dice, se antepone la
    verdad. No toca las respuestas que ya la dicen."""
    if not _RE_PREGUNTA_BOT.search(_norm(mensaje)):
        return respuesta
    r = _norm(respuesta)
    if ("asistente automatico" in r or "asistente virtual" in r
            or "soy un bot" in r or "soy un robot" in r):
        return respuesta
    return (f"Sí, te lo digo derecho: soy el asistente automático de "
            f"{business_name}.\n\n" + (respuesta or "").strip()).strip()


# ── 2. SALUDO Y AVISO DEL PRIMER MENSAJE ────────────────────────────────────
# Saludo que el modelo escribe al arranque de SU texto: se recorta cuando el
# codigo antepone el oficial. Solo saludos inequivocos; "buenas" pelado NO
# matchea, para no comerse un "Buenas noticias...".
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


# Aperturas de saludo a mitad de charla, mas anchas que las del turno 1. Estas
# EXIGEN un cierre de puntuacion, para no comerse una frase legitima: "¡Qué tal!"
# se recorta, "Qué tal te parece este mouse" no.
_RE_SALUDO_MEDIO = re.compile(
    r"^[¡!]*\s*(?:hola+|buen(?:as)?\s+(?:tardes|noches|d[ií]as?)|"
    r"qu[eé]\s+tal|c[oó]mo\s+(?:va|and[aá]s|est[aá]s)|"
    r"buenas)\s*[!.,:¡]+\s*",
    re.IGNORECASE)


def sin_saludo_del_modelo(respuesta: str) -> str:
    """Recorta el saludo que el modelo escribe por su cuenta a mitad de charla.

    En el turno 1 el saludo lo pone el CODIGO (con_saludo_inicial, abajo) y ahi
    se recorta el del modelo para no saludar dos veces. Del turno 2 en adelante
    no se recortaba nada, y el modelo abre igual: "¡Hola! Entiendo
    perfectamente...", "¡Qué tal! Te entiendo..." en el turno 2, 3 y 5 (banco
    29-jul, guiones 03 y 54). Un vendedor no te saluda cinco veces en la misma
    charla; suena a bot y es de lo que Martin viene marcando hace meses.
    """
    cuerpo = _RE_SALUDO_MEDIO.sub("", (respuesta or "").strip(), count=1).strip()
    if not cuerpo:
        return respuesta
    if cuerpo != (respuesta or "").strip():
        cuerpo = cuerpo[0].upper() + cuerpo[1:]
    return cuerpo


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
    """LA LINEA OBLIGATORIA del primer mensaje, en UNA sola definicion.

    LA OBLIGACION ES DECIR QUE ES UN BOT, NO VENDER EL SERVICIO. La segunda
    oracion que traia -"Te ayudo con precios, stock y envíos al instante"- eran
    48 caracteres de folleto en el mensaje donde el cliente todavia no pregunto
    nada, y encima abajo viene la respuesta que YA le da precios, stock y
    envios. Martin la marco como lo primero que sobra (7-ago). Lo que no se
    toca es el aviso de que es automatico: eso es una obligacion.

    ES UNA FUNCION Y NO TEXTO SUELTO ADENTRO porque cualquier cosa que decida
    sobre el mensaje final tiene que poder preguntar cual es la linea
    obligatoria, sin volver a escribirla. Escrita en dos lados se despegarian, y
    esa es la falla que este repo ya pago dos veces -el patron de la poda el
    31-jul, la regex del reparto el 6-ago-."""
    return f"¡Hola! Soy el asistente automático de {business_name}."
