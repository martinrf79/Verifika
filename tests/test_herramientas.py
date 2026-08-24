"""
AREA: LAS HERRAMIENTAS, que es donde vive todo lo que el modelo no decide.

Corren contra el catalogo y la FAQ REALES del repo, por el doble local de
Firestore. Cada test cubre una regla que el camino viejo defendia con una capa
que corregia al modelo DESPUES de escribir; aca la regla esta antes, en el dato
que se le entrega.
"""
import pytest

from app.core import herramientas as H
from app.core.contexto_turno import set_current_tienda

TIENDA = "verifika_prod"


@pytest.fixture(autouse=True)
def _doble(firestore_doble):
    set_current_tienda(TIENDA)
    from app.core.estado_venta import set_current_estado
    set_current_estado({})
    return firestore_doble


# ── LO QUE EL MODELO NO PUEDE NOMBRAR ────────────────────────────────────────
def test_el_esquema_ata_categoria_y_tema_a_la_fuente_viva():
    """La atadura del lado del modelo, DESPUES DE LA PUERTA UNICA (FICHA 06).

    No puede pedir una categoria que no vendemos: el enum sigue, mudado al
    renglon del item, y sigue saliendo del catalogo vivo. El TEMA cambio de
    mecanismo, no de exigencia: el modelo lo nombra con las palabras del
    cliente y lo certifica el codigo contra las señas de la fuente. La prueba
    de que sigue atado es que un tema que la casa NO tiene escrito vuelve
    `not_found` y no el mas parecido."""
    esq = {e["function"]["name"]: e["function"]["parameters"]
           for e in H.esquemas(TIENDA)}
    cats = (esq["registrar_pedido"]["properties"]["items"]["items"]
            ["properties"]["categoria"]["enum"])
    assert len(cats) > 5 and "heladeras" not in cats
    assert H.certificar_tema("descuento por transferencia", TIENDA) == {
        "veredicto": "exists", "temas": ["descuento_transferencia"],
        "nombre": "descuento por transferencia"}
    assert H.certificar_tema("garrafa de gas", TIENDA)["veredicto"] == "not_found"


def test_el_esquema_no_tiene_ref_ni_anyof():
    """Gemini rechaza los `$ref` y los `anyOf` que emite Pydantic para los
    opcionales. Si vuelven a colarse, la llamada uno falla ENTERA y el turno se
    queda sin herramientas: es un modo de falla mudo, por eso se testea la
    forma."""
    import json
    crudo = json.dumps(H.esquemas(TIENDA))
    assert "$ref" not in crudo and "anyOf" not in crudo and "$defs" not in crudo


# ── REGLA CERO: LA IDENTIDAD LA DECIDE EL CODIGO ─────────────────────────────
def test_varios_modelos_devuelven_ambiguo_y_el_modelo_no_puede_elegir():
    a = H.BuscarProductos(descripcion="notebook")
    r = H.buscar_productos(a, TIENDA)
    if r["estado"] == "ambiguo":
        assert len(r["productos"]) > 1
        assert "preguntale" in r["instruccion"].lower()
    else:
        # con una sola familia el veredicto es exists; nunca se inventa
        assert r["estado"] in ("encontrado", "no_encontrado")


@pytest.mark.parametrize("como_lo_escribe_el_cliente,esperado", [
    ("g203", "Logitech G203"),
    ("m170", "Logitech M170"),
    ("G203", "Logitech G203"),
    ("kb-110x", "Genius KB-110X"),
])
def test_el_codigo_de_modelo_solo_encuentra_el_producto(
        como_lo_escribe_el_cliente, esperado):
    """EL CLIENTE ESCRIBE EL CODIGO PELADO, sin la marca adelante.

    Medido el 10-ago: "tenes el g203?" daba `no_encontrado` con el Mouse
    Logitech G203 Lightsync en gondola, y "logitech g203" lo encontraba
    siempre. La causa estaba en `certificar_producto`: el codigo de modelo es
    un DESIGNADOR, se restaba del pedido, el pedido quedaba vacio y se cortaba
    antes de mirar el catalogo. O sea que la falla aparecia solo cuando el
    cliente escribe como escribe de verdad.

    Es la falla numero uno del negocio -negar stock que existe-, asi que tiene
    candado."""
    r = H.buscar_productos(
        H.BuscarProductos(descripcion=como_lo_escribe_el_cliente), TIENDA)
    assert r["estado"] == "encontrado", f"{como_lo_escribe_el_cliente}: {r}"
    nombres = " ".join(p.get("nombre", "") for p in r["productos"])
    assert esperado.lower() in nombres.lower()


def test_el_modelo_inventado_sigue_sin_existir():
    """La contracara del test de arriba, y es la que lo hace seguro: aflojar el
    corte no puede volver permisivo al certificador. Un codigo que NO esta en el
    vocabulario de los 880 sigue sin confirmarse."""
    r = H.buscar_productos(H.BuscarProductos(descripcion="g999"), TIENDA)
    assert r["estado"] == "no_encontrado"


def test_la_muletilla_corta_sigue_sin_traer_un_producto():
    """El caso que puso el corte original: 'un regalo para mi viejo' deja 'mi',
    que es la linea Mi de Xiaomi, y devolvia un cargador como si lo hubiera
    pedido. Eso no puede volver."""
    r = H.buscar_productos(
        H.BuscarProductos(descripcion="un regalo para mi viejo que labura "
                                      "en el campo"), TIENDA)
    assert r["estado"] != "encontrado"


def test_lo_que_no_existe_vuelve_como_no_encontrado_no_como_error():
    r = H.buscar_productos(
        H.BuscarProductos(descripcion="notebook cuantica xyz9000"), TIENDA)
    assert r["estado"] == "no_encontrado"


