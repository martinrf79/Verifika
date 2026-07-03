"""
RESPUESTAS CURADAS — el patron "LLM compila offline, runtime determinista".

Para los temas de FAQ mas preguntados, la TIENDA deja UNA respuesta aprobada
(campo `respuesta_curada` en faq.json, redactada por Martin en su voz, con
gancho de venta incluido). Cuando el turno es una pregunta PURA de politica y el
ruteo determinista matchea un tema curado, esa respuesta sale TAL CUAL: el
solver ni corre. Cero alucinacion posible (no se genera nada) y un turno mas
barato y mas rapido.

Los numeros NO viven en el texto curado: van como huecos {{concepto}} que el
codigo estampa desde los `valores` estructurados de la MISMA FAQ. Una tarifa que
cambia se cambia en el valor y la curada nunca queda vieja (una sola fuente).

Conservador como todo lo demas: el atajo actua SOLO cuando esta seguro —
pregunta pura (sin producto, sin carrito, sin cierre pendiente) y todos los
huecos resueltos. Ante cualquier duda devuelve None y el turno sigue por el
camino normal (solver + verificadores). Observabilidad: el llamador loguea
`interprete_libre_curada_servida` con el tema.
"""
import re

from app.logger import get_logger

log = get_logger(__name__)

_HUECO_RE = re.compile(r"\{\{(\w+)\}\}")

# Intenciones del interpretador con las que una pregunta pura de FAQ puede
# atajarse. Cualquier otra (decision_compra, aporta_dato, o interp caido) va al
# camino normal: en flujo de compra el solver contesta con todo el contexto.
_INTENCIONES_FAQ = {"pregunta_especifica", "posventa"}


def _money(n) -> str:
    try:
        return "$" + f"{int(round(n)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def _fmt_valor(v: dict) -> str | None:
    """Renderiza un valor estructurado como texto legible segun su unidad y
    modalidad. None si no hay forma segura de renderizarlo."""
    unidad = str(v.get("unidad") or "").strip().lower()
    if v.get("modalidad") == "rango":
        mn, mx = v.get("monto_min"), v.get("monto_max")
        if isinstance(mn, (int, float)) and isinstance(mx, (int, float)):
            return f"entre {_money(mn)} y {_money(mx)}"
        return None
    # Umbral (ej envio_gratis): el dato util no es el monto (0) sino el umbral.
    for k in ("umbral_ars", "base_ars"):
        u = v.get(k)
        if isinstance(u, (int, float)) and u > 0:
            return _money(u)
    m = v.get("monto")
    if not isinstance(m, (int, float)):
        return None
    if unidad == "porcentaje":
        return f"{int(m)}%"
    if unidad in ("", "ars", "pesos", "peso", "$"):
        return _money(m)
    # Cantidad no monetaria (cuotas, dias): el numero pelado.
    return str(int(m))


def estampar_valores(texto: str, faq_tema: dict) -> str | None:
    """Rellena cada hueco {{concepto}} con el valor estructurado de ese concepto
    en la MISMA FAQ. Si un hueco no resuelve, devuelve None: una curada a medias
    no se sirve (el turno cae al camino normal y queda el warning)."""
    valores = {str(v.get("concepto") or ""): v
               for v in (faq_tema.get("valores") or [])}

    fallo = []

    def _rep(m):
        v = valores.get(m.group(1))
        r = _fmt_valor(v) if v else None
        if r is None:
            fallo.append(m.group(1))
            return m.group(0)
        return r

    out = _HUECO_RE.sub(_rep, texto)
    if fallo:
        log.warning("curada_hueco_sin_valor", huecos=fallo[:5],
                    tema=faq_tema.get("tema"))
        return None
    return out


def servir_curada(mensaje: str, interp: dict | None, estado: dict | None,
                  pregunta_cierre_previa: bool, tienda_id: str,
                  ) -> tuple[str, str] | None:
    """Devuelve (tema, respuesta_estampada) si el turno se puede atajar con una
    respuesta curada; None en cualquier otro caso. Todas las condiciones son
    deterministas y conservadoras:
      - el ruteo por keywords (el MISMO de query_faq) matchea un tema curado;
      - el interprete ve una pregunta (no una compra en curso, no un dato);
      - no hay producto resuelto ni candidatos, ni carrito vigente, ni pregunta
        de cierre pendiente: nada de la venta en curso se pisa con un enlatado.
    """
    if pregunta_cierre_previa:
        return None
    if not isinstance(interp, dict) or not interp:
        return None
    if interp.get("intencion") not in _INTENCIONES_FAQ:
        return None
    if interp.get("producto_resuelto") or interp.get("candidatos"):
        return None
    if (estado or {}).get("carrito"):
        return None

    # Import perezoso: asi el doble de pruebas (sim_firestore) que parchea
    # firestore_client despues del import de este modulo igual nos alcanza.
    from app.storage.firestore_client import get_all_faq
    from app.core.tools import _faq_ranking_palabras
    faq = get_all_faq(tienda_id=tienda_id) or {}
    ranking = _faq_ranking_palabras(mensaje or "", faq)
    if not ranking:
        return None
    tema = ranking[0][1]
    data = faq.get(tema) or {}
    texto = str(data.get("respuesta_curada") or "").strip()
    if not texto:
        return None
    estampada = estampar_valores(texto, data)
    if not estampada:
        return None
    return tema, estampada
