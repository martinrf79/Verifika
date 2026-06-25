"""Configuración del bot v5 — Firestore + DeepSeek + tools + Verifika."""
import os
from functools import lru_cache
from pydantic import BaseModel


class Settings(BaseModel):
    # ────────────────────────────────────────────────────────
    # MODO DE PRUEBA DEL INTERPRETE (sesión 23-jun-2026) — INTERRUPTOR MAESTRO
    # ────────────────────────────────────────────────────────
    # Mientras SOLO_INTERPRETE está en true (DEFAULT), el orchestrator delega TODO
    # el turno a app/core/interprete_libre.py: intérprete + solver libre + memoria,
    # y NINGUNO de los otros ~70 flags ni de los cuatro caminos importa. Es la forma
    # de probar la interpretación en real con el resto apagado. Para volver al
    # sistema viejo: SOLO_INTERPRETE=false. No borra nada; es reversible.
    SOLO_INTERPRETE: bool = (
        os.getenv("SOLO_INTERPRETE", "true").lower() == "true"
    )
    # El bot muestra al final de cada respuesta QUÉ entendió el intérprete, para
    # poder juzgar la interpretación chateando, sin leer logs. Apagar con false
    # cuando ya no haga falta ver el detalle.
    INTERPRETE_DEBUG: bool = (
        os.getenv("INTERPRETE_DEBUG", "true").lower() == "true"
    )

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
    # Si el modelo devuelve contenido VACIO sin tool calls (vicio esporadico del
    # compat de Gemini), reintentar UNA vez antes de caer al fallback tecnico.
    REINTENTA_RESPUESTA_VACIA: bool = (
        os.getenv("REINTENTA_RESPUESTA_VACIA", "true").lower() == "true")

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
    UMBRAL_ENVIO_GRATIS: int = int(os.getenv("UMBRAL_ENVIO_GRATIS", "300000"))

    # NOTA: la calculadora defensiva (ex flag CALC_DEFENSIVA) ya es el UNICO camino
    # de calculate_total, cableada en app/core/tools.py (normaliza y valida inputs
    # del modelo antes de calcular). Consolidada 24-jun: dejo de ser flag.

    # Anclaje del Interpretador al catalogo. Hoy el Interpretador no ve el
    # catalogo: sus candidatos los inventa el modelo y a veces no existen. Con el
    # flag, despues de interpretar, los candidatos y el producto se aterrizan al
    # catalogo real por match de palabras mas fuzzy (sin embeddings), en
    # app/core/interprete_ancla.py. Si hay un producto real claro lo resuelve; si
    # hay varios reales empatados los deja como opciones y baja la confianza para
    # que el bot pregunte; si es una categoria generica lo deja para el Solver.
    # false: el Interpretador se comporta igual que hoy.
    INTERPRETE_ANCLA_CATALOGO: bool = (
        os.getenv("INTERPRETE_ANCLA_CATALOGO", "true").lower() == "true"
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

    # NO_RESALUDO: el bot saluda en el PRIMER mensaje, no a mitad de charla.
    # Bug visto: el Solver abre con "hola" en el segundo o tercer mensaje. Es
    # estilo del modelo, no del estado. Por codigo se saca el saludo inicial de
    # la respuesta cuando ya hay historial (no es el primer turno) y la respuesta
    # salio del Solver (no de un saludo deliberado por codigo). false: identico
    # al previo.
    NO_RESALUDO: bool = (
        os.getenv("NO_RESALUDO", "false").lower() == "true"
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

    # NOTA: la busqueda relajada (ex flag BUSQUEDA_RELAJADA) ya es el UNICO camino
    # de search_products, cableada en app/core/tools.py. Tapaba "0 ventas por negar
    # stock que existe". Consolidada 24-jun: dejo de ser flag.

    # NOTA: el matcheo de FAQ por palabras (ex flag FAQ_MATCH_PALABRAS) ya es el
    # UNICO camino de query_faq, cableado en app/core/tools.py: el tema especifico
    # gana al generico y la respuesta lleva temas relacionados. Consolidado 24-jun.
    # Proveedor del embedding: openai (con OPENAI_API_KEY) o deepseek (legacy).
    EMBEDDINGS_PROVIDER: str = os.getenv("EMBEDDINGS_PROVIDER", "openai").lower()
    EMBEDDINGS_MODEL: str = os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-small")

    # Busqueda disparada por codigo. La cañeria de tools depende del modelo: si
    # el modelo no llama search_products (visto con gemini en el molino del
    # 10-jun: "no tengo stock" en una tienda de 880) la maquinaria determinista
    # nunca recibe datos. Con el flag activo, cuando el interpretador detecta
    # exploracion o pregunta de producto, el CODIGO corre la busqueda antes del
    # Solver y le inyecta los resultados como evidencia en el mensaje. El modelo
    # ya tiene el catalogo relevante sin depender de que sepa llamar tools.
    # Cuesta una busqueda Firestore por turno y ~300 tokens; ahorra una vuelta
    # entera de LLM cuando funciona. false: identico al previo.
    BUSQUEDA_POR_CODIGO: bool = (
        os.getenv("BUSQUEDA_POR_CODIGO", "false").lower() == "true"
    )

    # Rescate de tool calls emitidos como texto. Algunos modelos (DeepSeek via
    # OpenRouter, Gemma) escriben los tokens del tool call en el contenido en
    # vez del campo tool_calls; sin este flag ese markup crudo llega al cliente
    # (16 de 100 respuestas en correr_pruebas del 10-jun). Con el flag activo,
    # el agente detecta el markup, parsea nombre y argumentos, EJECUTA la tool
    # de verdad y sigue el loop; si no puede parsear, limpia el markup para que
    # el cliente nunca lo vea. false: identico al previo.
    RESCATE_TOOLCALL_TEXTO: bool = (
        os.getenv("RESCATE_TOOLCALL_TEXTO", "true").lower() == "true"
    )

    # ────────────────────────────────────────────────────────
    # OBSERVABILIDAD
    # ────────────────────────────────────────────────────────

    # Telemetria del turno en memoria. Despues de cada process_message deja un
    # registro chico (tools llamadas con args y cantidad de resultados, estado,
    # outcome) que los molinos leen para volcar al CSV. Separa "el modelo no
    # llamo la tool" de "la llamo y el resultado se perdio" sin leer logs.
    # Solo memoria de proceso, cero red y cero tokens.
    TELEMETRIA_TURNO: bool = (
        os.getenv("TELEMETRIA_TURNO", "false").lower() == "true"
    )

    # Carrito vigente: los ITEMS del ultimo calculate_total ok se persisten en
    # la conversacion y se inyectan al Solver como pedido vigente. Cura la
    # clase "carrito muta de identidad": el cliente saca un producto y el
    # modelo recalcula con OTROS productos del registro (precios reales,
    # pedido equivocado; cazado por el arnes en b03 con carrito_drift).
    CARRITO_VIGENTE: bool = (
        os.getenv("CARRITO_VIGENTE", "false").lower() == "true"
    )

    # Piso contra el "presupuesto disfrazado": bloque Presupuesto/Total armado
    # a mano por el modelo sin calculate_total en el turno. off | shadow | on.
    PISO_PRESUPUESTO: str = os.getenv("PISO_PRESUPUESTO", "off").lower()

    # PROVIDER (motor determinista total): el codigo calcula en TODOS los turnos
    # aunque nadie lo pida (producto en foco, carrito vigente, envio con la
    # localidad conocida, descuento por transferencia) y le entrega al Solver
    # UN solo contrato por turno con los numeros ya cerrados. El Solver decide
    # cuales pegar y vende alrededor; jamas calcula. Reemplaza (consolida) las
    # inyecciones sueltas de registro/cotizador/AB/carrito/busqueda que hoy
    # compiten entre si en charlas largas. Necesita REGISTRO_SESION para tener
    # registro de donde resolver. Default off: pipeline identico al previo.
    PROVIDER: bool = os.getenv("PROVIDER", "false").lower() == "true"

    # ESTADO_PEDIDO (planilla unica): el codigo compone lo que ya calculo el
    # Provider mas los datos del cliente del lead en UN objeto que sale SIEMPRE
    # completo, cada turno, con todas las claves presentes aunque esten vacias:
    # items con precio_unitario y subtotal, subtotal, envio, total, datos del
    # cliente capturados hasta ahora, faltantes, link con su llave de frescura
    # (el total con que se emitio) y la etapa (consulta/pedido/cierre/capturado).
    # Es el continente del que cuelgan el render por codigo, el delta del carrito
    # y la regeneracion del link. Funcion pura, sin I/O: solo lee el dict del
    # Provider, el lead y la memoria del link. Default off: nadie lo consume aun.
    ESTADO_PEDIDO: bool = (
        os.getenv("ESTADO_PEDIDO", "false").lower() == "true"
    )

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

    # REGISTRO DE SESION DEL RESOLVEDOR (memoria de la cocina). La memoria de
    # texto guarda la prosa del bot (nombre y precio) pero NO el product_id que
    # devolvieron las tools: ese vive solo dentro del turno y se evapora. Por eso
    # en el turno siguiente la calculadora no encuentra el producto que el cliente
    # ya vio. Este registro persiste {id, nombre, precio} de los productos
    # mostrados, igual que proofs_recientes persiste los calculos, y se reinyecta
    # al Solver para que tenga el ID real. Default off, reversible. Gemelo del
    # PROOF_MEMORY de arriba.
    REGISTRO_SESION: bool = os.getenv("REGISTRO_SESION", "false").lower() == "true"
    REGISTRO_SESION_MAX: int = int(os.getenv("REGISTRO_SESION_MAX", "12"))

    # RESOLVEDOR DE PEDIDO POR CODIGO (movimiento 2: el codigo resuelve el HECHO,
    # no el LLM). Usa el registro de sesion para decidir a que producto se refiere
    # el cliente y conseguir su id real, sin depender de que el modelo lo recuerde
    # o lo pase bien. Es lo que convierte las ventas que se caen por id perdido en
    # cierres. Default off, reversible. Necesita REGISTRO_SESION on para tener de
    # donde resolver.
    RESOLVER_PEDIDO: bool = os.getenv("RESOLVER_PEDIDO", "false").lower() == "true"

    # COTIZADOR POR CODIGO (movimiento 2 puro): cuando el cliente quiere precio o
    # cerrar sobre un producto ya visto, el codigo resuelve el id y llama
    # calculate_total el mismo, y le pasa al Solver el presupuesto ya hecho para
    # que solo lo redacte. El numero no pasa por el LLM y se ahorra la vuelta de
    # tool calling del Solver. Default off. Necesita REGISTRO_SESION on.
    COTIZA_CODIGO: bool = os.getenv("COTIZA_CODIGO", "false").lower() == "true"

    # PRESUPUESTO A/B POR CODIGO: cuando el cliente quiere cotizar pero su
    # referencia matchea DOS productos del registro (hoy el cotizador devuelve
    # None y el Solver improvisa), el codigo arma LOS DOS presupuestos y el
    # Solver solo los presenta como opcion A y opcion B preguntando cual
    # prefiere. Decision de arquitectura de Martin: ante la duda, dos precios
    # siempre antes que esperar confirmacion. Tres o mas candidatos sigue
    # siendo ambiguo de verdad: no se cotiza. Default off. Necesita
    # COTIZA_CODIGO y REGISTRO_SESION on.
    PRESUPUESTO_AB: bool = os.getenv("PRESUPUESTO_AB", "false").lower() == "true"

    # MEDIO DE PAGO EN EL COTIZADOR: si el cliente nombra la transferencia
    # ("pago por transferencia", "con transferencia cuanto queda"), el cotizador
    # por codigo suma el descuento de la FAQ descuento_transferencia al calculo.
    # El concepto se lee de la FAQ de la tienda (store-agnostico); si la tienda
    # no tiene ese descuento, se cotiza sin el, nunca se pierde el presupuesto.
    # Default off.
    COTIZA_TRANSFERENCIA: bool = (
        os.getenv("COTIZA_TRANSFERENCIA", "false").lower() == "true"
    )

    # COMPUERTA UNICA (movimiento 3): flag maestro. Cuando on, el orchestrator
    # corre SOLO la compuerta (plata + servicios + hechos en una pasada contra la
    # fuente) y SALTEA todo el bloque viejo de gates: verificador, servicios,
    # hechos por separado, checker LLM, gate por gravedad, libro y guarda. O sea
    # desconecta las 14 capas de un switch, reversible. En off, conducta de hoy.
    COMPUERTA_UNICA: bool = os.getenv("COMPUERTA_UNICA", "false").lower() == "true"

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

    # PROMPT LIVIANO. El system prompt pesado (9 mega-reglas) le pide al modelo
    # custodiar cada dato con parrafos de amenazas, trabajo que el codigo YA hace
    # (verificador de numeros, calculadora, corrector). Esa carga redundante es lo
    # que lo hace fallar y motiva mas parches. Con el flag on, el Solver usa un
    # template corto (~35 lineas) que conserva venta, frases puente, opcion A/B y
    # confirmacion, y delega la custodia del HECHO al codigo. Clave: cuando la tool
    # no trae el dato, el modelo RELATA el veredicto de la tool (dos candidatos =
    # A/B, nada = pregunta corta o fallback) en vez de adivinar su propia ignorancia.
    # Default false: prod usa el prompt pesado. Se mide con A/B en el molino antes
    # de prenderlo. Convive con PROMPT_VENTA (en liviano la venta ya viene adentro).
    PROMPT_LIGERO: bool = os.getenv("PROMPT_LIGERO", "false").lower() == "true"

    # PUENTES DE VENTA. Cuando el sistema NO tiene el dato (no hay precio, no
    # entiende, servicio inexistente) hoy devuelve un fallback seco que corta la
    # venta. Con el flag on, ese fallback se reemplaza por un PUENTE: una frase que
    # mantiene viva la conversacion SIN inventar un hecho (ofrece lo que si hay,
    # ofrece consultar). Las frases son DATO (data/puentes.json, editable sin
    # deploy), no codigo. Regla dura: un puente NUNCA introduce un hecho. Si el
    # cliente INSISTE con el mismo hueco (umbral configurable), el puente escala y
    # deriva a asesor humano. Default false: el fallback se comporta igual que hoy.
    PUENTES_VENTA: bool = os.getenv("PUENTES_VENTA", "false").lower() == "true"

    # TOOLS MINIMAS (tier standard). 14 herramientas son 14 decisiones que el LLM
    # toma antes de responder; varias el modelo las puede pensar solo. Con el flag
    # on, NO se le muestran al LLM las tools que son razonamiento (find_within_budget,
    # compare_products, recommend_product) ni la redundante cubre_envio (cotizar_envio
    # ya resuelve cobertura). Quedan las que traen un HECHO de la fuente: search,
    # details, calculate_total, query_faq, list_catalog y cotizar_envio. Las funciones
    # SIGUEN en el registry (si algo las llama no rompe), solo desaparecen del schema.
    # Default false: el modelo ve todas, como hoy. Reversible.
    TOOLS_MINIMAS: bool = os.getenv("TOOLS_MINIMAS", "false").lower() == "true"

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
        os.getenv("CIERRE_FORZADO_MAX_ITER", "true").lower() == "true"
    )

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

    # Compuerta de stock en el Provider. Visto en prod 12-jun (teclados): la
    # calculadora cotizo 3 unidades de un producto con stock 0 y el contrato
    # ordenaba venderlo mientras la FICHA decia stock 0 — el Solver narro
    # contradicciones ("SI tenemos stock... tiene 0 unidades, no hay problema").
    # Con el flag activo, si el stock del foco o de un item del carrito no
    # alcanza, el contrato ordena NO confirmar la venta y ofrecer alternativa.
    # false: identico al previo.
    STOCK_GATE: bool = os.getenv("STOCK_GATE", "false").lower() == "true"

    # Vencimiento de la memoria de COMPRA en horas (0 = sin vencimiento,
    # identico al previo). Pasado el plazo desde el ultimo turno, el presupuesto
    # en memoria, el carrito vigente y la ultima localidad se descartan: una
    # charla vieja no cierra una venta de hoy ni aporta direccion fantasma.
    # El historial de texto y los productos vistos NO vencen.
    MEMORIA_TTL_HORAS: float = float(os.getenv("MEMORIA_TTL_HORAS", "0"))

    # Provider mas potente: lee pedidos combinados NUEVOS del mensaje por
    # codigo ("2 mouses y dos tablets") y los cierra enteros en el contrato.
    # Caso Esteban 12-jun: sin esto el contrato viajaba sin total y el Solver
    # caia a su respaldo (llamar la calculadora y redactar el resultado).
    # Ante ambiguedad (varios colores/modelos) NO adivina: lista las opciones
    # reales y ordena preguntar. false: identico al previo.
    PEDIDO_MULTI: bool = (
        os.getenv("PEDIDO_MULTI", "false").lower() == "true"
    )

    # CARRITO_DELTA: el codigo lee el CAMBIO sobre el carrito existente y lo muta
    # por codigo ("agrega un mouse", "saca el teclado", "mejor 3 en vez de 2"),
    # en vez de delegarlo al Solver (hoy el contrato le dice "parti de estos ids,
    # saca o cambia cantidades" y el modelo ejecuta). Tres operaciones: agregar
    # (resuelto contra el catalogo, reusa extraer_pedido), sacar y cambiar
    # cantidad (apuntados contra el carrito por categoria). Ante ambiguedad NO
    # adivina: lista las opciones y ordena preguntar. Funcion pura, testeable
    # offline. Alimenta el estado unico, que recalcula con los ids nuevos.
    # false: identico al previo.
    CARRITO_DELTA: bool = (
        os.getenv("CARRITO_DELTA", "false").lower() == "true"
    )

    # RENDER_CODIGO: el bloque numerico verificado lo ESTAMPA el codigo en la
    # respuesta, no lo transcribe el Solver. El Solver deja un marcador donde van
    # los numeros y el codigo lo reemplaza por la presentacion verificada; si el
    # modelo ignora el marcador, el codigo saca el presupuesto que el Solver
    # escribio a mano y estampa el verificado igual. Asi el numero llega limpio
    # pase lo que pase con el modelo, condicion para poner un Solver economico.
    # Funcion pura (app/core/render.py). false: identico al previo (el contrato
    # le sigue pidiendo al Solver copiar TAL CUAL y la compuerta corrige despues).
    RENDER_CODIGO: bool = (
        os.getenv("RENDER_CODIGO", "false").lower() == "true"
    )

    # CONFIRMACION_PROVIDER: la PREGUNTA DE CONFIRMACION (A_o_B, te_referis_a) la
    # arma el CODIGO desde los candidatos reales que el Provider ya tiene en mano
    # (ab de foco, ambiguos de multi), no el Solver. La señal tipo_confirmacion
    # del interprete entra como PISTA, no como veredicto: el codigo decide si
    # pregunta segun lo que el catalogo realmente dio (si el interprete marco
    # ambiguo pero el catalogo resolvio a uno, NO pregunta). La confirmacion pasa
    # a ser un campo SIEMPRE-PRESENTE (necesita=False y vacio cuando no hace
    # falta), misma disciplina que estado_pedido: nunca null. Funcion pura
    # (app/core/confirmacion.py). false: identico al previo (el Solver arma la
    # pregunta desde las secciones ambiguos del contrato).
    CONFIRMACION_PROVIDER: bool = (
        os.getenv("CONFIRMACION_PROVIDER", "true").lower() == "true"
    )

    # INTENCION_MANDA: el mensaje NUEVO manda sobre el estado guardado. Cuando el
    # interprete clasifica el turno como pregunta_especifica u otra (NO compra, NO
    # aporta_dato, NO exploracion) y el cliente no toco el carrito este turno, el
    # codigo NO arma la confirmacion pre-Solver ni le inyecta el presupuesto/carrito
    # vigente al Solver: lo deja contestar la pregunta a secas. Visto en prod
    # 15-jun (charla real): el presupuesto vigente ("2x Mouse M170") se arrastraba
    # y se re-estampaba en CADA turno, tapando "donde aprieto el boton", "no es eso",
    # "lee mi pregunta", y el A/B crudo respondia a preguntas y hasta pedidos
    # ilegales. El carrito NO se borra (sigue en memoria); solo deja de re-mostrarse
    # cuando el cliente esta preguntando. Confirmacion y puentes quedan intactos:
    # solo dejan de saltar cuando no corresponde. false: identico al previo.
    INTENCION_MANDA: bool = (
        os.getenv("INTENCION_MANDA", "false").lower() == "true"
    )

    # DIRECTOR_LLM: el LLM gobierna la caneria determinista. El interprete, en la
    # MISMA llamada que ya hace (sin sumar latencia), emite ACCIONES sobre el
    # carrito (agregar/sacar/cambiar_cantidad/vaciar) y el codigo las ejecuta
    # contra el catalogo real (app/core/director.py). El LLM decide el QUE; el
    # codigo sigue dueno del HECHO (id, precio, stock) y verifica al final.
    # Reemplaza la decision-por-codigo de cuando acoplar/desacoplar el carrito
    # (carrito_delta + arrastre), que era la fuente de los conflictos del Solver.
    # Idea de Martin 15-jun: igual que el LLM interpreta mejor que el codigo, decide
    # mejor que entra y sale del estado en cada turno. false: identico al previo
    # (el interprete no emite acciones y el carrito se maneja como hoy).
    DIRECTOR_LLM: bool = (
        os.getenv("DIRECTOR_LLM", "true").lower() == "true"
    )

    # CAMINO_NUEVO: la columna limpia de cinco pasos (app/core/camino_nuevo.py).
    # Reemplaza el orchestrator viejo entero por la caneria determinista que ya
    # existe en piezas verdes, sin las ~14 capas legacy que competian. Flujo:
    # interprete (LLM 1, emite acciones) -> director aplica al carrito -> provider
    # resuelve el hecho -> estado_pedido arma la planilla unica -> redactor (LLM 2)
    # viste y render estampa el numero verificado. Dos llamadas LLM por mensaje.
    # El cierre y el link los maneja la capa de leads que ya existe.
    # Idea de Martin 15-jun: el LLM decide que entra y sale del estado, el codigo
    # sigue dueno del hecho. true: el orchestrator delega TODO el turno a esta
    # columna y apaga el pipeline viejo. false: identico al previo (no corre).
    CAMINO_NUEVO: bool = (
        os.getenv("CAMINO_NUEVO", "false").lower() == "true"
    )

    # MODO_LIBRE: el experimento de Martin (16-jun). El modelo LLM responde LIBRE,
    # sin ninguna de las ~14 capas (interprete, nucleo, faq directo, provider,
    # verificadores, corrector, gate, leads). Lo unico que lo ata es que las tools
    # que ve (search_products, query_faq, list_catalog, get_product_details,
    # calculate_total) leen de Firestore: catalogo y FAQs reales. Prompt corto de
    # venta, sin parrafos defensivos. Idea: primero VER al modelo vender bien y
    # libre, despues filtrar/editar SOLO cuando alucine. El turno entero lo maneja
    # app/core/modo_libre.py, igual que CAMINO_NUEVO desvia el turno.
    # Se prende con MODO_LIBRE=true + LLM_PROVIDER=gemini + GEMINI_API_KEY.
    # true: el orchestrator delega TODO a modo_libre y apaga el pipeline viejo.
    # false: identico al previo (no corre, el bot actual queda intacto).
    MODO_LIBRE: bool = (
        os.getenv("MODO_LIBRE", "false").lower() == "true"
    )

    # Tools que ve el solver libre (MODO_LIBRE y el camino vivo SOLO_INTERPRETE).
    # Solo las que traen un HECHO real determinista: catalogo (search/details/list/
    # calculate_total), FAQs (query_faq) y envio (cotizar_envio, el codigo clasifica
    # la zona por CP y devuelve la tarifa de la tienda). Se le ocultan las de
    # razonamiento puro (find_within_budget, compare, recommend). Editable por env.
    MODO_LIBRE_TOOLS: str = os.getenv(
        "MODO_LIBRE_TOOLS",
        "search_products,get_product_details,list_catalog,query_faq,"
        "calculate_total,cotizar_envio")

    # Saludo respondido por codigo cuando el interprete lo marca con confianza
    # alta y el mensaje es corto y sin numeros. Visto 12-jun: "nueva compra"
    # paso por el Solver, que volco el presupuesto viejo e invento el umbral
    # del envio gratis -> bloqueo del juez -> fallback. Un saludo no tiene
    # numeros que ganar y si que perder. false: identico al previo.
    SALUDO_CODIGO: bool = (
        os.getenv("SALUDO_CODIGO", "false").lower() == "true"
    )

    # Pedido GENERICO de catalogo ("dame el catalogo", "que categorias tenes",
    # "lista completa") respondido por CODIGO con las categorias reales y su
    # conteo, no por el Solver. Visto en prod 14-jun: "dam el catalogo" -> el
    # Solver dijo "ahi tenes el catalogo, 880 productos" SIN listar nada (a veces
    # enumera, a veces no: variacion del modelo). Un pedido determinista lo
    # contesta el codigo, igual que el saludo. Conservador: solo dispara con
    # frases claras de catalogo/categorias, no con "que teclados tenes" (eso es
    # busqueda de categoria puntual). false: identico al previo.
    CATALOGO_CODIGO: bool = (
        os.getenv("CATALOGO_CODIGO", "false").lower() == "true"
    )

    # SOLVER_CODIGO (fallback sin LLM): si el Solver cae a fallback/vacio (el
    # modelo se colgo, agoto iteraciones o devolvio el mensaje tecnico), el
    # redactor por codigo (app/core/responder_codigo.py) arma la respuesta desde
    # el contrato del Provider + la planilla, deterministico y sin inventar. Asi
    # una consulta normal no muere en "problema tecnico" por una falla del
    # modelo. Solo actua cuando el Solver YA fallo: el camino feliz no se toca.
    # Es la mitad redactora del modo sin-LLM. false: identico al previo.
    SOLVER_CODIGO: bool = (
        os.getenv("SOLVER_CODIGO", "false").lower() == "true"
    )

    # SOLVER_CODIGO_PRIMARIO: el redactor por codigo responde SIEMPRE que el
    # contrato tenga dato, SALTEANDO el Solver (no solo en fallback). Mantiene el
    # interprete LLM (que es bueno); reemplaza solo al Solver. Da respuestas
    # deterministicas y roboticas (sin prosa de venta), gratis y reproducibles:
    # es el modo sin-LLM para probar el espinazo y como piso duro. Si el contrato
    # NO tiene dato (responder da None), cae al Solver normal. Default false:
    # prod usa el Solver. Pensado para prender en ventanas de prueba.
    SOLVER_CODIGO_PRIMARIO: bool = (
        os.getenv("SOLVER_CODIGO_PRIMARIO", "false").lower() == "true"
    )

    # "Nueva compra" / "empezar de cero" / "borra el pedido" descarta por
    # codigo TODA la memoria de compra (presupuesto, carrito, localidad,
    # proofs, productos vistos) Y el historial de texto, que es donde viven
    # los datos fantasma (la direccion "Arenales" de otra charla). Visto en
    # prod 12-jun: dos "nueva compra" seguidos y el bot re-vendio el pedido
    # viejo, porque ninguna pieza tenia la orden de soltarlo; el TTL de 12h
    # no cubre el pedido explicito del cliente. Si el mensaje es SOLO la
    # frase, se responde por codigo sin Solver; si ademas trae el pedido
    # nuevo, sigue el pipeline normal ya limpio. false: identico al previo.
    NUEVA_COMPRA_RESET: bool = (
        os.getenv("NUEVA_COMPRA_RESET", "false").lower() == "true"
    )

    # Codigo secreto de reset para pruebas. Si el mensaje del usuario es
    # exactamente este texto (case-insensitive, sin espacios extra), se borra
    # toda la conversacion y el sistema responde confirmando el reset.
    # Util para testear sin usar numeros distintos ni mecanismos de produccion.
    # Cambiar el valor si se quiere rotar el codigo. "" = desactivado.
    RESET_CODE: str = os.getenv("RESET_CODE", "verifika2026")

    # Limpieza de consulta del Provider: las palabras de PLATA y PEDIDO (total,
    # pedido, presupuesto, era, monto) salen de la busqueda, y si despues de
    # limpiar no queda NADA que describa un producto, no se busca (antes caia
    # al mensaje crudo y sembraba evidencia basura). Visto 12-jun: "cuanto era
    # el total de mi pedido?" sin pedido vigente matcheo 14 productos al azar
    # y el Solver fabrico un total de $142.000 con recibo y todo. De paso las
    # palabras cortas reales ("tv", "pc") sobreviven a la limpieza: los
    # articulos caen por lista, no por longitud. false: identico al previo.
    QUERY_PLATA_FUERA: bool = (
        os.getenv("QUERY_PLATA_FUERA", "false").lower() == "true"
    )

    # El pedido a medio armar PERSISTE entre turnos y la eleccion del cliente
    # lo completa por codigo. Visto en prod 12-jun noche (charla Martin): "2
    # mauses y dos teclados" quedo ambiguo (varios modelos), el bot pregunto
    # cuales, el cliente contesto "los baratos, armame la lista" y nadie junto
    # las dos mitades: sin carrito ni total, el cierre pidio datos sin precio
    # y "cuanto salen" termino en fallback. Con el flag, el Provider guarda
    # {items resueltos + terminos ambiguos con cantidad} y al turno siguiente,
    # si el cliente da criterio (barato/cualquiera/armame la lista), resuelve
    # cada termino al MAS BARATO CON STOCK, cotiza entero con envio y el
    # contrato viaja con el total cerrado. false: identico al previo.
    PEDIDO_PENDIENTE: bool = (
        os.getenv("PEDIDO_PENDIENTE", "false").lower() == "true"
    )

    # El cierre NO pide datos (nombre/telefono/pago) si la conversacion no
    # tiene presupuesto ni carrito: pedir datos para cerrar una venta sin
    # total es incoherente y quema confianza (visto en prod 12-jun noche:
    # "armame la lista" -> "me pasas tu nombre y forma de pago?" sin haber
    # dado JAMAS un precio). El lead ya queda registrado; el pedido de datos
    # se pospone al turno con precio. false: identico al previo.
    CIERRE_REQUIERE_PRESUPUESTO: bool = (
        os.getenv("CIERRE_REQUIERE_PRESUPUESTO", "false").lower() == "true"
    )

    # Los productos YA MOSTRADOS (registro de sesion, guardados por codigo con
    # id y precio reales del catalogo) entran a la evidencia del juez. Repetir
    # un precio que el bot ya mostro no puede ser alucinacion del valor; sin
    # esto el juez veta en falso la clarificacion que cita opciones del turno
    # anterior (visto 12-jun noche: "G502 a $70.000" precio REAL, bloqueado
    # por carpeta incompleta -> puente en vez de pregunta). Es la clase
    # "falso positivo por evidencia incompleta". false: identico al previo.
    EVIDENCIA_REGISTRO: bool = (
        os.getenv("EVIDENCIA_REGISTRO", "false").lower() == "true"
    )

    # NOTA: la siembra inicial del cierre (ex flag CIERRE_SIEMBRA_INICIAL) ya es el
    # UNICO camino en leads.py: al disparar el cierre con presupuesto, el lead se
    # siembra con los datos que ya trae el mensaje (nombre, telefono, direccion,
    # forma de pago); si estan los cuatro cierra ya, si falta pide solo lo que
    # falta. Consolidada 25-jun.

    # Leads no pide datos sobre un fallback. Visto en prod 11-jun: el verificador
    # bloqueo la respuesta (fallback "dejame consultar") y la capa de leads igual
    # mando "pasame tu nombre y telefono" — incoherente: el bot dice "no se" y
    # pide datos para cerrar en el mismo turno. Con el flag activo, si el turno
    # termino en fallback se POSPONE el pedido de datos (el lead ya quedo
    # registrado; se piden al turno siguiente). false: identico al previo.
    LEADS_NO_PIDE_EN_FALLBACK: bool = (
        os.getenv("LEADS_NO_PIDE_EN_FALLBACK", "false").lower() == "true"
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
    # AUTOCORRIGE — correccion determinista del total (Fase 1)
    # ────────────────────────────────────────────────────────
    # Partida doble de la verdad, primer corte. Cuando el verificador determinista
    # bloquea por una cifra de TOTAL sin respaldo, antes de repromptear (AUTOFIX) o
    # tirar el fallback, el codigo intenta REESCRIBIR esa cifra por el total
    # verdadero de la evidencia, sin llamar a ningun modelo. Solo corrige cuando el
    # reemplazo es inequivoco: un unico total valido del PROOF dentro de +-30% de la
    # cifra mala. Si hay ambiguedad, no toca nada y sigue el flujo de siempre. Corre
    # ANTES de AUTOFIX: si la correccion deja la respuesta verificable, se evita la
    # corrida LLM extra. Codigo puro en app/core/verificador.py (autocorregir_montos).
    # Default false: prod identico. Requiere VERIFICADOR_MODE=on para tener efecto.
    VERIFICADOR_AUTOCORRIGE: bool = (
        os.getenv("VERIFICADOR_AUTOCORRIGE", "false").lower() == "true"
    )

    # ────────────────────────────────────────────────────────
    # LIBRO_ASIENTOS — libro de asientos de numeros (Fase 2)
    # ────────────────────────────────────────────────────────
    # Partida doble de la verdad, segundo corte. El Solver, ademas de la prosa,
    # declara al final un LIBRO con cada CIFRA DE DINERO que afirmo, como asientos
    # {valor, fuente, que es}. El codigo (app/core/libro.py) extrae el bloque, lo
    # saca del texto antes de mostrar nada, y audita cada asiento contra la
    # evidencia: cuadra -> lo deja; valor mal pero la verdad esta en su fuente ->
    # lo REESCRIBE por el verdadero; sin respaldo -> queda como problema y lo frena
    # el piso duro. Mejora a VERIFICADOR_AUTOCORRIGE: cada cifra viene etiquetada
    # con su fuente, asi la correccion es precisa (precio vs total vs envio) en vez
    # de adivinar. Solo cubre NUMEROS. Default false: prod identico (el prompt del
    # Solver no cambia si esta off). Pensado para correr junto a VERIFICADOR_MODE=on.
    LIBRO_ASIENTOS: bool = os.getenv("LIBRO_ASIENTOS", "false").lower() == "true"

    # ────────────────────────────────────────────────────────
    # RESOLVER_ASPECTOS — pieza 2: el codigo resuelve cada campo del objeto de
    # comprension contra la fuente (catalogo, tablas, sesion). Empieza por la
    # LOCALIDAD contra el motor de envio: ademas de clasificar la zona, detecta
    # los nombres AMBIGUOS (san justo, capital sola, santa ana) que hoy el codigo
    # resuelve en silencio al cajon equivocado, y devuelve "necesita confirmacion"
    # con las provincias candidatas en vez de adivinar. El LLM extrae el nombre
    # tal cual; el codigo decide si lo resuelve o pregunta. Funcion pura, testeable
    # offline (app/core/resolver_aspectos.py). Default off: nadie lo consume aun.
    RESOLVER_ASPECTOS: bool = (
        os.getenv("RESOLVER_ASPECTOS", "false").lower() == "true"
    )

    # ────────────────────────────────────────────────────────
    # MOTOR_ENTRADA — el pequeño motor de 3 pasos, base de Verifika mejorado:
    # comprender (LLM, app/core/comprension.py) -> resolver (codigo,
    # resolver_aspectos) -> responder simple (codigo, responder_simple). El LLM
    # estructura la PREGUNTA, el codigo manda en el DATO y la RESPUESTA. Sin
    # verificador ni compuerta: esa capa se suma despues, encima de esta base.
    # app/core/motor_entrada.py. Default off: nadie lo consume aun.
    MOTOR_ENTRADA: bool = os.getenv("MOTOR_ENTRADA", "false").lower() == "true"

    # De donde sale el libro de asientos (resuelve el 75% de emision del Solver):
    #   solver    -> el Solver lo pega al final de su respuesta (lo actual). Falla
    #                ~25% porque el Solver esta sobrecargado.
    #   extractor -> el Solver responde LIBRE y una llamada LLM DEDICADA (rol
    #                corrector) extrae el libro de la prosa. +1 llamada, ~100% cobertura.
    #   fusion    -> el Solver responde LIBRE y la pasada del corrector anclado que
    #                YA corre se reusa para extraer el libro (no reescribe prosa).
    #                Sin llamadas extra respecto al baseline con CORRECTOR_ANCLADO on.
    # Solo aplica con LIBRO_ASIENTOS on. Default solver (conducta de siempre).
    LIBRO_MODO: str = os.getenv("LIBRO_MODO", "solver").lower()

    # NOTA: cotizar_envio (ex flag ENVIO_POR_ZONA) es ahora un tool SIEMPRE
    # presente: el CODIGO clasifica la zona desde el CP o la localidad y devuelve
    # la tarifa de la tienda; el modelo nunca elige la zona. Consolidada 24-jun.
    # cubre_envio se elimino: cotizar_envio ya implica cobertura.

    # ────────────────────────────────────────────────────────
    # FECHA_ENTREGA — tool determinista de plazo/fecha de entrega
    # ────────────────────────────────────────────────────────
    # Mata el caso (b): el bot prometiendo un dia exacto de entrega. Con el flag on
    # aparece calcular_entrega: el CODIGO toma la zona (por CP) y el plazo de la
    # tienda en dias habiles, saltea fines de semana y feriados (app/core/entrega.py)
    # y devuelve una VENTANA estimada, siempre como estimacion no garantizada. El
    # modelo nunca promete una fecha. Motor generico (calendario habil argentino) +
    # dato de tienda (plazo por zona). Default false.
    FECHA_ENTREGA: bool = os.getenv("FECHA_ENTREGA", "false").lower() == "true"

    # ────────────────────────────────────────────────────────
    # POSVENTA_TOOLS — plazos de devolucion/garantia + validacion CUIT
    # ────────────────────────────────────────────────────────
    # Cierra la naturaleza 1 (calculo determinista). Con el flag on aparecen:
    # plazo_devolucion (dias corridos desde la compra), garantia_vigente (meses del
    # producto) y validar_cuit (digito verificador, para factura A y confianza).
    # El codigo calcula la fecha limite y si esta vigente; el modelo no improvisa
    # fechas ni afirma garantia sin base. Motor generico + dato de tienda. En
    # app/core/posventa.py. Default false.
    POSVENTA_TOOLS: bool = os.getenv("POSVENTA_TOOLS", "false").lower() == "true"

    # ────────────────────────────────────────────────────────
    # GUARDA_COMPLETITUD — red anti-Solver del libro (Fase 4)
    # ────────────────────────────────────────────────────────
    # El libro es el UNICO canal de hechos de plata. La guarda corre el extractor
    # propio del codigo sobre la prosa final y exige que cada cifra de dinero pase
    # por el libro aprobado (o sea suma de sus valores). Una cifra que aparece en el
    # texto y no esta en el libro es una FUGA, aunque exista en la evidencia: caza
    # el contrabando (numero real en cajon equivocado) que el verificador de plata
    # no ve porque ese numero SI tiene respaldo en alguna fuente. Codigo puro en
    # app/core/libro.py (guarda_completitud). Solo tiene sentido con LIBRO_ASIENTOS
    # on (necesita el libro).
    # Modos:
    #   off    -> no corre (prod identico).
    #   shadow -> corre y loguea (guarda_completitud_shadow), NO bloquea. OBLIGATORIO
    #             primero: si el Solver declara libros incompletos, mide cuantas
    #             respuestas buenas se bloquearian antes de prender on.
    #   on     -> bloquea: si hay fuga, cae al fallback (una fuga no se recalcula).
    GUARDA_COMPLETITUD: str = os.getenv("GUARDA_COMPLETITUD", "off").lower()

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
    # 2.0-flash no razona; solo los 2.5+ lo traen prendido por default.
    return {"reasoning_effort": "none"} if "2.5" in m else {}


def deepseek_pensando(model_name: str) -> bool:
    """True si esta llamada va a ir en modo razonador: modelo v4 y thinking on."""
    return "v4" in (model_name or "").lower() and get_settings().DEEPSEEK_THINKING
