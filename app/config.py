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

    # NOTA: la busqueda relajada (ex flag BUSQUEDA_RELAJADA) ya es el UNICO camino
    # de search_products, cableada en app/core/tools.py. Tapaba "0 ventas por negar
    # stock que existe". Consolidada 24-jun: dejo de ser flag.

    # NOTA: el matcheo de FAQ por palabras (ex flag FAQ_MATCH_PALABRAS) ya es el
    # UNICO camino de query_faq, cableado en app/core/tools.py: el tema especifico
    # gana al generico y la respuesta lleva temas relacionados. Consolidado 24-jun.
    # Proveedor del embedding: openai (con OPENAI_API_KEY) o deepseek (legacy).
    EMBEDDINGS_PROVIDER: str = os.getenv("EMBEDDINGS_PROVIDER", "openai").lower()
    EMBEDDINGS_MODEL: str = os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-small")

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

    # Cuantos PROOF recientes arrastrar entre turnos, para que en la confirmacion
    # ("si, dale") el total repetido siga teniendo respaldo. Acompaña la memoria
    # de la conversacion y el reconocimiento del estado de compra.
    VERIFICADOR_PROOF_MEMORY: int = int(os.getenv("VERIFICADOR_PROOF_MEMORY", "7"))

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

    # TOOLS MINIMAS (tier standard). 14 herramientas son 14 decisiones que el LLM
    # toma antes de responder; varias el modelo las puede pensar solo. Con el flag
    # on, NO se le muestran al LLM las tools que son razonamiento (find_within_budget,
    # compare_products, recommend_product) ni la redundante cubre_envio (cotizar_envio
    # ya resuelve cobertura). Quedan las que traen un HECHO de la fuente: search,
    # details, calculate_total, query_faq, list_catalog y cotizar_envio. Las funciones
    # SIGUEN en el registry (si algo las llama no rompe), solo desaparecen del schema.
    # Default false: el modelo ve todas, como hoy. Reversible.
    TOOLS_MINIMAS: bool = os.getenv("TOOLS_MINIMAS", "false").lower() == "true"

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

    # Tools que ve el solver libre (MODO_LIBRE y el camino vivo SOLO_INTERPRETE).
    # Solo las que traen un HECHO real determinista: catalogo (search/details/list/
    # calculate_total), FAQs (query_faq) y envio (cotizar_envio, el codigo clasifica
    # la zona por CP y devuelve la tarifa de la tienda). Se le ocultan las de
    # razonamiento puro (find_within_budget, compare, recommend). Editable por env.
    MODO_LIBRE_TOOLS: str = os.getenv(
        "MODO_LIBRE_TOOLS",
        "search_products,get_product_details,list_catalog,query_faq,"
        "calculate_total,cotizar_envio")

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
