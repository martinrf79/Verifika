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


# ── EL REPARTO DE PAGO, UNA SOLA DEFINICION ─────────────────────────────────
# La vivian dos modulos con la misma regex escrita dos veces: el reconciliador
# tenia que saber que un reparto NO es una condicion de busqueda, y el hub tenia
# que saber cual reparto puede aplicar solo. Con dos copias, la del hub se
# arreglo el 6-ago y la del reconciliador no, y el turno se comio una ronda
# entera. Es exactamente la leccion del 31-jul con el patron de la poda: una
# regla escrita en dos lugares termina distinta.
_RE_DOS_PORCENTAJES = re.compile(r"\b(\d{1,3})\s*(?:/|-|y|,| )\s*(\d{1,3})\b")
_MEDIOS = ("transferencia", "mercado pago", "mercadopago", "mp", "efectivo",
           "tarjeta", "credito", "debito")

# ── LOS NUMEROS EN LETRAS ───────────────────────────────────────────────────
#
# LA FALLA, y es la que le puso nombre a esta etapa. El 7-ago se arreglo el
# reparto de pago leyendo "70/30" y se deployo. Corrido en vivo con la redaccion
# REAL de Martin -"divide el presupuesto en SETENTA TREINTA"- el mecanismo quedo
# mudo: no aplico el reparto y no declaro el supuesto. El modelo eligio solo, y
# eligio el 70 por Mercado Pago, que es el medio SIN descuento: $9.140 en contra
# del cliente. El arreglo del dia anterior habia funcionado por casualidad,
# porque esa vez el modelo transcribio la frase a digitos.
#
# La leccion no es "faltaba esta tabla": es que una regla que lee CASTELLANO
# depende de como el modelo transcriba, o sea de una loteria. Por eso la salida
# de fondo es el campo TIPADO de abajo, y esta tabla es la red para cuando el
# modelo no lo llena. Solo las decenas: un reparto de pago se dice "setenta
# treinta", nunca "setenta y tres coma cinco".
_DECENAS = {"diez": 10, "veinte": 20, "treinta": 30, "cuarenta": 40,
            "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80,
            "noventa": 90}
_RE_DOS_EN_LETRAS = re.compile(
    r"\b(" + "|".join(_DECENAS) + r")\b(?:\s+(?:y|por|,|-))?\s+\b("
    + "|".join(_DECENAS) + r")\b")


def _dos_porcentajes(texto: str):
    """Los dos porcentajes de un reparto, vengan en digitos o en letras."""
    m = _RE_DOS_PORCENTAJES.search(texto)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = _RE_DOS_EN_LETRAS.search(texto)
    if m:
        return _DECENAS[m.group(1)], _DECENAS[m.group(2)]
    return None


def reparto_declarado(pedido: dict) -> tuple:
    """EL REPARTO DE PAGO, LEIDO DEL CAMPO TIPADO. Devuelve (texto, mayor,
    menor) o ().

    ESTE ES EL CAMINO BUENO, y desde el 7-ago es el primero que se mira.
    `registrar_pedido.reparto_pago` es una lista de {medio, porcentaje} que
    llena el MODELO, que es quien sabe traducir "setenta treinta" a dos numeros.
    El codigo no lee castellano: lee dos enteros.

    Solo devuelve algo cuando el reparto es AMBIGUO en el medio -ninguna parte
    dice con que se paga-, porque ese es el unico caso que el codigo resuelve
    solo, asumiendo y declarando el supuesto. Si el cliente SI dijo el medio, el
    reparto viaja tal cual y no hay nada que asumir.
    """
    partes = [p for p in (pedido or {}).get("reparto_pago") or []
              if isinstance(p, dict)]
    if len(partes) != 2:
        return ()
    try:
        pcts = [float(p.get("porcentaje") or 0) for p in partes]
    except (TypeError, ValueError):
        return ()
    if abs(sum(pcts) - 100) > 1 or min(pcts) <= 0:
        return ()
    if any(_norm(p.get("medio")) for p in partes):
        return ()                      # el cliente dijo el medio: nada que asumir
    a, b = int(max(pcts)), int(min(pcts))
    return (f"reparto {a}/{b}", a, b)


