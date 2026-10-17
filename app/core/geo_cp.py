"""GEO_CP — resolutor determinista de PROVINCIA y CODIGO POSTAL desde el texto del cliente, con la tabla completa
de localidades de Argentina."""
import csv
import re
import unicodedata
from pathlib import Path

from app.logger import get_logger

log = get_logger(__name__)

_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "geo" / "codigos_postales_ar.csv"

# Provincia del CSV -> slug canonico (el mismo que usan las tarifas por provincia
# en config.py y el clasificador de envio.py). CABA es zona propia, no 'interior'.
_PROV_CSV_A_SLUG = {
    "ciudad autonoma de buenos aires": "caba",
    "buenos aires": "buenos_aires",
    "cordoba": "cordoba", "santa fe": "santa fe", "entre rios": "entre rios",
    "corrientes": "corrientes", "misiones": "misiones", "chaco": "chaco",
    "formosa": "formosa", "santiago del estero": "santiago del estero",
    "tucuman": "tucuman", "salta": "salta", "jujuy": "jujuy",
    "catamarca": "catamarca", "la rioja": "la rioja", "san juan": "san juan",
    "san luis": "san luis", "mendoza": "mendoza", "la pampa": "la pampa",
    "neuquen": "neuquen", "rio negro": "rio negro", "chubut": "chubut",
    "santa cruz": "santa cruz", "tierra del fuego": "tierra del fuego",
}

# Alias de provincia en el texto del cliente -> slug. Frases mas largas primero.
_PROV_ALIASES = {
    "ciudad autonoma de buenos aires": "caba", "ciudad de buenos aires": "caba",
    "capital federal": "caba", "capfed": "caba", "caba": "caba",
    "provincia de buenos aires": "buenos_aires", "pcia de buenos aires": "buenos_aires",
    "buenos aires": "buenos_aires", "bs as": "buenos_aires", "gba": "buenos_aires",
}
for _s in _PROV_CSV_A_SLUG.values():
    if _s not in ("caba", "buenos_aires"):
        _PROV_ALIASES[_s] = _s

# EL TOPE SALE DE LA TABLA, NO DE UNA CONSTANTE (12-ago-2026, barrido completo).
_MAX_NGRAM = 5  # piso; `_cargar` lo sube a lo que diga la tabla

