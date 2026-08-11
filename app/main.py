"""
FastAPI app principal — v4 multi-tenant + observabilidad.

Endpoints:
- GET  /                    → health check
- GET  /health              → health detallado
- GET  /admin/health/{tienda_id}  → health por tienda (multi-tenant)
- POST /webhook/telegram    → recibe mensajes de Telegram (tienda default)
- POST /webhook/whatsapp    → recibe mensajes de WhatsApp Cloud API (Meta)
- GET  /webhook/whatsapp    → verificación inicial Meta
"""
import os
import asyncio
import secrets
import time as _time
from fastapi import FastAPI, Request, BackgroundTasks, UploadFile, File, Query
from fastapi.responses import PlainTextResponse, JSONResponse

from app.logger import setup_logging, get_logger
import structlog
from app.config import get_settings
from app.core.orchestrator import process_message
from app.connectors.telegram import get_telegram_connector
from app.connectors.whatsapp import (
    get_whatsapp_connector_for_tienda,
    parse_whatsapp_payload,
)
from app.storage.firestore_client import (
    get_tienda_by_phone_id,
    already_processed,
)

setup_logging()
log = get_logger(__name__)
settings = get_settings()

# Procesar el mensaje DENTRO del request del webhook, no en segundo plano.
# Cloud Run estrangula la CPU apenas el request devolvio su respuesta; si el
# trabajo pesado corre en background (despues del 200), lo hace con la CPU
# estrangulada y se arrastra. Procesando dentro del request, la CPU sigue
# asignada y el flujo corre a velocidad plena, como en local. El webhook tarda
# un poco mas en devolver el 200, pero la idempotencia (already_processed)
# cubre cualquier reintento de Telegram/Meta. Default false: comportamiento
# actual (background). Poner PROCESAR_EN_REQUEST=true para activar.
PROCESAR_EN_REQUEST = os.getenv("PROCESAR_EN_REQUEST", "false").lower() == "true"

# ───────────────────────── Sentry (opcional) ─────────────────────────
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=0.1,
            environment=os.getenv("ENVIRONMENT", "production"),
            send_default_pii=False,
        )
        log.info("sentry_initialized")
    except ImportError:
        log.warning("sentry_dsn_set_but_sdk_not_installed")
    except Exception as e:
        log.warning("sentry_init_failed", error=str(e)[:100])

# ─────────────────────────── App ───────────────────────────
app = FastAPI(title="Agente Multi-Canal", version="4.0.0")


@app.on_event("startup")
async def _declarar_config_efectiva():
    """QUE CONFIGURACION CORRE DE VERDAD, escrito en el log al arrancar.

    Las envs del servicio en Cloud Run no se pueden leer desde afuera sin
    permiso de administrador, asi que hasta hoy nadie podia confirmar en que
    modo de cierre corre el bot vivo ni con que modelo, salvo entrando a la
    consola. Los logs SI se leen. Con esta linea, cada revision deja escrito
    con que arranco, y el banco imprime lo mismo en su banner: si las dos no
    coinciden, el banco esta probando otro sistema. No expone secretos, solo
    dice si estan puestos."""
    try:
        from app.core.leads import modo_cierre
        log.info("config_efectiva",
                 tienda_id=settings.TIENDA_ID,
                 modo_cierre=modo_cierre(settings.TIENDA_ID),
                 solver_model=settings.GEMINI_MODEL,
                 interprete=settings.INTERPRETER_PROVIDER,
                 gemini_key=bool(settings.GEMINI_API_KEY),
                 procesar_en_request=PROCESAR_EN_REQUEST,
                 fuente=_inventario_fuente())
    except Exception as e:
        log.warning("config_efectiva_error", error=str(e)[:150])


