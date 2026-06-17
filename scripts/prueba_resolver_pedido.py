"""
PRUEBA — resolvedor de pedido por codigo (movimiento 2).

Verifica, SIN LLM, que el codigo resuelve a que producto se refiere el cliente
usando solo el registro de sesion. Los casos salen de las fallas reales del arnes
multiturno con Gemini: ventas maduras que se caian porque el modelo perdia el id.

Correr:
    set PYTHONPATH=agente-v4
    agente-v4\\venv-win\\Scripts\\python.exe agente-v4\\scripts\\prueba_resolver_pedido.py
"""
from app.core.resolver_pedido import resolver_pedido

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


# Registro tipico de la conversacion 1 del arnes: dos mouses mostrados.
reg_mouses = [
    {"id": "MOUSE_G203", "nombre": "Logitech G203 Lightsync", "precio_ars": 38000},
    {"id": "MOUSE_DEATHADDER", "nombre": "Razer DeathAdder V3", "precio_ars": 125000},
]

# ── Superlativo de precio: "el mas barato" (conv 1 turno 4) ──
r = resolver_pedido("el mas barato cuanto sale?", reg_mouses)
chequear("mas barato -> G203", r and r["producto_id"] == "MOUSE_G203")
r = resolver_pedido("dame el mas caro", reg_mouses)
chequear("mas caro -> DeathAdder", r and r["producto_id"] == "MOUSE_DEATHADDER")

# ── Por nombre o marca ──
r = resolver_pedido("el Logitech G203 lo quiero", reg_mouses)
chequear("nombre Logitech G203 -> G203", r and r["producto_id"] == "MOUSE_G203")
r = resolver_pedido("me interesa el Razer", reg_mouses)
chequear("marca Razer -> DeathAdder",
         r and r["producto_id"] == "MOUSE_DEATHADDER")

# ── Caso canonico conv 5: un solo Samsung en registro, cierre por anafora ──
reg_ssd = [{"id": "SSD_SAMSUNG_980", "nombre": "SSD Samsung 980 PRO 1TB",
            "precio_ars": 225000}]
r = resolver_pedido("dale, lo confirmo", reg_ssd)
chequear("anafora con unico producto -> Samsung",
         r and r["producto_id"] == "SSD_SAMSUNG_980")
r = resolver_pedido("el Samsung de 1TB cuanto sale?", reg_ssd)
chequear("nombre Samsung -> Samsung", r and r["producto_id"] == "SSD_SAMSUNG_980")

# ── Ambiguedad: NO adivinar ──
r = resolver_pedido("me lo llevo", reg_mouses)
chequear("anafora con dos productos -> None (no adivina)", r is None)
reg_dos_samsung = [
    {"id": "SSD_SAMSUNG_980", "nombre": "SSD Samsung 980 PRO 1TB", "precio_ars": 225000},
    {"id": "MON_SAMSUNG_G5", "nombre": "Samsung Odyssey G5 32", "precio_ars": 485000},
]
r = resolver_pedido("el Samsung", reg_dos_samsung)
chequear("dos Samsung distintos -> None (ambiguo)", r is None)

# ── Cantidad ──
r = resolver_pedido("comprame dos G203", reg_mouses)
chequear("cantidad 'dos' -> 2", r and r["cantidad"] == 2 and
         r["producto_id"] == "MOUSE_G203")
r = resolver_pedido("llevo 3 del Razer", reg_mouses)
chequear("cantidad '3' -> 3", r and r["cantidad"] == 3)
r = resolver_pedido("el Logitech G203", reg_mouses)
chequear("sin cantidad -> default 1", r and r["cantidad"] == 1)

# ── Registro vacio o sin senal: None ──
chequear("registro vacio -> None", resolver_pedido("lo confirmo", []) is None)
chequear("mensaje sin referencia -> None",
         resolver_pedido("hola que tal", reg_mouses) is None)

# ── Conv 2: pide el de 27 pulgadas con dos monitores de 27 -> ambiguo ──
reg_monitores = [
    {"id": "MON_LG_27", "nombre": "Monitor LG UltraGear 27GP850", "precio_ars": 580000},
    {"id": "MON_AOC_27", "nombre": "Monitor AOC 27G2", "precio_ars": 295000},
]
r = resolver_pedido("el de 27 pulgadas cuanto es?", reg_monitores)
chequear("dos monitores 27 -> None (ambiguo)", r is None)

print()
if fallos:
    print(f"FALLARON {len(fallos)}: {fallos}")
    raise SystemExit(1)
print("TODO OK")
