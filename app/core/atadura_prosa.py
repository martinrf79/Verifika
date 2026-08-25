"""LA ATADURA DE LA PROSA — el segundo eje, el que NO es plata.

EL HUECO QUE CIERRA. El sistema ya tenia UNA atadura y funciona: la de los
NUMEROS de plata. El bloque de la cuenta lo escribe el codigo y se pega tal
cual, y `_sin_plata_inventada` borra todo peso que no haya calculado una
herramienta. Para la plata la separacion entre lo determinista y lo generado no
es una promesa del prompt: es fisica.

Fuera de la plata no habia NADA. Cuando el bot dice "pesa 144 gramos y tiene
garantia de doce meses", hasta hoy nadie verificaba de donde salio. La unica
guardia que miraba afirmaciones, `_sin_afirmar_sobre_el_catalogo`, caza frases
UNIVERSALES -"ninguno del catalogo cumple"- y una spec inventada de un producto
le pasa por al lado. Ahi vive la alucinacion que queda.

COMO SE ATA, y por que asi. Se le pide al REDACTOR que envuelva cada dato
concreto que afirma en una etiqueta con el id de donde lo saco:

    <d MOU0001>pesa 144 gramos</d>       dato de un producto
    <d costo_envio>el envio es gratis</d> dato de una politica de la casa

Despues el CODIGO contrasta cada afirmacion marcada contra el material que las
herramientas trajeron ESTE turno, borra la que no cierra, y saca las etiquetas.
El cliente lee prosa normal y nunca ve una etiqueta.

POR QUE ETIQUETA Y NO UN JSON CON DOS CAMPOS. El JSON con `prosa_fija` y
`prosa_generada` obliga al MODELO a decidir que es cada cosa, y eso es
exactamente lo que no queremos que decida: seria pedirle al que alucina que
declare si esta alucinando. La etiqueta no le pide un juicio, le pide una
REFERENCIA, y la referencia se verifica contra la fuente sin preguntarle nada.

LA DIVISION DEL TRABAJO CON LA OTRA ATADURA, y no se pisan. La plata la sigue
gobernando `_sin_plata_inventada`, que tiene el conjunto entero de montos
respaldados del turno. Aca los importes con signo se SALTEAN a proposito: dos
guardias castigando el mismo numero con criterios distintos se contradicen, y la
de plata ya gana esa pelea. Esta se ocupa de lo demas: gramos, meses, medidas,
capacidades, plazos.

QUE SE BORRA Y QUE NO, y es conservador a proposito. Se borra la ORACION que
contiene una afirmacion marcada cuyo numero no esta en la fuente de ese id, que
es el mismo trato que ya recibe una frase que afirma sobre los 880. Lo que
queda sin marcar no se toca: se CUENTA y se loguea, para saber cuanta prosa
sale sin respaldo antes de decidir si algun dia tambien se poda.
"""
import re

from app.logger import get_logger

log = get_logger(__name__)


# LA INSTRUCCION QUE VE EL REDACTOR. Se suma a `_INSTRUCCION_DOS`, no la
# reemplaza. Corta a proposito: cada renglon que se le agrega al prompt de
# redaccion compite con el objetivo de que el mensaje SALGA MAS CORTO.
INSTRUCCION = """MARCA DE DONDE SACASTE CADA DATO. Cuando afirmes un dato
concreto de un producto -garantia, peso, medidas, material, origen, color, que
trae la caja, para que sirve- envolvelo asi: <d ID>lo que afirmas</d>, donde ID
es el id del producto que viene en los datos. Ejemplo: <d MOU0001>pesa 144
gramos</d>. Si el dato sale de una politica de la casa, el ID es el nombre del
tema, por ejemplo <d costo_envio>hacemos envios a todo el pais</d>.
Tu criterio, tus recomendaciones y la conversacion NO se marcan.
No marques nada adentro del bloque de la cuenta, que va tal cual.
Las etiquetas no las ve el cliente: las saca el sistema."""


_RE_MARCA = re.compile(r"<d\s+([A-Za-z0-9_\-\.]{2,40})\s*>(.*?)</d\s*>",
                       re.IGNORECASE | re.DOTALL)
# La red: cualquier resto de etiqueta, abierta, cerrada o rota, se va igual.
# Una etiqueta que llega al cliente es peor que la alucinacion que evita.
_RE_ETIQUETA_SUELTA = re.compile(r"</?d\b[^>]*>", re.IGNORECASE)

