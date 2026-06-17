"""Reproduce la llamada del interpretador contra Gemini directo, con y sin
reasoning_effort=none, para ver si el thinking se apaga de verdad en requests
que piden JSON. Carga la clave de .secrets8.env."""
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if not os.getenv("GEMINI_API_KEY"):
    for linea in (ROOT / ".secrets8.env").read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, _, v = linea.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from openai import OpenAI

c = OpenAI(api_key=os.environ["GEMINI_API_KEY"],
           base_url=os.environ.get("GEMINI_BASE_URL",
                                   "https://generativelanguage.googleapis.com/v1beta/openai/"),
           timeout=30)

PROMPT = ("Analiza este mensaje de un cliente de una tienda y devolve SOLO un "
          "JSON valido con claves intencion, confianza (0 a 1) y "
          "producto_resuelto. Mensaje: hola, busco un mouse para jugar")

VARIANTES = [
    ("sin extra (default)", {}),
    ("reasoning_effort=none", {"reasoning_effort": "none"}),
    ("google thinking_budget=0", {"extra_body": {"google": {"thinking_config": {"thinking_budget": 0}}}}),
]

print(f"base_url: {c.base_url}")
for nombre, extra in VARIANTES:
    t0 = time.time()
    try:
        r = c.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[{"role": "user", "content": PROMPT}],
            temperature=0.0, max_tokens=400,
            **({"extra_body": extra} if extra else {}))
        u = r.usage
        det = getattr(u, "completion_tokens_details", None)
        rt = getattr(det, "reasoning_tokens", None) if det else None
        cont = r.choices[0].message.content or ""
        print(f"[{nombre}]  {time.time()-t0:5.1f}s  out={u.completion_tokens}  "
              f"reasoning_tokens={rt}  contenido={len(cont)} chars  -> {cont[:60]!r}")
    except Exception as e:
        print(f"[{nombre}]  {time.time()-t0:5.1f}s  EXCEPCION "
              f"{type(e).__name__}: {str(e)[:160]}")
