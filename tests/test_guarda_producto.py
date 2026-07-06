"""
AREA: GUARDA DE PRODUCTO (paso 2) — 'interprete BIEN, solver MAL' sobre el QUE.

Lockea _reanclar_si_producto_divergente: cuando el interprete resolvio con
confianza un NOMBRE que reconcilia con un unico producto del catalogo y el solver
mostro OTRO, el codigo re-ancla al producto correcto con su linea real y una
pregunta de confirmacion. Triple candado: confianza alta, nombre que reconcilia
UNICO, y que ese id no este entre los que el solver ya mostro.

Usa el catalogo REAL por la fixture firestore_doble (sin LLM). Elige los
productos del catalogo en runtime para no hardcodear ids.
"""
from app.core.interprete_libre import (
    _reanclar_si_producto_divergente, _resolver_nombre_a_producto)
from app.storage import firestore_client as fc

TIENDA = "verifika_prod"


def get_all_products(tienda_id=None):
    # Por el modulo, no por un nombre importado al tope: el doble parchea el
    # atributo del modulo DESPUES del import, un nombre ya ligado usa el original.
    return fc.get_all_products(tienda_id=tienda_id)


def _producto_reconciliable(cat):
    """Un producto cuyo NOMBRE COMPLETO reconcilia con el mismo unico producto:
    ningun otro producto tiene un nombre contenido en el suyo (ni al reves). Es
    el caso donde la guarda puede actuar sin ambiguedad."""
    for p in cat:
        r = _resolver_nombre_a_producto(p["nombre"], cat)
        if r and str(r["id"]) == str(p["id"]):
            return p
    return None


def test_reancla_a_producto_reconciliado(firestore_doble):
    cat = get_all_products(tienda_id=TIENDA)
    p1 = _producto_reconciliable(cat)
    assert p1, "el catalogo deberia tener un producto de nombre reconciliable unico"
    otro = next(p for p in cat if p["id"] != p1["id"])
    interp = {"producto_resuelto": p1["nombre"], "confianza": 0.95}
    # El solver mostro OTRO producto y no nombra al resuelto.
    resp = "Te recomiendo otra cosa que te puede servir un monton."
    out = _reanclar_si_producto_divergente(interp, resp, [otro["id"]], TIENDA)
    assert out is not None
    assert p1["nombre"] in out
    assert "¿Avanzo con ese?" in out


def test_confianza_baja_no_pisa(firestore_doble):
    cat = get_all_products(tienda_id=TIENDA)
    p1 = _producto_reconciliable(cat)
    otro = next(p for p in cat if p["id"] != p1["id"])
    interp = {"producto_resuelto": p1["nombre"], "confianza": 0.5}
    resp = "Te recomiendo otra cosa distinta."
    assert _reanclar_si_producto_divergente(interp, resp, [otro["id"]], TIENDA) is None


def test_solver_ya_mostro_el_reconciliado_no_pisa(firestore_doble):
    cat = get_all_products(tienda_id=TIENDA)
    p1 = _producto_reconciliable(cat)
    # El solver YA mostro ese producto (aunque el texto no lo nombre): la
    # divergencia era solo textual, no se toca.
    interp = {"producto_resuelto": p1["nombre"], "confianza": 0.95}
    resp = "Aca tenes la opcion que pediste."
    assert _reanclar_si_producto_divergente(interp, resp, [p1["id"]], TIENDA) is None


def test_categoria_ambigua_no_pisa(firestore_doble):
    # 'mouse' reconcilia con muchos productos -> None -> no se pisa.
    interp = {"producto_resuelto": "mouse", "confianza": 0.95}
    resp = "Te muestro un teclado que esta muy bueno."
    assert _reanclar_si_producto_divergente(interp, resp, ["ALGO"], TIENDA) is None


def test_producto_alineado_no_pisa(firestore_doble):
    # El solver SI nombra el producto resuelto: no hay divergencia, no se toca.
    cat = get_all_products(tienda_id=TIENDA)
    p1 = _producto_reconciliable(cat)
    interp = {"producto_resuelto": p1["nombre"], "confianza": 0.95}
    resp = f"Claro, el {p1['nombre']} es una gran eleccion."
    assert _reanclar_si_producto_divergente(interp, resp, ["X"], TIENDA) is None


def test_sin_producto_resuelto_no_pisa(firestore_doble):
    interp = {"producto_resuelto": None, "confianza": 0.95}
    assert _reanclar_si_producto_divergente(interp, "cualquier cosa", ["X"], TIENDA) is None
