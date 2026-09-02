"""
QUE UN ARREGLO NO ROMPA OTRO — el candado mecanico (Martin, 7-ago-2026).

EL RECLAMO, textual: "cada arreglo hay que tener en cuenta que no tiene que
tener conflictos con lo demas, porque a veces se arregla una cosa y se rompe
otra". Los tres numeros ya cubren la parte que se puede correr -las 40, las
charlas grabadas, la bateria offline-, pero hay una familia de conflictos que
NINGUN test de comportamiento ve, porque no rompe nada donde se toca: rompe algo
a noventa lineas de distancia y en silencio.

EL CASO REAL, del 7-ago y encontrado leyendo los logs de produccion.
`hub_venta.py` definia `_RE_RENGLON_CUENTA` DOS VECES a nivel de modulo:

    linea 828   _RE_RENGLON_CUENTA = re.compile(... + r".*$")   # para BORRAR
    linea 917   _RE_RENGLON_CUENTA = re.compile(...)            # para MATCHEAR

Las dos versiones eran razonables por separado. La segunda nacio despues, como
MEJORA -mas estricta, agarra "1 x Teclado" que a la primera se le escapaba- y su
autor no tenia forma de saber que estaba pisando a la otra. Python rebindea el
nombre al importar, asi que la segunda gana SIEMPRE, y el `sub()` de
`_bloque_entero_o_repuesto` -escrito contra la primera, que si terminaba en
`.*$`- paso a borrar solo el ARRANQUE del renglon. Al cliente le llegaba:

     $201.000
    3 envios): $24.000
    70%): $157.500

Una cuenta descuartizada, con parentesis huerfanos y sin la palabra Total. Un
arreglo correcto rompio una funcion que nadie toco. Cero tests en rojo.

POR QUE ESTO Y NO "LEER CON MAS CUIDADO". Es la misma leccion del 31-jul con el
patron de la poda escrito en dos lugares, y la misma de `reparto_ambiguo`: una
regla que vive dos veces termina distinta. La diferencia es que aquellas eran
dos nombres distintos con el mismo contenido -se ven leyendo- y esta es el MISMO
nombre dos veces, que no se ve ni leyendo el archivo entero, porque las dos
definiciones estan a cien lineas una de otra y las dos parecen bien.

Lo caza el parser, en milisegundos, sin correr una linea del bot.
"""
import ast
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))


def _modulos() -> list:
    return sorted(p for p in (_RAIZ / "app").rglob("*.py")
                  if "__pycache__" not in str(p))


def _asignaciones_de_modulo(arbol: ast.Module) -> list:
    """Los nombres asignados en el CUERPO del modulo, con su linea. Solo el
    nivel de arriba: adentro de una funcion o una clase, reasignar es normal."""
    fuera = []
    for nodo in arbol.body:
        destinos = []
        if isinstance(nodo, ast.Assign):
            destinos = nodo.targets
        elif isinstance(nodo, ast.AnnAssign) and nodo.value is not None:
            destinos = [nodo.target]
        for d in destinos:
            if isinstance(d, ast.Name):
                fuera.append((d.id, nodo.lineno))
    return fuera


def test_ningun_modulo_define_el_mismo_nombre_dos_veces():
    """Si un nombre de modulo se asigna dos veces, la segunda gana y la primera
    queda de adorno: cualquier funcion escrita contra la primera cambia de
    comportamiento sin que la toque nadie. Ver el caso del docstring."""
    pisados = []
    for archivo in _modulos():
        try:
            arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        except SyntaxError as e:                          # pragma: no cover
            pytest.fail(f"{archivo.relative_to(_RAIZ)} no parsea: {e}")
        vistos: dict = {}
        for nombre, linea in _asignaciones_de_modulo(arbol):
            if nombre in vistos:
                pisados.append(
                    f"{archivo.relative_to(_RAIZ)}: '{nombre}' se define en la "
                    f"linea {vistos[nombre]} y se PISA en la {linea}")
            vistos[nombre] = linea
    assert not pisados, (
        "UN NOMBRE DE MODULO DEFINIDO DOS VECES. La segunda gana al importar y "
        "la primera queda muerta, asi que toda funcion escrita contra la "
        "primera cambio de comportamiento en silencio. Dejá una sola "
        "definicion, o poneles nombres distintos si de verdad son dos cosas:\n"
        + "\n".join(f"  - {p}" for p in pisados))


def test_el_candado_ve_el_caso_que_lo_parió():
    """El test de arriba no sirve de nada si no caza el bug original. Se le da
    el codigo tal cual estaba y tiene que marcarlo."""
    roto = (
        "import re\n"
        "_RE_RENGLON_CUENTA = re.compile(r'^(?:total:).*$')\n"
        "def usar(t):\n"
        "    return _RE_RENGLON_CUENTA.sub('', t)\n"
        "_RE_RENGLON_CUENTA = re.compile(r'^(?:total\\s*:)')\n")
    repetidos = [n for n, _ in _asignaciones_de_modulo(ast.parse(roto))]
    assert repetidos.count("_RE_RENGLON_CUENTA") == 2

    # Y NO marca lo que es normal: reasignar adentro de una funcion, o un
    # `try/except ImportError` que define el mismo nombre por dos caminos.
    sano = (
        "def f():\n"
        "    x = 1\n"
        "    x = 2\n"
        "    return x\n"
        "try:\n"
        "    import json\n"
        "except ImportError:\n"
        "    json = None\n")
    nombres = [n for n, _ in _asignaciones_de_modulo(ast.parse(sano))]
    assert "x" not in nombres and "json" not in nombres
