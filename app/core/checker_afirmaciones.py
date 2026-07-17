"""
CHECKER DE AFIRMACIONES (nivel 3 del fiscal, 17-jul) — la Capa A del CLAUDE.md
(Proposer + Checker) aplicada a la prosa blanda. El codigo no puede juzgar si
"es ideal para gaming" tiene respaldo; un modelo chico SI, y chequear es mucho
mas facil que redactar. El contrato:

  - El modelo grande redacta libre (la venta no se aprieta).
  - Este checker recibe la respuesta + la EVIDENCIA del turno (fichas de los
    productos ofrecidos, FAQ consultada, prosa jurada citada) y devuelve, con
    salida atada por enum, cada afirmacion de HECHO con su veredicto:
    respaldada, sin_respaldo o neutral.
  - El CODIGO decide, determinista: una afirmacion sin_respaldo cuya oracion
    aparece VERBATIM en la respuesta y no contiene digitos ni $ (los numeros
    son territorio del verificador de plata, que ya corrio) se PODA. El resto
    solo se MARCA en el log: filtro blando, no mata la venta.
  - Error, timeout o sin clave -> None y el turno sigue igual. El checker
    jamas rompe ni bloquea.

Costo: una llamada corta a flash-lite por turno del solver (respuesta +
evidencia, sin el contexto grande). El log checker_sin_respaldo es el radar:
si un tipo de desliz se repite, se tapa con prosa jurada o ficha, no
cambiando este contrato.
"""
import asyncio
import json
import re

from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

# Tope de espera ACOTADO: el checker corre al final del camino critico y ante
# timeout es no-op, asi que el peor caso que puede sumar es esto. Medido vivo
# 17-jul: 1,5-2,9 s (promedio ~2 s) en tier gratis; 4 s cubre el triple del
# promedio sin dejar al cliente colgado si Gemini anda lento.
_TIMEOUT_S = 4
_MAX_EVIDENCIA = 4000

_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"afirmaciones": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "texto": {"type": "string"},
            "veredicto": {"type": "string",
                          "enum": ["respaldada", "sin_respaldo", "neutral"]},
        },
        "required": ["texto", "veredicto"]}}},
    "required": ["afirmaciones"]}


def evidencia_de_meta(meta: dict, tienda_id: str | None = None) -> str:
    """Junta la evidencia REAL del turno: ficha completa de cada producto que
    las tools mostraron, respuestas de FAQ consultadas y bloques de prosa
    jurada citados. Es lo unico contra lo que se juzga la respuesta."""
    from app.core.estado_venta import productos_de_meta
    from app.storage.firestore_client import get_product_by_id
    partes = []
    try:
        for p in productos_de_meta(meta):
            ficha = get_product_by_id(p["id"], tienda_id=tienda_id) or {}
            campos = {k: ficha.get(k) for k in
                      ("nombre", "categoria", "marca", "color", "material",
                       "origen", "uso_recomendado", "caracteristicas_extra",
                       "garantia_detalle", "contenido_caja", "descripcion")
                      if ficha.get(k)}
            if campos:
                partes.append("FICHA: " + json.dumps(campos, ensure_ascii=False))
    except Exception:
        pass
    for tc in (meta or {}).get("tools_called", []) or []:
        res = tc.get("result") or {}
        if tc.get("name") == "query_faq" and res.get("respuesta"):
            partes.append(f"FAQ {res.get('tema')}: {res['respuesta']}")
        if tc.get("name") == "consultar_guia_venta" and res.get("texto"):
            partes.append(f"CRITERIO JURADO {res.get('id')}: {res['texto']}")
    return "\n".join(partes)[:_MAX_EVIDENCIA]


def _prompt(respuesta: str, evidencia: str) -> str:
    return (
        "Sos el FISCAL de un bot de ventas. Abajo va la RESPUESTA que el bot "
        "quiere mandar y la EVIDENCIA real del sistema (fichas, FAQ, criterio "
        "jurado). Extrae de la respuesta cada AFIRMACION DE HECHO sobre "
        "productos o politicas (specs, material, origen, compatibilidad, "
        "garantia, servicios) y marca su veredicto:\n"
        "- respaldada: la evidencia la sostiene.\n"
        "- sin_respaldo: afirma algo que la evidencia NO dice.\n"
        "- neutral: opinion de venta, cortesia, pregunta o eco del cliente "
        "(no es un hecho chequeable).\n"
        "NO evalues precios ni numeros (otro sistema ya los verifico). Copia "
        "cada afirmacion TEXTUAL, tal cual aparece en la respuesta. Si no hay "
        "afirmaciones de hecho, devolve la lista vacia.\n\n"
        f"EVIDENCIA:\n{evidencia or '(sin evidencia este turno)'}\n\n"
        f"RESPUESTA:\n{respuesta}\n\n"
        "Devolve SOLO el JSON.")


async def chequear(respuesta: str, meta: dict, tienda_id: str | None = None,
                   trace_id: str | None = None) -> dict | None:
    """Corre el checker. Devuelve {'afirmaciones': [...], 'sin_respaldo': [...]}
    o None ante cualquier problema (el turno sigue igual)."""
    if not (respuesta or "").strip():
        return None
    evidencia = evidencia_de_meta(meta, tienda_id)
    prompt = _prompt(respuesta, evidencia)

    def _call():
        import os
        from openai import OpenAI
        key = (settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY") or "")
        key = key.split()[0] if key else ""
        if not key:
            return None
        c = OpenAI(api_key=key, base_url=settings.GEMINI_BASE_URL, timeout=_TIMEOUT_S)
        r = c.chat.completions.create(
            model=(settings.GEMINI_MODEL or "gemini-3.1-flash-lite"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0, max_tokens=600,
            extra_body={"reasoning_effort": "none"},
            response_format={"type": "json_schema", "json_schema": {
                "name": "fiscal", "strict": True, "schema": _SCHEMA}})
        return r.choices[0].message.content or ""
    try:
        raw = await asyncio.wait_for(asyncio.to_thread(_call), _TIMEOUT_S + 2)
        if not raw:
            return None
        data = json.loads(raw)
        afirmaciones = [a for a in data.get("afirmaciones", [])
                        if isinstance(a, dict) and a.get("texto")]
        sin_respaldo = [a["texto"] for a in afirmaciones
                        if a.get("veredicto") == "sin_respaldo"]
        return {"afirmaciones": afirmaciones, "sin_respaldo": sin_respaldo}
    except Exception as e:
        log.warning("checker_afirmaciones_error", trace_id=trace_id,
                    error=str(e)[:120])
        return None


_RE_DINERO_O_DIGITO = re.compile(r"[\d$]")


def podar_sin_respaldo(respuesta: str, sin_respaldo: list[str]) -> tuple[str, list[str]]:
    """Decision DETERMINISTA del codigo sobre el veredicto: poda la oracion
    solo cuando (a) la afirmacion aparece verbatim, (b) no trae digitos ni $
    (eso es del verificador de plata) y (c) queda respuesta en pie. Devuelve
    (texto, lista de lo efectivamente podado); lo no podable queda marcado en
    el log por el llamador."""
    texto = respuesta or ""
    podadas = []
    for afirmacion in sin_respaldo or []:
        a = str(afirmacion).strip()
        if not a or _RE_DINERO_O_DIGITO.search(a):
            continue
        if a not in texto:
            continue
        candidato = texto.replace(a, "").replace("  ", " ")
        candidato = re.sub(r"\n{3,}", "\n\n", candidato).strip(" .\n")
        if candidato:
            texto = candidato
            podadas.append(a)
    return (texto if podadas else respuesta), podadas
