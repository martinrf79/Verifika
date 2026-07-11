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

UMBRAL_CONFIANZA_MEDIA = float(os.getenv("INTERPRETER_UMBRAL_MEDIA", "0.6"))

INTENCIONES_VALIDAS = {"saludo", "exploracion", "pregunta_especifica", "aporta_dato",
                        "decision_compra", "otra"}

# Estados validos del embudo. Lista (no set) para que el enum del schema estricto
# sea estable entre llamadas.
ESTADOS_VALIDOS = ["saludo", "explorando", "esperando_confirmacion",
                   "esperando_datos", "derivar_humano", "posventa"]

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
                                       n_turnos_completos: int = 7,
                                       resumen: str = "") -> str:
    """Arma contexto conversacional con turnos recientes completos
    y resumen de turnos viejos. Trunca listados largos del bot."""
    if not history and not (resumen or "").strip():
        return "Sin historial previo"

    n_mensajes = n_turnos_completos * 2
    recientes = history[-n_mensajes:]
    viejos = history[:-n_mensajes] if len(history) > n_mensajes else []

    lineas = []

    # MEMORIA LARGA: el resumen acumulado de la charla vieja (turnos que ya no
    # estan en el historial vivo) entra primero, asi el interprete puede leer
    # una referencia a algo dicho muchos turnos atras (C2-C4).
    if (resumen or "").strip():
        lineas.append("LO HABLADO ANTES EN ESTA CHARLA (resumen acumulado de "
                      "turnos viejos):\n" + resumen.strip())
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






