"""
GUARDAS DE SALIDA — las cinco guardas deterministas que el camino vivo perdio.

DE DONDE SALEN. Vivian dentro de `interprete_libre`, que era el camino vivo
hasta que el orchestrator paso al hub. Al cortar, se fueron con el modulo, igual
que los verificadores: quedaron escritas, con sus tests en verde, probando codigo
que ya no corria. Un test que no corre sobre el codigo de produccion no vale.

Se rescatan ACA, puras y sin dependencias del legado, para poder borrar
`interprete_libre` sin perder comportamiento. Las cinco:

  1. HONESTIDAD DE BOT. Si el cliente pregunta si habla con una maquina, la
     respuesta lo dice. El prompt solo no alcanza -en el banco el solver
     esquivaba la pregunta-, asi que el codigo antepone la verdad. Esto no es
     una mejora de venta, es lo minimo que le debemos al que escribe.
  2. SALUDO Y AVISO. El primer mensaje de la charla abre con una linea fija que
     dice que es un asistente automatico. Determinista, no depende del prompt, y
     va UNA sola vez en toda la conversacion. Ademas recorta el saludo y la
     bienvenida que el modelo escribe por su cuenta, para no saludar dos veces.
  3. RESPUESTA HUECA. Una respuesta vacia, o corta y sin ningun dato ni pregunta
     que mueva la charla, no contesta nada. Las coletillas enlatadas no cuentan
     como sustancia: en real salio un turno que era SOLO la invitacion a avanzar.
  4. PRESUPUESTO SIN MODELOS. El cliente pide "2 teclados y 3 mouse" sin decir
     cuales y el modelo arma igual un presupuesto inventado, eligiendo el
     producto que se le ocurre. Caso real de WhatsApp del 8-jul. Si la respuesta
     trae un total, se reemplaza por opciones REALES con stock por categoria.
  5. FALLBACK CON CURADA. Cuando una guarda bloquea el turno, el enlatado
     generico es la peor salida si el cliente pregunto una politica que SI
     tenemos escrita: '¿como es la seña?' terminaba en 'no tengo esa
     informacion'. Si el ruteo matchea un tema curado, sale la respuesta oficial.

LO QUE NO SE RESCATO, y por que. Tres guardas del camino viejo quedaron sin
sentido con el diseno atado, no por descuido:
  - la del "mas barato divergente" y la de confirmacion del criterio: el
    criterio ahora lo traduce el interprete a un enum y `universo_productos`
    computa el minimo con stock por codigo; el solver solo puede referenciar
    ids del universo, asi que la divergencia que vigilaban es imposible por
    construccion.
  - el estampado de productos: `renderizar` estampa cada linea desde la fuente.
  - el destino unico por regex: lo resuelven `coercionar_destinos` y la tabla
    de CP del interpretador.
"""
import re
import unicodedata

from app.config import get_settings
from app.core.pedido_helpers import _linea_producto
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
    r"(?:bienvenid[oa]s?\b|soy\s+(?:tu|su|el|la)\s+asistente|"
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
    linea = (f"¡Hola! Soy el asistente automático de {business_name}. "
             "Te ayudo con precios, stock y envíos al instante.")
    return linea + ("\n\n" + cuerpo if cuerpo else "")


# ── 3. RESPUESTA HUECA ──────────────────────────────────────────────────────
_RE_SOLO_SALUDO = re.compile(
    r"^[\s¡!¿?.,]*(hola+|buenas+(\s+(tardes|noches))?|buen\s+d[ií]as?|"
    r"buenos\s+d[ií]as|que\s+tal|como\s+va|hey|hi)[\s!.,¿?]*$",
    re.IGNORECASE)


def mensaje_con_contenido(mensaje: str) -> bool:
    """True si el mensaje trae algo mas que un saludo pelado. Un 'hola' solo NO
    exige sustancia -el saludo de vuelta alcanza-; 'hola, busco una notebook' SI."""
    m = _norm(mensaje).strip()
    return bool(m) and not _RE_SOLO_SALUDO.match(m)


def _sin_coletillas(texto: str) -> str:
    """Saca las coletillas enlatadas para medir la sustancia real: una respuesta
    que es SOLO la invitacion a avanzar no contesta nada."""
    t = texto or ""
    try:
        from app.core.leads import PREGUNTA_CIERRE
        t = t.replace(PREGUNTA_CIERRE, " ")
    except Exception:
        pass
    # La invitacion a avanzar la redacta el solver, no es un enlatado fijo: se
    # descuenta generico una ultima linea que sea invitacion de cierre -pregunta
    # larga, 40 a 90 caracteres-. Una pregunta corta legitima ("¿Que buscas?")
    # queda: mueve la charla, es sustancia.
    lineas = [l for l in t.splitlines() if l.strip()]
    if lineas and "?" in lineas[-1] and 40 < len(lineas[-1].strip()) < 90:
        lineas = lineas[:-1]
    return "\n".join(lineas).strip()


# ACUSE DE RECIBO puro: el turno que no contesta nada, solo asiente. Es lo que
# esta guarda tiene que cazar, y nada mas que eso.
_RE_SOLO_ACUSE = re.compile(
    r"^(?:[\s¡!.,]*(?:claro|perfecto|dale|listo|genial|buenisimo|barbaro|"
    r"joya|ok|okey|entiendo|entendido|por supuesto|obvio|de una|excelente|"
    r"muy bien|bien|si|sip|correcto|exacto|dale si)[\s¡!.,:;-]*)+$",
    re.IGNORECASE)


