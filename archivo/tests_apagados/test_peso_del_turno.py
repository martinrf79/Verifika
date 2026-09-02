"""
EL CANDADO DEL PESO — el turno puede adelgazar, nunca engordar.

Es el ESPEJO del piso del mapa: alla la cobertura no puede bajar, aca el peso no
puede subir. Nacio del pedido de Martin del 13-ago de aliviar la carga del
modelo, y de una medicion que no existia: el repo sabia si el bot contestaba
BIEN y no sabia cuanto costaba cada respuesta.

POR QUE HACE FALTA UN CANDADO Y NO UN INFORME. El esquema de herramientas no lo
escribe nadie a mano: sale de los moldes Pydantic. Un campo nuevo con su
descripcion y su enum entra sin que nadie lo vea, y cada byte viaja en las DOS a
CUATRO llamadas de cada turno de cada cliente. Asi se llego a 27.518 bytes por
llamada, el 92% en el esquema, sin una sola decision de engordar.

Corre en cada push y tarda menos de un segundo: lee moldes, no llama a nadie.
"""
import json
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import peso_del_turno as P  # noqa: E402


def test_el_turno_no_engorda(firestore_doble):
    """LA VARA. Si un campo, una descripcion o un enum hacen crecer lo que
    viaja al modelo, esto lo dice en el mismo push. Bajar el techo se hace a
    mano con `--fijar`, que es una decision; subirlo no es una opcion."""
    m = P.medir()
    excesos = P.comparar_con_el_techo(m)
    assert not excesos, (
        "EL TURNO ENGORDO. Cada byte de estos viaja en las 2 a 4 llamadas de "
        "cada turno de cada cliente:\n  " + "\n  ".join(excesos))


def test_el_techo_existe_y_dice_de_que_esta_hecho(firestore_doble):
    """El techo sin desglose no sirve para bajarlo: hay que poder ver QUE pesa."""
    assert P.TECHO.exists(), "falta peso_techo.json"
    techo = json.loads(P.TECHO.read_text(encoding="utf-8"))
    assert techo["bytes_por_llamada"] > 0
    assert techo["detalle"], "el techo no guarda el desglose por herramienta"
    m = P.medir()
    assert set(techo["detalle"]) == set(m["detalle"]), (
        "el techo y la medicion no hablan de las mismas herramientas: "
        f"techo={sorted(techo['detalle'])} medido={sorted(m['detalle'])}")


def test_el_esquema_es_el_que_manda_y_queda_dicho(firestore_doble):
    """No es un test de umbral arbitrario: fija el HECHO que ordena el trabajo
    de aliviar. El 92% de lo que viaja al modelo es el esquema de herramientas,
    no las instrucciones. Cualquier sesion que quiera aliviar la carga tiene
    que atacar el esquema; limar los prompts es limar el 8%. Si algun dia esto
    se da vuelta, el rojo avisa que la conclusion cambio."""
    m = P.medir()
    assert m["pct_esquema"] > 60.0, (
        f"el esquema paso a ser el {m['pct_esquema']}% del peso: cambio la "
        "forma del problema y hay que releer por donde se aliviana")


def test_lo_que_el_modelo_no_llamo_nunca_queda_a_la_vista(firestore_doble):
    """NO es una vara: es un foco. Que una herramienta no aparezca en las 15
    charlas grabadas NO prueba que sea inutil -son 15, no el universo- pero si
    dice donde mirar primero cuando se recorte. Se afirma que la medicion
    funciona, no que el resultado sea de una forma."""
    m = P.medir()
    assert m["uso"]["turnos"] >= 40, (
        f"solo {m['uso']['turnos']} turnos grabados: la evidencia de uso quedo "
        "demasiado flaca para orientar un recorte")
    assert sum(m["uso"]["llamadas"].values()) > 100, (
        "el contador de uso no esta leyendo las llamadas de los casetes")
