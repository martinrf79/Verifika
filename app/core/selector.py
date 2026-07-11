"""
SELECTOR — la eleccion del MENU CERRADO (decision de Martin, 10-jul).

La causa comun de las fallas del banco 11-jul no era el dato (el juez salio
limpio) sino QUE responder: la cascada de regex y prioridades fijas del
compositor elegia la seccion equivocada porque no ve la conversacion entera.
El selector es UNA llamada LLM que recibe la lectura del interprete + el
estado sellado (pedido vigente, producto anotado, destinos, criterio,
resumen) y cuya UNICA salida posible, atada por schema estricto, es elegir
del MENU que secciones componen el turno. El modelo VE todo para elegir
bien; JAMAS escribe un dato: cada seccion la arma el CODIGO desde la fuente
y puede devolver None si la fuente no respalda (la atadura garantiza salida
EN el menu, no la eleccion correcta: los verificadores siguen atras).

Red de degradacion (mismo patron que el redactor): error, timeout o plan
vacio -> None, y el compositor cae a su cascada determinista de siempre.
El peor caso es la conducta vieja, nunca un dato falso.
"""
import asyncio

from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

_TIMEOUT_S = 8
_MAX_SECCIONES = 3

# El MENU. Cada tipo mapea a una seccion determinista del compositor.
TIPOS_MENU = (
    "saludo",             # bienvenida (solo saludo puro)
    "ficha_producto",     # ficha real de UN producto (argumento: nombre)
    "opciones_categoria",  # opciones con stock (argumento: categoria)
    "mas_barato",         # el minimo con stock (argumento: categoria o null)
    "intermedio",         # la opcion de precio medio (argumento: categoria)
    "envio",              # cotizar/informar envio del destino de la charla
    "faq",                # politica oficial curada (argumento: tema o null)
    "movida",             # curada de venta B (argumento: B4..B24 o null)
    "rechazo",            # reconocer un descarte, sin insistir
    "not_found",          # no trabajamos eso, honesto (argumento: termino)
    "preguntar",          # falta UN dato para responder bien
    "fallback",           # no se entendio
)


def _schema_selector() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "secciones": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "tipo": {"type": "string", "enum": list(TIPOS_MENU)},
                    "argumento": {"type": ["string", "null"]},
                },
                "required": ["tipo", "argumento"],
            }},
        },
        "required": ["secciones"],
    }


def _linea_estado(estado: dict, interp: dict, tienda_id: str) -> str:
    """El estado sellado COMPACTO que el selector ve para elegir bien."""
    partes = []
    an = (estado.get("producto_anotado") or {})
    if an.get("nombre"):
        partes.append(f"Producto ANOTADO por el cliente: {an['nombre']}")
    carrito = estado.get("carrito") or []
    if carrito:
        det = ", ".join(f"{c.get('cantidad', 1)}x {c.get('nombre')}"
                        for c in carrito[:6] if isinstance(c, dict))
        partes.append(f"Pedido vigente (carrito): {det}")
    pend = estado.get("pedido_categorias_pendiente") or []
    if pend:
        det = ", ".join(f"{c.get('cantidad')}x {c.get('categoria')}"
                        for c in pend if isinstance(c, dict))
        partes.append(f"Pedido pendiente de modelos: {det}")
    locs = estado.get("localidades_envio") or []
    if locs:
        partes.append("Destinos de envío dados: " + ", ".join(locs[:4]))
    if (estado.get("criterio") or "").strip():
        partes.append(f"Criterio del cliente: {estado['criterio']}")
    vistos = [p.get("nombre") for p in (estado.get("productos_vistos") or [])
              if isinstance(p, dict) and p.get("nombre")]
    if vistos:
        partes.append("Productos ya mostrados: " + "; ".join(vistos[:10]))
    if (estado.get("resumen_charla") or "").strip():
        partes.append("Resumen de la charla vieja: "
                      + estado["resumen_charla"][:400])
    from app.storage.firestore_client import get_categories
    cats = list(get_categories(tienda_id=tienda_id) or [])[:24]
    partes.append("Categorías reales de la tienda: "
                  + ", ".join(str(c) for c in cats))
    lec = []
    for k in ("intencion", "producto_resuelto", "candidatos", "criterio",
              "estado_conversacion", "confianza"):
        v = (interp or {}).get(k)
        if v not in (None, "", []):
            lec.append(f"{k}={v}")
    partes.append("Lectura del intérprete: " + "; ".join(lec))
    return "\n".join("- " + p for p in partes)


