"""
EL PEDIDO COMO OBJETO, Y EL RECONCILIADOR.

POR QUE EXISTE (Martin, 2-ago-2026). El sistema tenia diecinueve controles
-nueve invariantes en el juez, diez funciones `_sin_algo` en el hub- y los
diecinueve miraban la PROSA ya escrita. Cero miraban la DECISION. La prosa es
un espacio infinito: cada error nuevo llega con otras palabras y obliga a un
parche nuevo, para siempre. Eso fue el loop de meses.

La decision, en cambio, es un objeto chico y tipado. Se chequea de forma
general, UNA vez, para todos los casos.

EL CASO QUE LO PARIO, medido el 2-ago sobre un mensaje real:
  "Dame precio de dos auriculares, dos mouse y dos memorias... que lleven las
   menos partes chinas posibles... un auricular y un mouse a Cordoba capital,
   un teclado y un mouse a Concordia, los otros dos a posadas... divide el
   presupuesto en setenta treinta."
El bot cotizo CUATRO categorias sobre un pedido de tres, metio un teclado que
el cliente solo habia nombrado al hablar del envio, borro un auricular para
hacerle lugar, ignoro el filtro de origen que la herramienta ofrece, y ordeno
por el mas caro a partir de "el precio no seria tan importante". Los nueve
invariantes dijeron LIMPIO, porque ninguna de las cuatro fallas es una mentira
sobre el catalogo. Son fallas de DECISION.

COMO FUNCIONA. El modelo declara lo que entendio llamando a `registrar_pedido`
-una herramienta mas, con su esquema- y despues pide las herramientas que le
parecen. El codigo compara las dos cosas:

    lo que dijo que entendio   contra   lo que efectivamente pidió

Cuando no coinciden, el codigo hace UNA de dos cosas y nunca una tercera:
  1. le devuelve al modelo el faltante concreto para la vuelta siguiente, o
  2. si el pedido tiene una CONTRADICCION, obliga a preguntarle al cliente.

Nunca inventa la pieza que falta ni deja pasar. Es el mismo mecanismo del
veredicto `ambiguo` del certificador -que ya funciona hace meses para la
identidad del producto- extendido al pedido entero.

El reconciliador NO sabe de teclados ni de China. Sabe que el cliente nombro
tres categorias y el plan busco cuatro, y que una restriccion declarada no
viaja en ningun argumento. Por eso caza la CLASE y no el caso.
"""
import re
import unicodedata

from app.logger import get_logger

log = get_logger(__name__)


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def _stems(valor: str) -> list[str]:
    """Mismas raices que usa `herramientas._excluido`, para que lo que el
    reconciliador considera 'presente' sea lo mismo que el filtro considera
    aplicado. Si las dos definiciones divergen, el chequeo miente."""
    return [w[:4] for w in _norm(valor).split() if len(w) >= 4]


def _cubierto(texto: str, universo: str) -> bool:
    """Una raiz alcanza. Conservador a proposito: preferimos NO acusar un
    faltante falso antes que mandar al modelo a buscar de nuevo al pedo."""
    st = _stems(texto)
    return bool(st) and any(s in universo for s in st)


# Las herramientas que TRAEN productos. Un item del pedido se considera
# atendido si alguna de estas lo nombra.
_TRAEN_PRODUCTOS = ("buscar_productos", "ficha_producto", "ver_compatibilidad")


def _universo_de_busquedas(llamadas: list) -> str:
    """Todo lo que el plan efectivamente busco, en un solo texto normalizado:
    categorias, descripciones y los nombres de lo que volvio. Contra esto se
    chequea si cada item del pedido fue atendido."""
    partes = []
    for l in llamadas or []:
        if l.get("herramienta") not in _TRAEN_PRODUCTOS:
            continue
        ped = l.get("pedido") or {}
        partes.append(_norm(ped.get("categoria")))
        partes.append(_norm(ped.get("descripcion")))
        res = l.get("resultado") or {}
        for p in (res.get("productos") or []):
            partes.append(_norm(p.get("nombre")))
            partes.append(_norm(p.get("categoria")))
        prod = res.get("producto") or {}
        if prod:
            partes.append(_norm(prod.get("nombre")))
            partes.append(_norm(prod.get("categoria")))

    # LO YA COTIZADO TAMBIEN CUENTA COMO ATENDIDO. Sin esto el reconciliador
    # daba un FALSO POSITIVO caro, visto en la corrida del 2-ago: el cliente
    # pidio "los dos juntos", el modelo armo el presupuesto con los ids que ya
    # tenia de un turno anterior sin volver a buscar -que es lo correcto- y el
    # reconciliador le exigia buscar de nuevo lo que ya estaba en la cuenta.
    # Una vuelta entera del bucle al pedo, en tokens y en latencia.
    for l in (llamadas or []):
        if l.get("herramienta") != "armar_presupuesto":
            continue
        partes.append(_norm((l.get("resultado") or {}).get("bloque")))
    return " ".join(x for x in partes if x)


