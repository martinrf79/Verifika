"""
PRUEBA — CARRITO_DELTA (mutar el carrito por codigo), SIN LLM.

Verifica que mutar_carrito lee el cambio del mensaje y muta el carrito existente
sin el Solver: agregar (contra el catalogo, suma si ya esta), sacar (contra el
carrito, por categoria, con decremento), cambiar cantidad, ambiguedad sin
adivinar, referencia no encontrada, y que un mensaje sin delta no toca nada.

Catalogo y catalogo de busqueda monkeypatcheados, igual que prueba_pedido_multi.

Correr:
    set PYTHONPATH=.
    .\\venv-win\\Scripts\\python.exe .\\scripts\\prueba_carrito_delta.py
"""
import re
import app.core.tools as T
from app.core.tools_context import set_current_tienda

PRODS = {
    "MOUSE_G203": {"id": "MOUSE_G203", "nombre": "Logitech G203 Lightsync",
                   "categoria": "mouse", "marca": "Logitech",
                   "precio_ars": 38000, "stock": 10},
    "MOUSE_RAZER": {"id": "MOUSE_RAZER", "nombre": "Razer DeathAdder Essential",
                    "categoria": "mouse", "marca": "Razer",
                    "precio_ars": 45000, "stock": 10},
    "TEC_KUMARA": {"id": "TEC_KUMARA", "nombre": "Teclado Redragon Kumara",
                   "categoria": "teclado", "marca": "Redragon",
                   "precio_ars": 55000, "stock": 10},
    "MON_LG_27": {"id": "MON_LG_27", "nombre": "Monitor LG UltraGear 27",
                  "categoria": "monitor", "marca": "LG",
                  "precio_ars": 410000, "stock": 5},
    "AUR_HX": {"id": "AUR_HX", "nombre": "Auriculares HyperX Cloud II",
               "categoria": "auriculares", "marca": "HyperX",
               "precio_ars": 60000, "stock": 10},
}


def _fake_search(query=None, **kw):
    toks = [t for t in re.findall(r"[a-z0-9]+", str(query or "").lower())
            if len(t) >= 3]
    out = []
    for p in PRODS.values():
        texto = " ".join(str(p.get(k, "")).lower()
                         for k in ("nombre", "categoria", "marca"))
        if any(t in texto for t in toks):
            out.append(p)
    return {"productos": out, "encontrados": len(out)}


T.get_product_by_id = lambda pid, tienda_id=None: PRODS.get(str(pid).upper())
T.search_products = _fake_search
import app.storage.firestore_client as FS
FS.get_all_products = lambda tienda_id=None: list(PRODS.values())
set_current_tienda("test")

from app.core.carrito_delta import mutar_carrito

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


def cart():
    return [{"id": "MOUSE_G203", "nombre": "Logitech G203 Lightsync",
             "cantidad": 2},
            {"id": "TEC_KUMARA", "nombre": "Teclado Redragon Kumara",
             "cantidad": 1}]


def cant_de(carrito, pid):
    for it in carrito:
        if it["id"] == pid:
            return it["cantidad"]
    return None


# ── 1) AGREGAR producto nuevo ──
r = mutar_carrito("agrega 2 auriculares", cart(), tienda_id="test")
chequear("agregar nuevo: AUR_HX entra con cantidad 2",
         r and cant_de(r["carrito"], "AUR_HX") == 2)
chequear("agregar nuevo: el carrito pasa a 3 lineas",
         r and len(r["carrito"]) == 3)
chequear("agregar nuevo: cambio registrado de 0 a 2",
         r and any(c["op"] == "agregar" and c["id"] == "AUR_HX"
                   and c["de"] == 0 and c["a"] == 2 for c in r["cambios"]))

# ── 2) AGREGAR a un producto que YA esta: suma cantidad ──
r = mutar_carrito("agrega un logitech mas", cart(), tienda_id="test")
chequear("agregar existente: MOUSE_G203 pasa de 2 a 3",
         r and cant_de(r["carrito"], "MOUSE_G203") == 3)
chequear("agregar existente: sigue habiendo 2 lineas",
         r and len(r["carrito"]) == 2)

# ── 3) AGREGAR ambiguo: 'un mouse' matchea dos modelos, no adivina ──
r = mutar_carrito("agrega un mouse", cart(), tienda_id="test")
chequear("agregar ambiguo: queda en ambiguos, no inventa",
         r and any(a["op"] == "agregar" for a in r["ambiguos"]))
