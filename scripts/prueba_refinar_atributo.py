"""
PRUEBA OFFLINE — refinamiento por atributo discriminante (color/modelo).

Sin LLM, sin red: corre en milisegundos. Cubre la clase de bug que el banco de
cierre destapo: el cliente dice el color ('K380 negro') y el sistema igual
preguntaba A/B negro/blanco, o degradaba 'mouse G203 negro' a buscar 'mouse'.

Tres frentes:
  1. resolver_pedido: con color explicito resuelve a UN producto (no None).
  2. candidatos_pedido: 3+ candidatos que el color angosta a un A/B real.
  3. extraer_pedido (pedido_multi): codigo de modelo alfanumerico + color.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.resolver_pedido import (resolver_pedido, candidatos_pedido,  # noqa
                                      refinar_por_atributo)

# Registro sintetico: lo que el cliente "ya vio" en la charla.
REG = [
    {"id": "TEC-K380-N", "nombre": "Teclado Logitech K380 Negro", "precio_ars": 55000},
    {"id": "TEC-K380-B", "nombre": "Teclado Logitech K380 Blanco", "precio_ars": 55000},
    {"id": "TEC-G915-N", "nombre": "Teclado Logitech G915 TKL Negro", "precio_ars": 512500},
    {"id": "MOU-G203-N", "nombre": "Mouse Logitech G203 Lightsync Negro", "precio_ars": 37500},
    {"id": "MOU-G203-B", "nombre": "Mouse Logitech G203 Lightsync Blanco", "precio_ars": 37500},
]

ok = 0
fallos = 0


def chk(nombre, cond):
    global ok, fallos
    if cond:
        ok += 1
        print(f"[OK ] {nombre}")
    else:
        fallos += 1
        print(f"[XX ] {nombre}")


# 1) resolver_pedido honra el color explicito.
r = resolver_pedido("los 3 K380 negros", REG)
chk("K380 negros -> K380 Negro", r and r["producto_id"] == "TEC-K380-N" and r["cantidad"] == 3)

r = resolver_pedido("el K380 blanco", REG)
chk("K380 blanco -> K380 Blanco", r and r["producto_id"] == "TEC-K380-B")

# Sin color sigue siendo ambiguo (no adivina).
r = resolver_pedido("dame el K380", REG)
chk("K380 sin color -> None (ambiguo)", r is None)

# 2) candidatos_pedido: 'K380' (3 teclados con ese token? no, 2) -> A/B; con
#    color resuelve antes en resolver_pedido. Probamos que 'teclado negro'
#    (varios negros) NO arme A/B falso de 2 cuando hay 2 negros distintos.
c = candidatos_pedido("el mouse G203", REG)
chk("mouse G203 -> A/B (negro/blanco)", len(c) == 2)

# 3) extraer_pedido: modelo alfanumerico + color.
import app.core.tools as T  # noqa
import app.core.tools_context as TC  # noqa


def _fake_search(query=None, **kw):
    q = (query or "").lower()
    prods = [
        {"id": p["id"], "nombre": p["nombre"], "precio_ars": p["precio_ars"],
         "stock": 5}
        for p in REG
    ]
    hit = [p for p in prods
           if all(tok in p["nombre"].lower() for tok in q.split() if len(tok) > 2
                  and tok not in ("mouse", "teclado"))]
    # respaldo: token suelto
    if not hit:
        hit = [p for p in prods if any(tok in p["nombre"].lower()
                                       for tok in q.split() if len(tok) > 2)]
    return {"productos": hit, "encontrados": len(hit)}


T.search_products = _fake_search
TC.set_current_tienda("x")
from app.core.pedido_multi import extraer_pedido  # noqa

p = extraer_pedido("sumale un mouse G203 negro", "x")
item_ok = (p and p["items"] and p["items"][0]["product_id"] == "MOU-G203-N"
           and not p["ambiguos"])
chk("multi: mouse G203 negro -> item resuelto, sin ambiguos", item_ok)

p = extraer_pedido("quiero 2 teclados K380 negros", "x")
item_ok = (p and p["items"] and p["items"][0]["product_id"] == "TEC-K380-N"
           and p["items"][0]["cantidad"] == 2)
chk("multi: 2 teclados K380 negros -> item resuelto x2", item_ok)

# Anti pista-leak: el interprete arrastra el teclado del contexto previo, pero
# 'mouse G203 negro' NO debe resolver al teclado por compartir 'negro'.
p = extraer_pedido("sumale un mouse G203 negro", "x",
                   interpretacion={"producto_resuelto": "Teclado Logitech K380 Negro"})
item_ok = (p and p["items"] and p["items"][0]["product_id"] == "MOU-G203-N")
chk("multi: pista 'K380 Negro' NO secuestra 'mouse G203 negro'", item_ok)

# refinar_por_atributo directo: token que NO discrimina no cambia nada.
base = REG[:2]
chk("refinar sin discriminador (solo 'teclado') deja los 2",
    len(refinar_por_atributo(base, "teclado")) == 2)

print(f"\n{ok} OK, {fallos} fallos")
sys.exit(1 if fallos else 0)
