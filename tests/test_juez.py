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
