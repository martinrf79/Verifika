"""
RECALL DE MODELOS — etapa 1 del interprete: que modelos del catalogo PUEDEN ser
lo que nombro el cliente.

POR QUE ESTO MANDA. El enum de `producto_resuelto` no lleva los 482 modelos: el
limite documentado de structured outputs es 15.000 caracteres en TODO el schema
y los 482 solos son 11.000. Lleva los que esta funcion recupera. O sea que lo
que NO entra aca, el interprete no lo puede nombrar aunque lo haya entendido
perfecto: devuelve null o fuera_de_lista, el universo se queda sin el producto y
el bot termina diciendo que no lo tenemos teniendolo en stock. Es el cuello de
botella real de la interpretacion, y por eso el recall se mide (banco_pruebas/
banco_recall_modelos.py), no se opina.

QUE CAMBIA RESPECTO DEL RECALL VIEJO. El viejo comparaba las palabras del
mensaje contra la etiqueta "Marca Modelo" y nada mas. El catalogo tiene, por
producto, veinte columnas: nombre completo, `tags` con los sinonimos que cargo
la tienda ("mause", "raton", "puntero"), uso recomendado, material, color y
descripcion rica. Nada de eso se miraba. El cliente decia "el teclado mecanico
rgb que me mostraste" y como la etiqueta es "Redragon Kumara K552" no enganchaba
una sola palabra. Ahora cada modelo es un documento con los tokens de TODAS sus
variantes.

COMO PUNTUA, y por que no alcanza con contar palabras en comun. Cuatro
correcciones sobre el conteo crudo, cada una medida con el banco:

1. CAPAS DE PESO. Identidad (marca, modelo) pesa 3; nombre y tags pesan 2; el
   resto de la ficha pesa 1. Que el cliente acierte la marca vale mas que que
   acierte el material.
2. DESCUENTO POR FRECUENCIA (idf). Un token que aparece en casi todos los
   modelos no distingue nada: "usb" esta en cuatrocientos y vale casi cero;
   "g203" esta en uno y vale mucho. Sin este descuento, mirar la descripcion es
   PEOR que no mirarla: una palabra generica engancha trescientos modelos, la
   lista se llena de ruido y empuja afuera al producto correcto.
3. CORRECCION POR LARGO. Un modelo con descripcion larga junta muchos tokens
   flojos y le gana a uno que pego justo con dos palabras precisas.
4. CORTE RELATIVO al mejor puntaje. Lo que puntua muy por debajo del primero no
   es candidato, es relleno.

TIPOS. El pase por parecido ('zenbok' -> 'zenbook') corrige el TOKEN del
mensaje, no suma modelos al final: asi el corregido puntua por lo que vale y
sale arriba, en vez de entrar a la lista y quedar escondido en el fondo.

MEDIDO sobre el catalogo real de 880, 1552 casos (banco_recall_modelos.py):
recall@30 87,4% -> 100%, recall@5 71,2% -> 87,6%, y la lista de candidatos baja
de 23 a 11 modelos. El caso "el cliente describe sin nombrar" pasa de 19,4% a
100%. Costo: 3,3 ms por llamada mas 90 ms de indice una vez cada cinco minutos.

Determinista y offline: sin LLM, sin embeddings, sin red. Corre sobre el
catalogo ya cacheado.
"""
import math
import re
import time
import unicodedata
from difflib import get_close_matches

from app.logger import get_logger

log = get_logger(__name__)

# TOKENIZADOR PROPIO, y por que no se reusa el de pedido_helpers.
# `_tokens_producto` descarta una lista fija de palabras "genericas" -teclado,
# mouse, gaming, pro, plus, los colores- para que el CERTIFICADOR no confunda
# dos modelos por una palabra que comparten. Para el certificador eso esta bien;
# para el RECALL es un agujero, por dos motivos medidos con el banco:
#   - "G Pro X" y "Zenbook Pro" tienen esas palabras en el nombre REAL. Al
#     cliente que escribe "el g pro x negro" se le borraba el mensaje entero y
#     el recall devolvia cualquier cosa.
#   - la lista es una adivinanza fija: no sabe que en ESTA tienda "optico"
#     distingue y "usb" no.
# El idf hace ese trabajo mejor y con el dato: una palabra que esta en medio
# catalogo termina valiendo casi cero sola, pero SIGUE sumando cuando acompana
# a una que si distingue. Aca solo se sacan las palabras de funcion del
# castellano, que no son dato de ningun producto.
_VACIAS = {
    "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas", "y",
    "o", "u", "a", "al", "en", "con", "sin", "por", "para", "que", "cual",
    "cuales", "es", "son", "me", "te", "se", "lo", "le", "mi", "tu", "su",
    "este", "esta", "ese", "esa", "esos", "esas", "aquel", "algun", "alguna",
    "algo", "hay", "tenes", "tenes?", "tienen", "tiene", "quiero", "queria",
    "busco", "buscaba", "necesito", "dame", "decime", "cuanto", "cuanta",
    "cuantos", "sale", "vale", "cuesta", "mas", "muy", "pero", "tambien",
    "si", "no", "ok", "dale", "gracias", "hola", "buenas",
}