# Como se dice en castellano cada operador. Sin esto "menos de 120 gramos" no
# se reconoce en un filtro `peso_gramos menor 120`: el reconciliador acusa un
# faltante falso y quema una ronda entera de modelo.
_PALABRAS_OPERADOR = {
    "contiene": "contiene tiene con",
    "igual": "igual exacto",
    "mayor": "mayor mas desde minimo",
    "menor": "menor menos hasta maximo",
}


def _universo_de_restricciones(llamadas: list) -> str:
    """Donde puede viajar una restriccion declarada por el cliente: las
    condiciones estructuradas de la busqueda, el criterio de orden y los temas
    consultados.

    5-AGO: `excluir`, `tope_precio` y `orden` DEJARON DE EXISTIR como argumentos
    sueltos -se colapsaron en `filtros` y `ordenar_por`-, asi que este universo
    se arma de esos dos. Se siguen leyendo los viejos por si quedara una llamada
    en vuelo: no cuesta nada y evita acusar en falso durante el deploy.

    LOS FILTROS ENTRAN ACA DESDE EL 4-AGO, y no es un detalle: son la via
    principal por la que una condicion se aplica. Medido con el modelo vivo el
    mismo dia, ante "tenes algun mouse blanco?" el modelo pidio -bien-
    `color contiene blanco`, y el reconciliador, que solo miraba `excluir`,
    contesto que la condicion 'blanco' no se habia aplicado. El turno se comio
    una segunda ronda al pedo: 10.671 ms contra 5.060 de los que no la
    disparaban. Un chequeo que no conoce el argumento nuevo no protege: acusa.
    """
    partes = []
    for l in llamadas or []:
        ped = l.get("pedido") or {}
        for f in (ped.get("filtros") or []):
            if not isinstance(f, dict):
                continue
            partes.append(_norm(f.get("campo")).replace("_", " "))
            partes.append(_norm(f.get("valor")))
            partes.append(_PALABRAS_OPERADOR.get(_norm(f.get("operador")), ""))
        for v in (ped.get("excluir") or []):
            partes.append(_norm(v))
        if ped.get("tope_precio"):
            partes.append("presupuesto tope precio maximo gastar")
        if ped.get("orden"):
            partes.append(_norm(ped["orden"]))
        if ped.get("ordenar_por"):
            # SOLO EL NOMBRE DEL CAMPO. La primera version agregaba tambien una
            # bolsa de palabras -"el mas mejor menor mayor barato caro
            # liviano"- para que un superlativo contara como aplicado. Fue un
            # error y se cobro caro el mismo dia: la restriccion "MENOS partes
            # chinas" empezaba con "menos", "meno" pegaba dentro de "menor" de
            # la bolsa, y el reconciliador daba la condicion por APLICADA cuando
            # el modelo solo habia ordenado por pais_fabricacion. Nunca disparaba
            # la ronda dos y el turno terminaba en el muro. Medido: 3 de 3.
            #
            # Una bolsa de palabras genericas cubre cualquier cosa, y un chequeo
            # que cubre cualquier cosa no chequea nada. El costo de sacarla es
            # que "el mas barato" resuelto con `ordenar_por precio_ars` puede
            # acusarse en falso y costar una ronda. Se elige ese costo: una
            # ronda de mas se paga en segundos, una condicion que se pierde se
            # paga con la venta.
            partes.append(_norm(ped["ordenar_por"]).replace("_", " "))
        if l.get("herramienta") == "consultar_temas":
            partes += [_norm(t) for t in (ped.get("temas") or [])]
        # EL REPARTO DE PAGO TAMBIEN ES UN LUGAR DONDE UNA CONDICION VIAJA.
        #
        # LA RONDA PERDIDA, medida en produccion el 5-ago con el mensaje real de
        # Martin: declaro la restriccion "presupuesto 70/30" -que es como pidio
        # dividir el pago-, el modelo la aplico donde corresponde, en el
        # argumento `pago` de la cuenta, y este universo no lo miraba. El
        # reconciliador le contesto "pusiste la condicion 'presupuesto 70/30' y
        # no la aplicaste en ninguna busqueda, usala en el argumento que
        # corresponda". Es una exigencia IMPOSIBLE: un reparto de pago no es un
        # filtro de producto y no hay busqueda donde meterlo. El turno dio una
        # ronda entera de mas -8 segundos- y en esa ronda el modelo pidio CERO
        # herramientas, porque desde su lado ya estaba resuelto. Y tenia razon.
        for parte in (ped.get("pago") or []):
            if not isinstance(parte, dict):
                continue
            partes.append(_norm(parte.get("medio")))
            pct = parte.get("porcentaje")
            if pct is not None:
                # El numero pelado y sin decimales: el cliente escribe "70/30",
                # no "70.0".
                partes.append(str(int(float(pct))))
        if ped.get("pago"):
            partes.append("presupuesto pago dividido reparto porcentaje")
    return " ".join(x for x in partes if x)


