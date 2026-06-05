"""
GATE POR GRAVEDAD — el puente entre la politica (constitucion) y el mecanismo
general de grounding (el Checker de Verifika).

El Checker descompone la respuesta en afirmaciones atomicas tipadas (precio,
producto, stock, caracteristica, politica) y dictamina cada una contra la
evidencia: soportada, contradicha o sin_evidencia. Pero el Router de Confianza
de Verifika decide por un PUNTAJE global (soportadas/total), que es ciego a la
GRAVEDAD: un solo producto inventado entre cuatro datos buenos da score 0.8 y
pasa. Y trata igual a un precio que a una descripcion.

Esta pieza decide por gravedad, no por puntaje, siguiendo la constitucion:
- contradicha de CUALQUIER tipo bloquea. La evidencia la contradice: es la
  senal mas fuerte (promesa de dia que extiende el plazo de la FAQ, numero
  cambiado, condicion inventada).
- sin_evidencia bloquea SOLO en los tipos de alta gravedad donde inventar es
  grave: precio, stock, PRODUCTO que no existe, politica. Asi caza el producto
  inventado ("Redragon Dragonborn") que el puntaje global dejaba pasar.
- sin_evidencia de caracteristica u otro NO bloquea: un spec que la evidencia
  recortada no lista se deja pasar (lo cubre la honestidad del prompt), para no
  falsos-positivar, leccion del red-team.

Codigo puro, sin LLM. Es el Nivel 1 (politica declarativa) aplicado sobre la
salida del Nivel 2 (mecanismo de verificacion). Agregar o mover una clase de
gravedad es editar SIN_EVIDENCIA_BLOQUEA o la constitucion, no el motor.
"""
from typing import Optional

from app.logger import get_logger

log = get_logger(__name__)

# Tipos de afirmacion cuyo veredicto sin_evidencia YA bloquea, no solo el
# contradicha. AJUSTADO CON DATOS (diag comprador_apurado, scripts/diag_checker):
# bloquear todo sin_evidencia de alta gravedad sobre-bloqueaba 7 de 8 turnos. El
# culpable era 'politica' (y 'stock'): frases operativas RAZONABLES como
# "despachamos en el dia si pagas hoy" o "te paso el numero de seguimiento" no
# estan LITERAL en la FAQ, el Checker las marca sin_evidencia, y bloquearlas
# convierte al bot en un disco rayado de "dejame consultar". sin_evidencia es
# senal DEBIL: solo significa "la evidencia no lo menciona", no "es mentira".
# Por eso aca queda SOLO 'producto': un nombre de producto que no aparece en la
# evidencia es un invento concreto (caso Dragonborn) y en el diag no dio NI UN
# falso positivo. El resto se cubre con senal fuerte:
#   - numeros sin respaldo  -> verificador determinista de plata (linea cero)
#   - promesa de dia / plazo -> verificador_hechos determinista
#   - servicio inventado     -> verificador_servicios determinista
#   - politica/condicion cambiada o extendida -> el Checker la marca CONTRADICHA
#     (no sin_evidencia), y la contradicha SI bloquea siempre, abajo.
# Mover una clase aca es una decision de POLITICA, una linea, no tocar el motor.
SIN_EVIDENCIA_BLOQUEA = frozenset({"producto"})


def decidir_gate(veredictos: list[dict],
                 afirmaciones: list[dict],
                 sin_evidencia_bloquea: Optional[frozenset] = None,
                 trace_id: Optional[str] = None) -> dict:
    """Decide si bloquear segun gravedad, sobre los veredictos del Checker.

    Args:
        veredictos: lista del Checker [{id, veredicto, razon, ...}].
        afirmaciones: lista del Proposer [{id, texto, tipo}].
        sin_evidencia_bloquea: override del set de tipos que bloquean por
            sin_evidencia. Default SIN_EVIDENCIA_BLOQUEA.

    Returns:
        {bloquear: bool, problemas: [{id, tipo, motivo, texto, razon}]}
        motivo es 'contradicha' o 'sin_evidencia_alta'.
    """
    sin_ev = sin_evidencia_bloquea if sin_evidencia_bloquea is not None \
        else SIN_EVIDENCIA_BLOQUEA
    tipo_por_id = {a.get("id"): (a.get("tipo") or "otro") for a in (afirmaciones or [])}
    texto_por_id = {a.get("id"): a.get("texto", "") for a in (afirmaciones or [])}

    problemas: list[dict] = []
    for v in (veredictos or []):
        ver = v.get("veredicto")
        vid = v.get("id")
        tipo = tipo_por_id.get(vid, "otro")
        motivo = None
        if ver == "contradicha":
            motivo = "contradicha"
        elif ver == "sin_evidencia" and tipo in sin_ev:
            motivo = "sin_evidencia_alta"
        if motivo:
            problemas.append({
                "id": vid,
                "tipo": tipo,
                "motivo": motivo,
                "texto": texto_por_id.get(vid, ""),
                "razon": (v.get("razon") or "")[:120],
            })

    bloquear = bool(problemas)
    log.info("gate_gravedad", trace_id=trace_id, bloquear=bloquear,
             problemas=[f"{p['tipo']}:{p['motivo']}" for p in problemas])
    return {"bloquear": bloquear, "problemas": problemas}


def textos_no_respaldados(gate: dict) -> list[str]:
    """Helper para el autofix: los textos de afirmaciones problematicas, para
    listarselos al Solver y que rehaga sin inventar."""
    return [p["texto"] for p in gate.get("problemas", []) if p.get("texto")]
