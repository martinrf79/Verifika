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

# Las etapas del turno, en orden. Es la unica jerarquia del grafo.
ETAPAS = ("entrada", "decision", "reposicion", "redaccion", "salida", "memoria")


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


def _n(fn):
    """Envuelve una funcion del hub en la forma uniforme del grafo: recibe el
    texto y el contexto del turno, devuelve el texto."""
    return fn


# ── EL TURNO, NODO POR NODO, EN EL ORDEN EN QUE CORRE ───────────────────────
NODOS = (
    # ── entrada ──────────────────────────────────────────────────────────
    Nodo(id="estado", etapa="entrada",
         funcion="app.core.estado_venta:construir_estado",
         exige="la conversacion guardada de Firestore",
         garantiza="el estado del turno: carrito, productos vistos, "
                   "localidades, preferencias"),
    Nodo(id="memoria_texto", etapa="entrada",
         funcion="app.core.hub_venta:_memoria_texto",
         exige="el estado y el historial",
         garantiza="el bloque de memoria que ve el modelo, sin inventar nada "
                   "que no este en el estado"),

    # ── decision: que hace falta y que trajo ──────────────────────────────
    Nodo(id="decisor", etapa="decision",
         funcion="app.core.hub_venta:_pedir_herramientas",
         exige="el mensaje del cliente y la memoria",
         garantiza="una lista de herramientas con argumentos validados por el "
                   "molde, o texto directo si el turno no necesita ninguna"),
    Nodo(id="herramientas", etapa="decision",
         funcion="app.core.hub_venta:_ejecutar_en_paralelo",
         exige="pedidos con argumentos validos",
         garantiza="el resultado de cada herramienta, con su estado, sin que "
                   "una que falla tumbe a las otras"),
    Nodo(id="reconciliador", etapa="decision",
         funcion="app.core.pedido:reconciliar",
         exige="lo que el modelo declaro y lo que efectivamente pidio",
         garantiza="que falta y que hay que preguntar; nunca completa por su "
                   "cuenta"),

    # ── reposicion: lo que el modelo no aplico, lo aplica el codigo ───────
    Nodo(id="busqueda_repuesta", etapa="reposicion",
         funcion="app.core.hub_venta:_busqueda_de_lo_declarado",
         exige="un item declarado que ninguna herramienta busco",
         garantiza="la busqueda hecha por codigo, o nada; no inventa el "
                   "producto"),
    Nodo(id="condicion_repuesta", etapa="reposicion",
         funcion="app.core.hub_venta:_condicion_faltante_aplicada",
         exige="una condicion del cliente que el plan no aplico",
         garantiza="el filtro aplicado sobre lo que ya se trajo"),
    Nodo(id="cuenta_repuesta", etapa="reposicion",
         funcion="app.core.hub_venta:_cuenta_con_lo_declarado",
         exige="un pedido declarado sin cuenta",
         garantiza="la cuenta calculada por la calculadora sobre ids "
                   "certificados"),
    Nodo(id="reparto_repuesto", etapa="reposicion",
         funcion="app.core.hub_venta:_reparto_de_pago_declarado",
         exige="un reparto de pago declarado y no aplicado",
         garantiza="el split sellado por el codigo"),
    Nodo(id="supuesto_de_pago", etapa="reposicion",
         funcion="app.core.hub_venta:_supuesto_de_pago",
         exige="una cuenta con un supuesto de pago sin declarar",
         garantiza="el supuesto dicho en el mensaje, para que el cliente sepa "
                   "sobre que se calculo"),
    Nodo(id="bloques_a_uno", etapa="reposicion",
         funcion="app.core.hub_venta:_bloques_a_uno",
         exige="varias cuentas parciales del mismo turno",
         garantiza="UNA sola cuenta, con la aritmetica cerrando"),
    Nodo(id="indice_turno", etapa="decision",
         funcion="app.core.indice_turno:cobertura",
         exige="lo interpretado y el material que trajeron las herramientas",
         garantiza="que punto del pedido tiene con que contestarse y cual no"),

    # ── redaccion ────────────────────────────────────────────────────────
    Nodo(id="redactor", etapa="redaccion",
         funcion="app.core.hub_venta:_redactar",
         exige="el material de las herramientas y la obligacion del turno",
         garantiza="prosa del modelo, con las etiquetas de la atadura puestas"),

    # ── salida: de aca abajo, todo transforma el texto ───────────────────
    Nodo(id="atadura", etapa="salida",
         funcion="app.core.atadura_prosa:verificar",
         exige="prosa con etiquetas y las llamadas del turno",
         garantiza="prosa sin una sola etiqueta, con lo no respaldado podado",
         contratos=(NO_ENMUDECE, NO_LEVANTA, IDEMPOTENTE),
         aplicar=lambda t, c: __import__(
             "app.core.atadura_prosa", fromlist=["x"]).verificar(
                 t, c["llamadas"], c["trace_id"], tienda_id=c["tienda_id"])),
    Nodo(id="sin_json", etapa="salida",
         funcion="app.core.hub_venta:_sin_json_filtrado",
         exige="el texto del modelo",
         garantiza="sin JSON de herramientas filtrado al cliente",
         contratos=TODOS_LOS_CONTRATOS,
         aplicar=lambda t, c: _hub()._sin_json_filtrado(t, c["trace_id"])),
    Nodo(id="sin_markdown", etapa="salida",
         funcion="app.core.hub_venta:_sin_markdown",
         exige="el texto del modelo",
         garantiza="sin asteriscos de markdown, que WhatsApp no renderiza",
         contratos=TODOS_LOS_CONTRATOS,
         aplicar=lambda t, c: _hub()._sin_markdown(t)),
    Nodo(id="sin_plata_inventada", etapa="salida",
         funcion="app.core.hub_venta:_sin_plata_inventada",
         exige="el texto y las llamadas que respaldan cada cifra",
         garantiza="ningun importe sin respaldo en la cuenta o en la fuente",
         contratos=TODOS_LOS_CONTRATOS,
         aplicar=lambda t, c: _hub()._sin_plata_inventada(
             t, c["llamadas"], c["bloque"], c["trace_id"],
             previo=c["previo"], vistos=c["vistos"])),
    Nodo(id="sin_cobro_inventado", etapa="salida",
         funcion="app.core.hub_venta:_sin_cobro_inventado",
         exige="el texto y la tienda",
         garantiza="ningun CBU, alias ni link que no salga de la config real",
         contratos=TODOS_LOS_CONTRATOS,
         aplicar=lambda t, c: _hub()._sin_cobro_inventado(
             t, c["tienda_id"], c["trace_id"])),
    Nodo(id="cuenta_no_retipeada", etapa="salida",
         funcion="app.core.hub_venta:_cuenta_no_retipeada",
         exige="el texto y si el turno calculo",
         garantiza="la cuenta del turno anterior repuesta cuando el modelo la "
                   "retipeo mal",
         contratos=(NO_ENMUDECE, NO_LEVANTA, IDEMPOTENTE),
         repone=("previo",),
         aplicar=lambda t, c: _hub()._cuenta_no_retipeada(
             t, hubo_calculo=bool(c["bloque"]), previo=c["previo"],
             trace_id=c["trace_id"])),
    Nodo(id="sin_negar_lo_traido", etapa="salida",
         funcion="app.core.hub_venta:_sin_negar_lo_traido",
         exige="el texto y lo que las herramientas trajeron",
         garantiza="el bot no niega lo que el catalogo si tiene",
         contratos=TODOS_LOS_CONTRATOS,
         aplicar=lambda t, c: _hub()._sin_negar_lo_traido(
             t, c["llamadas"], c["trace_id"])),
    Nodo(id="sin_afirmar_del_catalogo", etapa="salida",
         funcion="app.core.hub_venta:_sin_afirmar_sobre_el_catalogo",
         exige="el texto y lo que se busco",
         garantiza="ninguna afirmacion sobre el catalogo entero sin haberlo "
                   "recorrido",
         contratos=TODOS_LOS_CONTRATOS,
         aplicar=lambda t, c: _hub()._sin_afirmar_sobre_el_catalogo(
             t, c["llamadas"], c["trace_id"])),
    Nodo(id="sin_descuento_inventado", etapa="salida",
         funcion="app.core.hub_venta:_sin_descuento_inventado",
         exige="el texto",
         garantiza="ningun porcentaje de descuento que no este en la FAQ",
         contratos=TODOS_LOS_CONTRATOS,
         aplicar=lambda t, c: _hub()._sin_descuento_inventado(
             t, c["trace_id"])),
    Nodo(id="sin_narracion_interna", etapa="salida",
         funcion="app.core.hub_venta:_sin_narracion_interna",
         exige="el texto",
         garantiza="el cliente no lee la cocina del sistema",
         contratos=TODOS_LOS_CONTRATOS,
         aplicar=lambda t, c: _hub()._sin_narracion_interna(t, c["trace_id"])),
    Nodo(id="sin_anuncio_vacio", etapa="salida",
         funcion="app.core.hub_venta:_sin_anuncio_vacio",
         exige="el texto",
         garantiza="ningun anuncio de presupuesto sin presupuesto abajo",
         contratos=TODOS_LOS_CONTRATOS,
         aplicar=lambda t, c: _hub()._sin_anuncio_vacio(t, c["trace_id"])),
    Nodo(id="bloque_repuesto", etapa="salida",
         funcion="app.core.hub_venta:_bloque_entero_o_repuesto",
         exige="el texto y el bloque sellado del codigo",
         garantiza="la cuenta viaja ENTERA o se repone entera; nunca mutilada",
         contratos=(NO_ENMUDECE, NO_LEVANTA, IDEMPOTENTE, NO_INVENTA_PLATA),
         repone=("bloque",),
         aplicar=lambda t, c: _hub()._bloque_entero_o_repuesto(
             t, c["bloque"], c["trace_id"])),
    Nodo(id="hallazgo_repuesto", etapa="salida",
         funcion="app.core.hub_venta:_bloque_entero_o_repuesto",
         exige="el texto y el bloque del hallazgo, si el turno encontro algo "
               "parecido a lo que no hay",
         garantiza="el hallazgo viaja entero o se repone entero, y sin barrer "
                   "la cuenta que ya esta puesta",
         contratos=(NO_ENMUDECE, NO_LEVANTA, IDEMPOTENTE, NO_INVENTA_PLATA),
         repone=("hallazgo",),
         aplicar=lambda t, c: _hub()._bloque_entero_o_repuesto(
             t, _hub()._bloque_hallazgo(c["llamadas"], t), c["trace_id"],
             barrer_cuenta=False)),
    Nodo(id="cierre", etapa="salida",
         funcion="app.core.hub_venta:_cerrar",
         exige="la señal de cierre y el presupuesto",
         garantiza="los datos de cobro que salen de la config, o nada"),
    Nodo(id="honestidad_bot", etapa="salida",
         funcion="app.core.guardas_salida:asegurar_honestidad_bot",
         exige="el mensaje del cliente y la respuesta",
         garantiza="si preguntan si es un bot, se dice que si",
         contratos=(NO_ENMUDECE, NO_LEVANTA, IDEMPOTENTE, NO_INVENTA_PLATA),
         aplicar=lambda t, c: __import__(
             "app.core.guardas_salida", fromlist=["x"]
         ).asegurar_honestidad_bot(c["mensaje"], t, c["negocio"])),
    Nodo(id="saludo", etapa="salida",
         funcion="app.core.guardas_salida:sin_saludo_del_modelo",
         exige="la respuesta y si es el primer mensaje de la charla",
         garantiza="el saludo se dice una vez y solo la primera",
         contratos=(NO_ENMUDECE, NO_LEVANTA, IDEMPOTENTE, NO_INVENTA_PLATA),
         aplicar=lambda t, c: __import__(
             "app.core.guardas_salida", fromlist=["x"]
         ).sin_saludo_del_modelo(t)),
    Nodo(id="punto_omitido", etapa="salida",
         funcion="app.core.hub_venta:_punto_omitido_repuesto",
         exige="el mensaje entero y los puntos que el cliente pidio",
         garantiza="ningun punto que el sistema sabe contestar se va sin "
                   "contestar; lo que repone es el bloque sellado del codigo",
         # NO declara NO_INVENTA_PLATA y no es un olvido: es el UNICO nodo que
         # SUMA, y lo que suma es la cuenta sellada de la calculadora, que trae
         # importes que el texto todavia no tenia. Esa es su razon de existir.
         contratos=(NO_ENMUDECE, NO_LEVANTA, IDEMPOTENTE),
         repone=("bloque",),
         aplicar=lambda t, c: _hub()._punto_omitido_repuesto(
             t, c.get("declarado") or {}, c["llamadas"], c.get("memoria") or [],
             c["tienda_id"], c["trace_id"])),
    Nodo(id="componedor", etapa="salida",
         funcion="app.core.mensaje:componer",
         exige="el mensaje entero y el anterior del bot",
         garantiza="sin repeticion, sin perder un dato: las seis reglas son "
                   "lossless",
         contratos=TODOS_LOS_CONTRATOS,
         aplicar=lambda t, c: __import__(
             "app.core.mensaje", fromlist=["x"]).componer(
                 t, anterior=c["anterior"], trace_id=c["trace_id"],
                 pregunta=c["mensaje"])),
    Nodo(id="aduana", etapa="salida",
         funcion="app.core.aduana:revisar_salida",
         exige="el mensaje compuesto, ya entero y todavia sin mandar",
         garantiza="los invariantes corridos: repara lo que puede probar sin "
                   "tocar un peso, y grita lo que no",
         contratos=TODOS_LOS_CONTRATOS,
         aplicar=lambda t, c: __import__(
             "app.core.aduana", fromlist=["x"]).revisar_salida(
                 t, anterior=c["anterior"], trace_id=c["trace_id"],
                 tienda_id=c["tienda_id"], vocabulario=c.get("vocabulario"))),

    # ── memoria ──────────────────────────────────────────────────────────
    Nodo(id="memoria", etapa="memoria",
         funcion="app.storage.firestore_client:save_conversation",
         exige="el turno cerrado",
         garantiza="el estado guardado para el turno siguiente; un error de "
                   "guardado no tumba la respuesta"),
)

