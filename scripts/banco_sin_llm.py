"""
BANCO SIN LLM — el espinazo entero SIN intérprete ni Solver, offline y gratis.

Cablea: ruteador por palabras clave (reemplaza al interprete) -> proveer (codigo)
-> construir_estado (codigo) -> responder_codigo (reemplaza al Solver). Cero
llamadas al modelo. Demuestra que el sistema puede responder consultas reales de
forma deterministica, y es la base del modo fallback + de las pruebas a escala.
"""
import csv
import sys
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CAT = []
with open(ROOT / "data/clientes/verifika_prod/productos.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        try:
            CAT.append({"id": row["id"].strip(), "nombre": row["nombre"].strip(),
                        "categoria": row["categoria"].strip().lower(),
                        "precio_ars": int(float(row["precio_ars"])),
                        "stock": int(row.get("stock", 0) or 0),
                        "color": (row.get("color") or "").strip().lower()})
        except (ValueError, KeyError):
            continue


def _norm(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s or "").lower())
                   if not unicodedata.combining(c))


def _fake_search(query=None, tienda_id=None, **kw):
    toks = [t for t in _norm(query).split() if len(t) > 2]
    scored = []
    for p in CAT:
        hay = _norm(p["nombre"] + " " + p["categoria"])
        sc = sum(1 for t in toks if t in hay)
        if sc:
            scored.append((sc, p))
    scored.sort(key=lambda x: -x[0])
    return {"productos": [p for _, p in scored[:10]], "encontrados": len(scored)}


import app.core.tools as T  # noqa: E402
import app.core.tools_context as TC  # noqa: E402
T.search_products = _fake_search
T.get_all_products = lambda tienda_id=None, force_refresh=False: CAT
_BYID = {p["id"]: p for p in CAT}
T.get_product_by_id = lambda pid, tienda_id=None: _BYID.get(str(pid))
T.get_categories = lambda tienda_id=None: sorted({p["categoria"] for p in CAT})
TC.set_current_tienda("verifika_prod")

from app.core.provider import proveer  # noqa: E402
from app.core.estado_pedido import construir_estado  # noqa: E402
from app.core.responder_codigo import responder  # noqa: E402

CATS = sorted({p["categoria"] for p in CAT})
_RE_CATALOGO = re.compile(r"(?i)\b(catalogo|catálogo|que categorias|mostrame todo)\b")
_RE_PRECIO = re.compile(r"(?i)\b(precio|cuanto|cuánto|cotiz|total|sale|vale)\b")


def rutear(msg):
    """Ruteador por palabras clave: arma el dict interpretacion sin LLM."""
    low = _norm(msg)
    inten = "pregunta_especifica" if _RE_PRECIO.search(msg) else "exploracion"
    return {"intencion": inten, "producto_resuelto": None,
            "candidatos": [], "confianza": 0.6}


def catalogo_texto(msg):
    if not _RE_CATALOGO.search(msg):
        return None
    from collections import Counter
    c = Counter(p["categoria"] for p in CAT)
    lineas = "\n".join(f"- {k} ({c[k]})" for k in CATS)
    return (f"Tenemos {len(CAT)} productos en estas categorias:\n{lineas}\n"
            "Decime cual te interesa y te paso los modelos y precios.")


MENSAJES = [
    "que teclados gamer tenes", "pasame precios de notebooks",
    "recomendame un mouse barato", "que monitores tenes para trabajar",
    "dame el catalogo", "que categorias tenes",
    "quiero una silla gamer", "tenes auriculares inalambricos",
    "precio de los parlantes", "mostrame tablets",
    "que ssd tenes", "memorias ram ddr5", "cuanto sale un router",
    "webcam para streaming", "impresoras epson",
]

ok = fallos = 0
print("=== BANCO SIN LLM — ruteador + proveer + estado + responder (cero LLM) ===\n")
for msg in MENSAJES:
    interp = rutear(msg)
    prov = proveer(msg, tienda_id="verifika_prod", registro=[], carrito=[],
                   localidad_memoria="", estado=None, interpretacion=interp)
    estado = construir_estado(prov, interpretacion=interp)
    resp = responder(prov, estado, msg, catalogo_texto=catalogo_texto(msg))
    tiene = bool(resp and ("$" in resp or "categorias" in resp.lower()))
    print(f"[{'OK ' if tiene else 'XX '}] {msg}")
    print(f"      {(resp or '(None - cae al puente)').strip()[:180]}")
    ok += tiene
    fallos += (not tiene)
print(f"\n=== {ok} con respuesta de datos, {fallos} sin datos ===")
sys.exit(1 if fallos else 0)
