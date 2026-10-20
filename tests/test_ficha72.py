"""FICHA 72 — el modelo elige la lectura, queda supuesta, y el "si" la vuelve lo dicho (20-oct-2026).

La charla real de WhatsApp del 19-oct 20:01, `banco_pruebas/reales/ad9301cdf3.json`, con las agendas que escribio el
modelo ese dia. En el segundo turno el cliente dijo "el teclado va aparte, envio a Posadas" y el modelo lo anoto como un
teclado nuevo: el bot pregunto dos veces por el teclado. Ahora el codigo arma las lecturas que cierran, el modelo elige
una con la cita del cliente —aca escrita a mano, por el mismo control que la del modelo—, y sale el presupuesto entero
supuesto. El tercer turno no paso en vivo: son las formas en que el modelo puede anotar el "si", y todas aceptan.

Por el webhook entero, sin llamar al modelo.
"""
import asyncio
import copy
import json
import os

import pytest

from banco_pruebas import cableado58 as CB
from banco_pruebas import clon_produccion as C

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASO = json.load(open(os.path.join(RAIZ, "banco_pruebas", "reales", "ad9301cdf3.json"), encoding="utf-8"))
T1, T2 = CASO["turnos"]
LA_BUENA = "a Córdoba capital, 1 auriculares y 1 mouse; a Concordia, 1 mouse; a Posadas, 1 auriculares, 2 memoria ram " \
           "y 1 teclado; 7 en total"
ELIGE = {"texto": LA_BUENA, "cita": "El teclado va aparte envio a posadas"}
PAGO = [{"medio": "transferencia", "porcentaje": 70}, {"medio": "Mercado Pago", "porcentaje": 30}]


def _charla(turnos: list, elige: dict = None) -> tuple:
    """Los turnos [(mensaje, agenda)] por el webhook; devuelve lo que leyo el cliente y la libreta de cada turno."""
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    interprete = CB.instalar()
    cola, vistos = [copy.deepcopy(a) for _, a in turnos], []

    async def _interpretar(mensaje, historial, estado, *a, **k):
        vistos.append(interprete.libreta(estado, historial, C.TIENDA))
        return cola.pop(0)

    async def _explicar(*a, **k):
        return ""
    real = interprete.interpretar, interprete.explicar
    interprete.interpretar, interprete.explicar = _interpretar, _explicar
    CB.ELEGIR.clear()
    CB.ELEGIR.update(elige or {})
    try:
        uid = f"ficha72_{abs(hash(json.dumps(turnos, sort_keys=True))) % 10 ** 8}"
        C.reiniciar_cliente(uid)
        return ["\n".join(asyncio.run(C.turno(uid, m))) for m, _ in turnos], vistos
    finally:
        interprete.interpretar, interprete.explicar = real
        llm_reintento._cliente = puerta
        CB.ELEGIR.clear()


def test_el_modelo_elige_la_lectura_y_sale_el_presupuesto_entero_supuesto():
    (r1, r2), vistos = _charla([(T1["mensaje"], T1["agenda"]), (T2["mensaje"], T2["agenda"])],
                               {T2["mensaje"]: ELIGE})
    assert "Entendí tu pedido así: " + LA_BUENA in r2, r2
    assert r2.count("Presupuesto:") == 3 and "Total general" in r2, r2
    # No vuelve a preguntar por el teclado, ni dos veces; lo que falta es lo unico que pregunta.
    assert "no estaba en tu lista" not in r2 and "¿Lo dejo así?" in r2 and "el 30%?" in r2, r2


def test_sin_eleccion_del_modelo_queda_como_antes():
    # Ninguna lectura con cita: el borrador pregunta como siempre, sin presupuesto.
    (r1, r2), _ = _charla([(T1["mensaje"], T1["agenda"]), (T2["mensaje"], T2["agenda"])])
    assert "Presupuesto:" not in r2 and "no estaba en tu lista" in r2, r2


