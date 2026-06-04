"""
RESPONDEDOR DETERMINISTA DE FAQ (Hito 2 del grounding anti alucinacion).

Idea: una pregunta PURA de politica de la tienda, "cuanto tarda a Salta",
"como puedo pagar", "hacen factura A", no necesita pasar por el LLM. El codigo
detecta el tema por palabras clave, agarra el texto YA CURADO de la FAQ y lo
responde tal cual. Sin generacion, no hay nada que alucinar. Es la version
determinista de la respuesta a las clases donde el bot bordaba de mas, envio y
formas de pago.

Tienda-agnostico: sale de la FAQ del cliente, mismo insumo que los
verificadores. No tiene listas fijas de temas: decide por puntaje de keywords.

Conservador a proposito: solo contesta directo cuando UN tema matchea fuerte y
domina claro, y el orchestrator confirma que no hay un producto en juego (una
cotizacion la maneja el Solver con la calculadora). Ante la duda devuelve None y
deja que siga el flujo normal. Asi un cortocircuito de mas no rompe la venta.

Detras del flag FAQ_DIRECTO. Apagado no se invoca.
"""
import re
import unicodedata
from typing import Optional

from app.logger import get_logger

log = get_logger(__name__)

# Puntaje minimo del tema ganador para contestar directo. El puntaje suma el
# largo de las keywords que matchean, asi una frase especifica como "formas de
# pago" pesa mas que una palabra suelta. 5 evita disparar con un match debil.
MIN_SCORE = 5
# El ganador tiene que dominar al segundo: si dos temas matchean parejo, la
# pregunta toca varios temas y la dejamos al Solver, que arma la respuesta
# combinada con las reglas del prompt. Solo cortocircuitamos lo monotema claro.
FACTOR_DOMINANCIA = 2.0


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


# Sufijos de flexion del espanol, del mas largo al mas corto. Sacarlos deja la
# raiz: pagar/pago/pagos -> pag, envio/envios/envian/enviar -> envi.
_SUFIJOS = ("ciones", "cion", "mente", "ando", "iendo", "aron", "ados", "adas",
            "ado", "ada", "amos", "aban", "ar", "er", "ir", "es", "os", "as",
            "an", "en", "a", "o", "e", "s")


def _raiz(w: str) -> str:
    for suf in _SUFIJOS:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)]
    return w


def _palabras(texto: str) -> list[str]:
    return [p for p in re.split(r"[^a-z0-9]+", _norm(texto)) if p]


def _palabra_matchea(kw_word: str, consulta_words: list[str]) -> bool:
    """Una palabra de keyword matchea si su RAIZ es igual a la de alguna palabra
    de la consulta. Asi 'pago' pega con 'pagar' y 'pagos' (raiz 'pag'), sin el
    sobre-match del prefijo, que cruzaba temas."""
    rk = _raiz(kw_word)
    if len(rk) < 3:
        # raiz muy corta: exigir palabra exacta para no sobre-matchear.
        return kw_word in consulta_words
    return any(_raiz(cw) == rk for cw in consulta_words)


def _kw_matchea(kw_norm: str, consulta_words: list[str]) -> bool:
    """Un keyword (una o varias palabras) matchea si TODAS sus palabras tienen
    match por raiz en la consulta. Cubre flexion y orden distinto."""
    kw_words = [w for w in kw_norm.split() if w]
    if not kw_words:
        return False
    return all(_palabra_matchea(w, consulta_words) for w in kw_words)


# Un match cuenta como ESPECIFICO si la keyword es una frase de varias palabras
# o una palabra larga. Las palabras sueltas y cortas, "persona", "local",
# "urgente", cruzan temas y enrutan mal, asi que NO alcanzan para contestar
# directo. Solo un match especifico habilita el cortocircuito.
LARGO_ESPECIFICO = 8


def _es_especifico(kw_norm: str) -> bool:
    return " " in kw_norm or len(kw_norm) >= LARGO_ESPECIFICO


def _puntajes(consulta: str, faq: dict) -> list[tuple[int, bool, str]]:
    """Puntaje por tema: suma del largo de las keywords que matchean por RAIZ en
    la consulta, mas si el tema tuvo al menos un match ESPECIFICO. Devuelve lista
    ordenada de mayor a menor (score, especifico, tema)."""
    cwords = _palabras(consulta)
    out = []
    for tema, data in (faq or {}).items():
        # Puntaje = largo de la keyword MAS LARGA que matchea (no la suma), asi
        # las variantes de una misma raiz, envio/envios/envian, no inflan el tema.
        mejor = 0
        especifico = False
        for kw in data.get("keywords", []) or []:
            k = _norm(kw)
            if k and _kw_matchea(k, cwords):
                mejor = max(mejor, len(k))
                if _es_especifico(k):
                    especifico = True
        if mejor:
            out.append((mejor, especifico, tema))
    out.sort(reverse=True)
    return out


