# -*- coding: utf-8 -*-
"""
Test determinista del rescate de afirmaciones del Proposer ante JSON truncado.
Sin LLM. Usa el caso real del molino (string cortado a la mitad).

Correr: winvenv\\Scripts\\python.exe scripts\\prueba_proposer_salvage.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.verifika.proposer import salvage_afirmaciones

# Caso real (trace f60b3bc5): el JSON se corto en la 2da afirmacion.
TRUNCADO = '''{
  "afirmaciones": [
    {"id": "a1", "texto": "El teclado Redragon Dragonborn no esta en el catalogo", "tipo": "producto"},
    {"id": "a2", "texto": "El teclado Redragon Kumara K552 cuesta 36000 pe'''

# JSON sano: debe rescatar las 2 igual.
SANO = '''{"afirmaciones": [
 {"id": "a1", "texto": "El G435 cuesta 97000", "tipo": "precio"},
 {"id": "a2", "texto": "Hay stock del G435", "tipo": "stock"}
]}'''

# Basura total: 0 rescatadas.
BASURA = "perdon, no puedo generar el JSON ahora"


def main():
    ok = 0
    total = 0

    total += 1
    r = salvage_afirmaciones(TRUNCADO)
    bien = len(r) == 1 and r[0]["texto"].startswith("El teclado Redragon Dragonborn")
    ok += bien
    print(f"[{'OK ' if bien else 'FALLA'}] truncado -> rescata {len(r)} (esperado 1): "
          f"{[a['tipo'] for a in r]}")

    total += 1
    r = salvage_afirmaciones(SANO)
    bien = len(r) == 2
    ok += bien
    print(f"[{'OK ' if bien else 'FALLA'}] sano -> rescata {len(r)} (esperado 2)")

    total += 1
    r = salvage_afirmaciones(BASURA)
    bien = len(r) == 0
    ok += bien
    print(f"[{'OK ' if bien else 'FALLA'}] basura -> rescata {len(r)} (esperado 0)")

    print(f"\n{ok}/{total} casos correctos")
    sys.exit(0 if ok == total else 1)


if __name__ == "__main__":
    main()
