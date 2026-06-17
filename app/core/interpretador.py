"""
INTERPRETADOR - capa de interpretacion previa al Solver.

Recibe el mensaje del cliente mas contexto enriquecido y devuelve JSON
estructurado para que el orchestrator decida el flujo.

v3: rediseño profundo. Sin listas hardcodeadas. Prompt minimalista
    que confia en el LLM con contexto enriquecido de siete turnos.
    Tres capas de filtro al final: validacion de schema, filtro de
    negacion, downgrade por baja confianza sin candidatos.

v4: prompt liberado. Intencion aporta_dato agregada para respuestas
    con datos concretos. Campo respondiendo_a agregado para detectar
    respuestas a preguntas previas del bot.

Feature flag: USE_INTERPRETER=true para activarlo. False por default.
"""
import os
import json
import re
import asyncio
from openai import OpenAI
from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

USE_INTERPRETER = os.getenv("USE_INTERPRETER", "false").lower() == "true"
UMBRAL_CONFIANZA_ALTA = float(os.getenv("INTERPRETER_UMBRAL_ALTA", "0.85"))
UMBRAL_CONFIANZA_MEDIA = float(os.getenv("INTERPRETER_UMBRAL_MEDIA", "0.6"))

INTENCIONES_VALIDAS = {"saludo", "exploracion", "pregunta_especifica", "aporta_dato",
                        "decision_compra", "otra"}

# Tipos de confirmacion validos (campo tipo_confirmacion, pista del flag
# CONFIRMACION_PROVIDER). Cualquier otra cosa se coerciona a None: el codigo
# decide igual con el catalogo, asi que un valor raro no debe fallar la lectura.
TIPOS_CONFIRMACION_VALIDOS = {"a_o_b", "te_referis_a", "confirmar_compra"}

# Estados que indican una charla YA en curso. Si la conversacion llego a
# cualquiera de estos, no puede "volver" a saludo sin perder el hilo.
ESTADOS_EN_CURSO = {"explorando", "esperando_confirmacion", "esperando_datos",
                    "derivar_humano", "posventa"}


def corregir_estado_regresion(estado_nuevo: str | None,
                              estado_anterior: str | None,
                              hay_historial: bool) -> str | None:
    """Una conversacion en curso NO puede volver a 'saludo'.

    El estado lo fija el LLM-interpretador y el orchestrator se lo inyecta al
    solver, cuya Regla #0 dice 'saludo, devolve el saludo y ofrece ayuda corta'.
    Si el interpretador lee mal un turno de mitad de charla como saludo (caso
    real: el cliente putea por el envio en el turno 11 y el bot contesta
    '¡Hola! Soy vendedor...'), el solver se reinicia y pierde el hilo. Esto es
    la falla (e), contradiccion entre turnos.

    Regla determinista: si ya hubo historial y el interpretador devuelve saludo,
    degradamos al estado anterior si era en curso, o a 'explorando'. El saludo
    solo es valido al arranque, cuando todavia no hay turnos previos.
    """
    if estado_nuevo == "saludo" and hay_historial:
        if estado_anterior in ESTADOS_EN_CURSO:
            return estado_anterior
        return "explorando"
    return estado_nuevo

# Frases nucleo de negacion o postergacion. Lista corta, solo se aplica
# como veto sobre decision_compra del LLM, no como decisor.
FRASES_NEGACION_NUCLEO = [
    "no quiero", "no lo quiero", "no la quiero",
    "no me sirve", "no me interesa",
    "tal vez despues", "tal vez mas adelante",
    "no se si", "me lo pienso", "lo pienso",
    "mas adelante", "ahora no", "despues veo",
    "lo voy a pensar", "lo pensare",
]

_client = None


