"""
EL GRAFO DEL TURNO — el cableado declarado, y los contratos de cada arista.

POR QUE EXISTE (Martin, 12-ago-2026). "Si tenemos que hacer el arreglo manual
de todas las posibles causas y errores, seria una actividad casi interminable".
Es exactamente asi, y no por falta de esfuerzo: es una propiedad de como esta
cableado el turno. Los dos errores de plata que encontro el barrido del codigo
esa misma mañana NO vivian adentro de un modulo, vivian en la COSTURA entre
dos, con los dos en verde. Mientras el cableado sea una funcion imperativa de
dos mil trescientas lineas, el conjunto de costuras no se puede enumerar, y lo
que no se enumera se descubre de a uno, a mano, cuando revienta.

QUE ES ESTO. El mismo turno que corre hoy, escrito como DATOS en vez de como
flujo: cada engranaje es un nodo con su funcion real, lo que exige al entrar y
lo que garantiza al salir. No agrega un camino nuevo ni cambia el orden de
nada. Lo que agrega es la posibilidad de preguntarle cosas al cableado.

LAS TRES COSAS QUE HABILITA, y por eso paga:

  1. EL CONTRATO EN LA ARISTA. Cada nodo de salida declara que contratos
     mecanicos cumple: que no deja mudo al bot, que no inventa un peso, que
     aplicarlo dos veces da lo mismo que una, que nunca levanta. Son cuatro
     propiedades por veintipico de nodos, o sea que un contrato escrito UNA vez
     se cobra en todos. Esa es la unica forma conocida de que el trabajo deje de
     crecer con la cantidad de bugs.
  2. EL BARRIDO SE GENERA DEL GRAFO. `tests/test_grafo_cableado.py` no tiene la
     lista de nodos escrita a mano: la recorre de aca. Un nodo nuevo entra al
     barrido por existir, no porque alguien se acuerde de agregarlo.
  3. EL VEREDICTO POR ENGRANAJE. Cuando la respuesta sale mal, hoy hay que leer
     la charla entera para saber CUAL fallo. Con el grafo cada nodo deja su
     marca con el trace_id, y el turno cierra con una linea que dice quien toco
     el mensaje y quien no.

LO QUE NO ES. No es un motor de flujo ni un framework de orquestacion: el turno
lo sigue corriendo `hub_venta.procesar_venta`, linea por linea, igual que ayer.
Meter un motor seria cambiar el camino vivo entero de una, que es justo lo que
este repo ya pago caro una vez. El grafo describe, ata y mide; el dia que el
motor haga falta, ya va a estar el mapa hecho.

LO QUE LO HACE VERDAD Y NO DOCUMENTACION. `test_el_grafo_no_puede_mentir` compara
esta tabla contra el codigo de `procesar_venta`: si un nodo declara una funcion
que no existe, si el orden declarado no es el orden real, o si el turno gana un
engranaje que nadie declaro, el push se pone rojo. Un mapa que puede envejecer
en silencio es peor que no tener mapa, y este repo ya se comio esa: el 11-ago
una sesion leyo un numero viejo de un documento y se lo repitio a Martin como
dato actual.
"""
import json
from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass, field

# ── LOS CONTRATOS, escritos una vez y cobrados en cada nodo ─────────────────
#
# Son MECANICOS a proposito: los cuatro se comprueban sin saber cual era la
# respuesta correcta, que es la unica manera de correrlos sobre entradas
# generadas. Un contrato que necesita un texto esperado no sirve acá.
NO_ENMUDECE = "no_enmudece"
"""Entra un mensaje con contenido, sale un mensaje con contenido. La falla que
esto cubre le llego a Martin: una guarda se comio el turno entero y el cliente
leyo el mensaje de respaldo. Un bot mudo no vende."""

NO_INVENTA_PLATA = "no_inventa_plata"
"""Todo importe que sale ya estaba en lo que entro, o en un bloque sellado por
el codigo que el nodo tiene permitido reponer. Ningun engranaje de salida puede
crear un numero de plata: la cuenta la hace la calculadora y nadie mas."""

IDEMPOTENTE = "idempotente"
"""Aplicarlo dos veces da lo mismo que aplicarlo una. Es el contrato que
protege del orden: un nodo idempotente no puede romperse porque otro corra
antes o porque el turno lo pase dos veces por un reintento."""

NO_LEVANTA = "no_levanta"
"""Ninguna entrada lo hace explotar. Un engranaje de control que levanta deja
el turno sin respuesta, que es peor que el defecto que venia a arreglar."""

TODOS_LOS_CONTRATOS = (NO_ENMUDECE, NO_INVENTA_PLATA, IDEMPOTENTE, NO_LEVANTA)

# ── LOS CONTRATOS DE LA MITAD QUE DECIDE ───────────────────────────────────
#
# Los cuatro de arriba son de los nodos que transforman TEXTO. La mitad de
# decision y reposicion no toca el texto: mueve DATOS -las llamadas a las
# herramientas, lo que el modelo declaro, lo que el reconciliador reclama-, asi
# que sus contratos son otros y hasta el 14-ago no estaban escritos. Eso dejaba
# quince de los treinta y tres nodos sin una sola propiedad que se pudiera
# comprobar sobre entradas generadas: la mitad que AMORTIGUA los errores era la
# que nadie medía.
#
# Se comprueban igual que los otros: sin saber cual era la respuesta correcta.
NO_INVENTA_ID = "no_inventa_id"
"""Ningun product_id sale de un nodo si no entro, o si no existe en el catalogo
real. Es la regla cero del proyecto -la identidad la decide el codigo- aplicada
a los engranajes que reponen: un nodo que completa lo que el modelo no hizo no
puede completarlo con un producto que no existe."""

