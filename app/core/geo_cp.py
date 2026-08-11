"""
GEO_CP — resolutor determinista de PROVINCIA y CODIGO POSTAL desde el texto del
cliente, con la tabla completa de localidades de Argentina.

Fuente: data/geo/codigos_postales_ar.csv (Correo Argentino, ~16 mil localidades,
provincia + localidad + CP). Es dato de referencia estatico: vive en el repo y se
carga en memoria una vez, igual que el catalogo. NO va a Firestore (es igual para
todas las tiendas) y no cambia entre sesiones.

Para que sirve: cuando el cliente da PROVINCIA + LOCALIDAD (el flujo que pide el
bot), este modulo devuelve la provincia canonica y un CP representativo. Con eso
envio.py clasifica la zona (caba/gba/interior) y cotiza la tarifa EXACTA de la
provincia. Reemplaza las listas parciales hechas a mano por la tabla completa.

Precision sobre cobertura: 2 mil localidades existen en mas de una provincia
('25 de mayo', 'san martin'); esas SOLO se resuelven si la provincia esta en el
texto. Sin provincia, unicamente se resuelve una localidad INEQUIVOCA (una sola
provincia) y con guarda contra la altura de calle, asi 'calle san martin 1234' no
se toma como el pueblo San Martin.
"""
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

_MAX_NGRAM = 5  # localidades de hasta 5 palabras (San Miguel de Tucuman, etc.)

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
    _CARGADO = True
    log.info("geo_cp_cargado", localidades=len(_LOC))


def _provincia_en_texto(t: str):
    """slug de la provincia nombrada en el texto, o None. Frase mas larga gana."""
    for frase in sorted(_PROV_ALIASES, key=len, reverse=True):
        if re.search(r"(^| )" + re.escape(frase) + r"( |$)", t):
            return _PROV_ALIASES[frase]
    return None


def _localidades_en_texto(t: str):
    """Segmenta el texto por 'maximal munch': recorre de izquierda a derecha y en
    cada posicion toma el nombre de localidad MAS LARGO que matchea, y salta esas
    palabras. Asi 'villa maria' se toma entero: si esa localidad es ambigua, NO
    se degrada a 'maria' (una localidad distinta) y no se inventa una provincia.
    Devuelve (palabras, [(localidad_norm, inicio, fin_palabra)])."""
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
    """CP de la unica localidad de `prov` cuyo nombre EMPIEZA con lo que
    escribio el cliente, o None si no hay exactamente una.

    Es el nombre de uso comun contra el nombre oficial: 'san nicolas' contra
    'san nicolas de los arroyos'. Se prueban los fragmentos del mensaje de mas
    largo a mas corto —asi 'san nicolas' le gana a 'san'— y se exige:
      - al menos DOS palabras, porque con una sola el prefijo caza cualquier
        cosa ('san' abre docenas de localidades);
      - que el prefijo termine en palabra completa, para no cortar al medio;
      - UN solo candidato en esa provincia. Con dos o mas no se elige: ahi
        preguntar es lo correcto.
    """
    # EL NOMBRE DE LA PROVINCIA SALE DEL TEXTO ANTES DE BUSCAR, y esto no es
    # cosmetico: sin sacarlo, "villa, Buenos Aires" -que nombra la provincia y
    # ninguna localidad- encontraba una localidad que EMPIEZA con "buenos
    # aires" y le estampaba su CP. O sea, le inventaba el destino al cliente,
    # que es lo unico que este sistema no puede hacer. Se vio en la prueba del
    # arreglo, antes de que saliera.
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
    """True si el texto nombra una localidad de la tabla o una provincia.
    Puerta para los candidatos a destino que salen por regex del mensaje
    libre: 'la otra direccion' o 'tres destinos' NO son lugares (charla real
    19-jul: cotizaron igual porque la provincia sticky los completaba)."""
    _cargar()
    t = _norm(texto)
    if not t:
        return False
    if _provincia_en_texto(t):
        return True
    return bool(_localidades_en_texto(t)[1])


def resolver(texto: str):
    """(prov_slug, cp) desde el texto del cliente, o (None, None).

    Con PROVINCIA en el texto: elige la localidad que pertenezca a esa provincia
    y devuelve su CP (desambigua las localidades repetidas). Con la provincia sola
    tambien devuelve (prov, None): alcanza para la tarifa de la provincia.

    SIN provincia: solo resuelve una localidad INEQUIVOCA (una sola provincia) y
    que no sea una altura de calle (no la sigue un numero). Asi no inventa."""
    _cargar()
    t = _norm(texto)
    if not t:
        return None, None
    prov = _provincia_en_texto(t)
    palabras, hits = _localidades_en_texto(t)

    if prov:
        for loc, ini, fin in hits:
            if prov in _LOC[loc]:
                return prov, _LOC[loc][prov]
        # EL NOMBRE CORTO, que es como habla el cliente (11-ago-2026).
        #
        # EL CASO REAL, de la charla de Martin: pidio un envio a "San Nicolás,
        # Buenos Aires" y el turno entero se cayo —no cotizo, no armo el
        # presupuesto, y le pidio el CODIGO POSTAL de una ciudad que esta en la
        # tabla—. La causa: en las 16.164 localidades la de Buenos Aires figura
        # con su nombre oficial, "san nicolas de los arroyos", y "san nicolas"
        # a secas existe pero en OTRAS SIETE provincias, ninguna Buenos Aires.
        #
        # POR QUE SOLO SE VE EN BUENOS AIRES. En el resto del pais la provincia
        # sola ya alcanza para la tarifa y el fallback de abajo salva el turno.
        # Buenos Aires es la unica donde la tarifa depende de la zona —CABA y
        # GBA contra interior— asi que sin localidad no se puede cotizar. Es la
        # provincia mas poblada: el error pega justo donde mas duele.
        #
        # LO QUE LO HACE SEGURO: se acepta solo si el prefijo resuelve a UNA
        # sola localidad de esa provincia. Con dos o mas no se elige ninguna y
        # el turno pregunta, que es cuando preguntar esta bien. Medido con un
        # barrido sobre la tabla entera: los nombres cortos ambiguos se
        # descartan solos y "san nicolas"/"san martin" en Buenos Aires dan un
        # unico candidato.
        cp = _por_prefijo(t, prov)
        if cp is not None:
            return prov, cp
        # Provincia nombrada pero sin localidad de esa provincia: la provincia
        # sola ya sirve para la tarifa.
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
