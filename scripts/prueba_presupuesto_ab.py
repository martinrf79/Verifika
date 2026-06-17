"""
PRUEBA — presupuesto A/B + transferencia en el cotizador, SIN LLM.

Cubre las dos piezas nuevas del diseño "el codigo arma el presupuesto siempre":
 1. PRESUPUESTO_AB: referencia que matchea DOS productos -> el codigo cotiza los
    dos y arma opcion A y opcion B (antes: None y el Solver improvisaba).
 2. COTIZA_TRANSFERENCIA: el cliente nombra la transferencia -> el descuento de
    la FAQ entra al calculo por codigo (antes: "no tengo informacion", caso c04
    del molino baseline). Tienda sin ese descuento -> cotiza sin el, no pierde.

Correr:
    venv-win\\Scripts\\python.exe scripts\\prueba_presupuesto_ab.py
"""
import os
import sys
from pathlib import Path

os.environ["PRESUPUESTO_AB"] = "true"
os.environ["COTIZA_TRANSFERENCIA"] = "true"
sys.path.insert(0, str(Path(__file__).parent.parent))

import app.core.tools as T
from app.core.tools_context import set_current_tienda

PRODS = {
    "MON_LG_27": {"id": "MON_LG_27", "nombre": "Monitor LG 27GP850 UltraGear",
                  "precio_ars": 480000, "stock": 5},
    "MON_SAM_27": {"id": "MON_SAM_27", "nombre": "Monitor Samsung Odyssey G5 27",
                   "precio_ars": 420000, "stock": 5},
    "MOUSE_G203": {"id": "MOUSE_G203", "nombre": "Logitech G203 Lightsync",
                   "precio_ars": 38000, "stock": 10},
}
T.get_product_by_id = lambda pid, tienda_id=None: PRODS.get(str(pid).upper())
FAQ = {
    "costo_envio": {"tema": "costo_envio", "tipo": "cuantitativo", "valores": [
        {"concepto": "envio_interior", "modalidad": "rango",
         "monto_min": 5000, "monto_max": 12000},
        {"concepto": "envio_caba_gba", "modalidad": "fijo", "monto": 3000},
    ]},
    "descuento_transferencia": {
        "tema": "descuento_transferencia", "tipo": "cuantitativo", "valores": [
            {"concepto": "descuento_transferencia", "modalidad": "fijo",
             "monto": 10, "unidad": "porcentaje", "efecto": "descuento"},
        ]},
}
T.get_all_faq = lambda tienda_id=None, force_refresh=False: FAQ
import app.storage.firestore_client as FS
FS.get_all_faq = lambda tienda_id=None, force_refresh=False: FAQ
set_current_tienda("test")

from app.core.cotizar_codigo import (
    cotizar_pedido, cotizar_pedido_ab, bloque_ab_para_solver, presentacion_ab)
from app.core.resolver_pedido import candidatos_pedido

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


reg2mon = [
    {"id": "MON_LG_27", "nombre": "Monitor LG 27GP850 UltraGear",
     "precio_ars": 480000},
    {"id": "MON_SAM_27", "nombre": "Monitor Samsung Odyssey G5 27",
     "precio_ars": 420000},
]
reg3 = reg2mon + [{"id": "MOUSE_G203", "nombre": "Logitech G203 Lightsync",
                   "precio_ars": 38000}]

# ── candidatos_pedido: expone la ambiguedad de a dos ──
chequear("'el de 27' matchea los dos monitores",
         len(candidatos_pedido("el de 27 cuanto sale", reg2mon)) == 2)
chequear("tres o mas candidatos -> vacio (ambiguo de verdad)",
         candidatos_pedido("cuanto sale", reg3) == [])
chequear("referencia unica -> vacio (lo cubre resolver_pedido)",
         candidatos_pedido("el Samsung cuanto sale", reg2mon) == [])
chequear("anafora con registro de dos -> los dos",
         len(candidatos_pedido("me lo llevo", reg2mon)) == 2)

# ── cotizar_pedido_ab: dos presupuestos completos ──
ab = cotizar_pedido_ab("el de 27 cuanto sale", reg2mon, "test")
chequear("A/B devuelve dos opciones", ab and len(ab["opciones"]) == 2)
chequear("opcion A con total correcto",
         ab and ab["opciones"][0]["calc"].get("total_ars") == 480000)
chequear("opcion B con total correcto",
         ab and ab["opciones"][1]["calc"].get("total_ars") == 420000)

blq = bloque_ab_para_solver(ab)
chequear("bloque A/B trae las dos cifras",
         "480.000" in blq and "420.000" in blq)
chequear("bloque A/B pide elegir sin elegir el",
         "cual prefiere" in blq.lower())
pres = presentacion_ab(ab)
chequear("presentacion A/B (verdad del turno) trae ambas",
         "Opcion A" in pres and "Opcion B" in pres and "480.000" in pres)

# ── A/B con envio: las dos opciones llevan el envio ──
ab_env = cotizar_pedido_ab("el de 27 con envio a Rosario", reg2mon, "test")
chequear("A/B con envio cotiza las dos",
         ab_env and all(o["con_envio"] for o in ab_env["opciones"]))
# Los dos monitores superan el umbral de envio gratis (250k): el motor aplica
# gratis automatico y el total queda fijo, sin rango. Comportamiento correcto.
chequear("A/B con envio: gratis por umbral, total fijo de A",
         ab_env and ab_env["opciones"][0]["calc"].get("total_ars") == 480000)

# ── transferencia: el descuento entra al calculo por codigo ──
reg_mouse = [{"id": "MOUSE_G203", "nombre": "Logitech G203 Lightsync",
              "precio_ars": 38000}]
cot_t = cotizar_pedido("lo pago por transferencia cuanto queda", reg_mouse, "test")
chequear("transferencia descuenta 10%: total 34200",
         cot_t and cot_t["calc"].get("total_ars") == 34200)
chequear("presentacion nombra el descuento",
         cot_t and "Descuento" in cot_t["calc"].get("presentacion", ""))

# ── transferencia + envio juntos ──
cot_te = cotizar_pedido("con transferencia y envio a Rosario cuanto queda",
                        reg_mouse, "test")
chequear("transferencia + envio: total max 38000-3800+12000",
         cot_te and cot_te["calc"].get("total_max_ars") == 46200)

# ── tienda SIN descuento por transferencia: cotiza sin el, no pierde ──
FAQ_SIN = {"costo_envio": FAQ["costo_envio"]}
T.get_all_faq = lambda tienda_id=None, force_refresh=False: FAQ_SIN
FS.get_all_faq = lambda tienda_id=None, force_refresh=False: FAQ_SIN
cot_sin = cotizar_pedido("pago por transferencia", reg_mouse, "test")
chequear("sin FAQ de transferencia igual cotiza: total 38000",
         cot_sin and cot_sin["calc"].get("total_ars") == 38000)

print()
if fallos:
    print(f"FALLARON {len(fallos)}: {fallos}")
    raise SystemExit(1)
print("TODO OK")
