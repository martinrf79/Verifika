"""EL AGENTE VIVO CON LO QUE GRABO EL MODELO — la vara del bot desde el 30-oct-2026, orden de Martin, FICHA 83.

Reemplaza a `test_cableado58.py`, que pasaba las 58 con la traduccion a mano por la lectura, que ya no esta en el bot.
Las 26 charlas que el agente grabo en el banco con su propia memoria pasan por el webhook entero del clon, con un modelo
falso que devuelve lo que devolvio el de verdad, `banco_pruebas/agente_replay.py`. Corre en cada push, antes del deploy.

  bien      turnos cuyas casillas de `vara_58.json` pasan: el piso es lo medido en el banco, 69 de 75.
  iguales   llamadas a herramientas que devuelven lo mismo que en el banco: todas. Si una cambia, el codigo cambio lo
            que el modelo leyo cuando se midio, y hay que medir de nuevo con el modelo.
"""
import pytest

from banco_pruebas import agente_replay as R

TURNOS, PISO_BIEN = 75, 69


@pytest.fixture(scope="module")
def corrida():
    from app.core import llm_reintento
    from app.core.flujo import agente
    puerta, responder, parecidos = llm_reintento._cliente, agente.responder, agente._parecidos
    yield R.correr()
    llm_reintento._cliente, agente.responder, agente._parecidos = puerta, responder, parecidos


def test_las_charlas_grabadas_no_bajan_del_piso(corrida):
    malas = [f"{f['id']} t{f['turno'] + 1}: {f['malas']}" for f in corrida["filas"] if f["malas"]]
    print(f"\nAGENTE: {corrida['bien']} de {corrida['turnos']} turnos bien")
    assert corrida["turnos"] == TURNOS
    assert corrida["bien"] >= PISO_BIEN, "\n".join(malas)


def test_cada_herramienta_devuelve_lo_que_leyo_el_modelo_al_medir(corrida):
    distintas = [f"{f['id']} t{f['turno'] + 1}: {f['distintas']}" for f in corrida["filas"] if f["distintas"]]
    print(f"\nHERRAMIENTAS: {corrida['iguales']} de {corrida['llamadas']} devuelven lo mismo que en el banco")
    assert corrida["iguales"] == corrida["llamadas"], "\n".join(distintas)
