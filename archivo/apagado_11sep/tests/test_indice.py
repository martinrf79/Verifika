"""
INDICE — lock del vocabulario unico.

Fija lo que se arreglo el 30-jul: habia DOS listas de nombres para el mismo eje
-93 categorias de base_conocimiento y 50 temas de FAQ, con 27 en comun- y los 23
temas que quedaban afuera el interprete no los podia nombrar. Un regex de
palabras sobre el mensaje crudo era el unico que los ruteaba: medido sobre las 66
charlas grabadas, 107 de 282 turnos.
"""
from app.core.indice import vocabulario, celda, celdas, obligatorias


def test_el_vocabulario_junta_las_dos_listas(firestore_doble):
    from app.core.guia_venta_prosa import categorias_conocimiento
    v = vocabulario("verifika_prod")
    assert len(v) == len(set(v)), "el vocabulario no puede repetir un nombre"
    for c in categorias_conocimiento():
        assert c in v
    # los que antes eran innombrables para el interprete
    for tema in ("cuotas", "envios", "marcas_originales", "devoluciones",
                 "garantia_como_usar"):
        assert tema in v


def test_los_tres_tipos_de_celda(firestore_doble):
    # dato: la respuesta esta escrita en la fuente
    c = celda("cuotas", "verifika_prod")
    assert c["tipo"] == "dato" and c["texto_faq"]
    # criterio: no hay respuesta guardada, hay material para razonar
    c = celda("objecion_precio", "verifika_prod")
    assert c["tipo"] == "criterio" and c["texto_criterio"] and not c["texto_faq"]
    # sin material no hay celda, y eso es un resultado valido
    assert celda("no_existe_esta_celda", "verifika_prod") is None
    assert celda("", "verifika_prod") is None


def test_obliga_la_prosa_y_no_el_producto(firestore_doble):
    """La celda de politica o de objecion se DEBE contestar; la de producto no.
    Sin esto el bot da una charla de asesoramiento cada vez que alguien pide el
    mouse mas barato."""
    cs = celdas(["cuotas", "objecion_precio", "mouse"], "verifika_prod")
    obl = obligatorias(cs)
    assert "cuotas" in obl and "objecion_precio" in obl
    assert "mouse" not in obl


def test_celdas_no_repite_y_respeta_el_orden(firestore_doble):
    cs = celdas(["objecion_precio", "cuotas", "objecion_precio"],
                "verifika_prod")
    assert [c["nombre"] for c in cs] == ["objecion_precio", "cuotas"]


def test_el_tope_de_obligatorias_es_real(firestore_doble):
    cs = celdas(vocabulario("verifika_prod"), "verifika_prod")
    assert len(obligatorias(cs)) <= 5
