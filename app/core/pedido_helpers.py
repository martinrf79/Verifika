"""
PEDIDO_HELPERS — funciones PURAS compartidas de pedido/producto.

Fuente ÚNICA de estos helpers. Nacieron dentro de interprete_libre (2296 líneas,
legado), que se borró con el cambio de arquitectura del 1-ago junto con
solver_gemini: hoy los usa el camino vivo -hub_venta, herramientas,
estado_venta, guia_pedido- y nadie más. Acá vive `certificar_producto`, que es
la regla cero del proyecto: quién decide si un producto existe es el CÓDIGO.

Sin dependencias de app.*: son puras, operan sobre los datos que reciben.
"""
from functools import lru_cache as _lru_cache


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


# La puntuacion que el cliente pega al final de una palabra y NO forma parte de
# ella. Se saca solo de los BORDES del token: adentro puede ser dato -el
# "Z906 5.1" de Logitech, un "16.1" de pantalla- y partirlo ahi romperia el
# modelo en dos numeros que no identifican nada.
_PUNTUACION = "?!.,;:\"'()[]{}¿¡«»…"


def _pelar(t: str) -> str:
    return t.strip(_PUNTUACION)


@_lru_cache(maxsize=8192)
def _tokens_cache(s: str) -> frozenset:
    """El tokenizado memorizado. `certificar_producto` re-tokeniza los 880
    productos del catalogo en CADA llamada, y un turno certifica varias veces:
    son cientos de miles de tokenizaciones por mensaje, todas del mismo texto
    -el catalogo no cambia dentro del turno-. La funcion es pura sobre un
    string, asi que memorizarla no cambia un solo veredicto; el barrido de los
    6.160 casos baja de 92 a 6 segundos, y el turno vivo paga lo mismo menos."""
    return frozenset(_tokens_producto_calc(s))


def _tokens_producto(s: str) -> set:
    return set(_tokens_cache(s))


def _tokens_producto_calc(s: str) -> set:
    # el numero de un solo digito NO se descarta: "IdeaPad 3" y "IdeaPad Slim 5"
    # se distinguen justo por ese caracter, y tirarlo hacia que el 3 matcheara
    # tambien al Slim 5 (visto en el universo del 28-jul).
    #
    # EL SIGNO DE PREGUNTA PEGADO, medido el 12-ago barriendo el catalogo: sin
    # pelar la puntuacion, "tenes el Logitech G203?" deja el token 'g203?', que
    # no existe en ningun producto, y el certificador contestaba `otro_modelo`
    # -"ese no lo tengo, mira estos otros de la linea"- sobre un producto que SI
    # esta en gondola. Es la falla numero uno del negocio, negar stock que
    # existe, y le pasaba a 517 de los 880 productos por un signo de puntuacion.
    return {p for p in (_pelar(t) for t in
                        _norm_txt(s).replace("-", " ").split())
            if p and (len(p) >= 2 or p.isdigit()) and p not in _GENERICAS}


# Lo unico que NUNCA distingue un producto de otro: los conectores del
# castellano. Todo lo demas -la letra suelta, 'pro', 'plus'- SI distingue, y es
# la diferencia entre la Kiyo X y la Kiyo Pro.
_CONECTORES = {"de", "la", "el", "con", "y", "para", "un", "una", "los", "las"}


def _tokens_fieles(s: str) -> set:
    """Los tokens SIN podar, para el desempate por especificidad.

    `_tokens_producto` poda a proposito: tira la palabra corta y la generica
    para que el match no se caiga por una muletilla. Esa poda es correcta para
    DECIDIR SI un producto matchea, y es exactamente lo que no sirve para
    decidir CUAL de dos matcheos es el que el cliente nombro: lo que separa la
    Kiyo X de la Kiyo Pro es una letra suelta y la palabra 'pro', y las dos las
    tira. Aca no se tira ninguna.
    """
    return {p for p in (_pelar(t) for t in
                        _norm_txt(s).replace("-", " ").split())
            if p and p not in _CONECTORES}


