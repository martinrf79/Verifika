# -*- coding: utf-8 -*-
"""
Test determinista del guard anti pierde-el-hilo (falla e). Sin LLM, sin
Firestore. Verifica que una conversacion en curso NO pueda volver a 'saludo',
sin romper el saludo legitimo del arranque.

Correr: winvenv\\Scripts\\python.exe scripts\\prueba_estado_regresion.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.core.interpretador import corregir_estado_regresion

# (estado_nuevo, estado_anterior, hay_historial, esperado, etiqueta)
CASOS = [
    # Arranque real: sin historial, saludo es legitimo y se respeta.
    ("saludo", None, False, "saludo", "arranque sin historial deja saludo"),
    ("saludo", "saludo", False, "saludo", "primer turno saludo->saludo"),
    # El caso de la falla (e): mitad de charla, el interpretador devuelve saludo.
    ("saludo", "explorando", True, "explorando",
     "regresion a saludo en charla -> conserva explorando"),
    ("saludo", "esperando_datos", True, "esperando_datos",
     "regresion a saludo con datos -> conserva esperando_datos"),
    # Si el anterior no era un estado en curso reconocido, cae a explorando.
    ("saludo", "saludo", True, "explorando",
     "saludo previo + historial -> explorando, no se reinicia"),
    ("saludo", None, True, "explorando",
     "sin estado anterior pero con historial -> explorando"),
    # Estados normales no se tocan nunca.
    ("explorando", "saludo", True, "explorando", "explorando pasa intacto"),
    ("esperando_confirmacion", "explorando", True, "esperando_confirmacion",
     "esperando_confirmacion pasa intacto"),
    ("derivar_humano", "esperando_datos", True, "derivar_humano",
     "derivar_humano pasa intacto"),
]


def main():
    ok = 0
    for estado_nuevo, estado_ant, hay_hist, esperado, etiq in CASOS:
        real = corregir_estado_regresion(estado_nuevo, estado_ant, hay_hist)
        bien = real == esperado
        ok += bien
        print(f"[{'OK ' if bien else 'FALLA'}] {etiq} | "
              f"{estado_nuevo} -> {real} (esperado {esperado})")
    print(f"\n{ok}/{len(CASOS)} casos correctos")
    sys.exit(0 if ok == len(CASOS) else 1)


if __name__ == "__main__":
    main()