def construir_prompt_interpretador(mensaje: str,
                                     contexto_conversacional: str,
                                     productos_mostrados: list[dict]) -> str:
    """Prompt liberado v4. Da al LLM contexto y libertad para entender.
    Verifika valida abajo, asi que el Interpretador puede interpretar."""

    productos_str = "\n".join([
        f"- {p['nombre']} a ${p['precio']:,}"
        for p in productos_mostrados
    ]) or "Sin productos mostrados aun"


    prompt = f"""Sos un interpretador de mensajes de clientes en un bot de ventas argentino.
Tu trabajo es entender que quiere el cliente, considerando toda la conversacion.
Devolves SOLO un JSON valido, sin texto extra.

CONTEXTO DE LA CONVERSACION (siete turnos recientes):
{contexto_conversacional}

PRODUCTOS QUE EL BOT YA MOSTRO AL CLIENTE:
{productos_str}

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
  "ofrecer_opciones": "null si no hay duda, o lista de dos opciones [opcion A, opcion B] cuando hay dos caminos posibles y no se puede determinar uno con certeza",
  "criterio": "mas_barato si el cliente expresa que quiere lo mas barato / mas economico / lo mas conveniente en CUALQUIER forma, abreviatura o modismo (ej lo mas barato, las mas baratas, lo mas eco, lo mas economico, mandame lo mas conveniente, lo de menor precio). null si no expresa ese criterio",
  "pedido": "lista de {{\\"producto\\": nombre EXACTO de un producto mostrado, \\"cantidad\\": numero}} SOLO cuando el cliente define un pedido concreto: que productos de los mostrados quiere y cuantos de cada uno (ej tres del DX-110 y dos teclados K120). Si no define productos y cantidades concretos, lista vacia []"
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
Cuando haya dos opciones o dos valores posibles y NO puedas determinar con certeza cual corresponde, no elijas uno ni promedies. Pobla ofrecer_opciones con las dos como opcion A y opcion B, cada una con su detalle o valor. Aplica a productos cuando hay duda entre dos, a envios con rango de costo, a precios o formas de pago con mas de una alternativa. Si el caso es claro y unico, deja ofrecer_opciones en null. Cuando pobles este campo, el estado suele ser esperando_confirmacion porque el cliente debera elegir.

PRODUCTO RESUELTO.
Solo si hay UN producto claro entre los mostrados al que el cliente se refiere.
Si hay duda entre dos o mas, producto_resuelto null y candidatos con esos productos.
Si no hay producto en contexto, producto_resuelto null.
Referencias COMPARATIVAS: "el mas barato", "el mas caro", "el otro", "el
primero" se resuelven comparando los PRECIOS y el orden de los productos
mostrados, no adivinando. "El barato no, el otro" apunta al que NO es el mas
barato. Si aun comparando queda empate o duda real, candidatos con los
posibles y confianza baja: preguntar es mejor que elegir mal.

CRITERIO.
Poné "mas_barato" cuando el cliente pide lo mas economico en cualquier forma: "lo mas barato", "las mas baratas", "lo mas eco", "lo mas economico", "mandame lo mas conveniente", "lo de menor precio", "algo barato". Cubri abreviaturas y modismos argentinos, no solo la palabra exacta. Si el cliente no expresa ese criterio, poné null. Es independiente del pedido: puede haber criterio sin pedido cerrado y viceversa.

PEDIDO.
Completalo SOLO cuando el cliente arma un pedido concreto: nombra productos que
estan entre los mostrados y dice cuantos quiere de cada uno. Usa el nombre EXACTO
del producto mostrado, no el apodo del cliente. Si el cliente pide un producto que
no esta entre los mostrados, o no da cantidades, o esta preguntando sin armar
pedido, deja la lista vacia. No inventes cantidades: solo las que dijo el cliente.

DESTINO por renglon del pedido.
Si el cliente reparte el pedido entre varios destinos, cada renglon lleva su
"destino" (la localidad tal cual la dijo) y las cantidades se DESGLOSAN por
destino. Ejemplo: mostrados teclado K120, mouse M170 y auricular H390; el
cliente dice "dame 2 teclados, 2 mouse y 2 auriculares: un teclado y un mouse
a Carlos Paz, un auricular y un teclado a Villa Maria, y el resto a Rio
Tercero". El pedido correcto es 6 renglones: K120 x1 destino Carlos Paz, M170
x1 destino Carlos Paz, H390 x1 destino Villa Maria, K120 x1 destino Villa
Maria, M170 x1 destino Rio Tercero, H390 x1 destino Rio Tercero. "El resto" =
lo pedido menos lo ya asignado. Las cantidades por producto tienen que sumar
lo que pidio el cliente. Con un solo destino o sin destino dicho, "destino"
va null en todos los renglones.

CONFIANZA.
alta 0.85 a 1.0, intencion inequivoca o referencia clara a un producto unico.
media 0.6 a 0.85, intencion identificada pero referencia parcial.
baja menor a 0.6, ambiguedad real que requiere preguntar al cliente.

Si dudas entre dos opciones, baja la confianza y pobla candidatos en lugar de adivinar.

Tene en cuenta que abajo tuyo hay un sistema de verificacion que controla numeros y productos contra catalogo y FAQ. No tengas miedo de interpretar con criterio, ese sistema te respalda. Tu prioridad es entender al cliente bien.

RESPUESTA SOLO EL JSON, SIN PREAMBULO NI EXPLICACION."""

    return prompt


_RE_BARATO_NO = re.compile(
    r"\b(?:el|la) barat[oa] no\b|\bno (?:quiero |me sirve )?(?:el|la) barat[oa]\b")


