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
# 8s: con el tope de 1400 tokens (respuesta_corregida incluida) los 4s
# originales cortaban la llamada y el turno quedaba sin fiscal (radar
# checker_afirmaciones_error con error vacio = TimeoutError, 20-jul).
_TIMEOUT_S = 8
# El tope subio dos veces el 29-jul, y las dos por el mismo motivo medido: cada
# vez que la evidencia se trunca, el juez juzga contra media verdad y poda
# contenido legitimo, que es peor que no tenerlo. Ahora entran las fichas
# COMPLETAS de los productos del turno mas el grounding de FAQ y de criterio.
# Son tokens de una llamada corta a flash-lite: la mas barata del sistema.
_MAX_EVIDENCIA = 14000

_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"afirmaciones": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "texto": {"type": "string"},
            "veredicto": {"type": "string",
                          "enum": ["respaldada", "sin_respaldo", "neutral"]},
        },
        "required": ["texto", "veredicto"]}},
        "respuesta_corregida": {"type": "string"}},
    "required": ["afirmaciones", "respuesta_corregida"]}


# Lo unico que NO viaja de la ficha: ruido interno que no dice nada del producto.
# TODO lo demas va, y esto es una regla, no una lista: al juez se le manda el
# REGISTRO COMPLETO, no un subconjunto curado.
_NO_VAN = {"_id", "created_at", "updated_at", "embedding", "tags",
           "descripcion_rica"}


