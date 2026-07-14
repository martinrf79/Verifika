"""
SOLVER GEMINI (12-jul) — el modelo LLAMA las herramientas y compone la
respuesta. Reemplaza al selector+compositor en el camino vivo para el caso
general; el codigo sigue siendo dueno del DATO porque cada precio, stock,
total, envio y politica sale de una tool determinista, nunca de la cabeza del
modelo. Los verificadores y guardias corren DESPUES como red (mismo patron de
degradacion: si el solver falla, el pipeline cae al compositor determinista).

Como funciona: Gemini recibe el menu de tools del sistema (get_tools_schema)
mas la guia de venta en prosa, decide cual llamar, el CODIGO la ejecuta contra
Firestore/FAQ/calculadora, le devuelve el resultado, en loop, hasta redactar.
Devuelve (respuesta, meta) con meta['tools_called'] en el formato estandar que
consume todo el downstream (evidencia, verificadores, envio, presupuesto,
carrito, cierre, memoria). Ante cualquier error devuelve (None, None) y el
llamador usa el compositor.

Endpoint NATIVO de Gemini (14-jul): el solver dejó el endpoint compat de OpenAI
y usa la API nativa (generateContent) para poder CACHEAR el prefijo fijo. El
system prompt + el schema de las 13 tools son ~2.580 tokens que viajaban en
CADA vuelta del loop; ahora van a un cache explicito (cachedContents) que se
cobra al 10%, y baja la factura ~a la mitad SIN cambiar un byte de lo que el
modelo ve (respuesta idéntica, riesgo de calidad cero). El cache se crea una
vez, dura por TTL y se refresca solo; si no se puede crear (tier sin cache), el
solver sigue igual mandando system+tools inline, solo que más caro. El thinking
va apagado por thinkingConfig.thinkingBudget=0 (el nativo no usa reasoning_effort).
"""
import asyncio
import hashlib
import json
import threading
import time

import httpx

from app.config import get_settings
from app.core import guia_venta_prosa
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

_MAX_ITERS = 7
_TIMEOUT_TOTAL_S = 30
_TOOL_RESULT_CAP = 4000  # chars del resultado de tool que se reenvia (como antes)


def _system_prompt(business_name: str) -> str:
    return (
        f"Sos el vendedor por WhatsApp de {business_name}, tienda argentina de "
        "tecnologia. Voseo, calido, directo, vendedor de verdad. Tu meta es "
        "VENDER y responder TODO lo que el cliente pregunta.\n\n"
        "REGLA DE ORO: NO inventes NINGUN dato duro. Todo precio, stock, nombre "
        "de producto, garantia, procedencia, material, costo de envio, plazo, "
        "cuota o politica SALE DE UNA HERRAMIENTA, nunca de tu cabeza. Antes de "
        "nombrar o recomendar un producto, buscalo con search_products o "
        "list_catalog y usa su id real. Para cualquier suma o total usa "
        "calculate_total (NUNCA sumes vos). Para el costo de envio usa "
        "cotizar_envio. Para politicas (factura, cuotas, devoluciones, garantia "
        "general, originalidad) usa query_faq. Para OPINAR, comparar o decir si "
        "un producto sirve para un uso, consulta consultar_guia_venta y razona "
        "desde ahi (no inventes criterios). Si un dato no lo devuelve ninguna "
        "tool, decilo con honestidad, no lo inventes.\n\n"
        "PROHIBIDO PUNTUAL, aunque suene util para vender:\n"
        "- NO hagas NINGUNA cuenta de cabeza: ni sumar, ni restar cuanto le "
        "sobra al cliente de su presupuesto, ni prorratear. Todo numero sale de "
        "calculate_total. Si le sobra plata, podes decir que le alcanza holgado, "
        "pero SIN poner la cifra de lo que sobra.\n"
        "- NO ofrezcas retiro en local ni pasar a buscar: la tienda es 100% "
        "online y solo entrega por envio.\n"
        "- NO asegures disponibilidad de un color o variante sin el stock de la "
        "tool; si no lo tenes, no lo afirmes.\n"
        "- NO prometas dias exactos de entrega ni fechas: el plazo sale de la "
        "FAQ o de calcular_entrega.\n"
        "- NO afirmes compatibilidad con una consola o equipo concreto (Play, "
        "Xbox, Mac, celular, TV) ni el tipo de conector, si la ficha del "
        "producto no lo dice textual. Si la ficha no lo aclara, decilo "
        "honesto: 'la ficha no lo especifica, lo confirmo antes de tu "
        "compra'.\n\n"
        "Dentro de esos limites, VENDE con todo: razona, opina, aconseja y "
        "compara con criterio de vendedor, apoyado en la guia de venta y la "
        "ficha real. Cerra siempre invitando a avanzar con la compra. Contesta "
        "en texto natural de WhatsApp, sin markdown pesado."
    )


