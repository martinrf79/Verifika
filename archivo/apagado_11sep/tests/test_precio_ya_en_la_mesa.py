"""EL PRECIO QUE EL TURNO YA TIENE — la fila `pide_precio` que se abre de gusto.

Medido en produccion el 11-sep-2026, charla 5493547504287, turno `1fe1d20c`, y
reproducido con la sonda despues de arreglar la busqueda sin rubro:

    consultar_productos   proyeccion=catalogo operacion=mas_caro -> ok
                          campo=precio_ars  valor=3100500.0
                          producto={id: NOT0160, precio_ars: 3100500, ...}
    turno_incompleto      abiertos=['pide_precio:1']  pregunto=True

El precio estaba EN LA MESA, traido de la fuente y certificado, y el turno
igual termino con "para pasarte el precio me falta cerrar cual y cuantos".

QUE ESTA MAL. `tabla.py:580` daba la fila `pide_precio` por cubierta SOLO si el
turno armo una cuenta, o sea un presupuesto con total. Un presupuesto necesita
un producto elegido y una cantidad; pero "dame el precio del mas caro" no pide
un presupuesto, pide UN PRECIO, y ese precio ya estaba.

LO QUE NO SE TOCA, y por eso hay un test por cada cosa:
  - `reparto_pago` sigue necesitando la cuenta: dividir un pago sin total no se
    puede, y ahi la pregunta es la respuesta honesta.
  - Cuando hay cuenta, la fila sigue saliendo `sellado` y el bloque de plata lo
    escribe el codigo, no el modelo.
  - Sin precio en la mesa, la fila sigue quedando `sin_material` y el turno
    pregunta. La compuerta de completitud no se afloja.
"""

import pytest


@pytest.fixture(scope="module")
def fuente():
    from banco_pruebas import sim_firestore
    sim_firestore.install()
    return "verifika_prod"


def _mesa(declarado, llamadas, bloque=""):
    from app.core import tabla
    return tabla.tabla(declarado, llamadas, bloque)


def _fila(mesa, fid):
    for f in mesa.get("puntos") or []:
        if f.get("id") == fid:
            return f
    return None


def _agregado_mas_caro(fuente):
    """La llamada REAL que hace el turno de produccion, contra la fuente viva."""
    from app.core.herramientas import consultar_productos
    from app.core.molde import ConsultarProductos
    res = consultar_productos(
        ConsultarProductos(proyeccion="catalogo", operacion="mas_caro"), fuente)
    assert res.get("estado") == "ok" and res.get("valor"), res
    return {"herramienta": "consultar_productos",
            "pedido": {"proyeccion": "catalogo", "operacion": "mas_caro"},
            "resultado": res}


def test_el_precio_en_la_mesa_cierra_la_fila(fuente):
    declarado = {"items": [], "restricciones": ["el articulo mas caro que tengas"],
                 "pide_precio": True}
    mesa = _mesa(declarado, [_agregado_mas_caro(fuente)])
    fila = _fila(mesa, "pide_precio:1")
    assert fila, f"no se abrio la fila: {[f.get('id') for f in mesa['puntos']]}"
    assert fila["estado"] != "sin_material", (
        "el turno trajo el precio de la fuente y la fila quedo abierta igual")
    assert fila["material"], "la fila quedo sin el precio que el turno ya tenia"


def test_sin_precio_en_la_mesa_la_fila_sigue_abierta(fuente):
    """LA COMPUERTA NO SE AFLOJA. Sin nada que respalde un precio, preguntar es
    la respuesta honesta y tiene que seguir pasando."""
    declarado = {"items": [], "pide_precio": True}
    mesa = _mesa(declarado, [])
    fila = _fila(mesa, "pide_precio:1")
    assert fila and fila["estado"] == "sin_material", (
        f"quedo {fila and fila['estado']}: sin material no se puede dar precio")


def test_el_reparto_del_pago_sigue_necesitando_la_cuenta(fuente):
    """Dividir un pago sin total no se puede, tenga o no precios la mesa."""
    declarado = {"items": [], "restricciones": ["el articulo mas caro que tengas"],
                 "reparto_pago": [{"porcentaje": 50}, {"porcentaje": 50}]}
    mesa = _mesa(declarado, [_agregado_mas_caro(fuente)])
    fila = _fila(mesa, "reparto_pago:1")
    assert fila and fila["estado"] == "sin_material", (
        f"quedo {fila and fila['estado']}: sin cuenta no hay reparto")


def test_con_cuenta_la_fila_sigue_sellada(fuente):
    """Con presupuesto armado, la plata la escribe el codigo y la fila va
    `sellado`: el modelo no tiene casilla donde retipear un numero."""
    declarado = {"items": [], "pide_precio": True}
    mesa = _mesa(declarado, [], bloque="Presupuesto:\nTotal: $3.100.500")
    fila = _fila(mesa, "pide_precio:1")
    assert fila and fila["estado"] == "sellado", f"quedo {fila and fila['estado']}"


def test_el_precio_LLEGA_AL_MENSAJE_aunque_el_modelo_lo_saltee(fuente):
    """LO QUE EL CLIENTE LEE, que es lo unico que cuenta.

    Con la fila en `con_material` el modelo la salteaba —medido con la sonda:
    `salteados=['pide_precio:1']`— y el cliente volvia a quedarse sin precio.
    Por eso la linea la escribe el CODIGO, como la cuenta. Este test manda una
    respuesta del modelo que NO dice nada del precio, y el precio tiene que
    salir igual.
    """
    from app.core import tabla
    declarado = {"items": [], "restricciones": ["el articulo mas caro que tengas"],
                 "pide_precio": True}
    mesa = _mesa(declarado, [_agregado_mas_caro(fuente)])
    respuesta = {"apertura": "Mira lo que tengo.",
                 "puntos": [{"id": "restricciones:1",
                             "texto": "Es la Notebook Asus ROG Strix G16."}],
                 "pregunta_final": "Te sirve?"}
    mensaje = tabla.armar(respuesta, mesa)
    if isinstance(mensaje, tuple):
        mensaje = mensaje[0]
    tope = _extremo_precio(fuente)
    assert "3.100.500" in mensaje or f"{tope:,}".replace(",", ".") in mensaje, (
        f"el precio no llego al mensaje:\n{mensaje}")


def _extremo_precio(tienda):
    from app.storage.firestore_client import get_all_products
    return max(p["precio_ars"] for p in (get_all_products(tienda_id=tienda) or [])
               if isinstance(p.get("precio_ars"), (int, float))
               and (p.get("stock") or 0) > 0)