def test_lo_que_no_vendemos_lo_dice_el_codigo_con_su_alternativa():
    """El "no" honesto no puede depender de que al modelo se le ocurra decirlo:
    lo decide el certificador de rubro desde no_vendidas.json."""
    r = H.buscar_productos(H.BuscarProductos(descripcion="una heladera"), TIENDA)
    assert r["estado"] == "no_vendemos"
    assert r["rubro_real"] == "tecnologia e informatica"


# ── EL DEFECTO ABIERTO DEL 1-AGO ─────────────────────────────────────────────
def test_si_la_exclusion_no_deja_nada_se_dice_no_se_devuelve_lo_mismo():
    """Charla real del 1-ago: el cliente pidio "lo que menos partes chinas
    tenga" y recibio el MISMO presupuesto, con las mismas marcas y sin una
    palabra de por que. Con una exclusion imposible la herramienta tiene que
    decir que no hay, nunca devolver el listado como si nada.

    ACTUALIZADO 2-ago: decir que no hay ya NO es cortar con un muro. La
    condicion casi nunca es binaria aunque el argumento lo sea -"las menos
    partes chinas posibles" sobre un catalogo 100% fabricado en China-, asi que
    la herramienta avisa que ninguno cumple del todo Y devuelve los que menos
    incumplen. Ninguna herramienta devuelve vacio.

    ACTUALIZADO 4-ago: la instruccion dejo de arrancar por el negativo, porque
    ERA ELLA la que escribia el muro: decia "hay que decirlo derecho, sin
    adornar" y el modelo generalizaba al catalogo entero. "Lo que menos X tenga"
    no es un filtro, es un RANKING. Ordenar siempre devuelve un primero y NUNCA
    puede producir un muro.

    ACTUALIZADO 5-ago: `excluir` DEJO DE EXISTIR como argumento. Era la tercera
    de cuatro puertas al mismo cuarto y llevaba su propio `_grado` aparte, que
    ademas puntuaba un JUICIO -3 por la marca, 2 por la fabricacion-. Ahora es
    una condicion mas, `no_contiene`, y el orden de los que menos se alejan sale
    del mismo mecanismo que el resto: contar cuantas condiciones incumple cada
    uno."""
    r = H.buscar_productos(
        H.BuscarProductos(categoria="mouse", filtros=[
            {"campo": "pais_fabricacion", "operador": "no_contiene",
             "valor": "china"},
            {"campo": "marca", "operador": "no_contiene", "valor": "logitech"},
            {"campo": "pais_marca", "operador": "no_contiene",
             "valor": "china"}]),
        TIENDA)
    assert r["estado"] in ("ninguno_cumple_del_todo", "encontrado")
    if r["estado"] == "ninguno_cumple_del_todo":
        # Con algo para ofrecer, EN ORDEN, y diciendo cual condicion falla.
        assert r["productos"]
        assert all("no_cumple" in p for p in r["productos"])
        cuantas = [len(p["no_cumple"]) for p in r["productos"]]
        assert cuantas == sorted(cuantas), "el que menos incumple va primero"
        # y la instruccion prohibe el universal, que es de donde salia el muro
        assert "catálogo entero" in r["instruccion"]
        # el hecho lo escribe el CODIGO, no se le pide al modelo en prosa
        assert "Lo que más se acerca" in r["bloque"]


def test_el_empate_se_informa_no_se_disimula():
    """MEDIDO EL 5-AGO, y es lo que hacia inutil al gradiente viejo: pidiendo
    "el mouse que menos partes chinas tenga, que no sea Logitech", DIECINUEVE
    mouse quedaban exactamente igual de lejos, y el codigo devolvia tres
    arbitrarios presentados como si fueran los menos chinos.

    La fuente distingue dos hechos -pais de la marca y pais de fabricacion-, asi
    que ese empate es REAL. La respuesta honesta no es inventar un gradiente mas
    fino para que salga un ganador: es decir el empate y desempatar por un
    criterio declarado. Un orden que la ficha no respalda es alucinacion."""
    r = H.buscar_productos(
        H.BuscarProductos(categoria="mouse", filtros=[
            {"campo": "pais_fabricacion", "operador": "no_contiene",
             "valor": "china"},
            {"campo": "marca", "operador": "no_contiene",
             "valor": "logitech"}]), TIENDA)
    assert r["estado"] == "ninguno_cumple_del_todo"
    assert r["empatados_igual_de_cerca"] > len(r["productos"])
    assert r["desempate"], "el criterio de desempate se declara"
    # el empate viaja ESCRITO en el bloque que el modelo pega, no como un dato
    # suelto que tenga que acordarse de mencionar
    assert "igual de cerca" in r["bloque"]
    # el desempate declarado es el precio: de menor a mayor entre los empatados
    precios = [p["precio_ars"] for p in r["productos"]]
    assert precios == sorted(precios)


def test_la_exclusion_por_origen_filtra_de_verdad():
    """El filtro viejo tomaba los primeros 4 caracteres de la FRASE entera: con
    'partes chinas' buscaba 'part' y no matcheaba nunca. Ahora son las raices de
    cada palabra, y viven en el operador `no_contiene`."""
    con_filtro = H.buscar_productos(
        H.BuscarProductos(categoria="mouse", cuantos=6, filtros=[
            {"campo": "origen", "operador": "no_contiene",
             "valor": "partes chinas"}]), TIENDA)
    if con_filtro["estado"] == "encontrado":
        for p in con_filtro["productos"]:
            assert "chin" not in str(p.get("origen", "")).lower()


