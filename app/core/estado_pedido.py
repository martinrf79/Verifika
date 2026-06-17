"""
ESTADO_PEDIDO — la planilla unica del turno, siempre completa.

El Provider ya calcula todo lo calculable del turno, pero lo devuelve en piezas
sueltas (foco, ab, multi, carrito_calc, envio...), cada una en None cuando no se
puede calcular, y el contrato se arma seccion por seccion, condicional. Ademas
los datos del cliente (nombre, telefono, direccion, forma de pago) viven aparte,
en el lead. Resultado: no hay UN objeto del pedido que salga completo siempre.

Este modulo compone eso en una sola planilla con TODAS las claves presentes cada
turno, vacias cuando no hay dato:

  - items: id, nombre, cantidad, precio_unitario, subtotal de cada linea
  - subtotal, envio, total (fijo o rango)
  - datos_cliente: nombre, telefono, direccion, forma_pago capturados hasta ahora
  - faltantes: que datos del cliente todavia no estan
  - link: la url actual y el total con que se emitio (la llave de frescura)
  - etapa: consulta / pedido / cierre / capturado
  - activo: si el cliente PIDIO esta cotizacion (no especulativa)
  - vendible: si el stock alcanza (False si el Provider marco faltante)
  - presentacion: el bloque numerico verificado, para que el render lo estampe

Es el continente del que cuelgan las otras tres piezas: el render por codigo
estampa desde presentacion, el delta del carrito muta items y recalcula, y la
regeneracion del link compara el total contra link.total_emitido.

Funcion PURA: no toca Firestore ni el LLM. Solo lee el dict que devuelve
proveer(), el lead y la memoria del link. Por eso se testea sin monkeypatch.

Detras del flag ESTADO_PEDIDO (default off). Nadie lo consume todavia: primero
el objeto sale verde, despues se enchufa.
"""
from typing import Optional

from app.logger import get_logger
from app.core.confirmacion import construir_confirmacion

log = get_logger(__name__)

# Datos del cliente que el cierre necesita. Espeja cierre.CAMPOS_REQUERIDOS; se
# define aca para que el modulo quede puro (no arrastra el import del extractor
# LLM del cierre). Si cambian alla, cambian aca: son el mismo contrato de venta.
CAMPOS_CLIENTE = ("nombre", "telefono", "direccion", "forma_pago")

# Estados de conversacion que ya son parte del cierre (el cliente esta dando o
# por dar sus datos).
_ESTADOS_CIERRE = ("esperando_datos", "esperando_confirmacion")


def _pedido_activo(prov: dict) -> tuple[Optional[dict], str]:
    """El calculo que representa EL pedido del turno, con su origen. Misma
    precedencia que verdad_del_turno: el foco gana (con envio si la zona se
    conoce), despues el pedido combinado, despues el carrito vigente. El A/B no
    es un pedido cerrado (el cliente todavia no eligio): no entra aca."""
    foco = prov.get("foco")
    carrito_calc = prov.get("carrito_calc")
    # El carrito ACUMULADO (2+ items) ES el pedido: gana sobre el foco (un solo
    # producto en foco). EN SINCRONIA con provider.verdad_del_turno: si una
    # cambia, la otra tambien, o el render y el guardado vuelven a divergir.
    if (carrito_calc and carrito_calc.get("presentacion")
            and len(carrito_calc.get("detalle") or []) >= 2):
        return carrito_calc, "carrito"
    if foco and (foco.get("calc") or {}).get("presentacion"):
        fec = prov.get("foco_envio_calc")
        if fec and fec.get("presentacion"):
            return fec, "foco_con_envio"
        return foco["calc"], "foco"
    multi = prov.get("multi")
    if multi and (multi.get("calc") or {}).get("presentacion"):
        return multi["calc"], "multi"
    if carrito_calc and carrito_calc.get("presentacion"):
        return carrito_calc, "carrito"
    return None, "ninguno"


def _items_de(calc: Optional[dict]) -> list[dict]:
    """Las lineas del pedido desde el detalle de calculate_total."""
    items = []
    for d in (calc or {}).get("detalle") or []:
        if not d.get("id"):
            continue
        items.append({
            "id": d["id"],
            "nombre": d.get("nombre"),
            "cantidad": d.get("cantidad", 1),
            "precio_unitario": d.get("precio_unitario"),
            "subtotal": d.get("subtotal"),
        })
    return items


def _total_de(calc: Optional[dict]) -> dict:
    """El total del pedido. fijo cuando hay un numero unico, rango cuando el
    envio es un rango de interior, sin_dato cuando todavia no hay pedido."""
    base = {"tipo": "sin_dato", "valor": None, "min": None, "max": None}
    if not calc:
        return base
    if calc.get("total_ars") is not None:
        return {"tipo": "fijo", "valor": calc["total_ars"],
                "min": None, "max": None}
    if calc.get("total_min_ars") is not None:
        return {"tipo": "rango", "valor": None,
                "min": calc.get("total_min_ars"), "max": calc.get("total_max_ars")}
    return base


def _envio_de(envio: Optional[dict]) -> dict:
    """La linea de envio normalizada. cerrado trae el monto (o gratis, o rango),
    pendiente_cp cuando falta la zona, sin_dato cuando el envio no esta en juego."""
    base = {"estado": "sin_dato", "modalidad": None, "monto": None,
            "min": None, "max": None, "zona": None, "concepto": None}
    if not envio:
        return base
    est = envio.get("estado")
    if est == "pedir_cp":
        base["estado"] = "pendiente_cp"
        return base
    if est == "cotizado":
        det = envio.get("detalle") or {}
        base["estado"] = "cerrado"
        base["zona"] = det.get("zona")
        base["concepto"] = det.get("concepto")
        if det.get("modalidad") == "rango":
            base["modalidad"] = "rango"
            base["min"] = det.get("monto_min")
            base["max"] = det.get("monto_max")
        elif det.get("concepto") == "envio_gratis" or det.get("monto") == 0:
            base["modalidad"] = "gratis"
            base["monto"] = 0
        else:
            base["modalidad"] = "fijo"
            base["monto"] = det.get("monto")
    return base


