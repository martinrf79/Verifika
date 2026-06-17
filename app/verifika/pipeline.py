"""
PIPELINE — orquesta el flujo Proposer → Checker → Router de Confianza.

Esta es la API pública que consumen los productos (agente de ventas, generador
de videos, etc).

Uso:

    from app.verifika.pipeline import verify_response

    resultado = verify_response(
        respuesta_solver=texto_que_devolvio_el_solver,
        evidence=[productos_y_faq_recuperados],
        trace_id="abc123",
    )

    if resultado["accion"] == "responder":
        mandar resultado["respuesta_final"]
    else:
        mandar resultado["respuesta_final"]  # ya es el fallback
"""
import os
import re
from typing import Optional

from app.verifika.proposer import propose_claims
from app.verifika.checker import check_claims
from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()


# ────────────────────────────────────────────────────────────
# RECONCILIACION NUMERICA DETERMINISTICA
# Para los numeros manda la calculadora, no el Checker. Si todas las cifras de
# dinero de una afirmacion estan en el PROOF, el catalogo o la FAQ, la
# afirmacion es soportada por construccion, sin importar el juicio del modelo.
# ────────────────────────────────────────────────────────────

# Solo miramos cifras de dinero. Las chicas, cantidades pedidas o porcentajes,
# se ignoran: no son el numero que importa verificar.
_MIN_MONETARIO = 1000
_NUM_RE = re.compile(r"\d[\d.]*")


def _parse_num(token: str):
    t = token.replace(".", "").strip()
    if not t.isdigit():
        return None
    try:
        return int(t)
    except ValueError:
        return None


def _numeros_confiables(evidence: list[dict]):
    """Junta los numeros verdaderos de la evidencia: precios de catalogo,
    valores de FAQ y todo lo que computo la calculadora en su PROOF.
    Devuelve un set de montos exactos y una lista de rangos (min, max)."""
    nums: set[int] = set()
    rangos: list[tuple] = []

    def _add(v):
        if isinstance(v, (int, float)):
            nums.add(int(v))

    for item in evidence or []:
        tipo = item.get("tipo")
        if tipo == "producto":
            _add(item.get("precio_ars"))
        elif tipo == "faq":
            for v in item.get("valores", []) or []:
                for k in ("monto", "monto_min", "monto_max",
                          "monto_calculado_ars", "base_ars"):
                    _add(v.get(k))
                # Umbrales que viven en el texto de la condicion, no en un campo
                # numerico. Ej "compra mayor a 250000": el 250000 es verdad.
                for tok in _NUM_RE.findall(str(v.get("condicion", ""))):
                    n = _parse_num(tok)
                    if n is not None and n >= _MIN_MONETARIO:
                        nums.add(n)
            # Numeros mencionados en el texto de la respuesta de la FAQ
            # (umbrales, montos), que tambien son verdad del negocio.
            for tok in _NUM_RE.findall(str(item.get("respuesta", ""))):
                n = _parse_num(tok)
                if n is not None and n >= _MIN_MONETARIO:
                    nums.add(n)
        elif tipo == "proof":
            proof = item.get("proof", {}) or {}
            for k in ("resultado", "resultado_min", "resultado_max",
                      "subtotal_productos"):
                _add(proof.get(k))
            for o in proof.get("operandos_productos", []) or []:
                _add(o.get("monto"))
            for e in proof.get("operandos_extras", []) or []:
                for k in ("monto", "monto_min", "monto_max",
                          "monto_calculado_ars", "base_ars"):
                    _add(e.get(k))
            rmin, rmax = proof.get("resultado_min"), proof.get("resultado_max")
            if isinstance(rmin, (int, float)) and isinstance(rmax, (int, float)):
                rangos.append((int(rmin), int(rmax)))
    return nums, rangos


def _reconciliar_numeros(veredictos: list[dict],
                         afirmaciones: list[dict],
                         evidence: list[dict],
                         trace_id: Optional[str] = None) -> list[dict]:
    """Corrige a soportada las afirmaciones cuyas cifras de dinero esten todas
    respaldadas por el PROOF, el catalogo o la FAQ. No toca las que tienen algun
    numero sin respaldo: esas siguen el veredicto del Checker."""
    nums, rangos = _numeros_confiables(evidence)
    if not nums and not rangos:
        return veredictos

    por_id = {a.get("id"): a for a in afirmaciones}

    def _confiable(n: int) -> bool:
        if n in nums:
            return True
        return any(lo <= n <= hi for lo, hi in rangos)

    corregidas = 0
    salida = []
    for v in veredictos:
        if v.get("veredicto") == "soportada":
            salida.append(v)
            continue
        texto = (por_id.get(v.get("id")) or {}).get("texto", "")
        grandes = [
            n for n in (_parse_num(t) for t in _NUM_RE.findall(texto))
            if n is not None and n >= _MIN_MONETARIO
        ]
        if grandes and all(_confiable(n) for n in grandes):
            nv = dict(v)
            nv["veredicto"] = "soportada"
            nv["razon"] = "cifra verificada contra proof/catalogo/faq (reconciliacion deterministica)"
            salida.append(nv)
            corregidas += 1
        else:
            salida.append(v)

    if corregidas:
        log.info("verifika_reconcile_numeric", trace_id=trace_id,
                 corregidas=corregidas)
    return salida


# ────────────────────────────────────────────────────────────
# ROUTER DE CONFIANZA — decide si responder o no
# ────────────────────────────────────────────────────────────

