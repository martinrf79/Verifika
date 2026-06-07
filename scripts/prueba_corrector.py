"""
SMOKE del corrector anclado. Le da borradores con alucinacion a proposito + la
evidencia real, y verifica que aterriza el hecho. Usa DeepSeek real (centavos).

Correr: winvenv\\Scripts\\python.exe scripts\\prueba_corrector.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Cargar secretos (DeepSeek) igual que el simulador.
_sec = ROOT / ".secrets.env"
if _sec.exists():
    for line in _sec.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from app.core.corrector import corregir_respuesta  # noqa: E402

# Evidencia de juguete: un producto real y una FAQ real.
EV = [
    {"tipo": "producto", "id": "NB001", "nombre": "Notebook HP 245 G9",
     "categoria": "notebook", "marca": "HP", "modelo": "245 G9",
     "precio_ars": 693000, "stock": 4, "color": "Gris",
     "garantia_meses": 12, "descripcion": "Core i5 16GB 512GB SSD"},
    {"tipo": "faq", "id": "1", "tema": "retiro_local",
     "respuesta": "Somos tienda online, despachamos por Andreani y OCA a todo el pais."},
]

CASOS = [
    {
        "nombre": "precio inventado",
        "draft": "La Notebook HP 245 G9 sale 850000 pesos, te la dejo en gris.",
        "espera": "deberia corregir a 693000",
    },
    {
        "nombre": "color/variante inventada",
        "draft": "Tenemos la HP 245 G9 en negro, plata y gris. En negro hay 3 unidades.",
        "espera": "deberia quedarse solo con gris (lo unico en evidencia)",
    },
    {
        "nombre": "servicio inventado (retiro en local)",
        "draft": "Si queres pasa a buscarla por nuestro local, te la dejo lista.",
        "espera": "deberia quitar el retiro (la FAQ dice online, sin local)",
    },
    {
        "nombre": "geografia (conocimiento general, NO borrar)",
        "draft": "Comodoro Rivadavia queda en Chubut, pero te llega igual la HP 245 "
                 "G9 a 850000 pesos por Andreani.",
        "espera": "MANTENER 'Chubut' (general) y CORREGIR el precio a 693000",
    },
    {
        "nombre": "A/B legitima (no tocar de mas)",
        "draft": "Si la queres para trabajo te va la HP 245 G9 a 693000. Si es para "
                 "gaming, decime y vemos otra. Cual de las dos?",
        "espera": "deberia preservar la estructura A/B y el precio correcto",
    },
]


def main():
    for c in CASOS:
        print("=" * 70)
        print(f"CASO: {c['nombre']}  ({c['espera']})")
        print(f"  BORRADOR : {c['draft']}")
        r = corregir_respuesta(c["draft"], EV, trace_id=c["nombre"])
        print(f"  CORREGIDA: {r['respuesta_final']}")
        print(f"  cambiada={r['cambiada']} ok={r['ok']}")
    print("=" * 70)
    print("Revisar a ojo: precio->693000, color->solo gris, retiro->quitado, "
          "geo->mantiene Chubut y corrige el precio, A/B->preservada.")


if __name__ == "__main__":
    main()
