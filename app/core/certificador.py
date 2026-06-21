"""
CERTIFICADOR DE IDENTIDAD DEL CATALOGO — la unica fuente de verdad sobre QUE
producto existe y cual no.

Principio madre (Martin, 15-jun): IDENTIDAD != COMPATIBILIDAD.
- Identidad: "¿existe una RTX 5070 en mi catalogo?" -> respuesta OBJETIVA, codigo.
- Compatibilidad: "¿la RTX 5070 sirve para mi mother?" -> respuesta RAZONADA, LLM.

El LLM NUNCA inventa identidad. Puede razonar, comparar, recomendar, cerrar; pero
NO decide que un producto existe. Eso lo decide ESTA funcion, y nadie mas: ni el
director, ni el ancla, ni pedido_multi, ni la calculadora, ni el cierre. Una sola
autoridad de identidad mata el sistema esquizofrenico (uno encuentra, otro no,
otro encuentra distinto).

Contrato: certificar() devuelve UNO de tres veredictos de PRIMERA CLASE:
  {"status": "exists",    "product_id": "...", "item": {...}}
  {"status": "ambiguous", "candidates": [{product_id, nombre, precio_ars}, ...]}
  {"status": "not_found"}

not_found NO es un error: es un resultado VALIDO y exitoso. La consulta se
resolvio, y la respuesta es "no tengo ese producto". El que consume el veredicto
(la columna) usa eso para tirar el puente fuera_catalogo, no para ofrecer algo
parecido.

REGLA para el resto del sistema: toda herramienta comercial (ficha, calculadora,
tarifa, cierre) consume un product_id CERTIFICADO; ninguna opera sobre un producto
inferido.

Funcion determinista (solo el search del catalogo toca red), testeable con el
banco dorado scripts/prueba_certificador.py.
"""
import re
from typing import Optional

from app.core.pedido_multi import _candidatos_con_typo, _relevante, _norm
from app.core.resolver_pedido import refinar_por_atributo
from app.logger import get_logger

log = get_logger(__name__)

# Categoria que el cliente nombra -> substring de la categoria real del catalogo.
# Frases de varias palabras (placa base, placa de video) PRIMERO: son las que
# evitan el salto de rubro. "placa" pelada NO mapea (ambigua a proposito).
_CAT_SINONIMOS = [
    ("motherboard", ["placa base", "placa madre", "placa mother",
                     "motherboard", "mother", "mobo"]),
    ("placa de video", ["placa de video", "placa de vídeo", "placa grafica",
                        "tarjeta de video", "tarjeta grafica", "gpu"]),
    ("memoria", ["memoria ram", "memoria"]),
    ("procesador", ["procesador", "microprocesador"]),
    ("monitor", ["monitor"]),
    ("notebook", ["notebook", "laptop"]),
    ("teclado", ["teclado"]),
    ("mouse", ["mouse", "raton"]),
    ("auricular", ["auriculares", "auricular", "vincha"]),
    ("silla", ["silla gamer", "silla"]),
    ("impresora", ["impresora"]),
    ("microfono", ["microfono", "micrófono"]),
    ("router", ["router"]),
    ("parlante", ["parlantes", "parlante"]),
    ("tablet", ["tablet"]),
    ("webcam", ["webcam", "camara web"]),
    ("disco", ["disco ssd", "disco", "ssd"]),
]


def _categoria_pedida(term: str) -> Optional[str]:
    """La categoria que el cliente nombra explicitamente, o None. No cruzar de
    rubro: si dijo 'placa base', el resultado tiene que ser motherboard."""
    t = _norm(term)
    for cat, frases in _CAT_SINONIMOS:
        for f in frases:
            if re.search(r"\b" + re.escape(_norm(f)) + r"\b", t):
                return cat
    return None


