"""
PRUEBA — ESTADO_PEDIDO (planilla unica del turno), SIN LLM.

Verifica que construir_estado compone una planilla que sale SIEMPRE completa
(todas las claves presentes cada turno), con los items, el total, el envio, los
datos del cliente, los faltantes, la etapa y la llave de frescura del link.

Corre sobre la salida REAL de proveer() (catalogo y FAQ monkeypatcheados, igual
que prueba_provider) para que los nombres de campo no se desincronicen, mas
casos a mano para link, etapas de cierre y mapeo de envio.

Correr:
    set PYTHONPATH=agente-v4
    agente-v4\\venv-win\\Scripts\\python.exe agente-v4\\scripts\\prueba_estado_pedido.py
"""
import os
os.environ.setdefault("COTIZA_TRANSFERENCIA", "true")

import app.core.tools as T
from app.core.tools_context import set_current_tienda

PRODS = {
    "SSD_SAMSUNG_980": {"id": "SSD_SAMSUNG_980", "nombre": "SSD Samsung 980 PRO 1TB",
                        "precio_ars": 225000, "stock": 10},
    "MOUSE_G203": {"id": "MOUSE_G203", "nombre": "Logitech G203 Lightsync",
                   "precio_ars": 38000, "stock": 10},
}
T.get_product_by_id = lambda pid, tienda_id=None: PRODS.get(str(pid).upper())
FAQ = {
    "costo_envio": {"tema": "costo_envio", "tipo": "cuantitativo", "valores": [
        {"concepto": "envio_caba_gba", "modalidad": "fijo", "monto": 3000},
    ]},
}
T.get_all_faq = lambda tienda_id=None, force_refresh=False: FAQ
import app.storage.firestore_client as FS
FS.get_all_faq = lambda tienda_id=None, force_refresh=False: FAQ
set_current_tienda("test")

from app.core.provider import proveer
from app.core.estado_pedido import (
    construir_estado, lineas_items, CAMPOS_CLIENTE)

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


REG = [{"id": "SSD_SAMSUNG_980", "nombre": "SSD Samsung 980 PRO 1TB",
        "precio_ars": 225000}]

# Claves que la planilla DEBE traer siempre, vacias o no.
CLAVES = ("etapa", "activo", "vendible", "origen", "items", "subtotal",
          "envio", "total", "datos_cliente", "faltantes", "link", "ambiguos",
          "confirmacion", "presentacion")

# ── 1) CONSULTA SIMPLE: sin registro no hay pedido, pero la planilla sale entera ──
p_consulta = proveer("hola, que tal", tienda_id="test", registro=[])
e = construir_estado(p_consulta)
chequear("consulta: estado trae TODAS las claves", all(k in e for k in CLAVES))
chequear("consulta: items vacio", e["items"] == [])
chequear("consulta: etapa = consulta", e["etapa"] == "consulta")
chequear("consulta: total sin_dato", e["total"]["tipo"] == "sin_dato")
chequear("consulta: datos_cliente con las 4 claves vacias",
         set(e["datos_cliente"]) == set(CAMPOS_CLIENTE)
         and all(v == "" for v in e["datos_cliente"].values()))
chequear("consulta: faltan los 4 datos", len(e["faltantes"]) == 4)
chequear("consulta: confirmacion presente y vacia (nunca null)",
         e["confirmacion"]["necesita"] is False)

# ── 2) PEDIDO ACTIVO: 'me lo llevo' resuelve el foco y cierra el total ──
p_ped = proveer("dale, me lo llevo", tienda_id="test", registro=REG)
e2 = construir_estado(p_ped)
chequear("pedido: un item con id real", len(e2["items"]) == 1
         and e2["items"][0]["id"] == "SSD_SAMSUNG_980")
chequear("pedido: item trae precio_unitario y subtotal",
         e2["items"][0]["precio_unitario"] == 225000
         and e2["items"][0]["subtotal"] == 225000)
chequear("pedido: total fijo 225000", e2["total"]["tipo"] == "fijo"
         and e2["total"]["valor"] == 225000)
chequear("pedido: subtotal = 225000", e2["subtotal"] == 225000)
chequear("pedido: activo (el cliente pidio cotizar)", e2["activo"] is True)
chequear("pedido: vendible (hay stock)", e2["vendible"] is True)
chequear("pedido: presentacion no vacia (para el render)",
         bool(e2["presentacion"]))
chequear("pedido: etapa = pedido (sin datos de cliente aun)",
         e2["etapa"] == "pedido")
chequear("pedido: lineas_items arma el detalle",
         "1x" in lineas_items(e2) and "225.000" in lineas_items(e2))

# ── 3) CIERRE: el mismo pedido con datos de cliente a medias ──
lead_parcial = {"nombre": "Pedro Gomez", "telefono": "3514567890"}
e3 = construir_estado(p_ped, lead=lead_parcial, estado_conv="esperando_datos")
chequear("cierre: etapa = cierre", e3["etapa"] == "cierre")
chequear("cierre: nombre y telefono capturados",
         e3["datos_cliente"]["nombre"] == "Pedro Gomez"
         and e3["datos_cliente"]["telefono"] == "3514567890")