def _get_client():
    global _client
    if _client is None:
        if settings.INTERPRETER_PROVIDER == "groq":
            from groq import Groq
            _client = Groq(api_key=settings.GROQ_API_KEY,
                           timeout=settings.LLM_TIMEOUT_SECONDS)
        elif settings.INTERPRETER_PROVIDER == "openai":
            _client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
        elif settings.INTERPRETER_PROVIDER == "anthropic":
            _client = OpenAI(
                api_key=settings.ANTHROPIC_API_KEY,
                base_url=settings.ANTHROPIC_BASE_URL,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
        elif settings.INTERPRETER_PROVIDER == "nemotron":
            # Nemotron via NIM (OpenAI-compatible). Permite correr todo el
            # pipeline sobre la key gratis de NVIDIA, sin DeepSeek.
            _client = OpenAI(
                api_key=settings.NEMOTRON_API_KEY,
                base_url=settings.NEMOTRON_BASE_URL,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
        elif settings.INTERPRETER_PROVIDER == "kimi":
            # Kimi (Moonshot) via NIM de NVIDIA (OpenAI-compatible). Gratis y
            # obediente. Misma key nvapi- que Nemotron si no hay KIMI_API_KEY propia.
            _client = OpenAI(
                api_key=settings.KIMI_API_KEY,
                base_url=settings.KIMI_BASE_URL,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
        elif settings.INTERPRETER_PROVIDER == "openrouter":
            _client = OpenAI(
                api_key=settings.OPENROUTER_API_KEY,
                base_url=settings.OPENROUTER_BASE_URL,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
        elif settings.INTERPRETER_PROVIDER == "gemini":
            # Gemini directo via endpoint compatible OpenAI. SIN esta rama el
            # provider gemini caia al else (DeepSeek): el interpretador de los
            # -AllGemini corria en secreto sobre DeepSeek (visto 10-jun).
            _client = OpenAI(
                api_key=settings.GEMINI_API_KEY,
                base_url=settings.GEMINI_BASE_URL,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
        else:
            _client = OpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com/v1",
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
    return _client


RE_PRODUCTO_PRECIO = re.compile(
    r"\*\*([^*]+)\*\*[^$]*?\$\s*([\d.]+)"
)


def extraer_productos_mostrados(history: list[dict],
                                  ultimos_n_turnos: int = 4) -> list[dict]:
    """Extrae productos mencionados en los ultimos turnos del bot."""
    productos = []
    turnos_bot = [h for h in history[-ultimos_n_turnos*2:]
                  if h.get("role") == "assistant"]

    for turno in turnos_bot[-ultimos_n_turnos:]:
        contenido = turno.get("content", "")
        matches = RE_PRODUCTO_PRECIO.findall(contenido)
        for nombre, precio_str in matches:
            try:
                precio = int(precio_str.replace(".", "").replace(",", ""))
                productos.append({
                    "nombre": nombre.strip(),
                    "precio": precio,
                })
            except ValueError:
                continue

    vistos = set()
    productos_unicos = []
    for p in productos:
        clave = p["nombre"]
        if clave not in vistos:
            vistos.add(clave)
            productos_unicos.append(p)

    return productos_unicos


def truncar_listado(texto: str, max_chars: int = 250) -> str:
    """Trunca listados largos del bot conservando inicio mas indicacion."""
    if len(texto) <= max_chars:
        return texto
    return texto[:max_chars] + "... (listado truncado)"


def construir_contexto_conversacional(history: list[dict],
                                       n_turnos_completos: int = 7) -> str:
    """Arma contexto conversacional con turnos recientes completos
    y resumen de turnos viejos. Trunca listados largos del bot."""
    if not history:
        return "Sin historial previo"

    n_mensajes = n_turnos_completos * 2
    recientes = history[-n_mensajes:]
    viejos = history[:-n_mensajes] if len(history) > n_mensajes else []

    lineas = []

    if viejos:
        lineas.append(f"Resumen de {len(viejos)} mensajes previos: "
                       "conversacion en curso, ver mensajes recientes para contexto actual.")

    for msg in recientes:
        rol = msg.get("role", "")
        contenido = msg.get("content", "")
        if rol == "assistant":
            contenido = truncar_listado(contenido)
            lineas.append(f"Bot: {contenido}")
        elif rol == "user":
            lineas.append(f"Cliente: {contenido}")

    return "\n".join(lineas)


# GUIA del campo tipo_confirmacion (solo con CONFIRMACION_PROVIDER on). El
# interprete SOLO clasifica el tipo de ambiguedad, NO escribe la frase: el codigo
# del Provider la arma con los datos reales del catalogo. Es una PISTA; el codigo
# decide si finalmente pregunta.
GUIA_TIPO_CONFIRMACION = """

GUIA DE TIPO DE CONFIRMACION, campo tipo_confirmacion.
Clasifica QUE TIPO de pregunta de confirmacion haria falta, no la escribas, solo el tipo. El sistema arma la frase con datos reales del catalogo.
a_o_b, el cliente podria referirse a dos productos o caminos distintos y habria que preguntar cual de los dos.
te_referis_a, el cliente nombra algo que puede ser varios modelos o variantes y habria que preguntar a cual.
confirmar_compra, el cliente parece decidir pero no es inequivoco y conviene confirmar antes de cerrar.
null, no hace falta ninguna confirmacion, el caso es claro.
Es solo una PISTA. Abajo el codigo decide con el catalogo real si finalmente pregunta, asi que no fuerces el campo, marcalo solo ante ambiguedad genuina.
"""


GUIA_ACCIONES_CARRITO = """

GUIA DE ACCIONES SOBRE EL CARRITO, campo acciones_carrito. LO MAS IMPORTANTE.
Es lo que hay que HACER con el pedido segun ESTE mensaje del cliente. El codigo lo ejecuta contra el catalogo: vos solo decis la accion y el texto del producto como lo nombro el cliente, no el id ni el precio.
Lista VACIA [] si el mensaje NO cambia el pedido: un saludo, una pregunta (precio, si sirve, como se usa, donde queda un boton), una duda, un comentario, un reclamo, o algo fuera de tema. En la enorme mayoria de los turnos que no son una orden de compra, la lista va vacia.
Emiti acciones SOLO cuando el cliente claramente quiere modificar el pedido:
  agregar: suma un producto. producto = como lo nombro, cantidad = cuantos (1 si no aclara). OJO: si en el turno anterior el bot ofrecio productos u opciones (un A o B, una lista, "cual preferis") y el cliente ELIGE uno ("los 3 K380 negros", "el blanco", "la opcion A", "dale ese", "el primero"), eso ES agregar: emiti agregar con el producto elegido y la cantidad que dijo.
  sacar: quita un producto que ya estaba en el pedido.
  cambiar_cantidad: cambia cuantas unidades de un producto YA en el pedido. cantidad = el numero nuevo (0 = sacarlo). Frases tipo "mejor que sean 2", "que sean 2 teclados", "cambialo a 2", "dejalo en 2", "en vez de 3 poneme 2", "hacelo 2" SON cambiar_cantidad sobre el producto de ese tipo que ya esta en el carrito; producto = como lo nombra (mira el PEDIDO ACTUAL para saber a cual te referis), cantidad = el numero nuevo. NO es una pregunta ni un pedido nuevo: el cliente esta ajustando lo que ya tiene.
  vaciar: el cliente quiere empezar de cero o descartar todo el pedido.
EJEMPLO CONCRETO. Si el PEDIDO ACTUAL tiene "3x Teclado Logitech K380 Negro" y "1x Mouse Logitech G203 Lightsync Negro", y el cliente dice "mejor que sean 2 teclados", devolves acciones_carrito: [{"tipo": "cambiar_cantidad", "producto": "Teclado K380", "cantidad": 2}]. Si dice "saca el mouse": [{"tipo": "sacar", "producto": "mouse G203"}]. Si dice "sumale otro teclado": [{"tipo": "agregar", "producto": "Teclado K380", "cantidad": 1}]. Siempre que el cliente ajuste el pedido, el campo acciones_carrito tiene que venir POBLADO, no vacio.
Regla de oro: ante la duda, NO toques el carrito (lista vacia). Una pregunta sobre un producto NUNCA es agregar. Cambiar de tema NO borra el pedido salvo que lo pida. Solo el cliente mueve su carrito; vos reflejas lo que el pidio en este mensaje, nada mas.
"""


GUIA_PRODUCTO_CONSULTADO = """

GUIA DE PRODUCTO CONSULTADO, campo producto_consultado.
Es el producto que el cliente NOMBRA o PREGUNTA en este mensaje, copiado en sus palabras (con marca y modelo si los dijo), EXISTA O NO en la tienda. Sirve para que el sistema verifique despues si existe; vos NO decidis si existe, solo lo extraes.
Ejemplos: "tenes una impresora 3D Zyltech?" -> "impresora 3D Zyltech". "que garantia tiene el teclado K380?" -> "teclado K380". "me sirve la RTX 5070?" -> "RTX 5070".
null si el mensaje NO nombra ningun producto: un saludo, una pregunta de politica general (envios, formas de pago), un dato de contacto, un comentario. No inventes ni completes un producto que el cliente no nombro.
"""


GUIA_CATALOGO = """

GUIA DE QUIERE_CATALOGO, campo quiere_catalogo (true o false). IMPORTANTE: es una INTENCION, no un producto.
true cuando el cliente pide una VISTA GENERAL del inventario, ver QUE HAY en general, sin nombrar un producto ni una categoria puntual: "catalogo", "mostrame todo", "que venden", "que tienen", "que productos hay", "que ofrecen", "inventario", "mostrame lo que tengas", "todo lo que vendan". No hay ninguna identidad que buscar; el cliente quiere el panorama.
false en TODO otro caso: si nombra un producto ("tenes el K380"), si nombra una categoria concreta ("que teclados tenes", "mostrame mouses"), si pregunta precio, envio, pago, garantia, o cualquier otra cosa. Ante la duda, false.
"""


def construir_prompt_interpretador(mensaje: str,
                                     contexto_conversacional: str,
                                     productos_mostrados: list[dict],
                                     carrito_actual: list[dict] | None = None) -> str:
    """Prompt liberado v4. Da al LLM contexto y libertad para entender.
    Verifika valida abajo, asi que el Interpretador puede interpretar."""

    productos_str = "\n".join([
        f"- {p['nombre']} a ${p['precio']:,}"
        for p in productos_mostrados
    ]) or "Sin productos mostrados aun"

    # DIRECTOR_LLM: el carrito vigente entra al prompt para que el LLM pueda
    # emitir sacar / cambiar_cantidad apuntando a un producto que YA esta cargado.
    # Sin esto el modelo no sabe que hay en el pedido y no acierta el target del
    # comando (visto: "mejor que sean 2 teclados" no emitia cambiar_cantidad).
    bloque_carrito = ""
    if settings.DIRECTOR_LLM and carrito_actual:
        _lineas = "\n".join(
            f"- {it.get('cantidad', 1)}x {it.get('nombre')}"
            for it in carrito_actual if it.get("nombre"))
        if _lineas:
            bloque_carrito = (
                "\n\nPEDIDO ACTUAL EN EL CARRITO DEL CLIENTE (lo que ya tiene "
                "cargado; para sacar o cambiar cantidad referite a estos):\n"
                + _lineas)

    # CONFIRMACION_PROVIDER: el interprete suma la PISTA tipo_confirmacion. Con el
    # flag off el prompt queda byte a byte igual al previo (baseline de pruebas).
    con_conf = settings.CONFIRMACION_PROVIDER
    coma_tc = "," if con_conf else ""
    linea_tc = ('\n  "tipo_confirmacion": "a_o_b|te_referis_a|confirmar_compra, '
                'o null"') if con_conf else ""
    guia_tc = GUIA_TIPO_CONFIRMACION if con_conf else ""

    # DIRECTOR_LLM: el interprete emite las ACCIONES sobre el carrito en el mismo
    # JSON. Con el flag off, estas tres variables quedan vacias y el prompt es
    # byte a byte igual al previo (baseline de pruebas intacto).
    con_dir = settings.DIRECTOR_LLM
    coma_ac = "," if con_dir else ""
    linea_ac = ('\n  "acciones_carrito": [{"tipo": '
                '"agregar|sacar|cambiar_cantidad|vaciar", '
                '"producto": "texto, o null", "cantidad": N}],'
                '\n  "producto_consultado": "el producto que el cliente nombra o '
                'pregunta en este mensaje, en sus palabras, exista o no, o null",'
                '\n  "quiere_catalogo": true/false'
                ) if con_dir else ""
    guia_ac = (GUIA_ACCIONES_CARRITO + GUIA_PRODUCTO_CONSULTADO
               + GUIA_CATALOGO) if con_dir else ""

    prompt = f"""Sos un interpretador de mensajes de clientes en un bot de ventas argentino.
Tu trabajo es entender que quiere el cliente, considerando toda la conversacion.
Devolves SOLO un JSON valido, sin texto extra.

CONTEXTO DE LA CONVERSACION (siete turnos recientes):
{contexto_conversacional}

PRODUCTOS QUE EL BOT YA MOSTRO AL CLIENTE:
{productos_str}{bloque_carrito}

MENSAJE ACTUAL DEL CLIENTE:
{mensaje}

DEVOLVE ESTE JSON:
{{
  "intencion": "saludo|exploracion|pregunta_especifica|decision_compra|aporta_dato|otra",
  "producto_resuelto": "nombre exacto del producto mostrado al que se refiere, o null",
  "candidatos": ["opcion1", "opcion2"],
  "confianza": 0.0 a 1.0,
  "datos_pedido": null,
  "respondiendo_a": "que pregunto el bot en su ultimo turno y a que responde el cliente, o null si no responde a una pregunta previa",
  "estado_conversacion": "saludo|explorando|esperando_confirmacion|esperando_datos|derivar_humano|posventa",
  "ofrecer_opciones": "null si no hay duda, o lista de dos opciones [opcion A, opcion B] cuando hay dos caminos posibles y no se puede determinar uno con certeza"{coma_tc}{linea_tc}{coma_ac}{linea_ac}
}}

GUIA DE INTENCIONES, usalas con criterio, no son recetas rigidas.

saludo, el cliente saluda o inicia conversacion.

exploracion, el cliente quiere ver que hay disponible, sin algo concreto en mente.

pregunta_especifica, el cliente pregunta sobre algo concreto. Producto, precio, envio, pago, garantia, stock, color, medidas. Tambien expresiones de interes tipo me gusta, me sirve, me interesa. Son evaluacion, no decision.

decision_compra, el cliente expresa decision INEQUIVOCA y AFIRMATIVA de comprar algo identificable. Frases tipo dale lo llevo, lo quiero, cerramos, pasame el link. Tambien un si o un dale como respuesta directa a una propuesta de cierre del bot. PROHIBIDO marcar decision_compra si hay negacion, postergacion o duda en el mensaje, aunque aparezca la palabra quiero o comprar.

aporta_dato, el cliente esta dando un dato concreto que el bot necesita para avanzar. Direccion, codigo postal, telefono, mail, eleccion de pago entre opciones ya ofrecidas, fecha o franja horaria, nombre. Tambien aclaraciones de cantidad o eleccion entre productos ya propuestos. Si el ultimo turno del bot pidio este dato explicitamente, es muy probable que la intencion sea esta.

otra, no encaja en ninguna anterior. Rechazos, postergaciones, comentarios fuera de tema.

COMO USAR EL CAMPO respondiendo_a.

Mira el ultimo turno del bot en el contexto. Si el bot hizo una pregunta o pidio algo, y el mensaje del cliente parece responder a eso, completa el campo describiendo brevemente que pregunto el bot y que responde el cliente. Ejemplo, el bot pregunto la direccion de envio, el cliente responde con calle altura y codigo postal. Si el mensaje del cliente no responde a nada previo, deja el campo en null.

GUIA DE ESTADO DE CONVERSACION, lo mas importante.
Determina el estado ACTUAL de la charla leyendo el ULTIMO mensaje del cliente en relacion a lo que el bot dijo en su turno anterior. No predigas a futuro. Lee lo que pasa AHORA. El ultimo mensaje del cliente es el eje de la decision, el historial es solo contexto.
saludo, el cliente recien llega o saluda, todavia no pidio ningun producto ni precio.
explorando, el cliente pregunta productos, precios o compara opciones, sin haberse decidido por uno.
esperando_confirmacion, el bot ofrecio algo concreto, un producto o un total, y el cliente todavia no dijo si o no.
esperando_datos, el cliente ya confirmo que quiere avanzar y falta que de direccion, forma de pago o datos de contacto.
derivar_humano, el cliente dio todos los datos necesarios o pidio hablar con una persona.
posventa, el cliente pregunta por algo posterior a la compra, garantia, seguimiento de pedido o consulta suelta fuera del flujo.

GUIA DE CAMINO A O B, campo ofrecer_opciones.
Cuando haya dos opciones o dos valores posibles y NO puedas determinar con certeza cual corresponde, no elijas uno ni promedies. Pobla ofrecer_opciones con las dos como opcion A y opcion B, cada una con su detalle o valor. Aplica a productos cuando hay duda entre dos, a envios con rango de costo, a precios o formas de pago con mas de una alternativa. Si el caso es claro y unico, deja ofrecer_opciones en null. Cuando pobles este campo, el estado suele ser esperando_confirmacion porque el cliente debera elegir.{guia_tc}

PRODUCTO RESUELTO.
Solo si hay UN producto claro entre los mostrados al que el cliente se refiere.
Si hay duda entre dos o mas, producto_resuelto null y candidatos con esos productos.
Si no hay producto en contexto, producto_resuelto null.

CONFIANZA.
alta 0.85 a 1.0, intencion inequivoca o referencia clara a un producto unico.
media 0.6 a 0.85, intencion identificada pero referencia parcial.
baja menor a 0.6, ambiguedad real que requiere preguntar al cliente.

Si dudas entre dos opciones, baja la confianza y pobla candidatos en lugar de adivinar.

Tene en cuenta que abajo tuyo hay un sistema de verificacion que controla numeros y productos contra catalogo y FAQ. No tengas miedo de interpretar con criterio, ese sistema te respalda. Tu prioridad es entender al cliente bien.{guia_ac}

RESPUESTA SOLO EL JSON, SIN PREAMBULO NI EXPLICACION."""

    return prompt


def validar_schema(resultado: dict) -> tuple[bool, str]:
    """Valida que el JSON tenga los campos requeridos con tipos correctos.
    Devuelve tupla valido mas mensaje de error."""
    if not isinstance(resultado, dict):
        return False, "resultado no es dict"
    intencion = resultado.get("intencion")
    if intencion not in INTENCIONES_VALIDAS:
        return False, f"intencion invalida, recibido {intencion}, esperado {INTENCIONES_VALIDAS}"
    confianza = resultado.get("confianza")
    if not isinstance(confianza, (int, float)):
        return False, "confianza no es numero"
    if confianza < 0 or confianza > 1:
        return False, f"confianza fuera de rango, recibido {confianza}"
    # candidatos: el LLM a veces lo manda null o como string suelto en vez de
    # lista. Antes eso fallaba la validacion y disparaba un RETRY al modelo
    # (latencia y costo de gusto). Lo coercionamos en el lugar: null/vacio -> [],
    # string -> [string]. Solo un tipo realmente raro (dict, numero) falla.
    candidatos = resultado.get("candidatos", [])
    if candidatos is None:
        resultado["candidatos"] = []
    elif isinstance(candidatos, str):
        resultado["candidatos"] = [candidatos.strip()] if candidatos.strip() else []
    elif not isinstance(candidatos, list):
        return False, "candidatos no es lista"
    # tipo_confirmacion: pista opcional. Se coerciona, nunca falla la validacion
    # (igual que candidatos): valor valido se conserva, cualquier otra cosa -> None.
    tc = resultado.get("tipo_confirmacion")
    if isinstance(tc, str) and tc.strip().lower() in TIPOS_CONFIRMACION_VALIDOS:
        resultado["tipo_confirmacion"] = tc.strip().lower()
    else:
        resultado["tipo_confirmacion"] = None
    # acciones_carrito: lista de acciones sobre el pedido (DIRECTOR_LLM). Se
    # coerciona y se filtra a las acciones bien formadas; cualquier cosa rara ->
    # []. Nunca falla la validacion (no dispara retry). El director valida de nuevo.
    acc = resultado.get("acciones_carrito")
    limpias = []
    if isinstance(acc, list):
        for a in acc:
            if (isinstance(a, dict)
                    and str(a.get("tipo", "")).strip().lower()
                    in ("agregar", "sacar", "cambiar_cantidad", "vaciar")):
                limpias.append(a)
    resultado["acciones_carrito"] = limpias
    # producto_consultado: el producto que el cliente nombra/pregunta, en texto.
    # El certificador decide despues si existe; aca solo se normaliza a str o None.
    pc = resultado.get("producto_consultado")
    resultado["producto_consultado"] = (
        pc.strip() if isinstance(pc, str) and pc.strip() else None)
    # quiere_catalogo: INTENCION de ver el inventario general (no un producto).
    qc = resultado.get("quiere_catalogo")
    resultado["quiere_catalogo"] = (
        qc is True or (isinstance(qc, str) and qc.strip().lower() == "true"))
    return True, ""


def contiene_negacion(mensaje: str) -> bool:
    """Detecta si el mensaje contiene frase nucleo de negacion o postergacion."""
    msg = mensaje.lower()
    for frase in FRASES_NEGACION_NUCLEO:
        if frase in msg:
            return True
    return False


def parsear_respuesta_llm(raw: str) -> dict | None:
    """Limpia y parsea JSON de la respuesta cruda del LLM."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


async def _llamar_llm(prompt: str) -> str:
    """Llamada al LLM con parametros fijos."""
    client = _get_client()

    def _do_call() -> str:
        if settings.INTERPRETER_PROVIDER == "groq":
            modelo = settings.GROQ_MODEL
        elif settings.INTERPRETER_PROVIDER == "openai":
            modelo = settings.OPENAI_MODEL
        elif settings.INTERPRETER_PROVIDER == "anthropic":
            modelo = settings.ANTHROPIC_MODEL
        elif settings.INTERPRETER_PROVIDER == "nemotron":
            modelo = settings.NEMOTRON_MODEL
        elif settings.INTERPRETER_PROVIDER == "kimi":
            modelo = settings.KIMI_MODEL
        elif settings.INTERPRETER_PROVIDER == "openrouter":
            modelo = settings.OPENROUTER_MODEL
        elif settings.INTERPRETER_PROVIDER == "gemini":
            modelo = settings.GEMINI_MODEL
        else:
            modelo = settings.DEEPSEEK_MODEL
        from app.config import (deepseek_extra_body, deepseek_pensando,
                                gemini_thinking_off, nvidia_thinking_off,
                                openrouter_reasoning_off)
        es_deepseek = settings.INTERPRETER_PROVIDER not in (
            "groq", "openai", "anthropic", "nemotron", "kimi", "openrouter",
            "gemini")
        # NVIDIA (nemotron/kimi) apaga thinking con chat_template_kwargs;
        # OpenRouter con reasoning; Gemini directo con reasoning_effort;
        # DeepSeek directo con su extra_body.
        nv = nvidia_thinking_off(settings.INTERPRETER_PROVIDER, modelo)
        orr = openrouter_reasoning_off(settings.INTERPRETER_PROVIDER, modelo)
        gm = gemini_thinking_off(settings.INTERPRETER_PROVIDER, modelo)
        extra = nv or orr or gm or (deepseek_extra_body(modelo) if es_deepseek else {})
        # En modo razonador el thinking consume tokens antes del JSON: le damos
        # mas presupuesto para que la respuesta no salga vacia.
        max_tok = 2000 if (es_deepseek and deepseek_pensando(modelo)) else 400
        try:
            response = client.chat.completions.create(
                model=modelo,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=max_tok,
                **({"extra_body": extra} if extra else {}),
            )
        except Exception:
            if extra:
                response = client.chat.completions.create(
                    model=modelo, messages=[{"role": "user", "content": prompt}],
                    temperature=0.0, max_tokens=max_tok)
            else:
                raise
        return response.choices[0].message.content or ""

    # El cliente OpenAI es sincrono: este create() bloquearia el event loop
    # pese a estar en una funcion async, asi que lo mandamos a un thread.
    return await asyncio.to_thread(_do_call)


async def interpretar_mensaje(mensaje: str,
                                history: list[dict],
                                trace_id: str,
                                estado_anterior: str | None = None,
                                tienda_id: str | None = None,
                                carrito_actual: list[dict] | None = None) -> dict:
    log.info("interpretar_mensaje_inicio")
    """Funcion principal del Interpretador.
    Prompt liberado mas tres capas de filtro al final."""
    try:
        productos = extraer_productos_mostrados(history)
        contexto_conv = construir_contexto_conversacional(history,
                                                            n_turnos_completos=7)

        if estado_anterior:
            contexto_conv = (
                f"ESTADO ACTUAL DE LA CONVERSACION segun el turno anterior: "
                f"{estado_anterior}. Usalo como contexto, pero determina el "
                f"estado real leyendo el ultimo mensaje del cliente.\n\n"
                + contexto_conv
            )
        prompt = construir_prompt_interpretador(
            mensaje, contexto_conv, productos, carrito_actual=carrito_actual)

        # Primera llamada al LLM
        raw = await _llamar_llm(prompt)
        resultado = parsear_respuesta_llm(raw)

        # Capa uno, validacion de schema con retry una vez
        if resultado is None:
            log.warning("interpretador_json_invalido_retry", trace_id=trace_id,
                        raw=raw[:200])
            prompt_retry = (prompt +
                            "\n\nTU RESPUESTA ANTERIOR NO FUE JSON VALIDO. "
                            "DEVOLVE SOLO EL JSON, SIN BACKTICKS NI EXPLICACION.")
            raw = await _llamar_llm(prompt_retry)
            resultado = parsear_respuesta_llm(raw)
            if resultado is None:
                log.error("interpretador_json_invalido_final", trace_id=trace_id)
                return {
                    "intencion": "otra",
                    "producto_resuelto": None,
                    "candidatos": [],
                    "confianza": 0.0,
                    "datos_pedido": None,
                    "respondiendo_a": None,
                    "error": "json_invalido",
                }

        valido, error_msg = validar_schema(resultado)
        if not valido:
            log.warning("interpretador_schema_invalido_retry", trace_id=trace_id,
                        error=error_msg)
            prompt_retry = (prompt +
                            f"\n\nTU RESPUESTA ANTERIOR FALLO VALIDACION, {error_msg}. "
                            "DEVOLVE SOLO EL JSON CON TODOS LOS CAMPOS CORRECTOS.")
            raw = await _llamar_llm(prompt_retry)
            resultado = parsear_respuesta_llm(raw)
            if resultado is None:
                resultado = {}
            valido, error_msg = validar_schema(resultado)
            if not valido:
                log.error("interpretador_schema_invalido_final", trace_id=trace_id,
                          error=error_msg)
                return {
                    "intencion": "otra",
                    "producto_resuelto": None,
                    "candidatos": [],
                    "confianza": 0.0,
                    "datos_pedido": None,
                    "respondiendo_a": None,
                    "error": f"schema_invalido_{error_msg}",
                }

        # Asegurar campos opcionales presentes
        if "producto_resuelto" not in resultado:
            resultado["producto_resuelto"] = None
        if "candidatos" not in resultado:
            resultado["candidatos"] = []
        if "datos_pedido" not in resultado:
            resultado["datos_pedido"] = None
        if "respondiendo_a" not in resultado:
            resultado["respondiendo_a"] = None
        if "tipo_confirmacion" not in resultado:
            resultado["tipo_confirmacion"] = None

        # Capa dos, filtro de negacion sobre decision_compra
        if resultado["intencion"] == "decision_compra" and contiene_negacion(mensaje):
            log.info("interpretador_filtro_negacion", trace_id=trace_id,
                     mensaje_preview=mensaje[:80])
            resultado["intencion"] = "otra"
            resultado["confianza"] = 0.3

        # Capa tres, downgrade si baja confianza sin candidatos
        if (resultado["confianza"] < UMBRAL_CONFIANZA_MEDIA
                and not resultado["candidatos"]
                and resultado["intencion"] in {"decision_compra", "pregunta_especifica"}):
            log.info("interpretador_downgrade_baja_confianza", trace_id=trace_id,
                     intencion_original=resultado["intencion"])
            resultado["intencion"] = "otra"

        # Capa cuatro, anclaje al catalogo: aterriza candidatos y producto a la
        # fuente de verdad. Detras del flag. El LLM corrige el lenguaje, el codigo
        # mapea a productos reales y resuelve o pide elegir.
        if settings.INTERPRETE_ANCLA_CATALOGO:
            try:
                from app.storage.firestore_client import get_all_products
                from app.core.tools_context import get_current_tienda
                tid = tienda_id or get_current_tienda()
                productos = get_all_products(tienda_id=tid)
                from app.core.interprete_ancla import anclar_a_catalogo
                resultado = anclar_a_catalogo(
                    resultado, mensaje, productos,
                    umbral_alta=UMBRAL_CONFIANZA_ALTA)
            except Exception as e:
                log.warning("interprete_ancla_error", trace_id=trace_id,
                            error=str(e)[:120])

        log.info("interpretador_ok", trace_id=trace_id,
                 intencion=resultado.get("intencion"),
                 confianza=resultado.get("confianza"),
                 producto_resuelto=resultado.get("producto_resuelto"),
                 respondiendo_a=resultado.get("respondiendo_a"),
                 candidatos_count=len(resultado.get("candidatos", [])),
                 productos_contexto=len(productos))

        return resultado

    except Exception as e:
        log.error("interpretador_error", trace_id=trace_id,
                  error=str(e)[:200])
        return {
            "intencion": "otra",
            "producto_resuelto": None,
            "candidatos": [],
            "confianza": 0.0,
            "datos_pedido": None,
            "respondiendo_a": None,
            "tipo_confirmacion": None,
            "error": str(e)[:100],
        }
