"""EL PEDIDO POR COMANDOS — las charlas modelo de la FICHA 86 (2-nov-2026, con Martin).

El modelo ya no reescribe el pedido entero: manda solo el cambio, con las palabras del cliente en `cita`, y el codigo
lo valida y lo aplica sobre el borrador de la FICHA 71, que vive entre turnos. Cada charla llama a la herramienta
`pedido` con los comandos que el modelo deberia mandar, sin modelo, y controla el borrador y lo que lee el cliente.

  dijo    lo que escribio el cliente en la charla, normalizado, como lo arma `agente.responder`.
  visto   los nombres que se le mostraron, normalizados: el candado de productos.
"""
import pytest

from banco_pruebas import clon_produccion as C


M220 = "Mouse Logitech M220 Silent Negro"
HYPERX = "Auriculares HyperX Cloud Stinger 2 Negro"
G203, G305 = "Mouse Logitech G203", "Mouse Logitech G305"


@pytest.fixture(scope="module")
def A():
    C.instalar()
    from app.core.flujo import agente
    return agente


def _n(texto: str) -> str:
    from app.core.flujo import catalogo as K
    return K.n(texto)


VISTO = _n(" ".join([M220, HYPERX, "Mouse Logitech G203 Lightsync Negro", "Mouse Logitech G305 Lightspeed Negro"]))


def turno(A, memoria: dict, comandos: dict, dijo: str) -> tuple:
    """Un turno que sale bien: la herramienta, y despues lo que `responder` aplica al final si hay respuesta."""
    cliente, nota = A.pedido(comandos, memoria, C.TIENDA, VISTO, _n(dijo))
    memoria.update(memoria.pop("_ultimo", {}))
    return cliente, nota


def renglones(memoria: dict) -> list:
    """El borrador como lo lee la herramienta: el guardado, o el pedido viejo convertido."""
    from app.core.flujo import agente
    return [(r["L"], r["que"], r["cantidad"], r["destino"])
            for r in agente.estado_de(memoria)["borrador"].get("renglones") or []]


TRES = {"agrega": [
    {"producto": M220, "cantidad": 1, "destino": "Concordia", "cita": "el m220 a concordia"},
    {"producto": HYPERX, "cantidad": 2, "destino": "Posadas", "cita": "dos hyperx a posadas"},
    {"producto": G203, "cantidad": 1, "destino": "Posadas", "cita": "un g203 tambien a posadas"}]}
DIJO_TRES = "quiero el m220 a concordia, dos hyperx a posadas y un g203 tambien a posadas"


def test_charla_1_pedido_simple(A):
    m = A.memoria_de({})
    dijo = "quiero el mouse m220 negro, mandalo a concordia"
    cliente, nota = turno(A, m, {"agrega": [{"producto": M220, "cantidad": 1, "destino": "Concordia",
                                             "cita": "mouse m220 negro mandalo a concordia"}]}, dijo)
    assert renglones(m) == [("L-1", M220, 1, "Concordia")]
    assert "Envio a Concordia" in cliente and "Total" in cliente
    assert "L-1" in nota


def test_charla_2_el_destino_que_no_dijo_no_entra(A):
    m = A.memoria_de({})
    turno(A, m, {"agrega": [{"producto": M220, "cantidad": 1, "destino": "Concordia", "cita": "el m220 a concordia"}]},
          "el m220 a concordia")
    cliente, nota = turno(A, m, {"agrega": [{"producto": HYPERX, "cantidad": 1, "destino": "CABA",
                                             "cita": "sumame unos auriculares hyperx"}]},
                          "sumame unos auriculares hyperx")
    assert renglones(m)[1] == ("L-2", HYPERX, 1, "")
    assert "CABA" in nota
    assert "¿A dónde va" in cliente


def test_charla_3_el_medio_que_no_dijo_no_entra(A):
    m = A.memoria_de({})
    turno(A, m, {"agrega": [{"producto": M220, "cantidad": 1, "destino": "Concordia", "cita": "el m220 a concordia"}]},
          "el m220 a concordia")
    cliente, _ = turno(A, m, {"pago": "70 transferencia, 30 mercado pago"}, "pago setenta treinta")
    assert "¿Con qué medio pagás cada parte" in cliente
    assert "descuento =" not in cliente


def test_charla_4_solo_el_cambio(A):
    m = A.memoria_de({})
    turno(A, m, TRES, DIJO_TRES)
    antes = renglones(m)
    turno(A, m, {"cambia": [{"es": "L-1", "producto": G305, "cita": "el mouse cambialo por el g305"}]},
          "el mouse cambialo por el g305")
    despues = renglones(m)
    assert len(despues) == 3
    assert despues[0][0] == "L-1" and despues[0][1] == G305
    assert despues[1:] == antes[1:]


def test_charla_5_entre_dos_pregunta_y_no_elige(A):
    m = A.memoria_de({})
    cliente, _ = turno(A, m, {"agrega": [{"entre": [G203, G305], "cantidad": 1, "cita": "me llevo uno"}]},
                       "me llevo uno")
    assert "¿Cuál decís" in cliente
    assert renglones(m) == []


def test_charla_6_sacar_sin_perder_los_otros(A):
    m = A.memoria_de({})
    turno(A, m, TRES, DIJO_TRES)
    antes = renglones(m)
    turno(A, m, {"saca": ["L-2"]}, "saca los auriculares")
    assert renglones(m) == [antes[0], antes[2]]


