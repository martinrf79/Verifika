"""LAS ETIQUETAS DE LOS 300 PRIMEROS MENSAJES NUEVOS (25-nov-2026). FICHA 108.

El mismo formato que `examen/etiquetas.py`, con sus ayudantes: E, P, C y los atajos. Escritas mirando solo el catalogo y
conceptos.json, sin ver lo que devuelve la busqueda. Partidas en dos tandas, `et_a.py` y `et_b.py`. No se cambian despues de
ver un resultado: si una esta mal, se corrige en su propio commit, diciendo por que.

    python3 primeros/control.py     # controla cada etiqueta contra el catalogo y congela con hash
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examen"))
from etiquetas import C, P, E, R, AT, PR, PL, CO, OR, OF, NO, RE, SD, NC, RC  # noqa: E402,F401
from etiquetas import cant, rub, mar, mod, col, orden, barato, gamer, oficina, fuera, MEC, INAL  # noqa: E402,F401

L = {}
for _m in ("et_a", "et_b"):
    try:
        L.update(__import__(_m).L)
    except ImportError:
        pass
