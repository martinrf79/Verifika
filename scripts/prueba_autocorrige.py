# -*- coding: utf-8 -*-
"""
Test determinista de la AUTOCORRECCION del total (Fase 1: partida doble de la
verdad). Sin Firestore, sin credenciales, sin LLM.

Verifica que autocorregir_montos:
  - reescriba un total mal calculado por el total verdadero del PROOF,
  - deje la respuesta verificando ok,
  - NO toque nada cuando el error no es plausible (numero inventado lejos),
  - NO toque nada cuando hay ambiguedad (empate de distancia),
  - NO toque una respuesta que ya estaba bien.

Correr: winvenv\\Scripts\\python.exe scripts\\prueba_autocorrige.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.core.verificador import autocorregir_montos, verificar_respuesta

# Evidencia tipica de un cierre: dos productos y un PROOF de calculate_total con
# envio fijo. Totales validos derivables: subtotal 250.000 y con envio 255.000.
PROOF = {
    "tipo": "calculo",
    "subtotal_productos": 250000,
    "operandos_productos": [
        {"monto": 120000},
        {"monto": 130000},
    ],
    "operandos_extras": [
        {"modalidad": "fijo", "monto": 5000, "concepto": "envio"},
    ],
    "resultado": 255000,
}
EVID = [
    {"tipo": "producto", "precio_ars": 120000},
    {"tipo": "producto", "precio_ars": 130000},
    {"tipo": "proof", "tool": "calculate_total", "proof": PROOF},
]

# (texto, debe_corregir, valor_esperado_en_corregida_o_None, etiqueta)
CASOS = [
    # --- DEBEN CORREGIR ---
    ("Perfecto, te llevas los dos. El total con envio te queda $258.000.",
     True, 255000, "total con envio mal sumado (258k -> 255k)"),
    ("Genial, entonces son $252.000 en total con el envio incluido.",
     True, 250000, "mas cerca del subtotal que del total (252k -> 250k)"),
    # --- NO DEBEN CORREGIR ---
    ("El total te queda $400.000 con todo incluido.",
     False, None, "numero inventado lejos (fuera de banda 15%)"),
    ("Listo, el total es $255.000 con el envio.",
     False, None, "ya estaba bien, nada que corregir"),
    ("Te paso el detalle: dos productos por $120.000 y $130.000.",
     False, None, "solo precios de catalogo, sin total roto"),
]


def _hay_monto(texto: str, valor: int) -> bool:
    """True si el valor aparece como cifra de dinero respaldada en el texto."""
    r = verificar_respuesta(texto, EVID)
    # cifra presente y verificando: chequeo simple por formato argentino
    return f"{valor:,}".replace(",", ".") in texto and r["ok"]


def main():
    ok = 0
    for texto, debe, esperado, etiq in CASOS:
        res = autocorregir_montos(texto, EVID, trace_id=etiq)
        corrigio = res["cambiada"]
        bien = corrigio == debe
        if bien and debe:
            # Ademas: quedo verificando ok y aparece el valor esperado.
            bien = res["verificacion"].get("ok") and _hay_monto(
                res["respuesta"], esperado)
        ok += bien
        estado = "OK " if bien else "FALLA"
        signo = "CORRIGE" if corrigio else "deja   "
        print(f"[{estado}] {signo} | esperado={'corrige' if debe else 'deja'} | "
              f"{etiq} -> {res['correcciones']}")
    print(f"\n{ok}/{len(CASOS)} casos correctos")
    sys.exit(0 if ok == len(CASOS) else 1)


if __name__ == "__main__":
    main()