def reparto_ambiguo(restricciones) -> tuple:
    """LA RED, para cuando el modelo no llena el campo tipado. Lee los
    porcentajes de una restriccion escrita en castellano.

    QUEDA COMO SEGUNDA OPCION, no como la primera. Nacio el 7-ago leyendo solo
    digitos, se cayo con "setenta treinta" -que es como lo escribio Martin-, y
    se le agregaron las letras. Esa rueda es exactamente la que el campo tipado
    viene a cortar: mientras el codigo tenga que leer castellano, siempre va a
    haber una forma de decirlo que no contemple. Si `reparto_declarado` empieza
    a acertar siempre, esta funcion se borra.
    """
    for r in (restricciones or []):
        t = _norm(r)
        if any(m in t for m in _MEDIOS):
            # El cliente SI dijo el medio. Cual porcentaje va con cual es
            # interpretacion del texto, y eso no lo hace el codigo: sigue
            # siendo del modelo, y si no lo aplica el reconciliador lo reclama.
            continue
        par = _dos_porcentajes(t)
        if not par:
            continue
        a, b = par
        if a + b != 100 or min(a, b) <= 0:
            continue
        return (str(r), max(a, b), min(a, b))
    return ()


def _cubierto(texto: str, universo: str) -> bool:
    """Una raiz alcanza. Conservador a proposito: preferimos NO acusar un
    faltante falso antes que mandar al modelo a buscar de nuevo al pedo.

    LAS PALABRAS DE MENOS DE CUATRO LETRAS TIENEN SU PROPIO CAMINO, y sin el
    esta funcion mentia de la peor manera posible: `_stems` descarta todo lo
    que tenga menos de cuatro letras, asi que para `ssd` y `ram` devolvia lista
    vacia y esto daba SIEMPRE False. O sea que un rubro de nombre corto no
    podia considerarse atendido NUNCA: el reconciliador lo reclamaba, el modelo
    lo buscaba, lo encontraba, y se lo volvia a reclamar. Un reclamo imposible
    y una ronda quemada por turno, con su latencia y sus tokens, cada vez que
    alguien escribia "ssd" o "ram" — y `ssd` es una categoria entera de la
    tienda.

    Lo encontro el barrido de la decision al subirle los sorteos de 3 a 12: con
    la muestra chica no aparecia. Es la prueba de que un barrido chico esconde.

    Para las cortas se compara la palabra ENTERA contra las palabras del
    universo, no por adentro: con `in` a secas, "ram" daria cubierto dentro de
    "programa" y estariamos cambiando un reclamo imposible por un faltante que
    se traga en silencio, que es peor.
    """
    st = _stems(texto)
    if st:
        return any(s in universo for s in st)
    cortas = [w for w in _norm(texto).split() if w]
    palabras = set(universo.split())
    return any(w in palabras for w in cortas)


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
        # `producto` LLEGA EN DOS FORMAS, y leerlo siempre como dict tumbaba
        # el turno. `ficha_producto` manda la ficha entera; `ver_compatibilidad`
        # manda el nombre pelado, porque al modelo no le hace falta mas que eso
        # para redactar el veredicto. Aca se lo leia con `.get("nombre")` sin
        # mirar que era: AttributeError, el hub atrapa la excepcion, y el
        # cliente recibe el mensaje enlatado en vez de la respuesta.
        #
        # Rompia SOLO la mitad que contesta. Las salidas que no resuelven
        # -`no_encontrado`, `equipo_desconocido`- no mandan string, asi que
        # pasaban limpias: el bot andaba bien justo cuando no sabia y moria
        # cuando sabia. Por eso parecia intermitente y no una puerta rota.
        # Candado en `tests/test_puertas_humo.py`, que ahora pasa el resultado
        # de CADA herramienta por aca.
        #
        # Y EL NOMBRE SE SUMA, no se descarta: si se tirara, el reconciliador
        # daria el item por NO atendido y mandaria a buscar de nuevo lo que la
        # herramienta ya trajo.
        prod = res.get("producto")
        if isinstance(prod, str):
            partes.append(_norm(prod))
        elif isinstance(prod, dict):
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


