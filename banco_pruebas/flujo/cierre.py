"""EL CIERRE — el pedido pasa a `leads`, que pide el nombre, avisa al dueño y da el cobro (19-oct-2026).

`leads` no se toco. Lo que cambia es de donde salen los datos del cliente: del interprete, en la casilla `cliente`
de la ficha 10, y de los patrones de `cierre.extraer_determinista` —telefono, direccion—. Ya no hay una segunda
llamada al modelo para leer el nombre: era otra interpretacion del mismo mensaje.
"""
from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()


async def cerrar(conv: dict, user_id: str, canal: str, tienda_id: str, mensaje: str, texto: str, trace_id: str,
                 compra: bool, cliente: dict, presupuesto: str) -> tuple:
    """(texto, datos del cliente, si quedo hecha la pregunta de cierre)."""
    from app.core.cierre import extraer_determinista
    from app.core.leads import _RE_PIDE_COBRO, procesar_mensaje_para_lead
    datos_turno = {**extraer_determinista(mensaje), **{k: v for k, v in (cliente or {}).items()
                                                      if k == "nombre" and v}}
    datos = {**(conv.get("datos_cliente_parciales") or {}), **datos_turno}
    pide_cobro = bool(_RE_PIDE_COBRO.search(mensaje or ""))
    senal = ({"intencion": "decision_compra", "confianza": 1.0} if compra or pide_cobro
             else {"intencion": "pregunta_especifica", "confianza": 0.9})
    meta = {}
    try:
        _, meta = await procesar_mensaje_para_lead(
            user_id, canal, tienda_id, mensaje, texto, trace_id, interpretacion=senal,
            presupuesto=presupuesto or conv.get("ultimo_presupuesto") or "", datos_turno=datos_turno,
            datos_previos=datos, presupuesto_nuevo=bool(presupuesto),
            pregunta_cierre_hecha=bool(conv.get("pregunta_cierre_hecha")))
    except Exception as e:  # noqa: BLE001 — el cierre nunca tumba el turno
        log.warning("flujo_cierre_error", trace_id=trace_id, error=str(e)[:160])
    rd = (meta.get("respuesta_directa") or "").strip()
    if rd and rd[:80] not in texto:
        texto = f"{texto}\n\n{rd}" if texto.strip() else rd
    return texto, datos, meta.get("accion") in ("pregunta_cierre", "pregunta_pendiente_cierre")
