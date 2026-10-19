"""EL TURNO — la misma firma que `respuesta.procesar_turno`, por el flujo nuevo (19-oct-2026)."""
from app.config import get_settings
from app.core import guardas_salida as gs
from app.core.contexto_turno import set_current_tienda
from app.logger import get_logger
from app.storage import firestore_client as fc

from . import estado as E
from . import interprete, redaccion
from .cierre import cerrar
from .ejecutor import ejecutar, normalizar

log = get_logger(__name__)
settings = get_settings()


async def procesar_turno(user_id: str, raw_message: str, tienda_id: str, canal: str, trace_id: str) -> str:
    set_current_tienda(tienda_id)
    conv = fc.get_conversation(user_id, tienda_id=tienda_id) or {}
    history = conv.get("history") or []
    estado = E.leer(conv)

    llena = await interprete.interpretar(raw_message, history, estado, tienda_id, trace_id)
    if llena is None:
        from app.core.guia_venta_prosa import mensaje
        return mensaje("sobrecarga", "Perdón, estoy con mucha demanda en este momento. "
                                     "Probá de nuevo en un ratito y te respondo. 🙏")
    llena = normalizar(llena)
    explicado = {str(q): await interprete.explicar(str(q), trace_id) for q in llena["explicar"]}
    try:
        t = ejecutar(llena, estado, tienda_id, explicar=explicado.get)
    except Exception as e:  # noqa: BLE001 — una traduccion que el codigo no puede cumplir no deja al cliente sin nada
        log.error("flujo_ejecutor_error", trace_id=trace_id, error=f"{type(e).__name__}: {str(e)[:200]}",
                  casillas=sorted(llena))
        return "No te entendí bien. ¿Me lo decís de otra forma?"
    if any(h["tipo"] == "pedido" for h in t.hechos):
        estado["nombre_pedido"] = False
    # EL NOMBRE SE PIDE UNA VEZ POR PEDIDO, en el primer turno sin otra pregunta: si no, la venta queda trabada.
    pide_nombre = bool(estado["pedido"]) and not estado["cliente"].get("nombre") and not t.preguntas \
        and not estado.get("nombre_pedido")
    if pide_nombre:
        estado["nombre_pedido"] = True
    texto = redaccion.texto(t.hechos, t.preguntas, pide_nombre)
    log.info("flujo_turno", trace_id=trace_id, casillas=sorted(k for k, v in (llena or {}).items() if v),
             hechos=[h["tipo"] for h in t.hechos], preguntas=len(t.preguntas),
             herramientas=[x["herramienta"] for x in t.llamadas])

    cuentas = [h for h in t.hechos if h["tipo"] == "cuenta"]
    presupuesto = None
    if cuentas:
        # CON VARIOS DESTINOS LO QUE SE COBRA ES EL TOTAL GENERAL: va en el presupuesto que lee el cierre.
        presupuesto = "\n".join(b["detalle"] for b in cuentas[-1]["bloques"])
        if cuentas[-1].get("general"):
            presupuesto += "\n" + cuentas[-1]["general"]["detalle"]
        presupuesto = presupuesto[-1500:]
    if not t.preguntas:
        cierre = await cerrar(estado, user_id, canal, tienda_id, presupuesto or conv.get("ultimo_presupuesto") or "",
                              trace_id, resumen=not cuentas)
        texto = f"{texto}\n\n{cierre}".strip() if cierre else texto
    texto = texto or "¿En qué te puedo ayudar?"
    if not history:
        texto = gs.con_saludo_inicial(texto, gs.business_name(tienda_id))
    history = (history + [{"role": "user", "content": raw_message},
                          {"role": "assistant", "content": texto}])[-(settings.HISTORY_LIMIT * 2):]
    try:
        fc.save_conversation(user_id, history, conv.get("summary") or "", tienda_id=tienda_id,
                          estado_conversacion="en_curso", estado_charla=estado, ultimo_presupuesto=presupuesto)
    except Exception as e:  # noqa: BLE001 — el cliente recibe su respuesta aunque no se haya guardado
        log.error("flujo_guardar_error", trace_id=trace_id, error=str(e)[:200])
    return texto
