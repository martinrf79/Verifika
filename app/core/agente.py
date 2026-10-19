"""LAS HERRAMIENTAS SOBRE EL MOTOR —el indice de la tienda, el rubro, la cuenta, el envio y la compatibilidad—
(26-sep-2026; el 19-oct quedo solo lo que usa el flujo, `app/core/flujo/`)."""
import contextvars
import json
import re
import unicodedata

from app.logger import get_logger

log = get_logger(__name__)

# EL TRACE DEL TURNO LLEGA HASTA EL MOTOR.
_TRACE: contextvars.ContextVar = contextvars.ContextVar("agente_trace", default="agente")


def _trace() -> str:
    return _TRACE.get()


def _n(t) -> str:
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _tokens(t) -> set:
    ws = {w for w in re.findall(r"[a-z0-9]+", _n(t)) if len(w) > 2}
    return ws | {w[:5] for w in ws if len(w) > 5}


# ══ EL INDICE: rubros, temas y campos, con sus alias ═══════════════════════

_INDICES: dict = {}


def _alias(tienda_id: str) -> dict:
    """Los alias de la tienda. Sin archivo, el indice anda igual con los
    nombres y los tags: los alias suman, no son condicion."""
    from pathlib import Path
    ruta = Path(__file__).resolve().parents[2] / "data" / "clientes" / tienda_id / "alias.json"
    if not ruta.exists():
        log.warning("agente_sin_alias", tienda_id=tienda_id)
        return {}
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def indice(tienda_id: str) -> dict:
    """Las bolsas de palabras por rubro, tema y campo."""
    if tienda_id in _INDICES:
        return _INDICES[tienda_id]
    from app.core.filtros_catalogo import campos_filtrables, recorrida
    from app.storage.firestore_client import get_all_faq, get_all_products
    al = _alias(tienda_id)
    rubros: dict = {}
    for c, _ in recorrida(tienda_id).get("categorias") or []:
        rubros[c] = {"nombre": _tokens(c), "alias": set()}
        for a in (al.get("rubros") or {}).get(c, []):
            rubros[c]["alias"] |= _tokens(a)
    for p in get_all_products(tienda_id=tienda_id) or []:
        c = p.get("categoria")
        if c in rubros:
            rubros[c]["alias"] |= _tokens(p.get("tags") or "")
    temas: dict = {}
    faq = get_all_faq(tienda_id=tienda_id) or {}
    for t, d in (faq.items() if isinstance(faq, dict) else []):
        kw = " ".join((d or {}).get("keywords") or []) if isinstance(d, dict) else ""
        temas[t] = {"nombre": _tokens(t.replace("_", " ")),
                    "alias": _tokens(kw + " " + " ".join((al.get("temas") or {}).get(t, []))),
                    "frases": [_n(k) for k in ((d or {}).get("keywords") or []) if isinstance(d, dict)
                               and len(_n(k)) > 3]}
    campos = {c: {"nombre": _tokens(c.replace("_", " ")),
                  "alias": _tokens(" ".join((al.get("campos") or {}).get(c, [])))}
              for c in campos_filtrables(tienda_id)}
    _INDICES[tienda_id] = {"rubros": rubros, "temas": temas, "campos": campos}
    return _INDICES[tienda_id]


def ubicar(texto: str, grupo: str, tienda_id: str, n: int = 3) -> list:
    """Los mejores candidatos de un grupo para las palabras del modelo."""
    q = _tokens(texto)
    if not q:
        return []
    puntos = []
    for clave, b in indice(tienda_id)[grupo].items():
        s = 2 * len(q & b["nombre"]) + len(q & b["alias"])
        if s:
            puntos.append((s, clave))
    puntos.sort(key=lambda x: (-x[0], x[1]))
    return [c for _, c in puntos[:n]]


def _rubro(texto: str, tienda_id: str):
    """El rubro de la tienda para lo que escribio el modelo: exacto, ubicado, o None."""
    if not texto:
        return None, []
    nombres = list(indice(tienda_id)["rubros"])
    exacto = next((r for r in nombres if _n(r) == _n(texto)), None)
    if exacto:
        return exacto, []
    cand = ubicar(texto, "rubros", tienda_id)
    return (cand[0] if cand else None), cand


# ══ LAS HERRAMIENTAS ════════════════════════════════════════════════════════

def _motor():
    from app.core import motor
    return motor


def h_envio(tienda_id: str, destinos=None, **_) -> dict:
    ds = [d for d in (destinos or []) if str(d).strip()]
    r = _motor().buscar([], tienda_id, _trace(), envios=[{"destino": d} for d in ds])
    return r.get("envios") or {"veredicto": "sin_tarifa", "destinos": ds}


def h_compatibilidad(tienda_id: str, producto: str = "", con: str = "", **_) -> dict:
    r = _motor().buscar([], tienda_id, _trace(), compat=[{"producto": producto, "con": con}])
    return {"compatibilidad": r.get("compatibilidad") or {"veredicto": "sin_dato"}}


def h_cuenta(tienda_id: str, items=None, destino: str = "", reparto_pago=None, destinos=None, **_) -> dict:
    its = [{"id": str(i.get("producto") or i.get("id") or ""), "cantidad": int(i.get("cantidad") or 1)}
           for i in (items or []) if isinstance(i, dict)]
    # UN ENVIO POR DESTINO (1-oct): "un mouse a Rosario y el resto a Concordia" son dos envios.
    ds = [str(d) for d in (destinos or []) if str(d).strip()] or ([destino] if destino else [])
    r = _motor().buscar([], tienda_id, _trace(), cuenta={"items": its},
                        envios=[{"destino": d, "va": "todo"} for d in ds] or None,
                        reparto_pago=reparto_pago or None)
    out = {"cuenta": r.get("cuenta") or {"veredicto": "sin_total"}}
    if r.get("envios"):
        out["envio"] = r["envios"]
    return out


HERRAMIENTAS = {"envio": h_envio, "compatibilidad": h_compatibilidad, "cuenta": h_cuenta}


def ejecutar(nombre: str, args: dict, tienda_id: str) -> dict:
    f = HERRAMIENTAS.get(nombre)
    if not f:
        return {"error": f"no existe la herramienta {nombre}"}
    try:
        return f(tienda_id, **(args or {}))
    except Exception as e:  # noqa: BLE001 — una herramienta que falla no deja al bot mudo
        log.warning("agente_herramienta_error", herramienta=nombre, error=f"{type(e).__name__}: {str(e)[:160]}")
        return {"error": "la consulta fallo; proba con otras palabras"}
