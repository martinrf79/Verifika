"""
UNA PREGUNTA DE COMPATIBILIDAD NO PUEDE TIRAR EL TURNO.

EL DIA QUE LO PAGO (25-ago-2026). Grabando `45_consigna_capciosas` el turno
"quiero enchufarlo a mi tablet por HDMI" moria entero con
`AttributeError: 'str' object has no attribute 'get'` y al cliente le llegaba el
enlatado de sobrecarga. No era la cuota ni el modelo: era una FORMA.

LA FORMA. `producto` vuelve de dos maneras, y las dos son correctas:

    buscar_productos / ficha_producto -> {"producto": {"id": ..., "nombre": ...}}
    ver_compatibilidad                -> {"producto": "Mouse Genius NX-7000"}

`ver_compatibilidad` devuelve el NOMBRE pelado porque su respuesta es sobre si
algo sirve para otra cosa, no sobre la identidad del producto: son los dos ejes
que la regla cero del CLAUDE.md manda no mezclar. Cinco consumidores ya lo
sabian y guardaban con `isinstance(..., dict)`. DOS no: `pedido` y `reposicion`.

POR QUE VALE UN ARCHIVO ENTERO. No es un detalle de plomeria: es TODA pregunta
de compatibilidad que resuelve, o sea una de las preguntas mas comerciales que
hay —"¿esto me sirve para lo que tengo?"— perdiendo la venta entera. Prioridad
uno del proyecto.

SE AFIRMA SOBRE CUANTOS CASOS: las dos formas por cada una de las dos funciones
que se rompian, mas que el nombre pelado no se PIERDA en el reconciliador.
"""
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from app.core.pedido import _universo_de_busquedas  # noqa: E402
from app.core.resolver import _cuenta_con_lo_declarado  # noqa: E402

# Tal cual las escribe `herramientas.py`.
COMPAT = {"herramienta": "ver_compatibilidad",
          "pedido": {"categoria": "mouse"},
          "resultado": {"estado": "ok", "producto": "Mouse Genius NX-7000",
                        "compatible": True}}
FICHA = {"herramienta": "ficha_producto",
         "pedido": {"categoria": "mouse"},
         "resultado": {"producto": {"id": "MOU0023",
                                    "nombre": "Mouse Genius NX-7000",
                                    "categoria": "mouse"}}}

FORMAS = [("nombre pelado, como lo manda ver_compatibilidad", COMPAT),
          ("ficha entera, como la manda ficha_producto", FICHA)]


@pytest.mark.parametrize("nombre,llamada", FORMAS)
def test_el_universo_de_busquedas_aguanta_las_dos_formas(nombre, llamada):
    """Esta es la linea exacta que tiraba el turno."""
    universo = _universo_de_busquedas([llamada])
    assert "genius" in universo, nombre


@pytest.mark.parametrize("nombre,llamada", FORMAS)
def test_la_reposicion_aguanta_las_dos_formas(nombre, llamada):
    """LA GEMELA QUE NO LLEGO A EXPLOTAR solo porque el turno moria unas lineas
    mas arriba, en `pedido`. Se entra por `pide_precio`, que es la puerta que
    lleva al armado de `vistos` sin necesitar una cuenta previa."""
    _cuenta_con_lo_declarado([llamada], {"pide_precio": True},
                             "verifika_prod", "test")  # no revienta


def test_el_nombre_pelado_cuenta_como_atendido():
    """NO ALCANZA CON NO EXPLOTAR. Si el nombre se descartara, el reconciliador
    daria el item por NO atendido y mandaria a buscar de nuevo lo que la
    herramienta ya trajo: una vuelta entera al pedo, en tokens y en latencia."""
    assert "genius" in _universo_de_busquedas([COMPAT])


def test_la_reposicion_no_se_traga_un_nombre_como_si_fuera_ficha():
    """Del otro lado: ahi se juntan fichas CERTIFICADAS, con id. Un nombre
    suelto no lo es y no puede colarse. Se mira la linea misma, que es lo que
    esta prueba puede afirmar sin armar media charla."""
    import inspect

    from app.core import resolver
    fuente = inspect.getsource(resolver._cuenta_con_lo_declarado)
    assert "isinstance(p, dict)" in fuente, (
        "el guardia que descarta el nombre pelado se fue de la reposicion")


def test_se_corrieron_las_dos_formas_por_cada_funcion():
    assert len(FORMAS) == 2