def test_el_presupuesto_maximo_es_una_condicion_mas():
    """Un tope imposible NO es lo mismo que no tener el producto: se ofrece lo
    mas cercano real. Con la categoria vacia, en cambio, el veredicto es
    no_encontrado: si no, el modelo dice que es cuestion de plata cuando en
    realidad no tenemos el rubro.

    5-ago: `tope_precio` dejo de ser un argumento propio. Era la segunda de las
    cuatro puertas y es exactamente `precio_ars menor X`, con la ventaja de que
    ahora se puede combinar con cualquier otra condicion en la misma llamada."""
    r = H.buscar_productos(
        H.BuscarProductos(categoria="notebook", filtros=[
            {"campo": "precio_ars", "operador": "menor", "valor": "100"}]),
        TIENDA)
    assert r["estado"] == "ninguno_cumple_del_todo"
    assert r["productos"], "nunca se devuelve vacio"
    vacia = H.buscar_productos(
        H.BuscarProductos(categoria="lavarropas", filtros=[
            {"campo": "precio_ars", "operador": "menor", "valor": "100"}]),
        TIENDA)
    assert vacia["estado"] in ("no_encontrado", "no_vendemos")


def test_el_orden_por_defecto_es_la_relevancia_no_el_precio():
    """LA FALLA MAS CARA DEL SISTEMA, medida el 5-ago. `descripcion` se usaba
    para UNA sola cosa, el certificador de identidad. Si no certificaba un
    modelo puntual se descartaba ENTERA y el resultado salia de ordenar por
    precio, que era el unico criterio de orden que existia en todo el sistema.

    Medido: "notebook para diseño grafico que le dure años" devolvia las TRES
    MAS BARATAS de 171, y "mouse gamer inalambrico" devolvia el Genius de
    $8.500 con cable. Las palabras del cliente no tocaban un solo campo, con
    `tags`, `descripcion_rica` y `uso_recomendado` llenos en 880 de 880."""
    baratos = H.buscar_productos(
        H.BuscarProductos(categoria="teclado", cuantos=3), TIENDA)
    con_desc = H.buscar_productos(
        H.BuscarProductos(categoria="teclado", cuantos=3,
                          descripcion="teclado inalambrico"), TIENDA)
    assert baratos["ordenados_por"].startswith("precio")
    assert con_desc["ordenados_por"] == "lo que mas se parece a lo que pidio"
    assert [p["id"] for p in con_desc["productos"]] != \
           [p["id"] for p in baratos["productos"]], \
        "la descripcion tiene que cambiar el orden, no ser decorativa"
    # y lo que trae es lo que el cliente pidio, no lo mas barato
    for p in con_desc["productos"]:
        assert "inalambr" in str(p.get("specs", {}).get("conexion", "")).lower()


def test_cuando_la_prosa_no_discrimina_se_cae_al_precio_Y_SE_DICE():
    """El limite honesto de la relevancia, medido sobre la fuente real: los 171
    notebooks tienen el MISMO `uso_recomendado` -"Trabajo y estudio"-, los
    mismos tags y la misma descripcion salvo el modelo. Ante "notebook para
    diseño grafico que le dure años" ninguna palabra separa a una de otra,
    porque lo que las diferencia es estructurado -ram, procesador, precio-, no
    esta en la prosa.

    Ahi el codigo NO puede elegir y no tiene que fingir que eligio: cae al
    precio y lo DICE en `ordenados_por`. Sin ese aviso el modelo presenta las
    tres mas baratas como si fueran las mejores para diseñar, que es la
    alucinacion exacta que se midio el 5-ago. Con el aviso, el modelo sabe que
    para responder bien tiene que pedir `ordenar_por ram` o una condicion."""
    r = H.buscar_productos(
        H.BuscarProductos(categoria="notebook", cuantos=3,
                          descripcion="notebook para diseño grafico que le "
                                      "dure años"), TIENDA)
    assert r["ordenados_por"].startswith("precio")
    # y la puerta para contestarla bien EXISTE: es el orden por un campo real
    mejor = H.buscar_productos(
        H.BuscarProductos(categoria="notebook", cuantos=3,
                          ordenar_por="ram", direccion="max"), TIENDA)
    assert mejor["ordenados_por"] == "ram max"
    assert mejor["productos"][0]["id"] != r["productos"][0]["id"]


def test_se_ordena_por_cualquier_campo_no_solo_por_precio():
    """"El mas liviano" no tenia llamada posible: `orden` aceptaba barato o
    caro y nada mas, con `ordenar_por` y `atributos_ordenables` escritos en
    fuente_producto desde el interprete que murio el 1-ago y sin ninguna
    herramienta que los expusiera. Diez atributos ordenables derivados de la
    fuente, cero puertas."""
    r = H.buscar_productos(
        H.BuscarProductos(categoria="mouse", cuantos=3,
                          ordenar_por="peso_gramos", direccion="min"), TIENDA)
    assert r["estado"] == "encontrado"
    assert r["ordenados_por"] == "peso_gramos min"
    pesos = [p["peso_gramos"] for p in r["productos"]]
    assert pesos == sorted(pesos)
    # y el mas pesado es el mismo mecanismo con la direccion al reves
    caro = H.buscar_productos(
        H.BuscarProductos(categoria="mouse", cuantos=3,
                          ordenar_por="garantia_meses", direccion="max"),
        TIENDA)
    garantias = [p["garantia_meses"] for p in caro["productos"]]
    assert garantias == sorted(garantias, reverse=True)