def _bloque_memoria(estado: dict) -> str:
    """Bloque de MEMORIA para el prompt: lo que la charla ya estableció y el
    solver no ve en la historia corta (resumen largo, producto anotado, pedido
    vigente, destino, criterio, datos del cliente). Sin esto el solver
    re-pregunta lo ya dicho o lo pierde: la historia que recibe son los últimos
    turnos, y el resumen de memoria larga no viajaba (visto 13-jul). Es
    contexto, NO fuente de números: los totales siguen saliendo de las tools."""
    if not isinstance(estado, dict):
        return ""
    partes: list[str] = []
    resumen = str(estado.get("resumen_charla") or "").strip()
    if resumen:
        partes.append(f"Resumen de lo charlado antes (turnos viejos): {resumen}")
    anotado = estado.get("producto_anotado") or {}
    if isinstance(anotado, dict) and anotado.get("nombre"):
        partes.append(
            "Producto que el cliente eligió y pidió anotar: "
            f"{anotado['nombre']} (id {anotado.get('id', '?')})")
    carrito = [c for c in (estado.get("carrito") or []) if isinstance(c, dict)]
    renglones = [f"{c.get('cantidad', 1)}x {c['nombre']}"
                 for c in carrito if c.get("nombre")]
    if renglones:
        partes.append("Pedido vigente del cliente: " + "; ".join(renglones)
                      + ". Para el total usa calculate_total, no lo re-armes.")
    destinos = [str(d).strip() for d in (estado.get("localidades_envio") or [])
                if str(d or "").strip()]
    localidad = str(estado.get("localidad_envio") or "").strip()
    if localidad and localidad not in destinos:
        destinos.append(localidad)
    if destinos:
        prov = str(estado.get("provincia_envio") or "").strip()
        partes.append("Destino de envío que el cliente ya dio: "
                      + ", ".join(destinos) + (f" ({prov})" if prov else "")
                      + ". No se lo vuelvas a pedir; cotiza con cotizar_envio.")
    criterio = str(estado.get("criterio") or "").strip()
    if criterio:
        partes.append(f"Criterio que pidió el cliente: {criterio}")
    datos = estado.get("datos_cliente") or {}
    if isinstance(datos, dict) and datos:
        partes.append("Datos que el cliente ya dio: " + "; ".join(
            f"{k}: {v}" for k, v in datos.items()))
    if not partes:
        return ""
    return ("MEMORIA DE LA CHARLA (ya establecido; usalo, no lo re-preguntes; "
            "todo numero igual sale de las tools):\n- " + "\n- ".join(partes))


def _native_base() -> str:
    """El endpoint nativo. GEMINI_BASE_URL viene como .../v1beta/openai/ ; el
    nativo es .../v1beta ."""
    return settings.GEMINI_BASE_URL.replace("/openai/", "/").rstrip("/")


def _limpiar_schema(s):
    """Deja solo lo que Gemini acepta en parameters (subset de OpenAPI). El
    schema OpenAI trae campos que el nativo rechaza."""
    if not isinstance(s, dict):
        return s
    ok = {"type", "description", "enum", "properties", "items", "required",
          "nullable"}
    out = {}
    for k, v in s.items():
        if k not in ok:
            continue
        if k == "properties":
            out[k] = {pk: _limpiar_schema(pv) for pk, pv in v.items()}
        elif k == "items":
            out[k] = _limpiar_schema(v)
        else:
            out[k] = v
    return out


