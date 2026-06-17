# -*- coding: utf-8 -*-
"""
Test de posventa: plazo de devolucion, garantia vigente, validacion de CUIT.
Sin Firestore, sin LLM. Fechas base fijas para determinismo.

Correr: winvenv\\Scripts\\python.exe scripts\\prueba_posventa.py
"""
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.core.posventa import plazo_devolucion, garantia_vigente, validar_cuit

resultados = []


def check(nombre, cond):
    resultados.append(cond)
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")


HOY = datetime.date(2026, 6, 8)

# --- devolucion ---
r = plazo_devolucion()  # sin fecha -> politica generica
check("devolucion sin fecha: politica 10 dias", r["ok"] and not r["tiene_fecha"] and r["dias"] == 10)

r = plazo_devolucion("2026-06-05", hoy=HOY)  # compra hace 3 dias -> vigente
check("devolucion compra reciente: vigente", r["vigente"] and r["limite"] == "2026-06-15")

r = plazo_devolucion("2026-05-01", hoy=HOY)  # compra vieja -> vencida
check("devolucion compra vieja: vencida", not r["vigente"])

# --- garantia ---
r = garantia_vigente("2026-01-10", 12, hoy=HOY)  # 12 meses -> vigente hasta 2027-01-10
check("garantia 12 meses: vigente", r["vigente"] and r["limite"] == "2027-01-10")

r = garantia_vigente("2024-01-10", 12, hoy=HOY)  # vencida
check("garantia vencida", not r["vigente"])

r = garantia_vigente("2026-01-31", 1, hoy=HOY)  # ajuste de mes corto -> 2026-02-28
check("garantia ajusta mes corto (31-ene +1m = 28-feb)", r["limite"] == "2026-02-28")

r = garantia_vigente(None, None)  # faltan datos -> pide
check("garantia sin datos: pide, no asume", not r["ok"])

# --- CUIT (digito verificador) ---
# Base 3071659554 -> digito verificador 0 por el algoritmo (verificado a mano).
check("CUIT valido 30-71659554-0", validar_cuit("30716595540")["valido"])
check("CUIT con guiones valido", validar_cuit("30-71659554-0")["valido"])
check("CUIT invalido (digito mal)", not validar_cuit("30716595549")["valido"])
check("CUIT corto invalido", not validar_cuit("123")["valido"])

ok = sum(resultados)
print(f"\n{ok}/{len(resultados)} casos correctos")
sys.exit(0 if ok == len(resultados) else 1)