@app.on_event("startup")
async def _precalentar_cache():
    """
    Precarga catálogo y FAQ de la tienda default al arrancar la instancia, así
    la PRIMERA consulta real no paga la lectura a Firestore (3-4s) dentro del
    camino del mensaje. El guardián y la evidencia leen esos caches en cada
    turno; sin precalentar, el primer mensaje de una instancia nueva los carga
    en frío. No bloqueante: si Firestore falla, el server arranca igual. Detrás
    de flag PRECALENTAR_CACHE (default true). Poner false para desactivar.
    """
    if os.getenv("PRECALENTAR_CACHE", "true").lower() != "true":
        log.info("precalentar_cache_desactivado")
        return
    try:
        from app.storage.firestore_client import get_all_products, get_all_faq
        tid = settings.TIENDA_ID
        prods = get_all_products(tienda_id=tid)
        faqs = get_all_faq(tienda_id=tid)
        log.info("cache_precalentado", tienda_id=tid,
                 productos=len(prods), faq=len(faqs))
    except Exception as e:
        log.warning("precalentar_cache_failed", error=str(e)[:150])


def _prosa(clave: str, respaldo: str) -> str:
    """Un texto fijo al cliente, de la FUENTE. Mismo criterio que `_sobrecarga`:
    el literal que va al lado es la red por si el archivo faltara, y el candado
    de `tests/test_prosa_en_la_fuente.py` exige que sea identico al de la
    fuente para que no se despeguen."""
    from app.core.guia_venta_prosa import mensaje
    return mensaje(clave, respaldo)


def _sobrecarga() -> str:
    """Lo que se le dice al cliente cuando el turno se cayo por un blip del LLM.
    El texto vive en la fuente, como toda la prosa desde el 3-ago; el literal es
    la red si el archivo faltara, porque este es justo el camino de los fallos."""
    from app.core.guia_venta_prosa import mensaje
    return mensaje("sobrecarga",
                   "Perdón, estoy con mucha demanda en este momento. "
                   "Probá de nuevo en un ratito y te respondo. 🙏")


@app.get("/")
async def root():
    return {"status": "ok", "service": "agente-multicanal", "version": "4.0.0"}


@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {
        "status": "healthy",
        "version": "4.0.0",
        "telegram_configured": bool(settings.TELEGRAM_TOKEN),
        "deepseek_configured": bool(settings.DEEPSEEK_API_KEY),
        "groq_configured": bool(settings.GROQ_API_KEY),
        # LA VERDAD, no el flag. Hasta el 30-jul esto declaraba
        # "llm_provider: openai" y el modelo de Groq, mientras el turno entero
        # corria en Gemini: el health del sistema mintiendo sobre en que corre.
        # El solver, las guardias y la memoria entran por `_cliente_gemini`; el
        # interprete por INTERPRETER_PROVIDER. Se reportan los DOS, porque son
        # las dos piezas que pueden cambiar de proveedor.
        "solver_provider": "gemini",
        "solver_model": settings.GEMINI_MODEL,
        "interpreter_provider": settings.INTERPRETER_PROVIDER,
        "sentry_enabled": bool(SENTRY_DSN),
        "default_tienda": settings.TIENDA_ID,
        # QUE MODO DE CIERRE CORRE DE VERDAD. La env del servicio no se puede
        # leer desde afuera y la config de tienda la pisa, asi que hasta hoy
        # nadie sabia si el bot vivo capta lead (A) o cobra (B). El banco
        # imprime el suyo en cada corrida: si los dos no dicen lo mismo, el
        # banco esta probando otro cierre que el que atiende a los clientes.
        "modo_cierre": _modo_cierre_efectivo(),
        # QUE SABE CONTESTAR EL SISTEMA, contado por fuente. Mismo criterio que
        # arriba: el health dice la verdad de lo que hay cargado. Si una fuente
        # deja de cargar se ve el cero aca, en vez de descubrirlo semanas
        # despues por una respuesta vacia -que es exactamente lo que paso con
        # los 23 temas de FAQ que el interprete no podia nombrar-.
        "fuente": _inventario_fuente(),
    }


def _modo_cierre_efectivo() -> str:
    """El modo de cierre que corre, tolerante: el health nunca se cae por esto."""
    try:
        from app.core.leads import modo_cierre
        return modo_cierre(settings.TIENDA_ID)
    except Exception as e:
        return f"error: {str(e)[:60]}"


def _inventario_fuente() -> dict:
    """El inventario del indice, tolerante: el health nunca se cae por esto."""
    try:
        from app.core.indice import inventario
        return inventario(settings.TIENDA_ID)
    except Exception as e:
        return {"error": str(e)[:120]}


