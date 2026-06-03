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
import os
import time
import uuid
import asyncio
import structlog
from app.core.agent import run_agent
from app.core.guardian import validate_response, clean_response
from app.core.verificador import verificar_respuesta
from app.core.verificador_servicios import verificar_servicios
from app.core.verificador_hechos import verificar_hechos
from app.config import get_settings
from app.logger import get_logger
from app.storage.firestore_client import (
    get_conversation,
    save_conversation,
    log_message,
    reset_conversation as fs_reset_conversation,
    get_all_products,
    get_all_faq,
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


VERIFIKA_EVIDENCE_FROM_TOOLS = settings.VERIFIKA_EVIDENCE_FROM_TOOLS

# Tools que devuelven productos del catalogo bajo distintas claves.
_TOOLS_CON_PRODUCTOS = (
    "search_products", "get_product_details", "find_within_budget",
    "compare_products", "recommend_product", "list_catalog",
)


def _build_evidence_from_tools(tools_called: list[dict],
                               tienda_id: str) -> list[dict]:
    """
    Construye la evidencia del Checker a partir de los resultados REALES de las
    tools, o sea lo que el Solver efectivamente vio. No relee el catalogo entero.

    - Productos: de search_products, get_product_details, find_within_budget,
      compare_products, recommend_product y el detalle de calculate_total.
    - FAQ: solo los temas que query_faq efectivamente devolvio, enriquecidos con
      los valores estructurados (rangos, montos) para que el Checker pueda
      verificar envios y descuentos.
    - Proofs: los calculos verificados de calculate_total.
    """
    productos_por_id: dict[str, dict] = {}
    faq_temas: set[str] = set()
    faq_evidence: list[dict] = []
    proof_evidence: list[dict] = []
    necesita_faq_struct = False

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
                if res.get("tipo") == "cuantitativo":
                    necesita_faq_struct = True

    # FAQ como evidencia. Dos modos:
    # - Completo (flag VERIFIKA_FULL_FAQ_EVIDENCE): entra TODA la FAQ, asi una
    #   afirmacion verdadera sobre un tema que el Solver no consulto, formas de
    #   pago por ejemplo, no cae como sin_evidencia y no bloquea de gusto.
    #   La FAQ es chica y get_all_faq esta cacheada, asi que es barato.
    # - Acotado: solo los temas que query_faq trajo, enriquecidos con valores.
    if settings.VERIFIKA_FULL_FAQ_EVIDENCE:
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
    elif necesita_faq_struct and faq_temas:
        try:
            faqs_full = get_all_faq(tienda_id=tienda_id)
            for item in faq_evidence:
                data = faqs_full.get(item["id"])
                if data and data.get("valores"):
                    item["valores"] = data["valores"]
        except Exception as e:
            log.warning("verifika_faq_struct_failed", error=str(e)[:100])

    return list(productos_por_id.values()) + faq_evidence + proof_evidence


def _build_evidence_for_verifika(tools_called: list[dict],
                                  tienda_id: str) -> list[dict]:
    """Reconstruye evidencia para Verifika."""
    if VERIFIKA_EVIDENCE_FROM_TOOLS:
        return _build_evidence_from_tools(tools_called, tienda_id)

    evidence = []

    tool_names = [t.get("name", "") for t in tools_called]
    uso_busqueda = any(n in ("search_products", "get_product_details",
                              "find_within_budget", "compare_products",
                              "recommend_product", "calculate_total")
                       for n in tool_names)
    uso_faq = "query_faq" in tool_names

    if uso_busqueda or not tool_names:
        try:
            productos = get_all_products(tienda_id=tienda_id)
            for p in productos:
                evidence.append({
                    "tipo": "producto",
                    "id": p.get("id"),
                    "nombre": p.get("nombre"),
                    "categoria": p.get("categoria"),
                    "precio_ars": p.get("precio_ars"),
                    "stock": p.get("stock"),
                    "descripcion": p.get("descripcion", ""),
                    "marca": p.get("marca"),
                    "modelo": p.get("modelo"),
                    "color": p.get("color"),
                    "material": p.get("material"),
                    "peso_gramos": p.get("peso_gramos"),
                    "dimensiones": p.get("dimensiones"),
                    "garantia_meses": p.get("garantia_meses"),
                    "uso_recomendado": p.get("uso_recomendado"),
                    "caracteristicas_extra": p.get("caracteristicas_extra"),
                })
        except Exception as e:
            log.warning("verifika_evidence_products_failed",
                        error=str(e)[:100])

    if uso_faq or not tool_names:
        try:
            faqs = get_all_faq(tienda_id=tienda_id)
            for tema_id, data in faqs.items():
                evidence.append({
                    "tipo": "faq",
                    "id": tema_id,
                    "tema": tema_id,
                    "respuesta": data.get("respuesta", ""),
                })
        except Exception as e:
            log.warning("verifika_evidence_faq_failed",
                        error=str(e)[:100])

    # Inyectar proofs de tools como evidencia tipo proof
    for t in tools_called:
        proof = t.get("proof")
        if proof:
            evidence.append({
                "tipo": "proof",
                "tool": t.get("name"),
                "proof": proof,
            })

    return evidence


async def _handoff_compra(user_id, canal, tienda_id, mensaje, producto_resuelto,
                            trace_id):
    log.info("_handoff_compra_inicio")
    """Crea lead fuerte y devuelve respuesta de handoff con producto correcto."""
    if not USE_LEADS:
        return None
    try:
        lead_id = crear_lead(
            user_id=user_id, canal=canal, tienda_id=tienda_id,
            ultimo_mensaje=mensaje,
            frase_disparadora=f"interpretador:decision_compra:{producto_resuelto}",
            nivel="fuerte", estado_inicial="datos_solicitados",
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


def _respuesta_saludo() -> str:
    """Saludo de apertura directo, sin invocar el Solver. Cordial e invita a
    avanzar: si el cliente queria algo mas, lo dice en el proximo turno y ahi
    corre el Solver normal. No se pierde venta, a lo sumo un turno."""
    return ("Hola, como va. Te puedo dar una mano con productos, precios, "
            "envios o formas de pago. Que estas buscando?")


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


# ─── DEFENSA 3 — confirmar antes de cotizar (interpretacion rica) ───
def _slots_ambiguos_decisivos(interp: dict) -> bool:
    """True si hay un slot DECISIVO sin resolver: un item sin producto claro o
    un destino sin cajon, que ademas el interprete marco en ambiguedades. Es la
    senal de que no se puede cotizar sin preguntar antes."""
    amb = interp.get("ambiguedades") or []
    for i, it in enumerate(interp.get("items") or []):
        if it.get("producto_resuelto"):
            continue
        if f"items[{i}]" in amb or (it.get("confianza") or 1) < 0.7:
            return True
    for i, d in enumerate(interp.get("destinos") or []):
        if not d.get("cajon") and f"destinos[{i}]" in amb:
            return True
    return False


def _intencion_de_compra(interp: dict) -> bool:
    """True si el cliente esta tratando de cotizar o comprar, no solo mirando.
    Senales: pide descuento, dio forma de pago, dio destino o cantidad, o hay
    decision de compra. Asi NO preguntamos de mas en una exploracion."""
    if interp.get("pide_descuento") or interp.get("forma_pago"):
        return True
    if "decision_compra" in (interp.get("intenciones") or []):
        return True
    if interp.get("destinos"):
        return True
    return any(it.get("cantidad") for it in (interp.get("items") or []))


def _respuesta_confirmacion_rica(interp: dict) -> str:
    """Read-back que pide confirmar el slot dudoso ANTES de cotizar. No adivina,
    pregunta. De paso repite el pedido, que es una jugada de venta."""
    refs = [str(it.get("referencia") or "").strip()
            for it in (interp.get("items") or [])
            if not it.get("producto_resuelto")]
    refs = [r for r in refs if r]
    pedido = " y ".join(refs) if refs else "lo que necesitas"
    msg = (f"Para pasarte el precio justo y no equivocarme, decime cual "
           f"exactamente queres de {pedido}.")
    dests = interp.get("destinos") or []
    if dests and dests[0].get("texto"):
        msg += f" Con eso te armo el total con envio a {dests[0]['texto']}."
    return msg


def _contexto_slots(interp: dict) -> str:
    """Bloque con los slots ya interpretados para que el Solver reciba el detalle
    masticado y no lo re-derive del mensaje crudo. Los numeros siguen saliendo de
    la calculadora, esto es guia de interpretacion."""
    partes = []
    items = interp.get("items") or []
    if items:
        _it = []
        for it in items:
            cant = it.get("cantidad")
            nom = it.get("producto_resuelto") or it.get("referencia") or "?"
            _it.append(f"{cant or ''}x {nom}".strip())
        partes.append("items: " + "; ".join(_it))
    dests = interp.get("destinos") or []
    if dests:
        partes.append("destinos: " + "; ".join(
            f"{d.get('texto')} ({d.get('cajon') or 'sin cajon'})" for d in dests))
    if interp.get("atributo_consultado"):
        partes.append("consulta puntual: " + str(interp["atributo_consultado"]))
    if interp.get("forma_pago"):
        partes.append("forma de pago: " + str(interp["forma_pago"]))
    if interp.get("pide_descuento"):
        partes.append("pide descuento: el unico descuento valido es el de la FAQ, "
                      "transferencia o efectivo, no inventes otro")
    if not partes:
        return ""
    return ("\n\n[Detalle ya interpretado del mensaje, usalo como guia, los "
            "numeros igual salen de la calculadora:\n- " + "\n- ".join(partes) + "]")


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

    # ─── INTERPRETADOR (pre-Solver) ───
    interpretacion = None
    interpreter_short_circuit = False
    final_response = None

    if USE_INTERPRETER:
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

            # Caso A: decision de compra con alta confianza, handoff directo.
            # Regla de orden: solo atajamos si ya se mostro un presupuesto en un
            # turno anterior. Si no, no cerramos sin precio: dejamos que el
            # Solver corra y responda el numero primero.
            _hay_presupuesto_previo = bool(str(presupuesto_memoria).strip())
            if (intencion == "decision_compra"
                    and confianza >= UMBRAL_CONFIANZA_ALTA
                    and producto_resuelto
                    and (_hay_presupuesto_previo
                         or not settings.CIERRE_PRECIO_PRIMERO)):
                handoff = await _handoff_compra(
                    user_id, canal, tid, raw_message,
                    producto_resuelto, trace_id)
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

            # Defensa 3: si hay un slot decisivo dudoso y el cliente quiere
            # cotizar, confirmamos antes de mandar al Solver. Preguntar, no adivinar.
            elif (settings.INTERPRETE_RICO
                    and not producto_resuelto
                    and _slots_ambiguos_decisivos(interpretacion)
                    and _intencion_de_compra(interpretacion)):
                final_response = _respuesta_confirmacion_rica(interpretacion)
                interpreter_short_circuit = True
                log.info("interpreter_confirmacion_rica", trace_id=trace_id,
                         ambiguedades=interpretacion.get("ambiguedades"))

        except Exception as e:
            log.error("interpreter_error", trace_id=trace_id,
                      error=str(e)[:200])
            # Si el interpretador falla, seguimos al flujo normal
            interpreter_short_circuit = False
        timings["interpret_ms"] = int((time.perf_counter() - _ts_interp) * 1000)

    # ─── SOLVER (solo si Interpretador no corto el flujo) ───
    response_text = None
    agent_meta = {"tools_called": [], "iterations": 0}

    if not interpreter_short_circuit:
        # Si hay producto resuelto, inyectarlo al Solver via mensaje
        mensaje_enriquecido = raw_message
        if (USE_INTERPRETER and interpretacion
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

        ctx_estado = f"\n\n[Estado de la conversacion: {estado_nuevo}]"
        if ofrecer_opciones:
            ctx_estado += (f"\n[ofrecer_opciones: el interpretador detecto dos "
                           f"caminos, presentalos como opcion A y B y pregunta "
                           f"cual prefiere: {ofrecer_opciones}]")
        mensaje_enriquecido = mensaje_enriquecido + ctx_estado

        # Detalle interpretado (Defensa 1): le pasamos al Solver los slots ya
        # entendidos para que adivine menos. Solo con el flag y si hubo interprete.
        if settings.INTERPRETE_RICO and interpretacion:
            mensaje_enriquecido += _contexto_slots(interpretacion)

        # Destino del envio para la calculadora defensiva. Determinista, por
        # keywords del mensaje del cliente. El LLM no lo elige: lo inyecta el
        # backend por contextvar, igual que la tienda. Solo cuando el flag esta on.
        if settings.CALC_DEFENSIVA:
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
        response_text, agent_meta = await run_agent(
            mensaje_enriquecido, history, trace_id,
            tienda_id=tid, user_id=user_id)
        timings["solver_ms"] = int((time.perf_counter() - _ts_solver) * 1000)

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
                    agent_meta.get("tools_called", []), tid)
                for p in proofs_memoria:
                    evidence.append({"tipo": "proof", "tool": "memoria",
                                     "proof": p})
            except Exception as e:
                log.warning("evidence_build_failed", trace_id=trace_id,
                            error=str(e)[:100])

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
            and response_text != settings.FALLBACK_MESSAGE
            and (VERIFICADOR_MODE != "on" or VERIFIKA_CHECKER_ADVISORY)
        )
        if _correr_checker:
            try:
                _ts_verifika = time.perf_counter()
                if settings.ASYNC_LLM_OFFLOAD:
                    verifika_result = await asyncio.to_thread(
                        verify_response,
                        respuesta_solver=cleaned_response,
                        evidence=evidence,
                        trace_id=trace_id,
                        fallback_message=settings.VERIFIKA_FALLBACK_MESSAGE,
                    )
                else:
                    verifika_result = verify_response(
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
        if VERIFICADOR_MODE == "on":
            # Gatea el codigo. Si una cifra no tiene respaldo, no se manda.
            if verificador_result and not verificador_result.get("ok", True):
                arreglado = False
                # AUTOFIX: reintento guiado antes de tirar el fallback.
                if settings.AUTOFIX:
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
                            meta2.get("tools_called", []), tid)
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
        if settings.VERIFICADOR_SERVICIOS == "on" and servicios_result is not None:
            if (not servicios_result.get("ok", True)
                    and final_response not in (
                        settings.VERIFIKA_FALLBACK_MESSAGE,
                        settings.FALLBACK_MESSAGE)):
                inventados = servicios_result.get("servicios_inventados", [])
                log.info("servicios_bloqueo", trace_id=trace_id,
                         servicios=inventados)
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
                            meta_s.get("tools_called", []), tid)
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
        if settings.VERIFICADOR_HECHOS == "on" and hechos_result is not None:
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
                            meta_h.get("tools_called", []), tid)
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
    else:
        validation = {"is_clean": True}
        verifika_result = None
        verificador_result = None
        servicios_result = None
        hechos_result = None

    # Ultimo presupuesto armado por la calculadora este turno, si lo hubo.
    presupuesto_turno = ""
    for _t in agent_meta.get("tools_called", []):
        if (isinstance(_t, dict) and _t.get("name") == "calculate_total"
                and isinstance(_t.get("result"), dict)
                and _t["result"].get("presentacion")):
            presupuesto_turno = _t["result"]["presentacion"]
    presupuesto_actual = presupuesto_turno or presupuesto_memoria

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
                # Si este turno el Solver armo un presupuesto y el cierre quiere
                # pedir datos, mostramos el precio primero y despues el pedido.
                # Nunca pisamos una cotizacion fresca con el pedido de datos.
                if (settings.CIERRE_PRECIO_PRIMERO and _pide_datos
                        and presupuesto_turno
                        and presupuesto_turno not in (final_response or "")):
                    final_response = (
                        final_response + "\n\n" + leads_meta["respuesta_directa"]
                    )
                else:
                    final_response = leads_meta["respuesta_directa"]
            elif extra_text:
                final_response = final_response + extra_text
        except Exception as e:
            log.warning("leads_pipeline_error", trace_id=trace_id,
                        error=str(e)[:200])

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

    try:
        save_conversation(user_id, history, conv.get("summary", ""),
                          tienda_id=tid, estado_conversacion=estado_nuevo,
                          ultima_compra=ultima_compra,
                          proofs_recientes=proofs_recientes,
                          ultimo_presupuesto=presupuesto_actual)
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

    log.info("message_completed", **log_payload)

    structlog.contextvars.clear_contextvars()
    return final_response


def reset_user(user_id: str, tienda_id: str | None = None):
    fs_reset_conversation(user_id, tienda_id=tienda_id)
