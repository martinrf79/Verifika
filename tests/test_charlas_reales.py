"""LAS CHARLAS REALES DE WHATSAPP, OTRA VEZ POR EL FLUJO VIVO — sin modelo (20-oct-2026).

Cada charla de `banco_pruebas/reales/` trae lo que mando el cliente y la agenda que devolvio el interprete en
produccion. Se repite turno por turno por el webhook entero del clon, como `cableado58`, con esas agendas, y se
controlan las clases que fallaron en vivo:

  el cierre no repite la cuenta que el cliente acaba de leer, ni deja un titulo suelto;
  con el pedido armado, una pregunta de la FAQ no termina invitando a elegir un producto;
  lo que el codigo elige de un rubro entra al pedido con aviso, se haya buscado el rubro o no.
"""
import json

import pytest

from banco_pruebas import cableado58 as R


def _charla(id_: str) -> dict:
    return json.load(open(f"banco_pruebas/reales/{id_}.json", encoding="utf-8"))


def _repetir(id_: str) -> list:
    """Lo que recibe el cliente hoy, turno por turno, con las agendas que grabo produccion."""
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    it = R.instalar()
    c = _charla(id_)
    charla = {"id": "real_" + c["id"], "turnos": [{"texto": t["mensaje"], "casillas": []} for t in c["turnos"]]}
    turnos = R.correr(charla, [t["agenda"] for t in c["turnos"]], it, {})
    llm_reintento._cliente = puerta
    return [t["respuesta"] for t in turnos]


@pytest.fixture(scope="module")
def joaquin():
    """La de los siete articulos a tres destinos del 20-oct, 15:26, que cerro con nombre y pago."""
    return _repetir("f95def4b1d")


def test_el_cierre_no_repite_la_cuenta_recien_leida(joaquin):
    pide_nombre, cierre = joaquin[-2], joaquin[-1]
    assert "Presupuesto:" in pide_nombre and "nombre" in pide_nombre
    assert "tomamos tu pedido" in cierre
    assert "Presupuesto:" not in cierre and "Resumen:" not in cierre, cierre


def test_con_pedido_la_faq_no_invita_a_elegir_producto(joaquin):
    from app.core.flujo import catalogo  # noqa: F401 — el clon ya instalo la FAQ del repo
    from app.storage.firestore_client import get_all_faq
    faq = get_all_faq(tienda_id="verifika_prod")["formas_pago"]
    medios = joaquin[2]
    assert faq["respuesta"] in medios, medios
    assert faq["respuesta_curada"][-60:] not in medios


def test_lo_elegido_sin_buscar_se_avisa(joaquin):
    # El teclado se pidio sin buscar su rubro: entra al pedido como lo eligio el codigo, y se dice.
    con_pedido = next(r for r in joaquin if "Teclado" in r and "Presupuesto:" in r)
    assert "Para el presupuesto tomé" in con_pedido and "teclado" in con_pedido.split("Para el presupuesto tomé")[1]


def test_el_cierre_no_repite_la_cuenta_leida_antes_de_otra_pregunta():
    # 20-oct, 16:56: la cuenta, despues las cuotas, despues el nombre. La cuenta ya leida no vuelve en el cierre.
    c = _charla("890d797d59")
    # En produccion el modelo eligio la unica lectura que cierra: la webcam aparte de la lista.
    R.ELEGIR[c["turnos"][0]["mensaje"]] = {"texto": "a Rosario, 1 mouse y 1 monitor; a Mendoza, 3 mouse, 1 monitor y "
                                                    "1 webcam; 7 en total", "cita": "y sumame una webcam para Mendoza"}
    try:
        cuenta, cuotas, cierre = _repetir("890d797d59")
    finally:
        R.ELEGIR.pop(c["turnos"][0]["mensaje"], None)
    assert "Presupuesto:" in cuenta and "cuotas" in cuotas and "Presupuesto:" not in cuotas
    assert "tomamos tu pedido" in cierre and "Presupuesto:" not in cierre, cierre


