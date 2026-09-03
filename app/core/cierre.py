"""
CIERRE DE VENTA — captura estructurada del pedido y los datos del cliente.

Cuando el cliente confirma la compra, el bot necesita cuatro datos para cerrar:
nombre, telefono, direccion y forma de pago. Este modulo los extrae del mensaje
con el modelo, que es interpretacion, no aritmetica, y arma los mensajes de
pedir lo que falta y de confirmacion final. El telefono ademas tiene respaldo
deterministico por regex.

Va dentro del circuito de leads.
"""
import json
import re
import unicodedata

from app.config import get_settings
from app.logger import get_logger
from app.core.leads import extraer_telefono

log = get_logger(__name__)
settings = get_settings()

# LO QUE SE LE PIDE AL CLIENTE PARA CERRAR. Solo el NOMBRE (Martin, 1-ago,
# sobre la charla real donde el bot pidio nombre completo, DNI y una direccion
# por destino en el PRIMER mensaje). Pedir un formulario antes de que el cliente
# se decida espanta la venta, y el DNI ni siquiera lo necesitamos: el modelo se
# lo invento, nunca estuvo en esta lista.
#
# El telefono ya lo tenemos del canal y se completa solo. La direccion y la
# forma de pago se coordinan en el contacto, no se exigen de entrada: por eso
# salen de aca. Se siguen GUARDANDO si el cliente las dice -el extractor las
# sigue leyendo-, pero ya no frenan el cierre.
CAMPOS_REQUERIDOS = ["nombre"]

# Los datos que igual se leen y se guardan cuando aparecen, aunque no se pidan.
CAMPOS_OPCIONALES = ["telefono", "direccion", "forma_pago"]
CAMPOS_EXTRAIBLES = CAMPOS_REQUERIDOS + CAMPOS_OPCIONALES

# ── GATILLO DE CIERRE (arreglo D) ────────────────────────────────────────────
# El sistema hace UNA pregunta de cierre cuando ya hay intencion suficiente. La
# respuesta del cliente decide de forma DETERMINISTA, sin depender de la confianza
# del LLM: cualquier respuesta que no sea un no claro dispara el lead fuerte; un no
# lo toma un humano. Asi el gatillo no se cuelga esperando que el modelo reclasifique.
_NEG_INICIO_RE = re.compile(r"^\s*(no|nop|nel|nah|negativo|jamas)\b", re.IGNORECASE)
_NEG_FRASES_RE = re.compile(
    r"(todav[ií]a\s+no|ahora\s+no|no\s+por\s+ahora|no\s+gracias|no\s+me\s+interesa|"
    r"m[aá]s\s+adelante|otro\s+d[ií]a|lo\s+pienso|lo\s+voy\s+a\s+pensar|"
    r"d[eé]jame\s+pensar|despu[eé]s\s+(?:lo\s+)?veo|lo\s+veo\s+despu[eé]s)",
    re.IGNORECASE)


# UNA CORRECCION DEL PEDIDO NO ES UN NO A LA VENTA. "no, el teclado sacalo,
# dejame solo los mouse" empieza con "no" y es exactamente lo contrario a un
# rechazo: el cliente esta ajustando lo que va a comprar. Cazado por el banco
# repetido, cuarta tanda: el cierre lo leia como desinteres, le avisaba al dueño
# que el lead estaba tibio y le pegaba al cliente "cuando quieras retomar, aca
# estoy" abajo del presupuesto que le acababa de pasar.
_CORRIGE_PEDIDO_RE = re.compile(
    r"\b(?:sac[aá]\w*|quit[aá]\w*|elimin[aá]\w*|borr[aá]\w*|agreg[aá]\w*|"
    r"sum[aá]\w*|pon[eé]\w*|cambi[aá]\w*|dej[aá]\w*|mejor|en\s+vez\s+de|"
    r"en\s+lugar\s+de|solo\s+(?:el|la|los|las)|nada\s+m[aá]s\s+(?:el|la))\b",
    re.IGNORECASE)


def es_no_interesado(respuesta: str) -> bool:
    """True si la respuesta del cliente denota un no o falta de interes. Determinista:
    detecta la negacion al inicio ('no', 'no gracias') o frases de postergacion
    ('todavia no', 'mas adelante', 'lo pienso'). Todo lo demas NO es un no.

    Y una correccion del pedido NUNCA es un no, aunque arranque con "no"."""
    t = (respuesta or "").strip()
    if not t:
        return False
    if _CORRIGE_PEDIDO_RE.search(t):
        return False
    if _NEG_INICIO_RE.match(t):
        return True
    return bool(_NEG_FRASES_RE.search(t))


