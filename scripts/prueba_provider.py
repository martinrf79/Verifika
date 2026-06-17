"""
PRUEBA — PROVIDER (motor determinista total), SIN LLM.

Verifica que el Provider calcula en todos los turnos aunque nadie lo pida
(foco, carrito, envio, catalogo), arma UN solo contrato para el Solver, marca
bien lo especulativo (no pisa carrito/presupuesto) y entrega la verdad del
turno solo cuando el cliente cotiza.

Correr:
    set PYTHONPATH=agente-v4
    agente-v4\\venv-win\\Scripts\\python.exe agente-v4\\scripts\\prueba_provider.py
"""
import os
os.environ.setdefault("COTIZA_TRANSFERENCIA", "true")

import app.core.tools as T
from app.core.tools_context import set_current_tienda

# Catalogo de prueba (monkeypatch, como el simulador).
PRODS = {
    "SSD_SAMSUNG_980": {"id": "SSD_SAMSUNG_980", "nombre": "SSD Samsung 980 PRO 1TB",
                        "precio_ars": 225000, "stock": 10,
                        "garantia_detalle": "Garantia oficial Samsung de 60 meses",
                        "origen": "Marca Samsung de Corea del Sur",
                        "material": "Aluminio y PCB",
                        "contenido_caja": "Unidad SSD, manual de garantia"},
    "MOUSE_G203": {"id": "MOUSE_G203", "nombre": "Logitech G203 Lightsync",
                   "precio_ars": 38000, "stock": 10},
    "MON_LG_27": {"id": "MON_LG_27", "nombre": "Monitor LG UltraGear 27GP850",
                  "precio_ars": 410000, "stock": 5},
    "MON_SAM_27": {"id": "MON_SAM_27", "nombre": "Monitor Samsung Odyssey G5 27",
                   "precio_ars": 380000, "stock": 5},
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
            {"concepto": "descuento_transferencia", "unidad": "porcentaje",
             "monto": 10},
        ]},
}
T.get_all_faq = lambda tienda_id=None, force_refresh=False: FAQ
import app.storage.firestore_client as FS
FS.get_all_faq = lambda tienda_id=None, force_refresh=False: FAQ
set_current_tienda("test")

from app.core.provider import proveer, contrato, verdad_del_turno

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


REG = [{"id": "SSD_SAMSUNG_980", "nombre": "SSD Samsung 980 PRO 1TB",
        "precio_ars": 225000},
       {"id": "MOUSE_G203", "nombre": "Logitech G203 Lightsync",
        "precio_ars": 38000}]

# ── 1) CONSULTA DE ATRIBUTO: la responde el Solver, NO se arma foco/A-B ──
# Direccion 'una eco' (16-jun): una pregunta de garantia/atributo sobre un
# producto NO genera una cotizacion especulativa (cotizar_pedido solo corre
# bajo intencion de cotizar). Pero el contrato igual lleva el producto del
# registro, asi el Solver tiene el dato a mano sin que nadie sume a ciegas.
p = proveer("el samsung tiene garantia?", tienda_id="test", registro=REG)
chequear("consulta atributo: no arma foco especulativo",
         p["foco"] is None and p["ab"] is None)
chequear("consulta atributo: NO hay verdad del turno (no cotiza)",
         verdad_del_turno(p) is None)
chequear("consulta atributo: ningun record de calculadora especulativo colado",
         all(r.get("speculativo") for r in p["registros"]
             if r["name"] == "calculate_total"))
c = contrato(p, estado="explorando", registro=REG)
chequear("contrato: lleva el producto del registro (precio a mano)",
         "CONTRATO DEL TURNO" in c and "225.000" in c)
chequear("contrato: regla de no calcular",
         "NUNCA sumes" in c)

# ── 2) COTIZA: 'me lo llevo' con registro de uno solo ──
reg_uno = [REG[0]]
p2 = proveer("dale, me lo llevo", tienda_id="test", registro=reg_uno)
chequear("cotiza: foco resuelto por anafora",
         p2["foco"] and p2["foco"]["producto_id"] == "SSD_SAMSUNG_980")
chequear("cotiza: verdad del turno = presentacion del foco",
         verdad_del_turno(p2) == p2["foco"]["calc"]["presentacion"])
