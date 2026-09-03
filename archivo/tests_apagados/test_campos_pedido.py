"""UNA SOLA LISTA DE CAMPOS. El tipo del punto ES el campo de
`registrar_pedido`. Sin apodos.

Si el cliente abre dos campos, el indice abre esos dos. Si abre diez, diez.
Las dieciocho clases dificiles caen en esos campos: no son otra taxonomia.
"""
from app.core.herramientas import CAMPOS_PEDIDO, RegistrarPedido
from app.core import indice_turno as IT
from banco_pruebas import preguntas as P


_DIEZ = {
    "items": [{"que": "mouse", "cantidad": 1}],
    "restricciones": ["sin partes chinas"],
    "destinos": ["Cordoba"],
    "pide_precio": True,
    "contradicciones": ["nombraste un teclado que no estaba en el pedido"],
    "reparto_pago": [{"porcentaje": 70}, {"porcentaje": 30}],
    "atributos": [{"de": "mouse", "campo": "dpi"}],
    "stock": ["mouse"],
    "compatibilidad": [{"que": "mouse", "para": "notebook"}],
    "temas": ["garantia"],
}


def test_la_lista_sale_del_molde_y_de_ningun_otro_lado():
    """Si alguien escribe los diez nombres a mano, en dos semanas hay once."""
    assert CAMPOS_PEDIDO == tuple(RegistrarPedido.model_fields.keys())
    assert len(CAMPOS_PEDIDO) == 10
    assert len(set(CAMPOS_PEDIDO)) == 10


def test_dos_campos_abren_dos_tipos_y_diez_abren_diez():
    dos = {"items": [{"que": "mouse", "cantidad": 1}], "pide_precio": True}
    assert set(IT.campos_abiertos(dos)) == {"items", "pide_precio"}
    assert {p["tipo"] for p in IT.puntos(dos)} == {"items", "pide_precio"}

    assert set(IT.campos_abiertos(_DIEZ)) == set(CAMPOS_PEDIDO)
    assert {p["tipo"] for p in IT.puntos(_DIEZ)} == set(CAMPOS_PEDIDO)


def test_el_tipo_es_el_campo_sin_apodo():
    """`condicion` al lado de `restricciones` era el telefono descompuesto."""
    tipos = {p["tipo"] for p in IT.puntos(_DIEZ)}
    assert not (tipos & set(IT.TIPOS_APODO)), tipos
    for p in IT.puntos(_DIEZ):
        assert p["tipo"] in CAMPOS_PEDIDO
        assert p["id"].startswith(p["tipo"] + ":")


def test_la_oferta_es_lo_unico_que_no_es_campo():
    """La abre el codigo, no el cliente. No se suma al molde."""
    assert IT.TIPO_OFERTA not in CAMPOS_PEDIDO
    assert set(IT.TIPOS_QUE_FRENAN) <= set(CAMPOS_PEDIDO)
    assert set(IT.TIPOS_SIN_OFERTA) == {IT.TIPO_OFERTA}


def test_las_clases_dificiles_caen_en_esos_campos():
    """Dieciocho clases, una lista. Cada clase nombra campos del molde
    o `cierre`, que no declara registrar_pedido."""
    nombres = {c[0] for c in P.CLASES}
    assert set(P.CLASE_A_CAMPOS) == nombres
    cubiertos = set()
    for clase, campos in P.CLASE_A_CAMPOS.items():
        assert campos, clase
        for campo in campos:
            if campo in P._FUERA_DEL_MOLDE:
                continue
            assert campo in CAMPOS_PEDIDO, f"{clase} apunta a {campo}"
            cubiertos.add(campo)
    faltan = set(CAMPOS_PEDIDO) - cubiertos
    assert not faltan, f"campos del molde sin clase: {sorted(faltan)}"