NO_PIERDE_EVIDENCIA = "no_pierde_evidencia"
"""Toda herramienta que entro sigue estando a la salida. Un nodo de reposicion
puede REEMPLAZAR el resultado de una busqueda -eso es su trabajo- pero no puede
hacer desaparecer la busqueda entera: lo que se pierde acá deja al redactor sin
el dato y el bot termina negando lo que el catalogo si tiene."""

NO_AGREGA_LO_NO_PEDIDO = "no_agrega_lo_no_pedido"
"""Ningun item entra a la cuenta si el cliente no lo pidio. Es el defecto que
esta ABIERTO en PENDIENTE: en la charla real del 12-ago salio a la cuenta un
auricular que no estaba en el carrito, y lo freno la regla cero de la
calculadora, que es la red y no el arreglo."""

NO_RECLAMA_LO_RESUELTO = "no_reclama_lo_resuelto"
"""Lo que ya esta atendido no se vuelve a reclamar. Cada reclamo imposible
quema una ronda entera del turno: mas latencia, mas tokens y ninguna respuesta
mejor. Medido el 7-ago: de 88 faltantes emitidos, 41 se repitieron en dos o mas
rondas del MISMO turno."""

CONTRATOS_DE_DATOS = (NO_LEVANTA, IDEMPOTENTE, NO_INVENTA_ID,
                      NO_PIERDE_EVIDENCIA, NO_AGREGA_LO_NO_PEDIDO)
"""La familia entera. Es el universo de nombres validos para un nodo que mueve
datos, igual que `TODOS_LOS_CONTRATOS` lo es para los que mueven texto."""

CONTRATOS_DE_REPOSICION = (NO_LEVANTA, IDEMPOTENTE, NO_INVENTA_ID,
                           NO_PIERDE_EVIDENCIA, NO_AGREGA_LO_NO_PEDIDO)
"""Los cinco que cumple el resolver y cumplia la reposicion. `no_reclama_lo_
resuelto` queda afuera a proposito: solo tenia sentido para el reconciliador,
que en la FICHA 34 salio del vivo. Declararselo al resolver seria un contrato
que se cumple por vacio, y un verde por vacio es el que enseña a no mirar."""

# Las etapas del turno, en orden. La de reposicion salio en la FICHA 34: el
# nexo es resolver, adentro de decision. Cinco etapas, no seis.
ETAPAS = ("entrada", "decision", "redaccion", "salida", "memoria")


@dataclass(frozen=True)
class Nodo:
    """Un engranaje del turno.

    `funcion` es el simbolo REAL, "modulo:funcion", y el candado lo verifica:
    sin eso esto seria una lista de nombres lindos. `exige` y `garantiza` son
    el contrato en prosa, para el que lee; `contratos` es el contrato en
    maquina, para el barrido."""
    id: str
    etapa: str
    funcion: str
    exige: str
    garantiza: str
    contratos: tuple = ()
    # Un nodo de salida transforma el texto: `aplicar` lo corre con el contexto
    # del turno, y es lo que permite barrerlo sin pasar por el modelo.
    aplicar: object = None
    # Las fuentes selladas que este nodo tiene permitido REPONER en el mensaje.
    # Sin esto, el nodo que vuelve a pegar la cuenta parece estar inventando
    # plata cuando en realidad esta devolviendo la del codigo.
    repone: tuple = ()
    # Un nodo de decision o reposicion NO transforma texto: mueve el estado del
    # turno -las llamadas, lo declarado, lo que reclama el reconciliador-.
    # `aplicar_datos` lo corre sobre ese estado y devuelve el estado nuevo, que
    # es lo que permite barrerlo sin pasar por el modelo.
    aplicar_datos: object = None
    # POR QUE ESTE NODO NO TIENE CONTRATO MECANICO. Es obligatorio cuando
    # `contratos` esta vacio, y el candado lo exige: sin esto un nodo sin
    # contrato no se distingue de un nodo al que nadie le escribio el contrato
    # todavia, que es exactamente como quedaron quince nodos sin que se notara.
    sin_contrato: str = ""
    # PIEZAS INTERNAS que registran con su propio id adentro de este nodo.
    # No son Nodo() propios: el barrido barre la puerta, el censo las cuenta
    # como huerfanos. La lista tiene que coincidir con G.censo().
    piezas: tuple = ()


def _n(fn):
    """Envuelve una funcion del hub en la forma uniforme del grafo: recibe el
    texto y el contexto del turno, devuelve el texto."""
    return fn


def _con(ctx: dict, **cambios) -> dict:
    """El estado del turno con un engranaje aplicado encima.

    Los nodos que mueven datos se declaran asi -estado adentro, estado afuera-
    para que el barrido pueda correrlos en cadena, compararlos antes y despues,
    y aplicarlos dos veces para el contrato de idempotencia, sin saber cual de
    ellos es. Es lo mismo que `aplicar` hace con el texto, un piso mas arriba."""
    fuera = dict(ctx)
    fuera.update(cambios)
    return fuera


