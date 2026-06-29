# -*- coding: utf-8 -*-
"""
Test determinista de la AUTOCORRECCION ANCLADA AL CONCEPTO (extension a precio y
envio, ademas del total). Sin Firestore, sin credenciales, sin LLM.

Verifica que autocorregir_montos, ademas de los totales:
  - corrija un costo de ENVIO mal tipeado por el real (pool de cotizar_envio),
  - NO toque un total grande aunque la frase mencione envio,
  - corrija un PRECIO mal tipeado por el del producto que el solver NOMBRO
    (ancla nombre <-> precio, no cercania numerica),
  - NO toque un precio cuando el nombre matchea DOS productos (ambiguo),
  - deje intacto un precio ya correcto,
  - estampe el 'concepto' en cada correccion para el log.

Correr: python scripts/prueba_autocorrige_concepto.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.core.verificador import autocorregir_montos

# ── ENVIO ────────────────────────────────────────────────────────────────
# Un PROOF de cotizar_envio con tarifa fija 5.000.
EVID_ENVIO = [
    {"tipo": "proof", "tool": "cotizar_envio",
     "proof": {"tipo": "envio", "valores": [5000], "resultado": 5000}},
]
# ── PRECIO (un solo producto) ────────────────────────────────────────────
EVID_PRECIO = [
    {"tipo": "producto", "id": "TEC001",
     "nombre": "Teclado Mecanico Razer BlackWidow V4", "precio_ars": 295000},
]
# ── PRECIO ambiguo (dos productos comparten 'teclado razer') ─────────────
EVID_AMBIGUO = [
    {"tipo": "producto", "id": "TEC001",
     "nombre": "Teclado Razer Huntsman", "precio_ars": 280000},
    {"tipo": "producto", "id": "TEC002",
     "nombre": "Teclado Razer BlackWidow", "precio_ars": 295000},
]

# (texto, evidencia, debe_corregir, valor_esperado, concepto_esperado, etiqueta)
CASOS = [
    ("Perfecto, el envio a Cordoba te sale $7.000.",
     EVID_ENVIO, True, 5000, "envio", "envio mal tipeado (7k -> 5k)"),
    ("Con el envio el total te queda $258.000.",
     EVID_ENVIO, False, None, None, "total grande en frase con envio: no es envio"),
    ("El Teclado Razer BlackWidow esta a $999.000, una masa.",
     EVID_PRECIO, True, 295000, "precio", "precio mal tipeado anclado al nombre"),
    ("El Teclado Razer esta a $999.000.",
     EVID_AMBIGUO, False, None, None, "nombre matchea dos productos: ambiguo, no toca"),
    ("El Teclado Razer BlackWidow esta a $295.000.",
     EVID_PRECIO, False, None, None, "precio ya correcto, nada que corregir"),
]


def main():
    ok = 0
    for texto, evid, debe, esperado, concepto, etiq in CASOS:
        res = autocorregir_montos(texto, evid, trace_id=etiq)
        corrigio = res["cambiada"]
        bien = corrigio == debe
        if bien and debe:
            corr = res["correcciones"][0] if res["correcciones"] else {}
            valor_ok = f"{esperado:,}".replace(",", ".") in res["respuesta"]
            bien = (valor_ok and corr.get("a") == esperado
                    and corr.get("concepto") == concepto
                    and res["verificacion"].get("ok"))
        ok += bien
        estado = "OK " if bien else "FALLA"
        signo = "CORRIGE" if corrigio else "deja   "
        print(f"[{estado}] {signo} | esperado={'corrige' if debe else 'deja'} | "
              f"{etiq} -> {res['correcciones']}")
    print(f"\n{ok}/{len(CASOS)} casos correctos")
    sys.exit(0 if ok == len(CASOS) else 1)


if __name__ == "__main__":
    main()
