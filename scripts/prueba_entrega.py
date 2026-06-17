# -*- coding: utf-8 -*-
"""
Test del motor de entrega: dias habiles (saltea finde y feriados), ventana por
zona, y honestidad (nunca un dia garantizado). Sin Firestore, sin LLM.

Correr: winvenv\\Scripts\\python.exe scripts\\prueba_entrega.py
"""
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.core.entrega import sumar_dias_habiles, estimar_entrega, _es_habil

resultados = []


def check(nombre, cond):
    resultados.append(cond)
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")


# --- dias habiles ---
# Vie 2026-06-05 + 1 habil = Lun 2026-06-08 (saltea sab/dom).
check("viernes +1 habil = lunes (saltea finde)",
      sumar_dias_habiles(datetime.date(2026, 6, 5), 1) == datetime.date(2026, 6, 8))

# Mie 2026-07-08 + 1 habil: saltea el 9 (Independencia), el 10 (puente) y el finde
# -> cae lunes 13. Confirma que saltea feriado, puente y fin de semana encadenados.
check("saltea feriado 9-jul + puente 10-jul + finde -> lunes 13",
      sumar_dias_habiles(datetime.date(2026, 7, 8), 1) == datetime.date(2026, 7, 13))

check("9 de julio NO es habil", not _es_habil(datetime.date(2026, 7, 9)))
check("sabado NO es habil", not _es_habil(datetime.date(2026, 6, 6)))
check("martes comun SI es habil", _es_habil(datetime.date(2026, 6, 9)))

# --- estimar_entrega ---
# Interior, plazo 3-7 habiles, desde lunes 2026-06-08.
r = estimar_entrega("interior", desde=datetime.date(2026, 6, 8))
check("interior: ok y plazo 3-7", r["ok"] and r["plazo_min"] == 3 and r["plazo_max"] == 7)
check("interior: fecha_max posterior a fecha_min", r["fecha_max"] >= r["fecha_min"])
check("interior: mensaje aclara que NO es dia garantizado",
      "no lo garantices" in r["mensaje_para_llm"] or "depende del correo" in r["mensaje_para_llm"])

# CABA plazo 1-3.
r = estimar_entrega("caba", desde=datetime.date(2026, 6, 8))
check("caba: plazo 1-3", r["ok"] and r["plazo_min"] == 1 and r["plazo_max"] == 3)

# Zona None -> pide dato, no estima.
r = estimar_entrega(None)
check("zona None: no ok, pide dato", (not r["ok"]) and r["zona"] is None)

ok = sum(resultados)
print(f"\n{ok}/{len(resultados)} casos correctos")
sys.exit(0 if ok == len(resultados) else 1)
