"""
AREA: EL INDICE DEL TURNO, el nexo entre lo interpretado y lo respondido.

Nace del pedido de Martin del 9-ago, que venia repitiendo hace sesiones: cada
punto que se interpreta de la pregunta tiene que tener su id, y la respuesta
tiene que contestar a ESE punto. La interpretacion entiende 100 y la respuesta
se cae igual, porque entre las dos no habia nadie mirando.

Los casos son el mensaje REAL que le llego a Martin por WhatsApp el 9-ago y su
version completa, para que el test mida las dos direcciones: que marque lo que
falta, y que NO marque cuando esta todo dicho. Un indice que marca en falso es
peor que no tener indice.
"""
from app.core import indice_turno as IT


def _del_cliente(faltan: list) -> list:
    """Los ids de los puntos QUE PIDIO EL CLIENTE, sin el punto de oferta.

    LA OFERTA ES DEL BOT, NO DEL CLIENTE (FICHA 15). Este archivo mide una sola
    cosa —que el ANCLAJE ate lo interpretado con lo respondido— y el punto de
    oferta no se ancla ni sale de lo declarado: se abre por codigo cuando una
    herramienta trajo un producto que el pedido no tiene. Dejarlo entrar en
    estas cuentas mezclaria dos varas distintas en el mismo numero. Lo que la
    oferta si tiene que cumplir esta medido aparte, en
    `tests/test_punto_de_oferta.py`."""
    return [p["id"] for p in faltan if p.get("tipo") != "oferta"]

DECLARADO = {
    "items": [{"que": "auriculares", "cantidad": 2},
              {"que": "mouse", "cantidad": 2},
              {"que": "memorias ram", "cantidad": 2}],
    "restricciones": ["menor cantidad de partes chinas posible"],
    "destinos": ["Cordoba capital", "Concordia", "Posadas"],
    "contradicciones": ["Mencionaste un teclado en el envío que no estaba en "
                        "el pedido inicial."],
    "reparto_pago": [{"porcentaje": 70}, {"porcentaje": 30}],
    "pide_precio": True,
}

_INCOMPLETO = """Te comento que los componentes son de origen chino.
Presupuesto:
- 2x Auriculares Redragon: $115.000
- 2x Mouse Genius: $17.000
- 2x Memoria ram Kingston: $69.000
Total: $225.000
Pago dividido:
- transferencia (70%) - mercado pago (30%)
Reparto de los envios:
- A Córdoba capital: 1x Auriculares"""

_COMPLETO = _INCOMPLETO + """
- A Concordia: 1x Mouse
- A Posadas: 2x Memoria ram
El teclado que mencionaste no estaba en el pedido, ¿lo agrego?"""


def test_cada_punto_interpretado_tiene_su_id():
    """El pedido de Martin, textual: cada parte de la pregunta interpretada
    tiene que tener un valor con el que la respuesta se pueda atar."""
    ps = IT.puntos(DECLARADO)
    ids = [p["id"] for p in ps]
    assert ids == ["item:1", "item:2", "item:3", "condicion:1", "destino:1",
                   "destino:2", "destino:3", "duda:1", "pago:1", "precio:1"]


def test_marca_lo_que_el_mensaje_REAL_no_contesto():
    """EL MENSAJE QUE LE LLEGO A MARTIN. Cotiza los tres rubros y el pago, pero
    nombra UN destino de tres y no pregunta por el teclado. Esos tres puntos, y
    solo esos, tienen que salir marcados."""
    r = IT.cobertura(DECLARADO, _INCOMPLETO, "t")
    assert [p["id"] for p in r["faltan"]] == ["destino:2", "destino:3", "duda:1"]


def test_no_marca_nada_cuando_esta_todo_dicho():
    """LA CONTRACARA, y es la que hace usable al indice. Si marca de mas, manda
    a agregar algo que ya esta y el mensaje crece por nada: seria peor que no
    tenerlo. Ojo con la condicion: el cliente dijo "partes CHINAS" y el mensaje
    dice "origen CHINO". Es el mismo punto y no puede figurar sin atender."""
    r = IT.cobertura(DECLARADO, _COMPLETO, "t")
    assert r["faltan"] == [], [p["id"] for p in r["faltan"]]


