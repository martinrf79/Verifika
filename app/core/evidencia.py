"""
EVIDENCIA — arma la evidencia para el filtro determinista (verificador) desde los
resultados REALES de las tools que vio el solver, o sea lo que efectivamente leyo.
Modulo neutro que usa el camino vivo (interprete_libre). No relee el catalogo
entero; solo la FAQ, que es chica y esta cacheada.
"""
from app.storage.firestore_client import get_all_faq
from app.logger import get_logger

log = get_logger(__name__)

# Tools que devuelven productos del catalogo bajo distintas claves.
_TOOLS_CON_PRODUCTOS = (
    "search_products", "get_product_details", "find_within_budget",
    "compare_products", "recommend_product", "list_catalog",
)


def build_evidence_from_tools(tools_called: list[dict],
                              tienda_id: str,
                              productos_vistos: list[dict] | None = None
                              ) -> list[dict]:
    """
    Construye la evidencia a partir de los resultados de las tools.
    - Productos: de search/details/find/compare/recommend/list y el detalle de
      calculate_total.
    - FAQ: entra TODA la FAQ con sus valores estructurados, asi una afirmacion
      verdadera sobre un tema que el solver no consulto no cae como sin_evidencia.
    - Proofs: los calculos verificados de calculate_total y cotizar_envio.
    - Productos ya mostrados (productos_vistos): respaldan un precio que el bot ya
      mostro en turnos anteriores, para que el filtro no vete en falso.
    """
    productos_por_id: dict[str, dict] = {}
    faq_evidence: list[dict] = []
    proof_evidence: list[dict] = []

    def _add_producto(p: dict):
        if not isinstance(p, dict):
            return
        pid = str(p.get("id") or "").upper()
        if not pid or pid in productos_por_id:
            return
        productos_por_id[pid] = {"tipo": "producto", **p}

    for t in tools_called or []:
        name = t.get("name", "")
        res = t.get("result")
        proof = t.get("proof")
        if proof:
            proof_evidence.append({"tipo": "proof", "tool": name, "proof": proof})

        if not isinstance(res, dict):
            continue

        if name in _TOOLS_CON_PRODUCTOS:
            for p in res.get("productos", []) or []:
                _add_producto(p)
            if isinstance(res.get("producto"), dict):
                _add_producto(res["producto"])

        if name == "calculate_total":
            for d in res.get("detalle", []) or []:
                _add_producto(d)

    # FAQ entera como evidencia (chica y cacheada).
    try:
        faqs_full = get_all_faq(tienda_id=tienda_id)
        for tema_id, data in faqs_full.items():
            item = {
                "tipo": "faq",
                "id": tema_id,
                "tema": tema_id,
                "respuesta": data.get("respuesta", ""),
                "faq_tipo": data.get("tipo", "informativo"),
            }
            if data.get("valores"):
                item["valores"] = data["valores"]
            faq_evidence.append(item)
    except Exception as e:
        log.warning("evidencia_full_faq_failed", error=str(e)[:100])

    for p in productos_vistos or []:
        _add_producto(p)

    return list(productos_por_id.values()) + faq_evidence + proof_evidence