# ── EL TURNO, NODO POR NODO, EN EL ORDEN EN QUE CORRE ───────────────────────
NODOS = (
    # ── entrada ──────────────────────────────────────────────────────────
    Nodo(id="estado", etapa="entrada",
         funcion="app.core.estado_venta:construir_estado",
         exige="la conversacion guardada de Firestore",
         garantiza="el estado del turno: carrito, productos vistos, "
                   "localidades, preferencias",
         sin_contrato="lo barre entero LA MEMORIA ENTRE TURNOS, que mide sus "
                      "campos contra esta misma funcion y llega al 100%: "
                      "escribirle contratos aca seria la misma prueba dos "
                      "veces"),
    Nodo(id="memoria_texto", etapa="entrada",
         funcion="app.core.hub_venta:_memoria_texto",
         exige="el estado y el historial",
         garantiza="el bloque de memoria que ve el modelo, sin inventar nada "
                   "que no este en el estado",
         contratos=(NO_LEVANTA, IDEMPOTENTE, NO_INVENTA_ID),
         aplicar_datos=lambda c: _con(
             c, memoria_texto=_hub()._memoria_texto(
                 c.get("estado") or {}, c.get("history") or [],
                 c["tienda_id"]))),

    # ── decision: que hace falta y que trajo ──────────────────────────────
    Nodo(id="decisor", etapa="decision",
         funcion="app.core.hub_venta:_pedir_herramientas",
         exige="el mensaje del cliente y la memoria",
         garantiza="una lista de herramientas con argumentos validados por el "
                   "molde, o texto directo si el turno no necesita ninguna",
         sin_contrato="es el modelo DECLARANDO. Ve registrar_pedido; el codigo "
                      "deriva que buscar. Lo que declara no es determinista y "
                      "ningun barrido lo puede comprobar: lo miden los "
                      "casetes, el explorador e interpretacion.py. Lo que SI "
                      "es determinista de este nodo -el esquema que le viaja y "
                      "la validacion de lo que devuelve- lo barren LO QUE EL "
                      "MODELO DECLARA y el barrido del esquema"),
    Nodo(id="herramientas", etapa="decision",
         funcion="app.core.hub_venta:_ejecutar_en_paralelo",
         exige="pedidos con argumentos validos",
         garantiza="el resultado de cada herramienta, con su estado, sin que "
                   "una que falla tumbe a las otras",
         # SIN IDEMPOTENTE, y sigue sin serlo aunque las rondas se hayan ido.
         # El 17-ago se intento cobrarle el contrato de yapa -sin rondas el
         # turno lo corre una sola vez, asi que parecia gratis- y el barrido lo
         # freno con 72 violaciones: al dejar de acumular, el nodo perdia las
         # herramientas que ya venian en el estado, o sea que se ganaba
         # `idempotente` pagando `no_pierde_evidencia`. Acumular no cuesta nada
         # -en el turno vivo la lista arranca vacia- y no perder evidencia
         # importa mucho mas: lo que se pierde aca deja al redactor sin el dato.
         contratos=(NO_LEVANTA, NO_INVENTA_ID, NO_PIERDE_EVIDENCIA,
                    NO_AGREGA_LO_NO_PEDIDO),
         aplicar_datos=lambda c: _con(
             c, llamadas=list(c.get("llamadas") or []) + _ejecutar_sync(
                 c.get("pedidos") or [], c["tienda_id"], c["trace_id"]))),
    Nodo(id="busquedas_derivadas", etapa="decision",
         funcion="app.core.resolver:_derivar_las_busquedas",
         exige="lo que el modelo declaro del mensaje",
         garantiza="una busqueda por cada cosa declarada, con las palabras del "
                   "cliente; no declara nada que el cliente no haya pedido",
         # IDEMPOTENTE de verdad y no por suerte: `_agregar` no repite una
         # herramienta con los mismos argumentos y devuelve la que ya estaba,
         # asi que la segunda pasada no agrega una llamada calcada ni cambia
         # una decision que dependa del estado de la primera.
         contratos=CONTRATOS_DE_REPOSICION,
         aplicar_datos=lambda c: _con(
             c, llamadas=_nexo()._derivar_las_busquedas(
                 c.get("llamadas") or [], c.get("declarado") or {},
                 c.get("memoria") or [], c["tienda_id"], c["trace_id"]))),
    # EL NEXO (FICHA 34). Reemplaza al reconciliador y a la puerta de
    # reposicion: una sola opinion sobre el pedido, desde lo declarado.
    Nodo(id="resolver", etapa="decision",
         funcion="app.core.resolver:resolver",
         exige="lo que el modelo declaro y la memoria de la charla",
         garantiza="las busquedas derivadas, la cuenta armada por la "
                   "calculadora sobre ids certificados y el contrato del "
                   "turno; no inventa un producto ni una cifra",
         contratos=CONTRATOS_DE_REPOSICION,
         piezas=("cuenta_repuesta", "reparto_repuesto",
                 "supuesto_de_pago", "bloques_a_uno"),
         aplicar_datos=lambda c: _aplicar_nexo(c)),
    Nodo(id="indice_turno", etapa="decision",
         funcion="app.core.indice_turno:cobertura",
         exige="lo interpretado y el material que trajeron las herramientas",
         garantiza="que punto del pedido tiene con que contestarse y cual no",
         contratos=(NO_LEVANTA, IDEMPOTENTE),
         piezas=("puerta_cobertura",),
         aplicar_datos=lambda c: _con(
             c, indice=__import__(
                 "app.core.indice_turno", fromlist=["x"]).cobertura(
                     c.get("declarado") or {}, c.get("texto") or "",
                     c["trace_id"], llamadas=c.get("llamadas") or [],
                     memoria=c.get("memoria") or []))),

    # ── redaccion ────────────────────────────────────────────────────────
    Nodo(id="redactor", etapa="redaccion",
         funcion="app.core.hub_venta:_redactar",
         exige="el material de las herramientas y la obligacion del turno",
         garantiza="prosa del modelo, con las etiquetas de la atadura puestas",
         sin_contrato="es el modelo escribiendo. La redaccion no es "
                      "determinista y ningun barrido la puede comprobar: la "
                      "miden los casetes con su piso, el explorador y los "
                      "invariantes. Lo que el codigo hace con esa prosa lo "
                      "barren las cuatro puertas de salida"),

    # ── salida: CUATRO PUERTAS ───────────────────────────────────────────
    #
    # ERAN DIECIOCHO NODOS (FICHA 10, 24-ago-2026), y las dieciocho
    # comprobaciones siguen corriendo: lo que se agrupo es el PASO DEL TURNO.
    # Cada puerta contesta UNA pregunta sobre el mensaje —de donde salio el
    # dato, quien calculo el numero, que tiene que estar si o si, como se lee—
    # y adentro corre sus piezas en un orden fijo, con `G.paso` cada una, asi
    # que el veredicto por engranaje es el mismo de antes. Lo que desaparece
    # son diecisiete costuras: los dos errores de plata de agosto no vivian
    # adentro de una pieza, vivian entre dos.
    #
    # LOS CONTRATOS DE UNA PUERTA SON LOS DE SU PIEZA MAS DEBIL, no la union
    # de todas: una cadena cumple lo que cumplen todos sus eslabones. Por eso
    # `procedencia` no declara NO_INVENTA_PLATA -la atadura nunca lo declaro- y
    # `obligacion` tampoco, porque su tercera pieza es la unica del turno que
    # SUMA, y lo que suma es la cuenta sellada de la calculadora.
    Nodo(id="procedencia", etapa="salida",
         funcion="app.core.salida:procedencia",
         exige="prosa del modelo, con las etiquetas puestas, y las llamadas "
               "del turno",
         garantiza="ningun dato que no venga del material del turno: sin "
                   "etiquetas, sin JSON, sin markdown, sin un CBU que no sea "
                   "el de la tienda, sin negar lo que el catalogo trajo, sin "
                   "afirmar sobre los 880, sin descuentos que no existen y "
                   "sin la cocina del sistema a la vista",
         contratos=(NO_ENMUDECE, NO_LEVANTA, IDEMPOTENTE),
         piezas=("atadura", "sin_json", "sin_markdown",
                 "sin_cobro_inventado", "sin_negar_lo_traido",
                 "sin_afirmar_del_catalogo", "sin_descuento_inventado",
                 "sin_narracion_interna"),
         aplicar=lambda t, c: __import__(
             "app.core.salida", fromlist=["x"]).procedencia(
                 t, c["llamadas"], c["trace_id"], c["tienda_id"])),
    Nodo(id="plata", etapa="salida",
         funcion="app.core.salida:plata",
         exige="el texto, las llamadas que respaldan cada cifra y el bloque "
               "sellado de la calculadora",
         garantiza="la cuenta es la que armo el codigo y viaja ENTERA; ningun "
                   "importe sale sin respaldo en ella o en la fuente; ningun "
                   "anuncio de presupuesto queda sin presupuesto abajo",
         contratos=TODOS_LOS_CONTRATOS,
         repone=("previo", "bloque", "hallazgo"),
         piezas=("la_cuenta_y_la_plata", "sin_anuncio_vacio",
                 "bloque_repuesto", "hallazgo_repuesto"),
         aplicar=lambda t, c: __import__(
             "app.core.salida", fromlist=["x"]).plata(
                 t, c["llamadas"], c["bloque"], c["trace_id"],
                 previo=c["previo"], vistos=c["vistos"])),
    Nodo(id="obligacion", etapa="salida",
         funcion="app.core.salida:obligacion",
         exige="el mensaje del cliente, si es el primer turno, y los puntos "
               "que el cliente abrio",
         garantiza="si preguntan si es un bot se dice que si; el saludo se "
                   "dice una vez y solo la primera; ningun punto que el "
                   "sistema sabe contestar se va sin contestar; con un total "
                   "cerrado sobre la mesa se dice COMO SE PAGA, una vez",
         contratos=(NO_ENMUDECE, NO_LEVANTA, IDEMPOTENTE),
         repone=("bloque",),
         piezas=("honestidad_bot", "saludo", "punto_omitido",
                 "camino_al_cobro"),
         aplicar=lambda t, c: __import__(
             "app.core.salida", fromlist=["x"]).obligacion(
                 t, c["mensaje"], c["negocio"], not c.get("anterior"),
                 c.get("declarado") or {}, c["llamadas"],
                 c.get("memoria") or [], c["tienda_id"], c["trace_id"])),
    Nodo(id="higiene", etapa="salida",
         funcion="app.core.salida:higiene",
         exige="el mensaje entero, ya compuesto por las tres puertas de "
               "arriba, y el anterior del bot",
         garantiza="sin repeticion, lossless, un mutador: componer. No "
                   "reescribe la prosa del modelo",
         contratos=TODOS_LOS_CONTRATOS,
         piezas=("componedor",),
         aplicar=lambda t, c: __import__(
             "app.core.salida", fromlist=["x"]).higiene(
                 t, c["anterior"], c["mensaje"], c["trace_id"],
                 c["tienda_id"], vocabulario=c.get("vocabulario"))),

    # ── memoria: guardar, cerrar y cobrar ────────────────────────────────
    #
    # EL CIERRE DEJA DE SER UNA GUARDIA DE SALIDA (FICHA 10). Nunca verifico
    # nada del texto: graba el lead y pega los datos de cobro que salen de la
    # config. Es el paso 6 del sistema objetivo -"memoria, cierre y cobro"- y
    # era el unico nodo de salida sin contrato mecanico, o sea una excepcion
    # que habia que escribir cada vez que alguien contaba los contratos. En su
    # etapa la excepcion desaparece: lo que sale al cliente lo ata la puerta
    # de la procedencia, que si tiene contratos.
    Nodo(id="cierre", etapa="memoria",
         funcion="app.core.hub_venta:_cerrar",
         exige="la señal de cierre y el presupuesto",
         garantiza="los datos de cobro que salen de la config, o nada",
         sin_contrato="no transforma el texto: graba el lead y devuelve los "
                      "datos de cobro. Escribe en el almacenamiento, que es "
                      "una de las cuatro razones declaradas en "
                      "sin_camino_offline. Lo que sale al cliente lo ata la "
                      "puerta de la procedencia, que si tiene contratos"),
    Nodo(id="memoria", etapa="memoria",
         funcion="app.storage.firestore_client:save_conversation",
         exige="el turno cerrado",
         garantiza="el estado guardado para el turno siguiente; un error de "
                   "guardado no tumba la respuesta",
         sin_contrato="escribe en Firestore, declarado en sin_camino_offline. "
                      "Lo que se guarda y como vuelve al turno siguiente lo "
                      "barre entero LA MEMORIA ENTRE TURNOS"),
)

