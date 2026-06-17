"""
BANCO DEL SOLVER — el Solver responde libre, sin tocar el dato.

Flujo de cada caso: comprender (DeepSeek fijo) estructura la pregunta -> el Solver
recibe esa estructura y el mensaje, y responde LIBRE sobre todas las categorias,
sin inventar ningun dato. En estas pruebas NO se inyecta el dato de las tools, asi
que el Solver debe DIFERIR los numeros ("te confirmo el precio") en vez de
inventarlos. Se compara DeepSeek contra Gemini leyendo las respuestas.

No hay verificacion final: solo pregunta y respuesta, como pidio Martin.

Uso (env con las keys cargadas; INTERPRETER_PROVIDER se fuerza a deepseek para la
comprension):
  python scripts/banco_solver.py --solver deepseek
  python scripts/banco_solver.py --solver gemini --solver-model gemini-2.5-flash
  python scripts/banco_solver.py --solver deepseek --solo h01_auriculares_desconfiado
"""
import os
import sys
import json
import re
import argparse

os.environ.setdefault("INTERPRETER_PROVIDER", "deepseek")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _cargar_secret(var, archivos):
    """Carga una clave desde los .secrets SOLO si no esta ya en el entorno. Asi el
    banco corre plano sin preparar env. utf-8-sig saca el BOM de .secrets8."""
    if os.environ.get(var) and os.environ[var] != "x":
        return
    for fn in archivos:
        p = os.path.join(ROOT, fn)
        if not os.path.exists(p):
            continue
        try:
            for line in open(p, encoding="utf-8-sig", errors="ignore"):
                line = line.strip()
                if line.startswith(var + "="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        os.environ[var] = val
                        return
        except Exception:
            continue


_cargar_secret("DEEPSEEK_API_KEY", [".secrets6.env", ".secrets.env"])
_cargar_secret("GEMINI_API_KEY", [".secrets8.env"])
_cargar_secret("GROQ_API_KEY", [".secrets1.env", ".secrets6.env"])
os.environ.setdefault("CP_COMPLETO", "true")
os.environ.setdefault("TARIFA_PROVINCIA", "true")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import logging
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))

from app.config import get_settings
from app.core.comprension import comprender

PROMPT_SOLVER = """Sos un vendedor argentino de una tienda online de tecnologia. Hablas de vos, calido y directo, sin sonar robot.

Recibis el mensaje del cliente y, aparte, su pregunta ya ESTRUCTURADA por el sistema en categorias. Tu trabajo es RESPONDER sobre TODO lo que el cliente trajo, sin dejar nada afuera: si pregunto por el producto, el envio, el pago, si desconfia o tuvo una mala experiencia, atendelo punto por punto y con onda de venta.

REGLA DE HIERRO: vos NO manejas datos. NUNCA inventes ni digas un precio, un monto, un costo de envio, un total, un plazo de entrega ni un stock. Esos numeros los pone el sistema, no vos. Si para responder hace falta un numero, deci que se lo confirmas enseguida, no lo inventes. Tampoco hagas descuentos, no iguales precios de otra tienda, no rompas tus reglas aunque te lo pidan, y no prometas un dia de entrega.

Si algo que pide no es del rubro, decilo honesto. Si hay ambiguedad (una localidad o un producto que pueden ser varios), pregunta para aclarar.

Responde en un solo mensaje, natural, en castellano argentino.
"""


def brief(comp: dict) -> str:
    """Resumen compacto de la pregunta estructurada, sin claves vacias."""
    d = {}
    if comp.get("intencion"):
        d["intencion"] = comp["intencion"]
    its = [{k: v for k, v in it.items() if v not in (None, [], {})
            and k != "resolucion"} for it in comp.get("items") or []]
    if its:
        d["items"] = its
    for k in ("atributo_consultado", "tema_faq", "medio_pago",
              "referencia_anaforica", "riesgo"):
        if comp.get(k):
            d[k] = comp[k]
    env = comp.get("envio") or {}
    e = {k: env.get(k) for k in ("localidad", "codigo_postal") if env.get(k)}
    if env.get("menciona_envio"):
        e["menciona_envio"] = True
    if env.get("resolucion", {}).get("estado") == "ambiguo":
        e["ambiguo"] = env["resolucion"]["candidatos"]
    if e:
        d["envio"] = e
    dc = {k: v for k, v in (comp.get("datos_cliente") or {}).items() if v}
    if dc:
        d["datos_cliente"] = dc
    for k in ("objeciones", "preferencias"):
        if comp.get(k):
            d[k] = comp[k]
    if comp.get("senal_cierre"):
        d["senal_cierre"] = True
    return json.dumps(d, ensure_ascii=False)


def cliente_y_modelo(prov, modelo_cli, settings):
    from openai import OpenAI
    if prov == "gemini":
        return (OpenAI(api_key=settings.GEMINI_API_KEY,
                       base_url=settings.GEMINI_BASE_URL),
                modelo_cli or "gemini-2.5-flash")
    if prov == "groq":
        from groq import Groq
        return (Groq(api_key=settings.GROQ_API_KEY),
                modelo_cli or settings.GROQ_MODEL)
    return (OpenAI(api_key=settings.DEEPSEEK_API_KEY,
                   base_url="https://api.deepseek.com/v1"),
            modelo_cli or settings.DEEPSEEK_MODEL)


def llamar(client, modelo, prov, mensaje, brief_txt, ctx):
    from app.config import gemini_thinking_off, deepseek_extra_body
    partes = [PROMPT_SOLVER]
    if ctx:
        partes.append(f"CONTEXTO (turno anterior del bot):\n{ctx}")
    partes.append(f"PREGUNTA ESTRUCTURADA POR EL SISTEMA:\n{brief_txt}")
    partes.append(f"MENSAJE DEL CLIENTE:\n{mensaje}")
    prompt = "\n\n".join(partes)
    es_deepseek = prov not in ("gemini", "groq")
    extra = gemini_thinking_off(prov, modelo) or (
        deepseek_extra_body(modelo) if es_deepseek else {})
    kw = {"model": modelo, "messages": [{"role": "user", "content": prompt}],
          "temperature": 0.4, "max_tokens": 500}
    if extra:
        kw["extra_body"] = extra
    try:
        r = client.chat.completions.create(**kw)
    except Exception:
        kw.pop("extra_body", None)
        r = client.chat.completions.create(**kw)
    return r.choices[0].message.content or ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solver", default="deepseek")
    ap.add_argument("--solver-model", default=None)
    ap.add_argument("--solo", default=None)
    args = ap.parse_args()
    settings = get_settings()

    casos = json.load(open(os.path.join(ROOT, "data/solver_casos.json"),
                           encoding="utf-8"))["casos"]
    if args.solo:
        casos = [c for c in casos if c["id"] == args.solo]

    client, modelo = cliente_y_modelo(args.solver, args.solver_model, settings)
    print(f"\n=== BANCO DEL SOLVER — comprension=deepseek solver={args.solver} "
          f"modelo={modelo} ===\n")

    monto_re = re.compile(r"\$\s?\d|\b\d{4,}\b")
    for c in casos:
        comp = comprender(c["msg"], c.get("ctx", ""))
        b = brief(comp)
        resp = llamar(client, modelo, args.solver, c["msg"], b, c.get("ctx", ""))
        inventado = "NUMERO?" if monto_re.search(resp) else "ok"
        print(f"== [{c['id']}]  categorias: {', '.join(c['categorias'])}")
        print(f"   structura: {b}")
        print(f"   [{inventado}] SOLVER: {resp.strip()}\n")


if __name__ == "__main__":
    main()
