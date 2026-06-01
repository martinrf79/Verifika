"""
Script de pruebas adversariales para Verifika.

Llama directamente a process_message del orchestrator, sin pasar por webhook.
Lee preguntas_100.json, dispara cada pregunta secuencialmente con 0.5s de delay,
y guarda resultados en resultados_pruebas.csv.

Uso:
    cd ~/agente-v4
    source venv/bin/activate
    python correr_pruebas.py

Salida:
    resultados_pruebas.csv con columnas: id, categoria, pregunta, respuesta, derivo, tiempo_seg
"""

import asyncio
import csv
import json
import sys
import time
from pathlib import Path

# Asegurar que app sea importable
sys.path.insert(0, str(Path(__file__).parent))

from app.core.orchestrator import process_message

ARCHIVO_PREGUNTAS = "preguntas_100.json"
ARCHIVO_SALIDA = "resultados_pruebas.csv"
TIENDA_ID = "verifika"
USER_ID_TEST = "test_adversarial_user"
DELAY_ENTRE_PREGUNTAS = 0.5

# Frases que indican derivacion (segun resumen, el bot no usa "humano" ni "derivar")
INDICADORES_DERIVACION = [
    "dejame consultar",
    "dejame averiguarte",
    "tengo que chequear",
    "te confirmo en un rato",
    "vuelvo con la respuesta",
    "consultar con el area",
]


def detecto_derivacion(respuesta: str) -> bool:
    """Detecta si la respuesta es una derivacion al dueño."""
    r = respuesta.lower()
    return any(ind in r for ind in INDICADORES_DERIVACION)


async def correr_pruebas():
    # Cargar preguntas
    with open(ARCHIVO_PREGUNTAS, encoding="utf-8") as f:
        data = json.load(f)

    preguntas = data["preguntas"]
    total = len(preguntas)
    print(f"Cargadas {total} preguntas. Tienda: {TIENDA_ID}")
    print(f"Estimacion de tiempo: {total * (DELAY_ENTRE_PREGUNTAS + 2):.0f} segundos aprox\n")

    resultados = []
    t_inicio_total = time.time()

    for i, p in enumerate(preguntas, 1):
        pid = p["id"]
        categoria = p["categoria"]
        pregunta = p["pregunta"]

        print(f"[{i}/{total}] ({categoria}) {pregunta[:60]}...")

        t0 = time.time()
        try:
            respuesta = await process_message(
                user_id=f"{USER_ID_TEST}_{pid}",
                raw_message=pregunta,
                tienda_id=TIENDA_ID,
            )
            tiempo = round(time.time() - t0, 2)
            derivo = detecto_derivacion(respuesta)
            print(f"   -> ({tiempo}s) {'DERIVO' if derivo else 'RESPONDIO'}: {respuesta[:80]}\n")
        except Exception as e:
            respuesta = f"ERROR: {type(e).__name__}: {e}"
            tiempo = round(time.time() - t0, 2)
            derivo = False
            print(f"   -> ERROR: {e}\n")

        resultados.append({
            "id": pid,
            "categoria": categoria,
            "pregunta": pregunta,
            "respuesta": respuesta,
            "derivo": "si" if derivo else "no",
            "tiempo_seg": tiempo,
        })

        # Guardar incrementalmente por si se corta
        guardar_csv(resultados)

        await asyncio.sleep(DELAY_ENTRE_PREGUNTAS)

    t_total = round(time.time() - t_inicio_total, 1)
    print(f"\nListo. {total} preguntas en {t_total}s. Resultados en {ARCHIVO_SALIDA}")
    print_resumen(resultados)


def guardar_csv(resultados):
    with open(ARCHIVO_SALIDA, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "categoria", "pregunta", "respuesta", "derivo", "tiempo_seg"],
        )
        writer.writeheader()
        writer.writerows(resultados)


def print_resumen(resultados):
    total = len(resultados)
    derivadas = sum(1 for r in resultados if r["derivo"] == "si")
    errores = sum(1 for r in resultados if r["respuesta"].startswith("ERROR:"))
    tiempo_prom = round(sum(r["tiempo_seg"] for r in resultados) / total, 2)

    por_cat = {}
    for r in resultados:
        c = r["categoria"]
        if c not in por_cat:
            por_cat[c] = {"total": 0, "derivadas": 0}
        por_cat[c]["total"] += 1
        if r["derivo"] == "si":
            por_cat[c]["derivadas"] += 1

    print("\n--- RESUMEN ---")
    print(f"Total preguntas: {total}")
    print(f"Derivadas al dueño: {derivadas} ({round(100*derivadas/total,1)}%)")
    print(f"Errores tecnicos: {errores}")
    print(f"Tiempo promedio por respuesta: {tiempo_prom}s")
    print("\nPor categoria:")
    for cat, stats in por_cat.items():
        pct = round(100 * stats["derivadas"] / stats["total"], 1)
        print(f"  {cat}: {stats['derivadas']}/{stats['total']} derivadas ({pct}%)")


if __name__ == "__main__":
    asyncio.run(correr_pruebas())
