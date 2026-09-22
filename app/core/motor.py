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

from app.core import bocas as BC
from app.logger import get_logger

log = get_logger(__name__)

NOMBRE = "buscar"

# Tope duro de filas por consulta. El modelo puede pedir menos, nunca mas: una
# busqueda que devuelve cuarenta fichas inunda el prompt y ademas no sirve, que
# es la leccion del catalogo entero que no entra.
TOPE_FILAS = 8

# La salida del orden: la respuesta cuando el cliente no pidio ninguno.
SIN_ORDEN = "ninguno"


def orden_plano(consulta: dict) -> dict:
    """Traduce el `orden` plano que escribe el modelo —`precio_ars_min`— al
    `ordenar_por` que leen el motor y el cotejo. `ninguno` no ordena. Si el
    modelo igual mando un `ordenar_por`, se respeta: gana lo explicito."""
    c = consulta
    o = str(c.get("orden") or "")
    if o and o != SIN_ORDEN and not c.get("ordenar_por"):
        campo, _, direccion = o.rpartition("_")
        if campo and direccion in ("min", "max"):
            c["ordenar_por"] = {"campo": campo, "direccion": direccion}
    return c
FILAS_POR_DEFECTO = 5

# Cuantas consultas entran en una llamada. Un pedido multiple —"dos auriculares,
# dos mouse y dos memorias"— es UNA llamada con tres consultas, no tres turnos.
TOPE_CONSULTAS = 6

# Hasta cuantos empatados siguen siendo UNA COSA con variantes -el mismo teclado
# en negro, blanco, gris y azul- y no un termino generico. Pasados estos, que el
# cliente haya nombrado una sola cosa y empaten veinte quiere decir que la
# nombro ancho, y ahi mostrar la lista es mejor que repreguntar.
TOPE_AMBIGUO = 4

