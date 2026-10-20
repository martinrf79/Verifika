"""EL TECHO DEL CODIGO — que `app/` no crezca sin control (15-oct-2026, pedido de Martin; cambiado el 20-oct).

POR QUE. Cada linea de mas es un lugar mas donde puede vivir una falla, y un archivo gigante no se audita. Pero lo que
se cuenta es el CODIGO: las lineas que ejecutan algo. Desde el 20-oct no cuentan los comentarios, las explicaciones de
cada funcion ni las lineas en blanco, porque son lo que hace auditable al codigo y contarlas castigaba escribirlas.

Dos candados:
  el total de `app/`   techo en `lineas_techo.json`, en lineas de codigo. Subirlo es una decision de Martin, en su
                       propio commit y con las cuentas escritas.
  cada archivo         no pasa de TOPE_ARCHIVO lineas de codigo: una pieza que crece se parte por lo que hace.

El 20-oct Martin subio el techo a 8.500 lineas de codigo, contra 7.220 de ese dia, para la mitad que falta para que el
bot venda. La holgura cubre ese margen: si el codigo baja mas que eso, el techo baja con el. El tope por archivo es 750:
ese dia `motor.py` tenia 702 y `calculadora.py` 653, que casi no tienen lugar; lo nuevo va en piezas chicas.
"""
import ast
import io
import json
import os
import tokenize

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TECHO = os.path.join(RAIZ, "tests", "lineas_techo.json")
HOLGURA = 1300
TOPE_ARCHIVO = 750


def lineas_de_codigo(src: str) -> int:
    """Las lineas que no son blancas, comentarios ni la explicacion de un modulo, clase o funcion."""
    fuera = set()
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body:
            d = n.body[0]
            if isinstance(d, ast.Expr) and isinstance(d.value, ast.Constant) and isinstance(d.value.value, str):
                fuera |= set(range(d.lineno, d.end_lineno + 1))
    comentarios = {t.start[0] for t in tokenize.generate_tokens(io.StringIO(src).readline)
                   if t.type == tokenize.COMMENT}
    return sum(1 for i, l in enumerate(src.splitlines(), 1)
               if l.strip() and i not in fuera and not (i in comentarios and l.strip().startswith("#")))


def por_archivo() -> dict:
    out = {}
    for base, _, archivos in os.walk(os.path.join(RAIZ, "app")):
        for a in archivos:
            if a.endswith(".py"):
                p = os.path.join(base, a)
                with open(p, encoding="utf-8") as f:
                    out[os.path.relpath(p, RAIZ)] = lineas_de_codigo(f.read())
    return out


def lineas_app() -> int:
    return sum(por_archivo().values())


def techo() -> int:
    return json.load(open(TECHO, encoding="utf-8"))["lineas_codigo_app"]


def test_el_codigo_no_crece():
    n = lineas_app()
    assert n <= techo(), (
        f"app/ tiene {n} lineas de codigo contra un techo de {techo()}: {n - techo()} de mas. "
        "Lo nuevo entra reemplazando lo viejo, no al lado.")
    print(f"\nCODIGO: {n} lineas de codigo en app/, techo {techo()}")


def test_ningun_archivo_es_gigante():
    grandes = {p: n for p, n in por_archivo().items() if n > TOPE_ARCHIVO}
    assert not grandes, f"pasan de {TOPE_ARCHIVO} lineas de codigo: {grandes}. Se parten por lo que hace cada parte."
    print(f"\nARCHIVOS: {len(por_archivo())}, el mayor con {max(por_archivo().values())} lineas de codigo")


def test_el_techo_esta_al_dia():
    """Si el codigo bajo mucho y el techo no, lo borrado puede volver a crecer gratis."""
    n = lineas_app()
    assert techo() - n <= HOLGURA, (
        f"el techo quedo {techo() - n} lineas por encima del codigo real ({n}): bajalo en su propio commit")
