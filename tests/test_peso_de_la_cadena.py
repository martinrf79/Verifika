"""
EL CANDADO DEL PESO DE LA CADENA.

Lo que mide y por que, en `banco_pruebas/peso_de_la_cadena.py`. Aca solo se
exige que el instrumento SIRVA: que corra, que mida todas las piezas del grafo
y no una lista aparte, y que el par que se pisa siga siendo visible.

NO tiene piso ni techo a proposito. Los numeros de este banco estan para
CAMBIAR: cuando el recorte fusione dos piezas, las veces y el solapamiento
bajan, y eso es el exito, no una regresion. Ponerle un piso seria congelar
justo lo que se quiere mover.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import peso_de_la_cadena as PC  # noqa: E402


def test_el_instrumento_mide_todas_las_piezas_del_grafo(firestore_doble):
    """La lista de piezas sale del cableado declarado, no de una copia. Si
    alguien agrega una guarda al turno, entra a la medicion por existir."""
    from app.verifika import grafo as G
    r = PC.medir()
    assert r["nodos"] == len(G.barribles()), (
        "el banco dejo de medir todas las piezas barribles del grafo")
    assert r["corridas"] > 0


def test_se_sigue_viendo_con_quien_se_pisa_cada_pieza(firestore_doble):
    """El dato que ordena el recorte es el solapamiento. Si el banco deja de
    calcularlo, la proxima sesion vuelve a recortar a ojo, que es como se
    rompio la respuesta dos veces."""
    r = PC.medir()
    assert r["pisan"], (
        "el banco no reporta ni un par que se pise: o se fusionaron todas, "
        "que seria una gran noticia, o el calculo se rompio")
    for p in r["pisan"]:
        assert 0 < p["solapamiento"] <= 100
        assert p["a"] != p["b"]
