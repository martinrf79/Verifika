"""CADA PRODUCTO, DICHO CON SU NOMBRE, ES ESE PRODUCTO — el examen real del 31-oct, FICHA 83.

"El Procesador Intel Core i9-14900K" no se reconocia: el catalogo partia el modelo por espacios, "i9-14900k", y el mensaje
por letras y numeros, "i9" y "14900k". Sus palabras quedaban sueltas y el verificador las leia como atributos falsos del
Ryzen de la misma oracion; el modelo saco la lista correcta de lo no fabricado en China. Y las notebooks Ryzen traen
"core i5" en los tags: "IdeaPad 3 Core i5" salia ambiguo con la Ryzen 7.

Se mide la clase entera: cada uno de los productos del catalogo, dicho en una oracion con su nombre. Antes del 31-oct,
105 no se reconocian; ahora 2.
"""
import re

import pytest

from banco_pruebas import clon_produccion as C

PENDIENTES = {"Microfono Rode NT-USB+ Negro", "Microfono Rode NT-USB+ Blanco"}


@pytest.fixture(scope="module")
def no_reconocidos():
    C.instalar()
    from app.core.flujo import catalogo as K
    from app.core.flujo import marcador as MK
    mal, ps = [], K.productos(C.TIENDA)
    for p in ps:
        ws = [w for w in re.findall(r"[a-z0-9]+", K.n(f"el {p['nombre']} esta bueno")) if w not in K._RELLENO]
        if not any(K.identificar(t, "", C.TIENDA).get("producto", {}).get("modelo") == p.get("modelo")
                   for t, _ in MK._productos(ws, C.TIENDA)):
            mal.append(p["nombre"])
    print(f"\nIDENTIDAD POR NOMBRE: {len(ps)} productos, {len(mal)} no se reconocen")
    return mal


def test_cada_producto_se_reconoce_por_su_nombre(no_reconocidos):
    assert set(no_reconocidos) <= PENDIENTES, sorted(set(no_reconocidos) - PENDIENTES)[:10]


@pytest.mark.xfail(strict=True, reason="A MEDIAS: el '+' de 'NT-USB+' se pierde al normalizar y queda igual al NT-USB "
                                       "Mini; distinguirlos pide leer el signo como parte del modelo")
def test_el_rode_nt_usb_mas(no_reconocidos):
    assert not set(no_reconocidos) & PENDIENTES
