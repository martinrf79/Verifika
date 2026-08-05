"""
EL CANDADO DEL MAPA — la zona ciega puede achicarse, nunca crecer.

QUE DEFIENDE. `banco_pruebas/mapa.py` cruza dos medidas: a que funciones se
llega desde el webhook, y cuales ejercita cada una de las 40 preguntas. Del
cruce sale LA ZONA CIEGA: codigo que corre en produccion y que ninguna prueba
toca. Medido el 5-ago: 143 de 304 funciones del camino vivo, el 47%.

POR QUE UN PISO Y NO UN CERO. Exigir cero hoy seria mentir sobre el estado y
dejar el CI rojo para siempre, que es la forma mas rapida de que nadie lo mire.
El piso dice otra cosa, que es la que sirve: **lo que se suma al camino vivo
nace con una pregunta que lo ejercite, o no se suma**. Es la regla de honestidad
de cobertura: una capa que no se ejercita no puntua.

COMO SE BAJA EL PISO. Se le escribe la prueba a una funcion ciega, se corre
`python3 banco_pruebas/mapa.py --fijar` y se commitea el piso nuevo. Cada
sesion deberia bajarlo, aunque sea de a poco.
"""
import json
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

PISO = _RAIZ / "banco_pruebas" / "mapa_piso.json"


def _mapa_en_proceso_limpio(tmp_path) -> dict:
    """EL MAPA SE MIDE EN UN PROCESO NUEVO. Medio sistema cachea -catalogo,
    FAQ, registro de campos, geo de CP-, asi que una funcion que ya corrio en
    otro test no se vuelve a ejecutar y el mapa la contaria como ciega. Medido:
    adentro de la bateria daban tres funciones ciegas de mas, y cambiaban segun
    el orden. En un subproceso el punto de partida es siempre el mismo."""
    import subprocess
    salida = tmp_path / "mapa.json"
    r = subprocess.run(
        [sys.executable, str(_RAIZ / "banco_pruebas" / "mapa.py"),
         "--json", str(salida)],
        capture_output=True, text=True, timeout=600, cwd=str(_RAIZ))
    assert salida.exists(), (
        f"el mapa no corrio: {r.returncode}\n{r.stderr[-2000:]}")
    return json.loads(salida.read_text(encoding="utf-8"))


def test_la_zona_ciega_no_crece(tmp_path):
    pytest.importorskip("coverage",
                        reason="el mapa necesita coverage para medir que "
                               "pregunta ejercita cada funcion")
    piso = json.loads(PISO.read_text(encoding="utf-8"))
    viejas = set(piso["zona_ciega"])
    ciega = {k for k, _ in _mapa_en_proceso_limpio(tmp_path)["zona_ciega"]}
    nuevas = sorted(ciega - viejas)
    assert not nuevas, (
        "ENTRO CODIGO CIEGO AL CAMINO VIVO: estas funciones corren en "
        "produccion y ninguna de las 40 preguntas las toca.\n  "
        + "\n  ".join(nuevas)
        + "\n\nO le escribis la prueba, o no va al camino vivo. Si de verdad "
          "bajo la zona ciega, refija el piso con "
          "`python3 banco_pruebas/mapa.py --fijar`.")
    assert len(ciega) <= len(viejas), (
        f"la zona ciega crecio de {len(viejas)} a {len(ciega)}")
