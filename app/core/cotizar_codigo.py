"""
COTIZADOR POR CODIGO — el codigo arma el presupuesto, el modelo solo redacta.

Cuando el cliente quiere cotizar o cerrar sobre un producto ya mostrado, en vez
de pedirle al modelo que recuerde el id, lo pase y llame la calculadora (donde
hoy pierde o inventa el id y la venta se cae), el CODIGO resuelve el id desde el
registro de sesion y llama calculate_total el mismo. Le entrega al Solver el
presupuesto ya verificado para que solo lo vista de venta. El numero no pasa por
el LLM.

Incluye el ENVIO: si el cliente lo pide, el codigo clasifica la zona desde el
mensaje (o desde la ultima localidad de la sesion) y arma el total completo
producto mas envio, con la tarifa real de la FAQ. Si la zona no es clara, NO
inventa: devuelve None y el flujo pregunta la zona.

Detras del flag COTIZA_CODIGO. Funcion testeable con catalogo y FAQ monkeypatcheados.
"""
from typing import Optional

from app.core.resolver_pedido import resolver_pedido, candidatos_pedido
from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

# Senales de que el cliente quiere precio o cerrar.
_QUIERE_PRECIO = (
    "cuanto", "cuánto", "precio", "sale", "total", "vale", "cuesta",
    "me lo llevo", "lo llevo", "lo confirmo", "confirmo", "lo compro",
    "comprar", "compralo", "cerralo", "cerrar", "lo quiero",
)
# Senales de envio: ahora SI cotizamos con envio, asi que cuentan como pedido.
_SENALES_ENVIO = ("envio", "envío", "enviar", "mandar", "manda", "despacho")


def _menciona_envio(mensaje: str) -> bool:
    m = (mensaje or "").lower()
    return any(e in m for e in _SENALES_ENVIO)


def quiere_cotizar(mensaje: str, estado: Optional[str] = None) -> bool:
    """True si el cliente pide precio/cierre o mete el envio. El estado de compra
    (esperando_confirmacion/datos) tambien cuenta como senal."""
    m = (mensaje or "").lower()
    if estado in ("esperando_confirmacion", "esperando_datos"):
        return True
    return (any(s in m for s in _QUIERE_PRECIO) or _menciona_envio(m))


_SENALES_TRANSFERENCIA = ("transferencia", "transferir", "transfiero")


def _menciona_transferencia(mensaje: str) -> bool:
    m = (mensaje or "").lower()
    return any(t in m for t in _SENALES_TRANSFERENCIA)


def _concepto_transferencia(tienda_id: str) -> Optional[str]:
    """Lee de la FAQ de la tienda el concepto del descuento por transferencia,
    si existe y es cuantitativo. Store-agnostico: el id del concepto sale del
    dato, no de una constante."""
    try:
        from app.storage.firestore_client import get_all_faq
        faq = get_all_faq(tienda_id=tienda_id) or {}
        data = faq.get("descuento_transferencia")
        if not data or data.get("tipo") != "cuantitativo":
            return None
        valores = data.get("valores") or []
        return valores[0].get("concepto") if valores else None
    except Exception:
        return None


def _zona_clara(texto: str) -> bool:
    """True si el texto trae una localidad/CP que el codigo sabe clasificar."""
    try:
        from app.core.envio import clasificar_zona
        return clasificar_zona(texto or "") is not None
    except Exception:
        return False


