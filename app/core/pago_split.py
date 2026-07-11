"""
SPLIT DE PAGO — reparte un total entre varios medios de pago y aplica el
descuento por transferencia a la parte que corresponde.

UNA sola función genérica, no una por variante: recibe una lista de medios con su
porcentaje y cubre cualquier combinación (50/50, 70/30, 60/40, tres medios, los
que sean) mientras sumen 100. El código dueña TODA la cuenta; el solver no
calcula ni una cifra.

Regla de negocio (Martín, 6-jul): todo medio que NO sea Mercado Pago cuenta como
transferencia y lleva el descuento; solo Mercado Pago queda afuera. El porcentaje
de descuento sale de la FAQ descuento_transferencia, no hardcodeado.

Lógica pura, determinista, sin LLM ni Firestore (los datos entran por parámetro).
"""
import unicodedata


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def es_mercado_pago(medio: str) -> bool:
    """True si el medio es Mercado Pago (único que NO lleva descuento). Todo lo
    demás (transferencia, Ualá, billeteras, etc.) cuenta como transferencia.
    Tolera guion bajo ('mercado_pago'): sin esto, el split del 11-jul le
    aplico el descuento a la mitad de Mercado Pago (error de PLATA)."""
    m = _norm(medio).replace("_", " ").replace("-", " ")
    return "mercado pago" in m or "mercadopago" in m or m in ("mp", "mercado")


def _money(n) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def calcular_split(base_ars: int, pago: list[dict],
                   pct_descuento: int) -> dict:
    """Reparte base_ars entre los medios de `pago` y aplica el descuento por
    transferencia a la parte que no es Mercado Pago.

    pago: lista de {"medio": str, "porcentaje": number}. Los porcentajes deben
        sumar 100 (se tolera ±1 por redondeo). Cubre cualquier reparto.
    pct_descuento: porcentaje de descuento por transferencia (de la FAQ).

    Devuelve {ok, partes:[{medio, porcentaje, monto_ars, es_transferencia,
    descuento_ars, monto_final_ars}], descuento_total_ars, total_final_ars}.
    ok False con motivo si el reparto no es válido (no se inventa una cuenta)."""
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
        es_transf = not es_mercado_pago(p["medio"])
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


# ── SPLIT DICHO EN EL MENSAJE (charla real 11-jul 17:22) ─────────────────────
# "Decime mitad transferencia y mitad mercado pago como quedaria" con el
# presupuesto ya sellado respondia "¿que producto estas mirando?": la cuenta
# existia (calcular_split) pero nada la disparaba desde el mensaje. Parser
# DETERMINISTA y conservador: solo reconoce un reparto entre transferencia y
# Mercado Pago con mitades o porcentajes que suman 100; ante cualquier otra
# cosa devuelve None y el turno sigue por el camino normal.
import re as _re

_RE_MITAD_SPLIT = _re.compile(r"\bmitad\b")
_RE_PCT_MEDIO = _re.compile(
    r"(\d{1,3})\s*(?:%|por ?ciento)?\s*(?:por |con |en |de )?"
    r"(transferencia|mercado ?pago|mercadopago)")


def pago_de_mensaje(mensaje: str) -> list[dict] | None:
    """[{medio, porcentaje}] si el mensaje reparte el pago entre transferencia
    y Mercado Pago; None si no. Formas cubiertas: 'mitad transferencia y
    mitad mercado pago' (cualquier orden) y '70 transferencia y 30 mercado
    pago' (con o sin %). Ambos medios tienen que estar nombrados."""
    m = _norm(mensaje)
    tiene_transf = "transferencia" in m
    tiene_mp = "mercado pago" in m or "mercadopago" in m
    if not (tiene_transf and tiene_mp):
        return None
    if _RE_MITAD_SPLIT.search(m):
        return [{"medio": "transferencia", "porcentaje": 50},
                {"medio": "mercado pago", "porcentaje": 50}]
    pares = _RE_PCT_MEDIO.findall(m)
    if len(pares) == 2:
        (n1, m1), (n2, m2) = pares
        try:
            p1, p2 = int(n1), int(n2)
        except ValueError:
            return None
        if abs(p1 + p2 - 100) <= 1 and _norm(m1) != _norm(m2):
            return [{"medio": _norm(m1), "porcentaje": p1},
                    {"medio": _norm(m2), "porcentaje": p2}]
    return None
