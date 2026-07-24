"""
DESTINO_RESOLVER — resolución centralizada de destinos de envío.

Las tres fuentes de verdad del flujo de envíos son completamente distintas
y no deben mezclarse:

1.  geo_cp / tabla de envíos
    Fuente de verdad de EXISTENCIA y CANONIZACIÓN de localidades y provincias.
    Certifica que el lugar geográfico es real y devuelve su forma canónica y
    slug de provincia.  No certifica que el cliente lo haya pedido.

2.  Memoria conversacional (estado["localidades_envio"], estado["provincia_envio"],
    estado["grupos_envio"])
    Certifica que el CLIENTE declaró o mantuvo esos destinos en algún turno
    anterior de esta conversación.  Un destino de memoria es válido aunque
    no reaparezca en el mensaje actual.

3.  Estado de cotización / proofs  (get_envio_localidades(), tarifas y proofs)
    Certifica qué destinos ya fueron cotizados y con qué tarifa en el turno
    actual.  Sirve para reusar tarifas y proofs; NO como fuente de identidad
    de qué destinos existen.

Invariante central
──────────────────
    geo_cp certifica que el lugar EXISTE.
    El mensaje o la memoria certifican que el CLIENTE lo pidió.
    Un lugar real de geo_cp que nunca fue declarado por el cliente NO se acepta.

Estados de resolución (EstadoDestino)
─────────────────────────────────────
    validado_nuevo   — declarado en el mensaje actual Y encontrado/canonizado
                       por geo_cp.
    validado_memoria — no aparece en el mensaje actual pero coincide con un
                       destino activo persistido en memoria conversacional.
    ambiguo          — el texto aparece en el mensaje y geo_cp lo reconoce como
                       lugar real, pero es ambiguo entre varias provincias y
                       requiere aclaración antes de cotizar.
    no_respaldado    — geo_cp reconoce el lugar pero el cliente nunca lo declaró
                       (no está en el mensaje ni en la memoria).  Se rechaza.
    no_encontrado    — geo_cp no reconoce el texto como ningún lugar real.
                       Se rechaza.

Uso típico
──────────
    from app.core.destino_resolver import resolver_destino
    res = resolver_destino(
        texto="Monte Ralo",
        mensaje_actual=raw_message,
        memoria_destinos=estado.get("localidades_envio") or [],
        provincia_sticky=estado.get("provincia_envio") or "",
    )
    if res["estado"] in ("validado_nuevo", "validado_memoria", "ambiguo"):
        # El destino es legítimo; continuar.
        loc = res["localidad_canonica"]
        prov = res["provincia"]
    else:
        # Destino fantasma; descartar.
        ...
"""

import re
import unicodedata
from typing import Literal

from app.logger import get_logger

log = get_logger(__name__)

EstadoDestino = Literal[
    "validado_nuevo",
    "validado_memoria",
    "ambiguo",
    "no_respaldado",
    "no_encontrado",
]

# Estados que representan un destino legítimo (declarado por el cliente).
ESTADOS_VALIDOS = frozenset({"validado_nuevo", "validado_memoria", "ambiguo"})

# Estados que representan un destino fantasma (rechazar).
ESTADOS_FANTASMA = frozenset({"no_respaldado", "no_encontrado"})


def _norm(s: str) -> str:
    """Normaliza para comparación: minúsculas, sin tildes, sin puntuación, sin
    espacios dobles.  Compatible con la normalización interna de geo_cp."""
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _en_texto(texto_norm: str, candidato_norm: str) -> bool:
    """True si candidato aparece como substring o como subconjunto de palabras
    en texto.  Tolera espaciado y variantes menores."""
    if not candidato_norm or not texto_norm:
        return False
    if candidato_norm in texto_norm:
        return True
    pd = set(candidato_norm.split())
    pm = set(texto_norm.split())
    return bool(pd) and pd <= pm


def _en_memoria(candidato_norm: str, mem_norms: list) -> bool:
    """True si candidato coincide (por subconjunto de palabras) con algún
    destino de la memoria conversacional.  Tolera tildes y separadores porque
    tanto candidato como memoria ya están normalizados con _norm()."""
    if not candidato_norm:
        return False
    pd = set(candidato_norm.split())
    for mv in mem_norms:
        pm = set(mv.split())
        if pd and pm and (pd <= pm or pm <= pd):
            return True
    return False


def _resultado(
    estado: str,
    loc: "str | None",
    prov: "str | None",
    original: str,
) -> dict:
    return {
        "estado": estado,
        "localidad_canonica": loc,
        "provincia": prov,
        "texto_original": original,
    }


