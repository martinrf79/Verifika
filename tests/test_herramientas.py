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
    """La unica atadura que queda del lado del modelo: no puede pedir una
    categoria que no vendemos ni un tema de politica que no existe. Los enums
    salen del catalogo y de la FAQ, no de una lista escrita a mano que despues
    diverge."""
    esq = {e["function"]["name"]: e["function"]["parameters"]
           for e in H.esquemas(TIENDA)}
    cats = esq["buscar_productos"]["properties"]["categoria"]["enum"]
    temas = esq["consultar_temas"]["properties"]["temas"]["items"]["enum"]
    assert len(cats) > 5 and len(temas) > 20
    assert "heladeras" not in cats
    assert "descuento_transferencia" in temas


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

    ACTUALIZADO 4-ago: el estado dejo de llamarse `ninguno_cumple_del_todo` y la
    instruccion dejo de arrancar por el negativo, porque ERA ELLA la que
    escribia el muro: decia "hay que decirlo derecho, sin adornar" y el modelo
    generalizaba al catalogo entero. "Lo que menos X tenga" no es un filtro, es
    un RANKING. Ordenar siempre devuelve un primero y NUNCA puede producir un
    muro."""
    r = H.buscar_productos(
        H.BuscarProductos(categoria="mouse", excluir=["mouse", "gaming",
                                                      "china", "taiwan",
                                                      "estados", "suiza"]),
        TIENDA)
    assert r["estado"] in ("ordenados_de_menos_a_mas", "encontrado")
    if r["estado"] == "ordenados_de_menos_a_mas":
        # Con algo para ofrecer, EN ORDEN, y con el grado de cada uno.
        assert r["productos"]
        assert all("cuanto_incumple" in p for p in r["productos"])
        grados = [p["cuanto_incumple"] for p in r["productos"]]
        assert grados == sorted(grados), "el que menos incumple va primero"
        # y la instruccion prohibe el universal, que es de donde salia el muro
        assert "catalogo entero" in r["instruccion"]


def test_la_exclusion_por_origen_filtra_de_verdad():
    """El filtro viejo tomaba los primeros 4 caracteres de la FRASE entera: con
    'partes chinas' buscaba 'part' y no matcheaba nunca. Ahora son las raices de
    cada palabra."""
    sin_filtro = H.buscar_productos(
        H.BuscarProductos(categoria="mouse", cuantos=6), TIENDA)
    con_filtro = H.buscar_productos(
        H.BuscarProductos(categoria="mouse", cuantos=6,
                          excluir=["partes chinas"]), TIENDA)
    if con_filtro["estado"] == "encontrado" and sin_filtro["estado"] == "encontrado":
        for p in con_filtro["productos"]:
            assert "chin" not in str(p.get("origen", "")).lower()


def test_nada_dentro_del_presupuesto_ofrece_lo_mas_cercano():
    """Un tope imposible NO es lo mismo que no tener el producto: se ofrece lo
    mas cercano real. Con la categoria vacia, en cambio, el veredicto es
    no_encontrado: si no, el modelo dice que es cuestion de plata cuando en
    realidad no tenemos el rubro."""
    r = H.buscar_productos(
        H.BuscarProductos(categoria="notebook", tope_precio=100), TIENDA)
    assert r["estado"] == "nada_dentro_del_presupuesto"
    assert r["lo_mas_cercano"]
    vacia = H.buscar_productos(
        H.BuscarProductos(categoria="lavarropas", tope_precio=100), TIENDA)
    assert vacia["estado"] in ("no_encontrado", "no_vendemos")


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
    esq = {e["function"]["name"]: e["function"]["parameters"]
           for e in H.esquemas(TIENDA)}
    criterios = esq["consultar_temas"]["properties"]["temas"]["items"]["enum"]
    assert len(criterios) > 50
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
