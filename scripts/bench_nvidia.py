"""
Benchmark de modelos GRATIS de NVIDIA NIM para elegir el mejor para pruebas.

Mide, por modelo: coherencia, latencia de respuesta simple, y latencia +
obediencia de tool calling (que llame la herramienta). Apaga el "thinking" en
los modelos que razonan por default, asi la comparacion es justa.

USO (desde la raiz, con el venv de Windows):
    venv-win\\Scripts\\python.exe scripts\\bench_nvidia.py .secrets7.env

Lee la clave nvapi- de KIMI_API_KEY o NEMOTRON_API_KEY del archivo que le pases.
"""
import io
import os
import sys
import time

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

from dotenv import load_dotenv
from openai import OpenAI

secrets_file = sys.argv[1] if len(sys.argv) > 1 else ".secrets7.env"
load_dotenv(secrets_file, override=True)
api_key = os.getenv("KIMI_API_KEY", "") or os.getenv("NEMOTRON_API_KEY", "")
base_url = os.getenv("KIMI_BASE_URL", "https://integrate.api.nvidia.com/v1")
if not api_key:
    print("[ERROR] No hay clave nvapi- en", secrets_file)
    sys.exit(1)

client = OpenAI(api_key=api_key, base_url=base_url, timeout=90)

# Candidatos: instruct rapidos con tool calling. Solo se prueban los que tu
# clave realmente ve (se filtran contra /models).
CANDIDATOS = [
    "deepseek-ai/deepseek-v4-flash",
    "deepseek-ai/deepseek-v4-pro",
    "meta/llama-3.3-70b-instruct",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "qwen/qwen3-next-80b-a3b-instruct",
    "qwen/qwen2.5-coder-32b-instruct",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "mistralai/mistral-small-24b-instruct",
    "microsoft/phi-4-mini-instruct",
]

# Modelos que razonan por default -> apagamos thinking (param de NVIDIA NIM).
def _extra(model: str) -> dict:
    m = model.lower()
    razona = ("v4" in m and "deepseek" in m) or "qwen3" in m or "nemotron" in m or "gpt-oss" in m
    if razona:
        return {"extra_body": {"chat_template_kwargs": {"thinking": False}}}
    return {}


def _call(model, messages, extra, **kw):
    """Intenta con el extra (thinking off); si el modelo no lo acepta, reintenta sin el."""
    try:
        return client.chat.completions.create(model=model, messages=messages, **extra, **kw)
    except Exception:
        if extra:
            return client.chat.completions.create(model=model, messages=messages, **kw)
        raise


TOOLS = [{
    "type": "function",
    "function": {
        "name": "buscar_producto",
        "description": "Busca un producto en el catalogo de la tienda por nombre.",
        "parameters": {"type": "object", "properties": {"nombre": {"type": "string"}}, "required": ["nombre"]},
    },
}]


def bench(model):
    extra = _extra(model)
    # 1) coherencia + latencia simple
    t0 = time.perf_counter()
    r = _call(model,
              [{"role": "system", "content": "Respondes en una sola linea, en espanol."},
               {"role": "user", "content": "Decime solo: VIVO y nada mas."}],
              extra, temperature=0.0, max_tokens=40)
    dt1 = time.perf_counter() - t0
    txt = (r.choices[0].message.content or "").strip()
    coherente = "VIVO" in txt.upper() and len(txt) < 40

    # 2) tool calling + latencia
    t0 = time.perf_counter()
    r = _call(model,
              [{"role": "system", "content": "Sos un vendedor. Para buscar productos usa la herramienta buscar_producto."},
               {"role": "user", "content": "Tenes auriculares bluetooth?"}],
              extra, tools=TOOLS, tool_choice="auto", temperature=0.0, max_tokens=120)
    dt2 = time.perf_counter() - t0
    obedece = bool(r.choices[0].message.tool_calls)

    return coherente, dt1, obedece, dt2, txt


# Filtrar candidatos a lo que la clave ve
print(f"[cfg] clave {api_key[:10]}...{api_key[-4:]}  base {base_url}")
print("[..] consultando catalogo visible...")
disponibles = {m.id for m in client.models.list().data}
a_probar = [c for c in CANDIDATOS if c in disponibles]

# Descubrimiento: sumar ids reales del catalogo por familia (rapidos/obedientes),
# por si algun id curado no existe con ese nombre exacto.
CLAVES_FAMILIA = ("llama-3.3", "llama-3.1", "qwen3", "qwen2.5", "gpt-oss",
                  "mistral-small", "phi-4", "nemotron-super", "deepseek-v4")
for mid in sorted(disponibles):
    low = mid.lower()
    if mid in a_probar:
        continue
    if any(k in low for k in CLAVES_FAMILIA) and ("instruct" in low or "gpt-oss" in low or "deepseek-v4" in low or "nemotron-super" in low):
        a_probar.append(mid)

# Cap para que no se eternice (~2 llamadas por modelo)
a_probar = a_probar[:12]
print("[ok] modelos a probar:")
for m in a_probar:
    print("   -", m)
print()

filas = []
for model in a_probar:
    print(f"=== {model} ===")
    try:
        coh, dt1, obe, dt2, txt = bench(model)
        print(f"   simple: {dt1:5.1f}s  coherente={coh}   tool: {dt2:5.1f}s  obedece={obe}   resp={txt!r}")
        filas.append((model, coh, dt1, obe, dt2))
    except Exception as e:
        print(f"   [ERROR] {type(e).__name__}: {str(e)[:140]}")
        filas.append((model, False, 999, False, 999))
    print()

# Ranking: primero los que obedecen y son coherentes, por latencia total
print("=" * 70)
print("RANKING (coherente + obedece, ordenado por latencia total)")
print("=" * 70)
buenos = [f for f in filas if f[1] and f[3]]
buenos.sort(key=lambda f: f[2] + f[4])
if not buenos:
    print("Ninguno paso coherencia + tool calling.")
for i, (model, coh, dt1, obe, dt2) in enumerate(buenos, 1):
    print(f"{i}. {model:48s}  total {dt1 + dt2:5.1f}s  (simple {dt1:.1f}s / tool {dt2:.1f}s)")
print()
otros = [f for f in filas if not (f[1] and f[3])]
if otros:
    print("No aptos (incoherente o no obedece):")
    for model, coh, dt1, obe, dt2 in otros:
        print(f"   - {model:48s} coherente={coh} obedece={obe}")