# Una duda o pregunta del cliente NO es una confirmacion de compra. Marcadores:
# el signo de pregunta, o cues de duda/interrogacion (estas seguro, en serio, cuanto,
# como, cuando, donde). Sin esto, una pregunta como "estas seguro que el envio llega
# a Santa Ana?" se tomaba como un si y el bot saltaba a pedir datos (apuro real visto
# en prod 1-jul).
_PREGUNTA_RE = re.compile(
    r"[¿?]|\b(seguro\s+que|est[aá]s?\s+seguro|est[aá]n\s+seguros?|en\s+serio|"
    r"de\s+verdad|es\s+cierto|es\s+verdad|me\s+lo\s+confirm|lo\s+confirm[aá]s|"
    r"realmente|cu[aá]nto|cu[aá]ntos|c[oó]mo|cu[aá]ndo|d[oó]nde|por\s+qu[eé]|"
    r"qu[eé]\s+tal)\b",
    re.IGNORECASE)


def parece_pregunta(mensaje: str) -> bool:
    """True si el mensaje es una pregunta o una duda del cliente. Determinista:
    detecta el signo de pregunta o cues de duda. Una pregunta se contesta, no
    cierra la venta."""
    return bool(_PREGUNTA_RE.search(mensaje or ""))


def dispara_lead_fuerte(pregunta_hecha: bool, respuesta: str) -> bool:
    """Gatillo del lead fuerte: solo dispara si el turno pasado se hizo la pregunta
    de cierre Y la respuesta no es un no NI una pregunta. Sin pregunta previa no
    dispara; un no lo toma un humano; una duda la contesta el bot y el cierre queda
    pendiente."""
    return (bool(pregunta_hecha) and not es_no_interesado(respuesta)
            and not parece_pregunta(respuesta))

# COMO SE NOMBRA CADA DATO QUE FALTA. Sale de la fuente, igual que la frase que
# lo contiene: si Martin quiere pedir "un celular" en vez de "un telefono de
# contacto", lo cambia en el json y nadie toca Python. El literal de al lado es
# la red por si el archivo faltara.
_ETIQUETAS_RESPALDO = {
    "nombre": "tu nombre y apellido",
    "telefono": "un telefono de contacto",
    "direccion": "la direccion de envio",
    "forma_pago": "la forma de pago",
}


def _etiqueta(clave: str) -> str:
    from app.core.guia_venta_prosa import etiqueta_dato
    return etiqueta_dato(clave, _ETIQUETAS_RESPALDO.get(clave, ""))

_EXTRACTOR_PROMPT = """Sos un extractor de datos para cerrar una venta. Del mensaje del cliente saca SOLO los datos que esten presentes, no inventes nada.

Devolve JSON estricto, sin texto antes ni despues:
{"nombre": "", "telefono": "", "direccion": "", "forma_pago": ""}

Reglas:
- nombre: nombre y apellido de la persona, si lo dice.
- telefono: solo numeros, si da un telefono.
- direccion: calle, numero y localidad, lo que sirva para el envio. Si el cliente da MAS DE UNA direccion (envios separados), devolvelas todas separadas por " | ".
- forma_pago: una sola de estas si la menciona: transferencia, mercado pago, efectivo, tarjeta, debito, credito.
- Si un dato NO esta en el mensaje, deja ese campo como string vacio. Nunca pongas datos que el cliente no dijo."""


# ── RESPALDOS DETERMINISTAS (sin LLM) ───────────────────────────────────────
# El codigo manda en los datos: forma de pago y direccion se pueden reconocer por
# patron con alta precision. Asi un dato dicho dentro de un mensaje de OTRA
# intencion (ej "presupuestame Cordoba con pago transferencia") igual se captura,
# sin depender de que el modelo lo saque ni de la puerta de intencion.

# Palabra de pago -> forma normalizada. Se matchea por palabra completa. La sigla
# 'mp' SOLO cuenta como Mercado Pago en contexto de pago (con mp, pago con mp): asi
# '48 mp de resolucion' de una camara no se toma como forma de pago (E9).
_FORMAS_PAGO = [
    (r"transferenc", "transferencia"),
    (r"\bmercado\s*pago\b", "mercado pago"),
    (r"(?:\bcon\b|\bpor\b|pag\w*|abon\w*|mando|transfier\w*)\s+(?:con\s+|por\s+)?mp\b",
     "mercado pago"),
    (r"efectiv", "efectivo"),
    (r"tarjeta", "tarjeta"),
    (r"\bdebito\b", "debito"),
    (r"\bcredito\b", "credito"),
]

