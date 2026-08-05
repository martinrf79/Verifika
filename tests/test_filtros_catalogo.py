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

from app.core import herramientas as H
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


def test_el_esquema_le_inyecta_el_enum_de_campos_al_modelo():
    esq = {e["function"]["name"]: e["function"]["parameters"]
           for e in H.esquemas(TIENDA)}
    campo = esq["buscar_productos"]["properties"]["filtros"]["items"]["properties"]["campo"]
    assert "color" in campo["enum"] and "bluetooth" in campo["enum"]
    assert "medidas" not in campo["enum"]  # nombre inventado, no esta en la fuente
    # los numericos se nombran: es el unico dato que no se deduce del nombre
    assert "peso_gramos" in campo["description"]


def test_el_esquema_de_filtros_no_trae_ref_ni_anyof():
    """Gemini rechaza los `$ref` que Pydantic emite para un modelo anidado. Con
    `list[Filtro]` eso es exactamente lo que sale del molde, asi que si el
    aplanado deja de correr la llamada uno falla ENTERA y el turno se queda sin
    herramientas: modo de falla mudo."""
    import json
    s = json.dumps(H.esquemas(TIENDA))
    assert "$ref" not in s and "anyOf" not in s and "$defs" not in s


# ── QUE FILTRE DE VERDAD ─────────────────────────────────────────────────────
def test_filtra_por_un_campo_de_columna():
    r = H.buscar_productos(H.BuscarProductos(
        categoria="mouse", cuantos=6,
        filtros=[{"campo": "color", "operador": "contiene",
                  "valor": "blanco"}]), TIENDA)
    assert r["estado"] == "encontrado"
    assert r["productos"]
    for p in r["productos"]:
        assert "blanco" in str(p.get("color", "")).lower()


def test_filtra_por_un_numero_con_el_borde_incluido():
    """`menor 500` es HASTA 500. El cliente dice 'hasta 500 gramos' mucho mas
    seguido que la desigualdad estricta, y el modelo traduce literal."""
    r = H.buscar_productos(H.BuscarProductos(
        categoria="mouse", cuantos=6,
        filtros=[{"campo": "peso_gramos", "operador": "menor",
                  "valor": "100"}]), TIENDA)
    assert r["estado"] == "encontrado"
    for p in r["productos"]:
        assert p["peso_gramos"] <= 100


def test_filtra_por_una_spec_que_no_es_columna():
    """Las specs son el estante donde viven bluetooth, conexion y bateria. El
    modelo pide el campo y no le importa en cual de los dos lo guardamos."""
    r = H.buscar_productos(H.BuscarProductos(
        categoria="notebook", cuantos=6,
        filtros=[{"campo": "ram", "operador": "contiene",
                  "valor": "16GB"}]), TIENDA)
    assert r["estado"] == "encontrado"
    assert r["condiciones_aplicadas"][0]["quedaron"] > 0


def test_dos_filtros_se_encadenan():
    r = H.buscar_productos(H.BuscarProductos(
        categoria="mouse", cuantos=6,
        filtros=[{"campo": "color", "operador": "contiene", "valor": "negro"},
                 {"campo": "peso_gramos", "operador": "menor",
                  "valor": "120"}]), TIENDA)
    if r["estado"] == "encontrado":
        for p in r["productos"]:
            assert "negro" in str(p.get("color", "")).lower()
            assert p["peso_gramos"] <= 120


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


def test_igual_sobre_una_spec_de_si_o_no_matchea_el_veredicto():
    """MEDIDO CON EL MODELO VIVO el 4-ago: ante "necesito unos auriculares con
    bluetooth" el modelo pidio `bluetooth igual si`, que es lo natural para un
    campo de si o no. Con igualdad estricta eso no matchea NUNCA, porque las
    specs estan escritas "veredicto, detalle": 234 productos dicen "si,
    bluetooth 5.0". El filtro daba cero y el bot contestaba que no hay, con el
    catalogo lleno. `igual` vale contra el string entero o su primer segmento."""
    p = {"specs": {"bluetooth": "si, bluetooth 5.0"}}
    q = {"specs": {"bluetooth": "no, este modelo es con cable"}}
    assert FC.evaluar(p, "bluetooth", "igual", "si", "texto") is True
    assert FC.evaluar(q, "bluetooth", "igual", "si", "texto") is False
    assert FC.evaluar(q, "bluetooth", "igual", "no", "texto") is True
    # y sobre el catalogo real tiene que traer los que si lo tienen
    r = H.buscar_productos(H.BuscarProductos(
        categoria="notebook", cuantos=3,
        filtros=[{"campo": "bluetooth", "operador": "igual",
                  "valor": "si"}]), TIENDA)
    assert r["estado"] == "encontrado" and r["hay_en_total"] > 100


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


