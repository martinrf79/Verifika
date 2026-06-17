"""
PRUEBA — pista tipo_confirmacion en el INTERPRETE (flag CONFIRMACION_PROVIDER).

Verifica lo determinista del cambio, SIN llamar al LLM:
  - con el flag ON el prompt suma el campo tipo_confirmacion y su guia
  - con el flag OFF el prompt queda igual al previo (sin el campo, JSON cierra bien)
  - validar_schema coerciona la pista: valor valido se conserva, cualquier otra
    cosa o ausencia -> None, y NUNCA falla la validacion

Correr:
    set PYTHONPATH=.
    .\\venv-win\\Scripts\\python.exe .\\scripts\\prueba_interprete_confirmacion.py
"""
import os
os.environ["CONFIRMACION_PROVIDER"] = "true"

import app.core.interpretador as I
from app.core.interpretador import construir_prompt_interpretador, validar_schema

fallos = []


def chequear(nombre, cond):
    print(f"[{'OK ' if cond else 'FALLA'}] {nombre}")
    if not cond:
        fallos.append(nombre)


# ── Prompt con el flag ON ──
I.settings.CONFIRMACION_PROVIDER = True
p_on = construir_prompt_interpretador("quiero 3 teclados", "Sin historial", [])
chequear("on: el JSON suma el campo tipo_confirmacion",
         '"tipo_confirmacion"' in p_on)
chequear("on: incluye la guia de tipo de confirmacion",
         "GUIA DE TIPO DE CONFIRMACION" in p_on)
chequear("on: nombra los tres tipos",
         "a_o_b" in p_on and "te_referis_a" in p_on
         and "confirmar_compra" in p_on)
chequear("on: aclara que es pista y el codigo decide",
         "PISTA" in p_on and "codigo decide" in p_on)

# ── Prompt con el flag OFF: identico al previo ──
I.settings.CONFIRMACION_PROVIDER = False
p_off = construir_prompt_interpretador("quiero 3 teclados", "Sin historial", [])
chequear("off: NO aparece el campo tipo_confirmacion",
         "tipo_confirmacion" not in p_off)
chequear("off: NO aparece la guia",
         "GUIA DE TIPO DE CONFIRMACION" not in p_off)
chequear("off: el JSON cierra bien tras ofrecer_opciones (sin coma colgada)",
         'con certeza"\n}' in p_off)
chequear("off: empalme exacto del previo (sin linea en blanco de mas)",
         "debera elegir.\n\nPRODUCTO RESUELTO." in p_off)
chequear("on: la guia se inserta justo ahi sin romper el empalme",
         "debera elegir.\n\nGUIA DE TIPO DE CONFIRMACION" in p_on)

# ── validar_schema: coercion de la pista (flag-independiente) ──
def _base(extra):
    d = {"intencion": "otra", "confianza": 0.5}
    d.update(extra)
    return d

r = _base({"tipo_confirmacion": "a_o_b"})
ok, _ = validar_schema(r)
chequear("schema: valor valido se conserva",
         ok and r["tipo_confirmacion"] == "a_o_b")

r = _base({"tipo_confirmacion": "A_O_B"})
validar_schema(r)
chequear("schema: normaliza mayusculas a minusculas",
         r["tipo_confirmacion"] == "a_o_b")

r = _base({"tipo_confirmacion": "cualquier_cosa"})
ok, _ = validar_schema(r)
chequear("schema: valor invalido -> None, sin fallar",
         ok and r["tipo_confirmacion"] is None)

r = _base({})
ok, _ = validar_schema(r)
chequear("schema: ausente -> None, sin fallar",
         ok and r["tipo_confirmacion"] is None)

r = _base({"tipo_confirmacion": None})
ok, _ = validar_schema(r)
chequear("schema: null -> None, sin fallar",
         ok and r["tipo_confirmacion"] is None)

print()
if fallos:
    print(f"RESULTADO: {len(fallos)} FALLAS")
    for f in fallos:
        print(f"  - {f}")
    raise SystemExit(1)
print("RESULTADO: TODO OK")
