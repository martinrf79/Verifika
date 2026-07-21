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


    prompt = f"""Sos el INTÉRPRETE de un bot de ventas argentino. Tu única tarea es ENTENDER qué quiere el cliente en el contexto de la charla y devolver datos estructurados. No le escribís al cliente y no inventás nada: abajo tuyo hay herramientas que traen el dato real del catálogo y una verificación que controla productos y números. Por eso podés interpretar con criterio y confianza, ese sistema te respalda.

Trabajás por PRINCIPIOS, no por recetas:
- El eje es el ÚLTIMO mensaje del cliente, leído contra lo que el bot dijo en su turno anterior. El historial es contexto, no protagonista. Leé lo que pasa AHORA, no predigas a futuro.
- El cliente dice lo mismo de mil formas. Normalizá al campo que corresponde, no matchees palabras sueltas.
- Ante DUDA REAL de cuál de dos productos quiso decir, no elijas ni promedies: bajá la confianza y poné los candidatos. Preguntar es mejor que adivinar.
- Si el cliente pregunta por VARIOS productos a la vez, eso NO es duda: es una consulta múltiple. Listá cada producto con lo que pide de él.
- El TONO manda sobre las palabras. Un "sí", "claro", "seguro", "obvio", "dale" IRÓNICO o sarcástico, o una promesa imposible tipo "seguro que mañana lo tengo gratis", NO es una decisión ni una afirmación real: es lo contrario.

CONTEXTO DE LA CHARLA (turnos recientes + memoria de lo hablado antes):
{contexto_conversacional}

PRODUCTOS QUE EL BOT YA MOSTRÓ AL CLIENTE:
{productos_str}

MENSAJE ACTUAL DEL CLIENTE:
{mensaje}

Devolvé SOLO este JSON, sin texto alrededor. Antes de responder, validá que cumpla el schema.

{{
  "respondiendo_a": "si el bot preguntó o pidió algo en su último turno y el cliente responde a eso, describilo corto; si no, null",
  "productos_consultados": [{{"producto": "nombre EXACTO de un producto mostrado", "consulta": "precio|ficha|stock|opinion|comparacion|envio|otra"}}],
  "producto_resuelto": "nombre EXACTO del ÚNICO producto foco de una decisión o pedido, o null",
  "candidatos": ["opción A", "opción B"],
  "ofrecer_opciones": "null, o lista de dos opciones [A, B] cuando hay dos caminos y no se puede elegir uno con certeza",
  "intencion": "saludo|exploracion|pregunta_especifica|aporta_dato|decision_compra|otra",
  "estado_conversacion": "saludo|explorando|esperando_confirmacion|esperando_datos|derivar_humano|posventa",
  "criterio": "mas_barato|intermedio|null",
  "pedido": [{{"producto": "nombre EXACTO de un producto mostrado", "cantidad": número, "destino": "localidad tal cual la dijo, o null"}}],
  "tope_presupuesto": número entero en pesos o null,
  "exclusiones": [{{"tipo": "origen|marca", "valor": "texto"}}],
  "uso_previsto": "una o dos palabras o null",
  "confianza": 0.0 a 1.0
}}

CÓMO LLENARLO, por principios.

productos_consultados. Todos los productos MOSTRADOS por los que el cliente pregunta en este mensaje, cada uno con qué quiere saber. Uno solo si pregunta por uno; dos o más si nombra varios. Ejemplo: "precio del Logitech y decime si el Genius anda bien" son dos ítems, Logitech consulta precio y Genius consulta opinion. Vacía si no pregunta por ningún producto puntual.

producto_resuelto. El ÚNICO producto foco de una decisión o pedido, para que total y cierre operen sobre uno certificado. Si pregunta por varios sin decidir, va null y los productos van en productos_consultados. Referencias comparativas u ordinales, el más barato, el otro, el segundo, se resuelven comparando precio y orden de lo mostrado, no adivinando.

candidatos. SOLO para DUDA real, no se sabe a cuál de dos se refiere. No lo uses para una consulta múltiple legítima, eso va en productos_consultados.

ofrecer_opciones. Solo cuando hay dos caminos posibles y no se puede elegir uno con certeza, poné los dos como A y B con su detalle; si el caso es claro, null. Suele ir con estado esperando_confirmacion.

intencion. saludo, inicia o saluda. exploracion, quiere ver qué hay sin algo concreto. pregunta_especifica, pregunta puntual, producto, precio, envío, pago, garantía, stock, o interés tipo me gusta, me sirve, son evaluación, no decisión. aporta_dato, da un dato para avanzar, dirección, CP, teléfono, mail, pago, cantidad; si el bot lo pidió en su turno anterior, casi seguro es esta. decision_compra, decisión INEQUÍVOCA y afirmativa, o un sí o dale a una propuesta de cierre; PROHIBIDO si hay negación, postergación o duda, aunque diga comprar o quiero. otra, rechazos o fuera de tema.

estado_conversacion. saludo, recién llega. explorando, pregunta o compara sin decidirse. esperando_confirmacion, el bot ofreció algo concreto y el cliente no dijo sí ni no. esperando_datos, ya confirmó avanzar y faltan sus datos. derivar_humano, dio todos los datos o pidió una persona. posventa, algo posterior a la compra o consulta suelta. Una charla en curso NO vuelve a saludo.

criterio. mas_barato cuando pide lo más económico en cualquier forma, lo más barato, lo más eco, lo más conveniente, lo de menor precio. intermedio cuando pide precio medio o RECHAZA lo más barato, algo intermedio, gama media, ni el más barato ni el más caro. null si no hay criterio. Cubrí modismos argentinos, no solo la palabra exacta.

pedido. SOLO cuando arma un pedido concreto, productos mostrados con cantidad, nombre exacto del mostrado, sin inventar cantidades. Si reparte entre destinos, cada renglón con su destino y las cantidades desglosadas; con un solo destino o sin decirlo, destino null. Un destino tiene que aparecer en el mensaje o en la memoria de la charla.

preferencias. tope_presupuesto solo si dice una CIFRA. exclusiones si descarta por origen o marca, sin partes chinas, nada de Redragon. uso_previsto si dice para qué lo quiere. Llená lo que el mensaje diga, el resto null o vacío.

confianza. alta 0.85 a 1.0 lectura inequívoca; media 0.6 a 0.85 parcial; baja menor a 0.6 ambigüedad real que pide preguntar. Si dudás entre dos, bajá la confianza y poné candidatos.

EJEMPLOS de lo difícil, refuerzo del criterio, no lista cerrada.
"no el negro, el blanco": producto_resuelto el blanco, no es compra.
"dale, pero antes la garantía": NO es decision_compra, hay condición.
"2 del DX-110... no, mejor 3": pedido final 3, la corrección manda.
"jaja sí, seguro que mañana lo tengo gratis": ironía, NO es compra aunque diga sí.
"precio del Logitech y decime si el Genius anda bien": productos_consultados con los dos, producto_resuelto null.
"el segundo": se resuelve por el orden de lo mostrado.
"ponele que sí": sí tibio, no rechazo.

RESPUESTA: SOLO el JSON válido, sin preámbulo ni explicación."""

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


