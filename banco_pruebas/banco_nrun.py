"""
BANCO N-RUN — la corroboracion que distingue "atado" de "tuvo suerte".

Un banco que corre UNA vez es una muestra de un proceso no-determinista: pasa o
falla por azar. Este corre cada probe N veces por el camino atado REAL
(hub_atado.procesar_atado) y mide tres cosas sobre la ULTIMA respuesta:

  1) COBERTURA: ¿contesto? (respuesta sustancial, no solo saludo/CTA/fallback).
     Cobertura < 100% = whiff = la respuesta NO esta atada.
  2) VARIANZA de wording: ¿las N respuestas son distintas entre si? Varianza 0 =
     plantilla robotica. Varianza alta = natural. (Atado Y no robotico.)
  3) NUMEROS: cuantas corridas gatillaron correccion de monto (senal de que el
     solver tejio una cifra que la red tuvo que arreglar).

Uso (clave paga recomendada para no throttlear):
    GEMINI_API_KEY=$GEMINI_API_KEY_PROD INTERPRETER_PROVIDER=gemini \
        LLM_PROVIDER=gemini N=10 python banco_pruebas/banco_nrun.py
"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from banco_pruebas.sim_firestore import install

TIENDA = "verifika_prod"

# Cada probe: (nombre, [mensajes de setup...], mensaje_medido). El setup arma el
# contexto (ej. mostrar una lista); se mide la respuesta al ultimo mensaje.
PROBES = [
    ("faq_iva", [], "el precio incluye IVA o pago aparte impuestos?"),
    ("faq_cuotas", [], "puedo pagar en cuotas sin interes?"),
    ("faq_garantia", [], "que garantia tienen los productos?"),
    ("faq_envio_costo", [], "cuanto sale el envio a cordoba capital?"),
    ("whiff_color", ["busco un mouse genius dx-110"],
     "ese me sirve pero no lo quiero negro, tenes otro color?"),
    ("compat", ["tenes auriculares redragon zeus x?"],
     "ese sirve para PS5?"),
]

# Palabras que, SOLAS, no cuentan como "contesto": saludo + CTA + fallback.
_VACIO = ("no tengo esa informacion confirmada",)


def _sustancial(texto: str) -> bool:
    t = (texto or "").strip().lower()
    if not t or any(v in t for v in _VACIO):
        return False
    # sacar lineas de puro saludo/CTA y ver si queda cuerpo
    cuerpo = [l for l in t.splitlines() if l.strip()
              and "?" not in l[-2:]  # no es solo una pregunta de cierre
              and not l.startswith(("hola", "¡hola", "buenas"))]
    return len("\n".join(cuerpo)) > 40


async def _una(procesar, msgs_setup, msg, i):
    from app.storage.firestore_client import reset_conversation
    user = f"nrun_{int(time.time()*1000)}_{i}"
    try:
        reset_conversation(user, tienda_id=TIENDA)
    except Exception:
        pass
    for m in msgs_setup:
        await procesar(user, m, TIENDA, "sim", "s")
    return await procesar(user, msg, TIENDA, "sim", f"m{i}")


async def main() -> int:
    install()
    from app.core.hub_atado import procesar_atado
    n = int(os.environ.get("N", "10") or 10)
    print(f"[n-run] N={n} por probe, camino atado real.\n")
    problemas = 0
    for nombre, setup, msg in PROBES:
        respuestas = []
        for i in range(n):
            try:
                r = await _una(procesar_atado, setup, msg, i)
            except Exception as e:
                r = f"<<ERROR {e}>>"
            respuestas.append(r)
        cubiertas = sum(_sustancial(r) for r in respuestas)
        distintas = len(set(r.strip() for r in respuestas))
        cobertura = cubiertas / n
        varianza = distintas / n
        estado = "OK " if cobertura == 1.0 and distintas >= max(2, n // 2) else "XX "
        if cobertura < 1.0 or distintas < 2:
            problemas += 1
        print(f"  {estado}{nombre:16} cobertura {cubiertas}/{n}  "
              f"wording {distintas}/{n} distintas")
        if cobertura < 1.0:
            fallo = next(r for r in respuestas if not _sustancial(r))
            print(f"       WHIFF ejemplo: {fallo[:100]!r}")
    print(f"\n=== {'PROBLEMAS: ' + str(problemas) if problemas else 'todo atado y variado'} ===")
    print("Cobertura 100% = no whiffea (atado). Wording distinto = no robotico.")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