# ── LA POLITICA CON SUS NUMEROS REALES ───────────────────────────────────────
def test_la_politica_vuelve_con_los_valores_estampados():
    """El texto es el que escribio Martin; los numeros los pone el codigo desde
    los valores estructurados del mismo tema. Sin esto el modelo teje el numero
    de memoria, que es de donde salio el 10 por ciento puesto donde iba el 80."""
    r = H.ejecutar("consultar_temas",
                   {"temas": ["descuento_transferencia"]}, TIENDA)
    t = r["temas"][0]
    assert t["estado"] == "encontrado"
    assert "{{" not in t["politica"]
    assert t["politica"].strip()


def test_un_tema_que_no_existe_no_inventa_politica():
    r = H.ejecutar("consultar_temas", {"temas": ["descuento_secreto"]}, TIENDA)
    assert r["temas"][0]["estado"] == "no_encontrado"


def test_un_tema_compartido_vuelve_con_LAS_DOS_MITADES():
    """EL BUG QUE PARIO LA FUSION (4-ago). `descuento_transferencia` estaba en
    los dos enums: por `consultar_politica` traia el diez por ciento real y por
    `consultar_criterio` una prosa sin un solo digito que literalmente dice que
    el numero lo trae la otra. El modelo elegia un area y contestaba con la
    mitad que le tocaba. Ahora un tema es UN tema y vuelve entero."""
    r = H.ejecutar("consultar_temas",
                   {"temas": ["descuento_transferencia"]}, TIENDA)
    t = r["temas"][0]
    assert t.get("politica") and t.get("criterio"), (
        "el tema compartido tiene que traer politica Y criterio en una sola "
        "llamada, que es el punto entero de la fusion")
    assert any(v.get("monto") for v in (t.get("valores") or [])), (
        "el numero real es lo que la mitad de criterio no puede tener")


def test_varias_preguntas_se_contestan_en_UNA_llamada():
    """Medido con el modelo vivo el 4-ago: ante "hacen envios al exterior?
    cuanto tarda a uruguay y cuanto sale" pidio UN tema y contesto una de las
    tres. Con un tema por llamada, pedir tres era pedir tres herramientas."""
    r = H.ejecutar("consultar_temas",
                   {"temas": ["envio_exterior", "plazo_envio", "costo_envio"]},
                   TIENDA)
    assert [t["tema"] for t in r["temas"]] == ["envio_exterior", "plazo_envio",
                                               "costo_envio"]
    assert all(t["estado"] == "encontrado" for t in r["temas"])


# ── LA CUENTA ────────────────────────────────────────────────────────────────
def _dos_productos():
    r = H.buscar_productos(H.BuscarProductos(categoria="mouse", cuantos=2),
                           TIENDA)
    assert r["estado"] == "encontrado", r
    return [p["id"] for p in r["productos"]]


def test_el_presupuesto_vuelve_como_bloque_ya_escrito():
    ids = _dos_productos()
    r = H.armar_presupuesto(H.ArmarPresupuesto(
        items=[H.ItemPedido(product_id=ids[0], cantidad=2)]), TIENDA)
    assert r["estado"] == "ok"
    assert "Presupuesto:" in r["bloque"] and "Total:" in r["bloque"]
    assert isinstance(r["total_ars"], (int, float))


def test_cobra_un_envio_por_destino():
    ids = _dos_productos()
    uno = H.armar_presupuesto(H.ArmarPresupuesto(
        items=[H.ItemPedido(product_id=ids[0], cantidad=1)],
        destinos=["Cordoba"]), TIENDA)
    tres = H.armar_presupuesto(H.ArmarPresupuesto(
        items=[H.ItemPedido(product_id=ids[0], cantidad=1)],
        destinos=["Cordoba", "Concordia", "Posadas"]), TIENDA)
    assert tres["total_ars"] >= uno["total_ars"]


def test_el_reparto_que_no_cierra_no_sale():
    """El modelo a veces resuelve mal "el resto" y reparte mas unidades de las
    que hay. Si el reparto no cierra contra los items, no se muestra: mejor sin
    detalle que con un detalle que contradice la cuenta."""
    ids = _dos_productos()
    r = H.armar_presupuesto(H.ArmarPresupuesto(
        items=[H.ItemPedido(product_id=ids[0], cantidad=2, destino="Cordoba"),
               H.ItemPedido(product_id=ids[1], cantidad=1)],
        destinos=["Cordoba", "Posadas"]), TIENDA)
    assert "Reparto de los envios" not in r["bloque"]


def test_el_reparto_que_cierra_sale_con_su_detalle():
    ids = _dos_productos()
    r = H.armar_presupuesto(H.ArmarPresupuesto(
        items=[H.ItemPedido(product_id=ids[0], cantidad=1, destino="Cordoba"),
               H.ItemPedido(product_id=ids[1], cantidad=1, destino="Posadas")],
        destinos=["Cordoba", "Posadas"]), TIENDA)
    assert "Reparto de los envios" in r["bloque"]


def test_el_split_de_pago_llega_al_bloque():
    ids = _dos_productos()
    r = H.armar_presupuesto(H.ArmarPresupuesto(
        items=[H.ItemPedido(product_id=ids[0], cantidad=2)],
        pago=[H.PartePago(medio="mercado pago", porcentaje=20),
              H.PartePago(medio="transferencia", porcentaje=80)]), TIENDA)
    assert "80%" in r["bloque"] or "transferencia" in r["bloque"].lower()


