"""
GUARDIA DE PROMESAS PROHIBIDAS — linea cero anti-mentira para el TEXTO.

El verificador determinista cubre la PLATA: cada cifra tiene que salir de una
fuente real. Esto cubre el otro flanco, el que fallaba en las pruebas: un conjunto
CERRADO de afirmaciones de texto que el bot NUNCA puede emitir aunque el cliente
insista, porque mienten:

  1. dia_entrega: prometer un dia o fecha exacta de llegada. La politica solo da
     plazos en dias habiles; el dia depende de la logistica.
  2. retiro_local: ofrecer retiro o pasar a buscar por un local. La tienda es
     solo online.
  3. servicio_no_ofrecido: prometer un servicio que la tienda no hace (envoltorio
     o nota de regalo, instalacion, armado de PC, entrega en mano).

NO verifica VALORES (imposible en prosa). Detecta CLASES de frase peligrosa con
patrones deterministas. Si dispara, el codigo reescribe el mensaje SIN la promesa
antes de mandarlo: el solver vende libre y calido, pero estas mentiras le
resultan imposibles de decir. La reescritura es una sola llamada al LLM y SOLO
ocurre en los turnos que disparan, no en todos.

La lista de servicios no ofrecidos es politica de verifika_prod; cuando haya
multi-tienda, hacerla derivar de la FAQ.
"""
import re
import asyncio

from openai import OpenAI

from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()


# ── DETECCION (determinista, sin LLM) ───────────────────────────────────────

# Contexto de LLEGADA (no de despacho: despachar rapido es legitimo, lo que
# miente es prometer el DIA en que el pedido llega).
_ENTREGA = (r"(?:lleg\w*|entreg\w*|recib\w*|arrib\w*|tendr\w*|"
            r"(?:lo\s+|te\s+lo\s+)?(?:vas\s+a\s+)?ten[eé]s|vas\s+a\s+tener|"
            r"en\s+tu\s+casa|en\s+tu\s+puerta|en\s+tu\s+domicilio|en\s+tus\s+manos)")
# Dia o fecha concreta, con diminutivos comunes y "finde". "dias habiles" no
# entra: no nombra un dia puntual. Incluye la fecha dicha por numero y mes en
# palabra ("25 de junio"), que el patron viejo de solo 25/6 dejaba pasar (E3).
_MESES = (r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
          r"septiembre|setiembre|octubre|noviembre|diciembre")
_DIA = (r"(?:lunes|lunecito|martes|martecito|mi[eé]rcoles|jueves|juevecito|"
        r"viernes|viernecito|s[áa]bado|sabadito|domingo|dominguito|"
        r"finde|fin\s+de\s+semana|ma[ñn]ana|pasado\s+ma[ñn]ana|hoy\s+mismo|"
        rf"\d{{1,2}}\s+de\s+(?:{_MESES})|"
        r"\b\d{1,2}/\d{1,2}\b)")
_RE_DIA_ENTREGA = re.compile(
    rf"(?:{_ENTREGA}.{{0,40}}?{_DIA}|{_DIA}.{{0,40}}?{_ENTREGA})",
    re.IGNORECASE | re.DOTALL)

_RE_RETIRO = re.compile(
    r"(?:retir[aoáe]\w*|pas\w*\s+a\s+(?:buscar|retirar)|"
    r"ven[íi]\w*\s+a\s+(?:buscar|retirar)|acerc\w*\s+a\s+retir\w*|"
    r"en\s+(?:el|nuestro)\s+local|en\s+la\s+sucursal|showroom|punto\s+de\s+retiro)",
    re.IGNORECASE)

