"""
GUIA DE COMPRA DETERMINISTA — "el mas barato con stock" lo computa el CODIGO.

El hueco real del 2-jul: el cliente pidio "el mas barato con stock" y el solver
ELIGIO mal (nego stock que existia y upselleo a lo caro). Elegir el minimo de una
lista es un problema CERRADO: fuente de verdad + chequeo univoco. Eso es del
codigo, no del modelo (generar > corregir > verificar).

Queda `categoria_no_vendida`, que la llama `herramientas` para negar honesto
lo que la tienda no vende. `mas_barato_con_stock` salio con la FICHA 38: el
vivo ya no la llamaba; el snapshot de `archivo/` la sigue nombrando.

QUE SE BORRO EL 14-AGO-2026 y por que se cuenta. Este modulo tenia ademas
`guia_mas_barato`, que armaba un bloque de texto para inyectarle al solver, con
`intermedio_con_stock` y `_categorias_en_juego` de ayudantes. Era el camino
viejo: el mapa midio que no se llega a ninguna de las tres desde ningun webhook.
Hoy el que decide el producto es el pedido sellado de `guia_pedido`, no un
bloque de prompt. Si algun dia hace falta ese bloque, esta en git.
"""
import re
import unicodedata

from app.storage.firestore_client import get_categories
from app.logger import get_logger

log = get_logger(__name__)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _singular(w: str) -> str:
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


# ── CERTIFICADOR DE CATEGORIA (17-jul, consigna 43) ────────────────────────────────────
# El certificador de identidad decide sobre PRODUCTOS; nadie decidia sobre la
# CATEGORIA. Cuando el cliente pide una categoria que la tienda NO vende
# (celular, consola, televisor), el universo del generador queda vacio y el
# modelo rellenaba siguiendo la premisa (comparo dos telefonos fantasma en la
# consigna). Con esto lo decide el CODIGO antes de llamar al modelo: honesto
# "no lo vendemos" + la alternativa real mas cercana. La tabla es finita y se
# amplia desde el radar de logs; palabras ambiguas ("play", "telefono" como
# dato de contacto) quedan AFUERA a proposito.
#
# FUENTE DE VERDAD: la lista vive en data/clientes/<tienda_id>/no_vendidas.json.
# Sumar un caso es agregar una linea a ESE json, no tocar codigo.
#
# La copia entera que estaba aca abajo como "fallback minimo" se BORRO el 3-ago:
# eran las mismas veintitres entradas escritas dos veces, y una lista de esas
# nunca queda igual a la otra por mucho tiempo. Si el archivo falta, el mapa
# queda vacio y el bot no niega una categoria por un dato que no leyo, que es la
# salida honesta; una copia vieja en codigo le haria negar mal y con confianza.
#
# CACHE POR TIENDA (FICHA 25, 26-ago-2026). Hasta hoy era una unica variable
# global: la primera tienda que llamaba esto cacheaba SU no_vendidas.json y
# CUALQUIER otra tienda de la misma instancia leia esa lista, aunque fuera de
# otro rubro. `categoria_no_vendida` ya recibia `tienda_id` de su llamador —el
# dato estaba, nadie lo usaba para elegir el archivo. No hay caso hoy porque
# solo existe una tienda; el bug queda mudo hasta que exista una segunda.
_NO_VENDIDAS_CACHE: dict[str, dict[str, str | None]] = {}


