"""Prueba el Solver COMPLETO con Groq, payload real (prompt grande + tools).
Mide latencia y caza errores o rate limit. Lee claves de .secrets.env (DeepSeek)
y .secrets1.env (Groq), nunca las imprime."""
import os
import time
import asyncio


def _load(path):
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()
            elif line.startswith("sk-"):
                os.environ["DEEPSEEK_API_KEY"] = line
            elif line.startswith("gsk_"):
                os.environ["GROQ_API_KEY"] = line
    except FileNotFoundError:
        pass


_load(".secrets.env")
_load(".secrets1.env")
# Forzar Groq en solver e interpretador ANTES de importar la app.
os.environ["LLM_PROVIDER"] = "groq"
os.environ["INTERPRETER_PROVIDER"] = "groq"
os.environ["ASYNC_LLM_OFFLOAD"] = "false"

import sys
sys.argv = ["prueba_groq"]
import prueba_modelo as pm  # dispara setup (firestore simulado, etc)


async def main():
    pm.set_current_tienda("verifika_prod")
    msgs = [
        "dame precio de 2 teclados y 3 mouses los mas economicos con envio a cordoba y transferencia",
        "cuanto sale el monitor mas barato",
    ]
    for m in msgs:
        t = time.time()
        try:
            resp, meta = await pm.AG.run_agent(
                m, [], "groq", tienda_id="verifika_prod", user_id="t")
            dt = round(time.time() - t, 1)
            print(f"\n[{dt}s] {m[:50]}")
            print("  tools:", [x.get("name") for x in meta.get("tools_called", [])])
            print("  resp:", resp[:220])
        except Exception as e:
            print(f"\nERROR en '{m[:40]}':", str(e)[:200])


if __name__ == "__main__":
    asyncio.run(main())
