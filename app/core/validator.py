"""
Validator post-LLM en codigo duro.

v4 (23 may 2026):
- Cinco categorias originales (composicion, normativas, promociones,
  garantias_universales, acciones_falsas).
- Sacamos las cuatro categorias nuevas que generaban demasiada friccion
  en respuestas legitimas de un vendedor.
- Verifika sigue activo como red de seguridad semantica.
- Mensajes de derivacion en tono vendedor.
"""
import re
import random
import logging

log = logging.getLogger(__name__)

VARIANTES_DERIVACION = [
    "Eso puntual no lo tengo confirmado, pero contame que buscas y te muestro lo que si tengo disponible.",
    "Ese dato preciso lo tengo que chequear, mientras tanto puedo mostrarte alternativas que tenemos en stock, decime que te interesa.",
    "No tengo esa info exacta confirmada, pero si me das una pista mas de lo que necesitas te ayudo a encontrar algo del catalogo.",
]


def mensaje_derivacion() -> str:
    return random.choice(VARIANTES_DERIVACION)


PALABRAS_PELIGROSAS = {
    "composicion": [
        "metal", "metalico", "metalica", "plomo", "aluminio", "madera",
        "plastico", "cuero", "algodon", "sintetico", "abs", "acero",
        "hierro", "bronce", "vidrio", "ceramica", "fibra", "carbono",
    ],
    "normativas": [
        "iso", "fda", "ce", "anmat", "iram", "norma", "normativa",
        "certificacion", "certificado", "certifica", "homologacion",
        "homologado", "estandar internacional", "seguridad internacional",
    ],
    "promociones": [
        "descuento", "promocion", "oferta", "2x1", "3x2", "rebaja",
        "cuotas sin interes", "envio gratis", "gratis", "bonificacion",
        "regalo", "premio", "sorteo",
    ],
    "garantias_universales": [
        "todos nuestros productos", "todos los productos",
        "todas nuestras", "garantia oficial", "garantizamos",
        "siempre tenemos", "siempre hay", "nunca falla",
    ],
    "acciones_falsas": [
        "te paso con un humano", "te transfiero", "te conecto con",
        "te derive a", "te derivamos", "ya te pase", "ya te transferi",
        "procese tu pedido", "aplique el descuento",
    ],
}


def _normalizar(texto: str) -> str:
    if not texto:
        return ""
    texto = texto.lower()
    reemplazos = {
        "\u00e1": "a", "\u00e9": "e", "\u00ed": "i",
        "\u00f3": "o", "\u00fa": "u", "\u00f1": "n",
    }
    for original, simple in reemplazos.items():
        texto = texto.replace(original, simple)
    return texto


def _palabra_en_texto(palabra: str, texto: str) -> bool:
    patron = r"\b" + re.escape(palabra) + r"\b"
    return bool(re.search(patron, texto))


def validar_respuesta(
    respuesta_llm: str,
    evidencia_texto: str,
    pregunta_usuario: str = "",
) -> dict:
    if not respuesta_llm or not respuesta_llm.strip():
        return {
            "valida": True,
            "respuesta_final": respuesta_llm,
            "motivo": "respuesta_vacia",
            "categoria": None,
            "palabra": None,
            "respuesta_original": respuesta_llm,
        }

    respuesta_norm = _normalizar(respuesta_llm)
    evidencia_norm = _normalizar(evidencia_texto or "")

    for categoria, palabras in PALABRAS_PELIGROSAS.items():
        for palabra in palabras:
            palabra_norm = _normalizar(palabra)
            if _palabra_en_texto(palabra_norm, respuesta_norm):
                if not _palabra_en_texto(palabra_norm, evidencia_norm):
                    log.warning(
                        "validator_block",
                        extra={
                            "categoria": categoria,
                            "palabra": palabra,
                            "pregunta": pregunta_usuario[:200] if pregunta_usuario else "",
                            "respuesta_llm": respuesta_llm[:300],
                        },
                    )
                    return {
                        "valida": False,
                        "respuesta_final": mensaje_derivacion(),
                        "motivo": "palabra_sin_evidencia",
                        "categoria": categoria,
                        "palabra": palabra,
                        "respuesta_original": respuesta_llm,
                    }

    return {
        "valida": True,
        "respuesta_final": respuesta_llm,
        "motivo": "ok",
        "categoria": None,
        "palabra": None,
        "respuesta_original": respuesta_llm,
    }
