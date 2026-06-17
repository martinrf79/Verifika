"""
MEDIR LATENCIA — cronometra en aislamiento los componentes que suman demora por
turno: Firestore, Interprete (LLM), Solver (LLM), y el largo del prompt del Solver.
Corre cada cosa 3 veces e imprime el promedio (la red LLM tiene varianza).

Uso (cargar secrets antes):
    .\\correr_local.ps1 py scripts\\medir_latencia.py largo
    .\\correr_local.ps1 py scripts\\medir_latencia.py ligero   # prompt desinflado
"""
import os
import sys
import time
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Cargar el preset (mismos flags que prod) ANTES de importar config.
for raw in (ROOT / "config/maquina_determinista.env").read_text(
        encoding="utf-8-sig").splitlines():
    ln = raw.strip()
    if ln and not ln.startswith("#") and "=" in ln:
        k, v = ln.split("=", 1)
        os.environ[k.strip()] = v.strip()

MODO = (sys.argv[1] if len(sys.argv) > 1 else "largo").lower()
os.environ["PROMPT_LIGERO"] = "true" if MODO == "ligero" else "false"

import logging          # noqa: E402
import structlog        # noqa: E402
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR))

from app.core import agent as A          # noqa: E402
from app.core.interpretador import interpretar_mensaje  # noqa: E402
from app.core.tools import get_all_products             # noqa: E402
from app.core.tools_context import set_current_tienda   # noqa: E402

TIENDA = "verifika_prod"
set_current_tienda(TIENDA)
N = 3


def prom(fn, *a, **k):
    ts = []
    out = None
    for _ in range(N):
        t0 = time.perf_counter()
        out = fn(*a, **k)
        ts.append(time.perf_counter() - t0)
    return sum(ts) / len(ts), min(ts), max(ts), out


async def aprom(coro_fn, *a, **k):
    ts = []
    for _ in range(N):
        t0 = time.perf_counter()
        await coro_fn(*a, **k)
        ts.append(time.perf_counter() - t0)
    return sum(ts) / len(ts), min(ts), max(ts)


async def main():
    plarge = A._SYSTEM_PROMPT_TEMPLATE.format(business_name="Verifika Tech")
    plig = A._SYSTEM_PROMPT_LIGERO.format(business_name="Verifika Tech")
    print(f"\n=== MEDIR LATENCIA — prompt={MODO} — {N} corridas c/u ===")
    print(f"solver={os.environ.get('LLM_PROVIDER')} "
          f"interp={os.environ.get('INTERPRETER_PROVIDER')}\n")

    print(f"PROMPT Solver NORMAL : {len(plarge):>6} chars  (~{len(plarge)//4} tokens)")
    print(f"PROMPT Solver LIGERO : {len(plig):>6} chars  (~{len(plig)//4} tokens)")
    print(f"En uso ahora        : {'LIGERO' if MODO == 'ligero' else 'NORMAL'}\n")

    # Firestore (catalogo entero). El 1er hit puede pegar a la red; los demas, cache.
    a, mn, mx, _ = prom(get_all_products, tienda_id=TIENDA)
    print(f"Firestore get_all_products: prom {a:.2f}s  (min {mn:.2f} / max {mx:.2f})")

    # Interprete (1 llamada LLM).
    a, mn, mx = await aprom(interpretar_mensaje,
                            "dame el precio de un teclado k380 negro", [],
                            "probe", tienda_id=TIENDA)
    print(f"Interprete (LLM)         : prom {a:.2f}s  (min {mn:.2f} / max {mx:.2f})")

    # Solver (1 llamada LLM, con el prompt segun MODO).
    a, mn, mx = await aprom(A.run_agent,
                            "dame el precio de un teclado k380 negro", [],
                            "probe", tienda_id=TIENDA, user_id="probe")
    print(f"Solver (LLM)             : prom {a:.2f}s  (min {mn:.2f} / max {mx:.2f})")


if __name__ == "__main__":
    asyncio.run(main())
