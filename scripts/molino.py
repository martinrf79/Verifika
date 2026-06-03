"""
MOLINO DE EVALUACION — corre un set de preguntas por el bot ENTERO, en paralelo,
y devuelve una planilla de puntaje por grupo. Reutilizable: el set, los flags y la
concurrencia se configuran por env, asi sirve para A/B (baseline vs nueva config).

Mismo flujo que produccion (interpretador + solver + tools + calculadora +
verificadores), sin Firestore ni Telegram (base local monkeypatcheada, leads off).
Corre las preguntas CONCURRENTES con un tope (semaforo), misma efectividad que
serial pero mucho mas rapido. DeepSeek aguanta la concurrencia.

Uso:
  winvenv\\Scripts\\python.exe scripts\\molino.py
  MOLINO_PREGUNTAS=data\\molino_set.jsonl MOLINO_CONC=10 MOLINO_TAG=nuevo \\
    INTERPRETE_RICO=true VERIFICADOR_SERVICIOS=on ... python scripts\\molino.py

Salidas: reports\\molino_<TAG>.json (respuestas) y planilla por consola.
"""
import os
import sys
import csv
import json
import time
import asyncio
import unicodedata
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Clave DeepSeek
_sec = os.path.join(ROOT, ".secrets.env")
if not os.path.exists(_sec):
    raise SystemExit("Falta .secrets.env")
for _l in open(_sec, encoding="utf-8"):
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        k, v = _l.split("=", 1)
        os.environ[k.strip()] = v.strip()
if not os.environ.get("DEEPSEEK_API_KEY", "").startswith("sk-"):
    raise SystemExit("No se encontro DEEPSEEK_API_KEY valida")

# Flags base de prod. Los de defensa se pueden pisar por env para A/B.
os.environ["USE_VERIFIKA"] = "false"
os.environ["USE_LEADS"] = "false"
os.environ["VERIFICADOR_MODE"] = "on"
os.environ["CALC_DEFENSIVA"] = "true"
os.environ["SOLVER_USA_PRESENTACION"] = "true"
os.environ["AUTOFIX"] = "true"
os.environ["ASYNC_LLM_OFFLOAD"] = "true"   # clave para que la concurrencia rinda
os.environ.setdefault("USE_INTERPRETER", "true")
os.environ.setdefault("INTERPRETE_ANCLA_CATALOGO", "true")
os.environ.setdefault("PROMPT_VENTA", "true")
os.environ.setdefault("INTERPRETE_RICO", "true")
os.environ.setdefault("VERIFICADOR_SERVICIOS", "on")
os.environ.setdefault("DIAG_TRACE", "false")

import logging
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))

sys.path.insert(0, ROOT)

TIENDA = os.environ.get("MOLINO_TIENDA", "verifika_2k")
os.environ["TIENDA_ID"] = TIENDA
PREGUNTAS = os.environ.get("MOLINO_PREGUNTAS",
                           os.path.join(ROOT, "data", "molino_set.jsonl"))
CONC = int(os.environ.get("MOLINO_CONC", "10"))
TAG = os.environ.get("MOLINO_TAG", "nuevo")

# ── Base local monkeypatcheada (sin Firestore) ──
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
faq = {x["tema"]: x for x in json.load(
    open(os.path.join(ROOT, f"data/clientes/{TIENDA}/faq.json"), encoding="utf-8"))}

import app.storage.firestore_client as FS
import app.core.tools as T
import app.storage.search as SE
import app.core.agent as AG
import app.core.guardian as GUARD
import app.core.orchestrator as ORCH

def _all_products(tienda_id=None, force_refresh=False): return prods
def _by_id(pid, tienda_id=None): return by_id.get(str(pid).upper()) or by_id.get(pid)
def _cats(tienda_id=None): return sorted({p["categoria"] for p in prods})
def _all_faq(tienda_id=None, force_refresh=False): return faq
def _get_conv(user_id, tienda_id=None):
    return {"history": [], "summary": "", "estado_conversacion": "saludo",
            "proofs_recientes": [], "ultimo_presupuesto": ""}
def _noop(*a, **k): return None
def _get_config(key, default=None, tienda_id=None):
    return "Verifika" if key in ("business_name", "nombre") else default

for mod in (FS, T, SE, AG, GUARD, ORCH):
    if hasattr(mod, "get_all_products"): mod.get_all_products = _all_products
    if hasattr(mod, "get_product_by_id"): mod.get_product_by_id = _by_id
    if hasattr(mod, "get_categories"): mod.get_categories = _cats
    if hasattr(mod, "get_all_faq"): mod.get_all_faq = _all_faq
    if hasattr(mod, "get_config"): mod.get_config = _get_config