def _tools_nativas():
    """El menu de tools en formato nativo (function_declarations)."""
    from app.core.tools import get_tools_schema
    decls = []
    for t in list(get_tools_schema()) + [guia_venta_prosa.tool_schema()]:
        fn = t.get("function", t)
        decls.append({"name": fn["name"],
                      "description": fn.get("description", ""),
                      "parameters": _limpiar_schema(fn.get("parameters", {}))})
    return [{"function_declarations": decls}]


_cache_lock = threading.Lock()
_cache_state: dict = {}  # clave -> {"name": str, "expira": float}


def _obtener_cache(client, modelo, system, tools):
    """Crea o reusa el cache explicito de system+tools. Devuelve el name o None
    (sin cache el solver sigue igual, mandando system+tools inline)."""
    ttl = int(settings.GEMINI_CACHE_TTL_S or 1800)
    clave = hashlib.sha1(
        (modelo + "|" + system + "|" + json.dumps(tools)).encode()).hexdigest()
    ahora = time.time()
    with _cache_lock:
        st = _cache_state.get(clave)
        if st and st["expira"] > ahora + 30:
            return st["name"]
    try:
        r = client.post(
            f"{_native_base()}/cachedContents",
            json={"model": f"models/{modelo}",
                  "system_instruction": {"parts": [{"text": system}]},
                  "tools": tools, "ttl": f"{ttl}s"})
        r.raise_for_status()
        name = r.json()["name"]
    except Exception as e:
        log.warning("solver_gemini_cache_error", error=str(e)[:200])
        return None
    with _cache_lock:
        _cache_state[clave] = {"name": name, "expira": ahora + ttl}
    return name


def _cap_result(res):
    """functionResponse exige un objeto JSON. Reenvia el resultado como string
    JSON, con el mismo tope de 4000 chars que usaba el path compat."""
    try:
        crudo = json.dumps(res, default=str)
    except Exception:
        crudo = str(res)
    return {"result": crudo[:_TOOL_RESULT_CAP]}


def _ejecutar_tool(nombre, args, trace_id):
    """Corre la tool: primero la guia local, despues las del sistema."""
    if nombre == "consultar_guia_venta":
        return guia_venta_prosa.consultar_guia_venta(**(args or {}))
    import app.core.tools as T
    fn = getattr(T, nombre, None)
    if not callable(fn):
        return {"error": f"tool desconocida: {nombre}"}
    try:
        return fn(**(args or {}))
    except Exception as e:
        log.warning("solver_gemini_tool_error", trace_id=trace_id,
                    tool=nombre, error=str(e)[:150])
        return {"error": str(e)[:150]}


def _generar(client, base, modelo, contents, gen_cfg, cache_name, system, tools,
             trace_id):
    """Una llamada a generateContent. Usa el cache si esta; si el cache falla
    (expiro/GC), invalida y reintenta inline con system+tools. Devuelve el JSON."""
    body = {"contents": contents, "generationConfig": gen_cfg}
    if cache_name:
        body["cachedContent"] = cache_name
    else:
        body["system_instruction"] = {"parts": [{"text": system}]}
        body["tools"] = tools
    url = f"{base}/models/{modelo}:generateContent"
    try:
        r = client.post(url, json=body)
        r.raise_for_status()
        return r.json(), cache_name
    except httpx.HTTPStatusError as e:
        if not cache_name:
            raise
        log.warning("solver_gemini_cache_fallback", trace_id=trace_id,
                    code=e.response.status_code)
        with _cache_lock:
            _cache_state.clear()
        body.pop("cachedContent", None)
        body["system_instruction"] = {"parts": [{"text": system}]}
        body["tools"] = tools
        r = client.post(url, json=body)
        r.raise_for_status()
        return r.json(), None


