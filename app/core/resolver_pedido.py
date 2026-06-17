"""
RESOLVEDOR DE PEDIDO POR CODIGO — el codigo resuelve el HECHO, no el LLM.

Dado el registro de sesion (productos ya mostrados con su id real) y el mensaje
del cliente, decide a que producto se refiere y devuelve su product_id, sin
preguntarle nada al modelo. Es el movimiento que independiza el cierre del LLM:
hoy el modelo pierde o inventa el id entre turnos y la venta madura se cae; aca
el id sale de la fuente (el registro), por construccion.

Resuelve cuatro formas de referirse a algo ya mostrado:
  - por nombre o marca: "el Samsung", "el Logitech G203"
  - por superlativo de precio: "el mas barato", "el mas caro"
  - anafora con un solo producto en juego: "ese", "me lo llevo", "lo confirmo"
  - cantidad: "comprame dos", "llevo 3"

Regla de oro: ante la duda, NO adivina. Si hay ambiguedad real (varios productos
posibles y ninguna senal para elegir), devuelve None y deja el flujo como esta.
Mejor no resolver que resolver mal.

Funcion pura, sin LLM ni red: se testea entera offline. Detras del flag
RESOLVER_PEDIDO; en off nadie la llama.
"""
import re
import unicodedata
from typing import Optional

# Palabras que no aportan a identificar un producto por nombre: conectores y
# adjetivos de categoria que aparecen en muchos nombres del catalogo.
_STOP = {
    "de", "el", "la", "los", "las", "un", "una", "con", "para", "por", "y",
    "que", "del", "al", "es", "su", "lo", "mi", "me", "te", "se", "gamer",
    "monitor", "mouse", "teclado", "auriculares", "silla", "disco", "ssd",
    "pro", "plus", "rgb", "inalambrico", "mecanico",
}

# Senales de que el cliente quiere avanzar sobre algo ya hablado (anafora).
_ANAFORA = (
    "ese", "esa", "eso", "este", "esta", "esto", "ese mismo", "el mismo",
    "me lo llevo", "lo llevo", "lo confirmo", "lo compro", "compralo",
    "cerralo", "dale ese", "ese dale", "lo quiero", "quiero ese",
)

# "los dos mas baratos", "las tres notebooks mas economicas", "los 2 mas caros":
# es pedir que se MUESTREN N opciones, NO comprar N unidades del mas barato.
# Visto en prod 14-jun: "dame precios de los dos mas baratos en cada caso" armaba
# un pedido fantasma de 2x el mouse mas barato que se arrastraba cada turno.
_RE_LISTAR_N = re.compile(
    r"(?i)\b(los|las)\s+(dos|tres|cuatro|cinco|seis|\d{1,2})\s+"
    r"(?:[a-záéíóúñü]+\s+){0,2}(?:mas\s+|m[aá]s\s+)?"
    r"(barat|economic|accesibl|car[oa]|baj)")

# Pregunta de ATRIBUTO o EXISTENCIA: no es elegir entre A y B, es pedir un dato
# (que el Solver responde con la ficha). Visto en prod 15-jun: "¿el Huntsman
# tiene luces al ritmo de la musica?" -> A/B "Negro o Blanco?"; "¿tienen el
# i9-14900K?" -> A/B "12400F o 13400F?" (matcheo generico procesador/intel/core).
# La confirmacion dispara e ignora la pregunta. Con esto, resolver/candidatos no
# arman seleccion y el turno sigue al Solver, que contesta.
# OJO: 'confirm*' queda AFUERA a proposito — 'lo confirmo' es cierre de compra,
# no pregunta. La compatibilidad se cubre con 'entra'/'compatible'.
_RE_PREGUNTA_ATRIBUTO = re.compile(
    r"(?i)\b(tienen?|trae|traen|viene|vienen|incluye|inclu[iy]en"
    r"|es\s+compatible|compatible|sirve|anda|funciona|entra|cabe|soporta"
    r"|admite)\b")