def categorias_en(term: str) -> set:
    """TODAS las categorias del catalogo nombradas en el texto, no solo la
    primera. Sirve para detectar un pedido de varios rubros ('2 sillas, 2 mouse y
    2 teclados'): eso NO es una identidad unica y no debe certificarse como un
    solo producto. El que consume decide; aca solo se cuentan los rubros."""
    t = _norm(term)
    cats = set()
    for cat, frases in _CAT_SINONIMOS:
        for f in frases:
            # Tolerante al plural: 'sillas', 'teclados', 'mouses' tienen que contar
            # igual que el singular del sinonimo.
            if re.search(r"\b" + re.escape(_norm(f)) + r"(?:es|s)?\b", t):
                cats.add(cat)
                break
    return cats


# Cantidades al inicio del termino ('2 sillas', 'dos teclados'). Son CUENTA, no
# parte de la identidad: si no se sacan, el guardia de modelo toma el '2' como un
# numero de modelo y devuelve not_found para un rubro que existe (visto: '2 sillas'
# daba not_found y el turno caia al puente).
_NUM_PALABRAS = {"un", "una", "uno", "dos", "tres", "cuatro", "cinco", "seis",
                 "siete", "ocho", "nueve", "diez"}


def _sin_cantidad_inicial(term: str) -> str:
    """Saca los tokens de cantidad del COMIENZO del termino. Solo al inicio y
    solo si queda texto: nunca vacia el termino ni toca un modelo interno."""
    toks = term.split()
    i = 0
    while i < len(toks) and (toks[i].isdigit()
                             or _norm(toks[i]) in _NUM_PALABRAS):
        i += 1
    resto = toks[i:]
    return " ".join(resto) if resto else term


def _toks_distintivos(term: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", _norm(term))
            if any(c.isdigit() for c in t) or len(t) >= 4]


def _nombre_toks(p: dict) -> set:
    return set(re.findall(r"[a-z0-9]+", _norm(p.get("nombre", ""))))


def _cubre(tok: str, cand_toks: set) -> bool:
    """El token aparece en el nombre del candidato, tolerante a plural/prefijo
    ('parlantes'~'parlante'). Numericos solo exactos ('5'!='15')."""
    for nt in cand_toks:
        if tok == nt:
            return True
        if tok.isdigit() or nt.isdigit():
            continue
        corto, largo = (tok, nt) if len(tok) <= len(nt) else (nt, tok)
        if len(corto) >= 3 and largo.startswith(corto):
            return True
    return False


def _mejor_por_tokens(cands: list[dict], term: str) -> Optional[dict]:
    """El candidato con MAS tokens distintivos en comun, solo si es ganador
    UNICO. Si el termino trae un token de modelo (con digito), el elegido TIENE
    que contenerlo: 'Odyssey G9 49' gana a G5/G3; 'B450M Steel' no cae en una RAM
    'Steel'."""
    toks = _toks_distintivos(term)
    digit_toks = [t for t in toks if any(c.isdigit() for c in t)]
    if not toks or not cands:
        return None

    def _score(p):
        nt = _nombre_toks(p)
        return sum(1 for t in toks if t in nt)

    ordenado = sorted(cands, key=_score, reverse=True)
    mejor, mejor_s = ordenado[0], _score(ordenado[0])
    segundo_s = _score(ordenado[1]) if len(ordenado) > 1 else 0
    if digit_toks and not any(d in _nombre_toks(mejor) for d in digit_toks):
        return None
    return mejor if mejor_s > 0 and mejor_s > segundo_s else None


def _exists(item: dict) -> dict:
    return {"status": "exists", "product_id": item.get("id"), "item": item}


def _ambiguous(cands: list[dict]) -> dict:
    return {"status": "ambiguous", "candidates": [
        {"product_id": c.get("id"), "nombre": c.get("nombre"),
         "precio_ars": c.get("precio_ars")} for c in cands[:3]]}


_NOT_FOUND = {"status": "not_found"}


