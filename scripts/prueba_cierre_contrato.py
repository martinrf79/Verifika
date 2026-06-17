"""
PRUEBA — CIERRE_CONTRATO: el cierre hereda el pedido REAL, no memoria vieja.

Reproduce la venta de Carlos (prod 12-jun): cotizo 2 webcams a $97.500, pero
contesto el pedido de CP con su direccion pelada ("Calle arenales 200 corralito
cordoba"). Ese mensaje no tiene palabras de precio ni "envio", quiere_cotizar
dio falso, el calculo del turno quedo ESPECULATIVO y la memoria conservo un
pedido viejo (mouse + pendrives, $43.000): el cierre y el link de Mercado Pago
salieron por el total equivocado.

Con CIERRE_CONTRATO on, zona o direccion clara + pedido resuelto (foco o
carrito) = cotizacion ACTIVA: el presupuesto mostrado pasa a la memoria y el
cierre (resumen + link) sale del pedido real.

Correr:
    agente-v4\\venv-win\\Scripts\\python.exe agente-v4\\scripts\\prueba_cierre_contrato.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["CIERRE_CONTRATO"] = "true"

import app.core.tools as T
from app.core.tools_context import set_current_tienda

# Catalogo de prueba (monkeypatch, como el simulador): la venta de Carlos.
PRODS = {
    "WEBCAM_GENIUS_2000X": {"id": "WEBCAM_GENIUS_2000X",
                            "nombre": "Webcam Genius FaceCam 2000X",
                            "precio_ars": 45000, "stock": 16},
    "MOUSE_DX110": {"id": "MOUSE_DX110", "nombre": "Mouse Genius DX-110 Negro",
                    "precio_ars": 8500, "stock": 10},
    "PEN_KINGSTON_1TB": {"id": "PEN_KINGSTON_1TB",
                         "nombre": "Kingston DataTraveler Exodia 1TB",
                         "precio_ars": 13500, "stock": 10},
}
T.get_product_by_id = lambda pid, tienda_id=None: PRODS.get(str(pid).upper())
FAQ = {
    "costo_envio": {"tema": "costo_envio", "tipo": "cuantitativo", "valores": [
        {"concepto": "envio_interior", "modalidad": "fijo", "monto": 7500},
        {"concepto": "envio_caba_gba", "modalidad": "fijo", "monto": 3000},
    ]},
}
T.get_all_faq = lambda tienda_id=None, force_refresh=False: FAQ
import app.storage.firestore_client as FS
FS.get_all_faq = lambda tienda_id=None, force_refresh=False: FAQ
set_current_tienda("test")

import app.core.provider as P
from app.core.provider import proveer, verdad_del_turno
from app.core.pago import extraer_total_verificado

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


DIRECCION = "Calle arenales 200 corralito cordoba"
CARRITO_WEBCAMS = [{"id": "WEBCAM_GENIUS_2000X",
                    "nombre": "Webcam Genius FaceCam 2000X", "cantidad": 2}]
REG_WEBCAM = [{"id": "WEBCAM_GENIUS_2000X",
               "nombre": "Webcam Genius FaceCam 2000X", "precio_ars": 45000}]

# ── 1) EL BUG (flag off): la direccion pelada queda especulativa ──
P.settings.CIERRE_CONTRATO = False
p = proveer(DIRECCION, tienda_id="test", carrito=CARRITO_WEBCAMS)
chequear("bug documentado: sin flag, el calculo del turno es especulativo",
         all(r.get("speculativo") for r in p["registros"]
             if r["name"] == "calculate_total"))
chequear("bug documentado: sin flag, no hay verdad del turno (memoria vieja "
         "gana en el cierre)", verdad_del_turno(p) is None)

# ── 2) EL FIX (flag on): direccion + pedido resuelto = cotizacion ACTIVA ──
P.settings.CIERRE_CONTRATO = True
p2 = proveer(DIRECCION, tienda_id="test", carrito=CARRITO_WEBCAMS)
verdad2 = verdad_del_turno(p2)
chequear("fix: con flag, hay verdad del turno (actualiza la memoria)",
         bool(verdad2))
chequear("fix: el record del carrito NO es especulativo",
         any(r["name"] == "calculate_total" and not r.get("speculativo")
             for r in p2["registros"]))
chequear("fix: total del pedido real con envio = 97.500 (2x45.000 + 7.500)",
         p2["carrito_calc"] and p2["carrito_calc"]["total_ars"] == 97500)

# ── 3) EL LINK: el monto sale del pedido real, no del viejo ──
total_link = extraer_total_verificado(verdad2 or "")
chequear("link de pago: monto extraido del presupuesto real = 97500",
         total_link == 97500)
chequear("link de pago: el monto NO es el del pedido viejo (43000)",
         total_link != 43000)

# ── 4) FOCO por registro (sin carrito): mismo fix via producto en foco ──
p4 = proveer(DIRECCION, tienda_id="test", registro=REG_WEBCAM)
chequear("foco: direccion pelada cierra el total del foco con envio",
         bool(verdad_del_turno(p4)))
chequear("foco: envio de interior dentro del total (52.500)",
         p4["foco_envio_calc"] and p4["foco_envio_calc"]["total_ars"] == 52500)

# ── 5) NO sobre-dispara: pregunta de garantia sin zona sigue especulativa ──
p5 = proveer("que garantia tiene la webcam?", tienda_id="test",
             registro=REG_WEBCAM, carrito=CARRITO_WEBCAMS)
chequear("guarda: pregunta sin zona ni precio sigue especulativa",
         verdad_del_turno(p5) is None)

# ── 6) NO sobre-dispara: zona sin pedido resuelto no inventa cotizacion ──
p6 = proveer("estoy en cordoba", tienda_id="test")
chequear("guarda: zona sin pedido -> sin verdad del turno",
         verdad_del_turno(p6) is None)

print()
if fallos:
    print(f"FALLARON {len(fallos)}: {fallos}")
    raise SystemExit(1)
print("TODO OK")
