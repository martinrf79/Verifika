# -*- coding: utf-8 -*-
"""
Test del clasificador de zona de envio (motor por CODIGO POSTAL + nombres).
Sin Firestore, sin LLM. Cubre:
- CPA oficial (primera letra = provincia, ISO 3166-2:AR).
- CP de 4 digitos SOLO con marcador (no confundir con altura de calle).
- trampa cajon_equivocado: "Cordoba Capital" -> interior, nunca CABA.
- indeterminada -> None (el codigo no adivina).

Correr: winvenv\\Scripts\\python.exe scripts\\prueba_envio.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.core.envio import clasificar_zona

# (texto, zona_esperada, etiqueta)
CASOS = [
    # --- CPA oficial (letra = provincia) ---
    ("Mi codigo es C1425ABC", "caba", "CPA C -> CABA"),
    ("X5000XXX", "interior", "CPA X -> Cordoba interior"),
    ("B1832ABC lomas", "gba", "CPA B + 1832 -> conurbano"),
    ("B7600AAA", "interior", "CPA B + 7600 -> Mar del Plata interior"),
    ("S2000ABC", "interior", "CPA S -> Santa Fe interior"),
    # --- CP 4 digitos CON marcador ---
    ("cp 1425", "caba", "CP marcado 1425 -> CABA"),
    ("codigo postal 5000", "interior", "CP marcado 5000 -> interior"),
    ("cp 1832", "gba", "CP marcado 1832 -> conurbano"),
    # --- COLISION altura de calle vs CP (critico): el numero suelto NO es CP ---
    ("Av Cabildo 2000, CABA", "caba", "2000 es altura, gana el nombre CABA"),
    ("Colon 4500 Cordoba capital", "interior", "4500 altura, Cordoba -> interior"),
    # --- Nombres ---
    ("mando a cordoba", "interior", "provincia cordoba"),
    ("Dean Funes 434", "interior", "ciudad interior"),
    ("Lomas de Zamora", "gba", "partido conurbano"),
    ("vivo en Palermo", "caba", "barrio porteño"),
    ("San Miguel de Tucuman", "interior", "capital provincial = interior"),
    # --- Indeterminada ---
    ("hola que tal", None, "sin localidad -> None"),
    ("un pueblito por la ruta 36", None, "pueblo desconocido sin CP -> None (pide dato)"),
]


def main():
    ok = 0
    for texto, esperada, etiq in CASOS:
        z = clasificar_zona(texto)
        bien = z == esperada
        ok += bien
        estado = "OK " if bien else "FALLA"
        print(f"[{estado}] zona={str(z):9} esperada={str(esperada):9} | {etiq}")
    print(f"\n{ok}/{len(CASOS)} casos correctos")
    sys.exit(0 if ok == len(CASOS) else 1)


if __name__ == "__main__":
    main()
