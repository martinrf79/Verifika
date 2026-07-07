"""
GUÍA DE VENTA — convierte la decisión del router (ruteo_venta) en la instrucción
de la MOVIDA que se le inyecta al solver, mismo carril que guia_mas_barato y
guia_memoria: el código decide la movida, el solver redacta los nexos.

La guía es INSTRUCCIONAL, no trae números: los datos duros (precio, total,
descuento de transferencia) siguen saliendo sellados de las tools, del estado
(bloque_para_solver) y del acople de curadas de FAQ, y los ancla el verificador.
Acá solo va el brief de la movida, el registro y el gancho, tal como los
borradores de BORRADORES_CURADAS_VENTA.md, en versión compacta para el solver.

Devuelve "" cuando el router dice 'normal': el turno sigue por el camino de
siempre, sin tocar nada.
"""
from app.core.ruteo_venta import rutear_venta

# Brief de cada movida en versión solver: qué mover, con el escape y el recordatorio
# de que el dato duro no se inventa. Registro universal, model-agnóstico.
_BRIEFS: dict[str, str] = {
    "B1": ("el cliente DELEGA la elección (indeciso). Elegí UN producto con "
           "criterio real, uso o relación precio-calidad, de los ya mostrados o "
           "vía las tools, proponelo con su precio real y cerrá invitando a "
           "confirmar. No vuelvas a listar todo."),
    "B2": ("el cliente CAMBIÓ de producto. Reanclá al nuevo, confirmá corto sin "
           "repetir lo descartado, y retomá donde estaban, envío, pago o cantidad."),
    "B3": ("el cliente afirma y NIEGA en la misma frase (le sirve el modelo pero "
           "no esa variante). No marques compra cerrada. Ofrecé la variante que SÍ "
           "hay según el catálogo y preguntá si le sirve."),
    "B4": ("el cliente pide DESCUENTO. El único descuento real es el de "
           "transferencia (sale de la FAQ). No inventes otra rebaja ni un "
           "porcentaje. Ofrecé armar el total pagando por transferencia."),
    "B5": ("OBJECIÓN de precio. No bajes el precio ni prometas igualar a otro. "
           "Reencuadrá en valor real, garantía y envío de la ficha, y ofrecé el "
           "descuento por transferencia. Cerrá invitando a avanzar."),
    "B6": ("consulta de CONFIANZA. Respaldá con hechos reales, productos "
           "originales, garantía oficial, medios de pago seguros. No inventes "
           "sellos ni certificaciones. Cerrá invitando a arrancar con la compra."),
    "B9": ("el cliente AFIRMA un precio o condición que no coincide con la "
           "fuente. NO confirmes su número ni lo repitas: el precio vigente sale "
           "SOLO de las tools. Dalo con naturalidad como el actual, sin acusar "
           "ni discutir, y seguí la venta normal."),
    "B11": ("el cliente POSTERGA. No presiones ni ofrezcas rebajas para forzar. "
            "Dejá la puerta abierta y la disponibilidad clara, con un cierre cálido "
            "que no le pida nada."),
    "B13": ("el cliente tiene URGENCIA. El plazo sale SOLO de la FAQ (query_faq "
            "plazo de envío; si hay servicio urgente, ofrecelo). PROHIBIDO "
            "prometer un día puntual de entrega. Si el plazo oficial no llega a "
            "su fecha, decilo con la verdad. Cerrá empujando a confirmar hoy "
            "para que el despacho salga cuanto antes."),
    "B14": ("pedido MAYORISTA o por cantidad grande. No inventes un precio ni un "
            "descuento por volumen: la política sale de query_faq (mayoristas) y "
            "el total de calculate_total. Tratalo como cliente grande; si el "
            "volumen excede lo que podés cerrar, ofrecé el contacto del equipo. "
            "Pedí la cantidad exacta si falta."),
    "B15": ("el cliente tiene un PRESUPUESTO TOPE. Buscá con las tools lo que "
            "entra en esa plata CON stock y proponé UNO con su precio real. Si "
            "nada entra, decilo derecho y mostrá lo más cercano sin forzar. "
            "Podés mencionar que por transferencia baja el precio (dato de la FAQ)."),
    "B16": ("la compra es un REGALO para otra persona. Si falta el dato clave "
            "(edad, uso o gustos), preguntá UNA sola cosa antes de recomendar. "
            "Con el dato, proponé UN producto real con el motivo en una frase. "
            "Solo afirmá envoltorio o presentación si la FAQ lo respalda."),
    "B17": ("el cliente está ENOJADO o se queja. NO vendas nada este turno. "
            "Disculpa corta y genuina, sin justificar ni discutir. Preguntá qué "
            "pasó puntualmente o resolvé lo que ya está claro; si excede lo que "
            "podés resolver, avisá que lo pasás con una persona del equipo, sin "
            "inventar plazos de respuesta."),
    "B18": ("el cliente pide un HUMANO o pregunta si sos un bot. Decí la VERDAD: "
            "sos el asistente automático de la tienda, sin hacerte pasar por "
            "persona. Ofrecé las dos vías: seguir resolviendo ahora (precios, "
            "stock, envíos al instante) o derivarlo a una persona del equipo. "
            "Que elija él."),
    "B19": ("el cliente CANCELA o se arrepiente. Aceptalo al primer mensaje, sin "
            "insistir, sin contraofertar ni pedir explicaciones. Si había pedido "
            "confirmado, la política sale de query_faq (cancelación). Cierre "
            "amable que deja la puerta abierta sin pedirle nada."),
    "B20": ("pregunta por un MEDIO DE PAGO que no ofrecemos. Decí que no, corto "
            "y sin vueltas, y reconducí a los medios reales de la FAQ "
            "(query_faq formas de pago). No aceptes ni insinúes que se va a "
            "sumar. Destacá el que más le conviene y ofrecé armar el total."),
    "B21": ("pregunta por ENVÍO AL EXTERIOR. La cobertura sale SOLO de query_faq "
            "(envío exterior); no inventes courier, costo ni plazo internacional. "
            "Si no hay envío afuera, decilo derecho y ofrecé la alternativa real "
            "si tiene sentido (que alguien lo reciba en Argentina)."),
    "B22": ("pide FOTOS o VIDEO. NO prometas mandar archivos: por este canal no "
            "se envían. Compensá con las specs y descripción REALES de la ficha "
            "(get_product_details) y, si la FAQ trae web o redes, apuntá ahí. "
            "Cerrá reenganchando con la venta."),
    "B23": ("RECLAMO POSVENTA (producto fallado, roto o garantía). Empatía "
            "primero, sin culpar al cliente ni al correo. La política y los "
            "plazos salen SOLO de query_faq (defectuoso, garantía, cambios). No "
            "prometas una resolución puntual: avisá que una persona del equipo "
            "toma el caso. Pedí el dato que falte del producto o pedido."),
}