def _rechazo_admin(request: Request):
    """LA PUERTA DE ADMIN, una sola. Devuelve la respuesta de rechazo, o None
    si el pedido pasa.

    Hasta el 4-ago-2026 los cuatro endpoints de admin leian ADMIN_TOKEN del
    entorno CON UN VALOR POR DEFECTO: un token fuerte escrito en el repo,
    sirviendo de contraseña real en produccion si la env no estaba puesta. Dos
    de esos endpoints ESCRIBEN -upload-catalog y upload-faq-, o sea que con esa
    palabra, que estaba en el codigo, se pisaba el catalogo de 880 productos y
    la FAQ entera. `tests/test_admin_auth.py` no deja que vuelva.

    Ahora si `ADMIN_TOKEN` no esta configurado la puerta queda CERRADA, no
    abierta con una clave conocida: se contesta 503 y no se atiende. Un admin
    que no anda se nota y se arregla; uno que atiende con la contraseña del
    repo no se nota nunca.

    Ojo al deployar: si `agente-bot` no tiene `ADMIN_TOKEN` cableado desde el
    secreto `admin-token`, estos cuatro endpoints pasan a contestar 503.
    """
    esperado = os.getenv("ADMIN_TOKEN", "")
    if not esperado:
        log.error("admin_sin_token_configurado", ruta=str(request.url.path))
        return JSONResponse(
            {"error": "admin deshabilitado: falta ADMIN_TOKEN"},
            status_code=503)
    recibido = request.headers.get("X-Admin-Token", "")
    # compare_digest: la comparacion con != se corta en el primer byte
    # distinto y filtra el token por tiempo de respuesta.
    if not secrets.compare_digest(recibido, esperado):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return None


@app.get("/admin/health/{tienda_id}")
async def health_tienda(tienda_id: str, request: Request):
    """Health por tienda. Verifica config + datos cargados."""
    if (rechazo := _rechazo_admin(request)) is not None:
        return rechazo

    from app.storage.firestore_client import get_all_products, get_all_faq
    try:
        productos = get_all_products(tienda_id=tienda_id)
        faq = get_all_faq(tienda_id=tienda_id)
        return {
            "tienda_id": tienda_id,
            "productos": len(productos),
            "faq": len(faq),
            "ok": len(productos) > 0,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)[:200]}, status_code=500)


@app.post("/admin/diag-latencia")
async def diag_latencia(request: Request):
    """
    Boton de diagnostico: mide llamadas PELADAS al modelo desde adentro de Cloud
    Run para aislar de donde sale la demora de un turno. No toca el flujo del
    bot. Requiere X-Admin-Token.

    Mide la forma REAL del camino vivo, que es tool calling con las siete
    herramientas. Antes media el solver viejo -tools,
    tool_choice required, system prompt grande- y encima con el cliente de
    `agent`, que sigue el flag LLM_PROVIDER: con LLM_PROVIDER=openai y la clave
    vencida, este diagnostico devolvia 401 mientras el bot andaba bien. Un
    diagnostico que miente es peor que no tenerlo.

    Comparar los ms entre pruebas:
      1 vs 2 = costo de mandar las herramientas
      2 vs 3 = costo del prompt grande
      3 vs 4 = costo del historial acumulado
    """
    if (rechazo := _rechazo_admin(request)) is not None:
        return rechazo

    from app.core.hub_venta import _cliente
    from app.core import herramientas as _H

    modelo = settings.GEMINI_MODEL
    out = {"camino": "herramientas (hub_venta)", "modelo": modelo}
    try:
        client = _cliente()
    except Exception as e:
        return JSONResponse({"error": f"cliente: {str(e)[:200]}"},
                            status_code=500)

    # Las herramientas REALES del turno: es lo que viaja en la llamada uno.
    try:
        tools = _H.esquemas(settings.TIENDA_ID)
    except Exception:
        tools = None

    prompt_grande = ("Sos un vendedor argentino. " + ("Regla de venta. " * 400))
    # Historial simulado pesado, como una charla de diez turnos.
    hist_sim = []
    for i in range(5):
        hist_sim.append({"role": "user",
                         "content": f"Consulta {i} sobre productos y precios"})
        hist_sim.append({"role": "assistant", "content": (
            "Te muestro opciones: Mouse Genius DX-110 $8.500, Teclado Genius "
            "KB-110X $12.000, Monitor Samsung 24 $165.000. ") * 3})

    def _llamar(messages, usar_schema, max_t):
        t0 = _time.perf_counter()
        kw = dict(model=modelo, messages=messages, max_tokens=max_t,
                  temperature=0, extra_body={"reasoning_effort": "none"})
        if usar_schema and tools:
            kw["tools"] = tools
            kw["tool_choice"] = "auto"
        r = client.chat.completions.create(**kw)
        ms = int((_time.perf_counter() - t0) * 1000)
        u = getattr(r, "usage", None)
        return {"ms": ms, "prompt_tokens": getattr(u, "prompt_tokens", None)}

    _ok = [{"role": "user", "content": "Responde solo: ok"}]
    _sys = [{"role": "system", "content": prompt_grande}]
    pruebas = {
        "1_minima": (_ok, False, 5),
        "2_con_herramientas": (_ok, True, 400),
        "3_prompt_grande": (_sys + _ok, True, 400),
        "4_historial_grande": (_sys + hist_sim + _ok, True, 400),
    }
    for nombre, (msgs, usar, max_t) in pruebas.items():
        try:
            out[nombre] = await asyncio.to_thread(_llamar, msgs, usar, max_t)
        except Exception as e:
            out[nombre] = {"error": str(e)[:150]}

    return out


