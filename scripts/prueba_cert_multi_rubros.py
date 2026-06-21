"""
PRUEBA — el certificador y el pedido de varios rubros, SIN LLM ni Firestore.

Regresion del bug visto en prod 21-jun: "dame precio de 2 sillas, 2 mouse y 2
teclados" caia al puente y, a la segunda, derivaba a humano ("contactar con el
area designada"). Causa: camino_nuevo le pasaba la frase entera al CERTIFICADOR,
que valida UN producto. Ese string no es una identidad unica -> not_found ->
apagaba el motor de pedido multiple (que SI resuelve) y tiraba el turno al puente.

Dos arreglos que este banco fija:
  1. La cantidad inicial ('2 sillas') es cuenta, no modelo: ya no da not_found.
  2. categorias_en() detecta 2+ rubros -> camino_nuevo NO certifica como SKU unico.

Mockea el catalogo y ejercita el codigo REAL de produccion (certificador). NO
toca produccion ni la red.

Correr:
    python scripts/prueba_cert_multi_rubros.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import app.core.tools as T
import app.storage.firestore_client as FS
from app.core.tools_context import set_current_tienda

PRODS = {
    "SIL0001": {"id": "SIL0001", "nombre": "Silla Gamer Redragon Negra",
                "precio_ars": 180000, "stock": 5, "categoria": "sillas"},
    "SIL0002": {"id": "SIL0002", "nombre": "Silla Gamer Redragon Roja",
                "precio_ars": 185000, "stock": 4, "categoria": "sillas"},
    "SIL0003": {"id": "SIL0003", "nombre": "Silla Oficina Basica Negra",
                "precio_ars": 95000, "stock": 9, "categoria": "sillas"},
    "MOU0009": {"id": "MOU0009", "nombre": "Mouse Logitech M170 Negro",
                "precio_ars": 12000, "stock": 16, "categoria": "mouses"},
    "TEC0020": {"id": "TEC0020", "nombre": "Teclado Genius KB-110X Negro",
                "precio_ars": 12000, "stock": 11, "categoria": "teclados"},
    "EPS0001": {"id": "EPS0001", "nombre": "Impresora Epson L3250",
                "precio_ars": 350000, "stock": 3, "categoria": "impresoras"},
}


def _search(query=None, **kw):
    q = str(query or "").lower()
    return {"productos": [p for p in PRODS.values()
                          if any(tok in p["nombre"].lower()
                                 or tok in p["categoria"] for tok in q.split())]}


T.search_products = _search
FS.get_all_products = lambda tienda_id=None, force_refresh=False: list(PRODS.values())
set_current_tienda("test")

from app.core.certificador import certificar, categorias_en

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


# ── Arreglo 1: la cantidad inicial no rompe la identidad del rubro ──
chequear("'2 sillas' -> ambiguous (antes not_found)",
         certificar("2 sillas", "test")["status"] == "ambiguous")
chequear("'dos teclados' -> no es not_found",
         certificar("dos teclados", "test")["status"] != "not_found")

# ── Arreglo 2: deteccion de pedido de varios rubros (tolera plural) ──
chequear("compound nombra 3 rubros",
         len(categorias_en("dame precio de 2 sillas 2 mouse 2 teclados")) == 3)
chequear("single nombra 1 rubro", len(categorias_en("2 sillas")) == 1)
chequear("sin rubro = 0", len(categorias_en("hola que tal")) == 0)

# ── No-regresion: el anti-invento sigue intacto ──
chequear("producto inexistente sigue dando not_found",
         certificar("impresora 3D Zyltech", "test")["status"] == "not_found")
chequear("un rubro con varias variantes sigue siendo ambiguous",
         certificar("silla", "test")["status"] == "ambiguous")

print()
if fallos:
    print(f"FALLARON {len(fallos)}: {fallos}")
    raise SystemExit(1)
print("TODO OK")
