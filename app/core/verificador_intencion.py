"""
VERIFICADOR DE INTENCION (nivel 2 del fiscal, 17-jul) — cruza la RESPUESTA
contra la lectura ESTRUCTURADA del turno. El codigo nunca razona sobre
lenguaje: el interprete ya tradujo el mensaje a estructura (preferencias,
tope, exclusiones) y aca solo se COMPARA estructura contra estructura.

Invariantes que fiscaliza:
  1. EXCLUSION VIOLADA: un producto ofrecido cuya marca o pais de marca esta
     excluido por el cliente. Aguas arriba el filtro de universo lo previene
     por construccion; esta es la red para los caminos que no pasan por ese
     filtro (compositor, memoria). Correccion QUIRURGICA: se saca la linea
     que nombra al producto excluido, solo si queda respuesta en pie; si no,
     se marca sin tocar (mejor una linea de mas que un turno mudo).
  2. TOPE SUPERADO: todo lo ofrecido queda arriba del tope de presupuesto
     del cliente. MARCA, no corrige: mostrar algo apenas arriba del tope
     avisando puede ser venta legitima; el evento en el log es la sonda para
     decidir si algun dia se endurece.

Determinista, sin LLM, sin llamadas nuevas. Los eventos van al log con
trace_id: son el radar de este fiscal.
"""
from app.logger import get_logger
from app.core.estado_venta import productos_de_meta
from app.core.generador_v2 import _pais_de_marca, _norm

log = get_logger(__name__)


def _producto_excluido(prod: dict, exclusiones: list[dict]) -> bool:
    """Mismo criterio que el filtro de universo (filtrar_por_preferencias):
    stem del valor contra la marca o el pais de la marca."""
    for e in exclusiones or []:
        stem = _norm(e.get("valor"))[:4]
        if not stem:
            continue
        if e.get("tipo") == "marca" and stem in _norm(prod.get("marca")):
            return True
        if e.get("tipo") == "origen":
            pais = _pais_de_marca(prod) or _norm(prod.get("origen"))
            if stem in pais:
                return True
    return False


def _quitar_lineas_con(texto: str, nombre: str) -> str:
    """Saca las lineas que nombran al producto (match por nombre completo
    normalizado dentro de la linea normalizada)."""
    n = _norm(nombre)
    lineas = [l for l in (texto or "").split("\n") if n not in _norm(l)]
    return "\n".join(lineas).strip()


def verificar_intencion(respuesta: str, meta: dict, prefs: dict,
                        tienda_id: str | None = None) -> dict:
    """Devuelve {'respuesta': texto (igual o corregido), 'eventos': [...]}.
    Nunca levanta: ante cualquier duda deja la respuesta como estaba."""
    out = {"respuesta": respuesta, "eventos": []}
    prefs = prefs if isinstance(prefs, dict) else {}
    exclusiones = [e for e in (prefs.get("exclusiones") or [])
                   if isinstance(e, dict) and e.get("valor")]
    tope = prefs.get("tope_presupuesto")
    if not exclusiones and not tope:
        return out
    try:
        from app.storage.firestore_client import get_product_by_id
        # Los dicts CRUDOS de las tools traen marca/origen; productos_de_meta
        # los normaliza a id/nombre/precio. Se juntan los dos: el catalogo
        # enriquece cuando el id resuelve, el crudo cubre el resto.
        crudos: dict[str, dict] = {}
        for tc in (meta or {}).get("tools_called", []) or []:
            res = tc.get("result")
            if not isinstance(res, dict):
                continue
            cands = list(res.get("productos") or [])
            if isinstance(res.get("producto"), dict):
                cands.append(res["producto"])
            for c in cands:
                if isinstance(c, dict) and c.get("id"):
                    crudos.setdefault(str(c["id"]).upper(), c)
        fichas = []
        for p in productos_de_meta(meta):
            ficha = (get_product_by_id(p["id"], tienda_id=tienda_id)
                     or crudos.get(p["id"]) or {})
            fichas.append({**p, **{k: ficha.get(k) for k in
                                   ("marca", "origen") if ficha.get(k)}})
        # 1. Exclusiones: poda quirurgica de la linea, si queda respuesta.
        texto = respuesta
        for p in fichas:
            if _producto_excluido(p, exclusiones):
                out["eventos"].append({"tipo": "exclusion_violada",
                                       "producto": p["nombre"]})
                podado = _quitar_lineas_con(texto, p["nombre"])
                if podado:
                    texto = podado
        if out["eventos"] and texto != respuesta:
            out["respuesta"] = texto
        # 2. Tope: marca cuando TODO lo ofrecido queda arriba del tope.
        if tope and fichas and all(p["precio"] > float(tope) for p in fichas):
            out["eventos"].append({"tipo": "tope_superado",
                                   "tope": int(tope),
                                   "minimo_ofrecido": min(p["precio"]
                                                          for p in fichas)})
    except Exception as e:  # red: el fiscal jamas rompe el turno
        log.warning("verificador_intencion_error", error=str(e)[:120])
    return out
