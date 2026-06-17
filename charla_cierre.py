"""
CHARLA DE CIERRE — la maquina nueva PRENDIDA, una charla dificil de punta a punta.

Prende por codigo los flags de la maquina determinista (sin tocar .secrets6.env)
y corre el flujo REAL (process_message) con una sola conversacion que toca las
cinco situaciones de la linea de llegada:

  1. saluda bien en el primer mensaje
  2. NO re-saluda en los siguientes
  3. resuelve un pedido ambiguo PREGUNTANDO con datos reales (confirmacion)
  4. aguanta un cambio de cantidad y de articulos (delta del carrito)
  5. cierra una compra sin inventar un numero (render + envio + link)

Uso (carga .secrets6.env con tus credenciales via el runner):
    .\\correr_local.ps1 py charla_cierre.py

Cada run usa un user_id nuevo, asi arranca con la memoria limpia.
"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# ── Prender la maquina nueva ANTES de importar el orchestrator (config lee env
#    al importar). No toca .secrets6.env: solo fuerza estos flags en este proceso.
FLAGS_ON = [
    # piezas nuevas
    "PROVIDER", "ESTADO_PEDIDO", "CONFIRMACION_PROVIDER", "CARRITO_DELTA",
    "RENDER_CODIGO", "NO_RESALUDO", "TOOLS_MINIMAS",
    # lo que la maquina necesita para funcionar
    "USE_INTERPRETER", "REGISTRO_SESION", "CARRITO_VIGENTE", "SALUDO_CODIGO",
    "ESTADO_NO_REGRESA_SALUDO", "PEDIDO_MULTI", "PEDIDO_PENDIENTE",
    "CIERRE_CONTRATO", "CIERRE_REQUIERE_PRESUPUESTO", "COTIZA_TRANSFERENCIA",
    "QUERY_PLATA_FUERA", "STOCK_GATE", "TARIFA_PROVINCIA", "LINK_PAGO",
    "BUSQUEDA_POR_CODIGO", "TELEMETRIA_TURNO", "ENVIO_GRATIS_AUTO",
    "NUEVA_COMPRA_RESET",
]
for _f in FLAGS_ON:
    os.environ[_f] = "true"

# Forzar DeepSeek (el de produccion, maneja bien las herramientas). El runner
# puede dejar el provider en Groq, que falla las tool-calls con llama.
os.environ["LLM_PROVIDER"] = "deepseek"
os.environ["INTERPRETER_PROVIDER"] = "deepseek"
os.environ["VERIFIKA_CORRECTOR_PROVIDER"] = "deepseek"

from app.core.orchestrator import process_message  # noqa: E402

# Tienda FIJA: el runner mete el nombre del script en SMOKE_TIENDA, no lo usamos.
TIENDA = "verifika_prod"
USER = f"cierre_test_{int(time.time())}"
PAUSA = float(os.getenv("CHARLA_PAUSA", "1.0"))

# Una conversacion, ocho turnos. El comentario dice que prueba cada uno.
CHARLA = [
    ("hola, buenas",                                    "1) saludo calido por codigo"),
    ("que teclados tenes?",                             "2) exploracion + busqueda (NO re-saludar)"),
    ("dame el precio de 3 teclados, capaz inalambricos, no se bien el color",
                                                        "3) AMBIGUO -> confirmacion con opciones reales"),
    ("el mas barato",                                   "4) resuelve el mas barato + estampa el numero"),
    ("sumale un mouse",                                 "5) delta: agrega un articulo"),
    ("mejor que sean 2 teclados",                       "6) delta: cambia la cantidad"),
    ("lo quiero, el envio es a Cordoba Capital",        "7) cierre + zona -> envio + total"),
    ("dale, soy Pedro Gomez, pago por transferencia",   "8) datos -> cierre + link, sin inventar"),
]


async def main():
    print(f"[charla_cierre] tienda={TIENDA} user={USER} turnos={len(CHARLA)} "
          f"flags_nuevos=ON")
    print("=" * 70)
    for i, (msg, que_prueba) in enumerate(CHARLA, 1):
        print(f"\n[{i}] ({que_prueba})")
        print(f"    CLIENTE: {msg}")
        t0 = time.time()
        try:
            resp = await process_message(
                user_id=USER, raw_message=msg, tienda_id=TIENDA,
                canal="telegram")
            print(f"    BOT ({round(time.time() - t0, 1)}s): {resp}")
        except Exception as e:
            print(f"    ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            break
        if i < len(CHARLA):
            await asyncio.sleep(PAUSA)
    print("\n" + "=" * 70)
    print("[fin]")


if __name__ == "__main__":
    asyncio.run(main())