async def _process_and_reply_telegram(chat_id: str, text: str):
    """Un turno por Telegram. Se BORRO por error en el barrido de codigo muerto
    del 29-jul (commit a0cd2f9) y el webhook quedo llamando a un nombre que ya no
    existia: cualquier mensaje por Telegram tiraba NameError y el cliente no
    recibia nada. No se noto porque el canal vivo es WhatsApp. Restaurado tal
    cual estaba."""
    try:
        connector = get_telegram_connector()

        if text.startswith("__AUDIO__:"):
            file_id = text.split(":", 1)[1]
            log.info("telegram_audio_received", chat_id=chat_id, file_id=file_id)
            audio_bytes = await connector.download_file(file_id)
            if not audio_bytes:
                await connector.send_message(chat_id, _prosa(
                    "audio_no_descargado",
                    "No pude descargar el audio, mandalo de nuevo por favor."))
                return
            from app.core.transcriber import transcribir_audio
            text = transcribir_audio(audio_bytes)
            if not text:
                await connector.send_message(chat_id, _prosa(
                    "audio_no_entendido",
                    "No pude entender el audio, podes escribirlo o mandarlo de nuevo?"))
                return
            log.info("telegram_audio_transcribed", chat_id=chat_id, chars=len(text))

        # Telegram solo soporta tienda default (no hay multi-tenant nativo)
        response = await process_message(chat_id, text, canal="telegram")
        from app.connectors.base import enviar_respuesta
        await enviar_respuesta(connector, chat_id, response)
    except Exception as e:
        log.error("telegram_processing_error", error=str(e), chat_id=chat_id)
        if SENTRY_DSN:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
        # Mismo criterio que WhatsApp: no dejar al cliente sin respuesta ante un
        # blip transitorio del LLM. Envio en su propio try.
        try:
            await get_telegram_connector().send_message(
                chat_id,
                _sobrecarga())
        except Exception:
            pass


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request, background: BackgroundTasks):
    payload = await request.json()
    update_id = payload.get("update_id")
    structlog.contextvars.clear_contextvars()
    if update_id:
        structlog.contextvars.bind_contextvars(turn_id=f"tg_{update_id}")
    log.info("telegram_webhook_received", update_id=update_id)

    # Idempotencia: si ya procesamos este update_id, ignorar
    if update_id and already_processed(f"tg_{update_id}"):
        log.info("telegram_duplicate_ignored", update_id=update_id)
        return {"ok": True, "duplicate": True}

    connector = get_telegram_connector()
    parsed = connector.parse_incoming(payload)

    if parsed:
        chat_id, text = parsed
        if PROCESAR_EN_REQUEST:
            # CPU asignada: procesamos antes de responder el 200.
            await _process_and_reply_telegram(chat_id, text)
        else:
            background.add_task(_process_and_reply_telegram, chat_id, text)

    return {"ok": True}


