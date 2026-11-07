"""EL DIAGRAMA NO SE QUEDA ATRAS — 7-nov-2026, a pedido de Martin.

`arquitectura/DIAGRAMA_FLUJO.md` lo genera `banco_pruebas/diagrama.py` leyendo `app/`. Estas pruebas hacen que una sesion no
pueda sumar o mover codigo sin que el diagrama lo diga:

  sin caja     toda funcion o clase de nivel superior de `app/` cae en una caja de `CAJAS`.
  al dia       el archivo generado es el que sale del codigo de hoy. Si falla: `python3 banco_pruebas/diagrama.py`.
  reglas vivas ninguna regla de `REGLAS` queda sin nada que asignar: una regla vieja es una caja que ya no existe.
  entradas     el analisis encuentra los webhooks y el orquestador; sin entradas, "alcanzable" no significa nada.
"""
import os
import re

import pytest

from banco_pruebas import diagrama as D


@pytest.fixture(scope="module")
def datos():
    return D.leer()


def test_toda_funcion_tiene_caja(datos):
    assert D.sin_caja(datos) == [], "agregalas a una caja en REGLAS de banco_pruebas/diagrama.py"


def test_el_archivo_generado_es_el_de_hoy(datos):
    assert os.path.exists(D.SALIDA), "falta: python3 banco_pruebas/diagrama.py"
    assert open(D.SALIDA, encoding="utf-8").read() == D.escribir(datos), "desactualizado: python3 banco_pruebas/diagrama.py"


def test_ninguna_regla_queda_sin_nada_que_asignar(datos):
    huerfanas = [r for r in D.REGLAS
                 if not any(re.search(r[1], n["modulo"]) and (r[2] is None or re.search(r[2], n["nombre"])) for n in datos["nodos"].values())]
    assert huerfanas == [], huerfanas


def test_el_analisis_encuentra_las_entradas(datos):
    nombres = " ".join(datos["entradas"])
    for esperada in ("whatsapp_webhook", "telegram_webhook", "process_message"):
        assert esperada in nombres, (esperada, datos["entradas"])
    assert sum(1 for n in datos["nodos"].values() if n["alcanzable"]) > 0.8 * len(datos["nodos"]), "casi nada alcanzable: el analisis se rompio"