def _modelo_mas_especifico(hits: list, resuelto: str) -> list:
    """De varios MODELOS que matchean, el que el cliente nombro ENTERO.

    EL DEFECTO QUE CIERRA, medido el 12-ago barriendo el catalogo entero: de los
    880 productos, 23 no resolvian escribiendo su nombre EXACTO del catalogo. No
    eran 23 problemas sino uno, en 16 modelos: `pedido <= nom` es una prueba de
    CONTENCION, asi que un modelo cuyo nombre esta contenido en el de otro de la
    misma marca no puede ganar nunca solo. El cliente escribia "Microfono Blue
    Yeti" y le contestaban preguntando si queria el Yeti o el Yeti Nano; lo mismo
    el 980 contra el 980 PRO, el Hyper 212 contra el Hyper 212 Halo, la Kiyo X
    contra la Kiyo Pro y el G502 X contra el G502 Hero.

    LA REGLA ES LA MISMA QUE YA GOBIERNA LA FAQ -el tema especifico le gana al
    generico- Y EL MAXIMAL MUNCH DE LAS LOCALIDADES, y tiene dos mitades porque
    el defecto tiene dos caras:

      1. NOMBRADO ENTERO. Se descartan los modelos que tienen alguna palabra
         propia que el cliente no dijo. Se cuenta cuanto dice el modelo DE MAS,
         nunca cuanto dice el cliente de mas: el rubro y el color que el cliente
         agrega no penalizan a nadie.
      2. EL MAS LARGO GANA. La primera mitad sola no alcanza, y lo mostro el
         mismo barrido: ante "Samsung 980 PRO 500GB" el modelo `980 500GB`
         TAMBIEN esta nombrado entero, porque sus palabras son un subconjunto de
         las del PRO. Entre dos nombrados enteros gana el que usa MAS de lo que
         el cliente escribio, que es exactamente el maximal munch con el que
         `geo_cp` desambigua 'villa maria' de 'maria'.

    SE MIRA EL MODELO, NO LA MARCA. El cliente no tiene por que nombrar la marca
    para identificar un producto: "g502 x" y "kiyo pro" alcanzan solos. Exigir la
    marca dejaba sin resolver el codigo de modelo pelado, que es como escribe el
    que ya sabe lo que quiere.

    CONSERVADOR, y es lo que lo hace seguro: si a los mejores todavia les falta
    una palabra -"logitech g502", que puede ser la X o la Hero- no gana ninguno y
    el turno PREGUNTA, que es lo correcto y lo que ya hacia. Nunca convierte un
    `exists` en otra cosa: solo puede desempatar un `ambiguous` que hoy no le
    sirve a nadie.
    """
    dicho = _tokens_fieles(resuelto)
    por_modelo: dict[tuple, list] = {}
    for p in hits:
        clave = (_norm_txt(p.get("marca")), _norm_txt(p.get("modelo")),
                 _norm_txt(p.get("categoria")))
        por_modelo.setdefault(clave, []).append(p)
    enteros = []
    for clave, ps in por_modelo.items():
        propias = _tokens_fieles(clave[1])
        if propias and not (propias - dicho):
            enteros.append((len(propias), ps))
    if not enteros:
        return []
    largo = max(n for n, _ in enteros)
    ganan = [ps for n, ps in enteros if n == largo]
    return ganan[0] if len(ganan) == 1 else []


