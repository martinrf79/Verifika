"""LA SEGUNDA CHARLA REAL CON LA AGENDA — 20-oct-2026, 13:43 UTC, por WhatsApp.

El bot pregunto "¿lo sumo el teclado?", el cliente dijo que si dos veces, y el bot volvio a preguntar lo mismo. Las
tres agendas son las que escribio el modelo, tal cual las guardo `interprete_ok`. Es la falla de memoria y cableado
que resuelve la FICHA 71, el borrador: el si confirma el renglon L-3 y no se vuelve a preguntar.
"""
import asyncio

from banco_pruebas import cableado58 as CB
from banco_pruebas import clon_produccion as C
from tests.test_charla_real_20oct import MENSAJE

T1 = {"preguntas": [
    {"n": 1, "cita": "Dame precio de dos auriculares,", "accion": "buscar", "rubro": "auriculares", "cantidad": 2,
     "orden": "nada"},
    {"n": 2, "cita": "dos mouse", "accion": "buscar", "rubro": "mouse", "cantidad": 2, "orden": "nada"},
    {"n": 3, "cita": "y dos memorias.", "accion": "buscar", "rubro": "memoria ram", "cantidad": 2, "orden": "nada"},
    {"n": 4, "cita": "El precio no sería tan importante.", "accion": "otro", "que": "dato"},
    {"n": 5, "cita": "Lo que sí que necesito que lleven las menos partes chinas posibles.", "accion": "otro",
     "que": "dato"},
    {"n": 6, "cita": "Un auricular y un mouse será envío a Córdoba capital.", "accion": "comprar", "agrega": [
        {"producto": "auriculares", "cantidad": 1, "destino": "Córdoba capital"},
        {"producto": "mouse", "cantidad": 1, "destino": "Córdoba capital"}]},
    {"n": 7, "cita": "Un teclado y un mouse será envío a Concordia.", "accion": "comprar", "agrega": [
        {"producto": "teclado", "cantidad": 1, "destino": "Concordia"},
        {"producto": "mouse", "cantidad": 1, "destino": "Concordia"}]},
    {"n": 8, "cita": "Los otros dos artículos serán con envío a posadas.", "accion": "comprar", "agrega": [
        {"producto": "los otros", "cantidad": 2, "destino": "Posadas"}]},
    {"n": 9, "cita": "Divide el presupuesto en setenta treinta,", "accion": "cuenta", "reparto": [
        {"medio": "sin decir", "porcentaje": 70}, {"medio": "sin decir", "porcentaje": 30}]},
    {"n": 10, "cita": "ya que veré en la fase siguiente cómo seguimos", "accion": "otro", "que": "dato"}],
    "cliente": {}}
T2 = {"preguntas": [
    {"n": 1, "cita": "Si en realidad son 7 articulos,", "accion": "otro", "que": "dato"},
    {"n": 2, "cita": "el teclado va a concordia,", "accion": "comprar", "responde": "R-1",
     "agrega": [{"producto": "teclado", "cantidad": 1, "destino": "Concordia"}]},
    {"n": 3, "cita": "lo demas como te dije.", "accion": "comprar", "responde": "R-1", "agrega": [
        {"producto": "auriculares", "cantidad": 1, "destino": "Córdoba capital"},
        {"producto": "mouse", "cantidad": 1, "destino": "Córdoba capital"},
        {"producto": "mouse", "cantidad": 1, "destino": "Concordia"},
        {"producto": "los otros", "cantidad": 2, "destino": "Posadas"}]}]}
T3 = {"preguntas": [
    {"n": 1, "cita": "Si suma el teclado", "accion": "comprar", "responde": "R-1", "agrega": [
        {"producto": "teclado", "cantidad": 1, "destino": "Concordia"},
        {"producto": "auriculares", "cantidad": 1, "destino": "Córdoba capital"},
        {"producto": "mouse", "cantidad": 1, "destino": "Córdoba capital"},
        {"producto": "mouse", "cantidad": 1, "destino": "Concordia"},
        {"producto": "los otros", "cantidad": 2, "destino": "Posadas"}]}], "cliente": {}}
TURNOS = [(MENSAJE, T1), ("Si en realidad son 7 articulos, el teclado va a concordia, lo demas como te dije.", T2),
          ("Si suma el teclado", T3)]


def test_un_si_a_la_repregunta_no_la_vuelve_a_preguntar():
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    interprete = CB.instalar()
    cola = [a for _, a in TURNOS]

    async def _interpretar(*a, **k):
        return cola.pop(0)

    async def _explicar(*a, **k):
        return ""
    real = interprete.interpretar, interprete.explicar
    interprete.interpretar, interprete.explicar = _interpretar, _explicar
    try:
        C.reiniciar_cliente("real_20oct_b")
        respuestas = ["\n".join(asyncio.run(C.turno("real_20oct_b", m))) for m, _ in TURNOS]
    finally:
        interprete.interpretar, interprete.explicar = real
        llm_reintento._cliente = puerta
    print("\nREAL 20-OCT B: 3 turnos\n" + "\n---\n".join(respuestas))
    assert "teclado" in respuestas[0] and "?" in respuestas[0], respuestas[0]
    # El cliente ya dijo que si al teclado: el bot no lo vuelve a preguntar, ni en el segundo turno ni en el tercero.
    for r in respuestas[1:]:
        assert "Pediste teclado" not in r, r