chequear("cierre: faltan direccion y forma_pago",
         set(e3["faltantes"]) == {"direccion", "forma_pago"})

# ── 4) CAPTURADO: los 4 datos presentes ──
lead_full = {"nombre": "Pedro Gomez", "telefono": "3514567890",
             "direccion": "San Martin 123, Cordoba", "forma_pago": "transferencia"}
e4 = construir_estado(p_ped, lead=lead_full)
chequear("capturado: etapa = capturado", e4["etapa"] == "capturado")
chequear("capturado: sin faltantes", e4["faltantes"] == [])

# ── 5) LINK Y FRESCURA (la llave del punto 5) ──
e5a = construir_estado(p_ped, link_actual="https://mp/abc", link_total=225000)
chequear("link: vigente cuando el total coincide", e5a["link"]["vigente"] is True)
e5b = construir_estado(p_ped, link_actual="https://mp/abc", link_total=180000)
chequear("link: NO vigente cuando el total cambio",
         e5b["link"]["vigente"] is False)
chequear("link: guarda el total con que se emitio",
         e5b["link"]["total_emitido"] == 180000)
e5c = construir_estado(p_ped)
chequear("link: sin link, vigente False", e5c["link"]["vigente"] is False)
e5d = construir_estado(p_consulta, link_actual="https://mp/abc", link_total=225000)
chequear("link: total indeterminado este turno -> vigente None",
         e5d["link"]["vigente"] is None)

# ── 6) ENVIO normalizado (casos a mano: construir_estado es puro) ──
e6a = construir_estado({"envio": {"estado": "cotizado", "detalle": {
    "modalidad": "fijo", "monto": 3000, "zona": "caba_gba",
    "concepto": "envio_caba_gba"}}})
chequear("envio: cerrado fijo con monto y zona",
         e6a["envio"]["estado"] == "cerrado"
         and e6a["envio"]["modalidad"] == "fijo"
         and e6a["envio"]["monto"] == 3000
         and e6a["envio"]["zona"] == "caba_gba")
e6b = construir_estado({"envio": {"estado": "pedir_cp"}})
chequear("envio: pendiente_cp cuando falta la zona",
         e6b["envio"]["estado"] == "pendiente_cp")
e6c = construir_estado({"envio": {"estado": "cotizado", "detalle": {
    "modalidad": "rango", "monto_min": 5000, "monto_max": 12000,
    "zona": "interior"}}})
chequear("envio: rango con min y max",
         e6c["envio"]["modalidad"] == "rango"
         and e6c["envio"]["min"] == 5000 and e6c["envio"]["max"] == 12000)
e6d = construir_estado({})
chequear("envio: sin_dato cuando no hay envio", e6d["envio"]["estado"] == "sin_dato")

# ── 7) VENDIBLE: el Provider marca stock faltante ──
e7 = construir_estado({**p_ped, "stock_falta": [
    {"producto_id": "SSD_SAMSUNG_980", "stock": 0, "pedido": 1}]})
chequear("vendible: False cuando hay stock faltante", e7["vendible"] is False)

# ── 8) CONFIRMACION en el estado: ambiguos de multi -> etapa confirmar ──
prov_conf = {"multi": {"items": [], "calc": None, "ambiguos": [
    {"termino": "teclado", "cantidad": 3, "candidatos": [
        {"id": "TEC_A", "nombre": "Teclado Logitech G915", "precio_ars": 512500},
        {"id": "TEC_B", "nombre": "Teclado Logitech K380", "precio_ars": 55000}]}]}}
e8 = construir_estado(prov_conf)
chequear("confirmacion: el estado la lleva poblada",
         e8["confirmacion"]["necesita"] is True
         and e8["confirmacion"]["tipo"] == "te_referis_a")
chequear("confirmacion: la frase trae los modelos reales",
         "G915" in e8["confirmacion"]["texto"]
         and "K380" in e8["confirmacion"]["texto"])
chequear("confirmacion: etapa = confirmar (el turno tiene que preguntar)",
         e8["etapa"] == "confirmar")
chequear("confirmacion: pista del interprete sin ambiguedad no fuerza pregunta",
         construir_estado(p_ped, interpretacion={"tipo_confirmacion": "a_o_b"})
         ["confirmacion"]["necesita"] is False)

# ── 9) INVARIANTE: TODA etapa devuelve el mismo esqueleto de claves ──
chequear("invariante: todas las salidas comparten claves",
         all(set(s) == set(CLAVES) for s in (e, e2, e3, e4, e5a, e6a, e7, e8)))

print()
if fallos:
    print(f"RESULTADO: {len(fallos)} FALLAS")
    for f in fallos:
        print(f"  - {f}")
    raise SystemExit(1)
print("RESULTADO: TODO OK")