# ── LA UNICA REGLA QUE MIRA LA SALIDA ────────────────────────────────────────
def test_la_plata_del_bloque_queda_respaldada_y_la_inventada_no():
    ids = _dos_productos()
    r = H.armar_presupuesto(H.ArmarPresupuesto(
        items=[H.ItemPedido(product_id=ids[0], cantidad=2)]), TIENDA)
    respaldados = H.montos_respaldados([r])
    total = int(r["total_ars"])
    assert not H.plata_inventada(f"Te queda en ${total:,}".replace(",", "."),
                                 respaldados)
    assert H.plata_inventada("Te lo dejo en $999.111", respaldados) == [999111]


def test_los_numeros_chicos_no_son_plata():
    """12 meses de garantia, 8GB, 2 unidades. Podar por cualquier digito fue el
    bug que borraba respuestas de spec en silencio."""
    assert H.plata_inventada("Tiene 12 meses de garantia y 8 GB", set()) == []


def test_la_spec_grande_con_su_unidad_tampoco_es_plata():
    """1600 DPI y 3200 MHz son numeros de cuatro digitos y NO son plata. Es la
    contracara del test de arriba: la regla tiene que ver la plata sin signo
    pero no puede comerse una spec, o vuelve a borrar dato real."""
    texto = "El mouse tiene 1600 DPI y la RAM es DDR4 3200 MHz, 16 GB."
    assert H.plata_inventada(texto, set()) == []


def test_la_plata_sin_signo_tambien_se_ve():
    """Primera corrida viva del camino nuevo: el modelo escribio "8500 ARS" y
    "6500 pesos". Con la regla mirando solo el signo peso, una cifra inventada
    sin signo salia derecho al cliente."""
    assert H.plata_inventada("Te lo dejo en 7400 pesos", {8500}) == [7400]
    assert H.plata_inventada("Sale 9300 ARS", {8500}) == [9300]
    assert H.plata_inventada("Sale 8500 pesos", {8500}) == []


def test_un_ano_no_es_un_monto():
    assert H.plata_inventada("La garantia corre hasta 2027", set()) == []


def test_el_precio_viaja_ya_escrito_para_que_el_modelo_lo_copie():
    r = H.buscar_productos(H.BuscarProductos(categoria="mouse", cuantos=1),
                           TIENDA)
    p = r["productos"][0]
    assert p["precio"].startswith("$") and "." in p["precio"]


def test_el_envio_contesta_con_estado_y_costo_escrito():
    r = H.ejecutar("cotizar_envio", {"localidad": "Concordia"}, TIENDA)
    assert r["estado"] in ("ok", "no_se_pudo")
    if r["estado"] == "ok":
        assert r["costo"].startswith("$")


# ── EL MOLDE COMO CANDADO ────────────────────────────────────────────────────
def test_un_argumento_fuera_de_molde_no_llega_a_la_funcion():
    """Pydantic valida antes de que nada toque plata. Un pedido mal formado
    vuelve como estado, no como excepcion que se lleva el turno."""
    assert H.validar("armar_presupuesto", {"items": "dos mouse"}) is None
    r = H.ejecutar("armar_presupuesto", {"items": "dos mouse"}, TIENDA)
    assert r["estado"] == "pedido_mal_formado"


def test_una_herramienta_que_no_existe_no_rompe_el_turno():
    assert H.ejecutar("hacer_descuento", {}, TIENDA)["estado"] == \
        "herramienta_desconocida"


def test_el_contexto_va_por_herramienta_y_no_se_pisa():
    """Un dict plano pisaria las claves entre herramientas: el no_encontrado de
    una taparia el resultado de la otra. Es el bug del `.update` del esquema
    original."""
    ctx = H.contexto_json([
        {"herramienta": "buscar_productos", "pedido": {}, "resultado":
            {"estado": "no_encontrado"}},
        {"herramienta": "consultar_temas", "pedido": {}, "resultado":
            {"estado": "encontrado", "politica": "Envio gratis"}}])
    assert "no_encontrado" in ctx and "Envio gratis" in ctx


def test_para_cerrar_solo_se_pide_el_nombre():
    """Charla real del 1-ago: el bot pidio nombre completo, DNI y una direccion
    por destino en el PRIMER mensaje. El DNI nunca estuvo en la lista, se lo
    invento el modelo; y de la lista salieron telefono, direccion y forma de
    pago, que se coordinan despues y no pueden frenar la venta."""
    from app.core.cierre import CAMPOS_REQUERIDOS, CAMPOS_EXTRAIBLES, faltantes
    assert CAMPOS_REQUERIDOS == ["nombre"]
    assert "dni" not in CAMPOS_EXTRAIBLES
    assert faltantes({"nombre": "Martin"}) == []
    # los opcionales se siguen guardando si el cliente los dice
    assert "direccion" in CAMPOS_EXTRAIBLES


# ── EL RAZONAMIENTO TAMBIEN VA ATADO ─────────────────────────────────────────
def test_el_criterio_de_venta_sale_de_la_fuente_y_esta_atado_por_enum():
    """El hueco que quedo al pasar a herramientas: el dato duro quedo atado y la
    prosa de criterio quedo suelta, o sea inventada por el modelo. En el repo
    viven 93 bloques escritos para esta tienda que no usaba nadie."""
    assert len(H.temas_consultables(TIENDA)) > 50
    # El modelo lo nombra con las palabras del cliente; el codigo lo certifica.
    assert H.certificar_temas(["memoria ram"], TIENDA)["temas"] == ["memoria_ram"]
    r = H.ejecutar("consultar_temas", {"temas": ["memoria_ram"]}, TIENDA)
    t = r["temas"][0]
    assert t["estado"] == "encontrado" and len(t["criterio"]) > 80


