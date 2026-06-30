# -*- coding: utf-8 -*-
"""
Test de cotizar_envio: zona (por codigo) + tarifa (dato de tienda) + envio gratis.
Sin Firestore: se monkeypatchea la FAQ y la tienda actual, como el molino.

Correr: winvenv\\Scripts\\python.exe scripts\\prueba_cotizar_envio.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import app.core.tools as T
from app.core.tools_context import set_current_tienda

# FAQ de envio real (misma forma que verifika_prod): caba_gba fijo, interior rango,
# gratis por umbral.
FAQ = {
    "costo_envio": {
        "tema": "costo_envio", "tipo": "cuantitativo",
        "valores": [
            {"concepto": "envio_caba_gba", "modalidad": "fijo", "monto": 4500},
            {"concepto": "envio_interior", "modalidad": "rango",
             "monto_min": 6500, "monto_max": 16000},
            {"concepto": "envio_gratis", "modalidad": "fijo", "monto": 0},
        ],
    }
}
T.get_all_faq = lambda tienda_id=None, force_refresh=False: FAQ
set_current_tienda("test")

resultados = []


def check(nombre, cond):
    resultados.append(cond)
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")


# CABA -> tarifa fija caba_gba
r = T.cotizar_envio("C1425ABC")
check("CABA: ok, fijo 4500, zona caba",
      r["ok"] and r["modalidad"] == "fijo" and r["monto"] == 4500 and r["zona"] == "caba")

# GBA -> misma tarifa metropolitana
r = T.cotizar_envio("Lomas de Zamora")
check("GBA: ok, fijo 4500", r["ok"] and r["monto"] == 4500 and r["zona"] == "gba")

# Tarifa fija POR PROVINCIA (fuente de verdad en config.py): Cordoba tiene su monto.
T.settings.ENVIO_INTERIOR_POR_PROVINCIA = {"cordoba": 6000, "chubut": 12000}
r = T.cotizar_envio("Colon 4500 Cordoba capital")
check("PROVINCIA: Cordoba -> fijo 6000 del mapa por provincia",
      r["ok"] and r["modalidad"] == "fijo" and r["monto"] == 6000
      and r.get("provincia") == "cordoba" and "monto_min" not in r)

# Interior SIN provincia en el mapa -> colapsa al tope publicado (16000), sin rango.
T.settings.ENVIO_INTERIOR_POR_PROVINCIA = {}
r = T.cotizar_envio("Colon 4500 Cordoba capital")
check("INTERIOR sin tarifa de provincia: fijo 16000 (tope, sin rango)",
      r["ok"] and r["modalidad"] == "fijo" and r["monto"] == 16000
      and r["zona"] == "interior" and "monto_min" not in r)

# Zona indeterminada -> no cotiza, pide dato
r = T.cotizar_envio("un pueblito por la ruta 36")
check("INDETERMINADA: no ok, zona None, pide dato",
      (not r["ok"]) and r["zona"] is None)

# Envio gratis por umbral (subtotal estrictamente mayor al umbral default 300000)
r = T.cotizar_envio("Cordoba", subtotal=350000)
check("GRATIS: subtotal alto -> monto 0",
      r["ok"] and r["concepto"] == "envio_gratis" and r["monto"] == 0)

# El PROOF respalda el numero (para el verificador)
r = T.cotizar_envio("C1425ABC")
check("PROOF presente con el monto", r["proof"]["valores"] == [4500])

# UMBRAL DE ENVIO GRATIS sale de la FAQ, NO del setting (regresion del bug
# 250000 vs 300000). Se pone umbral_ars=200000 en la FAQ: una compra de 210000
# tiene que salir gratis aunque el setting de respaldo sea mayor.
FAQ["costo_envio"]["valores"].append(
    {"concepto": "envio_gratis", "modalidad": "fijo", "monto": 0,
     "umbral_ars": 200000})
r = T.cotizar_envio("Cordoba", subtotal=210000)
check("UMBRAL: gratis a 210000 porque la FAQ manda (umbral 200000), no el setting",
      r["ok"] and r["concepto"] == "envio_gratis" and r["monto"] == 0)

ok = sum(resultados)
print(f"\n{ok}/{len(resultados)} casos correctos")
sys.exit(0 if ok == len(resultados) else 1)
