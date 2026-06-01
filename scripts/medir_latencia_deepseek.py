"""
MEDIDOR DE LATENCIA DE DEEPSEEK — mide cuanto tarda DeepSeek por llamada AHORA.

No toca produccion. Lee la clave de .secrets.env, nunca la imprime.
Hace dos tipos de llamada, cada una varias veces, y resume min/mediana/max:
  - liviana: prompt corto, sin tools. Piso de latencia del proveedor.
  - realista: system prompt completo del Solver + un mensaje de cotizacion,
    para ver lo que pesa de verdad cada turno.
Objetivo: confirmar si los segundos se van en la inferencia de DeepSeek
(latencia del proveedor) y no en nuestro codigo.
"""
import os
import sys
import time
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _cargar_secrets():
    path = os.path.join(ROOT, ".secrets.env")
    if not os.path.exists(path):
        raise SystemExit("Falta .secrets.env en la raiz del proyecto")
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()
            elif line.startswith("sk-"):
                os.environ["DEEPSEEK_API_KEY"] = line


_cargar_secrets()
key = os.environ.get("DEEPSEEK_API_KEY", "")
if not key.startswith("sk-"):
    raise SystemExit("No se encontro DEEPSEEK_API_KEY valida en .secrets.env")

from openai import OpenAI

client = OpenAI(api_key=key, base_url="https://api.deepseek.com/v1", timeout=60)
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# System prompt largo, representativo del Solver (sin pegar el real entero,
# pero del mismo orden de tamano para que el prefill pese parecido).
SYSTEM_LARGO = ("Sos un vendedor de una tienda online argentina de tecnologia "
                "y perifericos gamer. Hablas en espanol argentino, tuteando. "
                "Nunca inventes precios, stock ni caracteristicas: esos datos "
                "salen de las herramientas. Antes de afirmar algo de un "
                "producto, llamas search_products o get_product_details. Para "
                "envios, pagos, garantia, devoluciones, horarios o factura usas "
                "query_faq. Todo total, multiplicacion o presupuesto sale de "
                "calculate_total, nunca de cabeza. Si hay rango, presentas las "
                "dos puntas. Conciso, una a tres oraciones, texto plano sin "
                "markdown, precios con punto de mil. ") * 6


def medir(nombre, n, hacer_llamada):
    tiempos = []
    print(f"\n{nombre} ({n} llamadas):")
    for i in range(n):
        t0 = time.perf_counter()
        try:
            hacer_llamada()
        except Exception as e:
            print(f"  llamada {i+1}: ERROR {str(e)[:120]}")
            continue
        ms = int((time.perf_counter() - t0) * 1000)
        tiempos.append(ms)
        print(f"  llamada {i+1}: {ms} ms")
    if tiempos:
        print(f"  -> min {min(tiempos)} ms | mediana "
              f"{int(statistics.median(tiempos))} ms | max {max(tiempos)} ms")
    return tiempos


def llamada_liviana():
    client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "Decime hola en una palabra."}],
        temperature=0.2,
        max_tokens=20,
    )


def llamada_realista():
    client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_LARGO},
            {"role": "user", "content": "hola, cuanto sale un teclado gamer y "
             "el envio a cordoba capital pagando por transferencia?"},
        ],
        temperature=0.2,
        max_tokens=400,
    )


if __name__ == "__main__":
    print(f"Modelo: {MODEL} | endpoint: api.deepseek.com")
    print(f"System prompt realista: ~{len(SYSTEM_LARGO)} caracteres")
    livianas = medir("LIVIANA  (prompt corto, sin tools)", 4, llamada_liviana)
    realistas = medir("REALISTA (system largo + cotizacion)", 4, llamada_realista)

    print("\n" + "=" * 60)
    print("RESUMEN")
    if livianas:
        print(f"  Piso del proveedor (liviana): mediana "
              f"{int(statistics.median(livianas))} ms")
    if realistas:
        med = int(statistics.median(realistas))
        print(f"  Llamada realista de un turno: mediana {med} ms")
        print(f"  Un turno de cotizacion encadena 4-5 de estas en serie:")
        print(f"    estimado ~{med*4//1000}-{med*5//1000} s solo en DeepSeek")