def test_charla_7_la_cita_que_no_dijo_no_se_aplica(A):
    m = A.memoria_de({})
    _, nota = turno(A, m, {"agrega": [{"producto": M220, "cantidad": 3, "destino": "Concordia",
                                       "cita": "quiero tres mouse para la oficina"}]}, "hola, que tal")
    assert renglones(m) == []
    assert "no lo dijo el cliente" in nota
    # La cantidad que no es la de la cita tampoco: dijo dos.
    _, nota = turno(A, m, {"agrega": [{"producto": HYPERX, "cantidad": 3, "destino": "Posadas",
                                       "cita": "dos hyperx a posadas"}]}, "dos hyperx a posadas")
    assert renglones(m) == [("L-1", HYPERX, 2, "Posadas")]


def test_charla_8_la_charla_vieja_no_pierde_el_pedido(A):
    vieja = {"memoria_agente": {"pedido": [{"producto": M220, "cantidad": 1, "destino": "Concordia"},
                                           {"producto": HYPERX, "cantidad": 2, "destino": "Posadas"}]}}
    m = A.memoria_de(vieja)
    assert renglones(m) == [("L-1", M220, 1, "Concordia"), ("L-2", HYPERX, 2, "Posadas")]
    assert all(r["confirmado"] for r in A.estado_de(m)["borrador"]["renglones"])
    # Se convierte al leer y no se guarda: mientras el bot use el pedido viejo, no queda un estado viejo al lado.
    assert m["estado"] == {}
    # Cuando `pedido` escribe, el estado manda, y un pedido vaciado no resucita el viejo.
    turno(A, m, {"saca": ["L-1", "L-2"]}, "saca todo")
    assert m["estado"] and renglones(m) == []


def test_charla_9_el_turno_que_falla_no_guarda(A):
    m = A.memoria_de({})
    turno(A, m, {"agrega": [{"producto": M220, "cantidad": 1, "destino": "Concordia", "cita": "el m220 a concordia"}]},
          "el m220 a concordia")
    antes = renglones(m)
    # La herramienta corre, pero el turno no llega a responder: `_ultimo` nunca se aplica.
    A.pedido({"saca": ["L-1"]}, m, C.TIENDA, VISTO, _n("saca el mouse"))
    m.pop("_ultimo", None)
    assert renglones(m) == antes


def test_dos_llamadas_en_el_mismo_turno_se_suman(A):
    """La segunda llamada a `pedido` del turno parte de lo que dejo la primera, no de la memoria guardada."""
    m = A.memoria_de({})
    A.pedido({"agrega": [{"producto": M220, "cantidad": 1, "destino": "Concordia", "cita": "el m220 a concordia"}]},
             m, C.TIENDA, VISTO, _n("el m220 a concordia y dos hyperx a posadas"))
    A.pedido({"agrega": [{"producto": HYPERX, "cantidad": 2, "destino": "Posadas", "cita": "dos hyperx a posadas"}]},
             m, C.TIENDA, VISTO, _n("el m220 a concordia y dos hyperx a posadas"))
    m.update(m.pop("_ultimo"))
    assert [x[1] for x in renglones(m)] == [M220, HYPERX]


def test_el_pedido_lo_pega_el_codigo(A):
    """K21: el modelo no escribio el presupuesto porque creyo que no cambio nada. Si hubo `pedido`, va igual. Desde el
    7-nov la respuesta la arma el codigo con la herramienta responder, FICHA 90: ya no hay marca [[PEDIDO]] que poner."""
    pasos = [{"herramienta": "pedido", "pide": {}, "devuelve": "", "al_cliente": "Presupuesto: 1x Mouse"}]
    m = A.memoria_de({})
    texto, _ = A.armar({"saludo": "Listo, te lo sumo.", "bloques": [], "pregunta": "¿Te sirve?"}, A.Citas(), pasos, m, C.TIENDA)
    assert texto == "Listo, te lo sumo.\n\nPresupuesto: 1x Mouse\n\n¿Te sirve?"
    assert A.armar({"saludo": "Listo.", "bloques": [], "pregunta": ""}, A.Citas(), [], m, C.TIENDA)[0] == "Listo."


# ══ PROCEDENCIA SOLA: el paso 3, sin el ejecutor ══

def test_procedencia_rechaza_destino_medio_y_cita(A):
    dijo = _n("el m220 a concordia, pago setenta treinta")
    a, fuera = A.procedencia({"agrega": [{"producto": M220, "destino": "CABA", "cita": "el m220"},
                                         {"producto": HYPERX, "cita": "quiero auriculares para regalar"}],
                              "pago": "70 transferencia, 30 mercado pago"}, {}, dijo)
    assert a["agrega"] == [{"producto": M220, "cita": "el m220"}]
    assert [x for x in a["reparto"] if x["medio"]] == []
    assert any("CABA" in x for x in fuera) and any("regalar" in x for x in fuera)


def test_procedencia_deja_lo_dicho(A):
    dijo = _n("el m220 a concordia, 70 por transferencia y 30 con mercado pago")
    a, fuera = A.procedencia({"agrega": [{"producto": M220, "destino": "Concordia", "cita": "el m220 a concordia"}],
                              "pago": "70 transferencia, 30 mercado pago"}, {}, dijo)
    assert fuera == []
    assert a["agrega"][0]["destino"] == "Concordia"
    assert [x["medio"] for x in a["reparto"]] == ["transferencia", "mercado pago"]