POR_ID = {n.id: n for n in NODOS}


def _hub():
    """Import perezoso: `hub_venta` importa este modulo para registrar sus
    veredictos, asi que el grafo no puede importarlo arriba."""
    from app.core import hub_venta
    return hub_venta


def _nexo():
    """El resolver, perezoso: `resolver` pide `grafo` para dejar el veredicto
    de las busquedas y de la cuenta."""
    from app.core import resolver
    return resolver


def _aplicar_nexo(c: dict) -> dict:
    out = _nexo().resolver(
        c.get("declarado") or {},
        c.get("memoria") or [],
        c["tienda_id"],
        c["trace_id"],
        llamadas=c.get("llamadas") or [],
        descartados=c.get("descartados") or [],
        diferida=c.get("diferida") or [],
    )
    # El contrato del indice lleva ids de PUNTO (`item:1`, `oferta:1`), no de
    # producto. Si viaja en el ctx, `no_inventa_id` los lee como product_id.
    # El barrido mide las llamadas; el contrato lo consume el hub, no este
    # aplicar.
    return _con(c, llamadas=out["llamadas"], bloque=out["bloque"])


CICLOS = ()
"""EL TURNO NO TIENE CICLOS DESDE EL 17-AGO, y es el cambio que mas latencia
saco. Habia uno solo: si el reconciliador encontraba un faltante se volvia al
decisor, hasta cuatro veces. Ahora el faltante lo resuelve el codigo en el
resolver, y lo que ni asi se resuelve se lo dice el indice al redactor. Un
grafo sin ciclos tiene un numero fijo de llamadas al modelo por turno: dos."""