def _prompt(mensaje: str, interp: dict, estado: dict, tienda_id: str) -> str:
    return (
        "Sos el SELECTOR de un bot de ventas de una tienda online argentina. "
        "NO escribís texto: tu única salida es elegir del MENÚ qué secciones "
        "componen la respuesta de este turno, en orden. El código arma cada "
        "sección con datos verificados del catálogo y la FAQ.\n\n"
        "MENÚ (tipo: qué hace / argumento):\n"
        "- saludo: bienvenida; solo si el mensaje es un saludo puro.\n"
        "- ficha_producto: ficha real de UN producto puntual / nombre del "
        "producto tal como aparezca en la charla.\n"
        "- opciones_categoria: opciones con stock de una categoría / la "
        "categoría.\n"
        "- mas_barato: el más barato con stock / categoría o null.\n"
        "- intermedio: la opción de precio medio (cliente que rechaza lo más "
        "barato) / categoría o null.\n"
        "- envio: cotiza o informa el envío al destino dicho en la charla / "
        "null.\n"
        "- faq: política oficial de la tienda (pagos, cuotas, garantía, "
        "envíos en general, factura, devoluciones...) / null.\n"
        "- movida: jugada de venta para casos difíciles / una de: B4 regateo, "
        "B5 objeción de precio, B11 postergación, B17 queja, B18 pedir "
        "humano o sos bot, B19 cancelación, B22 fotos.\n"
        "- rechazo: el cliente descarta algo mostrado; se reconoce sin "
        "insistir / null.\n"
        "- not_found: pregunta por algo que la tienda no trabaja / el "
        "término.\n"
        "- preguntar: falta UN dato imprescindible / qué falta.\n"
        "- fallback: no se entiende el mensaje / null.\n\n"
        "REGLAS:\n"
        "- Elegí 1 a 3 secciones, las mínimas que respondan TODO lo que el "
        "cliente preguntó en este mensaje (si preguntó dos cosas, dos "
        "secciones, en el orden de sus preguntas).\n"
        "- Pregunta de TEXTO/política → faq o movida. Pregunta de "
        "ESTADO/CÁLCULO (precio, total, envío, stock) → sección de datos. "
        "PROHIBIDO tapar un cálculo con texto enlatado.\n"
        "- Si el cliente referencia algo ya elegido o anotado, usá ese "
        "producto, no vuelvas a listar opciones.\n"
        "- Ante ambigüedad real: preguntar. Nunca adivines.\n\n"
        f"ESTADO:\n{_linea_estado(estado, interp, tienda_id)}\n\n"
        f"Mensaje del cliente:\n{(mensaje or '').strip()}\n\n"
        "Respondé SOLO el JSON del plan."
    )


def validar_plan(d) -> list[dict] | None:
    """Filtra el plan crudo a una lista sana de secciones. None si no queda
    nada usable (el compositor cae a su cascada)."""
    if not isinstance(d, dict):
        return None
    plan = []
    vistos = set()
    for s in (d.get("secciones") or [])[:_MAX_SECCIONES]:
        if not isinstance(s, dict):
            continue
        tipo = str(s.get("tipo") or "")
        if tipo not in TIPOS_MENU or tipo in vistos:
            continue
        vistos.add(tipo)
        arg = s.get("argumento")
        plan.append({"tipo": tipo,
                     "argumento": str(arg).strip() if arg else None})
    return plan or None


async def elegir_plan(mensaje: str, interp: dict, estado: dict,
                      tienda_id: str,
                      trace_id: str | None = None) -> list[dict] | None:
    """El plan del turno elegido por el LLM, atado por schema estricto.
    None ante error/timeout/plan vacio: el compositor sigue con su cascada."""
    from app.core.interpretador import _llamar_llm, parsear_respuesta_llm
    prompt = _prompt(mensaje, interp or {}, estado or {}, tienda_id)
    rf = {"type": "json_schema", "json_schema": {
        "name": "plan_menu", "strict": True, "schema": _schema_selector()}}
    try:
        raw = await asyncio.wait_for(
            _llamar_llm(prompt, response_format=rf), timeout=_TIMEOUT_S)
    except Exception as e:
        log.warning("selector_llm_error", trace_id=trace_id,
                    error=str(e)[:120])
        return None
    plan = validar_plan(parsear_respuesta_llm(raw))
    log.info("selector_plan", trace_id=trace_id, plan=plan)
    return plan
