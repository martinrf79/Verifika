"""
EL MOTOR — la UNICA puerta por la que el modelo busca en la fuente.

QUE CAMBIA, y es lo unico que cambia. Hasta hoy el codigo ADIVINABA que fichas
ponerle delante al modelo: leia el mensaje crudo, sacaba palabras, y con eso
elegia cinco productos. El modelo recibia el resultado de una busqueda que
nunca pidio. Ahora la pide el.

POR QUE. El codigo no razona, asi que no puede elegir. Medido el 11-sep sobre
las funciones que adivinan: "que no sea de marca china" resolvia a
`origen no_contiene marc` —la raiz de "marca", que esta en los 880 origenes—,
o sea CERO productos y el bot contestando que no hay nada. No es un bug de esa
funcion: es que traducir una frase a un campo es razonar, y eso lo hace el
modelo o no lo hace nadie.

LA FORMA DE LA BUSQUEDA ES CONSULTA ESTRUCTURADA, y se descarto el resto:

  - PALABRA CLAVE SOLA no alcanza, y esta medido arriba.
  - EMBEDDINGS quedan afuera por la regla 10.4: una cita tiene que poder
    mapearse a un id. Un vecino cercano no se puede verificar mecanicamente, y
    lo que no se verifica no sale al cliente.
  - CONSULTA ESTRUCTURADA es el idioma nativo del modelo: campos y valores, que
    es lo que ya escribe. El codigo la EJECUTA, determinista de punta a punta.

El texto libre no se pierde: entra como UN campo mas de la consulta y lo resuelve
la relevancia, que ya existe y ya pesa por rareza. Es un criterio, no el
mecanismo.

UNA SOLA PUERTA Y UN SOLO NOMBRE. No son tres motores. Son tres MAPAS
—producto, envio, politicas— y un motor, porque el mecanismo de buscar es el
mismo en los tres. Si aparece un segundo motor, es la complejidad volviendo.

LO QUE ESTE MODULO NO HACE, a proposito:
  - No razona. No mira el mensaje del cliente: mira la consulta que el modelo
    escribio.
  - No inventa identidad. Devuelve un veredicto y ante `ambiguo` no elige.
  - No escribe un numero de plata. Devuelve la ficha con el precio ya escrito,
    igual que `fuente._ficha_corta`, y quien lo pone en el texto es `numeros`.

Y CASI TODO ESTO YA ESTABA. `aplicar`, `ordenar`, `rankear_por_cercania` y
`relevancia` viven en `filtros_catalogo` y estan medidas: la grilla entera del
barrido, 687 casos, da cero fallas. El motor las ENSAMBLA y les pone una puerta
con contrato. No es una capa nueva encima; es la puerta que faltaba.
"""
import json

from app.logger import get_logger

log = get_logger(__name__)

NOMBRE = "buscar"

# Tope duro de filas por consulta. El modelo puede pedir menos, nunca mas: una
# busqueda que devuelve cuarenta fichas inunda el prompt y ademas no sirve, que
# es la leccion del catalogo entero que no entra.
TOPE_FILAS = 8
FILAS_POR_DEFECTO = 5

# Cuantas consultas entran en una llamada. Un pedido multiple —"dos auriculares,
# dos mouse y dos memorias"— es UNA llamada con tres consultas, no tres turnos.
TOPE_CONSULTAS = 6

# Hasta cuantos empatados siguen siendo UNA COSA con variantes -el mismo teclado
# en negro, blanco, gris y azul- y no un termino generico. Pasados estos, que el
# cliente haya nombrado una sola cosa y empaten veinte quiere decir que la
# nombro ancho, y ahi mostrar la lista es mejor que repreguntar.
TOPE_AMBIGUO = 4

# Cuantas politicas de la casa vuelven en una llamada. El mismo tope que ya
# usaba `fuente`, y por el mismo motivo: ante un tema ambiguo se sirven TODOS
# los candidatos en vez de elegir, y tres alcanza para eso.
TOPE_TEMAS = 3

# LOS TEMAS QUE EL ENVIO APAGA, y viven ACA desde el 13-sep. Con una tarifa
# exacta cotizada, la politica publica apenas el RANGO -"de 5.000 a 12.000"- y
# el modelo escribia el numero flojo teniendo el bueno al lado. El apagado
# estaba en el turno, que era el que empujaba el envio; ahora las dos cosas se
# piden por esta puerta y la decision vive donde se ven las dos.
TEMAS_DEL_ENVIO = ("costo_envio", "envios")


# Cuantos pares de compatibilidad se evaluan en una llamada. Un armado -"¿la
# placa entra en esta mother, y la memoria?"- son dos o tres pares; mas que eso
# no es una pregunta de un cliente, es un barrido.
TOPE_COMPAT = 4

# Cuantas entradas de criterio vuelven en una llamada. El mismo tope que las
# politicas: ante un tema ambiguo se sirven todos los candidatos en vez de
# elegir, y tres alcanza para eso.
TOPE_CRITERIO = 3


class _Cond:
    """La condicion como la espera `filtros_catalogo.aplicar`, que lee por
    atributo. El modelo manda JSON, o sea diccionarios; esto es el unico
    adaptador y vive aca para que `aplicar` no tenga que saber de dos formas."""

    __slots__ = ("campo", "operador", "valor")

    def __init__(self, d: dict):
        self.campo = str((d or {}).get("campo") or "")
        self.operador = str((d or {}).get("operador") or "")
        self.valor = (d or {}).get("valor", "")


# ── EL ESQUEMA QUE VE EL MODELO ─────────────────────────────────────────────
#
# VIAJA COMO HERRAMIENTA DEL PROVEEDOR, NO COMO TEXTO. Es el primero de los
# tres candados de la FICHA 50: el modelo la ve en cada turno, con los nombres
# de campo validados por el enum. Un campo que no esta en el catalogo no se
# puede ni nombrar.
#
# LOS ENUMS SALEN DE LA FUENTE VIVA, igual que siempre. Tienda nueva, catalogo
# nuevo, esquema nuevo, sin tocar una linea de codigo.


