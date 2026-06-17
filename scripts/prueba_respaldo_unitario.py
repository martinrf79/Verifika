"""
PRUEBA — caso Esteban (12-jun prod): el juez vetaba en falso el precio unitario
REAL ($211.500 c/u de la tablet) cuando el producto no estaba en la evidencia
de catalogo del turno, porque el PROOF de la calculadora solo declaraba el
subtotal por item. Fix: el proof declara precio_unitario y el juez lo respalda.

Correr:
    agente-v4\\venv-win\\Scripts\\python.exe agente-v4\\scripts\\prueba_respaldo_unitario.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import app.core.tools as T
from app.core.tools_context import set_current_tienda

PRODS = {
    "MOU0009": {"id": "MOU0009", "nombre": "Mouse Logitech M170 Negro",
                "precio_ars": 12000, "stock": 16},
    "TAB0001": {"id": "TAB0001", "nombre": "Tablet Samsung Galaxy Tab A9 Gris",
                "precio_ars": 211500, "stock": 7},
}
T.get_product_by_id = lambda pid, tienda_id=None: PRODS.get(str(pid).upper())
T.get_all_faq = lambda tienda_id=None, force_refresh=False: {}
import app.storage.firestore_client as FS
FS.get_all_faq = lambda tienda_id=None, force_refresh=False: {}
set_current_tienda("test")

from app.core.verificador import verificar_respuesta

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


# La llamada REAL del caso: 2 mouses + 2 tablets, el proof que arma la tool.
calc = T.calculate_total(items=[{"product_id": "MOU0009", "cantidad": 2},
                                {"product_id": "TAB0001", "cantidad": 2}])
chequear("calculadora: total 2x12.000 + 2x211.500 = 447.000",
         calc.get("ok") and calc.get("total_ars") == 447000)
chequear("proof: declara el precio unitario de cada item",
         all("precio_unitario" in o
             for o in calc["proof"]["operandos_productos"]))

# Evidencia COMO LA DEL TURNO REAL: catalogo solo con mouses + el proof.
evidencia = [
    {"tipo": "producto", "precio_ars": 12000},
    {"tipo": "proof", "proof": calc["proof"]},
]

# La respuesta del Solver del caso real (numeros todos verdaderos).
RESPUESTA = (
    "Mouses: 2x Mouse Logitech M170 Negro: $12.000 c/u = $24.000. "
    "Tablets: 2x Tablet Samsung Galaxy Tab A9 Gris: $211.500 c/u = $423.000. "
    "Total: $447.000.")

v = verificar_respuesta(RESPUESTA, evidencia)
chequear("juez: la respuesta verdadera ya NO se veta (caso Esteban)",
         v.get("ok") and not v.get("numeros_no_respaldados"))

# El juez sigue cazando un numero realmente falso en la misma respuesta.
v2 = verificar_respuesta(RESPUESTA.replace("447.000", "999.999"), evidencia)
chequear("juez: un total falso sigue bloqueado",
         not v2.get("ok") and 999999 in (v2.get("numeros_no_respaldados") or []))

print()
if fallos:
    print(f"FALLARON {len(fallos)}: {fallos}")
    raise SystemExit(1)
print("TODO OK")
