"""
NOTIFICADOR al dueno.

Cuando el validator bloquea una respuesta (o cuando una conversacion deriva
por cualquier motivo), avisa al dueno por Telegram con tres datos:
- que pregunto el cliente
- que iba a contestar el bot
- chat id del cliente para que el dueno le responda directo

Usa el mismo token de Telegram del bot Verifika.
El chat id del dueno se lee de la variable de entorno OWNER_TELEGRAM_CHAT_ID.
Si no esta seteada, el notificador no hace nada (modo silencioso).

Se llama en background, no bloquea la respuesta al cliente.
"""
import os
import asyncio
import httpx

# structlog, como el resto de los modulos. El logger estandar de Python NO
# acepta kwargs (log.info("x", tienda_id=...) tira TypeError) y ese crash,
# dentro del try del envio, enmascaraba el resultado real de la notificacion
# (bug visto en prod 11-jun: "Logger._log() got an unexpected keyword 'error'").
from app.logger import get_logger

log = get_logger(__name__)

# Chat id del dueno. Si no esta seteado, el notificador queda inactivo.
OWNER_CHAT_ID = os.getenv("OWNER_TELEGRAM_CHAT_ID", "").strip()

# Token de Telegram del bot. Reutilizamos el mismo.
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()


async def notificar_derivacion(
    tienda_id: str,
    user_id: str,
    pregunta: str,
    respuesta_iba_a_dar: str,
    categoria: str = "",
    palabra: str = "",
    canal: str = "telegram",
) -> bool:
    """
    Envia alerta al dueno por Telegram cuando el bot deriva.
    No bloquea, falla silencioso si algo sale mal.
    """
    if not OWNER_CHAT_ID:
        # Modo silencioso: si no esta configurado el chat id del dueno, no avisa.
        return False

    if not TELEGRAM_TOKEN:
        log.warning("notificador_sin_token")
        return False

    # Armar mensaje
    enlace_directo = ""
    if canal == "whatsapp":
        enlace_directo = f"\nResponderle directo: https://wa.me/{user_id}"
    elif canal == "telegram":
        enlace_directo = f"\nChat id del cliente: {user_id}"

    motivo_linea = ""
    if categoria:
        motivo_linea = f"\nMotivo: {categoria}"
        if palabra:
            motivo_linea += f" (palabra: {palabra})"

    texto = (
        "ALERTA DE DERIVACION"
        f"\nTienda: {tienda_id}"
        f"\nCanal: {canal}"
        f"\nCliente: {user_id}"
        f"\n\nPregunto: {pregunta[:300]}"
        f"\n\nIba a responder: {respuesta_iba_a_dar[:400]}"
        f"{motivo_linea}"
        f"{enlace_directo}"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": OWNER_CHAT_ID,
        "text": texto,
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json=payload)
            if r.status_code == 200:
                log.info("notificador_ok", extra={"tienda_id": tienda_id})
                return True
            log.warning(
                "notificador_http_error",
                extra={
                    "status": r.status_code,
                    "body": r.text[:200],
                },
            )
            return False
    except Exception as e:
        log.warning("notificador_error", extra={"error": str(e)[:200]})
        return False


def disparar_notificacion_background(
    tienda_id: str,
    user_id: str,
    pregunta: str,
    respuesta_iba_a_dar: str,
    categoria: str = "",
    palabra: str = "",
    canal: str = "telegram",
):
    """
    Dispara la notificacion en background sin bloquear el flujo principal.
    Si no hay loop asyncio corriendo, crea uno temporal.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(notificar_derivacion(
                tienda_id, user_id, pregunta, respuesta_iba_a_dar,
                categoria, palabra, canal,
            ))
        else:
            loop.run_until_complete(notificar_derivacion(
                tienda_id, user_id, pregunta, respuesta_iba_a_dar,
                categoria, palabra, canal,
            ))
    except RuntimeError:
        # No hay loop, lo creamos
        try:
            asyncio.run(notificar_derivacion(
                tienda_id, user_id, pregunta, respuesta_iba_a_dar,
                categoria, palabra, canal,
            ))
        except Exception as e:
            log.warning("notificador_dispatch_error", extra={"error": str(e)[:200]})
    except Exception as e:
        log.warning("notificador_dispatch_error", extra={"error": str(e)[:200]})


async def notificar_lead(
    tienda_id: str,
    user_id: str,
    canal: str,
    estado: str,
    nombre: str = "",
    telefono: str = "",
    ultimo_mensaje: str = "",
    direccion: str = "",
    forma_pago: str = "",
    orden: str = "",
) -> bool:
    """
    Avisa al dueno por Telegram cuando hay un lead nuevo o capturado.
    No bloquea, falla silencioso si algo sale mal.

    estado puede ser intencion_detectada o capturado.
    """
    if not OWNER_CHAT_ID:
        return False
    if not TELEGRAM_TOKEN:
        log.warning("notificador_lead_sin_token")
        return False

    if estado == "lead_fuerte_captado":
        titulo = "Lead FUERTE captado, cliente confirmo"
        partes = ["El cliente dijo que si al cierre. El bot NO le pide datos, "
                  "sigue conversando. Contactalo vos para coordinar."]
        if nombre:
            partes.append(f"Nombre: {nombre}")
        if telefono:
            partes.append(f"Contacto: {telefono}")
        if direccion:
            partes.append(f"Direccion: {direccion}")
        if forma_pago:
            partes.append(f"Pago: {forma_pago}")
        if orden:
            partes.append(f"\nPedido:\n{orden}")
        detalle = "\n".join(partes)
    elif estado == "intencion_fuerte":
        titulo = "Lead FUERTE, cliente quiere comprar"
        detalle = "El bot le pidio nombre y telefono. Prepara la coordinacion."
    elif estado == "intencion_tibia":
        titulo = "Lead tibio, cliente evaluando"
        detalle = "El cliente esta haciendo consultas previas. El bot sigue conversando normal."
    elif estado == "intencion_detectada":
        titulo = "Nuevo lead detectado"
        detalle = "El cliente mostro intencion de compra. El bot le pidio nombre y telefono."
    elif estado == "capturado":
        titulo = "VENTA CERRADA, lead completo"
        partes = []
        if nombre:
            partes.append(f"Nombre: {nombre}")
        if telefono:
            partes.append(f"Telefono: {telefono}")
        if direccion:
            partes.append(f"Direccion: {direccion}")
        if forma_pago:
            partes.append(f"Pago: {forma_pago}")
        if orden:
            partes.append(f"\nPedido:\n{orden}")
        detalle = "\n".join(partes) if partes else "Datos parciales recibidos."
    else:
        titulo = f"Lead estado {estado}"
        detalle = ""

    enlace_directo = ""
    if canal == "whatsapp":
        enlace_directo = f"\nResponderle directo: https://wa.me/{user_id}"
    elif canal == "telegram":
        enlace_directo = f"\nChat id del cliente: {user_id}"

    msg = (
        f"{titulo}\n"
        f"Tienda: {tienda_id}\n"
        f"Canal: {canal}\n"
        f"{detalle}\n"
        f"Ultimo mensaje: {ultimo_mensaje[:200]}"
        f"{enlace_directo}"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json={"chat_id": OWNER_CHAT_ID, "text": msg})
        if r.status_code == 200:
            log.info("notificacion_lead_enviada", tienda_id=tienda_id,
                     estado=estado, canal=canal)
            return True
        log.warning("notificacion_lead_falla",
                    status=r.status_code, body=r.text[:200])
        return False
    except Exception as e:
        log.warning("notificacion_lead_excepcion", error=str(e)[:200])
        return False
