"""ENVIO POR ZONA — motor determinista de envio (codigo generico + datos de tienda)."""
import re
import unicodedata
from typing import Optional

from app.logger import get_logger

log = get_logger(__name__)


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or "")) \
        .encode("ascii", "ignore").decode().lower()
    # La puntuacion pegada rompe el match por palabra completa ("rosario," no matchea "rosario"): se vuelve
    # espacio.
    t = re.sub(r"[,;()!?¡¿]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ── CPA: primera letra -> provincia. Norma ISO 3166-2:AR (oficial, verificado). ──
_LETRA_PROVINCIA = {
    "a": "salta", "b": "buenos_aires", "c": "caba", "d": "san luis",
    "e": "entre rios", "f": "la rioja", "g": "santiago del estero",
    "h": "chaco", "j": "san juan", "k": "catamarca", "l": "la pampa",
    "m": "mendoza", "n": "misiones", "p": "formosa", "q": "neuquen",
    "r": "rio negro", "s": "santa fe", "t": "tucuman", "u": "chubut",
    "v": "tierra del fuego", "w": "corrientes", "x": "cordoba",
    "y": "jujuy", "z": "santa cruz",
}

# CPA completo: letra + 4 digitos + 3 letras (ej C1425ABC, X5000XXX).
_CPA_RE = re.compile(r"\b([a-z])(\d{4})[a-z]{3}\b", re.IGNORECASE)
# CP de 4 digitos SOLO si viene con marcador (cp, codigo postal, c.p.).
_CP_MARCADO_RE = re.compile(
    r"\b(?:cp|c\.p\.|codigo postal|cod postal|cod\. postal)\s*[:n°]?\s*(\d{4})\b",
    re.IGNORECASE)
# CPA corto (letra + 4 digitos, ej C1425) SOLO con marcador.
_CPA_CORTO_MARCADO_RE = re.compile(
    r"\b(?:cp|c\.p\.|codigo postal|cod postal|cod\. postal)\s*[:n°]?\s*"
    r"([a-z])\s*(\d{4})\b",
    re.IGNORECASE)
# CP PELADO: el mensaje ENTERO es un codigo postal, sin marcador.
_CP_SOLO_RE = re.compile(
    r"^(?:(?:mi|el)\s+)?(?:cp|c\.p\.|codigo postal|cod postal|cod\. postal)?"
    r"\s*(?:es\s+)?([a-z])?\s*(\d{4})\s*([a-z]{3})?$",
    re.IGNORECASE)


def _cp_solo(t: str):
    """(letra, cp4) si el texto normalizado ENTERO es un CP pelado, sino None."""
    m = _CP_SOLO_RE.match(t)
    if not m:
        return None
    letra = (m.group(1) or "").lower() or None
    return letra, int(m.group(2))


def _zona_por_4digitos(n: int) -> Optional[str]:
    """Zona por el CP de 4 digitos (sistema viejo)."""
    if 1000 <= n <= 1499:
        return "caba"
    if 1500 <= n <= 1899:
        return "gba"
    if n >= 1900:
        return "interior"
    return None  # < 1000 no es un CP valido


def _zona_por_provincia(prov: str, cp4: Optional[int]) -> Optional[str]:
    """Provincia (de la letra CPA) -> zona. CABA es caba; el resto de las provincias es interior con certeza (no
    entran en tarifa metropolitana)."""
    if prov == "caba":
        return "caba"
    if prov == "buenos_aires":
        if cp4 is not None:
            z = _zona_por_4digitos(cp4)
            # En provincia de Buenos Aires nunca es 'caba' (esa es la letra C).
            return "interior" if z == "caba" else (z or "interior")
        return None  # B sin CP: ambiguo, pedir el dato
    return "interior"


# ── Atajos por NOMBRE (cuando no hay CP). Certeros para lo nombrado. ──
_PROVINCIAS_INTERIOR = {
    "catamarca", "chaco", "chubut", "cordoba", "corrientes", "entre rios",
    "formosa", "jujuy", "la pampa", "la rioja", "mendoza", "misiones",
    "neuquen", "rio negro", "salta", "san juan", "san luis", "santa cruz",
    "santa fe", "santiago del estero", "tierra del fuego", "tucuman",
}
_CIUDADES_INTERIOR = {
    "rosario", "cordoba", "mendoza", "mar del plata", "san miguel de tucuman",
    "tucuman", "salta", "santa fe", "parana", "neuquen", "bariloche",
    "posadas", "resistencia", "corrientes", "bahia blanca", "tandil",
    "san juan", "jujuy", "san luis", "rio cuarto", "comodoro rivadavia",
    "villa carlos paz", "carlos paz", "dean funes", "rio gallegos", "ushuaia", "formosa",
    "la rioja", "catamarca", "santiago del estero", "concordia", "la plata",
    "almafuerte", "san agustin",
}
_PARTIDOS_GBA = {
    "lomas de zamora", "lanus", "avellaneda", "quilmes", "berazategui",
    "florencio varela", "almirante brown", "esteban echeverria", "ezeiza",
    "la matanza", "moron", "ituzaingo", "hurlingham", "tres de febrero",
    "general san martin", "vicente lopez", "san isidro", "san fernando",
    "tigre", "malvinas argentinas", "jose c paz", "san miguel", "moreno",
    "merlo", "marcos paz", "general rodriguez", "pilar", "escobar",
    "presidente peron", "ramos mejia", "san justo", "wilde", "bernal",
    "haedo", "castelar", "monte grande", "longchamps", "burzaco", "adrogue",
    "temperley", "banfield", "ciudadela", "caseros", "olivos", "martinez",
    "boulogne", "munro", "florida", "villa ballester", "san martin",
}
_CABA_MARKERS = {
    "caba", "capital federal", "ciudad autonoma de buenos aires",
    "ciudad de buenos aires", "capfed", "capital",
}
_BARRIOS_CABA = {
    "palermo", "belgrano", "caballito", "flores", "recoleta", "almagro",
    "villa urquiza", "villa devoto", "nunez", "saavedra", "boedo", "barracas",
    "san telmo", "constitucion", "once", "balvanera", "villa crespo",
    "colegiales", "chacarita", "liniers", "mataderos", "floresta",
    "parque patricios", "villa del parque", "monserrat", "retiro", "la boca",
    "puerto madero", "abasto", "congreso", "microcentro", "villa lugano",
}


def _zona_por_nombre(t: str) -> Optional[str]:
    def _c(frase: str) -> bool:
        return re.search(r"(^| )" + re.escape(frase) + r"( |$)", t) is not None

    def _c_calle(frase: str) -> bool:
        """Como _c, pero NO cuenta si el nombre viene seguido de un numero de calle ('san martin 1234'): eso es
        una direccion, no la localidad."""
        if not _c(frase):
            return False
        return not re.search(
            r"(^| )" + re.escape(frase) + r"\s+\d{1,5}( |$)", t)

    # Provincia o ciudad ganan PRIMERO, asi "Cordoba Capital" cae en interior y no
    # lo pisa la palabra "capital" de abajo (bug canonico del cajon equivocado).
    for p in _PROVINCIAS_INTERIOR:
        if _c(p):
            return "interior"
    for c in _CIUDADES_INTERIOR:
        if _c_calle(c):
            return "interior"
    # Ciudades de la tabla ciudad->provincia: toda ciudad ahi listada es interior (o interior bonaerense).
    for c in _CIUDAD_PROVINCIA:
        if _c_calle(c):
            return "interior"
    # Respuesta directa al colchon "Capital, Gran Buenos Aires o interior?": el cliente nombra la zona en
    # criollo y el codigo la toma tal cual.
    if _c("interior") or _c("interior del pais"):
        return "interior"
    for w in ("gran buenos aires", "gran bs as", "conurbano", "gba"):
        if _c(w):
            return "gba"
    for partido in _PARTIDOS_GBA:
        if _c_calle(partido):
            return "gba"
    for m in _CABA_MARKERS:
        if _c(m):
            return "caba"
    for b in _BARRIOS_CABA:
        if _c_calle(b):
            return "caba"
    return None


# ── Ciudad conocida -> provincia (para la tarifa por provincia). Solo ciudades
_CIUDAD_PROVINCIA = {
    "rosario": "santa fe", "santa fe": "santa fe", "rafaela": "santa fe",
    "venado tuerto": "santa fe",
    "cordoba": "cordoba", "rio cuarto": "cordoba", "villa carlos paz": "cordoba",
    "carlos paz": "cordoba", "dean funes": "cordoba", "rio tercero": "cordoba",
    "almafuerte": "cordoba", "villa maria": "cordoba", "alta gracia": "cordoba",
    "san francisco": "cordoba", "jesus maria": "cordoba",
    "despenaderos": "cordoba", "cosquin": "cordoba", "la falda": "cordoba",
    "villa general belgrano": "cordoba", "bell ville": "cordoba",
    "marcos juarez": "cordoba", "villa dolores": "cordoba",
    "mendoza": "mendoza", "san rafael": "mendoza", "godoy cruz": "mendoza",
    "mar del plata": "buenos_aires", "bahia blanca": "buenos_aires",
    "tandil": "buenos_aires", "la plata": "buenos_aires",
    "olavarria": "buenos_aires", "pergamino": "buenos_aires",
    "junin": "buenos_aires", "necochea": "buenos_aires",
    "san miguel de tucuman": "tucuman", "tucuman": "tucuman",
    "salta": "salta", "parana": "entre rios", "concordia": "entre rios",
    "gualeguaychu": "entre rios", "neuquen": "neuquen",
    "bariloche": "rio negro", "cipolletti": "rio negro",
    "general roca": "rio negro", "viedma": "rio negro",
    "posadas": "misiones", "obera": "misiones", "eldorado": "misiones",
    "resistencia": "chaco", "corrientes": "corrientes", "goya": "corrientes",
    "san juan": "san juan", "jujuy": "jujuy",
    "san salvador de jujuy": "jujuy", "san luis": "san luis",
    "villa mercedes": "san luis", "comodoro rivadavia": "chubut",
    "trelew": "chubut", "puerto madryn": "chubut", "rawson": "chubut",
    "rio gallegos": "santa cruz", "el calafate": "santa cruz",
    "ushuaia": "tierra del fuego", "rio grande": "tierra del fuego",
    "formosa": "formosa", "la rioja": "la rioja", "catamarca": "catamarca",
    "santiago del estero": "santiago del estero",
    "santa rosa": "la pampa", "general pico": "la pampa",
}


# CP de 4 digitos -> provincia, SOLO los bloques inequivocos del sistema del correo (cabecera de provincia).
_PROVINCIA_POR_CP4 = (
    (1000, 1499, "caba"),
    (3000, 3099, "santa fe"),
    (3100, 3299, "entre rios"),
    (3300, 3399, "misiones"),
    (3400, 3499, "corrientes"),
    (3500, 3599, "chaco"),
    (3600, 3699, "formosa"),
    (3700, 3799, "chaco"),
    (4000, 4199, "tucuman"),
    (4200, 4299, "santiago del estero"),
    (4400, 4599, "salta"),
    (4600, 4699, "jujuy"),
    (4700, 4799, "catamarca"),
    (5000, 5299, "cordoba"),
    (5300, 5399, "la rioja"),
    (5400, 5499, "san juan"),
    (5500, 5699, "mendoza"),
    (5700, 5799, "san luis"),
    (5800, 5999, "cordoba"),
    (9000, 9299, "chubut"),
    # Tierra del Fuego (Ushuaia 9410, Tolhuin 9412, Rio Grande 9420) esta incrustada dentro del bloque de
    # Santa Cruz: va PRIMERO porque gana el primer rango que matchea.
    (9410, 9420, "tierra del fuego"),
    (9300, 9499, "santa cruz"),
)

# Bloques EXTRA verificados, anclados en cabeceras conocidas del correo: La Plata 1900, Rosario 2000 / San
# Lorenzo 2200, Rafaela 2300 / Ceres 2340, San Francisco 2400 / Morteros 2421, Pergamino 2700 / Zarate 2800,
# Junin 6000, Tandil 7000 / Azul 7300 / Mar del Plata 7600, Bahia Blanca 8000.
_PROVINCIA_POR_CP4_EXT = (
    (1500, 1899, "buenos_aires"),
    (1900, 1999, "buenos_aires"),
    (2000, 2199, "santa fe"),
    (2300, 2399, "santa fe"),
    (2400, 2440, "cordoba"),
    (2700, 2899, "buenos_aires"),
    (6000, 6099, "buenos_aires"),
    (7000, 7999, "buenos_aires"),
    (8000, 8199, "buenos_aires"),
)


def _provincia_por_cp4(n: int) -> Optional[str]:
    for desde, hasta, prov in _PROVINCIA_POR_CP4:
        if desde <= n <= hasta:
            return prov
    for desde, hasta, prov in _PROVINCIA_POR_CP4_EXT:
        if desde <= n <= hasta:
            return prov
    return None


def clasificar_provincia(texto: str) -> Optional[str]:
    """Determina la PROVINCIA de una direccion, solo desde fuentes ciertas: 1."""
    t = _norm(texto)
    if not t:
        return None

    m = _CPA_RE.search(t) or _CPA_CORTO_MARCADO_RE.search(t)
    if m:
        prov = _LETRA_PROVINCIA.get(m.group(1).lower())
        if prov:
            return prov

    # CP pelado: el texto entero es un CP. La letra CPA manda; sin letra, el
    # numero por bloque inequivoco del correo.
    solo = _cp_solo(t)
    if solo:
        letra, cp4 = solo
        if letra and _LETRA_PROVINCIA.get(letra):
            return _LETRA_PROVINCIA[letra]
        prov = _provincia_por_cp4(cp4)
        if prov:
            return prov

    # Tabla completa de localidades (Correo Argentino): resuelve la provincia de cualquier localidad del pais,
    # no solo las de las listas a mano.
    from app.core import geo_cp
    prov_tabla, _cp = geo_cp.resolver(texto)
    if prov_tabla:
        return prov_tabla

    def _c(frase: str) -> bool:
        return re.search(r"(^| )" + re.escape(frase) + r"( |$)", t) is not None

    for p in _PROVINCIAS_INTERIOR:
        if _c(p):
            return p
    if _c("buenos aires") or _c("bs as") or _c("pcia de buenos aires"):
        return "buenos_aires"

    # Ciudades: las frases mas largas primero, asi "san salvador de jujuy" gana
    # antes que "jujuy" y "villa carlos paz" antes que "carlos paz".
    for ciudad in sorted(_CIUDAD_PROVINCIA, key=len, reverse=True):
        if _c(ciudad):
            return _CIUDAD_PROVINCIA[ciudad]

    # CP de 4 digitos con marcador (ej "cp 5121"): bloque inequivoco del correo.
    m = _CP_MARCADO_RE.search(t)
    if m:
        prov = _provincia_por_cp4(int(m.group(1)))
        if prov:
            return prov
    return None


def clasificar_zona(texto: str) -> Optional[str]:
    """Clasifica una direccion argentina en zona de envio por el CP (fuente de verdad) y, si no hay, por nombre."""
    t = _norm(texto)
    if not t:
        return None

    # 1) CPA completo: la letra es la provincia oficial.
    m = _CPA_RE.search(t)
    if m:
        letra = m.group(1).lower()
        cp4 = int(m.group(2))
        prov = _LETRA_PROVINCIA.get(letra)
        if prov:
            z = _zona_por_provincia(prov, cp4)
            if z:
                return z

    # 2a) CPA corto con marcador (ej "cp C1425"): la letra es la provincia.
    m = _CPA_CORTO_MARCADO_RE.search(t)
    if m:
        prov = _LETRA_PROVINCIA.get(m.group(1).lower())
        if prov:
            z = _zona_por_provincia(prov, int(m.group(2)))
            if z:
                return z

    # 2b) CP de 4 digitos con marcador explicito (no altura de calle).
    m = _CP_MARCADO_RE.search(t)
    if m:
        z = _zona_por_4digitos(int(m.group(1)))
        if z:
            return z

    # 2c) CP pelado: el texto entero es un CP, la respuesta natural cuando el bot lo pide.
    solo = _cp_solo(t)
    if solo:
        letra, cp4 = solo
        if letra and _LETRA_PROVINCIA.get(letra):
            z = _zona_por_provincia(_LETRA_PROVINCIA[letra], cp4)
            if z:
                return z
        z = _zona_por_4digitos(cp4)
        if z:
            return z

    # 3) Tabla completa de localidades (Correo Argentino): con provincia + localidad (o una localidad
    # inequivoca) sale la provincia y un CP representativo; con eso la zona es exacta.
    from app.core import geo_cp
    prov_tabla, cp_tabla = geo_cp.resolver(texto)
    if prov_tabla:
        z = _zona_por_provincia(prov_tabla, cp_tabla)
        if z:
            return z

    # 4) Nombre de provincia/ciudad/partido/barrio (respaldo de las listas a mano).
    z = _zona_por_nombre(t)
    if z:
        return z

    # 5) Indeterminada: el codigo no adivina.
    return None
