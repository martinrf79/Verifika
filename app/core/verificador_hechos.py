"""
VERIFICADOR DE HECHOS — tercera linea determinista de la anti alucinacion.

El verificador de plata cuida los NUMEROS de dinero. El de servicios cuida las
CAPACIDADES inventadas (retiro, instalacion, armado). Falta una clase mas que
aparecio con datos reales: el bot NARRA una REGLA de la tienda y la dice mal.
Caso canonico (conversacion de Jorge, soporte de notebook a Despeñaderos):
- La FAQ dice "interior 4 a 7 dias habiles" y el bot prometio "llega el jueves"
  y "24 a 72 horas". Comprimio la regla y comprometio un dia de entrega que el
  correo no garantiza.
- La FAQ lista las formas de pago, el bot agrego "American Express directo, sin
  intermediarios", un detalle que no esta en ningun lado.

La regla de oro de esta pieza, la que aprendimos a los golpes: NO es una lista
negra de frases (eso no escala, las redacciones son infinitas). Es deteccion por
CLASE de afirmacion (promete un dia de entrega, comprime el plazo, agrega un
detalle de pago) ATERRIZADA contra un HECHO ESTRUCTURADO sacado de la FAQ. La
clase es un concepto acotado, el hecho es un dato finito. Las mil formas de decir
"te llega el jueves" colapsan en una sola pregunta: la tienda compromete dias de
entrega? No. Entonces se marca, lo haya dicho como lo haya dicho.

Codigo puro, sin LLM, igual que las otras dos lineas. Ante la duda NO marca: si
un hecho no se pudo derivar de la FAQ, esa clase no se chequea (falla abierto,
para no bloquear de mas). Flag VERIFICADOR_HECHOS off/shadow/on, default off.
"""
import re
import unicodedata
from typing import Optional

from app.logger import get_logger

log = get_logger(__name__)

_DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado",
         "domingo")
# Verbos que, cerca de un dia, significan PROMESA DE ENTREGA ese dia (no horario
# de atencion). "atendemos de lunes a viernes" NO es esto.
# "lleg(?!ue)\w+" mata el SUBJUNTIVO: "que llegue el viernes" es condicion o
# deseo, no promesa. "llega/llegara/llego" (indicativo) si es promesa. Esto saca
# de raiz una familia de falsos positivos sin enumerar negaciones una por una.
_ARRIBO_RE = re.compile(
    r"\b(lleg(?!ue)\w+|recib[íi]s|recibe|entreg\w+|despach\w+|lo ten[ée]s|"
    r"te llega|sale el|sali[óo] el|estaria llegando|estar[íi]a en tus manos)\b")
# Marcas de que es HORARIO DE ATENCION, no entrega. Si aparecen en la ventana,
# no se marca el dia.
_HORARIO_RE = re.compile(r"atend\w+|horario|\bhs\b|de \d+ a \d+|a viernes")
# Si cerca del dia hay una NEGACION o un CONDICIONAL, no es una promesa de
# entrega ese dia. "para este jueves no llegaria", "para que llegue el viernes
# tendria que despacharse ya". El red-team mostro que el bot casi siempre NIEGA o
# CONDICIONA el dia, no lo promete. Ante la duda, no marcar.
# OJO: esta lista crece despacio a proposito, pero detectar "promesa vs negacion"
# en texto libre con regex es fragil (las formas de negar son infinitas). A la
# larga la DETECCION es trabajo del checker con LLM; el GROUNDING contra la ficha
# es lo que queda en codigo. Aca cubrimos los hedges reales vistos en red-team.
_NO_PROMESA_RE = re.compile(
    r"\bno\b|para que|si quer|si es|tendr[íi]a|deber[íi]a|habr[íi]a que|depende|"
    r"consult|fijate|capaz|quiz[áa]|dif[íi]cil|complicad|salvo|viable|estar[íi]a "
    r"complicad|no creo|no (te )?asegur|no (te )?garanti|no puedo confirm|"
    r"deja(me)? (consult|ver)|habria que ver")


def _normaliza(t) -> str:
    t = unicodedata.normalize("NFKD", str(t or ""))
    t = t.encode("ascii", "ignore").decode("ascii")
    return t.lower()


