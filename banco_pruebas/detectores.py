"""
DETECTORES DEL BANCO — los instrumentos con los que se MIDE una corrida.

De donde salen: hasta el 2-ago vivian en `app/core/verificador_stock.py` y
`app/core/guardia_promesas.py`, o sea adentro del bot, corrigiendo al modelo
despues de que escribiera. Esa capa se borro con el cambio de arquitectura: el
control ahora esta antes, en el dato que se le entrega al modelo.

Pero los DETECTORES en si no eran la capa: son puro regex contra el catalogo, y
son lo unico que permite auditar una corrida sin que un humano lea cada salida.
Se mudan aca, que es su lugar: un instrumento de medicion no manda en el camino
vivo. Si el bot afirma un stock que el catalogo desmiente, o promete un dia de
entrega, la corrida lo marca y no sale verde.

Se copiaron TAL CUAL, sin las funciones que reescribian texto -cuarentena,
instrucciones al modelo, la reescritura por LLM-, que eran la parte que corregia.
"""
import re

import re


def _tokens_significativos(nombre: str) -> list[str]:
    """Palabras distintivas de un nombre de producto: alfanumericas de 4+ chars.
    Descarta conectores y sufijos cortos (de, pro, v4) que dan falsos match."""
    return [t for t in re.findall(r"[a-z0-9]+", (nombre or "").lower())
            if len(t) >= 4]



# Ventana previa donde buscar el producto nombrado. Corta a proposito: el nombre
# tiene que estar pegado a la afirmacion para que el ancla sea creible.
_VENTANA = 110

# Negacion de stock. Cubre las formas vistas en real y variantes cercanas.
_RE_SIN_STOCK = re.compile(
    r"(?:sin\s+stock|no\s+(?:hay|tiene|tienen|tenemos|queda|quedan)"
    r"(?:\s+m[aá]s)?\s+(?:stock|unidades|disponibilidad)|"
    r"agotad\w+|no\s+est[aá]n?\s+disponibles?|sin\s+disponibilidad|"
    r"fuera\s+de\s+stock|no\s+lo\s+tenemos\s+disponible)",
    re.IGNORECASE)

# Afirmacion de disponibilidad. Incluye "lo tenemos" / "tenemos el X": afirmar
# que se TIENE un producto agotado es la misma promesa falsa aunque no diga la
# palabra stock (visto en el banco: "Tenemos el DX-110 Blanco", stock 0).
_RE_CON_STOCK = re.compile(
    r"(?:(?:tiene|tienen|tenemos|hay)\s+stock|en\s+stock|disponibles?\b|"
    r"(?:lo|la)\s+tenemos\b|tenemos\s+(?:el|la)\b)",
    re.IGNORECASE)

# Cifra de unidades SOLO con cue de disponibilidad: "quedan 9", "3 en stock",
# "5 disponibles", "4 unidades disponibles". Un numero pelado ("te confirmo 10
# unidades") es la cantidad del pedido, no una afirmacion de stock: no se toca.
_RE_UNIDADES = re.compile(
    r"(?:quedan?\s+(\d{1,4})\b|"
    r"(\d{1,4})\s+(?:unidades?\s+)?(?:en\s+stock|disponibles?)\b)",
    re.IGNORECASE)

# Si al numero lo sigue OTRA unidad (dias, cuotas...), no es stock ("quedan 3
# dias de oferta").
_RE_NO_ES_STOCK = re.compile(
    r"^\s*(?:d[ií]as?|cuotas?|mes(?:es)?|horas?|hs|pesos|%)", re.IGNORECASE)

# Frase condicional/hipotetica antes del disparo: "si no tiene stock te aviso".
_RE_CONDICIONAL = re.compile(
    r"\b(?:si|cuando|en\s+caso(?:\s+de)?|por\s+si)\b[^.!?\n]{0,45}$",
    re.IGNORECASE)

# Negacion pegada a una afirmacion de disponibilidad: "no tiene stock" contiene
# "tiene stock"; sin esta guarda la afirmacion dispararia dentro de su negacion.
_RE_NEGADO = re.compile(r"\b(?:no|sin|tampoco|nunca|ya\s+no)\b[\w\s]{0,12}$",
                        re.IGNORECASE)