# El arranque que ANUNCIA informacion. Si la frase es solo esto y nada mas, lo
# que quedo es el residuo de una poda, no una respuesta.
_RE_ANUNCIO_VACIO = re.compile(
    r"^[\s¡!¿?]*(?:[^.!?\n]{0,25}?\b)?"
    r"te\s+(?:cuento|comento|explico|paso|digo|aviso)\b",
    re.IGNORECASE)


def sin_sustancia(respuesta: str, hubo_datos: bool = False) -> bool:
    """True si la respuesta no CONTESTA nada: vacia, un acuse de recibo pelado
    ("Claro.", "Perfecto, dale.") o un resto de dos palabras.

    POR QUE NO SE MIDE POR LARGO, que era como estaba. La regla vieja daba
    hueca a lo que midiera menos de 60 caracteres y no tuviera cifra ni signo
    de pregunta. Con eso, "Tenemos mouse, teclados y notebooks." -36
    caracteres, una respuesta perfectamente buena- se reemplazaba por el
    enlatado: la guarda contra respuestas vacias borraba respuestas buenas. En
    el camino viejo casi no se notaba porque la prosa libre siempre era larga;
    con fragmentos, contestar corto y bien es lo normal.

    El criterio ahora es cualitativo y el error se inclina a propósito para el
    lado seguro: ante la duda NO se poda. Es preferible dejar pasar un turno
    flojo que borrar uno bueno y contestarle al cliente que no tenemos el dato.

    `hubo_datos`: si el turno emitio un fragmento de dato -producto, ficha,
    FAQ, criterio, calculo, envio- la respuesta contesta algo por construccion
    y no se juzga.
    """
    r = _sin_coletillas((respuesta or "").strip())
    if not r:
        return True
    if hubo_datos:
        return False
    if _RE_SOLO_ACUSE.match(r):
        return True
    tiene_dato = bool(re.search(r"[\d$?¿]", r))
    # ANUNCIO SIN ENTREGA: el residuo tipico de una poda. "Te cuento," "Te
    # cuento como nos manejamos": promete la informacion y ahi termina. Es el
    # caso que hay que cazar, y se caza por lo que la frase HACE -anunciar- y
    # no por cuanto mide. Medir por largo confundia esto con "Si, hacemos
    # envios a todo el pais", que contesta perfecto en 34 caracteres.
    if not tiene_dato and len(r) < 60 and _RE_ANUNCIO_VACIO.match(r):
        return True
    # resto muy corto y sin dato ni pregunta: no llega a ser una respuesta.
    return len(r) < 25 and not tiene_dato


# ── 4. PRESUPUESTO SIN MODELOS ──────────────────────────────────────────────
_RE_PRESUPUESTO_EN_TEXTO = re.compile(
    r"\bpresupuesto\b|\btotal\b[^\n]{0,20}\$", re.IGNORECASE)


def forzar_opciones_si_presupuesto(respuesta: str, cats_pedido: list,
                                   tienda_id: str) -> str | None:
    """El cliente pidio N unidades por CATEGORIA sin decir modelos y el modelo
    armo igual un presupuesto, eligiendo productos por su cuenta -con un teclado
    al precio de una notebook, caso real del 8-jul-. Se reemplaza por las
    opciones reales con stock. None si la respuesta no armo presupuesto."""
    if not cats_pedido or not respuesta:
        return None
    if not _RE_PRESUPUESTO_EN_TEXTO.search(respuesta):
        return None
    from app.core.guia_pedido import opciones_por_categoria
    bloques = []
    for n, cat in cats_pedido:
        ops = opciones_por_categoria(cat, tienda_id)
        if not ops:
            continue
        lineas = "\n".join("- " + _linea_producto(p) for p in ops)
        bloques.append(f"Para {'las' if n > 1 else 'la'} {n} de {cat}, "
                       f"opciones con stock:\n{lineas}")
    if not bloques:
        return None
    return ("¡Buena compra la que estás armando! Para pasarte el precio exacto "
            "necesito que me digas los modelos.\n\n"
            + "\n\n".join(bloques)
            + "\n\n¿Qué modelo elegís de cada categoría? Con eso te armo el "
            "total con los envíos al instante.")


# ── 5. FALLBACK CON CURADA ──────────────────────────────────────────────────
def fallback_o_curada(mensaje: str, interp, tienda_id: str,
                      trace_id: str | None = None) -> str:
    """Cuando una guarda BLOQUEA la respuesta, el enlatado generico es la peor
    salida si el cliente pregunto una politica que SI tenemos escrita. Si el
    ruteo matchea un tema curado, sale esa respuesta oficial."""
    try:
        from app.core.curadas import bloque_curado_por_mensaje
        bc = bloque_curado_por_mensaje(mensaje, interp, tienda_id)
        if bc:
            log.info("guarda_fallback_curada", trace_id=trace_id, tema=bc[0])
            return bc[1]
    except Exception as e:
        log.warning("guarda_fallback_curada_error", trace_id=trace_id,
                    error=str(e)[:120])
    return settings.VERIFIKA_FALLBACK_MESSAGE
