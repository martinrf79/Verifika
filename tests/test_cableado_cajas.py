"""LA TRAZA POR CAJAS COMO VARA — 7-nov-2026, a pedido de Martin.

`banco_pruebas/traza_cajas.py` corre un turno por el codigo vivo con el modelo falso repitiendo lo grabado, y aplica una regla a la
salida de cada caja. Si el modelo es siempre el mismo y la regla falla, la falla es del codigo, y la regla dice de que caja.

  el instrumento   las reglas de frontera de la caja 6 se cumplen cuando la salida es buena: sin falsas alarmas.
  PLAN             las dos fallas de WhatsApp del 7-nov que son de la caja 6 BUSCAR, escritas como tests que fallan: "notebooks y
                   tablets" dejaba las 25 filas en notebooks, y "mouse g203" por LIKE volvia vacio con el producto en la tabla.
"""
import asyncio

import pytest

from banco_pruebas import clon_produccion as C
from banco_pruebas.agente_replay import Grabado
from banco_pruebas.traza_cajas import Traza


@pytest.fixture(scope="module")
def A():
    C.instalar()
    from app.core import llm_reintento
    from app.core.flujo import agente
    antes = llm_reintento._cliente, agente._parecidos
    falso = Grabado()
    llm_reintento._cliente = lambda: falso
    agente._parecidos = lambda consulta, tipo, tienda_id: []
    agente._falso = falso
    yield agente
    llm_reintento._cliente, agente._parecidos = antes


def violaciones(A, mensaje: str, sql: str) -> list:
    A._falso.turno({"pasos": [{"herramienta": "buscar", "pide": {"consulta": sql}}],
                    "respuesta": {"saludo": "", "pregunta": "", "bloques": [{"cita": f"P{i}", "mostrar": [], "por": ""} for i in range(1, 13)]}})
    with Traza() as t:
        asyncio.run(A.responder(mensaje, [], A.memoria_de({}), "u_cajas", "telegram", C.TIENDA, "t"))
    return t.violaciones(C.TIENDA)


def test_una_busqueda_buena_no_dispara_ninguna_regla(A):
    sql = "SELECT nombre, precio, stock FROM productos WHERE nombre LIKE '%M220%' AND stock > 0"
    assert violaciones(A, "tenes el m220?", sql) == []


@pytest.mark.xfail(strict=True, reason="PLAN: caja 6 BUSCAR, el corte de 25 filas depende del ORDER BY del modelo: con ORDER BY rubro todo "
                                       "es notebook y las tablets no llegan, WhatsApp 7-nov. Se arregla en `tabla.consultar`.")
def test_notebooks_y_tablets_llegan_las_dos(A):
    sql = "SELECT nombre, precio, stock, rubro FROM productos WHERE (rubro = 'notebook' OR rubro = 'tablet') AND stock > 0 ORDER BY rubro, precio"
    assert violaciones(A, "Pasame todas las notebooks y tablets", sql) == []


@pytest.mark.xfail(strict=True, reason="PLAN: caja 6 BUSCAR, 'mouse g203' por LIKE de la frase entera vuelve vacio y el modelo dice que no "
                                       "hay stock, WhatsApp 7-nov. Se arregla donde la consulta resuelve el producto, no en la consigna.")
def test_un_producto_que_existe_no_vuelve_vacio(A):
    sql = "SELECT nombre, precio, stock FROM productos WHERE nombre LIKE '%mouse g203%' AND color = 'Negro' AND stock > 0 ORDER BY precio ASC"
    assert violaciones(A, "tenes un mouse g203 negro", sql) == []