# Cuantas cosas escritas por la casa vuelven en una llamada. El mismo tope que
# usa `fuente`, y por el mismo motivo: ante un tema ambiguo se sirven TODOS los
# candidatos en vez de elegir.
#
# SUBE DE 3 A 6 EL 20-sep Y NO ES AFLOJAR LA VARA: es la misma capacidad de
# antes en un solo campo. Hasta hoy el modelo podia pedir 3 por `temas` y 3
# por `criterio`, y los dos campos se fundieron en uno. Con 3 el mensaje que
# pregunta garantia, cuotas y ademas para que sirve un mouse perdia una de las
# tres, que es justo el defecto que esta tanda vino a cerrar.
TOPE_TEMAS = 6

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
    from app.core.fuente import SIN_TEMA
    from app.core.fuente import temas_del_tablero as _TEMAS
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
                               "corrijas.\n"
                               "`prefiere` y `evita` NO FILTRAN, ORDENAN: son "
                               "el GRADO, y MIRA CUAL: 'las menos partes "
                               "chinas posibles' es `evita` china; "
                               "'preferentemente Logitech' es `prefiere` "
                               "logitech. Vuelven TODOS y te digo cuantos "
                               "cumplen. `no_contiene` es para cuando EXCLUYE."},
            # SOLO LOS NUMERICOS, y el enum de los 41 que habia aca era caro
            # y ademas estaba mal: sobre una etiqueta -`color`, `bluetooth`- el
            # orden es alfabetico y no contesta ninguna pregunta de un cliente.
            # `orden_tiene_sentido` ya lo rechazaba DESPUES, o sea que el
            # modelo gastaba una consulta para que el motor le dijera que no.
            # EL ORDEN ES PLANO Y OBLIGATORIO, CON SALIDA (22-sep-2026). Era
            # un objeto opcional `ordenar_por` y medido en M17 —"algo q no
            # salga mucho"— el modelo lo omitia 1 de 2: sin orden, el cliente
            # que pidio lo barato recibia cualquier cosa. Es el patron que ya
            # funciono tres veces en este repo —`SIN_TEMA`,
            # `medio_no_disponible`, `pedir_total`—: una casilla que SIEMPRE
            # tiene respuesta puede ser obligatoria, y `ninguno` es la
            # respuesta cuando no pidio orden. Una sola forma: el objeto se
            # borra y el codigo traduce esto para el motor.
            #
            # SOLO LOS NUMERICOS, como siempre: sobre una etiqueta el orden es
            # alfabetico y no contesta ninguna pregunta de un cliente.
            "orden": {
                "type": "string",
                "enum": [SIN_ORDEN] + [f"{c}_{d}" for c in ordenables
                                       for d in ("min", "max")],
                "description": ("SIEMPRE. 'el mas barato', 'que no salga "
                                "mucho', 'acorde a la crisis' es precio_ars_"
                                "min; 'el mas liviano', peso_gramos_min. Si "
                                f"no pidio orden, '{SIN_ORDEN}'.")},
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
                         # QUE DEVUELVE NO VA ACA: el subtotal lo explica el
                     # encabezado del retorno, que nace con el retorno.
                     "description": "Cuantas UNIDADES de cada producto pide "
                                    "el cliente. No es la cantidad de "
                                    "filas."},
            # EL CAMPO `specs` SE BORRO EL 14-sep, y es la vieja que se apaga
            # por la que se prende. Se habia agregado el 13-sep para que el
            # mapa de specs no engordara la ficha, pero lo que engordaba era la
            # PROSA: medido, 60 al 63 por ciento del retorno de toda lista, y
            # las specs completas son mas baratas que ella en los cuatro
            # rubros. Sacada la prosa, las specs entran enteras y no hay nada
            # que pedir. La medicion esta en `fuente._ficha_corta`.
        },
        "required": ["orden"],
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
            #
            # Y YA NO SE ESCRIBE ACA (16-sep-2026, FICHA 55 §4.2). El indice
            # sale de `bocas.para_el_tablero`, que es la MISMA lista de la que
            # sale el encabezado del retorno y la regla de la plata del
            # prompt. Escribirlo dos veces es lo que hizo que el encabezado
            # tardara tres dias en enterarse de que habia cinco bocas.
            "description": BC.para_el_tablero(),
            "parameters": {
                "type": "object",
                "properties": {
                    # EL RENGLON, Y VA PRIMERO A PROPOSITO (21-sep-2026).
                    #
                    # EL MODELO ESCRIBE EN ORDEN, campo por campo. Hasta hoy
                    # lo primero que escribia eran las `consultas`, que ya es
                    # traducir y repartir a la vez; y lo ultimo de todo, seis
                    # campos despues, la `cuenta`. El peor lugar posible para
                    # lo que mas se olvidaba.
                    #
                    # ACA NO SE INTERPRETA, SE COPIA. Es la unica casilla del
                    # esquema que no le pide al modelo ninguna decision: que
                    # dijo el cliente, renglon por renglon, con sus palabras.
                    # Despues llena el resto con su propia lista delante, que
                    # es un andamio y no una instruccion: no le pedimos que se
                    # acuerde, le damos de donde copiar.
                    #
                    # ES LA PLANILLA PLANA DE LA FICHA 55 §4.1, NACIDA MUDA.
                    # Viaja, se loguea y NO cambia una sola respuesta, que es
                    # la regla 2 de las seis contra la cascada. El dia que el
                    # codigo rutee estos renglones, el campo ya va a estar
                    # lleno y medido sobre charlas reales.
                    #
                    # Y DA UN NUMERO QUE HOY NO EXISTE: cuantos renglones
                    # enumero contra cuantas casillas lleno. Enumerar siete y
                    # llenar cinco es un problema de REPARTO; enumerar cuatro
                    # es que no entendio. Hoy los dos fracasos se ven iguales.
                    #
                    # QUE EL ORDEN DEL ESQUEMA MANDE EL ORDEN DE ESCRITURA ES
                    # UNA APUESTA, no una ley: se mide en la proxima tanda.
                    "renglones": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "PRIMERO Y SIEMPRE. Todo lo que el cliente pidio "
                            "en este mensaje, UN RENGLON POR CADA COSA, con "
                            "LAS PALABRAS de el y sin interpretar: 'dos "
                            "notebooks', 'acorde a la crisis', 'los otros a "
                            "villa maria', 'la garantia'. Despues llenas los "
                            "campos de abajo con esta lista delante, y no "
                            "dejas ningun renglon afuera.")},
                    # EL PEDIDO DE TOTAL, PLANO Y OBLIGATORIO, y sale de
                    # adentro de `cuenta` por el mismo motivo por el que el
                    # 20-sep el reparto salio de ahi: adentro le pedia al
                    # modelo DOS decisiones para una cosa que el cliente dijo
                    # una vez.
                    #
                    # PEOR QUE EL REPARTO, PORQUE ERA IMPOSIBLE. `cuenta.items`
                    # pide un ID por producto y en la vuelta 1 el cliente
                    # nombro RUBROS -"dos notebooks"-: el modelo todavia no
                    # miro el catalogo y no tiene un solo id que escribir.
                    # Medido tres veces, se la salteaba y hacia el reparto O
                    # la cuenta, nunca las dos. No elegia: zafaba de una
                    # casilla que no podia completar.
                    #
                    # UN SI O NO SIEMPRE TIENE RESPUESTA, y por eso este SI
                    # puede ser obligatorio. Un objeto anidado obligatorio
                    # seria peor que opcional: lo forzaria a inventar algo
                    # para llenarlo.
                    #
                    # NACE MUDO: viaja, se loguea y no arma ninguna cuenta.
                    # La cuenta la sigue haciendo `cuenta.items` cuando hay
                    # ids, igual que ayer. Darle poder de frenar o de pedir es
                    # la vuelta siguiente, cuando el numero diga que se llena.
                    "pedir_total": {
                        "type": "boolean",
                        "description": (
                            "Si el cliente pidio un presupuesto, un total o "
                            "'cuanto me sale todo'. Es si o no y va SIEMPRE, "
                            "aunque todavia no tengas los ids.")},
                    "consultas": {"type": "array", "items": consulta,
                                  "description": f"Hasta {TOPE_CONSULTAS}."},
                    # EL MAPA 3, Y ES UN CAMPO MAS DE LA MISMA PUERTA. No hay
                    # una herramienta nueva a proposito: el mecanismo de buscar
                    # en la fuente es el mismo, cambia que se busca. Una
                    # herramienta aparte serian dos puertas para lo mismo.
                    #
                    # UNA SOLA PUERTA PARA TODO LO QUE LA CASA TIENE
                    # ESCRITO (20-sep-2026), y antes eran dos: `temas` y
                    # `criterio`. Eran la MISMA puerta con dos nombres. Las dos
                    # entraban por `fuente.certificar_temas` y las dos repartian
                    # por area con `_de_la_casa`, o sea que LA CAJA LA ELIGE EL
                    # CODIGO y da igual por cual de los dos campos entre el
                    # tema. Al modelo se le estaba haciendo elegir, en cada
                    # turno, una cosa que el codigo ya resuelve solo.
                    #
                    # Y ESTA ESCRITO DESDE EL 4-ago, en `temas_consultables`:
                    # "un tema es un tema; de que archivo sale es asunto del
                    # codigo". El tablero era el unico lugar que todavia no lo
                    # cumplia.
                    #
                    # AHORA LLEVA ENUM, y eso da vuelta la decision de la FICHA
                    # 06 del 23-ago con la cuenta medida al lado. Entonces eran
                    # 129 nombres y 2.299 bytes y salio por peso; hoy, sin los
                    # dos pilares de conducta, son 104 y 1.821, y la leyenda
                    # acaba de devolver 1.087 caracteres bajando su techo.
                    #
                    # LO QUE COMPRA: un candado duro donde habia atadura
                    # blanda. Un tema que la casa no tiene escrito deja de
                    # poder nombrarse, que es la misma regla con la que el
                    # esquema cierra los nombres de campo del catalogo.
                    "temas": {
                        "type": "array",
                        "items": {"type": "string",
                                  "enum": _TEMAS(tienda_id) + [SIN_TEMA]},
                        # LA DESCRIPCION NO REPITE EL INDICE, y eso es el
                        # bloque 0 de CLAUDE.md: la segunda descripcion de lo
                        # mismo es el telefono descompuesto. QUE contesta esta
                        # boca lo dice el indice, arriba; aca va solo como se
                        # elige y que pasa si no esta.
                        # SOLO LO QUE PREGUNTO, y es el defecto que trajo el
                        # enum. Medido 4 de 4 el 20-sep: a un pedido de
                        # precios le agrego `confianza_seguridad`,
                        # `pedir_descuento` y `envio_urgente`, que el cliente
                        # no nombro. Antes del enum no podia pasar —no tenia
                        # de donde elegir—; es el costo del candado.
                        "description": (
                            "SOLO lo que el cliente PREGUNTO: si no pregunto "
                            "nada de la casa, va vacio. Elegi el nombre de la "
                            "lista que cubre lo que pregunto. Si ninguno lo "
                            f"cubre poné '{SIN_TEMA}'. Hasta {TOPE_TEMAS}.")},
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
                    # EL VINCULO (20-sep-2026), Y ES LA CASILLA QUE NO SE
                    # PODIA LLENAR. `envios` era una lista de TEXTOS pelados,
                    # asi que "un auricular y un mouse va a Cordoba" no tenia
                    # donde escribirse: el modelo declaraba los tres destinos y
                    # la atadura se perdia, medido 0 de 4 en cuatro tandas.
                    #
                    # NO SE CERTIFICA NADA, y por eso es barato: `va` son las
                    # palabras del cliente y viajan como vinieron. El destino
                    # lo sigue clasificando la tabla —eso no cambia— y `va`
                    # vuelve pegado a su tarifa para que el modelo pueda decir
                    # QUE va a cada lado en vez de listar tres montos sueltos.
                    "envios": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "destino": {
                                    "type": "string",
                                    "description": "Con LAS PALABRAS del "
                                                   "cliente: 'Posadas', "
                                                   "'CP 5121'."},
                                "va": {
                                    "type": "string",
                                    "description": "QUE va a ese destino, con "
                                                   "las palabras del cliente: "
                                                   "'un auricular y un "
                                                   "mouse'."}},
                            "required": ["destino"]},
                        "description": (
                            "Un lugar que nombra va aca aunque solo pregunte "
                            "si llegan. Si lo dijo turnos atras esta en tu "
                            "memoria. Te "
                            "devuelvo la tarifa y el hueco que copias donde "
                            "vaya el costo: el monto NO lo escribis vos. "
                            f"Hasta {TOPE_ENVIOS}.")},
                    # EL REPARTO DEL PAGO SUBE AL PRIMER NIVEL (20-sep-2026)
                    # y sale de adentro de `cuenta`, donde nacio el 14-sep.
                    #
                    # MEDIDO CUATRO VECES EN WHATSAPP EL 19-sep, mismo mensaje:
                    # "divide el presupuesto en setenta treinta" se declaro
                    # CERO de 4. Adentro de `cuenta` el modelo tiene que tomar
                    # DOS decisiones para escribir una cosa que el cliente dijo
                    # una vez: primero resolver que quiere una cuenta, y recien
                    # ahi puede anotar el reparto. Las cuatro veces se quedo en
                    # la primera y el reparto no existio.
                    #
                    # Y HAY MEDICION DE QUE LO PLANO SE LLENA: en esas mismas
                    # cuatro corridas `envios` —primer nivel, lista de textos—
                    # salio 4 de 4, y `condiciones` —anidado dos niveles y
                    # opcional— salio 0 de 4. No es criterio del modelo, es
                    # forma del esquema.
                    #
                    # UNA COSA QUE EL CLIENTE DICE ES UN CAMPO. Esa es la regla
                    # entera, y es la misma por la que `temas` y `criterio` se
                    # fundieron en uno: no hacerle tomar al modelo decisiones
                    # que el cliente no tomo.
                    "reparto_pago": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                # EL MEDIO SE CIERRA (21-sep-2026), Y ERA EL
                                # ULTIMO CAMPO QUE AFIRMABA ALGO DE LA TIENDA
                                # SIN VERIFICARSE.
                                #
                                # MEDIDO: con `medio: "criptomonedas"` la
                                # cuenta salio con total y sin una palabra de
                                # aviso. Y sale PEOR que sin aviso: la regla
                                # de `pago_split` es que todo lo que NO es
                                # Mercado Pago cuenta como transferencia y
                                # lleva el descuento, asi que el bot cotizaba
                                # un 10% menos por un medio que la tienda no
                                # acepta. Plata mal, que es la regla 3.1.
                                #
                                # TRES VALORES Y NO MAS, y no salen de la
                                # prosa de la FAQ: salen de lo que el CODIGO
                                # distingue. `pago_split` solo separa Mercado
                                # Pago del resto; que la tienda liste Visa,
                                # Mastercard y Amex no cambia una cuenta.
                                # Perseguir la prosa para sacar marcas seria
                                # la enfermedad que este repo ya pago tres
                                # veces.
                                #
                                # Y EL CUARTO ES LA SALIDA, no un relleno:
                                # `medio_no_disponible` es el SIN_CAMPO del
                                # pago. Un cliente que dice "mitad en efectivo"
                                # tiene donde declararse, y el codigo puede
                                # decir que no se toma en vez de cobrarle un
                                # descuento que no corresponde.
                                "medio": {
                                    "type": "string",
                                    "enum": ["transferencia", "mercado_pago",
                                             "tarjeta",
                                             "medio_no_disponible"],
                                    "description": (
                                        "Con que paga. Si el cliente nombra "
                                        "uno que no esta en la lista poné "
                                        "'medio_no_disponible' y te digo que "
                                        "contestar: NO lo acomodes al mas "
                                        "parecido.")},
                                "porcentaje": {"type": "number"}},
                            "required": ["medio", "porcentaje"]},
                        "description": (
                            "Solo si reparte el pago: '70 transferencia 30 "
                            "Mercado Pago'. Suman 100. Anotalo en la MISMA "
                            "llamada, aunque no tengas los ids: me lo guardo y "
                            "lo aplico cuando llegue la cuenta.")},
                    # LO QUE EL CLIENTE AFIRMA (22-sep-2026). El motivo entero
                    # esta en `_una_afirmacion`: una sola casilla para la
                    # premisa falsa y para el dato que el cliente aporta,
                    # porque al modelo no se le pide que decida cual de las
                    # dos es. Anota lo que dijo; el codigo verifica.
                    "afirma": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sobre": {
                                    "type": "string",
                                    "description": "De que habla: el id, el "
                                                   "nombre que uso, o lo SUYO "
                                                   "-'mi notebook'-."},
                                "dice": {
                                    "type": "string",
                                    "description": "Lo que afirma, con SUS "
                                                   "palabras: 'inalambrico', "
                                                   "'8 giga'."}},
                            "required": ["sobre", "dice"]},
                        "description": (
                            "Lo que el cliente DA POR SENTADO en vez de "
                            "preguntarlo: 'el K120 inalambrico ese'. Te digo "
                            "si es cierto, si no —con el dato real— o si es "
                            f"cosa suya. No lo des por bueno vos. Hasta "
                            f"{TOPE_AFIRMA}.")},
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
                        # NO REPITE EL INDICE NI EL RETORNO: que contesta
                        # esta boca lo dice el indice, y que hacer con el
                        # veredicto lo dice el encabezado del retorno.
                        "description": (
                            "'¿anda con mi PS5?', '¿esta memoria entra en "
                            f"esta mother?'. Hasta {TOPE_COMPAT}.")},
                    # EL CAMPO `criterio` SE BORRO EL 20-sep, y es la vieja
                    # que se apaga por la que se prende. Nacio el 13-sep como
                    # la quinta boca cableada, y lo que se vio despues es que
                    # no era una puerta distinta: `criterio_de` y
                    # `politicas_de` son la misma funcion con otro nombre —la
                    # misma certificacion y el mismo reparto por area— asi que
                    # el campo solo le pedia al modelo que adivinara nuestro
                    # archivero. La BOCA sigue viva y sigue devolviendo su
                    # caja; lo que se apaga es la segunda forma de pedirla.
                    # `motor.buscar` conserva el parametro para no romper a
                    # quien lo llame, pero el tablero ya no lo ofrece.
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
                                        "id": {
                                            "type": "string",
                                            "description": (
                                                "El id que te devolvi, o el "
                                                "nombre que uso el cliente: no "
                                                "hace falta buscarlo antes, lo "
                                                "resuelvo yo. Si pega con mas "
                                                "de uno no lo cuento, te los "
                                                "devuelvo y preguntas cual.")},
                                        "cantidad": {"type": "integer"}},
                                    "required": ["id"]}},
                            },
                        # IDEM: el indice ya dice que contesta y que la
                        # suma la hace el codigo.
                        "description": (
                            "Vuelve el total ya sumado —con envio y "
                            "descuento— y el detalle.")}},
                # LOS DOS UNICOS OBLIGATORIOS, y hasta hoy no habia ninguno.
                # Un campo opcional se puede olvidar gratis y sin dejar
                # rastro; uno obligatorio no se puede saltear, porque no hay
                # respuesta valida sin el. No es que el modelo se acuerde
                # mejor: es que la forma no lo permite. Empuja muy fuerte,
                # no es un candado fisico.
                #
                # SOLO ESTOS DOS PORQUE SON LOS UNICOS QUE SIEMPRE TIENEN
                # RESPUESTA. Obligar `envios` o `temas` seria pedirle que
                # llene con ruido lo que el cliente no dijo, que es el defecto
                # que el enum de temas ya trajo una vez.
                "required": ["renglones", "pedir_total"]},
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
               trace_id: str = "", catalogo: list | None = None) -> dict:
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

    EL ID SE CERTIFICA ADENTRO, igual que en `_un_compat` (15-sep-2026, FICHA
    54 punto 3.2). El modelo puede escribir el nombre que uso el cliente y el
    codigo lo resuelve con la MISMA consulta de identidad; antes hacia falta
    una vuelta previa para conseguir el id, y una vuelta cuesta del orden de
    7.700 tokens. La regla 10.0 no se toca: el id lo certifica una funcion
    determinista, no el modelo.

    Y ACA LA AMBIGUEDAD NO TIENE ATAJO, que es la diferencia con la
    compatibilidad. Alla dos candidatos pueden dar el mismo veredicto y
    contestar sin elegir; aca cada candidato tiene SU precio, asi que un nombre
    que pega con mas de uno no se cuenta: vuelve `sin_total` con los
    candidatos, que es la respuesta 4 de la FICHA 52. Elegir seria inventarle
    plata al cliente.

    No lanza: una cuenta rota deja al turno sin total, nunca con uno inventado.
    """
    porid = {str(p.get("id")): p for p in (catalogo or [])}
    items, pedidos_como = [], []
    for x in (pedido or {}).get("items") or []:
        pid = str((x or {}).get("id") or "").strip()
        if not pid:
            continue
        try:
            cant = max(1, int((x or {}).get("cantidad") or 1))
        except (TypeError, ValueError):
            cant = 1
        if catalogo and pid not in porid:
            cert = _certificar_id(pid, catalogo, tienda_id)
            if cert.get("sin_total"):
                return cert
            pedidos_como.append({"pedido_como": pid, "id": cert["id"],
                                 "nombre": cert.get("nombre")})
            pid = cert["id"]
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
    # UN MEDIO QUE LA TIENDA NO TOMA NO ENTRA A LA CUENTA, Y SE DICE.
    # Dejarlo entrar es peor que ignorarlo: `pago_split` lo trataria como
    # transferencia y le aplicaria el descuento, o sea que el bot cotizaria
    # mas barato por algo que no se puede pagar.
    from app.core.filtros_catalogo import _norm
    no_disp = [x for x in reparto
               if _norm(x.get("medio")) == "medio_no_disponible"]
    if no_disp:
        reparto = [x for x in reparto if x not in no_disp]

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
    # EL ID CERTIFICADO VUELVE ESCRITO, por lo mismo que en `_un_compat`: el
    # modelo pidio por un nombre y tiene que saber de que ficha salio la plata.
    if pedidos_como:
        fuera["certificados"] = pedidos_como
    if no_disp:
        # EL MOTIVO VIAJA ESCRITO Y EL MODELO LO COPIA, que es como este repo
        # resuelve las negaciones: el dato es del codigo, la prosa del modelo.
        fuera["medio_no_disponible"] = (
            "el cliente nombro un medio de pago que la tienda no toma. Se "
            "cobra por transferencia, Mercado Pago o tarjeta. Decilo y no "
            "lo cuentes en el total.")
    # QUE HAY ADENTRO DEL TOTAL, y no es adorno: es lo que el turno guarda como
    # carrito para que el turno SIGUIENTE no lo rearme de cero. Medido el
    # 15-sep en WhatsApp: tres turnos seguidos sobre el MISMO pedido dieron
    # tres totales distintos -207.500, 284.000 y 395.000- porque cada uno
    # eligio productos y cantidades por su cuenta. Sin esta lista, lo unico que
    # sobrevive al turno es una cifra suelta que nadie puede verificar.
    fuera["items"] = [
        {"id": i["product_id"], "cantidad": i["cantidad"],
         "nombre": (porid.get(i["product_id"]) or {}).get("nombre") or ""}
        for i in items]
    return fuera


def _certificar_id(nombre: str, catalogo: list, tienda_id: str) -> dict:
    """EL NOMBRE QUE USO EL CLIENTE, RESUELTO A UN ID. Devuelve {id, nombre} o
    {sin_total: motivo} cuando no se puede certificar sin elegir.

    LA VARA ES MAS DURA QUE LA DE `_un_compat`, Y LA DIFERENCIA ES LA PLATA.
    Alla alcanza el veredicto de `_una`, porque dos candidatos pueden dar la
    misma respuesta de compatibilidad. Aca cada candidato tiene SU precio, y
    `_una` con `busco: uno` no alcanza: medido el 15-sep, "auriculares" le da
    veredicto `existe` con el Zeus X Negro primero -46 fichas se llaman asi y
    el orden desempata por parecido-. Contar eso seria elegir por el cliente.
    Asi que se pide identidad ENTERA: una sola ficha que se llame todo eso.

    NO ES UN MECANISMO NUEVO: es `lo_nombra`, el mismo certificador de
    identidad, preguntado en su forma estricta. `_una` sigue siendo quien
    escribe el motivo cuando no se puede certificar.
    """
    from app.core.filtros_catalogo import los_que_lo_nombran_entero
    exactos = los_que_lo_nombran_entero(catalogo, nombre)
    if len(exactos) == 1:
        return {"id": str(exactos[0].get("id")),
                "nombre": exactos[0].get("nombre")}
    cert = _una({"texto": nombre, "busco": "uno", "cuantos": TOPE_AMBIGUO},
                catalogo, tienda_id)
    filas = cert.get("filas") or []
    if not exactos and (not filas or cert.get("veredicto") == "no_existe"):
        return {"sin_total": f"no vendemos '{nombre}', asi que no puedo "
                             f"ponerlo en la cuenta: "
                             + (cert.get("motivo") or "no esta en el catalogo")}
    candidatos = (exactos or
                  [{"id": f.get("id"), "nombre": f.get("nombre")}
                   for f in filas])[:TOPE_AMBIGUO]
    lista = [f"{c.get('nombre')} ({c.get('id')})" for c in candidatos]
    return {"sin_total": f"'{nombre}' puede ser mas de uno y cada uno sale "
                         f"distinto, asi que no lo cuento: no elijas, "
                         f"pregunta cual de estos y volve a pedirme la cuenta "
                         f"con ese id. " + " | ".join(lista)}


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
        # "DE ESOS, EL MAS BARATO" (22-sep-2026). Los ids son el universo y
        # el orden se aplica ADENTRO: hasta hoy el orden se ignoraba con ids,
        # asi que el extremo "de esos" solo se podia pedir buscando en el
        # catalogo entero, y medido en la tanda de charlas —CH10— el bot
        # contesto "de los que te mencione, el mas barato es el KB-110X"
        # con un teclado que nunca habia mencionado.
        _o = c.get("ordenar_por") or {}
        if (_o.get("campo") and len(filas) > 1
                and orden_tiene_sentido(filas, str(_o["campo"]), tienda_id)):
            filas = ordenar(filas, str(_o["campo"]),
                            str(_o.get("direccion") or "min"), tienda_id)
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
        "productos": universo, "aplicados": [], "descartados": [],
        "sin_dato": 0, "preferencias": []}
    no_aplicado.extend(r["descartados"])
    quedan = r["productos"]

    # LA PREFERENCIA SE DICE, Y ESE ES MEDIO ARREGLO (20-sep-2026). `prefiere`
    # y `evita` ordenan y devuelven a todos, asi que si el modelo no se entera
    # de que NO se filtro, escribe "estos no tienen partes chinas" sobre una
    # lista donde los ultimos si las tienen. Un orden callado es una mentira
    # con cara de dato. Va en `motivo`, que es el renglon que el modelo ya lee
    # de cada resultado, y no en `no_aplicado`, que significa otra cosa: una
    # condicion que la fuente NO PUDO cumplir.
    for pref in r.get("preferencias") or []:
        donde = "primero" if pref["operador"] == "prefiere" else "al final"
        if pref.get("por") == "cercania":
            # SOBRE UN NUMERO NO SE CUMPLE, SE ESTA CERCA. Decir "171 de 171
            # lo cumplen" de un precio seria mentirle al modelo con la forma
            # de un dato.
            cerca = "mas cerca" if pref["operador"] == "prefiere" else "mas lejos"
            notas.append(
                f"{pref['campo']} NO se filtro, se ORDENO por cercania a "
                f"{pref['valor']}: primero los que estan {cerca}. Estan "
                f"TODOS, y ninguno 'cumple' ese numero: es un orden")
            continue
        notas.append(
            f"{pref['campo']} '{pref['valor']}' NO se filtro, se ORDENO: "
            f"{pref['cumplen']} de {pref['evaluados']} lo cumplen y van "
            f"{donde}. Estan TODOS, tambien los que no lo cumplen: no digas "
            f"que la lista entera lo cumple")
    cumplieron = len(quedan)
    empatados = 0
    veredicto = "existe"

    # 3. EL RESCATE. Si ninguna cumple todo, se trae lo mas parecido y se dice
    #    cual condicion falla. Devolver vacio seria decirle al cliente que no
    #    existe lo que si existe con una condicion menos.
    # EL RESCATE MIRA SOLO LO QUE FILTRA. Una preferencia no se puede
    # "incumplir": no saco a nadie, asi que contarla como condicion fallada
    # diria que un producto no cumple algo que nunca se le exigio.
    from app.core.filtros_catalogo import ORDENAN
    duras = [x for x in conds if x.operador not in ORDENAN]
    rescate = False
    if duras and not quedan:
        quedan, empatados, incumple = rankear_por_cercania(
            universo, duras, tienda_id)
        veredicto = "no_existe"
        rescate = True
        notas.append(f"ninguno cumple todo; esto es lo mas parecido, "
                     f"incumple {incumple} de {len(duras)}")
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
    # EL CAMPO POR EL QUE SE PREGUNTO VIAJA EN CADA FILA (20-sep-2026).
    #
    # ES EL MISMO DEFECTO QUE `no_cumple` YA CERRABA, y lo que se vio el 20-sep
    # es que lo cerraba SOLO EN EL RESCATE. Medido contra el catalogo vivo: una
    # busqueda de auriculares con condicion sobre `pais_fabricacion` devuelve
    # filas con id, nombre, categoria, stock, precio, modelo, specs y
    # caracteristicas_extra, y NI UN DATO del pais. El modelo tiene que hablar
    # del origen y no tiene el origen delante.
    #
    # Y LOS OPERADORES DE GRADO LO DESTAPARON. Con `prefiere` y `evita` el
    # veredicto es siempre `existe`, asi que el rescate —que es quien estampaba
    # `no_cumple`— no corre nunca, y las filas volvieron a viajar mudas. Una
    # preferencia sin el valor al lado es peor que un filtro: el modelo recibe
    # una lista ordenada y no puede decir por que ni cuales cumplen.
    #
    # LO MISMO PARA EL ORDEN: si se ordeno por peso, el peso viaja. Ordenar por
    # un campo que el modelo no ve es pedirle que confie en la fila de arriba.
    #
    # NO PISA NADA: si la ficha del rubro ya trae el campo, se respeta el que
    # estaba. Y lo que no tiene dato cargado no se inventa: se omite, que es la
    # diferencia entre "no lo tiene" y "no lo sabemos".
    from app.core.filtros_catalogo import SIN_CAMPO as _SIN, _valor_crudo
    campos_pedidos = [c.campo for c in conds if c.campo != _SIN]
    if campo_orden:
        campos_pedidos.append(campo_orden)
    campos_pedidos = sorted(set(campos_pedidos))

    filas = []
    for p in quedan[:tope]:
        f = _ficha_corta(p, unidades, specs_pedidas, detalle)
        for campo in campos_pedidos:
            if campo in f:
                continue
            crudo = _valor_crudo(p, campo)
            if crudo not in (None, "", [], {}):
                f[campo] = crudo
        if rescate:
            motivo_fila = dato_que_falla(p, duras, tienda_id)
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
            sin_criterio, cuenta=None, afirma=None) -> dict:
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
    if afirma:
        fuera["afirma"] = afirma
    return fuera


# ── LO QUE EL CLIENTE AFIRMA ────────────────────────────────────────────────
#
# UNA SOLA CASILLA PARA DOS COSAS QUE PARECIAN DISTINTAS, y esa es toda la
# idea. El cliente afirma algo; lo que cambia es contra que se puede
# verificar:
#
#   SOBRE UN PRODUCTO NUESTRO   "el teclado K120 inalambrico ese"
#                               hay ficha: se verifica y se contesta con el
#                               dato real. Es la PREMISA FALSA, el eje F2, y
#                               la FICHA 57 §5.1 la llama el unico vector que
#                               hoy pasaria por todos los candados: la
#                               alucinacion no la trae el modelo, la trae el
#                               CLIENTE, y aceptarla es mentir con sus
#                               palabras.
#
#   SOBRE ALGO SUYO             "mi notebook tiene 8 giga", "ya tengo el cable"
#                               no hay ficha contra que cotejar, y eso NO es un
#                               error: es una fuente de verdad que el cliente
#                               aporta y que vale para el resto de la charla.
#
# QUE LA MISMA CASILLA RESUELVA LAS DOS ES LO QUE LA HACE BARATA: al modelo no
# se le pide que decida de cual de los dos casos se trata. Anota lo que el
# cliente dijo y el CODIGO decide, que es la regla 10.0 aplicada a las
# afirmaciones: la identidad la decide una funcion determinista.
#
# LOS CUATRO VEREDICTOS, y `no_consta` es tan valido como los otros:
#
#   confirma      la ficha lo dice
#   contradice    la ficha dice OTRA cosa en ese mismo campo, y va el dato real
#   no_consta     ese campo esta vacio en la ficha, o nadie en el catalogo usa
#                 esa palabra. NO se puede negar por ausencia
#   del_cliente   no se resolvio a ningun producto: es dato suyo
#
# POR QUE `no_consta` Y NO "contradice" ANTE UNA FICHA MUDA. Ausencia de
# evidencia no es evidencia de ausencia, y confundirlas seria inventar una
# negacion — el mismo defecto que el campo muerto diciendo "no lo vendemos",
# que se acaba de arreglar un piso mas abajo.
#
# Y NO SE COMPARA POR PARECIDO. La verificacion la hace `evaluar`, la misma
# funcion con la que se resuelve cualquier condicion del catalogo, con sus
# tres respuestas de siempre: True, False y None. No hay ranking ni umbral.

# Cuantas afirmaciones se verifican en una llamada. Mas que esto no es un
# cliente hablando: es un formulario.
TOPE_AFIRMA = 4


def _una_afirmacion(pedido: dict, catalogo: list, tienda_id: str) -> dict:
    """UNA afirmacion del cliente, verificada contra la fuente."""
    from app.core.filtros_catalogo import (_valor_crudo, campos_con_el_valor,
                                           campos_filtrables, evaluar,
                                           los_que_lo_nombran_entero)
    sobre = str((pedido or {}).get("sobre") or "").strip()
    dice = str((pedido or {}).get("dice") or "").strip()
    base = {"sobre": sobre, "dice": dice}
    if not dice:
        return {**base, "veredicto": "no_consta",
                "motivo": "la afirmacion vino sin contenido"}
    # 1 · ¿DE QUE HABLA? La identidad la decide el certificador de siempre.
    fichas = los_que_lo_nombran_entero(catalogo, sobre) if sobre else []
    # NOMBRAR UN RUBRO NO ES NOMBRAR UNA FICHA, y es lo que cazo el primer test
    # de "mi notebook": `los_que_lo_nombran_entero` devuelve 191, porque "mi"
    # no es una palabra util y "notebook" lo dicen todas. Pasado `TOPE_AMBIGUO`
    # el cliente nombro ANCHO —es el mismo criterio con el que el motor decide
    # que una cosa con variantes dejo de serlo— y sobre un rubro entero no hay
    # ficha contra que cotejar: es dato suyo.
    if len(fichas) > TOPE_AMBIGUO:
        fichas = []
    if not fichas:
        return {**base, "veredicto": "del_cliente",
                "motivo": "no es de un producto nuestro, asi que es un dato "
                          "que aporta el cliente: tomalo como cierto y usalo "
                          "en el resto de la charla"}
    # 2 · ¿DONDE VIVIRIA ESO? Es el aterrizaje, el mismo del 22-sep.
    campos = campos_con_el_valor(catalogo, dice, tienda_id)
    if not campos:
        return {**base, "veredicto": "no_consta",
                "motivo": f"ningun producto del catalogo dice '{dice}', asi "
                          f"que no puedo confirmarlo NI negarlo"}
    registro = campos_filtrables(tienda_id)
    # 3 · CONTRA CADA FICHA CANDIDATA, con `evaluar` y sus tres respuestas.
    porficha = []
    for f in fichas[:TOPE_AMBIGUO]:
        visto, real = None, ""
        for campo in campos:
            r = evaluar(f, campo, "contiene", dice, registro.get(campo, ""))
            if r is True:
                visto = "confirma"
                break
            if r is False and visto is None:
                # CON `_valor_crudo` Y NO CON `get`: `conexion` y varios mas
                # los DERIVA `fuente_producto.enriquecer` y no estan en el
                # dict del catalogo. Con `get` el dato real salia `None`, o
                # sea que se le mandaba al modelo "el dato real es None" —peor
                # que no decir nada, porque suena a dato—.
                visto = "contradice"
                real = f"{campo}: {_valor_crudo(f, campo)}"
        porficha.append((visto or "no_consta", real, f))
    veredictos = {v for v, _, _ in porficha}
    # UNA AMBIGUEDAD DE IDENTIDAD NO IMPIDE VERIFICAR, y es el caso medido: "el
    # K120" son dos fichas —negra y blanca— y las dos contestan lo mismo sobre
    # si es inalambrico. Preguntar cual solo hace falta si difieren.
    if len(veredictos) > 1:
        return {**base, "veredicto": "ambiguo",
                "motivo": "'" + sobre + "' puede ser mas de uno y no todos "
                          "dicen lo mismo de eso: pregunta cual. "
                          + " | ".join(f"{f.get('nombre')} ({f.get('id')})"
                                       for _, _, f in porficha)}
    v, real, f = porficha[0]
    if v == "confirma":
        return {**base, "veredicto": "confirma", "id": str(f.get("id")),
                "motivo": f"la ficha de {f.get('nombre')} lo dice"}
    if v == "contradice":
        return {**base, "veredicto": "contradice", "id": str(f.get("id")),
                "dato_real": real,
                "motivo": f"{f.get('nombre')} NO es asi. El dato real es "
                          f"{real}. Deciselo con esas palabras antes de "
                          f"seguir: no le repitas la suya"}
    return {**base, "veredicto": "no_consta", "id": str(f.get("id")),
            "motivo": f"la ficha de {f.get('nombre')} no trae ese dato, asi "
                      f"que no lo puedo confirmar ni negar"}


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
           afirma: list | None = None,
           envios: list | None = None, localidad_previa: str = "",
           criterio: list | None = None, cuenta: dict | None = None,
           reparto_pago: list | None = None) -> dict:
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
    # LAS DOS FORMAS, y la vieja no se rompe. Desde el 20-sep el modelo manda
    # objetos con `destino` y `va`; un texto pelado sigue valiendo y es lo que
    # llega desde la memoria de una charla vieja.
    nombres, el_va = [], {}
    for e in (envios or []):
        if isinstance(e, dict):
            d = str(e.get("destino") or "").strip()
            if not d:
                continue
            nombres.append(d)
            if str(e.get("va") or "").strip():
                el_va[d] = str(e["va"]).strip()
        elif str(e or "").strip():
            nombres.append(str(e).strip())

    fuera_envios: dict = {}
    if nombres:
        try:
            fuera_envios = cotizar_destinos(nombres, tienda_id,
                                            localidad_previa) or {}
            # EL VINCULO VUELVE PEGADO A SU TARIFA. Separados, el modelo tiene
            # tres montos y tres frases y los aparea de memoria, que es la
            # junta blanda que este repo ya tiene numerada cuatro veces.
            for fila in fuera_envios.get("filas") or []:
                if fila.get("destino") in el_va:
                    fila["va"] = el_va[fila["destino"]]
        except Exception as e:  # noqa: BLE001 — sin tarifa no se inventa una
            log.warning("motor_envio_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
    cotizado = any(f.get("monto_ars") for f in fuera_envios.get("filas") or [])

    # LA VALVULA DE ESCAPE NO SE CERTIFICA, SE CONTESTA. `SIN_TEMA` es el valor
    # que el enum le deja escribir al modelo cuando el cliente pregunto algo de
    # la casa que la lista no cubre. Mandarlo al certificador seria pedirle que
    # le busque señas a una frase nuestra, y con las raices de cuatro letras
    # pegaria con cualquier cosa; va derecho a `sin_resolver`, que es la caja
    # que ya significa "eso la casa no lo tiene escrito".
    from app.core.fuente import SIN_TEMA
    pedidos = [t for t in (temas or []) if t != SIN_TEMA]
    fuera_temas, sin_resolver = [], []
    criterios, sin_criterio = [], []
    if len(pedidos) != len(temas or []):
        sin_resolver.append(SIN_TEMA)
    if pedidos:
        try:
            r = politicas_de(pedidos[:TOPE_TEMAS], tienda_id)
            fuera_temas = list(r["politicas"])
            sin_resolver += r["sin_resolver"]
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

    if (not consultas and not compat and not afirma
            and not (cuenta or {}).get("items")):
        # SOLO POLITICAS, SOLO ENVIO O SOLO CRITERIO ES UNA LLAMADA VALIDA.
        # `afirma` entra en la condicion porque verificar lo que el cliente da
        # por sentado NECESITA el catalogo, igual que la compatibilidad: sin
        # ficha no hay contra que cotejar. Se olvido en el primer cableado y
        # la caja volvia vacia en el unico caso en que el cliente afirma algo
        # sin pedir nada mas —que es justo como llega la premisa falsa—.
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

    # EL RAMAL DE LO QUE EL CLIENTE AFIRMA. Una afirmacion rota no tumba el
    # resto: vuelve `no_consta`, que es la salida honesta de esta boca y no
    # una negacion. El motivo entero esta en `_una_afirmacion`.
    afirmaciones = []
    for pedido in (afirma or [])[:TOPE_AFIRMA]:
        try:
            afirmaciones.append(_una_afirmacion(pedido, catalogo, tienda_id))
        except Exception as e:  # noqa: BLE001 — por ausencia no se niega nada
            log.warning("motor_afirma_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
            afirmaciones.append(
                {"sobre": str((pedido or {}).get("sobre") or ""),
                 "dice": str((pedido or {}).get("dice") or ""),
                 "veredicto": "no_consta",
                 "motivo": "eso no se pudo verificar"})

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
            # EL REPARTO ENTRA POR ARRIBA Y SE APLICA ADENTRO. El campo
            # subio al primer nivel del tablero, pero la cuenta lo sigue
            # leyendo de donde siempre: se junta aca y `_la_cuenta` no se
            # entera del cambio. Lo que el modelo haya anotado adentro de
            # `cuenta` sigue valiendo, asi que una llamada vieja no se rompe.
            if reparto_pago and not (cuenta or {}).get("reparto_pago"):
                cuenta = dict(cuenta or {})
                cuenta["reparto_pago"] = reparto_pago
            la_cuenta = _la_cuenta(cuenta, fuera_envios, tienda_id, trace_id,
                                   catalogo)
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
             afirma=[a["veredicto"] for a in afirmaciones],
             envios=[f["destino"] for f in fuera_envios.get("filas") or []],
             criterio=[c["tema"] for c in criterios],
             cuenta=la_cuenta.get("total_ars") or la_cuenta.get("sin_total"))
    return _salida(fuera, fuera_temas, sin_resolver, compatibilidades,
                   fuera_envios, criterios, sin_criterio, la_cuenta,
                   afirmaciones)


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
