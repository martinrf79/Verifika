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

    # Limpieza de markdown en la respuesta final (asteriscos, viñetas, encabezados).
    # Telegram y WhatsApp se mandan en texto plano: el markdown se ve roto.
    # Si algo sale mal, poner CLEAN_MARKDOWN=false y vuelve al comportamiento previo.
    CLEAN_MARKDOWN: bool = os.getenv("CLEAN_MARKDOWN", "true").lower() == "true"

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

    # Evidencia del Checker construida desde los resultados REALES de las tools
    # (lo que vio el Solver) en vez de releer todo el catálogo de Firestore.
    # Conecta bien las capas Solver→Checker y baja costo en tokens.
    # Si bloquea de más, poner VERIFIKA_EVIDENCE_FROM_TOOLS=false y vuelve a
    # la evidencia vieja (catálogo completo).
    VERIFIKA_EVIDENCE_FROM_TOOLS: bool = (
        os.getenv("VERIFIKA_EVIDENCE_FROM_TOOLS", "true").lower() == "true"
    )

    # ────────────────────────────────────────────────────────
    # ESCALABILIDAD — no bloquear el event loop
    # ────────────────────────────────────────────────────────

    # Los clientes LLM son SINCRONOS (cliente OpenAI sync). Cuando se los llama
    # dentro de un handler async de FastAPI, la llamada de red bloquea TODO el
    # server mientras espera la respuesta del modelo, que tarda segundos. Con un
    # solo usuario no se nota, pero con varios en paralelo se encolan: el segundo
    # espera a que termine el primero. Esto manda la llamada bloqueante a un
    # thread con asyncio.to_thread, asi el event loop sigue libre y los requests
    # se atienden de a varios. to_thread copia el contexto (contextvars), asi que
    # la tienda actual se sigue resolviendo bien dentro del thread.
    # Si algo sale mal, poner ASYNC_LLM_OFFLOAD=false y vuelve al comportamiento
    # previo (bloqueante).
    ASYNC_LLM_OFFLOAD: bool = (
        os.getenv("ASYNC_LLM_OFFLOAD", "true").lower() == "true"
    )

    # ────────────────────────────────────────────────────────
    # CAPA DE PRODUCTO — herramientas del agente de ventas
    # ────────────────────────────────────────────────────────

    # Calculo de extras porcentuales en calculate_total (descuentos, recargos).
    # Antes la calculadora solo manejaba montos fijos en pesos y rangos: un
    # descuento de 10 por ciento, guardado como monto 10 con unidad porcentaje,
    # se sumaba como 10 pesos en vez de restar el 10 por ciento del subtotal.
    # Con el flag activo lee el campo unidad: si es porcentaje, calcula el monto
    # sobre el subtotal de productos y, si es descuento, lo resta.
    # false vuelve al comportamiento viejo (todo como monto fijo en pesos).
    CALC_PORCENTAJES: bool = os.getenv("CALC_PORCENTAJES", "true").lower() == "true"

    # Envio gratis automatico por umbral. Si el subtotal de PRODUCTOS supera
    # UMBRAL_ENVIO_GRATIS, la calculadora pone el envio en gratis sola, sin
    # importar el concepto de envio que pida el Solver. Asi el total final sale
    # entero y deterministico de la calculadora (con envio gratis + descuento ya
    # aplicados), el Solver solo lo copia y el verificador no bloquea numeros
    # improvisados. Era la causa de los fallback en cierres con compra grande.
    # false vuelve al comportamiento previo (el envio depende del concepto).
    ENVIO_GRATIS_AUTO: bool = (
        os.getenv("ENVIO_GRATIS_AUTO", "true").lower() == "true"
    )
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

    # Interpretacion rica (Defensa 1). El interprete devuelve, ademas de los
    # campos de hoy, un esquema cerrado con los slots del mensaje: intenciones en
    # lista, items con cantidad y confianza, destinos con cajon razonado y
    # confianza, atributo consultado, forma de pago, pide_descuento y la lista de
    # ambiguedades (slots decisivos con confianza baja). El objetivo es que el
    # Solver reciba el detalle ya interpretado y adivine menos, y que las
    # ambiguedades disparen una confirmacion antes de cotizar. Es un SUPERSET del
    # JSON actual: los campos viejos siguen igual, solo se agregan los nuevos.
    # false: el interprete se comporta exactamente como hoy.
    INTERPRETE_RICO: bool = (
        os.getenv("INTERPRETE_RICO", "false").lower() == "true"
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

    # Herramienta para listar el catalogo completo o de una categoria, para
    # responder "que tenes", "mostrame todo" o "lista completa" sin depender de
    # que la busqueda por keywords enganche. false la saca del schema del LLM y
    # el bot vuelve a depender solo de search_products para mostrar productos.
    TOOL_LISTAR_CATALOGO: bool = (
        os.getenv("TOOL_LISTAR_CATALOGO", "true").lower() == "true"
    )

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
    # ROBUSTEZ DE VERIFIKA — bajar falsos bloqueos sin aflojar la guardia
    # ────────────────────────────────────────────────────────

    # El Checker solo puede validar lo que ve en la evidencia. Cuando una
    # respuesta toca varios temas de FAQ, formas de pago mas envio, el Solver
    # suele llamar query_faq una sola vez, asi que el resto queda sin evidencia
    # y afirmaciones VERDADERAS caen como sin_evidencia y bloquean. La FAQ es
    # chica, 22 temas, asi que la metemos entera como evidencia siempre.
    # false vuelve a la evidencia de FAQ solo de los temas que query_faq trajo.
    VERIFIKA_FULL_FAQ_EVIDENCE: bool = (
        os.getenv("VERIFIKA_FULL_FAQ_EVIDENCE", "true").lower() == "true"
    )

    # El Proposer a veces convierte una cantidad pedida, el "2x Monitor", en una
    # afirmacion de stock, "hay 2 unidades", que despues contradice el stock real
    # y bloquea. Esta regla le dice al Proposer que las cantidades pedidas NO son
    # stock. Las afirmaciones de stock explicitas se siguen verificando.
    # false saca la regla y vuelve al comportamiento previo.
    PROPOSER_IGNORA_CANTIDAD: bool = (
        os.getenv("PROPOSER_IGNORA_CANTIDAD", "true").lower() == "true"
    )

    # Reconciliacion numerica deterministica. Despues de que el Checker opina,
    # se revisan las afirmaciones que quedaron contradicha o sin_evidencia: si
    # TODAS las cifras de dinero de la afirmacion estan en el PROOF de la
    # calculadora, en un precio del catalogo o en un valor de la FAQ, se corrige
    # a soportada, porque esos numeros ya son verdad por construccion. Si alguna
    # cifra no sale de ninguna fuente, se respeta el veredicto del Checker y se
    # bloquea. Asi una alucinacion numerica se sigue frenando, pero un numero
    # correcto no lo bloquea un error de juicio del modelo. Corta el loop de
    # falsos bloqueos sobre aritmetica. false desactiva la reconciliacion.
    VERIFIKA_RECONCILE_NUMBERS: bool = (
        os.getenv("VERIFIKA_RECONCILE_NUMBERS", "true").lower() == "true"
    )

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
    # Conviene tenerlo con VERIFIKA_FULL_FAQ_EVIDENCE=true (ya en prod) para que la
    # FAQ entera sea la fuente de verdad.
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

    # ────────────────────────────────────────────────────────
    # FASE 1 — la calculadora arma el presupuesto, el Solver lo copia
    # ────────────────────────────────────────────────────────
    # calculate_total devuelve un campo presentacion, el presupuesto ya armado
    # en texto por codigo. Con este flag, el prompt del Solver le ordena copiar
    # ese bloque tal cual y NO calcular ni reescribir numeros. Asi ningun numero
    # sale de la cabeza del modelo. false vuelve al comportamiento previo.
    SOLVER_USA_PRESENTACION: bool = (
        os.getenv("SOLVER_USA_PRESENTACION", "true").lower() == "true"
    )

    # query_faq resuelve por keywords primero, sin llamar al modelo. Si las
    # palabras clave de la FAQ matchean la consulta, devuelve el tema al toque.
    # Si no matchea, cae al modelo como antes. Baja latencia sacando una llamada.
    # false vuelve a usar siempre el modelo como retriever.
    FAQ_KEYWORD_FIRST: bool = (
        os.getenv("FAQ_KEYWORD_FIRST", "true").lower() == "true"
    )

    # ────────────────────────────────────────────────────────
    # CIERRE DE VENTA — captura completa del pedido y datos del cliente
    # ────────────────────────────────────────────────────────
    # Dentro del circuito de leads (USE_LEADS), cuando el cliente confirma,
    # captura nombre, telefono, direccion y forma de pago, guarda el pedido y
    # avisa al dueno con la orden completa. false vuelve a la captura simple de
    # solo nombre y telefono. Requiere USE_LEADS=true para activarse.
    CIERRE_COMPLETO: bool = (
        os.getenv("CIERRE_COMPLETO", "true").lower() == "true"
    )

    # Regla de orden: nunca pedir datos de cierre antes de haber mostrado un
    # presupuesto. Si el cliente larga senial de compra pero todavia no vio un
    # precio, el Solver responde primero el precio y el cierre queda para el
    # turno siguiente. Evita que el bot pida nombre y telefono sin haber pasado
    # el numero. true por default. false vuelve a la conducta anterior.
    CIERRE_PRECIO_PRIMERO: bool = (
        os.getenv("CIERRE_PRECIO_PRIMERO", "true").lower() == "true"
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
