"""
PUERTA DE OBJECION — maneja regateo, descuento por cantidad y pedidos de
servicios que la tienda no ofrece (retiro, armado, envoltorio), con grounding.

Hoy estas caen al Solver y a veces terminan en el fallback feo (el verificador
bloquea porque el modelo repite el numero que tiro el cliente). Esta puerta las
agarra ANTES: detecta la clase de objecion, junta los HECHOS reales para pivotear
(el descuento por transferencia, mayoristas, el envio), y el redactor en etapa
objecion niega con cortesia lo que no existe y reencauza a lo que SI hay. Nunca
repite ni acepta el numero del cliente (lo prohibe la constitucion).

Codigo puro de deteccion. El render y el gate viven en el nucleo.
"""
import re
import unicodedata


def _n(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


# Pedido de un servicio que la tienda online no ofrece: retiro, armado, regalo.
_SERVICIO_RE = re.compile(
    r"\b(retir\w*|paso a buscar|pasar a buscar|lo busco|buscar por el local|"
    r"me lo arman|lo arman|armad\w*|me lo arme|envoltorio|para regalo|envuelt\w*|"
    r"empaque de regalo)\b")
# Descuento por cantidad / mayorista / reventa.
_CANTIDAD_RE = re.compile(
    r"\b(por cantidad|al por mayor|x mayor|mayorist\w*|revent\w*|revend\w*|"
    r"varias unidades|si compro \d+|compro \d+|llevo \d+|si llevo)\b")
# Regateo: ofrece un precio, pide igualar afuera, o tira un numero para abajo.
_REGATEO_RE = re.compile(
    r"\b(te doy|te ofrezco|te pago|me lo dejas|me lo deja|dejamelo|lo dejas a|"
    r"me haces precio|haceme precio|mas barato|en otro lado|en otro lugar|"
    r"en tal lado|me igualas|igualame|iguala el precio|lo vi a|lo consigo a|"
    r"me lo bajas|baja el precio|rebaja)\b")


def detectar_objecion(mensaje: str):
    """Devuelve 'servicio' | 'descuento_cantidad' | 'regateo' | None. El orden es
    de mas especifico a mas general para no pisar."""
    m = _n(mensaje)
    if _SERVICIO_RE.search(m):
        return "servicio"
    if _CANTIDAD_RE.search(m):
        return "descuento_cantidad"
    if _REGATEO_RE.search(m):
        return "regateo"
    return None


def _resp(faq: dict, tema: str) -> str:
    return ((faq or {}).get(tema, {}) or {}).get("respuesta", "").strip()


def hechos_de_objecion(tipo: str, faq: dict) -> list[str]:
    """Hechos REALES para pivotear, sacados de la FAQ. Lo que no exista en la
    tienda se omite (tienda-agnostico)."""
    if tipo == "regateo":
        temas = ["descuento_transferencia"]
    elif tipo == "descuento_cantidad":
        temas = ["descuento_transferencia", "mayoristas"]
    elif tipo == "servicio":
        temas = ["ubicacion", "envios", "retiro_local"]
    else:
        temas = []
    return [r for r in (_resp(faq, t) for t in temas) if r]


def directiva_de_objecion(tipo: str) -> str:
    """Instruccion para el redactor segun la clase. Nunca habilita inventar: solo
    marca el movimiento de venta, negar con cortesia y pivotear a lo que SI hay."""
    if tipo == "regateo":
        return ("El cliente tira un precio o pide igualar a otro lado. NO repitas "
                "ni aceptes ese numero. Deci con cortesia que es nuestro precio de "
                "catalogo y que no igualamos valores de afuera, y pivotea al "
                "descuento real de los hechos.")
    if tipo == "descuento_cantidad":
        return ("El cliente pide descuento por cantidad. Aclara que por cantidad "
                "no hay un descuento aparte, pero pivotea al descuento real y, si "
                "corresponde, a la opcion mayorista de los hechos.")
    if tipo == "servicio":
        return ("El cliente pide un servicio que NO ofrecemos (retiro, armado, "
                "envoltorio). Decilo con honestidad y en la misma frase pivotea al "
                "envio a domicilio de los hechos. Nunca prometas el servicio.")
    return ""
