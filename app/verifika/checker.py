"""
CHECKER — valida cada afirmación atómica contra la evidencia.

CLAVE: el Checker recibe SOLO las afirmaciones y la evidencia. No ve la
respuesta original ni la pregunta. Esto rompe el sesgo de autoconfirmación.

Para cada afirmación dictamina:
- "soportada": la evidencia la respalda directamente
- "contradicha": la evidencia la contradice
- "sin_evidencia": la evidencia no menciona el tema

La decisión final (responder o no) la toma el Router de Confianza, no el Checker.
"""
import json
from typing import Optional

from app.verifika.llm_adapter import llm_complete
from app.logger import get_logger

log = get_logger(__name__)


CHECKER_SYSTEM_PROMPT = """Sos un verificador de hechos. Recibís una lista de afirmaciones y un conjunto de evidencia (datos reales del catálogo y FAQ). Tu única tarea es decidir, para cada afirmación, si la evidencia la respalda.

REGLAS:
1. NO uses conocimiento externo. SOLO la evidencia provista.
2. "soportada" si la afirmación menciona elementos que están literalmente en la evidencia, aunque la frase no sea idéntica. Ejemplo, FAQ dice "aceptamos transferencia, Mercado Pago y tarjetas Visa, Mastercard, American Express", bot dice "aceptamos Mercado Pago", es "soportada" porque Mercado Pago está literal en la FAQ.
3. "soportada" si la afirmación es un subconjunto correcto de lo que dice la evidencia. Ejemplo, FAQ enumera cuatro medios de pago, bot enumera dos de esos cuatro sin agregar otros, es "soportada".
4. "contradicha" si la afirmación extiende, generaliza o cambia condiciones de lo que dice la evidencia. Ejemplo, FAQ dice "cuotas sin interés solo con Visa y Mastercard", bot dice "cuotas sin interés con cualquier tarjeta", es "contradicha". También si agrega medios de pago, marcas o servicios que la evidencia no menciona.
5. "contradicha" si los números no coinciden. Si afirmación dice 280000 y evidencia dice 285000, es "contradicha". Si dice "10 por ciento" y evidencia dice "diez por ciento", es "soportada" porque es el mismo número en distinto formato.
6. "sin_evidencia" si la evidencia no menciona el tema en absoluto.
7. NO inventes datos. Reconocer paráfrasis equivalentes está permitido, inventar condiciones nuevas no.
8. RANGOS Y VALORES ESTRUCTURADOS. Cuando la evidencia incluye "valores estructurados" con modalidad rango, el bot puede mencionar el rango completo, cualquier valor dentro del rango, o expresarlo como "entre X y Y", y es "soportada". Si el bot menciona un valor fuera del rango declarado, es "contradicha". Ejemplo, evidencia dice "envio_interior rango 5000 a 12000 ars", bot dice "envio a Santa Fe entre 5000 y 12000 pesos" es "soportada", bot dice "envio a Santa Fe 15000 pesos" es "contradicha".
9. SUMAS Y TOTALES. Cuando el bot presenta un total que combina precio firme de producto mas un rango de envio, validar que cada sumando este en la evidencia y que el total presentado sea aritmeticamente correcto. Si el bot dice "total entre 540000 y 547000" y la evidencia tiene producto 535000 mas envio rango 5000 a 12000, el total es correcto y es "soportada".
10. CALCULOS CON PROOF. La evidencia puede incluir entradas tipo PROOF que provienen de tools verificadas como calculate_total. Cada PROOF tiene formula, operandos productos, operandos extras y resultado. Si el bot menciona un numero que coincide con el resultado de algun PROOF, o con cualquiera de sus operandos, es "soportada", aunque ese numero no aparezca en los productos o FAQ por si solo. Los PROOFs son fuente de verdad para calculos derivados como subtotales, totales, descuentos aplicados y combinaciones aritmeticas. Ejemplo, evidencia tiene PROOF con productos SIL003 285000 y TEC004 12000, resultado 297000, y extras descuento 10 por ciento. Si el bot dice "el total con descuento es 267300", validar aritmetica, 297000 menos 10 por ciento es 267300, es "soportada".

11. NEGAR O LIMITAR ES SEGURO, NO ES CONTRADICHA. Si la afirmacion NIEGA una capacidad, servicio o garantia, o es MAS restrictiva o conservadora que la evidencia (el bot dice que algo NO se puede, que NO garantiza un dia, que un servicio NO figura, que NO hay express puntual), eso NO es "contradicha": que el bot se abstenga o limite es la conducta segura. Marcala "soportada" si la evidencia es coherente con esa limitacion, o "sin_evidencia" si la evidencia no toca el tema. SOLO es "contradicha" cuando la afirmacion AFIRMA de MAS: un dato, beneficio, capacidad, condicion o numero que la evidencia no respalda o que la evidencia contradice. Ejemplo, evidencia dice "envio express en CABA y GBA en 24 horas habiles", bot dice "no hay un envio express que te garantice el martes" es "soportada" (el bot es mas conservador, no contradice). Pero bot dice "el envio es gratis" cuando la evidencia dice que tiene costo es "contradicha" (afirma un beneficio que no existe).

FORMATO DE SALIDA: JSON estricto, sin texto antes ni después.
{
  "veredictos": [
    {"id": "a1", "veredicto": "soportada|contradicha|sin_evidencia", "evidencia_id": "..." o null, "razon": "breve"},
    ...
  ]
}

El campo "evidencia_id" debe ser el ID del producto o tema de FAQ que respalda la afirmación.
Si veredicto es "sin_evidencia", evidencia_id es null.
"""


