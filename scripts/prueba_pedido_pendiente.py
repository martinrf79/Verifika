"""
PRUEBA — PEDIDO PENDIENTE (el pedido a medio armar persiste y se completa), SIN LLM.

Caso real (charla Martin 12-jun noche): "2 mauses y dos teclados" quedo ambiguo,
el bot pregunto cuales, el cliente contesto "los baratos, armame la lista" y
nadie junto las dos mitades: sin carrito ni total, cierre pidiendo datos sin
precio y fallback. Esta bateria verifica que:
  1. el turno ambiguo deja un pendiente_nuevo con terminos y cantidades;
  2. el criterio del turno siguiente lo completa por codigo (mas barato con
     stock), cotiza entero y lo marca consumido;
  3. un mensaje sin criterio NO lo consume (sigue esperando);
  4. un pedido nuevo cerrado reemplaza al pendiente viejo;
  5. el detector de criterio no dispara con "dale" ni "si" pelados.

Correr:
    set PYTHONPATH=agente-v4
    agente-v4\\venv-win\\Scripts\\python.exe agente-v4\\scripts\\prueba_pedido_pendiente.py
"""
import os
os.environ["PEDIDO_MULTI"] = "true"
os.environ["PEDIDO_PENDIENTE"] = "true"

import app.core.tools as T
from app.core.tools_context import set_current_tienda

PRODS = {
    "MOU_M170": {"id": "MOU_M170", "nombre": "Mouse Logitech M170 Negro",
                 "precio_ars": 12000, "stock": 10},
    "MOU_G203": {"id": "MOU_G203", "nombre": "Mouse Logitech G203 Negro",
                 "precio_ars": 37500, "stock": 10},
    "TEC_K380": {"id": "TEC_K380", "nombre": "Teclado Logitech K380 Negro",
                 "precio_ars": 55000, "stock": 10},
    "TEC_G413": {"id": "TEC_G413", "nombre": "Teclado Logitech G413 Blanco",
                 "precio_ars": 98500, "stock": 10},
}
T.get_product_by_id = lambda pid, tienda_id=None: PRODS.get(str(pid).upper())


def _buscar(query=None, **kw):
    # OJO: matchea SOLO "mous" (no "maus"): el typo "mauses" del caso real
    # tiene que pasar por la correccion contra el vocabulario del catalogo.
    q = (query or "").lower()
    if "mous" in q:
        prods = [PRODS["MOU_M170"], PRODS["MOU_G203"]]
    elif "teclado" in q:
        prods = [PRODS["TEC_K380"], PRODS["TEC_G413"]]
    else:
        prods = []
    return {"productos": prods}


T.search_products = _buscar
FAQ = {
    "costo_envio": {"tema": "costo_envio", "tipo": "cuantitativo", "valores": [
        {"concepto": "envio_interior", "modalidad": "rango",
         "monto_min": 5000, "monto_max": 12000},
        {"concepto": "envio_caba_gba", "modalidad": "fijo", "monto": 3000},
    ]},
}
T.get_all_faq = lambda tienda_id=None, force_refresh=False: FAQ
import app.storage.firestore_client as FS
FS.get_all_faq = lambda tienda_id=None, force_refresh=False: FAQ
# Vocabulario del catalogo para la correccion de typos ("mause" -> "mouse").
FS.get_all_products = lambda force_refresh=False, tienda_id=None: list(PRODS.values())
set_current_tienda("test")

from app.core.provider import proveer, contrato, _pide_armar

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


# ── 1) Turno A: pedido con cantidades pero modelos ambiguos (typo incluido) ──
MSG_A = "Ok 2 mauses y dos teclados con envio color indistinto cuanto me saldrian"
pA = proveer(MSG_A, tienda_id="test")
chequear("turno A: el pedido queda ambiguo (sin calc)",
         pA["multi"] and not pA["multi"].get("calc")
         and len(pA["multi"]["ambiguos"]) == 2)
