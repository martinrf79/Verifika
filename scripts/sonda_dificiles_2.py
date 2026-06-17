"""
SONDA DIFICILES 2 — prueba OFFLINE (sin LLM, sin red) el subconjunto de la tanda
adversaria que estresa la CAPA DETERMINISTA de parseo: el riesgo es que el codigo
arme un pedido/total fantasma, resuelva mal, o no rechace lo que no existe. Lo
behavioral (jailbreak, fraude, sarcasmo) NO se prueba aca: eso es el banco vivo.

Reusa el mismo montaje que banco_determinista: catalogo real + fake_search.
Llama resolver_pedido / candidatos_pedido / extraer_pedido directos (lo que el
PROVIDER corre en prod) y asevera el comportamiento esperado por clase.

Uso:  .\\correr_local.ps1 py scripts\\sonda_dificiles_2.py
"""
import csv
import sys
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
                        "color": (row.get("color") or "").strip().lower(),
                        "marca": (row.get("marca") or "").strip()})
        except (ValueError, KeyError):
            continue


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return s.lower()


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

from app.core.resolver_pedido import resolver_pedido, candidatos_pedido  # noqa: E402
from app.core.pedido_multi import extraer_pedido  # noqa: E402

ok = 0
fallos = []


def chk(nombre, cond, detalle=""):
    global ok
    if cond:
        ok += 1
    else:
        fallos.append(f"{nombre}  ::  {detalle}")


def reg_por(query, cap=8):
    """Registro = lo que el cliente habria visto al buscar (search del catalogo)."""
    res = _fake_search(query=query)
    return [{"id": p["id"], "nombre": p["nombre"], "precio_ars": p["precio_ars"]}
            for p in res["productos"][:cap]]


def buscar_uno(query):
    res = _fake_search(query=query)
    return res["productos"][0] if res["productos"] else None


# ════════════════════════════════════════════════════════════════════
# CLASE A — preguntas de USO ABSURDO / ATRIBUTO no deben armar pedido/A-B
#   fantasma. El producto se resuelve (es real) o se deja al Solver; nunca
#   sale un foco/A-B inventado por la pregunta.
# ════════════════════════════════════════════════════════════════════
reg_router = reg_por("router tplink deco")
chk("A1 'viene con plato giratorio?' no arma A/B",
    candidatos_pedido("viene con plato giratorio o lo compro aparte?", reg_router) == [],
    str(candidatos_pedido("viene con plato giratorio o lo compro aparte?", reg_router)))

reg_tablet = reg_por("tablet samsung")
chk("A2 'se vuelve una compu cuantica? o explota la bateria?' no arma A/B",
    candidatos_pedido("se vuelve una compu cuantica o explota la bateria?", reg_tablet) == [],
    str(candidatos_pedido("se vuelve una compu cuantica o explota la bateria?", reg_tablet)))

# ════════════════════════════════════════════════════════════════════
# CLASE B — superlativo 'lo mas caro' resuelve al producto mas caro del
#   registro (no a uno cualquiera, no None).
# ════════════════════════════════════════════════════════════════════
reg_amplio = [{"id": p["id"], "nombre": p["nombre"], "precio_ars": p["precio_ars"]}
              for p in sorted(CAT, key=lambda x: x["precio_ars"])[-10:]]
mas_caro = max(reg_amplio, key=lambda p: p["precio_ars"])
r = resolver_pedido("vendeme lo mas caro que tengas, un solo producto", reg_amplio)
chk("B1 'lo mas caro' resuelve al mas caro",
    r and r["producto_id"] == mas_caro["id"], str(r))

# ════════════════════════════════════════════════════════════════════
# CLASE C — cantidad ALTA (mayorista) se respeta, no se degrada a 1. La
#   cantidad vive en items (si un solo modelo) o en ambiguos (si varios
#   modelos -> el bot pregunta cual, sin perder el 50/15).
# ════════════════════════════════════════════════════════════════════
def _cantidades(ped):
    its = (ped or {}).get("items") or []
    amb = (ped or {}).get("ambiguos") or []
    return [i.get("cantidad") for i in its] + [a.get("cantidad") for a in amb]


chk("C1 '50 impresoras' conserva cantidad 50",
    50 in _cantidades(extraer_pedido("quiero 50 impresoras epson ecotank", "verifika_prod")),
    str(_cantidades(extraer_pedido("quiero 50 impresoras epson ecotank", "verifika_prod"))))

chk("C2 '15 sillas' conserva cantidad 15",
    15 in _cantidades(extraer_pedido("quiero 15 sillas gamer noblechairs", "verifika_prod")),
    str(_cantidades(extraer_pedido("quiero 15 sillas gamer noblechairs", "verifika_prod"))))

# ════════════════════════════════════════════════════════════════════
# CLASE D — fuera de catalogo (absurdo) no inventa item.
# ════════════════════════════════════════════════════════════════════
for msg in ["1 playstation 5 con fifa 26", "1 seguro de vida",
            "1 bicicleta usada", "1 microondas con plato giratorio"]:
    ped = extraer_pedido(msg, "verifika_prod")
    items = (ped or {}).get("items") or []
    chk(f"D '{msg}' no inventa item", not items,
        str([i.get("nombre") for i in items]))

# ════════════════════════════════════════════════════════════════════
# CLASE E — el precio sale de la FUENTE, inmune al ruido aritmetico del
#   cliente ('multiplicalo x pi', 'restale la raiz de 144') y al lowball
#   ('te doy 30 mil por el que vale 163mil'): resolver devuelve el precio
#   real del catalogo, no el numero que tipeo el cliente.
# ════════════════════════════════════════════════════════════════════
# Registro de UN solo producto (sin ambiguedad) para aislar la propiedad de
# precio: lo que el cliente tipea ('x pi', '30 mil') nunca debe ser el precio.
real_ram = buscar_uno("memoria ram corsair vengeance ddr5")
reg_ram = [{"id": real_ram["id"], "nombre": real_ram["nombre"],
            "precio_ars": real_ram["precio_ars"]}]
r = resolver_pedido("dame esa memoria, multiplicalo x pi y restale la raiz de 144",
                    reg_ram)
chk("E1 ruido aritmetico no altera el precio (precio = fuente)",
    r and r["precio_ars"] == real_ram["precio_ars"]
    and str(r["precio_ars"]) not in ("3", "144"),
    f"resolvio={r} real={real_ram.get('precio_ars')}")

real_mouse = buscar_uno("mouse logitech g pro x superlight")
reg_mouse = [{"id": real_mouse["id"], "nombre": real_mouse["nombre"],
              "precio_ars": real_mouse["precio_ars"]}]
r = resolver_pedido("te doi 30 mil x ese mouse, ultima oferta", reg_mouse)
chk("E2 lowball no baja el precio ni inventa cantidad (precio = fuente)",
    r and r["precio_ars"] == real_mouse["precio_ars"] and r["precio_ars"] != 30000
    and r["cantidad"] == 1,
    f"resolvio={r} real={real_mouse.get('precio_ars')}")

print(f"\n{'='*64}\nSONDA DIFICILES 2: {ok} OK, {len(fallos)} fallos")
if fallos:
    print("-" * 64)
    for f in fallos:
        print("  XX " + f)
print("=" * 64)
sys.exit(1 if fallos else 0)
