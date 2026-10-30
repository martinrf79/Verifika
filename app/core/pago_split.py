"""SPLIT DE PAGO — reparte un total entre varios medios de pago y aplica el descuento por transferencia a la
parte que corresponde."""
import re

from app.core.filtros_catalogo import _norm

# Las palabras de la condicion que no nombran un medio: "PAGO por transferencia"
# no puede hacer que "Mercado PAGO" lleve el descuento.
_NO_NOMBRAN = {"pago", "pagos", "pagar", "pagando", "abonar", "abonando", "compra", "compras",
               "con", "por", "del", "de", "en", "el", "la", "los", "las", "local"}


def _palabras(t: str) -> set:
    return {w for w in re.findall(r"[a-z]+", _norm(t).replace("_", " ")) if len(w) > 3} - _NO_NOMBRAN


def lleva_descuento(medio: str, condicion: str) -> bool:
    """True si el medio nombra lo que dice la condicion del descuento."""
    return bool(_palabras(medio) & _palabras(condicion))


def _money(n) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def descuento_de(tienda_id: str) -> tuple:
    """(porcentaje, condicion) del descuento por transferencia, de la FAQ de la tienda."""
    try:
        from app.storage.firestore_client import get_all_faq
        vt = (((get_all_faq(tienda_id=tienda_id) or {}).get("descuento_transferencia")
               or {}).get("valores") or [])
        dv = next((v for v in vt if (v.get("unidad") or "").lower() == "porcentaje"), None)
        if dv:
            return int(dv.get("monto", 0)), str(dv.get("condicion") or "")
    except Exception as e:  # noqa: BLE001 — sin FAQ el reparto va sin descuento
        from app.logger import get_logger
        get_logger(__name__).warning("descuento_de_faq_error", error=str(e)[:150])
    return 0, ""


def calcular_split(base_ars: int, pago: list[dict],
                   pct_descuento: int, condicion: str) -> dict:
    """Reparte base_ars entre los medios de `pago` y aplica el descuento a la parte cuyo medio nombra la
    `condicion` del descuento. pago: lista de {"medio": str, "porcentaje": number}."""
    if not base_ars or base_ars <= 0:
        return {"ok": False, "motivo": "base invalida"}
    partes_in = [p for p in (pago or [])
                 if isinstance(p, dict) and p.get("medio")]
    if not partes_in:
        return {"ok": False, "motivo": "sin medios de pago"}
    try:
        pcts = [float(p.get("porcentaje") or 0) for p in partes_in]
    except (TypeError, ValueError):
        return {"ok": False, "motivo": "porcentaje no numerico"}
    if any(x <= 0 for x in pcts):
        return {"ok": False, "motivo": "porcentaje cero o negativo"}
    if abs(sum(pcts) - 100) > 1:
        return {"ok": False,
                "motivo": f"los porcentajes suman {sum(pcts):g}, no 100"}

    # Montos por medio; el último absorbe el redondeo para que la suma cierre EXACTA.
    partes: list[dict] = []
    acumulado = 0
    for i, (p, pct) in enumerate(zip(partes_in, pcts)):
        if i < len(partes_in) - 1:
            monto = round(base_ars * pct / 100)
        else:
            monto = base_ars - acumulado  # cierra exacto
        acumulado += monto
        es_transf = lleva_descuento(p["medio"], condicion)
        desc = round(monto * pct_descuento / 100) if es_transf else 0
        partes.append({
            "medio": str(p["medio"]).strip(),
            "porcentaje": pct,
            "monto_ars": monto,
            "es_transferencia": es_transf,
            "descuento_ars": desc,
            "monto_final_ars": monto - desc,
        })

    desc_total = sum(p["descuento_ars"] for p in partes)
    return {
        "ok": True,
        "partes": partes,
        "pct_descuento": pct_descuento,
        "descuento_total_ars": desc_total,
        "total_final_ars": base_ars - desc_total,
    }


def render_split(split: dict) -> str:
    """Bloque de texto del split, para estampar como dato sellado. "" si no ok."""
    if not split.get("ok"):
        return ""
    lineas = ["Pago dividido:"]
    for p in split["partes"]:
        pct = f"{p['porcentaje']:g}%"
        if p["es_transferencia"] and p["descuento_ars"]:
            lineas.append(
                f"- {p['medio']} ({pct}): ${_money(p['monto_ars'])} "
                f"- {split['pct_descuento']}% descuento = "
                f"${_money(p['monto_final_ars'])}")
        else:
            lineas.append(f"- {p['medio']} ({pct}): ${_money(p['monto_ars'])}")
    lineas.append(f"Total final: ${_money(split['total_final_ars'])}")
    return "\n".join(lineas)
