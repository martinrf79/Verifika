"""
Regresion del certificador de identidad, la Regla Cero del proyecto.

  E6   Falta el certificador determinista. La identidad (existe / es ambiguo / no
       existe) la debe decidir UNA sola funcion de codigo con tres veredictos de
       primera clase: exists, ambiguous, not_found. Hoy el modulo no existe.
  E15  search_products reemplaza un producto inexistente por alternativas sin
       decir 'no lo tengo'. Con el certificador, not_found es un resultado valido
       y explicito, y la respuesta al cliente debe reconocerlo antes de pivotear.

El arreglo esperado es app/core/certificador.py con una funcion certificar que,
dado el texto del cliente y el catalogo, devuelva uno de los tres veredictos.
Estos tests definen el contrato y HOY fallan porque el modulo no existe.
"""


def test_e6_modulo_certificador_existe():
    from app.core import certificador  # ImportError hoy
    assert hasattr(certificador, "certificar")


def test_e6_tres_veredictos_de_primera_clase():
    from app.core import certificador
    veredictos = set(getattr(certificador, "VEREDICTOS", set()))
    assert {"exists", "ambiguous", "not_found"} <= veredictos, (
        "El certificador debe declarar los tres veredictos de la Regla Cero.")


def test_e15_producto_inexistente_da_not_found():
    """E15: pedir algo que no esta en el catalogo devuelve not_found, un
    resultado valido y explicito, no un silencioso pivoteo a alternativas."""
    from app.core import certificador
    catalogo = [
        {"id": "p1", "nombre": "Mouse Gamer Redragon", "categoria": "mouse"},
        {"id": "p2", "nombre": "Teclado Mecanico HyperX", "categoria": "teclados"},
    ]
    r = certificador.certificar("una notebook gamer", catalogo)
    assert r.get("veredicto") == "not_found", (
        "Un producto que no existe debe certificarse not_found, no reemplazarse "
        "en silencio por alternativas.")