_LOC: dict = {}          # loc_norm -> {prov_slug: cp_int}
_CARGADO = False


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _cargar():
    global _CARGADO
    if _CARGADO:
        return
    try:
        with open(_CSV, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                prov_slug = _PROV_CSV_A_SLUG.get(_norm(r.get("provincia", "")))
                loc = _norm(r.get("localidad", ""))
                cp = (r.get("cp") or "").strip()
                if not prov_slug or not loc:
                    continue
                d = _LOC.setdefault(loc, {})
                # Primer CP no vacio por provincia: representativo, alcanza para la
                # zona (el split GBA/interior de Buenos Aires) y para el disclaimer.
                if prov_slug not in d and cp.isdigit():
                    d[prov_slug] = int(cp)
                elif prov_slug not in d:
                    d[prov_slug] = None
    except Exception as e:
        log.warning("geo_cp_carga_error", error=str(e)[:150])
    global _MAX_NGRAM
    if _LOC:
        _MAX_NGRAM = max(_MAX_NGRAM, max(len(l.split()) for l in _LOC))
    _CARGADO = True
    log.info("geo_cp_cargado", localidades=len(_LOC), max_ngram=_MAX_NGRAM)


def _provincia_en_texto(t: str, hits=None):
    """slug de la provincia nombrada en el texto, o None."""
    if hits is None:
        _, hits = _localidades_en_texto(t)
    palabras = t.split()
    for frase in sorted(_PROV_ALIASES, key=len, reverse=True):
        partes = frase.split()
        n = len(partes)
        for i in range(len(palabras) - n + 1):
            if palabras[i:i + n] != partes:
                continue
            # ¿esta ocurrencia vive adentro de una localidad mas larga?
            tapada = any(ini <= i and i + n <= fin and (fin - ini) > n
                         for _loc, ini, fin in hits)
            if not tapada:
                return _PROV_ALIASES[frase]
    return None


def _localidades_en_texto(t: str):
    """Segmenta el texto por 'maximal munch': recorre de izquierda a derecha y en cada posicion toma el nombre de
    localidad MAS LARGO que matchea, y salta esas palabras."""
    palabras = t.split()
    hits = []
    i = 0
    while i < len(palabras):
        encontrado = None
        for n in range(min(_MAX_NGRAM, len(palabras) - i), 0, -1):
            frag = " ".join(palabras[i:i + n])
            if frag in _LOC:
                encontrado = (frag, i, i + n)
                break
        if encontrado:
            hits.append(encontrado)
            i = encontrado[2]
        else:
            i += 1
    hits.sort(key=lambda h: -(h[2] - h[1]))  # el match mas largo primero
    return palabras, hits


def _por_prefijo(t: str, prov: str):
    """CP de la unica localidad de `prov` cuyo nombre EMPIEZA con lo que escribio el cliente, o None si no hay
    exactamente una."""
    # EL NOMBRE DE LA PROVINCIA SALE DEL TEXTO ANTES DE BUSCAR, y esto no es cosmetico: sin sacarlo, "villa,
    # Buenos Aires" -que nombra la provincia y ninguna localidad- encontraba una localidad que EMPIEZA con
    # "buenos aires" y le estampaba su CP.
    limpio = t
    for frase in sorted(_PROV_ALIASES, key=len, reverse=True):
        limpio = re.sub(r"(^| )" + re.escape(frase) + r"( |$)", " ", limpio)
    palabras = [p for p in limpio.replace(",", " ").split() if p]
    if len(palabras) < 2:
        return None
    for n in range(min(_MAX_NGRAM, len(palabras)), 1, -1):
        for i in range(0, len(palabras) - n + 1):
            frag = " ".join(palabras[i:i + n])
            if frag in _LOC and prov in _LOC[frag]:
                return _LOC[frag][prov]
            candidatos = [v[prov] for k, v in _LOC.items()
                          if prov in v and k.startswith(frag + " ")]
            if len(set(candidatos)) == 1:
                return candidatos[0]
    return None


def es_lugar_conocido(texto: str) -> bool:
    """True si el texto nombra una localidad de la tabla o una provincia."""
    _cargar()
    t = _norm(texto)
    if not t:
        return False
    if _provincia_en_texto(t):
        return True
    return bool(_localidades_en_texto(t)[1])


# `lugares_en_texto` SE BORRO EL 13-sep-2026, y no porque estuviera mal: partia "uno a Cordoba capital y otro
# a Posadas" en dos lugares contra la tabla, sin perseguir prosa, y ese multidestino sigue andando.


def resolver(texto: str):
    """(prov_slug, cp) desde el texto del cliente, o (None, None)."""
    _cargar()
    t = _norm(texto)
    if not t:
        return None, None
    # La segmentacion en localidades va PRIMERO: es la que le dice al detector de
    # provincia si 'corrientes' es la provincia o la segunda mitad de un pueblo.
    palabras, hits = _localidades_en_texto(t)
    prov = _provincia_en_texto(t, hits)

    if prov:
        for loc, ini, fin in hits:
            if prov in _LOC[loc]:
                return prov, _LOC[loc][prov]
        # EL NOMBRE CORTO, que es como habla el cliente (11-ago-2026).
        cp = _por_prefijo(t, prov)
        if cp is not None:
            return prov, cp
        # Provincia nombrada pero sin localidad de esa provincia: la provincia sola ya sirve para la tarifa.
        return prov, None

    # Sin provincia: solo una localidad inequivoca y no pegada a una altura.
    for loc, ini, fin in hits:
        provs = _LOC[loc]
        if len(provs) != 1:
            continue  # ambigua entre provincias: hace falta la provincia
        # Guarda de calle: si al fragmento le sigue un numero, es una direccion
        # ('san martin 1234'), no la localidad. Se descarta.
        if fin < len(palabras) and re.fullmatch(r"\d{1,5}", palabras[fin]):
            continue
        (unico_slug, cp), = provs.items()
        return unico_slug, cp
    return None, None