def test_un_campo_inventado_no_filtra_en_silencio_se_reporta():
    """Si un filtro se cae y no se dice, el modelo presenta como filtrada una
    lista que no lo esta: afirma que los tres productos son livianos cuando
    nadie los peso. La caida tiene que viajar en el resultado."""
    r = H.buscar_productos(H.BuscarProductos(
        categoria="mouse",
        filtros=[{"campo": "medidas", "operador": "contiene",
                  "valor": "chico"}]), TIENDA)
    assert r["estado"] == "encontrado"
    assert r["condiciones_no_aplicadas"][0]["campo"] == "medidas"
    assert "NO se pudieron aplicar" in r["instruccion"]


def test_mayor_sobre_un_campo_de_texto_se_rechaza_con_motivo():
    r = H.buscar_productos(H.BuscarProductos(
        categoria="mouse",
        filtros=[{"campo": "color", "operador": "mayor",
                  "valor": "5"}]), TIENDA)
    assert r["estado"] == "encontrado"
    assert "texto" in r["condiciones_no_aplicadas"][0]["motivo"]


# ── NINGUNA HERRAMIENTA DEVUELVE VACIO (Martin, 2-ago) ───────────────────────
def test_si_el_filtro_no_deja_nada_se_ofrece_lo_mas_parecido_y_se_dice_cual_falla():
    """Un filtro que no deja nada casi nunca significa que no tenemos el
    producto: significa que ESA condicion no se cumple. El caso real del
    catalogo: los 46 auriculares son con cable. Sin esto el bot contesta "no
    tenemos auriculares", que es mentira y mata la venta.

    Es la misma leccion que dejo `excluir` el 2-ago con las partes chinas."""
    r = H.buscar_productos(H.BuscarProductos(
        categoria="auriculares",
        filtros=[{"campo": "bluetooth", "operador": "contiene",
                  "valor": "si"}]), TIENDA)
    assert r["estado"] == "ninguno_cumple_del_todo"
    assert r["productos"], "nunca se devuelve vacio"
    # y se dice CUAL condicion es la que falla, producto por producto
    assert r["productos"][0]["no_cumple"]
    assert "bluetooth" in r["productos"][0]["no_cumple"][0]
    # EL HECHO YA NO VIAJA COMO INSTRUCCION, VIAJA COMO BLOQUE. Se le pedia al
    # modelo en prosa que no dijera que no tenemos el producto, y medido con la
    # clave paga el 5-ago abria con el muro igual. Ahora el codigo escribe el
    # renglon y el modelo lo pega, como ya pasa con la cuenta.
    assert "Lo que más se acerca" in r["bloque"]
    assert r["productos"][0]["nombre"] in r["bloque"]
    # EL DATO, NO LA CONDICION. Al cliente le llega el valor real de la ficha
    # -"bluetooth: no, este modelo es con cable"-, no la sintaxis del filtro.
    # La primera version pegaba "no cumple: bluetooth contiene si" y esa
    # cañeria interna salio en el mensaje al cliente, medido con la clave paga.
    assert "bluetooth" in r["bloque"]
    assert "contiene" not in r["bloque"] and "_" not in r["bloque"]


def test_el_rescate_ordena_por_cuantas_condiciones_cumple():
    """Con dos condiciones y ninguna que las cumpla las dos, primero va el que
    cumple una, no el primero del catalogo."""
    r = H.buscar_productos(H.BuscarProductos(
        categoria="notebook",
        filtros=[{"campo": "ram", "operador": "contiene", "valor": "16GB"},
                 {"campo": "garantia_meses", "operador": "mayor",
                  "valor": "24"}]), TIENDA)
    assert r["estado"] == "ninguno_cumple_del_todo"
    grados = [len(p["no_cumple"]) for p in r["productos"]]
    assert grados == sorted(grados), "el que menos incumple va primero"


