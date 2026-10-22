"""EL TURNO — el mensaje, la agenda del interprete, la agenda cumplida y la respuesta (20-oct-2026)."""
import copy

from app.config import get_settings
from app.core import guardas_salida as gs
from app.core.contexto_turno import set_current_tienda
from app.logger import get_logger
from app.storage import firestore_client as fc

from . import borrador as B
from . import estado as E
from . import interprete, redaccion
from .cierre import cerrar
from .agenda import preguntas
from .ejecutor import ejecutar

log = get_logger(__name__)
settings = get_settings()


async def procesar_turno(user_id: str, raw_message: str, tienda_id: str, canal: str, trace_id: str) -> str:
    set_current_tienda(tienda_id)
    conv = fc.get_conversation(user_id, tienda_id=tienda_id) or {}
    history = conv.get("history") or []
    estado = E.leer(conv)

    agenda = await interprete.interpretar(raw_message, history, estado, tienda_id, trace_id)
    if agenda is None:
        from app.core.guia_venta_prosa import mensaje
        return mensaje("sobrecarga", "Perdón, estoy con mucha demanda en este momento. "
                                     "Probá de nuevo en un ratito y te respondo. 🙏")
    explicado = {str(p.get("pregunta")): await interprete.explicar(str(p.get("pregunta")), trace_id)
                 for p in preguntas(agenda) if p.get("accion") == "explicar"}
    try:
        # LO DICHO QUE NO CIERRA SE ELIGE ENTRE LECTURAS, FICHA 72: una pasada sobre una copia deja las lecturas que
        # cierran; si hay, el modelo elige con las palabras del cliente y la pasada de verdad la anota supuesta.
        prueba = copy.deepcopy(estado)
        t = ejecutar(agenda, prueba, tienda_id, explicar=explicado.get)
        if t.lecturas:
            elegida = await interprete.elegir(raw_message, history, t.lecturas, trace_id)
            if elegida:
                prueba = copy.deepcopy(estado)
                t = ejecutar(agenda, prueba, tienda_id, explicar=explicado.get, elegida=elegida)
        estado = prueba
    except Exception as e:  # noqa: BLE001 — una agenda que el codigo no puede cumplir no deja al cliente sin nada
        log.error("flujo_ejecutor_error", trace_id=trace_id, error=f"{type(e).__name__}: {str(e)[:200]}",
                  acciones=[p.get("accion") for p in preguntas(agenda)])
        return "No te entendí bien. ¿Me lo decís de otra forma?"
    # EL NOMBRE SE PIDE UNA VEZ POR PEDIDO, en el primer turno sin otra pregunta: si no, la venta queda trabada. La
    # etapa sale del borrador; "para quien se pidio" es la huella del pedido, asi un pedido que cambia lo pide de nuevo.
    b = estado["borrador"]
    huella = B.huella(estado["pedido"])
    pide_nombre = B.etapa(b, [], estado["pedido"]) == "falta_nombre" and not t.preguntas \
        and b["cierre"].get("nombre_para") != huella
    if pide_nombre:
        b["cierre"]["nombre_para"] = huella
    if t.sueltas:
        # LO QUE EL CODIGO NO RESOLVIO LO CONTESTA EL VENDEDOR, con los datos del turno y nada mas: cada monto y cada
        # producto que nombre tiene que estar en ellos. Si no pasa el control, queda la repregunta del codigo.
        datos = "\n".join([redaccion.texto(t.hechos, [], False)]
                          + [f"En el pedido: {a['cantidad']}x {a['nombre']} a {a.get('destino') or 'sin destino'}"
                             for a in estado["pedido"]]
                          + [f"Mostrado: {m['nombre']} {m['precio']}" for m in estado["mostrados"][-10:]])
        for s in t.sueltas:
            dicho = await interprete.vender(s["cita"], datos, tienda_id, trace_id)
            if dicho and s["pregunta"] in t.preguntas:
                t.preguntas[t.preguntas.index(s["pregunta"])] = dicho
    texto = redaccion.texto(t.hechos, t.preguntas, pide_nombre)
    log.info("flujo_turno", trace_id=trace_id, estados=[t.estados.get(p.get("n")) for p in preguntas(agenda)],
             hechos=[h["tipo"] for h in t.hechos], preguntas=len(t.preguntas),
             herramientas=[x["herramienta"] for x in t.llamadas], normal=t.normal)

    cuentas = [h for h in t.hechos if h["tipo"] == "cuenta"]
    presupuesto = None
    if cuentas:
        # CON VARIOS DESTINOS LO QUE SE COBRA ES EL TOTAL GENERAL: va en el presupuesto que lee el cierre.
        presupuesto = "\n".join(b["detalle"] for b in cuentas[-1]["bloques"])
        if cuentas[-1].get("general"):
            presupuesto += "\n" + cuentas[-1]["general"]["detalle"]
        presupuesto = presupuesto[-1500:]
    if not t.preguntas:
        # LA CUENTA NO SE REPITE si va en este mensaje o si el bot ya la mando igual en la charla: el que da el nombre
        # la leyo, aunque en el medio haya preguntado las cuotas. Repetirla entera era el cierre del 20-oct.
        previo = presupuesto or conv.get("ultimo_presupuesto") or ""
        leida = bool(previo) and any(previo in str(m.get("content") or "") for m in history
                                     if m.get("role") == "assistant")
        cierre = await cerrar(estado, user_id, canal, tienda_id, previo, trace_id, resumen=not cuentas and not leida)
        texto = f"{texto}\n\n{cierre}".strip() if cierre else texto
    ultimo = next((str(m.get("content") or "") for m in reversed(history) if m.get("role") == "assistant"), "")
    if "si_sin_efecto" in t.normal and texto.strip() == ultimo.strip():
        # UN "OK" A UNA CUENTA RECIEN MOSTRADA no la manda de nuevo: es conformidad, y repetir era el mismo mensaje.
        texto = "Perfecto, queda así."
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