# Los numeros que ESTA guardia mira. Se excluye la plata -lo que viene pegado a
# un signo peso- porque de eso se ocupa `_sin_plata_inventada`, que tiene el
# conjunto completo de montos respaldados del turno.
#
# EL AGUJERO QUE TENIA, y lo encontro una alucinacion de verdad (10-ago). El
# patron arrancaba con `\d{1,3}` esperando grupos de miles, asi que un numero
# de CUATRO O MAS digitos escrito sin separador no matcheaba NADA: `8000` era
# invisible. El modelo dijo "sensibilidad de hasta 8000 DPI" -un dato que el
# catalogo no tiene, sacado del entrenamiento-, lo marco prolijo con el id del
# mouse, y la guardia lo dejo pasar porque no vio el numero. La atadura contaba
# la afirmacion como verificada sin haber verificado nada, que es la peor forma
# de fallar: en silencio y con el tablero en verde.
_RE_NUMERO = re.compile(r"(?<![$\d.,])\d+(?:[.,]\d+)*(?!\d)")

_RE_ORACION = re.compile(r"(?:[^.!?\n]|(?<=\d)[.,](?=\d))+[.!?]*")
# El punto de los miles no termina una oracion. Mismo arreglo y mismo motivo
# que en `salida._RE_ORACIONES`: esta funcion tambien BORRA oraciones, asi
# que con el patron viejo podia cortar por adentro de una cifra.

# Unidades que delatan un dato duro de producto en una oracion sin marcar. No
# se poda por esto: se CUENTA, que es lo que hoy no se sabe.
_RE_UNIDAD = re.compile(
    r"\b\d+\s*(?:gramos?|gr|g|kg|kilos?|meses?|anios?|años?|cm|mm|metros?|"
    r"pulgadas?|gb|tb|mb|mhz|ghz|w|watts?|mah|dpi|hz|nucleos?|puertos?)\b",
    re.IGNORECASE)


def _texto_de(valor) -> str:
    """Todo lo que un resultado de herramienta dice, aplanado a texto. Se
    compara contra esto: si el dato esta en cualquier campo de la fuente, la
    afirmacion tiene respaldo."""
    if isinstance(valor, dict):
        return " ".join(_texto_de(v) for v in valor.values())
    if isinstance(valor, (list, tuple)):
        return " ".join(_texto_de(v) for v in valor)
    if valor is None or isinstance(valor, bool):
        return ""
    return str(valor)


def fuentes(llamadas: list) -> dict:
    """El indice de esta vuelta: id de la fuente -> todo lo que dice.

    Se arma con lo que las herramientas trajeron ESTE turno y nada mas. Un id
    que el modelo nombre y no este aca no tiene respaldo, aunque el producto
    exista en los 880: no lo trajimos, asi que el modelo no lo leyo."""
    idx: dict[str, str] = {}

    def _sumar(clave, valor):
        clave = str(clave or "").strip()
        if not clave:
            return
        idx[clave.upper()] = (idx.get(clave.upper(), "") + " "
                              + _texto_de(valor)).strip()

    for l in (llamadas or []):
        r = l.get("resultado")
        if not isinstance(r, dict):
            continue
        # Productos: los de una busqueda y el de una ficha.
        for p in (r.get("productos") or []):
            if isinstance(p, dict) and p.get("id"):
                _sumar(p["id"], p)
        p = r.get("producto")
        if isinstance(p, dict) and p.get("id"):
            _sumar(p["id"], p)
        # Temas de la casa: la politica y el criterio vuelven con su nombre.
        for t in (r.get("temas") or []):
            if isinstance(t, dict) and t.get("tema"):
                _sumar(t["tema"], t)
        # El envio no tiene id propio: se lo nombra por la herramienta, que es
        # como el modelo lo va a nombrar si lo marca.
        if l.get("herramienta") == "cotizar_envio":
            _sumar("cotizar_envio", r)
            _sumar("envio", r)
    return idx


def _numeros(texto: str) -> list[str]:
    """Los numeros de una afirmacion, normalizados. `1.500` y `1500` son el
    mismo dato escrito de dos formas y la fuente usa las dos."""
    fuera = []
    for m in _RE_NUMERO.finditer(texto or ""):
        crudo = m.group(0)
        limpio = crudo.replace(".", "").replace(",", "")
        if limpio and limpio not in fuera:
            fuera.append(limpio)
    return fuera


def _respaldado(numero: str, fuente: str) -> bool:
    """El numero esta en la fuente, escrito como sea. Se compara contra la
    fuente con y sin separadores para que `24` matchee `24 meses` y `1500`
    matchee `1.500`."""
    plana = re.sub(r"[.,](?=\d{3}\b)", "", fuente or "")
    return bool(re.search(r"(?<!\d)" + re.escape(numero) + r"(?!\d)", plana))