def test_una_cita_que_el_cliente_no_dijo_no_vale():
    (r1, r2), _ = _charla([(T1["mensaje"], T1["agenda"]), (T2["mensaje"], T2["agenda"])],
                          {T2["mensaje"]: {"texto": LA_BUENA, "cita": "el teclado va con las memorias"}})
    assert "Entendí tu pedido así" not in r2, r2


T3 = "Si, dejalo asi. El 30 con mercado pago"
ACEPTA = {
    "acepta": [{"n": 1, "cita": "Si, dejalo asi.", "accion": "comprar", "responde": "R-1", "acepta": ["L-1"]}],
    "responde": [{"n": 1, "cita": "Si, dejalo asi.", "accion": "otro", "que": "dato", "responde": "R-1"}],
    "confirma": [{"n": 1, "cita": "Si, dejalo asi.", "accion": "comprar", "confirma": ["L-1"]}],
}


@pytest.mark.parametrize("forma", ACEPTA)
def test_el_si_a_lo_supuesto_lo_vuelve_lo_dicho_como_lo_anote_el_modelo(forma):
    pago = {"n": 2, "cita": "El 30 con mercado pago", "accion": "cuenta", "responde": "R-2", "reparto": PAGO}
    (_, r2, r3), vistos = _charla([(T1["mensaje"], T1["agenda"]), (T2["mensaje"], T2["agenda"]),
                                   (T3, {"preguntas": ACEPTA[forma] + [pago]})], {T2["mensaje"]: ELIGE})
    # La libreta del tercer turno le dijo al modelo que habia un supuesto y como aceptarlo.
    assert "SUPUESTO, Entendí tu pedido así" in vistos[2] and "R-1 \"¿Lo dejo así?\"" in vistos[2], vistos[2]
    assert "¿Lo dejo así?" not in r3 and "Entendí" not in r3, r3
    assert "Mercado Pago (30%)" in r3 and "Total general" in r3 and "nombre" in r3, r3


def test_un_si_solo_cuando_lo_unico_abierto_es_lo_supuesto():
    t2 = copy.deepcopy(T2["agenda"])
    t2["preguntas"][2].update(cita="y 70 transferencia y 30 mercado pago", reparto=PAGO)
    msg2 = T2["mensaje"] + " y 30 mercado pago"
    saludo = {"preguntas": [{"n": 1, "cita": "dale, perfecto", "accion": "otro", "que": "saludo"}]}
    (_, r2, r3), _ = _charla([(T1["mensaje"], T1["agenda"]), (msg2, t2), ("dale, perfecto", saludo)],
                             {msg2: ELIGE})
    assert r2.strip().endswith("¿Lo dejo así?"), r2
    assert "¿Lo dejo así?" not in r3 and "nombre" in r3, r3


def test_la_eleccion_se_controla():
    from app.core.flujo import interprete
    ls = [{"huella": "a", "texto": "x"}, {"huella": "b", "texto": "y"}]
    msg = "El teclado va aparte, envío a Posadas."
    assert interprete.eleccion({"lectura": 2, "cita": "va aparte envio a posadas"}, msg, [], ls) == "b"
    assert interprete.eleccion({"lectura": 3, "cita": "va aparte envio a posadas"}, msg, [], ls) == ""
    assert interprete.eleccion({"lectura": 1, "cita": "va a Concordia"}, msg, [], ls) == ""
    assert interprete.eleccion({"lectura": 1, "cita": "si"}, msg, [], ls) == ""
    assert interprete.eleccion({"lectura": 0}, msg, [], ls) == ""
    # La cita puede venir de un mensaje anterior del cliente.
    assert interprete.eleccion({"lectura": 1, "cita": "los otros dos"}, "dale", [
        {"role": "user", "content": "Los otros dos a Posadas"}], ls) == "a"
    print("\nELECCION: 6 de 6 controles")
