# SNAPSHOT FICHA 34, 28-ago-2026. Las funciones reconciliar e
# instruccion_de_preguntas, copiadas de app/core/pedido.py en el commit
# a6fff2f (origin/main al arrancar esta sesion). pedido.py se queda: tiene
# funciones vivas. Esto no corre. app/ no importa este archivo.

def reconciliar(pedido: dict, llamadas: list, trace_id: str = "",
                ya_resuelto: str = "", tienda_id: str = "") -> dict:
    """Compara lo que el modelo DECLARO que entendio contra lo que PIDIO.

    Devuelve:
      faltantes: lista de frases imperativas para la vuelta siguiente. Vacia =
                 el plan cubre el pedido.
      preguntar: lista de contradicciones que el modelo NO puede resolver solo.
                 Si viene con algo, el turno termina preguntandole al cliente.
      falta_el_reparto: el cliente nombro dos o mas destinos y ningun item
                 dice a cual va. Tipado y no frase por lo mismo que
                 `falta_la_cuenta`: no hay ronda donde el modelo lea un pedido
                 de que vuelva a declarar.
      falta_la_cuenta: el cliente pidio precio, hay productos sobre la mesa
                 y NADIE armo la cuenta. Tipado por el mismo motivo que
                 `sin_buscar`: lo consume el CODIGO, que arma la cuenta, y no
                 el modelo, que desde el 17-ago no tiene una ronda donde leer
                 la frase.
      sin_buscar: los mismos items de la regla 1, pero TIPADOS. El texto es
                 para el modelo; esta lista es para el codigo, que con ella
                 ejecuta la busqueda en vez de volver a pedirsela. Es el mismo
                 hecho dicho una sola vez: sacarlo del texto con una expresion
                 regular seria la misma regla escrita en dos lados.

    No inventa nada ni completa por su cuenta: solo dice que falta.
    """
    faltantes: list[str] = []
    preguntar: list[str] = []
    sin_buscar: list[str] = []
    if not pedido:
        return {"faltantes": [], "preguntar": [], "sin_buscar": [],
                "falta_la_cuenta": False, "falta_el_reparto": False}

    # LO QUE YA SE RESOLVIO EN TURNOS ANTERIORES TAMBIEN CUENTA COMO ATENDIDO.
    #
    # EL TERCER ESTADO, segunda mitad. Medido el 7-ago sobre las 10 charlas: de
    # los 41 faltantes que se repetian sin resolverse, 25 eran "no lo buscaste"
    # sobre items que el modelo NO volvio a buscar -y hacia bien-. El caso mas
    # claro: el cliente dice "acordate que los quiero negros" sobre un mouse que
    # ya se le habia mostrado y certificado dos turnos antes. El modelo declara
    # el item, no busca nada porque no hace falta, y el reconciliador le exige
    # buscar. Otra ronda quemada, y el reclamo es imposible: no hay nada que
    # buscar.
    #
    # La causa es que el reconciliador NO TENIA MEMORIA: comparaba el pedido
    # -que se acumula turno a turno- contra las llamadas de ESTE turno solo. El
    # dato ya existe en la conversacion, en `productos_vistos` y en el carrito;
    # solo habia que pasarselo.
    uni_prod = " ".join(x for x in
                        (_universo_de_busquedas(llamadas), _norm(ya_resuelto))
                        if x)
    uni_rest = _universo_de_restricciones(llamadas)
    uni_dest = _universo_de_destinos(llamadas)
    nombres = [l.get("herramienta") for l in (llamadas or [])]

    # 1. CADA ITEM NOMBRADO TIENE QUE HABER SIDO ATENDIDO, y ATENDIDO SON TRES
    #    ESTADOS, NO DOS. Es el chequeo que caza el auricular que se perdio.
    #
    #    EL BUG, medido el 7-ago sobre las 10 charlas: de 88 faltantes emitidos,
    #    41 se repitieron en dos o mas rondas del MISMO turno. 25 de esos 41
    #    eran este reclamo. Y NO eran falsos: el modelo habia declarado el item
    #    y de verdad no trajo nada, porque el producto NO EXISTE -"iPhone 15 Pro
    #    con Android", "disco HDD de 7000 MB/s"-. El reconciliador le decia
    #    "buscalo", el modelo lo buscaba, no encontraba, y se le volvia a decir
    #    "buscalo". Un reclamo IMPOSIBLE de satisfacer, y una ronda quemada cada
    #    vez.
    #
    #    LA CAUSA ES QUE FALTABA UN ESTADO. Para un item habia dos: buscado o no
    #    buscado. "Lo busque y no hay" caia en la misma bolsa que "no lo
    #    busque". No es un descuido nuestro: `rasa-sdk` tiene el mismo bug -su
    #    formulario decide con `tracker.get_slot(x) is None`, asi que un slot
    #    cuya extraccion fallo se vuelve a pedir para siempre- y la literatura
    #    de seguimiento de estado conversacional resuelve justamente con un
    #    TERCER valor para "no se puede completar".
    #
    #    Y ESTE REPO YA LO INVENTO. La regla cero de `CLAUDE.md` dice, textual:
    #    "not_found NO es un error, es un resultado valido y exitoso". El
    #    certificador tiene tres veredictos hace meses. Nunca se habia aplicado
    #    al ITEM del pedido, solo a la identidad del producto. Esto es esa misma
    #    regla, un nivel mas arriba.
    #
    #    Se mira el ESTADO que devolvio la herramienta, no las palabras: es el
    #    principio de tau-bench, juzgar por el estado observado y no por lo que
    #    el agente cuenta que hizo.
    for it in (pedido.get("items") or []):
        que = str(it.get("que") or "").strip()
        if not que:
            continue
        if _cubierto(que, uni_prod):
            continue                                    # atendido: trajo algo
        if _se_busco_y_no_hay(que, llamadas):
            continue                                    # atendido: no existe
        faltantes.append(
            f"El cliente pidio '{que}' y no lo buscaste. Buscalo.")
        if not _en_duda(que, pedido):
            sin_buscar.append(que)

    # 2. AL REVES: NADA COTIZADO QUE EL CLIENTE NO HAYA PEDIDO. Caza el item
    #    fantasma, el teclado que aparecio de la nada en la cuenta.
    pedido_txt = " ".join(_norm(it.get("que")) for it in
                          (pedido.get("items") or []))
    for l in (llamadas or []):
        if l.get("herramienta") != "armar_presupuesto":
            continue
        for it in ((l.get("pedido") or {}).get("items") or []):
            pid = str(it.get("product_id") or "")
            nom = ""
            for l2 in (llamadas or []):
                for p in ((l2.get("resultado") or {}).get("productos") or []):
                    if str(p.get("id")) == pid:
                        nom = _norm(p.get("categoria")) or _norm(p.get("nombre"))
            if nom and pedido_txt and not _cubierto(nom, pedido_txt):
                preguntar.append(
                    f"El cliente no pidio '{nom}' entre los productos a "
                    f"cotizar, pero lo nombro en otra parte del mensaje. "
                    f"Preguntale si lo suma o si reemplaza a otra cosa.")

    # 3. TODA RESTRICCION DECLARADA TIENE QUE VIAJAR EN ALGUN ARGUMENTO. Caza
    #    el "sin partes chinas" que el modelo entendio y despues no aplico.
    #
    #    SALVO EL REPARTO DE PAGO AMBIGUO, y esto se midio dos veces. "Divide el
    #    presupuesto en setenta treinta" no tiene ningun argumento de busqueda
    #    donde entrar: pedirselo es un faltante IMPOSIBLE. El 6-ago se creyo
    #    arreglado sumando el argumento `pago` al universo de arriba, pero eso
    #    solo tapa el caso en que el modelo SI lo aplico. Cuando no lo aplica
    #    -medido en produccion el 6-ago, 3 rondas seguidas- el reclamo vuelve a
    #    ser imposible, el modelo pide CERO herramientas porque tiene razon, y
    #    el turno paga 8 segundos por nada. Y encima el reparto se perdia igual.
    #    Ahora no se reclama: lo aplica el CODIGO despues del bucle, con el
    #    supuesto declarado en la cuenta. Ver `_reparto_de_pago_declarado`.
    #    Y NO SE RECLAMA SI NO HUBO NINGUNA BUSQUEDA (FICHA 06). El turno 1 de
    #    la charla real del 12-ago declara "que no sean fabricados en china" y
    #    CERO items: el cliente puso la condicion antes de pedir nada. Sin
    #    busqueda no hay argumento donde la condicion pueda viajar, asi que
    #    pedirle que la aplique es un reclamo IMPOSIBLE —la misma clase que la
    #    regla 1 arreglo el 7-ago con el tercer estado, y cada reclamo
    #    imposible ensucia el unico numero con el que se mide si lo declarado y
    #    lo hecho coinciden—. La condicion no se pierde: sigue en el pedido y
    #    se aplica en cuanto haya algo que buscar.
    hubo_busqueda = any(l.get("herramienta") in _TRAEN_PRODUCTOS
                        for l in (llamadas or []))
    ambiguo = (reparto_declarado(pedido)
               or reparto_ambiguo(pedido.get("restricciones")))
    for r in (pedido.get("restricciones") or []) if hubo_busqueda else []:
        if ambiguo and str(r) == ambiguo[0]:
            continue
        if not _cubierto(r, uni_rest) and not _la_resolvio_el_codigo(
                str(r), llamadas, tienda_id):
            faltantes.append(
                f"El cliente puso la condicion '{r}' y no la aplicaste en "
                f"ninguna busqueda. Usala en el argumento que corresponda.")

    # 4. TODO DESTINO NOMBRADO TIENE QUE ESTAR COTIZADO.
    for d in (pedido.get("destinos") or []):
        if not _cubierto(d, uni_dest):
            faltantes.append(
                f"El cliente nombro el destino '{d}' y no lo cotizaste.")

    # 5. SI PIDIO PRECIO, TIENE QUE HABER CUENTA. La regla del negocio: dejar
    #    un pedido de precio sin ningun numero es peor que cotizar de a partes.
    falta_la_cuenta = False
    if pedido.get("pide_precio") and "armar_presupuesto" not in nombres:
        if uni_prod:
            # LA MARCA TIPADA, aparte de la frase (FICHA 04, 21-ago-2026). La
            # frase esta escrita PARA EL MODELO y desde el 17-ago no hay ronda
            # siguiente que se la lea: quedaba un reclamo que nadie atendia, y
            # eso le costo el Total a dos turnos de la charla real del 12-ago.
            # El codigo no puede depender de buscar una subcadena adentro de
            # una prosa que se puede reescribir sin darse cuenta; el hecho se
            # dice UNA vez y se dice tipado. Es la misma leccion que
            # `sin_buscar`, tres reglas mas arriba.
            # LA FRASE SE FUE Y QUEDA LA MARCA (FICHA 06, 23-ago-2026). El
            # comentario de arriba ya decia que la frase no la lee nadie desde
            # el 17-ago; lo que faltaba era sacarla. Mientras estuvo, `faltantes`
            # medía DOS cosas a la vez —lo declarado que no se buscó, que es un
            # defecto, y la cuenta que la reposicion todavia no armo, que es el
            # orden normal del turno— y por eso no podia llegar a cero ni con el
            # sistema perfecto. El chequeo de aceptacion de la puerta unica es
            # justamente ese cero, asi que un contador que mide dos cosas no
            # sirve para tomarlo. El hecho sigue dicho, tipado y una sola vez.
            falta_la_cuenta = True

    # 6. LA CONTRADICCION QUE EL MODELO MISMO DECLARO. No se resuelve
    #    eligiendo: se pregunta. Es el `ambiguo` del certificador, aplicado al
    #    pedido entero.
    #    SALVO QUE EL SISTEMA YA LA HAYA RESUELTO. Ver
    #    `_contradiccion_desmentida`: el modelo cuenta mal, el codigo cuenta
    #    bien, y preguntar lo que uno mismo acaba de resolver cuesta la venta.
    for c in (pedido.get("contradicciones") or []):
        c = str(c).strip()
        if not c:
            continue
        if _contradiccion_desmentida(c, pedido, llamadas, tienda_id):
            log.info("contradiccion_desmentida", trace_id=trace_id,
                     unidades=_unidades_declaradas(pedido),
                     con_destino=_unidades_con_destino(llamadas),
                     decia=c[:120])
            continue
        # LA NOTA ES PARA VOS, NO PARA EL CLIENTE, y hay que decirselo. El
        # modelo escribe la contradiccion en TERCERA persona -"el cliente pidio
        # 2 auriculares pero menciono un teclado"- porque se la escribe a si
        # mismo; despues se la devolviamos con un "preguntale al cliente por
        # esto" adelante y la pegaba TAL CUAL en el mensaje. Salio a WhatsApp
        # dos turnos seguidos el 12-ago: el cliente leyendo como el sistema
        # habla de el. El invariante `le_habla_al_cliente_y_no_de_el` la caza
        # si igual se filtra; esto ataca el origen.
        preguntar.append(f"Antes de avanzar preguntaselo al cliente VOS, de "
                         f"vos a vos, con tus palabras y en una linea. NO "
                         f"copies esta nota: esta escrita para vos, no para "
                         f"el. Lo que hay que aclarar: {c}")

    # 7. VARIOS DESTINOS Y NINGUN ITEM CON DESTINO: el reparto no se declaro.
    #
    #    LA FALLA, medida en produccion el 6-ago. El cliente reparte seis
    #    unidades entre tres localidades -"un auricular y un mouse a Cordoba, un
    #    teclado y un mouse a Concordia, los otros dos a Posadas"- y el modelo
    #    declaro los tres destinos en la lista suelta `destinos` y NINGUN item
    #    con su `destino`. El campo existe desde el 5-ago justamente para esto.
    #    Sin el, la cuenta cobra tres envios y no puede decir que va a cada uno:
    #    salio "2 de 6 unidades quedaron sin destino asignado", que es honesto
    #    pero es un pedido que no cierra y una venta que no se toma.
    #
    #    Es la misma clase que la regla 1 -lo nombrado tiene que viajar- movida
    #    del QUE al ADONDE. No inventa el reparto: dice que falta declararlo.
    #
    #    EL DESTINO VALE VENGA DE DONDE VENGA (9-ago). Esta regla miraba SOLO
    #    los items de `registrar_pedido` y por eso no veia el reparto cuando el
    #    modelo lo pegaba en los renglones de la cuenta, que es donde de verdad
    #    hace falta. Costo tres rondas y 37,7 segundos en produccion; el detalle
    #    y el trace estan en `_unidades_con_destino`.
    destinos = [d for d in (pedido.get("destinos") or []) if str(d).strip()]
    items = pedido.get("items") or []
    #    Y ESTA TAMBIEN SE TIPA (FICHA 06), por el mismo motivo que la 5: su
    #    frase le pedia al modelo que VOLVIERA a declarar el pedido, y no hay
    #    ronda donde leerla. El reparto que falta no lo puede poner el codigo
    #    —seria elegir por el cliente a que ciudad va cada unidad— asi que el
    #    reclamo no tiene accion posible en este turno: lo que si tiene es
    #    quien lo diga. Los destinos ya abren un punto cada uno en
    #    `indice_turno`, y si el mensaje no dice que va a cada lado esos puntos
    #    salen sin contestar y el redactor recibe la obligacion. La marca queda
    #    tipada y logueada para que el hueco se vea; la frase muerta se va.
    falta_el_reparto = bool(
        len(destinos) >= 2 and items
        and not any(str(it.get("destino") or "").strip() for it in items)
        and not _reparto_cerrado(pedido, llamadas))

    if faltantes or preguntar or falta_la_cuenta or falta_el_reparto:
        log.info("reconciliador", trace_id=trace_id,
                 faltantes=faltantes[:4], preguntar=preguntar[:4],
                 falta_la_cuenta=falta_la_cuenta,
                 falta_el_reparto=falta_el_reparto)
    return {"falta_el_reparto": falta_el_reparto,
            "faltantes": faltantes, "preguntar": preguntar,
            "sin_buscar": sin_buscar, "falta_la_cuenta": falta_la_cuenta}


