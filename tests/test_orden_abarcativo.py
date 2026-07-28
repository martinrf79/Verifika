"""
LOCK del CRITERIO ABARCATIVO: "la que mas X" para CUALQUIER X de la fuente.

Este test no enumera preguntas a mano: las GENERA desde el catalogo. Por cada
atributo ordenable que la fuente tenga -columna numerica o spec con magnitud-
arma la pregunta "la de mas X" y "la de menos X" y verifica que haya camino
entero: que el atributo este en el enum del interprete, que el ordenamiento
devuelva el producto correcto y que el universo que ve el solver lo incluya.

Si manana la tienda suma una columna al catalogo, este test suma esa pregunta
SOLO. Esa es la medida de que el diseño es abarcativo y no una lista de casos.
"""
import pytest

from app.core.fuente_producto import (
    atributo_de, atributos_ordenables, ordenar_por, valor_numerico,
)
from app.core.generador_v2 import universo_productos
from app.core.interpretador import _schema_interprete


@pytest.fixture(scope="module")
def catalogo(firestore_doble):
    from app.storage.firestore_client import get_all_products
    return get_all_products(tienda_id="verifika_prod")


def test_los_atributos_salen_de_la_fuente_no_de_una_lista(catalogo):
    at = atributos_ordenables(catalogo)
    # las columnas numericas del catalogo tienen que estar sin declararlas
    for esperado in ("precio_ars", "peso_gramos", "garantia_meses"):
        assert esperado in at, f"{esperado} es una columna numerica y no aparecio"
    # y las specs con magnitud tambien
    for esperado in ("ram", "almacenamiento", "hz"):
        assert esperado in at, f"{esperado} es una spec con magnitud y no aparecio"
    # lo que NO es magnitud no puede colarse como ordenable
    assert "lector_huella" not in at
    assert "conexion" not in at


def test_toda_pregunta_de_superlativo_tiene_camino(catalogo):
    """El corazon: por CADA atributo de la fuente, las dos direcciones."""
    at = atributos_ordenables(catalogo)
    assert len(at) >= 8, "la fuente tendria que dar varios atributos ordenables"
    enum = _schema_interprete([], ["notebook"], [], [], sorted(at))
    enum_atrib = enum["properties"]["orden"]["properties"]["atributo"]["enum"]
    for atributo in at:
        # 1) el interprete tiene donde ponerlo
        assert atributo in enum_atrib, f"{atributo} no esta en el enum del schema"
        for direccion in ("max", "min"):
            # 2) el ordenamiento devuelve algo y esta bien ordenado
            orden = ordenar_por(catalogo, atributo, direccion)
            assert orden, f"{atributo}/{direccion} no devolvio ningun producto"
            vals = [atributo_de(p, atributo) for p in orden[:20]]
            esperado = sorted(vals, reverse=(direccion == "max"))
            assert vals == esperado, f"{atributo}/{direccion} salio desordenado"


def test_el_universo_del_solver_obedece_el_orden(catalogo):
    """De nada sirve interpretarlo si el solver no ve el producto correcto."""
    at = atributos_ordenables(catalogo)
    for atributo in sorted(at):
        interp = {"solicitud_nueva": [{"categoria": "notebook"}],
                  "orden": {"direccion": "max", "atributo": atributo}}
        universo = universo_productos("dame la notebook con mas de eso", {},
                                      "verifika_prod", interp)
        nbs = [p for p in universo if p.get("categoria") == "notebook"]
        if not nbs:
            continue
        cabeza = ordenar_por([p for p in catalogo
                              if p.get("categoria") == "notebook"
                              and int(p.get("stock") or 0) > 0],
                             atributo, "max")
        if not cabeza:
            continue
        assert any(p["id"] == cabeza[0]["id"] for p in universo), (
            f"el universo no incluyo el maximo de {atributo}: "
            f"{cabeza[0]['nombre']}")


def test_la_notebook_de_mas_capacidad_no_es_la_mas_barata(catalogo):
    """El caso REAL del 28-jul: pidio la de mas capacidad y le ofrecimos las
    cuatro mas baratas, teniendo 57 de 1TB."""
    interp = {"solicitud_nueva": [{"categoria": "notebook"}],
              "orden": {"direccion": "max", "atributo": "almacenamiento"}}
    universo = universo_productos("la notebook que mas capacidad tenga", {},
                                  "verifika_prod", interp)
    nbs = [p for p in universo if p.get("categoria") == "notebook"]
    assert nbs, "el universo quedo sin notebooks"
    assert any("1TB" in p["nombre"] for p in nbs[:4]), (
        "la cabeza del universo tendria que traer las de 1TB")


def test_magnitudes_comparables_entre_unidades():
    assert valor_numerico("2TB") > valor_numerico("512GB SSD")
    assert valor_numerico("1TB") == 1024
    assert valor_numerico("75Hz") == 75
    assert valor_numerico("550W") == 550
    assert valor_numerico("si, lector de huella integrado") is None


# ── LO QUE SALIO DE LA CHARLA REAL DEL 28-jul ───────────────────────────────

def test_el_orden_corre_aunque_haya_un_producto_en_foco(catalogo):
    """"y la mas liviana cual es" no nombra la categoria y sigue una charla
    sobre una notebook puntual. Antes el universo se cortaba en lo mostrado y
    el bot esquivaba el peso: "mas alla del peso, esta es muy versatil"."""
    from app.core.fuente_producto import ordenar_por
    nb = [p for p in catalogo if p["categoria"] == "notebook"]
    estado = {"productos_vistos": [{"id": nb[0]["id"], "nombre": nb[0]["nombre"]}]}
    universo = universo_productos(
        "y la mas liviana cual es", estado, "verifika_prod",
        {"producto_resuelto": nb[0]["nombre"],
         "orden": {"direccion": "min", "atributo": "peso_gramos"}})
    liviana = ordenar_por([p for p in nb if int(p.get("stock") or 0) > 0],
                          "peso_gramos", "min")[0]
    assert universo[0]["id"] == liviana["id"], (
        "la cabeza del orden tiene que ENCABEZAR el universo, no estar al final")


def test_la_garantia_la_contesta_el_producto_no_la_faq(catalogo):
    """Caso real: el bot dijo "6 meses" (el minimo generico de la FAQ) para una
    notebook cuya ficha dice 12."""
    from app.core.generador_v2 import estampar_honestidad_specs
    note = next(p for p in catalogo
                if "IdeaPad 3 Core i5" in p["nombre"])
    assert note["specs"].get("garantia"), "la garantia tiene que ser preguntable"
    salida = estampar_honestidad_specs(
        "Todos nuestros productos tienen garantia oficial de 6 meses.\n"
        "¿Querés que la reservemos?",
        "de que tiempo es la garantia?", note)
    assert "6 meses" not in salida, "la linea con el dato falso tiene que caerse"
    assert "12 meses" in salida
    assert salida.strip().endswith("?"), "el dato va ANTES del cierre"


def test_los_monitores_no_tienen_todos_los_mismos_hercios(catalogo):
    """La ficha del CSV decia 75Hz en los 24 monitores, que es un valor de
    plantilla. La planilla por modelo, que es dato curado, tiene que ganarle."""
    mons = [p for p in catalogo if p["categoria"] == "monitor"]
    valores = {p["specs"].get("hz") for p in mons}
    assert len(valores) > 3, f"todos los monitores con el mismo hz: {valores}"
