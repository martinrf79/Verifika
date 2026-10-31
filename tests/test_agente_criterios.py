"""CADA CRITERIO DEL CLIENTE LLEGA A UNA BUSQUEDA — el examen real del 31-oct, FICHA 83.

En once charlas, "necesito que lleven las menos partes chinas posibles" se busco como "auriculares", "mouse" y "memoria
ram": el buscador nunca recibio el origen y el bot dijo que no tenia el dato. `agente.sin_buscar` da cada palabra del
mensaje que el catalogo ata a un campo cuando nada de lo que pidio el modelo ata ese campo; vuelve al modelo una vez,
con la revision del verificador. Se compara por campo, no por letras: "chinos" en la busqueda cubre "chinas".
"""
import pytest

from banco_pruebas import clon_produccion as C

CHINAS = ("Dame precio de dos auriculares, dos mouse y dos memorias. El precio no sería tan importante. Lo que sí que "
          "necesito que lleven las menos partes chinas posibles.")
# (mensaje, lo que busco el modelo, lo que falta)
CASOS = [
    (CHINAS, ["auriculares", "mouse", "memoria ram"], ["chinas"]),
    (CHINAS, ["auriculares que no sean chinos", "mouse", "memoria ram"], []),
    (CHINAS, ["auriculares no fabricados en china", "mouse no fabricado en china", "memoria ram"], []),
    ("Tienes algun articulo que no sea fabricado en china", ["origen de los productos"], ["china"]),
    ("Tienes algun articulo que no sea fabricado en china", ["productos no fabricados en china"], []),
    ("quiero auriculares inalambricos baratos", ["auriculares baratos"], ["inalambricos"]),
    ("quiero auriculares inalambricos baratos", ["auriculares inalambricos"], []),
    ("cuanto sale el G305?", ["G305"], []),
    ("tenes teclados con rgb?", ["teclados"], ["rgb"]),
    ("tenes teclados con rgb?", ["teclado retroiluminado"], []),
]


@pytest.fixture(scope="module")
def A():
    C.instalar()
    from app.core.flujo import agente
    return agente


def test_los_criterios_sin_buscar(A):
    malos = []
    for mensaje, busco, falta in CASOS:
        dio = A.sin_buscar(mensaje, [{"pide": {"consulta": q}} for q in busco], C.TIENDA)
        if dio != falta:
            malos.append((mensaje[:40], busco, dio, falta))
    print(f"\nCRITERIOS SIN BUSCAR: {len(CASOS) - len(malos)} de {len(CASOS)} casos")
    assert not malos, malos
