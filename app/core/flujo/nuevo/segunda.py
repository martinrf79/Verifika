"""LA SEGUNDA LLAMADA CHICA: RETOCA LA RESPUESTA DEL CODIGO Y MANDA LOS COMANDOS DEL PEDIDO (17-nov-2026).

Orden de Martin del 17-nov: una llamada chica, solo para retocar lo que arma el codigo con los nexos, con la opcion de
sumarle funciones. Recibe el texto del codigo, el ultimo mensaje, la charla, la libreta del pedido y lo que el cliente
ya vio. Devuelve en una herramienta el texto retocado y, si el cliente compra, cotiza, cambia, saca, dice el pago o da su
nombre, los mismos comandos que mandaba el agente: los aplica el codigo de produccion. Medida en el banco,
`banco_pruebas/flujo/segunda.py`: unos 850 tokens de entrada de media y dos segundos.
"""
import asyncio
import json

# UMBRALES de la memoria, 17-nov: lo visto de los ultimos tres turnos, hasta quince productos; la charla de la llamada,
# los ultimos tres turnos enteros, y de antes solo las lineas del cliente, `agente.charla`, hasta MEMORIA_TURNOS.
VISTOS_TURNOS, VISTOS_MAX, CHARLA_TURNOS = 3, 15, 3

CONSIGNA = """Sos vendedor de una tienda online de tecnologia de Argentina que atiende por WhatsApp. El sistema ya busco en
la tienda lo que pide el ultimo mensaje y armo una respuesta con los datos reales: TEXTO DEL SISTEMA. Tu trabajo:

1. texto: la respuesta al cliente, a partir del TEXTO DEL SISTEMA. Podes ordenarla, acortarla y conectarla con la
   charla, en español rioplatense con voseo, corta y llevando a la venta. No agregues ningun dato que no este en el
   TEXTO DEL SISTEMA, en la libreta o en lo que el cliente ya vio: ni precios, ni productos, ni reglas, ni envios. Si el
   texto del sistema esta vacio o no contesta, pregunta lo que falta. El sistema ya saluda: no digas "hola".
2. Si el cliente compra, cambia, saca o confirma algo, manda pedido con solo ese cambio, con sus palabras en cita, un
   renglon por destino; para cambiar o sacar un renglon que ya esta, su numero de la libreta, L-1. El pago y el tope
   como los dijo. Si pregunta cuanto sale algo con envio o en total sin comprarlo, manda cotizar. Si confirma el pedido,
   dio su nombre y dijo con que medio paga, manda cobrar. El sistema pega el presupuesto y el cobro: no escribas montos.
3. "el primero", "ese", "de esos" son de LO QUE EL CLIENTE YA VIO, en el orden en que se lo mostraron. Para reservar se
   pide solo el nombre."""


def herramienta():
    """La unica herramienta: el texto, y los comandos del agente con sus mismos parametros."""
    from app.core.flujo import agente as A
    par = {h["function"]["name"]: h["function"]["parameters"] for h in A.HERRAMIENTAS}
    return {"type": "function", "name": "responder", "strict": False,
            "description": "La respuesta al cliente y, si hace falta, el cambio del pedido, la cotizacion o el cobro.",
            "parameters": {"type": "object", "required": ["texto"], "properties": {
                "texto": {"type": "string"}, "pedido": par["pedido"], "cotizar": par["cotizar"], "cobrar": par["cobrar"]}}}


def vistos_texto(memoria, tid):
    from app.core.flujo import tabla as T
    out = []
    for i, v in enumerate(reversed(memoria.get("vistos") or [])):
        filas = [T.ficha(p, tid) for p in v.get("ids") or []]
        filas = [f"  {k}. {f['nombre']}, ${int(f['precio']):,}".replace(",", ".") for k, f in enumerate(filas, 1) if f]
        if filas:
            out.append(("Lo ultimo que le mostraste:" if i == 0 else "Antes:") + "\n" + "\n".join(filas))
    return "\n".join(out)


def entrada(mensaje, historial, memoria, codigo, tid):
    """El mensaje de usuario de la segunda llamada."""
    from app.core.flujo import agente as A
    dicho = list(memoria.get("dicho") or [])
    vistos = vistos_texto(memoria, tid)
    return (f"{A.charla(historial[-2 * CHARLA_TURNOS:], dicho)}\n\n{A.memoria_texto(memoria, tid)}\n\n"
            + (f"LO QUE EL CLIENTE YA VIO:\n{vistos}\n\n" if vistos else "")
            + f"TEXTO DEL SISTEMA:\n{codigo or '(vacio)'}\n\nULTIMO MENSAJE DEL CLIENTE: {mensaje}")


async def llamar(usuario):
    """(argumentos de la herramienta, tokens de entrada, tokens de salida): el modelo de `FLUJO_MODELO` por la API de
    respuestas de OpenAI, la unica que le acepta herramientas con razonamiento."""
    from openai import OpenAI
    from app.config import get_settings
    s = get_settings()
    cli = OpenAI(api_key=(s.OPENAI_API_KEY or "").split()[0], timeout=float(s.LLM_TIMEOUT_SECONDS), max_retries=1)
    r = await asyncio.to_thread(lambda: cli.responses.create(
        model=s.FLUJO_MODELO, reasoning={"effort": s.FLUJO_RAZONAMIENTO}, instructions=CONSIGNA,
        input=[{"role": "user", "content": usuario}], tools=[herramienta()], tool_choice="required"))
    call = next((x for x in r.output if x.type == "function_call"), None)
    try:
        a = json.loads(call.arguments) if call else {}
    except ValueError:
        a = {}
    return a, r.usage.input_tokens, r.usage.output_tokens
