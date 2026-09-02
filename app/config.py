"""Configuración del bot v5 — Firestore + DeepSeek + tools + Verifika."""
import os
from functools import lru_cache
from pydantic import BaseModel


def _mensaje_de_la_fuente(clave: str, defecto: str) -> str:
    """Un mensaje fijo al cliente, leido de `base_conocimiento.json`. Va
    envuelto porque config se importa antes que casi todo y un fallo de lectura
    no puede tumbar el arranque: sin fuente vale el literal de al lado."""
    try:
        from app.core.guia_venta_prosa import mensaje
        return mensaje(clave, defecto)
    except Exception:
        return defecto


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

    # EL PROVIDER DEL CAMINO VIVO. Default GEMINI. El solver, las guardias,
    # la memoria y el extractor del cierre entran por hub_venta._cliente().
    # Los otros proveedores salieron el 2-sep a archivo/config_providers_20260902.py.
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").lower()

    # Groq Whisper, transcripcion de audio. No es el LLM del turno.
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # Gemini: endpoint compatible con OpenAI. Es LA puerta al modelo.
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    # PRODUCCION CLAVADA a gemini-3.1-flash-lite (Martin, 14-jul): el mas barato
    # y el que validamos con el cacheo de contexto (~46 USD/mes por 1000 msgs
    # diarios). NUNCA el alias -latest, que FLOTA y te cambia modelo y costo sin
    # avisar el dia que Google mueve el alias. Se repinea a mano si hace falta.
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    # EL DECISOR PIENSA (Martin, 2-ago). La llamada UNO -que decide que
    # herramienta y con que argumentos- es el paso mas dificil del turno y
    # corria con el pensamiento APAGADO, heredado de cuando el thinking se comia
    # los max_tokens del JSON. Medido el 2-ago: con thinking off el decisor
    # tradujo "el precio no seria tan importante" a orden=caro, ignoro el
    # excluir=china que el esquema ofrece, y cotizo 4 categorias sobre un pedido
    # de 3. Ahora piensa. El REDACTOR sigue sin pensar: escribe con el dato
    # delante y no decide nada.
    # Vacio = mismo modelo que el redactor. Se le pone otro -ej gemini-3-pro-
    # SOLO para el decisor, sin encarecer el turno entero.
    DECISOR_MODEL: str = os.getenv("DECISOR_MODEL", "")
    DECISOR_REASONING: str = os.getenv("DECISOR_REASONING", "low")
    # EL RAZONAMIENTO DEL REDACTOR. Estaba CLAVADO en "none" adentro de
    # `_redactar`. Se saco a config para poder MEDIRLO, y se midio con la clave
    # paga el 5-ago sobre las tres preguntas mas duras.
    #
    # RESULTADO: NO ARREGLO NADA Y COSTO LATENCIA. La falla que se queria
    # atacar -el modelo no aplica la condicion de origen y arranca la respuesta
    # por el muro- salio IGUAL con `low` que con `none`. Lo que cambio fue el
    # tiempo: 7.673 -> 10.098 ms en la pregunta del origen, 4.046 -> 7.161 en la
    # de la notebook, 5.306 -> 5.909 en la difusa. Entre medio segundo y tres
    # segundos por turno, sin mejora medible.
    #
    # Por eso el default vuelve a "none". Queda como config para volver a
    # medirlo cuando cambie el modelo, no como un camino apagado: el valor vivo
    # es el que corre.
    REDACTOR_REASONING: str = os.getenv("REDACTOR_REASONING", "none")
    GEMINI_BASE_URL: str = os.getenv(
        "GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai/")
    # TTL del cache explicito de contexto (system + schema de tools) que usa el
    # solver por el endpoint NATIVO. El prefijo fijo se cachea una vez y se cobra
    # al 10% en cada vuelta del loop; baja la factura ~a la mitad sin cambiar lo
    # que el modelo ve. Se refresca solo al expirar. Config operativa.
    GEMINI_CACHE_TTL_S: int = int(os.getenv("GEMINI_CACHE_TTL_S", "1800"))

    # DECISOR — la llamada UNO de hub_venta, la que elige herramientas. Es config
    # operativa, no un camino nuevo: con DECISOR_BASE_URL vacio el decisor sigue
    # yendo por Gemini exactamente como antes, mismo cliente y mismo modelo. Solo
    # si se setea la base_url el decisor apunta a otro provider compatible con la
    # API de OpenAI (Groq: https://api.groq.com/openai/v1, OpenAI:
    # https://api.openai.com/v1). El REDACTOR, la llamada DOS, NO se toca nunca:
    # sigue en Gemini pase lo que pase.
    # DECISOR_MODEL ya esta declarado arriba, junto al reasoning del decisor.
    DECISOR_BASE_URL: str = os.getenv("DECISOR_BASE_URL", "")
    DECISOR_API_KEY: str = os.getenv("DECISOR_API_KEY", "")

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

    # CUANTO SE ESPERA CUANDO EL PROVEEDOR PIDE ESPERAR. El 429 de la clave
    # gratis de Gemini viene con `retryDelay` -medido el 11-ago: 18 segundos,
    # cuota de 250.000 tokens de entrada por minuto-. Hasta ese tope se respeta
    # el numero que manda el proveedor; mas que eso se corta al toque, porque
    # un cliente esperando no puede quedar colgado un minuto.
    LLM_ESPERA_MAX_S: float = float(os.getenv("LLM_ESPERA_MAX_S", "20"))

    # Mensaje fallback cuando algo falla. Sale de la FUENTE, igual que el de
    # abajo: el literal es solo la red por si el archivo faltara.
    FALLBACK_MESSAGE: str = _mensaje_de_la_fuente(
        "problema_tecnico",
        "Disculpá, tuve un problema técnico. ¿Podés repetirme tu consulta?")

    # ────────────────────────────────────────────────────────
    # VERIFIKA — núcleo verificable
    # ────────────────────────────────────────────────────────

    # Lo que se le dice al cliente cuando el turno no pudo contestar. SIN env
    # que lo pise: la tenia, y una env seteada en Cloud Run habria dejado a la
    # fuente mandando en el repo y sin efecto en produccion, en silencio y sin
    # que ningun test lo notara. El texto sale de la fuente y de ningun otro
    # lado; el literal es la red si el archivo faltara.
    VERIFIKA_FALLBACK_MESSAGE: str = _mensaje_de_la_fuente(
        "sin_dato_confirmado",
        "No tengo esa información confirmada en el catálogo. "
        "Dejame consultar y te confirmo en breve.")

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
    # de calculate_total, cableada en app/core/calculadora.py (normaliza y valida inputs
    # del modelo antes de calcular). Consolidada 24-jun: dejo de ser flag.

    # NOTA: la busqueda relajada (ex flag BUSQUEDA_RELAJADA) ya es el UNICO camino
    # de search_products, cableada en app/core/calculadora.py. Tapaba "0 ventas por negar
    # stock que existe". Consolidada 24-jun: dejo de ser flag.

    # NOTA: el matcheo de FAQ por palabras (ex flag FAQ_MATCH_PALABRAS) ya es el
    # UNICO camino de query_faq, cableado en app/core/calculadora.py: el tema especifico
    # gana al generico y la respuesta lleva temas relacionados. Consolidado 24-jun.
    # EMBEDDINGS_PROVIDER se borro el 30-jul: no lo leia NADIE en todo `app`, y
    # su default "openai" era otra config muerta declarando un proveedor que no
    # se usa. El recall de modelos es determinista, sin embeddings.
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
    # "B" (venta) desde el 20-jul, orden de Martin: el cierre entrega el cobro
    # solo (CBU/alias demo + link generico de Mercado Pago hasta cargar los
    # reales en la config de la tienda). Riesgo: el link demo no cobra plata
    # de verdad; valido mientras el trafico es de prueba.
    MODO_CIERRE: str = os.getenv("MODO_CIERRE", "B").lower()

    # DATOS DE COBRO POR DEFECTO (demo). Config operativa de la tienda, no secreto:
    # la config de Firestore por tienda (cbu/alias/titular_cuenta/banco) PISA estos
    # valores. Estos defaults son de DEMOSTRACION, marcados como tal a proposito para
    # que nadie transfiera plata real a una cuenta de ejemplo; se editan por cliente.
    # Sirven para que en la demo el bot SI mande la modalidad de transferencia aunque
    # la tienda todavia no cargo sus datos reales. Editables por entorno.
    DEMO_CBU: str = os.getenv("DEMO_CBU", "0000000000000000000000")
    DEMO_ALIAS: str = os.getenv("DEMO_ALIAS", "demo.verifika")
    # Apto cliente: el "reemplazar" viejo quedaba a la vista en el cobro demo.
    DEMO_TITULAR: str = os.getenv("DEMO_TITULAR", "Verifika (cuenta demo)")
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