chequear("agregar ambiguo: el carrito no cambia",
         r and cant_de(r["carrito"], "MOUSE_G203") == 2 and len(r["carrito"]) == 2)

# ── 4) SACAR por categoria: 'el teclado' apunta a la linea ──
r = mutar_carrito("saca el teclado", cart(), tienda_id="test")
chequear("sacar: TEC_KUMARA sale del carrito",
         r and cant_de(r["carrito"], "TEC_KUMARA") is None)
chequear("sacar: queda solo el mouse",
         r and len(r["carrito"]) == 1 and r["carrito"][0]["id"] == "MOUSE_G203")
chequear("sacar: cambio de 1 a 0",
         r and any(c["op"] == "sacar" and c["a"] == 0 for c in r["cambios"]))

# ── 5) SACAR con decremento: 'quita un mouse' baja de 2 a 1 ──
r = mutar_carrito("quita un mouse", cart(), tienda_id="test")
chequear("sacar decremento: MOUSE_G203 pasa de 2 a 1",
         r and cant_de(r["carrito"], "MOUSE_G203") == 1)
chequear("sacar decremento: sigue en el carrito",
         r and len(r["carrito"]) == 2)

# ── 6) CAMBIAR cantidad 'en vez de' sobre carrito de un solo item ──
uno = [{"id": "MOUSE_G203", "nombre": "Logitech G203 Lightsync", "cantidad": 2}]
r = mutar_carrito("mejor 3 en vez de 2", uno, tienda_id="test")
chequear("cantidad: 'mejor 3 en vez de 2' fija 3 (no 2)",
         r and cant_de(r["carrito"], "MOUSE_G203") == 3)

# ── 7) CAMBIAR cantidad apuntando por categoria: 'que sean 3 los teclados' ──
r = mutar_carrito("que sean 3 los teclados", cart(), tienda_id="test")
chequear("cantidad por categoria: TEC_KUMARA pasa de 1 a 3",
         r and cant_de(r["carrito"], "TEC_KUMARA") == 3)
chequear("cantidad por categoria: el mouse no se toca",
         r and cant_de(r["carrito"], "MOUSE_G203") == 2)

# ── 8) SET 'poneme 5 mouses' apunta al mouse y fija 5 ──
r = mutar_carrito("poneme 5 mouses", cart(), tienda_id="test")
chequear("set: MOUSE_G203 pasa a 5",
         r and cant_de(r["carrito"], "MOUSE_G203") == 5)

# ── 9) SACAR superlativo: 'saca el mas caro' ──
dos = [{"id": "MOUSE_G203", "nombre": "Logitech G203 Lightsync", "cantidad": 1},
       {"id": "MON_LG_27", "nombre": "Monitor LG UltraGear 27", "cantidad": 1}]
r = mutar_carrito("saca el mas caro", dos, tienda_id="test")
chequear("sacar superlativo: sale el monitor (mas caro)",
         r and cant_de(r["carrito"], "MON_LG_27") is None
         and cant_de(r["carrito"], "MOUSE_G203") == 1)

# ── 10) SACAR no encontrado: 'saca la webcam' no apunta a nada ──
r = mutar_carrito("saca la webcam", cart(), tienda_id="test")
chequear("sacar no encontrado: queda en no_encontrado",
         r and any(n["op"] == "sacar" for n in r["no_encontrado"]))
chequear("sacar no encontrado: el carrito no cambia",
         r and len(r["carrito"]) == 2)

# ── 11) SIN delta: un mensaje normal no toca el carrito ──
r = mutar_carrito("cuanto sale el mouse?", cart(), tienda_id="test")
chequear("sin delta: devuelve None", r is None)
r = mutar_carrito("dale, me lo llevo", cart(), tienda_id="test")
chequear("sin delta: cierre tampoco dispara delta", r is None)

# ── 12) COMBINADO: sacar y agregar en el mismo mensaje ──
r = mutar_carrito("saca el teclado y agrega 2 auriculares", cart(),
                  tienda_id="test")
chequear("combinado: teclado afuera",
         r and cant_de(r["carrito"], "TEC_KUMARA") is None)
chequear("combinado: auriculares adentro con 2",
         r and cant_de(r["carrito"], "AUR_HX") == 2)
chequear("combinado: dos cambios registrados",
         r and len([c for c in r["cambios"] if c["op"] in ("sacar", "agregar")]) == 2)

print()
if fallos:
    print(f"RESULTADO: {len(fallos)} FALLAS")
    for f in fallos:
        print(f"  - {f}")
    raise SystemExit(1)
print("RESULTADO: TODO OK")