def _universo_de_destinos(llamadas: list) -> str:
    partes = []
    for l in llamadas or []:
        ped = l.get("pedido") or {}
        if l.get("herramienta") == "cotizar_envio":
            partes.append(_norm(ped.get("localidad")))
        for d in (ped.get("destinos") or []):
            partes.append(_norm(d))
        for it in (ped.get("items") or []):
            partes.append(_norm(it.get("destino")))
    return " ".join(x for x in partes if x)


def reconciliar(pedido: dict, llamadas: list, trace_id: str = "") -> dict:
    """Compara lo que el modelo DECLARO que entendio contra lo que PIDIO.

    Devuelve:
      faltantes: lista de frases imperativas para la vuelta siguiente. Vacia =
                 el plan cubre el pedido.
      preguntar: lista de contradicciones que el modelo NO puede resolver solo.
                 Si viene con algo, el turno termina preguntandole al cliente.

    No inventa nada ni completa por su cuenta: solo dice que falta.
    """
    faltantes: list[str] = []
    preguntar: list[str] = []
    if not pedido:
        return {"faltantes": [], "preguntar": []}

    uni_prod = _universo_de_busquedas(llamadas)
    uni_rest = _universo_de_restricciones(llamadas)
    uni_dest = _universo_de_destinos(llamadas)
    nombres = [l.get("herramienta") for l in (llamadas or [])]

    # 1. CADA ITEM NOMBRADO TIENE QUE HABER SIDO BUSCADO. Es el chequeo que
    #    caza el auricular que se perdio: el cliente nombro tres categorias y
    #    el plan trajo otras.
    for it in (pedido.get("items") or []):
        que = str(it.get("que") or "").strip()
        if not que:
            continue
        if not _cubierto(que, uni_prod):
            faltantes.append(
                f"El cliente pidio '{que}' y no lo buscaste. Buscalo.")

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
    for r in (pedido.get("restricciones") or []):
        if not _cubierto(r, uni_rest):
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
    if pedido.get("pide_precio") and "armar_presupuesto" not in nombres:
        if uni_prod:
            faltantes.append(
                "El cliente pidio precio y todavia no armaste la cuenta. "
                "Llama a armar_presupuesto con los ids que ya tenes.")

    # 6. LA CONTRADICCION QUE EL MODELO MISMO DECLARO. No se resuelve
    #    eligiendo: se pregunta. Es el `ambiguo` del certificador, aplicado al
    #    pedido entero.
    for c in (pedido.get("contradicciones") or []):
        c = str(c).strip()
        if c:
            preguntar.append(f"Preguntale al cliente por esto antes de "
                             f"avanzar: {c}")

    if faltantes or preguntar:
        log.info("reconciliador", trace_id=trace_id,
                 faltantes=faltantes[:4], preguntar=preguntar[:4])
    return {"faltantes": faltantes, "preguntar": preguntar}


def instruccion_de_faltantes(rec: dict) -> str:
    """El faltante convertido en instruccion para la vuelta siguiente del
    bucle. Le decimos QUE falta, nunca COMO resolverlo: el modelo elige la
    herramienta, el codigo solo marca el hueco."""
    lineas = list(rec.get("faltantes") or [])
    if not lineas:
        return ""
    # LA CUENTA VA PRIMERA Y NO LA FRENA UNA PREGUNTA PENDIENTE (4-ago-2026).
    # Medido tres veces seguidas con el modelo vivo sobre el mensaje real de
    # Martin: el reconciliador dijo "pedio precio y no armaste la cuenta", y la
    # ronda dos devolvio CERO herramientas en 2 de 3. El modelo entiende que si
    # tiene que preguntar algo, todavia no puede cotizar, y el cliente que pidio
    # precio de seis items se queda sin un solo numero. Mismo defecto medido en
    # 71_cambio_de_decision, 3 de 3 vueltas: no es de un guion, es sistemico.
    #
    # `instruccion_de_preguntas` ya decia "cotiza igual lo que si esta
    # definido", pero eso le llega al REDACTOR, que para entonces no tiene
    # numeros y tiene prohibido inventarlos. Tiene que llegarle al DECISOR, que
    # es la unica etapa que todavia puede llamar a armar_presupuesto.
    plata = [l for l in lineas if "armar_presupuesto" in l]
    resto = [l for l in lineas if l not in plata]
    cabeza = ""
    if plata:
        cabeza = ("PRIMERO LA CUENTA, y va aunque falte aclarar algo: " +
                  " ".join(plata) + " Cotizá lo que YA está definido con los "
                  "ids que tenés; que haya una contradicción por preguntar NO "
                  "te frena la cuenta. Dejar al cliente sin un solo número es "
                  "peor que cotizar de a partes.\n\n")
    if not resto:
        return cabeza.strip()
    return (cabeza + "REVISION DEL PLAN, y esto MANDA sobre todo lo demás que "
            "leas abajo. Comparé lo que el cliente pidió contra lo que "
            "buscaste y falta esto:\n- " + "\n- ".join(resto) +
            "\nTenés que pedir AHORA las herramientas que resuelvan esto. No "
            "contestes sin resolverlo: el dato existe y no lo pediste. Si de "
            "verdad ninguna herramienta puede resolverlo, recién ahí contestá "
            "sin inventarlo.")


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
