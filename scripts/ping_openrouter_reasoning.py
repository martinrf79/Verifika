"""
Sonda de latencia/razonamiento en OpenRouter: mide si el parametro reasoning
apaga de verdad el thinking de gemini-2.5-flash o si lo rechaza (y entonces
nuestro reintento limpio duplica cada llamada). Tres variantes, misma pregunta.

Uso (carga la clave de .secrets10.env):
    $env:PYTHONPATH="."; .\venv-win\Scripts\python.exe scripts\ping_openrouter_reasoning.py
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Cargar la clave si no esta en el entorno
if not os.getenv("OPENROUTER_API_KEY"):
    for linea in (ROOT / ".secrets10.env").read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, _, v = linea.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from openai import OpenAI

MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
client = OpenAI(api_key=os.environ["OPENROUTER_API_KEY"],
                base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                timeout=60)

PREGUNTA = [{"role": "user", "content":
             "Respondeme en una sola oracion: cuanto es 38000 menos el 10 por ciento?"}]

VARIANTES = [
    ("sin parametro (thinking default)", {}),
    ("reasoning enabled=false", {"extra_body": {"reasoning": {"enabled": False}}}),
    ("reasoning max_tokens=0", {"extra_body": {"reasoning": {"max_tokens": 0}}}),
    ("reasoning effort=none", {"extra_body": {"reasoning": {"effort": "none"}}}),
]

for nombre, extra in VARIANTES:
    t0 = time.time()
    try:
        r = client.chat.completions.create(
            model=MODEL, messages=PREGUNTA, temperature=0.0, max_tokens=200, **extra)
        dt = time.time() - t0
        u = r.usage
        det = getattr(u, "completion_tokens_details", None)
        rtok = getattr(det, "reasoning_tokens", None) if det else None
        texto = (r.choices[0].message.content or "")[:80]
        print(f"[{nombre}]  {dt:5.1f}s  out={u.completion_tokens}  "
              f"reasoning_tokens={rtok}  -> {texto}")
    except Exception as e:
        dt = time.time() - t0
        print(f"[{nombre}]  {dt:5.1f}s  RECHAZADO: {type(e).__name__}: {str(e)[:160]}")