def sin_etiquetas(texto: str) -> str:
    """La red que corre SIEMPRE, pase lo que pase con la verificacion. Que una
    etiqueta llegue al cliente es el unico resultado inaceptable de este
    modulo."""
    limpio = _RE_MARCA.sub(lambda m: m.group(2), texto or "")
    limpio = _RE_ETIQUETA_SUELTA.sub("", limpio)
    return re.sub(r"[ \t]{2,}", " ", limpio).strip()


def verificar(texto: str, llamadas: list, trace_id: str = "",
              tienda_id: str = "") -> str:
    """Contrasta lo afirmado contra la fuente, poda lo que no cierra y devuelve
    la prosa limpia, sin una sola etiqueta.

    Nunca levanta: si algo sale mal, saca las etiquetas y devuelve el texto tal
    como estaba. Una atadura rota no puede dejar mudo al bot."""
    try:
        return _verificar(texto, llamadas, trace_id, tienda_id)
    except Exception as e:
        log.warning("atadura_prosa_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")
        return sin_etiquetas(texto)


def _ficha_del_catalogo(fuente_id: str, tienda_id: str) -> str:
    """La ficha REAL del producto, para los ids que este turno no trajo.

    POR QUE EXISTE (11-ago-2026, charla real de Martin). El indice se armaba
    SOLO con lo que las herramientas trajeron en el turno, con este argumento
    escrito: "un id que el modelo nombre y no este aca no tiene respaldo,
    aunque el producto exista en los 880: no lo trajimos, asi que el modelo no
    lo leyo". La premisa es cierta y la CONSECUENCIA estaba mal: esas
    afirmaciones se contaban como huerfanas y **salian sin verificar**.

    En la charla del 11-ago el cliente ya tenia tres microfonos sobre la mesa y
    pregunto por los envios; ese turno no volvio a buscar productos, asi que
    las tres afirmaciones sobre origen y marca -"marca Razer de Estados Unidos,
    fabricado en China"- salieron con CERO control. Y no es un caso raro: en
    una charla de verdad casi todos los turnos son de seguimiento, o sea que
    la atadura se apagaba justo donde mas se usa.

    Lo que corresponde no es dejar pasar ni podar a ciegas: es **verificar
    contra el catalogo**, que es la fuente de verdad y esta a un id de
    distancia. Es MAS estricto que antes, no menos. Si el id tampoco existe en
    los 880, ahi si es huerfana de verdad -un id inventado- y se cuenta como
    tal."""
    if not fuente_id or not re.fullmatch(r"[A-Z]{2,5}\d{2,}", fuente_id or ""):
        return ""
    try:
        from app.storage.firestore_client import get_product_by_id
        p = get_product_by_id(fuente_id, tienda_id=tienda_id or None)
    except Exception as e:  # noqa: BLE001 — se registra: sin la ficha, la
        # atadura no puede contrastar y la afirmacion pasa sin verificar.
        log.error("atadura_ficha_ilegible", fuente_id=str(fuente_id),
                  error=f"{type(e).__name__}: {str(e)[:120]}")
        return ""
    return _texto_de(p) if p else ""


# ── EL DESCUENTO AFIRMADO ───────────────────────────────────────────────────
_RE_PCT_DESCUENTO = re.compile(
    r"(\d{1,2})\s*%[^\n]{0,40}?(?:descuento|off|rebaja|bonificaci)"
    r"|(?:descuento|rebaja|bonificaci\w*)[^\n]{0,40}?(\d{1,2})\s*%",
    re.IGNORECASE)
# Los descuentos REALES de la casa. Si la frase nombra uno, es politica y se
# queda: la misma exencion que usa la guardia del hub.
_RE_DESCUENTO_REAL = re.compile(
    r"transferenc|mayorist|cuotas sin inter[eé]s", re.IGNORECASE)