# ───────────────────────── WHATSAPP (Meta Cloud API multi-tenant) ─────────

async def _process_and_reply_whatsapp(tienda_id: str, user_id: str,
                                      text: str, whatsapp_token: str,
                                      phone_number_id: str):
    try:
        connector = get_whatsapp_connector_for_tienda(whatsapp_token, phone_number_id)

        if text.startswith("__AUDIO__:"):
            media_id = text.split(":", 1)[1]
            log.info("whatsapp_audio_received", user_id=user_id, media_id=media_id)
            audio_bytes = await connector.download_media(media_id)
            if not audio_bytes:
                await connector.send_message(user_id, _prosa(
                    "audio_no_descargado",
                    "No pude descargar el audio, mandalo de nuevo por favor."))
                return
            from app.core.transcriber import transcribir_audio
            text = transcribir_audio(audio_bytes)
            if not text:
                await connector.send_message(user_id, _prosa(
                    "audio_no_entendido",
                    "No pude entender el audio, podes escribirlo o mandarlo de nuevo?"))
                return
            log.info("whatsapp_audio_transcribed", user_id=user_id, chars=len(text))

        response = await process_message(user_id, text, tienda_id=tienda_id, canal="whatsapp")
        # EN PARTES, no en un bloque: el cliente empieza a leer antes. La memoria
        # ya guardo el texto completo adentro de process_message, asi que partir
        # el ENVIO no cambia lo que la charla recuerda.
        from app.connectors.base import enviar_respuesta
        await enviar_respuesta(connector, user_id, response)
    except Exception as e:
        log.error("whatsapp_processing_error", error=str(e),
                  user_id=user_id, tienda_id=tienda_id)
        if SENTRY_DSN:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
        # No dejar al cliente en silencio ante un blip transitorio (ej. 503 del
        # proveedor de LLM por sobrecarga): mandamos un fallback amable. El envio
        # va en su propio try para que un fallo de envio no vuelva a romper.
        try:
            await get_whatsapp_connector_for_tienda(
                whatsapp_token, phone_number_id).send_message(
                user_id,
                _sobrecarga())
        except Exception:
            pass


@app.get("/webhook/whatsapp")
async def whatsapp_verify(request: Request):
    """
    Verificación inicial de Meta. Acepta CUALQUIER verify_token que coincida
    con alguna tienda registrada en tiendas_index, o con WHATSAPP_VERIFY_TOKEN
    global (compatibilidad).
    """
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode != "subscribe":
        return JSONResponse({"error": "verification failed"}, status_code=403)

    # Compat: token global
    global_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    if global_token and token == global_token:
        return PlainTextResponse(challenge or "")

    # Buscar entre las tiendas registradas
    from google.cloud import firestore as _fs
    db = _fs.Client(project=settings.GCP_PROJECT)
    docs = db.collection("tiendas_index").where("verify_token", "==", token).limit(1).stream()
    for _ in docs:
        return PlainTextResponse(challenge or "")

    return JSONResponse({"error": "verification failed"}, status_code=403)


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background: BackgroundTasks):
    """
    Recibe webhook de Meta Cloud API. Resuelve la tienda por phone_number_id
    presente en el payload. Cada cliente tiene su propia config.
    """
    payload = await request.json()
    log.info("whatsapp_webhook_received")

    # Extraer phone_number_id del payload (identifica al cliente B2B)
    parsed = parse_whatsapp_payload(payload)
    if not parsed:
        return {"ok": True}

    phone_number_id, user_id, text, message_id = parsed

    structlog.contextvars.clear_contextvars()
    if message_id:
        structlog.contextvars.bind_contextvars(turn_id=f"wa_{message_id}")

    # Idempotencia: Meta a veces reenvía el mismo mensaje
    if message_id and already_processed(f"wa_{message_id}"):
        log.info("whatsapp_duplicate_ignored", message_id=message_id)
        return {"ok": True, "duplicate": True}

    # Resolver tienda
    tienda_data = get_tienda_by_phone_id(phone_number_id)
    if not tienda_data:
        log.error("whatsapp_unknown_phone_id", phone_id=phone_number_id)
        return {"ok": True, "error": "tienda no registrada"}

    if PROCESAR_EN_REQUEST:
        await _process_and_reply_whatsapp(
            tienda_data["tienda_id"], user_id, text,
            tienda_data["whatsapp_token"], phone_number_id,
        )
    else:
        background.add_task(
            _process_and_reply_whatsapp,
            tienda_data["tienda_id"],
            user_id,
            text,
            tienda_data["whatsapp_token"],
            phone_number_id,
        )
    return {"ok": True}