def _run(raw_message, history, tienda_id, business_name, trace_id,
         estado=None):
    """El loop de function calling nativo (sincrono; corre en un thread)."""
    system = _system_prompt(business_name)
    tools = _tools_nativas()
    modelo = settings.GEMINI_MODEL or "gemini-3.1-flash-lite"
    base = _native_base()
    gen_cfg = {"maxOutputTokens": 1200, "temperature": 0.5,
               "thinkingConfig": {"thinkingBudget": 0}}

    with httpx.Client(
            timeout=_TIMEOUT_TOTAL_S,
            headers={"x-goog-api-key": settings.GEMINI_API_KEY,
                     "Content-Type": "application/json"}) as client:
        cache_name = _obtener_cache(client, modelo, system, tools)

        # El system va en el cache; la MEMORIA de la charla es dinamica por turno,
        # asi que entra como primer turno de contexto, no en el cache.
        contents = []
        memoria = _bloque_memoria(estado or {})
        if memoria:
            contents.append({"role": "user", "parts": [{"text": memoria}]})
            contents.append({"role": "model",
                             "parts": [{"text": "Entendido, lo tengo presente."}]})
        for h in (history or [])[-6:]:
            if not isinstance(h, dict):
                continue
            rol = "model" if h.get("role") == "assistant" else "user"
            cont = str(h.get("content") or "").strip()
            if cont:
                contents.append({"role": rol, "parts": [{"text": cont[:800]}]})
        contents.append({"role": "user", "parts": [{"text": raw_message}]})

        tools_called = []
        for _ in range(_MAX_ITERS):
            data, cache_name = _generar(client, base, modelo, contents, gen_cfg,
                                        cache_name, system, tools, trace_id)
            cand = (data.get("candidates") or [{}])[0]
            parts = (cand.get("content") or {}).get("parts") or []
            fcalls = [p["functionCall"] for p in parts if "functionCall" in p]
            if not fcalls:
                texto = " ".join(p["text"] for p in parts
                                 if isinstance(p.get("text"), str)).strip()
                return texto, tools_called
            contents.append(cand["content"])
            resp_parts = []
            for fc in fcalls:
                nombre = fc.get("name", "")
                args = fc.get("args") or {}
                res = _ejecutar_tool(nombre, args, trace_id)
                entrada = {"name": nombre, "args": args, "result": res}
                if isinstance(res, dict) and res.get("proof"):
                    entrada["proof"] = res["proof"]
                tools_called.append(entrada)
                resp_parts.append({"functionResponse":
                                   {"name": nombre, "response": _cap_result(res)}})
            contents.append({"role": "function", "parts": resp_parts})
    # Se acabaron las iteraciones sin respuesta final: no hay texto confiable.
    log.warning("solver_gemini_sin_texto", trace_id=trace_id)
    return "", tools_called


async def generar_respuesta(raw_message, interp, estado, tienda_id, trace_id,
                            history, business_name):
    """Genera la respuesta con Gemini llamando las tools. Devuelve
    (respuesta, meta) o (None, None) ante error/timeout/sin-clave, para que el
    llamador caiga al compositor determinista."""
    if not settings.GEMINI_API_KEY:
        return None, None
    from app.core.tools_context import set_current_tienda
    from app.core.estado_venta import set_current_estado
    set_current_tienda(tienda_id)
    set_current_estado(estado if isinstance(estado, dict) else {})
    try:
        texto, tools_called = await asyncio.wait_for(
            asyncio.to_thread(_run, raw_message, history, tienda_id,
                              business_name, trace_id,
                              estado if isinstance(estado, dict) else {}),
            _TIMEOUT_TOTAL_S)
    except Exception as e:
        log.warning("solver_gemini_error", trace_id=trace_id, error=str(e)[:200])
        return None, None
    if not texto:
        return None, None
    log.info("solver_gemini_ok", trace_id=trace_id, tools=len(tools_called),
             preview=texto[:160])
    return texto, {"tools_called": tools_called, "secciones": []}
