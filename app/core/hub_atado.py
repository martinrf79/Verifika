"""
HUB ATADO — el turno completo con los DOS atados y SIN la pila de guardas.

Camino:
  1. INTERPRETE (Gemini, schema estricto): entiende y devuelve datos.
  2. SOLVER (solver_gemini): LLAMA las tools de area; el dato duro sale de la
     tool, no de la cabeza del modelo.
  3. ESTAMPADO por codigo del numero sellado y el producto real.
  4. MEMORIA: se persiste el estado esencial para que la charla recuerde entre
     turnos (history, resumen largo, productos vistos, carrito, destinos,
     criterio, provincia).

NO corre ninguna de las ~40 guardas/parches de interprete_libre. Reusa solo las
funciones PURAS de estado y estampado. Es candidato a reemplazar interprete_libre
en el camino vivo una vez medido en la bateria; hoy convive solo para medirse,
el orchestrator sigue en interprete_libre hasta que el numero lo justifique.
"""
import re
import time

from app.core.interpretador import interpretar_mensaje
from app.core import solver_gemini
from app.core.estado_venta import (
    construir_estado, set_current_estado,
    productos_de_meta, carrito_de_meta, envio_de_meta, merge_productos,
    detectar_criterio, criterio_del_interprete, get_envio_localidades)
from app.core.tools_context import set_current_tienda
from app.core.interprete_libre import (
    _presupuesto_de_meta, _sustituir_o_acoplar_presupuesto, _estampar_productos)
from app.config import get_settings
from app.logger import get_logger
from app.storage.firestore_client import (
    get_conversation, save_conversation, get_config, get_product_by_id)

log = get_logger(__name__)
settings = get_settings()

_RE_PROD = re.compile(r"\[\[PROD:([A-Za-z0-9_\-]+)\]\]")
_RE_PRESUP_SOBRANTE = re.compile(r"\s*\[\[PRESUPUESTO\]\]\s*")
# El solver a veces FILTRA el id interno del catalogo en el texto al cliente
# ("Genius KB-110X (id: TEC0019)"). El cliente no debe verlo. Limpieza del
# estampado, no una guarda; lo ideal es que el prompt del solver no lo emita.
_RE_ID_FILTRADO = re.compile(
    r"[\s,]*\(\s*(?:(?:id|sku|codigo)\s*[:=]?\s*)?"
    r"[A-Z]{2,5}\d{2,}(?:\s*/\s*[A-Z]{2,5}\d{2,})*\s*\)"
    r"|[\s,]*\b(?:id|sku|codigo)\s*[:=]\s*[A-Z]{2,5}\d{2,}",
    re.IGNORECASE)


