"""
PRUEBA DIRECTOR — testea aplicar_acciones() OFFLINE (sin LLM, sin red), contra el
catalogo real con fake_search, igual que banco_determinista. Verifica que las
acciones del interprete se ejecuten bien por codigo: agregar/sacar/cambiar/vaciar,
suma de cantidades, ambiguedad sin adivinar, fuera de catalogo, y la clave: lista
vacia NO toca el carrito (no hay arrastre).

Uso:  .\\correr_local.ps1 py scripts\\prueba_director.py
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
TC.set_current_tienda("verifika_prod")

from app.core.director import aplicar_acciones  # noqa: E402

TID = "verifika_prod"
ok = 0
fallos = []


def chk(nombre, cond, detalle=""):
    global ok
    if cond:
        ok += 1
    else:
        fallos.append(f"{nombre}  ::  {detalle}")


def cant_de(carrito, frag):
    for it in carrito:
        if frag.lower() in _norm(it["nombre"]):
            return it["cantidad"]
    return None


# 1) agregar resuelve y pone cantidad
r = aplicar_acciones([{"tipo": "agregar", "producto": "mouse logitech m170 negro",
                       "cantidad": 2}], [], TID)
chk("agregar M170 x2", len(r["carrito"]) == 1 and r["carrito"][0]["cantidad"] == 2,
    str(r["carrito"]))
chk("agregar trae precio del catalogo (no None)",
    r["carrito"] and isinstance(r["carrito"][0]["precio_ars"], (int, float)),
    str(r["carrito"]))

# 2) lista vacia NO toca el carrito (anti-arrastre)
base = [{"id": "X", "nombre": "Mouse Logitech M170 Negro", "cantidad": 2,
         "precio_ars": 12000}]
r = aplicar_acciones([], base, TID)
chk("acciones vacias no tocan el carrito", r["carrito"] == base and not r["cambios"],
    str(r))

# 3) agregar lo mismo suma cantidad
r = aplicar_acciones([{"tipo": "agregar", "producto": "teclado k380 negro",
                       "cantidad": 1},
                      {"tipo": "agregar", "producto": "teclado k380 negro",
                       "cantidad": 2}], [], TID)
chk("agregar dos veces suma a 3", cant_de(r["carrito"], "k380") == 3, str(r["carrito"]))

# 4) sacar quita del carrito
carrito = aplicar_acciones(
    [{"tipo": "agregar", "producto": "teclado k380 negro", "cantidad": 1},
     {"tipo": "agregar", "producto": "mouse g203 negro", "cantidad": 1}], [], TID)["carrito"]
r = aplicar_acciones([{"tipo": "sacar", "producto": "el teclado"}], carrito, TID)
chk("sacar el teclado lo quita",
    cant_de(r["carrito"], "k380") is None and cant_de(r["carrito"], "g203") == 1,
    str(r["carrito"]))

# 5) cambiar_cantidad
r = aplicar_acciones([{"tipo": "cambiar_cantidad", "producto": "mouse g203",
                       "cantidad": 5}], carrito, TID)
chk("cambiar cantidad del mouse a 5", cant_de(r["carrito"], "g203") == 5, str(r["carrito"]))

# 6) cambiar_cantidad a 0 lo saca
r = aplicar_acciones([{"tipo": "cambiar_cantidad", "producto": "mouse g203",
                       "cantidad": 0}], carrito, TID)
chk("cantidad 0 saca el item", cant_de(r["carrito"], "g203") is None, str(r["carrito"]))

# 7) vaciar
r = aplicar_acciones([{"tipo": "vaciar"}], carrito, TID)
chk("vaciar deja el carrito vacio", r["carrito"] == [], str(r["carrito"]))

# 8) agregar fuera de catalogo no inventa item
r = aplicar_acciones([{"tipo": "agregar", "producto": "playstation 5", "cantidad": 1}],
                     [], TID)
chk("fuera de catalogo no agrega", r["carrito"] == [] and r["no_encontrados"],
    str(r))

# 9) agregar ambiguo no adivina (devuelve candidatos)
r = aplicar_acciones([{"tipo": "agregar", "producto": "notebook lenovo ideapad",
                       "cantidad": 1}], [], TID)
chk("ambiguo no agrega, marca candidatos",
    r["carrito"] == [] and r["ambiguos"], str(r))

print(f"\n{'='*60}\nPRUEBA DIRECTOR: {ok} OK, {len(fallos)} fallos")
if fallos:
    print("-" * 60)
    for f in fallos:
        print("  XX " + f)
print("=" * 60)
sys.exit(1 if fallos else 0)