# Negacion de una forma de pago: 'no quiero transferencia', 'nunca por tarjeta'.
# La forma NEGADA se descarta, asi 'no quiero transferencia, prefiero efectivo'
# captura efectivo y no la rechazada (E8). 'sin' queda afuera a proposito: 'pago
# sin recargo con transferencia' no niega la transferencia.
_NEG_PAGO = re.compile(r"\b(?:no|nunca|tampoco)\b|nada\s+de|prefiero\s+no",
                       re.IGNORECASE)

# Cue words que confirman que un numero es un domicilio, no una cantidad/precio.
_DIR_CUE = (r"calle|avenida|\bav\b|\bav\.|pasaje|\bpje\b|ruta|barrio|altura|"
            r"manzana|\bmza\b|departamento|\bdepto\b|\bpiso\b|direccion|"
            r"domicilio|envi[oa]\s+a\b|enviar\s+a\b|mandar\s+a\b")


def _sin_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def extraer_forma_pago(mensaje: str) -> str:
    """Forma de pago por frase clave, normalizada. '' si no hay ninguna clara.
    Descarta la forma que viene NEGADA ('no quiero transferencia') y, entre las que
    quedan, devuelve la primera del mensaje: asi gana la elegida, no la rechazada."""
    txt = _sin_acentos((mensaje or "").lower())
    candidatos: list[tuple[int, str]] = []
    for patron, forma in _FORMAS_PAGO:
        m = re.search(patron, txt)
        if not m:
            continue
        # La forma negada ('no quiero X') se descarta: se mira la ventana previa.
        if _NEG_PAGO.search(txt[max(0, m.start() - 20):m.start()]):
            continue
        candidatos.append((m.start(), forma))
    if not candidatos:
        return ""
    candidatos.sort()
    return candidatos[0][1]


def extraer_direccion(mensaje: str) -> str:
    """Direccion SOLO cuando hay una cue word de domicilio cerca de un numero, para
    no confundir cantidades/precios con un domicilio. Conservador (precision sobre
    cobertura); el resto lo saca el LLM. Si hay varias, las une con ' | '."""
    txt = mensaje or ""
    if not re.search(_DIR_CUE, _sin_acentos(txt.lower())):
        return ""
    encontradas: list[str] = []
    # "<cue> ... <palabra(s)> <numero 1-5 digitos>" -> tramo de domicilio.
    for m in re.finditer(r"([A-Za-zÀ-ÿ.\s]{2,40}?\d{1,5})", txt):
        # Si el numero es un plan de pago o una cantidad ('4 cuotas', '3 pagos',
        # '6 meses'), NO es una altura de domicilio: se descarta (E10).
        siguiente = txt[m.end():m.end() + 12]
        if re.match(r"\s*(?:cuota|pago|mes\b|meses|unidad|producto|persona|"
                    r"a[nñ]o|dia)", siguiente, re.IGNORECASE):
            continue
        tramo = m.group(1).strip(" ,.;")
        if re.search(r"\d", tramo) and len(tramo) >= 4:
            encontradas.append(re.sub(r"\s+", " ", tramo))
    vistos: list[str] = []
    for d in encontradas:
        if d not in vistos:
            vistos.append(d)
    return " | ".join(vistos[:3])


def extraer_determinista(mensaje: str) -> dict:
    """Datos sacables SIN LLM (telefono, forma de pago, direccion con cue). Pensado
    para correr en CADA turno: barato, alta precision, no atado a la intencion.
    Devuelve solo los campos que reconocio (no pone vacios)."""
    datos: dict = {}
    tel = extraer_telefono(mensaje)
    if tel:
        datos["telefono"] = tel
    fp = extraer_forma_pago(mensaje)
    if fp:
        datos["forma_pago"] = fp
    dir_ = extraer_direccion(mensaje)
    if dir_:
        datos["direccion"] = dir_
    return datos