def test_con_tope_elige_lo_mas_barato_y_el_pago_partido_no_queda_sin_resolver():
    # 20-oct, 18:39: siete articulos a dos destinos, "no mas de 600 mil" y "mitad transferencia, mitad Mastercard".
    # Se elegia la primera opcion de cada rubro, 1,4 millones sin aviso, y la segunda pregunta de plata quedaba suelta.
    c = _charla("4fd4fffe62")
    R.ELEGIR[c["turnos"][0]["mensaje"]] = {"texto": "a Rosario, 2 mouse, 1 teclado y 1 webcam; a Neuquén, 1 mouse, 1 "
                                                    "teclado y 1 auriculares; 7 en total", "cita": "el resto a Neuquén"}
    try:
        cuenta = _repetir("4fd4fffe62")[0]
    finally:
        R.ELEGIR.pop(c["turnos"][0]["mensaje"], None)
    assert "No llegué a resolver" not in cuenta, cuenta
    assert "Pago dividido" in cuenta and "el más barato de teclado" in cuenta
    total = int(cuenta.split("Total final: $")[1].split()[0].replace(".", ""))
    assert total <= 600000, cuenta


def test_cambiar_el_criterio_del_pedido_mantiene_los_destinos():
    # 20-oct, 19:29: con el pedido armado, "arma todo con lo mejor que tengas". Se tradujo como rehacer el pedido y se
    # perdieron la webcam y los destinos. Traducido como manda la consigna, un buscar por rubro con el orden nuevo, el
    # codigo rearma el pedido con lo mismo dicho, lo cuenta y la lectura elegida sigue valiendo.
    c = _charla("19d2fdb852")
    m0 = c["turnos"][0]["mensaje"]
    R.ELEGIR[m0] = {"texto": "a Rosario, 2 mouse, 1 teclado y 1 webcam; a Neuquén, 1 mouse, 1 teclado y 1 auriculares; "
                             "7 en total", "cita": "el resto a Neuquén"}
    mejor = {"preguntas": [{"n": i, "cita": "Arma todo con lo mejor que tengas", "accion": "buscar", "rubro": r,
                            "orden": "mas caro"} for i, r in enumerate(("mouse", "teclado", "auriculares", "webcam"), 1)]}
    charla = {"id": "real_mejor", "turnos": [{"texto": m0, "casillas": []},
                                             {"texto": "Arma todo con lo mejor que tengas", "casillas": []}]}
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    try:
        respuestas = [t["respuesta"] for t in R.correr(charla, [c["turnos"][0]["agenda"], mejor], R.instalar(), {})]
    finally:
        R.ELEGIR.pop(m0, None)
        llm_reintento._cliente = puerta
    mejor_ = respuestas[1]
    assert "Envio a Rosario" in mejor_ and "Envio a Neuquén" in mejor_ and "Webcam" in mejor_, mejor_
    assert "el de gama más alta de teclado" in mejor_ and "Total general" in mejor_


def test_otro_orden_para_lo_pedido_se_reparte_a_cada_rubro():
    # "No tomes lo mas barato, toma lo mas caro", como lo tradujo Gemini el 20-oct con la consigna nueva: una busqueda
    # con rubro "lo pedido". El codigo la reparte a los cuatro rubros, webcam incluida, y "entre lo mostrado" no vale.
    c = _charla("19d2fdb852")
    m0 = c["turnos"][0]["mensaje"]
    R.ELEGIR[m0] = {"texto": "a Rosario, 2 mouse, 1 teclado y 1 webcam; a Neuquén, 1 mouse, 1 teclado y 1 auriculares; "
                             "7 en total", "cita": "el resto a Neuquén"}
    caro = {"preguntas": [{"n": 1, "cita": "No tomes lo mas barato toma lo mas caro", "accion": "buscar",
                           "rubro": "lo pedido", "orden": "mas caro", "entre_lo_mostrado": True}]}
    charla = {"id": "real_lo_pedido", "turnos": [{"texto": m0, "casillas": []},
                                                 {"texto": "No tomes lo mas barato toma lo mas caro", "casillas": []}]}
    from app.core import llm_reintento
    puerta = llm_reintento._cliente
    try:
        caro_ = R.correr(charla, [c["turnos"][0]["agenda"], caro], R.instalar(), {})[1]["respuesta"]
    finally:
        R.ELEGIR.pop(m0, None)
        llm_reintento._cliente = puerta
    for rubro in ("mouse", "teclado", "auriculares", "webcam"):
        assert f"el de gama más alta de {rubro}" in caro_, caro_
    assert "Envio a Rosario" in caro_ and "Envio a Neuquén" in caro_