def test_la_duda_se_atiende_PREGUNTANDO_no_nombrando():
    """Una contradiccion no se cierra nombrandola al pasar: se pregunta. Es la
    regla cero -ante lo ambiguo se pregunta- llevada al indice."""
    nombrada = _INCOMPLETO + "\nEl teclado no estaba en el pedido inicial."
    r = IT.cobertura(DECLARADO, nombrada, "t")
    assert "duda:1" in [p["id"] for p in r["faltan"]]
    con_pregunta = nombrada + " ¿Lo sumo?"
    r2 = IT.cobertura(DECLARADO, con_pregunta, "t")
    assert "duda:1" not in [p["id"] for p in r2["faltan"]]


def test_la_instruccion_nombra_el_punto_concreto():
    """Ya esta medido dos veces en este repo que una correccion generica no
    mueve al modelo: ante "te falto algo" pidio cero herramientas 3 de 3. El
    punto con su texto es una cosa sola y verificable."""
    r = IT.cobertura(DECLARADO, _INCOMPLETO, "t")
    ins = IT.instruccion(r["faltan"])
    assert "Concordia" in ins and "Posadas" in ins and "teclado" in ins
    assert IT.instruccion([]) == ""


def test_sin_pedido_declarado_el_indice_se_calla():
    """Un saludo o un gracias no tiene puntos: no hay nada que atar y no se
    inventa una obligacion."""
    r = IT.cobertura({}, "Hola, ¿en qué te ayudo?", "t")
    assert r["puntos"] == [] and r["faltan"] == []


# ── EL ANCLAJE POR EVIDENCIA (12-ago-2026) ──────────────────────────────────
#
# EL DEFECTO, medido sobre las charlas grabadas antes de tocar nada: el indice
# decia que 65 de 515 puntos no llegaban al texto final, y al leerlos uno por
# uno la MAYORIA eran falsas alarmas suyas. La causa no era un umbral: el
# vinculo entre lo interpretado y lo respondido se reconstruia al final
# comparando las PALABRAS DEL CLIENTE contra la prosa del modelo, y esas dos no
# coinciden nunca porque el modelo escribe con las suyas.
#
# EL ARREGLO es atar por identidad: cada punto se mide tambien contra su
# EVIDENCIA -el producto que devolvio la busqueda, lo que el codigo busco, el
# precio que trajo la ficha, el producto del carrito-, que el sistema conoce con
# nombre y apellido. Despues del arreglo: 5 de 515, y los cinco son el MISMO
# caso, que es real.

_BUSQUEDA_MOUSE = {
    "herramienta": "buscar_productos",
    "pedido": {"categoria": "mouse", "descripcion": "mouse inalambrico gamer barato"},
    "resultado": {"estado": "ok", "productos": [
        {"nombre": "Mouse Logitech M170 Negro", "precio": "$12.000",
         "precio_ars": 12000}]},
}


def test_el_sinonimo_del_modelo_no_deja_el_punto_sin_atender():
    """EL CASO QUE MAS SE REPETIA. El cliente pidio un mouse "para jugar" y
    "barato"; el bot contesto "es inalambrico, el fabricante lo cataloga como
    ideal para gaming" y "la opcion mas economica". Estaba contestado y figuraba
    sin atender, porque el indice buscaba las palabras JUGAR y BARATO.

    Con el anclaje no hay sinonimo que rompa nada: "Logitech M170" es
    exactamente el producto que la busqueda de ese punto devolvio."""
    declarado = {"items": [{"que": "mouse inalambrico para jugar", "cantidad": 1}],
                 "restricciones": ["para jugar", "barato"]}
    texto = ("Para lo que buscas, el Logitech M170 es la opcion mas economica. "
             "Es inalambrico y el fabricante lo cataloga como ideal para gaming.")
    sin_evidencia = IT.cobertura(declarado, texto, "t")
    assert sin_evidencia["faltan"], "el caso ya no reproduce el defecto viejo"
    con_evidencia = IT.cobertura(declarado, texto, "t",
                                 llamadas=[_BUSQUEDA_MOUSE])
    assert _del_cliente(con_evidencia["faltan"]) == []


