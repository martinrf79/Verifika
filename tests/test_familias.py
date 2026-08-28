"""EL CATALOGO DE LA PREGUNTA. Una pregunta mezcla familias; es lo normal.

Los diez del molde no alcanzan: una pregunta tambien puede abrir memoria
y cierre. Las dieciocho clases dificiles y los veinte campos del
interprete muerto caen aca. No se inventa otra lista al lado.
"""
from pathlib import Path

from app.core import familias as F
from app.core import indice_turno as IT
from app.core.estado_venta import construir_estado
from app.core.herramientas import CAMPOS_PEDIDO, RegistrarPedido
from banco_pruebas import preguntas as P

_RAIZ = Path(__file__).resolve().parent.parent


def test_declaracion_es_exactamente_el_molde():
    """Si alguien suma un campo al molde y no al catalogo, hay dos listas."""
    assert CAMPOS_PEDIDO == tuple(RegistrarPedido.model_fields.keys())
    assert set(F.DECLARACION) == set(CAMPOS_PEDIDO)
    assert len(F.DECLARACION) == len(set(F.DECLARACION)) == 10


def test_el_catalogo_es_declaracion_mas_memoria_y_cierre():
    assert F.FAMILIAS == F.DECLARACION + (F.MEMORIA, F.CIERRE)
    assert len(F.FAMILIAS) == 12
    assert F.MEMORIA not in F.DECLARACION
    assert F.CIERRE not in F.DECLARACION
    assert "oferta" not in F.FAMILIAS
    assert set(F.NO_ES_PREGUNTA) == {IT.TIPO_OFERTA}


def test_una_pregunta_mezclada_abre_esas_familias_y_no_otras():
    """Pedido, precio, si le sirve y garantia en la misma frase: cuatro
    familias. Memoria no se abre por existir: hay que pedirla."""
    mezcla = {
        "items": [{"que": "mouse", "cantidad": 1}],
        "pide_precio": True,
        "compatibilidad": [{"que": "mouse", "para": "notebook"}],
        "temas": ["garantia"],
    }
    assert set(F.abiertas(mezcla)) == {
        "items", "pide_precio", "compatibilidad", "temas",
    }
    assert F.MEMORIA not in F.abiertas(mezcla)
    assert F.CIERRE not in F.abiertas(mezcla)
    con_todo = F.abiertas(mezcla, memoria=True, cierre=True)
    assert set(con_todo) == {
        "items", "pide_precio", "compatibilidad", "temas",
        F.MEMORIA, F.CIERRE,
    }


def test_el_indice_habla_declaracion_y_reexporta_el_catalogo():
    dos = {"items": [{"que": "mouse", "cantidad": 1}], "pide_precio": True}
    assert IT.campos_abiertos(dos) == F.abiertas(dos)
    tipos = {p["tipo"] for p in IT.puntos(dos)}
    assert tipos <= set(F.DECLARACION)
    assert not (tipos & set(IT.TIPOS_APODO))


def test_las_clases_dificiles_caen_en_el_catalogo():
    nombres = {c[0] for c in P.CLASES}
    assert set(P.CLASE_A_CAMPOS) == nombres
    cubiertos = set()
    for clase, campos in P.CLASE_A_CAMPOS.items():
        assert campos, clase
        for campo in campos:
            assert campo in F.FAMILIAS, f"{clase} apunta a {campo}"
            cubiertos.add(campo)
    faltan_molde = set(F.DECLARACION) - cubiertos
    assert not faltan_molde, f"declaracion sin clase: {sorted(faltan_molde)}"
    assert F.CIERRE in cubiertos
    assert F.MEMORIA not in cubiertos


def test_memoria_son_las_claves_del_estado():
    """Sin apodo: la pieza se llama como la clave de construir_estado."""
    claves = set(construir_estado({}, {}).keys())
    assert set(F.MEMORIA_PIEZAS) | set(F.MEMORIA_CONTEXTO) == claves
    assert not (set(F.MEMORIA_PIEZAS) & set(F.MEMORIA_CONTEXTO))
    assert F.MEMORIA not in claves


def test_los_veinte_del_viejo_caen_o_murieron_con_motivo():
    assert len(F.DEL_VIEJO) == 20
    assert set(F.MURIO_CON_EL_INTERPRETE) == {
        k for k, v in F.DEL_VIEJO.items() if v is None
    }
    for campo, familia in F.DEL_VIEJO.items():
        if familia is None:
            motivo = F.MURIO_CON_EL_INTERPRETE[campo]
            assert len(motivo) >= 20, campo
            continue
        assert familia in F.FAMILIAS, f"{campo} apunta a {familia}"


def test_los_veinte_siguen_escritos_en_el_interprete_muerto():
    """Si alguien borra un campo alla y aca no, el mapa miente."""
    texto = (_RAIZ / "banco_pruebas/interprete_viejo/interpretador.py"
             ).read_text(encoding="utf-8")
    faltan = [k for k in F.DEL_VIEJO if f'"{k}"' not in texto]
    assert not faltan, faltan
