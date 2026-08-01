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


def _money(n):
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return None


def _linea_producto(p: dict) -> str:
    """Linea REAL de un producto desde el catalogo: nombre + precio + stock. La
    verdad de la fuente, la usa el estampado de [[PROD:id]] y la guarda de
    producto para re-anclar con el dato real, no re-tipeado."""
    if not isinstance(p, dict):
        return ""
    nombre = str(p.get("nombre", "")).strip()
    precio = _money(p.get("precio_ars"))
    stock = p.get("stock", 0)
    partes = [nombre]
    if precio:
        partes.append(f"- ${precio}")
    if isinstance(stock, int) and stock > 0:
        partes.append(f"({stock} en stock)")
    return " ".join(partes).strip()


def _norm_txt(s) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


# palabras que no distinguen un producto de otro: si el cliente solo dice una
# de estas, no nombro un producto, nombro una categoria.
_GENERICAS = {"notebook", "note", "laptop", "mouse", "mause", "raton", "teclado",
              "monitor", "tablet", "auricular", "auriculares", "auris", "parlante",
              "microfono", "webcam", "camara", "router", "impresora", "gabinete",
              "fuente", "cooler", "silla", "ssd", "disco", "memoria", "ram",
              "procesador", "placa", "motherboard", "cargador", "de", "la", "el",
              "con", "y", "para", "un", "una", "los", "las", "gaming", "gamer",
              "pro", "plus", "color", "negro", "blanco", "gris", "azul", "rojo"}


def _tokens_producto(s: str) -> set:
    # el numero de un solo digito NO se descarta: "IdeaPad 3" y "IdeaPad Slim 5"
    # se distinguen justo por ese caracter, y tirarlo hacia que el 3 matcheara
    # tambien al Slim 5 (visto en el universo del 28-jul).
    return {t for t in _norm_txt(s).replace("-", " ").split()
            if (len(t) >= 2 or t.isdigit()) and t not in _GENERICAS}


def certificar_producto(resuelto: str, catalogo: list) -> tuple[str, list]:
    """CERTIFICADOR de identidad: (veredicto, productos). Regla cero del
    proyecto: quien decide si un producto existe es el CODIGO.

    veredicto:
      exists    -> un solo MODELO real; `productos` trae sus variantes (colores,
                   CPU). Todo lo que las variantes comparten se puede contestar.
      ambiguous -> varios MODELOS distintos; hay que preguntar cual.
      not_found -> nada del catalogo matchea.

    El match es por TOKENS significativos, no por substring contiguo. El
    substring era la falla estructural que dejaba ciega a toda la cadena: el
    cliente escribe "la asus tuf f15" y el catalogo dice "Notebook Asus TUF
    Gaming F15 Core i5 16GB 512GB SSD Gris", asi que no habia contencion en
    ningun sentido y salia None; y "zenbook 14" pegaba en las 9 variantes, que
    tambien caia a None por ambiguo. Con None, el universo se quedaba sin el
    producto, el prompt no llevaba un solo dato y el guardia de specs ni corria:
    el bot terminaba prometiendo chequear, negando que el producto exista o
    hablando del dato sin decirlo. Un catalogo con variantes de color y de CPU
    cae en esto casi siempre.
    """
    toks = _tokens_producto(resuelto)
    if not toks:
        return "not_found", []
    hits, laxos = [], []
    for p in (catalogo or []):
        if not (p.get("nombre") and p.get("id")):
            continue
        nom = _tokens_producto(f"{p.get('nombre')} {p.get('marca') or ''} "
                               f"{p.get('modelo') or ''}")
        # DOS DIRECCIONES, porque entran dos cosas distintas por aca:
        # 1) el nombre limpio que resolvio el interprete -"asus tuf f15"-, que
        #    tiene que estar contenido en el del catalogo;
        # 2) el MENSAJE crudo del cliente -"tenes la acer nitro 5?"-, al que le
        #    sobran palabras, y ahi lo que tiene que estar contenido es la marca
        #    y el modelo del producto dentro del mensaje.
        # En el catalogo real el campo modelo arrastra el CPU y la RAM
        # ("Nitro 5 Core i5 16GB 512GB SSD"), asi que pedir el modelo entero
        # dentro del mensaje no matchea nunca. La marca si tiene que estar
        # completa, y del modelo alcanza con que el cliente haya dicho al menos
        # una palabra propia: "acer nitro 5" pega, "algo de acer" no.
        marca = _tokens_producto(p.get("marca"))
        modelo = _tokens_producto(p.get("modelo"))
        if toks <= nom:
            hits.append(p)
        elif marca and marca <= toks and (modelo & toks):
            laxos.append(p)
    # La estricta MANDA: si el nombre limpio pego, la laxa no se usa. Sin esta
    # precedencia, "asus tuf f15" se llevaba puestos los monitores Asus TUF,
    # porque comparten marca y la palabra TUF.
    hits = hits or laxos
    if not hits:
        return "not_found", []
    modelos = {(_norm_txt(p.get("marca")), _norm_txt(p.get("modelo")),
                _norm_txt(p.get("categoria"))) for p in hits}
    return ("exists" if len(modelos) == 1 else "ambiguous"), hits


