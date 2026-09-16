"""
GUARDAS DE SALIDA — las TRES cosas que no pueden depender del prompt.

De las cinco que vivian aca quedaron dos, y no por recorte de tiempo: con el hub
de herramientas las otras tres perdieron sentido. La tercera es del 16-sep y es
de otra familia: las dos de abajo ponen algo que falta, esa MIRA lo que el
modelo afirmo.

  1. HONESTIDAD DE BOT. Si el cliente pregunta si habla con una maquina, la
     respuesta lo dice. El prompt solo no alcanzo nunca -en el banco el modelo
     esquivaba la pregunta-, asi que el codigo antepone la verdad. No es una
     mejora de venta, es lo minimo que le debemos al que escribe.
  2. SALUDO Y AVISO. El primer mensaje de la charla abre con una linea fija que
     avisa que es un asistente automatico. Es una obligacion, no un criterio de
     redaccion, asi que la pone el codigo y va UNA sola vez. Ademas recorta el
     saludo que el modelo escribe por su cuenta, para no saludar dos veces ni
     abrir con "hola" en el turno cinco.
  3. LA GUARDA DE ESTADO. Si la respuesta afirma sobre un campo del catalogo
     que el turno nunca tuvo delante, queda el renglon. NACE MUDA: mira y no
     toca. El caso y el motivo, abajo, arriba de la funcion.

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
        except Exception as e:  # noqa: BLE001 — se registra: con el nombre del
            # entorno en vez del de la tienda, la guarda de identidad se
            # presenta como otro negocio y nadie se entera.
            log.error("business_name_ilegible", tienda_id=str(tienda_id),
                      error=f"{type(e).__name__}: {str(e)[:120]}")
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
    from app.core.guia_venta_prosa import mensaje
    linea = mensaje("honestidad_bot",
                    "Sí, te lo digo derecho: soy el asistente automático de "
                    "{negocio}.").format(negocio=business_name)
    return (linea + "\n\n" + (respuesta or "").strip()).strip()


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
    from app.core.guia_venta_prosa import mensaje
    return mensaje("saludo_inicial",
                   "¡Hola! Soy el asistente automático de {negocio}."
                   ).format(negocio=business_name)


# ── 3. LA GUARDA DE ESTADO — afirmar sobre un campo que el turno no miro ─────
#
# EL CASO, MEDIDO DOS VECES EN WHATSAPP, el 15 y el 16-sep-2026: el bot contesto
# que no tiene el pais de fabricacion. El campo esta cargado en 880 de 880
# productos y viaja en el tablero, en la leyenda, con sus cinco valores. No lo
# consulto y contesto igual.
#
# POR QUE NO ES LA GUARDA DE `numeros`, que ya existe y funciona: esa mira
# CIFRAS. "No tenemos ese dato" no lleva ninguna, asi que pasa entera. La cifra
# inventada tiene candado desde el 11-sep; la afirmacion inventada no tiene
# ninguno.
#
# LA CONDICION ES DE ESTADO Y NO DE VOCABULARIO, y esa es la regla 4 de la FICHA
# 55 §5. No se persigue la frase: perseguir prosa con una lista de frases ya
# fracaso tres veces en este repo —fueron 4 nodos, despues 18, despues 46—. Lo
# que se mira es un NOMBRE DE CAMPO, que es un token verificable igual que una
# cifra: la lista sale de `campos_filtrables` sobre la fuente viva, no la
# escribe nadie, y no crece con el catalogo sino con la variedad. Es el mismo
# argumento que ya sostiene la leyenda del tablero.
#
# NACE MUDA (FICHA 55 §4.3 y §5.2). Escribe su renglon y no toca una sola
# respuesta. Recien cuando la pelicula muestre que el renglon coincide con lo
# que se lee en la charla real se decide si frena, y con que recorte: hoy un
# campo de una palabra —`color`, `marca`, `stock`— aparece en cualquier
# respuesta legitima, y "te lo puedo buscar por color" no es una afirmacion
# sobre la fuente. Frenar con eso adentro seria cambiar un defecto por otro mas
# caro. Asi nacio el indice viejo y asi se revierte gratis.

# Los conectores que pueden aparecer entre las palabras de un campo cuando el
# modelo lo escribe en castellano: `pais_fabricacion` sale como "pais de
# fabricacion". Es un conjunto CERRADO de cinco preposiciones y articulos, la
# gramatica minima para unir dos sustantivos, y no crece: no es una lista de
# frases, que es lo que este repo tiene prohibido.
_UNEN = r"(?:\s+(?:de|del|la|el|en))*\s+"


def _patron_de_campo(campo: str):
    """El campo del catalogo como lo escribiria un vendedor. `garantia_meses`
    pega con "garantia meses" y con "garantia en meses"; `color`, con "color".

    Se compara sobre el texto NORMALIZADO —minusculas y sin acentos— asi que
    "país de fabricación" y "pais de fabricacion" son lo mismo."""
    partes = [re.escape(p) for p in _norm(campo).split("_") if p]
    if not partes:
        return None
    return re.compile(r"\b" + _UNEN.join(partes) + r"\b")


def campos_nombrados(texto: str, campos) -> list:
    """Los campos del catalogo que el texto nombra. Determinista y sin
    ranking: o el nombre esta, o no esta. Nada de aparear por palabras
    compartidas, que es la enfermedad que el MAPA_CABLEADO ya tiene numerada
    cuatro veces —D3, D4, D6 y D16—."""
    plano = _norm(texto)
    fuera = []
    for campo in campos or ():
        patron = _patron_de_campo(campo)
        if patron and patron.search(plano):
            fuera.append(str(campo))
    return fuera


def afirmo_sin_mirar(texto: str, tocados, tienda_id: str,
                     trace_id: str = "") -> list:
    """Los campos que la respuesta nombra y que el turno NUNCA tuvo delante.

    `tocados` son los campos que el turno SI miro, y se juntan de los dos
    lados por los que un campo puede llegarle al modelo: los que alguna
    consulta uso como condicion u orden, y los que vinieron cargados en las
    fichas que volvieron. Un campo que entro por cualquiera de los dos esta
    respaldado y no se cuenta.

    DEVUELVE LA LISTA Y NO TOCA EL TEXTO. La pieza nace muda a proposito; el
    motivo entero esta arriba.
    """
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
        # EL RENGLON ES LA PIEZA. Sale con el campo y con cuantos campos tuvo
        # el turno en la mano, que es lo que permite leer el falso positivo:
        # un turno que no busco nada y nombra un campo no es lo mismo que uno
        # que trajo diez fichas y nombro el unico que no miro.
        log.warning("afirmo_sin_mirar", trace_id=trace_id,
                    campos=sin_respaldo[:6], tocados=len(tocados or ()))
    return sin_respaldo


# CUANTAS PALABRAS TIENE QUE TENER UN CAMPO PARA QUE SE LO CORRIJA, y este
# numero es todo el recorte entre ver y actuar.
#
# La guarda VE todos los campos: ese es el renglon y no se toca, porque es el
# numero con el que se decide. Lo que se CORRIGE es un subconjunto, y el corte
# es de forma: un campo de una palabra —`color`, `marca`, `stock`, `modelo`,
# `peso`— es una palabra comun del castellano comercial, y "te lo puedo buscar
# por color" no es una afirmacion sobre la fuente. Uno de dos palabras
# —`pais_fabricacion`, `memoria_video`, `garantia_meses`— es jerga de la
# fuente: si el modelo lo escribe es porque esta hablando de ESE campo.
#
# ES UN CORTE DE FORMA Y NO DE VOCABULARIO, que es lo que lo hace admisible
# bajo la regla 4 de la FICHA 55: no hay una lista de campos elegidos a mano
# que alguien tenga que mantener. Se cuenta cuantas partes tiene el nombre que
# la fuente ya le puso.
PALABRAS_PARA_CORREGIR = 2

# Cuantas correcciones se hacen por turno. UNA. Cada una cuesta una vuelta al
# modelo, y una segunda seria perseguir al modelo hasta que diga lo que
# queremos, que es otra cosa y no se hace.
TOPE_CORRECCIONES = 1


def para_corregir(sin_respaldo, tienda_id: str) -> tuple:
    """El campo que vale la pena devolverle al modelo, con lo que la fuente
    dice de el. `(None, "")` si no hay ninguno.

    DOS FILTROS Y NINGUNO MAS. Que el nombre tenga varias partes, que es el
    recorte de arriba. Y que la fuente TENGA algo escrito de ese campo: si no
    tiene, la negacion del modelo era correcta y no hay nada que corregir. Ese
    segundo filtro no es cosmetico —es lo que evita que el codigo le discuta al
    modelo una verdad—.
    """
    from app.core.filtros_catalogo import que_dice_la_fuente_de
    for campo in sin_respaldo or ():
        if len(str(campo).split("_")) < PALABRAS_PARA_CORREGIR:
            continue
        dice = que_dice_la_fuente_de(str(campo), tienda_id)
        if dice:
            return str(campo), dice
    return None, ""


def correccion_de_estado(texto: str, tocados, tienda_id: str,
                         trace_id: str = "") -> str:
    """EL BLOQUE QUE VUELVE AL MODELO cuando afirmo sobre un campo que no miro.
    Cadena vacia si no hay nada que corregir.

    POR QUE DEVOLVER EL DATO Y NO TIRAR LA RESPUESTA. Tirarla deja al cliente
    sin contestar por una frase de mas, que es un remedio peor: la guarda de
    plata puede hacerlo porque una cifra inventada contamina el mensaje entero,
    y una afirmacion sobre un campo no. Y editar la frase esta prohibido: la
    prosa es del modelo, y cortarla por palabras es el solver de fragmentos que
    se borro el 2-ago.

    ASI QUE SE HACE LO QUE LA FICHA 55 §1-bis YA DECIDIO: la negacion la escribe
    el codigo y el modelo la COPIA. El mecanismo no es nuevo —es el hueco de
    valor, que ya funciona y aparecio solo en la tanda del 13-sep— aplicado a lo
    que el modelo AFIRMA en vez de a lo que BUSCA.

    EL CASO, medido en WhatsApp el 16-sep-2026 a las 12:05 UTC. El cliente pidio
    seis productos con "las menos partes chinas posibles". El modelo mando
    cuatro consultas SIN una sola condicion —tiro la restriccion entera— y
    contesto "no contamos con informacion sobre el pais de fabricacion", con el
    campo cargado en 880 de 880 y con sus cinco valores en el tablero que el
    mismo tenia delante. Y esa negacion falsa se llevo puesto el resto del
    turno: no dio un solo precio de las veinte fichas que habia traido, no pidio
    la cuenta del setenta treinta, y no marco que el cliente nombro un teclado
    que no habia pedido. **No fueron cuatro defectos: fue uno, y los otros tres
    colgaban de el.**
    """
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
        "Si el cliente pidio algo sobre ese campo, pedilo por el motor con una "
        "condicion y con una de esas palabras. Si volves a decir que no lo "
        "tenemos, le estas mintiendo al cliente.\n"
        "Y el resto del pedido se contesta IGUAL: los precios que ya volvieron, "
        "los envios que ya se cotizaron y la cuenta si la pidio. Una condicion "
        "que no se pueda cumplir se dice en un renglon y no cancela nada.")
