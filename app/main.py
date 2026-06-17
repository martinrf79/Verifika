"""
FastAPI app principal — v4 multi-tenant + observabilidad.

Endpoints:
- GET  /                    → health check
- GET  /health              → health detallado
- GET  /admin/health/{tienda_id}  → health por tienda (multi-tenant)
- POST /webhook/telegram    → recibe mensajes de Telegram (tienda default)
- POST /webhook/whatsapp    → recibe mensajes de WhatsApp Cloud API (Meta)
- GET  /webhook/whatsapp    → verificación inicial Meta
- POST /admin/load-data     → carga inicial datos (tienda default)
"""
import os
import asyncio
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
        "llm_provider": settings.LLM_PROVIDER,
        "model": (settings.DEEPSEEK_MODEL if settings.LLM_PROVIDER == "deepseek"
                  else settings.GROQ_MODEL),
        "sentry_enabled": bool(SENTRY_DSN),
        "default_tienda": settings.TIENDA_ID,
    }


@app.get("/admin/health/{tienda_id}")
async def health_tienda(tienda_id: str, request: Request):
    """Health por tienda. Verifica config + datos cargados."""
    token = request.headers.get("X-Admin-Token", "")
    if token != os.getenv("ADMIN_TOKEN", "cargar2026"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

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
    Botón de diagnóstico: mide una llamada PELADA al modelo desde adentro de
    Cloud Run, sin tools y sin historial, para aislar la causa de la demora.
    - minima_1 / minima_2: llamada mínima. Es el tiempo puro de red + arranque
      del proveedor desde Cloud Run. Si da 1-2s, la red está bien y la demora
      es la cantidad de llamadas/capas del flujo. Si da ~7s, es el entorno/red.
    - con_tools: misma llamada pero mandando el esquema de herramientas, para
      ver si las tools por sí solas agregan tiempo.
    No toca el flujo del bot. Requiere X-Admin-Token.
    """
    token = request.headers.get("X-Admin-Token", "")
    if token != os.getenv("ADMIN_TOKEN", "cargar2026"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    from app.core.agent import _get_client, _get_schema
    from app.core.tools_context import set_current_tienda

    if settings.LLM_PROVIDER == "groq":
        modelo = settings.GROQ_MODEL
    elif settings.LLM_PROVIDER == "gemini":
        modelo = settings.GEMINI_MODEL
    elif settings.LLM_PROVIDER == "openai":
        modelo = settings.OPENAI_MODEL
    elif settings.LLM_PROVIDER == "anthropic":
        modelo = settings.ANTHROPIC_MODEL
    elif settings.LLM_PROVIDER == "nemotron":
        modelo = settings.NEMOTRON_MODEL
    else:
        modelo = settings.DEEPSEEK_MODEL

    out = {"provider": settings.LLM_PROVIDER, "modelo": modelo}

    try:
        client = _get_client()
    except Exception as e:
        return JSONResponse({"error": f"cliente: {str(e)[:200]}"},
                            status_code=500)

    from app.core.agent import _build_system_prompt
    try:
        set_current_tienda(settings.TIENDA_ID)
        sys_prompt = _build_system_prompt(settings.TIENDA_ID)
    except Exception:
        sys_prompt = "Sos un vendedor."
    try:
        schema = _get_schema()
    except Exception:
        schema = None

    # Historial simulado pesado (10 mensajes con listados) para medir el efecto
    # del contexto acumulado, como en una charla real.
    hist_sim = []
    for i in range(5):
        hist_sim.append({"role": "user",
                         "content": f"Consulta {i} sobre productos y precios"})
        hist_sim.append({"role": "assistant", "content": (
            "Te muestro opciones: Mouse Genius DX-110 $8.500, Teclado Genius "
            "KB-110X $12.000, Monitor Samsung 24 $165.000, Auriculares Sony "
            "$685.000. Hacemos envios a todo el pais por Andreani y OCA. ") * 3})

    def _llamar(messages, tools=None, tc="auto", max_t=5):
        t0 = _time.perf_counter()
        kw = dict(model=modelo, messages=messages, max_tokens=max_t,
                  temperature=0)
        if tools:
            kw["tools"] = tools
            kw["tool_choice"] = tc
        r = client.chat.completions.create(**kw)
        ms = int((_time.perf_counter() - t0) * 1000)
        u = getattr(r, "usage", None)
        return {"ms": ms, "prompt_tokens": getattr(u, "prompt_tokens", None)}

    _ok = [{"role": "user", "content": "Responde solo: ok"}]
    _sys = [{"role": "system", "content": sys_prompt}]
    # Cada prueba aisla un factor; comparar los ms entre ellas:
    #  1 vs 2 = costo de mandar el esquema de herramientas
    #  2 vs 3 = costo de forzar el uso de herramienta (tool_choice required)
    #  2 vs 4 = costo del system prompt grande + max_tokens alto
    #  4 vs 5 = costo del historial acumulado
    pruebas = {
        "1_minima": (_ok, None, "auto", 5),
        "2_tools_auto": (_ok, schema, "auto", 5),
        "3_tools_required": (_ok, schema, "required", 5),
        "4_system_grande": (_sys + _ok, schema, "auto", 800),
        "5_historial_grande": (_sys + hist_sim + _ok, schema, "auto", 800),
    }
    for nombre, (msgs, tools, tc, max_t) in pruebas.items():
        try:
            out[nombre] = await asyncio.to_thread(_llamar, msgs, tools, tc, max_t)
        except Exception as e:
            out[nombre] = {"error": str(e)[:150]}

    return out


# ───────────────────────── TELEGRAM ─────────────────────────

async def _process_and_reply_telegram(chat_id: str, text: str):
    try:
        connector = get_telegram_connector()

        if text.startswith("__AUDIO__:"):
            file_id = text.split(":", 1)[1]
            log.info("telegram_audio_received", chat_id=chat_id, file_id=file_id)
            audio_bytes = await connector.download_file(file_id)
            if not audio_bytes:
                await connector.send_message(chat_id, "No pude descargar el audio, mandalo de nuevo por favor.")
                return
            from app.core.transcriber import transcribir_audio
            text = transcribir_audio(audio_bytes)
            if not text:
                await connector.send_message(chat_id, "No pude entender el audio, podes escribirlo o mandarlo de nuevo?")
                return
            log.info("telegram_audio_transcribed", chat_id=chat_id, chars=len(text))

        # Telegram solo soporta tienda default (no hay multi-tenant nativo)
        response = await process_message(chat_id, text, canal="telegram")
        await connector.send_message(chat_id, response)
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
                "Perdón, estoy con mucha demanda en este momento. "
                "Probá de nuevo en un ratito y te respondo. 🙏")
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
                await connector.send_message(user_id, "No pude descargar el audio, mandalo de nuevo por favor.")
                return
            from app.core.transcriber import transcribir_audio
            text = transcribir_audio(audio_bytes)
            if not text:
                await connector.send_message(user_id, "No pude entender el audio, podes escribirlo o mandarlo de nuevo?")
                return
            log.info("whatsapp_audio_transcribed", user_id=user_id, chars=len(text))

        response = await process_message(user_id, text, tienda_id=tienda_id, canal="whatsapp")
        await connector.send_message(user_id, response)
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
                "Perdón, estoy con mucha demanda en este momento. "
                "Probá de nuevo en un ratito y te respondo. 🙏")
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


# ───────────────────── ADMIN: cargar datos a tienda default ─────────────────

@app.post("/admin/load-data")
async def admin_load_data(request: Request):
    """Carga inicial de productos y FAQ para la tienda DEFAULT."""
    token = request.headers.get("X-Admin-Token", "")
    if token != os.getenv("ADMIN_TOKEN", "cargar2026"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        import json
        from app.storage.firestore_client import (
            upsert_product, upsert_faq, set_config,
        )

        productos_path = "/app/data/productos.json"
        if not os.path.exists(productos_path):
            productos_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data", "productos.json"
            )

        with open(productos_path, "r", encoding="utf-8") as f:
            productos = json.load(f)

        productos_ok = 0
        for p in productos:
            try:
                upsert_product(p["id"], p)
                productos_ok += 1
            except Exception as e:
                log.error("product_load_error", id=p.get("id"), error=str(e)[:100])

        FAQ = {
            "envios": {
                "keywords": ["envío", "envio", "envían", "envian", "mandan", "interior",
                             "ciudad", "domicilio", "entrega", "llega", "correo"],
                "respuesta": (
                    "Hacemos envíos a todo el país por correo (Andreani / OCA). "
                    "Capital y GBA: 24-48hs hábiles. Interior: 3-7 días hábiles."
                ),
            },
            "pago": {
                "keywords": ["pago", "pagar", "tarjeta", "efectivo", "transferencia",
                             "mercado pago", "mercadopago", "cuotas", "débito", "crédito"],
                "respuesta": (
                    "Aceptamos: transferencia bancaria, Mercado Pago (tarjetas crédito/débito), "
                    "y efectivo en local. Hasta 3 cuotas sin interés con tarjetas seleccionadas."
                ),
            },
            "garantia": {
                "keywords": ["garantía", "garantia", "rotura", "falla", "defecto", "se rompe"],
                "respuesta": "Todos nuestros productos tienen 6 meses de garantía oficial.",
            },
            "devolucion": {
                "keywords": ["devolución", "devolucion", "devolver", "cambio",
                             "arrepentido", "arrepentir"],
                "respuesta": (
                    "Tenés 10 días corridos desde la recepción para devolver el producto, "
                    "siempre que esté en empaque original sin uso."
                ),
            },
            "horarios": {
                "keywords": ["horario", "horarios", "abren", "atienden", "disponible",
                             "atención", "atencion"],
                "respuesta": "Atendemos de lunes a viernes de 9 a 19hs. Sábados de 9 a 13hs.",
            },
            "ubicacion": {
                "keywords": ["dirección", "direccion", "local", "dónde están", "donde estan",
                             "sucursal", "ubicación", "ubicacion", "retirar"],
                "respuesta": (
                    "Trabajamos online con envío a todo el país. "
                    "Para retirar coordinamos en CABA con cita."
                ),
            },
            "factura": {
                "keywords": ["factura", "comprobante", "iva", "responsable inscripto"],
                "respuesta": "Emitimos factura A o B según corresponda.",
            },
            "stock": {
                "keywords": ["disponibilidad general", "tenes stock", "tenés stock"],
                "respuesta": "Sí, tenemos stock. Consultá por modelo específico.",
            },
        }

        faq_ok = 0
        for tema, data in FAQ.items():
            try:
                upsert_faq(tema, data)
                faq_ok += 1
            except Exception as e:
                log.error("faq_load_error", tema=tema, error=str(e)[:100])

        try:
            set_config("nombre", "Tienda Tecno")
            set_config("contacto_humano", "Si necesitás hablar con un humano, escribinos")
        except Exception as e:
            log.error("config_load_error", error=str(e)[:100])

        return {
            "ok": True,
            "productos_cargados": productos_ok,
            "productos_total": len(productos),
            "faq_cargada": faq_ok,
        }

    except Exception as e:
        log.error("admin_load_data_error", error=str(e)[:200])
        return JSONResponse({"error": str(e)[:200]}, status_code=500)


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
    Campos esperados: id, nombre, categoria, precio_ars, stock, descripcion.
    """
    pid = (row.get("id") or "").strip()
    nombre = (row.get("nombre") or "").strip()
    categoria = (row.get("categoria") or "").strip().lower()
    precio_raw = (row.get("precio_ars") or row.get("precio") or "").strip()
    stock_raw = (row.get("stock") or "0").strip()
    descripcion = (row.get("descripcion") or "").strip()
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

    return {
        "id": pid,
        "nombre": nombre,
        "categoria": categoria,
        "precio_ars": precio,
        "stock": stock,
        "descripcion": descripcion,
    }, None


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
    token = request.headers.get("X-Admin-Token", "")
    if token != os.getenv("ADMIN_TOKEN", "cargar2026"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

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

        return {
            "ok": True,
            "tienda_id": tienda_id,
            "modo": modo,
            "productos_borrados": borrados,
            "productos_cargados": cargados,
            "filas_invalidas": len(errores),
            "errores_validacion": errores[:20],
            "errores_carga": errores_carga[:20],
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
    token = request.headers.get("X-Admin-Token", "")
    if token != os.getenv("ADMIN_TOKEN", "cargar2026"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

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