def _ambiguos_de(prov: dict) -> list[dict]:
    """Terminos que el cliente pidio y todavia tienen varias opciones reales
    ('2 mouses' con varios modelos). El pedido no cierra hasta que elija."""
    multi = prov.get("multi") or {}
    return [{"termino": a.get("termino"), "cantidad": a.get("cantidad")}
            for a in (multi.get("ambiguos") or [])]


def construir_estado(prov: dict, *,
                     lead: Optional[dict] = None,
                     link_actual: str = "",
                     link_total: Optional[int] = None,
                     estado_conv: Optional[str] = None,
                     interpretacion: Optional[dict] = None,
                     trace_id: Optional[str] = None) -> dict:
    """Compone la planilla unica del turno. Siempre devuelve el mismo objeto con
    todas las claves; lo que no hay queda vacio, nunca ausente.

    Args:
        prov: lo que devuelve provider.proveer().
        lead: datos del cliente capturados hasta ahora (nombre, telefono,
            direccion, forma_pago). Vacios o ausentes los que falten.
        link_actual: la url del link de pago ya emitido, si hubo.
        link_total: el total con que se emitio ese link (la llave de frescura).
        estado_conv: el estado de la conversacion (esperando_datos, etc).
        interpretacion: la del interprete, para la pista de confirmacion.

    Returns:
        dict con items, subtotal, envio, total, datos_cliente, faltantes, link,
        etapa, activo, vendible, presentacion, ambiguos, confirmacion, origen.
    """
    prov = prov or {}
    calc, origen = _pedido_activo(prov)

    # Confirmacion: campo siempre presente (necesita=False y vacio cuando no hace
    # falta). El codigo arma la frase desde los candidatos reales del Provider;
    # la pista del interprete entra como tal, no decide.
    confirmacion = construir_confirmacion(
        prov, interpretacion=interpretacion, estado_conv=estado_conv,
        trace_id=trace_id)

    items = _items_de(calc)
    total = _total_de(calc)
    subtotal = (calc or {}).get("subtotal_productos_ars")
    presentacion = (calc or {}).get("presentacion", "")
    envio = _envio_de(prov.get("envio"))

    datos_cliente = {c: str((lead or {}).get(c, "") or "").strip()
                     for c in CAMPOS_CLIENTE}
    faltantes = [c for c in CAMPOS_CLIENTE if not datos_cliente[c]]

    # Link y su frescura: vigente solo cuando hay link Y este turno hay un total
    # fijo con que compararlo. Sin total fijo este turno (no se recalculo el
    # pedido, o el total es un rango) queda None: indeterminado, no falso-rancio.
    total_fijo = total["valor"] if total["tipo"] == "fijo" else None
    if not link_actual:
        link_vigente = False
    elif total_fijo is None:
        link_vigente = None
    else:
        link_vigente = (link_total == total_fijo)
    link = {"url": str(link_actual or ""), "total_emitido": link_total,
            "vigente": link_vigente}

    # Etapa: si el turno tiene que preguntar (confirmacion abierta) y no hay un
    # pedido cerrado, la etapa es confirmar (el trabajo es resolver la
    # ambiguedad). Sin items es consulta; con items, capturado cuando estan los
    # cuatro datos del cliente, cierre cuando hay algun dato o el estado ya es de
    # cierre, pedido en el resto.
    tiene_cliente = any(datos_cliente.values())
    if confirmacion["necesita"] and not items:
        etapa = "confirmar"
    elif not items:
        etapa = "consulta"
    elif not faltantes:
        etapa = "capturado"
    elif tiene_cliente or estado_conv in _ESTADOS_CIERRE:
        etapa = "cierre"
    else:
        etapa = "pedido"

    estado = {
        "etapa": etapa,
        "activo": bool(prov.get("quiere_cotizar")),
        "vendible": not bool(prov.get("stock_falta")),
        "origen": origen,
        "items": items,
        "subtotal": subtotal,
        "envio": envio,
        "total": total,
        "datos_cliente": datos_cliente,
        "faltantes": faltantes,
        "link": link,
        "ambiguos": _ambiguos_de(prov),
        "confirmacion": confirmacion,
        "presentacion": presentacion,
    }

    log.info("estado_pedido_construido", trace_id=trace_id, etapa=etapa,
             origen=origen, items=len(items), total_tipo=total["tipo"],
             faltan=len(faltantes), link_vigente=link_vigente,
             activo=estado["activo"], vendible=estado["vendible"],
             confirma=confirmacion["necesita"])
    return estado


def lineas_items(estado: dict) -> str:
    """Detalle de items en texto, para el resumen del cierre (punto 5): el
    resumen sale del estado, no de un string suelto que puede venir sin detalle.
    Una linea por item; vacio si no hay items."""
    out = []
    for it in estado.get("items") or []:
        cant = it.get("cantidad", 1)
        nombre = it.get("nombre") or it.get("id")
        sub = it.get("subtotal")
        if isinstance(sub, (int, float)):
            monto = f"${sub:,.0f}".replace(",", ".")
            out.append(f"- {cant}x {nombre}: {monto}")
        else:
            out.append(f"- {cant}x {nombre}")
    return "\n".join(out)
