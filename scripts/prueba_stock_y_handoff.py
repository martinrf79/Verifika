"""
PRUEBA — STOCK_GATE + handoff de cierre + vencimiento de memoria, SIN LLM.

Las tres clases que dejo a la vista la prueba de Telegram del 12-jun (teclados):
  1. STOCK_GATE: la calculadora cotizaba 3 unidades de un producto con stock 0
     y el contrato ordenaba venderlo. Ahora el contrato ordena NO vender.
  2. Handoff fuerte: "ok enviame link" + "y el link de mp?" creaban DOS leads y
     repetian un enlatado que ignoraba el pedido del link. Ahora reusa el lead
     activo y reconoce el link.
  3. Memoria vencida: presupuesto/carrito/localidad de una charla vieja no
     valen para la venta de hoy (direccion fantasma "Calle Arenales 200").

Correr:
    agente-v4\\venv-win\\Scripts\\python.exe agente-v4\\scripts\\prueba_stock_y_handoff.py
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["STOCK_GATE"] = "true"
os.environ["CIERRE_CONTRATO"] = "true"
os.environ["USE_LEADS"] = "true"

import app.core.tools as T
from app.core.tools_context import set_current_tienda

PRODS = {
    "TEC0020": {"id": "TEC0020", "nombre": "Teclado Genius KB-110X Blanco",
                "precio_ars": 12000, "stock": 0},
    "MOU0009": {"id": "MOU0009", "nombre": "Mouse Logitech M170 Negro",
                "precio_ars": 12000, "stock": 10},
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
set_current_tienda("test")

import app.core.provider as P
from app.core.provider import proveer, contrato

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


# ── 1) STOCK_GATE: carrito con 3 teclados de stock 0 (el caso real) ──
CARRITO_TEC = [{"id": "TEC0020", "nombre": "Teclado Genius KB-110X Blanco",
                "cantidad": 3}]
p = proveer("y el envio", tienda_id="test", carrito=CARRITO_TEC,
            localidad_memoria="villa rumipal cordoba")
chequear("stock: faltante detectado en el carrito (stock 0, pide 3)",
         p["stock_falta"] and p["stock_falta"][0]["producto_id"] == "TEC0020"
         and p["stock_falta"][0]["stock"] == 0)
c = contrato(p, estado="explorando")
chequear("stock: contrato ordena NO vender, primera seccion",
         "STOCK INSUFICIENTE" in c)
chequear("stock: contrato prohibe link y 'no hay problema'",
         "NO ofrezcas link" in c and "no hay problema" in c)

# ── 2) STOCK_GATE: con stock suficiente, el contrato lleva el stock REAL ──
# (la otra mitad del caso teclados: el Solver dijo "0 unidades" con stock 11
# en Firestore; con las unidades reales en el contrato no puede inventar)
REG_MOU = [{"id": "MOU0009", "nombre": "Mouse Logitech M170 Negro",
            "precio_ars": 12000}]
p2 = proveer("cuanto sale el mouse?", tienda_id="test", registro=REG_MOU)
c2 = contrato(p2, estado="explorando", registro=REG_MOU)
chequear("stock: con stock suficiente no hay faltante",
         not p2["stock_falta"] and "STOCK INSUFICIENTE" not in c2)
chequear("stock: el contrato trae el stock REAL del pedido (10 unidades)",
         p2["stock_info"] and "STOCK REAL" in c2 and "10 unidades" in c2)

# ── 3) STOCK_GATE off: identico al previo ──
P.settings.STOCK_GATE = False
p3 = proveer("y el envio", tienda_id="test", carrito=CARRITO_TEC,
             localidad_memoria="villa rumipal cordoba")
chequear("stock: flag off no marca nada", not p3["stock_falta"])
P.settings.STOCK_GATE = True

# ── 4) HANDOFF: lead activo se reusa y el pedido de link se reconoce ──
import app.core.orchestrator as O

_creados = []


def _fake_crear_lead(**kw):
    _creados.append(kw)
    return f"lead_nuevo_{len(_creados)}"


async def _fake_notificar(**kw):
    return None


O.crear_lead = _fake_crear_lead
O.notificar_lead = _fake_notificar

import app.core.leads as L

_lead_activo = {"lead_id": "L_VIEJO", "estado": "datos_solicitados"}
L.get_lead_activo = lambda *a, **k: _lead_activo
L.actualizar_lead = lambda *a, **k: None


async def _correr_handoff(mensaje):
    return await O._handoff_compra(
        "u1", "telegram", "test", mensaje, "Teclado Genius KB-110X Blanco", "t")


r1 = asyncio.run(_correr_handoff("ok enviame link"))
chequear("handoff: con lead activo NO crea otro lead",
         r1 and r1[1] == "L_VIEJO" and len(_creados) == 0)
chequear("handoff: pedido de link reconocido en la respuesta",
         r1 and "link de pago" in r1[0] and "nombre" in r1[0])

r2 = asyncio.run(_correr_handoff("y el link de mp?"))
chequear("handoff: segunda insistencia tampoco duplica lead",
         r2 and r2[1] == "L_VIEJO" and len(_creados) == 0)

# Sin lead activo: crea uno solo y notifica una vez.
L.get_lead_activo = lambda *a, **k: None
r3 = asyncio.run(_correr_handoff("dale lo llevo"))
chequear("handoff: sin lead activo crea UNO con el enlatado normal",
         r3 and len(_creados) == 1 and "te confirmo el" in r3[0])

# ── 4b) LINK INVENTADO: toda URL del Solver se elimina por codigo ──
_fake = ("Te paso el link de pago: 👉 [Link de pago Mercado Pago]"
         "(https://mpago.verifika.tech/pago/3-teclados) Cualquier duda avisame.")
_limpio = O._sin_links(_fake)
chequear("links: URL markdown inventada eliminada entera",
         "http" not in _limpio and "mpago" not in _limpio
         and "Cualquier duda" in _limpio)
chequear("links: URL suelta tambien se elimina",
         "http" not in O._sin_links("pagá acá https://falso.com/x y listo"))
chequear("links: texto sin URLs queda intacto",
         O._sin_links("Total: $43.500, decime tu direccion")
         == "Total: $43.500, decime tu direccion")

# ── 4c) SALUDO POR CODIGO: condicion estricta ──
chequear("saludo: 'nueva compra' con confianza alta -> saludo por codigo",
         O._es_saludo_simple("saludo", 0.95, "nueva compra") is True)
chequear("saludo: mensaje con numeros NUNCA es saludo (hay pedido)",
         O._es_saludo_simple("saludo", 0.95, "hola quiero 2 mouses") is False)
chequear("saludo: confianza baja no dispara",
         O._es_saludo_simple("saludo", 0.6, "hola") is False)
chequear("saludo: mensaje largo no dispara",
         O._es_saludo_simple("saludo", 0.95,
                             "hola buenas tardes queria consultar por el "
                             "envio de un pedido que hice") is False)
chequear("saludo: otra intencion no dispara",
         O._es_saludo_simple("pregunta_especifica", 0.95, "hola") is False)

# ── 5) MEMORIA: vencimiento por TTL ──
_vieja = datetime.now(timezone.utc) - timedelta(hours=30)
_fresca = datetime.now(timezone.utc) - timedelta(hours=2)
chequear("memoria: 30h con TTL 12 -> vencida",
         O._memoria_vencida(_vieja, 12) is True)
chequear("memoria: 2h con TTL 12 -> vigente",
         O._memoria_vencida(_fresca, 12) is False)
chequear("memoria: TTL 0 -> nunca vence",
         O._memoria_vencida(_vieja, 0) is False)
chequear("memoria: updated_at None -> no vence (ante la duda)",
         O._memoria_vencida(None, 12) is False)

print()
if fallos:
    print(f"FALLARON {len(fallos)}: {fallos}")
    raise SystemExit(1)
print("TODO OK")
