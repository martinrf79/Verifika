"""Valida con el Interpretador REAL (DeepSeek) que el atajo de saludo no se
mete donde no debe.

Regla del atajo: dispara solo si intencion == 'saludo' y confianza >= 0.85.
  - Saludos puros -> deben disparar el atajo.
  - Saludos con pedido comercial -> NO deben (no son saludo para el interpretador).
Lee la clave de .secrets.env, nunca la imprime. No toca produccion ni Firestore.
"""
import os
import sys
import asyncio

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cargar_secrets():
    path = os.path.join(ROOT, ".secrets.env")
    if not os.path.exists(path):
        raise SystemExit("Falta .secrets.env en la raiz del proyecto")
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()
            elif line.startswith("sk-"):
                os.environ["DEEPSEEK_API_KEY"] = line


_cargar_secrets()
if not os.environ.get("DEEPSEEK_API_KEY", "").startswith("sk-"):
    raise SystemExit("No se encontro DEEPSEEK_API_KEY valida en .secrets.env")

sys.path.insert(0, ROOT)
from app.core.interpretador import interpretar_mensaje

UMBRAL = 0.85

# (mensaje, deberia_disparar_atajo)
CASOS = [
    ("hola", True),
    ("buenas", True),
    ("que tal", True),
    ("buen dia", True),
    ("hola como va todo", True),
    ("holaa buenas tardes", True),
    # Trampas: arrancan como saludo pero traen pedido comercial -> NO atajo
    ("hola, cuanto sale un teclado gamer?", False),
    ("buenas, tenes mouse inalambrico?", False),
    ("hola quiero comprar una silla de oficina", False),
    ("que tal, me pasas precios de auriculares?", False),
]


async def main():
    print("\n=== INTERPRETADOR REAL: clasificacion de saludos ===\n")
    fallas = 0
    for mensaje, espera_atajo in CASOS:
        r = await interpretar_mensaje(mensaje, [], "test-saludo")
        intencion = r.get("intencion")
        conf = r.get("confianza", 0.0)
        dispara = intencion == "saludo" and conf >= UMBRAL
        ok = dispara == espera_atajo
        if not ok:
            fallas += 1
        estado = "OK" if ok else "FALLA"
        atajo = "ATAJO" if dispara else "solver"
        print(f"  [{estado}] {atajo:6} | intencion={intencion} conf={conf} "
              f":: {mensaje}")
    print(f"\n  Total: {len(CASOS)} casos, {fallas} fallas")
    print("  (ATAJO = responde saludo directo | solver = corre el flujo normal)\n")


if __name__ == "__main__":
    asyncio.run(main())
