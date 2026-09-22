"""
AREA: EL ATERRIZAJE — del concepto que el modelo entendio al campo de ESTA
tienda, que es el salto donde falla todo lo medido.

LOS DOS SALTOS, y este archivo cuida el segundo. El primero —de las palabras
del cliente al concepto— lo hace el modelo de cabeza, es universal y no crece
con el catalogo: "se traba con muchas pestañas" a memoria, "aparato con teclas"
a teclado. El segundo —del concepto al campo— es donde el modelo elige de una
lista que es UNA SOLA para las 880 filas mientras los campos viven POR
CATEGORIA.

EL CASO QUE ORDENA TODO, turno 2c36e750 de produccion: el modelo razona bien,
pide memoria ram con `ram_ampliable igual si`, las 96 memorias no tienen ese
campo cargado, el filtro deja cero productos, el veredicto sale `no_existe` y
el bot contesta que no lo tenemos. **El modelo interpreto bien y el sistema
contesto mal.**

EL MISMO DEFECTO EXISTE EN EL CATALOGO DEL REPO y por eso se puede medir
offline: `color` esta cargado en 861 de los 880 productos y en CERO de los 19
procesadores. "Un procesador negro" devolvia cero.
"""
import pytest

from app.core import filtros_catalogo as FC
from app.core import motor as MT

TIENDA = "verifika_prod"


@pytest.fixture(autouse=True)
def _doble(firestore_doble):
    from app.core.contexto_turno import set_current_tienda
    from app.core.filtros_catalogo import limpiar_cache
    set_current_tienda(TIENDA)
    limpiar_cache()
    return firestore_doble


def _todo() -> list:
    from app.storage.firestore_client import get_all_products
    return get_all_products(tienda_id=TIENDA) or []


def _procesadores() -> list:
    return [p for p in _todo()
            if str(p.get("categoria", "")).strip().lower() == "procesador"]


# ── EL CAMPO MUERTO NO PUEDE DECIR "NO LO VENDEMOS" ─────────────────────────

def test_el_campo_vacio_en_toda_la_categoria_no_vacia_el_resultado():
    """`color` esta en cero de los 19 procesadores. Antes: cero filas y el bot
    diciendo que no lo tenemos. Ahora: la condicion no se pudo aplicar y los
    19 siguen ahi."""
    procs = _procesadores()
    assert procs, "el catalogo no trae procesadores"
    assert not any(str(p.get("color", "")).strip() for p in procs)
    r = MT.buscar([{"categoria": "procesador", "condiciones": [
        {"campo": "color", "operador": "igual", "valor": "negro"}]}], TIENDA)
    res = r["resultados"][0]
    assert res["veredicto"] == "existe", "un campo sin dato dijo no_existe"
    assert res["filas"], "se llevo puesto el resultado"
    motivos = " ".join(str(x) for x in (res.get("no_aplicado") or []))
    assert "color" in motivos
    assert "no se puede filtrar" in motivos


def test_el_motivo_dice_cuantos_son_y_no_miente():
    procs = _procesadores()
    r = FC.aplicar(procs, [FC_cond("color", "igual", "negro")], TIENDA)
    assert len(r["productos"]) == len(procs)
    assert r["aplicados"] == []
    assert len(r["descartados"]) == 1
    assert f"{len(procs)} productos" in r["descartados"][0]["motivo"]


def test_un_campo_con_dato_parcial_sigue_filtrando_normal():
    """El recorte es `sin_dato == evaluados`, no `sin_dato > 0`. Un campo
    incompleto filtra como siempre: lo que se arregla es la ausencia TOTAL."""
    mouses = [p for p in _todo()
              if str(p.get("categoria", "")).strip().lower() == "mouse"]
    r = FC.aplicar(mouses, [FC_cond("color", "igual", "negro")], TIENDA)
    assert r["aplicados"], "no aplico un campo que si tiene dato"
    assert len(r["productos"]) < len(mouses), "no filtro nada"


def test_el_resto_del_pedido_sobrevive_al_campo_muerto():
    """La boca CATALOGO le promete al modelo que un campo que no existe se dice
    y NO cancela el resto. Con dos condiciones, la buena tiene que aplicarse."""
    procs = _procesadores()
    r = FC.aplicar(procs, [FC_cond("color", "igual", "negro"),
                           FC_cond("marca", "contiene", "intel")], TIENDA)
    assert len(r["descartados"]) == 1
    assert [a["campo"] for a in r["aplicados"]] == ["marca"]
    assert all("intel" in str(p.get("marca", "")).lower()
               for p in r["productos"])


# ── EL ATERRIZAJE: DONDE VIVE ESE VALOR ─────────────────────────────────────

def test_campos_cargados_no_es_lo_mismo_que_campos_filtrables():
    procs = _procesadores()
    delrubro = FC.campos_cargados(procs, TIENDA)
    assert "color" not in delrubro
    assert "marca" in delrubro and "precio_ars" in delrubro
    assert "color" in FC.campos_filtrables(TIENDA)


def test_el_indice_encuentra_el_campo_donde_vive_el_valor():
    todos = _todo()
    assert "marca" in FC.campos_con_el_valor(todos, "logitech", TIENDA)
    assert FC.campos_con_el_valor(todos, "no_existe_este_valor_raro",
                                  TIENDA) == []
    assert FC.campos_con_el_valor(todos, "", TIENDA) == []


def test_el_descarte_sugiere_donde_si_esta_el_valor():
    """Si el valor vive en otro campo, el motivo lo dice. Es lo que le permite
    al modelo corregir en la vuelta siguiente sin adivinar nuestro esquema."""
    todos = _todo()
    r = FC.aplicar(todos, [FC_cond(FC.SIN_CAMPO, "igual", "logitech")], TIENDA)
    motivo = r["descartados"][0]["motivo"]
    assert "marca" in motivo
    assert "volve a buscar" in motivo


def test_no_se_inventa_una_sugerencia_cuando_no_la_hay():
    """Una sugerencia inventada es peor que ninguna."""
    r = FC.aplicar(_todo(),
                   [FC_cond(FC.SIN_CAMPO, "igual", "zzzz_nada")], TIENDA)
    motivo = r["descartados"][0]["motivo"]
    assert "SI esta cargado" not in motivo


def test_la_sugerencia_no_se_propone_a_si_misma():
    """Sobre el campo que acaba de fallar no se sugiere ese mismo campo."""
    procs = _procesadores()
    r = FC.aplicar(procs, [FC_cond("color", "igual", "intel")], TIENDA)
    motivo = r["descartados"][0]["motivo"]
    assert "ese valor SI esta cargado en" in motivo
    assert "color" not in motivo.split("SI esta cargado en")[1]


# ── AYUDANTE ────────────────────────────────────────────────────────────────

class _C:
    def __init__(self, campo, operador, valor):
        self.campo, self.operador, self.valor = campo, operador, valor


def FC_cond(campo, operador, valor):
    """Una condicion como la espera `aplicar`, que lee por atributo."""
    return _C(campo, operador, valor)
