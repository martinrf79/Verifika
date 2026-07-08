"""
AREA (vivo): banco de INTERPRETACION — el interprete real contra casos
dificiles (ambiguedad, ironia, correcciones, negaciones dobles). Modulo de
prioridad 1 de Martin (8-jul): sin interpretar bien no hay bot viable.

Corre con la API real:  python -m pytest -m vivo tests/test_vivo_interpretacion.py
"""
import asyncio

import pytest


@pytest.mark.vivo
def test_banco_interpretacion_supera_el_piso(firestore_doble):
    from banco_pruebas.banco_interpretacion import correr, PISO
    score = asyncio.run(correr(verbose=True))
    assert score >= PISO, f"interpretacion {score:.0%} < piso {PISO:.0%}"