def test_un_tema_sin_criterio_no_lo_inventa():
    r = H.ejecutar("consultar_temas", {"temas": ["brujeria"]}, TIENDA)
    t = r["temas"][0]
    assert t["estado"] == "no_encontrado"
    assert "honesto" in t["instruccion"]


def test_el_criterio_de_OTRO_tema_no_se_cuela_por_parecido():
    """`consultar_guia_venta` matchea aproximado, y sobre el enum unido eso
    traia criterio ajeno: medido el 4-ago, `especificaciones` caia en
    `verificacion_pagos`, `fabricacion` en `ubicacion` y `formas_contacto` en
    `formas_pago`. Un criterio del tema equivocado es peor que ninguno, porque
    suena fundado."""
    for tema in ("especificaciones", "fabricacion", "formas_contacto"):
        t = H.ejecutar("consultar_temas", {"temas": [tema]}, TIENDA)["temas"][0]
        assert not t.get("criterio"), (
            f"{tema} se trajo criterio de otro tema por parecido de nombre")
        assert t.get("politica"), f"{tema} perdio su politica de la FAQ"


def test_no_encontrado_no_se_convierte_en_no_vendemos_la_categoria():
    """Banco repetido del 1-ago: ante "tenes memoria ram de 16gb" el bot
    contesto "no estamos vendiendo modulos de RAM sueltos", con el catalogo
    lleno de memorias. La herramienta ahora devuelve las reales de esa
    categoria para que el no sea del MODELO puntual, no del rubro."""
    r = H.buscar_productos(
        H.BuscarProductos(descripcion="memoria ram de 16gb"), TIENDA)
    if r["estado"] == "no_encontrado":
        assert r.get("hay_en_la_categoria"), r
        assert "NO digas que no vendemos el rubro" in r["instruccion"]


def test_una_correccion_del_pedido_no_es_un_no_a_la_venta():
    """Banco repetido, cuarta tanda: "no, el teclado sacalo, dejame solo los
    mouse" arranca con "no" y es lo contrario a un rechazo. El cierre lo leia
    como desinteres, le avisaba al dueño que el lead estaba tibio, y le pegaba
    al cliente "cuando quieras retomar, aca estoy" abajo del presupuesto que le
    acababa de pasar."""
    from app.core.cierre import es_no_interesado
    assert not es_no_interesado("no, el teclado sacalo, dejame solo los mouse")
    assert not es_no_interesado("no, mejor agregame dos mouse")
    # los NO de verdad siguen siendo no
    assert es_no_interesado("no gracias")
    assert es_no_interesado("no por ahora")
    assert es_no_interesado("lo voy a pensar")


def test_todos_los_campos_de_la_ficha_existen_en_la_fuente(firestore_doble):
    """EL BUG DEL 3-ago. `_CAMPOS_FICHA` pedia "garantia", "medidas" y
    "caracteristicas", que en la fuente se llaman garantia_meses, dimensiones y
    caracteristicas_extra. `_ficha` descarta con `if prod.get(k)` cualquier
    nombre que no exista, asi que los tres se caian EN SILENCIO y el modelo
    nunca vio esos datos. Un campo mal escrito no se puede volver a colar."""
    from app.core.herramientas import _CAMPOS_FICHA
    from app.storage.firestore_client import get_all_products

    productos = get_all_products(tienda_id="verifika_prod") or []
    assert productos, "el doble tiene que traer el catalogo real"
    # La union de claves sobre una muestra amplia: un campo puede venir vacio en
    # un producto suelto y existir igual en la fuente.
    reales = set()
    for p in productos[:200]:
        reales |= set(p.keys())
    inventados = [c for c in _CAMPOS_FICHA if c not in reales]
    assert not inventados, (
        f"campos pedidos que NO existen en la fuente: {inventados}. "
        f"Se descartarian en silencio. Disponibles: {sorted(reales)}")


def test_la_ficha_lleva_los_datos_comparables(firestore_doble):
    """Peso, medidas, color y garantia tienen que viajar como CAMPO, no sueltos
    adentro de la prosa: si no, el modelo no los puede comparar entre productos
    y termina razonando de su cabeza sobre datos que tenemos."""
    from app.core.herramientas import _ficha
    from app.storage.firestore_client import get_all_products

    p = get_all_products(tienda_id="verifika_prod")[0]
    f = _ficha(p, "verifika_prod")
    for campo in ("peso_gramos", "dimensiones", "color", "garantia_meses"):
        assert campo in f, f"{campo} no llega al modelo"


# ── EL RUBRO QUE DIJO EL CLIENTE, Y EL MODELO QUE NO EXISTE ──────────────────
# Cuatro fallas medidas el 5-ago-2026 sobre las 40 pruebas de Martin. Las cuatro
# eran del certificador, y las cuatro se veian como un error del modelo.
def test_el_rubro_nombrado_acota_la_busqueda():
    """'tenes memoria ram de 16gb' devolvia NOTEBOOKS: '16gb' esta en el nombre
    de las notebooks, y el rubro que el cliente dijo se tiraba. El nombre del
    rubro no sirve para elegir un modelo, pero si para saber en que estante
    buscar."""
    r = H.buscar_productos(H.BuscarProductos(descripcion="memoria ram de 16gb"),
                           TIENDA)
    devueltos = (r.get("productos") or []) + (r.get("hay_en_la_categoria") or [])
    assert devueltos
    assert {p["categoria"] for p in devueltos} == {"memoria ram"}


def test_la_tablet_no_devuelve_un_monitor():
    """Charla real del 24-jul: 'decime precio de tablet samsung' traia el
    Monitor Samsung Odyssey."""
    r = H.buscar_productos(H.BuscarProductos(descripcion="tablet samsung"),
                           TIENDA)
    assert {p["categoria"] for p in (r.get("productos") or [])} == {"tablet"}


