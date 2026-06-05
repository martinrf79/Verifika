"""
PROPOSER — descompone la respuesta del Solver en afirmaciones atómicas verificables.

CLAVE: el Proposer recibe SOLO el texto de la respuesta. No ve la pregunta
original. No ve la evidencia. Esto rompe el sesgo de autoconfirmación.

Una "afirmación atómica" es una oración o cláusula que afirma UN hecho concreto:
- "El monitor Samsung Odyssey G7 cuesta 280.000 pesos"  ← afirmación atómica
- "Tenemos varios monitores incluyendo el G7 a 280.000 y otros más baratos"  ← NO, son varias
"""
import json
import re
from typing import Optional

from app.verifika.llm_adapter import llm_complete
from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

# Objeto-afirmacion mas interno: {...} sin llaves anidadas. Cada afirmacion del
# Proposer es plana (id, texto, tipo), asi que esto matchea una por una.
_OBJ_RE = re.compile(r"\{[^{}]*\}")


def salvage_afirmaciones(content: str) -> list[dict]:
    """Rescata las afirmaciones COMPLETAS de un JSON truncado. Si el modelo se
    queda sin tokens y corta la salida a la mitad de un string, json.loads falla
    y perdiamos TODAS las afirmaciones del turno: el Checker se quedaba sin nada
    que verificar y la respuesta pasaba sin gatear. Esto extrae los objetos
    {..."texto"...} que SI cerraron y descarta solo el ultimo cortado. Codigo
    puro, sin LLM."""
    out: list[dict] = []
    for m in _OBJ_RE.finditer(content or ""):
        try:
            o = json.loads(m.group(0))
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(o, dict) and o.get("texto"):
            out.append(o)
    return out


# Evita que el Proposer convierta una cantidad pedida por el cliente en una
# afirmacion de stock.
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

    system_content = PROPOSER_SYSTEM_PROMPT + _REGLA_CANTIDAD

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": f"Texto a descomponer:\n\n{respuesta_texto}"},
    ]

    try:
        result = llm_complete(
            messages=messages,
            role="proposer",
            temperature=0.0,  # determinista
            # 1200: una respuesta larga del Solver (presupuesto + objeciones)
            # genera muchas afirmaciones y 600 tokens truncaba el JSON.
            max_tokens=1200,
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
        afirmaciones = parsed.get("afirmaciones", [])
        if not isinstance(afirmaciones, list):
            log.warning("proposer_afirmaciones_not_list", trace_id=trace_id)
            return []
    except json.JSONDecodeError as e:
        # JSON truncado (el modelo se quedo sin tokens): rescatamos las
        # afirmaciones que SI cerraron en vez de perder todo el turno.
        afirmaciones = salvage_afirmaciones(content)
        if afirmaciones:
            log.warning("proposer_json_salvaged", trace_id=trace_id,
                        rescatadas=len(afirmaciones), error=str(e)[:80])
        else:
            log.warning("proposer_json_invalid", trace_id=trace_id,
                        error=str(e)[:100], content_preview=content[:200])
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
