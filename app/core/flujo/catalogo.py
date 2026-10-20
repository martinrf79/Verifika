"""EL CATALOGO DEL EJECUTOR — quien es un producto nombrado y que productos cumplen una busqueda (19-oct-2026).

Dos preguntas, las dos deterministas y sobre la fuente de la tienda:

  identificar   "G305 negro" -> un producto, con los tres veredictos de la regla 7.0: exists, ambiguous, not_found.
                Un modelo en varios colores es UN producto; el color elige la variante, y si no lo dijo y hay mas de
                uno con stock, queda por preguntar.
  buscar        rubro + condiciones en palabras del cliente + orden. Cada condicion se ata a UN campo del catalogo
                donde ese valor existe, en el orden de `PRIORIDAD`; lo que no esta en ningun campo no filtra y se dice.

No hay listas de palabras de producto escritas aca: los valores salen de los productos de la tienda, sus campos y sus
tags. Las unicas palabras fijas son de gramatica —negar, poner un tope, rellenar— y estan en `_NIEGA`, `_TOPE` y
`_RELLENO`.
"""
import re
import unicodedata

from app.core import agente
from app.core.filtros_catalogo import los_que_lo_nombran_entero, vocabulario
from app.storage import firestore_client as fc


def n(t) -> str:
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")).strip()


def productos(tienda_id: str) -> list:
    return fc.get_all_products(tienda_id=tienda_id) or []


def rubro(texto: str, tienda_id: str) -> str:
    """El rubro de la tienda para lo que escribio el interprete, o "" si no es ninguno."""
    return agente._rubro(texto, tienda_id)[0] or ""


def solo_rubro(texto: str, tienda_id: str) -> str:
    """El rubro si el texto nombra SOLO un rubro —"auriculares", "un mouse", "memorias"—, o "". "Teclado Logitech" no:
    trae algo mas que el rubro, y eso lo decide la identidad o una busqueda."""
    rub = rubro(texto, tienda_id)
    palabras = [w for w in n(texto).split() if w not in _RELLENO and not w.isdigit()]
    return rub if rub and palabras and all(w[:5] in n(rub) for w in palabras) else ""


def con_stock(p: dict) -> bool:
    return entero(p.get("stock")) > 0


def entero(v, defecto: int = 0) -> int:
    """Un numero que puede venir como texto del interprete: "2", "2.0", "300000". Lo que no es numero, el defecto."""
    try:
        return int(float(str(v).replace(",", ".")))
    except (TypeError, ValueError):
        return defecto


# ══ IDENTIDAD ════════════════════════════════════════════════════════════════

def _colores_de(p: dict, todos: list) -> list:
    """Las variantes del mismo modelo, una por color."""
    return [q for q in todos if q.get("modelo") and q.get("modelo") == p.get("modelo")
            and q.get("marca") == p.get("marca") and q.get("categoria") == p.get("categoria")]


_IDENTIDAD = {}  # (tienda, nombre, color) -> (el catalogo con que se calculo, el veredicto)


def identificar(nombre: str, color: str, tienda_id: str) -> dict:
    """{"veredicto": "exists", "producto", "variantes"} con el producto ya en su color si se pudo elegir;
    "falta_color": True si hay varios colores con stock y no dijo cual. {"veredicto": "ambiguous", "opciones"} si
    nombra varios modelos. {"veredicto": "not_found"} si no nombra ninguno.

    Se recuerda mientras el catalogo sea el mismo, para las lecturas del borrador: la lista es nueva en cada lectura,
    los productos no."""
    todos = productos(tienda_id)
    clave, marca = (tienda_id, nombre, color), (len(todos), todos[0] if todos else None)
    viejo = _IDENTIDAD.get(clave)
    if not (viejo and viejo[0][0] == marca[0] and viejo[0][1] is marca[1]):
        if len(_IDENTIDAD) > 2000:
            _IDENTIDAD.clear()
        viejo = _IDENTIDAD[clave] = (marca, _identificar(nombre, color, todos))
    return dict(viejo[1])


