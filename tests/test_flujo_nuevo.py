"""EL FLUJO NUEVO DE DOS LLAMADAS, CON LO QUE GRABO EL MODELO — la vara del bot desde el 17-nov-2026, orden de Martin.

Reemplaza a `test_agente.py`: el agente quedo archivado, se vuelve a el con git revert. Las 26 charlas pasan por el webhook
entero del clon, `turno.procesar_turno` -> `nuevo/turno.responder`, con las piezas grabadas del banco,
`banco_pruebas/flujo/segunda.py`: la llamada 0 elegida, los puntajes de los embeddings y Jev de cada nexo, y la segunda
llamada de la corrida s2. El codigo que corre es el del bot: los nexos, el texto del codigo, el control, los comandos del
pedido y la memoria.

  bien      turnos cuyas casillas de `vara_58.json` pasan: el piso es lo medido el 17-nov, 58 de 75.
  memoria   lo que el turno guarda en Firestore vuelve en el siguiente: lo visto y el pedido.
  sin red   si la segunda llamada, los nexos o la llamada 0 fallan, el cliente igual recibe el texto del codigo o una
            pregunta, nunca un error.
"""
import asyncio
import os
import sys

import pytest

AQUI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "banco_pruebas", "flujo")
sys.path.insert(0, AQUI)

TURNOS, PISO_BIEN = 75, 58


@pytest.fixture(scope="module")
def S():
    import segunda
    from app.core.flujo.nuevo import turno as T
    responder = T.responder
    yield segunda
    T.responder = responder


@pytest.fixture(scope="module")
def corrida(S):
    return S.correr("s2")


def test_las_26_charlas_no_bajan_del_piso(corrida):
    malas = [f"{f['id']} t{f['turno'] + 1}: {f['malas']}" for f in corrida["filas"] if f["malas"]]
    print(f"\nFLUJO NUEVO: {corrida['bien']} de {corrida['turnos']} turnos bien")
    assert corrida["turnos"] == TURNOS
    assert corrida["bien"] >= PISO_BIEN, "\n".join(malas)


def test_la_memoria_vuelve_en_el_turno_siguiente(S, corrida):
    """C50: "estoy entre el G203 y el G305", "me llevo uno", "el primero". Lo visto se guarda en Firestore, un objeto por
    turno: como lista de listas Firestore lo rechazaba y la memoria se perdia sin aviso, corrida s1 del 17-nov."""
    from app.storage import firestore_client as fc
    from banco_pruebas import clon_produccion as C
    S.correr("s2", ["C50"])
    m = (fc.get_conversation("agente_C50", tienda_id=C.TIENDA) or {}).get("memoria_agente") or {}
    assert m.get("vistos") and all(isinstance(v, dict) and v.get("ids") for v in m["vistos"])
    assert m.get("pedido") and "G203" in str(m["pedido"])


class _Rota:
    """Piezas que fallan: la que se nombra levanta."""

    def __init__(self, falla, base):
        self.falla, self.base = falla, base

    def lineas(self, mensaje):
        if self.falla == "lineas":
            raise RuntimeError("sin llamada 0")
        return self.base.lineas(mensaje)

    def nexos(self, mensaje, crudas):
        if self.falla == "nexos":
            raise RuntimeError("sin embeddings")
        return self.base.nexos(mensaje, crudas)

    async def segunda(self, usuario):
        if self.falla == "segunda":
            raise RuntimeError("sin segunda llamada")
        return await self.base.segunda(usuario)


@pytest.mark.parametrize("falla", ["segunda", "nexos", "lineas"])
def test_si_una_pieza_cae_el_cliente_igual_recibe_respuesta(S, corrida, falla):
    from app.core.flujo import agente as A
    S.ESTADO.update({"charla": "K16", "turno": 0, "cid": None, "etiqueta": "s2", "modo": "grabado"})
    r = asyncio.run(S._RESPONDER["vivo"]("quiero 2 mouse genius dx-110 negro y 1 teclado logitech k120 negro, cuanto sale?",
                                         [], A.memoria_de({}), "u_rota", "telegram", "verifika_prod", "t",
                                         piezas=_Rota(falla, S.Grabado())))
    assert "respuesta" in r
    if falla == "segunda":
        # Sin segunda llamada sale el texto del codigo, con los precios reales.
        assert "8.500" in r["respuesta"] and "14.500" in r["respuesta"]


@pytest.mark.xfail(strict=True, reason="A MEDIAS: la charla larga de 22 turnos, 17-nov. El lugar del primer turno llega al "
                                       "ultimo y el total sale bien, 47.500, pero dice Misiones y no Posadas: la llamada 0 "
                                       "no marca destino en 'soy de Posadas, Misiones' y la segunda llamada toma la provincia.")
def test_la_charla_larga_recuerda_la_ciudad_del_primer_turno(S, corrida):
    assert S.larga("m1")
