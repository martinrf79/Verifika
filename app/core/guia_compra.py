"""
GUIA DE COMPRA DETERMINISTA — "el mas barato con stock" lo computa el CODIGO.

El hueco real del 2-jul: el cliente pidio "el mas barato con stock" y el solver
ELIGIO mal (nego stock que existia y upselleo a lo caro). Elegir el minimo de una
lista es un problema CERRADO: fuente de verdad + chequeo univoco. Eso es del
codigo, no del modelo (generar > corregir > verificar).

Este modulo computa el mas barato CON stock de las categorias en juego y arma un
bloque de GUIA que se inyecta al solver junto con el estado. El solver conserva
la redaccion y la venta; el QUE producto es exactamente ese ya viene decidido y
referenciado como [[PROD:id]], que el estampado rellena con nombre+precio+stock
reales de la fuente. No es una tool opcional que el modelo puede no llamar: si el
cliente pidio lo mas barato, la guia viaja SIEMPRE en el turno.
"""
import re
import unicodedata

from app.core.tools_context import get_current_tienda
from app.storage.firestore_client import (
    get_all_products, get_product_by_id, get_categories)
from app.logger import get_logger

log = get_logger(__name__)

# Tope de categorias por guia: mas que esto ya no es una eleccion, es un listado.
_MAX_CATEGORIAS = 3


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _singular(w: str) -> str:
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


def mas_barato_con_stock(categoria: str | None = None) -> dict | None:
    """El producto mas barato CON stock del catalogo (de una categoria, o de
    todo). None si no hay ninguno con stock. Determinista: minimo por precio con
    filtro stock > 0, la misma regla siempre."""
    tid = get_current_tienda()
    productos = [p for p in get_all_products(tienda_id=tid)
                 if p.get("stock", 0) > 0
                 and isinstance(p.get("precio_ars"), (int, float))]
    if categoria:
        cat = _norm(categoria)
        productos = [p for p in productos
                     if _norm(p.get("categoria", "")) == cat]
    if not productos:
        return None
    return min(productos, key=lambda p: p["precio_ars"])


def intermedio_con_stock(categoria: str | None = None) -> dict | None:
    """La opcion INTERMEDIA con stock (criterio 'intermedio', 11-jul: el
    cliente que rechaza lo mas barato). Determinista: el ESCALON de precio
    siguiente al minimo (segundo precio distinto). La mediana de toda la
    categoria proponia un teclado de $144.000 a quien pidio 'economico pero
    no lo mas barato' (visto en el banco); el escalon de arriba del minimo
    es lo que ese cliente pide. None si no hay ninguno con stock."""
    tid = get_current_tienda()
    productos = [p for p in get_all_products(tienda_id=tid)
                 if p.get("stock", 0) > 0
                 and isinstance(p.get("precio_ars"), (int, float))]
    if categoria:
        cat = _norm(categoria)
        productos = [p for p in productos
                     if _norm(p.get("categoria", "")) == cat]
    if not productos:
        return None
    productos.sort(key=lambda p: (p["precio_ars"], str(p.get("id"))))
    minimo = productos[0]["precio_ars"]
    for p in productos:
        if p["precio_ars"] > minimo:
            return p
    return productos[-1]  # todos al mismo precio: el ultimo estable


def _categorias_en_juego(mensaje: str,
                         productos_vistos: list[dict] | None) -> list[str]:
    """Las categorias sobre las que el cliente esta eligiendo: las nombradas en
    el mensaje (contra las categorias reales de la tienda, tolerante a plural) y
    las de los ultimos productos que el bot ya mostro."""
    tid = get_current_tienda()
    try:
        cats_reales = list(get_categories(tienda_id=tid))
    except Exception:
        cats_reales = []
    palabras = {_singular(w) for w in _norm(mensaje).split()}
    en_juego: list[str] = []
    for c in cats_reales:
        if _singular(_norm(c)) in palabras:
            en_juego.append(c)
    if not en_juego:
        for p in (productos_vistos or [])[-6:]:
            pid = str(p.get("id") or "")
            if not pid:
                continue
            try:
                prod = get_product_by_id(pid, tienda_id=tid)
            except Exception:
                prod = None
            cat = (prod or {}).get("categoria")
            if cat and cat not in en_juego:
                en_juego.append(cat)
    return en_juego[:_MAX_CATEGORIAS]