def _label(faq: dict, tema: str) -> str:
    """Etiqueta humana de un tema para el read-back: su keyword mas descriptiva
    (la mas larga). Cae al nombre del tema con guiones bajos en espacios."""
    kws = (faq.get(tema, {}) or {}).get("keywords", []) or []
    if kws:
        return max(kws, key=len)
    return (tema or "").replace("_", " ")


def _readback(faq: dict, opciones: list[str]) -> str:
    a = _label(faq, opciones[0])
    b = _label(faq, opciones[1])
    return f"Para no equivocarme, te referis a {a} o a {b}?"


def resolver_puertas(consulta: str,
                     faq: dict,
                     hay_producto: bool = False,
                     compra_activa: bool = False,
                     es_consulta_info: bool = False,
                     trace_id: Optional[str] = None) -> dict:
    """Cuatro puertas sobre la fuente de verdad. Devuelve un veredicto:
      responder -> {puerta, tema, respuesta, venta}: hay un hecho dominante claro.
      confirmar -> {puerta, opciones, mensaje}: dos temas fuertes compiten, se
                   hace read-back en vez de adivinar.
      consultar -> {puerta, motivo}: es pregunta de politica pero la fuente no
                   tiene el dato; deriva o consulta.
      seguir    -> {puerta}: no es una pregunta de fuente (producto, charla); que
                   siga el resto del pipeline.
    Ante la duda nunca inventa: cae en confirmar, consultar o seguir.
    """
    # Sin match fuerte de la fuente, DELEGAMOS al Solver. El Solver busca en el
    # catalogo (una pregunta de producto como "cuanto sale la RTX 4070" la
    # resuelve ahi) y, si no hay nada, abstiene seguro via verificador. No
    # abstenemos en el nucleo: hacerlo pisaba preguntas de producto que el Solver
    # SI sabe contestar. La objecion (regateo/retiro) se chequea aparte, antes.
    def _sin_dato() -> dict:
        return {"puerta": "seguir"}

    # Compra activa (decision de compra): va al solver para cotizar y cerrar,
    # aunque haya un match de FAQ. El match fuerte gana sobre la simple MENCION
    # de producto, pero no sobre la intencion de comprar.
    if compra_activa or not faq:
        return {"puerta": "seguir"}
    puntajes = _puntajes(consulta, faq)
    if not puntajes:
        return _sin_dato()
    top_score, top_esp, top_tema = puntajes[0]
    # Match debil o no especifico: el enrutamiento no es confiable.
    if top_score < MIN_SCORE or not top_esp:
        log.info("puerta_match_debil", trace_id=trace_id, top=top_tema,
                 top_score=top_score)
        return _sin_dato()
    # Dos temas especificos y parejos compiten: es una pregunta COMPUESTA, el
    # cliente quiere las DOS cosas (precio y cuotas, iva y factura). Rebotarla con
    # un read-back es mala UX; la maneja el Solver, que con sus tools contesta las
    # dos partes. La puerta confirmar queda para ambiguedad real de producto, no
    # para multi-tema de FAQ.
    if len(puntajes) > 1:
        s2, esp2, tema2 = puntajes[1]
        if esp2 and s2 >= MIN_SCORE and top_score < s2 * FACTOR_DOMINANCIA:
            log.info("puerta_compuesta_seguir", trace_id=trace_id,
                     opciones=[top_tema, tema2])
            return {"puerta": "seguir"}
    # Dominante y claro: PUERTA RESPONDER, con la capa de conversion si existe.
    entrada = faq.get(top_tema, {}) or {}
    respuesta = (entrada.get("respuesta", "") or "").strip()
    if not respuesta:
        return _sin_dato()
    venta = (entrada.get("venta", "") or "").strip()
    log.info("puerta_responder", trace_id=trace_id, tema=top_tema,
             score=top_score, con_venta=bool(venta))
    return {"puerta": "responder", "tema": top_tema, "respuesta": respuesta,
            "venta": venta}


def responder_faq_directo(consulta: str,
                          faq: dict,
                          hay_producto: bool = False,
                          trace_id: Optional[str] = None) -> Optional[dict]:
    """Compat para el flag FAQ_DIRECTO: solo la puerta RESPONDER (dato dominante
    claro). Para el resto devuelve None y sigue el flujo de hoy. El nucleo nuevo
    usa resolver_puertas, que cubre las cuatro."""
    # En el flag simple, cualquier producto en juego corta al Solver (estricto).
    v = resolver_puertas(consulta, faq, hay_producto=hay_producto,
                         compra_activa=hay_producto, trace_id=trace_id)
    if v.get("puerta") == "responder":
        return {"tema": v["tema"], "respuesta": v["respuesta"],
                "venta": v.get("venta", "")}
    return None