def evidencia_de_meta(meta: dict, tienda_id: str | None = None) -> str:
    """Junta la evidencia REAL del turno: ficha COMPLETA de cada producto que
    las tools mostraron, respuestas de FAQ consultadas y bloques de prosa
    jurada citados. Es lo unico contra lo que se juzga la respuesta.

    LA FICHA VA ENTERA, y esta es la correccion mas importante de todo el
    fiscal. Antes viajaba un subconjunto curado de once campos: nombre,
    categoria, marca, color, material, origen, uso, caracteristicas, garantia,
    contenido de la caja y descripcion. Faltaba, entre otras cosas, el mapa
    `specs` que arma `fuente_producto` -almacenamiento, RAM, procesador,
    hercios- que es justo lo que el CODIGO estampa en la respuesta cuando el
    cliente pregunta una spec.

    Resultado medido en el banco del 29-jul, guion 68 turno 2: el codigo
    estampo "Memoria RAM: 4GB" y "Características: 128GB" desde la fuente, el
    juez no vio esos campos en su evidencia, los marco SIN RESPALDO y su
    reescritura los borro. Al cliente le llego "Tablet Samsung Galaxy Tab A9
    Gris. Tablet Lenovo Tab M10 Plata. Memoria RAM." -las etiquetas sin los
    valores-. O sea: el fiscal borrando la verdad que el propio codigo acababa
    de estampar de la fuente, que es la peor falla posible de este diseno.

    La leccion es general y vale para cualquier campo que se sume manana: al
    juez se le da el registro COMPLETO. Un juez con menos evidencia que el
    sistema que audita no detecta alucinacion, fabrica una."""
    from app.core.estado_venta import productos_de_meta
    from app.storage.firestore_client import get_product_by_id
    partes = []
    try:
        ids = [str(p["id"]).upper() for p in productos_de_meta(meta)
               if p.get("id")]
        # Los productos que el turno NOMBRO aunque no vengan de una tool: los
        # estampa el codigo desde la fuente igual (linea de producto, ficha,
        # spec honesta). Sin ellos el juez marcaba sin respaldo la linea
        # "Teclado Logitech K120 Blanco - $14.500 (22 en stock)", que la
        # escribio el CODIGO desde el catalogo (banco 29-jul).
        for pid in (meta or {}).get("productos_evidencia", []) or []:
            if str(pid).upper() not in ids:
                ids.append(str(pid).upper())
        for pid in ids[:12]:
            ficha = get_product_by_id(pid, tienda_id=tienda_id) or {}
            campos = {k: v for k, v in ficha.items()
                      if k not in _NO_VAN and v not in (None, "", [], {})}
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
    # Prosa de criterio RECUPERADA por el codigo (RAG) aunque el modelo no
    # eligiera llamar la tool: es fuente jurada del corpus igual, asi el
    # razonamiento fundado en ella NO se poda por "sin respaldo". Solo prosa
    # (cero digitos): los numeros los sigue gobernando el verificador de plata.
    for pr in (meta or {}).get("prosa_evidencia", []) or []:
        if isinstance(pr, dict) and pr.get("texto"):
            partes.append(f"CRITERIO JURADO {pr.get('id')}: {pr['texto']}")
    # FAQ que el CODIGO le paso al solver como grounding aunque el modelo no la
    # emitiera como fragmento. Misma razon que la de arriba: el juez tiene que
    # ver TODO lo que el solver vio, si no poda por ciego lo que estaba fundado.
    for fq in (meta or {}).get("faq_evidencia", []) or []:
        if isinstance(fq, dict) and fq.get("texto"):
            partes.append(f"FAQ {fq.get('tema')}: {fq['texto']}")
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
        "HONESTIDAD NO ES INVENTO: cuando el bot dice que algo NO lo tiene, "
        "NO lo vende, NO lo trabaja o NO lo tiene confirmado, eso es "
        "honestidad y va como neutral, salvo que la evidencia diga que SI lo "
        "tiene. NO evalues precios ni numeros (otro sistema ya los "
        "verifico). Copia cada afirmacion como ORACION COMPLETA, textual, "
        "tal cual aparece en la respuesta. Si no hay afirmaciones de hecho, "
        "devolve la lista vacia.\n"
        "Ademas devolve 'respuesta_corregida': la MISMA respuesta pero "
        "arreglando SOLO lo sin_respaldo. Sacá o reformulá con criterio lo que "
        "la evidencia no sostiene, SIN inventar nada nuevo, SIN agregar numeros, "
        "precios ni productos que no esten en la evidencia. Manté el tono de "
        "venta calido, el voseo y TODO lo respaldado y lo honesto. Copiá igual, "
        "sin tocar, cualquier linea que tenga numeros, precios o el presupuesto. "
        "Si la respuesta ya esta bien y no hay nada que corregir, devolve "
        "'respuesta_corregida' como cadena vacia.\n\n"
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
            temperature=0.0, max_tokens=1400,
            extra_body={"reasoning_effort": "none"},
            response_format={"type": "json_schema", "json_schema": {
                "name": "fiscal", "strict": True, "schema": _SCHEMA}})
        return r.choices[0].message.content or ""
    try:
        raw = await asyncio.wait_for(asyncio.to_thread(_call), _TIMEOUT_S + 2)
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # JSON cortado por el tope de tokens (3 veces en el banco 19/20
            # jul): se repara con el mismo cerrador del interpretador. Si ni
            # asi, no-op como siempre; el turno no queda sin fiscal por un
            # corte de la respuesta larga.
            from app.core.interpretador import _reparar_json_truncado
            data = _reparar_json_truncado(raw)
            if data is None:
                raise
            log.warning("checker_json_truncado_reparado", trace_id=trace_id)
        afirmaciones = [a for a in data.get("afirmaciones", [])
                        if isinstance(a, dict) and a.get("texto")]
        sin_respaldo = [a["texto"] for a in afirmaciones
                        if a.get("veredicto") == "sin_respaldo"]
        corregida = str(data.get("respuesta_corregida") or "").strip()
        # la evidencia vuelve con el veredicto: `rewrite_segura` la necesita
        # para saber que numero es de la fuente y por lo tanto intocable.
        return {"afirmaciones": afirmaciones, "sin_respaldo": sin_respaldo,
                "corregida": corregida, "evidencia": evidencia}
    except Exception as e:
        # El TIPO va siempre: un TimeoutError tiene str vacio y el radar
        # quedaba mudo sobre la causa (visto 20-jul).
        log.warning("checker_afirmaciones_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:100]}")
        return None


_RE_NUM = re.compile(r"\d+")


