"""PENDIENTE.md NO CRECE — 16-oct-2026, pedido de Martin.

POR QUE. El hook del arranque imprime el titular de cada item; con treinta items de parrafos largos, lo de arriba
tapaba lo importante y lo viejo nunca se borraba. CLAUDE.md fija veinte; aca se hace cumplir, y se exige que la
sesion nueva tenga por donde arrancar: un DONDE VA y al menos un SIGUE.
"""
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _items() -> list:
    texto = open(os.path.join(RAIZ, "PENDIENTE.md"), encoding="utf-8").read()
    abajo = texto.split("\n---\n", 1)[1]
    return re.findall(r"^- \*\*(.+?)\*\*", abajo, re.M)


def test_no_pasa_de_veinte_items():
    estados = _items()
    print(f"\nPENDIENTE: {len(estados)} items")
    assert 0 < len(estados) <= 20, f"{len(estados)} items: lo hecho u obsoleto se borra al cerrar la sesion"


def test_la_sesion_nueva_sabe_donde_va_y_por_donde_sigue():
    estados = _items()
    assert estados[0] == "DONDE VA", "el primer item es DONDE VA"
    assert sum(e.startswith("SIGUE") for e in estados) >= 1, "falta un SIGUE: la sesion nueva no sabe por donde ir"