def _identificar(nombre: str, color: str, todos: list) -> dict:
    texto = f"{nombre} {color or ''}".strip()
    hallados = los_que_lo_nombran_entero(todos, texto) or los_que_lo_nombran_entero(todos, nombre)
    if not hallados:
        return {"veredicto": "not_found", "nombre": nombre}
    modelos = list(dict.fromkeys((p.get("marca"), p.get("modelo") or p["id"]) for p in hallados))
    if len(modelos) > 1:
        return {"veredicto": "ambiguous", "nombre": nombre,
                "opciones": [next(p for p in hallados if (p.get("marca"), p.get("modelo") or p["id"]) == m)
                             for m in modelos]}
    variantes = _colores_de(hallados[0], todos) or hallados
    pedido = set(n(texto).split())
    del_color = [p for p in variantes if p.get("color") and set(n(p["color"]).split()) <= pedido]
    if len(del_color) == 1:
        return {"veredicto": "exists", "producto": del_color[0], "variantes": variantes}
    if color and not del_color and len(variantes) > 1:
        # Pidio un color que el modelo no tiene: no se cambia por otro en silencio.
        hay = [p for p in variantes if con_stock(p)] or variantes
        return {"veredicto": "exists", "producto": hay[0], "variantes": variantes, "falta_color": True,
                "no_hay_color": color}
    if len(variantes) == 1:
        return {"veredicto": "exists", "producto": variantes[0], "variantes": variantes}
    hay = [p for p in variantes if con_stock(p)]
    if len(hay) == 1:
        return {"veredicto": "exists", "producto": hay[0], "variantes": variantes}
    return {"veredicto": "exists", "producto": (hay or variantes)[0], "variantes": variantes, "falta_color": True}


def por_id(pid: str, tienda_id: str) -> dict:
    return fc.get_product_by_id(str(pid), tienda_id=tienda_id) or {}


# ══ BUSQUEDA ═════════════════════════════════════════════════════════════════

# Donde se busca un valor, en este orden: el primer campo donde algun producto del rubro lo trae es el que filtra.
# "con cable" filtra por conexion y no por contenido_caja, que dice "cable o receptor".
PRIORIDAD = ("marca", "color", "conexion", "ram", "almacenamiento", "procesador", "hz", "panel", "resolucion",
             "memoria_video", "potencia", "switch_teclado", "retroiluminacion", "bluetooth", "pais_fabricacion",
             "pais_marca", "tags", "modelo", "nombre", "descripcion")

_NIEGA = re.compile(r"^(?:que\s+)?(?:no\s+(?:sea[ns]?\s+)?|sin\s+|ni\s+|excepto\s+|salvo\s+|nada\s+de\s+)")
# Un tope es de plata si el numero no lleva unidad: "hasta 16 GB" es memoria, no precio.
_TOPE = re.compile(r"\b(menos de|hasta|maximo|no mas de|por debajo de|mas de|desde|minimo)\s*\$?\s*([\d.,]+)"
                   r"(?![\d.,])\s*(millones|millon|mil|k|lucas)?\b(?!\s*(?:gb|tb|hz|w|watts|mah|mm|pulgadas|gramos|g|meses)\b)")
_RELLENO = set("a al con de del el en la las lo los para por que un una unos unas y o sea posible preferentemente "
               "preferiblemente idealmente algo alguno alguna".split())


def _valores(prod: dict, campo: str) -> str:
    if campo == "tags":
        return n(prod.get("tags"))
    v = prod.get(campo)
    if v in (None, ""):
        v = (prod.get("specs") or {}).get(campo)
    return n(v)


def _contiene(texto: str, valor: str) -> bool:
    if not texto or not valor:
        return False
    # Palabra entera, con plural: "red" no es "redragon", "inalambrico" si es "inalambricos".
    return re.search(rf"(?<![a-z0-9]){re.escape(valor)}(?:s|es)?(?![a-z0-9])", texto) is not None


_POR = {"mil": 1_000, "k": 1_000, "lucas": 1_000, "millon": 1_000_000, "millones": 1_000_000}


def _monto(numero: str, por: str) -> int:
    """"200 mil", "1,5 millones", "1.500.000". Con multiplicador, una coma o un punto con una o dos cifras atras
    es decimal; sin el, el punto es de miles."""
    if por and re.fullmatch(r"\d+[.,]\d{1,2}", numero):
        v = float(numero.replace(",", "."))
    else:
        v = int(re.sub(r"\D", "", numero.split(",")[0]) or 0)
    return int(v * _POR.get(por or "", 1))


