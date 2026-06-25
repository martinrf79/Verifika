"""
VERIFIKA — adaptador de modelo LLM reutilizable.

- llm_adapter: interfaz unica para cualquier modelo LLM, por rol.

El Checker LLM (proposer/checker/pipeline) se consolido y borro el 25-jun: el
camino vivo usa el filtro determinista (app/core/verificador.py), no un LLM
juzgando a otro LLM.
"""
from app.verifika.llm_adapter import llm_complete, list_roles_config

__all__ = [
    "llm_complete",
    "list_roles_config",
]
