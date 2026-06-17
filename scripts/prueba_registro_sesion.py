"""
PRUEBA — registro de sesion del resolvedor (memoria de la cocina).

Prueba la mecanica nueva SIN servicios (sin Firestore ni LLM): que los IDs de
los productos que vieron las tools se extraen, se mergean con la memoria y se
arman en el bloque que recibe el Solver. Es el problema "numero real, cajon
equivocado": el cliente vuelve a referirse a un producto y el id tiene que estar.

Correr:
    set PYTHONPATH=agente-v4
    agente-v4\\venv-win\\Scripts\\python.exe agente-v4\\scripts\\prueba_registro_sesion.py
"""
from app.core.orchestrator import (
    _extraer_productos_vistos, _merge_productos_vistos, _ctx_productos_vistos)

fallos = []


def chequear(nombre, cond):
    estado = "OK " if cond else "FALLA"
    print(f"[{estado}] {nombre}")
    if not cond:
        fallos.append(nombre)


# ── 1) Extraccion: search_products devuelve productos con id ──
tools_search = [{
    "name": "search_products",
    "result": {"productos": [
        {"id": "MONITOR_SAMSUNG_G5", "nombre": "Samsung Odyssey G5",
         "precio_ars": 225000, "categoria": "monitores"},
        {"id": "MONITOR_LG_27", "nombre": "LG UltraGear 27",
         "precio_ars": 310000},
    ]}
}]
ext = _extraer_productos_vistos(tools_search)
ids = {p["id"] for p in ext}
chequear("search_products: extrae los dos ids",
         ids == {"MONITOR_SAMSUNG_G5", "MONITOR_LG_27"})
chequear("search_products: conserva nombre y precio",
         any(p["nombre"] == "Samsung Odyssey G5" and p["precio_ars"] == 225000
             for p in ext))

# ── 2) get_product_details (clave 'producto' singular) ──
tools_det = [{
    "name": "get_product_details",
    "result": {"producto": {"id": "MOUSE_G502", "nombre": "Logitech G502",
                            "precio_ars": 48000}}
}]
ext2 = _extraer_productos_vistos(tools_det)
chequear("get_product_details: extrae el producto singular",
         len(ext2) == 1 and ext2[0]["id"] == "MOUSE_G502")

# ── 3) calculate_total usa precio_unitario, no precio_ars ──
tools_calc = [{
    "name": "calculate_total",
    "result": {"detalle": [
        {"id": "TECLADO_HYPERX", "nombre": "HyperX Alloy",
         "precio_unitario": 95000, "cantidad": 1},
    ]}
}]
ext3 = _extraer_productos_vistos(tools_calc)
chequear("calculate_total: toma precio_unitario como precio",
         len(ext3) == 1 and ext3[0]["precio_ars"] == 95000)

# ── 4) Dedup dentro del turno (mismo id en dos tools) ──
ext4 = _extraer_productos_vistos(tools_search + tools_search)
chequear("dedup dentro del turno por id", len(ext4) == 2)

# ── 5) Producto sin id o sin precio se descarta (no ensucia el registro) ──
tools_basura = [{
    "name": "search_products",
    "result": {"productos": [
        {"nombre": "Sin id", "precio_ars": 1000},
        {"id": "SIN_PRECIO", "nombre": "Sin precio"},
        {"id": "BUENO", "nombre": "Valido", "precio_ars": 5000},
    ]}
}]
ext5 = _extraer_productos_vistos(tools_basura)
chequear("descarta productos sin id o sin precio",
         {p["id"] for p in ext5} == {"BUENO"})

# ── 6) Merge: el turno pisa a la memoria (precio fresco gana) y va al frente ──
memoria = [{"id": "MONITOR_SAMSUNG_G5", "nombre": "Samsung Odyssey G5",
            "precio_ars": 200000}]  # precio viejo
turno = [{"id": "MONITOR_SAMSUNG_G5", "nombre": "Samsung Odyssey G5",
          "precio_ars": 225000}]   # precio nuevo
merged = _merge_productos_vistos(turno, memoria, cap=12)
chequear("merge: dedup id repetido entre turno y memoria", len(merged) == 1)
chequear("merge: el precio fresco del turno gana",
         merged[0]["precio_ars"] == 225000)

# ── 7) Merge: agrega los nuevos al frente y conserva los viejos ──
memoria2 = [{"id": "VIEJO", "nombre": "Viejo", "precio_ars": 1000}]
turno2 = [{"id": "NUEVO", "nombre": "Nuevo", "precio_ars": 2000}]
merged2 = _merge_productos_vistos(turno2, memoria2, cap=12)
chequear("merge: turno al frente, memoria atras",
         [p["id"] for p in merged2] == ["NUEVO", "VIEJO"])

# ── 8) Cap: nunca mas de `cap` productos, los mas recientes ──
turno_grande = [{"id": f"P{i}", "nombre": f"Prod {i}", "precio_ars": i * 1000}
                for i in range(20)]
merged3 = _merge_productos_vistos(turno_grande, [], cap=12)
chequear("cap: corta a 12", len(merged3) == 12)
chequear("cap: conserva los primeros (mas recientes)",
         merged3[0]["id"] == "P0")

# ── 9) Bloque para el Solver: formato e id presente ──
ctx = _ctx_productos_vistos([
    {"id": "MONITOR_SAMSUNG_G5", "nombre": "Samsung Odyssey G5",
     "precio_ars": 225000},
    {"id": "MOUSE_G502", "nombre": "Logitech G502", "precio_ars": 48000},
])
chequear("bloque: contiene el id real", "MONITOR_SAMSUNG_G5" in ctx)
chequear("bloque: precio formateado $225.000", "$225.000" in ctx)
chequear("bloque: instruye usar ese id para calculate_total",
         "calculate_total" in ctx and "no lo busques" in ctx)

# ── 10) Bloque vacio si no hay nada (no inyecta ruido) ──
chequear("bloque vacio sin productos", _ctx_productos_vistos([]) == "")
chequear("bloque vacio si falta id",
         _ctx_productos_vistos([{"nombre": "X", "precio_ars": 1}]) == "")

# ── Resultado ──
print()
if fallos:
    print(f"FALLARON {len(fallos)}: {fallos}")
    raise SystemExit(1)
print("TODO OK")