def _format_evidence(evidence: list[dict]) -> str:
    """Convierte la lista de evidencia a texto legible para el modelo."""
    if not evidence:
        return "(sin evidencia disponible)"

    lines = []
    for item in evidence:
        tipo = item.get("tipo", "producto")
        if tipo == "producto":
            lines.append(
                f"[{item.get('id', '?')}] {item.get('nombre', '?')} "
                f"| categoria: {item.get('categoria', '?')} "
                f"| marca: {item.get('marca', '?')} "
                f"| modelo: {item.get('modelo', '?')} "
                f"| precio: {item.get('precio_ars', '?')} pesos "
                f"| stock: {item.get('stock', '?')} unidades "
                f"| color: {item.get('color', '?')} "
                f"| material: {item.get('material', '?')} "
                f"| peso: {item.get('peso_gramos', '?')} gramos "
                f"| dimensiones: {item.get('dimensiones', '?')} "
                f"| garantia: {item.get('garantia_meses', '?')} meses "
                f"| uso: {item.get('uso_recomendado', '?')} "
                f"| descripcion: {item.get('descripcion', '')} "
                f"| caracteristicas: {item.get('caracteristicas_extra', '')}"
            )
        elif tipo == "faq":
            valores = item.get("valores") or []
            linea = (
                f"[FAQ-{item.get('id', '?')}] tema: {item.get('tema', '?')} "
                f"| respuesta: {item.get('respuesta', '')}"
            )
            if valores:
                vals_txt = []
                for v in valores:
                    concepto = v.get("concepto", "?")
                    modalidad = v.get("modalidad", "?")
                    unidad = v.get("unidad", "")
                    cond = v.get("condicion", "")
                    if modalidad == "rango":
                        vals_txt.append(
                            f"{concepto} rango {v.get('monto_min','?')} a {v.get('monto_max','?')} {unidad}"
                            + (f" si {cond}" if cond else "")
                        )
                    else:
                        vals_txt.append(
                            f"{concepto} fijo {v.get('monto','?')} {unidad}"
                            + (f" si {cond}" if cond else "")
                        )
                linea += " | valores estructurados: " + " ; ".join(vals_txt)
            lines.append(linea)
        elif tipo == "proof":
            proof = item.get("proof", {})
            tool_name = item.get("tool", "?")
            formula = proof.get("formula", "?")
            ops_prod = proof.get("operandos_productos", [])
            ops_extra = proof.get("operandos_extras", [])
            resultado = proof.get("resultado") or f"min {proof.get('resultado_min','?')} max {proof.get('resultado_max','?')}"
            ops_prod_txt = ", ".join(f"{o.get('id')}={o.get('monto')}" for o in ops_prod) if ops_prod else "(sin productos)"
            ops_extra_txt = []
            for e in ops_extra:
                concepto = e.get("concepto", "?")
                if e.get("modalidad") == "rango":
                    ops_extra_txt.append(f"{concepto} rango {e.get('monto_min','?')} a {e.get('monto_max','?')}")
                else:
                    ops_extra_txt.append(f"{concepto} fijo {e.get('monto','?')}")
            ops_extra_str = ", ".join(ops_extra_txt) if ops_extra_txt else "(sin extras)"
            lines.append(
                f"[PROOF-{tool_name}] formula: {formula} | productos: {ops_prod_txt} | extras: {ops_extra_str} | resultado: {resultado}"
            )
        else:
            lines.append(f"[{item.get('id', '?')}] {json.dumps(item, ensure_ascii=False)}")

    return "\n".join(lines)