_SUP_BARATO = ("mas barato", "mas economico", "el barato", "mas accesible",
               "el menor", "el mas bajo",
               # femenino (la webcam mas barata, la mas economica)
               "mas barata", "mas economica", "la barata", "la mas baja")
_SUP_CARO = ("mas caro", "mas premium", "el mejor", "el top", "el mas alto",
             "mas cara", "la mejor", "la mas alta")

# Numeros escritos a palabra, para la cantidad.
_NUM_PALABRA = {
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
    "cinco": 5, "seis": 6, "par": 2, "una unidad": 1,
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return s.lower()


def _tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _norm(s))


def _sing(w: str) -> str:
    """Singular tosco: 'negros' -> 'negro', 'teclados' -> 'teclado'. No toca
    palabras cortas para no romper modelos ('tkl')."""
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


def refinar_por_atributo(cands: list[dict], mensaje: str) -> list[dict]:
    """Angosta una lista de candidatos con los tokens del mensaje que
    DISCRIMINAN entre ellos (color, sufijo de modelo: 'negro', 'tkl'). Un token
    discrimina si aparece en el nombre de algunos candidatos pero NO de todos.
    Generico a proposito: no lista colores ni modelos, usa lo que realmente
    separa a los candidatos que hay. Singulariza para que 'negros' pegue con
    'Negro'. Si un token deja la lista en cero, no se aplica (se ignora)."""
    msg_sing = {_sing(t) for t in _tokens(mensaje) if len(_sing(t)) >= 3}
    filtrado = list(cands)
    for t in msg_sing:
        con = [p for p in filtrado
               if t in {_sing(x) for x in _tokens(p.get("nombre", ""))}]
        if 0 < len(con) < len(filtrado):
            filtrado = con
    return filtrado


def _detectar_cantidad(msg_norm: str) -> int:
    """Cantidad pedida. Default 1. Cifra explicita gana a palabra."""
    m = re.search(r"\b(\d{1,2})\b", msg_norm)
    if m:
        n = int(m.group(1))
        # Un numero suelto chico es cantidad; descartamos numeros grandes (precios)
        # que ya se filtran por el \d{1,2}, y el 0.
        if 1 <= n <= 20:
            return n
    for palabra, n in _NUM_PALABRA.items():
        if re.search(r"\b" + re.escape(palabra) + r"\b", msg_norm):
            return n
    return 1


def _candidatos_por_nombre(msg_norm: str, msg_tokens: set,
                           registro: list[dict]) -> list[dict]:
    """Productos del registro que el mensaje nombra. Match en dos sentidos:
    un token del mensaje aparece dentro del nombre del producto, o un token
    significativo del nombre aparece en el mensaje. Asi 'samsung' pega con
    'Samsung Odyssey G5' y '27' pega con 'LG UltraGear 27GP850'."""
    cand = []
    for p in registro:
        nombre_norm = _norm(p.get("nombre", ""))
        nombre_tokens = [t for t in _tokens(nombre_norm)
                         if t not in _STOP and len(t) >= 3]
        pega = False
        # token del mensaje (>=3, o numero >=2) contenido en el nombre
        for t in msg_tokens:
            if (len(t) >= 3 or (t.isdigit() and len(t) >= 2)) and t in nombre_norm:
                pega = True
                break
        # token significativo del nombre mencionado en el mensaje
        if not pega:
            for t in nombre_tokens:
                if t in msg_tokens:
                    pega = True
                    break
        if pega:
            cand.append(p)
    return cand


