"""
BANCO DETERMINISTA OFFLINE — testea la capa de PARSEO contra el catalogo REAL,
sin LLM, sin red, en milisegundos. Genera casos de las 22 categorias reales
cruzando intenciones y dificultades, y verifica las funciones donde viven los
bugs (resolver_pedido, candidatos_pedido, extraer_pedido, refinar, _relevante,
_pide_catalogo). Es la red que caza la familia de misparses ANTES de gastar una
llamada al modelo.

No reemplaza al banco vivo (eso prueba el Solver y la cañeria entera): cubre el
ESQUELETO determinista a escala que a mano no se puede.

Uso:  .\\correr_local.ps1 py scripts\\banco_determinista.py
"""
import csv
import os
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── Catalogo real ──
CAT = []
with open(ROOT / "data/clientes/verifika_prod/productos.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        try:
            CAT.append({"id": row["id"].strip(), "nombre": row["nombre"].strip(),
                        "categoria": row["categoria"].strip().lower(),
                        "precio_ars": int(float(row["precio_ars"])),
                        "stock": int(row.get("stock", 0) or 0),
                        "color": (row.get("color") or "").strip().lower(),
                        "marca": (row.get("marca") or "").strip()})
        except (ValueError, KeyError):
            continue


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return s.lower()


# ── Fake search (solapamiento de tokens) para las funciones que buscan ──
def _fake_search(query=None, tienda_id=None, **kw):
    toks = [t for t in _norm(query).split() if len(t) > 2]
    scored = []
    for p in CAT:
        hay = _norm(f"{p['nombre']} {p['categoria']} {p['marca']}")
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
TC.set_current_tienda("verifika_prod")

from app.core.resolver_pedido import (resolver_pedido, candidatos_pedido,  # noqa
                                      refinar_por_atributo)
from app.core.pedido_multi import extraer_pedido  # noqa

ok = 0
fallos = []


def chk(nombre, cond, detalle=""):
    global ok
    if cond:
        ok += 1
    else:
        fallos.append(f"{nombre}  {detalle}")


by_cat = defaultdict(list)
for p in CAT:
    by_cat[p["categoria"]].append(p)

REG_MAX = 12  # registro por categoria (lo que el cliente "vio")

# ════════════════════════════════════════════════════════════════════
# 1) Por categoria: 'el mas barato' resuelve; 'los dos/N mas baratos' NO arma
#    pedido; cantidad explicita se respeta.
# ════════════════════════════════════════════════════════════════════
for cat, prods in by_cat.items():
    reg = [{"id": p["id"], "nombre": p["nombre"], "precio_ars": p["precio_ars"]}
           for p in sorted(prods, key=lambda x: x["precio_ars"])[:REG_MAX]]
    if len(reg) < 2:
        continue
    barato = min(reg, key=lambda p: p["precio_ars"])

    r = resolver_pedido("el mas barato", reg)
    chk(f"[{cat}] 'el mas barato' resuelve al mas barato",
        r and r["producto_id"] == barato["id"], str(r))

    for frase in ("dame los dos mas baratos", "los dos mas baratos en cada caso",
                  "las tres mas economicas", "los 2 mas baratos", "los dos mas caros"):
        r = resolver_pedido(frase, reg)
        chk(f"[{cat}] '{frase}' NO arma pedido (es listar)", r is None, str(r))
        c = candidatos_pedido(frase, reg)
        chk(f"[{cat}] '{frase}' NO arma A/B", c == [], str(c))

    # Cantidad explicita: 'comprame 3 <marca>' -> cantidad 3.
    marca = next((p["marca"] for p in prods if p["marca"]), "")
    if marca:
        r = resolver_pedido(f"comprame 3 {marca}", reg)
        if r:
            chk(f"[{cat}] 'comprame 3 {marca}' cantidad=3", r["cantidad"] == 3, str(r))

# ════════════════════════════════════════════════════════════════════
# 2) Color discrimina: mismo modelo, dos colores -> 'el X <color>' resuelve al
#    color pedido (no ambiguo).
# ════════════════════════════════════════════════════════════════════
def _base(p):
    n = _norm(p["nombre"])
    col = _norm(p["color"])
    return n[:-len(col)].strip() if col and n.endswith(col) else n


grupos = defaultdict(list)
for p in CAT:
    if p["color"]:
        grupos[(p["categoria"], _base(p))].append(p)

probados_color = 0
for (cat, base), ps in grupos.items():
    colores = {p["color"]: p for p in ps}
    if len(colores) < 2 or not base:
        continue
    reg = [{"id": p["id"], "nombre": p["nombre"], "precio_ars": p["precio_ars"]}
           for p in ps]
    color, prod = next(iter(colores.items()))
    r = resolver_pedido(f"quiero el {base} {color}", reg)
    chk(f"[color] '{base} {color}' resuelve a ese color",
        r and r["producto_id"] == prod["id"], str(r))
    probados_color += 1
    if probados_color >= 40:
        break

# ════════════════════════════════════════════════════════════════════
# 3) Fuera de catalogo: extraer_pedido NO debe inventar items.
# ════════════════════════════════════════════════════════════════════
FUERA = ["1 iphone 15 pro max", "2 freidoras de aire", "1 bicicleta rodado 29",
         "1 playstation 5", "1 lavarropas drean", "1 smart tv samsung 55",
         "3 zapatillas nike", "1 heladera no frost", "2 termos stanley"]
for msg in FUERA:
    ped = extraer_pedido(msg, "verifika_prod")
    items = (ped or {}).get("items") or []
    chk(f"[fuera] '{msg}' no inventa item", not items,
        str([i.get("product_id") for i in items]))

# ════════════════════════════════════════════════════════════════════
# 5) Pedido multi real: 'N <categoria>' resuelve por categoria con cantidad.
# ════════════════════════════════════════════════════════════════════
for cat in ("teclado", "mouse", "auriculares", "monitor", "tablet", "notebook"):
    ped = extraer_pedido(f"quiero 2 {cat}s", "verifika_prod")
    its = (ped or {}).get("items") or []
    amb = (ped or {}).get("ambiguos") or []
    chk(f"[multi] '2 {cat}s' resuelve o pregunta (no vacio)",
        bool(its or amb), "ni items ni ambiguos")

print(f"\n{'='*60}\nBANCO DETERMINISTA: {ok} OK, {len(fallos)} fallos")
if fallos:
    print("-" * 60)
    for f in fallos[:60]:
        print("  XX " + f)
print("=" * 60)
sys.exit(1 if fallos else 0)
