# -*- coding: utf-8 -*-
"""
Test de la INTEGRACION calculadora <-> cotizar_envio (herramientas mellizas).

Garantiza que el costo de envio se calcula en UN SOLO lugar (cotizar_envio) y que
calculate_total solo lo TOMA, lo cobra una vez por destino y lo suma. Sin Firestore:
se monkeypatchea la FAQ, el catalogo y la tienda, como el resto de los bancos.

Caza la falla vieja de los 3 envios: que la calculadora y el corrector daban
totales distintos porque el envio salia de dos motores. Ahora:
  - calculate_total NO elige zona: pide el costo a cotizar_envio.
  - el costo de un envio (unitario) NO contamina el pool de TOTALES del corrector.
  - multi-destino cobra el envio x cantidad de destinos, coherente entre las dos.

Correr: python3 scripts/prueba_envio_calculadora.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import app.core.tools as T
import app.storage.firestore_client as FS
from app.core.tools_context import set_current_tienda
from app.core.estado_venta import set_envio_localidad
from app.core.verificador import (
    _totales_validos, _envios_validos, verificar_respuesta, autocorregir_montos)

# ── Fixtures deterministas (misma forma que verifika_prod) ───────────────────
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
PRODUCTOS = {
    "M1": {"id": "M1", "nombre": "Mouse Test", "precio_ars": 50000, "stock": 99},
}

_faq = lambda tienda_id=None, force_refresh=False: FAQ
_prod = lambda pid, tienda_id=None: PRODUCTOS.get(str(pid).upper())
# Se parchea en T (nombres top-level) y en FS (imports locales dentro de las tools).
T.get_all_faq = _faq
FS.get_all_faq = _faq
T.get_product_by_id = _prod
FS.get_product_by_id = _prod
# Sin tabla de tarifas por provincia: interior cae al rango generico (no credenciales).
FS.get_config = lambda clave, tienda_id=None: {}
set_current_tienda("test")

resultados = []


def check(nombre, cond):
    resultados.append(bool(cond))
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")


def _proofs(res):
    """Evidencia tipo proof a partir del result de calculate_total."""
    ev = []
    if res.get("proof"):
        ev.append({"tipo": "proof", "tool": "calculate_total", "proof": res["proof"]})
    return ev


# ── CASO 1: 3 envios a CABA (tarifa fija). El solver ya cotizo, asi que la
#    localidad esta en el puente; la calculadora le pide el costo a cotizar_envio. ──
set_envio_localidad("C1425ABC")
r1 = T.calculate_total(
    items=[{"product_id": "M1", "cantidad": 1}],
    items_extra=[{"faq_tema": "costo_envio", "concepto": "lo_que_sea"}],
    destinos=3)
# producto 50000 + envio 4500 x 3 destinos = 63500
check("3 envios CABA: total = 63500 (50000 + 4500x3)",
      r1.get("ok") and r1.get("total_ars") == 63500)
extra_env = next((e for e in r1.get("extras", []) if e.get("faq_tema") == "costo_envio"), {})
check("3 envios CABA: el extra de envio es 13500 con destinos=3",
      extra_env.get("monto") == 13500 and extra_env.get("destinos") == 3)

ev1 = _proofs(r1)
# Ademas, el proof del cotizar_envio unitario (lo que el solver le mostro al cliente).
ev1.append({"tipo": "proof", "tool": "cotizar_envio",
            "proof": T.cotizar_envio("C1425ABC")["proof"]})
tot1 = _totales_validos(ev1)
env1 = _envios_validos(ev1)
check("corrector: el total 63500 es candidato valido", 63500 in tot1)
check("corrector: el envio unitario 4500 NO contamina el pool de TOTALES",
      4500 not in tot1)
check("corrector: el pool de envios tiene unitario 4500 y los 3 envios 13500",
      4500 in env1 and 13500 in env1)
# El mensaje del solver con el total correcto pasa el verificador.
verif1 = verificar_respuesta(
    "Son 50.000 del mouse mas 13.500 de envio, total 63.500.", ev1, "c1")
check("verificador: mensaje con total real 63500 pasa", verif1["ok"])

# ── CASO 2: 3 envios al interior (rango). El total sale como rango, x3. ──
set_envio_localidad("Cordoba")
r2 = T.calculate_total(
    items=[{"product_id": "M1", "cantidad": 1}],
    items_extra=[{"faq_tema": "costo_envio", "concepto": "envio_interior"}],
    destinos=3)
# 50000 + (6500..16000) x 3 = 69500 .. 98000
check("3 envios interior: total_min 69500, total_max 98000",
      r2.get("ok") and r2.get("total_min_ars") == 69500
      and r2.get("total_max_ars") == 98000)

# ── CASO 3: el solver NO cotizo y no hay direccion. La calculadora NO inventa
#    un envio: devuelve ok False pidiendo la zona. ──
set_envio_localidad(None)
r3 = T.calculate_total(
    items=[{"product_id": "M1", "cantidad": 1}],
    items_extra=[{"faq_tema": "costo_envio", "concepto": "envio_caba_gba"}],
    destinos=1)
check("sin zona: la calculadora no inventa envio, pide el dato",
      r3.get("ok") is False)

# ── CASO 4: un solo envio (destinos=1), comportamiento clasico intacto. ──
set_envio_localidad("C1425ABC")
r4 = T.calculate_total(
    items=[{"product_id": "M1", "cantidad": 2}],
    items_extra=[{"faq_tema": "costo_envio", "concepto": "envio_caba_gba"}])
# 2x50000 + 4500 = 104500, un solo envio (sin clave destinos)
extra4 = next((e for e in r4.get("extras", []) if e.get("faq_tema") == "costo_envio"), {})
check("1 envio CABA: total 104500, envio 4500 sin multiplicar",
      r4.get("ok") and r4.get("total_ars") == 104500
      and extra4.get("monto") == 4500 and "destinos" not in extra4)

ok = sum(resultados)
print(f"\n{ok}/{len(resultados)} casos correctos")
sys.exit(0 if ok == len(resultados) else 1)