def _corregir_referencia_comparativa(resultado: dict, mensaje: str,
                                     productos_vistos: list[dict] | None) -> dict:
    """Filtro DETERMINISTA de un sesgo medido del modelo (banco de
    interpretacion, 8-jul): ante 'el barato no, el otro' con dos variantes
    baratas empatadas, GPT-4 mini resuelve confiado la OTRA variante barata en
    vez del que no es barato. La comparacion de precios es un problema CERRADO:
    si el cliente NEGO el barato y el interprete resolvio un producto con el
    precio MINIMO de los vistos, el codigo lo corrige: al unico mas caro si hay
    uno, o a candidatos con confianza baja si hay varios."""
    import unicodedata

    def _n(s):
        s = unicodedata.normalize("NFKD", str(s or "").lower())
        return "".join(c for c in s if not unicodedata.combining(c))

    if not isinstance(resultado, dict) or not _RE_BARATO_NO.search(_n(mensaje)):
        return resultado
    vistos = [v for v in (productos_vistos or [])
              if isinstance(v, dict) and v.get("nombre")
              and isinstance(v.get("precio", v.get("precio_ars")), (int, float))]
    if len(vistos) < 2:
        return resultado
    precio_de = {_n(v["nombre"]): int(v.get("precio", v.get("precio_ars")))
                 for v in vistos}
    pmin = min(precio_de.values())
    caros = [v["nombre"] for v in vistos
             if precio_de[_n(v["nombre"])] > pmin]
    if not caros:
        return resultado  # todos empatados: no hay "otro" que computar
    resuelto = _n(resultado.get("producto_resuelto"))
    if resuelto and precio_de.get(resuelto, pmin + 1) > pmin:
        return resultado  # ya resolvio uno NO barato: lectura coherente
    log.info("interpretador_comparativa_corregida",
             de=resultado.get("producto_resuelto"), caros=caros[:3])
    if len(caros) == 1:
        resultado["producto_resuelto"] = caros[0]
        # El pedido que arrastre el barato negado se re-apunta al correcto.
        for it in (resultado.get("pedido") or []):
            if isinstance(it, dict) and precio_de.get(
                    _n(it.get("producto")), pmin + 1) == pmin:
                it["producto"] = caros[0]
    else:
        resultado["producto_resuelto"] = None
        resultado["candidatos"] = caros[:3]
        resultado["confianza"] = min(
            float(resultado.get("confianza") or 0), 0.5)
        resultado["pedido"] = []
    return resultado


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
    return True, ""


def _reparar_json_truncado(cleaned: str) -> dict | None:
    """Red determinista contra el JSON cortado por max_tokens. Caso real
    (banco 11-jul, gpt-4o-mini): la gramatica del schema estricto obliga el
    proximo campo requerido, el modelo prefiere cerrar el objeto, y como el
    cierre esta prohibido emite espacios en blanco hasta agotar los tokens.
    Queda un JSON valido a medio cerrar y el turno caia al fallback de
    intencion 'otra' confianza 0. Aca se cierra lo que quedo abierto (string,
    llaves, corchetes) y se reintenta el parseo; si ni asi parsea, None."""
    s = cleaned.rstrip().rstrip(",")
    pila = []
    en_string = False
    escape = False
    for ch in s:
        if en_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                en_string = False
        elif ch == '"':
            en_string = True
        elif ch in "{[":
            pila.append(ch)
        elif ch in "}]":
            if pila:
                pila.pop()
    if en_string:
        s += '"'
        s = s.rstrip().rstrip(",")
    s += "".join("}" if c == "{" else "]" for c in reversed(pila))
    try:
        out = json.loads(s)
    except json.JSONDecodeError:
        return None
    return out if isinstance(out, dict) else None