# ADMIN: la carga inicial vivia aca y se BORRO el 3-ago-2026.
# `POST /admin/load-data` escribia 100 productos SINTETICOS de
# data/productos.json -ids MON-001- y una FAQ de 8 temas escrita a mano,
# sobre la tienda default, con el token 'cargar2026' hardcodeado como
# valor por defecto. Firestore estaba intacto -verificado el 3-ago: 880
# productos y 50 temas de FAQ, cero diferencias contra el repo- pero una
# sola llamada pisaba el catalogo real. La carga se hace por
# /admin/upload-catalog/{tienda_id} y /admin/upload-faq/{tienda_id}, que
# reciben la fuente del repo y piden la tienda explicita.


# ────────────────── ADMIN: subir catálogo y FAQ por tienda (HTTP, sin redeploy) ──────────────────

def _csv_to_dicts(content_bytes: bytes) -> tuple[list[dict], list[str]]:
    """
    Parsea CSV a lista de dicts. Devuelve (filas, errores).
    Detecta separador (coma o punto y coma) y limpia BOM/espacios.
    """
    import csv
    import io
    errores: list[str] = []
    try:
        text = content_bytes.decode("utf-8-sig")  # quita BOM si está
    except UnicodeDecodeError:
        try:
            text = content_bytes.decode("latin-1")
        except Exception as e:
            return [], [f"No se pudo decodificar el archivo: {e}"]

    # Detectar separador con Sniffer; si falla, asumir coma
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel  # coma

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    filas: list[dict] = []
    for i, row in enumerate(reader, start=2):  # fila 1 es header
        # Limpiar claves y valores
        clean = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items() if k}
        clean["_row_num"] = i
        filas.append(clean)
    return filas, errores


def _validate_producto_row(row: dict) -> tuple[dict | None, str | None]:
    """
    Valida una fila de productos. Devuelve (producto_normalizado, error).
    Minimo obligatorio: id, nombre, categoria, precio_ars, stock.

    El producto que se guarda lo arma `fuente_producto.normalizar_producto`:
    conserva TODAS las columnas del CSV (esta funcion se quedaba con 6 de 20 y
    dejaba a la ficha sin procedencia, garantia, contenido de la caja ni
    specs), depura la spec fantasma y estampa el mapa `specs`. Una sola puerta
    de ingesta, la misma que usa scripts/crear_cliente.py.
    """
    pid = (row.get("id") or "").strip()
    nombre = (row.get("nombre") or "").strip()
    categoria = (row.get("categoria") or "").strip().lower()
    precio_raw = (row.get("precio_ars") or row.get("precio") or "").strip()
    stock_raw = (row.get("stock") or "0").strip()
    row_num = row.get("_row_num", "?")

    if not pid:
        return None, f"fila {row_num}: falta 'id'"
    if not nombre:
        return None, f"fila {row_num} ({pid}): falta 'nombre'"
    if not categoria:
        return None, f"fila {row_num} ({pid}): falta 'categoria'"
    try:
        precio = int(float(precio_raw.replace(".", "").replace(",", ".")))
    except (ValueError, AttributeError):
        return None, f"fila {row_num} ({pid}): precio_ars inválido ('{precio_raw}')"
    try:
        stock = int(stock_raw)
    except ValueError:
        return None, f"fila {row_num} ({pid}): stock inválido ('{stock_raw}')"
    if precio < 0 or stock < 0:
        return None, f"fila {row_num} ({pid}): precio o stock negativo"

    from app.core.fuente_producto import normalizar_producto
    prod = normalizar_producto(row)
    prod.update({"id": pid, "nombre": nombre, "categoria": categoria,
                 "precio_ars": precio, "stock": stock})
    return prod, None


