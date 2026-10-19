"""EL CIERRE — con pedido y nombre, se toma el pedido, se avisa al dueño y se da el cobro (19-oct-2026).

No lee el mensaje del cliente. Decide con el estado de la charla: el pedido lo escribio el ejecutor y el nombre lo
trajo el interprete en la casilla `cliente`. El bot pide el nombre y nada mas: el contacto es el numero del canal.

  sin pedido                      nada
  pedido sin nombre               la redaccion ya pidio el nombre
  pedido y nombre, sin cerrar     lead capturado, aviso al dueño, confirmacion y cobro
  pedido igual al ya cerrado      nada: no se cierra dos veces

De `leads` y `cierre` usa solo lo que guarda el lead, avisa y escribe la confirmacion; de `pago`, el cobro. Sus
lecturas del mensaje —si pide el link, si dice que no, si pregunta— no se usan: eran otra interpretacion.
"""
from app.core import cierre as C
from app.core.leads import crear_lead, actualizar_lead, modo_cierre
from app.core.notificador import notificar_lead
from app.logger import get_logger

log = get_logger(__name__)


def _huella(pedido: list) -> str:
    """El pedido en un texto: Firestore no guarda listas dentro de listas."""
    return "|".join(sorted(f"{a['id']}:{a['cantidad']}:{a.get('destino') or ''}" for a in pedido))


async def cerrar(estado: dict, user_id: str, canal: str, tienda_id: str, presupuesto: str, trace_id: str) -> str:
    """El texto del cierre para sumar a la respuesta, o "" si no toca cerrar."""
    nombre = str(estado["cliente"].get("nombre") or "").strip()
    if not estado["pedido"] or not nombre or estado.get("cerrado") == _huella(estado["pedido"]):
        return ""
    medio = (estado["reparto"][0]["medio"] if estado["reparto"] else "")
    lead = {"nombre": nombre, "telefono": user_id, "forma_pago": medio, "orden": presupuesto}
    try:
        lead_id = crear_lead(user_id, canal, tienda_id, ultimo_mensaje="", frase_disparadora="pedido y nombre",
                             nivel="fuerte", estado_inicial="capturado", orden=presupuesto)
        actualizar_lead(lead_id, tienda_id, {"nombre": nombre, "telefono": user_id, "forma_pago": medio})
        await notificar_lead(tienda_id=tienda_id, user_id=user_id, canal=canal, estado="capturado", nombre=nombre,
                             telefono=user_id, direccion="", forma_pago=medio, orden=presupuesto, ultimo_mensaje="")
    except Exception as e:  # noqa: BLE001 — sin lead guardado el cliente igual recibe la confirmacion
        log.warning("flujo_cierre_lead_error", trace_id=trace_id, error=str(e)[:160])
    texto = C.mensaje_confirmacion(lead, presupuesto)
    if modo_cierre(tienda_id) == "venta":
        try:
            from app.core.pago import instruccion_cobro
            cobro = await instruccion_cobro(presupuesto, lead, tienda_id, trace_id)
            texto += f"\n{cobro}" if cobro else ""
        except Exception as e:  # noqa: BLE001
            log.warning("flujo_cobro_error", trace_id=trace_id, error=str(e)[:160])
    estado["cerrado"] = _huella(estado["pedido"])
    log.info("flujo_cierre", trace_id=trace_id, articulos=len(estado["pedido"]), medio=medio)
    return texto
