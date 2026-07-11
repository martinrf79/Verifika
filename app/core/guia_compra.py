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