def cotizar_pedido(mensaje: str, registro: list[dict],
                   tienda_id: str,
                   localidad: Optional[str] = None,
                   trace_id: Optional[str] = None) -> Optional[dict]:
    """Resuelve el producto del registro y arma el presupuesto por codigo,
    con envio si el cliente lo pide.

    Args:
        localidad: ultima localidad conocida de la sesion, por si el turno actual
            no la nombra (ej. "el envio ahi" tras haber dicho la ciudad antes).

    Returns:
        {"producto_id", "nombre", "cantidad", "con_envio", "calc"} con el
        resultado de calculate_total (incluye presentacion y proof), o None si no
        se resolvio con confianza, el calculo no dio ok, o se pidio envio pero la
        zona no es clara (en cuyo caso el flujo pregunta la zona).
    """
    hit = resolver_pedido(mensaje, registro)
    if not hit:
        # Si hay un SOLO producto en el registro y el cliente esta cotizando
        # (esta funcion solo corre bajo intencion de cotizar), es ese, aunque no
        # lo nombre. Seguro: no hay con que confundirlo.
        if len(registro) == 1 and registro[0].get("id"):
            p = registro[0]
            hit = {"producto_id": p["id"], "nombre": p.get("nombre"),
                   "precio_ars": p.get("precio_ars"), "cantidad": 1,
                   "motivo": "unico_en_registro"}
        else:
            return None

    from app.core.tools import calculate_total, cotizar_envio
    from app.core.tools_context import set_current_tienda
    set_current_tienda(tienda_id)
    items = [{"product_id": hit["producto_id"], "cantidad": hit["cantidad"]}]

    def _salida(calc, con_envio):
        return {"producto_id": hit["producto_id"], "nombre": hit["nombre"],
                "cantidad": hit["cantidad"], "con_envio": con_envio, "calc": calc}

    # Medio de pago (flag): si el cliente nombra la transferencia, el descuento
    # entra al calculo desde la FAQ. Si la tienda no lo tiene, se cotiza sin el:
    # el presupuesto nunca se pierde por un extra que no existe.
    extras_transf = []
    if settings.COTIZA_TRANSFERENCIA and _menciona_transferencia(mensaje):
        concepto_t = _concepto_transferencia(tienda_id)
        if concepto_t:
            extras_transf = [{"faq_tema": "descuento_transferencia",
                              "concepto": concepto_t}]

    def _calcular(extras: list) -> Optional[dict]:
        """calculate_total con reintento sin transferencia si el extra falla."""
        try:
            calc = calculate_total(items=items, items_extra=extras or None)
        except Exception as e:
            log.warning("cotizar_codigo_error", trace_id=trace_id,
                        error=str(e)[:160])
            return None
        if isinstance(calc, dict) and calc.get("ok"):
            return calc
        if extras_transf and extras_transf[0] in (extras or []):
            sin_transf = [e for e in extras if e not in extras_transf]
            return _calcular(sin_transf)
        return None

    calc_prod = _calcular(extras_transf)
    if not calc_prod:
        log.info("cotizar_codigo_calc_no_ok", trace_id=trace_id,
                 producto=hit["producto_id"])
        return None

    # Sin envio en juego: cotizamos solo productos (con transferencia si entro).
    if not _menciona_envio(mensaje):
        log.info("cotizar_codigo_ok", trace_id=trace_id, con_envio=False,
                 producto=hit["producto_id"], motivo=hit["motivo"])
        return _salida(calc_prod, False)

    # Con envio: la localidad sale del turno si la trae, si no de la memoria.
    loc = mensaje if _zona_clara(mensaje) else (localidad or "")
    if not _zona_clara(loc):
        # Pidio envio pero no hay zona clara: no damos un total a medias.
        log.info("cotizar_codigo_envio_sin_zona", trace_id=trace_id)
        return None

    # cotizar_envio con subtotal 0 para obtener el CONCEPTO de la zona (sin que
    # aplique gratis aca); el gratis por umbral lo decide calculate_total, fuente
    # unica del total.
    try:
        env = cotizar_envio(localidad=loc, subtotal=0)
    except Exception as e:
        log.warning("cotizar_codigo_envio_error", trace_id=trace_id,
                    error=str(e)[:160])
        return None
    if not env.get("ok") or not env.get("concepto"):
        return None

    calc_full = _calcular(
        [{"faq_tema": "costo_envio", "concepto": env["concepto"]}] + extras_transf)
    if not calc_full:
        return None

    log.info("cotizar_codigo_ok", trace_id=trace_id, con_envio=True,
             producto=hit["producto_id"], zona=env.get("zona"),
             motivo=hit["motivo"])
    return _salida(calc_full, True)


