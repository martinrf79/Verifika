"""
Molino MULTITURNO: corre conversaciones guionadas de 8 a 12 turnos por el flujo
real (process_message), con el MISMO user_id por conversacion para que el bot
arrastre el historial. Resetea entre conversaciones. Mide lo que el molino de 100
preguntas aisladas NO mide: que el bot mantenga el hilo, los A/B, las confirmaciones
y no se reinicie a mitad de charla.

Uso (via el lanzador, que carga las env vars):
    correr_local.ps1 molino-multi
    correr_local.ps1 molino-multi verifika_prod

Salida: resultados_multiturno.csv (una fila por turno) + resumen por consola.
"""
import asyncio
import csv
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Telemetria SIEMPRE en el molino: la columna tools del CSV separa "el modelo
# no llamo la tool" de "la llamo y el resultado se perdio". Solo memoria.
os.environ.setdefault("TELEMETRIA_TURNO", "true")

from app.core.orchestrator import process_message, reset_user
from app.core.telemetria import tools_compacto
from app.config import get_settings

ARCHIVO = "conversaciones_multiturno.json"
# Etiqueta opcional para no pisar corridas al comparar modelos. La setea el
# lanzador (correr_local.ps1 -KimiModel ...). Sin etiqueta, nombre de siempre.
_TAG = os.getenv("BENCH_TAG", "").strip()
_TAG = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in _TAG)
SALIDA = f"resultados_multiturno_{_TAG}.csv" if _TAG else "resultados_multiturno.csv"
TIENDA = sys.argv[1] if len(sys.argv) > 1 else os.getenv("SMOKE_TIENDA", "verifika_prod")
DELAY = 0.3


def es_fallback(resp: str, s) -> bool:
    return resp in (s.FALLBACK_MESSAGE, s.VERIFIKA_FALLBACK_MESSAGE)


async def main():
    s = get_settings()
    with open(ARCHIVO, encoding="utf-8") as f:
        data = json.load(f)
    convs = data["conversaciones"]

    print("=" * 64)
    print(f"MOLINO MULTITURNO  |  tienda={TIENDA}")
    print(f"Solver={s.LLM_PROVIDER}  Interpreter={s.INTERPRETER_PROVIDER}  "
          f"Corrector={os.getenv('VERIFIKA_CORRECTOR_PROVIDER','deepseek')}/"
          f"{os.getenv('VERIFIKA_CORRECTOR_MODEL','-')}")
    print(f"{len(convs)} conversaciones, {sum(len(c['turnos']) for c in convs)} turnos")
    print("=" * 64)

    filas = []
    t_total = time.time()

    for c in convs:
        cid = c["id"]
        user = f"multiturno_{cid}"
        reset_user(user, tienda_id=TIENDA)
        print(f"\n### {cid}  ({c['escenario']})")

        for i, msg in enumerate(c["turnos"], 1):
            t0 = time.time()
            tools = ""
            try:
                resp = await process_message(
                    user_id=user, raw_message=msg, tienda_id=TIENDA, canal="telegram")
                dt = round(time.time() - t0, 1)
                fb = es_fallback(resp, s)
                tools = tools_compacto()
                marca = "  [FALLBACK]" if fb else ""
                print(f"  T{i:02d} ({dt:4.1f}s){marca}  C: {msg}")
                print(f"            B: {resp[:160]}")
                print(f"            T: {tools[:160]}")
            except Exception as e:
                dt = round(time.time() - t0, 1)
                resp = f"ERROR: {type(e).__name__}: {e}"
                fb = False
                print(f"  T{i:02d} ERROR: {e}")
            filas.append({
                "conv_id": cid, "escenario": c["escenario"], "turno": i,
                "mensaje": msg, "respuesta": resp,
                "tiempo_seg": dt, "fallback": "si" if fb else "no",
                "error": "si" if str(resp).startswith("ERROR:") else "no",
                "tools": tools,
            })
            guardar(filas)
            await asyncio.sleep(DELAY)

    resumen(filas, round(time.time() - t_total, 1))


def guardar(filas):
    with open(SALIDA, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "conv_id", "escenario", "turno", "mensaje", "respuesta",
            "tiempo_seg", "fallback", "error", "tools"])
        w.writeheader()
        w.writerows(filas)


def resumen(filas, t_total):
    n = len(filas)
    fb = sum(1 for r in filas if r["fallback"] == "si")
    err = sum(1 for r in filas if r["error"] == "si")
    tprom = round(sum(r["tiempo_seg"] for r in filas) / n, 1) if n else 0
    print("\n" + "=" * 64)
    print("RESUMEN MULTITURNO")
    print(f"Turnos totales      : {n}")
    print(f"Tiempo promedio/turno: {tprom}s")
    print(f"Fallbacks           : {fb}  ({round(100*fb/n,1) if n else 0}%)")
    print(f"Errores tecnicos    : {err}")
    print(f"Tiempo total corrida: {t_total}s")
    print(f"\nResultados en {SALIDA}")


if __name__ == "__main__":
    asyncio.run(main())
