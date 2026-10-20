"""CIERRE DE VENTA — el texto de la confirmacion del pedido tomado.

El cierre lo decide `flujo/cierre.py` con el estado de la charla: aca queda solo lo que se le escribe al cliente.
Las lecturas del mensaje que vivian aca —si dice que no, si pregunta, la forma de pago o la direccion por regex— se
borraron el 20-oct: eran otra interpretacion, y el unico que lee el mensaje es el interprete.
"""

# LO QUE SE LE PIDE AL CLIENTE PARA CERRAR.
CAMPOS_REQUERIDOS = ["nombre"]


def faltantes(lead: dict) -> list[str]:
    """Campos requeridos que el lead todavia no tiene."""
    return [c for c in CAMPOS_REQUERIDOS if not str(lead.get(c, "")).strip()]


def mensaje_confirmacion(lead: dict, presupuesto: str = "") -> str:
    from app.core.guia_venta_prosa import mensaje
    nombre = str(lead.get("nombre", "")).split(" ")[0] if lead.get("nombre") else ""
    partes = [mensaje("cierre_tomamos_pedido", "Listo{nombre}, tomamos tu pedido.",
                      nombre=(f" {nombre}" if nombre else ""))]
    # SIN TITULO PROPIO: el presupuesto de la calculadora ya abre con el suyo, y "Resumen:" encima de "Presupuesto:"
    # quedaba suelto, como le llego a Martin el 20-oct.
    if (presupuesto or "").strip():
        partes.append(presupuesto)
    direccion = str(lead.get("direccion", "")).strip()
    pago = str(lead.get("forma_pago", "")).strip()
    cola = mensaje("cierre_equipo_contacta", "El equipo te contacta para coordinar")
    if pago:
        cola += mensaje("cierre_coordina_pago", " el pago por {pago}", pago=pago)
    if direccion:
        cola += mensaje("cierre_coordina_envio", " y el envio a {direccion}",
                        direccion=direccion)
    cola += mensaje("cierre_gracias", ". Gracias por tu compra.")
    partes.append(cola)
    return "\n".join(partes)