_SEPARADORES = re.compile(r"[^0-9a-z]+")


def tokens(s) -> set:
    """Tokens de un texto para el recall. Conserva letras sueltas y numeros:
    'G Pro X' y 'IdeaPad 3' se distinguen justo por eso."""
    txt = unicodedata.normalize("NFKD", str(s or "").lower())
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return {t for t in _SEPARADORES.split(txt) if t and t not in _VACIAS}

# Las tres capas de la ficha. Un campo que no exista en la tienda simplemente no
# aporta tokens: sumar una columna al CSV la hace buscable sin tocar este codigo.
_CAPAS = (
    (("marca", "modelo"), 3.0),
    (("nombre", "tags"), 2.0),
    (("categoria", "uso_recomendado", "caracteristicas_extra", "material",
      "color", "descripcion_rica", "descripcion"), 1.0),
)

# Mismo TTL que el cache del catalogo (firestore_client._CACHE_TTL_SECONDS): el
# indice se reconstruye cuando el catalogo se pudo haber movido abajo.
_TTL_S = 300
_CACHE: dict[str, dict] = {}
_CACHE_TS: dict[str, float] = {}

# Piso de largo para buscar un typo: con menos de 4 letras el parecido trae
# cualquier cosa. Mismo criterio que tenia el recall viejo.
_LARGO_TYPO = 4
_CUTOFF_TYPO = 0.8
# Cuanto vale una palabra CORREGIDA respecto de una que el cliente escribio
# bien. Menos de 1 para que, ante empate, gane el que pego exacto.
_PENA_TYPO = 0.7

# CORTE RELATIVO al mejor puntaje. Lo que puntua menos de esto comparado con el
# primero no es un candidato, es relleno: engorda el enum, gasta tokens y le da
# al interprete un lugar mas donde equivocarse.
# El valor sale del banco, no del gusto: sobre los 1552 casos del catalogo real,
# de 0 a 0,45 el recall@30 se queda clavado en 100% y la lista baja de 23 a 10;
# recien en 0,50 empieza a perder casos. Se toma 0,40, que corta a la mitad con
# dos escalones de margen antes de la primera perdida.
_CORTE_RELATIVO = 0.40


def etiqueta_modelo(p: dict) -> str:
    """La etiqueta 'Marca Modelo' de un producto. MISMA forma que arma
    `interpretador.modelos_del_catalogo`, para que el indice y el vocabulario
    del enum hablen del mismo objeto."""
    if not isinstance(p, dict):
        return ""
    marca = str(p.get("marca") or "").strip()
    modelo = str(p.get("modelo") or "").strip()
    return f"{marca} {modelo}".strip()


def _construir(productos: list) -> dict:
    """{etiqueta_en_minuscula: {token: peso}} con el peso YA descontado por idf.

    Un modelo con nueve variantes (colores, CPU) es UN documento: lo que dice
    cualquiera de sus variantes sirve para encontrarlo.
    """
    docs: dict[str, dict] = {}
    for p in (productos or []):
        et = etiqueta_modelo(p).lower()
        if not et:
            continue
        d = docs.setdefault(et, {})
        for campos, peso in _CAPAS:
            for campo in campos:
                for t in tokens(p.get(campo)):
                    # el token se queda con su MEJOR capa: si "logitech" esta en
                    # marca y ademas en la descripcion, vale como identidad.
                    if d.get(t, 0.0) < peso:
                        d[t] = peso
    n = len(docs)
    if not n:
        return {}
    df: dict[str, int] = {}
    for d in docs.values():
        for t in d:
            df[t] = df.get(t, 0) + 1
    # LARGO PROMEDIO del documento, para la correccion de abajo.
    largo_prom = sum(len(d) for d in docs.values()) / n
    for d in docs.values():
        # 1) idf suavizado: log((N+1)/df). Con df=N da casi cero (no distingue)
        #    y nunca exactamente cero, asi un catalogo chico no queda sin
        #    puntajes.
        # 2) CORRECCION POR LARGO. Un modelo con descripcion larga junta muchos
        #    tokens flojos y le gana a uno que pego justo con dos palabras
        #    precisas. Es el sesgo clasico de la busqueda por palabras y lo
        #    medimos: sin esta correccion el caso "el cliente describe sin
        #    nombrar" traia el correcto en la lista pero enterrado. Se divide
        #    por cuanto mas largo es el documento que el promedio, atenuado
        #    (mismo criterio que el b=0.75 de BM25: corrige, no aplasta).
        factor = 0.25 + 0.75 * (len(d) / largo_prom) if largo_prom else 1.0
        for t, peso in d.items():
            d[t] = peso * math.log((n + 1) / df[t]) / factor
    return docs