def parsear_respuesta_llm(raw: str) -> dict | None:
    """Limpia y parsea JSON de la respuesta cruda del LLM. Si no parsea,
    intenta la reparacion determinista del truncado por max_tokens."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        reparado = _reparar_json_truncado(cleaned)
        if reparado is not None:
            log.warning("interpretador_json_truncado_reparado",
                        largo_raw=len(raw))
        return reparado


def _schema_interprete(nombres_mostrados: list[str]) -> dict:
    """Schema estricto para constrained generation DURA: Structured Outputs de
    OpenAI y el response_format json_schema del endpoint compatible de Gemini.
    intencion y estado atados a su enum; producto_resuelto atado al enum de
    los productos REALMENTE mostrados (o null): el interprete no puede referenciar
    a nivel token un producto que no se mostro. El LLM sigue INTERPRETANDO; el
    schema solo evita que emita un valor fuera de la fuente. En los demas
    providers el schema se ignora y queda el parseo + validacion de siempre."""
    nombres = list(dict.fromkeys(n for n in nombres_mostrados if n))
    prod_enum = ([None] + nombres) if nombres else [None]
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "intencion": {"type": "string", "enum": sorted(INTENCIONES_VALIDAS)},
            "producto_resuelto": {"type": ["string", "null"], "enum": prod_enum},
            "candidatos": {"type": "array", "items": {"type": "string"}},
            "confianza": {"type": "number"},
            "datos_pedido": {"type": ["string", "null"]},
            "respondiendo_a": {"type": ["string", "null"]},
            "estado_conversacion": {"type": "string", "enum": ESTADOS_VALIDOS},
            "ofrecer_opciones": {"type": ["array", "null"],
                                 "items": {"type": "string"}},
            # CRITERIO de eleccion por precio (9-jul): segundo interprete del
            # "lo mas barato". El regex del codigo (detectar_criterio) no cubre
            # "eco" ni abreviaturas; el LLM si. Se cruza con el regex en
            # concordancia_criterio: coinciden -> se arma; divergen -> se
            # confirma. Enum acotado: solo "mas_barato" o null.
            "criterio": {"type": ["string", "null"], "enum": ["mas_barato", None]},
            # PEDIDO estructurado (8-jul): cuando el cliente define productos
            # concretos CON cantidad, el interprete lo extrae atado al enum de
            # lo MOSTRADO. Es la entrada de la guia determinista de pedido: el
            # codigo llama la calculadora con estos items y sella el bloque; el
            # solver no elige ids. Fuera de OpenAI/Gemini el campo llega libre
            # y la validacion de abajo lo filtra igual (todo o nada).
            "pedido": {"type": ["array", "null"], "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "producto": {"type": ["string", "null"], "enum": prod_enum},
                    "cantidad": {"type": "integer"},
                    # DESTINO por renglon (pedido de Martin, 10-jul): pedidos
                    # multi-envio ("un teclado y un mouse a Carlos Paz, el
                    # resto a Rio Tercero") salen ya repartidos y el codigo
                    # cotiza cada grupo. Renglon plano, NO grupos anidados:
                    # Firestore prohibe listas anidadas (bug real 8-jul).
                    # null = destino unico o sin decir.
                    "destino": {"type": ["string", "null"]},
                },
                "required": ["producto", "cantidad", "destino"],
            }},
        },
        "required": ["intencion", "producto_resuelto", "candidatos", "confianza",
                     "datos_pedido", "respondiendo_a", "estado_conversacion",
                     "ofrecer_opciones", "criterio", "pedido"],
    }


async def _llamar_llm(prompt: str, response_format: dict | None = None) -> str:
    """Llamada al LLM con parametros fijos. response_format (json_schema strict)
    se aplica en OpenAI y Gemini; en otros providers se ignora y cae al parseo
    normal."""
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
        kwargs = {"model": modelo,
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.0, "max_tokens": max_tok}
        if extra:
            kwargs["extra_body"] = extra
        # Generacion restringida a nivel token via json_schema: OpenAI
        # (Structured Outputs) y Gemini (el endpoint compatible acepta
        # response_format json_schema; los 2.5 la respetan duro). Si el
        # provider lo rechaza, el except de abajo reintenta sin schema.
        rf = (response_format if (settings.INTERPRETER_PROVIDER in
                                  ("openai", "gemini") and response_format)
              else None)
        try:
            if rf:
                response = client.chat.completions.create(response_format=rf, **kwargs)
            else:
                response = client.chat.completions.create(**kwargs)
        except Exception:
            # Si el schema estricto o el extra no lo acepta el modelo, se reintenta
            # sin ellos: cae al parseo + validacion de siempre. La red no se cae.
            kwargs.pop("extra_body", None)
            response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    # El cliente OpenAI es sincrono: este create() bloquearia el event loop
    # pese a estar en una funcion async, asi que lo mandamos a un thread.
    return await asyncio.to_thread(_do_call)


async def interpretar_mensaje(mensaje: str,
                                history: list[dict],
                                trace_id: str,
                                estado_anterior: str | None = None,
                                tienda_id: str | None = None,
                                productos_vistos: list[dict] | None = None,
                                resumen: str = "") -> dict:
    log.info("interpretar_mensaje_inicio")
    """Funcion principal del Interpretador.
    Prompt liberado mas tres capas de filtro al final."""
    try:
        productos = extraer_productos_mostrados(history)
        # Los productos VISTOS del estado (ids reales persistidos por las tools y
        # los [[PROD:]] estampados) enriquecen el contexto y el ENUM del schema:
        # son mas confiables que el regex sobre el historial (el solver no
        # siempre lista en negrita). Dedup por nombre, los del regex primero.
        _nombres_regex = {p.get("nombre") for p in productos}
        for pv in (productos_vistos or []):
            if not isinstance(pv, dict) or not pv.get("nombre"):
                continue
            if pv["nombre"] in _nombres_regex:
                continue
            _precio = pv.get("precio", pv.get("precio_ars"))
            if isinstance(_precio, (int, float)):
                productos.append({"nombre": pv["nombre"], "precio": int(_precio)})
                _nombres_regex.add(pv["nombre"])
        contexto_conv = construir_contexto_conversacional(
            history, n_turnos_completos=7, resumen=resumen)

        if estado_anterior:
            contexto_conv = (
                f"ESTADO ACTUAL DE LA CONVERSACION segun el turno anterior: "
                f"{estado_anterior}. Usalo como contexto, pero determina el "
                f"estado real leyendo el ultimo mensaje del cliente.\n\n"
                + contexto_conv
            )
        prompt = construir_prompt_interpretador(
            mensaje, contexto_conv, productos)

        # Constrained generation dura (solo OpenAI): el enum de producto_resuelto
        # se arma con los productos que el bot REALMENTE mostro este contexto.
        _nombres = [p.get("nombre") for p in productos if p.get("nombre")]
        _rf = {"type": "json_schema", "json_schema": {
            "name": "interpretacion", "strict": True,
            "schema": _schema_interprete(_nombres)}}

        # Primera llamada al LLM
        raw = await _llamar_llm(prompt, response_format=_rf)
        resultado = parsear_respuesta_llm(raw)

        # Capa uno, validacion de schema con retry una vez
        if resultado is None:
            log.warning("interpretador_json_invalido_retry", trace_id=trace_id,
                        raw=raw[:200])
            prompt_retry = (prompt +
                            "\n\nTU RESPUESTA ANTERIOR NO FUE JSON VALIDO. "
                            "DEVOLVE SOLO EL JSON, SIN BACKTICKS NI EXPLICACION.")
            raw = await _llamar_llm(prompt_retry, response_format=_rf)
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
            raw = await _llamar_llm(prompt_retry, response_format=_rf)
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
        if not isinstance(resultado.get("pedido"), list):
            resultado["pedido"] = []

        # Sesgo medido del modelo en referencias comparativas ('el barato no,
        # el otro'): la comparacion de precios la corrige el CODIGO.
        resultado = _corregir_referencia_comparativa(
            resultado, mensaje, productos_vistos)

        # El interprete tiene LIBERTAD para interpretar: el codigo NO cambia su
        # intencion. Se quitaron las capas que la pisaban (veto de negacion y
        # downgrade por baja confianza); negacion, duda y ambiguedad ya las maneja
        # el prompt del LLM (baja la confianza y pobla candidatos). El codigo solo
        # valida que el JSON tenga forma; lo que el LLM entendio, queda.

        log.info("interpretador_ok", trace_id=trace_id,
                 intencion=resultado.get("intencion"),
                 confianza=resultado.get("confianza"),
                 producto_resuelto=resultado.get("producto_resuelto"),
                 respondiendo_a=resultado.get("respondiendo_a"),
                 candidatos_count=len(resultado.get("candidatos", [])),
                 pedido=resultado.get("pedido"),
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