def _sin_descuento_sin_respaldo(texto: str, fuente: str, trace_id: str) -> str:
    """UN DESCUENTO QUE NINGUNA HERRAMIENTA TRAJO NO EXISTE.

    POR QUE VIVE ACA Y NO EN EL HUB (17-ago-2026). El hueco es viejo: la
    guardia del hub pide beneficio Y gestion en la misma oracion, asi que caza
    el descuento OFRECIDO -"puedo consultar que descuento aplicarte"- y deja
    pasar el AFIRMADO -"te hago un 25% de descuento por ser vos"-, que es la
    peor de las dos porque no deja lugar a duda y alguien la tiene que
    sostener despues.

    Se intento cerrarlo alla, con otra regla de prosa, y salio muy mal: le
    corto el medio al renglon real del pago dividido y dejo "$67.750" donde
    iban $67.500 y $60.750. Un candado contra la alucinacion invento un
    precio. La leccion es la del plan de recorte: esto se cierra contra la
    FUENTE, no sumando la regla numero dieciocho sobre el texto ya escrito, y
    la atadura es el lugar donde se contrasta contra la fuente.

    LAS CUATRO ATADURAS QUE LO HACEN SEGURO, y las tres primeras nacen de
    aquel error:
      1. No toca un renglon que escribio el CODIGO -la cuenta, el reparto-.
      2. No toca una linea que lleve plata. Es basto a proposito: preferimos
         dejar pasar un descuento raro antes que rozar una cifra.
      3. Corta por oraciones con el patron que ya NO parte los numeros.
      4. Si el turno no trajo material, no poda: sin con que comparar, no hay
         nada que probar, y podar por las dudas se come la politica que el bot
         conto bien dos turnos atras.
    """
    if not (texto or "").strip() or not (fuente or "").strip():
        return texto
    try:
        from app.core.mensaje import _es_de_codigo
    except Exception as e:  # noqa: BLE001 — se registra: sin la pieza no se
        # poda, o sea que un descuento sin respaldo sale entero.
        log.error("atadura_sin_es_de_codigo",
                  error=f"{type(e).__name__}: {str(e)[:120]}")
        return texto
    fuera = []
    for linea in texto.splitlines():
        if _es_de_codigo(linea) or "$" in linea:
            continue
        for m in _RE_ORACION.finditer(linea):
            frase = m.group(0)
            if _RE_DESCUENTO_REAL.search(frase):
                continue
            pct = _RE_PCT_DESCUENTO.search(frase)
            if not pct:
                continue
            valor = next((g for g in pct.groups() if g), "")
            if valor and f"{valor}%" not in fuente and f"{valor} %" not in fuente:
                fuera.append(frase)
    if not fuera:
        return texto
    limpio = texto
    for frase in fuera:
        limpio = limpio.replace(frase, "")
    log.error("atadura_prosa_descuento_sin_respaldo", trace_id=trace_id,
              frases=[f.strip()[:80] for f in fuera[:3]])
    return re.sub(r"\n{3,}", "\n\n", limpio).strip()


