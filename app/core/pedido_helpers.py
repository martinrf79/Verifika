"""
PEDIDO_HELPERS — funciones PURAS compartidas de pedido/producto.

Fuente ÚNICA de estos helpers. Nacieron dentro de interprete_libre (2296 líneas,
legado), pero el camino vivo (hub_atado, generador_v2, compositor, estado_venta,
guia_pedido) los reusa sin necesitar nada del resto de ese módulo. Se extraen acá
para que el camino vivo NO dependa del legado y para tener una sola copia (sin
duplicar la lógica). interprete_libre y solver_gemini los re-importan desde acá,
así lo que aún los usa por el nombre viejo sigue funcionando.

Sin dependencias de app.*: son puras, operan sobre los datos que reciben.
"""


def _money(n) -> str:
    """Formatea un número como pesos argentinos con separador de miles:
    273000 -> '$273.000'. Función canónica; los demás módulos importan
    desde aquí en vez de duplicar la lógica."""
    try:
        return "$" + f"{int(round(n)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def _linea_producto(p: dict) -> str:
    """Linea REAL de un producto desde el catalogo: nombre + precio + stock. La
    verdad de la fuente, la usa el estampado de [[PROD:id]] y la guarda de
    producto para re-anclar con el dato real, no re-tipeado."""
    if not isinstance(p, dict):
        return ""
    nombre = str(p.get("nombre", "")).strip()
    precio_raw = p.get("precio_ars")
    stock = p.get("stock", 0)
    partes = [nombre]
    if isinstance(precio_raw, (int, float)):
        partes.append(f"- {_money(precio_raw)}")
    if isinstance(stock, int) and stock > 0:
        partes.append(f"({stock} en stock)")
    return " ".join(partes).strip()


def _resolver_nombre_a_producto(resuelto: str, catalogo: list) -> dict | None:
    """Reconcilia el NOMBRE que resolvio el interprete con UN producto del
    catalogo, por contencion de nombre completo: el nombre del catalogo esta
    contenido en el resuelto o al reves (matchear por token suelto daria
    'mouse' contra medio catalogo; por eso el viejo certificador de queries no
    servia aca y se retiro en la limpieza del 10-jul). Devuelve el producto
    SOLO si matchea uno unico; ante cero o varios, None (no se pisa la
    respuesta). Un termino vago como 'mouse' matchea muchos y cae a None, que
    es lo que queremos."""
    import unicodedata

    def _n(s):
        s = unicodedata.normalize("NFKD", str(s or "").lower())
        return "".join(c for c in s if not unicodedata.combining(c)).strip()

    r = _n(resuelto)
    if not r:
        return None
    hits: dict[str, dict] = {}
    for p in catalogo or []:
        nom = _n(p.get("nombre"))
        pid = str(p.get("id") or "")
        if nom and pid and (nom in r or r in nom):
            hits[pid] = p
    return next(iter(hits.values())) if len(hits) == 1 else None


def _presupuesto_de_meta(meta: dict) -> str:
    """Saca el presupuesto YA VERIFICADO (campo presentacion de calculate_total)
    del meta del solver, para que el cierre y el link de pago usen el total real
    de la calculadora, nunca uno inventado. "" si el solver no calculo este turno."""
    for tc in reversed((meta or {}).get("tools_called", []) or []):
        if tc.get("name") == "calculate_total":
            pres = (tc.get("result") or {}).get("presentacion")
            if pres:
                return pres
    return ""


def _parece_aportar_dato(mensaje: str) -> bool:
    """Heuristica barata: el mensaje parece traer un dato de cierre (numero, pago,
    o cue de domicilio), aunque el interprete no lo haya marcado como aporta_dato.
    Abre el extractor LLM en cotizaciones que ya mencionan direccion o pago."""
    if not mensaje:
        return False
    t = mensaje.lower()
    if any(ch.isdigit() for ch in t):
        return True
    claves = ("transferenc", "mercado pago", "efectivo", "tarjeta", "debito",
              "credito", "calle", "avenida", " av ", "direccion", "domicilio",
              "envio a", "enviar a", "me llamo", "mi nombre")
    return any(k in t for k in claves)


def _destinos_de_interp(interp) -> list[str]:
    """Destinos DISTINTOS (no null) del pedido que extrajo el interprete (atado
    por enum). Es la SEÑAL para forzar cotizar_envio: si el cliente reparte el
    pedido, el solver DEBE cotizar cada destino antes de redactar. No calcula
    nada, solo lista que hay que cotizar."""
    dests: list[str] = []
    for it in (interp or {}).get("pedido") or []:
        if not isinstance(it, dict):
            continue
        d = str(it.get("destino") or "").strip()
        if d and d.lower() not in [x.lower() for x in dests]:
            dests.append(d)
    return dests
