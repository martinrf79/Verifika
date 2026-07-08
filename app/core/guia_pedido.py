"""
GUIA DETERMINISTA DE PEDIDO (8-jul) — el CODIGO arma el presupuesto cuando el
pedido esta definido; el solver no elige ids ni suma a mano.

Cierra el hueco visto en el caso real de multi-envio: el cliente nombro los
tres productos con cantidades y el solver llamo la calculadora con ids
EQUIVOCADOS (TEC0011/MOU0049 por el K120/DX-110 pedidos) y despues tipeo la
cuenta a mano, con renglones sin multiplicar y un solo envio sumado de tres.

El camino nuevo, mismo patron que guia_mas_barato / guia_memoria:
  1. El INTERPRETE (constrained: el campo `pedido` esta atado por enum a los
     productos MOSTRADOS) extrae que productos y cuantos pidio el cliente.
  2. Este modulo reconcilia cada nombre con UN id de los productos vistos
     (match exacto normalizado; el enum ya garantiza el texto) y llama
     calculate_total con esos items, los destinos cotizados y el envio.
  3. El resultado entra a meta.tools_called como una llamada mas: el marcador
     [[PRESUPUESTO]] se estampa con la presentacion sellada, el proof respalda
     los montos en el verificador y el cierre usa el total real.

Conservador como todo: ante CUALQUIER duda (confianza baja, un nombre que no
reconcilia, cantidad rara, la calculadora devuelve error) devuelve None y el
turno sigue por el camino de siempre. Todo o nada: no se calcula un pedido a
medias.
"""
import unicodedata

from app.logger import get_logger

log = get_logger(__name__)

# Confianza minima del interprete para que el codigo se anime a armar el
# pedido solo. Umbral operativo (config en codigo, no flag).
_CONF_MIN = 0.6
# Techo sano de cantidad por item: un numero disparatado no arma pedido.
_MAX_CANTIDAD = 99


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def items_de_pedido(interp: dict | None,
                    productos_vistos: list[dict] | None) -> list[dict] | None:
    """[{product_id, cantidad}] si el pedido del interprete reconcilia ENTERO
    con los productos vistos (cada nombre matchea UN id). None ante cualquier
    duda: un item que no reconcilia invalida todo el pedido."""
    if not isinstance(interp, dict):
        return None
    try:
        conf = float(interp.get("confianza") or 0)
    except (TypeError, ValueError):
        return None
    if conf < _CONF_MIN:
        return None
    pedido = interp.get("pedido")
    if not isinstance(pedido, list) or not pedido:
        return None
    por_nombre: dict[str, str] = {}
    for pv in (productos_vistos or []):
        if isinstance(pv, dict) and pv.get("nombre") and pv.get("id"):
            por_nombre[_norm(pv["nombre"])] = str(pv["id"]).upper()
    if not por_nombre:
        return None
    items: list[dict] = []
    for it in pedido:
        if not isinstance(it, dict):
            return None
        pid = por_nombre.get(_norm(it.get("producto")))
        try:
            cant = int(it.get("cantidad"))
        except (TypeError, ValueError):
            return None
        if not pid or not (1 <= cant <= _MAX_CANTIDAD):
            return None
        # Un id repetido en el pedido es un artefacto del modelo, no un pedido
        # real ("3 mouse" dos veces): todo-o-nada, no se suma dos veces.
        if any(i["product_id"] == pid for i in items):
            return None
        items.append({"product_id": pid, "cantidad": cant})
    return items or None


def calcular_pedido(interp: dict | None, estado: dict | None,
                    tienda_id: str, trace_id: str | None = None) -> list[dict] | None:
    """Corre calculate_total con el pedido extraido por el interprete. Devuelve
    la lista de entradas estilo tools_called (para mergear en meta) o None si
    la guia no aplica o la calculadora no pudo (stock, envio sin zona, etc.)."""
    estado = estado if isinstance(estado, dict) else {}
    items = items_de_pedido(interp, estado.get("productos_vistos"))
    if not items:
        # Visibilidad: si el interprete SI trajo un pedido pero no reconcilio
        # con los vistos, eso es un hueco a mirar (nombre distinto, visto sin
        # id). Un pedido vacio del interprete es el caso normal y no se loguea.
        if isinstance(interp, dict) and interp.get("pedido"):
            log.warning("guia_pedido_no_reconcilia", trace_id=trace_id,
                        pedido=interp.get("pedido"),
                        vistos=[str((p or {}).get("nombre"))[:40]
                                for p in (estado.get("productos_vistos") or [])[:8]])
        return None
    from app.core.tools_context import set_current_tienda
    from app.core.tools import calculate_total
    set_current_tienda(tienda_id)

    # Destinos: los que la charla ya cotizo (memoria multi-destino). El envio
    # solo se suma si hay al menos una zona resuelta; si no, el presupuesto va
    # sin envio y el solver pide el dato como siempre.
    locs = [l for l in (estado.get("localidades_envio") or []) if l]
    destinos = max(1, len(locs))
    extra = ([{"faq_tema": "costo_envio", "concepto": "envio"}]
             if locs else None)

    args = {"items": items, "destinos": destinos,
            **({"items_extra": extra} if extra else {})}
    try:
        res = calculate_total(**args)
    except Exception as e:
        log.warning("guia_pedido_calc_error", trace_id=trace_id,
                    error=str(e)[:120])
        return None
    if not isinstance(res, dict) or not res.get("ok") or not res.get("presentacion"):
        log.info("guia_pedido_no_aplica", trace_id=trace_id,
                 motivo=str((res or {}).get("mensaje_para_llm"))[:120])
        return None
    log.info("guia_pedido_calculado", trace_id=trace_id,
             items=len(items), destinos=destinos)
    entrada = {"name": "calculate_total", "args": args, "result": res}
    if res.get("proof"):
        entrada["proof"] = res["proof"]
    return [entrada]


# Instruccion para el solver cuando la guia calculo el pedido: redacta la
# venta alrededor del bloque sellado, sin tocar un numero.
INSTRUCCION_SOLVER = (
    "\n\n[PEDIDO YA CALCULADO: el código armó el presupuesto EXACTO del pedido "
    "del cliente con la calculadora oficial (productos, cantidades, envío por "
    "destino). Escribí tu respuesta de venta y poné el marcador [[PRESUPUESTO]] "
    "donde va el detalle: el código estampa ahí el bloque real. NO escribas vos "
    "ningún precio, subtotal, total ni costo de envío, ni vuelvas a llamar "
    "calculate_total: ya está hecho.]")