def test_el_modelo_que_no_existe_no_se_confirma():
    """Piden la Asus ROG Strix G15 y tenemos la G16. Confirmarla es inventarle
    stock y specs a un producto ajeno, que es la falla numero uno de la
    consigna. Y un no pelado tira la venta teniendo la linea en gondola."""
    r = H.buscar_productos(
        H.BuscarProductos(descripcion="notebook Asus ROG Strix G15"), TIENDA)
    assert r["estado"] == "no_encontrado"
    linea = r.get("hay_en_la_categoria") or []
    assert linea and all("g15" not in p["nombre"].lower() for p in linea)
    assert all(p["categoria"] == "notebook" for p in linea)


def test_la_charla_del_cliente_no_rompe_la_identidad():
    """El esquema pide la descripcion 'tal cual la dijo el cliente', asi que
    entra con verbos: 'quiero una notebook asus' daba not_found mientras
    'notebook asus' daba ambiguo. La palabra que no existe en ningun producto no
    distingue nada."""
    r = H.buscar_productos(
        H.BuscarProductos(descripcion="quiero una notebook asus"), TIENDA)
    assert r["estado"] == "ambiguo"
    assert {p["categoria"] for p in r["productos"]} == {"notebook"}


def test_una_palabra_corta_no_certifica_un_producto():
    """La contracara de la regla de arriba: en 'un regalo para mi viejo' queda
    'mi', que es la linea Mi de Xiaomi, y devolvia un cargador como si el
    cliente lo hubiera pedido."""
    r = H.buscar_productos(
        H.BuscarProductos(descripcion="un regalo para mi viejo que labura en "
                                      "el campo"), TIENDA)
    assert r["estado"] == "no_encontrado"
    assert r.get("categorias_que_vendemos")


def test_el_cliente_escribe_como_habla():
    """'qiero un mause', 'tenes auris tmbn': si el codigo no reconoce el rubro,
    la busqueda vuelve vacia y no hay prompt que lo arregle."""
    from app.core.guia_pedido import categorias_nombradas
    assert categorias_nombradas("qiero un mause barato", TIENDA) == ["mouse"]
    assert categorias_nombradas("tenes auris tmbn", TIENDA) == ["auriculares"]


def test_que_productos_tenes_tiene_puerta():
    """La pregunta mas comun de todas -'que vendes', 'pasame el catalogo'- no
    tenia forma de contestarse con dato: `valores campo=categoria` volvia
    campo_desconocido y la lista la ponia el modelo de memoria."""
    from app.storage.firestore_client import get_all_products
    r = H.consultar_catalogo(
        H.ConsultarCatalogo(operacion="valores", campo="categoria"), TIENDA)
    reales = {p["categoria"] for p in get_all_products(tienda_id=TIENDA)
              if (p.get("stock") or 0) > 0}
    assert r["estado"] == "ok"
    assert r["cuantos_distintos"] == len(reales)
    # LA PUERTA YA NO LA ABRE EL MODELO (FICHA 06): `consultar_catalogo` dejo de
    # ser visible y esta consulta la deriva el codigo cuando el cliente pregunta
    # si tenemos algo y la busqueda vuelve sin nada. Lo que se prueba aca es que
    # la herramienta contesta con el numero real; que se llame sola lo prueba
    # `test_hub_venta.py`.


def test_la_tablet_del_cliente_es_un_equipo_conocido():
    """'lo enchufo a mi tablet' devolvia equipo_desconocido con 27 tablets en
    el catalogo. Se contesta desde la ficha, y si la ficha no lo dice, sin_dato
    honesto."""
    from app.storage.firestore_client import get_all_products
    ssd = next(p for p in get_all_products(tienda_id=TIENDA)
               if p["categoria"] == "ssd" and (p.get("stock") or 0) > 0)
    r = H.ejecutar("ver_compatibilidad",
                   {"product_id": ssd["id"], "equipo": "mi tablet"}, TIENDA)
    assert r["estado"] == "ok"
    veredictos = [c["veredicto"] for c in r["compatibilidad"]]
    assert veredictos and all(
        v in ("compatible", "incompatible", "sin_dato") for v in veredictos)


def test_el_hueco_de_idioma_queda_anotado():
    """El codigo no razona: acumula. Lo que no pudo llevar ni a un producto ni a
    un rubro queda con las palabras del cliente, para que la proxima sesion
    arranque de la lista y no de leer una charla a mano."""
    from app.core import huecos
    huecos.limpiar()
    H.buscar_productos(
        H.BuscarProductos(descripcion="tenes un joystick inalambrico"), TIENDA)
    res = [h for h in huecos.resumen(TIENDA) if h["tipo"] == "sin_rubro"]
    assert res and res[0]["ejemplos"]


# ── EL NULL QUE EL MOLDE PEDIA Y RECHAZABA (9-ago-2026) ──────────────────────
# La redaccion coloquial de la pregunta de Martin daba 8 sobre 100 en las TRES
# corridas: `registrar_pedido` volvia `pedido_mal_formado` y el turno se caia
# entero, sin cuenta y sin la pregunta por el teclado. No era la redaccion: el
# modelo mandaba `medio: null` porque la descripcion del campo se lo pedia, y
# el tipo aceptaba la cadena vacia pero no el null.

