"""Prueba el INTERPRETADOR con Groq (no usa tools, deberia volar)."""
import os
import sys
import time
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load(p):
    try:
        for l in open(p, encoding="utf-8"):
            l = l.strip()
            if not l or l.startswith("#"):
                continue
            if "=" in l:
                k, v = l.split("=", 1)
                os.environ[k.strip()] = v.strip()
            elif l.startswith("sk-"):
                os.environ["DEEPSEEK_API_KEY"] = l
            elif l.startswith("gsk_"):
                os.environ["GROQ_API_KEY"] = l
    except FileNotFoundError:
        pass


_load(".secrets.env")
_load(".secrets1.env")
os.environ["INTERPRETER_PROVIDER"] = "groq"
os.environ["ASYNC_LLM_OFFLOAD"] = "false"

from app.core.interpretador import interpretar_mensaje


async def main():
    casos = ["quiero comprar 2 teclados genius",
             "si dale lo llevo", "hola que tal", "el negro me gusta"]
    for m in casos:
        t = time.time()
        try:
            r = await interpretar_mensaje(m, [], "it", estado_anterior="explorando")
            print(f"[{round(time.time()-t,2)}s] '{m}' -> intencion={r.get('intencion')} "
                  f"estado={r.get('estado_conversacion')} conf={r.get('confianza')}")
        except Exception as e:
            print(f"ERROR '{m}': {str(e)[:160]}")


if __name__ == "__main__":
    asyncio.run(main())
