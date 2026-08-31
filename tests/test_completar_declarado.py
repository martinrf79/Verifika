"""
DESPUES DE registrar_pedido: leer el mensaje, completar item→ciudad y el
articulo que falte, y recien ahi buscar y cotizar.

EL CASO, el mensaje real de WhatsApp del 28-ago. El bot cotizo siete
unidades y tres envios, y en el mismo mensaje dijo 'me faltan 7 de 7
unidades sin asignar'. La cuenta ya tenia los destinos; le faltaba el
reparto. La respuesta cambia cuando sale con tres envios y siete
productos ASIGNADOS, no cuando el modelo razona mejor.

Corre offline, sin modelo.
"""
import pytest

from app.core import filtros_catalogo as FC
from app.core import herramientas as H
from app.core import resolver as R
from app.core.contexto_turno import set_current_tienda
from app.core.estado_venta import set_current_estado

TIENDA = "verifika_prod"

_MSG = (
    "Dame precio de dos auriculares, dos mouse y dos memorias. El precio "
    "no seria tan importante. Lo que si que necesito que lleven las menos "
    "partes chinas posibles. Un auricular y un mouse sera envio a Cordoba "
    "capital. Un teclado y un mouse sera envio a Concordia. Los otros dos "
    "articulos seran con envio a posadas. Divide el presupuesto en setenta "
    "treinta, ya que vere en la fase siguiente como seguimos."
)

_DECL_INCOMPLETO = {
    "items": [{"que": "auriculares", "cantidad": 2, "categoria": "auriculares"},
              {"que": "mouse", "cantidad": 2, "categoria": "mouse"},
              {"que": "memorias", "cantidad": 2, "categoria": "memoria ram"}],
    "restricciones": ["las menos partes chinas posibles"],
    "destinos": ["Cordoba capital", "Concordia", "Posadas"],
    "pide_precio": True,
    "contradicciones": [
        "Mencionaste un teclado en el envio a Concordia que no estaba "
        "en tu lista inicial"],
    "reparto_pago": [{"porcentaje": 70}, {"porcentaje": 30}],
}


@pytest.fixture(autouse=True)
def _doble(firestore_doble):
    set_current_tienda(TIENDA)
    set_current_estado({"mensaje_del_turno": _MSG})
    FC.limpiar_cache()
    yield
    set_current_estado({})


def test_cantidades_del_mensaje_son_siete_con_el_teclado():
    """Primera mencion: 2+2+2, y el teclado aparece en el envio. Son 7."""
    cats = FC.cantidades_por_categoria(_MSG, TIENDA)
    por = {c: n for n, c in cats}
    assert sum(por.values()) == 7, cats
    assert any("teclado" in c.lower() for c in por), cats
    assert any("auricular" in c.lower() for c in por), cats
    assert any("mouse" in c.lower() for c in por), cats


def test_el_mensaje_completa_item_ciudad_y_el_teclado():
    """Sin modelo: el codigo lee el mensaje y deja 7 unidades en 3 destinos."""
    fuera = R._completar_el_declarado(dict(_DECL_INCOMPLETO), TIENDA)
    items = fuera["items"]
    unidades = sum(max(1, int(i.get("cantidad") or 1)) for i in items)
    assert unidades == 7, items
    destinos = {str(i.get("destino") or "") for i in items}
    assert len(destinos) == 3, destinos
    assert all(i.get("destino") for i in items), items
    assert any("teclado" in (i.get("categoria") or i.get("que") or "").lower()
               for i in items), items
    # LA CONTRADICCION SOBREVIVE, y hasta el 31-ago esta linea afirmaba lo
    # contrario. El requisito cambio de verdad y lo cambio una charla real: en
    # el turno 2dde2ad0 el cliente pidio SEIS articulos, el codigo completo el
    # reparto leyendo el mensaje, borro las dos contradicciones porque nombraban
    # categorias que habian quedado en el carrito, y el cliente se fue con siete
    # unidades y un teclado de $12.000 que nunca pidio, sin una sola pregunta.
    #
    # Que el teclado este en el carrito no cierra la contradiccion: es lo que la
    # abre. Completar el reparto es merito del codigo y esta bien que lo haga;
    # decidir por el cliente que ademas se lo lleva, no. Las dos cosas conviven
    # y por eso este test las afirma juntas: el item se queda -abajo se
    # comprueba que Concordia sale con sus dos unidades- y la contradiccion
    # tambien, para que el turno la pregunte.
    assert fuera.get("contradicciones"), (
        "el codigo se comio la contradiccion al completar el reparto")
    assert any("teclado" in c.lower() for c in fuera["contradicciones"]), (
        fuera["contradicciones"])
    # Cordoba: auricular + mouse. Concordia: teclado + mouse.
    def _en(ciudad):
        return [i for i in items if ciudad in H._norm(i.get("destino"))]
    assert sum(i["cantidad"] for i in _en("cordoba")) == 2
    assert sum(i["cantidad"] for i in _en("concordia")) == 2
    assert sum(i["cantidad"] for i in _en("posadas")) == 3


def test_la_cuenta_sale_con_tres_envios_y_siete_productos(firestore_doble):
    """LA VARA. No mide prosa del modelo: mide la cuenta sellada. 3 envios,
    7 unidades, ninguna sin asignar."""
    declarado = dict(_DECL_INCOMPLETO)
    declarado["items"] = [dict(i) for i in _DECL_INCOMPLETO["items"]]
    llamadas = [{"herramienta": "registrar_pedido",
                 "resultado": {"estado": "registrado", "pedido": declarado}}]
    out = R.resolver(declarado, [], TIENDA, "t", llamadas=llamadas)
    bloque = out["bloque"] or ""
    cuenta = next((l for l in out["llamadas"] if R._es_presupuesto(l)
                   and (l.get("resultado") or {}).get("estado") == "ok"), None)
    assert cuenta, "el codigo no armo la cuenta"
    items = (cuenta.get("pedido") or {}).get("items") or []
    unidades = sum(max(1, int(i.get("cantidad") or 1)) for i in items)
    destinos = (cuenta.get("pedido") or {}).get("destinos") or []
    assert unidades == 7, items
    assert len(destinos) == 3, destinos
    assert all(i.get("destino") for i in items), items
    assert "sin asignar" not in bloque, bloque
    assert "3 envios" in bloque or "3 envíos" in bloque, bloque
    assert "Reparto de los envios" in bloque or "A Cordoba" in bloque \
        or "A Córdoba" in bloque, bloque
