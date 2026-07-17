"""
INTERPRETE_LIBRE — el turno completo del bot (hub del camino vivo).

Desde el COMPOSITOR (decisión de Martín, 8-jul) el modelo NUNCA le escribe al
cliente. El turno es:

  1. INTERPRETE (LLM, interpretador.interpretar_mensaje, structured outputs):
     entiende el mensaje en el contexto de la charla y devuelve SOLO datos.
  2. COMPOSITOR (código, compositor.componer): compone el 100% del texto de
     salida desde plantillas, curadas y tools selladas. El solver libre
     (agent.run_agent) se ELIMINO en la limpieza del 10-jul.
  3. Verificadores y guardas deterministas como red, sobre el mensaje final.

La interpretación de cada turno se LOGUEA (evento interprete_libre_interpretacion)
para diagnosticar, pero NO se muestra al cliente.

Es el ÚNICO camino del bot: el orchestrator delega acá todo el turno, sin flags.
"""
import re
import time
import unicodedata

from app.core.interpretador import interpretar_mensaje
from app.core.leads import (
    procesar_mensaje_para_lead, descartar_leads_activos, get_lead_activo)
from app.core.estado_venta import (
    construir_estado, set_current_estado,
    productos_de_meta, carrito_de_meta, envio_de_meta, merge_productos,
    detectar_criterio, criterio_del_interprete, concordancia_criterio,
    get_envio_localidades)
from app.config import get_settings
from app.logger import get_logger
from app.storage.firestore_client import (
    get_conversation, save_conversation, log_message, reset_conversation,
    get_config,
)

log = get_logger(__name__)
settings = get_settings()




def _business_name(tienda_id: str | None) -> str:
    name = settings.BUSINESS_NAME
    if tienda_id:
        try:
            stored = get_config("business_name", tienda_id=tienda_id)
            if stored:
                name = stored
        except Exception:
            pass
    return name



def _presupuesto_de_meta(meta: dict) -> str:
    """Saca el presupuesto YA VERIFICADO (campo presentacion de calculate_total)
    del meta del solver, para que el cierre y el link de pago usen el total real
    de la calculadora, nunca uno inventado. "" si el solver no calculo este turno."""
    for tc in reversed((meta or {}).get("tools_called", []) or []):
        if tc.get("name") == "calculate_total":
            pres = (tc.get("result") or {}).get("presentacion")
            if pres:
                return pres
    return ""


def _money(n):
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return None


def _linea_producto(p: dict) -> str:
    """Linea REAL de un producto desde el catalogo: nombre + precio + stock. La
    verdad de la fuente, la usa el estampado de [[PROD:id]] y la guarda de
    producto para re-anclar con el dato real, no re-tipeado."""
    if not isinstance(p, dict):
        return ""
    nombre = str(p.get("nombre", "")).strip()
    precio = _money(p.get("precio_ars"))
    stock = p.get("stock", 0)
    partes = [nombre]
    if precio:
        partes.append(f"- ${precio}")
    if isinstance(stock, int) and stock > 0:
        partes.append(f"({stock} en stock)")
    return " ".join(partes).strip()


def _estampar_productos(texto: str, tienda_id: str, trace_id: str = None) -> str:
    """Reemplaza cada [[PROD:<id>]] por nombre + precio + stock REALES del catalogo.
    El solver ELIGE que producto mostrar (curaduria de venta); el codigo pone el DATO
    (verdad de la fuente). Un id que no existe se quita: el solver no puede inventar un
    producto ni un precio. Asi el listado nace del catalogo, no del texto del modelo."""
    if not texto or "[[PROD:" not in texto:
        return texto or ""
    from app.storage.firestore_client import get_product_by_id

    def _rep(m):
        pid = (m.group(1) or "").strip().upper()
        try:
            p = get_product_by_id(pid, tienda_id=tienda_id)
        except Exception:
            p = None
        if not p:
            log.warning("interprete_libre_prod_inexistente", trace_id=trace_id, pid=pid)
            return ""
        return _linea_producto(p)

    return re.sub(r"\[\[PROD:([A-Za-z0-9_\-]+)\]\]", _rep, texto)



def _forzar_pregunta_si_ambiguo(interp: dict, respuesta: str) -> str | None:
    """Guarda determinista del caso 'interprete BIEN, solver MAL': cuando el
    interprete marco ofrecer_opciones (hay dos caminos y no se puede elegir con
    certeza) pero el solver NO planteo la eleccion, se FUERZA la pregunta A o B en
    vez de dejar que el solver elija por el cliente. Asi la divergencia no se
    resuelve con una alucinacion silenciosa, sino con una pregunta de confirmacion.
    Devuelve el texto a usar, o None si no corresponde tocar la respuesta."""
    if not isinstance(interp, dict):
        return None
    opciones = interp.get("ofrecer_opciones")
    if not isinstance(opciones, list) or len(opciones) < 2:
        return None
    a, b = str(opciones[0]).strip(), str(opciones[1]).strip()
    if not a or not b:
        return None
    import unicodedata

    def _n(s):
        s = unicodedata.normalize("NFKD", str(s or "").lower())
        return "".join(c for c in s if not unicodedata.combining(c))

    r = _n(respuesta)
    ya_pregunta = ("?" in (respuesta or "")) or ("¿" in (respuesta or ""))

    def _menciona(op):
        toks = [t for t in _n(op).split() if len(t) > 3][:3]
        return bool(toks) and any(t in r for t in toks)

    # Si el solver YA pregunta y nombra las dos opciones, planteo la eleccion bien:
    # se respeta su redaccion. En cualquier otro caso (eligio una, o no pregunto),
    # se fuerza la pregunta con el detalle que dio el interprete.
    if ya_pregunta and _menciona(a) and _menciona(b):
        return None
    return ("Quiero darte la opción correcta, tengo dos y no me quiero equivocar:\n"
            f"- Opción A: {a}\n- Opción B: {b}\n\n¿Cuál preferís?")


# Confianza minima del interprete para PISAR al solver por divergencia de
# producto. Si el interprete no esta seguro del producto, no se override al
# solver: la guarda solo actua cuando la lectura es UNIVOCA (conf alta) y el
# nombre resuelto reconcilia con UN unico producto del catalogo. Umbral
# operativo, vive en codigo (config, no flag apagada).
_CONF_MIN_PRODUCTO = 0.8


def _resolver_nombre_a_producto(resuelto: str, catalogo: list) -> dict | None:
    """Reconcilia el NOMBRE que resolvio el interprete con UN producto del
    catalogo, por contencion de nombre completo: el nombre del catalogo esta
    contenido en el resuelto o al reves (matchear por token suelto daria
    'mouse' contra medio catalogo; por eso el viejo certificador de queries no
    servia aca y se retiro en la limpieza del 10-jul). Devuelve el producto
    SOLO si matchea uno unico; ante cero o varios, None (no se pisa la
    respuesta). Un termino vago como 'mouse' matchea muchos y cae a None, que
    es lo que queremos."""
    import unicodedata

    def _n(s):
        s = unicodedata.normalize("NFKD", str(s or "").lower())
        return "".join(c for c in s if not unicodedata.combining(c)).strip()

    r = _n(resuelto)
    if not r:
        return None
    hits: dict[str, dict] = {}
    for p in catalogo or []:
        nom = _n(p.get("nombre"))
        pid = str(p.get("id") or "")
        if nom and pid and (nom in r or r in nom):
            hits[pid] = p
    return next(iter(hits.values())) if len(hits) == 1 else None


def _reanclar_si_producto_divergente(interp: dict, respuesta: str,
                                     ids_mostrados: list, tienda_id: str) -> str | None:
    """Guarda determinista del caso 'interprete BIEN, solver MAL' sobre el
    PRODUCTO (gemela de _forzar_pregunta_si_ambiguo, para un solo producto).

    Si el interprete resolvio CON CONFIANZA un producto, ese nombre reconcilia
    con UN unico producto del catalogo y el solver mostro OTRO id, no se deja
    pasar el producto equivocado: se re-ancla al producto correcto con su LINEA
    REAL del catalogo y una pregunta de confirmacion. No cierra sobre esto: solo
    pregunta, nunca compromete una venta sobre un id inferido (Regla Cero).
    Triple candado para no pisar respuestas buenas: confianza alta, nombre que
    reconcilia UNICO, y que ese id NO este entre los que el solver ya mostro (si
    ya lo mostro, la divergencia era solo textual, ej categoria vs nombre).
    Devuelve el texto re-anclado o None."""
    if not isinstance(interp, dict):
        return None
    try:
        conf = float(interp.get("confianza") or 0)
    except (TypeError, ValueError):
        conf = 0.0
    if conf < _CONF_MIN_PRODUCTO:
        return None
    resuelto = str(interp.get("producto_resuelto") or "").strip()
    if not resuelto:
        return None
    # Divergencia de producto, inline (era divergencia.py, retirado 10-jul): el
    # turno MOSTRO productos pero ninguno de los tokens con carne del nombre
    # resuelto aparece en la respuesta -> se mostro OTRO producto.
    if not ids_mostrados:
        return None

    def _sin_acentos(s):
        s = unicodedata.normalize("NFKD", str(s or "").lower())
        return "".join(c for c in s if not unicodedata.combining(c))

    _toks = [t for t in _sin_acentos(resuelto).split() if len(t) > 3]
    _r = _sin_acentos(respuesta)
    if not _toks or any(t in _r for t in _toks):
        return None
    from app.storage.firestore_client import get_all_products
    p = _resolver_nombre_a_producto(resuelto, get_all_products(tienda_id=tienda_id))
    if not isinstance(p, dict) or not p.get("nombre"):
        return None  # nombre vago o que no reconcilia unico: no se pisa al solver
    pid = str(p.get("id") or "").upper()
    ya_mostrados = {str(i).upper() for i in (ids_mostrados or [])}
    if not pid or pid in ya_mostrados:
        return None  # el solver YA mostro ese producto: no hay divergencia real
    linea = _linea_producto(p)
    return (f"Pará que no me quiero equivocar: vos buscás el {p['nombre']}, "
            f"¿verdad?\n{linea}\n¿Avanzo con ese?")


# DESTINO UNICO ("mandalo todo a Salta", "me mude"): el pedido entero va a UN
# lugar y los destinos viejos quedan OBSOLETOS. Sin esto, el solver re-cotiza
# el destino anterior desde el historial y el total cobra dos envios (visto en
# el banco 8-jul: mudanza de Mendoza a Salta cobro $18.000 de envio). El flag
# es sticky y lo limpia un pedido multi-destino explicito.
_RE_DESTINO_UNICO = re.compile(
    r"\btodo\b.{0,25}\ba\b|\bme mud[eo]\b|\bahora vivo en\b|"
    r"\bcambi\w{0,5}\s+(?:el\s+|la\s+)?(?:envio|destino|direccion)\b")
_RE_MULTI_DESTINO = re.compile(
    r"\b(?:uno|una)\b.{0,30}\ba\b.{0,60}\b(?:otro|otra)\b.{0,30}\ba\b|"
    r"\bdestinos (?:distintos|diferentes|separados)\b|\bpor separado a\b")