def bloque_para_solver(cot: dict) -> str:
    """Arma la linea que recibe el Solver: el presupuesto ya hecho, para que
    redacte la venta alrededor SIN tocar las cifras."""
    pres = (cot.get("calc") or {}).get("presentacion", "")
    if not pres:
        return ""
    return ("\n\n[Presupuesto YA calculado y verificado por el sistema. Copia "
            "estas cifras TAL CUAL y redacta la venta alrededor, sin recalcular "
            "ni cambiar ningun numero:\n" + pres + "]")


def cotizar_pedido_ab(mensaje: str, registro: list[dict],
                      tienda_id: str,
                      localidad: Optional[str] = None,
                      trace_id: Optional[str] = None) -> Optional[dict]:
    """Presupuesto A/B por codigo: cuando la referencia del cliente matchea DOS
    productos del registro (caso donde resolver_pedido se rinde con None), el
    codigo cotiza los dos y el Solver solo presenta opcion A y opcion B
    preguntando cual prefiere. Ante la duda, dos precios; nunca un promedio ni
    una adivinanza.

    Returns:
        {"opciones": [cot_a, cot_b]} con la misma forma de cotizar_pedido, o
        None si no hay exactamente dos candidatos o alguna cotizacion falla
        (un A/B a medias confunde mas de lo que ayuda).
    """
    candidatos = candidatos_pedido(mensaje, registro)
    if len(candidatos) != 2:
        return None
    opciones = []
    for c in candidatos:
        # Registro de un solo producto: cotizar_pedido resuelve por construccion
        # (unico_en_registro) y reusa entero el camino de envio y transferencia.
        sub_registro = [{"id": c["producto_id"], "nombre": c["nombre"],
                         "precio_ars": c["precio_ars"]}]
        cot = cotizar_pedido(mensaje, sub_registro, tienda_id,
                             localidad=localidad, trace_id=trace_id)
        if not cot:
            return None
        opciones.append(cot)
    log.info("cotizar_ab_ok", trace_id=trace_id,
             a=opciones[0]["producto_id"], b=opciones[1]["producto_id"])
    return {"opciones": opciones}


def bloque_ab_para_solver(ab: dict) -> str:
    """Las dos opciones ya calculadas, para que el Solver las presente como
    opcion A y opcion B y cierre preguntando cual prefiere. Mismo contrato que
    el campo ofrecer_opciones del interpretador: nunca elegir, nunca promediar."""
    ops = ab.get("opciones") or []
    if len(ops) != 2:
        return ""
    partes = []
    for letra, cot in zip(("A", "B"), ops):
        pres = (cot.get("calc") or {}).get("presentacion", "")
        partes.append(f"OPCION {letra} — {cot.get('nombre')}:\n{pres}")
    return ("\n\n[El cliente puede referirse a DOS productos. El sistema ya "
            "calculo los dos presupuestos. Presentalos como opcion A y opcion B "
            "copiando las cifras TAL CUAL, sin recalcular ni elegir vos, y "
            "termina preguntando cual prefiere:\n" + "\n\n".join(partes) + "]")


def presentacion_ab(ab: dict) -> str:
    """Texto plano de las dos opciones, para usar de verdad del turno en la
    compuerta: si el Solver rompe las cifras, se cae a ESTE texto."""
    ops = ab.get("opciones") or []
    partes = []
    for letra, cot in zip(("A", "B"), ops):
        pres = (cot.get("calc") or {}).get("presentacion", "")
        partes.append(f"Opcion {letra} — {cot.get('nombre')}:\n{pres}")
    return ("Tengo dos opciones segun a cual te refieras.\n\n"
            + "\n\n".join(partes) + "\n\nCual preferis?")
