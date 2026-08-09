"""
AREA: EL INDICE DEL TURNO, el nexo entre lo interpretado y lo respondido.

Nace del pedido de Martin del 9-ago, que venia repitiendo hace sesiones: cada
punto que se interpreta de la pregunta tiene que tener su id, y la respuesta
tiene que contestar a ESE punto. La interpretacion entiende 100 y la respuesta
se cae igual, porque entre las dos no habia nadie mirando.

Los casos son el mensaje REAL que le llego a Martin por WhatsApp el 9-ago y su
version completa, para que el test mida las dos direcciones: que marque lo que
falta, y que NO marque cuando esta todo dicho. Un indice que marca en falso es
peor que no tener indice.
"""
from app.core import indice_turno as IT

DECLARADO = {
    "items": [{"que": "auriculares", "cantidad": 2},
              {"que": "mouse", "cantidad": 2},
              {"que": "memorias ram", "cantidad": 2}],
    "restricciones": ["menor cantidad de partes chinas posible"],
    "destinos": ["Cordoba capital", "Concordia", "Posadas"],
    "contradicciones": ["Mencionaste un teclado en el envío que no estaba en "
                        "el pedido inicial."],
    "reparto_pago": [{"porcentaje": 70}, {"porcentaje": 30}],
    "pide_precio": True,
}

_INCOMPLETO = """Te comento que los componentes son de origen chino.
Presupuesto:
- 2x Auriculares Redragon: $115.000
- 2x Mouse Genius: $17.000
- 2x Memoria ram Kingston: $69.000
Total: $225.000
Pago dividido:
- transferencia (70%) - mercado pago (30%)
Reparto de los envios:
- A Córdoba capital: 1x Auriculares"""

_COMPLETO = _INCOMPLETO + """
- A Concordia: 1x Mouse
- A Posadas: 2x Memoria ram
El teclado que mencionaste no estaba en el pedido, ¿lo agrego?"""


def test_cada_punto_interpretado_tiene_su_id():
    """El pedido de Martin, textual: cada parte de la pregunta interpretada
    tiene que tener un valor con el que la respuesta se pueda atar."""
    ps = IT.puntos(DECLARADO)
    ids = [p["id"] for p in ps]
    assert ids == ["item:1", "item:2", "item:3", "condicion:1", "destino:1",
                   "destino:2", "destino:3", "duda:1", "pago:1", "precio:1"]


def test_marca_lo_que_el_mensaje_REAL_no_contesto():
    """EL MENSAJE QUE LE LLEGO A MARTIN. Cotiza los tres rubros y el pago, pero
    nombra UN destino de tres y no pregunta por el teclado. Esos tres puntos, y
    solo esos, tienen que salir marcados."""
    r = IT.cobertura(DECLARADO, _INCOMPLETO, "t")
    assert [p["id"] for p in r["faltan"]] == ["destino:2", "destino:3", "duda:1"]


def test_no_marca_nada_cuando_esta_todo_dicho():
    """LA CONTRACARA, y es la que hace usable al indice. Si marca de mas, manda
    a agregar algo que ya esta y el mensaje crece por nada: seria peor que no
    tenerlo. Ojo con la condicion: el cliente dijo "partes CHINAS" y el mensaje
    dice "origen CHINO". Es el mismo punto y no puede figurar sin atender."""
    r = IT.cobertura(DECLARADO, _COMPLETO, "t")
    assert r["faltan"] == [], [p["id"] for p in r["faltan"]]


def test_la_duda_se_atiende_PREGUNTANDO_no_nombrando():
    """Una contradiccion no se cierra nombrandola al pasar: se pregunta. Es la
    regla cero -ante lo ambiguo se pregunta- llevada al indice."""
    nombrada = _INCOMPLETO + "\nEl teclado no estaba en el pedido inicial."
    r = IT.cobertura(DECLARADO, nombrada, "t")
    assert "duda:1" in [p["id"] for p in r["faltan"]]
    con_pregunta = nombrada + " ¿Lo sumo?"
    r2 = IT.cobertura(DECLARADO, con_pregunta, "t")
    assert "duda:1" not in [p["id"] for p in r2["faltan"]]


def test_la_instruccion_nombra_el_punto_concreto():
    """Ya esta medido dos veces en este repo que una correccion generica no
    mueve al modelo: ante "te falto algo" pidio cero herramientas 3 de 3. El
    punto con su texto es una cosa sola y verificable."""
    r = IT.cobertura(DECLARADO, _INCOMPLETO, "t")
    ins = IT.instruccion(r["faltan"])
    assert "Concordia" in ins and "Posadas" in ins and "teclado" in ins
    assert IT.instruccion([]) == ""


def test_sin_pedido_declarado_el_indice_se_calla():
    """Un saludo o un gracias no tiene puntos: no hay nada que atar y no se
    inventa una obligacion."""
    r = IT.cobertura({}, "Hola, ¿en qué te ayudo?", "t")
    assert r["puntos"] == [] and r["faltan"] == []