chequear("cotiza: record del foco NO especulativo (actualiza memoria)",
         any(r["name"] == "calculate_total" and not r.get("speculativo")
             for r in p2["registros"]))

# ── 3) A/B: la referencia matchea dos monitores ──
reg_mon = [{"id": "MON_LG_27", "nombre": "Monitor LG UltraGear 27GP850",
            "precio_ars": 410000},
           {"id": "MON_SAM_27", "nombre": "Monitor Samsung Odyssey G5 27",
            "precio_ars": 380000}]
p3 = proveer("cuanto sale el monitor?", tienda_id="test", registro=reg_mon)
chequear("ab: dos opciones cotizadas", p3["ab"] and len(p3["ab"]["opciones"]) == 2)
chequear("ab: verdad del turno presenta A y B",
         "Opcion A" in (verdad_del_turno(p3) or ""))
chequear("ab: records especulativos (el cliente no eligio)",
         all(r.get("speculativo") for r in p3["registros"]
             if r["name"] == "calculate_total"))
c3 = contrato(p3, estado="explorando", registro=reg_mon)
chequear("ab: contrato presenta opcion A y B sin elegir",
         "OPCION A" in c3 and "OPCION B" in c3 and "cual prefiere" in c3)

# ── 4) CARRITO: total vigente recalculado por codigo ──
carrito = [{"id": "SSD_SAMSUNG_980", "nombre": "SSD Samsung 980 PRO 1TB",
            "cantidad": 1},
           {"id": "MOUSE_G203", "nombre": "Logitech G203 Lightsync",
            "cantidad": 2}]
p4 = proveer("cuanto me queda el total?", tienda_id="test",
             registro=REG, carrito=carrito)
chequear("carrito: total recalculado 225000+76000=301000",
         p4["carrito_calc"] and p4["carrito_calc"]["total_ars"] == 301000)
chequear("carrito: verdad del turno = presentacion del carrito",
         verdad_del_turno(p4) == p4["carrito_calc"]["presentacion"])
c4 = contrato(p4, estado="esperando_confirmacion", registro=REG)
chequear("carrito: contrato trae PEDIDO VIGENTE con ids reales",
         "PEDIDO VIGENTE" in c4 and "SSD_SAMSUNG_980" in c4)

# ── 5) ENVIO con localidad de memoria ('el envio ahi') ──
p5 = proveer("y el envio cuanto sale?", tienda_id="test", registro=reg_uno,
             localidad_memoria="soy de Rosario")
chequear("envio memoria: zona interior cotizada",
         p5["envio"] and p5["envio"]["estado"] == "cotizado"
         and p5["envio"]["detalle"].get("zona") == "interior")
c5 = contrato(p5, estado="explorando", registro=reg_uno)
chequear("envio memoria: contrato trae la linea de envio", "ENVIO" in c5)

# ── 6) ENVIO sin zona: la directiva es pedir el CP ──
p6 = proveer("me lo mandas a casa?", tienda_id="test", registro=reg_uno)
chequear("envio sin zona: estado pedir_cp",
         p6["envio"] and p6["envio"]["estado"] == "pedir_cp")
c6 = contrato(p6, estado="explorando", registro=reg_uno)
chequear("envio sin zona: contrato pide el CP y prohibe inventar numero",
         "codigo postal" in c6 and "NO des un numero de envio" in c6)

# ── 7) FOCO + ENVIO en el mensaje (compuesto, total cerrado) ──
p7 = proveer("el samsung con envio a Rosario, lo confirmo", tienda_id="test",
             registro=reg_uno)
chequear("foco+envio: cotizado con envio incluido",
         p7["foco"] and p7["foco"]["con_envio"] is True)

# ── 8) TRANSFERENCIA: el descuento entra al calculo del carrito ──
p8 = proveer("pago por transferencia, cuanto queda?", tienda_id="test",
             registro=REG, carrito=carrito)
chequear("transferencia: el total del carrito baja 10% (270900)",
         p8["carrito_calc"] and p8["carrito_calc"]["total_ars"] == 270900)

