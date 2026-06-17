"""
PRUEBA — PEDIDO_MULTI (Provider mas potente), SIN LLM.

El Provider lee pedidos combinados NUEVOS del mensaje por codigo y los cierra
enteros en el contrato (caso Esteban: "2 mauses y dos tablets dame los precios
mas bajos"). Ante ambiguedad no adivina: lista opciones reales y ordena
preguntar.

Correr:
    agente-v4\\venv-win\\Scripts\\python.exe agente-v4\\scripts\\prueba_pedido_multi.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["PEDIDO_MULTI"] = "true"
os.environ["STOCK_GATE"] = "true"

import app.core.tools as T
from app.core.tools_context import set_current_tienda

PRODS = {
    "MOU0009": {"id": "MOU0009", "nombre": "Mouse Logitech M170 Negro",
                "precio_ars": 12000, "stock": 16, "categoria": "mouses"},
    "MOU0010": {"id": "MOU0010", "nombre": "Mouse Logitech M170 Blanco",
                "precio_ars": 12000, "stock": 17, "categoria": "mouses"},
    "MOU0001": {"id": "MOU0001", "nombre": "Mouse Logitech G Pro Negro",
                "precio_ars": 163000, "stock": 5, "categoria": "mouses"},
    "TAB0001": {"id": "TAB0001", "nombre": "Tablet Samsung Galaxy Tab A9 Gris",
                "precio_ars": 211500, "stock": 7, "categoria": "tablets"},
    "TAB0002": {"id": "TAB0002", "nombre": "Tablet Samsung Galaxy Tab A9 Azul",
                "precio_ars": 211500, "stock": 13, "categoria": "tablets"},
    "TEC0020": {"id": "TEC0020", "nombre": "Teclado Genius KB-110X Blanco",
                "precio_ars": 12000, "stock": 11, "categoria": "teclados"},
    "AUR0001": {"id": "AUR0001", "nombre": "Auricular HyperX Cloud II",
                "precio_ars": 98000, "stock": 0, "categoria": "auriculares"},
}
T.get_product_by_id = lambda pid, tienda_id=None: PRODS.get(str(pid).upper())
FAQ = {
    "costo_envio": {"tema": "costo_envio", "tipo": "cuantitativo", "valores": [
        {"concepto": "envio_interior", "modalidad": "fijo", "monto": 7500},
    ]},
}
T.get_all_faq = lambda tienda_id=None, force_refresh=False: FAQ
import app.storage.firestore_client as FS
FS.get_all_faq = lambda tienda_id=None, force_refresh=False: FAQ


def _search_mock(query=None, **kw):
    q = str(query or "").lower()
    hits = [p for p in PRODS.values()
            if any(tok in p["nombre"].lower() or tok in p["categoria"]
                   for tok in q.split())]
    return {"encontrados": len(hits), "productos": hits}


T.search_products = _search_mock
set_current_tienda("test")

from app.core.pedido_multi import extraer_pedido
from app.core.provider import proveer, contrato, verdad_del_turno

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


# ── 1) CASO ESTEBAN: combo nuevo con "mas bajos" -> cerrado por codigo ──
MSG = "necesito 2 mouses y dos tablets dame los precios mas bajos que tengas"
ped = extraer_pedido(MSG, "test")
chequear("extractor: dos renglones resueltos (mouse x2, tablet x2)",
         ped and len(ped["items"]) == 2 and not ped["ambiguos"]
         and {(i["product_id"], i["cantidad"]) for i in ped["items"]}
         == {("MOU0009", 2), ("TAB0001", 2)})

p = proveer(MSG, tienda_id="test")
chequear("provider: pedido combinado calculado entero (447.000)",
         p["multi"] and p["multi"]["calc"]["total_ars"] == 447000)
chequear("provider: verdad del turno = presentacion del combo",
         verdad_del_turno(p) == p["multi"]["calc"]["presentacion"])
c = contrato(p, estado="explorando")
chequear("contrato: lleva PEDIDO COMBINADO con ids y total",
         "PEDIDO COMBINADO" in c and "MOU0009" in c and "447.000" in c)

# ── 2) AMBIGUO sin "barato": lista opciones, no adivina ──
p2 = proveer("quiero 2 mouses", tienda_id="test")
chequear("ambiguo: con 3 mouses y sin 'barato' no adivina",
         p2["multi"] and not p2["multi"]["items"]
         and p2["multi"]["ambiguos"])
c2 = contrato(p2, estado="explorando")
chequear("ambiguo: contrato ordena preguntar con opciones reales",
         "VARIAS opciones reales" in c2 and "Pregunta cual prefiere" in c2)
chequear("ambiguo: sin verdad del turno (no hay total que defender)",
         verdad_del_turno(p2) is None)

# ── 3) Cantidades en palabras y tipeo: "tres teclados" ──
p3 = proveer("dame tres teclados de los economicos", tienda_id="test")
chequear("palabras: 'tres teclados' = 3x Genius 36.000",
         p3["multi"] and p3["multi"]["calc"]["total_ars"] == 36000
         and p3["multi"]["items"][0]["cantidad"] == 3)

# ── 4) SIN stock no entra: auriculares stock 0 ──
ped4 = extraer_pedido("quiero 2 auriculares baratos", "test")
chequear("stock: producto sin stock no se elige",
         not ped4 or not ped4["items"])

# ── 5) Mensaje sin cantidades: None, no inventa pedidos ──
chequear("sin pedido: 'que garantia tiene el mouse?' -> None",
         extraer_pedido("que garantia tiene el mouse?", "test") is None)

# ── 6) Con envio y zona: compra grande = envio GRATIS auto (regla real) ──
p6 = proveer("2 mouses y 2 tablets baratos con envio a villa rumipal cordoba",
             tienda_id="test")
chequear("envio: combo grande = 447.000 con envio gratis por umbral",
         p6["multi"] and p6["multi"]["calc"]["total_ars"] == 447000
         and any(e.get("envio_gratis_auto")
                 for e in p6["multi"]["calc"].get("extras") or []))

# ── 6b) Compra chica: el envio SI suma (2 teclados 24.000 + 7.500) ──
p6b = proveer("2 teclados baratos con envio a villa rumipal cordoba",
              tienda_id="test")
chequear("envio: combo chico = 31.500 con envio sumado",
         p6b["multi"] and p6b["multi"]["calc"]["total_ars"] == 31500)

# ── 7) No pisa al foco: con registro y referencia, foco manda ──
REG = [{"id": "TEC0020", "nombre": "Teclado Genius KB-110X Blanco",
        "precio_ars": 12000}]
p7 = proveer("dale, me llevo 2 de esos teclados", tienda_id="test",
             registro=REG)
chequear("foco primero: si el foco resuelve, multi no interviene",
         p7["foco"] is not None and p7["multi"] is None)

# ── 9) INTERPRETE PRIMERO: su lectura resuelve la ambiguedad del crudo ──
# "2 tablets" crudo da 2 candidatas (gris/azul, mismo precio) = ambiguo; con
# el interprete resolviendo la Gris, el extractor lee IGUAL que el Provider.
ped9 = extraer_pedido("quiero 2 tablets", "test")
chequear("interprete: sin pista, 2 tablets es ambiguo",
         ped9 and not ped9["items"] and ped9["ambiguos"])
ped9b = extraer_pedido(
    "quiero 2 tablets", "test",
    interpretacion={"producto_resuelto": "Tablet Samsung Galaxy Tab A9 Gris"})
chequear("interprete: con pista, la Gris queda elegida y cotizable",
         ped9b and len(ped9b["items"]) == 1
         and ped9b["items"][0]["product_id"] == "TAB0001"
         and ped9b["items"][0]["cantidad"] == 2)

# ── 10) Pista que NO matchea el termino no contamina otro renglon ──
ped10 = extraer_pedido(
    "2 mouses baratos", "test",
    interpretacion={"producto_resuelto": "Tablet Samsung Galaxy Tab A9 Gris"})
chequear("interprete: pista de otro producto no pisa el renglon",
         ped10 and ped10["items"]
         and ped10["items"][0]["product_id"] == "MOU0009")

# ── 8) Flag off: identico al previo ──
import app.core.provider as P
P.settings.PEDIDO_MULTI = False
p8 = proveer(MSG, tienda_id="test")
chequear("flag off: multi None", p8["multi"] is None)
P.settings.PEDIDO_MULTI = True

print()
if fallos:
    print(f"FALLARON {len(fallos)}: {fallos}")
    raise SystemExit(1)
print("TODO OK")