def rewrite_segura(original: str, corregida: str,
                   evidencia: str = "") -> str | None:
    """RED DE CODIGO sobre la reescritura del critico (manera 3). Acepta la
    version corregida SOLO si: no esta vacia ni es un muñon, no trae un
    marcador sin estampar, NO introduce ningun numero nuevo, y NO BORRA un
    numero que la EVIDENCIA respalda. Devuelve la corregida si es segura, None
    si hay que caer a la poda determinista.

    LAS DOS DIRECCIONES, y por que hacen falta las dos. Que no invente una
    cifra estuvo desde el principio. Que no BORRE una se agrego el 29-jul,
    despues de verlo en el banco: el codigo estampa "Memoria RAM: 4GB" desde la
    fuente y el reescritor lo saca, dejando "Memoria RAM." pelado. Un numero
    que esta en la evidencia NO es del reescritor: lo puso el codigo desde el
    catalogo. Solo puede sacar cifras que la fuente no respalda -por ejemplo
    "sumergible hasta 3 metros"-, que es exactamente lo que tiene que hacer."""
    c = (corregida or "").strip()
    if len(re.sub(r"\s", "", c)) < 15:
        return None
    if "[[" in c or "]]" in c:
        return None
    nums_orig = set(_RE_NUM.findall(original or ""))
    nums_new = set(_RE_NUM.findall(c))
    if nums_new - nums_orig:
        return None
    # lo que se borro y la fuente respalda: no era del reescritor, lo estampo
    # el codigo desde el catalogo.
    if evidencia:
        respaldados = set(_RE_NUM.findall(evidencia))
        if (nums_orig - nums_new) & respaldados:
            return None
    return c


_RE_DINERO_O_DIGITO = re.compile(r"[\d$]")

# Guardia de HONESTIDAD (17-jul, visto en la consigna): el modelo genera "no
# vendemos celulares" / "Cuota Simple no trabajamos" y el checker lo marcaba
# sin_respaldo (la evidencia no lo DICE) borrando la honestidad recien
# generada. Una negacion de oferta o un "no lo tengo confirmado" NUNCA se
# poda: es exactamente lo que queremos que el bot diga.
_RE_HONESTIDAD = re.compile(
    r"\bno\s+(?:lo\s+|la\s+|los\s+|las\s+|te\s+)?"
    r"(?:vendemos|vendo|trabajamos|tenemos|tengo|manejamos|ofrecemos|"
    r"ofrezco|aplicamos|aplico|hacemos|incluye|incluimos|puedo|podemos)\b"
    r"|no\s+(?:lo\s+)?(?:tengo|esta|está)\s+confirmad"
    r"|no\s+(?:me\s+)?figura|no\s+esta\s+especificad|no\s+está\s+especificad",
    re.IGNORECASE)

_RE_FIN_ORACION = re.compile(r"(?<=[.!?…])\s+|\n+")


def podar_sin_respaldo(respuesta: str, sin_respaldo: list[str]) -> tuple[str, list[str]]:
    """Decision DETERMINISTA del codigo sobre el veredicto: se poda SOLO una
    ORACION COMPLETA de la respuesta que coincida con la afirmacion (nunca un
    pedazo al medio: eso dejaba muñones tipo 'te cuento que , pero'), que no
    traiga digitos ni $ (territorio del verificador de plata) ni sea una
    frase de HONESTIDAD (negacion de oferta / no confirmado), y solo si queda
    respuesta en pie. Devuelve (texto, lista de lo efectivamente podado)."""
    texto = respuesta or ""
    reclamos = []
    for a in sin_respaldo or []:
        a = str(a).strip().strip('"')
        if a and not _RE_DINERO_O_DIGITO.search(a) and not _RE_HONESTIDAD.search(a):
            reclamos.append(a.rstrip(".!?… ").lower())
    if not reclamos:
        return respuesta, []
    podadas = []

    def _podable(oracion: str) -> bool:
        o = oracion.strip().rstrip(".!?… ").lower()
        if not o or _RE_DINERO_O_DIGITO.search(oracion) or _RE_HONESTIDAD.search(oracion):
            return False
        return any(o == r or (len(r) > 20 and r in o and len(o) - len(r) < 15)
                   for r in reclamos)

    lineas_out = []
    for linea in texto.split("\n"):
        oraciones = [s for s in _RE_FIN_ORACION.split(linea) if s is not None]
        keep = []
        for s in oraciones:
            if _podable(s):
                podadas.append(s.strip())
            else:
                keep.append(s)
        lineas_out.append(" ".join(k.strip() for k in keep if k.strip()))
    candidato = "\n".join(lineas_out)
    candidato = re.sub(r"\n{3,}", "\n\n", candidato).strip()
    if not podadas or not candidato:
        return respuesta, []
    return candidato, podadas
