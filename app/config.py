"""Configuración del bot v5 — Firestore + DeepSeek + tools + Verifika."""
import os
from functools import lru_cache
from pydantic import BaseModel


def _mensaje_de_la_fuente(clave: str, defecto: str) -> str:
    """Un mensaje fijo al cliente, leido de `base_conocimiento.json`."""
    try:
        from app.core.guia_venta_prosa import mensaje
        return mensaje(clave, defecto)
    except Exception:
        return defecto


class Settings(BaseModel):
    # NOTA: el cartel de interpretacion (ex flag INTERPRETE_DEBUG) se quito del mensaje al cliente.

    # Negocio
    BUSINESS_NAME: str = os.getenv("BUSINESS_NAME", "Tienda Tecno")
    TIENDA_ID: str = os.getenv("TIENDA_ID", "tienda_principal")

    # GCP
    GCP_PROJECT: str = os.getenv("GCP_PROJECT", "memory-engine-v1")

    # Telegram
    TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")

    # WhatsApp
    WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "")
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "")

    # EL PROVIDER DEL CAMINO VIVO. Default GEMINI.
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").lower()

    # Groq Whisper, transcripcion de audio. No es el LLM del turno.
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # Gemini: endpoint compatible con OpenAI. Es LA puerta al modelo.
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    # PRODUCCION CLAVADA a gemini-3.1-flash-lite (Martin, 14-jul): el mas barato y el que validamos con el
    # cacheo de contexto (~46 USD/mes por 1000 msgs diarios).
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    # EL RAZONAMIENTO DEL REDACTOR. Estaba CLAVADO en "none" adentro de `_redactar`.
    REDACTOR_REASONING: str = os.getenv("REDACTOR_REASONING", "none")
    GEMINI_BASE_URL: str = os.getenv(
        "GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai/")
    # DEEPSEEK, el otro proveedor que se mide (27-sep-2026).
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    # TTL del cache explicito de contexto (system + schema de tools) que usa el solver por el endpoint NATIVO.
    GEMINI_CACHE_TTL_S: int = int(os.getenv("GEMINI_CACHE_TTL_S", "1800"))

    # Comportamiento del LLM
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.2"))
    MAX_OUTPUT_TOKENS: int = int(os.getenv("MAX_OUTPUT_TOKENS", "800"))
    # 6 da aire a turnos contextuales, como un cambio de opinion que obliga a re-buscar y recalcular.
    MAX_TOOL_ITERATIONS: int = int(os.getenv("MAX_TOOL_ITERATIONS", "8"))

    # Historial de conversación: 10 turnos = 20 entradas
    HISTORY_LIMIT: int = int(os.getenv("HISTORY_LIMIT", "10"))

    # Búsqueda: cuántos productos devolver al LLM por consulta
    SEARCH_TOP_N: int = int(os.getenv("SEARCH_TOP_N", "10"))

    # CUANTO SE ESPERA CUANDO EL PROVEEDOR PIDE ESPERAR.
    LLM_ESPERA_MAX_S: float = float(os.getenv("LLM_ESPERA_MAX_S", "20"))

    # Mensaje fallback cuando algo falla. Sale de la FUENTE, igual que el de
    # abajo: el literal es solo la red por si el archivo faltara.
    FALLBACK_MESSAGE: str = _mensaje_de_la_fuente(
        "problema_tecnico",
        "Disculpá, tuve un problema técnico. ¿Podés repetirme tu consulta?")

    # ────────────────────────────────────────────────────────

    # Lo que se le dice al cliente cuando el turno no pudo contestar.
    VERIFIKA_FALLBACK_MESSAGE: str = _mensaje_de_la_fuente(
        "sin_dato_confirmado",
        "No tengo esa información confirmada en el catálogo. "
        "Dejame consultar y te confirmo en breve.")

    # ────────────────────────────────────────────────────────

    # Envio gratis automatico por umbral. La FUENTE DE VERDAD del umbral es la FAQ costo_envio (concepto
    # envio_gratis), el mismo numero que el bot le dice al cliente; cotizar_envio lo lee de ahi.
    UMBRAL_ENVIO_GRATIS: int = int(os.getenv("UMBRAL_ENVIO_GRATIS", "250000"))

    # NOTA: la calculadora defensiva (ex flag CALC_DEFENSIVA) ya es el UNICO camino de calculate_total,
    # cableada en app/core/calculadora.py (normaliza y valida inputs del modelo antes de calcular).

    # NOTA: la busqueda relajada (ex flag BUSQUEDA_RELAJADA) ya es el UNICO camino de search_products,
    # cableada en app/core/calculadora.py.

    # NOTA: el matcheo de FAQ por palabras (ex flag FAQ_MATCH_PALABRAS) ya es el UNICO camino de query_faq,
    # cableado en app/core/calculadora.py: el tema especifico gana al generico y la respuesta lleva temas
    # relacionados.
    EMBEDDINGS_MODEL: str = os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-small")

    # ────────────────────────────────────────────────────────

    # Cuantos PROOF recientes arrastrar entre turnos, para que en la confirmacion ("si, dale") el total
    # repetido siga teniendo respaldo.
    VERIFICADOR_PROOF_MEMORY: int = int(os.getenv("VERIFICADOR_PROOF_MEMORY", "7"))

    # AUTOCORRECCION DETERMINISTA (partida doble de la verdad).
    AUTOCORRIGE_MONTOS: bool = os.getenv("AUTOCORRIGE_MONTOS", "true").lower() == "true"

    # ────────────────────────────────────────────────────────
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))

    # NOTA: la tarifa de envio por PROVINCIA (ex flag TARIFA_PROVINCIA) ya es el UNICO camino de cotizar_envio
    # y de la calculadora: con la provincia o el CP determinados, el codigo devuelve la tarifa exacta de
    # config/tarifas_envio; si no, cae al rango publicado, nunca adivina.

    # NOTA: el link de pago Mercado Pago (ex flag LINK_PAGO) y el cierre desde el contrato (ex flag
    # CIERRE_CONTRATO) ya son el UNICO camino del cierre, cableados en leads.py/provider.py: con el lead
    # capturado el codigo genera la preferencia con el total VERIFICADO (total en rango = sin link), y dar la
    # direccion/zona cuenta como señal de compra.

    # NOTA: MODO_LIBRE_TOOLS se retiro en la limpieza del 10-jul: era el recorte de tools del solver libre,
    # que ya no corre (el compositor llama las tools por codigo, no elige de un menu).

    # SWITCH DE VERSION DEL BOT (A/B). Un solo lugar para elegir que version corre.
    MODO_CIERRE: str = os.getenv("MODO_CIERRE", "B").lower()

    # DATOS DE COBRO POR DEFECTO (demo). Config operativa de la tienda, no secreto: la config de Firestore por
    # tienda (cbu/alias/titular_cuenta/banco) PISA estos valores.
    DEMO_CBU: str = os.getenv("DEMO_CBU", "0000000000000000000000")
    DEMO_ALIAS: str = os.getenv("DEMO_ALIAS", "demo.verifika")
    # Apto cliente: el "reemplazar" viejo quedaba a la vista en el cobro demo.
    DEMO_TITULAR: str = os.getenv("DEMO_TITULAR", "Verifika (cuenta demo)")
    DEMO_BANCO: str = os.getenv("DEMO_BANCO", "Banco Demo")
    # Link de pago de DEMO cuando no hay token de Mercado Pago cargado: asi el bot igual manda un enlace y se
    # ve la accion.
    DEMO_LINK_PAGO: str = os.getenv("DEMO_LINK_PAGO", "https://mpago.la/demo")

    # TARIFA DE ENVIO AL INTERIOR POR PROVINCIA (fuente de verdad en codigo).
    ENVIO_INTERIOR_POR_PROVINCIA: dict = {
        # Cercano
        "buenos_aires": 6000, "cordoba": 6000, "santa fe": 6000,
        "entre rios": 6000, "la pampa": 6000,
        # Medio
        "mendoza": 9000, "san luis": 9000, "san juan": 9000, "tucuman": 9000,
        "santiago del estero": 9000, "la rioja": 9000, "catamarca": 9000,
        "salta": 9000, "jujuy": 9000, "corrientes": 9000, "chaco": 9000,
        "formosa": 9000, "misiones": 9000, "neuquen": 9000, "rio negro": 9000,
        # Lejano (Patagonia sur)
        "chubut": 12000, "santa cruz": 12000, "tierra del fuego": 12000,
    }

    # Codigo secreto de reset para pruebas. Si el mensaje del usuario es exactamente este texto
    # (case-insensitive, sin espacios extra), se borra toda la conversacion y el sistema responde confirmando
    # el reset.
    RESET_CODE: str = os.getenv("RESET_CODE", "verifika2026")

    # NOTA: la siembra inicial del cierre (ex flag CIERRE_SIEMBRA_INICIAL) ya es el UNICO camino en leads.py:
    # al disparar el cierre con presupuesto, el lead se siembra con los datos que ya trae el mensaje (nombre,
    # telefono, direccion, forma de pago); si estan los cuatro cierra ya, si falta pide solo lo que falta.

    # NOTA: cotizar_envio (ex flag ENVIO_POR_ZONA) es ahora un tool SIEMPRE presente: el CODIGO clasifica la
    # zona desde el CP o la localidad y devuelve la tarifa de la tienda; el modelo nunca elige la zona.

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
