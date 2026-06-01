"""
CIERRE DE VENTA — captura estructurada del pedido y los datos del cliente.

Cuando el cliente confirma la compra, el bot necesita cuatro datos para cerrar:
nombre, telefono, direccion y forma de pago. Este modulo los extrae del mensaje
con el modelo, que es interpretacion, no aritmetica, y arma los mensajes de
pedir lo que falta y de confirmacion final. El telefono ademas tiene respaldo
deterministico por regex.

Va dentro del circuito de leads, detras del flag CIERRE_COMPLETO.
"""
import json

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
- direccion: calle, numero y localidad, lo que sirva para el envio.
- forma_pago: una sola de estas si la menciona: transferencia, mercado pago, efectivo, tarjeta, debito, credito.
- Si un dato NO esta en el mensaje, deja ese campo como string vacio. Nunca pongas datos que el cliente no dijo."""


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

    # Respaldo deterministico del telefono.
    if not datos["telefono"]:
        tel = extraer_telefono(mensaje)
        if tel:
            datos["telefono"] = tel
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