FS.get_conversation = _get_conv
ORCH.get_conversation = _get_conv
ORCH.save_conversation = _noop
ORCH.log_message = _noop


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
                    qs.append({"id": f"r{i:03d}", "texto": t, "grupo": "?"})
    return qs


def _n(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()

def clasificar(resp: str) -> str:
    t = _n(resp)
    # Preciso: el fallback tecnico es el mensaje exacto o un [ERROR], NO cualquier
    # respuesta que mencione "problema tecnico" (un bot honesto lo dice al hablar
    # de garantia/soporte).
    if t.startswith("[error") or "tuve un problema tecnico" in t:
        return "fallback_tecnico"
    if "no tengo esa informacion confirmada" in t:
        return "fallback_verificador"
    if "no equivocarme" in t:
        return "confirmacion"
    return "ok"


async def correr(qs):
    sem = asyncio.Semaphore(CONC)
    salidas = [None] * len(qs)
    hechos = [0]

    async def one(idx, q):
        async with sem:
            try:
                resp = await ORCH.process_message(
                    user_id=f"m_{q['id']}", raw_message=q["texto"],
                    tienda_id=TIENDA, canal="telegram")
            except Exception as e:
                resp = f"[ERROR: {str(e)[:160]}]"
            salidas[idx] = {"id": q["id"], "grupo": q.get("grupo", "?"),
                            "pregunta": q["texto"], "respuesta": resp,
                            "clase": clasificar(resp)}
            hechos[0] += 1
            if hechos[0] % 25 == 0:
                print(f"  ... {hechos[0]}/{len(qs)}")

    await asyncio.gather(*(one(i, q) for i, q in enumerate(qs)))
    return salidas


def planilla(salidas):
    porg = defaultdict(list)
    for s in salidas:
        porg[s["grupo"]].append(s)
    clases = ["ok", "confirmacion", "fallback_verificador", "fallback_tecnico"]
    print("\n=== PLANILLA MOLINO (tag %s, tienda %s) ===" % (TAG, TIENDA))
    print("%-10s %5s %5s %6s %8s %9s %6s" %
          ("grupo", "n", "ok", "confir", "fb_verif", "fb_tecn", "largo"))
    for g in sorted(porg):
        ss = porg[g]
        c = {k: sum(1 for s in ss if s["clase"] == k) for k in clases}
        largo = sum(len(s["respuesta"]) for s in ss) // len(ss)
        print("%-10s %5d %5d %6d %8d %9d %6d" %
              (g, len(ss), c["ok"], c["confirmacion"],
               c["fallback_verificador"], c["fallback_tecnico"], largo))
    tot = {k: sum(1 for s in salidas if s["clase"] == k) for k in clases}
    largo = sum(len(s["respuesta"]) for s in salidas) // len(salidas)
    print("%-10s %5d %5d %6d %8d %9d %6d" %
          ("TOTAL", len(salidas), tot["ok"], tot["confirmacion"],
           tot["fallback_verificador"], tot["fallback_tecnico"], largo))
    print("\nFallbacks tecnicos (errores duros, deberian ser 0):",
          [s["id"] for s in salidas if s["clase"] == "fallback_tecnico"][:20])


def main():
    qs = leer(PREGUNTAS)
    print("=== MOLINO: %d preguntas, conc %d, tienda %s, tag %s ===" %
          (len(qs), CONC, TIENDA, TAG))
    flags = ["USE_INTERPRETER", "INTERPRETE_RICO", "INTERPRETE_ANCLA_CATALOGO",
             "VERIFICADOR_SERVICIOS", "PROMPT_VENTA", "AUTOFIX", "VERIFICADOR_MODE"]
    print("flags:", {f: os.environ.get(f) for f in flags})
    t0 = time.time()
    salidas = asyncio.run(correr(qs))
    dt = time.time() - t0
    reportes = os.path.join(ROOT, "reports")
    os.makedirs(reportes, exist_ok=True)
    out = os.path.join(reportes, f"molino_{TAG}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(salidas, f, ensure_ascii=False, indent=2)
    planilla(salidas)
    print("\nTiempo total: %.0fs (%.1fs/pregunta efectiva)" % (dt, dt / len(qs)))
    print("Respuestas en reports/molino_%s.json" % TAG)


if __name__ == "__main__":
    main()