def coercionar_destinos(resultado: dict, mensaje: str) -> dict:
    """DESTINO FANTASMA (caso real WhatsApp 17-jul): el interprete metio
    'Rosario' en el pedido cuando el cliente jamas nombro una localidad
    (contaminacion de los ejemplos del prompt). Invariante determinista: un
    destino del pedido tiene que APARECER en el mensaje del cliente O en la
    MEMORIA de destinos de la charla (localidades cotizadas, provincia
    sticky). Lo segundo cierra el pendiente del 18-jul: el cliente daba los
    destinos en un turno y al confirmar en el siguiente ('dale, confirmalo')
    el guardia los anulaba como fantasmas y el envio se caia del total
    (visto de nuevo en el banco 20-jul, guion 48). Muta y devuelve."""
    import unicodedata

    def _n(s):
        s = unicodedata.normalize("NFKD", str(s or "").lower())
        s = "".join(c for c in s if not unicodedata.combining(c))
        return s.replace(",", " ").strip()

    m = _n(mensaje)
    memoria: list[str] = []
    try:
        from app.core.estado_venta import get_current_estado
        est = get_current_estado() or {}
        memoria = [_n(x) for x in (est.get("localidades_envio") or []) if x]
        for k in ("localidad_envio", "provincia_envio"):
            v = _n(est.get(k) or "")
            if v:
                memoria.append(v)
    except Exception:
        memoria = []

    def _en_memoria(dn: str) -> bool:
        pd = set(dn.split())
        for mv in memoria:
            pm = set(mv.split())
            if pd <= pm or pm <= pd:
                return True
        return False

    fantasmas = []
    for it in (resultado.get("pedido") or []):
        if not isinstance(it, dict):
            continue
        d = it.get("destino")
        if not d:
            continue
        dn = _n(d)
        if dn in m or _en_memoria(dn):
            continue
        fantasmas.append(str(d))
        it["destino"] = None
    if fantasmas:
        log.warning("interpretador_destino_fantasma", destinos=fantasmas[:4])
    return resultado


