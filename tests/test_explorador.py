"""
AREA: EL EXPLORADOR (`banco_pruebas/explorador.py`).

QUE SE PRUEBA, y es lo unico que se puede probar sin gastar cuota: que las
charlas se ARMAN bien y que el juez las juzga. La corrida contra el modelo vive
afuera del CI a proposito -necesita clave y minutos-; lo que el CI tiene que
garantizar es que el instrumento no se pudra en silencio.

LA MITAD IMPORTANTE es `test_el_explorador_encuentra_un_defecto_plantado`: un
instrumento de deteccion que nunca detecto nada no se distingue de uno roto. Se
le planta una charla con un error de plata conocido y tiene que verlo.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import random  # noqa: E402

from banco_pruebas.explorador import (  # noqa: E402
    CONDUCTAS, GUIONES, armar_charla, juzgar)

_CATALOGO = [
    {"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro", "categoria": "mouse"},
    {"id": "TEC0007", "nombre": "Teclado Logitech K120", "categoria": "teclados"},
    {"id": "AUR0011", "nombre": "Auricular HyperX Cloud II", "categoria": "auriculares"},
    {"id": "NOT0002", "nombre": "Notebook Lenovo V15 G4", "categoria": "notebooks"},
]


def test_cada_guion_arma_una_charla_completa():
    """Un guion es una secuencia de CONDUCTAS, no de preguntas. Si una conducta
    se renombra y un guion queda apuntando al vacio, la charla sale corta y el
    numero de la corrida miente sin avisar."""
    rnd = random.Random(3)
    for nombre, pasos in GUIONES.items():
        assert all(p in CONDUCTAS for p in pasos), f"{nombre} pide una conducta que no existe"
        charla = armar_charla(rnd, _CATALOGO, nombre)
        assert len(charla["turnos"]) == len(pasos)
        assert all(t.strip() for t in charla["turnos"]), f"{nombre} genero un turno vacio"


def test_la_charla_usa_productos_reales_del_catalogo():
    """El escenario se sortea del catalogo vivo. Si el explorador inventara los
    productos, estaria probando contra algo que la tienda no vende y sus
    hallazgos no valdrian nada."""
    charla = armar_charla(random.Random(1), _CATALOGO, "confirmacion_multiturno")
    nombres = {p["nombre"] for p in charla["escenario"]["productos"]}
    assert nombres <= {c["nombre"] for c in _CATALOGO}
    assert charla["escenario"]["destino_a"] != charla["escenario"]["destino_b"]


def test_la_charla_de_confirmacion_repite_la_confirmacion():
    """Este guion existe por un motivo concreto: es la charla REAL del 10-ago
    -el cliente confirma dos veces sin cambiar nada- y era el escenario que
    NINGUNA de las 13 charlas grabadas tenia. Si se pierde, vuelve el hueco."""
    pasos = GUIONES["confirmacion_multiturno"]
    assert pasos.count("confirmar") + pasos.count("confirmar_otra_vez") >= 2


def test_el_explorador_encuentra_un_defecto_plantado():
    """UN DETECTOR QUE NUNCA DETECTA NADA NO SE DISTINGUE DE UNO ROTO. Se le
    planta el error de plata del 10-ago -cobrar el total entero por una via
    cuando el pago va dividido- y tiene que verlo, sin que nadie le diga cual
    era la respuesta correcta."""
    charla = armar_charla(random.Random(5), _CATALOGO, "confirmacion_multiturno")
    corrida = {**charla, "respuestas": [
        "Hola, te paso el detalle.",
        "Presupuesto:\n- 1x Mouse Genius DX-110 Negro: $8.500 c/u = $8.500\n"
        "Subtotal: $8.500\nTotal final: $8.500",
        "Lo dividimos asi:\n- transferencia (65%): $5.525\n"
        "- mercado pago (35%): $2.975\nTotal final: $8.500\n"
        "Datos para transferir:\nMonto: $8.500",
    ], "ms": [10, 10, 10]}
    fallas = juzgar(corrida, {c["nombre"] for c in _CATALOGO})
    reglas = {f["regla"] for f in fallas}
    assert "cobra_distinto_de_lo_que_factura" in reglas, fallas
    # y deja dicho EN QUE turno y con que dijo el cliente, que es lo que
    # convierte un numero en un diagnostico
    culpable = next(f for f in fallas if f["regla"] == "cobra_distinto_de_lo_que_factura")
    assert culpable["turno"] == 3
    assert culpable["dijo"] and culpable["paso"]


def test_la_charla_limpia_no_grita():
    """La otra mitad: un invariante que grita de mas es peor que uno que no
    existe, porque entrena a ignorarlo."""
    charla = armar_charla(random.Random(2), _CATALOGO, "regateo")
    corrida = {**charla, "respuestas": [
        "Tengo el Mouse Genius DX-110 Negro a $8.500. ¿Te lo reservo?",
        "El envio a Cordoba tarda entre 4 y 7 dias habiles desde el pago.",
    ], "ms": [10, 10]}
    assert juzgar(corrida, {c["nombre"] for c in _CATALOGO}) == []