# Los estados de herramienta que significan "se busco de verdad y la fuente no
# tiene nada que dar". Son resultados VALIDOS, no fallas: la respuesta honesta
# -"eso no lo tenemos"- es la respuesta, no un paso pendiente.
_SE_BUSCO_Y_NO_HAY = ("no_encontrado", "no_vendemos", "sin_stock",
                      "nada_dentro_del_presupuesto")


def _se_busco_y_no_hay(que: str, llamadas: list) -> bool:
    """EL TERCER ESTADO. ¿Para este item se llamo a una herramienta que trae
    productos, y volvio diciendo que no hay?

    Se ata al item por lo que se PIDIO -la categoria y la descripcion de esa
    misma llamada-, no por lo que volvio, porque justamente no volvio nada.
    """
    for l in (llamadas or []):
        if l.get("herramienta") not in _TRAEN_PRODUCTOS:
            continue
        if (l.get("resultado") or {}).get("estado") not in _SE_BUSCO_Y_NO_HAY:
            continue
        ped = l.get("pedido") or {}
        pedido_txt = " ".join(_norm(ped.get(k)) for k in
                              ("categoria", "descripcion", "product_id"))
        if pedido_txt.strip() and _cubierto(que, pedido_txt):
            return True
    return False


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


def _unidades_declaradas(pedido: dict) -> int:
    return sum(max(1, int(i.get("cantidad") or 1))
               for i in (pedido.get("items") or []) if str(i.get("que") or "").strip())


def _unidades_con_destino(llamadas: list) -> int:
    """Las unidades que YA tienen su destino pegado en una cuenta armada.

    EL REPARTO NO VIVE DONDE LO BUSCABAMOS, y esto costo tres rondas en
    produccion. Trace 57ad6a0d, 9-ago, 14:13:33: el modelo resolvio el reparto
    PERFECTO -"los otros dos articulos" por resta- y lo declaro en los seis
    renglones de `armar_presupuesto`, que es donde el reparto hace falta porque
    es lo que cobra los envios. La regla 7 miraba unicamente los items de
    `registrar_pedido`, no lo encontraba, y le pedia al modelo que volviera a
    declarar algo que acababa de declarar bien. Se repitio en las rondas 2, 3 y
    4, el turno tardo 37,7 segundos y cerro en `faltantes_sin_resolver` sobre
    algo que estaba hecho.

    Es la misma clase de falla que las otras caras de esta moneda: no habia un
    error de diseño, habia un cable mirando el lugar equivocado.
    """
    mejor = 0
    for l in llamadas or []:
        if l.get("herramienta") != "armar_presupuesto":
            continue
        items = (l.get("pedido") or {}).get("items") or []
        mejor = max(mejor, sum(max(1, int(i.get("cantidad") or 1))
                               for i in items
                               if str(i.get("destino") or "").strip()))
    return mejor


def _reparto_cerrado(pedido: dict, llamadas: list) -> bool:
    """Todas las unidades que el cliente pidio tienen destino en la cuenta."""
    declaradas = _unidades_declaradas(pedido)
    return bool(declaradas) and _unidades_con_destino(llamadas) >= declaradas


