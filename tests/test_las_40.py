"""
EL MARCADOR, CABLEADO AL CI. Corre `banco_pruebas/las_40.py` -las 40 pruebas
reales de Martin, la parte de CODIGO- en cada push, gratis y en dos segundos.

POR QUE ES UN TEST Y NO UN SCRIPT QUE ALGUIEN SE ACUERDA DE CORRER. Es la misma
historia de siempre en este repo: la capacidad existia y nadie la miraba, asi
que se rompia en silencio y aparecia semanas despues leyendo una charla real.
Con esto, la pregunta que se cae vuelve con nombre y apellido en la corrida.

LA REGLA: el marcador no baja. Si sumas una pregunta al registro y sale roja, se
arregla antes de mergear; ese es el metodo del RESUMEN, no una formalidad. Un
rojo aca dice exactamente cual de las 40 se rompio y por que.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))


def test_las_40_siguen_en_verde(firestore_doble):
    from banco_pruebas.las_40 import correr, LAS_40

    filas = correr()
    assert len(filas) == len(LAS_40) == 40
    rojas = [f"{f['id']} ({f['nombre']}): {f['causa'] or f['obtenido']}"
             for f in filas if not f["ok"]]
    assert not rojas, ("EL MARCADOR BAJO. Preguntas en rojo:\n  "
                       + "\n  ".join(rojas))