def test_una_respuesta_correcta_que_no_nombra_ningun_producto_cuenta():
    """"De Samsung tenemos 38 modelos, de iPhone no trabajamos ninguna linea"
    contesta el punto sin listar un solo producto. Ancla lo que el codigo
    BUSCO, que es la otra mitad de la evidencia."""
    declarado = {"items": [{"que": "celulares samsung", "cantidad": 1}]}
    llamadas = [{"herramienta": "buscar_productos",
                 "pedido": {"categoria": "celulares", "descripcion": "samsung"},
                 "resultado": {"estado": "no_encontrado"}}]
    texto = ("De Samsung tenemos 38 modelos disponibles en catalogo, pero de "
             "iPhone no trabajamos ninguna linea en este momento.")
    r = IT.cobertura(declarado, texto, "t", llamadas=llamadas)
    assert r["faltan"] == []


def test_la_tercera_puerta_de_los_productos_tambien_ancla():
    """LA PLOMERIA, no la logica: cuando el modelo EXACTO no existe, las
    alternativas viajan en `hay_en_la_categoria` y no en `productos`. El mismo
    dato con otro nombre de campo, y el indice no lo veia. Es una respuesta
    correcta y frecuente: "ese SSD de 7000 MB/s no lo tenemos, pero si estos"."""
    declarado = {"items": [{"que": "ssd de 7000 MB/s", "cantidad": 1}],
                 "pide_precio": True}
    llamadas = [{"herramienta": "buscar_productos",
                 "pedido": {"categoria": "almacenamiento", "descripcion": "ssd 7000"},
                 "resultado": {"estado": "no_encontrado", "hay_en_la_categoria": [
                     {"nombre": "Ssd Kingston A400 SATA 500GB", "precio": "$28.500"}]}}]
    texto = ("No contamos con un SSD que alcance esa velocidad, pero si "
             "disponemos de otras opciones:\n- Ssd Kingston A400 SATA 500GB: $28.500")
    r = IT.cobertura(declarado, texto, "t", llamadas=llamadas)
    assert _del_cliente(r["faltan"]) == []


def test_la_memoria_es_evidencia_cuando_el_turno_no_busco_nada():
    """LA EVIDENCIA NO SIEMPRE ESTA EN ESTE TURNO. El cliente pide dos unidades
    de la notebook que venia mirando; el turno no llama a ninguna herramienta
    porque no hace falta, y hace bien. El punto se contesta igual, con lo que
    ya estaba en el carrito."""
    declarado = {"items": [{"que": "Notebook HP 245 G9 Core i5 16GB 512GB SSD Gris",
                            "cantidad": 2}]}
    carrito = [{"nombre": "Notebook HP 245 G9 Core i5 16GB 512GB SSD Gris"}]
    texto = "Registre tu interes por dos unidades de la Notebook HP 245 G9."
    assert IT.cobertura(declarado, texto, "t")["faltan"], "ya no reproduce"
    r = IT.cobertura(declarado, texto, "t", memoria=carrito)
    assert r["faltan"] == []


def test_un_producto_de_la_memoria_no_contesta_un_punto_ajeno():
    """LA ATADURA QUE HACE SEGURO AL ANCLAJE DE MEMORIA. Si cualquier producto
    visto contestara cualquier punto, el indice quedaria ciego a la omision que
    justamente tiene que ver. Solo ancla el producto que el punto NOMBRA."""
    declarado = {"items": [{"que": "teclado mecanico", "cantidad": 1}]}
    carrito = [{"nombre": "Notebook HP 245 G9 Core i5"}]
    texto = "La Notebook HP 245 G9 es una gran eleccion."
    r = IT.cobertura(declarado, texto, "t", memoria=carrito)
    assert [p["id"] for p in r["faltan"]] == ["item:1"]


def test_una_omision_de_verdad_sigue_saliendo_marcada():
    """EL CASO QUE QUEDA VIVO despues del arreglo, y es real: el cliente pide el
    precio de dos unidades y el turno contesta con una frase de venta, sin un
    solo numero y sin llamar a ninguna herramienta. Si el anclaje tapara esto,
    habriamos cambiado un indice ruidoso por uno ciego."""
    declarado = {"items": [{"que": "Notebook HP 245 G9", "cantidad": 2}],
                 "pide_precio": True}
    carrito = [{"nombre": "Notebook HP 245 G9 Core i5"}]
    texto = ("Que bueno que te interese llevarte dos unidades de la Notebook "
             "HP 245 G9. El precio ya es el mas competitivo que podemos ofrecer.")
    r = IT.cobertura(declarado, texto, "t", llamadas=[], memoria=carrito)
    assert [p["id"] for p in r["faltan"]] == ["precio:1"]