def _senala_a_unos_pocos(c: str, pedido: dict) -> bool:
    """¿La contradiccion apunta a ALGUNOS items y no al pedido entero?

    Es la misma salvaguarda que ya usa `_en_duda`, mirada desde el otro lado:
    una contradiccion que nombra TODOS los rubros -o ninguno- habla del pedido
    como conjunto; una que nombra unos pocos senala a un producto concreto.
    """
    items = [str(i.get("que") or "") for i in (pedido.get("items") or [])]
    nombrados = [i for i in items if i and _cubierto(i, _norm(c))]
    return bool(nombrados) and len(nombrados) < len(items)


def _nombra_rubro_ajeno(c: str, pedido: dict, tienda_id: str) -> bool:
    """¿La contradiccion nombra un rubro de la tienda que NO esta en el pedido?

    Es el caso del teclado: "nombro un teclado en el envio a Concordia que no
    estaba en el pedido". Esa contradiccion es LEGITIMA y se pregunta siempre,
    cierre o no cierre la aritmetica del reparto. Sin tienda no se puede saber,
    y ante la duda se pregunta: el default conservador es preguntar.
    """
    if not tienda_id:
        return True
    try:
        from app.core.guia_pedido import categorias_nombradas
        nombradas = categorias_nombradas(c, tienda_id) or []
    except Exception:
        return True
    pedido_txt = " ".join(_norm(i.get("que")) for i in (pedido.get("items") or []))
    return any(not _cubierto(cat, pedido_txt) for cat in nombradas)


def _contradiccion_desmentida(c: str, pedido: dict, llamadas: list,
                              tienda_id: str) -> bool:
    """¿El propio sistema ya resolvio lo que el modelo dice que no cierra?

    EL CASO, medido en produccion el 9-ago, trace 57ad6a0d. El cliente escribio
    seis articulos y repartio cuatro por su nombre mas "los otros dos". El
    modelo declaro esta contradiccion: "pidio 6 articulos, pero al detallar los
    envios solo menciono 5". **Es un error de aritmetica suyo**: nombra cuatro y
    "los otros dos", que son seis. La regla 6 tomaba cualquier contradiccion
    declarada y la convertia en pregunta sin contar nada, asi que al cliente le
    llego "confirmame el destino del sexto articulo" DEBAJO de un presupuesto
    donde los seis ya tenian su destino. El bot le pregunta algo que el mismo
    acababa de resolver, que es la falla que `objetivo.py` castiga como
    "pregunta lo que ya sabe".

    CONTAR ES DEL CODIGO, NO DEL MODELO. Esto no persigue la redaccion de la
    contradiccion: la contrasta con el hecho duro -cuantas unidades tienen
    destino-, que es lo unico que no cambia de palabras.

    LAS DOS SALVAGUARDAS, sin las cuales esto haria mas daño que bien:
      - si nombra un rubro que no esta en el pedido, se pregunta igual. Ese es
        el teclado, y es la contradiccion que SI hay que hacer.
      - si senala a unos pocos items y no al pedido entero, se pregunta igual:
        habla de un producto, no del reparto.
    """
    if _nombra_rubro_ajeno(c, pedido, tienda_id):
        return False
    if _senala_a_unos_pocos(c, pedido):
        return False
    return _reparto_cerrado(pedido, llamadas)