def guia_mas_barato(mensaje: str,
                    productos_vistos: list[dict] | None = None) -> str:
    """Bloque de guia para el solver cuando el criterio del cliente es "lo mas
    barato": el codigo ya computo el mas barato CON stock por categoria en juego
    (o global si no hay categoria) y el solver debe ofrecer EXACTAMENTE ese.
    '' si no hay nada que guiar (catalogo sin stock)."""
    lineas: list[str] = []
    try:
        cats = _categorias_en_juego(mensaje, productos_vistos)
        if cats:
            for c in cats:
                p = mas_barato_con_stock(categoria=c)
                if p:
                    lineas.append(
                        f"en {c}: [[PROD:{p['id']}]] ({p.get('stock')} en stock)")
        else:
            p = mas_barato_con_stock()
            if p:
                lineas.append(
                    f"del catalogo: [[PROD:{p['id']}]] ({p.get('stock')} en stock)")
    except Exception as e:
        log.warning("guia_mas_barato_error", error=str(e)[:120])
        return ""
    if not lineas:
        return ""
    return ("\n\n[GUIA DETERMINISTA, calculada por el codigo desde el catalogo "
            "real: el mas barato CON STOCK es " + "; ".join(lineas) +
            ". Si el cliente quiere lo mas barato, ofrece EXACTAMENTE ese, "
            "usando el marcador [[PROD:id]] tal cual. NO elijas vos otro ni "
            "digas que no tiene stock.]")


# ── CERTIFICADOR DE CATEGORIA (17-jul, consigna 43) ──────────────────────────
# El certificador de identidad decide sobre PRODUCTOS; nadie decidia sobre la
# CATEGORIA. Cuando el cliente pide una categoria que la tienda NO vende
# (celular, consola, televisor), el universo del generador queda vacio y el
# modelo rellenaba siguiendo la premisa (comparo dos telefonos fantasma en la
# consigna). Con esto lo decide el CODIGO antes de llamar al modelo: honesto
# "no lo vendemos" + la alternativa real mas cercana. La tabla es finita y se
# amplia desde el radar de logs; palabras ambiguas ("play", "telefono" como
# dato de contacto) quedan AFUERA a proposito.
#
# FUENTE DE VERDAD: la lista vive en data/clientes/verifika_prod/no_vendidas.json.
# Sumar un caso es agregar una linea a ESE json, no tocar codigo. El dict de abajo
# es solo el fallback minimo si el archivo faltara; el archivo, si esta, manda.
_NO_VENDIDAS_FALLBACK: dict[str, str | None] = {
    "celular": "tablet", "celulares": "tablet", "smartphone": "tablet",
    "smartphones": "tablet", "iphone": "tablet", "iphones": "tablet",
    "televisor": "monitor", "televisores": "monitor", "smart tv": "monitor",
    "consola": None, "consolas": None, "playstation": None, "xbox": None,
    "nintendo": None, "drone": None, "drones": None,
    "smartwatch": "tablet", "smartwatches": "tablet",
    "heladera": None, "heladeras": None, "lavarropas": None,
    "microondas": None, "aire acondicionado": None,
}
_NO_VENDIDAS_CACHE: dict[str, str | None] | None = None


def _no_vendidas() -> dict[str, str | None]:
    """Lee la fuente de verdad (no_vendidas.json) una vez y la cachea; si el
    archivo falta o esta roto, cae al fallback en codigo."""
    global _NO_VENDIDAS_CACHE
    if _NO_VENDIDAS_CACHE is not None:
        return _NO_VENDIDAS_CACHE
    import json
    import os
    ruta = os.path.join(os.path.dirname(__file__), "..", "..", "data",
                        "clientes", "verifika_prod", "no_vendidas.json")
    try:
        with open(ruta, encoding="utf-8") as f:
            data = json.load(f)
        mapa = {str(k).strip().lower(): v
                for k, v in (data.get("no_vendidas") or {}).items() if k}
        _NO_VENDIDAS_CACHE = mapa or dict(_NO_VENDIDAS_FALLBACK)
    except Exception:
        _NO_VENDIDAS_CACHE = dict(_NO_VENDIDAS_FALLBACK)
    return _NO_VENDIDAS_CACHE


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
    no_vendidas = _no_vendidas()
    pedida = next((p for p in no_vendidas if f" {p} " in m), None)
    if not pedida:
        return None
    # NO es un pedido de compra si lo nombra para preguntar COMPATIBILIDAD:
    # "el mas barato sirve para PS5?" pregunta por el mouse, no pide una PS5.
    # Contestarle "PS5 no trabajamos" es un despropósito y encima tapa la
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

