"""
DIAGNOSTICO DE BLOQUEO: muestra el BORRADOR que el solver intento mandar y que
numero exacto bloqueo el verificador, para los casos que cayeron a fallback.
El cliente solo ve el fallback; esto destapa el motivo. Local, sin red.
"""
import os
import sys
import csv
import json
import asyncio

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for _l in open(os.path.join(ROOT, ".secrets.env"), encoding="utf-8"):
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        k, v = _l.split("=", 1); os.environ[k.strip()] = v.strip()
    elif _l.startswith("sk-"):
        os.environ["DEEPSEEK_API_KEY"] = _l

os.environ["USE_INTERPRETER"] = "true"; os.environ["USE_VERIFIKA"] = "false"
os.environ["USE_LEADS"] = "false"; os.environ["VERIFICADOR_MODE"] = "on"
os.environ["CALC_DEFENSIVA"] = "true"; os.environ["INTERPRETE_ANCLA_CATALOGO"] = "true"
os.environ["SOLVER_USA_PRESENTACION"] = "true"; os.environ["ASYNC_LLM_OFFLOAD"] = "false"
os.environ["TIENDA_ID"] = "verifika_2k"

import logging
import structlog
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))
sys.path.insert(0, ROOT)

TIENDA = "verifika_2k"
prods = []
with open(os.path.join(ROOT, f"data/clientes/{TIENDA}/productos.csv"), encoding="utf-8") as f:
    for row in csv.DictReader(f):
        p = {"id": row["id"].strip(), "nombre": row["nombre"].strip(),
             "categoria": row["categoria"].strip().lower(),
             "precio_ars": int(float(row["precio_ars"])), "stock": int(row.get("stock", 0)),
             "descripcion": row.get("descripcion", "")}
        for k, v in row.items():
            if k not in p and v and str(v).strip(): p[k] = str(v).strip()
        prods.append(p)
by_id = {p["id"]: p for p in prods}
faq = {x["tema"]: x for x in json.load(open(os.path.join(ROOT, f"data/clientes/{TIENDA}/faq.json"), encoding="utf-8"))}

import app.storage.firestore_client as FS
import app.core.tools as T
import app.storage.search as SE
import app.core.agent as AG
import app.core.guardian as GUARD
import app.core.orchestrator as ORCH
from app.core.verificador import verificar_respuesta
from app.core.tools_context import set_current_tienda

_ap = lambda tienda_id=None, force_refresh=False: prods
_bi = lambda pid, tienda_id=None: by_id.get(str(pid).upper()) or by_id.get(pid)
_ct = lambda tienda_id=None: sorted({p["categoria"] for p in prods})
_af = lambda tienda_id=None, force_refresh=False: faq
_cfg = lambda key, default=None, tienda_id=None: ("Verifika" if key in ("business_name", "nombre") else default)
for mod in (FS, T, SE, AG, GUARD, ORCH):
    for nm, fn in (("get_all_products", _ap), ("get_product_by_id", _bi),
                   ("get_categories", _ct), ("get_all_faq", _af), ("get_config", _cfg)):
        if hasattr(mod, nm): setattr(mod, nm, fn)


async def main():
    preguntas = [
        "necesito una notebook para la facu que no sea muy pesada y dure la bateria todo el dia",
        "la asus gamer tiene pantalla de 144hz? y cuanto pesa?",
    ]
    set_current_tienda(TIENDA)
    for q in preguntas:
        resp, meta = await ORCH.run_agent(q, [], "diag", tienda_id=TIENDA, user_id="d")
        clean = GUARD.clean_response(resp, tienda_id=TIENDA)
        ev = ORCH._build_evidence_for_verifika(meta.get("tools_called", []), TIENDA)
        v = verificar_respuesta(clean, ev)
        print("\n=== " + q[:60] + " ===")
        print("BORRADOR DEL SOLVER:\n", clean)
        print("VERIFICADOR:", v["accion"], "| no_respaldados:", v["numeros_no_respaldados"])

asyncio.run(main())
