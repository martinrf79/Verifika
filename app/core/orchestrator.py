"""
ORCHESTRATOR — coordina el flujo completo.
Historial persistente en Firestore (sobrevive reinicios de Cloud Run).
Multi-tenant: si tienda_id es None, usa la default del settings.

v5: integración con Verifika detrás de feature flag USE_VERIFIKA.
v6: integración con Interpretador detrás de feature flag USE_INTERPRETER.
- Si USE_INTERPRETER=false (default): comportamiento idéntico a v5.
- Si USE_INTERPRETER=true: corre el Interpretador antes del Solver para
  resolver referencias parciales y detectar intencion de compra temprano.
"""
import json
import os
import re
import time
import uuid
import asyncio
import structlog
from app.core.agent import run_agent
from app.core.guardian import validate_response, clean_response
from app.core.verificador import verificar_respuesta, autocorregir_montos
from app.core.verificador_servicios import verificar_servicios
from app.core.verificador_hechos import verificar_hechos
from app.core.faq_responder import responder_faq_directo
from app.core.nucleo import procesar_nucleo
from app.config import get_settings
from app.logger import get_logger
from app.storage.firestore_client import (
    get_conversation,
    save_conversation,
    log_message,
    reset_conversation as fs_reset_conversation,
    get_all_faq,
    get_all_products,
    get_config,
)

log = get_logger(__name__)
settings = get_settings()

# ────────────────────────────────────────────────────────────
# FEATURE FLAGS
# ────────────────────────────────────────────────────────────
USE_VERIFIKA = os.getenv("USE_VERIFIKA", "false").lower() == "true"
USE_LEADS = os.getenv("USE_LEADS", "false").lower() == "true"
USE_INTERPRETER = os.getenv("USE_INTERPRETER", "false").lower() == "true"

# Verificador determinista (linea cero). off | shadow | on.
VERIFICADOR_MODE = settings.VERIFICADOR_MODE
VERIFIKA_CHECKER_ADVISORY = settings.VERIFIKA_CHECKER_ADVISORY
PROOF_MEMORY = settings.VERIFICADOR_PROOF_MEMORY

UMBRAL_CONFIANZA_ALTA = float(os.getenv("INTERPRETER_UMBRAL_ALTA", "0.85"))
UMBRAL_CONFIANZA_BAJA = float(os.getenv("INTERPRETER_UMBRAL_BAJA", "0.6"))

if USE_LEADS:
    from app.core.leads import procesar_mensaje_para_lead, crear_lead
    from app.core.notificador import notificar_lead
    log.info("leads_enabled")
else:
    log.info("leads_disabled")

if USE_VERIFIKA:
    from app.verifika.pipeline import verify_response
    log.info("verifika_enabled")
else:
    log.info("verifika_disabled")

if USE_INTERPRETER:
    from app.core.interpretador import interpretar_mensaje, extraer_productos_mostrados
    log.info("interpreter_enabled")
else:
    log.info("interpreter_disabled")


# Tools que devuelven productos del catalogo bajo distintas claves.
_TOOLS_CON_PRODUCTOS = (
    "search_products", "get_product_details", "find_within_budget",
    "compare_products", "recommend_product", "list_catalog",
)


def _build_evidence_from_tools(tools_called: list[dict],
                               tienda_id: str,
                               productos_vistos: list[dict] | None = None
                               ) -> list[dict]:
    """
    Construye la evidencia del Checker a partir de los resultados REALES de las
    tools, o sea lo que el Solver efectivamente vio. No relee el catalogo entero.

    - Productos: de search_products, get_product_details, find_within_budget,
      compare_products, recommend_product y el detalle de calculate_total.
    - FAQ: solo los temas que query_faq efectivamente devolvio, enriquecidos con
      los valores estructurados (rangos, montos) para que el Checker pueda
      verificar envios y descuentos.
    - Proofs: los calculos verificados de calculate_total.
    - Registro de sesion (flag EVIDENCIA_REGISTRO): los productos YA MOSTRADOS
      en turnos anteriores, con su precio real guardado por codigo. Repetir un
      precio que el bot ya mostro no puede ser alucinacion del valor; sin esto
      el juez veta en falso la clarificacion que cita opciones del turno
      anterior (visto 12-jun noche: "G502 a $70.000" real, bloqueado, puente).
    """
    productos_por_id: dict[str, dict] = {}
    faq_temas: set[str] = set()
    faq_evidence: list[dict] = []
    proof_evidence: list[dict] = []

    def _add_producto(p: dict):
        if not isinstance(p, dict):
            return
        pid = str(p.get("id") or "").upper()
        if not pid or pid in productos_por_id:
            return
        productos_por_id[pid] = {"tipo": "producto", **p}

    for t in tools_called:
        name = t.get("name", "")
        res = t.get("result")
        proof = t.get("proof")
        if proof:
            proof_evidence.append({"tipo": "proof", "tool": name, "proof": proof})

        if not isinstance(res, dict):
            continue

        if name in _TOOLS_CON_PRODUCTOS:
            for p in res.get("productos", []) or []:
                _add_producto(p)
            if isinstance(res.get("producto"), dict):
                _add_producto(res["producto"])

        if name == "calculate_total":
            for d in res.get("detalle", []) or []:
                _add_producto(d)

        if name == "query_faq" and res.get("encontrada"):
            tema = res.get("tema")
            if tema and tema not in faq_temas:
                faq_temas.add(tema)
                faq_evidence.append({
                    "tipo": "faq",
                    "id": tema,
                    "tema": tema,
                    "respuesta": res.get("respuesta", ""),
                    "faq_tipo": res.get("tipo", "informativo"),
                })

    # FAQ como evidencia: entra TODA la FAQ, asi una afirmacion verdadera sobre
    # un tema que el Solver no consulto, formas de pago por ejemplo, no cae como
    # sin_evidencia y no bloquea de gusto. La FAQ es chica y get_all_faq esta
    # cacheada, asi que es barato.
    try:
        faqs_full = get_all_faq(tienda_id=tienda_id)
        faq_evidence = []
        for tema_id, data in faqs_full.items():
            item = {
                "tipo": "faq",
                "id": tema_id,
                "tema": tema_id,
                "respuesta": data.get("respuesta", ""),
                "faq_tipo": data.get("tipo", "informativo"),
            }
            if data.get("valores"):
                item["valores"] = data["valores"]
            faq_evidence.append(item)
    except Exception as e:
        log.warning("verifika_full_faq_failed", error=str(e)[:100])

    if settings.EVIDENCIA_REGISTRO:
        for p in productos_vistos or []:
            _add_producto(p)

    return list(productos_por_id.values()) + faq_evidence + proof_evidence


def _build_evidence_for_verifika(tools_called: list[dict],
                                  tienda_id: str,
                                  productos_vistos: list[dict] | None = None
                                  ) -> list[dict]:
    """Reconstruye evidencia para Verifika desde los resultados reales de las
    tools que vio el Solver."""
    return _build_evidence_from_tools(tools_called, tienda_id,
                                      productos_vistos=productos_vistos)


def _extraer_productos_vistos(tools_called: list[dict]) -> list[dict]:
    """Saca {id, nombre, precio_ars} de los productos que devolvieron las tools
    este turno, para el registro de sesion. Liviano: no relee la FAQ ni el
    catalogo, solo mira lo que el Solver efectivamente vio. Dedup por ID dentro
    del turno; el merge con la memoria lo hace el orchestrator."""
    por_id: dict[str, dict] = {}

    def _add(p):
        if not isinstance(p, dict):
            return
        pid = str(p.get("id") or "").upper()
        # precio_ars en el catalogo; precio_unitario en el detalle de calculate_total.
        precio = p.get("precio_ars")
        if not isinstance(precio, (int, float)):
            precio = p.get("precio_unitario")
        nombre = p.get("nombre")
        if not pid or not nombre or not isinstance(precio, (int, float)):
            return
        por_id.setdefault(pid, {
            "id": pid, "nombre": nombre, "precio_ars": int(precio)})

    for t in tools_called:
        res = t.get("result") if isinstance(t, dict) else None
        if not isinstance(res, dict):
            continue
        name = t.get("name", "")
        if name in _TOOLS_CON_PRODUCTOS:
            for p in res.get("productos", []) or []:
                _add(p)
            if isinstance(res.get("producto"), dict):
                _add(res["producto"])
        if name == "calculate_total":
            for d in res.get("detalle", []) or []:
                _add(d)
    return list(por_id.values())


def _merge_productos_vistos(productos_turno: list[dict],
                            productos_memoria: list[dict],
                            cap: int) -> list[dict]:
    """Une los productos del turno con los de la memoria. El turno PISA a la
    memoria (precio fresco gana) y va al frente; dedup por id; capa a los `cap`
    mas recientes. Lo de este turno es lo mas relevante para el proximo."""
    por_id: dict[str, dict] = {}
    for p in list(productos_turno) + list(productos_memoria):
        pid = str(p.get("id") or "").upper()
        if pid and pid not in por_id:
            por_id[pid] = p
    return list(por_id.values())[:cap]


def _sin_links(texto: str) -> str:
    """Elimina toda URL del texto del Solver: links markdown enteros (con su
    etiqueta) y URLs sueltas. El unico link legitimo lo agrega el codigo en el
    cierre, despues de esta limpieza."""
    t = re.sub(r"\[([^\]]*)\]\(\s*https?://[^)]*\)", "", str(texto or ""))
    t = re.sub(r"\S*https?://\S+", "", t)
    return re.sub(r"[ \t]{2,}", " ", t).strip()


def _memoria_vencida(updated_at, ttl_horas: float) -> bool:
    """True si la memoria de compra ya vencio (mas de ttl_horas desde el ultimo
    turno). ttl_horas 0 = sin vencimiento. Tolera updated_at None o de tipos
    raros (Firestore Timestamp / datetime): ante la duda NO vence."""
    if not ttl_horas or ttl_horas <= 0 or updated_at is None:
        return False
    try:
        from datetime import datetime, timezone
        upd = (updated_at if isinstance(updated_at, datetime)
               else getattr(updated_at, "ToDatetime", lambda: None)())
        if upd is None:
            return False
        if upd.tzinfo is None:
            upd = upd.replace(tzinfo=timezone.utc)
        horas = (datetime.now(timezone.utc) - upd).total_seconds() / 3600.0
        return horas > ttl_horas
    except Exception:
        return False


async def _handoff_compra(user_id, canal, tienda_id, mensaje, producto_resuelto,
                            trace_id, presupuesto: str = ""):
    log.info("_handoff_compra_inicio")
    """Crea lead fuerte y devuelve respuesta de handoff con producto correcto."""
    if not USE_LEADS:
        return None
    try:
        # CIERRE_CONTRATO: si ya hay un lead activo pidiendo datos, NO se crea
        # otro ni se re-notifica (visto en prod 12-jun: "ok enviame link" +
        # "y el link de mp?" crearon dos leads en un minuto con el mismo
        # enlatado). Se reusa el lead y se actualiza el ultimo mensaje.
        lead_id = None
        lead_reusado = False
        if settings.CIERRE_CONTRATO:
            try:
                from app.core.leads import get_lead_activo, actualizar_lead
                _activo = get_lead_activo(user_id, canal, tienda_id)
                if _activo and _activo.get("estado") == "datos_solicitados":
                    lead_id = _activo.get("lead_id")
                    lead_reusado = True
                    actualizar_lead(lead_id, tienda_id,
                                    {"ultimo_mensaje": (mensaje or "")[:500]})
                    log.info("interpreter_handoff_lead_reusado",
                             lead_id=lead_id, trace_id=trace_id)
            except Exception as e:
                log.warning("handoff_lead_activo_error", error=str(e)[:120],
                            trace_id=trace_id)
        if not lead_id:
            lead_id = crear_lead(
                user_id=user_id, canal=canal, tienda_id=tienda_id,
                ultimo_mensaje=mensaje,
                frase_disparadora=f"interpretador:decision_compra:{producto_resuelto}",
                nivel="fuerte", estado_inicial="datos_solicitados",
                orden=presupuesto,
            )
            log.info("interpreter_handoff_fuerte", lead_id=lead_id,
                     producto=producto_resuelto, trace_id=trace_id)
            try:
                await notificar_lead(
                    tienda_id=tienda_id, user_id=user_id, canal=canal,
                    estado="intencion_fuerte", nombre="", telefono="",
                    ultimo_mensaje=f"{mensaje} | producto: {producto_resuelto}",
                )
            except Exception as e:
                log.warning("notificar_lead_failed", error=str(e)[:120])

        # CIERRE_CONTRATO: si el cliente pide el link de pago, la respuesta lo
        # RECONOCE en vez de repetir el enlatado que lo ignora.
        _pide_link = bool(re.search(
            r"(?i)\blink\b|mercado\s*pago|\bmp\b|como\s+pago|donde\s+pago",
            mensaje or ""))
        if settings.CIERRE_CONTRATO and _pide_link:
            respuesta = (
                f"Dale, te paso el link de pago del {producto_resuelto} "
                "apenas me digas tu nombre y un telefono de contacto. "
                "Pasamelos y te lo mando al toque."
            )
        elif lead_reusado:
            respuesta = (
                f"Seguimos con el {producto_resuelto}. Para avanzar solo me "
                "falta tu nombre y un telefono donde ubicarte, pasamelos y "
                "cerramos."
            )
        else:
            respuesta = (
                f"Buenisimo, te confirmo el {producto_resuelto}. "
                "En un momento te contacta una persona del equipo para coordinar "
                "tu compra. Pasame por favor tu nombre y un telefono donde ubicarte."
            )
        return respuesta, lead_id
    except Exception as e:
        log.warning("interpreter_handoff_error", error=str(e)[:200],
                    trace_id=trace_id)
        return None