def resolver_destino(
    texto: str,
    mensaje_actual: str,
    memoria_destinos: list,
    provincia_sticky: str = "",
) -> dict:
    """Resuelve un destino de envío contra las tres fuentes de verdad.

    Parámetros
    ----------
    texto           : texto del destino a resolver (puede tener tildes,
                      comas, etc.).  Proviene del campo ``destino`` de un
                      ítem del pedido interpretado.
    mensaje_actual  : mensaje del cliente en el turno actual (raw o levemente
                      normalizado; la función aplica su propia normalización).
    memoria_destinos: lista de localidades activas declaradas en turnos
                      anteriores (viene de ``estado["localidades_envio"]``).
    provincia_sticky: provincia que el cliente fijó en la conversación
                      (viene de ``estado["provincia_envio"]``).  Se usa para
                      desambiguar localidades que existen en varias provincias.

    Devuelve
    --------
    dict con las claves:
        estado           — EstadoDestino
        localidad_canonica — forma normalizada de la localidad en la tabla
                             geo_cp, o None si no se pudo resolver.
        provincia        — slug de provincia (p. ej. "cordoba", "jujuy"),
                           o None si no se pudo determinar.
        texto_original   — texto recibido sin modificar.

    La regla fundamental es: geo_cp certifica que el lugar existe; el mensaje
    o la memoria del estado certifican que el cliente lo pidió.  Un destino
    real en geo_cp que el cliente nunca declaró devuelve "no_respaldado".
    """
    from app.core import geo_cp as _geo
    _geo._cargar()

    texto_original = str(texto or "").strip()
    if not texto_original:
        return _resultado("no_encontrado", None, None, "")

    t_norm = _norm(texto_original)
    m_norm = _norm(mensaje_actual or "")
    mem_norms = [_norm(x) for x in (memoria_destinos or []) if x]
    prov_sticky_norm = _norm(provincia_sticky or "")

    # ── Paso 1: canonizar con geo_cp (enriquecimiento, no compuerta) ──────────
    # geo_cp provee la forma canónica y la provincia; no rechaza destinos
    # declarados por el cliente aunque la tabla no los conozca exactamente.
    prov_en_texto = _geo._provincia_en_texto(t_norm)
    _, hits = _geo._localidades_en_texto(t_norm)

    loc_canon: "str | None" = None
    prov_canon: "str | None" = None
    es_ambiguo = False

    if prov_en_texto:
        prov_canon = prov_en_texto
        for loc, ini, fin in hits:
            if prov_en_texto in _geo._LOC.get(loc, {}):
                loc_canon = loc
                break
        # Solo provincia en el texto (sin localidad específica): válida para cotizar.
    elif hits:
        loc0 = hits[0][0]
        provs = _geo._LOC.get(loc0, {})
        if len(provs) == 1:
            loc_canon = loc0
            prov_canon = next(iter(provs))
        elif len(provs) > 1:
            loc_canon = loc0
            es_ambiguo = True

    # Intentar resolver ambigüedad con la provincia sticky de la conversación.
    if es_ambiguo and prov_sticky_norm:
        prov_desde_sticky = _geo._provincia_en_texto(prov_sticky_norm)
        if prov_desde_sticky and prov_desde_sticky in _geo._LOC.get(loc_canon or "", {}):
            prov_canon = prov_desde_sticky
            es_ambiguo = False

    geo_reconoce = bool(prov_canon or loc_canon or es_ambiguo)

    # ── Paso 2: ¿está en el mensaje actual? ──────────────────────────────────
    # Un destino declarado por el cliente en este turno es válido aunque geo_cp
    # no lo conozca exactamente (p. ej. "Carlos Paz" vs "Villa Carlos Paz").
    en_msg = _en_texto(m_norm, t_norm)
    if not en_msg and loc_canon:
        # Verificar también con la forma canónica: el intérprete pudo agregar
        # la provincia al texto del destino; lo que importa es que la
        # localidad base aparezca en el mensaje del cliente.
        en_msg = _en_texto(m_norm, _norm(loc_canon))

    if en_msg:
        if es_ambiguo:
            return _resultado("ambiguo", loc_canon, prov_canon, texto_original)
        return _resultado("validado_nuevo", loc_canon, prov_canon, texto_original)

    # ── Paso 3: ¿está en la memoria conversacional? ──────────────────────────
    # La provincia sticky también es memoria declarada por el cliente (la fijó
    # en algún turno anterior); se incluye en los checks de subconjunto.
    effective_mem = list(mem_norms)
    if prov_sticky_norm and prov_sticky_norm not in effective_mem:
        effective_mem.append(prov_sticky_norm)

    checks = [t_norm]
    if loc_canon:
        checks.append(_norm(loc_canon))

    for cn in checks:
        if _en_memoria(cn, effective_mem):
            return _resultado("validado_memoria", loc_canon, prov_canon, texto_original)

    # ── Paso 4: lugar no declarado — rechazar ────────────────────────────────
    # Distinguimos entre "lugar real de geo_cp que el cliente nunca declaró"
    # (no_respaldado) y "texto que no es ningún lugar conocido" (no_encontrado).
    # Ambos estados son FANTASMA y el llamador debe anular el destino.
    if not geo_reconoce:
        return _resultado("no_encontrado", None, None, texto_original)
    return _resultado("no_respaldado", loc_canon, prov_canon, texto_original)


def es_destino_valido(resultado_resolver: dict) -> bool:
    """Conveniencia: True si el estado de resolver_destino es legítimo
    (el destino fue declarado por el cliente en algún punto)."""
    return resultado_resolver.get("estado") in ESTADOS_VALIDOS