async def procesar_atado(user_id: str, raw_message: str, tienda_id: str,
                         canal: str, trace_id: str) -> str:
    """Un turno del bot por el flujo atado. Devuelve el texto para el cliente."""
    t0 = time.time()
    conv = get_conversation(user_id, tienda_id=tienda_id)
    history = conv.get("history", []) or []
    estado_anterior = conv.get("estado_conversacion", "saludo") or "saludo"

    estado = construir_estado(conv, None)
    from app.core.envio import clasificar_provincia
    _prov_msg = clasificar_provincia(raw_message) or ""
    if _prov_msg:
        estado["provincia_envio"] = _prov_msg
    set_current_tienda(tienda_id)
    set_current_estado(estado)

    # ── INTERPRETE ──────────────────────────────────────────────────────
    resumen = estado.get("resumen_charla") or ""
    interp = await interpretar_mensaje(
        raw_message, history, trace_id, estado_anterior=estado_anterior,
        tienda_id=tienda_id, productos_vistos=estado.get("productos_vistos"),
        resumen=resumen)
    estado_nuevo = (interp.get("estado_conversacion") or estado_anterior
                    if isinstance(interp, dict) else estado_anterior)
    log.info("hub_atado_interp", trace_id=trace_id,
             intencion=interp.get("intencion"),
             producto=interp.get("producto_resuelto"),
             consultados=interp.get("productos_consultados"))

    # ── GUIA DETERMINISTA del "mas barato" ──────────────────────────────
    # Elegir el minimo con stock es un problema CERRADO: lo computa el codigo y
    # viaja al solver para que ofrezca EXACTAMENTE ese, en vez de adivinar (el
    # banco lo mostro intermitente: en el guion 52 nego stock que existia).
    if (detectar_criterio(raw_message) == "más barato"
            or criterio_del_interprete(interp)):
        try:
            from app.core.guia_compra import guia_mas_barato
            _g = guia_mas_barato(raw_message, estado.get("productos_vistos"))
            if _g:
                estado["guia_determinista"] = _g
                log.info("hub_atado_guia_mas_barato", trace_id=trace_id)
        except Exception as e:
            log.warning("hub_atado_guia_error", trace_id=trace_id,
                        error=str(e)[:120])

    # ── SOLVER atado a las tools ────────────────────────────────────────
    business = (get_config("business_name", tienda_id=tienda_id)
                or settings.BUSINESS_NAME)
    texto, meta = await solver_gemini.generar_respuesta(
        raw_message, interp, estado, tienda_id, trace_id, history, business)
    if not texto:
        texto, meta = settings.VERIFIKA_FALLBACK_MESSAGE, (meta or {})

    # ── ESTAMPADO por codigo ────────────────────────────────────────────
    ids_mostrados = [m.upper() for m in _RE_PROD.findall(texto or "")]
    present = _presupuesto_de_meta(meta)
    if present:
        texto = _sustituir_o_acoplar_presupuesto(texto, present)
    texto = _estampar_productos(texto, tienda_id, trace_id)
    # Si el modelo puso [[PRESUPUESTO]] sin un total que sellar, se saca prolijo
    # para no filtrar el marcador (limpieza del estampado, no una guarda).
    texto = _RE_PRESUP_SOBRANTE.sub(" ", texto).strip()
    texto = _RE_ID_FILTRADO.sub("", texto)

    # ── MEMORIA ─────────────────────────────────────────────────────────
    history = history + [
        {"role": "user", "content": raw_message},
        {"role": "assistant", "content": texto}]
    resumen_charla = conv.get("summary", "") or ""
    descartados = history[:-(settings.HISTORY_LIMIT * 2)]
    if descartados:
        try:
            from app.core.memoria_larga import actualizar_resumen
            resumen_charla = await actualizar_resumen(
                resumen_charla, descartados, trace_id)
        except Exception as e:
            log.warning("hub_atado_memoria_error", trace_id=trace_id,
                        error=str(e)[:120])
    history = history[-(settings.HISTORY_LIMIT * 2):]

    mostrados: list[dict] = []
    for pid in {i.upper() for i in ids_mostrados}:
        try:
            pp = get_product_by_id(pid, tienda_id=tienda_id)
        except Exception:
            pp = None
        if (isinstance(pp, dict) and pp.get("nombre")
                and isinstance(pp.get("precio_ars"), (int, float))):
            mostrados.append({"id": pid, "nombre": pp["nombre"],
                              "precio": int(pp["precio_ars"])})
    productos_vistos = merge_productos(
        conv.get("productos_vistos") or [], productos_de_meta(meta) + mostrados)
    _intent = interp.get("intencion") if isinstance(interp, dict) else None
    carrito_vigente = ((carrito_de_meta(meta) if _intent not in ("otra",) else [])
                       or (conv.get("carrito_vigente") or []))
    ultima_localidad = envio_de_meta(meta) or (conv.get("ultima_localidad") or "")
    ultimas_localidades = get_envio_localidades() or (
        conv.get("ultimas_localidades") or [])
    criterio_cliente = (
        detectar_criterio(raw_message)
        or ("más barato" if criterio_del_interprete(interp) else "")
        or (conv.get("criterio_cliente") or ""))
    provincia_envio = _prov_msg or (conv.get("provincia_envio") or "")

    try:
        save_conversation(
            user_id, history, resumen_charla, tienda_id=tienda_id,
            estado_conversacion=estado_nuevo,
            productos_vistos=productos_vistos, carrito_vigente=carrito_vigente,
            ultima_localidad=ultima_localidad,
            ultimas_localidades=ultimas_localidades,
            criterio_cliente=criterio_cliente, provincia_envio=provincia_envio)
    except Exception as e:
        log.warning("hub_atado_save_error", trace_id=trace_id, error=str(e)[:150])

    log.info("hub_atado_ok", trace_id=trace_id,
             latency_ms=int((time.time() - t0) * 1000),
             tools=len((meta or {}).get("tools_called", [])))
    return texto