def _ctx_productos_vistos(productos_vistos: list[dict]) -> str:
    """Arma el bloque por-turno con los productos del registro de sesion y su id
    real, para inyectarlo al Solver. Asi cuando el cliente se refiere a uno ya
    mostrado, el modelo tiene el product_id para calculate_total sin re-buscar.
    Devuelve '' si no hay nada que pasar."""
    lineas = []
    for p in productos_vistos:
        pid = p.get("id")
        nombre = p.get("nombre")
        precio = p.get("precio_ars")
        if not pid or not nombre:
            continue
        if isinstance(precio, (int, float)):
            lineas.append(f"- {nombre} (id {pid}): ${precio:,.0f}".replace(",", "."))
        else:
            lineas.append(f"- {nombre} (id {pid})")
    if not lineas:
        return ""
    return ("\n\n[Productos ya mostrados en la charla, con su id real. Si el "
            "cliente se refiere a uno de estos, usa ese id para calculate_total; "
            "no lo busques de nuevo ni lo inventes:\n" + "\n".join(lineas) + "]")


# NUEVA_COMPRA_RESET: frases que piden descartar el pedido en curso y arrancar
# de cero. Deteccion por codigo, sin depender del interprete (que clasifica
# "nueva compra" como saludo). Entre el verbo y el sustantivo se toleran hasta
# dos palabras ("borra todo el pedido", "olvidate de ese carrito").
_PATRON_NUEVA_COMPRA = re.compile(
    r"(?i)\b(?:"
    r"(?:nuev[oa]|otr[oa])\s+(?:compra|pedido)"
    r"|(?:empez\w*|empec\w*|arran[cq]\w*|comen[cz]\w*)\s+de\s+(?:nuevo|cero)"
    r"|(?:borr\w*|cancel\w*|olvid\w*|descart\w*|anul\w*)\s+"
    r"(?:\S+\s+){0,2}(?:pedido|carrito|compra|presupuesto)"
    r")\b")


# Pregunta que SI es sobre el pedido/carrito/total vigente: aca el presupuesto
# es relevante y NO hay que suprimirlo (el codigo lo arma y lo respalda). Sin esto
# "cuanto me queda en total?" caia como pregunta generica y el total viajaba sin
# verdad por codigo. Distinto de "donde aprieto el boton", que no toca el pedido.
_RE_PREGUNTA_PEDIDO = re.compile(
    r"(?i)\b(total|presupuesto|carrito|pedido|me\s+queda|cuanto\s+llevo"
    r"|cuanto\s+(?:me\s+)?(?:queda|sale|cuesta|es|va|seria|sal[ei]))\b")


def _es_nueva_compra(mensaje: str) -> bool:
    """El cliente pide descartar el pedido en curso y empezar de cero."""
    return bool(_PATRON_NUEVA_COMPRA.search(mensaje or ""))


def _es_nueva_compra_pura(mensaje: str) -> bool:
    """El mensaje es SOLO el pedido de reset (corto y sin numeros): se responde
    por codigo. Si ademas trae el pedido nuevo ("nueva compra: 2 mouse"), va al
    pipeline normal con la memoria ya limpia."""
    m = (mensaje or "").strip()
    return len(m) <= 40 and not re.search(r"\d", m)


def _respuesta_nueva_compra() -> str:
    """Confirmacion del reset, por codigo: no hay numeros que ganar."""
    return ("Listo, arrancamos de cero: el pedido anterior queda descartado. "
            "Que estas buscando?")


def _es_saludo_simple(intencion, confianza, mensaje: str) -> bool:
    """Saludo puro segun el interprete: confianza alta, mensaje corto y sin
    numeros (un pedido con cantidades jamas se trata como saludo)."""
    return (intencion == "saludo" and (confianza or 0) >= 0.85
            and len((mensaje or "").strip()) <= 40
            and not re.search(r"\d", mensaje or ""))


def _respuesta_saludo() -> str:
    """Saludo de apertura directo, sin invocar el Solver. Cordial e invita a
    avanzar: si el cliente queria algo mas, lo dice en el proximo turno y ahi
    corre el Solver normal. No se pierde venta, a lo sumo un turno."""
    return ("Hola, como va. Te puedo dar una mano con productos, precios, "
            "envios o formas de pago. Que estas buscando?")


# Pedido GENERICO de catalogo. Conservador: frases claras de catalogo/categorias/
# lista completa. NO dispara con 'que teclados tenes' (busqueda de categoria
# puntual, que el pipeline normal resuelve mostrando productos).
_RE_CATALOGO = re.compile(
    r"(?i)\b(cat[aá]logo|que\s+categor[ií]as|que\s+rubros|lista\s+completa"
    r"|lista\s+de\s+productos|mostrame\s+todo|todo\s+el\s+catalogo"
    r"|que\s+productos\s+(?:tenes|tienen|venden|manejan|hay))\b")


def _pide_catalogo(mensaje: str) -> bool:
    return bool(_RE_CATALOGO.search(mensaje or ""))


def _respuesta_catalogo(tienda_id: str) -> str | None:
    """Lista las categorias reales con su conteo, por codigo. None si no se
    pueden leer (cae al pipeline normal)."""
    try:
        from app.core.tools import list_catalog
        from app.core.tools_context import set_current_tienda
        set_current_tienda(tienda_id)
        r = list_catalog()
        resumen = r.get("categorias_resumen") or {}
        if not resumen:
            return None
        cats = sorted(resumen.keys())
        total = r.get("total", sum(resumen.values()))
        lineas = "\n".join(f"- {c} ({resumen[c]})" for c in cats)
        return (f"Tenemos {total} productos en estas categorias:\n{lineas}\n"
                "Decime cual te interesa y te paso los modelos y precios.")
    except Exception:
        return None


def _respuesta_clarificacion(candidatos: list[str]) -> str:
    log.info("_respuesta_clarificacion_inicio")
    """Arma respuesta de clarificacion con dos o tres opciones."""
    if not candidatos:
        return "Disculpa, no entendi bien. A cual te referis?"
    if len(candidatos) == 1:
        return f"Te referis al {candidatos[0]}?"
    if len(candidatos) == 2:
        return f"Te referis al {candidatos[0]} o al {candidatos[1]}?"
    opciones = ", ".join(candidatos[:-1]) + f", o {candidatos[-1]}"
    return f"Tenemos varios. Te referis al {opciones}?"


# Un mensaje que CAMBIA el pedido (suma/saca/cambia cantidad, o trae la zona de
# envio) no es un "cerralo": el motor determinista tiene que recalcularlo. Sin
# esto, el atajo de decision_compra (Caso A) ataja al handoff y se come el delta
# ("mejor que sean 2 teclados", "el envio es a Cordoba") dejando el total viejo.
_RE_CAMBIA_PEDIDO = re.compile(
    r"(?i)\b(sumale|sumar|sum[aá]\b|agreg\w*|a[nñ]ad\w*|incorpor\w*"
    r"|saca\w*|saque\w*|quit\w*|elimin\w*|borr\w*"
    r"|mejor\s+(?:\d|un|dos|tres|cuatro|cinco)|que\s+sean?\b|en\s+vez\s+de"
    r"|cambi\w*\s+a|dej\w*\s+en|pon[eé]\w*\s+\d"
    r"|env[ií]o|envi\w*|despach\w*|mand\w*\s+a|c[oó]digo\s+postal|\bcp\b)")


def _mensaje_cambia_pedido(msg: str) -> bool:
    return bool(_RE_CAMBIA_PEDIDO.search(msg or ""))


