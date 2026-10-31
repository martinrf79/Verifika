"""LAS REGLAS DE LA TIENDA SIEMPRE A LA VISTA, Y CONTROLADAS — el examen real del 31-oct, orden de Martin, FICHA 83.

Las reglas llegaban solo si el modelo las buscaba. En el examen dijo "no contamos con descuentos por cantidad", con
mayoristas y 10% por transferencia en la FAQ, y "no contamos con informacion del origen", que la ficha tiene.
  la hoja        una linea por tema de la FAQ, armada por codigo en cada turno: si la FAQ cambia, cambia.
  el verificador una oracion que niega o restringe un tema de la FAQ cuya regla no niega ni restringe nada.
"""
import pytest

from banco_pruebas import clon_produccion as C

# Del examen real, tal cual las dijo el bot: deben marcarse.
NIEGAN = ["Nuestros precios son finales y ya incluyen IVA; no contamos con descuentos adicionales por cantidad.",
          "Los precios que manejo son los que ves y no tengo margen para hacer descuentos por cantidad.",
          "Te cuento que no hacemos factura A."]
# Lo que no niega una regla, o la niega como la FAQ: no deben marcarse.
NO_NIEGAN = ["Qué lindo Posadas, hacemos envíos para allá sin problemas.",
             "Como todavía no me pasaste la localidad, solo me falta saber a dónde va el envío.",
             "No tenemos local físico: somos solo online.",
             "No vendemos usados ni reacondicionados.",
             "Te cuento que no tenemos ninguna promo de 50% off vigente.",
             "Tenemos 10 por ciento de descuento pagando por transferencia."]


@pytest.fixture(scope="module")
def tienda():
    C.instalar()
    from app.core.flujo import agente, verificador
    return agente, verificador


def test_la_hoja_trae_cada_tema_de_la_faq_una_vez(tienda):
    from app.storage.firestore_client import get_all_faq
    agente, _ = tienda
    hoja = agente.hoja_reglas(C.TIENDA)
    faq = get_all_faq(tienda_id=C.TIENDA)
    lineas = [x for x in hoja.split("\n") if x.startswith("- ")]
    print(f"\nLA HOJA: {len(lineas)} lineas, {len(hoja.split())} palabras")
    assert len(lineas) == len([d for d in faq.values() if d.get("respuesta")])
    assert "mayoristas: Para compras mayoristas" in hoja and "10 por ciento de descuento" in hoja


def test_una_regla_negada_se_marca_y_la_que_no_niega_no(tienda):
    agente, V = tienda
    fuente = agente.hoja_reglas(C.TIENDA)
    marcadas = [o for o in NIEGAN if any(c == "regla" for c, _ in V.verificar(o, fuente, C.TIENDA))]
    falsas = [o for o in NO_NIEGAN if any(c == "regla" for c, _ in V.verificar(o, fuente, C.TIENDA))]
    print(f"\nREGLAS: {len(marcadas)} de {len(NIEGAN)} negadas marcadas, {len(falsas)} de {len(NO_NIEGAN)} falsas alarmas")
    assert len(marcadas) == len(NIEGAN) and not falsas, (marcadas, falsas)
