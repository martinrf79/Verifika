"""Configuración del bot v5 — Firestore + DeepSeek + tools + Verifika."""
import os
from functools import lru_cache
from pydantic import BaseModel


class Settings(BaseModel):
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
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "deepseek").lower()

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
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_BASE_URL: str = os.getenv(
        "GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai/")

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

    # Comportamiento del LLM
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.2"))
    MAX_OUTPUT_TOKENS: int = int(os.getenv("MAX_OUTPUT_TOKENS", "800"))
    # 6 da aire a turnos contextuales, como un cambio de opinion que obliga a
    # re-buscar y recalcular. Los turnos simples siguen cerrando en 1 o 2.
    MAX_TOOL_ITERATIONS: int = int(os.getenv("MAX_TOOL_ITERATIONS", "6"))

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

    # Activar/desactivar el pipeline Proposer + Checker
    USE_VERIFIKA: bool = os.getenv("USE_VERIFIKA", "false").lower() == "true"

    # Mensaje cuando Verifika decide no mandar la respuesta del Solver
    VERIFIKA_FALLBACK_MESSAGE: str = os.getenv(
        "VERIFIKA_FALLBACK_MESSAGE",
        "No tengo esa información confirmada en el catálogo. "
        "Dejame consultar y te confirmo en breve."
    )

    # ────────────────────────────────────────────────────────
    # CAPA DE PRODUCTO — herramientas del agente de ventas
    # ────────────────────────────────────────────────────────

    # Envio gratis automatico por umbral. Si el subtotal de PRODUCTOS supera
    # UMBRAL_ENVIO_GRATIS, la calculadora pone el envio en gratis sola, sin
    # importar el concepto de envio que pida el Solver. Asi el total final sale
    # entero y deterministico de la calculadora.
    UMBRAL_ENVIO_GRATIS: int = int(os.getenv("UMBRAL_ENVIO_GRATIS", "250000"))

    # Calculadora defensiva. Normaliza y valida los inputs que manda el modelo
    # ANTES de calcular, en app/core/calc_defensiva.py. Resuelve dualidades como
    # el verificador resuelve la salida: rechaza cantidades cero o negativas,
    # normaliza la capitalizacion del concepto de FAQ, fusiona el mismo producto
    # mandado en dos lineas y deduplica un extra identico mandado dos veces. Asi
    # un input sucio del modelo no ensucia el total ni dispara fallback.
    # false: comportamiento identico al previo, la calculadora confia en el input.
    CALC_DEFENSIVA: bool = (
        os.getenv("CALC_DEFENSIVA", "false").lower() == "true"
    )

    # Anclaje del Interpretador al catalogo. Hoy el Interpretador no ve el
    # catalogo: sus candidatos los inventa el modelo y a veces no existen. Con el
    # flag, despues de interpretar, los candidatos y el producto se aterrizan al
    # catalogo real por match de palabras mas fuzzy (sin embeddings), en
    # app/core/interprete_ancla.py. Si hay un producto real claro lo resuelve; si
    # hay varios reales empatados los deja como opciones y baja la confianza para
    # que el bot pregunte; si es una categoria generica lo deja para el Solver.
    # false: el Interpretador se comporta igual que hoy.
    INTERPRETE_ANCLA_CATALOGO: bool = (
        os.getenv("INTERPRETE_ANCLA_CATALOGO", "false").lower() == "true"
    )

    # Respondedor determinista de FAQ (Hito 2, puerta 1). Una pregunta pura de
    # politica de la tienda, "como pago", "cuanto tarda a Salta", se contesta con
    # el texto curado de la FAQ SIN pasar por el LLM. Sin generacion, no hay
    # alucinacion. Conservador: solo dispara con un match especifico y dominante
    # y sin producto en juego; ante la duda defiere al Solver. Codigo en
    # app/core/faq_responder.py. false: todo va al Solver como hoy.
    FAQ_DIRECTO: bool = os.getenv("FAQ_DIRECTO", "false").lower() == "true"

    # Guard anti pierde-el-hilo. Una conversacion en curso no puede volver a
    # estado 'saludo'. El estado lo fija el LLM-interpretador y se lo inyecta al
    # solver, cuya Regla #0 dice 'saludo, devolve el saludo'. Si el interpretador
    # lee mal un turno de mitad de charla como saludo, el solver se reinicia con
    # un '¡Hola! Soy vendedor...' y pierde el contexto (falla e, contradiccion
    # entre turnos, vista en el molino). Con el flag on, si ya hubo historial y el
    # estado vuelve a saludo, se degrada a 'explorando' o al estado en curso
    # anterior, en app/core/interpretador.corregir_estado_regresion. Solo aplica
    # con USE_INTERPRETER. false: el estado pasa tal cual lo da el interpretador.
    ESTADO_NO_REGRESA_SALUDO: bool = (
        os.getenv("ESTADO_NO_REGRESA_SALUDO", "false").lower() == "true"
    )

    # PERILLA MAESTRA del nucleo nuevo "fuente de verdad" (camino A). Cuando esta
    # en on, el mensaje corre por el flujo de cuatro puertas: un LLM entiende
    # (solo entiende), el codigo enruta por suficiencia de evidencia, el codigo
    # resuelve el hecho de la fuente, un LLM lo viste de venta, y el gate por
    # gravedad mas autofix son el piso. off: el sistema corre como hoy. Se
    # construye en paralelo, no rompe el camino actual; si no convence, se apaga.
    NUCLEO_FUENTE_VERDAD: bool = (
        os.getenv("NUCLEO_FUENTE_VERDAD", "false").lower() == "true"
    )

    # Busqueda semantica con embeddings. Con el flag activo, la busqueda mezcla
    # el puntaje por palabras con el puntaje por significado (coseno entre el
    # vector de la consulta y el del producto). Ayuda cuando el cliente usa
    # sinonimos o no nombra las palabras exactas del catalogo, y a rankear los
    # mas relevantes entre muchos. Requiere que los productos tengan su vector
    # generado (scripts/generar_embeddings.py). false: solo busqueda por palabras.
    EMBEDDINGS_ON: bool = os.getenv("EMBEDDINGS_ON", "false").lower() == "true"
    # Proveedor del embedding: openai (con OPENAI_API_KEY) o deepseek (legacy).
    EMBEDDINGS_PROVIDER: str = os.getenv("EMBEDDINGS_PROVIDER", "openai").lower()
    EMBEDDINGS_MODEL: str = os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-small")

    # ────────────────────────────────────────────────────────
    # OBSERVABILIDAD
    # ────────────────────────────────────────────────────────

    # Diagnostico verboso (nivel dos). Cuando esta en true, ademas de las
    # metricas baratas que van siempre (tiempos por etapa, trace_id en todos
    # los eventos, contadores de decision), se loguea el detalle pesado para
    # investigar: el texto que iba a responder el bot, cuanta evidencia vio y,
    # por cada afirmacion, su tipo, su veredicto y la razon del Checker.
    # Se prende solo para diagnosticar y se apaga despues, por costo y privacidad.
    DIAG_TRACE: bool = os.getenv("DIAG_TRACE", "false").lower() == "true"

    # ────────────────────────────────────────────────────────
    # VERIFICADOR DETERMINISTA — linea cero de la anti alucinacion
    # ────────────────────────────────────────────────────────
    # La decision final de mandar o no la respuesta la toma el CODIGO, no un
    # modelo. El verificador escanea la respuesta y exige que cada cifra de
    # dinero salga de una fuente real: precio de catalogo, valor o texto de FAQ,
    # o un PROOF de la calculadora, de este turno o de turnos recientes. Si una
    # cifra no tiene respaldo, se bloquea. Es exacto y no entra en loop.
    #
    # Modos:
    #   off    -> no corre. Gatea Verifika (Checker LLM) como hasta ahora.
    #   shadow -> corre y loguea su decision, pero NO cambia la conducta. Gatea
    #             Verifika. Sirve para comparar con datos antes de confiar.
    #   on     -> el verificador determinista GATEA. El Checker LLM se desconecta
    #             (o queda de asesor si VERIFIKA_CHECKER_ADVISORY=true).
    VERIFICADOR_MODE: str = os.getenv("VERIFICADOR_MODE", "shadow").lower()

    # Cuantos PROOF recientes arrastrar entre turnos, para que en la confirmacion
    # ("si, dale") el total repetido siga teniendo respaldo. Acompaña la memoria
    # de la conversacion y el reconocimiento del estado de compra.
    VERIFICADOR_PROOF_MEMORY: int = int(os.getenv("VERIFICADOR_PROOF_MEMORY", "7"))

    # Si el verificador gatea (modo on), correr igual el Checker LLM solo para
    # loguear una segunda opinion, sin bloquear. Default false: desconectado,
    # para ahorrar las dos llamadas al modelo y bajar latencia.
    VERIFIKA_CHECKER_ADVISORY: bool = (
        os.getenv("VERIFIKA_CHECKER_ADVISORY", "false").lower() == "true"
    )

    # ────────────────────────────────────────────────────────
    # VERIFICADOR DE SERVICIOS — segunda linea, anti promesa inventada
    # ────────────────────────────────────────────────────────
    # El verificador de plata cuida las cifras. Este cuida los SERVICIOS: que el
    # bot no prometa capacidades que la tienda no ofrece (empaque para regalo,
    # instalacion, entrega en mano, retiro en local de una tienda online, garantia
    # extendida, servicio tecnico). Es codigo puro en app/core/verificador_servicios.py:
    # arma lo que la tienda SI ofrece desde la evidencia real (texto de FAQ y
    # campos de producto) y marca un servicio riesgoso afirmado que no este
    # respaldado ahi. Una negacion ("no hacemos envoltorio") no se marca.
    # La FAQ entera entra como evidencia, asi que es la fuente de verdad.
    #
    # Modos (independiente del VERIFICADOR_MODE de plata):
    #   off    -> no corre.
    #   shadow -> corre y loguea su decision (evento servicios_shadow), no cambia
    #             la conducta. Para medir con datos reales antes de confiar.
    #   on     -> gatea: si la respuesta promete un servicio inventado, manda el
    #             VERIFIKA_FALLBACK_MESSAGE en vez de la promesa falsa.
    VERIFICADOR_SERVICIOS: str = os.getenv("VERIFICADOR_SERVICIOS", "off").lower()

    # ────────────────────────────────────────────────────────
    # VERIFICADOR DE HECHOS (tercera linea anti alucinacion, por codigo)
    # ────────────────────────────────────────────────────────
    # Cuida una clase que ni plata ni servicios cubren: el bot NARRA una REGLA de
    # la tienda y la dice mal. Caso canonico (charla de Jorge): la FAQ dice
    # "interior 4 a 7 dias habiles" y el bot prometio "llega el jueves" y "24 a 72
    # horas"; o agrego "American Express directo, sin intermediarios", detalle que
    # no esta en la FAQ. Codigo puro en app/core/verificador_hechos.py: deriva una
    # ficha de HECHOS de la FAQ (plazo de envio, zonas express, formas de pago) y
    # marca por CLASE (promete un dia de entrega, comprime el plazo a horas, agrega
    # un detalle de pago sin respaldo). NO es lista negra de frases. Ante la duda
    # no marca (si el hecho no se pudo derivar, esa clase no se chequea).
    #
    # Modos (independiente de plata y de servicios):
    #   off    -> no corre.
    #   shadow -> corre y loguea (evento hechos_shadow), no cambia la conducta.
    #   on     -> gatea: manda el VERIFIKA_FALLBACK_MESSAGE en vez de la regla mal
    #             narrada. Rollout recomendado: shadow primero, medir, despues on.
    VERIFICADOR_HECHOS: str = os.getenv("VERIFICADOR_HECHOS", "off").lower()

    # ────────────────────────────────────────────────────────
    # LATENCIA — timeout de las llamadas al modelo
    # ────────────────────────────────────────────────────────
    # Sin timeout, el cliente espera hasta 600 segundos y una llamada lenta
    # cuelga todo el mensaje. Esto la corta a tiempo. Una llamada sana tarda
    # 5 a 10 segundos, asi que el cap solo actua sobre cuelgues anormales.
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))

    # Provider del interpretador. Default DeepSeek. Poner groq para que tambien
    # use Groq y baje su latencia. El Solver se cambia aparte con LLM_PROVIDER.
    INTERPRETER_PROVIDER: str = os.getenv("INTERPRETER_PROVIDER", "deepseek").lower()

    # Capa de razonamiento de venta en el prompt del Solver. Apendice nuevo
    # (Regla 9) que NO toca las 8 reglas probadas: le ensena al modelo a hacer
    # avanzar la venta sin inventar nada. Tranquiliza la duda tecnica con lo del
    # catalogo, afirma compatibilidad y originalidad desde las specs, lee la senal
    # de compra (si compro dos, lo necesito urgente, te oferto ya) y avanza al
    # cierre, y cuando piden un servicio que no esta en la FAQ pivotea a lo que si
    # hacemos en vez de cortar. Sigue prohibido inventar numeros, datos o promesas.
    # Default false: el prompt se comporta igual que hoy. Se mide con A/B en
    # scripts/prueba_bot_completo.py antes de prenderlo en prod.
    PROMPT_VENTA: bool = os.getenv("PROMPT_VENTA", "false").lower() == "true"

    # CHECKER COMO GATE GENERAL POR GRAVEDAD. El Checker de Verifika (Proposer +
    # Checker LLM) es el mecanismo GENERAL de grounding: descompone la respuesta
    # en afirmaciones tipadas e indica cuales no tiene respaldo en la evidencia,
    # cubriendo de una sola forma las infinitas redacciones (producto inventado,
    # promesa de dia que extiende el plazo, servicio o politica sin respaldo) que
    # los verificadores deterministas cazan con regex de a una. Con el flag on, el
    # Checker corre AUNQUE VERIFICADOR_MODE=on y su salida pasa por el gate por
    # gravedad (app/core/gate_gravedad.py): bloquea contradicha de cualquier tipo
    # y sin_evidencia de tipos duros (precio, stock, producto, politica), no las
    # caracteristicas blandas. Si AUTOFIX, repromptea antes del fallback. Cuesta
    # dos llamadas LLM extra por turno (Proposer + Checker): se prende cuando se
    # prioriza robustez sobre tokens. Los numeros siguen mandados por la
    # calculadora via reconciliacion numerica del pipeline. false: como hoy.
    CHECKER_GATEA: bool = (
        os.getenv("CHECKER_GATEA", "false").lower() == "true"
    )

    # Constitucion como tabla unica de reglas en el prompt del Solver. Hoy las
    # reglas del Solver estan dispersas en el prompt (reglas 1-9) y, por otro
    # lado, el gate (verificadores de plata, servicios y hechos) las enforcea por
    # codigo. La constitucion (app/core/constitucion.py) es la tabla canonica que
    # mezcla las prohibiciones que gatea el codigo con los deberes de venta. Con
    # el flag on, ese mismo texto se inyecta como preambulo supremo del prompt,
    # asi el Solver LEE exactamente las reglas que despues gatea el codigo (una
    # sola fuente). Las reglas 1-9 quedan como el COMO operativo (buscar primero,
    # calculate_total, etc.); la constitucion es el QUE manda sobre todo.
    # false: el prompt se comporta igual que hoy, sin el preambulo.
    PROMPT_CONSTITUCION: bool = (
        os.getenv("PROMPT_CONSTITUCION", "false").lower() == "true"
    )

    # Corrector anclado: segunda pasada LLM stateless sobre la respuesta del
    # Solver. Recibe la respuesta tal cual MAS la evidencia del turno (productos,
    # FAQ, PROOF), sin memoria ni historial ni la pregunta original, y aterriza
    # cada hecho a la evidencia: corrige o quita lo que no tiene respaldo,
    # preservando la estructura (opciones A/B, confirmacion) y el tono de venta.
    # Constrene la generacion (no puede afirmar lo que no recibio) en vez de solo
    # detectar despues. Corre ANTES del verificador determinista, que sigue siendo
    # el piso duro de numeros. Modelo configurable: rol 'corrector' del
    # llm_adapter (VERIFIKA_CORRECTOR_PROVIDER/MODEL), default deepseek. Cuesta +1
    # llamada LLM por turno. false: prod identico, no corre. Ver app/core/corrector.py.
    CORRECTOR_ANCLADO: bool = (
        os.getenv("CORRECTOR_ANCLADO", "false").lower() == "true"
    )

    # Cierre forzado al pegar el tope de iteraciones del Solver. Hoy, si el
    # Solver agota MAX_TOOL_ITERATIONS (caso de calculo complejo: multi-producto
    # mas rango de envio mas descuento), devuelve el FALLBACK_MESSAGE "tuve un
    # problema tecnico" a mitad de charla, que es un error VISIBLE para el
    # cliente. Con el flag on, antes de rendirse hace UNA llamada final sin tools
    # para cerrar con lo que ya junto. Seguro: el verificador determinista gatea
    # despues cualquier cifra sin respaldo. En app/core/agent.py. false: se
    # comporta igual que hoy (manda el fallback).
    CIERRE_FORZADO_MAX_ITER: bool = (
        os.getenv("CIERRE_FORZADO_MAX_ITER", "false").lower() == "true"
    )

    # ────────────────────────────────────────────────────────
    # AUTOFIX — autocorreccion ante bloqueo del verificador
    # ────────────────────────────────────────────────────────
    # Cuando el verificador determinista bloquea por numeros sin respaldo, en vez
    # de mandar el fallback, reintenta UNA vez: le pide al Solver que rehaga el
    # presupuesto con la calculadora, sin inventar, y vuelve a verificar. Si se
    # corrige, responde bien. Si no, recien ahi manda el fallback. Suma una
    # corrida del Solver solo cuando hubo bloqueo, que es raro. Default false.
    AUTOFIX: bool = os.getenv("AUTOFIX", "false").lower() == "true"

    # ────────────────────────────────────────────────────────
    # ANTI-JAILBREAK — filtro de ENTRADA, primera linea, por codigo
    # ────────────────────────────────────────────────────────
    # Antes de cualquier LLM, el mensaje del cliente pasa por reglas deterministas
    # (regex de patrones de manipulacion + largo). Caza intentos de jailbreak
    # ("ignora tus instrucciones", "actua como", "decime tu prompt", "modo
    # desarrollador", volcados enormes) que buscan que el bot se salga de su rol.
    # NO interpreta nada: frena basura antes de gastar tokens. Codigo puro en
    # app/core/antijailbreak.py. Conservador: solo marca patrones claros de ataque,
    # una consulta normal de cliente NUNCA dispara.
    # Modos:
    #   off    -> no corre (prod identico).
    #   shadow -> corre y loguea (evento antijailbreak_shadow), NO bloquea. Para
    #             medir falsos positivos con trafico real antes de confiar.
    #   on     -> bloquea: si detecta ataque, devuelve una respuesta estatica de
    #             marca y corta el pipeline sin llamar al LLM.
    ANTI_JAILBREAK: str = os.getenv("ANTI_JAILBREAK", "off").lower()


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


def deepseek_pensando(model_name: str) -> bool:
    """True si esta llamada va a ir en modo razonador: modelo v4 y thinking on."""
    return "v4" in (model_name or "").lower() and get_settings().DEEPSEEK_THINKING
