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


def _productos():
    """El catalogo real del repo por el doble local de Firestore."""
    from app.storage.firestore_client import get_all_products
    return get_all_products(tienda_id=TIENDA) or []


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
    porque comparar '24' contra '24 meses' da un resultado que parece bien.

    SON TRES TIPOS DESDE EL 11-SEP, no dos. `bluetooth` dejo de ser `texto` y
    paso a ser `si_no`: no cambio el dato, cambio que ahora se lo nombra por lo
    que es. La vara de antes -que no fuera numero- sigue entera abajo."""
    campos = FC.campos_filtrables(TIENDA)
    assert campos["peso_gramos"] == "numero"
    assert campos["garantia_meses"] == "numero"
    assert campos["color"] == "texto"
    assert campos["bluetooth"] == "si_no"
    # LA MISMA VARA DEL SIEMPRE, aplicada al veredicto. `bateria` dice "si,
    # bateria recargable" en 470 fichas y "funciona con 1 pila AA" en 12: esas
    # 12 no dicen que no, asi que el campo NO es de si o no.
    assert campos["bateria"] == "texto"
    assert campos["wifi"] == "texto"


def test_un_campo_de_si_o_no_resuelve_el_no_aunque_la_ficha_no_ponga_coma():
    """EL AGUJERO QUE CIERRA EL TIPO, medido el 11-sep sobre el catalogo vivo.

    La fuente escribe el veredicto de dos formas: con coma -"si, lector
    microSD"- y sin ella -"no trae lector de tarjetas"-. El `igual` de texto
    cortaba por la coma, asi que salvaba la primera y no la segunda: de los
    ocho campos de si o no, TRES daban casi cero para el `no`. El cliente que
    pedia una notebook sin lector de huella se llevaba un "no hay", con 123
    fichas que lo dicen."""
    campos = FC.campos_filtrables(TIENDA)
    prods = _productos()
    for campo in ("lector_tarjetas", "lector_huella", "thunderbolt"):
        assert campos[campo] == "si_no", campo
        dicen_no = [p for p in prods
                    if FC._valor_crudo(p, campo)
                    and FC._norm(FC._valor_crudo(p, campo)).startswith("no")]
        assert len(dicen_no) > 50, campo
        cumplen = [p for p in prods
                   if FC.evaluar(p, campo, "igual", "no", "si_no") is True]
        assert len(cumplen) == len(dicen_no), campo


def test_sobre_un_campo_de_si_o_no_mayor_y_menor_se_descartan():
    """El tipo nuevo no abre una puerta que no existia: comparar por mayor un
    veredicto no ordena nada, y se devuelve como filtro NO aplicado con su
    motivo, igual que sobre un campo de texto."""
    class F:
        campo, operador, valor = "bluetooth", "mayor", "5"
    r = FC.aplicar(_productos(), [F()], TIENDA)
    assert r["aplicados"] == []
    assert len(r["descartados"]) == 1
    assert "mayor o menor" in r["descartados"][0]["motivo"]


def test_el_inventario_y_los_campos_salen_de_UNA_recorrida_y_UN_cache():
    """LA FALLA QUE ESTO CIERRA, y no la veia nadie porque no era un test rojo
    sino un numero viejo: `campos_filtrables` aca y `fuente.inventario` alla
    recorrian los mismos 880 productos, cada una con su cache, y
    `invalidate_cache` -la que corre en cada /admin/upload-catalog- no tocaba
    ninguno de los dos. Subir un catalogo nuevo dejaba al bot diciendo el
    numero de productos del viejo hasta que el proceso se reiniciara."""
    from app.core import fuente as F
    from app.storage.firestore_client import invalidate_cache

    r = FC.recorrida(TIENDA)
    assert r["campos"] == FC.campos_filtrables(TIENDA)
    assert F.inventario(TIENDA)["productos"] == r["productos"] == 880
    assert len(r["categorias"]) == 22

    # El cache de lo derivado muere con el catalogo, y por una sola puerta.
    FC._cache[TIENDA] = dict(r, productos=1, campos={"inventado": "texto"})
    assert F.inventario(TIENDA)["productos"] == 1
    invalidate_cache(TIENDA)
    assert F.inventario(TIENDA)["productos"] == 880
    assert "inventado" not in FC.campos_filtrables(TIENDA)






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










# ── LA EXCLUSION YA NO LA RESUELVE EL CODIGO (11-sep-2026) ──────────────────
#
# `resolver_exclusion` y `resolver_inclusion` se borraron con el motor.
# Traducian la frase del cliente a un campo cortando raices de cuatro letras, y
# eso es razonar: "que no sea de marca china" resolvia a
# `origen no_contiene marc` -la raiz de "marca", que esta en los 880 origenes-,
# o sea CERO productos y el bot diciendo que no hay nada.
#
# Las frases que median los dos tests que estaban aca -"menos partes chinas
# posibles" y sus seis formas, mas las cuatro que NO son exclusiones- no se
# perdieron: la traduccion la escribe ahora el modelo, asi que se miden donde se
# puede medir al modelo, en `banco_pruebas/barrido_orden.py`. Lo que SI se sigue
# midiendo offline es la otra mitad, la que el codigo si puede garantizar: que
# la condicion, una vez escrita, saque exactamente lo que tiene que sacar.

def test_la_exclusion_por_campo_saca_lo_que_tiene_que_sacar(firestore_doble):
    prods = _productos()
    chinos = [p for p in prods
              if "chin" in FC._norm(FC._valor_crudo(p, "pais_marca"))]
    assert len(chinos) > 20, "el catalogo tiene que tener marcas chinas"

    class F:
        campo, operador, valor = "pais_marca", "no_contiene", "china"
    r = FC.aplicar(prods, [F()], TIENDA)
    quedaron = {str(p.get("id")) for p in r["productos"]}
    assert not (quedaron & {str(p.get("id")) for p in chinos}), \
        "quedo adentro una marca china"