def nodos_de(etapa: str) -> tuple:
    return tuple(n for n in NODOS if n.etapa == etapa)


def barribles() -> tuple:
    """Los nodos que el barrido puede correr solo, sin modelo y sin red: los
    que transforman texto y saben decir como se los llama."""
    return tuple(n for n in NODOS if n.aplicar and n.contratos)


def barribles_de_datos() -> tuple:
    """Los nodos de la mitad que DECIDE: no tocan el texto, mueven el estado
    del turno. Se corren igual que los otros, sin modelo y sin red."""
    return tuple(n for n in NODOS if n.aplicar_datos and n.contratos)


def sin_contrato() -> tuple:
    """Los nodos que NO tienen contrato mecanico, cada uno con su motivo.

    Es una lista corta y tiene que quedar corta: el candado
    `test_ningun_nodo_queda_sin_contrato_ni_motivo` no deja que un nodo entre
    al turno sin una cosa o la otra. Un nodo sin contrato y sin motivo es
    indistinguible de un nodo al que nadie le escribio el contrato, y asi
    quedaron quince sin que nadie lo notara hasta el 14-ago."""
    return tuple((n.id, n.sin_contrato) for n in NODOS if not n.contratos)


def _ejecutar_sync(pedidos: list, tienda_id: str, trace_id: str) -> list:
    """El ejecutor paralelo, corrido desde codigo sincronico. Es el MISMO
    `_ejecutar_en_paralelo` del turno vivo: el barrido no puede tener su propia
    version, que es la leccion mas cara de este repo."""
    import asyncio
    return asyncio.run(_hub()._ejecutar_en_paralelo(pedidos, tienda_id,
                                                    trace_id))


# ── EL VEREDICTO POR ENGRANAJE ─────────────────────────────────────────────
#
# EL PROBLEMA QUE CIERRA, y estaba abierto en PENDIENTE desde el 11-ago: cuando
# la respuesta sale mal hay que leer la charla entera para saber cual de los
# veintipico de engranajes la rompio. Las piezas ya logueaban sueltas, cada una
# con su nombre y su formato.
#
# EL VEREDICTO SE MIDE, NO SE DECLARA. Un nodo "intervino" si el texto que
# devolvio es distinto del que recibio. No se le pregunta al nodo ni se confia
# en lo que loguea: se compara. Es la misma regla que hace confiables a los
# invariantes, y por eso no puede mentir.
_marcas: ContextVar[list | None] = ContextVar("grafo_marcas", default=None)