# ── 9) CATALOGO: busqueda por codigo absorbida en el contrato ──
T.search_products = lambda query=None, **kw: {
    "encontrados": 1,
    "productos": [PRODS["MOUSE_G203"] | {"precio": 38000}],
}
p9 = proveer("tenes mouse para jugar?", tienda_id="test",
             interpretacion={"intencion": "exploracion"})
chequear("catalogo: busqueda corrida por codigo",
         p9["catalogo"] and p9["catalogo"]["compacto"]["encontrados"] == 1)
c9 = contrato(p9, estado="explorando")
chequear("catalogo: resultados dentro del contrato",
         "CATALOGO" in c9 and "MOUSE_G203" in c9)
chequear("catalogo: record sintetico para la evidencia",
         any(r["name"] == "search_products" for r in p9["registros"]))

# ── 10) FOCO ya en carrito: no se duplica el calculo ──
p10 = proveer("lo confirmo", tienda_id="test", registro=reg_uno,
              carrito=[{"id": "SSD_SAMSUNG_980", "nombre": "SSD", "cantidad": 1}])
chequear("foco==carrito: no duplica (carrito_calc None, foco presente)",
         p10["foco"] and p10["carrito_calc"] is None)

# ── 11) ZONA CONOCIDA sin nombrar envio: el total CON envio tambien se cierra ──
# (clase del atacante caotico: "total final" con localidad ya dada; sin el
# numero cerrado el modelo sumaba producto+envio a mano)
p11 = proveer("cuanto sale el ssd?", tienda_id="test", registro=reg_uno,
              localidad_memoria="soy de Rosario")
chequear("zona conocida: foco pelado + variante con envio",
         p11["foco"] and p11["foco_envio_calc"])
c11 = contrato(p11, estado="explorando", registro=reg_uno)
chequear("zona conocida: contrato trae el total CON envio",
         "Total CON envio" in c11)
chequear("zona conocida: la verdad del turno es el total con envio",
         verdad_del_turno(p11) == p11["foco_envio_calc"]["presentacion"])

p12 = proveer("dame el total final de una vez", tienda_id="test",
              registro=REG, carrito=carrito,
              localidad_memoria="Nueva Cordoba, ya te dije")
chequear("carrito+zona: el envio entra al total aunque no lo nombre",
         p12["carrito_calc"] and (p12["carrito_calc"].get("extras")))

# ── 13) ENVIO SIN ZONA pero producto resoluble: presupuesto del producto
# cerrado + directiva de pedir CP (la venta no queda muda) ──
p13 = proveer("la mas barata me la llevo con envio", tienda_id="test",
              registro=REG)
chequear("envio sin zona: foco cerrado sin envio (el mouse, mas barato)",
         p13["foco"] and p13["foco"]["producto_id"] == "MOUSE_G203"
         and p13["foco"]["con_envio"] is False)
chequear("envio sin zona: igual pide el CP",
         p13["envio"] and p13["envio"]["estado"] == "pedir_cp")
c13 = contrato(p13, estado="esperando_confirmacion", registro=REG)
chequear("envio sin zona: contrato trae producto Y pedido de CP",
         "PRODUCTO EN FOCO" in c13 and "codigo postal" in c13)

# ── 14) FICHA: los atributos reales del foco entran al contrato ──
p14 = proveer("que garantia tiene el samsung?", tienda_id="test",
              registro=reg_uno)
chequear("ficha: atributos del foco presentes",
         p14["ficha"] and "60 meses" in p14["ficha"]
         and "Corea del Sur" in p14["ficha"])
c14 = contrato(p14, estado="explorando", registro=reg_uno)
chequear("ficha: contrato trae FICHA REAL con regla de honestidad",
         "FICHA REAL" in c14 and "no lo afirmes" in c14
         and "60 meses" in c14)

# ── 15) FICHA: producto pelado (sin atributos) -> sin seccion, sin romper ──
p15 = proveer("el G203 que material tiene?", tienda_id="test",
              registro=[REG[1]])
chequear("ficha: producto sin atributos -> solo stock o nada, contrato sano",
         "CONTRATO DEL TURNO" in contrato(p15, estado="explorando",
                                          registro=[REG[1]]))

print()
if fallos:
    print(f"FALLARON {len(fallos)}: {fallos}")
    raise SystemExit(1)
print("TODO OK")
