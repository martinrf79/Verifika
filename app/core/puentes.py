"""
PUENTES de venta (flag PUENTES_VENTA).

Un PUENTE es una frase que mantiene viva la venta cuando el sistema NO tiene el
dato (no hay precio, no entiende, servicio inexistente, atributo que no figura)
SIN inventar un hecho. Reemplaza el fallback seco "no tengo esa info confirmada"
por algo que ofrece seguir o consultar.

REGLA DURA: un puente NUNCA introduce un hecho (ni precio, ni stock, ni plazo,
ni servicio, ni promesa). Las frases son DATO (data/puentes.json), no logica;
se editan sin tocar codigo ni deployar.

INSISTENCIA: si el cliente vuelve a chocar contra el MISMO hueco, el puente
escala. Al llegar al umbral (default 2) deriva a asesor humano. El conteo se
lleva por usuario, en memoria (best-effort, se pierde al reiniciar el proceso);
se resetea cuando el usuario recibe una respuesta real (marcar_resuelto).

Punto de uso: el orchestrator llama elegir_puente() en el lugar donde hoy
devolveria el fallback por falta de fuente, solo si PUENTES_VENTA esta on.
"""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path

from app.logger import get_logger

log = get_logger(__name__)

_ARCHIVO = Path(__file__).resolve().parents[2] / "data" / "puentes.json"
_CACHE: dict | None = None

# Conteo de choques consecutivos por usuario: {user_id: (tipo, count)}.
_INSISTENCIA: dict[str, tuple[str, int]] = {}


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or "")) \
        .encode("ascii", "ignore").decode().lower()
    return " ".join(t.split())


def cargar_puentes() -> dict:
    """Carga el banco de puentes desde data/puentes.json (cacheado). Si falla,
    devuelve un banco minimo para no romper el flujo."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        with open(_ARCHIVO, encoding="utf-8") as f:
            _CACHE = json.load(f)
    except Exception as e:
        log.warning("puentes_carga_error", error=str(e)[:160])
        _CACHE = {
            "umbral_insistencia": 2,
            "puentes": {"generico": {"keywords": [], "texto": (
                "Esa puntual la confirmo y te aviso, y mientras seguimos con lo "
                "que si tengo a mano?")}},
            "derivar_humano": (
                "Te paso con una persona del equipo que te lo confirma. Me dejas "
                "tu nombre y un telefono?"),
        }
    return _CACHE


def clasificar_situacion(consulta: str) -> str:
    """Mapea la consulta del cliente a un tipo de puente por keyword. El tipo
    'no_entiende'/'generico' es el default cuando ninguna familia matchea."""
    t = _norm(consulta)
    banco = cargar_puentes().get("puentes", {})
    mejor_tipo = "generico"
    mejor_score = 0
    for tipo, p in banco.items():
        score = 0
        for kw in p.get("keywords", []):
            k = _norm(kw)
            if k and k in t:
                # keyword multipalabra pesa mas (mas especifica, menos colision)
                score += 2 if " " in k else 1
        if score > mejor_score:
            mejor_score, mejor_tipo = score, tipo
    return mejor_tipo if mejor_score > 0 else "generico"


def elegir_puente(consulta: str, user_id: str | None = None) -> dict:
    """Devuelve el puente para esta consulta.

    Return: {tipo, texto, derivar}. derivar=True cuando el cliente insistio con
    el mismo hueco hasta el umbral: el texto pasa a ser la derivacion a humano y
    el orchestrator debe marcar estado derivar_humano.
    """
    banco = cargar_puentes()
    umbral = int(banco.get("umbral_insistencia", 2))
    tipo = clasificar_situacion(consulta)

    # Conteo de insistencia: mismo tipo consecutivo suma; tipo distinto reinicia.
    prev_tipo, prev_n = _INSISTENCIA.get(user_id or "", ("", 0))
    n = prev_n + 1 if tipo == prev_tipo else 1
    _INSISTENCIA[user_id or ""] = (tipo, n)

    if n >= umbral:
        log.info("puente_derivar", user_id=user_id, tipo=tipo, insistencia=n)
        return {"tipo": "derivar_humano", "texto": banco.get(
            "derivar_humano", ""), "derivar": True}

    p = banco.get("puentes", {}).get(tipo) or banco.get("puentes", {}).get(
        "generico", {})
    log.info("puente_elegido", user_id=user_id, tipo=tipo, insistencia=n)
    return {"tipo": tipo, "texto": p.get("texto", ""), "derivar": False}


def marcar_resuelto(user_id: str | None) -> None:
    """El usuario recibio una respuesta real: corta la racha de insistencia."""
    if user_id:
        _INSISTENCIA.pop(user_id, None)


def reset(user_id: str | None) -> None:
    """Reset duro del estado de un usuario (lo usa reset_user)."""
    if user_id:
        _INSISTENCIA.pop(user_id, None)