def _en_duda(que: str, pedido: dict) -> bool:
    """¿El modelo MISMO marco este item como dudoso?

    NACE DE UN DEFECTO PROPIO, medido el 9-ago. Con la busqueda repuesta por
    codigo, la redaccion coloquial cotizo SIETE unidades: el cliente pidio dos
    auriculares, dos mouse y dos memorias, nombro un teclado al repartir los
    envios, y el modelo lo declaro en los DOS lados a la vez -como item y como
    contradiccion-. El codigo lo busco, la cuenta lo sumo y al cliente le
    llegaron $12.000 de mercaderia que no pidio.

    El molde ya dice cual es la regla: "si nombro algo al pasar y no queda claro
    que lo quiera, no lo pongas en items: ponelo en contradicciones". Declararlo
    en los dos lados es el propio modelo diciendo que no esta seguro, y ante la
    duda se PREGUNTA, no se cotiza. Es la regla cero del proyecto -el `ambiguo`
    del certificador- aplicada al item del pedido.

    LA SALVAGUARDA, sin la cual esto haria mas daño que bien: una contradiccion
    que nombra TODOS los items -"pediste 2 auriculares, 2 mouse y 2 memorias,
    pero la distribucion no cierra"- habla del pedido entero y no marca a
    ninguno en particular. Ahi no se descarta nada. Solo cuenta cuando la
    contradiccion senala a UNOS POCOS y no a todos.
    """
    dudas = [_norm(c) for c in (pedido.get("contradicciones") or []) if c]
    if not dudas:
        return False
    items = [str(i.get("que") or "") for i in (pedido.get("items") or [])]
    for duda in dudas:
        nombrados = [i for i in items if i and _cubierto(i, duda)]
        if nombrados and len(nombrados) < len(items) and _cubierto(que, duda):
            return True
    return False


def _la_resolvio_el_codigo(restriccion: str, llamadas: list,
                           tienda_id: str) -> bool:
    """¿Esta condicion viaja en una busqueda porque LA TRADUJO EL CODIGO?

    POR QUE HACE FALTA (FICHA 06, 23-ago-2026), y es la misma falla que este
    chequeo ya pago dos veces: **un chequeo que no conoce el argumento nuevo no
    protege, acusa.** El 4-ago fueron los `filtros`, que el universo de arriba
    no miraba. Ahora es el ORDEN: desde la puerta unica, "el mas barato" no es
    un filtro sino un `ordenar_por precio_ars`, y el universo de texto solo
    guarda el NOMBRE del campo. "el mas barato" contra "precio ars" no comparte
    ni una raiz, asi que la condicion se aplicaba perfecto y el reconciliador
    la reclamaba igual: 8 turnos de 54, todos superlativos.

    SE PREGUNTA CON LA MISMA FUNCION QUE TRADUJO, no con una lista de palabras.
    El comentario de `_universo_de_restricciones` cuenta el intento anterior y
    lo que costo: una bolsa de sinonimos -"el mas mejor menor mayor barato"-
    hizo que "MENOS partes chinas" contara como aplicada porque "meno" pegaba
    dentro de "menor". Aca no hay parecido de texto: se le pide a
    `resolver_orden` el campo que sacaria de esta frase y se mira si ESE campo
    es por el que se ordeno. Una sola definicion, dos usos, como `_stems`.

    SOLO SE LLAMA CUANDO EL TEXTO YA FALLO, asi que en el caso normal no cuesta
    nada: estas funciones recorren el catalogo."""
    from app.core import filtros_catalogo as FC
    pedidos = [l.get("pedido") or {} for l in (llamadas or [])]
    orden = FC.resolver_orden(restriccion, tienda_id)
    if orden and any(p.get("ordenar_por") == orden["campo"] for p in pedidos):
        return True
    cond = (FC.resolver_exclusion(restriccion, tienda_id)
            or FC.resolver_inclusion(restriccion, tienda_id))
    if cond and any(cond in (p.get("filtros") or []) for p in pedidos):
        return True
    # LA TERCERA PUERTA ES LA DESCRIPCION, y es la que usa la condicion que no
    # entra en ninguna columna: el uso -"para trabajar", "que ande para
    # jugar"-. `uso_recomendado` es prosa, ahi pega cualquier palabra, asi que
    # no hay filtro posible y el codigo la manda al texto con el que se ordena
    # por parecido. Viajar en la descripcion ES viajar en un argumento, que es
    # literalmente lo que esta regla pide.
    return any(_cubierto(restriccion, _norm(p.get("descripcion")))
               for p in pedidos if p.get("descripcion"))


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