def coercionar_preferencias(resultado: dict) -> dict:
    """Coercion defensiva de los campos de preferencias para providers sin
    schema estricto: tope solo entero positivo; exclusiones solo dicts con tipo
    origen/marca y valor no vacio; uso string corto o None. Muta y devuelve."""
    _tope = resultado.get("tope_presupuesto")
    try:
        resultado["tope_presupuesto"] = (
            int(_tope) if _tope and int(_tope) > 0 else None)
    except (TypeError, ValueError):
        resultado["tope_presupuesto"] = None
    _exc = resultado.get("exclusiones")
    resultado["exclusiones"] = [
        {"tipo": str(e["tipo"]), "valor": str(e["valor"]).strip()}
        for e in (_exc if isinstance(_exc, list) else [])
        if isinstance(e, dict) and e.get("tipo") in ("origen", "marca")
        and str(e.get("valor") or "").strip()]
    _uso = resultado.get("uso_previsto")
    resultado["uso_previsto"] = (
        str(_uso).strip()[:60] if _uso and str(_uso).strip() else None)
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
    consulta_enum = ["precio", "ficha", "stock", "opinion",
                     "comparacion", "envio", "otra"]
    return {
        "type": "object",
        "additionalProperties": False,
        # Orden pensado para la generacion de Gemini: primero los campos de
        # interpretacion (a que responde, que productos consulta), despues las
        # decisiones (intencion, estado), y la confianza al FINAL para que
        # refleje lo ya resuelto, no al reves.
        "properties": {
            "respondiendo_a": {"type": ["string", "null"]},
            # PRODUCTOS CONSULTADOS (21-jul): el cliente puede preguntar por DOS
            # o MAS productos en el mismo mensaje, uno para precio y otro para
            # opinion. Antes solo habia producto_resuelto (uno) o candidatos
            # (duda), y una consulta multiple legitima caia a null (caso 17 del
            # banco). Cada item es un producto MOSTRADO (enum) mas que pide de el.
            "productos_consultados": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "producto": {"type": ["string", "null"], "enum": prod_enum},
                    "consulta": {"type": "string", "enum": consulta_enum},
                },
                "required": ["producto", "consulta"],
            }},
            "producto_resuelto": {"type": ["string", "null"], "enum": prod_enum},
            "candidatos": {"type": "array", "items": {"type": "string"}},
            "ofrecer_opciones": {"type": ["array", "null"],
                                 "items": {"type": "string"}},
            "intencion": {"type": "string", "enum": sorted(INTENCIONES_VALIDAS)},
            "estado_conversacion": {"type": "string", "enum": ESTADOS_VALIDOS},
            # CRITERIO de eleccion por precio (9-jul): el LLM cubre "eco" y
            # abreviaturas que el regex del codigo no. Enum acotado.
            # "intermedio" (11-jul): rechazar el minimo es un criterio propio.
            "criterio": {"type": ["string", "null"],
                         "enum": ["mas_barato", "intermedio", None]},
            # PEDIDO estructurado (8-jul): productos MOSTRADOS con cantidad,
            # atado por enum. Alimenta la guia determinista de pedido; el solver
            # no elige ids. destino por renglon, plano (Firestore prohibe listas
            # anidadas, bug real 8-jul). null = destino unico o sin decir.
            "pedido": {"type": ["array", "null"], "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "producto": {"type": ["string", "null"], "enum": prod_enum},
                    "cantidad": {"type": "integer"},
                    "destino": {"type": ["string", "null"]},
                },
                "required": ["producto", "cantidad", "destino"],
            }},
            # PREFERENCIAS (16-jul): tope solo con CIFRA; exclusiones por origen
            # o marca; uso en una o dos palabras. Consumidas por el generador.
            "tope_presupuesto": {"type": ["integer", "null"]},
            "exclusiones": {"type": ["array", "null"], "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "tipo": {"type": "string", "enum": ["origen", "marca"]},
                    "valor": {"type": "string"},
                },
                "required": ["tipo", "valor"],
            }},
            "uso_previsto": {"type": ["string", "null"]},
            "confianza": {"type": "number"},
        },
        "required": ["respondiendo_a", "productos_consultados",
                     "producto_resuelto", "candidatos", "ofrecer_opciones",
                     "intencion", "estado_conversacion", "criterio", "pedido",
                     "tope_presupuesto", "exclusiones", "uso_previsto",
                     "confianza"],
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
                    "productos_consultados": [],
                    "confianza": 0.0,
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
                    "productos_consultados": [],
                    "confianza": 0.0,
                    "respondiendo_a": None,
                    "error": f"schema_invalido_{error_msg}",
                }

        # Asegurar campos opcionales presentes
        if "producto_resuelto" not in resultado:
            resultado["producto_resuelto"] = None
        if "candidatos" not in resultado:
            resultado["candidatos"] = []
        if not isinstance(resultado.get("productos_consultados"), list):
            resultado["productos_consultados"] = []
        if "respondiendo_a" not in resultado:
            resultado["respondiendo_a"] = None
        if not isinstance(resultado.get("pedido"), list):
            resultado["pedido"] = []
        coercionar_preferencias(resultado)
        coercionar_destinos(resultado, mensaje)

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
            "productos_consultados": [],
            "confianza": 0.0,
            "respondiendo_a": None,
            "tipo_confirmacion": None,
            "error": str(e)[:100],
        }
