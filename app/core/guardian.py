"""
GUARDIÁN L1 — única capa de validación post-respuesta.
Verifica que los IDs y precios mencionados en la respuesta del LLM existan
realmente en el catálogo. Si no, log + señalamos. No reescribimos la respuesta.

Es una red de seguridad para detectar alucinaciones, no para repararlas.
Con la arquitectura de tools, las alucinaciones son raras pero no imposibles
(el LLM puede mencionar un precio que no llamó).
"""
import os
import re
from app.storage.firestore_client import get_all_products, get_product_by_id, get_all_faq
from app.logger import get_logger

log = get_logger(__name__)

ID_PATTERN = re.compile(r"\b([A-Z]{3,4}-\d{3})\b")
PRICE_PATTERN = re.compile(r"\$\s*([\d.]+)")

# Tolerancia para precios mencionados (ej: redondeos)
PRICE_TOLERANCE_PCT = 0.01

# Marcadores internos que el backend inyecta al Solver dentro del mensaje
# (contexto del interpretador, estado, registro de sesion, presupuesto por
# codigo). Algunos modelos los repiten en la respuesta y el cliente los ve
# (paso con gemini-2.5-flash en el molino multiturno). Se borran por codigo
# antes de mostrar. Flag LIMPIA_MARCADORES_INTERNOS, default on: es higiene,
# nunca hay un caso legitimo en que el cliente deba ver estos bloques.
MARCADOR_INTERNO_PATTERN = re.compile(
    r"\[(?:Contexto del Interpretador|Estado de la conversaci[oó]n|"
    r"ofrecer_opciones|El cliente se refiere a|Presupuesto YA calculado|"
    r"Productos ya mostrados)[^\]]*\]",
    re.IGNORECASE | re.DOTALL)


def validate_response(response_text: str, trace_id: str,
                      tienda_id: str | None = None) -> dict:
    log.info("validate_response_inicio")
    """Valida estructuralmente la respuesta. NO la modifica.

    tienda_id es obligatorio en multi-tenant: sin el, se valida contra la
    tienda default y se generan falsos positivos en otras tiendas.
    """
    productos = get_all_products(tienda_id=tienda_id)
    valid_ids = {p["id"].upper() for p in productos}
    valid_prices = {p["precio_ars"] for p in productos}
    # Sumar numeros validos de FAQ, son precios de envio, descuentos, plazos.
    try:
        faqs = get_all_faq(tienda_id=tienda_id)
        for tema_id, data in faqs.items():
            respuesta = data.get("respuesta", "")
            for raw in PRICE_PATTERN.findall(respuesta):
                try:
                    valid_prices.add(int(raw.replace(".", "").replace(",", "")))
                except ValueError:
                    continue
            # Tambien numeros sin signo peso, tipo doscientos cincuenta mil
            for raw in re.findall(r"\b(\d{4,7})\b", respuesta):
                try:
                    valid_prices.add(int(raw))
                except ValueError:
                    continue
    except Exception as e:
        log.warning("guardian_faq_load_failed", error=str(e)[:100])

    ids_found = ID_PATTERN.findall(response_text)
    prices_found = []
    for raw in PRICE_PATTERN.findall(response_text):
        try:
            prices_found.append(int(raw.replace(".", "").replace(",", "")))
        except ValueError:
            continue

    invalid_ids = [pid for pid in ids_found if pid.upper() not in valid_ids]
    invalid_prices = [
        p for p in prices_found
        if not any(abs(p - vp) <= max(vp * PRICE_TOLERANCE_PCT, 100) for vp in valid_prices)
        and p > 1000  # ignoramos números chicos que pueden ser otra cosa
    ]

    report = {
        "ids_found": ids_found,
        "prices_found": prices_found,
        "invalid_ids": invalid_ids,
        "invalid_prices": invalid_prices,
        "is_clean": len(invalid_ids) == 0 and len(invalid_prices) == 0,
    }

    if not report["is_clean"]:
        log.warning("guardian_validation_issue", trace_id=trace_id, **report)
    else:
        log.info("guardian_validation_ok", trace_id=trace_id,
                 ids=len(ids_found), prices=len(prices_found))

    return report


def _strip_markdown(text: str) -> str:
    """
    Saca el markdown que DeepSeek mete aunque el prompt lo prohiba.
    Telegram y WhatsApp se mandan en texto plano: los asteriscos, las vinetas
    y los encabezados se ven literales y la respuesta queda rota.
    Opera sobre el texto con saltos de linea todavia presentes, antes de
    colapsar espacios. Conserva el contenido, solo saca los marcadores.
    """
    # Encabezados: ## Titulo  ->  Titulo
    text = re.sub(r"(?m)^[ \t]{0,3}#{1,6}[ \t]*", "", text)
    # Negrita/italica con asteriscos: **x** *x* -> x
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*\n]+)\*", r"\1", text)
    # Negrita/italica con guion bajo: __x__ -> x
    text = re.sub(r"__([^_]+)__", r"\1", text)
    # Vinetas al inicio de linea: "- item" / "* item" / "+ item" -> "item"
    # Se mantiene cada item en su propia linea para que al colapsar quede
    # separado por un espacio y no se peguen las palabras.
    text = re.sub(r"(?m)^[ \t]*[-*+][ \t]+", "", text)
    # Asteriscos sueltos que hayan quedado
    text = text.replace("*", "")
    return text


def clean_response(response_text: str, tienda_id: str | None = None) -> str:
    """
    Limpia la respuesta para mostrarla al usuario:
    - Reemplaza markers [ID] residuales por nombre del producto.
    - Si el ID no existe, lo borra silenciosamente.
    - Saca markdown (asteriscos, vinetas, encabezados).
    - Normaliza espacios.

    tienda_id es obligatorio en multi-tenant: el reemplazo de [ID] busca el
    producto en la tienda correcta, no en la default.
    """
    def _replace(match):
        product_id = match.group(1)
        product = get_product_by_id(product_id, tienda_id=tienda_id)
        if not product:
            return ""
        return product["nombre"]

    # Marcadores internos del backend que el modelo haya repetido
    if os.getenv("LIMPIA_MARCADORES_INTERNOS", "true").lower() == "true":
        response_text = MARCADOR_INTERNO_PATTERN.sub("", response_text)
    # Marker con corchetes: [MON-001]
    cleaned = re.sub(r"\[([A-Z]{3,4}-\d{3})\]", _replace, response_text)
    # Sacar markdown antes de colapsar espacios (necesita los saltos de linea)
    cleaned = _strip_markdown(cleaned)
    # Normalizar dobles espacios y espacios antes de signos
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s+([,.!?;:])", r"\1", cleaned)
    return cleaned.strip()