def _validate_faq_row(row: dict) -> tuple[tuple[str, dict] | None, str | None]:
    """
    Valida una fila de FAQ. Devuelve ((tema_id, data), error).
    Campos esperados: tema, keywords, respuesta.
    Keywords: string separado por comas.
    """
    tema = (row.get("tema") or "").strip().lower()
    keywords_raw = (row.get("keywords") or "").strip()
    respuesta = (row.get("respuesta") or "").strip()
    row_num = row.get("_row_num", "?")

    if not tema:
        return None, f"fila {row_num}: falta 'tema'"
    if not respuesta:
        return None, f"fila {row_num} ({tema}): falta 'respuesta'"

    keywords = [k.strip().lower() for k in keywords_raw.split(",") if k.strip()]
    return (tema, {"keywords": keywords, "respuesta": respuesta}), None


@app.post("/admin/upload-catalog/{tienda_id}")
async def upload_catalog(
    tienda_id: str,
    request: Request,
    file: UploadFile = File(...),
    upsert: bool = Query(False, description="Si True, mantiene productos viejos. Por defecto reemplaza."),
):
    """
    Sube un CSV de productos para una tienda.
    Por defecto REEMPLAZA todo el catálogo (borra los viejos antes).
    Con ?upsert=true mantiene los viejos y solo agrega/actualiza por id.

    Headers: X-Admin-Token
    Body: multipart/form-data, field 'file' = archivo .csv
    CSV columns: id,nombre,categoria,precio_ars,stock,descripcion
    """
    if (rechazo := _rechazo_admin(request)) is not None:
        return rechazo

    if not file.filename.lower().endswith(".csv"):
        return JSONResponse({"error": "El archivo debe ser .csv"}, status_code=400)

    try:
        content = await file.read()
        if len(content) > 5_000_000:  # 5 MB max
            return JSONResponse({"error": "archivo muy grande (máx 5MB)"}, status_code=400)

        filas, errores_parse = _csv_to_dicts(content)
        if errores_parse:
            return JSONResponse({"error": "; ".join(errores_parse)}, status_code=400)
        if not filas:
            return JSONResponse({"error": "CSV vacío o sin filas válidas"}, status_code=400)

        # Validar todas las filas primero (no escribimos nada hasta validar)
        productos_validos: list[dict] = []
        errores: list[str] = []
        ids_vistos: set[str] = set()
        for row in filas:
            prod, err = _validate_producto_row(row)
            if err:
                errores.append(err)
                continue
            if prod["id"] in ids_vistos:
                errores.append(f"id duplicado en el CSV: {prod['id']}")
                continue
            ids_vistos.add(prod["id"])
            productos_validos.append(prod)

        if not productos_validos:
            return JSONResponse({
                "error": "Ninguna fila válida",
                "errores": errores[:20],
            }, status_code=400)

        from app.storage.firestore_client import (
            upsert_product, delete_all_products, invalidate_cache,
        )

        modo = "upsert" if upsert else "replace"
        borrados = 0
        if not upsert:
            borrados = delete_all_products(tienda_id=tienda_id)

        cargados = 0
        errores_carga: list[str] = []
        for prod in productos_validos:
            try:
                upsert_product(prod["id"], prod, tienda_id=tienda_id)
                cargados += 1
            except Exception as e:
                errores_carga.append(f"{prod['id']}: {str(e)[:100]}")

        invalidate_cache(tienda_id)
        log.info("catalog_uploaded",
                 tienda_id=tienda_id, modo=modo,
                 cargados=cargados, borrados=borrados,
                 errores=len(errores) + len(errores_carga))

        # COHERENCIA DE LOS DATOS, en la puerta por donde entran. Lo de las 57
        # fichas que le mentian al cliente no fue un bug de codigo, fue el
        # catalogo, y no habia nada mirandolo. Se AVISA, no se bloquea: el
        # catalogo ya quedo cargado y la purga de ingesta neutraliza la prosa
        # contradicha, asi que rechazar la carga entera seria peor. Lo que no
        # puede pasar es que entre en silencio.
        incoherencias = []
        try:
            from app.core.coherencia_datos import revisar_todo
            for nombre, problemas in revisar_todo(tienda_id).items():
                if problemas:
                    incoherencias.append(f"{nombre}: {len(problemas)}")
                    log.warning("catalog_incoherente", tienda_id=tienda_id,
                                chequeo=nombre, cuantos=len(problemas),
                                ejemplos=[str(p)[:160] for p in problemas[:3]])
        except Exception as e:
            log.warning("catalog_coherencia_error", tienda_id=tienda_id,
                        error=str(e)[:150])

        return {
            "ok": True,
            "tienda_id": tienda_id,
            "modo": modo,
            "productos_borrados": borrados,
            "productos_cargados": cargados,
            "filas_invalidas": len(errores),
            "errores_validacion": errores[:20],
            "errores_carga": errores_carga[:20],
            "incoherencias": incoherencias,
        }

    except Exception as e:
        log.error("upload_catalog_error", tienda_id=tienda_id, error=str(e)[:200])
        return JSONResponse({"error": str(e)[:200]}, status_code=500)


