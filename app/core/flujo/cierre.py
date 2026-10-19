"""EL CIERRE — con pedido y nombre, se toma el pedido, se avisa al dueño y se da el cobro (19-oct-2026).

No lee el mensaje del cliente. Decide con la etapa del borrador, FICHA 71: el pedido es lo resuelto del borrador y el
nombre lo trajo el interprete en la casilla `cliente`. El bot pide el nombre y nada mas: el contacto es el numero del
canal.

  vacio o armando                 nada
  falta_nombre                    la redaccion ya pidio el nombre
  completo                        lead capturado, aviso al dueño, confirmacion y cobro
  cerrado, igual al ya cerrado    nada: no se cierra dos veces
  completo despues de cerrado     el pedido cambio: se actualiza el mismo lead, no se crea otro

Llama a `leads` por el modulo —`leads.crear_lead`, `leads.notificar_lead`—, asi el doble del banco lo reemplaza
siempre. De `leads` y `cierre` usa solo lo que guarda el lead, avisa y escribe la confirmacion; de `pago`, el cobro. Sus
lecturas del mensaje —si pide el link, si dice que no, si pregunta— no se usan: eran otra interpretacion.
"""
from app.core import cierre as C
from app.core import leads
from app.logger import get_logger

from . import borrador as B

log = get_logger(__name__)


async def cerrar(estado: dict, user_id: str, canal: str, tienda_id: str, presupuesto: str, trace_id: str,
                 resumen: bool = True) -> str:
    """El texto del cierre para sumar a la respuesta, o "" si no toca cerrar."""
    b = estado["borrador"]
    if B.etapa(b, [], estado["pedido"]) != "completo":
        return ""
    nombre = str(b["cliente"].get("nombre") or "").strip()
    medios = list(dict.fromkeys(str(r["medio"]) for r in B.pago_listo(b) if r.get("medio")))
    medio = " y ".join(medios)
    destinos = ", ".join(dict.fromkeys(a["destino"] for a in estado["pedido"] if a.get("destino")))
    lead = {"nombre": nombre, "telefono": user_id, "forma_pago": medio, "direccion": destinos, "orden": presupuesto}
    try:
        lead_id = b["cierre"].get("lead") or leads.crear_lead(
            user_id, canal, tienda_id, ultimo_mensaje="", frase_disparadora="pedido y nombre", nivel="fuerte",
            estado_inicial="capturado", orden=presupuesto)
        b["cierre"]["lead"] = lead_id or ""
        leads.actualizar_lead(lead_id, tienda_id, {"nombre": nombre, "telefono": user_id, "forma_pago": medio,
                                             "direccion": destinos, "orden": presupuesto})
        await leads.notificar_lead(tienda_id=tienda_id, user_id=user_id, canal=canal, estado="capturado", nombre=nombre,
                             telefono=user_id, direccion=destinos, forma_pago=medio, orden=presupuesto,
                             ultimo_mensaje="")
    except Exception as e:  # noqa: BLE001 — sin lead guardado el cliente igual recibe la confirmacion
        log.warning("flujo_cierre_lead_error", trace_id=trace_id, error=str(e)[:160])
    # La cuenta no se repite si el cliente la acaba de leer en este mismo mensaje.
    # Sin medio dicho, la confirmacion igual nombra el pago: "coordinar y el envio a Rosario" quedaba cojo.
    texto = C.mensaje_confirmacion({**lead, "forma_pago": medio or "el medio que elijas"}, presupuesto if resumen else "")
    if leads.modo_cierre(tienda_id) == "venta":
        from app.core.pago import instruccion_cobro
        # UN COBRO POR MEDIO: con 70/30, el CBU por la parte de transferencia y el link por la de Mercado Pago.
        for m in medios or [""]:
            try:
                cobro = await instruccion_cobro(presupuesto, {**lead, "forma_pago": m}, tienda_id, trace_id)
                texto += f"\n{cobro}" if cobro else ""
            except Exception as e:  # noqa: BLE001
                log.warning("flujo_cobro_error", trace_id=trace_id, error=str(e)[:160])
    b["cierre"]["huella"] = B.huella(estado["pedido"])
    log.info("flujo_cierre", trace_id=trace_id, articulos=len(estado["pedido"]), medio=medio)
    return texto
