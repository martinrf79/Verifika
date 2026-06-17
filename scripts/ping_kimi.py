"""
Ping a Kimi (Moonshot) via NIM de NVIDIA con la clave gratis nvapi-.

Prueba que la API responde, mide latencia, prueba VARIOS ids de modelo (porque
el nombre exacto cambia segun el catalogo) y verifica tool calling (que el
modelo "haga caso" y llame una herramienta). No toca prod: solo lee el .env.

USO (desde la raiz del repo, con el venv de Windows):
    venv-win\\Scripts\\python.exe scripts\\ping_kimi.py .secrets7.env

Argumento 1 opcional: ruta al archivo de secrets (default .secrets6.env).
Si KIMI_MODEL esta seteado en el .env, prueba SOLO ese. Si no, prueba la lista
de candidatos de abajo y te dice cual responde bien.
"""
import io
import os
import sys
import time

# ── Forzar UTF-8 en stdout (Windows usa cp1252 y crashea con acentos/emoji) ──
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

from dotenv import load_dotenv
from openai import OpenAI

# ── Cargar secrets ──────────────────────────────────────────────
secrets_file = sys.argv[1] if len(sys.argv) > 1 else ".secrets6.env"
if os.path.exists(secrets_file):
    load_dotenv(secrets_file, override=True)
    print(f"[ok] secrets cargados de {secrets_file}")
else:
    print(f"[aviso] {secrets_file} no existe, uso variables de entorno del sistema")

# ── Resolver config de Kimi (misma logica que el adapter) ───────
api_key = os.getenv("KIMI_API_KEY", "") or os.getenv("NEMOTRON_API_KEY", "")
base_url = os.getenv("KIMI_BASE_URL", "https://integrate.api.nvidia.com/v1")

if not api_key:
    print("[ERROR] No hay KIMI_API_KEY ni NEMOTRON_API_KEY. Cargalas en el .secretsX.env")
    sys.exit(1)

# Prioridad del modelo: arg 2 en la linea de comando > KIMI_MODEL del .env >
# barrido de candidatos. Asi podes probar cualquier modelo de NVIDIA sin tocar
# el .env, por ejemplo:
#   ping_kimi.py .secrets7.env deepseek-ai/deepseek-v4-flash
arg_model = sys.argv[2].strip() if len(sys.argv) > 2 else ""
forced = arg_model or os.getenv("KIMI_MODEL", "").strip()
if forced:
    candidatos = [forced]
else:
    candidatos = [
        "moonshotai/kimi-k2-instruct",
        "moonshotai/kimi-k2-instruct-0905",
        "moonshotai/kimi-k2.5",
        "moonshotai/kimi-k2.6",
    ]

print(f"[cfg] base_url = {base_url}")
print(f"[cfg] api_key  = {api_key[:10]}...{api_key[-4:]}  (prefijo {api_key.split('-')[0]}-)")
print(f"[cfg] modelos a probar = {candidatos}")
print("-" * 60)

client = OpenAI(api_key=api_key, base_url=base_url, timeout=90)


def _extra_for(model: str) -> dict:
    """Los DeepSeek v4 razonan por default y eso suma 40-50s de latencia.
    Apagamos el thinking para medir la velocidad real (igual que en prod)."""
    if "v4" in model.lower() and "deepseek" in model.lower():
        return {"extra_body": {"chat_template_kwargs": {"thinking": False}}}
    return {}


def prueba_simple(model: str):
    t0 = time.perf_counter()
    r = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Respondes en una sola linea, en espanol."},
            {"role": "user", "content": "Decime solo: KIMI VIVO y nada mas."},
        ],
        temperature=0.0,
        max_tokens=50,
        **_extra_for(model),
    )
    dt = time.perf_counter() - t0
    return r.choices[0].message.content or "", dt


def prueba_tool(model: str):
    tools = [{
        "type": "function",
        "function": {
            "name": "buscar_producto",
            "description": "Busca un producto en el catalogo de la tienda por nombre.",
            "parameters": {
                "type": "object",
                "properties": {"nombre": {"type": "string"}},
                "required": ["nombre"],
            },
        },
    }]
    t0 = time.perf_counter()
    r = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Sos un vendedor. Para buscar productos usa la herramienta buscar_producto."},
            {"role": "user", "content": "Tenes auriculares bluetooth?"},
        ],
        tools=tools,
        tool_choice="auto",
        temperature=0.0,
        max_tokens=120,
        **_extra_for(model),
    )
    dt = time.perf_counter() - t0
    return r.choices[0].message.tool_calls, r.choices[0].message.content, dt


ganador = None
for model in candidatos:
    print(f"\n=== modelo: {model} ===")
    try:
        txt, dt = prueba_simple(model)
        print(f"  [1] respuesta: {txt!r}  ({dt:.2f}s)")
        coherente = "KIMI" in txt.upper() and "VIVO" in txt.upper()
        if not coherente:
            print("      [aviso] respuesta incoherente -> id de modelo probablemente equivocado")
            continue
    except Exception as e:
        print(f"  [1] [ERROR] {type(e).__name__}: {str(e)[:200]}")
        continue

    try:
        tc, content, dt = prueba_tool(model)
        if tc:
            print(f"  [2] [ok] llamo a la tool: {tc[0].function.name}({tc[0].function.arguments})  ({dt:.2f}s)")
        else:
            print(f"  [2] [aviso] no uso tool, texto: {content!r}  ({dt:.2f}s)")
    except Exception as e:
        print(f"  [2] [ERROR] tool calling: {type(e).__name__}: {str(e)[:200]}")

    ganador = model
    break

print("\n" + "-" * 60)
if ganador:
    print(f"[OK] Modelo que funciona: {ganador}")
    print(f"     Fijalo en tu .secretsX.env con:  KIMI_MODEL={ganador}")
else:
    print("[FALLO] Ningun id de modelo respondio coherente.")
    print("        Revisa el nombre exacto en https://build.nvidia.com/models (familia moonshotai)")
    print("        o confirma que la clave nvapi- tenga acceso a Kimi.")