def atar(condicion: str, universo: list, tienda_id: str) -> dict:
    """Una condicion en palabras -> {"campo", "valor", "niega"} o {"tope": ("max"|"min", monto)} o
    {"sin_campo": condicion} si ningun campo del rubro trae ese valor."""
    c = n(condicion)
    t = _TOPE.search(c)
    if t:
        return {"tope": ("min" if t.group(1) in ("mas de", "desde", "minimo") else "max", _monto(t.group(2), t.group(3)))}
    niega = bool(_NIEGA.search(c))
    c = _NIEGA.sub("", c)
    c = re.sub(r"\b(\d+)\s+(gb|tb|hz|w|mah|mm)\b", r"\1\2", c)
    campos = set(vocabulario(tienda_id))
    palabras = [w for w in c.split() if w not in _RELLENO]
    pista = [w for w in palabras if w in campos and w not in ("modelo", "nombre", "descripcion")]
    valor = " ".join(w for w in palabras if w not in pista)
    if not valor:
        return {"sin_campo": condicion}
    donde = pista + [x for x in PRIORIDAD if x not in pista]
    for campo in donde:
        if any(_contiene(_valores(p, campo), valor) for p in universo):
            return {"campo": campo, "valor": valor, "niega": niega}
    # Toda la frase no esta: cada palabra por su lado, y todas tienen que estar.
    partes = [atar(("no " if niega else "") + w, universo, tienda_id) for w in valor.split()] if " " in valor else []
    if partes and all("campo" in x for x in partes):
        return {"todas": partes}
    return {"sin_campo": condicion}


def cumple(prod: dict, filtro: dict) -> bool:
    if "todas" in filtro:
        return all(cumple(prod, f) for f in filtro["todas"])
    if "tope" in filtro:
        lado, monto = filtro["tope"]
        precio = int(prod.get("precio_ars") or 0)
        return precio <= monto if lado == "max" else precio >= monto
    hay = _contiene(_valores(prod, filtro["campo"]), filtro["valor"])
    return not hay if filtro["niega"] else hay


ORDEN = {"mas barato": ("precio_ars", 1), "mas caro": ("precio_ars", -1),
         "mas liviano": ("peso_gramos", 1), "mas pesado": ("peso_gramos", -1)}


def buscar(rubro_: str, condiciones: list, orden: str, cuantos: int, tienda_id: str, entre: list = None) -> dict:
    """{"filas", "sin_campo", "vacio_por", "orden_desconocido"}. Las filas son productos con stock, uno por modelo.
    Si las condiciones juntas dejan cero, vuelve lo que hay sin la que vacio y `vacio_por` dice cual fue."""
    universo = [p for p in productos(tienda_id) if (not rubro_ or p.get("categoria") == rubro_)
                and (entre is None or str(p["id"]) in entre)]
    filtros, sin_campo = [], []
    for c in condiciones or []:
        f = atar(str(c), universo, tienda_id)
        (sin_campo.append(f["sin_campo"]) if "sin_campo" in f else filtros.append((str(c), f)))
    quedan = [p for p in universo if con_stock(p) and all(cumple(p, f) for _, f in filtros)]
    vacio_por = []
    if not quedan and filtros:
        vacio_por = [c for c, f in filtros if not any(cumple(p, f) for p in universo if con_stock(p))] or \
                    [c for c, _ in filtros]
        quedan = [p for p in universo if con_stock(p) and all(cumple(p, f) for c, f in filtros if c not in vacio_por)]
    clave = ORDEN.get(n(orden))
    if not clave:
        cuantos = max(int(cuantos or 0), 5)
    else:
        quedan.sort(key=lambda p: clave[1] * float(p.get(clave[0]) or 0))
    filas, vistos = [], set()
    for p in quedan:
        m = (p.get("marca"), p.get("modelo") or p["id"])
        if m not in vistos:
            vistos.add(m)
            filas.append(p)
    return {"filas": filas[:max(1, int(cuantos or 5))], "sin_campo": sin_campo, "vacio_por": vacio_por,
            "orden_desconocido": n(orden) if orden and n(orden) not in ("nada", "") and not clave else ""}
