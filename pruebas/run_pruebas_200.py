"""
Ejecutor de la bateria de pruebas Verifika v2.
Captura ademas si fue fallback, longitud de respuesta y productos mencionados.
"""
import asyncio
import csv
import sys
import os
import time
import re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["TIENDA_ID"] = "verifika_prod"

from app.core.orchestrator import process_message

FRASES_FALLBACK = [
    "no tengo esa informacion confirmada en el catalogo",
    "dejame consultar y te confirmo",
    "dejame consultar con el area",
    "ese dato preciso lo tengo que chequear",
    "dejame averiguarte eso bien",
    "esa info la tengo que chequear",
]

JUICIOS_VALOR = [
    "vale la pena", "es mejor", "va muy bien", "la mas comoda",
    "te recomiendo", "yo elegiria", "mi opinion", "en mi opinion",
    "es el mejor", "es la mejor", "te conviene",
]


def normalizar(t):
    if not t:
        return ""
    t = t.lower()
    for a,b in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ñ","n")]:
        t = t.replace(a,b)
    return t


def es_fallback(r):
    rn = normalizar(r)
    return any(f in rn for f in FRASES_FALLBACK)


def tiene_juicio_valor(r):
    rn = normalizar(r)
    encontrados = [j for j in JUICIOS_VALOR if j in rn]
    return encontrados


async def correr_una_prueba(caso, idx, total):
    user_id = f"test_prueba_{caso['id']}"
    pregunta = caso["pregunta"]
    print(f"[{idx}/{total}] {caso['id']}: {pregunta[:60]}", flush=True)
    t0 = time.time()
    try:
        respuesta = await process_message(user_id, pregunta, tienda_id="verifika_prod")
        latencia_ms = int((time.time() - t0) * 1000)
        error = ""
    except Exception as e:
        respuesta = ""
        latencia_ms = int((time.time() - t0) * 1000)
        error = str(e)[:200]
    return {
        "id": caso["id"],
        "categoria": caso["categoria"],
        "comportamiento_esperado": caso["comportamiento_esperado"],
        "pregunta": pregunta,
        "respuesta": respuesta,
        "latencia_ms": latencia_ms,
        "longitud_respuesta": len(respuesta),
        "es_fallback": "si" if es_fallback(respuesta) else "no",
        "juicios_valor_detectados": ",".join(tiene_juicio_valor(respuesta)),
        "error": error,
        "user_id": user_id,
    }


async def main():
    ruta_dataset = os.path.join(os.path.dirname(__file__), "dataset_200.csv")
    with open(ruta_dataset) as f:
        casos = list(csv.DictReader(f))
    print(f"Total casos: {len(casos)}")
    print(f"Inicio: {datetime.now().isoformat()}")
    print("-" * 60)
    resultados = []
    for idx, caso in enumerate(casos, 1):
        r = await correr_una_prueba(caso, idx, len(casos))
        resultados.append(r)
        await asyncio.sleep(0.3)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_informe = os.path.join(os.path.dirname(__file__), f"informe_200_{timestamp}.csv")
    with open(ruta_informe, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(resultados[0].keys()))
        writer.writeheader()
        writer.writerows(resultados)
    print("-" * 60)
    print(f"Fin: {datetime.now().isoformat()}")
    print(f"Informe: {ruta_informe}")
    total = len(resultados)
    fallbacks = sum(1 for r in resultados if r["es_fallback"] == "si")
    con_juicio = sum(1 for r in resultados if r["juicios_valor_detectados"])
    errores = sum(1 for r in resultados if r["error"])
    lat_promedio = sum(r["latencia_ms"] for r in resultados) / total if total else 0
    print(f"Total: {total} | Errores: {errores} | Fallbacks: {fallbacks} | Con juicios de valor: {con_juicio} | Latencia: {lat_promedio:.0f} ms")


if __name__ == "__main__":
    asyncio.run(main())