def _norm_msg(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


# Pregunta directa de IDENTIDAD del bot ("sos un robot?", "con quien hablo?").
# La honestidad es obligatoria y el prompt solo no alcanza (visto en el banco:
# el solver esquivo la pregunta): si el cliente pregunta y la respuesta no dice
# la verdad, el codigo la antepone determinista.
_RE_PREGUNTA_BOT = re.compile(
    r"\bsos\s+(?:un\s+)?(?:bot|robot|humano|una\s+maquina|una\s+ia|real)\b"
    r"|\beres\s+(?:un\s+)?(?:bot|robot|humano)\b"
    r"|\bhablo\s+con\s+(?:un\s+)?(?:bot|robot|humano|una\s+persona|una\s+maquina)\b"
    r"|\bcon\s+quien\s+(?:hablo|estoy\s+hablando)\b"
    r"|\bme\s+atiende\s+(?:un\s+)?(?:bot|robot|una\s+maquina)\b",
    re.IGNORECASE)


def _asegurar_honestidad_bot(mensaje: str, respuesta: str,
                             business_name: str) -> str:
    """Si el cliente pregunta si habla con un bot y la respuesta no lo dice, el
    codigo antepone la verdad. Determinista; no toca respuestas que ya la dicen."""
    import unicodedata

    def _n(s):
        s = unicodedata.normalize("NFKD", str(s or "").lower())
        return "".join(c for c in s if not unicodedata.combining(c))

    if not _RE_PREGUNTA_BOT.search(_n(mensaje)):
        return respuesta
    r = _n(respuesta)
    if ("asistente automatico" in r or "asistente virtual" in r
            or "soy un bot" in r or "soy un robot" in r):
        return respuesta
    return (f"Sí, te lo digo derecho: soy el asistente automático de "
            f"{business_name}.\n\n" + (respuesta or "").strip()).strip()


# Saludo del solver al arranque de SU texto: se recorta cuando el codigo
# antepone el saludo oficial, para no saludar dos veces. Solo saludos
# inequivocos ("hola", "buenas tardes/noches", "buen dia"); "buenas" pelado NO
# matchea para no comerse un "Buenas noticias...".
_RE_SALUDO_SOLVER = re.compile(
    r"^[¡!]*\s*(hola+|buen(as)?\s+(tardes|noches|d[ií]as?))\b[\s,.!:]*",
    re.IGNORECASE)

# Bienvenida REDUNDANTE del modelo en el turno 1 (17-jul, visto en repro): el
# codigo ya antepone el saludo oficial y el modelo ademas abre con "Bienvenido
# a X, soy tu asistente. Que bueno que nos contactes." = doble saludo. Se
# recortan del arranque del cuerpo las oraciones que son pura bienvenida (dos
# como maximo, solo al inicio; el resto del texto no se toca).
_RE_BIENVENIDA_SOLVER = re.compile(
    r"^(?:[¡!]\s*)?[^.!?\n]{0,80}?"
    r"(?:bienvenid[oa]s?\b|soy\s+(?:tu|su|el|la)\s+asistente|"
    r"qu[eé]\s+bueno\s+que\s+nos\s+(?:contactes|escribas)|"
    r"gracias\s+por\s+(?:contactarnos|escribirnos))"
    r"[^.!?\n]*[.!?]\s*",
    re.IGNORECASE)


def _con_saludo_inicial(respuesta: str, business_name: str) -> str:
    """Primer mensaje de la charla: linea FIJA de saludo cordial con el aviso de
    herramienta automatica (determinista, no depende del prompt), y abajo la
    respuesta del turno. El aviso va una sola vez en toda la conversacion."""
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


# ── Piso de composicion (fila Z): funciones puras ───────────────────────────
_RE_SOLO_SALUDO = re.compile(
    r"^[\s¡!¿?.,]*(hola+|buenas+(\s+(tardes|noches))?|buen\s+d[ií]as?|"
    r"buenos\s+d[ií]as|que\s+tal|como\s+va|hey|hi)[\s!.,¿?]*$",
    re.IGNORECASE)


def _mensaje_con_contenido(mensaje: str) -> bool:
    """True si el mensaje del cliente trae algo mas que un saludo pelado. Un
    'hola' solo NO exige sustancia (el saludo de vuelta alcanza); 'hola, busco
    una notebook' SI."""
    import unicodedata
    m = unicodedata.normalize("NFKD", str(mensaje or "").lower())
    m = "".join(c for c in m if not unicodedata.combining(c)).strip()
    return bool(m) and not _RE_SOLO_SALUDO.match(m)


def _sin_sustancia(respuesta: str) -> bool:
    """True si la respuesta quedo hueca: vacia, o corta y sin ningun dato ($ o
    digito) ni pregunta que mueva la charla. Una respuesta corta CON pregunta
    ('¿Que estas buscando?') o con dato estampado es valida."""
    r = (respuesta or "").strip()
    if not r:
        return True
    return len(r) < 60 and not re.search(r"[\d$?¿]", r)


_RE_PRESUPUESTO_EN_TEXTO = re.compile(
    r"\bpresupuesto\b|\btotal\b[^\n]{0,20}\$", re.IGNORECASE)


def _forzar_opciones_si_presupuesto(respuesta: str, cats_pedido: list,
                                    tienda_id: str) -> str | None:
    """Guarda del PEDIDO POR CATEGORIAS (prioridad 1, caso real WhatsApp
    8-jul): el cliente pidio N unidades por categoria SIN modelos y el solver
    igual armo un presupuesto inventado (1x de cada producto que se le ocurrio,
    con un teclado al precio de una notebook). Si la respuesta trae un
    presupuesto/total, se reemplaza por el mensaje correcto construido por el
    CODIGO: opciones reales con stock por categoria + pregunta de modelos.
    None si la respuesta no armo presupuesto (el brief alcanzo)."""
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


def _norm_txt(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


_RE_NEGACION = re.compile(
    r"\bno\b|ningun|mejor no|otra cosa|no gracias|dejalo|olvidalo")
_RE_AFIRMACION = re.compile(
    r"\b(si|sisi|sip|sep|dale|obvio|claro|correcto|exacto|eso|esos|esas|esa|"
    r"ok|oka|okey|oki|de una|va|vamos|vale|perfecto|joya|listo|bueno|"
    r"buenisimo|hacelo|hagamoslo|confirmo|confirmado|ahi|asi|tal cual)\b")


def _es_afirmacion_barato(mensaje: str, interp: dict) -> bool:
    """El cliente confirma que SI quiere lo mas barato tras la pregunta de
    confirmacion. Cuenta un 'si'/'dale'/'eso', volver a decir el criterio, o que
    el LLM lo lea de nuevo. Una negacion explicita manda que NO."""
    t = _norm_txt(mensaje)
    if _RE_NEGACION.search(t):
        return False
    if detectar_criterio(mensaje) or criterio_del_interprete(interp):
        return True
    return bool(_RE_AFIRMACION.search(t))


def _reanclar_si_barato_divergente(respuesta: str, id_barato: str,
                                   ids_mostrados: list, tienda_id: str) -> str | None:
    """Guarda del MAS BARATO (caso 'codigo BIEN, solver MAL'): la guia
    determinista ya computo el minimo con stock, pero el solver afirmo que el
    mas barato es OTRO producto (visto en el banco 8-jul: dijo M170 $12.000
    cuando el DX-110 sale $8.500). Si la respuesta reclama 'mas barato' y no
    muestra el producto que computo el codigo, se re-ancla con su linea real.
    Devuelve el texto re-anclado o None si la respuesta esta bien."""
    if not id_barato or not respuesta:
        return None
    import unicodedata

    def _nn(s):
        s = unicodedata.normalize("NFKD", str(s or "").lower())
        return "".join(c for c in s if not unicodedata.combining(c))

    r = _nn(respuesta)
    if not re.search(r"mas (barat|econom)", r):
        return None
    if id_barato.upper() in {str(i).upper() for i in (ids_mostrados or [])}:
        return None
    from app.storage.firestore_client import get_product_by_id
    try:
        p = get_product_by_id(id_barato.upper(), tienda_id=tienda_id)
    except Exception:
        p = None
    if not isinstance(p, dict) or not p.get("nombre"):
        return None
    if _nn(p["nombre"]) in r:
        return None  # el solver SI mostro el correcto, solo sin marcador
    return (f"El más barato con stock es el {p['nombre']}:\n"
            f"{_linea_producto(p)}\n"
            "¿Te lo sumo o querés ver más opciones?")


def _fallback_o_curada(mensaje: str, interp: dict | None, tienda_id: str,
                       trace_id: str | None = None) -> str:
    """Cuando una guarda BLOQUEA la respuesta, el enlatado generico es la peor
    salida si el cliente pregunto una POLITICA que tiene curada (visto en el
    banco 8-jul: '¿como es la seña?' termino en 'no tengo esa informacion').
    Si el ruteo matchea un tema curado, sale ESA respuesta oficial; si no, el
    fallback de siempre."""
    try:
        from app.core.curadas import bloque_curado_por_mensaje
        _bc = bloque_curado_por_mensaje(mensaje, interp, tienda_id)
        if _bc:
            log.info("interprete_libre_fallback_curada", trace_id=trace_id,
                     tema=_bc[0])
            return _bc[1]
    except Exception as e:
        log.warning("interprete_libre_fallback_curada_error",
                    trace_id=trace_id, error=str(e)[:120])
    return settings.VERIFIKA_FALLBACK_MESSAGE


def _parece_aportar_dato(mensaje: str) -> bool:
    """Heuristica barata: el mensaje parece traer un dato de cierre (numero, pago,
    o cue de domicilio), aunque el interprete no lo haya marcado como aporta_dato.
    Abre el extractor LLM en cotizaciones que ya mencionan direccion o pago."""
    if not mensaje:
        return False
    t = mensaje.lower()
    if any(ch.isdigit() for ch in t):
        return True
    claves = ("transferenc", "mercado pago", "efectivo", "tarjeta", "debito",
              "credito", "calle", "avenida", " av ", "direccion", "domicilio",
              "envio a", "enviar a", "me llamo", "mi nombre")
    return any(k in t for k in claves)


async def procesar_interprete_libre(user_id: str, raw_message: str,
                                    tienda_id: str, canal: str,
                                    trace_id: str) -> str:
    """Maneja el turno entero: intérprete + solver libre + memoria. La
    interpretación se loguea para diagnosticar, no se muestra al cliente."""
    t0 = time.time()

    conv = get_conversation(user_id, tienda_id=tienda_id)
    history = conv.get("history", []) or []
    estado_anterior = conv.get("estado_conversacion", "saludo") or "saludo"
    # PROOF de turnos anteriores: respaldan un total que el cliente confirma y el
    # bot repite sin recalcular, asi el filtro determinista no bloquea en falso.
    proofs_memoria = conv.get("proofs_recientes", []) or []

    # ── RESET_CODE: palabra clave de PRUEBA para arrancar de cero ────────
    # El bot mantiene CONTINUIDAD siempre. NO resetea con frases naturales como
    # "nueva compra" (un cliente real las usa para seguir comprando, no para
    # borrar todo). Para las pruebas hay una palabra clave dedicada (RESET_CODE,
    # ej "verifika2026"): si el mensaje es EXACTAMENTE esa, se borra la conversacion
    # entera y se confirma. Con clientes reales no hace falta; es solo para testear
    # desde el mismo numero sin tocar el entorno.
    _rc = (settings.RESET_CODE or "").strip().lower()
    if _rc and (raw_message or "").strip().lower() == _rc:
        try:
            reset_conversation(user_id, tienda_id=tienda_id)
            descartar_leads_activos(user_id, canal, tienda_id)
        except Exception as e:
            log.warning("interprete_libre_reset_error", trace_id=trace_id,
                        error=str(e)[:120])
        log.info("interprete_libre_reset_code", trace_id=trace_id, user_id=user_id)
        return "Listo, conversacion reiniciada. Empezamos de cero."

    # ── ESTADO DE VENTA: fuente unica del turno, una sola carga ─────────────
    # Se arma desde la conversacion persistida + el lead activo y se setea en la
    # contextvar, asi el interprete, el solver, las herramientas y el cierre leen
    # la MISMA verdad sin recibirla por parametro (igual que tienda y destino).
    lead_activo = None
    try:
        lead_activo = get_lead_activo(user_id, canal, tienda_id)
    except Exception as e:
        log.warning("interprete_libre_lead_lookup_error", trace_id=trace_id,
                    error=str(e)[:120])
    estado = construir_estado(conv, lead_activo)
    # La ULTIMA respuesta del bot entra al estado del turno: la usan las
    # curadas para NO repetir el mismo bloque enlatado que acaba de salir
    # (charla real 11-jul 17:59: pregunta de detalle sobre tarjetas ->
    # re-sirvio identica la curada de formas de pago en vez del honesto
    # "ese detalle no lo tengo confirmado").
    for _h in reversed(history or []):
        if isinstance(_h, dict) and _h.get("role") == "assistant":
            estado["ultima_respuesta_bot"] = str(_h.get("content") or "")
            break
    # La provincia dicha en ESTE mensaje entra al estado del turno YA (no recien
    # al persistir al final): asi cotizar_envio resuelve una localidad ambigua
    # ('Los Condores') con la provincia que el cliente acaba de dar en la misma
    # frase. Se detecta una sola vez y se reusa al persistir abajo.
    from app.core.envio import clasificar_provincia
    _prov_msg = clasificar_provincia(raw_message) or ""
    if _prov_msg:
        estado["provincia_envio"] = _prov_msg
    # DESTINO UNICO sticky: "mandalo todo a X" / "me mude" manda todo a UN
    # lugar hasta que el cliente pida destinos separados de nuevo. La
    # calculadora lo lee para no cobrar un envio por un destino obsoleto que
    # el solver re-cotice desde el historial.
    _msg_norm = _norm_msg(raw_message)
    if _RE_MULTI_DESTINO.search(_msg_norm):
        destino_unico = False
    elif _RE_DESTINO_UNICO.search(_msg_norm):
        destino_unico = True
    else:
        destino_unico = bool(conv.get("destino_unico"))
    estado["destino_unico"] = destino_unico
    set_current_estado(estado)

    # ── PASO 1: INTERPRETE ──────────────────────────────────────────────
    # El producto ANOTADO viaja como contexto del interprete junto al resumen:
    # "el que te dije al principio" resuelve aunque el turno del ancla ya haya
    # caido del historial vivo.
    _resumen_interp = estado.get("resumen_charla") or ""
    _ancla_previa = estado.get("producto_anotado") or {}
    if _ancla_previa.get("nombre"):
        _resumen_interp = (_resumen_interp + " [Producto elegido y anotado "
                           f"por el cliente: {_ancla_previa['nombre']}]").strip()
    interp = {}
    try:
        interp = await interpretar_mensaje(
            raw_message, history, trace_id,
            estado_anterior=estado_anterior, tienda_id=tienda_id,
            productos_vistos=estado.get("productos_vistos"),
            resumen=_resumen_interp)
    except Exception as e:
        log.error("interprete_libre_interp_error", trace_id=trace_id,
                  error=str(e)[:200])

    estado_nuevo = (interp.get("estado_conversacion")
                    or estado_anterior) if isinstance(interp, dict) else estado_anterior

    # La interpretacion va al LOG para diagnosticar (reemplaza el cartel que antes
    # se mostraba al cliente). Asi se juzga la interpretacion sin molestar la charla.
    if isinstance(interp, dict):
        log.info("interprete_libre_interpretacion", trace_id=trace_id,
                 intencion=interp.get("intencion"), confianza=interp.get("confianza"),
                 estado=interp.get("estado_conversacion"),
                 producto=interp.get("producto_resuelto"),
                 responde_a=interp.get("respondiendo_a"),
                 candidatos=interp.get("candidatos"),
                 pedido=interp.get("pedido"))

    # ANCLA DE PRODUCTO ANOTADO (11-jul): dos mutaciones deterministas sobre
    # la interpretacion. "Me gusta X, anotalo" con candidato unico completa
    # producto_resuelto (la ficha reemplaza al fallback "no te entendi");
    # "el que te dije al principio" resuelve al ancla persistida y, si pide
    # total/cierre, arma el pedido para que la guia selle el presupuesto real.
    try:
        from app.core.estado_venta import aplicar_ancla_producto
        from app.storage.firestore_client import get_all_products as _gap_ancla
        _ancla_ev = aplicar_ancla_producto(
            interp, raw_message, estado, _gap_ancla(tienda_id=tienda_id))
        if _ancla_ev:
            log.info("interprete_libre_ancla_producto", trace_id=trace_id,
                     evento=_ancla_ev,
                     producto=interp.get("producto_resuelto"))
    except Exception as e:
        log.warning("interprete_libre_ancla_error", trace_id=trace_id,
                    error=str(e)[:120])

    # Flag one-shot del gatillo de cierre (se lee ACA porque tambien condiciona
    # el atajo curado: con una pregunta de cierre pendiente no se ataja nada).
    pregunta_cierre_previa = bool(conv.get("pregunta_cierre_hecha"))

    # ── ATAJO CURADO: pregunta PURA de politica -> respuesta aprobada ───────
    # Patron "LLM compila offline, runtime determinista": si el ruteo de FAQ
    # matchea un tema con respuesta_curada y el turno no tiene venta en juego
    # (sin producto, sin carrito, sin cierre pendiente), sale el texto aprobado
    # por la tienda con los numeros estampados de los valores. El solver NI
    # CORRE: cero alucinacion posible y un turno mas barato. Ante cualquier
    # duda devuelve None y el turno sigue por el camino normal.
    respuesta_curada_servida = False
    respuesta = ""
    meta: dict = {}
    # Marca si la respuesta la genero el SOLVER GEMINI (llamando las tools). En
    # ese caso las guardas de FORMATO que corrigen al viejo solver libre
    # (reanclar mas barato / producto, forzar A/B, forzar opciones) NO corren:
    # peleaban con la prosa natural del modelo y la reescribian aunque el dato
    # fuera correcto (el modelo dice "DX-110 en color Negro", la guarda buscaba
    # "DX-110 Negro" literal). Los verificadores REALES (plata, stock, promesas,
    # FAQ) siguen corriendo igual como red: la atadura al dato no se afloja.
    _via_solver = False
    try:
        from app.core.curadas import servir_curada
        _cur = servir_curada(raw_message, interp, estado,
                             pregunta_cierre_previa, tienda_id)
        if _cur:
            respuesta = _cur[1]
            respuesta_curada_servida = True
            log.info("interprete_libre_curada_servida", trace_id=trace_id,
                     tema=_cur[0])
    except Exception as e:
        log.warning("interprete_libre_curada_error", trace_id=trace_id,
                    error=str(e)[:120])

    # GUIA DETERMINISTA "mas barato con stock" (blindaje del hueco real 2-jul):
    # si el criterio del cliente es el precio (dicho este turno o sticky en
    # memoria), elegir el minimo es un problema CERRADO y lo computa el CODIGO.
    # El id computado alimenta la guarda del mas barato de mas abajo, que
    # re-ancla si la respuesta afirma que el mas barato es OTRO producto.
    _id_barato = ""
    # Solo con criterio BARATO dicho en ESTE mensaje: el guard del minimo no
    # aplica al criterio "intermedio" (11-jul) ni al sticky de turnos viejos
    # (11-jul, banco: el cliente pregunto por el HyperX y el sticky de tres
    # turnos atras hizo que la guarda reescribiera la respuesta correcta al
    # mas barato de otra categoria). El sticky sigue valiendo para ARMAR el
    # pedido pendiente; para POLICIAR la respuesta solo vale el turno.
    if detectar_criterio(raw_message) == "más barato":
        try:
            from app.core.guia_compra import guia_mas_barato
            _guia_barato = guia_mas_barato(
                raw_message, estado.get("productos_vistos"))
            if _guia_barato:
                _mb = re.search(r"\[\[PROD:([A-Za-z0-9_\-]+)\]\]", _guia_barato)
                _id_barato = (_mb.group(1).upper() if _mb else "")
                log.info("interprete_libre_guia_mas_barato", trace_id=trace_id)
        except Exception as e:
            log.warning("interprete_libre_guia_barato_error", trace_id=trace_id,
                        error=str(e)[:120])

    # GUIA DETERMINISTA DE PEDIDO (8-jul): si el interprete extrajo el pedido
    # completo (productos MOSTRADOS + cantidades, atado por enum), el CODIGO
    # llama la calculadora y sella el presupuesto; el solver redacta alrededor
    # del bloque y no elige ids ni suma a mano. Cierra el caso real de
    # multi-envio: ids equivocados en calculate_total y cuenta tipeada a mano.
    _tools_precalc: list = []
    _cats_pedido: list = []
    # Flag de confirmacion de criterio pendiente para el turno siguiente: se
    # prende cuando los DOS interpretes del "mas barato" divergen y se pregunta.
    _criterio_confirmar = False
    # Mensaje SELLADO de pedido este turno: el acople de politica corre igual
    # (charla real 10-jul: "...y dime cuanto demora" pegado al pedido se
    # perdia porque el sellado marcaba el turno como curada servida).
    _sellado_pedido = False
    # El rechazo vacio o EDITO el carrito este turno ("sacalo"): al persistir,
    # el carrito viejo no debe volver de la memoria aunque la intencion del
    # turno sea "otra" (el rechazo suele leerse asi).
    _carrito_vaciado = False
    _carrito_editado = False
    if not respuesta_curada_servida:
        try:
            from app.core.guia_pedido import calcular_pedido
            _tools_precalc = calcular_pedido(
                interp, estado, tienda_id, trace_id,
                mensaje=raw_message) or []
            # PEDIDO POR CATEGORIAS sin modelos (prioridad 1, caso real 8-jul):
            # "4 notebooks, 3 teclados y 5 mouse" -> nada de presupuesto
            # inventado; opciones por categoria y preguntar modelos. El
            # pendiente es STICKY: mientras los modelos no esten elegidos
            # (ni pedido sellado ni carrito), NINGUN turno puede armar un
            # presupuesto (el solver lo hizo en el turno siguiente, con diez
            # items de fantasia por $607.000).
            # EDICION DEL PEDIDO POR RECHAZO (11-jul, guion 28: "el auricular
            # no, sacalo" re-ofrecia las mismas opciones): si el interprete no
            # trajo el pedido editado y el mensaje descarta un item del
            # carrito vigente, el CODIGO lo quita y recalcula sellado.
            if not _tools_precalc and (estado.get("carrito") or []):
                from app.core.estado_venta import rechazados_del_carrito
                from app.storage.firestore_client import (
                    get_all_products as _gap_rech)
                _quitados, _restantes = rechazados_del_carrito(
                    estado.get("carrito"), raw_message,
                    _gap_rech(tienda_id=tienda_id))
                if _quitados:
                    _noms_q = ", ".join(
                        str(q.get("nombre") or "") for q in _quitados)
                    if _restantes:
                        from app.core.guia_pedido import (
                            _calcular_items_sellados,
                            mensaje_presupuesto_sellado)
                        _items_rest = [
                            {"product_id": str(r.get("id") or "").upper(),
                             "cantidad": int(r.get("cantidad") or 1)}
                            for r in _restantes if r.get("id")]
                        _tools_precalc = _calcular_items_sellados(
                            _items_rest, estado, tienda_id, trace_id,
                            raw_message) or []
                        if _tools_precalc:
                            respuesta = (
                                f"Listo, saqué {_noms_q} del pedido. Queda "
                                "así:\n\n" + mensaje_presupuesto_sellado(
                                    _tools_precalc[0]["result"]["presentacion"]))
                            respuesta_curada_servida = True
                            _sellado_pedido = True
                            _carrito_editado = True
                            log.info("interprete_libre_pedido_editado",
                                     trace_id=trace_id, quitados=_noms_q)
                    else:
                        respuesta = (
                            f"Listo, saqué {_noms_q} y el pedido quedó "
                            "vacío, sin problema. ¿Te muestro alguna "
                            "alternativa o buscás otra cosa?")
                        respuesta_curada_servida = True
                        _carrito_vaciado = True
                        log.info("interprete_libre_pedido_vaciado",
                                 trace_id=trace_id, quitados=_noms_q)
            # SPLIT DE PAGO SOBRE EL PEDIDO VIGENTE (charla real 11-jul
            # 17:22): "mitad transferencia y mitad mercado pago" con el
            # presupuesto ya sellado respondia "¿que producto estas
            # mirando?". La cuenta existia (pago_split via calculate_total);
            # ahora el mensaje la dispara con los items del carrito y los
            # destinos de memoria, y sale el bloque sellado con el reparto.
            if (not _tools_precalc and not respuesta_curada_servida
                    and (estado.get("carrito") or [])):
                from app.core.pago_split import pago_de_mensaje
                from app.core.estado_venta import es_rechazo as _es_rech_sp
                _re_edita = re.compile(
                    r"sacal[eo]|agregal[eo]|sumal[eo]|dejame solo"
                    r"|quedate con|cambial[eo]")
                # Solo cuando el mensaje es ESENCIALMENTE de pago: si ademas
                # edita items o cambia destinos, la combinacion la resuelve
                # el selector v2 con todos los argumentos juntos.
                _solo_pago = (pago_de_mensaje(raw_message)
                              and not _es_rech_sp(raw_message)
                              and not _re_edita.search(_norm_txt(raw_message)))
                if _solo_pago:
                    from app.core.guia_pedido import (
                        cotizar_destinos_del_mensaje as _cddm_sp)
                    _solo_pago = not _cddm_sp(raw_message)
                if _solo_pago:
                    from app.core.guia_pedido import _calcular_items_sellados
                    _items_cv = [
                        {"product_id": str(c.get("id") or "").upper(),
                         "cantidad": int(c.get("cantidad") or 1)}
                        for c in estado["carrito"] if c.get("id")]
                    _tools_precalc = _calcular_items_sellados(
                        _items_cv, estado, tienda_id, trace_id,
                        raw_message) or []
                    if _tools_precalc:
                        respuesta = (
                            "Así queda tu pedido con ese reparto de "
                            "pago:\n\n"
                            + _tools_precalc[0]["result"]["presentacion"]
                            + "\n\nEnvío orientativo, puede variar al "
                              "confirmar la compra.\n¿Lo dejamos "
                              "confirmado así?")
                        respuesta_curada_servida = True
                        _sellado_pedido = True
                        log.info("interprete_libre_split_pago_vigente",
                                 trace_id=trace_id)
            if not _tools_precalc and not respuesta_curada_servida:
                from app.core.guia_pedido import cantidades_por_categoria
                _cats_pedido = cantidades_por_categoria(raw_message, tienda_id)
                _cats_de_memoria = False
                if not _cats_pedido and not (estado.get("carrito") or []):
                    _cats_de_memoria = True
                    # Persistido como lista de DICTS: Firestore real prohibe
                    # listas anidadas (bug real 8-jul: 400 'Nested arrays are
                    # not allowed' rompia el save COMPLETO y el bot quedaba
                    # amnesico justo en las charlas con categorias).
                    _cats_pedido = [
                        (c.get("cantidad"), c.get("categoria"))
                        for c in (conv.get("pedido_categorias_pendiente") or [])
                        if isinstance(c, dict)
                        and isinstance(c.get("cantidad"), int)
                        and c.get("categoria")]
                    # Un pendiente de MEMORIA solo vale si el cliente sigue en
                    # ESA conversacion: si este mensaje nombra explicitamente
                    # OTRA categoria de la tienda, el pendiente viejo no se
                    # sella ni persiste (13-jul: '¿un ssd me sirve?' dejaba
                    # pendiente (1, ssd) y 'el mas barato de esos auriculares'
                    # sellaba un pedido de SSD que nadie pidio).
                    if _cats_pedido:
                        from app.core.guia_pedido import categorias_nombradas
                        _noms = set(categorias_nombradas(
                            raw_message, tienda_id))
                        if _noms and not (_noms
                                          & {c for _, c in _cats_pedido}):
                            log.info(
                                "interprete_libre_pendiente_descartado",
                                trace_id=trace_id,
                                pendiente=[c for _, c in _cats_pedido],
                                nombradas=sorted(_noms))
                            _cats_pedido = []
                # ASIGNACION PARCIAL DE DESTINO (11-jul, guion 29): "una
                # parte va a Rafaela, un teclado y un mouse van ahi" NO es
                # un pedido nuevo: es el MISMO pedido repartiendo envios.
                # Si el pedido vigente CONTIENE las cantidades del mensaje,
                # no se pisa nada: se cotizan los destinos (los nuevos y los
                # ya dados, para que persistan juntos) y el pedido sigue.
                if _cats_pedido and not _cats_de_memoria:
                    from app.core.estado_venta import (
                        es_asignacion_destino,
                        cantidades_vigentes_por_categoria)
                    if es_asignacion_destino(raw_message):
                        from app.storage.firestore_client import (
                            get_all_products as _gap_dest)
                        _vig = cantidades_vigentes_por_categoria(
                            estado.get("carrito"),
                            conv.get("pedido_categorias_pendiente"),
                            _gap_dest(tienda_id=tienda_id))
                        _entra = _vig and all(
                            _vig.get(_norm_txt(c), 0) >= n
                            for n, c in _cats_pedido)
                        if _entra:
                            from app.core.guia_pedido import (
                                cotizar_destinos_del_mensaje)
                            from app.core.tools import cotizar_envio as _ce

                            def _reg_envio(_loc, _q):
                                # El proof de CADA cotizacion entra a meta:
                                # sin el, el verificador no tiene respaldo
                                # del monto correcto y lo "autocorrige" a un
                                # valor de la FAQ (visto 11-jul: $6.000 de
                                # Rafaela pisado a $5.000).
                                _e = {"name": "cotizar_envio",
                                      "args": {"localidad": _loc},
                                      "result": _q}
                                if isinstance(_q, dict) and _q.get("proof"):
                                    _e["proof"] = _q["proof"]
                                _tools_precalc.append(_e)

                            _dest_msg = cotizar_destinos_del_mensaje(
                                raw_message)
                            # Re-cotizar los destinos ya dados: la memoria
                            # de localidades persiste TODAS juntas.
                            for _loc_prev in (
                                    estado.get("localidades_envio") or []):
                                if _loc_prev and _loc_prev not in _dest_msg:
                                    _qp = _ce(localidad=_loc_prev)
                                    if _qp.get("ok"):
                                        _reg_envio(_loc_prev, _qp)
                            from app.core.estado_venta import (
                                get_envio_localidades as _gel)
                            _todas = _gel()
                            if _dest_msg:
                                _lineas_env = []
                                for _d in _dest_msg:
                                    _q = _ce(localidad=_d)
                                    if _q.get("ok"):
                                        _reg_envio(_d, _q)
                                        _m = _q.get("monto")
                                        _c = ("gratis" if _m in (0, None)
                                              else f"${_m:,}".replace(
                                                  ",", "."))
                                        _lineas_env.append(
                                            f"- Envío a {_d}: {_c}")
                                respuesta = (
                                    "Listo, repartimos los envíos y el "
                                    "pedido queda igual.\n"
                                    + "\n".join(_lineas_env)
                                    + "\n¿Te paso el total final con todos "
                                      "los envíos?")
                                respuesta_curada_servida = True
                                # El pendiente vigente (si el pedido aun no
                                # es carrito) se conserva: repartir destinos
                                # no borra el pedido.
                                _cats_pedido = [
                                    (c.get("cantidad"), c.get("categoria"))
                                    for c in (conv.get(
                                        "pedido_categorias_pendiente") or [])
                                    if isinstance(c, dict)
                                    and isinstance(c.get("cantidad"), int)
                                    and c.get("categoria")]
                                log.info(
                                    "interprete_libre_asignacion_destino",
                                    trace_id=trace_id, destinos=_todas)
                if _cats_pedido and not respuesta_curada_servida:
                    # ATAJOS 100% DETERMINISTAS (decision 8-jul tras la charla
                    # real de Martin): en el flujo de pedido por categorias el
                    # MENSAJE ENTERO lo arma el CODIGO y el solver NI CORRE. La
                    # prosa del LLM listaba productos sin stock, re-pedia la
                    # provincia ya dada y contradecia al bloque sellado.
                    # "Los mas baratos": el codigo elige el mas barato con
                    # stock de cada categoria, sella el total y LO ESCRIBE.
                    #
                    # CRITERIO por DOS interpretes (decision de Martin, 9-jul):
                    # el regex del codigo no cubre "eco"/abreviaturas, el LLM si.
                    # Coinciden -> se arma; divergen -> se CONFIRMA con una
                    # pregunta corta (nunca el "¿que producto?" que ignoraba el
                    # pedido). Una confirmacion afirmada del turno previo cuenta
                    # como coincidencia; una negacion la cancela.
                    _conc = concordancia_criterio(raw_message, interp)
                    if conv.get("criterio_confirmar_pendiente"):
                        if _es_afirmacion_barato(raw_message, interp):
                            # El "si" arma con el criterio que quedo sticky al
                            # preguntar: intermedio confirma intermedios.
                            _conc = ("intermedio_confirmado"
                                     if (conv.get("criterio_cliente") or "")
                                     == "intermedio" else "actuar")
                        elif _RE_NEGACION.search(_norm_txt(raw_message)):
                            _conc = ""
                    if _conc == "intermedio_confirmado":
                        # Criterio INTERMEDIO confirmado por el cliente: el
                        # codigo elige la opcion del medio por precio de cada
                        # categoria y sella el total (mismo camino que los
                        # baratos, otro elegidor).
                        from app.core.guia_pedido import (
                            calcular_categorias_intermedias,
                            mensaje_presupuesto_sellado,
                            pregunta_destinos_pendientes)
                        _tools_precalc = calcular_categorias_intermedias(
                            _cats_pedido, estado, tienda_id, trace_id,
                            mensaje=raw_message) or []
                        if _tools_precalc:
                            from app.core.guia_pedido import (
                                reparto_envios_detalle)
                            _rep_txt, _rep_tools = reparto_envios_detalle(
                                raw_message, _cats_pedido, tienda_id)
                            _tools_precalc = _tools_precalc + _rep_tools
                            respuesta = (mensaje_presupuesto_sellado(
                                _tools_precalc[0]["result"]["presentacion"],
                                reparto=_rep_txt)
                                + pregunta_destinos_pendientes(raw_message))
                            respuesta_curada_servida = True
                            _sellado_pedido = True
                            log.info("interprete_libre_categorias_intermedias",
                                     trace_id=trace_id, cats=_cats_pedido)
                            _cats_pedido = []
                    elif _conc == "intermedio":
                        # Criterio INTERMEDIO leido este turno (caso real del
                        # banco 11-jul: "economicos pero no lo mas barato que
                        # haya" armaba los MAS baratos, lo contrario de lo
                        # pedido). Como "intermedio" es difuso, se PROPONE la
                        # opcion del medio de cada categoria con datos reales
                        # y se confirma antes de sellar plata.
                        from app.core.guia_compra import intermedio_con_stock
                        from app.core.tools_context import set_current_tienda
                        set_current_tienda(tienda_id)
                        _lineas_int = []
                        for _n, _cat in _cats_pedido:
                            _pi = intermedio_con_stock(_cat)
                            if isinstance(_pi, dict) and _pi.get("nombre"):
                                _lineas_int.append(
                                    f"- {_n}x " + _linea_producto(_pi))
                        if _lineas_int:
                            respuesta = (
                                "Buscás algo intermedio, ni lo más económico "
                                "ni lo más caro. Te propongo:\n"
                                + "\n".join(_lineas_int)
                                + "\n¿Te armo el total con estos? Confirmame "
                                  "con un sí y te paso el presupuesto al "
                                  "instante.")
                            respuesta_curada_servida = True
                            _criterio_confirmar = True
                            log.info("interprete_libre_criterio_intermedio",
                                     trace_id=trace_id, cats=_cats_pedido)
                    elif _conc == "actuar":
                        from app.core.guia_pedido import (
                            calcular_categorias_baratas,
                            mensaje_presupuesto_sellado)
                        _tools_precalc = calcular_categorias_baratas(
                            _cats_pedido, estado, tienda_id, trace_id,
                            mensaje=raw_message) or []
                        if _tools_precalc:
                            from app.core.guia_pedido import (
                                pregunta_destinos_pendientes,
                                reparto_envios_detalle)
                            # REPARTO por destino (charla real 11-jul 10:42):
                            # la plata salia bien pero el mensaje no mostraba
                            # que grupo va a cada destino. Con proofs de cada
                            # tramo para el verificador.
                            _rep_txt, _rep_tools = reparto_envios_detalle(
                                raw_message, _cats_pedido, tienda_id)
                            _tools_precalc = _tools_precalc + _rep_tools
                            respuesta = (mensaje_presupuesto_sellado(
                                _tools_precalc[0]["result"]["presentacion"],
                                reparto=_rep_txt)
                                + pregunta_destinos_pendientes(raw_message))
                            respuesta_curada_servida = True
                            _sellado_pedido = True
                            log.info("interprete_libre_categorias_baratas",
                                     trace_id=trace_id, cats=_cats_pedido)
                            _cats_pedido = []
                    elif _conc == "confirmar":
                        # Divergen los dos interpretes: pregunta corta que NO
                        # pierde el pedido pendiente y deja armado el "si".
                        respuesta = (
                            "¿Te referís a que te arme el total con los más "
                            "baratos con stock de cada categoría? Confirmame "
                            "con un sí y te paso el presupuesto al instante.")
                        respuesta_curada_servida = True
                        _criterio_confirmar = True
                        log.info("interprete_libre_criterio_confirmar",
                                 trace_id=trace_id, cats=_cats_pedido)
                    # Pedido nuevo por categorias (dicho en ESTE mensaje): el
                    # codigo cotiza los destinos del mensaje y arma las
                    # opciones reales. Con pendiente de MEMORIA no se re-sirve
                    # la lista (el cliente pregunto otra cosa, ej confianza):
                    # va el brief + la guarda, y el solver contesta lo suyo.
                    if (_cats_pedido and not respuesta_curada_servida
                            and not _cats_de_memoria):
                        from app.core.guia_pedido import (
                            cotizar_destinos_del_mensaje,
                            mensaje_opciones_categorias)
                        _dest_ok = cotizar_destinos_del_mensaje(raw_message)
                        _txt_ops = mensaje_opciones_categorias(
                            _cats_pedido, tienda_id, _dest_ok)
                        if _txt_ops:
                            respuesta = _txt_ops
                            respuesta_curada_servida = True
                            log.info("interprete_libre_opciones_categorias",
                                     trace_id=trace_id, cats=_cats_pedido,
                                     destinos=_dest_ok)
                        else:
                            # Sin texto de opciones: queda el pendiente sticky y
                            # la guarda de abajo impide un presupuesto inventado.
                            log.info("interprete_libre_pedido_categorias",
                                     trace_id=trace_id, cats=_cats_pedido)
                    elif _cats_pedido and not respuesta_curada_servida:
                        # Pendiente de MEMORIA: el compositor contesta lo suyo;
                        # la guarda impide cualquier presupuesto inventado.
                        log.info("interprete_libre_pedido_categorias",
                                 trace_id=trace_id, cats=_cats_pedido,
                                 origen="memoria")
            if _tools_precalc:
                # El pedido queda SELLADO para el turno: calculate_total rechaza
                # a un solver que quiera AGREGAR productos que el cliente no
                # pidio (el estado es el mismo dict de la contextvar del turno).
                estado["pedido_sellado_turno"] = [
                    i.get("product_id")
                    for i in _tools_precalc[0].get("args", {}).get("items", [])]
                log.info("interprete_libre_guia_pedido", trace_id=trace_id)
        except Exception as e:
            log.warning("interprete_libre_guia_pedido_error", trace_id=trace_id,
                        error=str(e)[:120])

    log.info("interprete_libre_inicio", trace_id=trace_id,
             intencion=interp.get("intencion") if isinstance(interp, dict) else None,
             hist=len(history))

    # CERTIFICADOR DE CATEGORIA (17-jul, consigna 43): si el cliente pide una
    # categoria que NO vendemos (celular, consola, televisor) y no nombra
    # ninguna real, lo decide el CODIGO: honesto "no lo vendemos" + la
    # alternativa real mas cercana con opciones estampadas. Sin esto el
    # universo quedaba vacio y el modelo rellenaba siguiendo la premisa.
    _cat_no_vendida_servida = False
    if not (respuesta_curada_servida or _sellado_pedido or _tools_precalc):
        try:
            from app.core.guia_compra import categoria_no_vendida
            _cnv = categoria_no_vendida(raw_message, tienda_id)
            if _cnv:
                _pedida, _alt = _cnv
                _partes_cnv = [f"Te soy honesto: {_pedida} no vendemos, "
                               "nuestro rubro es tecnología e informática."]
                if _alt:
                    from app.core.guia_pedido import opciones_por_categoria
                    _ops = opciones_por_categoria(_alt, tienda_id, k=3)
                    if _ops:
                        _partes_cnv.append(
                            f"Si te sirve, en {_alt} tengo estas opciones "
                            "con precio y stock reales:\n"
                            + "\n".join("- " + _linea_producto(p) for p in _ops))
                _partes_cnv.append("¿Te muestro algo de lo que sí tenemos?")
                respuesta = "\n\n".join(_partes_cnv)
                _cat_no_vendida_servida = True
                log.info("interprete_libre_categoria_no_vendida",
                         trace_id=trace_id, pedida=_pedida, alternativa=_alt)
        except Exception as e:
            log.warning("interprete_libre_cat_no_vendida_error",
                        trace_id=trace_id, error=str(e)[:120])

    # GENERADOR DE FRAGMENTOS primario (atadura por contrato tipado, 16-jul):
    # el modelo NO compone texto libre; devuelve una lista de FRAGMENTOS atados
    # por enum (producto, calculo, presupuesto, ficha, faq, envio, criterio,
    # cierre) y el CODIGO renderiza cada dato desde la fuente. Por construccion
    # el modelo no puede escribir un numero ni un id que no exista; el criterio
    # de venta va por grounding mas cita sobre el corpus jurado. Reemplaza al
    # solver de texto libre en el camino vivo (queda superado, no apagado al
    # lado). CONDUCE el turno salvo cuando el codigo ya sello el pedido por la
    # calculadora (ahi el total lo dueña el codigo). Su meta['tools_called']
    # alimenta a todo el downstream; los verificadores (plata, stock, promesas,
    # FAQ, cita) corren DESPUES como red. Falla, timeout o sin clave -> camino
    # determinista de abajo.
    # El pedido SELLADO por la guia YA NO saltea al generador (caso real
    # 21:32: "quiero la gris, envio a Monte Ralo, ¿que dia llega? es para
    # regalo" y la plantilla respondio SOLO el presupuesto y re-pidio la
    # localidad dicha). El bloque sellado viaja como presupuesto EXTERNO: el
    # modelo lo posiciona intocable y responde ALREDEDOR el resto (plazo,
    # regalo, envio). Si el generador falla, la plantilla sigue de red abajo.
    if not (_sellado_pedido or _cat_no_vendida_servida):
        try:
            from app.core.generador_v2 import generar_fragmentos, renderizar
            _presu_ext = None
            if _tools_precalc:
                try:
                    _presu_ext = (
                        _tools_precalc[0]["result"]["presentacion"].strip(),
                        list(_tools_precalc))
                except (KeyError, IndexError, AttributeError):
                    _presu_ext = None
            _frags, _uni, _presu, _presu_tools = await generar_fragmentos(
                raw_message, history, estado, tienda_id, interp, trace_id,
                presupuesto_externo=_presu_ext)
            if _frags:
                _texto, _tools = renderizar(
                    _frags, _uni, estado, tienda_id, trace_id,
                    presupuesto_pre=_presu, presupuesto_tools=_presu_tools)
                if _texto and _texto.strip():
                    _citada = []
                    for _tc in _tools:
                        if _tc.get("name") == "consultar_guia_venta":
                            _cid = (_tc.get("result") or {}).get("id")
                            if _cid and str(_cid) not in _citada:
                                _citada.append(str(_cid))
                    respuesta, _via_solver = _texto, True
                    meta = {"tools_called": _tools, "secciones": [],
                            "prosa_citada": _citada,
                            "turno_criterio": bool(_citada)}
                    log.info("interprete_libre_generador_ok", trace_id=trace_id,
                             fragmentos=len(_frags), prosa_citada=_citada)
        except Exception as e:
            log.warning("interprete_libre_generador_error",
                        trace_id=trace_id, error=str(e)[:150])

    if not _via_solver and not respuesta_curada_servida and not _cat_no_vendida_servida:
        # RED determinista: el CODIGO compone desde plantillas, curadas y tools
        # selladas (el camino previo, cuando el solver no condujo).
        try:
            if _tools_precalc:
                # Pedido ya SELLADO por la guia (modelos elegidos): plantilla
                # fija + bloque de la calculadora. Titulo NEUTRAL (guion 32).
                from app.core.guia_pedido import (
                    mensaje_presupuesto_sellado, pregunta_destinos_pendientes)
                # El cierre no re-pide la forma de pago si el cliente ya la dio,
                # ni este turno ni en uno previo (persistida en el lead). Bug
                # real: pedia la modalidad de pago que el cliente ya habia dado.
                from app.core.cierre import extraer_forma_pago
                _pago_conocido = bool(
                    (conv.get("datos_cliente_parciales") or {}).get("forma_pago")
                    or extraer_forma_pago(raw_message))
                respuesta = (mensaje_presupuesto_sellado(
                    _tools_precalc[0]["result"]["presentacion"],
                    titulo="Listo, así queda tu pedido:",
                    pago_conocido=_pago_conocido)
                    + pregunta_destinos_pendientes(raw_message))
                _sellado_pedido = True
            else:
                # SELECTOR del menu cerrado + COMPOSITOR: una llamada LLM con
                # schema estricto elige las secciones; la cascada de regex queda
                # atras ante error. El texto duro sale del codigo, no del modelo.
                from app.core.compositor import componer
                _plan = None
                try:
                    from app.core.selector import elegir_plan
                    _plan = await elegir_plan(
                        raw_message, interp, estado, tienda_id, trace_id)
                except Exception as e:
                    log.warning("interprete_libre_selector_error",
                                trace_id=trace_id, error=str(e)[:120])
                respuesta, meta = componer(
                    raw_message, interp, estado, tienda_id, trace_id,
                    plan=_plan)
                # NIVEL 2 de la escalera: con dos o mas bloques, el REDACTOR
                # cose la prosa. Sello violado o error -> compositor puro.
                try:
                    _secs = meta.get("secciones") or []
                    if len(_secs) >= 2:
                        from app.core.redactor import redactar
                        _red = await redactar(
                            raw_message, _secs, tienda_id, trace_id,
                            estado.get("productos_vistos"))
                        if _red:
                            respuesta = _red
                            log.info("interprete_libre_redactor_ok",
                                     trace_id=trace_id)
                except Exception as e:
                    log.warning("interprete_libre_redactor_error",
                                trace_id=trace_id, error=str(e)[:120])
        except Exception as e:
            log.error("interprete_libre_compositor_error", trace_id=trace_id,
                      error=str(e)[:200])
            respuesta = settings.FALLBACK_MESSAGE

    # El calculo PRE-hecho por la guia de pedido entra a meta como una tool mas,
    # AL FINAL: los lectores (presupuesto, carrito, proofs, evidencia) recorren
    # reversed(), asi el presupuesto sellado del CODIGO gana sobre un
    # calculate_total del solver con items equivocados en el mismo turno.
    if _tools_precalc:
        meta["tools_called"] = (meta.get("tools_called") or []) + _tools_precalc

    # ── DIAGNOSTICO DE INTEGRACION (solver <-> herramientas mellizas) ──────────
    # Loguea, por turno, lo que DEVOLVIERON las tools deterministas (result/proof)
    # y la respuesta CRUDA del solver, ANTES de estampar/corregir. Sin esto no se
    # puede ver si el dato real de la herramienta llega al mensaje o el solver lo
    # re-tipea distinto. Compacto y truncado; son datos de la tienda, no del
    # cliente. Comparar contra respuesta_preview (final) cierra el triplete.
    try:
        _tools_dump = [
            {"t": tc.get("name"), "res": str(tc.get("result"))[:180]}
            for tc in (meta.get("tools_called") or [])
        ]
        log.info("interprete_libre_solver_crudo", trace_id=trace_id,
                 respuesta_cruda=(respuesta or "")[:400],
                 tools=_tools_dump[:8])
    except Exception:
        pass

    # ── CLON (ESTAMPA): los datos duros NACEN de la fuente, no del modelo ──
    # El solver pone un marcador donde va cada dato duro; el codigo lo reemplaza por
    # el bloque real renderizado desde la tool/Firestore (precio = presentacion de
    # calculate_total; envio = cotizar_envio; politica = respuesta verbatim de
    # query_faq). Asi ni el presupuesto, ni el envio, ni una politica se re-tipean o
    # se inventan. Marcador sin dato (la tool no corrio) -> se quita, no se inventa.
    # Se loguea cuando el solver dio el presupuesto SIN marcador, para medir.
    _env = envio_de_meta(meta)
    _present = _presupuesto_de_meta(meta)
    _marcadores = {
        "[[PRESUPUESTO]]": _present,
        "[[ENVIO]]": (f"Envio a {_env}" if _env else ""),
        # El marcador [[FAQ]] se retiro (consolidacion): la politica ahora entra
        # SIEMPRE por el ACOPLE del bloque curado, decidido por el codigo, no por
        # un marcador que el solver podia no poner. Uno que haya quedado en el
        # texto se limpia como marcador sin dato.
        "[[FAQ]]": "",
    }
    # El Ensamblador coloca cada bloque cuidando la congruencia: un dato de una
    # linea va donde el solver puso el marcador; un bloque de varias lineas
    # (presupuesto, politica) se levanta a su propio parrafo y no queda
    # incrustado en medio de una oracion. Un marcador sin dato se quita limpio.
    from app.core.ensamblador import colocar_bloque
    _tenia_marcador_presup = "[[PRESUPUESTO]]" in (respuesta or "")
    for _marca, _bloque in _marcadores.items():
        if _marca not in (respuesta or ""):
            continue
        respuesta = colocar_bloque(respuesta, _marca, _bloque)
        if _bloque:
            log.info("interprete_libre_estampado", trace_id=trace_id, marca=_marca)
        else:
            log.warning("interprete_libre_marcador_sin_dato",
                        trace_id=trace_id, marca=_marca)
    if _present and not _tenia_marcador_presup:
        log.warning("interprete_libre_presupuesto_sin_marcador", trace_id=trace_id)
        # ULTIMA MILLA del Ensamblador (caso real 8-jul): si el CODIGO sello el
        # presupuesto (guia de pedido / categorias baratas) y el solver no puso
        # el marcador (dijo "voy a calcular el total, un momento" y nada), el
        # bloque sellado NO se pierde: se acopla en vertical, como la FAQ. El
        # marcador es una ayuda, no una condicion para que el cliente vea el
        # total que el codigo ya computo.
        if _tools_precalc:
            from app.core.curadas import acoplar_bloque as _acoplar_presup
            respuesta = _acoplar_presup(respuesta, _present)
            log.info("interprete_libre_presupuesto_acoplado", trace_id=trace_id)

    # Productos: el solver los referencia por [[PROD:<id>]] y el codigo pone
    # nombre+precio+stock reales del catalogo (curaduria del solver, datos de la
    # fuente). Un id inventado se cae solo.
    # Los ids que el solver mostro (antes de estampar): son el QUE realmente en la
    # respuesta. Se guardan para respaldar sus precios reales en el verificador.
    _ids_mostrados = re.findall(r"\[\[PROD:([A-Za-z0-9_\-]+)\]\]", respuesta or "")
    if "[[PROD:" in (respuesta or ""):
        respuesta = _estampar_productos(respuesta, tienda_id, trace_id)
        log.info("interprete_libre_productos_estampados", trace_id=trace_id)

    # ── ACOPLE CURADO de FAQ (reemplaza al marcador [[FAQ]]) ────────────────
    # Si el turno consulto la FAQ, la politica sale del BLOQUE curado del tema
    # (texto aprobado por la tienda con los numeros estampados de los valores),
    # pegado en VERTICAL debajo de la prosa del solver. Lo decide el CODIGO por
    # el query_faq del turno, no un marcador que el solver podia no poner. Un
    # solo cierre por mensaje y sin duplicar si el solver pego el texto tal
    # cual. Corre antes de los verificadores, que auditan el mensaje final.
    tema_acoplado = ""
    if ((not respuesta_curada_servida or _sellado_pedido)
            and respuesta != settings.FALLBACK_MESSAGE):
        try:
            from app.core.curadas import (
                bloque_curado_de_meta, bloque_curado_por_mensaje, acoplar_bloque)
            # Doble ancla: primero el query_faq que el solver llamo; si no llamo
            # ninguno pero el interprete ve una pregunta de politica y el ruteo
            # matchea un tema curado, el bloque va IGUAL (el codigo decide, no
            # depende de la obediencia del solver). Sobre el mensaje SELLADO del
            # pedido, el gate de intencion se saltea: la intencion es de compra
            # pero la pregunta de politica pegada al pedido sale igual.
            _bc_meta = bloque_curado_de_meta(meta, tienda_id)
            _bc = (_bc_meta
                   or bloque_curado_por_mensaje(
                       raw_message, interp, tienda_id,
                       sin_gate_intencion=_sellado_pedido))
            if _bc:
                from app.core.curadas import (
                    solapa_prosa, temas_cubiertos_por_tools, prosa_trae_valores)
                from app.storage.firestore_client import get_all_faq as _gaf
                _tema_bc, _bloque_bc = _bc
                _valores_bc = ((_gaf(tienda_id=tienda_id) or {})
                               .get(_tema_bc) or {}).get("valores")
                _tiene_valores = bool(_valores_bc)
                # Pertinencia (vista en real 4-jul): el bloque NO va cuando una
                # tool del mismo dominio ya dio la respuesta concreta (envio
                # cotizado, descuento en el total), ni cuando la prosa ya dice
                # lo mismo Y el tema es de texto puro. Un tema con numeros
                # lleva SIEMPRE su bloque: el numero oficial no se negocia.
                from app.core.curadas import bloque_repetido
                if bloque_repetido(_bloque_bc, estado, raw_message):
                    # El mismo enlatado que acaba de salir no se re-pega
                    # (11-jul 17:59): el cliente pregunta un detalle que el
                    # bloque no contiene.
                    log.info("interprete_libre_acople_salteado", trace_id=trace_id,
                             tema=_tema_bc, motivo="repetido")
                elif _tema_bc in temas_cubiertos_por_tools(meta):
                    log.info("interprete_libre_acople_salteado", trace_id=trace_id,
                             tema=_tema_bc, motivo="tool_cubre")
                elif _bc_meta and not _tiene_valores and _via_solver:
                    # El bloque nace del query_faq que el SOLVER llamo: ya
                    # leyo esa politica y la integro a su prosa. Un tema de
                    # texto puro no se re-pega (13-jul: el enlatado de
                    # compatibilidad "decime que producto miras" salia
                    # DESPUES de que el solver ya habia detallado el
                    # producto). Un tema con montos sigue llevando bloque.
                    log.info("interprete_libre_acople_salteado", trace_id=trace_id,
                             tema=_tema_bc, motivo="solver_ya_leyo_faq")
                elif not _tiene_valores and solapa_prosa(respuesta, _bloque_bc):
                    log.info("interprete_libre_acople_salteado", trace_id=trace_id,
                             tema=_tema_bc, motivo="prosa_solapa")
                # Tema NUMERICO cuya prosa ya trae TODOS los montos oficiales
                # y ademas dice lo mismo que el bloque: pegarlo repetiria la
                # politica dos veces con un segundo gancho (visto en el banco,
                # guion de acople). El numero oficial esta literal en la prosa
                # y el verificador de FAQ numerica lo audita igual.
                elif (_tiene_valores and prosa_trae_valores(respuesta, _valores_bc)
                        and solapa_prosa(respuesta, _bloque_bc)):
                    log.info("interprete_libre_acople_salteado", trace_id=trace_id,
                             tema=_tema_bc, motivo="prosa_trae_valores")
                else:
                    respuesta = acoplar_bloque(respuesta, _bloque_bc)
                    tema_acoplado = _tema_bc
                    log.info("interprete_libre_faq_acoplada", trace_id=trace_id,
                             tema=tema_acoplado)
        except Exception as e:
            log.warning("interprete_libre_acople_error", trace_id=trace_id,
                        error=str(e)[:120])

    # ── PASO 2a: FILTRO DETERMINISTA — CLON DEL MOTOR DE PRECIOS/ENVIO ──────
    # Partida doble de la verdad. Las herramientas deterministas (calculadora,
    # tarifa de envio, ficha del catalogo) le dan los numeros al Solver via
    # tool-call. Su PROOF queda guardado. ACA ese MISMO motor se usa como CLON
    # para auditar la respuesta que el Solver redacto:
    #   - si cada cifra de dinero coincide con el PROOF, la respuesta pasa intacta;
    #   - si el Solver CAMBIO un total y la verdad esta en el PROOF, el codigo
    #     REESCRIBE la cifra mala por la buena, sin llamar a ningun modelo
    #     (autocorregir_montos, conservador: solo un reemplazo INEQUIVOCO).
    # Con AUTOCORRIGE_MONTOS=false vuelve a modo observacion: solo loguea, no toca.
    proofs_turno = [t["proof"] for t in (meta.get("tools_called") or [])
                    if t.get("proof")]
    # La evidencia del turno se comparte con los verificadores por campo de mas
    # abajo (stock, FAQ numerica): se declara afuera del try para que un error en
    # el filtro de plata no los deje sin fuente.
    evidencia: list = []
    if respuesta != settings.FALLBACK_MESSAGE:
        try:
            from app.core.evidencia import build_evidence_from_tools
            from app.core.verificador import (
                verificar_respuesta, autocorregir_montos)
            # Productos vistos en turnos anteriores: su precio REAL respalda una
            # cifra que el bot ya mostro y repite, asi el filtro no la marca en
            # falso. El estado los guarda con la clave 'precio'; el verificador
            # lee 'precio_ars', por eso se normaliza al pasarlos.
            # Cada visto se re-lee VIVO del catalogo por id: asi la evidencia
            # trae el precio Y el stock actuales y los verificadores (plata y
            # stock) pueden juzgar afirmaciones sobre productos de turnos
            # anteriores. La memoria guarda el precio de cuando se mostro; el
            # que juzga es siempre el dato vivo de la fuente. Si la lectura
            # falla, queda el precio de memoria (sin stock: no acusa a nadie).
            from app.storage.firestore_client import get_product_by_id as _gpid_ev
            prods_vistos = []
            for p in (estado.get("productos_vistos") or []):
                if not isinstance(p, dict):
                    continue
                _vivo = None
                _pid = str(p.get("id") or "").upper()
                if _pid:
                    try:
                        _vivo = _gpid_ev(_pid, tienda_id=tienda_id)
                    except Exception:
                        _vivo = None
                if isinstance(_vivo, dict) and _vivo.get("precio_ars") is not None:
                    prods_vistos.append(_vivo)
                else:
                    prods_vistos.append(
                        {**p, "precio_ars": p.get("precio_ars", p.get("precio"))})
            evidencia = build_evidence_from_tools(
                meta.get("tools_called", []) or [], tienda_id,
                productos_vistos=prods_vistos)
            evidencia += [{"tipo": "proof", "proof": p} for p in proofs_memoria]
            # Productos que el solver MOSTRO ([[PROD:id]]): se respaldan con su
            # precio_ars REAL de get_product_by_id, asi un precio real mostrado nunca
            # cae como "sin respaldo" (es el QUE que de verdad esta en la respuesta).
            if _ids_mostrados:
                from app.storage.firestore_client import get_product_by_id as _gpid
                for _pid in {i.upper() for i in _ids_mostrados}:
                    try:
                        _pp = _gpid(_pid, tienda_id=tienda_id)
                    except Exception:
                        _pp = None
                    if isinstance(_pp, dict) and _pp.get("precio_ars") is not None:
                        evidencia.append({"tipo": "producto", **_pp})
            # Todo producto NOMBRADO con su nombre completo en la respuesta
            # entra VIVO a la evidencia: la melliza no puede juzgar lo que no
            # ve. Visto en el banco: el solver tipeo a mano una linea de
            # producto sin tool ni marcador ("NX-7000 - $8.000, 11 en stock",
            # precio y stock de fantasia) y ni la plata ni el stock la
            # corrigieron porque el producto no estaba en la evidencia.
            from app.core.evidencia import productos_nombrados_en
            _ids_ev = {str(i.get("id") or "").upper() for i in evidencia
                       if i.get("tipo") == "producto"}
            for _pn in productos_nombrados_en(respuesta, tienda_id):
                if str(_pn.get("id") or "").upper() not in _ids_ev:
                    evidencia.append({"tipo": "producto", **_pn})
            # QUE PROACTIVO: el codigo busca en el catalogo lo que el cliente pidio,
            # SIN depender de que el solver haya buscado. Esos productos REALES entran
            # como evidencia COMPLETA del QUE, asi el corrector valida/corrige contra
            # la fuente y no marca en falso un precio real ni deja pasar uno inventado.
            try:
                from app.core.tools import search_products as _search_que
                _ids_ya = {str(i.get("id") or "").upper()
                           for i in evidencia if i.get("tipo") == "producto"}
                _qres = _search_que(query=raw_message) or {}
                for _p in (_qres.get("productos") or [])[:12]:
                    if isinstance(_p, dict) and str(_p.get("id") or "").upper() not in _ids_ya:
                        evidencia.append({"tipo": "producto", **_p})
            except Exception as e:
                log.warning("interprete_libre_que_proactivo_error",
                            trace_id=trace_id, error=str(e)[:120])
            # El catalogo guarda el precio bajo 'precio' o 'precio_ars' segun la
            # fuente; el verificador lee SOLO precio_ars. Se normaliza TODA la
            # evidencia de productos para que un precio real no caiga como
            # "sin respaldo" por un nombre de campo (causa del falso positivo 14500).
            for _i in evidencia:
                if (_i.get("tipo") == "producto" and _i.get("precio_ars") is None
                        and isinstance(_i.get("precio"), (int, float))):
                    _i["precio_ars"] = _i["precio"]
            # Precios reales del catalogo: nunca se pisan aunque el filtro no los
            # vea respaldados en este turno (pueden venir de uno anterior).
            precios_validos = {
                int(i["precio_ars"]) for i in evidencia
                if i.get("tipo") == "producto"
                and isinstance(i.get("precio_ars"), (int, float))
            }
            # Observabilidad de la evidencia del turno: sin esto un producto que
            # NO entro (y deja al ancla del corrector matchear un hermano por
            # tokens) se diagnostica a ciegas (caso NX-7000 del banco, 8-jul).
            log.info("interprete_libre_evidencia", trace_id=trace_id,
                     productos=[str(i.get("id")) for i in evidencia
                                if i.get("tipo") == "producto"][:20],
                     proofs=len([i for i in evidencia if i.get("tipo") == "proof"]),
                     faqs=len([i for i in evidencia if i.get("tipo") == "faq"]))
            if settings.AUTOCORRIGE_MONTOS:
                fix = autocorregir_montos(
                    respuesta, evidencia, trace_id,
                    precios_validos=precios_validos)
                if fix["cambiada"] and fix["verificacion"].get("ok"):
                    # El Solver habia cambiado el total y se reescribio por el real.
                    log.warning("interprete_libre_monto_corregido",
                                trace_id=trace_id,
                                correcciones=fix["correcciones"][:8],
                                respuesta_preview=fix["respuesta"][:220])
                    respuesta = fix["respuesta"]
                elif fix["cambiada"]:
                    # Se intento corregir pero el texto sigue sin cerrar: no se
                    # arriesga un numero a medias, queda el original (shadow).
                    log.warning("interprete_libre_correccion_descartada",
                                trace_id=trace_id,
                                correcciones=fix["correcciones"][:8])
                elif not fix["verificacion"].get("ok"):
                    # Cifra de plata sin respaldo que no se pudo corregir. La
                    # melliza activa decide: bloquea (canned) SOLO si no hay
                    # ninguna evidencia de donde pudo salir el numero, ni tools de
                    # este turno ni memoria. El solver que repite un presupuesto ya
                    # calculado en turnos anteriores no llama tools pero sus cifras
                    # son legitimas: la evidencia esta en proofs/productos de
                    # memoria, asi que queda en shadow y la respuesta sale.
                    from app.core.verificador import (
                        decidir_accion_no_respaldado, es_presupuesto_inventado)
                    hay_tools = bool(meta.get("tools_called"))
                    hay_memoria = bool(proofs_memoria) or bool(prods_vistos)
                    _no_resp = fix["verificacion"]["numeros_no_respaldados"]
                    # HUECO CERRADO (real 15-jul): la memoria legitima YA entra a
                    # la evidencia de arriba (proofs + productos vistos), asi que
                    # una cifra que igual quedo sin respaldo NO salio de la
                    # memoria: es invento. Si forma un PRESUPUESTO (varias cifras
                    # o estructura con total), se bloquea, no se deja pasar en
                    # shadow como antes (un presupuesto inventado se colaba solo
                    # porque existia memoria de turnos previos).
                    if es_presupuesto_inventado(_no_resp, respuesta):
                        accion = "bloquear"
                    else:
                        accion = decidir_accion_no_respaldado(
                            verificacion_ok=False, hay_tools=hay_tools,
                            hay_memoria=hay_memoria)
                    if accion == "bloquear":
                        log.warning("interprete_libre_numero_bloqueado",
                                    trace_id=trace_id,
                                    no_respaldados=fix["verificacion"]["numeros_no_respaldados"][:8],
                                    respuesta_preview=respuesta[:220])
                        respuesta = _fallback_o_curada(raw_message, interp, tienda_id, trace_id)
                    else:
                        log.warning("interprete_libre_numero_no_respaldado_shadow",
                                    trace_id=trace_id,
                                    no_respaldados=fix["verificacion"]["numeros_no_respaldados"][:8],
                                    respuesta_preview=respuesta[:220])
            else:
                veredicto = verificar_respuesta(respuesta, evidencia, trace_id)
                if not veredicto["ok"]:
                    log.warning("interprete_libre_numero_no_respaldado_shadow",
                                trace_id=trace_id,
                                no_respaldados=veredicto["numeros_no_respaldados"][:8],
                                respuesta_preview=respuesta[:220])
        except Exception as e:
            log.warning("interprete_libre_verif_error", trace_id=trace_id,
                        error=str(e)[:160])

    # ── ASIENTOS: el Subtotal declarado = suma de los renglones del mensaje ──
    # (candidata del RESUMEN, vista dos veces en el banco). Solo corrige con la
    # suma RESPALDADA por la evidencia; cualquier renglon ilegible aborta.
    if respuesta != settings.FALLBACK_MESSAGE and evidencia:
        try:
            from app.core.verificador import corregir_subtotal_renglones
            _fix_sub = corregir_subtotal_renglones(respuesta, evidencia, trace_id)
            if _fix_sub["cambiada"]:
                respuesta = _fix_sub["respuesta"]
        except Exception as e:
            log.warning("interprete_libre_subtotal_error", trace_id=trace_id,
                        error=str(e)[:120])

    # ── PASO 2a-ter: VERIFICADOR DE STOCK (mismo patron por campo) ──────────
    # La plata ya esta cubierta; este es el campo por donde se filtro la
    # alucinacion real del 2-jul (negar stock que existia). Dos piezas:
    # 1) la CIFRA de unidades contradicha se reescribe por la real (safe-override
    #    determinista); 2) una CONTRADICCION de texto (negar stock existente,
    #    ofrecer un agotado) se reescribe con la maquinaria de guardia_promesas,
    #    con el dato real del catalogo en la regla. Solo juzga productos cuyo
    #    stock REAL esta en la evidencia de este turno.
    if respuesta != settings.FALLBACK_MESSAGE and evidencia:
        try:
            from app.core.verificador_stock import (
                corregir_unidades_stock, detectar_stock_contradicho,
                instruccion_stock, cuarentena_stock)
            _fix_stock = corregir_unidades_stock(respuesta, evidencia)
            if _fix_stock["correcciones"]:
                log.warning("interprete_libre_stock_cifra_corregida",
                            trace_id=trace_id,
                            correcciones=_fix_stock["correcciones"][:8])
                respuesta = _fix_stock["respuesta"]
            _contradicho = detectar_stock_contradicho(respuesta, evidencia)
            if _contradicho:
                log.warning("interprete_libre_stock_contradicho",
                            trace_id=trace_id, casos=_contradicho[:6],
                            respuesta_preview=respuesta[:200])
                from app.core.guardia_promesas import reescribir_con_reglas
                _nueva = await reescribir_con_reglas(
                    respuesta, instruccion_stock(_contradicho), trace_id)
                if _nueva:
                    respuesta = _nueva
                _quedan = detectar_stock_contradicho(respuesta, evidencia)
                if _quedan:
                    # Red DETERMINISTA (mismo patron que la guardia, visto en
                    # el banco: la reescritura dejo la mentira y salio al
                    # cliente): se podan las lineas contradichas; sin mensaje
                    # decente, canned. Antes aca solo se logueaba stock_persiste.
                    _poda = cuarentena_stock(respuesta, evidencia)
                    if _poda and not detectar_stock_contradicho(_poda, evidencia):
                        respuesta = _poda
                        log.warning("interprete_libre_stock_cuarentena",
                                    trace_id=trace_id, casos=_quedan[:6],
                                    respuesta_preview=_poda[:200])
                    else:
                        respuesta = _fallback_o_curada(raw_message, interp, tienda_id, trace_id)
                        log.warning("interprete_libre_stock_bloqueado",
                                    trace_id=trace_id, casos=_quedan[:6])
                else:
                    log.info("interprete_libre_stock_reescrito",
                             trace_id=trace_id)
        except Exception as e:
            log.warning("interprete_libre_stock_error", trace_id=trace_id,
                        error=str(e)[:160])

    # ── PASO 2a-quater: FAQ NUMERICA (porcentaje, cuotas, plazos, garantia) ──
    # Los numeros chicos de politica que la plata no mira. Si el numero
    # contradice la fuente y el turno consulto la FAQ (ancla del tema), se
    # estampa el valor verdadero; sin ancla univoca, queda logueado.
    if respuesta != settings.FALLBACK_MESSAGE and evidencia:
        try:
            from app.core.verificador_faq import (
                autocorregir_faq_numerica, temas_de_meta)
            # El tema del bloque ACOPLADO tambien ancla: si el codigo pego la
            # politica oficial de un tema, un numero de la prosa del solver que
            # la contradiga se juzga contra ESE tema aunque el solver no haya
            # llamado query_faq (visto en real 4-jul: '3 a 5 dias' inventado).
            _temas_turno = set(temas_de_meta(meta))
            if tema_acoplado:
                _temas_turno.add(tema_acoplado)
            _fix_faq = autocorregir_faq_numerica(
                respuesta, evidencia,
                temas_consultados=_temas_turno, trace_id=trace_id)
            if _fix_faq["cambiada"] and _fix_faq["verificacion"]["ok"]:
                log.warning("interprete_libre_faq_numerica_corregida",
                            trace_id=trace_id,
                            correcciones=_fix_faq["correcciones"][:8])
                respuesta = _fix_faq["respuesta"]
            elif not _fix_faq["verificacion"]["ok"]:
                log.warning("interprete_libre_faq_numerica_sin_respaldo",
                            trace_id=trace_id,
                            sin_respaldo=_fix_faq["verificacion"]["sin_respaldo"][:8],
                            respuesta_preview=respuesta[:200])
        except Exception as e:
            log.warning("interprete_libre_faq_numerica_error",
                        trace_id=trace_id, error=str(e)[:160])
    # ── VERIFICADOR DE CITA DE PROSA (ladrillo 2 del RAG) ───────────────────
    # Cuando el solver condujo apoyandose en la guia de venta, chequea que cada
    # bloque de criterio que declaro (meta['prosa_citada']) exista de verdad en
    # el corpus jurado. Asi la prosa de venta queda ATADA a la fuente igual que
    # el numero: si un id citado no resuelve, se loguea (candado + sonda).
    # Deterministico, sin llamar al modelo; no reescribe, la prosa buena sale
    # igual. En el camino sano los ids salen del propio corpus y siempre validan.
    if _via_solver:
        try:
            from app.core.verificador_cita import verificar_meta
            _vc = verificar_meta(meta)
            if _vc["citas"]:
                (log.warning if not _vc["ok"] else log.info)(
                    "interprete_libre_cita_prosa", trace_id=trace_id,
                    validas=_vc["validas"], invalidas=_vc["invalidas"])
            elif meta.get("turno_criterio"):
                # ATADURA DURA (gate blando): turno de criterio que, pese al
                # forzado de la tool, quedo SIN prosa consultada. No se degrada
                # (filtro blando, no matar la venta), pero se marca fuerte: es la
                # mina para ver si el forzado falla y decidir endurecerlo.
                log.warning("interprete_libre_cita_criterio_sin_respaldo",
                            trace_id=trace_id, respuesta_preview=(respuesta or "")[:160])
        except Exception as e:
            log.warning("interprete_libre_cita_error", trace_id=trace_id,
                        error=str(e)[:160])

    # ── FISCAL NIVEL 2: INVARIANTES DE INTENCION (determinista, 17-jul) ─────
    # La respuesta se cruza contra la lectura ESTRUCTURADA del turno: un
    # producto de marca/origen EXCLUIDO por el cliente se poda quirurgico (la
    # red del filtro de universo); todo ofrecido arriba del TOPE se marca.
    # Estructura contra estructura, sin LLM, jamas rompe el turno.
    try:
        from app.core.verificador_intencion import verificar_intencion
        from app.core.estado_venta import preferencias_actualizadas as _prefs_turno
        _prefs_fiscal = _prefs_turno(
            conv.get("preferencias_cliente"), interp, raw_message)
        if _prefs_fiscal:
            _vi = verificar_intencion(respuesta, meta, _prefs_fiscal, tienda_id)
            if _vi["eventos"]:
                log.warning("interprete_libre_intencion_fiscal",
                            trace_id=trace_id, eventos=_vi["eventos"],
                            corrigio=_vi["respuesta"] != respuesta)
                respuesta = _vi["respuesta"]
    except Exception as e:
        log.warning("interprete_libre_intencion_error", trace_id=trace_id,
                    error=str(e)[:120])

    # ── FISCAL NIVEL 3: CHECKER DE AFIRMACIONES BLANDAS (17-jul) ────────────
    # Solo cuando el generador/solver condujo (prosa del modelo en juego): un
    # modelo chico compara cada afirmacion de HECHO contra la evidencia del
    # turno (fichas, FAQ, prosa jurada) con veredicto atado por enum. El
    # CODIGO decide: sin_respaldo verbatim y sin digitos se poda; el resto se
    # marca (checker_sin_respaldo = radar). Error o sin clave -> no-op.
    if _via_solver and respuesta and respuesta != settings.FALLBACK_MESSAGE:
        try:
            from app.core.checker_afirmaciones import chequear, podar_sin_respaldo
            _chk = await chequear(respuesta, meta, tienda_id, trace_id)
            if _chk and _chk["sin_respaldo"]:
                _texto_chk, _podadas = podar_sin_respaldo(
                    respuesta, _chk["sin_respaldo"])
                log.warning("interprete_libre_checker_sin_respaldo",
                            trace_id=trace_id,
                            sin_respaldo=_chk["sin_respaldo"][:6],
                            podadas=len(_podadas))
                respuesta = _texto_chk
            elif _chk is not None:
                log.info("interprete_libre_checker_ok", trace_id=trace_id,
                         afirmaciones=len(_chk["afirmaciones"]))
        except Exception as e:
            log.warning("interprete_libre_checker_error", trace_id=trace_id,
                        error=str(e)[:120])

    proofs_recientes = (proofs_memoria + proofs_turno)[-settings.VERIFICADOR_PROOF_MEMORY:]

    # ── PASO 2a-bis: GUARDIA DE PROMESAS PROHIBIDAS (enforce) ───────────────
    # Linea cero del TEXTO: un conjunto cerrado de afirmaciones que el bot no puede
    # decir aunque el cliente insista (dia exacto de entrega, retiro en local,
    # servicios fuera de la FAQ). Si la deteccion determinista dispara, el codigo
    # reescribe el mensaje sin la promesa antes de mandarlo. Una sola llamada extra
    # al modelo y SOLO en los turnos que disparan, no en todos.
    if respuesta != settings.FALLBACK_MESSAGE:
        try:
            from app.core.guardia_promesas import (
                detectar, reescribir_sin_promesas, cuarentena_prohibidas)
            clases = detectar(respuesta)
            if clases:
                log.warning("interprete_libre_promesa_prohibida", trace_id=trace_id,
                            clases=clases, respuesta_preview=respuesta[:200])
                nueva = ""
                try:
                    nueva = await reescribir_sin_promesas(respuesta, clases, trace_id)
                except Exception as e:
                    log.warning("interprete_libre_reescritura_error",
                                trace_id=trace_id, error=str(e)[:120])
                if nueva and not detectar(nueva):
                    respuesta = nueva
                    log.info("interprete_libre_promesa_reescrita",
                             trace_id=trace_id, clases=clases)
                else:
                    # Red DETERMINISTA (hueco real 4-jul: el editor devolvio vacio
                    # y una direccion inventada salio al cliente). Se podan las
                    # lineas con promesa; si no queda mensaje decente, canned.
                    poda = cuarentena_prohibidas(nueva or respuesta)
                    if poda and not detectar(poda):
                        respuesta = poda
                        log.warning("interprete_libre_promesa_cuarentena",
                                    trace_id=trace_id, clases=clases,
                                    respuesta_preview=poda[:200])
                    else:
                        respuesta = _fallback_o_curada(raw_message, interp, tienda_id, trace_id)
                        log.warning("interprete_libre_promesa_bloqueada",
                                    trace_id=trace_id, clases=clases)
        except Exception as e:
            log.warning("interprete_libre_guardia_error", trace_id=trace_id,
                        error=str(e)[:160])

    # ── HONESTIDAD DE BOT (gatillo determinista, pendiente del disclaimer) ──
    # "sos un robot?" exige la verdad; si el solver la esquivo, se antepone.
    if respuesta != settings.FALLBACK_MESSAGE:
        _resp_honesta = _asegurar_honestidad_bot(
            raw_message, respuesta, _business_name(tienda_id))
        if _resp_honesta != respuesta:
            respuesta = _resp_honesta
            log.info("interprete_libre_honestidad_bot", trace_id=trace_id)

    # ── GUARDA DE DIVERGENCIA (caso interprete BIEN, solver MAL) ────────────
    # Si el interprete marco ofrecer_opciones (dos caminos, no se puede elegir con
    # certeza) pero el solver NO planteo la eleccion, se FUERZA la pregunta A/B.
    # Asi la divergencia se resuelve con una pregunta de confirmacion, no con una
    # eleccion silenciosa del solver. Si esto dispara, no se cierra este turno: no
    # se cierra sobre un producto todavia ambiguo.
    ambiguo_forzado = False
    if respuesta != settings.FALLBACK_MESSAGE and not _via_solver:
        _preg_amb = _forzar_pregunta_si_ambiguo(interp, respuesta)
        if _preg_amb:
            respuesta = _preg_amb
            ambiguo_forzado = True
            log.info("interprete_libre_pregunta_ambiguo_forzada", trace_id=trace_id)

    # ── GUARDA DE PRODUCTO (paso 2: interprete BIEN, solver MAL sobre el QUE) ──
    # Extiende el MISMO patron de la guarda A/B al producto unico: si el
    # interprete resolvio con confianza un producto que el certificador confirma
    # como unico y real, y el solver mostro OTRO, se re-ancla al producto
    # correcto con su linea REAL del catalogo y una pregunta de confirmacion. Si
    # dispara, no se cierra este turno: el producto todavia no esta confirmado.
    producto_forzado = False
    if respuesta != settings.FALLBACK_MESSAGE and not ambiguo_forzado and not _via_solver:
        try:
            _re_prod = _reanclar_si_producto_divergente(
                interp, respuesta, _ids_mostrados, tienda_id)
            if _re_prod:
                respuesta = _re_prod
                producto_forzado = True
                log.warning("interprete_libre_producto_reanclado",
                            trace_id=trace_id,
                            producto=str(interp.get("producto_resuelto"))[:60])
            # GUARDA DEL PEDIDO POR CATEGORIAS: si el cliente pidio N x
            # categoria SIN modelos y el solver igual armo un presupuesto, lo
            # reemplaza el mensaje correcto construido por el codigo (opciones
            # reales + pregunta de modelos). Prioridad 1 de Martin, 8-jul.
            # Solo sobre una respuesta que NO compuso el codigo: si ya salio una
            # curada, la confirmacion de criterio o el bloque sellado, no se
            # re-fuerza (mi pregunta de confirmacion dice "presupuesto" y este
            # guard la confundia con un presupuesto inventado, bug 9-jul).
            if (not producto_forzado and _cats_pedido and not _tools_precalc
                    and not respuesta_curada_servida):
                _re_cats = _forzar_opciones_si_presupuesto(
                    respuesta, _cats_pedido, tienda_id)
                if _re_cats:
                    respuesta = _re_cats
                    producto_forzado = True
                    log.warning("interprete_libre_opciones_forzadas",
                                trace_id=trace_id, cats=_cats_pedido)
            # GUARDA DEL MAS BARATO: mismo patron, sobre el minimo que computo
            # la guia determinista. Si el solver afirmo que el mas barato es
            # OTRO producto, se re-ancla al real (dato del catalogo).
            # NO corre sobre un pedido SELLADO ni cuando el cliente pidio un
            # producto PUNTUAL con pedido armado (banco 11-jul: el cliente
            # cerro con el M170 anotado y la guarda reescribio la respuesta
            # correcta al DX-110 por un criterio sticky contaminado).
            _pidio_puntual = bool(
                str(interp.get("producto_resuelto") or "").strip()
                and (interp.get("pedido") or []))
            if (not producto_forzado and _id_barato
                    and not _sellado_pedido and not _pidio_puntual):
                _re_barato = _reanclar_si_barato_divergente(
                    respuesta, _id_barato, _ids_mostrados, tienda_id)
                if _re_barato:
                    respuesta = _re_barato
                    producto_forzado = True
                    log.warning("interprete_libre_barato_reanclado",
                                trace_id=trace_id, id_barato=_id_barato)
        except Exception as e:
            log.warning("interprete_libre_producto_guarda_error",
                        trace_id=trace_id, error=str(e)[:120])

    # ── PASO 2b: CIERRE (codigo) — capta el lead, pide datos, manda el link ──
    # El codigo toma el control SOLO cuando hay que cerrar: detecta la decision de
    # compra por la interpretacion, junta nombre/telefono/direccion/forma de pago y
    # genera el link de Mercado Pago con el total VERIFICADO de la calculadora (de
    # presentacion, nunca un monto del modelo). Si no hay cierre, la respuesta libre
    # del solver queda intacta. El presupuesto sale del turno o de la memoria.
    _present_turno = _presupuesto_de_meta(meta)
    presupuesto = _present_turno or (conv.get("ultimo_presupuesto") or "")
    # Presupuesto NUEVO = la calculadora dio un total ESTE turno (no de memoria).
    # Es el momento natural para la pregunta suave de cierre, asi no se repite.
    presupuesto_nuevo = bool(_present_turno)

    # ── ACUMULAR DATOS DEL CLIENTE turno a turno (raiz del re-pedido) ────────
    # El cliente suele dar la direccion, el pago o el nombre ANTES de la decision
    # de compra, o DENTRO de un mensaje de otra intencion (ej una cotizacion que ya
    # menciona "pago transferencia"). Antes la extraccion estaba atada a la intencion
    # (solo aporta_dato/decision_compra), asi que ese dato se perdia y el cierre lo
    # volvia a pedir. Ahora: (1) la extraccion DETERMINISTA (telefono, pago,
    # direccion por patron) corre SIEMPRE, barata y sin LLM; (2) el extractor LLM
    # corre cuando el interprete sugiere datos O el mensaje trae numeros/cue de dato.
    # El acumulado viaja al cierre y se persiste al final del turno.
    _intent = interp.get("intencion") if isinstance(interp, dict) else None
    datos_previos = conv.get("datos_cliente_parciales") or {}
    datos_turno: dict = {}
    try:
        from app.core.cierre import extraer_determinista, extraer_datos_cliente
        # Determinista, en CADA turno: el codigo manda en los datos.
        datos_turno.update(extraer_determinista(raw_message))
        # LLM, cuando hay senal de dato (intencion o el texto lo parece).
        if _intent in ("aporta_dato", "decision_compra") or _parece_aportar_dato(raw_message):
            for k, v in extraer_datos_cliente(raw_message, trace_id).items():
                if v:
                    datos_turno[k] = v
    except Exception as e:
        log.warning("interprete_libre_extractor_error", trace_id=trace_id,
                    error=str(e)[:120])
    datos_acumulados = {**datos_previos, **datos_turno}
    if datos_turno:
        log.info("interprete_libre_datos_turno", trace_id=trace_id,
                 user_id=user_id, intencion=_intent,
                 campos=sorted(datos_turno.keys()),
                 acumulado=sorted(datos_acumulados.keys()))

    # El flag one-shot del gatillo de cierre (D) ya se leyo arriba (condiciona
    # tambien el atajo curado): si el turno pasado el bot hizo la pregunta de
    # cierre, este turno la respuesta del cliente la decide.
    meta_lead: dict = {}
    # No se cierra cuando una guarda forzo una pregunta (ambiguedad A/B o
    # re-ancla de producto): el producto todavia no esta confirmado, cerrar seria
    # sobre algo indefinido.
    if (respuesta != settings.FALLBACK_MESSAGE
            and not ambiguo_forzado and not producto_forzado):
        try:
            _, meta_lead = await procesar_mensaje_para_lead(
                user_id, canal, tienda_id, raw_message, respuesta, trace_id,
                interpretacion=interp if isinstance(interp, dict) else None,
                presupuesto=presupuesto,
                datos_turno=datos_turno, datos_previos=datos_acumulados,
                presupuesto_nuevo=presupuesto_nuevo,
                pregunta_cierre_hecha=pregunta_cierre_previa)
            if meta_lead.get("respuesta_directa"):
                respuesta = meta_lead["respuesta_directa"]
                log.info("interprete_libre_cierre", trace_id=trace_id,
                         accion=meta_lead.get("accion"))
        except Exception as e:
            log.warning("interprete_libre_lead_error", trace_id=trace_id,
                        error=str(e)[:160])
    # Queda marcado el turno en que se hizo la pregunta; al siguiente se consume y
    # vuelve a False, asi la pregunta se hace una sola vez. EXCEPCION: si el cliente
    # respondio con una duda o pregunta, el cierre sigue PENDIENTE (no se consume),
    # asi un "dale" en el turno siguiente todavia cierra.
    pregunta_cierre_hecha = (
        meta_lead.get("accion") in ("pregunta_cierre", "pregunta_pendiente_cierre"))

    # ── PISO DE COMPOSICION (fila Z de la matriz, 17-jul) ───────────────────
    # NUNCA sale un turno sin sustancia. Visto en la consigna: las podas
    # (checker, prosa) dejaban un residuo vacio ("Te cuento,") y en el turno 1
    # el saludo fijo lo tapaba quedando saludo pelado ante una pregunta real.
    # Regla determinista: si el mensaje del cliente traia CONTENIDO y la
    # respuesta quedo sin dato, sin pregunta y corta, sale el honesto de la
    # fila Z (no confirmado + derivacion + repregunta que sigue vendiendo).
    # El warning es el radar: cada disparo es un hueco de fuente o un residuo
    # de poda para mirar.
    if (respuesta != settings.FALLBACK_MESSAGE
            and _mensaje_con_contenido(raw_message)
            and _sin_sustancia(respuesta)):
        log.warning("interprete_libre_piso_composicion", trace_id=trace_id,
                    residuo=(respuesta or "")[:120])
        respuesta = (
            "Eso puntual no lo tengo confirmado ahora como para dártelo "
            "seguro. Lo consulto con el equipo y te escribo, o si preferís "
            "te paso con una persona. Mientras tanto contame qué estás "
            "buscando, así te muestro opciones con precio y stock reales.")

    # ── SALUDO INICIAL (solo el PRIMER mensaje de la charla) ────────────────
    # Determinista: saludo cordial + aviso de que es una herramienta automatica,
    # UNA sola vez (pedido de Martin 8-jul; el prompt solo ya fallo en real para
    # esto). Los turnos siguientes no lo repiten. Si el solver ya arranco
    # saludando, su saludo se recorta para no saludar dos veces.
    if not history:
        respuesta = _con_saludo_inicial(respuesta, _business_name(tienda_id))
        log.info("interprete_libre_saludo_inicial", trace_id=trace_id)

    # El cliente recibe la respuesta limpia: el cartel de interpretacion se quito
    # (ahora va al log). La interpretacion se sigue viendo en interprete_libre_interpretacion.
    respuesta_final = respuesta

    # ── MEMORIA: guardar el turno (el solver siempre recuerda la charla) ──
    history = history + [
        {"role": "user", "content": raw_message},
        {"role": "assistant", "content": respuesta},
    ]
    # MEMORIA LARGA (8-jul): los turnos que el recorte descarta se FUNDEN en el
    # resumen acumulado (campo summary, antes iba vacio y lo viejo se perdia).
    # Cubre retomar charla vieja, contradiccion lejana y dato dado hace muchos
    # turnos (C2-C4). Solo llama al LLM en los turnos donde la charla desborda
    # el tope; si falla, red determinista en memoria_larga.
    resumen_charla = conv.get("summary", "") or ""
    _descartados = history[:-(settings.HISTORY_LIMIT * 2)]
    if _descartados:
        try:
            from app.core.memoria_larga import actualizar_resumen
            resumen_charla = await actualizar_resumen(
                resumen_charla, _descartados, trace_id)
        except Exception as e:
            log.warning("interprete_libre_memoria_larga_error",
                        trace_id=trace_id, error=str(e)[:120])
    history = history[-(settings.HISTORY_LIMIT * 2):]

    # ── ESTADO DE VENTA: mergear lo de este turno con la memoria y persistir ──
    # Los datos deterministas (productos con precio real, carrito, envio) que las
    # tools generaron este turno se suman a los de turnos anteriores, asi el bloque
    # del proximo turno los tiene a la vista. Si este turno no llamo una tool, queda
    # lo que ya habia en memoria.
    # Los productos que el bot MOSTRO ([[PROD:id]] estampados, ej. los que trae la
    # guia determinista) tambien son vistos, aunque el turno no haya llamado tools.
    # Sin esto el turno de la guia no deja rastro y el solver del proximo turno
    # ADIVINA el id de memoria (visto en el banco: pidio el total con un teclado de
    # $172.500 en vez del de $12.000 mostrado). Nombre y precio salen del catalogo.
    mostrados: list[dict] = []
    if _ids_mostrados:
        from app.storage.firestore_client import get_product_by_id as _gpid_mem
        for _pid in {i.upper() for i in _ids_mostrados}:
            try:
                _pp = _gpid_mem(_pid, tienda_id=tienda_id)
            except Exception:
                _pp = None
            if (isinstance(_pp, dict) and _pp.get("nombre")
                    and isinstance(_pp.get("precio_ars"), (int, float))):
                mostrados.append({"id": _pid, "nombre": _pp["nombre"],
                                  "precio": int(_pp["precio_ars"])})
    productos_vistos = merge_productos(
        conv.get("productos_vistos") or [], productos_de_meta(meta) + mostrados)
    # El carrito NO se actualiza en un turno SIN intencion de compra: si el
    # cliente dijo "no quiero nada mas" (intencion otra) y el solver igual corrio
    # una calculadora especulativa, ese detalle NO pisa el pedido del cliente.
    # Visto en el banco (8-jul): un microfono especulativo entro al carrito en el
    # turno del rechazo y el sello del turno siguiente lo dio por vigente.
    _cambia_carrito = _intent not in ("otra",)
    carrito_vigente = ((carrito_de_meta(meta) if _cambia_carrito else [])
                       or (conv.get("carrito_vigente") or []))
    if _carrito_vaciado:
        # El rechazo dejo el pedido vacio: no vuelve el carrito de memoria.
        carrito_vigente = []
    elif _carrito_editado:
        # El rechazo recalculo el pedido sin el item: manda el nuevo aunque
        # la intencion del turno haya sido "otra".
        carrito_vigente = carrito_de_meta(meta) or carrito_vigente
    ultima_localidad = envio_de_meta(meta) or (conv.get("ultima_localidad") or "")
    # TODAS las localidades cotizadas con exito (multi-destino), no solo la
    # ultima: si este turno no se cotizo ninguna queda lo de memoria. Sin esto,
    # "y el total de todo?" al turno siguiente de cotizar dos destinos vuelve a
    # pedir un CP que el cliente ya dio (visto en el banco, guion multi-destino).
    ultimas_localidades = get_envio_localidades() or (
        conv.get("ultimas_localidades") or [])
    # Criterio del cliente ("lo mas barato"): lo leen los DOS interpretes (regex
    # del codigo + campo del LLM, que entiende "eco" y abreviaturas) y es STICKY.
    # Una vez dicho persiste entre turnos hasta que el cliente diga otro, asi el
    # bot no vuelve a preguntar modelo ni color (arreglo B).
    from app.core.estado_venta import criterio_llm as _criterio_llm
    # OJO: una OBJECION de precio ("mi hermano dice que en otro lado esta
    # mas barato") NO es un criterio del cliente; dejaba sticky "más barato"
    # y contaminaba los turnos siguientes (banco 11-jul). Con ruteo B4/B5,
    # el criterio del mensaje no se toma.
    try:
        from app.core.ruteo_venta import rutear_venta as _rv_crit
        _cat_crit = (_rv_crit(raw_message, interp, estado) or {}).get(
            "categoria")
    except Exception:
        _cat_crit = None
    if _cat_crit in ("B4", "B5"):
        # Regateo u objecion: NINGUNA lectura de criterio del mensaje (ni
        # regex ni LLM) queda sticky; solo persiste lo que ya habia.
        criterio_cliente = conv.get("criterio_cliente") or ""
    else:
        criterio_cliente = (
            detectar_criterio(raw_message)
            or ("más barato" if criterio_del_interprete(interp) else "")
            or ("intermedio" if _criterio_llm(interp) == "intermedio" else "")
            or (conv.get("criterio_cliente") or ""))
    # Provincia del cliente: se detecta determinista y es STICKY. Una vez dada
    # persiste entre turnos y se aplica a TODOS los destinos, asi el bot no repide
    # el CP de cada pueblo (arreglo C, el 'ya te dije pueblo y provincia'). La
    # deteccion de este turno ya se hizo al arranque (_prov_msg, la usa el estado).
    provincia_envio = _prov_msg or (conv.get("provincia_envio") or "")
    # ANCLA de producto anotado: se actualiza con lo resuelto este turno (ya
    # pasado por aplicar_ancla_producto) y se limpia solo ante una negacion
    # que NOMBRA al ancla. Conservador: ante duda queda el previo.
    try:
        from app.core.estado_venta import producto_anotado_actualizado
        from app.storage.firestore_client import get_all_products as _gap_save
        producto_anotado = producto_anotado_actualizado(
            conv.get("producto_anotado"), interp, raw_message,
            _gap_save(tienda_id=tienda_id))
    except Exception as e:
        log.warning("interprete_libre_ancla_save_error", trace_id=trace_id,
                    error=str(e)[:120])
        producto_anotado = conv.get("producto_anotado") or {}
    # PREFERENCIAS sticky (16-jul): exclusiones por origen/marca, tope de
    # presupuesto y uso previsto que leyo el interprete este turno se funden
    # con las previas y persisten; las consume el generador filtrando el
    # universo por construccion.
    try:
        from app.core.estado_venta import preferencias_actualizadas
        preferencias_cliente = preferencias_actualizadas(
            conv.get("preferencias_cliente"), interp, raw_message)
        if preferencias_cliente != (conv.get("preferencias_cliente") or {}):
            log.info("interprete_libre_preferencias", trace_id=trace_id,
                     preferencias=preferencias_cliente)
    except Exception as e:
        log.warning("interprete_libre_preferencias_error", trace_id=trace_id,
                    error=str(e)[:120])
        preferencias_cliente = conv.get("preferencias_cliente") or {}

    latency_ms = int((time.time() - t0) * 1000)
    try:
        save_conversation(user_id, history, resumen_charla,
                          tienda_id=tienda_id,
                          estado_conversacion=estado_nuevo,
                          ultimo_presupuesto=presupuesto,
                          proofs_recientes=proofs_recientes,
                          productos_vistos=productos_vistos,
                          carrito_vigente=carrito_vigente,
                          ultima_localidad=ultima_localidad,
                          ultimas_localidades=ultimas_localidades,
                          criterio_cliente=criterio_cliente,
                          provincia_envio=provincia_envio,
                          destino_unico=destino_unico,
                          # El pendiente de modelos persiste hasta que el
                          # pedido se selle o se forme carrito; asi ningun
                          # turno intermedio puede inventar un presupuesto.
                          # Lista de DICTS, nunca lista de listas: Firestore
                          # real rechaza arrays anidados y tiraba el save
                          # entero (bug real 8-jul, amnesia en produccion).
                          pedido_categorias_pendiente=(
                              [{"cantidad": int(n), "categoria": str(c)}
                               for n, c in _cats_pedido]
                              if (_cats_pedido and not _tools_precalc
                                  and not carrito_vigente) else []),
                          # Confirmacion de criterio pendiente: prendida cuando
                          # los dos interpretes del "mas barato" divergen y se
                          # pregunto. El turno siguiente, un "si" cuenta como
                          # coincidencia y arma el total.
                          criterio_confirmar_pendiente=_criterio_confirmar,
                          pregunta_cierre_hecha=pregunta_cierre_hecha,
                          datos_cliente_parciales=datos_acumulados,
                          producto_anotado=producto_anotado,
                          preferencias_cliente=preferencias_cliente)
    except Exception as e:
        log.warning("interprete_libre_save_failed", trace_id=trace_id,
                    error=str(e)[:120])
    try:
        log_message(user_id, raw_message, respuesta_final,
                    meta.get("tools_called", []),
                    latency_ms, trace_id, tienda_id=tienda_id)
    except Exception as e:
        log.warning("interprete_libre_log_failed", trace_id=trace_id,
                    error=str(e)[:120])

    # Preview de la respuesta del bot en CADA turno: sin esto el texto que el bot
    # contesta no queda en Cloud Logging (solo en Firestore y solo en los WARNING
    # de correccion), y se diagnostica a ciegas. Es la salida del bot, no dato del
    # cliente; truncado para no inflar el log. Permite leer que dijo el bot por
    # trace_id sin depender de copiar a mano.
    log.info("interprete_libre_ok", trace_id=trace_id, ms=latency_ms,
             respuesta_preview=(respuesta_final or "")[:300])
    return respuesta_final
