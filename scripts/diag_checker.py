# -*- coding: utf-8 -*-
"""
DIAGNOSTICO del sobre-bloqueo del Checker. Reproduce los turnos del CLIENTE de un
escenario ya grabado (reports/...json) a traves del bot real, con el log del gate
prendido, y muestra por turno: si bloqueo, por que motivo/tipo, y los textos
marcados. No usa juez ni cliente simulado: solo el bot. Barato.

Correr: winvenv\\Scripts\\python.exe scripts\\diag_checker.py <escenario_id> [report.json]
"""
import os
import sys
import json
import asyncio
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Secretos + tienda + flags ANTES de importar el simulador (que monkeypatchea).
sp = ROOT / ".secrets.env"
if sp.exists():
    for line in open(sp, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()
os.environ["MOLINO_TIENDA"] = os.environ.get("MOLINO_TIENDA", "verifika_prod")

ESC = sys.argv[1] if len(sys.argv) > 1 else "comprador_apurado"
# Report mas nuevo si no se pasa uno.
if len(sys.argv) > 2:
    report = Path(sys.argv[2])
else:
    reps = sorted((ROOT / "reports").glob("simulacion_multiturno_*.json"))
    report = reps[-1]
data = json.load(open(report, encoding="utf-8"))
turns = None
for r in data:
    if r["id"] == ESC:
        turns = r["turns"]
        break
if turns is None:
    raise SystemExit(f"escenario {ESC} no esta en {report.name}")
client_turns = [t["content"] for t in turns if t["role"] == "user"]
print(f"Diag {ESC} desde {report.name}: {len(client_turns)} turnos de cliente\n")

# Importa el simulador: corre su monkeypatch de datos y flags. Despues
# reactivamos los logs INFO (el simulador los silencia a WARNING).
import scripts.simulador_multiturno as SIM  # noqa: E402
import logging  # noqa: E402
import structlog  # noqa: E402

# Capturamos solo los eventos que importan, a stdout, formato corto.
EVENTOS = {"checker_gate_bloqueo", "checker_gate_autofix_ok",
           "checker_gate_autofix_fallo", "gate_gravedad", "verificador_shadow",
           "servicios_bloqueo", "hechos_bloqueo", "diag_verificador"}


def _filtro(logger, method, event_dict):
    if event_dict.get("event") in EVENTOS:
        return event_dict
    raise structlog.DropEvent


structlog.configure(
    processors=[_filtro, structlog.processors.KeyValueRenderer(
        key_order=["event"])],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

ORCH = SIM.ORCH


async def main():
    uid = f"diag_{ESC}"
    SIM.mock_get_conversation(uid, SIM.TIENDA)
    for i, msg in enumerate(client_turns, 1):
        print(f"===== TURNO CLIENTE {i}: {msg[:90]}")
        resp = await ORCH.process_message(
            user_id=uid, raw_message=msg, tienda_id=SIM.TIENDA, canal="telegram")
        es_fb = ("No tengo esa informaci" in resp or "confirmada en el cat" in resp)
        marca = "  [FALLBACK dejame consultar]" if es_fb else ""
        print(f"  BOT: {resp[:160]}{marca}\n")


asyncio.run(main())