# ── EL CENSO, ADENTRO DEL GRAFO ────────────────────────────────────────────
#
# EL AGUJERO QUE CIERRA (FICHA 12). `registrar()` dejaba la marca del turno y
# nada mas: `_marcas` es un ContextVar que `abrir_turno` PISA en cada turno, asi
# que al terminar la charla no quedaba nada que contar. Para saber cuantas veces
# corrio e intervino cada engranaje sobre las quince charlas habia que envolver
# `G.registrar` DESDE AFUERA, y eso lo hacia `peso_del_censo.py` con un espia a
# mano. Un instrumento que solo mide si alguien le pone un espia encima mide lo
# que el espia ve, no lo que el turno hace: el dia que una pieza registre por
# otro camino, el espia no se entera y el censo cuenta cero en silencio.
#
# QUE ES ESTO. El mismo `registrar()` que ya llamaban las seis etapas, sumando
# ademas a un contador acumulado por nodo. No agrega una llamada nueva ni un
# camino nuevo: agrega DOS SUMAS adentro de la que ya estaba.
#
# LAS CUATRO REGLAS QUE LO HACEN SEGURO, y son las mismas que las de `registrar`:
#
#   1. NO CAMBIA COMPORTAMIENTO NI PUEDE TUMBAR UN TURNO. Va adentro del mismo
#      `registrar`, que nunca levanta, y son sumas sobre `defaultdict(int)`.
#   2. NO CRECE SIN LIMITE. Las claves son ids de nodo, que son finitos, y los
#      detalles se cortan en tres por nodo. Un contador que crece con los turnos
#      seria una perdida de memoria en un servicio que vive dias.
#   3. CUENTA TODAS LAS LLAMADAS, tambien las de afuera de un turno abierto.
#      `registrar` se va temprano si no hay hoja de marcas; el censo suma ANTES
#      de esa puerta, porque un engranaje que corre fuera del turno igual corrio
#      y esconderlo es la misma ceguera que se esta cerrando.
#   4. NO SE APAGA CON UNA FLAG. Son dos sumas por engranaje y el repo no deja
#      caminos apagados al lado del vivo.
#
# LO QUE HABILITA, Y ES EL PUNTO: `peso_del_censo.py` dejo de envolver nada y
# `tests/test_censo_del_grafo.py` afirma SOBRE CUANTOS NODOS midio, asi que el
# censo ya no puede pasar por vacio.

_censo_corrio: dict = defaultdict(int)
_censo_intervino: dict = defaultdict(int)
_censo_detalles: dict = defaultdict(list)
_censo_notas: dict = defaultdict(int)
_censo_turnos = 0

# LOS ENGRANAJES QUE LEVANTARON, CONTADOS APARTE. {nodo: [tipos de excepcion]}.
#
# POR QUE ES UN CONTADOR PROPIO Y NO UNA LINEA MAS DEL DETALLE (FICHA 19). Una
# excepcion atrapada y seguida de largo es la puerta por la que entraron los dos
# peores defectos que este repo encontro: el crasher de compatibilidad, que le
# devolvia el enlatado al cliente, y el `(?i)` del componedor, que alargaba los
# mensajes sin un solo test rojo. Las dos veces la marca estaba —`G.paso` deja
# `levanto:X` desde que existe— y las dos veces NADIE LA MIRABA, porque estaba
# adentro de una lista de detalles de la que ningun test afirmaba nada.
#
# Con esto la marca deja de ser un detalle y pasa a ser un numero que la bateria
# puede poner en rojo: `tests/test_ninguna_guardia_se_traga_una_excepcion.py`
# corre el corpus y exige CERO. Esa es la mitad viva del candado; la otra es
# estatica y mira el codigo.
_censo_levantes: dict = defaultdict(list)


def _censar(nodo_id: str, intervino: bool, detalle: str = "") -> None:
    """La suma acumulada de un engranaje. Nunca levanta, por lo mismo que
    `registrar`: un instrumento no puede tumbar lo que mide."""
    try:
        _censo_corrio[nodo_id] += 1
        if str(detalle or "").startswith("levanto:"):
            _censo_levantes[nodo_id].append(str(detalle)[len("levanto:"):])
        if intervino:
            _censo_intervino[nodo_id] += 1
            if detalle and len(_censo_detalles[nodo_id]) < 3:
                _censo_detalles[nodo_id].append(str(detalle)[:40])
    except Exception:  # noqa: BLE001 — medir peor es mejor que tumbar el turno
        pass


def censo_reiniciar() -> None:
    """Pone el censo en cero. La llama quien va a medir una tanda —el banco, un
    test— para que no arrastre lo que conto una corrida anterior."""
    global _censo_turnos
    _censo_corrio.clear()
    _censo_intervino.clear()
    _censo_detalles.clear()
    _censo_notas.clear()
    _censo_levantes.clear()
    _censo_turnos = 0


