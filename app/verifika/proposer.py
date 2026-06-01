"""
PROPOSER — descompone la respuesta del Solver en afirmaciones atómicas verificables.

CLAVE: el Proposer recibe SOLO el texto de la respuesta. No ve la pregunta
original. No ve la evidencia. Esto rompe el sesgo de autoconfirmación.

Una "afirmación atómica" es una oración o cláusula que afirma UN hecho concreto:
- "El monitor Samsung Odyssey G7 cuesta 280.000 pesos"  ← afirmación atómica
- "Tenemos varios monitores incluyendo el G7 a 280.000 y otros más baratos"  ← NO, son varias
"""
import json
from typing import Optional

from app.verifika.llm_adapter import llm_complete
from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()


# Regla extra opcional (flag PROPOSER_IGNORA_CANTIDAD). Evita que el Proposer
# convierta una cantidad pedida por el cliente en una afirmacion de stock.
_REGLA_CANTIDAD = """
6. CANTIDADES PEDIDAS NO SON STOCK. Si el texto menciona una cantidad que el cliente quiere comprar, por ejemplo "2x Monitor", "2 monitores", "3 teclados", "llevo 4 sillas", eso es la cantidad pedida, NO cuantas unidades hay disponibles. NO generes afirmaciones de tipo stock a partir de cantidades pedidas, multiplicaciones de presupuesto ni lineas de un total. Solo genera una afirmacion de stock si el texto dice explicitamente que HAY X unidades disponibles o en stock."""


PROPOSER_SYSTEM_PROMPT = """Sos un descompositor de afirmaciones. Tu única tarea es leer un texto y extraer las afirmaciones atómicas que contiene.

REGLAS:
1. Cada afirmación debe ser UN solo hecho concreto y verificable.
2. NO interpretes, NO opines, NO agregues información.
3. Si el texto contiene una afirmación compuesta (con "y", "pero", comas), descomponela en varias.
4. Ignorá saludos, preguntas, frases de cortesía, sugerencias.
5. Solo afirmaciones sobre HECHOS: precios, productos, características, stock, condiciones, políticas.

FORMATO DE SALIDA: JSON estricto, sin texto antes ni después.
{
  "afirmaciones": [
    {"id": "a1", "texto": "...", "tipo": "precio|producto|stock|caracteristica|politica|otro"},
    ...
  ]
}

Si el texto no contiene afirmaciones verificables (es un saludo, una pregunta, una frase social), devolvé:
{"afirmaciones": []}

EJEMPLOS:

Texto: "Tenemos el monitor Samsung G7 a $280.000 con stock disponible."
Salida:
{
  "afirmaciones": [
    {"id": "a1", "texto": "El monitor Samsung G7 cuesta 280000 pesos", "tipo": "precio"},
    {"id": "a2", "texto": "El monitor Samsung G7 tiene stock disponible", "tipo": "stock"}
  ]
}

Texto: "¡Hola! ¿En qué te puedo ayudar?"
Salida:
{"afirmaciones": []}

Texto: "El envío es gratis a partir de 50.000 pesos y demora 3 días hábiles."
Salida:
{
  "afirmaciones": [
    {"id": "a1", "texto": "El envío es gratis a partir de 50000 pesos", "tipo": "politica"},
    {"id": "a2", "texto": "El envío demora 3 días hábiles", "tipo": "politica"}
  ]
}
"""


def propose_claims(respuesta_texto: str,
                   trace_id: Optional[str] = None) -> list[dict]:
    """
    Descompone una respuesta en afirmaciones atómicas.

    Args:
        respuesta_texto: el texto de respuesta del Solver
        trace_id: para logging correlacionado

    Returns:
        Lista de afirmaciones: [{"id": "a1", "texto": "...", "tipo": "..."}, ...]
        Lista vacía si no hay afirmaciones verificables.
    """
    if not respuesta_texto or not respuesta_texto.strip():
        log.info("proposer_empty_input", trace_id=trace_id)
        return []

    system_content = PROPOSER_SYSTEM_PROMPT
    if settings.PROPOSER_IGNORA_CANTIDAD:
        system_content = system_content + _REGLA_CANTIDAD

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": f"Texto a descomponer:\n\n{respuesta_texto}"},
    ]

    try:
        result = llm_complete(
            messages=messages,
            role="proposer",
            temperature=0.0,  # determinista
            max_tokens=600,
            trace_id=trace_id,
        )
    except Exception as e:
        log.error("proposer_llm_error", trace_id=trace_id, error=str(e)[:200])
        return []

    content = result.get("content", "").strip()

    # Limpieza: a veces el modelo mete ```json ... ```
    if content.startswith("```"):
        content = content.split("```")[1] if "```" in content[3:] else content[3:]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        log.warning("proposer_json_invalid", trace_id=trace_id,
                    error=str(e)[:100], content_preview=content[:200])
        return []

    afirmaciones = parsed.get("afirmaciones", [])
    if not isinstance(afirmaciones, list):
        log.warning("proposer_afirmaciones_not_list", trace_id=trace_id)
        return []

    # Validación básica de estructura
    afirmaciones_validas = []
    for i, a in enumerate(afirmaciones):
        if not isinstance(a, dict):
            continue
        if "texto" not in a or not a["texto"]:
            continue
        # Normalizar
        afirmaciones_validas.append({
            "id": a.get("id", f"a{i+1}"),
            "texto": a["texto"].strip(),
            "tipo": a.get("tipo", "otro"),
        })

    log.info("proposer_ok", trace_id=trace_id,
             total=len(afirmaciones_validas))

    return afirmaciones_validas
