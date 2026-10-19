"""LA PRIMERA CHARLA REAL CON LA AGENDA — 20-oct-2026, por WhatsApp, apenas deployado.

El modelo escribio la agenda de abajo, tal cual la guardo `interprete_ok`, y el codigo fallo en tres cosas:
  1. partio la compra en tres preguntas y anoto la primera sola, con su presupuesto, mientras preguntaba por las otras;
  2. "los otros dos" no contaba lo de las otras dos preguntas: "quedan 2 auriculares, 2 mouse, 2 memoria";
  3. el 70/30 sin medio salio como cobro: "sin decir (70%)", con partes que no suman el total.
Y al turno siguiente la compra que no se anoto no estaba en ningun lado: el modelo no la podia rearmar.

Con la agenda del modelo, por el webhook entero y sin llamar al modelo.
"""
import asyncio

from banco_pruebas import cableado58 as CB
from banco_pruebas import clon_produccion as C

MENSAJE = ("Dame precio de dos auriculares, dos mouse y dos memorias. El precio no sería tan importante. Lo que sí que "
           "necesito que lleven las menos partes chinas posibles. Un auricular y un mouse será envío a Córdoba capital. "
           "Un teclado y un mouse será envío a Concordia. Los otros dos artículos serán con envío a posadas. Divide el "
           "presupuesto en setenta treinta, ya que veré en la fase siguiente cómo seguimos")

DEL_MODELO = {"preguntas": [
    {"n": 1, "cita": "Dame precio de dos auriculares,", "accion": "buscar", "rubro": "auriculares", "cantidad": 2,
     "orden": "nada"},
    {"n": 2, "cita": "dos mouse", "accion": "buscar", "rubro": "mouse", "cantidad": 2, "orden": "nada"},
    {"n": 3, "cita": "y dos memorias.", "accion": "buscar", "rubro": "memoria ram", "cantidad": 2, "orden": "nada"},
    {"n": 4, "cita": "El precio no sería tan importante.", "accion": "otro", "que": "dato"},
    {"n": 5, "cita": "Lo que sí que necesito que lleven las menos partes chinas posibles.", "accion": "politica",
     "tema": "contenido_caja"},
    {"n": 6, "cita": "Un auricular y un mouse será envío a Córdoba capital.", "accion": "comprar", "agrega": [
        {"producto": "auriculares", "cantidad": 1, "destino": "Córdoba capital"},
        {"producto": "mouse", "cantidad": 1, "destino": "Córdoba capital"}]},
    {"n": 7, "cita": "Un teclado y un mouse será envío a Concordia.", "accion": "comprar", "agrega": [
        {"producto": "teclado", "cantidad": 1, "destino": "Concordia"},
        {"producto": "mouse", "cantidad": 1, "destino": "Concordia"}]},
    {"n": 8, "cita": "Los otros dos artículos serán con envío a posadas.", "accion": "comprar", "agrega": [
        {"producto": "los otros", "cantidad": 2, "destino": "Posadas"}]},
    {"n": 9, "cita": "Divide el presupuesto en setenta treinta, ya que veré en la fase siguiente cómo seguimos",
     "accion": "cuenta", "reparto": [{"medio": "sin decir", "porcentaje": 70},
                                     {"medio": "sin decir", "porcentaje": 30}]}], "cliente": {}}


def test_la_compra_partida_se_pregunta_entera_y_queda_para_el_turno_siguiente():
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    interprete = CB.instalar()
    vistos = []

    async def _interpretar(mensaje, historial, estado, *a, **k):
        vistos.append(interprete.libreta(estado, historial, C.TIENDA))
        return DEL_MODELO if len(vistos) == 1 else {"preguntas": []}

    async def _explicar(*a, **k):
        return ""
    real = interprete.interpretar, interprete.explicar
    interprete.interpretar, interprete.explicar = _interpretar, _explicar
    try:
        C.reiniciar_cliente("real_20oct")
        texto = "\n".join(asyncio.run(C.turno("real_20oct", MENSAJE)))
        asyncio.run(C.turno("real_20oct", "Si serian 7 articulos en total, lo demas como te dije"))
    finally:
        interprete.interpretar, interprete.explicar = real
        llm_reintento._cliente = puerta
    # 1. Nada anotado a medias: sin presupuesto mientras pregunta.
    assert "Presupuesto:" not in texto, texto
    assert "teclado" in texto and "?" in texto, texto
    # 2. Si pregunta por los otros, cuenta lo de las otras preguntas: no quedan 2 de cada uno.
    assert "quedan 2 auriculares, 2 mouse" not in texto, texto
    # 3. El reparto sin medio se pregunta, no se cobra.
    assert "sin decir" not in texto and "medio" in texto, texto
    # Y la compra queda entera en la libreta del turno siguiente, con sus destinos.
    assert "SIN ANOTAR" in vistos[1] and all(d in vistos[1] for d in ("Concordia", "Posadas")), vistos[1]
    print(f"\nREAL 20-OCT: 4 de 4 fallas cubiertas\n{texto}\n---\n{vistos[1]}")
