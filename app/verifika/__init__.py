"""
VERIFIKA — núcleo verificable reutilizable entre productos.

Componentes:
- llm_adapter: interfaz única para cualquier modelo LLM
- proposer: descompone respuesta en afirmaciones atómicas
- checker: valida cada afirmación contra evidencia
- pipeline: orquesta Proposer + Checker para una respuesta dada

Uso desde un producto (ej: agente de ventas):

    from app.verifika.pipeline import verify_response

    resultado = verify_response(
        respuesta_solver="...",
        evidencia=[...],  # productos/fragmentos recuperados
        trace_id="abc123",
    )

    if resultado["confianza"] >= 0.7:
        # mandar la respuesta
    else:
        # responder "no tengo esa info"
"""
from app.verifika.llm_adapter import llm_complete, list_roles_config
from app.verifika.proposer import propose_claims
from app.verifika.checker import check_claims
from app.verifika.pipeline import verify_response

__all__ = [
    "llm_complete",
    "list_roles_config",
    "propose_claims",
    "check_claims",
    "verify_response",
]
