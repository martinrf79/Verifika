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
_NO_VENDIDAS: dict[str, str | None] = {
    "celular": "tablet", "celulares": "tablet", "smartphone": "tablet",
    "smartphones": "tablet", "iphone": "tablet", "iphones": "tablet",
    "televisor": "monitor", "televisores": "monitor", "smart tv": "monitor",
    "consola": None, "consolas": None, "playstation": None, "xbox": None,
    "nintendo": None, "drone": None, "drones": None,
    "smartwatch": "tablet", "smartwatches": "tablet",
    "heladera": None, "heladeras": None, "lavarropas": None,
    "microondas": None, "aire acondicionado": None,
}


def categoria_no_vendida(mensaje: str,
                         tienda_id: str | None = None) -> tuple[str, str | None] | None:
    """(palabra pedida, categoria alternativa REAL o None) si el mensaje pide
    una categoria que la tienda no vende; None si no aplica. Si el mensaje
    ademas nombra una categoria REAL, no aplica: ese turno lo conduce el
    generador con el universo normal (responde lo que si hay)."""
    m = " " + _norm(mensaje) + " "
    pedida = next((p for p in _NO_VENDIDAS if f" {p} " in m), None)
    if not pedida:
        return None
    reales = [str(c) for c in (get_categories(tienda_id=tienda_id) or [])]
    for c in reales:
        cn = _norm(c)
        if f" {cn} " in m or f" {_singular(cn)} " in m:
            return None
    alt = _NO_VENDIDAS[pedida]
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


def modelo_puntual(mensaje: str, tienda_id: str | None = None) -> dict | None:
    """Identidad de un MODELO puntual preguntado, decidida por el CODIGO.
    None si el mensaje no pregunta por un modelo. Si pregunta, devuelve
    {"frase", "exactos", "cercanos", "categoria"}:
      - exactos: productos reales que matchean TODA la frase del modelo
        (pregunto por el Odyssey G5 y existe el Odyssey G5 32).
      - cercanos: productos que comparten el token de modelo (pregunto el
        Asus ROG Strix G15 y existe la Dell G15).
      - los dos vacios: el modelo no existe en catalogo; categoria trae la
        categoria nombrada para ofrecer opciones reales."""
    m = _norm(mensaje)
    if not m or not _RE_PIDE_PRODUCTO.search(m):
        return None
    palabras = m.replace(",", " ").replace("?", " ").replace("¿", " ").split()
    idx = next((i for i, w in enumerate(palabras)
                if _RE_TOKEN_MODELO.match(w) and not _RE_UNIDAD.match(w)), None)
    if idx is None:
        return None
    ancla = palabras[idx]
    # La frase del modelo: el ancla + hasta 3 palabras previas con sustancia
    # ("samsung odyssey g5", "rog strix g15").
    frase = [ancla]
    for w in reversed(palabras[max(0, idx - 3):idx]):
        if w in _STOP_MODELO or _RE_UNIDAD.match(w) or w.isdigit() and len(w) < 3:
            break
        frase.insert(0, w)
    prods = get_all_products(tienda_id=tienda_id) or []
    cats_reales = {_norm(c) for c in (get_categories(tienda_id=tienda_id) or [])}
    toks_frase = [t for t in frase
                  if t not in _STOP_MODELO and _norm(t) not in cats_reales
                  and _singular(_norm(t)) not in {_singular(c) for c in cats_reales}]
    exactos, cercanos = [], []
    for p in prods:
        base = " " + _norm(str(p.get("nombre", "")) + " "
                           + str(p.get("modelo", ""))).replace("-", " ") + " "
        if f" {ancla} " not in base:
            continue
        cercanos.append(p)
        if all(t in base for t in toks_frase):
            exactos.append(p)
    if exactos and _RE_DECISION.search(m):
        # Modelo real + verbo de decision: es un pedido, no una duda de
        # identidad. Lo conduce el flujo normal.
        return None
    cat_op = None
    for c in (get_categories(tienda_id=tienda_id) or []):
        cn = _norm(c)
        if f" {cn} " in f" {m} " or f" {_singular(cn)} " in f" {m} ":
            cat_op = str(c)
            break
    def _orden(p):
        return (p.get("stock", 0) <= 0, p.get("precio_ars") or 0)
    return {"frase": " ".join(toks_frase) or ancla,
            "exactos": sorted(exactos, key=_orden)[:3],
            "cercanos": sorted(cercanos, key=_orden)[:3],
            "categoria": cat_op}
