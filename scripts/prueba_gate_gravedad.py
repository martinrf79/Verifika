# -*- coding: utf-8 -*-
"""
Test determinista del gate por gravedad. Sin LLM, sin Firestore. Verifica que el
puente politica-mecanismo bloquee lo grave y deje pasar lo blando.

Correr: winvenv\\Scripts\\python.exe scripts\\prueba_gate_gravedad.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.core.gate_gravedad import decidir_gate, textos_no_respaldados


def caso(afs, vers):
    return afs, vers


# (afirmaciones, veredictos, debe_bloquear, etiqueta)
CASOS = [
    # Producto inventado (Dragonborn): sin_evidencia de tipo producto -> bloquea,
    # AUNQUE el resto este soportado (el puntaje global lo dejaba pasar).
    ([{"id": "a1", "texto": "tenemos el Redragon Dragonborn", "tipo": "producto"},
      {"id": "a2", "texto": "el G435 cuesta 97000", "tipo": "precio"}],
     [{"id": "a1", "veredicto": "sin_evidencia"},
      {"id": "a2", "veredicto": "soportada"}],
     True, "producto inventado entre datos buenos -> bloquea"),
    # Contradicha de cualquier tipo bloquea (promesa de dia que extiende plazo).
    ([{"id": "a1", "texto": "te llega el martes", "tipo": "politica"}],
     [{"id": "a1", "veredicto": "contradicha"}],
     True, "politica contradicha (promesa de dia) -> bloquea"),
    ([{"id": "a1", "texto": "el envio a Cordoba sale 3000", "tipo": "politica"}],
     [{"id": "a1", "veredicto": "contradicha"}],
     True, "precio de envio contradicho -> bloquea"),
    # Precio sin evidencia: NO bloquea por el Checker (lo cubre el verificador
    # determinista de plata). Evita el sobre-bloqueo de señal débil.
    ([{"id": "a1", "texto": "sale 999999", "tipo": "precio"}],
     [{"id": "a1", "veredicto": "sin_evidencia"}],
     False, "precio sin evidencia -> NO bloquea (lo cubre plata)"),
    # Politica sin evidencia: NO bloquea. Caso real del diag: "despachamos en el
    # dia" no esta literal en la FAQ pero no es mentira. Era el sobre-bloqueo.
    ([{"id": "a1", "texto": "despachamos en el dia si pagas hoy", "tipo": "politica"}],
     [{"id": "a1", "veredicto": "sin_evidencia"}],
     False, "politica sin evidencia (operativa) -> NO bloquea"),
    # Stock sin evidencia: NO bloquea (señal débil, sobre-bloqueaba).
    ([{"id": "a1", "texto": "despachamos en el dia", "tipo": "stock"}],
     [{"id": "a1", "veredicto": "sin_evidencia"}],
     False, "stock sin evidencia -> NO bloquea"),
    # Caracteristica sin evidencia: NO bloquea (evita falsos positivos de spec).
    ([{"id": "a1", "texto": "es resistente a golpes", "tipo": "caracteristica"}],
     [{"id": "a1", "veredicto": "sin_evidencia"}],
     False, "caracteristica sin evidencia -> NO bloquea"),
    # Politica CONTRADICHA si bloquea (la evidencia la contradice).
    ([{"id": "a1", "texto": "cuotas sin interes con cualquier tarjeta", "tipo": "politica"}],
     [{"id": "a1", "veredicto": "contradicha"}],
     True, "politica contradicha (condicion extendida) -> bloquea"),
    # Todo soportado -> no bloquea.
    ([{"id": "a1", "texto": "el G435 cuesta 97000", "tipo": "precio"}],
     [{"id": "a1", "veredicto": "soportada"}],
     False, "todo soportado -> no bloquea"),
    # Caracteristica CONTRADICHA si bloquea (la evidencia la contradice).
    ([{"id": "a1", "texto": "tiene 32GB de RAM", "tipo": "caracteristica"}],
     [{"id": "a1", "veredicto": "contradicha"}],
     True, "caracteristica contradicha -> bloquea"),
    # Sin afirmaciones (saludo) -> no bloquea.
    ([], [], False, "respuesta social sin afirmaciones -> no bloquea"),
]


def main():
    ok = 0
    for afs, vers, debe, etiq in CASOS:
        g = decidir_gate(vers, afs, trace_id=etiq)
        bien = g["bloquear"] == debe
        ok += bien
        signo = "BLOQUEA" if g["bloquear"] else "pasa   "
        print(f"[{'OK ' if bien else 'FALLA'}] {signo} | esperado="
              f"{'bloquea' if debe else 'pasa'} | {etiq}")
    # Chequeo del helper de autofix.
    afs = [{"id": "a1", "texto": "tenemos el Dragonborn", "tipo": "producto"}]
    vers = [{"id": "a1", "veredicto": "sin_evidencia"}]
    txts = textos_no_respaldados(decidir_gate(vers, afs))
    assert txts == ["tenemos el Dragonborn"], txts
    print(f"\n{ok}/{len(CASOS)} casos correctos | helper autofix OK")
    sys.exit(0 if ok == len(CASOS) else 1)


if __name__ == "__main__":
    main()