def indice(tienda_id: str | None = None) -> dict:
    """El indice de la tienda, cacheado. {} si no hay catalogo a mano (tests
    puros, sin doble de Firestore): el llamador cae al recall por etiqueta."""
    tid = tienda_id or ""
    ahora = time.time()
    if tid in _CACHE and (ahora - _CACHE_TS.get(tid, 0.0)) < _TTL_S:
        return _CACHE[tid]
    try:
        from app.storage.firestore_client import get_all_products
        productos = get_all_products(tienda_id=tienda_id) or []
    except Exception as e:
        log.warning("recall_indice_error", error=str(e)[:150])
        return {}
    t0 = time.time()
    idx = _construir(productos)
    _CACHE[tid] = idx
    _CACHE_TS[tid] = ahora
    log.info("recall_indice_construido", tienda_id=tid, modelos=len(idx),
             productos=len(productos), ms=int((time.time() - t0) * 1000))
    return idx


def invalidar(tienda_id: str | None = None) -> None:
    """Tira el indice. Para el banco y para despues de recargar el catalogo."""
    if tienda_id is None:
        _CACHE.clear()
        _CACHE_TS.clear()
        return
    _CACHE.pop(tienda_id, None)
    _CACHE_TS.pop(tienda_id, None)


def _recall_etiqueta(toks: set, modelos: list, tope: int) -> dict:
    """Recall SOLO por la etiqueta 'Marca Modelo'. Es el camino de respaldo
    cuando no hay catalogo abajo (tests puros). Era el recall completo hasta
    hoy: se conserva como piso, nunca como camino principal."""
    puntajes: dict[str, float] = {}
    for m in modelos:
        comunes = toks & tokens(m)
        if comunes:
            puntajes[m] = float(len(comunes))
    if len(puntajes) < tope:
        vocab = {t for m in modelos for t in tokens(m)}
        for m in _por_typo(toks, vocab, modelos, tokens):
            puntajes.setdefault(m, 0.5)
    return puntajes


def _por_typo(toks: set, vocab: set, modelos: list, tokens_de) -> list:
    """Modelos que enganchan por PARECIDO cuando ninguna palabra pego exacto.
    'zenbok' -> 'zenbook'. Devuelve etiquetas, sin puntaje. Solo lo usa el
    camino de respaldo sin indice; con indice se corrige el TOKEN (ver
    `_expandir_typos`), que es lo que deja al corregido bien rankeado."""
    salida = []
    for t in toks:
        if t in vocab or len(t) < _LARGO_TYPO:
            continue
        for parecida in get_close_matches(t, vocab, n=2, cutoff=_CUTOFF_TYPO):
            for m in modelos:
                if parecida in tokens_de(m):
                    salida.append(m)
    return salida


def _expandir_typos(toks: set, vocab: set) -> dict:
    """{token: cuanto vale} para puntuar. El token que existe en el catalogo
    vale 1. El que no existe se corrige por parecido y su correccion vale
    _PENA_TYPO.

    Por que asi y no sumando modelos al final con un puntaje fijo, que era lo
    que habia: con puntaje fijo el modelo corregido entraba a la lista pero al
    FONDO, detras de treinta que habian pegado por una palabra floja. O sea que
    'la zenbok 14' lo encontraba y a la vez lo escondia. Corrigiendo el token,
    el corregido puntua por lo que vale de verdad -marca, idf- y sale arriba.
    """
    pesos = {t: 1.0 for t in toks}
    for t in toks:
        if t in vocab or len(t) < _LARGO_TYPO:
            continue
        for parecida in get_close_matches(t, vocab, n=2, cutoff=_CUTOFF_TYPO):
            if pesos.get(parecida, 0.0) < _PENA_TYPO:
                pesos[parecida] = _PENA_TYPO
    return pesos


def candidatos(mensaje: str, modelos: list | None, contexto: str = "",
               tope: int = 30, tienda_id: str | None = None) -> list:
    """Los modelos del catalogo que rozan lo que dijo el cliente, mejor primero.

    `modelos` es el vocabulario AUTORIZADO (lo que devuelve
    `modelos_del_catalogo`): nada que no este ahi puede salir de aca, porque es
    lo que va al enum del schema. El indice solo decide el ORDEN y el corte.

    Mira mensaje Y contexto de la charla: la repregunta no repite el nombre
    ("y esa cuanto pesa?").
    """
    todos = [m for m in (modelos or []) if m]
    if not todos:
        return []
    toks = tokens(mensaje) | tokens(contexto)
    if not toks:
        return []

    idx = indice(tienda_id)
    if not idx:
        puntajes = _recall_etiqueta(toks, todos, tope)
        return [m for m, _ in sorted(puntajes.items(), key=lambda x: -x[1])][:tope]

    vocab = {t for pesos in idx.values() for t in pesos}
    consulta = _expandir_typos(toks, vocab)

    puntajes: dict[str, float] = {}
    for m in todos:
        pesos = idx.get(m.lower())
        if not pesos:
            # etiqueta sin ficha en el indice: no la perdemos, cae al piso viejo
            comunes = toks & tokens(m)
            if comunes:
                puntajes[m] = float(len(comunes))
            continue
        s = 0.0
        for t, vale in consulta.items():
            s += pesos.get(t, 0.0) * vale
        if s > 0:
            puntajes[m] = s

    if not puntajes:
        return []
    piso = max(puntajes.values()) * _CORTE_RELATIVO
    return [m for m, s in sorted(puntajes.items(), key=lambda x: (-x[1], x[0]))
            if s >= piso][:tope]