def certificar_producto(resuelto: str, catalogo: list) -> tuple[str, list]:
    """CERTIFICADOR de identidad: (veredicto, productos). Regla cero del
    proyecto: quien decide si un producto existe es el CODIGO.

    veredicto:
      exists      -> un solo MODELO real; `productos` trae sus variantes
                     (colores, CPU). Todo lo que comparten se puede contestar.
      ambiguous   -> varios MODELOS distintos; hay que preguntar cual.
      otro_modelo -> el cliente nombro un DESIGNADOR que no existe en la fuente
                     -pide la ROG Strix G15 y tenemos la G16-. `productos` trae
                     los de esa linea, para ofrecerlos SIN confirmar el que
                     pidio. No es exists disfrazado: el que pidio NO lo tenemos.
      not_found   -> nada del catalogo matchea.

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
    # EL VOCABULARIO DE LA FUENTE, en la misma pasada. Sirve para las dos reglas
    # de abajo, que separan la palabra que sobra del modelo que no existe.
    fichas, vocabulario = [], set()
    for p in (catalogo or []):
        if not (p.get("nombre") and p.get("id")):
            continue
        nom = _tokens_producto(f"{p.get('nombre')} {p.get('marca') or ''} "
                               f"{p.get('modelo') or ''}")
        vocabulario |= nom
        fichas.append((p, nom))

    # ── REGLA 1: LA PALABRA QUE NO EXISTE EN NINGUN PRODUCTO ES CHARLA ───────
    # El esquema le pide al modelo la descripcion "tal cual la dijo el cliente",
    # asi que entra con verbos y muletillas: "quiero una notebook asus". Con el
    # match estricto -toks <= nombre- una sola palabra de mas tira todo abajo, y
    # medido el 5-ago "quiero una notebook asus" daba not_found mientras
    # "notebook asus" daba ambiguo. Lo que no esta en el vocabulario de los 880
    # no distingue un producto de otro: se ignora.
    # ── REGLA 2: EL DESIGNADOR ES LA PARTE QUE IDENTIFICA EL MODELO ──────────
    # "g15" no es una muletilla: es lo que distingue una notebook de otra, y es
    # el caso de la consigna -piden la ROG Strix G15, tenemos la G16 y le
    # pegabamos las specs de esa-. Se reconoce por la forma, letras y digitos
    # juntos. Una cantidad suelta ("2 auriculares") o una medida ("27
    # pulgadas") no entra: son digitos pelados, no designadores. Y no alcanza
    # con que exista en el catalogo -"g15" existe, es una Dell-: tiene que
    # estar en el producto que matchea.
    designadores = {t for t in toks
                    if any(c.isdigit() for c in t) and any(c.isalpha() for c in t)}
    toks = toks - ({t for t in toks if t not in vocabulario} - designadores)
    pedido = toks - designadores
    # Una sola palabra corta no identifica nada: "un regalo para mi viejo" deja
    # 'mi', que es la linea Mi de Xiaomi, y devolvia un cargador como si el
    # cliente lo hubiera pedido.
    #
    # PERO EL CODIGO DE MODELO SOLO SI IDENTIFICA, y este corte lo mataba
    # (medido el 10-ago). "tenes el g203?" deja toks={'g203'}, que es TODO
    # designador, asi que `pedido` quedaba vacio y se devolvia not_found **sin
    # mirar el catalogo**, con el Mouse Logitech G203 Lightsync en gondola. Lo
    # mismo con "m170". Con la marca adelante -"logitech g203"- funcionaba
    # siempre, o sea que la falla se veia solo cuando el cliente escribe como
    # escribe de verdad: el codigo pelado. Es la falla numero uno del negocio,
    # negar stock que existe.
    #
    # La proteccion de arriba se conserva entera: se sigue con el designador
    # SOLO si esa palabra existe en el vocabulario de los 880. Un modelo
    # inventado -"g999"- no esta, y sale not_found como antes. Y abajo el match
    # ya hace lo correcto sin tocar nada: con `pedido` vacio, el que tiene el
    # designador en el nombre es HIT y el que no lo tiene es LINEA, que es
    # justo la distincion entre el producto pedido y su familia.
    #
    # DOS PALABRAS CORTAS JUNTAS SI IDENTIFICAN, y el barrido lo mostro: el
    # modelo "Go 3" de Insta360 son dos tokens de dos y un caracter, los dos
    # sobrevivieron a la Regla 1 -o sea que los dos existen en el catalogo- y
    # aun asi la guarda lo mataba. La proteccion original apunta a UNA palabra
    # corta suelta -el 'mi' que queda de "un regalo para mi viejo" y devolvia un
    # cargador Xiaomi-, no a un modelo escrito entero.
    if not pedido or (len(pedido) == 1 and all(len(t) < 3 for t in pedido)):
        if not (designadores & vocabulario):
            return "not_found", []

    hits, laxos, linea = [], [], []
    for p, nom in fichas:
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
        # El match se hace SIN el designador y se mira aparte si el producto lo
        # tiene. Asi el que lo tiene es el producto pedido, y el que no lo tiene
        # pero comparte todo lo demas es la LINEA: lo que hay que ofrecer sin
        # confirmar el modelo que no existe.
        if pedido <= nom:
            (hits if designadores <= nom else linea).append(p)
        elif marca and marca <= pedido and (modelo & pedido):
            (laxos if designadores <= nom else linea).append(p)
    # La estricta MANDA: si el nombre limpio pego, la laxa no se usa. Sin esta
    # precedencia, "asus tuf f15" se llevaba puestos los monitores Asus TUF,
    # porque comparten marca y la palabra TUF.
    hits = hits or laxos
    if not hits:
        if designadores and linea:
            return "otro_modelo", linea
        return "not_found", []
    modelos = {(_norm_txt(p.get("marca")), _norm_txt(p.get("modelo")),
                _norm_txt(p.get("categoria"))) for p in hits}
    if len(modelos) == 1:
        return "exists", hits
    # Varios modelos matchean. Antes de preguntar, se mira si el cliente nombro
    # UNO entero: el nombre contenido en otro no puede ganar solo, y esa era la
    # causa de los 23 del barrido. Ver `_modelo_mas_especifico`.
    nombrado = _modelo_mas_especifico(hits, resuelto)
    if nombrado:
        return "exists", nombrado
    return "ambiguous", hits