def _verificar(texto: str, llamadas: list, trace_id: str,
               tienda_id: str = "") -> str:
    marcas = list(_RE_MARCA.finditer(texto or ""))
    idx = fuentes(llamadas)

    # LOS IDS QUE VIENEN DE TURNOS ANTERIORES SE VERIFICAN CONTRA EL CATALOGO.
    # Ver `_ficha_del_catalogo`: sin esto, todo turno de seguimiento salia sin
    # una sola afirmacion controlada.
    for m in marcas:
        fid = m.group(1).strip().upper()
        if fid not in idx:
            ficha = _ficha_del_catalogo(fid, tienda_id)
            if ficha:
                idx[fid] = ficha

    # EL RESPALDO SE BUSCA EN DOS ANILLOS, y el segundo es el que evita el daño.
    # Primero en la fuente que el modelo NOMBRO. Si el numero no esta ahi, se
    # busca en TODO lo que trajeron las herramientas este turno, porque hay dos
    # fallas distintas escondidas abajo del mismo sintoma:
    #
    #   ROTULO EQUIVOCADO. El dato es cierto y esta en la mesa, pero el modelo
    #   lo colgo del id de al lado. Tipico: los dias de envio los trae
    #   `cotizar_envio` y el modelo los marca con el id del producto. Borrar
    #   esto seria borrar una respuesta CORRECTA, que es peor que el error.
    #
    #   INVENTO. El numero no esta en ninguna fuente del turno. Ninguna
    #   herramienta lo dijo, o sea que salio del entrenamiento. Eso si se poda.
    #
    # Es la misma logica que ya gobierna las huerfanas: equivocarse de rotulo no
    # es mentir. Y deja la guardia ESTRICTA donde tiene que estarlo -contra lo
    # que no dijo ninguna fuente- sin castigar el desorden.
    todo = " ".join(idx.values())

    sin_respaldo = []   # el numero no lo dijo NINGUNA fuente del turno
    mal_rotuladas = []  # el dato existe, pero colgado del id equivocado
    huerfanas = []      # marcadas con un id que este turno no se trajo
    for m in marcas:
        fuente_id = m.group(1).strip().upper()
        afirmacion = m.group(2)
        fuente = idx.get(fuente_id)
        if fuente is None:
            huerfanas.append((m.group(0), fuente_id, afirmacion))
            continue
        malos = [n for n in _numeros(afirmacion) if not _respaldado(n, fuente)]
        if not malos:
            continue
        inventados = [n for n in malos if not _respaldado(n, todo)]
        if inventados:
            sin_respaldo.append((m.group(0), fuente_id, afirmacion, inventados))
        else:
            mal_rotuladas.append((fuente_id, afirmacion, malos))

    # LO QUE NO CIERRA SE VA CON SU ORACION ENTERA, que es el trato que ya
    # reciben las frases que afirman sobre el catalogo. Sacar solo el pedazo
    # marcado deja la oracion coja -"El mouse y viene con cable"- y eso es peor
    # de leer que la falta del dato.
    limpio = texto or ""
    for crudo, fuente_id, afirmacion, malos in sin_respaldo:
        limpio = _borrar_oracion_de(limpio, crudo)
        log.error("atadura_prosa_dato_sin_respaldo", trace_id=trace_id,
                  fuente=fuente_id, numeros=malos[:4], dijo=afirmacion[:120])

    # LA HUERFANA NO SE BORRA, y es a proposito. Que el modelo marque con un id
    # que no trajimos suele ser que se equivoco de etiqueta, no que invento el
    # dato; borrar por eso castigaria una respuesta buena por un error de
    # rotulo. Se cuenta y se mira en el log.
    for crudo, fuente_id, afirmacion in huerfanas:
        log.warning("atadura_prosa_id_desconocido", trace_id=trace_id,
                    fuente=fuente_id, dijo=afirmacion[:120])

    # El rotulo equivocado no se borra: se ve. Si esto sube mucho, el arreglo
    # es de PROMPT -decirle mejor de donde cuelga cada dato-, no de poda.
    for fuente_id, afirmacion, numeros in mal_rotuladas:
        log.warning("atadura_prosa_rotulo_equivocado", trace_id=trace_id,
                    fuente=fuente_id, numeros=numeros[:4],
                    dijo=afirmacion[:120])

    limpio = sin_etiquetas(limpio)

    # EL DESCUENTO AFIRMADO, contra la fuente. Va DESPUES de sacar las
    # etiquetas para trabajar sobre la prosa que va a leer el cliente, que es
    # la misma que ven las guardias de abajo.
    limpio = _sin_descuento_sin_respaldo(limpio, todo, trace_id)

    # EL NUMERO QUE MANDA: cuanta prosa con dato duro salio SIN marcar. Es la
    # medida de cuanto sigue viniendo del entrenamiento y no de la fuente. No
    # se poda por esto todavia; primero se mide.
    sueltas = _oraciones_con_dato_sin_marcar(texto or "")
    log.info("atadura_prosa", trace_id=trace_id,
             marcadas=len(marcas), podadas=len(sin_respaldo),
             mal_rotuladas=len(mal_rotuladas),
             huerfanas=len(huerfanas), con_dato_sin_marcar=len(sueltas),
             ejemplo=(sueltas[0][:100] if sueltas else ""))
    return re.sub(r"\n{3,}", "\n\n", limpio).strip()


def _borrar_oracion_de(texto: str, fragmento: str) -> str:
    """Saca la oracion que contiene el fragmento. Si no se puede aislar la
    oracion, saca el fragmento solo: perder una linea es peor que perder una
    frase, pero dejar el dato falso es peor que las dos."""
    pos = texto.find(fragmento)
    if pos < 0:
        return texto
    arranque = max((texto.rfind(c, 0, pos) for c in ".!?\n"), default=-1)
    fin = min((p for p in (texto.find(c, pos + len(fragmento))
                           for c in ".!?\n") if p >= 0), default=-1)
    if fin < 0:
        fin = len(texto)
    else:
        fin += 1
    return (texto[:arranque + 1] + texto[fin:]).strip()


def _oraciones_con_dato_sin_marcar(texto: str) -> list[str]:
    """Oraciones que traen un dato duro con unidad y no estan marcadas. El
    bloque de la cuenta no cuenta: lo escribe el codigo y por eso no se marca."""
    fuera = []
    marcadas = " ".join(m.group(2) for m in _RE_MARCA.finditer(texto))
    for m in _RE_ORACION.finditer(_RE_ETIQUETA_SUELTA.sub("", texto)):
        frase = m.group(0).strip()
        if not frase or "$" in frase or frase.startswith("-"):
            continue
        if not _RE_UNIDAD.search(frase):
            continue
        if frase[:40] in marcadas:
            continue
        fuera.append(frase)
    return fuera