_RE_SERVICIOS = re.compile(
    r"envoltori\w*|envolv\w*\s+(?:para|de)\s+regalo|envuelt\w*\s+(?:para|de)?\s*regalo|"
    r"papel\w*\s+de?\s*regalo|papelit\w*|"
    r"nota\s+(?:a\s+mano|manuscrita|escrita\s+a\s+mano)|"
    r"tarjet\w*\s+de\s+regalo|tarjetit\w*|mo[ñn]o\s+de\s+regalo|"
    r"instalaci\w*|instal\w*\s+a\s+domicilio|"
    r"arm[aoáe]\w*\s+(?:la|tu|mi)?\s*(?:pc|compu|computadora)|"
    r"armado\s+de\s+(?:pc|compu)|ensambl\w*|"
    r"entrega\s+en\s+mano|te\s+lo\s+llevo\s+(?:en\s+persona|personalmente)",
    re.IGNORECASE)


# Negacion de POLITICA de la tienda: "no hacemos", "no tenemos", "no ofrecemos".
# Cuando el disparo cae dentro de una de estas, la tienda esta siendo HONESTA
# (niega un servicio que no da), no prometiendo: no es una promesa prohibida (E4).
_NEG_POLITICA = re.compile(
    r"\b(?:no|tampoco)\s+(?:\w+\s+){0,2}"
    r"(?:hac\w+|ten\w+|ofrec\w+|cont\w+|hay|dam\w+|realiz\w+|brind\w+|"
    r"manej\w+|trabaj\w+|dispon\w+)",
    re.IGNORECASE)


def _negado(texto: str, start: int) -> bool:
    """True si el disparo viene dentro de una negacion de politica de la tienda
    ('no hacemos instalacion'): es honestidad, no una promesa. Mira la ventana
    corta antes del match, asi una negacion lejana e inconexa no lo tapa."""
    return bool(_NEG_POLITICA.search(texto[max(0, start - 30):start]))


def detectar(respuesta: str) -> list[str]:
    """Devuelve las clases de promesa prohibida presentes en el texto. [] si limpio.
    Un disparo dentro de una negacion de politica ('no hacemos X') no cuenta: la
    tienda niega el servicio, no lo promete."""
    if not respuesta:
        return []
    clases = []
    for clase, rx in (("dia_entrega", _RE_DIA_ENTREGA),
                      ("retiro_local", _RE_RETIRO),
                      ("servicio_no_ofrecido", _RE_SERVICIOS)):
        for m in rx.finditer(respuesta):
            if not _negado(respuesta, m.start()):
                clases.append(clase)
                break
    return clases


# ── REESCRITURA (una sola llamada al LLM, solo si disparo) ───────────────────

_INSTR = {
    "dia_entrega": ("no prometas ningun dia ni fecha exacta de entrega: deci el "
                    "plazo en dias habiles y aclara que el dia depende de la logistica"),
    "retiro_local": ("no ofrezcas retiro ni pasar a buscar por un local porque la "
                     "tienda es solo online: ofrece envio a domicilio"),
    "servicio_no_ofrecido": ("no prometas servicios que no ofrecemos como envoltorio "
                             "o nota de regalo, instalacion, armado o entrega en mano: "
                             "decilo con honestidad y pivotea a lo que si hacemos"),
}

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.DEEPSEEK_API_KEY,
                         base_url="https://api.deepseek.com/v1",
                         timeout=settings.LLM_TIMEOUT_SECONDS)
    return _client


async def reescribir_sin_promesas(respuesta: str, clases: list[str],
                                  trace_id: str | None = None) -> str:
    """Reescribe el mensaje sacando las promesas prohibidas, manteniendo el tono y
    la intencion de venta. No agrega datos. Una sola llamada a DeepSeek."""
    reglas = "; ".join(_INSTR[c] for c in clases if c in _INSTR)
    if not reglas:
        return respuesta
    prompt = (
        "Sos un editor. Reescribi el mensaje de un vendedor manteniendo el mismo "
        f"tono calido y la intencion de venta, pero {reglas}. No agregues datos "
        "nuevos ni numeros. Devolve SOLO el mensaje reescrito, sin comillas ni "
        f"explicacion.\n\nMensaje:\n{respuesta}")

    def _call() -> str:
        r = _get_client().chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2, max_tokens=settings.MAX_OUTPUT_TOKENS)
        return (r.choices[0].message.content or "").strip()

    return await asyncio.to_thread(_call)