def test_el_pedido_con_medio_en_null_se_registra():
    """LOS ARGUMENTOS SON LOS REALES, copiados del log de la corrida viva del
    9-ago -trace dcf5dda0-. Si este test se pone rojo, volvio el turno mudo."""
    args = {
        "items": [{"que": "auriculares", "cantidad": 2},
                  {"que": "mouse", "cantidad": 2},
                  {"que": "memorias ram", "cantidad": 2},
                  {"que": "teclado", "cantidad": 1}],
        "restricciones": ["menor cantidad de partes chinas posible"],
        "destinos": ["Córdoba Capital", "Concordia", "Posadas"],
        "pide_precio": True,
        "reparto_pago": [{"porcentaje": 70, "medio": None},
                         {"porcentaje": 30, "medio": None}],
    }
    r = H.ejecutar("registrar_pedido", args, TIENDA)
    assert r["estado"] == "registrado"
    # y el reparto llega entero, que es lo que despues repone el codigo
    partes = r["pedido"]["reparto_pago"]
    assert [p["porcentaje"] for p in partes] == [70, 30]
    assert all(p["medio"] == "" for p in partes)


def test_ningun_molde_se_rompe_con_un_null_en_un_campo_con_default():
    """EL BARRIDO, y es lo que convierte el arreglo en experiencia.

    Arreglar `medio` a mano tapaba ESTE caso y dejaba viva la clase entera: hoy
    hay 9 moldes y cualquiera de ellos vuelve a tirar el turno si el modelo
    manda null en un campo que tiene default. Un campo con default no se rompe
    porque llegue null: null ahi significa 'no lo dije', que es justo lo que el
    default resuelve. El barrido lo prueba en TODOS los moldes, incluidos los
    que se agreguen despues de esta sesion."""
    def _relleno(modelo):
        """Lo minimo que el molde exige, para que la unica cosa que se este
        midiendo sea el null y no un campo que falta."""
        fuera = {}
        for campo, info in modelo.model_fields.items():
            if not info.is_required():
                continue
            hijo = H._submodelo(info.annotation)
            uno = _relleno(hijo) if hijo is not None else "x"
            if hijo is None and info.annotation in (int, float):
                uno = 1
            fuera[campo] = [uno] if "list" in str(info.annotation) else uno
        return fuera

    for nombre, modelo in H._MOLDES.items():
        base = _relleno(modelo)
        for campo, info in modelo.model_fields.items():
            if info.is_required() or info.get_default() is None:
                continue
            assert H.validar(nombre, {**base, campo: None}) is not None, (
                f"{nombre}.{campo} tira el turno entero con null")
        # y un renglon adentro de cada submodelo, que es donde estaba el de hoy
        for campo, info in modelo.model_fields.items():
            hijo = H._submodelo(info.annotation)
            if hijo is None:
                continue
            nulos = {c: None for c, i in hijo.model_fields.items()
                     if not i.is_required() and i.get_default() is not None}
            if not nulos:
                continue
            renglon = {**_relleno(hijo), **nulos}
            assert H.validar(nombre, {**base, campo: [renglon]}) is not None, \
                f"{nombre}.{campo}[] tira el turno con null"


# ── LA CAUSA DE LA REPETICION QUE VIO MARTIN (15-ago-2026) ──────────────────
def test_el_dato_igual_en_todas_las_fichas_viaja_una_sola_vez(firestore_doble):
    """LA CAUSA, y no era del modelo. Al cliente le llego "La garantia es de 120
    meses por defectos de fabricacion" TRES VECES, una por producto. El modelo
    hizo lo que se le pidio: `buscar_productos` devolvia las fichas y CADA UNA
    traia pegada la misma politica de garantia entera. En un resultado de 3.127
    caracteres la garantia viajaba 15 veces.

    Se estaba tapando en la SALIDA, borrando las oraciones repetidas despues de
    escritas. Eso es limpiar el sintoma: el codigo generaba la repeticion y otra
    pieza la barria. Se corta en el origen, que es donde ademas es gratis."""
    r = H.ejecutar("buscar_productos", {"categoria": "memoria ram"}, TIENDA)
    prods = r.get("productos") or []
    assert len(prods) >= 2, "hace falta mas de un producto para medir esto"

    comunes = r.get("igual_en_todos") or {}
    assert "garantia_detalle" in comunes, (
        "la politica de garantia sigue viajando pegada a cada ficha: "
        f"factorizado={sorted(comunes)}")
    # y NO quedo ademas en cada producto: una vez es una vez
    assert not any("garantia_detalle" in p for p in prods)
    # el hecho sigue estando, no se perdio
    assert "120" in str(comunes.get("garantia_detalle", "")) or \
           comunes.get("garantia_meses") == 120


def test_lo_que_identifica_y_cobra_nunca_se_factoriza(firestore_doble):
    """El otro lado, que es donde esto se vuelve peligroso: el precio, el stock
    y el nombre se leen ficha por ficha -la regla de la plata y el certificador-.
    Dos productos al mismo precio NO pueden compartir un precio 'comun'."""
    r = H.ejecutar("buscar_productos", {"categoria": "mouse"}, TIENDA)
    comunes = r.get("igual_en_todos") or {}
    for prohibido in ("id", "nombre", "precio", "precio_ars", "stock"):
        assert prohibido not in comunes, f"se factorizo {prohibido}"
    for p in (r.get("productos") or []):
        assert "nombre" in p and "precio" in p


def test_con_un_solo_producto_no_se_factoriza_nada(firestore_doble):
    """Sin dos fichas no hay repeticion que sacar, y mover el dato a otra clave
    seria cambiar la forma del resultado sin ganar nada."""
    r = H.ejecutar("buscar_productos",
                   {"descripcion": "Kingston Fury Beast DDR4 3200 8GB Negro"},
                   TIENDA)
    if len(r.get("productos") or []) == 1:
        assert "igual_en_todos" not in r