def test_el_anclaje_nunca_puede_agregar_una_alarma():
    """LA PROPIEDAD QUE HACE SEGURO EL CAMBIO ENTERO, y por eso se afirma sobre
    entradas generadas y no sobre un caso: medir con evidencia solo puede SACAR
    un punto de la lista de faltantes, nunca meter uno nuevo. Sin esto, el
    arreglo podria estar tapando un defecto en un lado y creando otro en otro."""
    import itertools

    textos = ["Te paso el Logitech M170 a $12.000.", "No tengo eso.",
              "Hola, ¿en que te ayudo?", "El mouse gamer mas economico es este."]
    declarados = [
        {"items": [{"que": "mouse inalambrico para jugar", "cantidad": 1}]},
        {"items": [{"que": "teclado", "cantidad": 2}], "pide_precio": True},
        {"restricciones": ["barato"], "items": [{"que": "mouse", "cantidad": 1}]},
    ]
    for dec, txt in itertools.product(declarados, textos):
        sin = set(_del_cliente(IT.cobertura(dec, txt, "t")["faltan"]))
        con = set(_del_cliente(IT.cobertura(
            dec, txt, "t", llamadas=[_BUSQUEDA_MOUSE],
            memoria=[{"nombre": "Teclado Genius KB-110X"}])["faltan"]))
        assert con <= sin, f"el anclaje AGREGO faltantes: {con - sin} en {txt}"


# ── EL CONTRATO NO_OMITE (pieza 3, 12-ago-2026) ─────────────────────────────

def test_el_punto_omitido_se_repone_con_la_cuenta_sellada(firestore_doble):
    """LA UNICA GUARDIA QUE SUMA, y el caso que la hizo nacer es real.

    El cliente pregunta cuanto sale llevar DOS unidades de la notebook que
    venia mirando. El turno no llama a ninguna herramienta —el producto ya esta
    certificado en el carrito— y le llega una frase de venta entera, sin un solo
    numero. Las diecisiete guardias de salida lo dejan pasar porque todas
    RESTAN: no hay nada mal escrito, hay algo que no esta."""
    from app.core.contexto_turno import set_current_tienda
    from app.core import hub_venta as HV
    from app.core import salida as SAL
    from app.storage.firestore_client import get_all_products

    set_current_tienda("verifika_prod")
    prod = next(p for p in get_all_products(tienda_id="verifika_prod")
                if p.get("stock", 0) >= 3 and p.get("precio_ars"))
    declarado = {"items": [{"que": prod["nombre"], "cantidad": 2}],
                 "pide_precio": True}
    memoria = [{"id": prod["id"], "nombre": prod["nombre"],
                "categoria": prod.get("categoria", "")}]
    sin_numero = (f"Que bueno que te interese llevarte dos unidades de la "
                  f"{prod['nombre']}. El precio ya es el mas competitivo.")

    salida = SAL._punto_omitido_repuesto(sin_numero, declarado, [], memoria,
                                        "verifika_prod", "t")
    assert "Presupuesto:" in salida and "Total:" in salida
    assert sin_numero in salida, "no se toca lo que el modelo escribio"
    assert f"{prod['precio_ars'] * 2:,}".replace(",", ".") in salida


def test_no_toca_el_mensaje_cuando_el_punto_ya_esta_contestado(firestore_doble):
    """LA CONTRACARA, y es la que evita la repeticion. Se probo reponer ANTES de
    redactar y en un turno medido la ficha ya decia "Precio: $693.000": la
    cuenta repuesta lo estampo dos veces mas, el mismo numero TRES veces en un
    mensaje. Corriendo despues, el texto ya existe y no hay nada que adivinar."""
    from app.core.contexto_turno import set_current_tienda
    from app.core import hub_venta as HV
    from app.core import salida as SAL
    from app.storage.firestore_client import get_all_products

    set_current_tienda("verifika_prod")
    prod = next(p for p in get_all_products(tienda_id="verifika_prod")
                if p.get("stock", 0) >= 3 and p.get("precio_ars"))
    declarado = {"items": [{"que": prod["nombre"], "cantidad": 1}],
                 "pide_precio": True}
    memoria = [{"id": prod["id"], "nombre": prod["nombre"],
                "categoria": prod.get("categoria", "")}]
    precio = f"{prod['precio_ars']:,}".replace(",", ".")
    con_numero = (f"La {prod['nombre']} sale ${precio}.\n"
                  f"Total: ${precio}\n¿Te la reservo?")
    assert SAL._punto_omitido_repuesto(con_numero, declarado, [], memoria,
                                      "verifika_prod", "t") == con_numero


