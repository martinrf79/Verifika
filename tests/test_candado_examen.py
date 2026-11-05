"""EL CANDADO DE LO QUE YA ANDA — FICHA 87, solucion 1, 5-nov-2026.

Las 42 charlas reales grabadas con el catalogo en SQL pasan por el codigo de hoy sin modelo,
`banco_pruebas/examen_real/candado.py`, y en los 100 turnos que esa corrida tenia bien se compara lo que pone el codigo
—presupuestos, cobro, lo que marca el verificador y el texto final— contra la foto `candado_sql_r2.json`. Hasta el 5-nov
cuidaba 79 turnos de la corrida del 3-nov, grabada con la busqueda por frases, que se borro. Un cambio que altera uno hace fallar el test: se mira el turno, y si
el cambio lo mejoro se saca la foto de nuevo en el mismo commit, diciendo que turno y por que.
"""
import pytest

from banco_pruebas.examen_real import candado as CA

CUIDADOS = 100


@pytest.fixture(scope="module")
def hoy():
    from app.core import llm_reintento
    from app.core.flujo import agente
    puerta, responder, parecidos = llm_reintento._cliente, agente.responder, agente._parecidos
    yield CA.correr()
    llm_reintento._cliente, agente.responder, agente._parecidos = puerta, responder, parecidos


def test_los_turnos_que_andaban_no_cambian(hoy):
    import json
    foto = json.load(open(CA.FOTO, encoding="utf-8"))
    cuidados = [k for k in foto if CA.cuidado(k.split(" t")[0], int(k.split(" t")[1]))]
    cambiados = CA.diferencias(foto, hoy["turnos"])
    print(f"\nCANDADO: {len(cuidados) - len(cambiados)} de {len(cuidados)} turnos que andaban, iguales")
    assert len(cuidados) == CUIDADOS
    assert not cambiados, "\n".join(cambiados)


def test_ninguna_consulta_sin_sus_parecidos(hoy):
    """Una consulta nueva da otros rubros que en produccion: se rearma la tabla con `candado.py --parecidos`."""
    assert not hoy["faltan"], hoy["faltan"]


def test_ningun_turno_sin_respuesta(hoy):
    sin = [k for k, v in hoy["turnos"].items() if v["error"]]
    print(f"\nTURNOS SIN RESPUESTA: {len(sin)} de {len(hoy['turnos'])}")
    assert not sin, sin