def resolver_pedido(mensaje: str,
                    registro: list[dict]) -> Optional[dict]:
    """Resuelve a que producto del registro se refiere el cliente.

    Args:
        mensaje: el texto crudo del cliente.
        registro: productos vistos en la sesion, cada uno {id, nombre, precio_ars}.

    Returns:
        {"producto_id", "nombre", "precio_ars", "cantidad", "motivo"} si resuelve
        con confianza, o None si hay ambiguedad o no hay nada que resolver.
    """
    if not registro:
        return None
    # "los dos mas baratos" = mostrar N opciones, NO comprar N: no se arma foco.
    if _RE_LISTAR_N.search(mensaje or ""):
        return None
    # Pregunta de atributo/existencia: la responde el Solver, no se arma foco/A/B.
    if _RE_PREGUNTA_ATRIBUTO.search(mensaje or ""):
        return None
    msg_norm = _norm(mensaje)
    msg_tokens = set(_tokens(mensaje))
    cantidad = _detectar_cantidad(msg_norm)

    def _arma(p: dict, motivo: str) -> dict:
        return {"producto_id": p.get("id"), "nombre": p.get("nombre"),
                "precio_ars": p.get("precio_ars"), "cantidad": cantidad,
                "motivo": motivo}

    # 1) Superlativo de precio: manda sobre todo lo demas, es inequivoco.
    if any(s in msg_norm for s in _SUP_BARATO):
        validos = [p for p in registro
                   if isinstance(p.get("precio_ars"), (int, float))]
        if validos:
            return _arma(min(validos, key=lambda p: p["precio_ars"]),
                         "superlativo_barato")
    if any(s in msg_norm for s in _SUP_CARO):
        validos = [p for p in registro
                   if isinstance(p.get("precio_ars"), (int, float))]
        if validos:
            return _arma(max(validos, key=lambda p: p["precio_ars"]),
                         "superlativo_caro")

    # 2) Por nombre o marca.
    cand = _candidatos_por_nombre(msg_norm, msg_tokens, registro)
    if len(cand) > 1:
        # Nombra algo y matchea varios: antes de rendirse, angostar por el
        # atributo que discrimina ('K380 negro' entre negro y blanco). El
        # cliente YA eligio; no es ambiguo de verdad.
        cand = refinar_por_atributo(cand, mensaje)
    if len(cand) == 1:
        return _arma(cand[0], "nombre")
    if len(cand) > 1:
        # Sigue matcheando varios sin nada que discrimine: ambiguo, no adivinamos.
        return None

    # 3) Anafora con un solo producto en juego. Si hay mas de uno, ambiguo.
    if any(a in msg_norm for a in _ANAFORA):
        if len(registro) == 1:
            return _arma(registro[0], "anafora_unico")
        return None

    return None


def candidatos_pedido(mensaje: str, registro: list[dict]) -> list[dict]:
    """Los casos donde resolver_pedido devuelve None por ambiguedad, expuestos
    para el presupuesto A/B: si la referencia matchea DOS productos, el codigo
    cotiza los dos y el cliente elige. Devuelve los candidatos con la cantidad
    detectada, o lista vacia si no hay ambiguedad util (cero, uno, o tres o mas
    candidatos: esos casos los cubren resolver_pedido o la pregunta corta).

    Cada candidato: {"producto_id", "nombre", "precio_ars", "cantidad"}.
    """
    if not registro:
        return []
    if _RE_LISTAR_N.search(mensaje or ""):
        return []
    if _RE_PREGUNTA_ATRIBUTO.search(mensaje or ""):
        return []
    msg_norm = _norm(mensaje)
    msg_tokens = set(_tokens(mensaje))
    cantidad = _detectar_cantidad(msg_norm)

    cand = _candidatos_por_nombre(msg_norm, msg_tokens, registro)
    # Mas de dos: si el cliente trajo un atributo que angosta a dos (color,
    # modelo), exponer ese A/B en vez de descartar por "tres o mas".
    if len(cand) > 2:
        cand = refinar_por_atributo(cand, mensaje)
    # Anafora con exactamente dos en juego tambien es un A/B natural.
    if not cand and any(a in msg_norm for a in _ANAFORA) and len(registro) == 2:
        cand = list(registro)
    if len(cand) != 2:
        return []
    return [{"producto_id": p.get("id"), "nombre": p.get("nombre"),
             "precio_ars": p.get("precio_ars"), "cantidad": cantidad}
            for p in cand]
