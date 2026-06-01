"""
PRUEBA DEL BOT COMPLETO (end to end, local).

Corre el FLUJO ENTERO de un mensaje, igual que en produccion: interpretador +
solver con herramientas + calculadora + verificador determinista. Devuelve la
RESPUESTA TAL CUAL le llegaria al cliente. NO toca Firestore ni Telegram: la base
se simula con el catalogo y la FAQ locales, y leads queda apagado.

Sirve para juzgar lo que importa de verdad: que el bot conteste bien, sobre todo
las preguntas simples. Mide la robustez del producto entero, no de una pieza.

Uso:
  winvenv\\Scripts\\python.exe scripts\\prueba_bot_completo.py --tienda verifika_2k --preguntas data\\preguntas_reales_notebook.jsonl
  ... --limit 12     (primeras 12, para ver rapido)
"""
import os
import sys
import csv
import json
import asyncio
import argparse

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Cargar la clave de DeepSeek (sin imprimirla).
_sec = os.path.join(ROOT, ".secrets.env")
if not os.path.exists(_sec):
    raise SystemExit("Falta .secrets.env")
for _l in open(_sec, encoding="utf-8"):
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        k, v = _l.split("=", 1)
        os.environ[k.strip()] = v.strip()
    elif _l.startswith("sk-"):
        os.environ["DEEPSEEK_API_KEY"] = _l
if not os.environ.get("DEEPSEEK_API_KEY", "").startswith("sk-"):
    raise SystemExit("No se encontro DEEPSEEK_API_KEY valida")

# Flags del bot, estado deseado de prod, ANTES de importar la app.
os.environ["USE_INTERPRETER"] = "true"
os.environ["USE_VERIFIKA"] = "false"        # gatea el verificador deterministico
os.environ["USE_LEADS"] = "false"           # sin Telegram
os.environ["VERIFICADOR_MODE"] = "on"
os.environ["CALC_DEFENSIVA"] = "true"
os.environ["INTERPRETE_ANCLA_CATALOGO"] = "true"
os.environ["SOLVER_USA_PRESENTACION"] = "true"
os.environ["ASYNC_LLM_OFFLOAD"] = "false"
os.environ.setdefault("DIAG_TRACE", "false")

# Silenciar logs INFO para ver solo las respuestas.
import logging
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))

sys.path.insert(0, ROOT)

# Tienda a usar.
TIENDA = "verifika_2k"
if "--tienda" in sys.argv:
    TIENDA = sys.argv[sys.argv.index("--tienda") + 1]
os.environ["TIENDA_ID"] = TIENDA

# ── Cargar catalogo y FAQ locales ──
prods = []
with open(os.path.join(ROOT, f"data/clientes/{TIENDA}/productos.csv"),
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
by_id = {p["id"]: p for p in prods}
faq_list = json.load(open(os.path.join(ROOT, f"data/clientes/{TIENDA}/faq.json"),
                          encoding="utf-8"))
faq = {x["tema"]: x for x in faq_list}

# ── Monkeypatch: base simulada en memoria, sin Firestore ni red ──
import app.storage.firestore_client as FS
import app.core.tools as T
import app.storage.search as SE
import app.core.agent as AG
import app.core.guardian as GUARD
import app.core.orchestrator as ORCH

def _all_products(tienda_id=None, force_refresh=False):
    return prods
def _by_id(pid, tienda_id=None):
    return by_id.get(str(pid).upper()) or by_id.get(pid)
def _cats(tienda_id=None):
    return sorted({p["categoria"] for p in prods})
def _all_faq(tienda_id=None, force_refresh=False):
    return faq
def _get_conv(user_id, tienda_id=None):
    return {"history": [], "summary": "", "estado_conversacion": "saludo",
            "proofs_recientes": [], "ultimo_presupuesto": ""}
def _noop(*a, **k):
    return None
def _get_config(key, default=None, tienda_id=None):
    if key in ("business_name", "nombre"):
        return "Verifika"
    return default

for mod in (FS, T, SE, AG, GUARD, ORCH):
    if hasattr(mod, "get_all_products"):
        mod.get_all_products = _all_products
    if hasattr(mod, "get_product_by_id"):
        mod.get_product_by_id = _by_id
    if hasattr(mod, "get_categories"):
        mod.get_categories = _cats
    if hasattr(mod, "get_all_faq"):
        mod.get_all_faq = _all_faq
    if hasattr(mod, "get_config"):
        mod.get_config = _get_config
FS.get_conversation = _get_conv
ORCH.get_conversation = _get_conv
ORCH.save_conversation = _noop
ORCH.log_message = _noop


async def correr(qs):
    salidas = []
    for i, q in enumerate(qs, 1):
        try:
            resp = await ORCH.process_message(
                user_id=f"test_{q['id']}", raw_message=q["texto"],
                tienda_id=TIENDA, canal="telegram")
        except Exception as e:
            resp = f"[ERROR: {str(e)[:160]}]"
        salidas.append({"id": q["id"], "pregunta": q["texto"], "respuesta": resp})
        print(f"\n--- {q['id']} ---")
        print(f"CLIENTE: {q['texto']}")
        print(f"BOT: {resp}")
    return salidas


def leer(path):
    qs = []
    with open(path, encoding="utf-8") as f:
        if path.lower().endswith(".jsonl"):
            for line in f:
                line = line.strip()
                if line:
                    qs.append(json.loads(line))
        else:
            for i, line in enumerate(f, 1):
                t = line.strip()
                if t and not t.startswith("#"):
                    qs.append({"id": f"r{i:03d}", "texto": t})
    return qs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tienda", default="verifika_2k")
    ap.add_argument("--preguntas",
                    default=os.path.join(ROOT, "data", "preguntas_reales_notebook.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    qs = leer(args.preguntas)
    if args.limit:
        qs = qs[:args.limit]
    print(f"=== BOT COMPLETO sobre {len(qs)} preguntas (tienda {TIENDA}) ===")
    salidas = asyncio.run(correr(qs))

    reportes = os.path.join(ROOT, "reports")
    os.makedirs(reportes, exist_ok=True)
    with open(os.path.join(reportes, "respuestas_bot_completo.json"), "w",
              encoding="utf-8") as f:
        json.dump(salidas, f, ensure_ascii=False, indent=2)
    print(f"\n\nRespuestas guardadas en reports/respuestas_bot_completo.json "
          f"({len(salidas)} respuestas)")


if __name__ == "__main__":
    main()
