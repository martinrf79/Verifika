"""LO QUE EL VERIFICADOR NO CAZABA EN EL EXAMEN REAL — cuatro clases, 3-nov. Sin modelo.

  hecho          dice que armo el presupuesto o que pasa los datos de pago, y la respuesta no los trae: c3391d, b8bb00.
  existencia     "no tengo" o "solo tengo" un rubro con un atributo, contra el catalogo con stock: badf4f.
  compatibilidad una clase entera que anda con un equipo, "la mayoria de los mouses andan en la Play": bf4a05; y la
                 oracion sin producto que sigue a una que nombra uno, "Es compatible con PS5": b8bb00.
  medios         los medios que la tienda dice aceptar son todos los de su FAQ: 96b39f.
  de todos       una medida dicha de todos los productos es la de cada uno: "todos con 12 meses de garantia", e35851.
Las frases son las del bot, tal cual. Las que no deben marcarse cuidan las falsas alarmas.
"""
import pytest

from banco_pruebas import clon_produccion as C

MARCAN = {
    "hecho": ["Te armé el presupuesto para que lo veas. Si te sirve, avisame.",
              "Acá te paso el presupuesto actualizado y los datos para que puedas realizar el pago:",
              "Para avanzar, te paso los datos para que realices la transferencia:"],
    "existencia": ["Si buscás algo similar que sea inalámbrico, por ahora no tengo nada en stock, solo tengo teclados "
                   "con cable USB.", "No tenemos teclados inalámbricos."],
    "compatibilidad": ["La verdad es que la mayoría de los mouses USB funcionan en la Play, pero no tenemos uno que lo "
                       "diga.", "El más económico es el Redragon Zeus X a $57.500. Es compatible con PS5."],
    "regla": ["¡Hola! Además de transferencia bancaria, aceptamos Mercado Pago.",
              "Aceptamos transferencia, Mercado Pago y tarjeta Naranja.",
              "Te cuento: todos nuestros productos tienen garantía oficial de 12 meses."],
}
NO_MARCAN = ["¿Te gustaría que te arme un presupuesto por uno?", "Si me confirmás, así te armo el presupuesto.",
             "Pasame tu nombre y te paso los datos para la transferencia.", "No tenemos teclados Samsung.",
             "Te cuento que no tenemos teclados de la marca Samsung en nuestro catálogo.",
             "No tenemos teclados rosas.", "Para saber qué memoria le sirve a tu notebook, pasame el modelo.",
             "Sobre la tarjeta de débito, la aceptamos a través de Mercado Pago.",
             "Aceptamos transferencia bancaria, Mercado Pago y tarjetas Visa, Mastercard y American Express.",
             "El G305 es inalámbrico. Es muy preciso.", "Todos nuestros productos tienen garantía oficial."]


@pytest.fixture(scope="module")
def V():
    C.instalar()
    from app.core.flujo import verificador
    return verificador


@pytest.mark.parametrize("clase,frase", [(c, f) for c, fs in MARCAN.items() for f in fs])
def test_lo_que_el_examen_real_dejaba_pasar_se_marca(V, clase, frase):
    assert clase in [c for c, _ in V.verificar(frase, "redragon zeus x $57.500 mouse", C.TIENDA)], frase


@pytest.mark.parametrize("frase", NO_MARCAN)
def test_lo_cierto_o_lo_futuro_no_se_marca(V, frase):
    assert V.verificar(frase, "Mouse Logitech G305 Lightspeed Negro inalambrico", C.TIENDA) == [], frase


def test_con_el_presupuesto_o_los_datos_pegados_no_se_marca(V):
    texto = "Acá te paso el presupuesto:\nPresupuesto:\n- 1x Mouse: $1\nAcá te dejo los datos: Alias: demo.verifika"
    assert not [h for h in V.verificar(texto, "Alias: demo.verifika $1", C.TIENDA) if h[0] == "hecho"]