chequear("turno A: el typo 'mauses' NO pierde el renglon (corregido a mouse)",
         any("mou" in str(c.get("nombre", "")).lower()
             for a in pA["multi"]["ambiguos"] for c in a["candidatos"]))
chequear("turno A: pendiente_nuevo guardado con 2 terminos",
         pA["pendiente_nuevo"]
         and len(pA["pendiente_nuevo"]["ambiguos"]) == 2)
chequear("turno A: las cantidades viajan en el pendiente",
         sorted(a["cantidad"] for a in pA["pendiente_nuevo"]["ambiguos"])
         == [2, 2])
chequear("turno A: nada consumido", not pA["pendiente_consumido"])

PENDIENTE = pA["pendiente_nuevo"]

# ── 2) Turno B: el criterio completa el pedido por codigo ──
MSG_B = "Los baratos si armame la lista envio a carlos paz no se el cp"
pB = proveer(MSG_B, tienda_id="test", pedido_pendiente=PENDIENTE)
chequear("turno B: pedido completado (multi con calc)",
         pB["multi"] and pB["multi"].get("calc")
         and pB["multi"].get("desde_pendiente"))
ids_b = {(i["product_id"], i["cantidad"]) for i in pB["multi"]["items"]}
chequear("turno B: eligio el mas barato con stock de cada termino",
         ids_b == {("MOU_M170", 2), ("TEC_K380", 2)})
chequear("turno B: subtotal correcto 2x12000 + 2x55000 = 134000",
         pB["multi"]["calc"].get("subtotal_productos_ars") == 134000
         or pB["multi"]["calc"].get("total_ars") == 134000)
chequear("turno B: el envio entro al calculo (carlos paz = interior)",
         "Envio" in (pB["multi"]["calc"].get("presentacion") or ""))
chequear("turno B: pendiente consumido", pB["pendiente_consumido"])
chequear("turno B: cotiza activo (actualiza carrito y presupuesto)",
         pB["quiere_cotizar"] is True)
cB = contrato(pB, estado="explorando")
chequear("turno B: contrato dice PEDIDO PENDIENTE completado",
         "PEDIDO PENDIENTE completado" in cB)
chequear("turno B: contrato avisa que puede cambiar de modelo",
         "cambiar de modelo" in cB)

# ── 3) Mensaje sin criterio NO consume el pendiente ──
pC = proveer("gracias, despues te confirmo", tienda_id="test",
             pedido_pendiente=PENDIENTE)
chequear("sin criterio: no completa ni consume",
         not pC["pendiente_consumido"] and not pC["multi"])

# ── 4) Un pedido nuevo cerrado reemplaza al pendiente viejo ──
pD = proveer("mejor dame 1 mouse barato solo", tienda_id="test",
             pedido_pendiente=PENDIENTE)
chequear("pedido nuevo: cierra solo el mouse barato",
         pD["multi"] and pD["multi"].get("calc")
         and [(i["product_id"], i["cantidad"]) for i in pD["multi"]["items"]]
         == [("MOU_M170", 1)])
chequear("pedido nuevo: el pendiente viejo queda consumido",
         pD["pendiente_consumido"])

# ── 5) Detector de criterio: positivos y negativos ──
positivos = ["los baratos si armame la lista", "el mas economico",
             "cualquiera esta bien", "color indistinto, el que sea",
             "armame el presupuesto", "haceme la lista"]
for f in positivos:
    chequear(f"criterio detecta: '{f}'", _pide_armar(f))
negativos = ["dale", "si", "cuanto sale el envio", "tenes stock?",
             "a que hora abren"]
for f in negativos:
    chequear(f"criterio NO detecta: '{f}'", not _pide_armar(f))

# ── Resumen ──
print()
if fallos:
    print(f"RESULTADO: FALLARON {len(fallos)}:")
    for f in fallos:
        print(f"  - {f}")
    raise SystemExit(1)
print("TODO OK")