# Colores del catalogo y sus variantes de genero, a una clave canonica. Sirve
# para no acusar a un producto de una afirmacion que habla de OTRO color: "el
# KB-110X Blanco... el negro esta sin stock" es honesto (el blanco tiene stock,
# el negro NO), pero el ancla cae al Blanco nombrado y disparaba falso positivo.
_COLOR_CANON = {
    "negro": "negro", "negra": "negro",
    "blanco": "blanco", "blanca": "blanco",
    "gris": "gris", "plata": "plata", "plateado": "plata", "plateada": "plata",
    "azul": "azul", "celeste": "celeste",
    "rojo": "rojo", "roja": "rojo",
    "verde": "verde", "rosa": "rosa", "rosado": "rosa", "rosada": "rosa",
    "amarillo": "amarillo", "amarilla": "amarillo", "violeta": "violeta",
    "naranja": "naranja", "dorado": "dorado", "dorada": "dorado",
    "bordo": "bordo", "beige": "beige",
}


def _norm_txt(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _color_de_otra_variante(texto: str, m: "re.Match", prod: dict) -> bool:
    """True si la CLAUSULA de la afirmacion nombra un color distinto al del
    producto anclado: entonces habla de OTRA variante y no lo acusa. El producto
    real tiene campo `color`; sin color conocido, no se aplica la guarda."""
    canon_prod = _COLOR_CANON.get(_norm_txt(prod.get("color")).strip())
    if not canon_prod:
        return False
    # Clausula: desde el limite de oracion o parentesis previo hasta un poco
    # despues del disparo. El color que CALIFICA la afirmacion es el mas CERCANO
    # al disparo, no cualquiera de la clausula: el nombre del producto trae su
    # propio color mas atras ("KB-110X Blanco, el negro esta sin stock") y no
    # debe confundir. Se compara ese color cercano con el del producto anclado.
    ini = 0
    for ch in ".!?\n(":
        pos = texto.rfind(ch, 0, m.start())
        if pos + 1 > ini:
            ini = pos + 1
    win = _norm_txt(texto[ini:m.end() + 15])
    trig = m.start() - ini
    mejor = None  # (distancia_al_disparo, color_canonico)
    for w, canon in _COLOR_CANON.items():
        for cm in re.finditer(r"\b" + re.escape(w) + r"\b", win):
            d = abs(cm.start() - trig)
            if mejor is None or d < mejor[0]:
                mejor = (d, canon)
    return mejor is not None and mejor[1] != canon_prod


def _productos_con_stock(evidencia: list[dict]) -> list[dict]:
    """Productos de la evidencia cuyo stock real ES conocido (entero). Los de
    memoria sin stock no juzgan: el stock cambia turno a turno."""
    return [i for i in (evidencia or [])
            if i.get("tipo") == "producto" and isinstance(i.get("stock"), int)]


def _producto_en_ventana(pre: str, productos: list[dict]) -> dict | None:
    """El UNICO producto del catalogo nombrado en la ventana de texto dada.
    None si ninguno matchea o si matchean dos distintos (ambiguo). Mismo
    anclaje por tokens del nombre que usa el verificador de plata."""
    # Ancla EXACTA primero: el nombre COMPLETO del producto esta literal en la
    # ventana (el estampado imprime el nombre completo, asi que es el caso
    # normal). Uno solo con nombre completo presente gana aunque hermanos de
    # la misma marca compartan tokens ("Genius DX-110" vs "Genius NX-7000",
    # cuyos codigos cortos el tokenizador descarta). Dos nombres completos
    # presentes = ambiguedad real, se sigue con el puntaje por tokens.
    # Dedup por id: el mismo producto puede entrar a la evidencia por varios
    # caminos (mostrado + nombrado + busqueda del turno) y dos entradas
    # identicas NO son ambiguedad (bug visto en el banco: el duplicado hacia
    # caer el ancla exacta al puntaje por tokens, donde dos blancos de modelos
    # distintos empataban y la mentira pasaba).
    exactos = {str(p.get("id") or id(p)).upper(): p for p in productos
               if (p.get("nombre") or "").strip()
               and str(p["nombre"]).lower() in pre}
    if len(exactos) == 1:
        return next(iter(exactos.values()))
    candidatos: dict[str, tuple[int, dict]] = {}
    for p in productos:
        toks = _tokens_significativos(p.get("nombre", ""))
        if not toks:
            continue
        # Tokens con LIMITE DE PALABRA: el chequeo por substring anclaba
        # productos que NO estaban en el texto ('model' del Glorious Model O
        # matcheaba adentro de 'modelo' y con 'blanco' llegaba al umbral;
        # falso sin_stock_falso visto en el banco 13-jul).
        presentes = sum(
            1 for t in toks
            if re.search(r"\b" + re.escape(str(t)) + r"\b", pre))
        if presentes >= min(2, len(toks)):
            candidatos[str(p.get("id") or "").upper()] = (presentes, p)
    if not candidatos:
        return None
    if len(candidatos) == 1:
        return next(iter(candidatos.values()))[1]
    # Desempate entre variantes del mismo modelo (el caso comun: dos colores):
    # gana el que matchea MAS tokens del nombre, porque el token que sobra es
    # justamente el distintivo ("blanco" nombra al Blanco, no al Negro). Empate
    # real de puntaje sigue siendo ambiguo y no se toca.
    puntajes = sorted((c[0] for c in candidatos.values()), reverse=True)
    if puntajes[0] > puntajes[1]:
        return max(candidatos.values(), key=lambda c: c[0])[1]
    return None


def _producto_nombrado(texto: str, start: int,
                       productos: list[dict]) -> dict | None:
    """Ancla hacia ATRAS: el producto nombrado en la ventana previa a start."""
    return _producto_en_ventana(
        texto[max(0, start - _VENTANA):start].lower(), productos)


def _producto_anclado(texto: str, m: "re.Match", productos: list[dict],
                      misma_oracion: bool = False) -> dict | None:
    """Ancla de una afirmacion de disponibilidad: primero hacia atras (el caso
    normal, 'el X no tiene stock') y si no hay, hacia ADELANTE ('tenemos el X',
    'no hay stock del X': el nombre viene despues del verbo). Misma regla de
    unicidad en las dos direcciones.

    misma_oracion=True corta la ventana adelante en el primer limite de
    oracion: para una NEGACION, el producto negado viene en la misma clausula;
    lo que sigue despues del punto suele ser la ALTERNATIVA que se ofrece y
    anclarla acusaria al producto equivocado (falso positivo visto en el
    banco: 'no tiene stock. Mira estas opciones: Glorious...')."""
    p = _producto_nombrado(texto, m.start(), productos)
    if p is not None:
        return p
    post = texto[m.end():m.end() + _VENTANA]
    if misma_oracion:
        corte = re.search(r"[.!?\n]", post)
        if corte:
            post = post[:corte.start()]
    return _producto_en_ventana(post.lower(), productos)


def detectar_stock_contradicho(respuesta: str,
                               evidencia: list[dict]) -> list[dict]:
    """Afirmaciones de disponibilidad que CONTRADICEN el catalogo, ancladas a un
    producto unico. Devuelve [{clase, id, nombre, stock}]:
      - sin_stock_falso: niega stock de un producto que SI tiene (venta perdida).
      - con_stock_falso: ofrece como disponible un producto agotado (promesa falsa).
    Una negacion VERDADERA (agotado de verdad) no dispara: es honestidad."""
    productos = _productos_con_stock(evidencia)
    if not respuesta or not productos:
        return []
    out: list[dict] = []
    vistos: set[tuple] = set()

    def _agregar(clase: str, p: dict):
        clave = (clase, str(p.get("id") or "").upper())
        if clave in vistos:
            return
        vistos.add(clave)
        out.append({"clase": clase, "id": str(p.get("id") or "").upper(),
                    "nombre": p.get("nombre", ""), "stock": int(p["stock"])})

    for m in _RE_SIN_STOCK.finditer(respuesta):
        if _RE_CONDICIONAL.search(respuesta[max(0, m.start() - 50):m.start()]):
            continue
        p = _producto_anclado(respuesta, m, productos, misma_oracion=True)
        if p is not None and int(p["stock"]) > 0:
            if _color_de_otra_variante(respuesta, m, p):
                continue
            _agregar("sin_stock_falso", p)
    for m in _RE_CON_STOCK.finditer(respuesta):
        if _RE_NEGADO.search(respuesta[max(0, m.start() - 20):m.start()]):
            continue
        p = _producto_anclado(respuesta, m, productos)
        if p is not None and int(p["stock"]) == 0:
            if _color_de_otra_variante(respuesta, m, p):
                continue
            _agregar("con_stock_falso", p)
    return out


def corregir_unidades_stock(respuesta: str, evidencia: list[dict]) -> dict:
    """Safe-override de la CIFRA de unidades: si el texto declara una cantidad en
    stock distinta a la del catalogo y el producto anclado es unico, reescribe
    SOLO el numero por el real. Devuelve {respuesta, correcciones}."""
    productos = _productos_con_stock(evidencia)
    if not respuesta or not productos:
        return {"respuesta": respuesta, "correcciones": []}
    reemplazos: list[tuple] = []
    correcciones: list[dict] = []
    for m in _RE_UNIDADES.finditer(respuesta):
        if _RE_NO_ES_STOCK.match(respuesta[m.end():m.end() + 10]):
            continue
        gidx = 1 if m.group(1) else 2
        n = int(m.group(gidx))
        p = _producto_nombrado(respuesta, m.start(), productos)
        if p is None:
            continue
        real = int(p["stock"])
        if n == real:
            continue
        s, e = m.span(gidx)
        reemplazos.append((s, e, str(real)))
        correcciones.append({"de": n, "a": real,
                             "id": str(p.get("id") or "").upper(),
                             "concepto": "stock"})
    if not reemplazos:
        return {"respuesta": respuesta, "correcciones": []}
    nuevo = respuesta
    for s, e, token in sorted(reemplazos, reverse=True):
        nuevo = nuevo[:s] + token + nuevo[e:]
    return {"respuesta": nuevo, "correcciones": correcciones}




import asyncio




# ── DETECCION (determinista, sin LLM) ───────────────────────────────────────

# Contexto de LLEGADA (no de despacho: despachar rapido es legitimo, lo que
# miente es prometer el DIA en que el pedido llega).
_ENTREGA = (r"(?:lleg\w*|entreg\w*|recib\w*|arrib\w*|tendr\w*|teng\w*|"
            r"(?:lo\s+|te\s+lo\s+)?(?:vas\s+a\s+)?ten[eé]s|vas\s+a\s+tener|"
            r"en\s+tu\s+casa|en\s+tu\s+puerta|en\s+tu\s+domicilio|en\s+tus\s+manos)")
# Dia o fecha concreta, con diminutivos comunes y "finde". "dias habiles" no
# entra: no nombra un dia puntual. Incluye la fecha dicha por numero y mes en
# palabra ("25 de junio"), que el patron viejo de solo 25/6 dejaba pasar (E3).
_MESES = (r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
          r"septiembre|setiembre|octubre|noviembre|diciembre")
_DIA = (r"(?:lunes|lunecito|martes|martecito|mi[eé]rcoles|jueves|juevecito|"
        r"viernes|viernecito|s[áa]bado|sabadito|domingo|dominguito|"
        r"finde|fin\s+de\s+semana|semana\s+que\s+viene|pr[oó]xima\s+semana|"
        r"semana\s+pr[oó]xima|ma[ñn]ana|pasado\s+ma[ñn]ana|hoy\s+mismo|"
        rf"\d{{1,2}}\s+de\s+(?:{_MESES})|"
        r"\b\d{1,2}/\d{1,2}\b)")
# El dia y el verbo de entrega tienen que estar en la MISMA oracion. El hueco
# era `.{0,40}` con DOTALL, o sea que cruzaba puntos y saltos de linea y pegaba
# dos frases que no tenian nada que ver. Caso real, guion 21 turno 4: "...lo
# resolvemos hoy mismo.\n\nSi el producto llegó con un faltante..." disparaba
# dia_entrega uniendo el "hoy mismo" de un parrafo con el "llegó" del siguiente.
# Ni la reescritura ni la poda podian arreglar una promesa que no existia, asi
# que el turno entero -una respuesta correcta sobre garantia- caia al enlatado.
# Prometer un dia sigue siendo imposible: "te llega el martes" esta en una sola
# oracion, que es como se prometen las cosas de verdad.
_RE_DIA_ENTREGA = re.compile(
    rf"(?:{_ENTREGA}[^.!?\n]{{0,40}}?{_DIA}|{_DIA}[^.!?\n]{{0,40}}?{_ENTREGA})",
    re.IGNORECASE)

# RETIRO EN LOCAL. El verbo suelto NO alcanza: "retiro el teclado del pedido" es
# sacar un item, no invitar a buscarlo por el local. Ese falso positivo aparecio
# en la cuarta tanda del banco repetido sobre una respuesta perfecta, y un rojo
# falso ensena a ignorar el tablero. El verbo ahora exige el LUGAR cerca.
_RE_RETIRO = re.compile(
    r"(?:retir[aoáe]\w*|pas\w*\s+a\s+(?:buscar|retirar)|"
    r"ven[íi]\w*\s+a\s+(?:buscar|retirar)|acerc\w*\s+a\s+retir\w*)"
    r"[^.!?\n]{0,40}?"
    r"(?:local|sucursal|showroom|dep[oó]sito|oficina|direcci[oó]n)"
    r"|en\s+(?:el|nuestro)\s+local|en\s+la\s+sucursal|showroom"
    r"|punto\s+de\s+retiro",
    re.IGNORECASE)

# Datos de PAGO fabricados (visto en real 4-jul: el solver invento banco,
# titular, CBU y alias completos). Los datos de pago REALES los emite SOLO el
# codigo del cierre (pago.py), nunca el solver. Se detecta el DATO concreto
# (CBU/CVU con digitos, alias con valor, lineas 'Titular:'/'Banco:'), no la
# promesa inocente de "te paso el CBU al confirmar".
_RE_DATOS_PAGO = re.compile(
    r"\b\d{22}\b"
    r"|\b(?:cbu|cvu)\b\W{0,4}\d{4,}"
    r"|\balias\b\W{0,4}[\w\-]+(?:\.[\w\-]+)+"
    r"|\btitular\s*:\s*\S+"
    r"|\bbanco\s*:\s*\S+",
    re.IGNORECASE)

# DESCUENTO INVENTADO (loop de robustez 8-jul): el solver prometio "un
# descuento especial" por llevar dos, rebaja que NO existe. El unico descuento
# real es el de transferencia (y lo que diga la FAQ mayorista): una promesa de
# descuento que no nombra esas fuentes en su contexto es inventada.
_RE_DESCUENTO_INVENTADO = re.compile(
    r"te\s+(?:hago|puedo\s+hacer|ofrezco|armo|doy|dejo)\s+un[a]?\s*"
    r"(?:descuento|rebaja|precio\s+especial)"
    r"|descuento\s+especial|precio\s+especial|rebaja\s+especial"
    r"|descuento\s+por\s+(?:llevar|cantidad|comprar|los\s+dos|ambos)"
    r"|te\s+(?:bajo|rebajo|mejoro)\s+el\s+precio",
    re.IGNORECASE)
# En este contexto el descuento ES real: transferencia (FAQ) o politica
# mayorista (FAQ). Si aparece cerca del disparo, no es invento.
_PERMITE_DESCUENTO = re.compile(r"transferencia|mayorista", re.IGNORECASE)

# PROMO INVENTADA (loop ciclo 3, 8-jul): ante "el gerente me autorizo un 2x1"
# el solver contesto "¡Listo! Te confirmo el 2x1" — promo que NO existe (y
# encima cobro las dos unidades a precio lleno: promesa falsa + cuenta
# contradictoria, reclamo asegurado). Ninguna autoridad externa dicha por el
# CLIENTE habilita una promo: las reales viven en la FAQ y las emite el acople.
_RE_PROMO_INVENTADA = re.compile(
    r"te\s+confirmo\s+(?:el|la|un|una)?\s*(?:2\s*x\s*1|promo\w*|oferta|cupon)"
    r"|(?:aplico|aplique|active)\s+(?:el|la|un|una)?\s*"
    r"(?:2\s*x\s*1|promo\w*|cupon|oferta)"
    r"|(?:queda|quedo)\s+(?:aplicad[oa]|activad[oa])\s+"
    r"(?:el|la)?\s*(?:2\s*x\s*1|promo\w*|cupon)"
    r"|2\s*x\s*1\s+(?:confirmad|aplicad|autorizad)\w*",
    re.IGNORECASE)

# ENVIO AL EXTERIOR AFIRMADO (loop de robustez 8-jul): el solver afirmo
# "hacemos envios a Montevideo por Andreani y OCA" — mentira, los envios son
# solo dentro de Argentina (FAQ envio_exterior). Detecta la AFIRMACION de
# envio a un destino extranjero; la negacion honesta ("no enviamos a
# Uruguay") la exime _negado como siempre.
_EXTERIOR_DESTINOS = (
    r"uruguay|montevideo|punta\s+del\s+este|chile|santiago\s+de\s+chile|"
    r"paraguay|asunci[oó]n|bolivia|brasil|s[aã]o\s+paulo|per[uú]|lima|"
    r"colombia|bogot[aá]|m[eé]xico|espa[ñn]a|madrid|barcelona|miami|"
    r"estados\s+unidos|el\s+exterior|todo\s+el\s+mundo|otros?\s+pa[ií]ses|"
    r"fuera\s+de(?:l\s+pais|\s+argentina)")
# El lookbehind de negacion va en el regex porque el verbo ES el inicio del
# match y la ventana de _negado no lo alcanza ("No hacemos envios a Uruguay").
_RE_ENVIO_EXTERIOR = re.compile(
    rf"(?<!no )(?<!tampoco )"
    rf"(?:enviamos|mandamos|llegamos|despachamos|"
    rf"(?:hacemos|realizamos)\s+env[ií]os?|te\s+lo\s+(?:mando|env[ií]o|enviamos))"
    rf"(?:\s+\w+){{0,3}}?\s+a(?:l)?\s+(?:{_EXTERIOR_DESTINOS})"
    rf"|(?<!no )(?<!tampoco )(?:hacemos|realizamos|tenemos)\s+"
    rf"env[ií]os?\s+internacional\w*",
    re.IGNORECASE)

_RE_SERVICIOS = re.compile(
    r"envoltori\w*|envolv\w*\s+(?:para|de)\s+regalo|envuelt\w*\s+(?:para|de)?\s*regalo|"
    r"papel\w*\s+de?\s*regalo|papelit\w*|"
    r"nota\s+(?:a\s+mano|manuscrita|escrita\s+a\s+mano)|"
    r"tarjet\w*\s+de\s+regalo|tarjetit\w*|mo[ñn]o\s+de\s+regalo|"
    r"instalaci\w*|instal\w*\s+a\s+domicilio|"
    r"arm[aoáe]\w*\s+(?:la|tu|mi)?\s*(?:pc|compu|computadora)|"
    r"armado\s+de\s+(?:pc|compu)|ensambl\w*|"
    r"entrega\s+en\s+mano|te\s+lo\s+llevo\s+(?:en\s+persona|personalmente)",
    re.IGNORECASE)


# Negacion de POLITICA de la tienda: "no hacemos", "no tenemos", "no ofrecemos".
# Cuando el disparo cae dentro de una de estas, la tienda esta siendo HONESTA
# (niega un servicio que no da), no prometiendo: no es una promesa prohibida (E4).
_NEG_POLITICA = re.compile(
    r"\b(?:no|tampoco)\s+(?:\w+\s+){0,2}"
    r"(?:hac\w+|ten\w+|ofrec\w+|cont\w+|hay|dam\w+|realiz\w+|brind\w+|"
    r"manej\w+|trabaj\w+|dispon\w+)",
    re.IGNORECASE)


def _negado(texto: str, start: int) -> bool:
    """True si el disparo viene dentro de una negacion de politica de la tienda
    ('no hacemos instalacion', 'sin punto de retiro'): es honestidad, no una
    promesa. Mira la ventana corta antes del match, asi una negacion lejana e
    inconexa no lo tapa. El 'sin' solo cuenta pegado al match ('tienda online,
    sin punto de retiro'), no un 'sin problema' cualquiera en la oracion."""
    ventana = texto[max(0, start - 30):start]
    if _NEG_POLITICA.search(ventana):
        return True
    return bool(re.search(r"\bsin\s*$", ventana, re.IGNORECASE))


def detectar_promesas(respuesta: str) -> list[str]:
    """Devuelve las clases de promesa prohibida presentes en el texto. [] si limpio.
    Un disparo dentro de una negacion de politica ('no hacemos X') no cuenta: la
    tienda niega el servicio, no lo promete."""
    if not respuesta:
        return []
    clases = []
    for clase, rx in (("dia_entrega", _RE_DIA_ENTREGA),
                      ("retiro_local", _RE_RETIRO),
                      ("servicio_no_ofrecido", _RE_SERVICIOS),
                      ("datos_pago", _RE_DATOS_PAGO),
                      ("descuento_inventado", _RE_DESCUENTO_INVENTADO),
                      ("envio_exterior", _RE_ENVIO_EXTERIOR),
                      ("promo_inventada", _RE_PROMO_INVENTADA)):
        for m in rx.finditer(respuesta):
            if _negado(respuesta, m.start()):
                continue
            # El descuento con fuente real cerca (transferencia, mayorista)
            # no es invento: no dispara.
            if clase == "descuento_inventado" and _PERMITE_DESCUENTO.search(
                    respuesta[max(0, m.start() - 80):m.end() + 80]):
                continue
            clases.append(clase)
            break
    return clases


# ── ANUNCIO SIN CONTENIDO ────────────────────────────────────────────────────
# Vivia en `guardas_salida` como RADAR: no podaba, solo marcaba. Con el hub de
# herramientas la mide el banco, que es donde se mide.
_RE_ANUNCIA = re.compile(
    r"te\s+(?:cuento|explico|detallo)|te\s+l[oa]\s+confirmo"
    r"|la\s+disponibilidad\s+te\s+la\s+confirmo|como\s+viene\s+la\s+mano",
    re.IGNORECASE)
_RE_ENTREGA = (
    re.compile(r"\$\s?\d"),                       # una cifra de plata
    re.compile(r"(?m)^\s*-\s+\S"),                # una lista de opciones
    re.compile(r"(?i)\bno\b[^.\n]{0,60}(vend|trabaj|tenemos|tengo|contamos"
               r"|cat[aá]logo|confirmar|especifica|figura|llegamos)"),  # no honesto
    re.compile(r"(?i)(cu[aá]l|qu[eé] uso|d[oó]nde|provincia|c[oó]digo postal"
               r"|localidad)[^?]*\?"),            # pregunta que pide el dato
)
# NOTA de un error propio, para que no se repita: al mover la regla la ensanche
# -"que uso" pasaba a "que <lo que sea>"- pensando que asi cubria mas casos. Lo
# que hizo fue lo contrario: "¿Querés QUE AVANCEMOS con alguno?" pasaba a contar
# como pregunta de dato y el detector se quedaba mudo justo en el turno hueco
# que lo estrenó. Una regla que se mueve se mueve IGUAL; si hay que ampliarla,
# se amplia despues y con un caso que lo justifique.


def anuncio_sin_contenido(respuesta: str, tope: int = 340) -> bool:
    """True si la respuesta promete contar algo y no lo cuenta. Conservador:
    solo respuestas CORTAS, porque la prosa larga de criterio es contenido
    aunque no traiga cifras."""
    r = (respuesta or "").strip()
    if len(r) >= tope or not _RE_ANUNCIA.search(r):
        return False
    return not any(rx.search(r) for rx in _RE_ENTREGA)
