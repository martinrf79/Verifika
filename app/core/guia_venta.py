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
    "B11": ("el cliente POSTERGA. No presiones ni ofrezcas rebajas para forzar. "
            "Dejá la puerta abierta y la disponibilidad clara, con un cierre cálido "
            "que no le pida nada."),
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
