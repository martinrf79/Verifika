"""
PRUEBA — NUEVA_COMPRA_RESET (deteccion por codigo del pedido de arrancar de cero).

Prueba el detector SIN servicios (sin Firestore ni LLM): que las frases que
piden descartar el pedido en curso se detectan, que las charlas normales NO
disparan el reset (falso positivo = borrar un carrito vivo), y que la variante
"pura" distingue el mensaje a secas (respuesta por codigo) del que ademas trae
el pedido nuevo (sigue al pipeline con la memoria limpia).

Caso origen: prod 12-jun, dos "nueva compra" seguidos y el bot re-vendio el
pedido viejo de Esteban (2 mouse + 2 tablets, $447.000), porque ninguna pieza
tenia la orden de soltarlo.

Correr:
    set PYTHONPATH=agente-v4
    agente-v4\\venv-win\\Scripts\\python.exe agente-v4\\scripts\\prueba_nueva_compra.py
"""
import re

from app.core.orchestrator import (
    _es_nueva_compra, _es_nueva_compra_pura, _respuesta_nueva_compra)

fallos = []


def chequear(nombre, cond):
    estado = "OK " if cond else "FALLA"
    print(f"[{estado}] {nombre}")
    if not cond:
        fallos.append(nombre)


# ── 1) Positivos: frases que piden el reset ──
positivos = [
    "nueva compra",
    "Nueva compra",
    "quiero hacer otra compra",
    "nuevo pedido",
    "quiero hacer otro pedido",
    "empecemos de nuevo",
    "arranquemos de cero",
    "empezar de cero",
    "borra el pedido",
    "borra todo el pedido",
    "cancela el pedido",
    "cancelame esa compra",
    "olvidate del carrito",
    "descarta ese presupuesto",
    "anula la compra",
]
for frase in positivos:
    chequear(f"detecta: '{frase}'", _es_nueva_compra(frase))

# ── 2) Negativos: charla normal de venta que NO debe borrar el carrito ──
negativos = [
    "quiero comprar un mouse nuevo",
    "sumale otro mouse al pedido",
    "cuanto sale el pedido",
    "tienen stock del teclado",
    "como va mi compra anterior",
    "el envio a Cordoba cuanto cuesta",
    "dame el total con envio",
    "agregale una tablet al carrito",
    "hola, como va",
    "",
]
for frase in negativos:
    chequear(f"NO detecta: '{frase or '(vacio)'}'", not _es_nueva_compra(frase))

# ── 3) Pura vs con pedido nuevo en el mismo mensaje ──
chequear("'nueva compra' a secas es pura",
         _es_nueva_compra_pura("nueva compra"))
chequear("'empecemos de nuevo' es pura",
         _es_nueva_compra_pura("empecemos de nuevo"))
chequear("'nueva compra: 2 mouse y una tablet' NO es pura (trae numeros)",
         not _es_nueva_compra_pura("nueva compra: 2 mouse y una tablet"))
chequear("frase larga con pedido nuevo NO es pura",
         not _es_nueva_compra_pura(
             "nueva compra, ahora quiero una tablet samsung y un teclado"))

# ── 4) La respuesta enlatada no trae numeros (nada que el juez deba mirar) ──
resp = _respuesta_nueva_compra()
chequear("respuesta por codigo sin numeros", not re.search(r"\d", resp))
chequear("respuesta confirma el descarte", "descartado" in resp)

# ── Resumen ──
total = len(positivos) + len(negativos) + 6
print()
if fallos:
    print(f"RESULTADO: {total - len(fallos)}/{total} — FALLARON {len(fallos)}:")
    for f in fallos:
        print(f"  - {f}")
    raise SystemExit(1)
print(f"RESULTADO: {total}/{total} OK")