# `instruccion_de_faltantes` SE BORRO EL 17-AGO, con el bucle de rondas. Era la
# unica consumidora de `rec["faltantes"]` y su unico destino era el DECISOR de la
# vuelta siguiente: le decia que herramienta le habia faltado pedir. Sin vuelta
# siguiente no tiene a quien hablarle. Lo que hacia se reparte en dos, y las dos
# ya existian: lo que se puede resolver sin el modelo lo resuelven las
# reposiciones del hub, y lo que no, se lo dice el INDICE al redactor mirando el
# material que quedo. `rec["faltantes"]` se sigue calculando y se sigue logueando,
# que es donde servia de verdad: para ver cuando una reposicion no alcanzo.


def instruccion_de_preguntas(rec: dict) -> str:
    """Cuando el pedido no cierra, el turno NO elige por el cliente: pregunta.
    Esto entra en el prompt del redactor y manda sobre el resto."""
    lineas = list(rec.get("preguntar") or [])
    if not lineas:
        return ""
    return ("EL PEDIDO NO CIERRA Y NO PODES ELEGIR VOS. Antes de cerrar la "
            "respuesta, preguntale al cliente lo siguiente, con naturalidad y "
            "en una sola pregunta si se puede:\n- " + "\n- ".join(lineas) +
            "\nCotizá igual lo que sí está definido: dejarlo sin ningún número "
            "es peor. Pero la pregunta va sí o sí.")
