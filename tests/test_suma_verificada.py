"""LA SUMA QUE EL CODIGO PUEDE COMPROBAR NO ES INVENTO — medido en la tanda
de charlas del 22-sep-2026: "precio del K120 y del G203" salio como "no tengo
esa informacion" 2 de 3, porque el modelo agrego "$52.000 los dos" y la
guarda no encontraba 52.000 en ninguna fuente. La suma estaba bien."""
from app.core import numeros as N

K120 = {"id": "TEC0029", "nombre": "Teclado Logitech K120 Negro",
        "precio_ars": 14500, "precio": "$14.500"}
G203 = {"id": "MOU0001", "nombre": "Mouse Logitech G203 Lightsync Negro",
        "precio_ars": 37500, "precio": "$37.500"}


def test_la_suma_de_dos_precios_de_la_ficha_sale():
    texto = "El K120 sale $14.500 y el G203 $37.500: los dos, $52.000."
    salida, informe = N.llenar(texto, [K120, G203], "t")
    assert not informe["inventada"], informe
    assert "$52.000" in salida


def test_cantidad_por_precio_mas_envio_sale():
    texto = "Dos G203 con envio a Rosario: $82.000."
    _s, informe = N.llenar(texto, [G203], "t", envios={"Rosario": 7000})
    assert not informe["inventada"], informe


def test_una_suma_MAL_hecha_sigue_cayendo():
    """La plata tiene que estar bien: 14.500 + 37.500 no es 53.000."""
    _s, informe = N.llenar("Los dos te salen $53.000.", [K120, G203], "t")
    assert informe["inventada"], "una suma equivocada paso como verificada"


def test_una_cifra_sin_fuente_sigue_cayendo():
    _s, informe = N.llenar("Sale $99.999.", [K120], "t")
    assert informe["inventada"]
