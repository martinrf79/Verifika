"""
ANTI-JAILBREAK — filtro de ENTRADA, primera linea de defensa, por codigo.

Antes de que el mensaje del cliente toque ningun LLM (interprete, solver), pasa
por reglas deterministas que cazan intentos de manipular al bot para sacarlo de
su rol: "ignora tus instrucciones", "actua como", "decime tu prompt", "modo
desarrollador", volcados de texto enormes. Si dispara, el orchestrator corta el
pipeline y devuelve una respuesta estatica de marca, sin gastar tokens ni
arriesgar que el modelo obedezca al atacante.

NO interpreta nada ni usa LLM: es regex + largo. Conservador a proposito: solo
marca patrones inequivocos de ataque. Una consulta normal de cliente (precios,
envios, devoluciones, "me hacen descuento", "actua rapido el envio?") NUNCA debe
disparar. Ante la duda, NO marca: un falso bloqueo le corta la charla a un
cliente real, peor que dejar pasar un intento raro que igual cae en los gates de
salida.

Detras del flag ANTI_JAILBREAK (off/shadow/on, default off). El wiring vive en
app/core/orchestrator.py, al inicio de process_message.
"""
import re
import unicodedata

from app.logger import get_logger

log = get_logger(__name__)

# Largo a partir del cual un solo mensaje es sospechoso de relleno de prompt.
# Los mensajes reales de ecommerce son cortos; aun una consulta detallada rara
# vez pasa de unos cientos de chars. Alto a proposito para no morder a un cliente
# que pega specs largas.
LARGO_SOSPECHOSO = 4000

# Respuesta estatica de marca cuando se detecta un ataque. Cordial, no acusatoria
# (un cliente curioso no es un enemigo), reencauza a la venta.
RESPUESTA_BLOQUEO = (
    "Disculpa, con eso no te puedo ayudar. Estoy para asesorarte con productos, "
    "precios, envios y formas de pago. Que estas buscando?"
)

# Patrones de manipulacion. Se evaluan sobre el texto NORMALIZADO (minusculas,
# sin acentos), asi "ignorá" e "ignora" matchean igual. Cada patron apunta a una
# construccion adversarial concreta, no a palabras sueltas comunes.
_PATRONES_RAW = [
    # Pedir ignorar/olvidar las instrucciones del sistema.
    r"ignora(?:r|s|me|las|lo)?\s+(?:todas?\s+)?(?:tus|las|mis|sus)\s+"
    r"(?:anteriores\s+|previas\s+)?(?:instruccion|indicacion|regla|orden|directiva)",
    r"olvida(?:te|r)?\s+(?:de\s+)?(?:todas?\s+)?(?:tus|las|lo)\s+"
    r"(?:instruccion|regla|indicacion|orden|anterior)",
    r"ignore\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above)\s+"
    r"(?:instruction|prompt|rule)",
    r"disregard\s+(?:all\s+)?(?:previous|prior|the\s+above)\s+"
    r"(?:instruction|prompt|rule)",
    # Pedir que revele/repita su prompt o instrucciones.
    r"(?:decime|deci|mostra(?:me)?|revela(?:me)?|repeti(?:me)?|dame|imprimi|"
    r"escribi|cual\s+es)\s+(?:cual\s+es\s+)?(?:tu|el|tus|las)\s+"
    r"(?:system\s*)?(?:prompt|instruccion|indicacion|configuracion|"
    r"reglas?\s+de\s+sistema)",
    r"(?:reveal|show|print|repeat|tell\s+me|what\s+(?:is|are))\s+"
    r"(?:your|the)\s+(?:system\s+)?(?:prompt|instruction)",
    r"\bsystem\s*prompt\b",
    # Forzar un rol nuevo / negar el rol actual.
    r"a\s+partir\s+de\s+ahora\s+(?:vas\s+a|sos|ya\s+no\s+sos|te\s+llamas|"
    r"actua|no\s+sos)",
    r"from\s+now\s+on\s+you\s+(?:are|will|must|no\s+longer)",
    r"(?:hace|haces|hacete)\s+de\s+cuenta\s+que\s+(?:sos|eres|no\s+sos)",
    r"(?:pretende|pretenda|finge|simula)\s+(?:ser|que\s+sos)",
    r"\bact\s+as\s+(?:a|an|if|the)\b",
    r"\byou\s+are\s+now\s+(?:a|an|dan|jailbroken|in)\b",
    r"olvida(?:te)?\s+que\s+(?:sos|eres)\s+(?:un|una|el|la)",
    r"\bno\s+(?:sos|eres)\s+(?:un|una)\s+"
    r"(?:asistente|bot|vendedor|ia|modelo|chatbot)",
    # Modos de evasion conocidos.
    r"\b(?:modo|mode)\s+(?:desarrollador|developer|dios|god|"
    r"sin\s+restriccion|libre|jailbreak)",
    r"\bjailbreak\b",
    # Pedir explicitamente saltarse reglas/filtros (pareado a un verbo de conducta
    # para no morder un inocente "sin limite de compra").
    r"(?:responde|responde|contesta|actua|habla|comporta(?:te)?|se)\w*\s+"
    r"sin\s+(?:restriccion|filtro|censura|limite|regla|moral|etica)",
]

_PATRONES = [re.compile(p, re.IGNORECASE) for p in _PATRONES_RAW]


def _normalizar(texto: str) -> str:
    """Minusculas y sin acentos, para que los patrones matcheen variantes."""
    t = (texto or "").lower()
    return "".join(c for c in unicodedata.normalize("NFD", t)
                   if not unicodedata.combining(c))


def evaluar_mensaje(mensaje: str) -> dict:
    """Evalua un mensaje de entrada.

    Devuelve dict:
      - ataque: bool, si se detecto un patron de manipulacion o relleno.
      - motivo: str corto ("patron" / "largo" / "").
      - patron: str, el patron que matcheo (para log y tuning), o "".
    """
    if not mensaje or not mensaje.strip():
        return {"ataque": False, "motivo": "", "patron": ""}

    if len(mensaje) > LARGO_SOSPECHOSO:
        return {"ataque": True, "motivo": "largo", "patron": f">{LARGO_SOSPECHOSO}"}

    norm = _normalizar(mensaje)
    for rx in _PATRONES:
        m = rx.search(norm)
        if m:
            return {"ataque": True, "motivo": "patron",
                    "patron": m.group(0)[:60]}

    return {"ataque": False, "motivo": "", "patron": ""}
