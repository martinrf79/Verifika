"""Pasa el auditor del molino de focos sobre un CSV de cualquier corrida
multiturno ya hecha. Solo las clases genericas (sin expectativas por turno).

Uso: python scripts/auditar_csv.py resultados_multiturno_xxx.csv [tienda]
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import correr_molino_focos as M

archivo = sys.argv[1] if len(sys.argv) > 1 else "resultados_multiturno.csv"
tienda = sys.argv[2] if len(sys.argv) > 2 else "verifika_prod"

precios = M._precios_catalogo(tienda)
previas: dict[str, list] = {}
n = 0
with open(archivo, encoding="utf-8") as f:
    for row in csv.DictReader(f):
        cid = row["conv_id"]
        alertas = M.auditar(row["mensaje"], row["respuesta"],
                            previas.get(cid, []), {}, precios)
        previas.setdefault(cid, []).append(row["respuesta"])
        if alertas:
            n += 1
            print(f"[{cid}] t{row['turno']}: {alertas}")
            print(f"   C: {row['mensaje']}")
            print(f"   B: {row['respuesta'][:140]}")
print(f"--- {n} turnos con alerta")