def check_claims(afirmaciones: list[dict],
                 evidence: list[dict],
                 trace_id: Optional[str] = None) -> list[dict]:
    log.info(f"check_claims INICIO afirmaciones={afirmaciones}")
    """
    Verifica cada afirmación contra la evidencia.

    Args:
        afirmaciones: lista de {"id", "texto", "tipo"} del Proposer
        evidence: lista de productos/FAQs recuperados durante la búsqueda
        trace_id: para logging correlacionado

    Returns:
        Lista de veredictos: [{"id", "veredicto", "evidencia_id", "razon"}, ...]
    """
    if not afirmaciones:
        log.info("checker_no_claims", trace_id=trace_id)
        return []

    afirmaciones_texto = "\n".join(
        f"- {a['id']}: {a['texto']}" for a in afirmaciones
    )

    evidencia_texto = _format_evidence(evidence)

    user_message = f"""EVIDENCIA DISPONIBLE:
{evidencia_texto}

AFIRMACIONES A VERIFICAR:
{afirmaciones_texto}

Devolvé el JSON con los veredictos."""

    messages = [
        {"role": "system", "content": CHECKER_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    try:
        result = llm_complete(
            messages=messages,
            role="checker",
            temperature=0.0,
            max_tokens=1000,
            trace_id=trace_id,
        )
    except Exception as e:
        log.error("checker_llm_error", trace_id=trace_id, error=str(e)[:200])
        # Si el Checker falla, devolvemos "sin_evidencia" para todas
        # (el Router de Confianza decidirá qué hacer)
        return [
            {"id": a["id"], "veredicto": "sin_evidencia",
             "evidencia_id": None, "razon": "checker_error"}
            for a in afirmaciones
        ]

    content = result.get("content", "").strip()

    if content.startswith("```"):
        content = content.split("```")[1] if "```" in content[3:] else content[3:]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as e:
        log.warning("checker_json_invalid", trace_id=trace_id,
                    error=str(e)[:100], content_preview=content[:200])
        return [
            {"id": a["id"], "veredicto": "sin_evidencia",
             "evidencia_id": None, "razon": "json_invalid"}
            for a in afirmaciones
        ]

    veredictos = parsed.get("veredictos", [])
    if not isinstance(veredictos, list):
        return [
            {"id": a["id"], "veredicto": "sin_evidencia",
             "evidencia_id": None, "razon": "no_list"}
            for a in afirmaciones
        ]

    # Asegurar que todas las afirmaciones tengan veredicto
    veredictos_por_id = {v.get("id"): v for v in veredictos if isinstance(v, dict)}
    final = []
    for a in afirmaciones:
        v = veredictos_por_id.get(a["id"])
        if not v or v.get("veredicto") not in ("soportada", "contradicha", "sin_evidencia"):
            final.append({
                "id": a["id"],
                "veredicto": "sin_evidencia",
                "evidencia_id": None,
                "razon": "missing_or_invalid",
            })
        else:
            final.append({
                "id": a["id"],
                "veredicto": v["veredicto"],
                "evidencia_id": v.get("evidencia_id"),
                "razon": v.get("razon", "")[:100],
            })

    soportadas = sum(1 for v in final if v["veredicto"] == "soportada")
    contradichas = sum(1 for v in final if v["veredicto"] == "contradicha")
    sin_evidencia = sum(1 for v in final if v["veredicto"] == "sin_evidencia")

    log.info("checker_ok", trace_id=trace_id,
             total=len(final), soportadas=soportadas,
             contradichas=contradichas, sin_evidencia=sin_evidencia)

    return final