# ── QUE NO SE ROMPA LO QUE YA ANDABA ─────────────────────────────────────────
def test_sin_condiciones_la_busqueda_dice_cuantos_habia_y_con_que_criterio():
    """`filtros` sigue siendo opcional, pero desde el 5-ago toda busqueda vuelve
    con DOS datos que antes no viajaban, y los dos son anti-muro:

      `hay_en_total`  : cuantos habia de verdad. Sin esto el modelo ve tres
                        productos y habla como si fueran todo el rubro.
      `ordenados_por` : con que criterio se ordenaron. Sin esto no puede decir
                        "estos son los mas baratos" sin adivinar, ni saber que
                        la lista responde a lo que el cliente describio."""
    r = H.buscar_productos(
        H.BuscarProductos(categoria="mouse", cuantos=3), TIENDA)
    assert r["estado"] == "encontrado"
    assert set(r) == {"estado", "productos", "hay_en_total", "ordenados_por"}
    assert r["hay_en_total"] > 3, "hay 45 mouse con stock, no 3"
    assert "precio" in r["ordenados_por"]


# ── EL RECONCILIADOR TIENE QUE CONOCER EL ARGUMENTO NUEVO ────────────────────
# No habia NI UN test de `pedido.reconciliar` en la bateria. Estos cubren la
# parte que toca a los filtros, que es la que se acaba de mover.
def _llamada(filtros=None, **ped):
    return [{"herramienta": "buscar_productos",
             "pedido": {"categoria": "mouse", "filtros": filtros, **ped},
             "resultado": {"productos": []}}]


@pytest.mark.parametrize("restriccion,filtro", [
    ("blanco", {"campo": "color", "operador": "contiene", "valor": "blanco"}),
    ("menos de 120 gramos",
     {"campo": "peso_gramos", "operador": "menor", "valor": "120"}),
    ("resistente al agua",
     {"campo": "resistencia_agua", "operador": "contiene", "valor": "si"}),
    ("con bluetooth",
     {"campo": "bluetooth", "operador": "igual", "valor": "si"}),
    ("16gb de ram",
     {"campo": "ram", "operador": "contiene", "valor": "16GB"}),
])
def test_una_condicion_aplicada_por_filtro_no_se_acusa_como_faltante(
        restriccion, filtro):
    """MEDIDO CON EL MODELO VIVO el 4-ago: ante "tenes algun mouse blanco?" el
    modelo pidio -bien- `color contiene blanco`, y el reconciliador, que solo
    miraba `excluir`, contesto que la condicion no se habia aplicado. El turno
    se comio una segunda ronda al pedo: 10.671 ms contra 5.060 de los que no la
    disparaban. Un chequeo que no conoce el argumento nuevo no protege: acusa,
    y ademas cuesta una llamada de modelo por turno."""
    from app.core.pedido import reconciliar
    r = reconciliar({"items": [{"que": "mouse"}],
                     "restricciones": [restriccion]}, _llamada([filtro]))
    assert not r["faltantes"], r["faltantes"]


def test_pero_si_la_condicion_no_viaja_en_ningun_lado_se_sigue_acusando():
    """La contracara: aflojar el chequeo hasta que no acuse nunca lo rompe. Sin
    filtro, la condicion sigue siendo un faltante."""
    from app.core.pedido import reconciliar
    r = reconciliar({"items": [{"que": "mouse"}],
                     "restricciones": ["blanco"]}, _llamada())
    assert r["faltantes"] and "blanco" in r["faltantes"][0]


def test_un_filtro_de_otra_cosa_no_tapa_la_condicion_pedida():
    """El universo no puede volverse tan ancho que cualquier filtro cubra
    cualquier condicion."""
    from app.core.pedido import reconciliar
    r = reconciliar(
        {"items": [{"que": "mouse"}], "restricciones": ["resistente al agua"]},
        _llamada([{"campo": "color", "operador": "contiene",
                   "valor": "negro"}]))
    assert r["faltantes"]


def test_los_filtros_no_pisan_al_certificador_de_rubro():
    """El orden importa: primero la identidad y el rubro, que los decide el
    codigo, y recien despues las condiciones. Si no, un filtro imposible
    disfraza de "no vendemos eso" algo que si vendemos."""
    r = H.buscar_productos(H.BuscarProductos(
        descripcion="una heladera",
        filtros=[{"campo": "color", "operador": "contiene",
                  "valor": "blanco"}]), TIENDA)
    assert r["estado"] == "no_vendemos"
