"""ESTAMPADO DE LA FAQ CURADA — los numeros nunca viven en el texto."""
import re

from app.logger import get_logger
from app.core.calculadora import _money

log = get_logger(__name__)

_HUECO_RE = re.compile(r"\{\{(\w+)\}\}")


def _fmt_valor(v: dict) -> str | None:
    """Renderiza un valor estructurado como texto legible segun su unidad y modalidad."""
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
    """Rellena cada hueco {{concepto}} con el valor estructurado de ese concepto en la MISMA FAQ."""
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
