"""EL TURNO — la misma firma que `respuesta.procesar_turno`, por el flujo nuevo (19-oct-2026)."""
from app.config import get_settings
from app.core import guardas_salida as gs
from app.core.contexto_turno import set_current_tienda
from app.logger import get_logger
from app.storage.firestore_client import get_conversation, save_conversation

from . import estado as E
from . import interprete, redaccion
from .cierre import cerrar
from .ejecutor import ejecutar

log = get_logger(__name__)
settings = get_settings()


async def procesar_turno(user_id: str, raw_message: str, tienda_id: str, canal: str, trace_id: str) -> str:
    set_current_tienda(tienda_id)
    conv = get_conversation(user_id, tienda_id=tienda_id) or {}
    history = conv.get("history") or []
    estado = E.leer(conv)

    llena = interprete.interpretar(raw_message, history, E.texto(estado), trace_id)
    t = ejecutar(llena, estado, tienda_id, explicar=lambda q: interprete.explicar(q, trace_id))
    nuevo = any(h["tipo"] == "pedido" for h in t.hechos)
    pide_nombre = nuevo and not estado["cliente"].get("nombre")
    texto = redaccion.texto(t.hechos, t.preguntas, pide_nombre)
    log.info("flujo_turno", trace_id=trace_id, casillas=sorted(k for k, v in (llena or {}).items() if v),
             hechos=[h["tipo"] for h in t.hechos], preguntas=len(t.preguntas),
             herramientas=[x["herramienta"] for x in t.llamadas])

    cuentas = [h for h in t.hechos if h["tipo"] == "cuenta"]
    presupuesto = "\n".join(b["detalle"] for b in cuentas[-1]["bloques"])[:900] if cuentas else None
    if not t.preguntas:
        cierre = await cerrar(estado, user_id, canal, tienda_id, presupuesto or conv.get("ultimo_presupuesto") or "",
                              trace_id)
        texto = f"{texto}\n\n{cierre}".strip() if cierre else texto
    texto = texto or "¿En qué te puedo ayudar?"
    if not history:
        texto = gs.con_saludo_inicial(texto, gs.business_name(tienda_id))
    history = (history + [{"role": "user", "content": raw_message},
                          {"role": "assistant", "content": texto}])[-(settings.HISTORY_LIMIT * 2):]
    save_conversation(user_id, history, conv.get("summary") or "", tienda_id=tienda_id,
                      estado_conversacion="en_curso", estado_charla=estado, ultimo_presupuesto=presupuesto)
    return texto
