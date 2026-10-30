"""LA COMPATIBILIDAD QUE AFIRMA LA RESPUESTA, CONTRA LA FICHA, Y LO QUE SIGUE MARCADO NO SALE (30-oct-2026, FICHA 83).

Visto en K10: "los HyperX Cloud Stinger 2 son los que van directo al joystick" de la PS5 salio sin que el buscador
mostrara compatibilidad. Era cierto por casualidad: el modelo lo dijo de memoria, y el verificador no miraba ese eje.
Desde hoy, toda oracion que nombra un producto y dice que anda, sirve o es compatible con un equipo se compara con la
ficha de compatibilidad: afirmar lo que la ficha no dice es un hallazgo, y negar lo que dice, tambien. Dudar no.
El banco que lo mide sobre las respuestas grabadas es `banco_pruebas/alucinaciones.py`.
"""
import pytest

from banco_pruebas import clon_produccion as C

FUENTE = "Mouse Logitech M170 Negro HyperX Cloud Stinger 2 Teclado Logitech K120 Negro"

# (oracion, marca): lo que la ficha dice del M170, del Stinger 2 y del K120.
CASOS = [
    ("El M170 anda con la Mac.", False),
    ("El M170 anda con la PS5.", True),
    ("Los HyperX Cloud Stinger 2 son compatibles con la PS5.", False),
    ("Los HyperX Cloud Stinger 2 no son compatibles con la PS5.", True),
    ("El M170 no anda con la PS5.", False),
    ("No te puedo confirmar si el M170 funciona con la Xbox.", False),
    ("El K120 sirve para la notebook.", False),
    ("El K120 anda con el iPhone.", True),
    ("Sobre la compatibilidad con PS5, los HyperX Cloud Stinger 2 son los que van directo al joystick.", False),
    ("¿El M170 te sirve para la Mac?", False),
]


@pytest.fixture(scope="module")
def V():
    C.instalar()
    from app.core.flujo import verificador
    return verificador


def test_cada_afirmacion_de_compatibilidad_contra_la_ficha(V):
    from app.core.flujo import catalogo as K
    malas = [(t, m) for t, m in CASOS
             if any(h[0] == "compatibilidad" for h in V.verificar(t, K.n(FUENTE + " " + t), C.TIENDA)) != m]
    print(f"\nCOMPATIBILIDAD: {len(CASOS) - len(malas)} de {len(CASOS)} oraciones juzgadas como la ficha")
    assert not malas


def test_una_negacion_no_es_un_atributo(V):
    """C46 con la gratis, 30-oct: "sin teclado numerico" marcaba "sin" como atributo, y el bloqueo sacaba un teclado
    que estaba bien ofrecido."""
    from app.core.flujo import catalogo as K
    t = "El HyperX Alloy Origins Core es TKL, sin teclado numérico, y viene en negro."
    assert V.verificar(t, K.n("Teclado HyperX Alloy Origins Core Negro " + t), C.TIENDA) == []


def test_lo_marcado_sale_y_lo_pegado_queda(V):
    from app.core.flujo import catalogo as K
    pegado = "Presupuesto:\n- 1x Mouse Logitech M170 Negro: $12.000 c/u = $12.000\nTotal: $12.000"
    texto = f"Te paso el presupuesto.\n{pegado}\nEl M170 anda con la PS5. Decime si lo reservo."
    limpio = V.sin_marcadas(texto, K.n(FUENTE + " " + pegado), C.TIENDA, [pegado])
    assert pegado in limpio and "Decime si lo reservo." in limpio and "PS5" not in limpio