def construir_ficha(evidence: list[dict]) -> dict:
    """Deriva de la FAQ los HECHOS estructurados que el bot tiende a narrar mal.
    Lo que no se puede derivar queda en None y esa clase no se chequea."""
    corpus_parts = []
    formas_pago = None
    for item in evidence or []:
        if item.get("tipo") != "faq":
            continue
        tema = _normaliza(item.get("tema", ""))
        resp = _normaliza(item.get("respuesta", ""))
        corpus_parts.append(resp)
        if "pago" in tema or "tarjeta" in tema or "american" in resp:
            formas_pago = (formas_pago or "") + " " + resp
    corpus = " ".join(corpus_parts)

    ficha: dict = {
        "plazo_interior_dias": None,   # (min, max) en dias habiles
        "plazo_caba_dias": None,
        "entrega_en_dias": None,       # True si el plazo se mide en dias (no horas)
        "express_zonas": [],           # zonas con envio express por horas
        "formas_pago_texto": formas_pago,
        "compromete_dia_entrega": False,  # la FAQ promete un dia puntual? casi nunca
    }

    # Plazo interior y CABA: "interior 4 a 7 dias", "caba y gba 2 a 3 dias".
    m_int = re.search(r"interior[^.]{0,30}?(\d+)\s*a\s*(\d+)\s*dias", corpus)
    if m_int:
        ficha["plazo_interior_dias"] = (int(m_int.group(1)), int(m_int.group(2)))
        ficha["entrega_en_dias"] = True
    m_caba = re.search(r"(caba|gba)[^.]{0,30}?(\d+)\s*a\s*(\d+)\s*dias", corpus)
    if m_caba:
        ficha["plazo_caba_dias"] = (int(m_caba.group(2)), int(m_caba.group(3)))

    # Express por horas: solo en ciertas zonas (CABA/GBA en demo).
    if re.search(r"express", corpus):
        zonas = []
        m_exp = re.search(r"express[^.]{0,40}", corpus)
        seg = m_exp.group(0) if m_exp else ""
        for z in ("caba", "gba"):
            if z in seg:
                zonas.append(z)
        ficha["express_zonas"] = zonas

    return ficha


def _promete_dia_entrega(resp: str) -> Optional[str]:
    """Devuelve el dia si la respuesta COMPROMETE la entrega un dia puntual de la
    semana (lo que el correo no garantiza), sin confundir con horario de atencion."""
    for dia in _DIAS:
        for m in re.finditer(r"\b" + dia + r"\b", resp):
            ini = max(0, m.start() - 45)
            fin = min(len(resp), m.end() + 45)
            ventana = resp[ini:fin]
            if _HORARIO_RE.search(ventana):
                continue
            if _NO_PROMESA_RE.search(ventana):
                continue
            if _ARRIBO_RE.search(ventana):
                return dia
    return None


def _entrega_comprimida_en_horas(resp: str, ficha: dict) -> bool:
    """True si la respuesta promete la entrega en HORAS cuando la regla de la
    tienda la mide en DIAS y no es un caso express habilitado."""
    if not ficha.get("entrega_en_dias"):
        return False
    # "24 a 72 horas", "24 horas habiles" en contexto de envio/entrega. OJO: el
    # express de CABA/GBA SI es en horas y el bot lo explica bien (y lo niega para
    # el interior). El red-team mostro que marcar todo "horas" da falsos positivos.
    # Solo es error cuando se le pega un plazo en horas a un envio que la regla
    # mide en dias SIN el calificador express. Caso Jorge: "24 a 72 horas al
    # interior".
    for m in re.finditer(r"(\d+)\s*(a\s*\d+\s*)?horas?", resp):
        ini = max(0, m.start() - 60)
        ventana = resp[ini:m.end() + 30]
        if not re.search(r"envio|entreg\w+|lleg\w+|despach\w+|recib\w+",
                         ventana):
            continue
        # Negacion o condicional cerca ("no te puedo asegurar 24 horas", "no
        # tenemos express"): el bot declina, no promete.
        if _NO_PROMESA_RE.search(ventana):
            continue
        # Si en la ventana esta "express" o una zona express, es la explicacion
        # legitima del servicio, no una compresion del plazo al interior.
        if "express" in ventana or any(z in ventana for z in
                                       ficha.get("express_zonas", [])):
            continue
        return True
    return False


def _detalle_pago_inventado(resp: str, ficha: dict) -> Optional[str]:
    """Marca un detalle de PROCESAMIENTO de pago que la respuesta afirma y la FAQ
    no respalda (ej 'American Express directo, sin intermediarios')."""
    gatillo = re.search(
        r"(directo,?\s*sin intermediari\w+|sin intermediari\w+|"
        r"procesamos\w*\s+direct\w+|de forma directa)", resp)
    if not gatillo:
        return None
    respaldo = _normaliza(ficha.get("formas_pago_texto") or "")
    # Si la FAQ misma habla de "directo/sin intermediario", esta respaldado.
    if "intermediari" in respaldo or "directo" in respaldo:
        return None
    return gatillo.group(0)


def verificar_hechos(respuesta: str,
                     evidence: list[dict],
                     trace_id: Optional[str] = None) -> dict:
    """
    Marca afirmaciones que NARRAN mal una regla de la tienda. Devuelve:
        {ok, accion: responder|bloquear, problemas: [str], hechos: [str]}
    'problemas' lista las clases marcadas (promesa_dia_entrega,
    plazo_en_horas, detalle_pago_inventado).
    """
    resp = _normaliza(respuesta)
    ficha = construir_ficha(evidence)
    problemas: list[str] = []

    dia = _promete_dia_entrega(resp)
    if dia:
        problemas.append("promesa_dia_entrega:" + dia)

    if _entrega_comprimida_en_horas(resp, ficha):
        problemas.append("plazo_en_horas")

    pago = _detalle_pago_inventado(resp, ficha)
    if pago:
        problemas.append("detalle_pago_inventado")

    ok = len(problemas) == 0
    accion = "responder" if ok else "bloquear"
    log.info("verificador_hechos", trace_id=trace_id, accion=accion,
             problemas=problemas)
    return {"ok": ok, "accion": accion, "problemas": problemas,
            "hechos": problemas}
