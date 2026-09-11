"""
AREA: LOS FILTROS ESTRUCTURADOS DEL CATALOGO.

EL AGUJERO QUE CIERRAN, medido el 4-ago sobre `main`: el catalogo tiene veinte
columnas llenas al cien por ciento en los 880 productos y veinticuatro claves de
`specs`, y `buscar_productos` le dejaba pedir al modelo seis cosas. Ante "tenes
alguno blanco" o "que sea resistente al agua" no tenia COMO preguntarselo al
codigo: recibia tres fichas y razonaba sobre la prosa. Eso es el mecanismo de
alucinacion con el dato ya cargado en la fuente.

Corren contra el catalogo REAL del repo por el doble local de Firestore.
"""
import pytest

from app.core import filtros_catalogo as FC
from app.core.contexto_turno import set_current_tienda

TIENDA = "verifika_prod"


@pytest.fixture(autouse=True)
def _doble(firestore_doble):
    set_current_tienda(TIENDA)
    FC.limpiar_cache()
    return firestore_doble


# ── LA ATADURA: EL ENUM SALE DE LA FUENTE ────────────────────────────────────
def test_los_campos_filtrables_salen_del_catalogo_vivo():
    """Misma regla que `categoria` y que `temas`: el modelo no puede nombrar un
    campo que la fuente no tiene. Si el enum se escribiera a mano, el dia que
    cambie una columna el filtro deja de filtrar EN SILENCIO."""
    campos = FC.campos_filtrables(TIENDA)
    # columnas del catalogo
    for c in ("color", "material", "peso_gramos", "dimensiones",
              "garantia_meses", "origen", "contenido_caja", "uso_recomendado"):
        assert c in campos, c
    # claves de specs, que es donde viven las que mas pregunta el cliente
    for c in ("bluetooth", "conexion", "bateria", "resistencia_agua", "wifi"):
        assert c in campos, c
    # el PRECIO entra al registro desde el 5-ago: tenia su propia puerta
    # -`tope_precio` y `orden`- y era la cuarta forma de decir lo mismo. Ahora
    # es una condicion mas -`precio_ars menor X`- y un criterio de orden mas.
    assert campos["precio_ars"] == "numero"
    # y los dos paises que el origen escondia, derivados de la fuente: el
    # cliente que no quiere marca china no esta pidiendo lo mismo que el que no
    # quiere fabricacion china, y pegados no habia forma de pedir uno solo.
    assert campos["pais_marca"] == "texto"
    assert campos["pais_fabricacion"] == "texto"
    # lo que NO se ofrece, cada uno por su motivo
    for c in ("id", "tags", "descripcion_rica", "specs", "compat",
              "categoria", "stock"):
        assert c not in campos, c


def test_el_tipo_se_infiere_del_dato_no_se_declara_a_mano():
    """`mayor` y `menor` solo tienen sentido sobre numeros. El tipo se deduce
    de los valores del catalogo: un campo mitad numero mitad texto es texto,
    porque comparar '24' contra '24 meses' da un resultado que parece bien."""
    campos = FC.campos_filtrables(TIENDA)
    assert campos["peso_gramos"] == "numero"
    assert campos["garantia_meses"] == "numero"
    assert campos["color"] == "texto"
    assert campos["bluetooth"] == "texto"






# ── QUE FILTRE DE VERDAD ─────────────────────────────────────────────────────








# ── LOS BORDES QUE ROMPEN EN SILENCIO ────────────────────────────────────────
def test_un_valor_corto_matchea_palabra_entera_no_substring():
    """El borde que obliga a la palabra entera: la mitad de las specs empiezan
    con 'si,' o 'no,'. Con substring pelado, `bluetooth contiene si` daba
    VERDADERO sobre "no, este modelo es con cable" -por el 'si' de 'version'-
    y el bot afirmaba que un producto tiene bluetooth cuando la fuente dice lo
    contrario. Es alucinacion generada por el filtro."""
    assert FC._texto_contiene("si, bluetooth 5.0", "si") is True
    assert FC._texto_contiene("Mouse, cable o receptor USB segun version",
                              "si") is False
    assert FC._texto_contiene("no, este modelo es con cable", "no") is True
    assert FC._texto_contiene("Negro", "no") is False
    # y las palabras largas siguen matcheando por dentro
    assert FC._texto_contiene("Mouse inalambrico", "inalambr") is True




def test_sin_dato_no_es_un_no():
    """El silencio de la ficha no se entiende como incumplimiento. Si el
    producto no tiene el campo, no se sabe: es la misma regla que
    `specs_preguntables`, el dato manda y el modelo no afirma lo que la fuente
    no dice."""
    p = {"peso_gramos": 144, "specs": {"bluetooth": "no, con cable"}}
    assert FC.evaluar(p, "wifi", "contiene", "si", "texto") is None
    assert FC.evaluar(p, "bluetooth", "contiene", "si", "texto") is False
    assert FC.evaluar(p, "peso_gramos", "menor", "200", "numero") is True


def test_el_numero_se_saca_aunque_venga_con_la_unidad():
    """El modelo manda '500 gramos' cuando el cliente lo dijo asi."""
    p = {"peso_gramos": 144}
    assert FC.evaluar(p, "peso_gramos", "menor", "200 gramos", "numero") is True






# ── NINGUNA HERRAMIENTA DEVUELVE VACIO (Martin, 2-ago) ───────────────────────




# ── QUE NO SE ROMPA LO QUE YA ANDABA ─────────────────────────────────────────


# ── EL RECONCILIADOR TIENE QUE CONOCER EL ARGUMENTO NUEVO ────────────────────
# No habia NI UN test de `pedido.reconciliar` en la bateria. Estos cubren la
# parte que toca a los filtros, que es la que se acaba de mover.
def _llamada(filtros=None, **ped):
    return [{"herramienta": "buscar_productos",
             "pedido": {"categoria": "mouse", "filtros": filtros, **ped},
             "resultado": {"productos": []}}]










# ── PEDIR MENOS DE ALGO ES UNA FORMA, NO UNA PALABRA (9-ago-2026) ────────────

def test_la_minimizacion_se_resuelve_se_diga_como_se_diga():
    """"menos partes chinas posibles" resolvia y "la MENOR cantidad de partes
    chinas posible" -como lo dijo Martin en la redaccion coloquial- devolvia
    None: el unico criterio que el cliente puso se perdia entero, y con el la
    unica razon por la que escribio. Se cubre la FORMA, no la palabra con que
    se dijo esta vez."""
    from app.core import filtros_catalogo as FC
    for frase in ("menos partes chinas posibles",
                  "menor cantidad de partes chinas posible",
                  "la minima cantidad de componentes chinos",
                  "lo menos chino posible",
                  "que no sean chinos"):
        cond = FC.resolver_exclusion(frase, TIENDA)
        assert cond and cond["operador"] == "no_contiene", frase
        assert cond["valor"] == "chin", frase


def test_lo_que_NO_es_una_exclusion_sigue_sin_tocarse():
    """LA CONTRACARA, y es la que hace seguro el cambio de arriba. Aplicar una
    condicion al reves es peor que no aplicarla: quien PIDE algo chino no puede
    terminar con un filtro que se lo saca, y una palabra suelta como 'menor' en
    otro contexto no puede inventar una condicion."""
    from app.core import filtros_catalogo as FC
    for frase in ("quiero productos chinos", "mouse chino",
                  "para mi hijo menor", "el precio menor posible"):
        assert FC.resolver_exclusion(frase, TIENDA) is None, frase