def _equipos(tienda_id: str) -> str:
    """Los equipos que el vocabulario de compatibilidad conoce, con la etiqueta
    que lee un cliente. Salen de la FUENTE viva -`compatibilidad_vocabulario.
    json`-, igual que el enum de campos: una tienda nueva trae los suyos sin
    tocar una linea. Son doce y caben; el alias -"de apple", "la play"- lo
    resuelve el codigo, asi que no hace falta escribirlos aca."""
    try:
        from app.core.compatibilidad import vocabulario
        v = vocabulario(tienda_id)
        etq = [str((d or {}).get("etiqueta") or pid)
               for pid, d in (v.get("plataformas") or {}).items()]
        return ", ".join(etq)
    except Exception as e:  # noqa: BLE001 — sin vocabulario se pide en prosa
        log.warning("motor_equipos_error", tienda_id=tienda_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")
        return "una notebook, una PC, una consola, un celular"


def esquema(tienda_id: str) -> dict:
    """La herramienta tal como viaja al modelo, en formato OpenAI-compatible."""
    from app.core.filtros_catalogo import (OPERADORES, SIN_CAMPO,
                                           campos_filtrables,
                                           campos_ordenables, leyenda,
                                           recorrida)
    r = recorrida(tienda_id)
    campos = sorted(campos_filtrables(tienda_id))
    categorias = [c for c, _ in r.get("categorias") or []]
    # EL TOPE DE DESTINOS LO PONE QUIEN COTIZA, y se lee de ahi en vez de
    # copiarlo: un numero escrito dos veces se separa el dia que uno cambia.
    from app.core.fuente import TOPE_DESTINOS as TOPE_ENVIOS
    ordenables = campos_ordenables(tienda_id)
    vocab = leyenda(tienda_id)
    equipos = _equipos(tienda_id)
    consulta = {
        "type": "object",
        "properties": {
            "texto": {
                "type": "string",
                "description": "Las palabras del cliente para buscar por "
                               "parecido. Opcional."},
            "categoria": {
                "type": "string", "enum": categorias,
                "description": "El rubro, si el cliente lo nombro."},
            "condiciones": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "campo": {
                            "type": "string",
                            "enum": campos + [SIN_CAMPO],
                            # LA LEYENDA VIVE ACA, pegada al campo que decide.
                            # El enum cierra los NOMBRES; esto dice, de cada
                            # uno, en cuantos productos esta cargado y CON QUE
                            # PALABRAS esta escrito. Es la parte B del tablero
                            # y sale de la fuente viva, asi que una tienda
                            # nueva trae su vocabulario sin tocar codigo.
                            "description": (
                                "El campo del catalogo. Esto es lo que hay "
                                "adentro de cada uno:\n\n" + vocab)},
                        "operador": {"type": "string",
                                     "enum": list(OPERADORES)},
                        "valor": {"type": "string"},
                    },
                    "required": ["campo", "operador", "valor"]},
                "description": "Lo que el producto tiene que cumplir. Si el "
                               f"catalogo no tiene campo para eso, usa "
                               f"'{SIN_CAMPO}' y se te dice. Si escribis un "
                               "valor que la fuente no usa NO filtro por eso: "
                               "te devuelvo los valores reales para que "
                               "corrijas."},
            # SOLO LOS NUMERICOS, y el enum de los 41 que habia aca era caro
            # y ademas estaba mal: sobre una etiqueta -`color`, `bluetooth`- el
            # orden es alfabetico y no contesta ninguna pregunta de un cliente.
            # `orden_tiene_sentido` ya lo rechazaba DESPUES, o sea que el
            # modelo gastaba una consulta para que el motor le dijera que no.
            "ordenar_por": {
                "type": "object",
                "properties": {
                    "campo": {"type": "string", "enum": ordenables},
                    "direccion": {"type": "string", "enum": ["min", "max"]}},
                "required": ["campo", "direccion"],
                "description": "Para 'el mas barato', 'el mas liviano'."},
            "ids": {
                "type": "array", "items": {"type": "string"},
                "description": "Ids exactos, para volver a un producto que ya "
                               "le mostraste."},
            "busco": {
                "type": "string", "enum": ["uno", "varios"],
                "description": "'uno' si el cliente nombro UN producto "
                               "puntual; 'varios' si pidio opciones. Con "
                               "'uno', si hay dos que pegan igual se te dice "
                               "y tenes que preguntar cual."},
            "cuantos": {"type": "integer",
                        "description": f"Filas, hasta {TOPE_FILAS}."},
            # LA CANTIDAD ES EL CALCULO DE ESTA BOCA, y por eso entra como un
            # campo de la consulta y no como una herramienta nueva. "Dos
            # teclados de esos" vuelve con el subtotal ya hecho, asi el modelo
            # copia en vez de multiplicar. No se confunde con `cuantos`: una
            # dice cuantas FILAS mostrar, la otra cuantas UNIDADES compra.
            "cantidad": {"type": "integer",
                         "description": "Cuantas UNIDADES de cada producto "
                                        "pide el cliente. Con dos o mas te "
                                        "devuelvo el subtotal ya calculado. "
                                        "No es la cantidad de filas."},
            # EL CAMPO `specs` SE BORRO EL 14-sep, y es la vieja que se apaga
            # por la que se prende. Se habia agregado el 13-sep para que el
            # mapa de specs no engordara la ficha, pero lo que engordaba era la
            # PROSA: medido, 60 al 63 por ciento del retorno de toda lista, y
            # las specs completas son mas baratas que ella en los cuatro
            # rubros. Sacada la prosa, las specs entran enteras y no hay nada
            # que pedir. La medicion esta en `fuente._ficha_corta`.
        },
    }
    return {
        "type": "function",
        "function": {
            "name": NOMBRE,
            # LA DESCRIPCION ES EL TABLERO, y por eso dice lo que antes decia
            # el prompt en prosa. El esquema viaja en las vueltas donde SE
            # PUEDE buscar y desaparece en la de contestar, que es justo donde
            # esto ya no sirve; el prompt viajaba las tres. Mudarlo no borra
            # una instruccion: la pone donde se usa.
            #
            # LAS CINCO BOCAS SE NOMBRAN. Una boca que el tablero no nombra no
            # existe para el modelo aunque tenga cable, y hasta hoy se
            # nombraban dos: el catalogo y los temas.
            "description": (
                "Busca en la fuente de la tienda. Es el UNICO lugar del que "
                "salen las fichas, los precios y lo que la casa tiene escrito: "
                "llamala ANTES de hablar de un producto o de una politica, y "
                "si no lo buscaste, no lo tenes.\n"
                "LO QUE PODES PEDIR ACA:\n"
                "- CATALOGO: que hay, que trae, cuanto sale, cuanto stock, "
                "cual cumple tal cosa. Va en `consultas`.\n"
                "- POLITICAS de la casa: garantia, cambios, cuotas, "
                "facturacion, plazos, descuentos. Va en `temas`, corto y con "
                "las palabras del cliente.\n"
                "- COMPATIBILIDAD: si un producto anda con el equipo del "
                "cliente o con otro producto. Va en `compatibilidad`, y sale "
                "de la tabla de la casa, no de tu memoria.\n"
                "- CRITERIO: para que sirve, cual conviene, que diferencia hay "
                "entre dos, que significa gama media. Va en `criterio`, y es "
                "lo que la casa tiene escrito, no tu opinion.\n"
                "- CUENTA: cuanto sale todo junto. Va en `cuenta`, "
                "con los ids y las cantidades; la suma la hago yo.\n"
                "- Todas en la MISMA llamada, y varias consultas "
                "juntas si el cliente pidio varias cosas.\n"
                "- ENVIO: cuanto sale y en cuanto llega. Va en `envios`, "
                "con el lugar que nombro el cliente.\n"
                "Si lo que salio no sirve, volve a llamarla con otra "
                "consulta."),
            "parameters": {
                "type": "object",
                "properties": {
                    "consultas": {"type": "array", "items": consulta,
                                  "description": f"Hasta {TOPE_CONSULTAS}."},
                    # EL MAPA 3, Y ES UN CAMPO MAS DE LA MISMA PUERTA. No hay
                    # una herramienta nueva a proposito: el mecanismo de buscar
                    # en la fuente es el mismo, cambia que se busca. Una
                    # herramienta aparte serian dos puertas para lo mismo.
                    #
                    # NO LLEVA ENUM, y va contra la costumbre del resto del
                    # esquema. Los 129 temas pesaban 2.299 bytes en CADA
                    # llamada, y ese enum ya se saco una vez por eso (FICHA 06,
                    # 23-ago). El modelo nombra el tema con LAS PALABRAS DEL
                    # CLIENTE y `fuente.certificar_temas` lo resuelve contra las
                    # señas que la fuente ya tiene escritas: la atadura esta en
                    # el codigo, no en el esquema.
                    "temas": {
                        "type": "array", "items": {"type": "string"},
                        "description": (
                            "Lo que el cliente pregunta sobre la CASA y no "
                            "sobre un producto: garantia, cambios, cuotas, "
                            "facturacion, plazos. Nombra el tema CORTO, en "
                            "POCAS PALABRAS y con las del cliente: 'garantia', "
                            "'cambios', no la frase entera que escribio. Te "
                            "devuelvo lo que la casa tiene escrito, y si no lo "
                            "tiene te lo digo y se lo decis asi. Hasta "
                            f"{TOPE_TEMAS}.")},
                    # LA BOCA DE COMPATIBILIDAD, Y ES UN CAMPO MAS DE LA MISMA
                    # PUERTA (13-sep-2026). Mismo criterio que `temas`: el
                    # mecanismo de preguntarle a la fuente es el mismo, cambia
                    # QUE se le pregunta. Una herramienta aparte serian dos
                    # puertas para lo mismo.
                    #
                    # CONSUME UN ID CERTIFICADO, y eso es la regla 10.0: la
                    # identidad la decide una funcion determinista, no esta
                    # pregunta. Compatibilidad e identidad siguen siendo dos
                    # ejes y no se mezclan.
                    #
                    # LO QUE CAMBIO EL 15-sep ES QUIEN CERTIFICA, no si se
                    # certifica: `producto` acepta el nombre que dijo el
                    # cliente y lo resuelve el CODIGO, adentro de la boca, con
                    # la misma consulta que escribiria el modelo. Antes hacia
                    # falta una vuelta previa para conseguir el id, y medido el
                    # 15-sep esa vuelta se comia la pregunta: el paso uno
                    # volvia `ambiguo` y el turno se quedaba ahi. El motivo
                    # entero esta en `_un_compat`.
                    # LA BOCA DE ENVIO, QUE HASTA HOY EMPUJABA EL CODIGO.
                    # El destino sigue siendo determinista -lo clasifica la
                    # tabla, no el modelo-; lo que cambia es quien PIDE. El
                    # modelo nombra el lugar con las palabras del cliente, que
                    # ademas es la unica parte del envio que no es argentina.
                    "envios": {
                        "type": "array", "items": {"type": "string"},
                        "description": (
                            "Los destinos que nombro el cliente, con SUS "
                            "palabras: 'Posadas', 'CP 5121'. Si lo dijo turnos "
                            "atras esta en tu memoria. Te devuelvo la tarifa "
                            "exacta, el plazo y el hueco que copias donde vaya "
                            f"el costo: el monto NO lo escribis vos. Hasta "
                            f"{TOPE_ENVIOS}.")},
                    "compatibilidad": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "producto": {
                                    "type": "string",
                                    "description": "El id que te devolvi, o "
                                                   "el nombre que uso el "
                                                   "cliente: no hace falta "
                                                   "buscarlo antes, lo "
                                                   "resuelvo yo. Si hay dos "
                                                   "que pegan igual te los "
                                                   "devuelvo y preguntas."},
                                "con": {
                                    "type": "string",
                                    "description": "El equipo del cliente —"
                                                   + equipos + "— o el id de "
                                                   "OTRO producto."}},
                            "required": ["producto", "con"]},
                        "description": (
                            "'¿anda con mi PS5?', '¿esta memoria entra en "
                            "esta mother?'. Vuelve compatible, incompatible o "
                            "sin_dato con el motivo escrito; el sin_dato no "
                            "se completa, se avisa. Hasta "
                            f"{TOPE_COMPAT}.")},
                    # LA BOCA DE CRITERIO, Y ES UN CAMPO MAS DE LA MISMA PUERTA
                    # (13-sep-2026). Cuarta vez el mismo criterio: `temas`,
                    # `compatibilidad`, `envios` y esto preguntan a la fuente
                    # por areas distintas con el MISMO mecanismo. Una
                    # herramienta aparte serian dos puertas para lo mismo.
                    #
                    # TAMPOCO LLEVA ENUM, por lo mismo que `temas`: los 129
                    # nombres pesaban 2.299 bytes en cada llamada. El modelo lo
                    # nombra con LAS PALABRAS DEL CLIENTE y lo certifica
                    # `fuente.criterio_de` contra los disparadores que la
                    # fuente ya tiene escritos.
                    "criterio": {
                        "type": "array", "items": {"type": "string"},
                        "description": (
                            "Para que SIRVE algo, cual CONVIENE segun el uso, "
                            "que diferencia hay entre dos, y que significa "
                            "gama baja o media aca. Nombralo CORTO y con las "
                            "palabras del cliente: 'mouse', 'para jugar', "
                            "'gama media'. Es el criterio de la casa, no una "
                            "ficha: no trae numeros ni precios, esos salen de "
                            "`consultas`. Si la casa no lo tiene escrito te lo "
                            f"digo y se lo decis asi. Hasta {TOPE_CRITERIO}.")},
                    # LA CUENTA, Y NO ES UNA BOCA: NO TIENE AREA DE FUENTE.
                    # Es aritmetica sobre lo que las bocas ya devolvieron, y
                    # por eso vive en el RETORNO. Es un campo mas de la misma
                    # puerta por el mismo criterio que las otras cinco: el
                    # mecanismo es el mismo, cambia que se pide.
                    #
                    # LOS DESTINOS NO SE PIDEN ACA: salen de `envios`, en esta
                    # misma llamada. Pedirlos dos veces abre la puerta a que
                    # las dos respuestas no coincidan.
                    "cuenta": {
                        "type": "object",
                        "properties": {
                            "items": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "cantidad": {"type": "integer"}},
                                    "required": ["id"]}},
                            "reparto_pago": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "medio": {"type": "string"},
                                        "porcentaje": {"type": "number"}},
                                    "required": ["medio", "porcentaje"]},
                                "description": (
                                    "Solo si reparte el pago: '70 transferencia "
                                    "30 Mercado Pago'. Suman 100. El descuento "
                                    "lo aplico yo.")}},
                        "description": (
                            "Cuanto sale TODO junto. Los `id` que te devolvi, "
                            "con su cantidad. Te vuelve el total ya sumado "
                            "—productos, envio de los destinos que pediste y "
                            "descuento— y el detalle. No sumes vos.")}},
                "required": []},
        },
    }


