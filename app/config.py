"""Configuración del bot v5 — Firestore + DeepSeek + tools + Verifika."""
import os
from functools import lru_cache
from pydantic import BaseModel

class Settings(BaseModel):
    # NOTA: el cartel de interpretacion (ex flag INTERPRETE_DEBUG) se quito del
    # mensaje al cliente. La interpretacion ahora va al log (evento
    # interprete_libre_interpretacion). Consolidado 25-jun.

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

    # LLM provider — soportamos deepseek (default) y groq (fallback)
    # NOTA: Verifika tiene su propia config por rol en llm_adapter.py.
    # Estos settings son SOLO para el Solver del agente v4 (legacy).
    # Provider del SOLVER. OK explicito de Martin (7-jul-2026): se pasa a OpenAI
    # gpt-4o-mini para correr la constrained generation dura de punta a punta.
    # Es config, no camino apagado; se vuelve a deepseek cambiando este default.
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai").lower()

    # DeepSeek
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    # deepseek-chat se da de baja el 24-jul-2026; migrado a deepseek-v4-flash
    # (validado, A/B 120 empate limpio). Corre non-thinking por DEEPSEEK_THINKING=false.
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

    # Los modelos DeepSeek v4 (deepseek-v4-flash, deepseek-v4-pro) traen
    # RAZONAMIENTO (thinking) por default. Eso rompe dos cosas nuestras: el solver
    # fuerza tool_choice=required en la primera vuelta y thinking no lo soporta, y
    # el razonamiento se come el presupuesto de tokens del interpretador (JSON
    # vacio). Ademas suma latencia, que peleamos mucho por bajar. Con este flag en
    # false (default) APAGAMOS el thinking en los v4 (extra_body thinking disabled),
    # asi se portan como el deepseek-chat viejo: rapido, tool calling forzado OK.
    # Ponerlo en true solo si algun dia se quiere medir el modo razonador.
    # No afecta a deepseek-chat ni a otros providers (el helper solo toca modelos v4).
    DEEPSEEK_THINKING: bool = os.getenv("DEEPSEEK_THINKING", "false").lower() == "true"

    # Groq (fallback)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # Gemini (alternativa rapida con tool calling solido y limite gratis enorme).
    # Usa el endpoint compatible con OpenAI de Google, asi entra con el mismo
    # cliente. Se activa con LLM_PROVIDER=gemini.
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    # PRODUCCION CLAVADA a gemini-3-flash-preview (Martin, 13-jul): el alias
    # gemini-flash-latest FLOTA (hoy resuelve a gemini-3.5-flash) y el dia que
    # Google mueve el alias te cambia el modelo y el costo sin avisar. El
    # camino vivo se probo con Gemini 3 Flash, asi que se pinea EXPLICITO. Se
    # repinea a mano cuando salga la version GA estable; nunca con -latest.
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
    GEMINI_BASE_URL: str = os.getenv(
        "GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai/")
    # TTL del cache explicito de contexto (system + schema de tools) que usa el
    # solver por el endpoint NATIVO. El prefijo fijo se cachea una vez y se cobra
    # al 10% en cada vuelta del loop; baja la factura ~a la mitad sin cambiar lo
    # que el modelo ve. Se refresca solo al expirar. Config operativa.
    GEMINI_CACHE_TTL_S: int = int(os.getenv("GEMINI_CACHE_TTL_S", "1800"))

    # OpenAI nativo (servidores en EEUU, tool calling solido). Se activa con
    # LLM_PROVIDER=openai o INTERPRETER_PROVIDER=openai. Usa el mismo cliente
    # OpenAI con la base_url default (api.openai.com). gpt-4o-mini es economico
    # (~0,15 USD el millon de tokens de entrada) y maneja bien las herramientas.
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Anthropic Claude via su endpoint compatible con OpenAI (mismo cliente, otra
    # base_url, igual que Gemini). Probado: el compat acepta tool calling y
    # tool_choice required. Se activa con LLM_PROVIDER=anthropic o
    # INTERPRETER_PROVIDER=anthropic. Haiku es el modelo chico, economico y el que
    # menos alucina en la practica. claude-haiku-4-5 es el id vigente (los 3.5
    # estan dados de baja). Cuesta plata: solo con OK de Martin.
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
    # Normalizado para garantizar el sufijo /v1 (el entorno puede tener una env
    # ANTHROPIC_BASE_URL sin /v1, que da 404 con el cliente OpenAI).
    ANTHROPIC_BASE_URL: str = (
        os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        .rstrip("/").removesuffix("/v1") + "/v1")

    # NVIDIA Nemotron via su endpoint NIM compatible con OpenAI (mismo cliente,
    # otra base_url, igual que Gemini y Anthropic). API gratis en build.nvidia.com,
    # la key arranca con nvapi-. Se activa con LLM_PROVIDER=nemotron para el Solver
    # o por rol con VERIFIKA_*_PROVIDER=nemotron (ej el corrector). Modelo grande
    # para pruebas intensivas. El id EXACTO sale del catalogo de NVIDIA y se setea
    # por env en NEMOTRON_MODEL: el default es un placeholder, reemplazalo por el id
    # real de Nemotron 3 Ultra. OJO: el tool calling de NIM no garantiza
    # tool_choice=required, asi que el Solver con Nemotron va en auto (ver agent.py).
    NEMOTRON_API_KEY: str = os.getenv("NEMOTRON_API_KEY", "")
    NEMOTRON_MODEL: str = os.getenv("NEMOTRON_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
    NEMOTRON_BASE_URL: str = os.getenv(
        "NEMOTRON_BASE_URL", "https://integrate.api.nvidia.com/v1")

    # Kimi (Moonshot) via NIM de NVIDIA: gratis, obediente, con tool calling real.
    # Misma clave nvapi- que Nemotron: si no hay KIMI_API_KEY propia, cae a
    # NEMOTRON_API_KEY. Se activa con LLM_PROVIDER=kimi para el Solver o por rol con
    # VERIFIKA_*_PROVIDER=kimi. El id exacto sale del catalogo NVIDIA; el default es
    # Kimi K2.6. Si tu clave fuera de Moonshot directo u OpenRouter, solo cambia
    # KIMI_BASE_URL. El tool calling required de NIM no esta garantizado: el Solver
    # con kimi va en auto (igual que nemotron y gemini).
    KIMI_API_KEY: str = os.getenv("KIMI_API_KEY", "") or os.getenv("NEMOTRON_API_KEY", "")
    KIMI_MODEL: str = os.getenv("KIMI_MODEL", "moonshotai/kimi-k2.6")
    KIMI_BASE_URL: str = os.getenv(
        "KIMI_BASE_URL", "https://integrate.api.nvidia.com/v1")

    # OpenRouter: un solo endpoint OpenAI-compatible que rutea a cientos de modelos
    # (deepseek, llama, qwen, gemini...). Clave arranca con sk-or-. El modelo se
    # elige por id (ej meta-llama/llama-3.3-70b-instruct, deepseek/deepseek-chat).
    # Con $10 cargados una vez: 1000 pedidos gratis/dia + pago barato sin tope.
    # Se activa con LLM_PROVIDER=openrouter o por rol con VERIFIKA_*_PROVIDER=openrouter.
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct")
    OPENROUTER_BASE_URL: str = os.getenv(
        "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    # Comportamiento del LLM
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.2"))
    MAX_OUTPUT_TOKENS: int = int(os.getenv("MAX_OUTPUT_TOKENS", "800"))
    # 6 da aire a turnos contextuales, como un cambio de opinion que obliga a
    # re-buscar y recalcular. Los turnos simples siguen cerrando en 1 o 2.
    MAX_TOOL_ITERATIONS: int = int(os.getenv("MAX_TOOL_ITERATIONS", "8"))

    # Historial de conversación: 10 turnos = 20 entradas
    HISTORY_LIMIT: int = int(os.getenv("HISTORY_LIMIT", "10"))

    # Búsqueda: cuántos productos devolver al LLM por consulta
    SEARCH_TOP_N: int = int(os.getenv("SEARCH_TOP_N", "10"))

    # Mensaje fallback cuando algo falla
    FALLBACK_MESSAGE: str = (
        "Disculpá, tuve un problema técnico. ¿Podés repetirme tu consulta?"
    )

    # ────────────────────────────────────────────────────────
    # VERIFIKA — núcleo verificable
    # ────────────────────────────────────────────────────────

    # Mensaje cuando Verifika decide no mandar la respuesta del Solver
    VERIFIKA_FALLBACK_MESSAGE: str = os.getenv(
        "VERIFIKA_FALLBACK_MESSAGE",
        "No tengo esa información confirmada en el catálogo. "
        "Dejame consultar y te confirmo en breve."
    )

    # ────────────────────────────────────────────────────────
    # CAPA DE PRODUCTO — herramientas del agente de ventas
    # ────────────────────────────────────────────────────────

    # Envio gratis automatico por umbral. La FUENTE DE VERDAD del umbral es la FAQ
    # costo_envio (concepto envio_gratis), el mismo numero que el bot le dice al
    # cliente; cotizar_envio lo lee de ahi. Esto es SOLO el respaldo si la FAQ no lo
    # trae. Se alinea a 250000 (el valor publicado en la FAQ) para que el respaldo no
    # vuelva a divergir del numero que ve el cliente (era el bug: 250000 vs 300000).
    UMBRAL_ENVIO_GRATIS: int = int(os.getenv("UMBRAL_ENVIO_GRATIS", "250000"))

    # NOTA: la calculadora defensiva (ex flag CALC_DEFENSIVA) ya es el UNICO camino
    # de calculate_total, cableada en app/core/tools.py (normaliza y valida inputs
    # del modelo antes de calcular). Consolidada 24-jun: dejo de ser flag.

    # NOTA: la busqueda relajada (ex flag BUSQUEDA_RELAJADA) ya es el UNICO camino
    # de search_products, cableada en app/core/tools.py. Tapaba "0 ventas por negar
    # stock que existe". Consolidada 24-jun: dejo de ser flag.

    # NOTA: el matcheo de FAQ por palabras (ex flag FAQ_MATCH_PALABRAS) ya es el
    # UNICO camino de query_faq, cableado en app/core/tools.py: el tema especifico
    # gana al generico y la respuesta lleva temas relacionados. Consolidado 24-jun.
    # Proveedor del embedding: openai (con OPENAI_API_KEY) o deepseek (legacy).
    EMBEDDINGS_PROVIDER: str = os.getenv("EMBEDDINGS_PROVIDER", "openai").lower()
    EMBEDDINGS_MODEL: str = os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-small")

    # ────────────────────────────────────────────────────────
    # OBSERVABILIDAD
    # ────────────────────────────────────────────────────────

    # Cuantos PROOF recientes arrastrar entre turnos, para que en la confirmacion
    # ("si, dale") el total repetido siga teniendo respaldo. Acompaña la memoria
    # de la conversacion y el reconocimiento del estado de compra.
    VERIFICADOR_PROOF_MEMORY: int = int(os.getenv("VERIFICADOR_PROOF_MEMORY", "7"))

    # AUTOCORRECCION DETERMINISTA (partida doble de la verdad). El mismo motor de
    # las herramientas (calculadora, tarifa de envio) que le da los numeros al
    # Solver se usa DESPUES como CLON para auditar la respuesta que el Solver
    # escribio: si una cifra de total fue cambiada y la verdad esta en el PROOF, el
    # codigo la REESCRIBE por la buena, sin llamar a ningun modelo (ver
    # autocorregir_montos en verificador.py). Si la cifra ya es correcta, pasa
    # intacta. Conservador: solo toca un total con un reemplazo INEQUIVOCO; ante
    # cualquier ambiguedad no la toca. false = vuelve a modo observacion (el paso
    # 2a solo loguea las cifras no respaldadas, no corrige).
    AUTOCORRIGE_MONTOS: bool = os.getenv("AUTOCORRIGE_MONTOS", "true").lower() == "true"

    # ────────────────────────────────────────────────────────
    # LATENCIA — timeout de las llamadas al modelo
    # ────────────────────────────────────────────────────────
    # Sin timeout, el cliente espera hasta 600 segundos y una llamada lenta
    # cuelga todo el mensaje. Esto la corta a tiempo. Una llamada sana tarda
    # 5 a 10 segundos, asi que el cap solo actua sobre cuelgues anormales.
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))

    # Provider del interpretador. OK de Martin (7-jul-2026): OpenAI gpt-4o-mini,
    # para que el interprete corra con Structured Outputs (constrained generation
    # dura: intencion, estado y producto_resuelto atados a enum). El Solver se
    # cambia aparte con LLM_PROVIDER. Config, no camino apagado.
    INTERPRETER_PROVIDER: str = os.getenv("INTERPRETER_PROVIDER", "openai").lower()

    # NOTA: la tarifa de envio por PROVINCIA (ex flag TARIFA_PROVINCIA) ya es el
    # UNICO camino de cotizar_envio y de la calculadora: con la provincia o el CP
    # determinados, el codigo devuelve la tarifa exacta de config/tarifas_envio;
    # si no, cae al rango publicado, nunca adivina. Consolidada 24-jun.

    # NOTA: el link de pago Mercado Pago (ex flag LINK_PAGO) y el cierre desde el
    # contrato (ex flag CIERRE_CONTRATO) ya son el UNICO camino del cierre, cableados
    # en leads.py/provider.py: con el lead capturado el codigo genera la preferencia
    # con el total VERIFICADO (total en rango = sin link), y dar la direccion/zona
    # cuenta como señal de compra. Requiere config/mp_access_token en Firestore o
    # MP_ACCESS_TOKEN por entorno; sin token, no manda link. Consolidados 25-jun.

    # NOTA: MODO_LIBRE_TOOLS se retiro en la limpieza del 10-jul: era el recorte
    # de tools del solver libre, que ya no corre (el compositor llama las tools
    # por codigo, no elige de un menu).

    # SWITCH DE VERSION DEL BOT (A/B). Un solo lugar para elegir que version corre.
    # Poner "A" o "B" aca (o por la env MODO_CIERRE), o en la config Firestore
    # 'modo_cierre' por tienda, que pisa este default. Es config de producto, no un
    # camino apagado:
    #   A (o "lead")  = el bot capta el lead fuerte y avisa; cierra un humano, y el
    #                   bot sigue conversando sin pedir datos. <-- deploy 1: prueba
    #                   en produccion de que el lead fuerte dispara y no frena la
    #                   iteracion. Despues de validarlo se vuelve a "B".
    #   B (o "venta") = el bot cierra la venta y manda el cobro: link de Mercado
    #                   Pago o CBU segun la forma de pago.
    #   off           = el cierre no actua; el bot vende igual, sin captar lead.
    MODO_CIERRE: str = os.getenv("MODO_CIERRE", "A").lower()

    # DATOS DE COBRO POR DEFECTO (demo). Config operativa de la tienda, no secreto:
    # la config de Firestore por tienda (cbu/alias/titular_cuenta/banco) PISA estos
    # valores. Estos defaults son de DEMOSTRACION, marcados como tal a proposito para
    # que nadie transfiera plata real a una cuenta de ejemplo; se editan por cliente.
    # Sirven para que en la demo el bot SI mande la modalidad de transferencia aunque
    # la tienda todavia no cargo sus datos reales. Editables por entorno.
    DEMO_CBU: str = os.getenv("DEMO_CBU", "0000000000000000000000")
    DEMO_ALIAS: str = os.getenv("DEMO_ALIAS", "demo.verifika")
    DEMO_TITULAR: str = os.getenv("DEMO_TITULAR", "CUENTA DEMO - reemplazar")
    DEMO_BANCO: str = os.getenv("DEMO_BANCO", "Banco Demo")
    # Link de pago de DEMO cuando no hay token de Mercado Pago cargado: asi el bot
    # igual manda un enlace y se ve la accion. En produccion real, el token genera
    # el link verdadero y este no se usa.
    DEMO_LINK_PAGO: str = os.getenv("DEMO_LINK_PAGO", "https://mpago.la/demo")

    # TARIFA DE ENVIO AL INTERIOR POR PROVINCIA (fuente de verdad en codigo). El
    # interior dejo de ser un rango: cada provincia tiene un monto fijo, dentro del
    # rango publicado en la FAQ costo_envio (5000-12000), agrupado en tres tramos
    # por distancia al origen de despacho (Buenos Aires). Asi cotizar_envio devuelve
    # UN numero por destino, el Solver no inventa una cifra y el total sale unico.
    # Editar aca para ajustar; una entrada en Firestore config 'tarifas_envio'
    # (clave 'provincias') pisa este default por tienda. Las claves son los slugs
    # que devuelve clasificar_provincia (envio.py). El disclaimer avisa que el costo
    # puede variar al confirmar la compra.
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

    # Codigo secreto de reset para pruebas. Si el mensaje del usuario es
    # exactamente este texto (case-insensitive, sin espacios extra), se borra
    # toda la conversacion y el sistema responde confirmando el reset.
    # Util para testear sin usar numeros distintos ni mecanismos de produccion.
    # Cambiar el valor si se quiere rotar el codigo. "" = desactivado.
    RESET_CODE: str = os.getenv("RESET_CODE", "verifika2026")

    # NOTA: la siembra inicial del cierre (ex flag CIERRE_SIEMBRA_INICIAL) ya es el
    # UNICO camino en leads.py: al disparar el cierre con presupuesto, el lead se
    # siembra con los datos que ya trae el mensaje (nombre, telefono, direccion,
    # forma de pago); si estan los cuatro cierra ya, si falta pide solo lo que
    # falta. Consolidada 25-jun.

    # NOTA: cotizar_envio (ex flag ENVIO_POR_ZONA) es ahora un tool SIEMPRE
    # presente: el CODIGO clasifica la zona desde el CP o la localidad y devuelve
    # la tarifa de la tienda; el modelo nunca elige la zona. Consolidada 24-jun.
    # cubre_envio se elimino: cotizar_envio ya implica cobertura.

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

def deepseek_extra_body(model_name: str, think: bool | None = None) -> dict:
    """extra_body para la llamada al cliente segun el modelo DeepSeek.
    Para los v4 (que razonan por default) apaga el thinking salvo que se quiera
    razonar. think=None usa el default global DEEPSEEK_THINKING; think=True/False
    lo fuerza para esta llamada puntual. Devuelve {} si no aplica (deepseek-chat
    viejo u otros providers, o thinking on que es el default del v4)."""
    if "v4" not in (model_name or "").lower():
        return {}
    if think is None:
        think = get_settings().DEEPSEEK_THINKING
    if think:
        return {}  # el v4 razona por default, no hace falta forzar nada
    return {"thinking": {"type": "disabled"}}

def nvidia_thinking_off(provider: str, model_name: str) -> dict:
    """extra_body para apagar el thinking en el endpoint de NVIDIA NIM.
    Aplica solo a los providers que pegan a NVIDIA (nemotron, kimi) y a modelos
    que razonan por default (deepseek v4, qwen3, nemotron, gpt-oss). En esos, el
    razonamiento suma 30 a 200s de latencia. Para otros providers o modelos
    devuelve {} (no se toca nada). NVIDIA usa chat_template_kwargs, distinto del
    extra_body de DeepSeek directo."""
    if (provider or "").lower() not in ("nemotron", "kimi"):
        return {}
    m = (model_name or "").lower()
    razona = (("v4" in m and "deepseek" in m) or "qwen3" in m
              or "nemotron" in m or "gpt-oss" in m)
    return {"chat_template_kwargs": {"thinking": False}} if razona else {}

def openrouter_reasoning_off(provider: str, model_name: str) -> dict:
    """extra_body para apagar el razonamiento via OpenRouter. Gemelo de
    nvidia_thinking_off: los modelos que razonan por default (gemini-2.5,
    qwen3, deepseek v4/r1, gpt-oss) suman 10-40s de latencia por turno aunque
    la salida tenga 13 tokens (medido en el molino multiturno con
    gemini-2.5-flash). OpenRouter unifica el apagado con el parametro
    reasoning. Para otros providers o modelos devuelve {} (no se toca nada).
    Si un modelo no soporta apagarlo (ej gemini-2.5-pro), el call site ya
    reintenta limpio. Se puede desactivar con OPENROUTER_REASONING_OFF=false."""
    if (provider or "").lower() != "openrouter":
        return {}
    if os.getenv("OPENROUTER_REASONING_OFF", "true").lower() != "true":
        return {}
    m = (model_name or "").lower()
    razona = ("gemini-2.5" in m or "qwen3" in m or "gpt-oss" in m
              or ("deepseek" in m and ("v4" in m or "r1" in m))
              or "thinking" in m)
    return {"reasoning": {"enabled": False}} if razona else {}

def gemini_thinking_off(provider: str, model_name: str) -> dict:
    """extra_body para apagar el thinking en la API DIRECTA de Gemini (endpoint
    compatible OpenAI). gemini-2.5 piensa por default y el pensamiento consume
    MAX_OUTPUT_TOKENS: si se lo come entero, el contenido sale VACIO (los 3
    "problema tecnico" del molino del 10-jun) o cortado a mitad de frase.
    Medido: default 2.8s con 4 chars de contenido; con reasoning_effort=none
    1.4s con la respuesta completa. Se desactiva con GEMINI_THINKING_OFF=false."""
    if (provider or "").lower() != "gemini":
        return {}
    if os.getenv("GEMINI_THINKING_OFF", "true").lower() != "true":
        return {}
    m = (model_name or "").lower()
    # 2.0-flash no razona; 2.5+, gemini-3 y los alias -latest lo traen
    # prendido por default (verificado 11-jul con gemini-flash-latest: el
    # thinking se comia los 400 tokens y el JSON salia cortado; con
    # reasoning_effort=none el schema estricto respondio perfecto).
    return {} if "2.0" in m else {"reasoning_effort": "none"}

def deepseek_pensando(model_name: str) -> bool:
    """True si esta llamada va a ir en modo razonador: modelo v4 y thinking on."""
    return "v4" in (model_name or "").lower() and get_settings().DEEPSEEK_THINKING
