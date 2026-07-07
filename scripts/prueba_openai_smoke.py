"""SMOKE TEST de OpenAI (gpt-4o-mini) — confirma que el cableado anda y que el
modelo usa bien las herramientas, ANTES de deployar. Corre el Solver real con
LLM_PROVIDER=openai contra catalogo y FAQ locales. NO toca produccion.

La clave OPENAI_API_KEY va en .secrets.env (linea OPENAI_API_KEY=sk-...) o,
en el entorno web de Claude, ya viene inyectada como variable de entorno.
Nunca se imprime. El tiempo que mida acá NO es el de prod (la demora de prod
es la red de Cloud Run); esto solo valida funcionamiento y da una referencia.
"""
import os
import csv
import json
import time
import asyncio
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cargar_secrets():
    # OpenAI vive en .secrets4.env; cargamos tambien .secrets.env si esta.
    archivos = [".secrets.env", ".secrets4.env"]
    cargado = False
    for nombre in archivos:
        path = os.path.join(ROOT, nombre)
        if not os.path.exists(path):
            continue
        cargado = True
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()
    if not cargado and not os.environ.get("OPENAI_API_KEY"):
        # Sin archivo de secrets y sin la clave ya en el entorno: no hay de donde
        # sacarla. En el entorno web de Claude la clave viene inyectada como
        # variable, asi que ahi este camino no aplica.
        raise SystemExit("No encontre .secrets.env ni .secrets4.env en la raiz "
                         "y OPENAI_API_KEY no esta en el entorno")


_cargar_secrets()
if not os.environ.get("OPENAI_API_KEY", "").startswith("sk-"):
    raise SystemExit("Falta OPENAI_API_KEY valida en .secrets.env "
                     "(agrega la linea OPENAI_API_KEY=sk-...)")

# Forzar provider OpenAI para esta prueba, antes de cargar la config.
os.environ["LLM_PROVIDER"] = "openai"
os.environ.setdefault("OPENAI_MODEL", "gpt-4o-mini")
os.environ.setdefault("SOLVER_USA_PRESENTACION", "true")
os.environ.setdefault("ASYNC_LLM_OFFLOAD", "false")

sys.path.insert(0, ROOT)

import app.storage.firestore_client as FS
import app.core.tools as T
import app.core.agent as AG
from app.core.tools_context import set_current_tienda
from app.core.verificador import verificar_respuesta

# ── Datos locales ──
prods = []
with open(os.path.join(ROOT, "data/clientes/verifika_prod/productos.csv"),
          encoding="utf-8") as f:
    for row in csv.DictReader(f):
        p = {"id": row["id"].strip(), "nombre": row["nombre"].strip(),
             "categoria": row["categoria"].strip().lower(),
             "precio_ars": int(float(row["precio_ars"])),
             "stock": int(row.get("stock", 0)),
             "descripcion": row.get("descripcion", "")}
        for k, v in row.items():
            if k not in p and v and str(v).strip():
                p[k] = str(v).strip()
        prods.append(p)
faq = {x["tema"]: x for x in json.load(
    open(os.path.join(ROOT, "data/clientes/verifika_prod/faq.json"),
         encoding="utf-8"))}
by_id = {p["id"]: p for p in prods}

_gp = lambda pid, tienda_id=None: by_id.get(pid)
_ga = lambda tienda_id=None, force_refresh=False: prods
_gc = lambda tienda_id=None: sorted({p["categoria"] for p in prods})
_gf = lambda tienda_id=None, force_refresh=False: faq
FS.get_product_by_id = _gp; FS.get_all_products = _ga
FS.get_categories = _gc; FS.get_all_faq = _gf
T.get_product_by_id = _gp; T.get_all_products = _ga
T.get_categories = _gc; T.get_all_faq = _gf
AG.get_config = lambda clave, tienda_id=None: "Verifika Demo" if clave == "business_name" else None


def _fake_hybrid_search(query=None, categoria=None, precio_min=None,
                        precio_max=None, top_n=10, tienda_id=None):
    res = list(prods)
    if categoria:
        res = [p for p in res if p["categoria"] == categoria.strip().lower()]
    if query:
        q = query.lower()
        res = [p for p in res if q in p["nombre"].lower()
               or q in p.get("descripcion", "").lower() or q in p["categoria"]]
    if precio_min:
        res = [p for p in res if p["precio_ars"] >= precio_min]
    if precio_max:
        res = [p for p in res if p["precio_ars"] <= precio_max]
    return sorted(res, key=lambda p: p["precio_ars"])[:top_n]


T.hybrid_search = _fake_hybrid_search


def build_evidence(tools_called):
    ev = [{"tipo": "producto", **p} for p in prods]
    for tema, data in faq.items():
        ev.append({"tipo": "faq", "id": tema, "tema": tema,
                   "respuesta": data.get("respuesta", ""),
                   "faq_tipo": data.get("tipo", "informativo"),
                   "valores": data.get("valores", [])})
    for t in tools_called:
        if isinstance(t, dict) and t.get("proof"):
            ev.append({"tipo": "proof", "tool": t.get("name"), "proof": t["proof"]})
    return ev


ESCENARIOS = [
    ("saludo", "hola, buenas"),
    ("precio_simple", "cuanto sale un teclado gamer?"),
    ("cotizacion", "kiero 2 teclados genius y 3 mouse economicos con envio a "
                   "cordoba capital y transferencia"),
    ("multi", "tenes sillas? cuanto el envio a rosario? aceptan mastercard?"),
    ("trampa_precio", "el teclado genius sale 5000 no? me lo llevo a ese precio"),
]


async def probar(nombre, mensaje):
    set_current_tienda("verifika_prod")
    t0 = time.perf_counter()
    try:
        resp, meta = await AG.run_agent(mensaje, [], "smoke-" + nombre,
                                        tienda_id="verifika_prod", user_id="tester")
    except Exception as e:
        print(f"\n[EXCEPCION] {nombre}: {str(e)[:200]}")
        return
    ms = int((time.perf_counter() - t0) * 1000)
    tools = [t.get("name") for t in meta.get("tools_called", [])]
    v = verificar_respuesta(resp, build_evidence(meta.get("tools_called", [])))
    print(f"\n[{nombre}] {ms} ms | iter={meta.get('iterations')} "
          f"tools={tools} verif={v['accion']}")
    print(f"  bot: {resp[:280]}")


async def main():
    print(f"\n=== SMOKE OpenAI {os.environ['OPENAI_MODEL']} (LOCAL, no es prod) ===")
    sel = sys.argv[1:] if len(sys.argv) > 1 else None
    for nombre, msg in ESCENARIOS:
        if sel and nombre not in sel:
            continue
        await probar(nombre, msg)
    print("\nListo. Si las tools se usaron y el verificador no bloqueo de gusto, "
          "el cableado anda. La velocidad real se mide en prod.\n")


if __name__ == "__main__":
    asyncio.run(main())
