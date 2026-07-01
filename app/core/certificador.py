"""
CERTIFICADOR DE IDENTIDAD - Regla Cero del proyecto (Martin, 15-jun).

La identidad de un producto, si EXISTE, es AMBIGUO, o NO existe, la decide UNA
sola funcion determinista, no el LLM. Tres veredictos de primera clase:

  - exists:    un unico producto del catalogo matchea lo que pidio el cliente.
  - ambiguous: matchean varios; hay que preguntar cual, no elegir por el cliente.
  - not_found: nada matchea. NO es un error: es un resultado valido y explicito,
               el 'no tenemos eso' honesto, en vez de pivotear en silencio a
               alternativas (bug E15).

Es codigo puro, sin LLM: normaliza el texto, saca los tokens que IDENTIFICAN un
producto (descarta articulos, verbos de pedido y modificadores genericos como
'gamer' o 'pro', que dicen COMO es la cosa pero no QUE es) y los cruza con el
catalogo. Para los casos claros manda la fuente de verdad, el catalogo; los tres
veredictos existen para los casos confusos, donde ambiguous dispara una pregunta
de confirmacion en vez de que el bot elija o invente.
"""
import re
import unicodedata

VEREDICTOS = {"exists", "ambiguous", "not_found"}

# Palabras que NO identifican un producto: articulos, cuantificadores, verbos de
# pedido, conectores y modificadores genericos. Un adjetivo como 'gamer' no dice
# QUE es la cosa, solo como es, asi que se descarta antes de cruzar con el
# catalogo: 'una notebook gamer' se identifica por 'notebook', no por 'gamer'.
_STOP = {
    "una", "uno", "unos", "unas", "los", "las", "del", "con", "por", "para",
    "que", "quiero", "necesito", "busco", "buscando", "tienen", "tenes",
    "hay", "dame", "algun", "alguna", "alguno", "tipo", "modelo", "marca",
    "precio", "cuesta", "vale", "sale", "mostrame", "mostra", "algo",
    # modificadores genericos que no identifican el producto en si
    "gamer", "gaming", "pro", "premium", "nuevo", "nueva", "barato", "barata",
    "economico", "economica", "bueno", "buena", "mejor", "rgb", "inalambrico",
    "inalambrica", "bluetooth", "chico", "chica", "grande", "rojo", "negro",
    "blanco", "color",
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _tokens_identificadores(texto: str) -> set:
    """Tokens que identifican un producto: alfanumericos de 4+ chars que no sean
    stopwords ni modificadores genericos."""
    return {t for t in re.findall(r"[a-z0-9]+", _norm(texto))
            if len(t) >= 4 and t not in _STOP}


def _tokens_producto(prod: dict) -> set:
    """Tokens del producto para matchear: nombre + categoria, normalizados."""
    texto = f"{prod.get('nombre', '')} {prod.get('categoria', '')}"
    return set(re.findall(r"[a-z0-9]+", _norm(texto)))


def certificar(texto: str, catalogo: list[dict]) -> dict:
    """Certifica la identidad de lo que pidio el cliente contra el catalogo.

    Devuelve {'veredicto': exists|ambiguous|not_found, 'candidatos': [ids],
    'tokens': [...]}. Determinista, sin LLM.

    - not_found: ningun producto comparte un token identificador con el pedido.
      Es el 'no tenemos eso' explicito (E15), no un pivoteo silencioso.
    - exists: exactamente un producto matchea.
    - ambiguous: matchean dos o mas; el llamador debe PREGUNTAR cual, no elegir.
    """
    tokens = _tokens_identificadores(texto)
    if not tokens:
        return {"veredicto": "not_found", "candidatos": [], "tokens": []}

    candidatos: list = []
    for prod in catalogo or []:
        if tokens & _tokens_producto(prod):
            pid = prod.get("id")
            if pid is not None and pid not in candidatos:
                candidatos.append(pid)

    if not candidatos:
        veredicto = "not_found"
    elif len(candidatos) == 1:
        veredicto = "exists"
    else:
        veredicto = "ambiguous"
    return {"veredicto": veredicto, "candidatos": candidatos,
            "tokens": sorted(tokens)}