# ── LA BUSQUEDA ─────────────────────────────────────────────────────────────


def _universo(catalogo: list, categoria: str, tienda_id: str) -> tuple:
    """El catalogo acotado al rubro que pidio el modelo. Si el rubro no existe
    se dice y se busca en todo: acotar a la nada devolveria cero en silencio."""
    from app.core.filtros_catalogo import _norm
    cat = _norm(categoria)
    if not cat:
        return catalogo, ""
    dentro = [p for p in catalogo if _norm(p.get("categoria")) == cat]
    if dentro:
        return dentro, ""
    return catalogo, f"la categoria '{categoria}' no existe en el catalogo"


def _por_ids(catalogo: list, ids: list) -> list:
    pedidos = [str(i).strip() for i in (ids or []) if str(i).strip()]
    if not pedidos:
        return []
    porid = {str(p.get("id")): p for p in catalogo}
    return [porid[i] for i in pedidos if i in porid]


def _con_la_cuenta(filas: list, unidades: int, trace_id: str = "") -> None:
    """EL SUBTOTAL DE CADA LINEA, HECHO POR `calculadora` (13-sep-2026).

    ES EL CALCULO DE ESTA BOCA, y el criterio de la FICHA 52: cada boca trae su
    calculo adentro. Envio ya lo hacia —su tabla de tarifas es fuente y el
    codigo deriva la del destino— y catalogo no tenia el suyo: "dos teclados de
    esos" volvia con el precio unitario y la multiplicacion quedaba para el
    modelo, que es justo lo que el modelo no tiene que hacer.

    POR QUE LA HERRAMIENTA Y NO UN `precio * cantidad` ACA. Porque seria un
    SEGUNDO lugar donde el repo hace cuentas de plata, y el dia que las dos se
    separen nadie va a saber cual manda. `calculadora.calculate_total` es la
    herramienta de la plata, esta escrita, esta medida, y desde el apagon del
    11-sep NO LA LLAMABA NADIE desde `app/`: enchufarla aca no agrega una pieza,
    revive la que estaba.

    LO QUE NO HACE, y es la mitad que no le toca a esta boca: el total del
    pedido, el envio y el descuento. Eso cruza bocas y vive en el retorno. Por
    eso se llama con `items` y nada mas —sin `pago`, sin `destinos`, sin
    `items_extra`— y de lo que devuelve se usa UNA cosa: el subtotal de cada
    linea.

    No devuelve nada: escribe sobre las filas. Si la cuenta falla, la fila
    queda con su cantidad y sin subtotal, que es honesto; lo que no puede pasar
    es que una cuenta rota tumbe la busqueda.
    """
    if unidades <= 1 or not filas:
        return
    from app.core.fuente import _plata
    try:
        from app.core.calculadora import calculate_total
        # SIN VALIDAR STOCK: esto es una LISTA de opciones, no un pedido. El
        # motivo entero y la medicion estan en `calculadora.calculate_total`.
        # El stock de cada fila viaja igual en la ficha, asi que el modelo lo
        # ve y lo puede decir; lo que no puede pasar es que un agotado deje sin
        # subtotal a los otros cuatro.
        r = calculate_total(items=[{"product_id": f.get("id"),
                                    "cantidad": unidades}
                                   for f in filas if f.get("id")],
                            validar_stock=False)
        if not r.get("ok"):
            log.warning("motor_cuenta_sin_ok", trace_id=trace_id,
                        motivo=str(r.get("mensaje_para_llm"))[:120])
            return
        por_id = {str(d.get("id")): d for d in (r.get("detalle") or [])}
    except Exception as e:  # noqa: BLE001 — una cuenta rota no tumba la busqueda
        log.warning("motor_cuenta_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")
        return
    for f in filas:
        d = por_id.get(str(f.get("id")))
        if not d or d.get("subtotal") in (None, ""):
            continue
        f["subtotal_ars"] = d["subtotal"]
        # Ya escrito, igual que el precio: una cadena se copia, un numero
        # pelado invita a redondearlo o a sumarle el envio de memoria.
        f["subtotal"] = _plata(d["subtotal"])


