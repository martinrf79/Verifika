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
from app.verifika.llm_adapter import llm_complete
from app.core.leads import extraer_telefono

log = get_logger(__name__)
settings = get_settings()

CAMPOS_REQUERIDOS = ["nombre", "telefono", "direccion", "forma_pago"]

_ETIQUETAS = {
    "nombre": "tu nombre y apellido",
    "telefono": "un telefono de contacto",
    "direccion": "la direccion de envio",
    "forma_pago": "la forma de pago",
}

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
    campos, vacios los que no esten."""
    datos = {c: "" for c in CAMPOS_REQUERIDOS}
    try:
        r = llm_complete(
            messages=[
                {"role": "system", "content": _EXTRACTOR_PROMPT},
                {"role": "user", "content": mensaje},
            ],
            role="proposer", temperature=0.0, max_tokens=160, trace_id=trace_id,
        )
        content = r.get("content", "").strip()
        if content.startswith("```"):
            content = content.split("```")[1] if "```" in content[3:] else content[3:]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        parsed = json.loads(content)
        for c in CAMPOS_REQUERIDOS:
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


def mensaje_pedir_datos(falt: list[str]) -> str:
    pend = [_ETIQUETAS[c] for c in falt if c in _ETIQUETAS]
    if not pend:
        return "Genial, ya tengo todo para cerrar tu pedido."
    if len(pend) == 1:
        return f"Genial. Para cerrar el pedido me falta {pend[0]}. Me lo pasas?"
    cuerpo = ", ".join(pend[:-1]) + " y " + pend[-1]
    return f"Genial. Para cerrar el pedido me faltan {cuerpo}. Me los pasas?"


def mensaje_confirmacion(lead: dict, presupuesto: str = "") -> str:
    nombre = str(lead.get("nombre", "")).split(" ")[0] if lead.get("nombre") else ""
    saludo = f"Listo {nombre}, " if nombre else "Listo, "
    partes = [saludo + "tomamos tu pedido."]
    if presupuesto:
        partes.append("Resumen:\n" + presupuesto)
    direccion = str(lead.get("direccion", "")).strip()
    pago = str(lead.get("forma_pago", "")).strip()
    cola = "El equipo te contacta para coordinar"
    if pago:
        cola += f" el pago por {pago}"
    if direccion:
        cola += f" y el envio a {direccion}"
    cola += ". Gracias por tu compra."
    partes.append(cola)
    return "\n".join(partes)