def extraer_datos_cliente(mensaje: str, trace_id=None) -> dict:
    """Extrae los datos presentes en el mensaje. Devuelve dict con los cuatro
    campos, vacios los que no esten. Misma puerta al modelo que el resto del
    turno: `llm_reintento._cliente`. Si esa llamada falla, el respaldo
    determinista de abajo rellena lo que se pueda por patron."""
    datos = {c: "" for c in CAMPOS_EXTRAIBLES}
    try:
        from app.core.llm_reintento import _cliente, _modelo
        cli = _cliente()
        if cli is None:
            raise RuntimeError("sin cliente")
        r = cli.chat.completions.create(
            model=_modelo(),
            messages=[
                {"role": "system", "content": _EXTRACTOR_PROMPT},
                {"role": "user", "content": mensaje},
            ],
            temperature=0.0, max_tokens=160,
            extra_body={"reasoning_effort": "none"},
        )
        content = (r.choices[0].message.content or "").strip()
        if content.startswith("```"):
            content = content.split("```")[1] if "```" in content[3:] else content[3:]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        parsed = json.loads(content)
        for c in CAMPOS_EXTRAIBLES:
            v = str(parsed.get(c, "") or "").strip()
            if v:
                datos[c] = v
    except Exception as e:
        log.warning("cierre_extractor_error", trace_id=trace_id, error=str(e)[:150])

    # Respaldo deterministico: telefono, forma de pago y direccion por patron.
    # Solo rellena lo que el LLM dejo vacio; nunca pisa lo que el modelo si saco.
    for campo, valor in extraer_determinista(mensaje).items():
        if valor and not datos.get(campo):
            datos[campo] = valor
    return datos


def faltantes(lead: dict) -> list[str]:
    """Campos requeridos que el lead todavia no tiene."""
    return [c for c in CAMPOS_REQUERIDOS if not str(lead.get(c, "")).strip()]


def mensaje_pedir_datos(falt: list[str], insistencia: int = 0) -> str:
    """El pedido de datos del cierre.

    `insistencia` es cuantas veces YA se pidieron estos mismos campos. La
    primera vez se pide entero; de la segunda en adelante se dice distinto y
    mas corto. Antes esta funcion devolvia siempre el mismo bloque, asi que un
    cliente que tardaba dos turnos en pasar sus datos recibia el parrafo
    identico dos y tres veces seguidas: la repeticion mas visible que tenia el
    bot, y el banco no la veia porque probaba el otro modo de cierre.
    """
    from app.core.guia_venta_prosa import mensaje
    pend = [_etiqueta(c) for c in falt if c in _ETIQUETAS_RESPALDO]
    pend = [p for p in pend if p]
    if not pend:
        return mensaje("cierre_tengo_todo",
                       "Genial, ya tengo todo para cerrar tu pedido.")
    uno = len(pend) == 1
    cuerpo = pend[0] if uno else ", ".join(pend[:-1]) + " y " + pend[-1]
    if insistencia <= 0:
        clave = "cierre_falta_uno_completo" if uno else "cierre_faltan_varios_completo"
        respaldo = ("Genial. Para cerrar el pedido me falta {cosas}. Me lo pasas?"
                    if uno else
                    "Genial. Para cerrar el pedido me faltan {cosas}. Me los pasas?")
        return mensaje(clave, respaldo, cosas=cuerpo)
    if insistencia == 1:
        clave = "cierre_pendiente_uno" if uno else "cierre_pendiente_varios"
        respaldo = ("Me queda pendiente {cosas} y lo dejo tomado." if uno else
                    "Me quedan pendientes {cosas} y lo dejo tomado.")
        return mensaje(clave, respaldo, cosas=cuerpo)
    return mensaje("cierre_apenas_me_pases", "Apenas me pases {cosas} lo cierro.",
                   cosas=cuerpo)


def mensaje_confirmacion(lead: dict, presupuesto: str = "") -> str:
    from app.core.guia_venta_prosa import mensaje
    nombre = str(lead.get("nombre", "")).split(" ")[0] if lead.get("nombre") else ""
    partes = [mensaje("cierre_tomamos_pedido", "Listo{nombre}, tomamos tu pedido.",
                      nombre=(f" {nombre}" if nombre else ""))]
    # EL TITULO SOLO SI HAY CUENTA. De aca nacio el "Resumen:" huerfano que le
    # llego a Martin en TRES charlas: el titulo se pegaba y el bloque se podaba
    # despues, dejando la promesa sin nada abajo.
    if (presupuesto or "").strip():
        partes.append(mensaje("cierre_titulo_resumen", "Resumen:") + "\n" + presupuesto)
    direccion = str(lead.get("direccion", "")).strip()
    pago = str(lead.get("forma_pago", "")).strip()
    cola = mensaje("cierre_equipo_contacta", "El equipo te contacta para coordinar")
    if pago:
        cola += mensaje("cierre_coordina_pago", " el pago por {pago}", pago=pago)
    if direccion:
        cola += mensaje("cierre_coordina_envio", " y el envio a {direccion}",
                        direccion=direccion)
    cola += mensaje("cierre_gracias", ". Gracias por tu compra.")
    partes.append(cola)
    return "\n".join(partes)