# Umbral mínimo de afirmaciones soportadas para mandar la respuesta tal cual.
# Configurable por env: VERIFIKA_UMBRAL_CONFIANZA=0.7
UMBRAL_CONFIANZA = float(os.getenv("VERIFIKA_UMBRAL_CONFIANZA", "0.7"))

# Si hay AUNQUE SEA UNA afirmación contradicha, bloqueamos.
# Configurable: VERIFIKA_BLOQUEAR_CONTRADICHAS=true|false
BLOQUEAR_CONTRADICHAS = os.getenv("VERIFIKA_BLOQUEAR_CONTRADICHAS", "true").lower() == "true"

# Mensaje cuando no hay confianza suficiente.
# Cada producto puede sobreescribir este mensaje en su capa.
DEFAULT_FALLBACK = (
    "No tengo esa información confirmada en el catálogo. "
    "Dejame consultar y te confirmo en breve."
)


def _calcular_confianza(veredictos: list[dict]) -> dict:
    """
    Calcula score de confianza basado en veredictos del Checker.

    Returns:
        {
            "score": 0.0 a 1.0,
            "total": int,
            "soportadas": int,
            "contradichas": int,
            "sin_evidencia": int,
            "tiene_contradichas": bool,
        }
    """
    if not veredictos:
        # Si no hay afirmaciones, asumimos que la respuesta es social
        # (saludo, pregunta de vuelta) → confianza máxima
        return {
            "score": 1.0,
            "total": 0,
            "soportadas": 0,
            "contradichas": 0,
            "sin_evidencia": 0,
            "tiene_contradichas": False,
        }

    total = len(veredictos)
    soportadas = sum(1 for v in veredictos if v["veredicto"] == "soportada")
    contradichas = sum(1 for v in veredictos if v["veredicto"] == "contradicha")
    sin_evidencia = sum(1 for v in veredictos if v["veredicto"] == "sin_evidencia")

    score = soportadas / total if total > 0 else 1.0

    return {
        "score": score,
        "total": total,
        "soportadas": soportadas,
        "contradichas": contradichas,
        "sin_evidencia": sin_evidencia,
        "tiene_contradichas": contradichas > 0,
    }


def _decidir_accion(confianza: dict) -> str:
    """Router de Confianza: decide qué hacer con la respuesta."""
    if confianza["total"] == 0:
        # Respuesta sin afirmaciones (saludo, pregunta) → dejar pasar
        return "responder"

    if BLOQUEAR_CONTRADICHAS and confianza["tiene_contradichas"]:
        return "bloquear"

    if confianza["score"] >= UMBRAL_CONFIANZA:
        return "responder"

    return "bloquear"


# ────────────────────────────────────────────────────────────
# API PÚBLICA
# ────────────────────────────────────────────────────────────

def verify_response(
    respuesta_solver: str,
    evidence: list[dict],
    trace_id: Optional[str] = None,
    fallback_message: Optional[str] = None,
) -> dict:
    """
    Verifica una respuesta del Solver y decide si mandarla o no.

    Args:
        respuesta_solver: el texto generado por el Solver
        evidence: lista de productos/FAQs recuperados durante la búsqueda
                  (los mismos que se le pasaron al Solver vía tools)
        trace_id: para logging correlacionado
        fallback_message: mensaje a usar si se bloquea la respuesta.
                          Si es None, usa DEFAULT_FALLBACK.

    Returns:
        {
            "accion": "responder" | "bloquear",
            "respuesta_final": str,  # respuesta original o fallback
            "respuesta_solver": str,  # original sin tocar
            "afirmaciones": [...],
            "veredictos": [...],
            "confianza": {...},
            "trace_id": str,
        }
    """
    fallback = fallback_message or DEFAULT_FALLBACK

    # 1) Proposer: descomponer en afirmaciones atómicas
    afirmaciones = propose_claims(respuesta_solver, trace_id=trace_id)

    # 2) Checker: verificar cada afirmación contra la evidencia
    veredictos = check_claims(afirmaciones, evidence, trace_id=trace_id)

    # 2.5) Reconciliacion numerica: para las cifras manda la calculadora, no el
    # Checker. Corrige falsos contradicha o sin_evidencia sobre numeros que ya
    # son verdad en el PROOF, el catalogo o la FAQ. Las alucinaciones numericas
    # reales no se tocan, porque su numero no esta en ninguna fuente.
    veredictos = _reconciliar_numeros(
        veredictos, afirmaciones, evidence, trace_id=trace_id)

    # 3) Router de Confianza: calcular score y decidir
    confianza = _calcular_confianza(veredictos)
    accion = _decidir_accion(confianza)

    if accion == "responder":
        respuesta_final = respuesta_solver
    else:
        respuesta_final = fallback

    resultado = {
        "accion": accion,
        "respuesta_final": respuesta_final,
        "respuesta_solver": respuesta_solver,
        "afirmaciones": afirmaciones,
        "veredictos": veredictos,
        "confianza": confianza,
        "trace_id": trace_id,
    }

    log.info("verifika_pipeline_done",
             trace_id=trace_id,
             accion=accion,
             score=round(confianza["score"], 2),
             total_afirmaciones=confianza["total"],
             soportadas=confianza["soportadas"],
             contradichas=confianza["contradichas"],
             sin_evidencia=confianza["sin_evidencia"])

    return resultado