def test_sin_nada_certificado_no_inventa_una_cuenta(firestore_doble):
    """El limite duro: si no hay un producto certificado con el que armar la
    cuenta, el mensaje sale sin numeros y no se inventa uno. Un punto sin
    contestar es honesto; un precio inventado es la falla numero uno."""
    from app.core.contexto_turno import set_current_tienda
    from app.core import hub_venta as HV
    from app.core import salida as SAL

    set_current_tienda("verifika_prod")
    declarado = {"items": [{"que": "algo que no existe", "cantidad": 2}],
                 "pide_precio": True}
    texto = "No tengo ese producto en el catalogo."
    assert SAL._punto_omitido_repuesto(texto, declarado, [], [],
                                      "verifika_prod", "t") == texto


# ── LA CONDICION QUE SE APLICA Y NO SE DECLARA (12-ago-2026) ────────────────

def test_el_filtro_aplicado_se_vuelve_restriccion_declarada():
    """EL CASO QUE MARTIN VE EN REAL: pide "las menos partes chinas posibles",
    el sistema SI lo entiende —la busqueda sale con `pais_fabricacion
    no_contiene china`— y el criterio no aparece en lo declarado. Medido con el
    banco de interpretacion: falla en 3 de 6 redacciones de la misma pregunta.

    Sin declararlo queda fuera de TODOS los controles: el reconciliador y el
    indice trabajan sobre lo declarado, asi que nadie puede exigir que se
    conteste algo que nunca se anoto."""
    from app.core.hub_venta import _restricciones_de_los_filtros

    declarado = {"items": [{"que": "memoria ram", "cantidad": 2}]}
    llamadas = [{"herramienta": "buscar_productos",
                 "pedido": {"categoria": "memoria ram",
                            "filtros": [{"campo": "pais_fabricacion",
                                         "operador": "no_contiene",
                                         "valor": "china"}]},
                 "resultado": {"estado": "ninguno_cumple_del_todo"}}]
    salida = _restricciones_de_los_filtros(declarado, llamadas, "t")
    texto = " ".join(salida["restricciones"]).lower()
    assert "china" in texto
    # y con eso el criterio ENTRA al indice como punto propio
    puntos = IT.puntos(salida)
    assert any(p["tipo"] == "condicion" and "china" in p["termino"].lower()
               for p in puntos)


def test_no_duplica_una_restriccion_que_el_modelo_ya_declaro():
    """Si el modelo la declaro bien, no se agrega una segunda copia con otras
    palabras: seria el mismo punto contado dos veces y el indice pediria que se
    conteste dos veces."""
    from app.core.hub_venta import _restricciones_de_los_filtros

    declarado = {"items": [{"que": "memoria ram", "cantidad": 2}],
                 "restricciones": ["las menos partes chinas posibles"]}
    llamadas = [{"herramienta": "buscar_productos",
                 "pedido": {"filtros": [{"campo": "pais_fabricacion",
                                         "operador": "no_contiene",
                                         "valor": "china"}]},
                 "resultado": {}}]
    salida = _restricciones_de_los_filtros(declarado, llamadas, "t")
    assert salida["restricciones"] == ["las menos partes chinas posibles"]


def test_sin_filtros_no_toca_lo_declarado():
    """Un turno sin condiciones no gana restricciones de la nada."""
    from app.core.hub_venta import _restricciones_de_los_filtros

    declarado = {"items": [{"que": "mouse", "cantidad": 1}]}
    llamadas = [{"herramienta": "buscar_productos",
                 "pedido": {"categoria": "mouse"}, "resultado": {}}]
    assert _restricciones_de_los_filtros(declarado, llamadas, "t") == declarado
