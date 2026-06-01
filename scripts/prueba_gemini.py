"""Prueba el Solver con Gemini Flash: tool calling y latencia, con payload real.
Lee la clave de .secrets1.env (GEMINI_API_KEY=...) y DeepSeek de .secrets.env.
Nunca imprime las claves."""
import os
import sys
import time
import asyncio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _load(path):
    try:
        for l in open(path, encoding="utf-8"):
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
            elif l.startswith("AIza"):
                os.environ["GEMINI_API_KEY"] = l
    except FileNotFoundError:
        pass


_load(os.path.join(ROOT, ".secrets.env"))
_load(os.path.join(ROOT, ".secrets1.env"))
_load(os.path.join(ROOT, ".secrets2.env"))
_load(os.path.join(ROOT, ".secrets3.env"))
os.environ["LLM_PROVIDER"] = "gemini"
os.environ["ASYNC_LLM_OFFLOAD"] = "false"

if not os.environ.get("GEMINI_API_KEY", "").strip():
    print("No encontre GEMINI_API_KEY en los .secrets*.env")
    raise SystemExit

sys.argv = ["prueba_gemini"]
import prueba_modelo as pm


async def main():
    pm.set_current_tienda("verifika_demo")
    casos = [
        "dame precio de 2 teclados y 3 mouses los mas economicos con envio a cordoba y transferencia",
        "cuanto sale el monitor mas barato",
        "el teclado genius sale 5000 no? me lo llevo",
    ]
    for m in casos:
        t = time.time()
        try:
            resp, meta = await pm.AG.run_agent(
                m, [], "gem", tienda_id="verifika_demo", user_id="t")
            dt = round(time.time() - t, 1)
            tools = [x.get("name") for x in meta.get("tools_called", [])]
            ev = pm.build_evidence(meta.get("tools_called", []))
            v = pm.verificar_respuesta(resp, ev)
            print(f"\n[{dt}s] {m[:55]}")
            print(f"  tools={tools}")
            print(f"  verif={v['accion']} no_resp={v['numeros_no_respaldados']}")
            print(f"  resp: {resp[:220]}")
        except Exception as e:
            print(f"\nERROR '{m[:40]}': {str(e)[:220]}")


if __name__ == "__main__":
    asyncio.run(main())