# Qué aclarar cuando la acción es 'preguntar' (escape), por categoría.
_PREGUNTAS: dict[str, str] = {
    "B7": ("el pedido matchea MÁS DE UN producto. NO elijas por el cliente: nombrá "
           "las variantes reales y preguntá cuál quiere. No des un precio de cierre "
           "todavía."),
    "B1": ("no hay criterio para recomendar. Preguntá UNA cosa, para qué uso lo "
           "quiere o qué presupuesto maneja, antes de proponer."),
    "B2": ("no queda claro a qué producto cambia. Preguntá cuál exactamente antes "
           "de reanclar."),
}


def guia_venta(mensaje: str, interp: dict | None, estado: dict | None) -> str:
    """Instrucción de la movida para el solver, o "" si el turno va por el camino
    normal. No decide ningún número; solo la movida comercial y su escape."""
    d = rutear_venta(mensaje, interp, estado)
    accion = d.get("accion")
    cat = d.get("categoria")

    if accion == "movida" and cat in _BRIEFS:
        return (f"\n\n[VENTA ({cat}): {_BRIEFS[cat]} Los precios y datos de la "
                "tienda salen SOLO de las tools y el estado, no los inventes.]")

    if accion == "preguntar":
        texto = _PREGUNTAS.get(cat) or (
            "no hay certeza para afirmar. Hacé UNA pregunta corta para aclarar "
            "antes de afirmar o cerrar.")
        return f"\n\n[VENTA ({cat}): {texto}]"

    return ""
