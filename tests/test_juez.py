"""
AREA: Juez de invariantes del banco de pruebas (banco_pruebas/juez.py).

El juez audita cada respuesta de una charla simulada con los MISMOS detectores
del camino vivo, contra el catalogo real del doble. Estos tests lockean que
detecta las clases de error vistas en el banco y que no acusa en falso a una
respuesta sana.
"""
from banco_pruebas.juez import juzgar


def test_respuesta_sana_pasa_limpia(firestore_doble):
    r = ("El Mouse Genius DX-110 Negro sale $8.500 y hay 11 en stock. "
         "Te lo mando a domicilio; pasame tu codigo postal y te cotizo.")
    assert juzgar(r) == []


def test_stock_inventado_se_marca(firestore_doble):
    """El caso del banco: ofrecer la variante agotada como disponible."""
    r = "Tenemos el Mouse Genius DX-110 Blanco - $8.500 (11 en stock)."
    problemas = juzgar(r)
    assert any("stock" in p for p in problemas)


def test_marcador_sin_estampar_se_marca(firestore_doble):
    assert any("marcador" in p
               for p in juzgar("Te recomiendo [[PROD:MOU0023]], va joya."))


def test_narracion_interna_se_marca(firestore_doble):
    r = "Ahí me pide más precisión para Córdoba. Decime el código postal."
    assert any("narracion" in p for p in juzgar(r))


def test_precio_de_lista_pisado_se_marca(firestore_doble):
    """Producto nombrado con un precio que no es el del catalogo."""
    r = "El Mouse Genius DX-110 Negro sale $9.900, aprovechalo."
    assert any("precio" in p for p in juzgar(r))


def test_total_de_cuenta_no_es_falso_positivo(firestore_doble):
    """Un total declarado como cuenta no se compara contra el precio de lista
    del producto nombrado (eso lo verifica el pipeline con el proof)."""
    r = ("2x Mouse Genius DX-110 Negro a $8.500 c/u. "
         "Con envio a Cordoba $7.500, Total: $24.500.")
    assert juzgar(r) == []


def test_tarifa_de_envio_junto_al_producto_no_es_falso_positivo(firestore_doble):
    """La cifra del envio puede aparecer pegada al nombre del producto sin la
    palabra envio cerca ('Mouse ... a Cordoba: $7.500'): si coincide con una
    tarifa conocida de la tienda, no se acusa como precio de lista pisado.
    Visto en la primera corrida viva del guion multi-destino."""
    r = "- Mouse Genius DX-110 Negro a Cordoba: $7.500"
    assert juzgar(r) == []


def test_precio_de_otro_producto_despues_del_anclado_no_acusa(firestore_doble):
    """Si entre el nombre anclado y la cifra ya hay otro monto, esa cifra es de
    otra cosa (el nombre del segundo producto puede venir incompleto y no
    anclar). Visto en la tanda viva: los $57.500 de los Zeus X acusados al
    DX-110 Negro."""
    r = ("Te anoto el Mouse Genius DX-110 Negro a $8.500. "
         "Y los auriculares Zeus X salen $57.500, decime si los sumo.")
    assert juzgar(r) == []


def test_doble_pregunta_de_cierre_acusa(firestore_doble):
    """Dos preguntas de confirmacion en la misma respuesta = doble cierre
    robotico. Reproducido en la corrida demo del 19-jul (el solver cerro con
    '¿Lo dejamos confirmado asi?' y el gatillo pego la enlatada encima)."""
    r = ("Total: $28.000\n\n¿Lo dejamos confirmado así?\n\n"
         "¿Seguimos adelante con tu pedido así te lo dejo preparado?")
    assert any("doble pregunta de cierre" in p for p in juzgar(r))


def test_una_pregunta_de_cierre_mas_una_de_dato_no_acusa(firestore_doble):
    """Una confirmacion + una pregunta de dato no es doble cierre."""
    r = ("Total: $28.000. ¿A qué localidad te lo mando? "
         "¿Seguimos adelante con tu pedido así te lo dejo preparado?")
    assert not any("doble pregunta" in p for p in juzgar(r))