@app.post("/admin/upload-faq/{tienda_id}")
async def upload_faq(
    tienda_id: str,
    request: Request,
    file: UploadFile = File(...),
    upsert: bool = Query(False, description="Si True, mantiene FAQ vieja. Por defecto reemplaza."),
):
    """
    Sube un CSV de FAQ para una tienda.
    Por defecto REEMPLAZA toda la FAQ. Con ?upsert=true solo agrega/actualiza.

    CSV columns: tema,keywords,respuesta
    keywords: palabras separadas por coma dentro de la misma celda
    """
    if (rechazo := _rechazo_admin(request)) is not None:
        return rechazo

    if not file.filename.lower().endswith(".csv"):
        return JSONResponse({"error": "El archivo debe ser .csv"}, status_code=400)

    try:
        content = await file.read()
        if len(content) > 1_000_000:  # 1 MB max para FAQ
            return JSONResponse({"error": "archivo muy grande (máx 1MB)"}, status_code=400)

        filas, errores_parse = _csv_to_dicts(content)
        if errores_parse:
            return JSONResponse({"error": "; ".join(errores_parse)}, status_code=400)
        if not filas:
            return JSONResponse({"error": "CSV vacío"}, status_code=400)

        faq_validas: list[tuple[str, dict]] = []
        errores: list[str] = []
        temas_vistos: set[str] = set()
        for row in filas:
            res, err = _validate_faq_row(row)
            if err:
                errores.append(err)
                continue
            tema, data = res
            if tema in temas_vistos:
                errores.append(f"tema duplicado en el CSV: {tema}")
                continue
            temas_vistos.add(tema)
            faq_validas.append((tema, data))

        if not faq_validas:
            return JSONResponse({
                "error": "Ninguna fila válida",
                "errores": errores[:20],
            }, status_code=400)

        from app.storage.firestore_client import upsert_faq, delete_all_faq

        modo = "upsert" if upsert else "replace"
        borradas = 0
        if not upsert:
            borradas = delete_all_faq(tienda_id=tienda_id)

        cargadas = 0
        errores_carga: list[str] = []
        for tema, data in faq_validas:
            try:
                upsert_faq(tema, data, tienda_id=tienda_id)
                cargadas += 1
            except Exception as e:
                errores_carga.append(f"{tema}: {str(e)[:100]}")

        log.info("faq_uploaded",
                 tienda_id=tienda_id, modo=modo,
                 cargadas=cargadas, borradas=borradas,
                 errores=len(errores) + len(errores_carga))

        return {
            "ok": True,
            "tienda_id": tienda_id,
            "modo": modo,
            "faq_borradas": borradas,
            "faq_cargadas": cargadas,
            "filas_invalidas": len(errores),
            "errores_validacion": errores[:20],
            "errores_carga": errores_carga[:20],
        }

    except Exception as e:
        log.error("upload_faq_error", tienda_id=tienda_id, error=str(e)[:200])
        return JSONResponse({"error": str(e)[:200]}, status_code=500)
