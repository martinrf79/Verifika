"""EL SIMULADOR EN LA BATERIA — la multipregunta de los siete articulos, con el cliente y el modelo simulados (FICHA 72).

`banco_pruebas/simulador.py` corre la charla real del 19-oct por el flujo vivo con las fallas que el modelo ya tuvo en
produccion, sorteadas. Con semillas fijas el resultado es el mismo en cada corrida, asi que sirve de candado:
  - por guion, cuantas corridas terminan con el pedido de la verdad aceptado no baja del piso de
    `tests/simulador_piso.json`, que solo sube;
  - ninguna corrida muestra un presupuesto equivocado sin decir que supuso algo.
"""
import json
import os

from banco_pruebas import cableado58 as CB
from banco_pruebas import simulador as S

PISO = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulador_piso.json"),
                      encoding="utf-8"))


def test_el_simulador_no_baja_del_piso_y_no_miente():
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    interprete = CB.instalar()
    real = interprete.interpretar, interprete.explicar, interprete.elegir

    async def _explicar(*a, **k):
        return ""
    interprete.explicar = _explicar
    try:
        medido = {g: S.medir(g, PISO["corridas"], PISO["elige"], interprete) for g in S.GUIONES}
    finally:
        interprete.interpretar, interprete.explicar, interprete.elegir = real
        llm_reintento._cliente = puerta
    bien = {g: round(m["bien"] * PISO["corridas"]) for g, m in medido.items()}
    assert all(m["mal_sin_aviso"] == 0 for m in medido.values()), medido
    assert all(bien[g] >= PISO["bien"][g] for g in S.GUIONES), f"bajo del piso: {bien} contra {PISO['bien']}"
    print(f"\nSIMULADOR: {sum(bien.values())} de {PISO['corridas'] * len(bien)} corridas bien, "
          f"piso {sum(PISO['bien'].values())}, ninguna equivocada sin aviso: {bien}")