POR_ID = {n.id: n for n in NODOS}


def _hub():
    """Import perezoso: `hub_venta` importa este modulo para registrar sus
    veredictos, asi que el grafo no puede importarlo arriba."""
    from app.core import hub_venta
    return hub_venta


def aristas() -> tuple:
    """El cableado como pares. El turno es una cadena: cada nodo recibe lo que
    dejo el anterior. Las rondas del decisor son el unico ciclo y esta
    declarado aparte, en `CICLOS`."""
    return tuple((NODOS[i].id, NODOS[i + 1].id) for i in range(len(NODOS) - 1))


CICLOS = (("reconciliador", "decisor"),)
"""El unico ciclo del turno: si el reconciliador encuentra un faltante, se
vuelve al decisor. Tope de dos rondas, en `_MAX_RONDAS`."""


def nodos_de(etapa: str) -> tuple:
    return tuple(n for n in NODOS if n.etapa == etapa)


def barribles() -> tuple:
    """Los nodos que el barrido puede correr solo, sin modelo y sin red: los
    que transforman texto y saben decir como se los llama."""
    return tuple(n for n in NODOS if n.aplicar and n.contratos)


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


def abrir_turno() -> None:
    """Arranca la hoja de veredictos del turno. La llama el hub una sola vez."""
    _marcas.set([])


def registrar(nodo_id: str, intervino: bool, detalle: str = "") -> None:
    """Deja la marca de un engranaje. Nunca levanta: un registro roto no puede
    tumbar un turno."""
    marcas = _marcas.get()
    if marcas is None:
        return
    marcas.append({"nodo": nodo_id, "intervino": bool(intervino),
                   "detalle": str(detalle or "")[:80]})


def marcas() -> list:
    return list(_marcas.get() or [])


def veredicto_del_turno() -> dict:
    """Lo que se loguea al cerrar: quien toco el mensaje, en orden. Los que no
    tocaron nada no se nombran; son la mayoria y llenarian el log."""
    todas = marcas()
    return {
        "engranajes": len(todas),
        "intervinieron": [m["nodo"] for m in todas if m["intervino"]],
        "detalle": [f"{m['nodo']}:{m['detalle']}" for m in todas
                    if m["intervino"] and m["detalle"]][:6],
    }


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