def certificar(termino: str, tienda_id: str, *,
               pista: Optional[str] = None,
               trace_id: Optional[str] = None) -> dict:
    """Certifica la identidad de UN producto nombrado por el cliente.

    Args:
        termino: el texto del producto como lo nombro el cliente.
        pista: nombre que el interprete (LLM) resolvio, si lo hay. Es una PISTA
            mas precisa para buscar; NO decide identidad por si sola, se valida
            igual contra el catalogo.

    Returns:
        Uno de los tres veredictos del contrato (exists / ambiguous / not_found).
    """
    termino = (termino or "").strip()
    if not termino:
        return dict(_NOT_FOUND)
    # La cantidad al inicio ('2 sillas') es cuenta, no identidad: se saca para que
    # el guardia de modelo no tome el numero como un SKU inexistente.
    termino = _sin_cantidad_inicial(termino)

    # 1) Candidatos del catalogo (con red de typos). La pista del interprete, si
    #    existe y trae un token distintivo, busca primero (mas precisa).
    cands: list[dict] = []
    if pista and _toks_distintivos(pista):
        cands = _candidatos_con_typo(pista, tienda_id, trace_id=trace_id)
        cands = _relevante(cands, pista)
    if not cands:
        cands = _candidatos_con_typo(termino, tienda_id, trace_id=trace_id)
        cands = _relevante(cands, termino)
    if not cands:
        log.info("certificar_not_found", trace_id=trace_id, termino=termino[:60],
                 motivo="sin_candidatos")
        return dict(_NOT_FOUND)

    # 2) Guardia de categoria: si nombro un rubro, el resultado tiene que ser de
    #    ESE rubro. Si no hay ninguno, NO se cruza: not_found, no una placa de
    #    video por una placa base.
    cat = _categoria_pedida(termino)
    if cat:
        en_cat = [c for c in cands if cat in _norm(c.get("categoria", ""))]
        if not en_cat:
            log.info("certificar_not_found", trace_id=trace_id,
                     termino=termino[:60], motivo=f"sin_categoria:{cat}")
            return dict(_NOT_FOUND)
        cands = en_cat

    # 3) Guardia de modelo: si nombro un modelo (token con digito) y NINGUN
    #    candidato lo contiene, lo que matcheo es ruido (palabra floja compartida
    #    tipo 'Steel'): not_found.
    dig = [t for t in re.findall(r"[a-z0-9]+", _norm(termino))
           if any(c.isdigit() for c in t)]
    if dig and not any(d in _nombre_toks(c) for c in cands for d in dig):
        log.info("certificar_not_found", trace_id=trace_id, termino=termino[:60],
                 motivo="modelo_ausente")
        return dict(_NOT_FOUND)

    # 3.5) Guardia del SUSTANTIVO CABEZA: el primer token distintivo (lo que el
    #      cliente pide: 'heladera', 'teclado', 'impresora') tiene que aparecer en
    #      algun candidato. Si el match se sostiene SOLO por la marca ('heladera
    #      Samsung' -> 'Cargador Samsung'), es ruido: not_found, no se ofrece otro
    #      rubro de la misma marca.
    toks_t = _toks_distintivos(termino)
    if toks_t and not any(_cubre(toks_t[0], _nombre_toks(c)) for c in cands):
        log.info("certificar_not_found", trace_id=trace_id, termino=termino[:60],
                 motivo="cabeza_ausente")
        return dict(_NOT_FOUND)

    # 4) Angostar por atributo (color/modelo) si hay varios.
    if len(cands) > 1:
        cands = refinar_por_atributo(cands, termino) or cands

    # 5) Pista EXACTA del interprete: si su nombre matchea uno, gana (certificado
    #    igual, porque salio del catalogo).
    if pista:
        exacto = [c for c in cands
                  if _norm(c.get("nombre", "")) == _norm(pista)]
        if len(exacto) == 1:
            return _exists(exacto[0])

    if len(cands) == 1:
        return _exists(cands[0])

    # 6) Ganador claro por solapamiento de tokens (modelo exacto del cliente).
    mejor = _mejor_por_tokens(cands, termino)
    if mejor is not None:
        return _exists(mejor)

    # 7) Varias variantes reales: AMBIGUO, el que consume tiene que preguntar.
    log.info("certificar_ambiguous", trace_id=trace_id, termino=termino[:60],
             n=len(cands))
    return _ambiguous(cands)