def censo() -> dict:
    """LO QUE MIDIO EL GRAFO, sin que nadie lo envuelva.

    `declarados` son los nodos de `NODOS`. `huerfanos` son los que dejan marca
    y NO estan declarados: las piezas internas de cada puerta, de la cuenta
    del resolver y de la cobertura, nombradas en el campo `piezas` de ese
    Nodo. **No son nodos faltantes y no se esconden**: corren adentro de su
    puerta, el barrido barre las puertas, el censo las cuenta aparte para que
    el numero no mienta ni por arriba ni por abajo. El candado esta en
    `tests/test_censo_del_grafo.py`.

    `turnos` sale de `abrir_turno`, que corre una vez por turno, y sirve de
    control: ningun nodo puede haber corrido mas veces que turnos hubo. Si uno
    lo supera esta marcando dos veces y TODOS los porcentajes quedan mal en
    silencio."""
    declarados = {n.id: n.etapa for n in NODOS}
    filas = []
    for nodo_id in sorted(set(_censo_corrio) | set(declarados)):
        corrio = _censo_corrio.get(nodo_id, 0)
        intervino = _censo_intervino.get(nodo_id, 0)
        if corrio == 0:
            clase = "NUNCA CORRE"
        elif intervino == 0:
            clase = "MUERTO"
        elif intervino == corrio:
            clase = "ESTRUCTURAL"
        else:
            clase = "A VECES"
        filas.append({
            "nodo": nodo_id,
            "etapa": declarados.get(nodo_id, "(sin declarar)"),
            "declarado": nodo_id in declarados,
            "corrio": corrio,
            "intervino": intervino,
            "pct": round(100 * intervino / corrio) if corrio else 0,
            "clase": clase,
            "muestra": list(_censo_detalles.get(nodo_id, []))[:3],
        })
    medidos = [f for f in filas if f["corrio"]]
    return {
        "turnos": _censo_turnos,
        "nodos_declarados": len(declarados),
        "nodos_medidos": len(medidos),
        "declarados_medidos": len([f for f in medidos if f["declarado"]]),
        "huerfanos_medidos": len([f for f in medidos if not f["declarado"]]),
        "etapas_medidas": sorted({f["etapa"] for f in medidos if f["declarado"]}),
        "ciegos": [f["nodo"] for f in filas if not f["corrio"]],
        "marcan_de_mas": [f["nodo"] for f in medidos
                          if _censo_turnos and f["corrio"] > _censo_turnos],
        "notas": dict(_censo_notas),
        # LOS QUE LEVANTARON. Vacio es lo unico aceptable, y la bateria lo
        # exige: un engranaje que explota y sigue de largo devuelve el texto
        # como entro, o sea que el control que ese engranaje era NO CORRIO y
        # el cliente lee lo que la guardia tenia que haber arreglado.
        "levantes": {k: list(v) for k, v in _censo_levantes.items() if v},
        "filas": filas,
    }


def abrir_turno() -> None:
    """Arranca la hoja de veredictos del turno. La llama el hub una sola vez.

    Y es tambien lo que le da al censo su DENOMINADOR: un turno abierto es un
    turno, y sin ese numero 'corrio 54 veces' no quiere decir nada."""
    global _censo_turnos
    _marcas.set([])
    _notas.set({})
    _censo_turnos += 1


def registrar(nodo_id: str, intervino: bool, detalle: str = "") -> None:
    """Deja la marca de un engranaje. Nunca levanta: un registro roto no puede
    tumbar un turno."""
    _censar(nodo_id, bool(intervino), detalle)
    marcas = _marcas.get()
    if marcas is None:
        return
    marcas.append({"nodo": nodo_id, "intervino": bool(intervino),
                   "detalle": str(detalle or "")[:80]})


_notas: ContextVar[dict | None] = ContextVar("grafo_notas", default=None)


def anotar(clave: str, valor) -> None:
    """El veredicto de un engranaje que NO transforma texto: el decisor,
    el indice.

    POR QUE ESTO Y NO OCHO LINEAS DE LOG (Martin, 12-ago-2026, y es su pedido
    textual: que todo lo que pasa adentro se pueda revisar). Cada engranaje ya
    dejaba su marca, pero cada uno en su propio evento y con su propio formato:
    para revisar UN turno habia que juntar ocho lineas a mano y saber cual
    buscar. Un sistema que solo se puede auditar por un experto que sabe donde
    mirar no esta auditado.

    Las marcas no cambian —cada modulo sigue logueando lo suyo, que sirve para
    el detalle—; lo que se agrega es el RESUMEN en un solo lugar, la ficha del
    turno, pegada a la linea de cierre que ya se lee siempre."""
    try:
        _censo_notas[str(clave)] += 1
    except Exception:  # noqa: BLE001 — un instrumento no rompe lo que mide
        pass
    notas = _notas.get()
    if notas is None:
        return
    notas[str(clave)] = valor


def marcas() -> list:
    return list(_marcas.get() or [])


def veredicto_del_turno() -> dict:
    """LA FICHA DEL TURNO: todo lo que paso adentro, en una sola linea.

    Los engranajes que tocaron el mensaje —medido comparando, no
    preguntandoles— mas el veredicto de los que deciden y no escriben. Los que
    no tocaron nada no se nombran; son la mayoria y llenarian el log.

    Se lee de arriba abajo como el turno: que se entendio, que se busco, que
    reclamo el reconciliador, que punto quedo sin contestar, que engranaje
    intervino y que invariante salto antes de mandar. Si algo salio mal, esta
    en esta linea o no paso."""
    todas = marcas()
    ficha = {
        "engranajes": len(todas),
        "intervinieron": [m["nodo"] for m in todas if m["intervino"]],
        "detalle": [f"{m['nodo']}:{m['detalle']}" for m in todas
                    if m["intervino"] and m["detalle"]][:6],
    }
    ficha.update(_notas.get() or {})
    return ficha


