"""EL PESO DEL MOLDE — lo que se paga en CADA llamada al decisor.

El molde es lo que ve el modelo en L1: `app/core/molde.py`, con los enums que
`esquemas()` inyecta desde la fuente viva. Viaja entero en cada turno de cada
charla, asi que cada byte que se le suma se paga para siempre.

POR QUE ESTE CANDADO, y es la regla 9 de `CLAUDE.md` aplicada a un numero. El
techo de 6.000 estaba escrito en un COMENTARIO —`filtros_catalogo.py`, donde se
explica por que el extremo no es un campo del molde— y no lo media nadie. Un
numero que vive en prosa envejece el dia que alguien suma un enum. Medido el
11-sep-2026: el molde pesa 5.940 y el techo son 6.000, o sea que quedaban 60
bytes y eso no lo sabia ninguna sesion.

EL TECHO NO ES UNA PARED, ES UN PRESUPUESTO. Subirlo es una decision de Martin
y va en su propio commit, con las cuentas escritas, igual que cualquier otro
umbral de este repo. Lo que este test impide es que suba SOLO.

Para ver el peso y de que esta hecho:

    python3 -m pytest -q tests/test_molde_techo.py -s
"""

import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TECHO = os.path.join(RAIZ, "banco_pruebas", "molde_techo.json")


def _molde_bytes(tienda_id: str = "verifika_prod") -> tuple:
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    from app.core.molde import esquemas
    esquema = esquemas(tienda_id)
    entero = len(json.dumps(esquema, ensure_ascii=False).encode())

    enums: dict = {}

    def _mirar(nodo, ruta=""):
        if isinstance(nodo, dict):
            for k, v in nodo.items():
                if k == "enum":
                    enums[ruta] = (len(v),
                                   len(json.dumps(v, ensure_ascii=False).encode()))
                else:
                    _mirar(v, f"{ruta}/{k}")
        elif isinstance(nodo, list):
            for v in nodo:
                _mirar(v, ruta)

    _mirar(esquema)
    return entero, enums


def _casilla(ruta: str) -> str:
    """El nombre legible de donde vive un enum: `atributos.campo`. La ruta
    cruda viene llena de `properties` y de `items` del JSON Schema, que son
    plomeria del formato y no casillas del molde."""
    partes = [p for p in ruta.split("/")
              if p and p not in ("function", "parameters", "properties", "items")]
    return ".".join(partes[-2:]) if partes else ruta


def test_el_molde_no_pasa_su_techo():
    with open(TECHO, encoding="utf-8") as fh:
        techo = json.load(fh)["bytes"]
    entero, enums = _molde_bytes()
    detalle = "  ".join(f"{_casilla(r)} {b}b en {n} valores"
                        for r, (n, b) in enums.items())
    print(f"\nmolde {entero} bytes de un techo de {techo}. "
          f"Enums: {detalle}")
    assert entero <= techo, (
        f"el molde pesa {entero} bytes y el techo son {techo}. Se paga en CADA "
        f"llamada al decisor. Subir el techo es decision de Martin y va en su "
        f"propio commit con las cuentas. Enums de hoy: {detalle}")
