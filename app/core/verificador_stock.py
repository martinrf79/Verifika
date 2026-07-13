"""
VERIFICADOR DE STOCK — el MISMO patron del verificador de plata, aplicado al campo
disponibilidad. Es el campo por donde se filtro la alucinacion real del 2-jul: el
solver invento faltantes ("DX-110 no tiene stock", falso) y upselleo a lo caro.

Invariante (uno, no casos): toda afirmacion de disponibilidad de la respuesta,
anclada a UN producto nombrado, tiene que coincidir con el stock del catalogo.

Dos piezas, ambas deterministas en la deteccion:
  1. CIFRA de unidades ("quedan 9", "3 en stock"): si contradice el catalogo y el
     ancla es unica, se reescribe SOLO la cifra (safe-override, edicion minima).
  2. CONTRADICCION de texto ("no tiene stock" de un producto que SI tiene;
     "disponible" de uno agotado): no se puede corregir con un numero, se marca la
     clase y el llamador reescribe con la MISMA maquinaria de guardia_promesas
     (una llamada LLM solo en los turnos que disparan).

Conservador como la plata: el ancla debe ser UN unico producto nombrado en la
ventana previa; ante ambiguedad, frase condicional o stock desconocido, no toca.
Solo juzga productos cuyo stock REAL esta en la evidencia DE ESTE turno (el stock
cambia; un dato viejo no acusa a nadie).
"""
import re

from app.core.verificador import _tokens_significativos
from app.logger import get_logger

log = get_logger(__name__)

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


def cuarentena_stock(texto: str, evidencia: list[dict]) -> str:
    """Red DETERMINISTA para cuando la reescritura LLM falla o deja la
    contradiccion (mismo patron que guardia_promesas.cuarentena_prohibidas,
    visto en el banco: la reescritura dejo 'el Blanco esta disponible' con
    stock CERO y salio al cliente): poda las LINEAS del mensaje donde la
    deteccion de stock contradicho dispara. La linea entera, porque el detalle
    que acompana la afirmacion falsa es parte de la misma invencion. Puede
    devolver '' si todo el mensaje era la mentira; el llamador decide el
    fallback final."""
    lineas = (texto or "").split("\n")
    limpias = [l for l in lineas
               if not detectar_stock_contradicho(l, evidencia)]
    return "\n".join(limpias).strip()


def instruccion_stock(contradicciones: list[dict]) -> str:
    """Regla de reescritura para la maquinaria de guardia_promesas, con el dato
    REAL del catalogo adentro, asi la reescritura no inventa."""
    partes = []
    for c in contradicciones:
        if c["clase"] == "sin_stock_falso":
            partes.append(
                f"el producto {c['nombre']} SI tiene stock ({c['stock']} "
                f"unidades): no digas que no hay stock, ofrecelo con su "
                f"disponibilidad real")
        else:
            partes.append(
                f"el producto {c['nombre']} esta SIN stock: no lo ofrezcas "
                f"como disponible, ofrece una alternativa del catalogo")
    return "; ".join(partes)