def _resolver_nombre_a_producto(resuelto: str, catalogo: list) -> dict | None:
    """UN producto del catalogo para el nombre que resolvio el interprete, o
    None si no se puede decidir. Se apoya en certificar_producto: si las
    variantes son del MISMO modelo, devuelve la primera -comparten ficha, specs
    y casi siempre precio-; si son modelos distintos o no hay ninguno, None."""
    veredicto, hits = certificar_producto(resuelto, catalogo)
    return hits[0] if veredicto == "exists" else None


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
    """Destinos DISTINTOS (no null) que leyo el interprete, del pedido y de la
    solicitud nueva. MANDA sobre los que reescribe el solver: en la charla real
    del 1-ago el interprete leyo los tres -Berrotaran, Concordia y Posadas- y
    el modelo emitio dos, asi que se cobro un envio de menos."""
    dests: list[str] = []
    for campo in ("pedido", "solicitud_nueva"):
        for it in (interp or {}).get(campo) or []:
            if not isinstance(it, dict):
                continue
            d = str(it.get("destino") or "").strip()
            if d and d.lower() not in [x.lower() for x in dests]:
                dests.append(d)
    return dests


def grupos_de_interp(interp, tienda_id=None) -> list | None:
    """El REPARTO del pedido tal como lo leyo el interprete: qué cantidad de qué
    categoria va a cada destino, en el formato que consume `calculate_total`.

    Por que existe (charla real de Martin, 1-ago). El reparto lo armaba un
    regex sobre el mensaje crudo, y ante "2 memorias 2 auriculares y 2 mauses,
    1 memoria y un auricular a berrotaran, 1 auricular y 1 mause a concordia,
    el resto a posadas" ese regex leyo DOS AURICULARES y nada mas: perdio las
    memorias, los mouses y un destino entero. El interprete, en el mismo turno,
    lo habia leido completo. Esto usa lo que ya estaba resuelto en vez de
    volver a adivinarlo.

    Devuelve None si el interprete no repartio nada, y ahi el llamador cae al
    camino de siempre. No inventa: si un renglon no trae destino, no entra.
    """
    grupos: dict = {}
    for campo in ("pedido", "solicitud_nueva"):
        for it in (interp or {}).get(campo) or []:
            if not isinstance(it, dict):
                continue
            destino = str(it.get("destino") or "").strip()
            if not destino:
                continue
            # la categoria sale del renglon (solicitud_nueva) o del producto ya
            # mostrado (pedido); sin ninguna de las dos el renglon no sirve
            # para agrupar y se descarta.
            cat = str(it.get("categoria") or "").strip()
            if not cat and it.get("producto"):
                cat = _categoria_de_producto(str(it["producto"]), tienda_id)
            if not cat:
                continue
            try:
                n = int(it.get("cantidad") or 1)
            except (TypeError, ValueError):
                n = 1
            if n <= 0:
                continue
            clave = destino.lower()
            grupos.setdefault(clave, {"destino": destino, "cats": {}})
            grupos[clave]["cats"][cat] = grupos[clave]["cats"].get(cat, 0) + n
    if len(grupos) < 2:
        # con un solo destino no hay reparto que hacer: la cuenta es una sola.
        return None
    return [{"destino": g["destino"],
             "cats": [{"n": n, "cat": c} for c, n in g["cats"].items()]}
            for g in grupos.values()]


def _categoria_de_producto(nombre: str, tienda_id=None) -> str:
    """La categoria REAL de un producto ya mostrado. Vacio si no se ubica."""
    try:
        from app.storage.firestore_client import get_all_products
        n = _norm_txt(nombre)
        for p in get_all_products(tienda_id=tienda_id) or []:
            if _norm_txt(p.get("nombre")) == n:
                return str(p.get("categoria") or "")
    except Exception:
        pass
    return ""