def _no_vendidas(tienda_id: str | None = None) -> dict[str, str | None]:
    """Lee la fuente de verdad (no_vendidas.json) de UNA tienda y la cachea por
    tienda_id. Si el archivo falta o esta roto devuelve vacio: sin fuente no se
    niega nada."""
    from app.core.contexto_turno import get_current_tienda
    from app.config import get_settings
    tid = tienda_id or get_current_tienda() or get_settings().TIENDA_ID
    if tid in _NO_VENDIDAS_CACHE:
        return _NO_VENDIDAS_CACHE[tid]
    import json
    import os
    ruta = os.path.join(os.path.dirname(__file__), "..", "..", "data",
                        "clientes", tid, "no_vendidas.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            data = json.load(f)
        _NO_VENDIDAS_CACHE[tid] = {str(k).strip().lower(): v
                                   for k, v in (data.get("no_vendidas") or {}).items()
                                   if k}
    except Exception:
        log.warning("no_vendidas_sin_fuente", ruta=ruta, tienda_id=tid)
        _NO_VENDIDAS_CACHE[tid] = {}
    return _NO_VENDIDAS_CACHE[tid]


# El cliente nombra algo que no vendemos para preguntar si lo NUESTRO le sirve
# con eso. Es una pregunta de compatibilidad, no un pedido de compra.
_RE_COMPATIBILIDAD = re.compile(
    r"\b(?:sirve|sirven|anda|andan|funciona|funcionan|va|van|compatible|"
    r"compatibles|conecta|conectan|entra|entran)\b[^.?!]{0,25}?"
    r"\b(?:para|con|en)\b"
    r"|\bcompatibilidad\b|\bse\s+puede\s+usar\b|\blo\s+puedo\s+usar\b",
    re.IGNORECASE)


def categoria_no_vendida(mensaje: str,
                         tienda_id: str | None = None) -> tuple[str, str | None] | None:
    """(palabra pedida, categoria alternativa REAL o None) si el mensaje pide
    una categoria que la tienda no vende; None si no aplica. Si el mensaje
    ademas nombra una categoria REAL, no aplica: ese turno lo conduce el
    generador con el universo normal (responde lo que si hay)."""
    # Puntuacion a espacios: sin esto "ps5?" o "celulares?" (signo pegado al
    # final) no matchean el borde de palabra y el no honesto no salia.
    m = " " + re.sub(r"[^\w]+", " ", _norm(mensaje)) + " "
    no_vendidas = _no_vendidas(tienda_id)
    pedida = next((p for p in no_vendidas if f" {p} " in m), None)
    if not pedida:
        return None
    # NO es un pedido de compra si lo nombra para preguntar COMPATIBILIDAD:
    # "el mas barato sirve para PS5?" pregunta por el mouse, no pide una PS5.
    # Contestarle "PS5 no trabajamos" es un despropósito y encima tapa la
    # respuesta real (banco 29-jul, guion 54 turno 2).
    if _RE_COMPATIBILIDAD.search(m):
        return None
    reales = [str(c) for c in (get_categories(tienda_id=tienda_id) or [])]
    for c in reales:
        cn = _norm(c)
        if f" {cn} " in m or f" {_singular(cn)} " in m:
            return None
    alt = no_vendidas[pedida]
    if alt and not any(_norm(c) == _norm(alt) for c in reales):
        alt = None
    return pedida, alt


# ── CERTIFICADOR DE MODELO PUNTUAL (19-jul, guiones 39/40 de la consigna) ────
# "¿Tienen el ROG Strix G15?" / "¿el monitor Samsung Odyssey G5?": el modelo
# NO esta en catalogo y el turno salia hueco ("te lo confirmo al instante")
# o con una politica inventada ("por politica no trabajamos Asus"). La
# identidad la decide el CODIGO (regla cero): token de modelo que no existe
# en el catalogo -> not_found honesto + opciones reales de la categoria.

# El cliente esta preguntando por un producto (no charlando de otra cosa).
_RE_PIDE_PRODUCTO = re.compile(
    r"\b(tienen|tenes|tene|hay|stock|disponib\w*|precio|busco|quiero"
    r"|modelo|me interesa)\b")

# Token con pinta de modelo: letras y numeros mezclados (g15, x3d, mx518).
_RE_TOKEN_MODELO = re.compile(r"^[a-z]+\d+[a-z0-9]*$")

# Unidades y medidas que parecen modelo pero no lo son (4k, 27p, 16gb solo).
_RE_UNIDAD = re.compile(
    r"^\d+[a-z]{1,3}$|^(full|ultra)hd$|^[0-9]+(gb|tb|hz|mah|dpi|mm|cm|w)$")

_STOP_MODELO = {"modelo", "el", "la", "los", "las", "de", "del", "un", "una",
                "en", "con", "y", "o", "stock", "tienen", "hay", "para"}


# Verbos de DECISION: "quiero, dame, sumalo" no es una pregunta de identidad,
# es un pedido, y ese lo conduce el flujo de pedido normal.
_RE_DECISION = re.compile(r"\b(quiero|dame|sumal[oa]|sumame|llevo|comprar"
                          r"|agrega|anotal[oa])\b")