def _la_cuenta(pedido: dict, envios: dict, tienda_id: str,
               trace_id: str = "") -> dict:
    """LA CUENTA DEL RETORNO — lo que CRUZA bocas, calculado ANTES de redactar.

    QUE ES Y POR QUE VIVE ACA. Cada boca trae su calculo adentro: catalogo
    multiplica por la cantidad, envio saca la tarifa de su tabla. Pero el TOTAL
    del pedido, el descuento por transferencia y el reparto entre medios de
    pago no son de ninguna boca: cruzan todas. La FICHA 52 los pone en el
    RETORNO, y el punto es el ANTES: el modelo escribe con el numero resuelto
    en la mano en vez de dejar un hueco que el codigo tapa despues.

    QUE CAMBIA. Hasta hoy `{{total}}` lo resolvia `numeros` SUMANDO las cifras
    que ya estaban escritas en el mensaje. Esa suma no puede conocer el
    descuento por transferencia ni el reparto 70/30, asi que el setenta treinta
    no existia: `calculate_total` es la unica que llama a `pago_split`, y desde
    el apagon del 11-sep el TOTAL del pedido no la llamaba nunca.

    TODA LA PLATA LA HACE `calculadora`, incluido el envio. La tarifa no se
    suma a mano aca: entra como `items_extra` por el mismo camino que la
    calculadora ya tiene escrito, con el `concepto` que ella misma deriva de la
    provincia. Un segundo lugar donde este repo sume plata es un segundo lugar
    que se puede separar del primero.

    LOS DESTINOS NO SE DECLARAN: salen de lo que la boca de envio YA cotizo en
    esta misma llamada. Preguntarselos al modelo seria pedir dos veces el mismo
    dato y abrir la puerta a que las dos respuestas no coincidan.

    No lanza: una cuenta rota deja al turno sin total, nunca con uno inventado.
    """
    items = []
    for x in (pedido or {}).get("items") or []:
        pid = str((x or {}).get("id") or "").strip()
        if not pid:
            continue
        try:
            cant = max(1, int((x or {}).get("cantidad") or 1))
        except (TypeError, ValueError):
            cant = 1
        items.append({"product_id": pid, "cantidad": cant})
    if not items:
        return {}

    from app.core.calculadora import calculate_total, cotizar_envio

    # EL ENVIO ENTRA POR LA CALCULADORA, con el concepto que ella deriva de la
    # provincia. Un destino que no clasifica no suma nada y tampoco rompe: la
    # cuenta sale sin envio y el retorno lo dice por la boca de envio.
    extras = []
    for fila in (envios or {}).get("filas") or []:
        destino = str(fila.get("destino") or "").strip()
        if not destino or not fila.get("monto_ars"):
            continue
        try:
            q = cotizar_envio(destino)
        except Exception as e:  # noqa: BLE001 — sin concepto no se suma envio
            log.warning("motor_cuenta_envio_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
            continue
        if q.get("ok") and q.get("concepto"):
            extras.append({"faq_tema": "costo_envio",
                           "concepto": q["concepto"]})

    reparto = [x for x in ((pedido or {}).get("reparto_pago") or [])
               if isinstance(x, dict) and x.get("medio")]

    try:
        r = calculate_total(items=items, items_extra=extras or None,
                            pago=reparto or None)
    except Exception as e:  # noqa: BLE001 — una cuenta rota no tumba el turno
        log.warning("motor_cuenta_total_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:150]}")
        return {}
    if not r.get("ok"):
        # EL MOTIVO VIAJA. Un total que no se pudo hacer y vuelve mudo se lee
        # como un total de cero; con el motivo escrito el modelo dice que le
        # falta para poder darlo, que es la respuesta 5 de las seis.
        return {"sin_total": str(r.get("mensaje_para_llm") or
                                 "no se pudo armar la cuenta")}

    from app.core.fuente import _plata
    fuera = {"total_ars": r.get("total_ars"),
             "total": _plata(r.get("total_ars")),
             # LA PRESENTACION YA VIENE ESCRITA POR LA CALCULADORA, renglon por
             # renglon, con el subtotal, el envio y el reparto. Reescribirla
             # aca seria la segunda descripcion de lo mismo.
             "detalle": r.get("presentacion") or ""}
    if r.get("total_final_ars") is not None:
        fuera["total_final_ars"] = r["total_final_ars"]
        fuera["total_final"] = _plata(r["total_final_ars"])
    return fuera


def _no_vendemos(texto: str, categoria: str, tienda_id: str):
    """Si lo que se pidio es una categoria que la tienda NO vende, decirlo con
    la alternativa REAL al lado. None si no aplica.

    Se le pasa lo que ESCRIBIO EL MODELO —el texto de la consulta y el rubro—,
    no el mensaje crudo del cliente: el motor no mira el mensaje, mira la
    consulta, y esa es la unica entrada que tiene. Un fallo de esta funcion no
    puede tumbar la busqueda: sin fuente no se niega nada, que es la salida
    honesta que `guia_compra` ya documenta.
    """
    from app.core.guia_compra import categoria_no_vendida
    for frase in (f"{texto} {categoria}".strip(), texto, categoria):
        if not frase:
            continue
        try:
            r = categoria_no_vendida(frase, tienda_id)
        except Exception as e:  # noqa: BLE001 — sin fuente no se niega nada
            log.warning("motor_no_vendidas_error", tienda_id=tienda_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
            return None
        if r:
            pedida, alt = r
            return {"pedido": pedida,
                    "en_su_lugar": alt or "",
                    "motivo": f"la tienda no vende {pedida}"
                              + (f"; lo mas cercano que si hay es {alt}"
                                 if alt else "; no hay nada equivalente")}
    return None


def _una(consulta: dict, catalogo: list, tienda_id: str) -> dict:
    """UNA consulta del modelo contra el catalogo. Devuelve el resultado
    ENTERO: lo que trajo, cuantos habia, que no se pudo aplicar y por que.

    NUNCA VUELVE VACIA SIN MOTIVO ESCRITO. Es la regla de Martin del 2-ago y la
    razon por la que este contrato es mas grande que "una lista de productos":
    un cero sin explicacion hace que el modelo le diga al cliente que no hay,
    cuando lo que pasa es que la fuente no tiene el dato.
    """
    from app.core.fuente import _ficha_corta
    from app.core.filtros_catalogo import (alguno_lo_nombra, aplicar,
                                           dato_que_falla, ordenar,
                                           orden_tiene_sentido,
                                           pesos_por_rareza,
                                           rankear_por_cercania, relevancia)
    c = consulta or {}
    texto = str(c.get("texto") or "").strip()
    tope = c.get("cuantos")
    try:
        tope = int(tope)
    except (TypeError, ValueError):
        tope = FILAS_POR_DEFECTO
    tope = max(1, min(TOPE_FILAS, tope))
    try:
        unidades = max(1, int(c.get("cantidad") or 1))
    except (TypeError, ValueError):
        unidades = 1
    # EL DETALLE LO DECIDE `busco`, Y NADA MAS (14-sep-2026). Con `uno` el
    # cliente pregunta por UN producto y quiere el parrafo; con `varios` pidio
    # opciones, y la prosa de cinco fichas era el 63% del retorno. Las specs
    # viajan enteras en los dos casos: el campo `specs` de la consulta se borro
    # porque dejo de significar algo. El motivo entero esta en
    # `fuente._ficha_corta`, con la medicion al lado.
    detalle = str(c.get("busco") or "") == "uno"
    specs_pedidas = None

    no_aplicado, notas = [], []

    # 1. POR ID PRIMERO. Es como resuelve la memoria —"el que me mostraste
    #    antes"— y no necesita ni parecido ni condiciones.
    if c.get("ids"):
        filas_id = _por_ids(catalogo, c["ids"])
        filas = filas_id
        faltan = [str(i) for i in c["ids"] if str(i) not in
                  {str(p.get("id")) for p in filas}]
        fichas_id = [_ficha_corta(p, unidades, specs_pedidas, detalle)
                     for p in filas[:tope]]
        _con_la_cuenta(fichas_id, unidades)
        return {"veredicto": "existe" if filas else "no_existe",
                "cuantos_habia": len(filas),
                "filas": fichas_id,
                "no_aplicado": ([{"campo": "ids", "motivo":
                                  f"no existen estos ids: {', '.join(faltan)}"}]
                                if faltan else []),
                "sin_dato": 0, "empatados": 0,
                "motivo": "" if filas else "ninguno de esos ids esta en el catalogo"}

    # EL "NO LO VENDEMOS" VA PRIMERO, Y ESE ES EL PUNTO (13-sep-2026).
    #
    # Estaba escrito abajo, colgando de "si no quedo ninguno", y ahi NO CORRIA
    # NUNCA: una consulta con `texto: celular` y sin condiciones deja el
    # universo entero, la relevancia ordena los 880 y vuelven CINCO PRODUCTOS
    # con veredicto `existe`. O sea que a "tenes celulares?" el motor contesta
    # que si, con cinco cosas que no son celulares, y el modelo no tiene como
    # saberlo. Es la respuesta 2 dicha como la 3 al reves, que la FICHA 52
    # llama el defecto mas caro del nicho.
    #
    # La relevancia SIEMPRE devuelve algo: esa es su naturaleza y por eso no
    # puede ser la que decida si existe. Lo decide la fuente, antes.
    no_lo_vendemos = _no_vendemos(texto, str(c.get("categoria") or ""),
                                  tienda_id)
    if no_lo_vendemos:
        # LAS FILAS SON LAS DE LA ALTERNATIVA REAL, no las del parecido. Es la
        # respuesta 3 entera: no hay ficha de eso, y esto SI tengo en su lugar.
        alt = no_lo_vendemos.get("en_su_lugar") or ""
        de_la_alt, _ = _universo(catalogo, alt, tienda_id) if alt else ([], "")
        filas_alt = [_ficha_corta(p, unidades, specs_pedidas, detalle)
                     for p in (de_la_alt if alt else [])[:tope]]
        _con_la_cuenta(filas_alt, unidades)
        return {"veredicto": "no_existe",
                "cuantos_habia": 0,
                "de_cuantos_se_miro": len(catalogo),
                "filas": filas_alt,
                "no_aplicado": [],
                "sin_dato": 0,
                "empatados": 0,
                "no_lo_vendemos": no_lo_vendemos,
                "motivo": no_lo_vendemos["motivo"]}

    universo, aviso = _universo(catalogo, str(c.get("categoria") or ""),
                                tienda_id)
    if aviso:
        no_aplicado.append({"campo": "categoria", "motivo": aviso})
    de_cuantos = len(universo)

    # 2. LAS CONDICIONES. `aplicar` ya informa el tercer balde —los que no
    #    tienen el dato— y los filtros que no se pudieron aplicar con su motivo.
    # EL HUECO DE VALOR, ANTES DE FILTRAR (13-sep-2026). Si la fuente no
    # escribe esa palabra en ese campo, la condicion no se aplica y se DICE con
    # los valores reales al lado. Filtrarla daria cero, y un cero se lee como
    # "no lo tenemos" cuando lo que pasa es que el modelo escribio `japon`
    # donde la fuente dice `china, taiwan o corea segun linea`.
    #
    # Es la misma escuela que `SIN_CAMPO` y corre solo sobre los campos cuyo
    # vocabulario se conoce entero. Sobre `modelo`, con 482 valores, el que
    # contesta es el rescate por cercania, que ya existe.
    from app.core.filtros_catalogo import condicion_sin_vocabulario
    crudas = []
    for x in (c.get("condiciones") or []):
        campo = str((x or {}).get("campo") or "")
        reales = condicion_sin_vocabulario(campo, str((x or {}).get("operador")
                                                      or ""),
                                           (x or {}).get("valor", ""),
                                           tienda_id)
        if reales is None:
            crudas.append(x)
            continue
        no_aplicado.append({
            "campo": campo,
            "motivo": f"la fuente no escribe '{(x or {}).get('valor')}' en "
                      f"{campo}; lo que dice es: {' | '.join(reales)}. No se "
                      f"filtro por eso: volve a pedir con una de esas"})
    conds = [_Cond(x) for x in crudas]
    r = aplicar(universo, conds, tienda_id) if conds else {
        "productos": universo, "aplicados": [], "descartados": [], "sin_dato": 0}
    no_aplicado.extend(r["descartados"])
    quedan = r["productos"]
    cumplieron = len(quedan)
    empatados = 0
    veredicto = "existe"

    # 3. EL RESCATE. Si ninguna cumple todo, se trae lo mas parecido y se dice
    #    cual condicion falla. Devolver vacio seria decirle al cliente que no
    #    existe lo que si existe con una condicion menos.
    rescate = False
    if conds and not quedan:
        quedan, empatados, incumple = rankear_por_cercania(
            universo, conds, tienda_id)
        veredicto = "no_existe"
        rescate = True
        notas.append(f"ninguno cumple todo; esto es lo mas parecido, "
                     f"incumple {incumple} de {len(conds)}")
        if empatados > 1:
            notas.append(f"{empatados} estan igual de lejos y se desempato "
                         f"por precio")

    # 4. EL ORDEN. Solo si ordenar por ese campo ordena por ALGO: sobre valores
    #    que son etiquetas —"China", "Negro"— el orden es alfabetico y no
    #    contesta ninguna pregunta que un cliente pueda hacer.
    orden = c.get("ordenar_por") or {}
    campo_orden = str(orden.get("campo") or "")
    orden_aplicado = False
    if campo_orden:
        if quedan and orden_tiene_sentido(quedan, campo_orden, tienda_id):
            quedan = ordenar(quedan, campo_orden,
                             str(orden.get("direccion") or "min"), tienda_id)
            orden_aplicado = True
        else:
            no_aplicado.append({
                "campo": campo_orden,
                "motivo": "ordenar por ese campo no ordena por nada: sus "
                          "valores son etiquetas, no magnitudes"})
    # EL PARECIDO SE CALCULA SIEMPRE QUE HAYA TEXTO, Y ANTES COLGABA DEL ORDEN
    # (13-sep-2026). Estaba escrito como `elif`, asi que una consulta con
    # `ordenar_por` no calculaba puntajes y por lo tanto NO PODIA ver una
    # ambiguedad de identidad. Medido sobre el catalogo vivo: "Teclado Logitech
    # K380" con `busco: uno` devuelve `ambiguo` con los dos que pegan igual, y
    # el MISMO pedido con un orden por precio devuelve `existe` con cinco y el
    # modelo eligiendo. La obligacion de preguntar de la regla 10.0 se perdia
    # por una perilla que no tiene nada que ver con la identidad.
    puntos = {}
    if texto and quedan:
        raras = pesos_por_rareza(quedan, texto)
        puntos = {id(p): relevancia(p, texto, raras) for p in quedan}
        if not campo_orden:
            quedan = sorted(quedan, key=lambda p: (-puntos[id(p)],
                                                   p.get("precio_ars") or 0))
        # AMBIGUO ES DE IDENTIDAD, Y SOLO DE IDENTIDAD.
        #
        # Es la regla 10.0: ante `ambiguous` el modelo esta OBLIGADO a
        # preguntar, no a elegir. Eso vale cuando el cliente nombro UNA cosa y
        # el catalogo tiene dos que le pegan igual —el mismo teclado en negro y
        # en blanco—: elegir ahi es inventar identidad.
        #
        # NO vale para un empate cualquiera. Que 171 notebooks esten igual de
        # lejos de un precio imposible no es una ambiguedad: es que la
        # condicion no se puede cumplir, y eso es `no_existe` con el rescate al
        # lado. Confundir los dos haria que el bot repregunte donde tiene que
        # contestar.
        #
        # LA MARCA LA DECLARA EL MODELO, Y ANTES ERA EL TOPE DE FILAS. Hasta el
        # 11-sep la condicion era `cuantos == 1`, o sea que se leia la
        # INTENCION del cliente desde una perilla de paginado. Dos agujeros
        # medidos: el modelo que pedia cinco filas de un producto puntual no
        # recibia la ambiguedad NUNCA —y ahi es donde elegir es inventar—, y
        # cualquier consulta con `cuantos: 1` la recibia aunque el cliente
        # hubiera pedido "el mas barato". Si el cliente nombro una cosa o pidio
        # opciones es IDIOMA, y el idioma lo lee el modelo: ahora lo declara en
        # `busco` y el codigo certifica el empate, que es lo unico que el
        # codigo puede saber.
        #
        # EL EMPATE DEL RESCATE NO SE PISA. `empatados` puede venir cargado de
        # arriba -"52 estan igual de lejos"- y eso es informacion del cliente:
        # solo se lo reemplaza cuando de verdad hay una ambiguedad de
        # identidad, nunca con un cero de paso.
        # EL MEJOR PUNTAJE SE BUSCA CON `max`, no en la primera fila: con un
        # orden explicito la primera es la mas barata, no la que mas pega.
        # ── EL UMBRAL DE IDENTIDAD ──────────────────────────────────────
        #
        # QUE TAPA, medido el 14-sep sobre el catalogo vivo: `dron`,
        # `bicicleta`, `zapatillas`, `guitarra`, `perfume`, `colchon` y
        # `taladro` volvian `existe` con los MISMOS cinco mouse. Ocho falsos
        # positivos sobre doce pedidos de cosas que la tienda no vende. El bot
        # le decia que si al que pregunto por algo que no existe, que es el
        # defecto mas caro del nicho.
        #
        # POR QUE NO LO TAPA `no_vendidas.json`: esa lista solo conoce las
        # palabras que alguien escribio adentro. Perseguir esto con una lista
        # de palabras es el camino que este repo ya recorrio tres veces y del
        # que ya volvio.
        #
        # LA REGLA, y no tiene numero: si NINGUNA ficha del catalogo se LLAMA
        # algo de lo que pidio, no existe. `relevancia` no puede decidirlo
        # porque es un ordenador; `lo_nombra` mira identidad y nada mas.
        #
        # SOLO CORRE SIN RECORTE, y esa es la otra mitad. Si la consulta trajo
        # una categoria o una condicion que SI se aplico, el universo ya esta
        # acotado por algo real y el texto es una caracteristica, no una
        # identidad: "teclado retroiluminado" no se llama asi en ninguna ficha
        # y tiene que seguir contestando.
        sin_identidad = (not r.get("aplicados")
                         and de_cuantos == len(catalogo)
                         and not alguno_lo_nombra(quedan, texto))
        if sin_identidad:
            veredicto = "no_existe"
            if max(puntos.values()) <= 0 and not orden_aplicado:
                # NI NOMBRADO NI MENCIONADO. Mostrar "lo mas parecido" aca
                # seria mostrar los cinco mas baratos, que no se parecen a
                # nada: es ruido adentro de la caja donde todo lo demas es
                # dato certificado.
                quedan = []
                # EL MOTIVO DICE EL HECHO Y NO CONCLUYE DE MAS. "Ninguna ficha
                # lo nombra" no es lo mismo que "la tienda no lo vende": esa
                # frase es de `no_vendidas`, que la tiene escrita y curada. Aca
                # puede ser que el cliente lo diga con una palabra que la casa
                # no escribe -"algo para jugar"-, y ahi lo que corresponde es
                # volver a buscar por categoria, no decirle que no hay.
                #
                # LAS CATEGORIAS NO SE LISTAN ACA: ya viajan en el enum del
                # esquema, en cada llamada. Escribirlas de nuevo seria la
                # segunda copia de lo mismo.
                notas.append(f"ninguna ficha del catalogo dice '{texto}': ni "
                             f"en el nombre, ni en la marca, ni en el modelo, "
                             f"ni en los tags, ni en la categoria, ni en la "
                             f"prosa. Si asi es como lo dice el cliente y no "
                             f"como lo escribe la tienda, volve a buscar con "
                             f"una categoria")
            elif orden_aplicado:
                # EL ORDEN EXPLICITO PIDE UN EXTREMO, Y EL EXTREMO EXISTE
                # AUNQUE LAS PALABRAS NO NOMBREN NADA. "Lo mas barato que
                # tengas" no nombra un producto y tiene que contestar con los
                # mas baratos; medido el 14-sep, el umbral sin esta rama se lo
                # llevaba puesto y devolvia cero.
                #
                # EL VEREDICTO IGUAL ES `no_existe`, y ahi esta lo que salva
                # "zapatillas mas baratas": las filas son el extremo real del
                # catalogo, pero el motivo dice que ninguna se llama asi. El
                # modelo contesta las dos cosas -eso no hay, esto es lo mas
                # barato que si tengo- en vez de elegir una.
                notas.append(f"ninguna ficha se llama '{texto}'; estas son las "
                             f"del orden que pediste, no las que nombraste")
            else:
                notas.append(f"ninguna ficha se llama '{texto}'; estas lo "
                             f"mencionan y es lo mas parecido que hay")

        if (not sin_identidad and str(c.get("busco") or "") == "uno"
                and len(quedan) > 1):
            mejor = max(puntos.values())
            iguales = [p for p in quedan if puntos[id(p)] == mejor]
            if 1 < len(iguales) <= TOPE_AMBIGUO and mejor > 0:
                veredicto = "ambiguo"
                empatados = len(iguales)
                notas.append(f"hay {empatados} que pegan igual con lo que "
                             f"pidio: no elijas, pregunta cual")
                # SE SIRVEN TODOS LOS CANDIDATOS, no el primero. Decirle al
                # modelo que hay dos y mostrarle uno es pedirle que pregunte
                # por algo que no puede ver. Es la misma linea que ya tiene
                # `certificar_temas` ante un tema ambiguo.
                quedan = iguales
                tope = min(TOPE_FILAS, max(tope, empatados))

    if not quedan:
        veredicto = "no_existe"
        notas.append("el catalogo no tiene nada de eso")

    # LA FILA DEL RESCATE DICE POR QUE NO CUMPLE, Y ES EL DATO REAL.
    #
    # Medido el 11-sep sobre el catalogo vivo: "un mouse que no sea de
    # fabricacion china" devuelve `no_existe` -los 52 lo son- con tres mouse al
    # lado como lo mas parecido, y esas tres fichas viajan MUDAS: el campo por
    # el que se filtro no esta en la ficha corta, porque `campos_ficha` trae los
    # del rubro. O sea que el modelo recibe tres mouse sin un solo dato que lo
    # contradiga y un motivo en prosa a un renglon de distancia. Ofrecer lo que
    # el cliente acaba de excluir esta a un paso.
    #
    # Con esto cada fila del rescate lleva `no_cumple` con el VALOR de la ficha
    # —"origen: Marca Genius de Taiwan. Fabricado en China."—, asi el modelo
    # puede decir la verdad entera: no tengo ninguno sin eso, y estos son los
    # que hay. Y el cliente decide, que es lo que no puede hacer si no lo ve.
    #
    # `dato_que_falla` ya estaba escrita para esto, con su caso y su fecha, y no
    # la llamaba nadie: quedo suelta cuando se apago el bloque que la usaba.
    filas = []
    for p in quedan[:tope]:
        f = _ficha_corta(p, unidades, specs_pedidas, detalle)
        if rescate:
            motivo_fila = dato_que_falla(p, conds, tienda_id)
            if motivo_fila:
                f["no_cumple"] = motivo_fila
        filas.append(f)
    _con_la_cuenta(filas, unidades)

    return {"veredicto": veredicto,
            "cuantos_habia": cumplieron if conds else de_cuantos,
            "de_cuantos_se_miro": de_cuantos,
            "filas": filas,
            "no_aplicado": no_aplicado,
            "sin_dato": r.get("sin_dato", 0),
            "empatados": empatados,
            "motivo": "; ".join(notas)}


def _salida(resultados, temas, sin_resolver, compat, envios, criterio,
            sin_criterio, cuenta=None) -> dict:
    """El retorno, con UNA sola forma. Las cajas que nadie pidio no viajan: una
    clave vacia en cada turno es ruido adentro de la caja donde todo lo demas
    es dato certificado."""
    fuera = {"resultados": resultados, "politicas": temas,
             "temas_sin_resolver": sin_resolver}
    if compat:
        fuera["compatibilidad"] = compat
    if envios:
        fuera["envios"] = envios
    if criterio:
        fuera["criterio"] = criterio
    if sin_criterio:
        fuera["criterio_sin_resolver"] = sin_criterio
    if cuenta:
        fuera["cuenta"] = cuenta
    return fuera


def _un_compat(pedido: dict, catalogo: list, tienda_id: str) -> dict:
    """UN par de compatibilidad, certificado. Devuelve {producto, con,
    veredicto, motivo} con veredicto en compatible / incompatible / ambiguo /
    sin_dato.

    EL VEREDICTO LO ESCRIBE EL CODIGO Y EL MOTIVO TAMBIEN. Es el modulo
    `compatibilidad`, que estaba entero y no lo llamaba NADIE desde el turno:
    la tabla se estampa en cada ficha al leer el catalogo -`fuente_producto.
    enriquecer`- y despues se tiraba, porque `_ficha_corta` no la muestra. El
    dato existia, el cable no. De ahi salia que la compatibilidad la contestara
    el modelo de memoria, que es la alucinacion del 29-jul -"anda con cualquier
    notebook", dicho sobre una RAM de escritorio-.

    `sin_dato` NO ES UN ERROR: es la respuesta 2 de la FICHA 52 y se sirve tal
    cual. Un hueco que el modelo completa es peor que un hueco.

    AMBIGUO ES LA REGLA 10.0 otra vez: "de apple" son macOS e iOS a la vez y
    elegir uno seria decidir por el cliente, asi que vuelven los dos y se
    pregunta.
    """
    pid = str((pedido or {}).get("producto") or "").strip()
    con = str((pedido or {}).get("con") or "").strip()
    base = {"producto": pid, "con": con}
    porid = {str(p.get("id")): p for p in catalogo}
    # UN PEDIDO VACIO NO ES UN NOMBRE, y se corta antes de resolver nada: sin
    # producto no hay identidad que certificar, y mandarlo a la busqueda
    # devolveria el catalogo entero como si el cliente hubiera nombrado algo.
    if not pid or not con:
        return {**base, "veredicto": "sin_dato",
                "motivo": "el par vino incompleto: necesito el producto y con "
                          "que lo quiere usar"}
    prod = porid.get(pid)
    if not prod:
        # ── EL DOS PASOS SE RESUELVE ADENTRO (15-sep-2026, FICHA 54, 3.2) ──
        #
        # QUE PASABA. `producto` exigia un id que el modelo YA hubiera
        # recibido, asi que "el teclado K380 anda con mi PS5" costaba dos
        # vueltas: buscar el K380, recibir el id, y recien ahi preguntar. En la
        # practica ni eso: medido el 15-sep, el paso uno volvio `ambiguo` -hay
        # dos K380- y el turno se quedo ahi, que ante un ambiguo es correcto,
        # pero el cliente nunca supo si andaba con la PS5. El campo
        # `compatibilidad` no se pidio en NINGUNA de las tres corridas.
        #
        # LA REGLA 10.0 NO SE TOCA, y esto es exactamente lo que dice: la
        # identidad la decide UNA FUNCION DETERMINISTA con tres veredictos, y
        # la herramienta consume un id CERTIFICADO. Lo que cambia es QUIEN
        # certifica: antes el modelo tenia que traer el id de una vuelta
        # anterior, ahora lo certifica el codigo aca mismo. El modelo sigue sin
        # decidir identidad; sigue sin poder inventar un producto.
        #
        # Y ES EL MISMO CAMINO DE IDENTIDAD, no uno nuevo: se llama a `_una`
        # con `busco: uno`, que es la consulta que el modelo escribiria. Un
        # segundo mecanismo de "cual producto es este" seria la cosa suelta que
        # la regla 2 prohibe, y ademas se desincronizaria del primero.
        cert = _una({"texto": pid, "busco": "uno", "cuantos": TOPE_AMBIGUO},
                    catalogo, tienda_id)
        filas = cert.get("filas") or []
        if cert.get("veredicto") == "ambiguo" or len(filas) > 1:
            # AMBIGUO DE IDENTIDAD. No se elige nunca: eso es la regla 10.0.
            #
            # PERO LA PREGUNTA PUEDE NO NECESITAR LA IDENTIDAD, y ahi esta la
            # otra mitad de esa misma regla: identidad y compatibilidad son
            # DOS EJES. Medido el 15-sep con el caso del banco: "el teclado
            # K380 anda con mi PS5" da dos candidatos -el negro y el blanco- y
            # los dos dan el MISMO veredicto contra la PS5, porque el color no
            # cambia con que anda. Preguntarle al cliente cual de los dos para
            # despues contestarle lo mismo es fricción sin dato adentro.
            #
            # Asi que se evaluan TODOS los candidatos y solo se repregunta si
            # el veredicto cambia entre ellos, que es cuando la identidad SI
            # hace falta para contestar. La identidad sigue sin resolverse: no
            # se elige un producto, se dice que para todos la respuesta es la
            # misma.
            candidatos = [porid.get(str(f.get("id"))) for f in
                          filas[:TOPE_AMBIGUO]]
            candidatos = [c for c in candidatos if c]
            juicios = [_evaluar(c, con, porid, tienda_id) for c in candidatos]
            distintos = {j["veredicto"] for j in juicios}
            # SI EL VEREDICTO COMUN ES `ambiguo` LA REPREGUNTA ES OTRA: esa
            # ambiguedad es del OTRO lado del par -"de apple" son macOS e iOS-
            # y su motivo ya dice que hay que preguntar cual equipo tiene. Se
            # devuelve tal cual: agregarle "no hace falta preguntar cual
            # producto" seria contestar una pregunta con la otra.
            if distintos == {"ambiguo"}:
                return {**base, **juicios[0], "pedido_como": pid}
            if len(distintos) == 1 and juicios:
                nombres = [str(c.get("nombre")) for c in candidatos]
                return {**base, **juicios[0],
                        "nombre": " / ".join(nombres),
                        "pedido_como": pid,
                        "vale_para_todos": nombres,
                        "motivo": f"para los {len(nombres)} que pegan con "
                                  f"'{pid}' la respuesta es la misma, asi que "
                                  f"no hace falta que preguntes cual: "
                                  + juicios[0]["motivo"]}
            lista = [{"id": c.get("id"), "nombre": c.get("nombre")}
                     for c in candidatos]
            return {**base, "veredicto": "ambiguo", "candidatos": lista,
                    "motivo": f"'{pid}' puede ser mas de uno y la respuesta "
                              f"cambia segun cual: no elijas, pregunta cual y "
                              f"volve a pedirme el par con ese id"}
        if not filas or cert.get("veredicto") == "no_existe":
            # NO EXISTE NO ES UN ERROR: es la respuesta 3 de la FICHA 52.
            return {**base, "veredicto": "sin_dato",
                    "motivo": f"no vendemos '{pid}', asi que no puedo decirte "
                              f"con que anda: " + (cert.get("motivo") or
                                                   "no esta en el catalogo")}
        prod = porid.get(str(filas[0].get("id")))
        if not prod:
            return {**base, "veredicto": "sin_dato",
                    "motivo": f"no tengo ningun producto con el id '{pid}': "
                              f"buscalo primero y usa el id que te devuelvo"}
        # EL ID CERTIFICADO VUELVE ESCRITO, y no es cosmetico: el modelo pidio
        # por un nombre y tiene que saber de que ficha salio el veredicto.
        base["producto"] = str(prod.get("id"))
        base["pedido_como"] = pid
    base["nombre"] = prod.get("nombre")
    return {**base, **_evaluar(prod, con, porid, tienda_id)}


def _evaluar(prod: dict, con: str, porid: dict, tienda_id: str) -> dict:
    """EL EJE DE COMPATIBILIDAD, CON LA IDENTIDAD YA RESUELTA. Devuelve
    {veredicto, motivo} y, segun el caso, contra que se evaluo.

    Esta partido de `_un_compat` porque se llama DOS VECES: una con el
    producto certificado, y una por candidato cuando el nombre del cliente
    pega con varios. Una segunda copia de estas reglas seria la cosa suelta
    que la regla 2 prohibe.
    """
    from app.core.compatibilidad import (etiqueta_plataforma, evaluar,
                                         evaluar_par, plataformas_del_mensaje)
    # EL OTRO PRODUCTO PRIMERO. Un id del catalogo es identidad certificada; un
    # alias de plataforma es una lectura del texto. Ante los dos, manda el dato.
    otro = porid.get(con)
    if otro:
        veredicto, motivo = evaluar_par(prod, otro, tienda_id)
        return {"con_nombre": otro.get("nombre"), "veredicto": veredicto,
                "motivo": motivo or "la tabla de la casa no dice si estos dos "
                                    "van juntos"}

    equipos = plataformas_del_mensaje(con, tienda_id)
    if not equipos:
        return {"veredicto": "sin_dato",
                "motivo": f"no reconozco '{con}' como un equipo ni como un id "
                          f"del catalogo; los equipos que conozco son: "
                          + _equipos(tienda_id)}
    if len(equipos) > 1:
        etqs = [etiqueta_plataforma(e, tienda_id) for e in equipos]
        return {"veredicto": "ambiguo", "candidatos": etqs,
                "motivo": f"'{con}' puede ser {' o '.join(etqs)}: no elijas, "
                          f"pregunta cual tiene"}
    veredicto, motivo = evaluar(prod, equipos[0], tienda_id)
    return {"con_equipo": etiqueta_plataforma(equipos[0], tienda_id),
            "veredicto": veredicto,
            "motivo": motivo or (
                f"la tabla de la casa no dice si {prod.get('nombre')} anda con "
                f"{etiqueta_plataforma(equipos[0], tienda_id)}")}


def buscar(consultas: list, tienda_id: str, trace_id: str = "",
           temas: list | None = None, compat: list | None = None,
           envios: list | None = None, localidad_previa: str = "",
           criterio: list | None = None, cuenta: dict | None = None) -> dict:
    """LA PUERTA. Catalogo, politicas, compatibilidad, envio y el criterio de la
    casa, en una llamada.

    `localidad_previa` es lo unico que entra de la charla, y no es una
    excepcion: es el dato con el que la tabla desambigua una localidad
    -"Los Condores" con "cordoba" al lado-. El destino lo NOMBRA el modelo.

    No lanza: un error de busqueda deja al bot sin fichas, nunca mudo.
    """
    from app.core.fuente import cotizar_destinos, criterio_de, politicas_de

    # EL ENVIO PRIMERO, PORQUE APAGA UNA POLITICA. Con la tarifa exacta de un
    # destino cotizada, la politica del RANGO no se sirve: son dos caminos para
    # el mismo numero y gana el flojo. El apagado vivia en el turno, que era
    # quien empujaba el envio; ahora las dos cosas entran por aca y la decision
    # vive donde se ven las dos.
    fuera_envios: dict = {}
    if envios:
        try:
            fuera_envios = cotizar_destinos(envios, tienda_id,
                                            localidad_previa) or {}
        except Exception as e:  # noqa: BLE001 — sin tarifa no se inventa una
            log.warning("motor_envio_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
    cotizado = any(f.get("monto_ars") for f in fuera_envios.get("filas") or [])

    fuera_temas, sin_resolver = [], []
    criterios, sin_criterio = [], []
    if temas:
        try:
            r = politicas_de(list(temas)[:TOPE_TEMAS], tienda_id)
            fuera_temas = list(r["politicas"])
            sin_resolver = r["sin_resolver"]
            # EL TEMA QUE LA FAQ NO CONTESTA VUELVE POR SU BOCA, no rotulado
            # como politica: el reparto por area lo hace `fuente`, que es la
            # que sabe de que archivo salio cada texto.
            criterios = list(r.get("criterio") or [])
        except Exception as e:  # noqa: BLE001 — sin politica no se inventa una
            log.warning("motor_temas_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")

    # EL RAMAL A CRITERIO. La boca no necesita el catalogo -su fuente es
    # `base_conocimiento.json`- asi que se resuelve antes de leerlo, igual que
    # las politicas: preguntar para que sirve un mouse no tiene por que costar
    # una lectura de 880 fichas.
    if criterio:
        try:
            rc = criterio_de(list(criterio)[:TOPE_CRITERIO], tienda_id)
            # SIN REPETIR: el mismo tema puede llegar por los dos campos, y
            # mandarle dos veces la misma prosa es el gasto que no se hace.
            ya = {c["tema"] for c in criterios}
            criterios += [c for c in rc["criterio"] if c["tema"] not in ya]
            ya_pol = {p["tema"] for p in fuera_temas}
            fuera_temas += [p for p in rc["politicas"]
                            if p["tema"] not in ya_pol]
            sin_criterio = rc["sin_resolver"]
        except Exception as e:  # noqa: BLE001 — sin criterio no se opina
            log.warning("motor_criterio_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")

    # EL APAGADO DEL ENVIO SE APLICA A LAS DOS ENTRADAS, y esto es lo que hay
    # que cuidar al sumar un campo que tambien puede devolver politicas: con la
    # tarifa exacta cotizada, la politica del RANGO no se sirve, y filtrando
    # solo lo que entro por `temas` el mismo numero flojo volvia a entrar por
    # `criterio`, que es la regla 2 rota por la puerta de atras.
    if cotizado:
        fuera_temas = [p for p in fuera_temas
                       if p["tema"] not in TEMAS_DEL_ENVIO]

    if not consultas and not compat and not (cuenta or {}).get("items"):
        # SOLO POLITICAS, SOLO ENVIO O SOLO CRITERIO ES UNA LLAMADA VALIDA.
        # "¿Cual es la politica de garantia?" y "¿para que me sirve?" no
        # necesitan tocar el catalogo, y obligar a inventar una consulta vacia
        # para preguntarlo seria pedirle al modelo que aprenda nuestra plomeria.
        return _salida([], fuera_temas, sin_resolver, [], fuera_envios,
                       criterios, sin_criterio)

    # LA COMPATIBILIDAD TAMBIEN NECESITA EL CATALOGO, y por eso la lectura no
    # cuelga mas de `consultas`: el par se evalua sobre las fichas reales, que
    # son las que traen la tabla estampada.
    from app.storage.firestore_client import get_all_products
    try:
        catalogo = get_all_products(tienda_id=tienda_id) or []
    except Exception as e:  # noqa: BLE001 — sin catalogo se contesta sin fichas
        log.warning("motor_catalogo_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {e}")
        catalogo = []
    if not catalogo:
        r = _salida([], fuera_temas, sin_resolver, [], fuera_envios,
                    criterios, sin_criterio)
        r["motivo"] = "no se pudo leer el catalogo"
        return r

    # EL RAMAL A COMPATIBILIDAD. Un par roto no tumba el resto, igual que una
    # consulta rota: vuelve `sin_dato`, que es la salida honesta de esta boca.
    compatibilidades = []
    for pedido in (compat or [])[:TOPE_COMPAT]:
        try:
            compatibilidades.append(_un_compat(pedido, catalogo, tienda_id))
        except Exception as e:  # noqa: BLE001 — sin dato no se afirma nada
            log.warning("motor_compat_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
            compatibilidades.append(
                {"producto": str((pedido or {}).get("producto") or ""),
                 "con": str((pedido or {}).get("con") or ""),
                 "veredicto": "sin_dato",
                 "motivo": "eso no se pudo verificar"})

    # LA CONSULTA REPETIDA SE EJECUTA UNA SOLA VEZ (13-sep-2026).
    #
    # MEDIDO: 6 repetidas sobre 31 en la tanda del tablero, y la causa NO era
    # la que decia el comentario de `_anotar` -"entre vuelta y vuelta el modelo
    # no ve lo que ya pidio"-. Ese texto se escribio antes de que `hallazgos`
    # empezara a mandarle "Buscaste: ..." de vuelta, asi que hoy SI lo ve. Las
    # repetidas son otra cosa y se ven en el crudo: el modelo manda dos
    # consultas IDENTICAS en la MISMA llamada -"monitor, varios" dos veces-, y
    # ahi no hay vuelta de por medio que valga.
    #
    # POR ESO EL ARREGLO ES DETERMINISTA Y VIVE ACA. Pedirselo al prompt seria
    # gastar tokens en cada turno para que el modelo se acuerde de algo que el
    # codigo puede garantizar. Ejecutar dos veces lo mismo cuesta la busqueda
    # al pedo Y las filas duplicadas adentro del retorno, que es lo caro.
    #
    # NO SE DESCARTA EN SILENCIO: la consulta repetida vuelve en su lugar, con
    # las mismas filas y un renglon que lo dice. El modelo mando N consultas y
    # tiene que recibir N resultados; un hueco en la lista lo obligaria a
    # adivinar cual falto. Y el numero sigue contandose en `informe`, que es
    # donde se mira si esto empeora.
    # EL NUMERO DE LA CONSULTA VIVE EN `vistas`, NO ADENTRO DEL RESULTADO. Un
    # `_n` colgado del dict se le va al modelo dentro del retorno, y un campo
    # que no significa nada para el que lee es ruido que hay que aprender a
    # ignorar, justo en la caja donde todo lo demas es dato certificado.
    vistas: dict = {}
    fuera = []
    for c in (consultas or [])[:TOPE_CONSULTAS]:
        seña = json.dumps(c, ensure_ascii=False, sort_keys=True, default=str)
        if seña in vistas:
            # SIN LAS FILAS, y ahi esta el ahorro de verdad. Copiarlas seria
            # mandarle al modelo las mismas cinco fichas dos veces adentro del
            # mismo retorno, que es justo el gasto que esto viene a sacar.
            fuera.append({
                "veredicto": vistas[seña][0]["veredicto"],
                "filas": [], "cuantos_habia": vistas[seña][0]["cuantos_habia"],
                "no_aplicado": [], "sin_dato": 0, "empatados": 0,
                "repetida": (f"identica a tu consulta numero "
                             f"{vistas[seña][1]} de esta misma llamada. Se "
                             f"busco una sola vez y el resultado esta ahi"),
                "motivo": ""})
            continue
        try:
            r_una = _una(c, catalogo, tienda_id)
            vistas[seña] = (r_una, len(fuera) + 1)
            fuera.append(r_una)
        except Exception as e:  # noqa: BLE001 — una consulta rota no tumba el resto
            log.warning("motor_consulta_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
            fuera.append({"veredicto": "no_existe", "filas": [],
                          "cuantos_habia": 0, "no_aplicado": [], "sin_dato": 0,
                          "empatados": 0,
                          "motivo": "esa consulta no se pudo ejecutar"})
    # LA CUENTA VA ULTIMA, Y ESE ES SU LUGAR: es lo unico que cruza bocas, asi
    # que necesita que las otras ya hayan contestado. Con los envios de esta
    # misma llamada ya cotizados, la tarifa entra a la cuenta sin volver a
    # pedirsela a nadie.
    la_cuenta = {}
    if cuenta:
        try:
            la_cuenta = _la_cuenta(cuenta, fuera_envios, tienda_id, trace_id)
        except Exception as e:  # noqa: BLE001 — sin total no se inventa uno
            log.warning("motor_cuenta_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:150]}")

    repetidas = sum(1 for f in fuera if f.get("repetida"))
    log.info("motor_buscar", trace_id=trace_id, consultas=len(fuera),
             repetidas=repetidas,
             veredictos=[f["veredicto"] for f in fuera],
             filas=[len(f["filas"]) for f in fuera],
             temas=[p["tema"] for p in fuera_temas],
             compat=[c["veredicto"] for c in compatibilidades],
             envios=[f["destino"] for f in fuera_envios.get("filas") or []],
             criterio=[c["tema"] for c in criterios],
             cuenta=la_cuenta.get("total_ars") or la_cuenta.get("sin_total"))
    return _salida(fuera, fuera_temas, sin_resolver, compatibilidades,
                   fuera_envios, criterios, sin_criterio, la_cuenta)


def fichas_de(resultado: dict) -> list[dict]:
    """Las fichas de todas las consultas, sin repetir. Es lo que la guarda de
    procedencia necesita: un numero que no este en estas fichas no sale al
    cliente, y da igual en cual de las consultas aparecio."""
    fuera, vistos = [], set()
    for r in (resultado or {}).get("resultados") or []:
        for f in r.get("filas") or []:
            i = str(f.get("id"))
            if i not in vistos:
                vistos.add(i)
                fuera.append(f)
    return fuera