# ── LOS ENGRANAJES QUE NO TRANSFORMAN TEXTO ────────────────────────────────
#
# EL AGUJERO QUE CIERRAN (FICHA 01). Hasta hoy el unico que llamaba a
# `registrar()` era `G.paso`, y `G.paso` envuelve transformaciones de TEXTO: de
# los 32 nodos declarados registraban 17, todos de la etapa `salida`. Las otras
# cinco etapas -entrada, decision, reposicion, redaccion, memoria- estaban
# declaradas con su contrato y NO se observaban. El instrumento era ciego justo
# en la etapa donde estaba el problema, y por eso la reposicion hubo que medirla
# a mano el 18-ago envolviendola desde un script.
#
# LA PREGUNTA QUE HAY QUE CONTESTAR PARA CADA UNO, y es la trampa conocida:
# `G.paso` decide "intervino" comparando el texto que entro contra el que salio.
# Un nodo que NO transforma texto no se puede medir asi, con lo cual hay que
# DECIR que significa que intervino, nodo por nodo. Se contesta en dos formas y
# ninguna le pregunta al nodo:
#
#   `paso_datos`  el nodo recibe un estado y devuelve el estado nuevo -las
#                 piezas de la cuenta del resolver-. Intervino si el estado
#                 CAMBIO, comparado serializado. Es la misma regla de `G.paso`
#                 un piso mas arriba.
#   `veredicto`   el nodo produce algo que no es su propia entrada -el estado
#                 inicial, los pedidos del decisor, el texto del redactor, el
#                 guardado-. Ahi el criterio se escribe en el sitio de la
#                 llamada, en una linea, y queda a la vista de quien audita.
#
# LAS TRES REGLAS QUE LOS HACEN SEGUROS:
#   1. NINGUNO CAMBIA COMPORTAMIENTO. `paso_datos` devuelve exactamente lo que
#      devuelve la funcion, y si la funcion levanta, RE-LEVANTA. No se traga la
#      excepcion como hace `G.paso`: alla tragarla cumple NO_ENMUDECE, aca
#      tragarla inventaria un camino que hoy no existe.
#   2. UN REGISTRO ROTO NO PUEDE TUMBAR UN TURNO. `registrar` ya no levanta, y
#      `_huella` tampoco: ante cualquier cosa rara cae a `repr`.
#   3. UNA MARCA POR NODO Y POR TURNO. Las llamadas van en el hilo principal de
#      `procesar_venta`, que corre una vez por turno y no tiene bucle alrededor.
#      Si un nodo marcara dos veces, el censo contaria de mas y TODOS los
#      porcentajes quedarian mal en silencio; se verifica mirando que `corrio`
#      no supere la cantidad de turnos en `peso_del_censo.py`.


def _huella(valor) -> str:
    """La forma estable de un estado, para poder compararlo antes y despues.

    `sort_keys` para que dos dicts iguales con las claves en otro orden den la
    misma huella, y `default=str` para que un objeto que no sea JSON no levante.
    Si ni asi se puede serializar, cae a `repr`: medir peor es aceptable, tumbar
    el turno por medir no lo es."""
    try:
        return json.dumps(valor, sort_keys=True, default=str, ensure_ascii=False)
    except Exception:  # noqa: BLE001 — un instrumento no rompe lo que mide
        try:
            return repr(valor)
        except Exception:  # noqa: BLE001
            return ""


def paso_datos(nodo_id: str, funcion, estado, *args, **kwargs):
    """Corre un engranaje que mueve DATOS y deja su veredicto.

    El estado entra por el primer parametro y sale como resultado, que es como
    estan escritas las piezas de la cuenta del resolver. Intervino si la huella
    cambio.

    NO cambia el comportamiento: devuelve lo mismo que la funcion, y si la
    funcion levanta, la excepcion sigue viaje despues de dejar la marca."""
    antes = _huella(estado)
    try:
        salida = funcion(estado, *args, **kwargs)
    except Exception as e:  # noqa: BLE001 — se marca y se re-levanta
        registrar(nodo_id, True, f"levanto:{type(e).__name__}")
        raise
    despues = _huella(salida)
    registrar(nodo_id, despues != antes,
              f"{len(antes)}->{len(despues)}" if despues != antes else "")
    return salida


def veredicto(nodo_id: str, intervino, detalle: str = "") -> None:
    """La marca de un engranaje cuyo 'intervino' NO se puede sacar comparando
    su entrada con su salida, porque no devuelve lo que recibio.

    Es `registrar` con otro nombre a proposito: el nombre dice que el criterio
    lo escribio una persona en el sitio de la llamada, y no lo midio el grafo.
    Los cinco que lo usan -el estado, el decisor, el redactor, el cierre y el
    guardado- tienen su criterio en una linea al lado, que es lo que se audita."""
    registrar(nodo_id, bool(intervino), detalle)


def paso(nodo_id: str, funcion, texto: str, *args, **kwargs) -> str:
    """Corre un engranaje de salida y deja su veredicto.

    Es el unico lugar donde se decide si un nodo "intervino", y lo decide
    comparando. Si el engranaje levanta, se devuelve el texto tal como entro y
    se marca: **ninguna guardia puede dejar mudo al bot**, que es el contrato
    NO_ENMUDECE aplicado en vivo y no solo en el barrido."""
    try:
        salida = funcion(texto, *args, **kwargs)
    except Exception as e:  # noqa: BLE001 — un control no puede tumbar el turno
        registrar(nodo_id, True, f"levanto:{type(e).__name__}")
        return texto
    if not (salida or "").strip() and (texto or "").strip():
        registrar(nodo_id, True, "enmudecio:se_descarto")
        return texto
    registrar(nodo_id, salida != texto,
              f"{len(texto or '')}->{len(salida or '')}" if salida != texto
              else "")
    return salida
