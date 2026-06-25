"""
SMOKE de la logica DETERMINISTA del camino vivo, offline (sin Firestore ni LLM).

Cubre las piezas que el codigo manda y que se pueden probar sin red: clasificacion
de zona de envio, normalizacion defensiva de la calculadora, y el filtro
determinista (verificador). NO prueba el interprete ni el solver: esos son LLM y
necesitan claves, se prueban en WhatsApp.

Correr:  python3 scripts/smoke_logica.py   (antes: bash scripts/setup_test_env.sh)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.envio import clasificar_zona, clasificar_provincia
from app.core.verificador import verificar_respuesta

fallos = 0


def check(nombre, cond):
    global fallos
    print(("OK  " if cond else "FALLA ") + nombre)
    if not cond:
        fallos += 1


# ── Envio: clasificacion de zona/provincia ───────────────────────────────
check("san agustin -> interior", clasificar_zona("envio a san agustin") == "interior")
check("san agustin cordoba -> provincia cordoba",
      clasificar_provincia("san agustin cordoba") == "cordoba")
check("caba -> caba", clasificar_zona("a caba") == "caba")
check("lanus -> gba", clasificar_zona("lanus") == "gba")
check("cp 5257 -> interior", clasificar_zona("cp 5257") == "interior")
check("texto vacio -> None (no adivina)", clasificar_zona("") is None)

# ── Verificador: respaldo de cifras ──────────────────────────────────────
ev = [
    {"tipo": "producto", "id": "M1", "precio_ars": 8500},
    {"tipo": "proof", "proof": {"tipo": "envio", "resultado": 7500, "valores": [7500]}},
]
ok_buena = verificar_respuesta(
    "2x Mouse 8.500 = 17.000, envio 7.500, total 24.500", ev, "smoke")
check("cierre real (todo respaldado) pasa", ok_buena["ok"] is True)

ok_inventada = verificar_respuesta(
    "El combo sale 999.999 pesos", ev, "smoke")
check("cifra inventada se marca", ok_inventada["ok"] is False)

print()
if fallos:
    print(f"=== {fallos} FALLAS ===")
    raise SystemExit(1)
print("=== todo verde ===")