async def process_message(user_id: str, raw_message: str,
                          tienda_id: str | None = None,
                          canal: str = "telegram") -> str:
    log.info("process_message_inicio")
    """Procesa un mensaje del cliente. Devuelve la respuesta."""
    trace_id = str(uuid.uuid4())[:8]
    t0 = time.time()
    tid = tienda_id or settings.TIENDA_ID

    # Observabilidad: atar trace_id y tienda al contexto. El logger tiene
    # merge_contextvars, asi que TODOS los eventos de este request, incluidos
    # los de tools, firestore, agente y verifika, heredan el trace_id sin tener
    # que pasarlo a mano. Cada request corre en su propia task asyncio con su
    # copia de contexto, asi que no se mezcla entre usuarios concurrentes.
    structlog.contextvars.bind_contextvars(trace_id=trace_id, tienda_id=tid)

    # Tiempos por etapa (nivel uno de observabilidad, siempre activo y barato).
    timings: dict[str, int] = {}

    log.info("message_received", trace_id=trace_id, tienda_id=tid,
             user_id=user_id, msg_preview=raw_message[:80])

    # ─── SOLO_INTERPRETE: modo de prueba del intérprete (interruptor maestro) ───
    # Va ARRIBA DE TODO. Mientras está prendido (default), el turno entero lo
    # maneja interprete_libre (intérprete + solver libre + memoria) y NINGÚN otro
    # flag ni camino corre. Es como Martín quiere probar la interpretación con el
    # resto apagado, sin depender de la config de Cloud Run. Off vuelve al viejo.
    if settings.SOLO_INTERPRETE:
        from app.core.interprete_libre import procesar_interprete_libre
        resp = await procesar_interprete_libre(
            user_id, raw_message, tid, canal, trace_id)
        structlog.contextvars.clear_contextvars()
        return resp

    # ─── MODO_LIBRE: el modelo responde libre, sin ninguna capa ───
    # El experimento de Martin (16-jun). El turno entero lo maneja
    # app/core/modo_libre.py: Gemini con un prompt corto de venta y las tools
    # atadas a Firestore (catalogo + FAQs), sin interprete, nucleo, provider,
    # verificadores, corrector ni gate. Es a proposito: primero ver al modelo
    # vender libre y leer el texto crudo, despues filtrar solo lo que alucine.
    # Va ARRIBA DE TODO, incluso del anti-jailbreak, para que la salida sea de
    # verdad cruda. En off esta rama no existe y el pipeline viejo corre intacto.
    if settings.MODO_LIBRE:
        from app.core.modo_libre import procesar_modo_libre
        resp = await procesar_modo_libre(
            user_id, raw_message, tid, canal, trace_id)
        structlog.contextvars.clear_contextvars()
        return resp

    # ─── ANTI-JAILBREAK (primera linea, filtro de entrada por codigo) ───
    # Corre antes de cualquier LLM. En 'on', un patron de manipulacion corta el
    # pipeline con una respuesta estatica de marca, sin gastar tokens. En
    # 'shadow' solo loguea para medir falsos positivos. En 'off' no corre.
    if settings.ANTI_JAILBREAK != "off":
        try:
            from app.core.antijailbreak import (
                evaluar_mensaje, RESPUESTA_BLOQUEO)
            _aj = evaluar_mensaje(raw_message)
            if _aj["ataque"]:
                if settings.ANTI_JAILBREAK == "on":
                    log.warning("antijailbreak_bloqueo", trace_id=trace_id,
                                motivo=_aj["motivo"], patron=_aj["patron"])
                    return RESPUESTA_BLOQUEO
                log.info("antijailbreak_shadow", trace_id=trace_id,
                         motivo=_aj["motivo"], patron=_aj["patron"])
        except Exception as e:
            log.error("antijailbreak_error", trace_id=trace_id,
                      error=str(e)[:160])

    # ─── CAMINO_NUEVO: la columna limpia de cinco pasos ───
    # Con el flag on, el turno entero lo maneja app/core/camino_nuevo.py: la
    # canera determinista que ya existe en piezas verdes (interprete que emite
    # comandos -> director -> provider -> estado_pedido -> redactor + render),
    # sin las capas legacy de abajo que competian. El anti-jailbreak ya corrio
    # arriba, asi protege tambien al camino nuevo. En off, esta rama no existe y
    # el pipeline viejo corre intacto.
    if settings.CAMINO_NUEVO:
        from app.core.camino_nuevo import procesar_camino_nuevo
        resp = await procesar_camino_nuevo(
            user_id, raw_message, tid, canal, trace_id)
        structlog.contextvars.clear_contextvars()
        return resp

    conv = get_conversation(user_id, tienda_id=tid)
    history = conv.get("history", [])
    estado_anterior = conv.get("estado_conversacion", "saludo")
    estado_nuevo = estado_anterior
    ultima_compra = None
    ofrecer_opciones = None
    # PROOF de turnos anteriores (memoria de compra): permiten verificar el total
    # cuando el cliente confirma y el bot lo repite sin recalcular.
    proofs_memoria = conv.get("proofs_recientes", []) or []
    # Ultimo presupuesto armado por la calculadora, para adjuntarlo al lead en
    # la confirmacion, aunque este turno no recalcule.
    presupuesto_memoria = conv.get("ultimo_presupuesto", "") or ""
    # Registro de sesion: productos vistos en turnos anteriores con su product_id.
    # Es la memoria de la cocina que la memoria de texto no guarda.
    productos_vistos_memoria = conv.get("productos_vistos", []) or []
    # Ultima localidad de envio mencionada, para cotizar el envio cuando el cliente
    # dice "el envio ahi" sin repetir la ciudad.
    ultima_localidad_memoria = conv.get("ultima_localidad", "") or ""
    # Carrito vigente: items del ultimo presupuesto calculado, para que el
    # pedido conserve su identidad cuando el cliente saca/confirma.
    carrito_memoria = conv.get("carrito_vigente", []) or []
    # Pedido pendiente: el pedido a medio armar (cantidades dichas, modelos
    # sin elegir) esperando el criterio del cliente para completarse por codigo.
    pedido_pendiente_memoria = conv.get("pedido_pendiente") or None

    # MEMORIA_TTL_HORAS: la memoria de COMPRA vence. Un presupuesto, carrito o
    # localidad de una charla de dias atras no puede cerrar una venta de hoy ni
    # aportar una direccion fantasma (visto en prod 12-jun: cierre con pedido
    # viejo y "Calle Arenales 200" de otra conversacion). El historial de texto
    # y los productos vistos se conservan: vence solo lo que puede cobrar.
    if _memoria_vencida(conv.get("updated_at"), settings.MEMORIA_TTL_HORAS) \
            and (presupuesto_memoria or carrito_memoria
                 or ultima_localidad_memoria or pedido_pendiente_memoria):
        log.info("memoria_compra_vencida", trace_id=trace_id,
                 ttl_horas=settings.MEMORIA_TTL_HORAS)
        presupuesto_memoria = ""
        carrito_memoria = []
        ultima_localidad_memoria = ""
        pedido_pendiente_memoria = None

    # ─── INTERPRETADOR (pre-Solver) ───
    interpretacion = None
    interpreter_short_circuit = False
    final_response = None
    # Pedido pendiente a persistir: dict = guardar, {} = limpiar (se consumio
    # o lo reemplazo un pedido nuevo), None = no tocar el campo en Firestore.
    pedido_pendiente_out = None

    # ─── RESET_CODE: codigo secreto de pruebas (antes de cualquier LLM) ───
    # Si el mensaje es exactamente el codigo configurado (ej: "verifika2026"),
    # se borra toda la conversacion y se responde por codigo. Util para pruebas
    # desde el mismo numero sin cambiar el entorno de produccion.
    _rc = (settings.RESET_CODE or "").strip().lower()
    if _rc and (raw_message or "").strip().lower() == _rc:
        presupuesto_memoria = ""
        carrito_memoria = []
        ultima_localidad_memoria = ""
        proofs_memoria = []
        productos_vistos_memoria = []
        pedido_pendiente_memoria = None
        history = []
        conv["summary"] = ""
        estado_anterior = "saludo"
        estado_nuevo = "saludo"
        try:
            save_conversation(user_id, [], "", tienda_id=tid,
                              estado_conversacion="saludo",
                              proofs_recientes=[], ultimo_presupuesto="",
                              productos_vistos=[], ultima_localidad="",
                              carrito_vigente=[], pedido_pendiente={})
        except Exception as e:
            log.warning("reset_code_save_failed", trace_id=trace_id,
                        error=str(e)[:120])
        if USE_LEADS:
            try:
                from app.core.leads import descartar_leads_activos
                descartar_leads_activos(user_id, canal, tid)
            except Exception:
                pass
        log.info("reset_code_triggered", trace_id=trace_id, user_id=user_id)
        final_response = "Listo, conversacion reiniciada. Empezamos de cero."
        interpreter_short_circuit = True

    # ─── NUEVA_COMPRA_RESET (por codigo, antes de cualquier LLM) ───
    # "nueva compra" descarta la memoria de compra ENTERA y el historial de
    # texto: ahi viven los datos fantasma (la direccion "Arenales" de otra
    # charla) y el pedido viejo que el Solver re-vende si se lo seguimos
    # sirviendo. El borrado se persiste YA, sin depender de como termine el
    # turno: si el proceso muere despues, la memoria igual quedo limpia.
    if settings.NUEVA_COMPRA_RESET and _es_nueva_compra(raw_message):
        presupuesto_memoria = ""
        carrito_memoria = []
        ultima_localidad_memoria = ""
        proofs_memoria = []
        productos_vistos_memoria = []
        pedido_pendiente_memoria = None
        history = []
        conv["summary"] = ""
        estado_anterior = "saludo"
        estado_nuevo = "saludo"
        try:
            save_conversation(user_id, [], "", tienda_id=tid,
                              estado_conversacion="saludo",
                              proofs_recientes=[], ultimo_presupuesto="",
                              productos_vistos=[], ultima_localidad="",
                              carrito_vigente=[], pedido_pendiente={})
        except Exception as e:
            log.warning("nueva_compra_reset_save_failed", trace_id=trace_id,
                        error=str(e)[:120])
        # Descartar el lead viejo: el reset de la conversacion NO tocaba los
        # leads, asi un pedido a medio llenar (nombre, pago, orden de otra compra)
        # sobrevivia y se completaba con la direccion nueva (prod 16-jun: cierre
        # con "javier rojas" y 2 gabinetes sobre una compra de RAM).
        if USE_LEADS:
            try:
                from app.core.leads import descartar_leads_activos
                _nd = descartar_leads_activos(user_id, canal, tid)
                if _nd:
                    log.info("nueva_compra_leads_descartados", trace_id=trace_id,
                             cantidad=_nd)
            except Exception as e:
                log.warning("nueva_compra_leads_error", trace_id=trace_id,
                            error=str(e)[:120])
        log.info("nueva_compra_reset", trace_id=trace_id,
                 puro=_es_nueva_compra_pura(raw_message))
        if _es_nueva_compra_pura(raw_message):
            final_response = _respuesta_nueva_compra()
            interpreter_short_circuit = True

    # CATALOGO_CODIGO: pedido generico de catalogo -> el codigo lista las
    # categorias reales (no el Solver, que a veces dice "ahi tenes 880 productos"
    # sin listar nada). Determinista, como el saludo. Si no se pueden leer las
    # categorias, _respuesta_catalogo da None y sigue el pipeline normal.
    if (settings.CATALOGO_CODIGO and not interpreter_short_circuit
            and _pide_catalogo(raw_message)):
        _cat = _respuesta_catalogo(tid)
        if _cat:
            final_response = _cat
            interpreter_short_circuit = True
            log.info("catalogo_por_codigo", trace_id=trace_id)

    if USE_INTERPRETER and not interpreter_short_circuit:
        _ts_interp = time.perf_counter()
        try:
            interpretacion = await interpretar_mensaje(
                raw_message, history, trace_id,
                estado_anterior=estado_anterior, tienda_id=tid)

            intencion = interpretacion.get("intencion")
            confianza = interpretacion.get("confianza", 0.0)
            producto_resuelto = interpretacion.get("producto_resuelto")
            candidatos = interpretacion.get("candidatos", [])
            estado_nuevo = interpretacion.get("estado_conversacion") or estado_anterior
            ofrecer_opciones = interpretacion.get("ofrecer_opciones")

            # SALUDO_CODIGO: a un saludo se responde saludando, por codigo.
            # Visto 12-jun ("nueva compra"): el Solver volco el presupuesto
            # viejo del carrito e invento el umbral del envio gratis ($300.000
            # con regla real de $250.000); el juez bloqueo dos veces y el
            # cliente recibio un fallback. Un saludo nunca pasa por el Solver:
            # no hay numeros que ganar y si que perder.
            if (settings.SALUDO_CODIGO
                    and _es_saludo_simple(intencion, confianza, raw_message)):
                final_response = _respuesta_saludo()
                interpreter_short_circuit = True
                log.info("saludo_por_codigo", trace_id=trace_id)

            # Caso A: decision de compra con alta confianza, handoff directo.
            # Regla de orden: solo atajamos si ya se mostro un presupuesto en un
            # turno anterior. Si no, no cerramos sin precio: dejamos que el
            # Solver corra y responda el numero primero.
            # Subordinacion al motor determinista: si el mensaje CAMBIA el pedido
            # (delta o trae la zona de envio), NO se ataja al handoff aunque el
            # interprete lo lea como decision_compra; el provider y el delta
            # tienen que recalcular y mostrar el total nuevo. El cierre lo cierra
            # despues la capa de leads, ya con el total fresco a la vista.
            _hay_presupuesto_previo = bool(str(presupuesto_memoria).strip())
            _cambia_pedido = ((settings.CARRITO_DELTA or settings.PROVIDER)
                              and _mensaje_cambia_pedido(raw_message))
            if (intencion == "decision_compra"
                    and confianza >= UMBRAL_CONFIANZA_ALTA
                    and producto_resuelto
                    and _hay_presupuesto_previo
                    and not _cambia_pedido):
                handoff = await _handoff_compra(
                    user_id, canal, tid, raw_message,
                    producto_resuelto, trace_id,
                    presupuesto=presupuesto_memoria)
                if handoff:
                    final_response, _lead_id = handoff
                    interpreter_short_circuit = True
                    ultima_compra = producto_resuelto

            # Caso B: confianza baja con candidatos, pedir clarificacion.
            # Solo si los candidatos son productos reales mostrados, no inventados.
            elif confianza < UMBRAL_CONFIANZA_BAJA and candidatos:
                productos_history = extraer_productos_mostrados(history)
                nombres_validos = {p["nombre"] for p in productos_history}
                candidatos_validos = [
                    cand for cand in candidatos
                    if cand in nombres_validos or len(cand) > 40
                ]
                if candidatos_validos:
                    final_response = _respuesta_clarificacion(candidatos_validos)
                    interpreter_short_circuit = True
                    log.info("interpreter_clarificacion", trace_id=trace_id,
                             candidatos_count=len(candidatos_validos))
                else:
                    log.info("interpreter_candidatos_invalidos", trace_id=trace_id,
                             candidatos_originales=candidatos[:3])

        except Exception as e:
            log.error("interpreter_error", trace_id=trace_id,
                      error=str(e)[:200])
            # Si el interpretador falla, seguimos al flujo normal
            interpreter_short_circuit = False
        timings["interpret_ms"] = int((time.perf_counter() - _ts_interp) * 1000)

        # Guard anti pierde-el-hilo: una charla en curso no vuelve a 'saludo'.
        # Evita que el solver se reinicie con un '¡Hola! Soy vendedor...' a mitad
        # de conversacion por una mala lectura del interpretador (falla e).
        if settings.ESTADO_NO_REGRESA_SALUDO and history:
            from app.core.interpretador import corregir_estado_regresion
            _estado_corr = corregir_estado_regresion(
                estado_nuevo, estado_anterior, hay_historial=True)
            if _estado_corr != estado_nuevo:
                log.info("estado_regresion_corregida", trace_id=trace_id,
                         de=estado_nuevo, a=_estado_corr)
                estado_nuevo = _estado_corr

    # ─── NUCLEO FUENTE DE VERDAD (cuatro puertas) ───
    # Camino A: el codigo resuelve el hecho de la fuente y enruta por una de
    # cuatro puertas (responder / confirmar / consultar / seguir). Tiene
    # precedencia sobre FAQ_DIRECTO. Si la puerta es 'seguir', delega al pipeline
    # de hoy intacto. Detras de la perilla maestra; en off no se ejecuta.
    if settings.NUCLEO_FUENTE_VERDAD and not interpreter_short_circuit:
        try:
            from app.core.interpretador import _llamar_llm as _llamar_redactor
            _bn = settings.BUSINESS_NAME
            try:
                _bn = get_config("business_name", tienda_id=tid) or _bn
            except Exception:
                pass
            _nuc = await procesar_nucleo(
                raw_message, interpretacion, get_all_faq(tienda_id=tid),
                _llamar_redactor, etapa=estado_nuevo, business_name=_bn,
                trace_id=trace_id)
            if _nuc["manejado"]:
                final_response = _nuc["respuesta"]
                interpreter_short_circuit = True
                log.info("nucleo_manejado", trace_id=trace_id,
                         puerta=_nuc["puerta"], vestido=_nuc.get("vestido"))
        except Exception as e:
            log.warning("nucleo_error", trace_id=trace_id, error=str(e)[:160])

    # ─── RESPONDEDOR DETERMINISTA DE FAQ (puerta 1) ───
    # Una pregunta pura de politica con tema claro y sin producto en juego se
    # contesta con el texto curado de la FAQ, sin pasar por el Solver. Cero
    # generacion, cero alucinacion. Conservador: ante la duda defiere al Solver.
    if settings.FAQ_DIRECTO and not interpreter_short_circuit:
        try:
            _hay_prod = bool(
                interpretacion and (
                    interpretacion.get("producto_resuelto")
                    or interpretacion.get("candidatos")
                    or interpretacion.get("intencion") == "decision_compra"))
            _faq_dir = responder_faq_directo(
                raw_message, get_all_faq(tienda_id=tid),
                hay_producto=_hay_prod, trace_id=trace_id)
            if _faq_dir:
                final_response = _faq_dir["respuesta"]
                interpreter_short_circuit = True
                log.info("faq_directo_short_circuit", trace_id=trace_id,
                         tema=_faq_dir["tema"])
        except Exception as e:
            log.warning("faq_directo_error", trace_id=trace_id,
                        error=str(e)[:120])

    # ─── SOLVER (solo si Interpretador no corto el flujo) ───
    response_text = None
    agent_meta = {"tools_called": [], "iterations": 0}
    # Verdad del turno: el presupuesto que el codigo arma por su cuenta (cotizador
    # por codigo). Si la compuerta bloquea, cae a esto en vez de censurar.
    presupuesto_codigo = None

    # ─── DETERMINISTA PRE-SOLVER: delta del carrito + estado + puerta de confirmacion ───
    # Antes del Solver, por codigo: (1) si el cliente cambio el carrito
    # (agrega/saca/cambia cantidad), se muta por codigo; (2) se arma la planilla
    # del turno (estado_pedido); (3) si el turno es AMBIGUO, el codigo pregunta el
    # mismo con datos reales del catalogo y saltea el Solver, igual que las
    # puertas del nucleo y de FAQ directo. Asi el Solver, cuando corre, nunca
    # recibe un turno ambiguo ni sin datos. El _prov_turno se reusa abajo para no
    # cotizar dos veces. Todo gateado; en off el pipeline es identico al previo.
    _prov_turno = None
    _estado_turno = None
    _delta_aplicado = False
    _hubo_cambio_carrito = False
    # ─── DIRECTOR_LLM: el LLM gobierna el carrito (reemplaza carrito_delta) ───
    # Las acciones que el interprete emitio en su JSON (agregar/sacar/cambiar/
    # vaciar) se ejecutan por codigo contra el catalogo. El director es la
    # AUTORIDAD del carrito este turno: se marca _delta_aplicado para que
    # pedido_multi no vuelva a extraer del texto y compita. Sin acciones, el
    # carrito queda igual (no hay arrastre). En off, esta rama no corre.
    if (settings.DIRECTOR_LLM and not interpreter_short_circuit
            and interpretacion is not None):
        try:
            from app.core.director import aplicar_acciones
            _acc = interpretacion.get("acciones_carrito") or []
            _dir = aplicar_acciones(_acc, carrito_memoria, tid, trace_id=trace_id)
            carrito_memoria = _dir["carrito"]
            _hubo_cambio_carrito = bool(_dir["cambios"])
            _delta_aplicado = True
            if _dir["cambios"]:
                log.info("director_carrito_orch", trace_id=trace_id,
                         cambios=len(_dir["cambios"]), items=len(carrito_memoria))
        except Exception as e:
            log.warning("director_orch_error", trace_id=trace_id,
                        error=str(e)[:160])
    elif (settings.CARRITO_DELTA and not interpreter_short_circuit
            and carrito_memoria):
        try:
            from app.core.carrito_delta import mutar_carrito
            _delta = mutar_carrito(raw_message, carrito_memoria, tienda_id=tid,
                                   interpretacion=interpretacion,
                                   trace_id=trace_id)
            if _delta and _delta["cambios"]:
                carrito_memoria = _delta["carrito"]
                _delta_aplicado = True
                _hubo_cambio_carrito = True
                log.info("carrito_delta_aplicado_orch", trace_id=trace_id,
                         cambios=len(_delta["cambios"]),
                         items=len(carrito_memoria))
        except Exception as e:
            log.warning("carrito_delta_orch_error", trace_id=trace_id,
                        error=str(e)[:160])
    # ─── EL MENSAJE NUEVO MANDA (flag INTENCION_MANDA) ───
    # Si el interprete clasifico el turno como pregunta u "otra" (no compra, no
    # dato, no exploracion) y el cliente no toco el carrito este turno, el codigo
    # NO arma confirmacion ni le inyecta el presupuesto vigente al Solver: lo deja
    # contestar la pregunta sin re-estampar el pedido viejo. El carrito sigue en
    # memoria, solo no se re-muestra. En off, _pregunta_manda es siempre False y
    # el pipeline es identico al previo.
    _pregunta_manda = bool(
        settings.INTENCION_MANDA
        and interpretacion
        and interpretacion.get("intencion") in ("pregunta_especifica", "otra")
        and not _hubo_cambio_carrito
        and not _RE_PREGUNTA_PEDIDO.search(raw_message or ""))
    if _pregunta_manda:
        log.info("intencion_manda_pregunta", trace_id=trace_id,
                 intencion=interpretacion.get("intencion"))
    # Carrito del turno: ante una pregunta, el provider IGNORA el carrito de
    # memoria (no se arrastra el pedido viejo al contrato), pero igual cotiza lo
    # que el cliente nombre ahora. El carrito NO se borra: sigue en memoria para
    # el proximo turno de compra. En off (o turno normal) es el carrito de siempre.
    _carrito_turno = ([] if _pregunta_manda
                      else (carrito_memoria if settings.CARRITO_VIGENTE else []))
    if settings.PROVIDER and not interpreter_short_circuit:
        try:
            from app.core.provider import proveer as _proveer_fn
            _prov_turno = _proveer_fn(
                raw_message, tienda_id=tid,
                registro=productos_vistos_memoria,
                carrito=_carrito_turno,
                localidad_memoria=ultima_localidad_memoria,
                estado=estado_nuevo, interpretacion=interpretacion,
                pedido_pendiente=pedido_pendiente_memoria,
                delta_aplicado=_delta_aplicado,
                trace_id=trace_id)
            # Con DIRECTOR_LLM, si el director toco el carrito, ESE carrito es la
            # unica verdad: se anulan las selecciones alternativas del provider
            # (foco/ab/multi) que competian e inyectaban un A/B ajeno. El
            # carrito_calc queda y es lo que cotiza/renderiza el resto.
            if (settings.DIRECTOR_LLM and _hubo_cambio_carrito
                    and _prov_turno is not None):
                for _k in ("foco", "ab", "multi", "foco_envio_calc"):
                    _prov_turno[_k] = None
            if settings.ESTADO_PEDIDO:
                from app.core.estado_pedido import construir_estado
                _estado_turno = construir_estado(
                    _prov_turno, estado_conv=estado_nuevo,
                    interpretacion=interpretacion, trace_id=trace_id)
                # Con DIRECTOR_LLM, el carrito lo gobierna el director: el provider
                # NO debe cortocircuitar con su propia confirmacion/A-B (competia y
                # le ganaba al carrito del director). Subordinado: solo cotiza.
                # El cortocircuito (saltea el LLM con un "cual preferis?" canned)
                # SOLO si el turno realmente quiere cotizar. Sin intencion de
                # compra, una ambiguedad del catalogo no debe secuestrar la
                # respuesta: visto vivo 16-jun, "5 items en CSV", "conectar a una
                # licuadora philips" o "metete en el router" disparaban el canned
                # y salteaban al LLM (que deberia responder/rechazar). Con esto el
                # LLM corre con el contrato en mano (los candidatos siguen ahi).
                if (settings.CONFIRMACION_PROVIDER
                        and not settings.DIRECTOR_LLM
                        and _estado_turno["confirmacion"]["necesita"]
                        and _prov_turno.get("quiere_cotizar")):
                    final_response = _estado_turno["confirmacion"]["texto"]
                    interpreter_short_circuit = True
                    log.info("confirmacion_corto_pre_solver", trace_id=trace_id,
                             tipo=_estado_turno["confirmacion"]["tipo"])
        except Exception as e:
            log.warning("determinista_pre_solver_error", trace_id=trace_id,
                        error=str(e)[:160])
            _prov_turno = None

    if not interpreter_short_circuit:
        # Si hay producto resuelto, inyectarlo al Solver via mensaje
        mensaje_enriquecido = raw_message

        # ─── PROVIDER (flag): motor determinista total ───
        # El codigo calcula TODO lo calculable del turno (foco, carrito, envio,
        # catalogo) aunque nadie lo pida, y arma UN solo contrato para el Solver.
        # Cuando corre, apaga las inyecciones legacy de abajo (que competian
        # entre si en charlas largas). Sus calculos entran a tools_called como
        # registros sinteticos para que la evidencia los respalde.
        _legacy_iny = True
        _provider_records: list = []
        if settings.PROVIDER:
            try:
                from app.core.provider import (
                    proveer, contrato, verdad_del_turno)
                # Reusa el calculo del pre-Solver si ya corrio (no cotiza dos
                # veces); si el pre-Solver fallo o no corrio, cotiza aca. Mismo
                # carrito del turno (vacio ante una pregunta: no arrastra el viejo).
                _prov = _prov_turno if _prov_turno is not None else proveer(
                    raw_message, tienda_id=tid,
                    registro=productos_vistos_memoria,
                    carrito=_carrito_turno,
                    localidad_memoria=ultima_localidad_memoria,
                    estado=estado_nuevo, interpretacion=interpretacion,
                    pedido_pendiente=pedido_pendiente_memoria,
                    delta_aplicado=_delta_aplicado,
                    trace_id=trace_id)
                if _prov.get("pendiente_nuevo") is not None:
                    pedido_pendiente_out = _prov["pendiente_nuevo"]
                elif _prov.get("pendiente_consumido"):
                    pedido_pendiente_out = {}
                _prod_interp = None
                if (USE_INTERPRETER and interpretacion
                        and interpretacion.get("producto_resuelto")
                        and interpretacion.get("confianza", 0)
                        >= UMBRAL_CONFIANZA_ALTA):
                    _prod_interp = interpretacion["producto_resuelto"]
                _bloque = contrato(
                    _prov, estado=estado_nuevo,
                    ofrecer_opciones=ofrecer_opciones,
                    registro=productos_vistos_memoria,
                    producto_interpretador=_prod_interp)
                if _bloque:
                    mensaje_enriquecido = raw_message + _bloque
                presupuesto_codigo = verdad_del_turno(_prov)
                _provider_records = _prov["registros"]
                _legacy_iny = False
                log.info("provider_contrato_inyectado", trace_id=trace_id,
                         largo=len(_bloque), registros=len(_provider_records),
                         verdad=bool(presupuesto_codigo))
            except Exception as e:
                # Si el Provider falla, cae al camino legacy entero: el turno
                # nunca se pierde por el motor nuevo.
                log.error("provider_error", trace_id=trace_id,
                          error=str(e)[:200])
                _legacy_iny = True
                _provider_records = []

        if (_legacy_iny and USE_INTERPRETER and interpretacion
                and interpretacion.get("producto_resuelto")
                and interpretacion.get("confianza", 0) >= UMBRAL_CONFIANZA_ALTA):
            producto = interpretacion["producto_resuelto"]
            mensaje_enriquecido = (
                f"{raw_message}\n\n"
                f"[Contexto del Interpretador: el cliente se refiere al "
                f"{producto}]"
            )
            log.info("interpreter_enriched_solver", trace_id=trace_id,
                     producto=producto)

        if _legacy_iny:
            ctx_estado = f"\n\n[Estado de la conversacion: {estado_nuevo}]"
            if ofrecer_opciones:
                ctx_estado += (f"\n[ofrecer_opciones: el interpretador detecto dos "
                               f"caminos, presentalos como opcion A y B y pregunta "
                               f"cual prefiere: {ofrecer_opciones}]")
            mensaje_enriquecido = mensaje_enriquecido + ctx_estado

        # Registro de sesion: pasarle al Solver los productos ya mostrados con su
        # id real, para que resuelva "comprame ese" sin re-buscar ni inventar el
        # id. Solo con el flag on y si hay registro. La memoria de texto guarda la
        # prosa; esto le da la memoria de la cocina.
        if _legacy_iny and settings.REGISTRO_SESION and productos_vistos_memoria:
            # Movimiento 2: el codigo resuelve el HECHO. Escalera de precedencia,
            # de mas a menos dueño del dato por codigo, cada peldaño ahorra mas
            # tokens que el anterior:
            #  1) COTIZA_CODIGO: el codigo arma el presupuesto y se lo da hecho al
            #     Solver para que solo lo redacte. El numero no pasa por el LLM.
            #  2) RESOLVER_PEDIDO: el codigo resuelve el id y se lo da en una linea
            #     dirigida; el Solver llama la calculadora con ese id.
            #  3) registro completo: el listado de vistos como contexto.
            _cot = None
            if settings.COTIZA_CODIGO:
                try:
                    from app.core.cotizar_codigo import (
                        quiere_cotizar, cotizar_pedido, bloque_para_solver)
                    if quiere_cotizar(raw_message, estado_nuevo):
                        _cot = cotizar_pedido(
                            raw_message, productos_vistos_memoria, tid,
                            localidad=ultima_localidad_memoria, trace_id=trace_id)
                except Exception as e:
                    log.warning("cotiza_codigo_error", trace_id=trace_id,
                                error=str(e)[:160])
            # Presupuesto A/B (flag): la referencia matchea dos productos, el
            # codigo cotiza los dos y el Solver presenta opcion A y opcion B.
            _ab = None
            if not _cot and settings.PRESUPUESTO_AB and settings.COTIZA_CODIGO:
                try:
                    from app.core.cotizar_codigo import (
                        quiere_cotizar, cotizar_pedido_ab,
                        bloque_ab_para_solver, presentacion_ab)
                    if quiere_cotizar(raw_message, estado_nuevo):
                        _ab = cotizar_pedido_ab(
                            raw_message, productos_vistos_memoria, tid,
                            localidad=ultima_localidad_memoria,
                            trace_id=trace_id)
                except Exception as e:
                    log.warning("presupuesto_ab_error", trace_id=trace_id,
                                error=str(e)[:160])
            _hit = None
            if not _cot and not _ab and settings.RESOLVER_PEDIDO:
                try:
                    from app.core.resolver_pedido import resolver_pedido
                    _hit = resolver_pedido(raw_message, productos_vistos_memoria)
                except Exception as e:
                    log.warning("resolver_pedido_error", trace_id=trace_id,
                                error=str(e)[:160])
            if _cot:
                mensaje_enriquecido = mensaje_enriquecido + bloque_para_solver(_cot)
                presupuesto_codigo = (_cot.get("calc") or {}).get("presentacion")
                log.info("cotiza_codigo_inyectado", trace_id=trace_id,
                         producto=_cot["producto_id"], cantidad=_cot["cantidad"])
            elif _ab:
                mensaje_enriquecido = mensaje_enriquecido + bloque_ab_para_solver(_ab)
                presupuesto_codigo = presentacion_ab(_ab)
                log.info("presupuesto_ab_inyectado", trace_id=trace_id,
                         a=_ab["opciones"][0]["producto_id"],
                         b=_ab["opciones"][1]["producto_id"])
            elif _hit:
                mensaje_enriquecido = mensaje_enriquecido + (
                    f"\n\n[El cliente se refiere a {_hit['nombre']}, id "
                    f"{_hit['producto_id']}, cantidad {_hit['cantidad']}. Usa "
                    "EXACTAMENTE ese id en calculate_total; no lo busques de nuevo "
                    "ni lo cambies.]")
                log.info("resolver_pedido_inyectado", trace_id=trace_id,
                         producto=_hit["producto_id"], motivo=_hit["motivo"])
            else:
                _ctx_prod = _ctx_productos_vistos(productos_vistos_memoria)
                if _ctx_prod:
                    mensaje_enriquecido = mensaje_enriquecido + _ctx_prod
                    log.info("registro_sesion_inyectado", trace_id=trace_id,
                             productos=len(productos_vistos_memoria))

        # Carrito vigente (flag): el pedido YA presupuestado, con ids reales.
        # Sin esto, en "sacale X" o "el total final" el modelo rearma el pedido
        # desde el registro o una re-busqueda y mete OTROS productos (precios
        # reales, identidad cambiada; clase carrito_drift del arnes).
        if _legacy_iny and settings.CARRITO_VIGENTE and carrito_memoria:
            _items_txt = "; ".join(
                f"{it.get('cantidad', 1)}x {it.get('nombre')} (id {it.get('id')})"
                for it in carrito_memoria if it.get("id"))
            if _items_txt:
                mensaje_enriquecido = mensaje_enriquecido + (
                    "\n\n[PEDIDO VIGENTE, ya presupuestado: " + _items_txt +
                    ". Si el cliente confirma, saca o cambia cantidades, "
                    "recalcula con calculate_total partiendo de ESTOS ids; "
                    "NO los reemplaces por otros productos. Solo agrega un id "
                    "distinto si el cliente pide un producto nuevo.]")
                log.info("carrito_vigente_inyectado", trace_id=trace_id,
                         items=len(carrito_memoria))

        # Busqueda disparada por CODIGO (flag BUSQUEDA_POR_CODIGO). Si el
        # interpretador detecto exploracion o pregunta de producto, el backend
        # corre la busqueda ANTES del Solver y le inyecta los resultados como
        # evidencia. El modelo ya tiene el catalogo relevante aunque no sepa o
        # no quiera llamar tools (cañeria rota con gemini/gemma en el molino
        # del 10-jun). El registro sintetico se suma a tools_called despues de
        # run_agent para que el verificador respalde estos precios.
        _busqueda_codigo_record = None
        if (_legacy_iny and settings.BUSQUEDA_POR_CODIGO and interpretacion
                and not presupuesto_codigo):
            _intencion_prod = interpretacion.get("intencion") in (
                "exploracion", "pregunta_especifica")
            _ref_prod = (interpretacion.get("producto_resuelto")
                         or interpretacion.get("candidatos"))
            if _intencion_prod or _ref_prod:
                try:
                    from app.core.tools import search_products
                    from app.core.tools_context import set_current_tienda
                    set_current_tienda(tid)
                    _q = (interpretacion.get("producto_resuelto")
                          or (interpretacion.get("candidatos") or [None])[0]
                          or raw_message)
                    _res = search_products(query=_q)
                    _prods = (_res.get("productos") or [])[:5]
                    _claves = ("id", "nombre", "precio", "precio_ars", "stock",
                               "stock_unidades", "categoria", "marca", "modelo")
                    _prods = [{k: p[k] for k in _claves if k in p}
                              for p in _prods if isinstance(p, dict)]
                    _res_compacto = {
                        "encontrados": _res.get("encontrados", len(_prods)),
                        "productos": _prods,
                    }
                    if _res.get("mensaje_para_llm"):
                        _res_compacto["mensaje_para_llm"] = _res["mensaje_para_llm"]
                    mensaje_enriquecido = mensaje_enriquecido + (
                        "\n\n[El sistema YA busco en el catalogo por este "
                        "mensaje. Resultado REAL de search_products(query="
                        f"'{_q}'): {json.dumps(_res_compacto, ensure_ascii=False)}. "
                        "Usa estos datos como evidencia: precios, stock e ids "
                        "son la fuente. Si necesitas detalle o calcular un "
                        "total, llama las tools con estos ids.]")
                    _busqueda_codigo_record = {
                        "name": "search_products", "args": {"query": _q},
                        "result_keys": list(_res.keys()),
                        "proof": None, "result": _res,
                    }
                    log.info("busqueda_codigo_inyectada", trace_id=trace_id,
                             query=str(_q)[:60],
                             encontrados=_res_compacto["encontrados"])
                except Exception as e:
                    log.warning("busqueda_codigo_error", trace_id=trace_id,
                                error=str(e)[:160])

        # Destino del envio para la calculadora defensiva. Determinista, por
        # keywords del mensaje del cliente. El LLM no lo elige: lo inyecta el
        # backend por contextvar, igual que la tienda. Unico camino, sin flag.
        try:
            from app.core.tools_context import set_current_destino
            from app.core.calc_defensiva import destino_a_categoria
            _dest = destino_a_categoria(raw_message)
            set_current_destino(_dest)
            if _dest:
                log.info("destino_detectado", trace_id=trace_id, destino=_dest)
        except Exception as e:
            log.warning("destino_deteccion_error", trace_id=trace_id,
                        error=str(e)[:120])

        _ts_solver = time.perf_counter()
        # ─── SOLVER_CODIGO_PRIMARIO: redactor por codigo ANTES del Solver ───
        # Si el contrato tiene dato, responde por codigo y saltea el Solver
        # (modo sin-LLM, deterministico). Si no hay dato, response_text queda
        # None y cae al Solver normal abajo. Mantiene el interprete LLM.
        response_text = None
        agent_meta = {}
        if settings.SOLVER_CODIGO_PRIMARIO and _prov_turno is not None:
            try:
                from app.core.responder_codigo import responder as _resp_cod
                _cat_txt = (_respuesta_catalogo(tid)
                            if _pide_catalogo(raw_message) else None)
                _det = _resp_cod(_prov_turno, _estado_turno, raw_message,
                                 catalogo_texto=_cat_txt)
                if _det:
                    response_text = _det
                    agent_meta = {"tools_called": list(_provider_records or [])}
                    log.info("solver_codigo_primario", trace_id=trace_id)
            except Exception as e:
                log.warning("solver_codigo_primario_error", trace_id=trace_id,
                            error=str(e)[:160])

        if not response_text:
            response_text, agent_meta = await run_agent(
                mensaje_enriquecido, history, trace_id,
                tienda_id=tid, user_id=user_id)
        timings["solver_ms"] = int((time.perf_counter() - _ts_solver) * 1000)

        # ─── SOLVER_CODIGO: fallback sin LLM ───
        # Si el Solver cayo a fallback/vacio, el redactor por codigo arma la
        # respuesta desde el contrato + la planilla (deterministico, no inventa).
        # Solo actua cuando el Solver YA fallo: el camino feliz no se toca.
        if settings.SOLVER_CODIGO and _prov_turno is not None:
            _es_fb = (not str(response_text or "").strip()) or response_text in (
                settings.FALLBACK_MESSAGE, settings.VERIFIKA_FALLBACK_MESSAGE)
            if _es_fb:
                try:
                    from app.core.responder_codigo import responder as _resp_cod
                    _cat_txt = (_respuesta_catalogo(tid)
                                if _pide_catalogo(raw_message) else None)
                    _det = _resp_cod(_prov_turno, _estado_turno, raw_message,
                                     catalogo_texto=_cat_txt)
                    if _det:
                        response_text = _det
                        log.info("solver_codigo_fallback", trace_id=trace_id)
                except Exception as e:
                    log.warning("solver_codigo_error", trace_id=trace_id,
                                error=str(e)[:160])

        # La busqueda hecha por codigo entra a tools_called: el verificador y
        # el Checker necesitan respaldar los precios que el Solver cito de ahi.
        if _busqueda_codigo_record:
            agent_meta.setdefault("tools_called", []).insert(
                0, _busqueda_codigo_record)

        # Los calculos del Provider tambien entran a tools_called: el
        # verificador, la compuerta y el arnes respaldan con esto los numeros
        # del contrato que el Solver haya citado.
        if _provider_records:
            agent_meta.setdefault("tools_called", [])[0:0] = _provider_records

        # ─── LIBRO DE ASIENTOS (Fase 2): extraer ANTES de limpiar ───
        # El Solver pega al final un bloque [[LIBRO]] con cada cifra de dinero y su
        # fuente. Se saca del texto crudo aca (antes de validate/clean, que
        # colapsan espacios y lo romperian) para que el cliente nunca lo vea. Los
        # asientos se auditan mas abajo, cuando ya esta armada la evidencia.
        libro_asientos: list[dict] = []
        libro_emitido = False
        # Modo solver: el libro viene pegado en la respuesta del Solver, hay que
        # sacarlo del texto CRUDO aca (antes de clean). En los modos extractor/fusion
        # el Solver respondio libre y el libro se obtiene mas abajo, con la evidencia.
        if (settings.LIBRO_ASIENTOS and settings.LIBRO_MODO == "solver"
                and response_text):
            try:
                from app.core.libro import parsear_libro, diag_record
                prosa, libro_asientos, hubo = parsear_libro(response_text)
                libro_emitido = hubo
                response_text = prosa
                log.info("libro_parseado", trace_id=trace_id, hubo=hubo,
                         asientos=len(libro_asientos))
                diag_record(user_id, emitio_libro=hubo,
                            n_asientos=len(libro_asientos))
            except Exception as e:
                log.error("libro_parse_error", trace_id=trace_id,
                          error=str(e)[:200])

        # ─── GUARDIAN L1 ───
        _ts_guardian = time.perf_counter()
        validation = validate_response(response_text, trace_id, tienda_id=tid)
        cleaned_response = clean_response(response_text, tienda_id=tid)
        timings["guardian_ms"] = int((time.perf_counter() - _ts_guardian) * 1000)

        # ─── EVIDENCIA COMPARTIDA (tools de este turno + PROOF de memoria) ───
        # La usan el verificador determinista y el Checker LLM. Sumar los PROOF
        # de turnos anteriores hace que en la confirmacion el total repetido
        # siga teniendo respaldo aunque el bot no recalcule.
        verifika_result = None
        verificador_result = None
        servicios_result = None
        hechos_result = None
        evidence: list[dict] = []
        if response_text and response_text != settings.FALLBACK_MESSAGE:
            try:
                evidence = _build_evidence_for_verifika(
                    agent_meta.get("tools_called", []), tid,
                    productos_vistos=productos_vistos_memoria)
                for p in proofs_memoria:
                    evidence.append({"tipo": "proof", "tool": "memoria",
                                     "proof": p})
            except Exception as e:
                log.warning("evidence_build_failed", trace_id=trace_id,
                            error=str(e)[:100])

        # Precios reales del catalogo de la tienda: red para que la correccion NO
        # pise un numero que es un precio legitimo (aunque no este en la evidencia
        # del turno, por venir citado de un turno anterior). Se arma una vez por
        # request desde el catalogo cacheado. Vacio si algo falla (la correccion
        # vuelve al comportamiento previo, el piso duro corre igual).
        precios_validos: set = set()
        if ((settings.LIBRO_ASIENTOS or settings.VERIFICADOR_AUTOCORRIGE
                or settings.COMPUERTA_UNICA)
                and response_text != settings.FALLBACK_MESSAGE):
            try:
                precios_validos = {
                    int(p["precio_ars"])
                    for p in (get_all_products(tienda_id=tid) or [])
                    if isinstance(p.get("precio_ars"), (int, float))
                }
            except Exception as e:
                log.warning("precios_validos_error", trace_id=trace_id,
                            error=str(e)[:120])

        # ─── LIBRO via CORRECTOR (modos extractor/fusion) ───
        # El Solver respondio libre; aca el corrector LLM declara el libro de la
        # prosa (resuelve el 75% de emision del Solver, que esta sobrecargado).
        # extractor: llamada dedicada, +1. fusion: reusa la pasada del corrector
        # anclado que ya corre, por eso despues saltea ese corrector. El corrector
        # solo IDENTIFICA las cifras; el codigo las corrige en la auditoria de abajo.
        corrector_consumido = False
        if (settings.LIBRO_ASIENTOS
                and settings.LIBRO_MODO in ("extractor", "fusion")
                and not settings.COMPUERTA_UNICA
                and evidence and response_text != settings.FALLBACK_MESSAGE):
            try:
                from app.core.corrector import extraer_libro
                from app.core.libro import diag_record
                libro_asientos = await asyncio.to_thread(
                    extraer_libro, cleaned_response, evidence, trace_id)
                libro_emitido = True  # el canal del libro corrio (no el Solver)
                diag_record(user_id, emitio_libro=True,
                            n_asientos=len(libro_asientos))
                if settings.LIBRO_MODO == "fusion":
                    corrector_consumido = True
            except Exception as e:
                log.error("libro_extractor_error", trace_id=trace_id,
                          error=str(e)[:200])

        # ─── AUDITORIA DEL LIBRO (Fase 2): corregir cifras por su fuente ───
        # Cada asiento numerico se cuadra contra la evidencia. Si una cifra esta mal
        # y la verdad esta en su fuente declarada, el codigo la reescribe en la
        # prosa, preciso por fuente (precio vs total vs envio), sin LLM. Corre antes
        # del corrector anclado y del piso duro, asi todos ven el texto ya corregido.
        libro_aprob: list[dict] = []
        if (settings.LIBRO_ASIENTOS and libro_asientos and evidence
                and response_text != settings.FALLBACK_MESSAGE):
            try:
                from app.core.libro import (
                    auditar_libro, aplicar_correcciones, libro_aprobado,
                    diag_record)
                _aud = auditar_libro(libro_asientos, evidence, trace_id=trace_id,
                                     precios_validos=precios_validos)
                libro_aprob = libro_aprobado(libro_asientos, _aud)
                diag_record(user_id, correcciones=_aud["correcciones"],
                            problemas=len(_aud["problemas"]))
                if _aud["correcciones"]:
                    _ap = aplicar_correcciones(
                        cleaned_response, _aud["correcciones"], trace_id=trace_id)
                    if _ap["cambiada"]:
                        cleaned_response = _ap["respuesta"]
                        log.info("libro_corregido", trace_id=trace_id,
                                 aplicadas=_ap["aplicadas"][:10])
            except Exception as e:
                log.error("libro_auditoria_error", trace_id=trace_id,
                          error=str(e)[:200])

        # ─── CORRECTOR ANCLADO (pasada stateless: aterriza la respuesta a la
        # evidencia ANTES del piso duro) ───
        # Recibe la respuesta del Solver tal cual (con su A/B o confirmacion) mas
        # la evidencia del turno, sin memoria ni pregunta original, y corrige o
        # quita lo que no tenga respaldo. Reescribe cleaned_response, asi todos
        # los gates de abajo (determinista, servicios, hechos, checker) ven el
        # texto ya aterrizado. Fail-open: si falla, deja la respuesta original y
        # el piso duro corre igual.
        if (settings.CORRECTOR_ANCLADO and not corrector_consumido
                and not settings.COMPUERTA_UNICA
                and response_text
                and response_text != settings.FALLBACK_MESSAGE and evidence):
            try:
                from app.core.corrector import corregir_respuesta
                # Fase 3: si hay libro aprobado, el corrector lo recibe como unica
                # verdad de plata y ata el render a esas cifras (no aterriza a
                # ciegas). Sin libro, corre como siempre.
                _corr = await asyncio.to_thread(
                    corregir_respuesta, cleaned_response, evidence,
                    trace_id, libro_aprob or None)
                if _corr.get("ok") and _corr.get("cambiada"):
                    log.info("corrector_aplicado", trace_id=trace_id)
                    cleaned_response = _corr["respuesta_final"]
            except Exception as e:
                log.error("corrector_wire_error", trace_id=trace_id,
                          error=str(e)[:200])

        # ─── VERIFICADOR DETERMINISTA (linea cero, decide por codigo) ───
        if (VERIFICADOR_MODE != "off" and response_text
                and response_text != settings.FALLBACK_MESSAGE):
            try:
                verificador_result = verificar_respuesta(
                    cleaned_response, evidence, trace_id=trace_id)
            except Exception as e:
                log.error("verificador_error", trace_id=trace_id,
                          error=str(e)[:200])
                verificador_result = {"ok": True, "accion": "responder"}

            # Diag del verificador: en modo on no corre el Checker, asi que sin
            # esto no veriamos el texto que se bloqueo. Solo con DIAG_TRACE.
            if settings.DIAG_TRACE and verificador_result is not None:
                _ev_tipos: dict[str, int] = {}
                for e in evidence:
                    _k = e.get("tipo", "?")
                    _ev_tipos[_k] = _ev_tipos.get(_k, 0) + 1
                log.info(
                    "diag_verificador",
                    accion=verificador_result.get("accion"),
                    no_respaldados=verificador_result.get(
                        "numeros_no_respaldados", []),
                    total_numeros=verificador_result.get("total_numeros"),
                    evidence_tipos=_ev_tipos,
                    tools_turno=[
                        t.get("name")
                        for t in agent_meta.get("tools_called", [])
                    ],
                    solver_response=cleaned_response[:1500],
                )

        # ─── VERIFICADOR DE SERVICIOS (segunda linea, plata aparte) ───
        # Marca promesas de servicios que la tienda no ofrece. Codigo puro, usa la
        # misma evidencia. No bloquea numeros: cuida capacidades inventadas.
        if (settings.VERIFICADOR_SERVICIOS != "off" and response_text
                and response_text != settings.FALLBACK_MESSAGE):
            try:
                servicios_result = verificar_servicios(
                    cleaned_response, evidence, trace_id=trace_id)
            except Exception as e:
                log.error("verificador_servicios_error", trace_id=trace_id,
                          error=str(e)[:200])
                servicios_result = {"ok": True, "accion": "responder"}

        # ─── VERIFICADOR DE HECHOS (tercera linea: reglas mal narradas) ───
        # Marca cuando el bot dice mal una REGLA de la tienda (plazo de envio,
        # un dia de entrega que el correo no garantiza, un detalle de pago sin
        # respaldo). Codigo puro, misma evidencia. No toca numeros ni capacidades.
        if (settings.VERIFICADOR_HECHOS != "off" and response_text
                and response_text != settings.FALLBACK_MESSAGE):
            try:
                hechos_result = verificar_hechos(
                    cleaned_response, evidence, trace_id=trace_id)
            except Exception as e:
                log.error("verificador_hechos_error", trace_id=trace_id,
                          error=str(e)[:200])
                hechos_result = {"ok": True, "accion": "responder"}

        # ─── CHECKER LLM (Verifika) ───
        # Gatea solo si el verificador NO esta en on. En on queda desconectado,
        # salvo que se lo deje de asesor con VERIFIKA_CHECKER_ADVISORY para log.
        _correr_checker = (
            USE_VERIFIKA and response_text
            and not settings.COMPUERTA_UNICA
            and response_text != settings.FALLBACK_MESSAGE
            and (VERIFICADOR_MODE != "on" or VERIFIKA_CHECKER_ADVISORY
                 or settings.CHECKER_GATEA)
        )
        if _correr_checker:
            try:
                _ts_verifika = time.perf_counter()
                verifika_result = await asyncio.to_thread(
                    verify_response,
                    respuesta_solver=cleaned_response,
                    evidence=evidence,
                    trace_id=trace_id,
                    fallback_message=settings.VERIFIKA_FALLBACK_MESSAGE,
                )
                timings["verifika_ms"] = int(
                    (time.perf_counter() - _ts_verifika) * 1000)

                if settings.DIAG_TRACE:
                    _ver_by_id = {
                        v.get("id"): v
                        for v in verifika_result.get("veredictos", [])
                    }
                    _claims = []
                    for a in verifika_result.get("afirmaciones", []):
                        v = _ver_by_id.get(a.get("id"), {})
                        _claims.append({
                            "texto": a.get("texto"),
                            "tipo": a.get("tipo"),
                            "veredicto": v.get("veredicto"),
                            "razon": v.get("razon"),
                        })
                    _ev_tipos: dict[str, int] = {}
                    for e in evidence:
                        _k = e.get("tipo", "?")
                        _ev_tipos[_k] = _ev_tipos.get(_k, 0) + 1
                    log.info(
                        "diag_verifika",
                        accion=verifika_result["accion"],
                        score=round(verifika_result["confianza"]["score"], 2),
                        evidence_count=len(evidence),
                        evidence_tipos=_ev_tipos,
                        tools_turno=[
                            t.get("name")
                            for t in agent_meta.get("tools_called", [])
                        ],
                        solver_response=cleaned_response[:1500],
                        claims=_claims,
                    )
            except Exception as e:
                log.error("verifika_pipeline_error", trace_id=trace_id,
                          error=str(e)[:200])
                verifika_result = None

        # ─── DECISION FINAL ───
        # COMPUERTA UNICA (movimiento 3): si el flag maestro esta on, la decision
        # la toma SOLO la compuerta y se saltean todos los gates viejos. Una pasada
        # contra la fuente: corrige la plata hacia la verdad, bloquea lo que no se
        # puede corregir. En off, esta rama no existe y corre el flujo de hoy.
        if settings.COMPUERTA_UNICA:
            from app.core.compuerta import evaluar as _compuerta_evaluar
            _cp = _compuerta_evaluar(
                cleaned_response, evidence, trace_id=trace_id,
                precios_validos=precios_validos,
                verdad_turno=presupuesto_codigo)
            # respuesta_final ya viene resuelta: el texto corregido si paso, la
            # verdad del turno si cayo, o "" si no hay con que caer. En ese ultimo
            # caso ponemos el fallback, que los puentes (si estan on) convierten en
            # algo que mantiene la venta.
            final_response = (_cp["respuesta_final"]
                              or settings.VERIFIKA_FALLBACK_MESSAGE)
            log.info("compuerta_unica_decidio", trace_id=trace_id,
                     accion=_cp["accion"], corrigio=_cp["corrigio_plata"],
                     clases=list(_cp["problemas"].keys()))
        elif VERIFICADOR_MODE == "on":
            # Gatea el codigo. Si una cifra no tiene respaldo, no se manda.
            if verificador_result and not verificador_result.get("ok", True):
                arreglado = False
                # AUTOCORRIGE (Fase 1): correccion determinista del total ANTES de
                # repromptear. Si la verdad esta en la evidencia, el codigo reescribe
                # la cifra mala por la buena sin LLM. Solo se acepta si el texto
                # corregido verifica ok; si no, se descarta y sigue AUTOFIX/fallback.
                if settings.VERIFICADOR_AUTOCORRIGE:
                    try:
                        ac = autocorregir_montos(
                            cleaned_response, evidence, trace_id=trace_id,
                            precios_validos=precios_validos)
                        if ac["cambiada"] and ac["verificacion"].get("ok"):
                            final_response = ac["respuesta"]
                            cleaned_response = ac["respuesta"]
                            verificador_result = ac["verificacion"]
                            arreglado = True
                            log.info("autocorrige_aplicado", trace_id=trace_id,
                                     correcciones=ac["correcciones"][:10])
                    except Exception as e:
                        log.error("autocorrige_error", trace_id=trace_id,
                                  error=str(e)[:200])
                # AUTOFIX: reintento guiado antes de tirar el fallback.
                if not arreglado and settings.AUTOFIX:
                    no_resp = verificador_result.get("numeros_no_respaldados", [])
                    log.info("autofix_intento", trace_id=trace_id,
                             no_respaldados=no_resp[:10])
                    try:
                        _ts_fix = time.perf_counter()
                        correctivo = (
                            mensaje_enriquecido
                            + "\n\n[Sistema: en tu respuesta anterior estos numeros "
                            f"no estaban respaldados por la calculadora ni el "
                            f"catalogo: {no_resp}. Rehace el presupuesto llamando a "
                            "calculate_total y NO inventes ningun numero. Mostra "
                            "solo cifras que devuelvan las herramientas.]"
                        )
                        resp2, meta2 = await run_agent(
                            correctivo, history, trace_id,
                            tienda_id=tid, user_id=user_id)
                        clean2 = clean_response(resp2, tienda_id=tid)
                        ev2 = _build_evidence_for_verifika(
                            meta2.get("tools_called", []), tid,
                            productos_vistos=productos_vistos_memoria)
                        for p in proofs_memoria:
                            ev2.append({"tipo": "proof", "tool": "memoria",
                                        "proof": p})
                        vr2 = verificar_respuesta(clean2, ev2, trace_id=trace_id)
                        timings["autofix_ms"] = int(
                            (time.perf_counter() - _ts_fix) * 1000)
                        if vr2.get("ok"):
                            final_response = clean2
                            cleaned_response = clean2
                            verificador_result = vr2
                            agent_meta = meta2
                            arreglado = True
                            log.info("autofix_ok", trace_id=trace_id)
                        else:
                            log.info("autofix_fallo", trace_id=trace_id,
                                     no_respaldados=vr2.get(
                                         "numeros_no_respaldados", [])[:10])
                    except Exception as e:
                        log.error("autofix_error", trace_id=trace_id,
                                  error=str(e)[:200])
                if not arreglado:
                    final_response = settings.VERIFIKA_FALLBACK_MESSAGE
            else:
                final_response = cleaned_response
        elif verifika_result:
            # off o shadow: gatea el Checker LLM, conducta de siempre.
            final_response = verifika_result["respuesta_final"]
        else:
            final_response = cleaned_response

        # En shadow comparamos las dos decisiones sin cambiar conducta.
        if VERIFICADOR_MODE == "shadow" and verificador_result is not None:
            log.info("verificador_shadow", trace_id=trace_id,
                     verificador_accion=verificador_result.get("accion"),
                     verifika_accion=(verifika_result or {}).get("accion"),
                     numeros_no_respaldados=verificador_result.get(
                         "numeros_no_respaldados", [])[:10])

        # ─── GATE DE SERVICIOS (independiente del modo de plata) ───
        # Si la respuesta promete un servicio que la tienda no ofrece, no se manda.
        # No corre AUTOFIX: una promesa inventada no se arregla recalculando, asi
        # que va directo al fallback. En shadow solo loguea para medir.
        if (settings.VERIFICADOR_SERVICIOS == "on" and servicios_result is not None
                and not settings.COMPUERTA_UNICA):
            if (not servicios_result.get("ok", True)
                    and final_response not in (
                        settings.VERIFIKA_FALLBACK_MESSAGE,
                        settings.FALLBACK_MESSAGE)):
                inventados = servicios_result.get("servicios_inventados", [])
                # Preview del texto bloqueado: sin esto, diagnosticar un falso
                # positivo obliga a adivinar que frase gatillo (visto 10-jun).
                log.info("servicios_bloqueo", trace_id=trace_id,
                         servicios=inventados,
                         respuesta_preview=str(final_response)[:200])
                arreglado_serv = False
                # AUTOFIX para servicios: reintento guiado antes del fallback,
                # misma logica que con la plata pero apuntado a la promesa inventada.
                if settings.AUTOFIX:
                    try:
                        correctivo = (
                            mensaje_enriquecido
                            + "\n\n[Sistema: en tu respuesta anterior prometiste "
                            f"servicios que la tienda NO ofrece segun la FAQ: "
                            f"{inventados}. NO los prometas. Si el cliente los pide, "
                            "deci con honestidad que eso no figura y que lo "
                            "consultas, y ofrece lo que SI hay. No inventes "
                            "capacidades ni servicios.]")
                        resp_s, meta_s = await run_agent(
                            correctivo, history, trace_id,
                            tienda_id=tid, user_id=user_id)
                        clean_s = clean_response(resp_s, tienda_id=tid)
                        ev_s = _build_evidence_for_verifika(
                            meta_s.get("tools_called", []), tid,
                            productos_vistos=productos_vistos_memoria)
                        for p in proofs_memoria:
                            ev_s.append({"tipo": "proof", "tool": "memoria",
                                         "proof": p})
                        vs2 = verificar_servicios(clean_s, ev_s, trace_id=trace_id)
                        # La nueva respuesta tambien tiene que pasar el de plata.
                        vr_s = (verificar_respuesta(clean_s, ev_s, trace_id=trace_id)
                                if VERIFICADOR_MODE != "off" else {"ok": True})
                        if vs2.get("ok") and vr_s.get("ok", True):
                            final_response = clean_s
                            arreglado_serv = True
                            log.info("servicios_autofix_ok", trace_id=trace_id)
                        else:
                            log.info("servicios_autofix_fallo", trace_id=trace_id,
                                     servicios=vs2.get("servicios_inventados", []))
                    except Exception as e:
                        log.error("servicios_autofix_error", trace_id=trace_id,
                                  error=str(e)[:200])
                if not arreglado_serv:
                    final_response = settings.VERIFIKA_FALLBACK_MESSAGE
        elif (settings.VERIFICADOR_SERVICIOS == "shadow"
                and servicios_result is not None):
            log.info("servicios_shadow", trace_id=trace_id,
                     accion=servicios_result.get("accion"),
                     servicios=servicios_result.get("servicios_inventados", []))

        # ─── GATE del verificador de HECHOS ───
        # Si la respuesta narra mal una regla (plazo, dia de entrega, pago), no se
        # manda tal cual. Con AUTOFIX reintenta una respuesta correcta (con el
        # plazo real) ANTES del fallback: el contrario de mentir no es callar, es
        # decir la verdad comercial. En shadow solo loguea para medir.
        if (settings.VERIFICADOR_HECHOS == "on" and hechos_result is not None
                and not settings.COMPUERTA_UNICA):
            if (not hechos_result.get("ok", True)
                    and final_response not in (
                        settings.VERIFIKA_FALLBACK_MESSAGE,
                        settings.FALLBACK_MESSAGE)):
                problemas_h = hechos_result.get("problemas", [])
                log.info("hechos_bloqueo", trace_id=trace_id, problemas=problemas_h)
                arreglado_hechos = False
                if settings.AUTOFIX:
                    try:
                        correctivo = (
                            mensaje_enriquecido
                            + "\n\n[Sistema: en tu respuesta anterior narraste mal "
                            f"una regla de la tienda ({problemas_h}). Corregi sin "
                            "inventar: NO prometas un dia exacto de entrega ni "
                            "acortes el plazo; deci el plazo en dias habiles TAL "
                            "CUAL la FAQ (usa query_faq) y aclara que el dia depende "
                            "del correo. NO inventes detalles de pago que no esten "
                            "en la FAQ. Da una respuesta honesta y comercial con el "
                            "dato real.]")
                        resp_h, meta_h = await run_agent(
                            correctivo, history, trace_id,
                            tienda_id=tid, user_id=user_id)
                        clean_h = clean_response(resp_h, tienda_id=tid)
                        ev_h = _build_evidence_for_verifika(
                            meta_h.get("tools_called", []), tid,
                            productos_vistos=productos_vistos_memoria)
                        for p in proofs_memoria:
                            ev_h.append({"tipo": "proof", "tool": "memoria",
                                         "proof": p})
                        vh2 = verificar_hechos(clean_h, ev_h, trace_id=trace_id)
                        vr_h = (verificar_respuesta(clean_h, ev_h, trace_id=trace_id)
                                if VERIFICADOR_MODE != "off" else {"ok": True})
                        if vh2.get("ok") and vr_h.get("ok", True):
                            final_response = clean_h
                            arreglado_hechos = True
                            log.info("hechos_autofix_ok", trace_id=trace_id)
                        else:
                            log.info("hechos_autofix_fallo", trace_id=trace_id,
                                     problemas=vh2.get("problemas", []))
                    except Exception as e:
                        log.error("hechos_autofix_error", trace_id=trace_id,
                                  error=str(e)[:200])
                if not arreglado_hechos:
                    final_response = settings.VERIFIKA_FALLBACK_MESSAGE
        elif (settings.VERIFICADOR_HECHOS == "shadow"
                and hechos_result is not None):
            log.info("hechos_shadow", trace_id=trace_id,
                     accion=hechos_result.get("accion"),
                     problemas=hechos_result.get("problemas", []))

        # ─── GUARDA DE COMPLETITUD (Fase 4): red anti-Solver del libro ───
        # El libro es el unico canal de hechos de plata. La guarda cruza cada cifra
        # de la prosa final contra el libro aprobado: una cifra fuera del libro es
        # fuga, aunque exista en la evidencia (caza el contrabando que el verificador
        # de plata no ve). Solo con LIBRO_ASIENTOS on hay libro. No corre AUTOFIX:
        # una fuga no se recalcula, va directo al fallback. En shadow solo loguea.
        # Solo corre si el Solver EMITIO un libro: sin libro no hay contra que
        # cruzar y marcaria toda cifra buena como fuga. La no-emision es otra falla
        # (se mide aparte por el diagnostico), no un problema de completitud.
        if (settings.GUARDA_COMPLETITUD in ("on", "shadow")
                and not settings.COMPUERTA_UNICA
                and settings.LIBRO_ASIENTOS and libro_emitido
                and final_response not in (
                    settings.VERIFIKA_FALLBACK_MESSAGE,
                    settings.FALLBACK_MESSAGE)):
            try:
                from app.core.libro import guarda_completitud, diag_record
                _g = guarda_completitud(
                    final_response, libro_aprob, evidence, trace_id=trace_id)
                diag_record(user_id, guarda_ok=_g["ok"], fugas=_g["fugas"])
                if not _g["ok"]:
                    if settings.GUARDA_COMPLETITUD == "on":
                        log.info("guarda_bloqueo", trace_id=trace_id,
                                 fugas=_g["fugas"][:10])
                        final_response = settings.VERIFIKA_FALLBACK_MESSAGE
                    else:
                        log.info("guarda_completitud_shadow", trace_id=trace_id,
                                 fugas=_g["fugas"][:10],
                                 total_montos=_g["total_montos"])
            except Exception as e:
                log.error("guarda_completitud_error", trace_id=trace_id,
                          error=str(e)[:200])

        # ─── GATE GENERAL POR GRAVEDAD (Checker de Verifika) ───
        # El mecanismo GENERAL de grounding: el Checker marca las afirmaciones
        # sin respaldo en la evidencia y el gate por gravedad decide. Caza de una
        # sola forma lo que los verificadores deterministas cazan de a uno
        # (producto inventado, promesa de dia, servicio o politica sin respaldo).
        # Los numeros ya los reconcilio el pipeline contra la calculadora, asi
        # que aca no se pelea con la plata. Con AUTOFIX repromptea antes del
        # fallback: el contrario de inventar no es callar, es decir lo verdadero.
        if (settings.CHECKER_GATEA and verifika_result is not None
                and not settings.COMPUERTA_UNICA):
            try:
                from app.core.gate_gravedad import (
                    decidir_gate, textos_no_respaldados)
                _gate = decidir_gate(
                    verifika_result.get("veredictos", []),
                    verifika_result.get("afirmaciones", []),
                    trace_id=trace_id)
            except Exception as e:
                log.error("checker_gate_error", trace_id=trace_id,
                          error=str(e)[:160])
                _gate = {"bloquear": False, "problemas": []}
            if (_gate["bloquear"]
                    and final_response not in (
                        settings.VERIFIKA_FALLBACK_MESSAGE,
                        settings.FALLBACK_MESSAGE)):
                _no_resp = textos_no_respaldados(_gate)
                log.info("checker_gate_bloqueo", trace_id=trace_id,
                         problemas=[f"{p['tipo']}:{p['motivo']}"
                                    for p in _gate["problemas"]],
                         textos=_no_resp[:6])
                _arreglado_chk = False
                if settings.AUTOFIX:
                    try:
                        correctivo = (
                            mensaje_enriquecido
                            + "\n\n[Sistema: en tu respuesta anterior estas "
                            f"afirmaciones NO tienen respaldo en la evidencia de "
                            f"las herramientas: {_no_resp}. No las afirmes. Si es "
                            "un producto, NO lo nombres si no aparece en el "
                            "catalogo (usa search_products). Si es una politica o "
                            "un plazo, cita SOLO lo que diga la FAQ (usa query_faq) "
                            "sin extender ni prometer un dia. Rehace la respuesta "
                            "solo con datos respaldados.]")
                        resp_c, meta_c = await run_agent(
                            correctivo, history, trace_id,
                            tienda_id=tid, user_id=user_id)
                        clean_c = clean_response(resp_c, tienda_id=tid)
                        ev_c = _build_evidence_for_verifika(
                            meta_c.get("tools_called", []), tid,
                            productos_vistos=productos_vistos_memoria)
                        for p in proofs_memoria:
                            ev_c.append({"tipo": "proof", "tool": "memoria",
                                         "proof": p})
                        vc2 = await asyncio.to_thread(
                            verify_response,
                            respuesta_solver=clean_c, evidence=ev_c,
                            trace_id=trace_id,
                            fallback_message=settings.VERIFIKA_FALLBACK_MESSAGE)
                        g2 = decidir_gate(vc2.get("veredictos", []),
                                          vc2.get("afirmaciones", []),
                                          trace_id=trace_id)
                        vr_c = (verificar_respuesta(clean_c, ev_c, trace_id=trace_id)
                                if VERIFICADOR_MODE != "off" else {"ok": True})
                        if not g2["bloquear"] and vr_c.get("ok", True):
                            final_response = clean_c
                            _arreglado_chk = True
                            log.info("checker_gate_autofix_ok", trace_id=trace_id)
                        else:
                            log.info("checker_gate_autofix_fallo", trace_id=trace_id,
                                     problemas=[p["tipo"] for p in g2["problemas"]])
                    except Exception as e:
                        log.error("checker_gate_autofix_error", trace_id=trace_id,
                                  error=str(e)[:200])
                if not _arreglado_chk:
                    final_response = settings.VERIFIKA_FALLBACK_MESSAGE
    else:
        validation = {"is_clean": True}
        verifika_result = None
        verificador_result = None
        servicios_result = None
        hechos_result = None

    # Ultimo presupuesto armado por la calculadora este turno, si lo hubo.
    # Del mismo resultado salen los ITEMS del carrito vigente (id, nombre,
    # cantidad): la identidad del pedido, no solo el texto.
    presupuesto_turno = ""
    carrito_turno: list = []
    for _t in agent_meta.get("tools_called", []):
        # Los calculos ESPECULATIVOS del Provider (nadie los pidio) respaldan
        # numeros pero no son el pedido: no pisan carrito ni presupuesto.
        if (isinstance(_t, dict) and _t.get("name") == "calculate_total"
                and not _t.get("speculativo")
                and isinstance(_t.get("result"), dict)
                and _t["result"].get("presentacion")):
            presupuesto_turno = _t["result"]["presentacion"]
            carrito_turno = [
                {"id": d.get("id"), "nombre": d.get("nombre"),
                 "cantidad": d.get("cantidad", 1)}
                for d in (_t["result"].get("detalle") or []) if d.get("id")
            ]
    # FUENTE UNICA del pedido a persistir: si la planilla del turno tiene items,
    # ESA es la verdad (refleja el carrito post-delta con la precedencia carrito
    # sobre foco), no los calculos especulativos sueltos de tools_called. Asi el
    # carrito guardado, el render y el cierre cuelgan del mismo objeto y el total
    # no rebota entre turnos.
    if (settings.ESTADO_PEDIDO and _estado_turno
            and _estado_turno.get("items")):
        carrito_turno = [{"id": it["id"], "nombre": it.get("nombre"),
                          "cantidad": it.get("cantidad", 1)}
                         for it in _estado_turno["items"] if it.get("id")]
        if _estado_turno.get("presentacion"):
            presupuesto_turno = _estado_turno["presentacion"]

    presupuesto_actual = presupuesto_turno or presupuesto_memoria
    carrito_actual = carrito_turno or carrito_memoria

    # ─── RENDER_CODIGO: estampar el bloque numerico verificado por codigo ───
    # Si el codigo tiene la verdad del turno (presupuesto verificado), el bloque
    # se PEGA en la respuesta en vez de confiar en que el Solver lo copie. Si el
    # Solver dejo el marcador lo reemplaza; si lo ignoro y escribio sus propios
    # numeros, el codigo se los saca y estampa el verificado. Va antes de PISO,
    # que solo actua cuando NO hay verdad del codigo: se complementan.
    if (settings.RENDER_CODIGO and presupuesto_codigo and final_response
            and final_response not in (settings.FALLBACK_MESSAGE,
                                       settings.VERIFIKA_FALLBACK_MESSAGE)):
        try:
            from app.core.render import renderizar
            _antes_render = final_response
            final_response = renderizar(final_response, presupuesto_codigo)
            if final_response != _antes_render:
                log.info("render_codigo_estampado", trace_id=trace_id)
        except Exception as e:
            log.warning("render_codigo_error", trace_id=trace_id,
                        error=str(e)[:160])

    # PISO_PRESUPUESTO (off/shadow/on): caza el "presupuesto disfrazado" — la
    # respuesta trae un bloque tipo Presupuesto/Total armado A MANO (sin
    # calculate_total ok este turno ni verdad del codigo). Cazado por el
    # atacante caotico: el modelo imita el formato de la calculadora y suma el
    # solo. shadow: solo loguea. on: reemplaza por el calculo verificado del
    # carrito vigente, con aviso por si el cliente sumo algo nuevo.
    _modo_piso = settings.PISO_PRESUPUESTO
    if (_modo_piso in ("shadow", "on") and not presupuesto_turno
            and not presupuesto_codigo
            and final_response not in (settings.FALLBACK_MESSAGE,
                                       settings.VERIFIKA_FALLBACK_MESSAGE)
            and re.search(r"(?i)presupuesto:|total[^\n]{0,25}\$\s?\d",
                          final_response or "")):
        log.warning("piso_presupuesto_detectado", trace_id=trace_id,
                    modo=_modo_piso, tiene_carrito=bool(carrito_memoria))
        if _modo_piso == "on" and carrito_memoria:
            try:
                from app.core.tools import calculate_total as _ct
                from app.core.tools_context import set_current_tienda as _sct
                _sct(tid)
                _calc = _ct(items=[{"product_id": it["id"],
                                    "cantidad": it.get("cantidad", 1)}
                                   for it in carrito_memoria if it.get("id")])
                if isinstance(_calc, dict) and _calc.get("ok") \
                        and _calc.get("presentacion"):
                    final_response = (
                        "Te paso el presupuesto verificado de tu pedido:\n"
                        + _calc["presentacion"]
                        + "\nSi sumaste o sacaste algo decime y lo recalculo.")
                    presupuesto_actual = _calc["presentacion"]
                    log.warning("piso_presupuesto_aplicado", trace_id=trace_id)
            except Exception as e:
                log.warning("piso_presupuesto_error", trace_id=trace_id,
                            error=str(e)[:120])

    # ─── LINK SOLO POR CODIGO: ninguna URL nace del Solver ───
    # Visto 12-jun: el Solver fabrico un link de pago FALSO (mpago.verifika.tech)
    # con formato perfecto, y ningun verificador caza URLs. El unico link
    # legitimo (Mercado Pago) lo agrega el CODIGO en el cierre, DESPUES de esta
    # linea: toda URL que llegue hasta aca es inventada y se elimina.
    if settings.CIERRE_CONTRATO and final_response \
            and re.search(r"https?://", final_response):
        _urls = re.findall(r"https?://\S+", final_response)
        log.warning("link_inventado_bloqueado", trace_id=trace_id,
                    urls=[u[:60] for u in _urls])
        final_response = _sin_links(final_response)

    # ─── LEADS (solo si no hubo short-circuit por Interpretador) ───
    leads_meta = {"accion": "ninguna"}
    if USE_LEADS and not interpreter_short_circuit:
        try:
            extra_text, leads_meta = await procesar_mensaje_para_lead(
                user_id=user_id, canal=canal, tienda_id=tid,
                mensaje=raw_message, respuesta_solver=final_response,
                trace_id=trace_id,
                interpretacion=interpretacion,
                presupuesto=presupuesto_actual,
            )
            if leads_meta.get("respuesta_directa"):
                _accion = leads_meta.get("accion")
                _pide_datos = _accion in ("pidiendo_datos", "handoff_humano")
                _es_fallback = final_response in (
                    settings.FALLBACK_MESSAGE, settings.VERIFIKA_FALLBACK_MESSAGE)
                # Turno en fallback: el bot acaba de decir "no se / lo consulto".
                # Pedirle nombre y telefono en la misma respuesta es incoherente
                # y quema confianza. El lead ya quedo registrado: el pedido de
                # datos se pospone al proximo turno coherente.
                if settings.LEADS_NO_PIDE_EN_FALLBACK and _pide_datos and _es_fallback:
                    log.info("leads_pedido_pospuesto_por_fallback",
                             trace_id=trace_id, accion=_accion)
                # CIERRE_REQUIERE_PRESUPUESTO: pedir nombre/telefono/pago sin
                # haber dado JAMAS un precio es cerrar una venta sin total
                # (visto en prod 12-jun noche: "armame la lista" -> "me pasas
                # tu nombre y forma de pago?" sin presupuesto). El lead ya
                # quedo registrado; este turno la prioridad es cotizar.
                elif (settings.CIERRE_REQUIERE_PRESUPUESTO and _pide_datos
                        and not str(presupuesto_actual or "").strip()
                        and not carrito_actual):
                    log.info("leads_pedido_sin_presupuesto_pospuesto",
                             trace_id=trace_id, accion=_accion)
                # El cliente tiene que VER su pedido y total antes de que le
                # pidamos los datos. Nunca reemplazamos la respuesta (que muestra
                # productos/presupuesto) por un pedido de datos pelado: lo SUMAMOS
                # al final. Cura el handoff prematuro recurrente ("los 3 K380
                # negros" -> "pasame nombre y telefono" sin mostrar el precio).
                elif _pide_datos and final_response and not _es_fallback:
                    if leads_meta["respuesta_directa"] not in (final_response or ""):
                        final_response = (
                            final_response + "\n\n"
                            + leads_meta["respuesta_directa"])
                    log.info("leads_datos_apendizado", trace_id=trace_id,
                             accion=_accion)
                else:
                    final_response = leads_meta["respuesta_directa"]
            elif extra_text:
                final_response = final_response + extra_text
        except Exception as e:
            log.warning("leads_pipeline_error", trace_id=trace_id,
                        error=str(e)[:200])

    # ─── PUENTES DE VENTA (flag PUENTES_VENTA) ───
    # El sistema bloqueo por falta de fuente y quedo el fallback seco. En vez de
    # cortar la venta, se elige un PUENTE: mantiene la charla viva SIN inventar un
    # hecho. Si el cliente insiste con el mismo hueco, el puente deriva a humano
    # (estado derivar_humano). Si la respuesta NO es fallback, se corta la racha.
    if settings.PUENTES_VENTA and not interpreter_short_circuit:
        try:
            from app.core.puentes import elegir_puente, marcar_resuelto
            if final_response == settings.VERIFIKA_FALLBACK_MESSAGE:
                _p = elegir_puente(raw_message, user_id=user_id)
                if _p.get("texto"):
                    final_response = _p["texto"]
                    if _p.get("derivar"):
                        estado_nuevo = "derivar_humano"
                    log.info("puente_aplicado", trace_id=trace_id,
                             tipo=_p.get("tipo"), derivar=_p.get("derivar"))
            elif final_response != settings.FALLBACK_MESSAGE:
                marcar_resuelto(user_id)
        except Exception as e:
            log.warning("puentes_error", trace_id=trace_id, error=str(e)[:160])

    # ─── NO_RESALUDO: sacar el saludo a mitad de charla ───
    # El bot saluda en el primer mensaje, no en el segundo ni el tercero. Solo
    # con historial previo (no es el primer turno) y sobre respuesta del Solver
    # (no sobre un saludo deliberado por codigo, que va por short-circuit).
    if (settings.NO_RESALUDO and history and not interpreter_short_circuit
            and final_response):
        try:
            from app.core.resaludo import quitar_resaludo
            _sin_resaludo = quitar_resaludo(final_response)
            if _sin_resaludo != final_response:
                final_response = _sin_resaludo
                log.info("resaludo_sacado", trace_id=trace_id)
        except Exception as e:
            log.warning("resaludo_error", trace_id=trace_id, error=str(e)[:120])

    # ─── PERSISTIR ───
    history.append({"role": "user", "content": raw_message})
    history.append({"role": "assistant", "content": final_response})
    cap = settings.HISTORY_LIMIT * 2
    if len(history) > cap:
        history = history[-cap:]

    # Memoria de PROOF: arrastra los calculos recientes para que en la
    # confirmacion el total repetido siga teniendo respaldo. Cap por turnos.
    proofs_turno = [
        t["proof"] for t in agent_meta.get("tools_called", [])
        if isinstance(t, dict) and t.get("proof")
    ]
    proofs_recientes = (proofs_memoria + proofs_turno)[-PROOF_MEMORY:]

    # Registro de sesion: merge de los productos vistos este turno con los de la
    # memoria. El turno PISA a la memoria (precio fresco gana) y va al frente; se
    # capa a REGISTRO_SESION_MAX, los mas recientes primero. Solo con el flag on;
    # en off queda None y save_conversation no toca el campo.
    productos_vistos_nuevo = None
    if settings.REGISTRO_SESION:
        try:
            # Los records del Provider (busquedas) se inyectan a tools_called solo
            # en el camino principal. Cuando la confirmacion cortocircuita ("¿cual
            # preferis?"), ese camino se saltea y los productos MOSTRADOS en la
            # pregunta no entran al registro -> el turno siguiente ('el G203
            # negro') no tiene donde resolver la eleccion. Se incluyen aca para
            # que el registro capture lo que el cliente vio, haya short-circuit o no.
            _tools_reg = agent_meta.get("tools_called", [])
            if _prov_turno and _prov_turno.get("registros"):
                _tools_reg = list(_prov_turno["registros"]) + _tools_reg
            productos_turno = _extraer_productos_vistos(_tools_reg)
            productos_vistos_nuevo = _merge_productos_vistos(
                productos_turno, productos_vistos_memoria,
                settings.REGISTRO_SESION_MAX)
            log.info("registro_sesion_guardado", trace_id=trace_id,
                     vistos=len(productos_vistos_nuevo),
                     nuevos_turno=len(productos_turno))
        except Exception as e:
            log.warning("registro_sesion_error", trace_id=trace_id,
                        error=str(e)[:160])

    # Ultima localidad de envio: si el turno trae una zona clara, esa pasa a ser
    # la vigente; si no, se conserva la de memoria. Para cotizar el envio en el
    # "el envio ahi" sin que el cliente repita la ciudad.
    ultima_localidad_nueva = None
    if settings.REGISTRO_SESION:
        try:
            from app.core.envio import clasificar_zona
            if clasificar_zona(raw_message):
                ultima_localidad_nueva = raw_message
            elif ultima_localidad_memoria:
                ultima_localidad_nueva = ultima_localidad_memoria
        except Exception as e:
            log.warning("ultima_localidad_error", trace_id=trace_id,
                        error=str(e)[:120])

    try:
        save_conversation(user_id, history, conv.get("summary", ""),
                          tienda_id=tid, estado_conversacion=estado_nuevo,
                          ultima_compra=ultima_compra,
                          proofs_recientes=proofs_recientes,
                          ultimo_presupuesto=presupuesto_actual,
                          productos_vistos=productos_vistos_nuevo,
                          ultima_localidad=ultima_localidad_nueva,
                          carrito_vigente=(carrito_actual
                                           if settings.CARRITO_VIGENTE else None),
                          pedido_pendiente=pedido_pendiente_out)
    except Exception as e:
        log.warning("save_conversation_failed", error=str(e)[:100])

    latency_ms = int((time.time() - t0) * 1000)

    log_message(
        user_id=user_id, mensaje_usuario=raw_message,
        respuesta_bot=final_response,
        tools_called=[t["name"] for t in agent_meta.get("tools_called", [])],
        latency_ms=latency_ms, trace_id=trace_id, tienda_id=tid,
    )

    log_payload = {
        "trace_id": trace_id, "tienda_id": tid, "user_id": user_id,
        "latency_ms": latency_ms,
        "tools_called": [t["name"] for t in agent_meta.get("tools_called", [])],
        "iterations": agent_meta.get("iterations"),
        "validation_clean": validation.get("is_clean", True),
        "interpreter_short_circuit": interpreter_short_circuit,
    }
    log_payload["estado_conversacion"] = estado_nuevo
    if ofrecer_opciones:
        log_payload["ofrecer_opciones"] = True
    if interpretacion:
        log_payload["interpreter_intencion"] = interpretacion.get("intencion")
        log_payload["interpreter_confianza"] = round(
            interpretacion.get("confianza", 0), 2)
        log_payload["interpreter_producto"] = interpretacion.get(
            "producto_resuelto")
    if leads_meta.get("accion") != "ninguna":
        log_payload["leads_accion"] = leads_meta["accion"]
        if leads_meta.get("lead_id"):
            log_payload["lead_id"] = leads_meta["lead_id"]
    if verifika_result:
        conf = verifika_result["confianza"]
        log_payload["verifika_accion"] = verifika_result["accion"]
        log_payload["verifika_score"] = round(conf["score"], 2)
        log_payload["verifika_total_afirmaciones"] = conf["total"]
        # Contadores de decision: KPIs de tasa de bloqueo y de sin evidencia.
        log_payload["verifika_soportadas"] = conf.get("soportadas")
        log_payload["verifika_sin_evidencia"] = conf.get("sin_evidencia")
        log_payload["verifika_contradichas"] = conf.get("contradichas")
        log_payload["blocked"] = verifika_result["accion"] == "bloquear"

    # Tiempos por etapa y total: siempre presentes, para ver donde se va el tiempo.
    for _k, _v in timings.items():
        log_payload[f"t_{_k}"] = _v
    log_payload["t_total_ms"] = latency_ms

    # Outcome: clasificacion unica del resultado, para los KPIs en una sola query.
    _la = leads_meta.get("accion", "ninguna")
    if final_response == settings.FALLBACK_MESSAGE:
        outcome = "fallback_tecnico"
    elif final_response == settings.VERIFIKA_FALLBACK_MESSAGE:
        outcome = "bloqueado"
    elif _la == "lead_capturado":
        outcome = "venta_cerrada"
    elif _la in ("pidiendo_datos", "handoff_humano"):
        outcome = "tomando_datos"
    elif _la == "tibia_registrada":
        outcome = "lead_tibio"
    else:
        outcome = "ok"
    log_payload["outcome"] = outcome

    # Telemetria del turno para los molinos (flag, solo memoria de proceso).
    if settings.TELEMETRIA_TURNO:
        try:
            from app.core.telemetria import registrar_turno
            registrar_turno(
                agent_meta.get("tools_called", []), estado=estado_nuevo,
                outcome=outcome, presupuesto_codigo=bool(presupuesto_codigo),
                short_circuit=interpreter_short_circuit,
                verdad=presupuesto_codigo if isinstance(presupuesto_codigo, str) else None,
                user_id=user_id)
        except Exception as e:
            log.warning("telemetria_turno_error", error=str(e)[:100])

    log.info("message_completed", **log_payload)

    structlog.contextvars.clear_contextvars()
    return final_response


def reset_user(user_id: str, tienda_id: str | None = None):
    fs_reset_conversation(user_id, tienda_id=tienda_id)
    try:
        from app.core.puentes import reset as _reset_puentes
        _reset_puentes(user_id)
    except Exception:
        pass
