"""
VERIFICADOR DE FAQ NUMERICA — los numeros CHICOS de politica que la plata no mira.

El verificador de plata cubre montos de dinero. Pero una politica mal parafraseada
miente igual con numeros chicos: "25% de descuento" (es 20%), "24 cuotas" (son 6),
"45 dias" (son 2 a 7), "36 meses de garantia" (son 24). Este modulo aplica el
MISMO patron por campo, con clases ancladas a la UNIDAD:

  porcentaje  EXACTO   un % es un valor puntual de la politica.
  meses       EXACTO   la garantia es la que es.
  cuotas      RANGO    "hasta 6 cuotas" habilita cualquier N <= 6.
  dias        RANGO    "de 2 a 7 dias" habilita cualquier N en el rango.
  horas       RANGO    horarios ("de 9 a 18 hs").

El pool de verdad por clase sale de lo ESTRUCTURADO y de la prosa de la FAQ (la
prosa aca SI respalda: el numero de la politica vive en su texto cargado por la
tienda, no es texto del modelo) mas el catalogo (garantia_meses).

Correccion (safe-override) SOLO anclada al tema consultado este turno: si
query_faq trajo un tema y su pool de esa clase tiene UN unico valor, la cifra
mala se reescribe por la buena (edicion minima). Sin ancla o con pool ambiguo,
se marca para el log y no se toca (mismo criterio conservador que la plata).
"""
import re

from app.logger import get_logger

log = get_logger(__name__)

# Clases de numero con unidad. El nombre de grupo 1 es siempre la cifra.
_CLASES: dict[str, re.Pattern] = {
    "porcentaje": re.compile(r"(\d{1,2})\s*(?:%|por\s?ciento)", re.IGNORECASE),
    "cuotas": re.compile(r"(\d{1,3})\s+cuotas?\b", re.IGNORECASE),
    "dias": re.compile(r"(\d{1,3})\s+d[ií]as?\b", re.IGNORECASE),
    "meses": re.compile(r"(\d{1,3})\s+mes(?:es)?\b", re.IGNORECASE),
    "horas": re.compile(r"(\d{1,2})\s*(?:hs\b|horas?\b)", re.IGNORECASE),
}

# Semantica del respaldo por clase: exacta (el valor tiene que estar en el pool)
# o de rango (cualquier N entre el minimo y el maximo del pool vale, porque la
# politica dice "hasta X" o "de A a B" y ofrecer menos es legitimo).
_EXACTAS = {"porcentaje", "meses"}

# Unidad declarada en un valor estructurado de FAQ -> clase de este verificador.
_UNIDAD_A_CLASE = {"porcentaje": "porcentaje", "cuotas": "cuotas",
                   "cuota": "cuotas", "dias": "dias", "dia": "dias",
                   "meses": "meses", "mes": "meses"}


# Rango escrito en prosa: "de 2 a 7 dias", "entre 6 y 12 cuotas", "9 a 18 hs".
# Solo para el POOL de verdad (la prosa de la FAQ): sin esto el piso del rango
# no se captura (el "2" de "2 a 7 dias" no va seguido de la unidad) y un plazo
# legitimo dentro del rango caeria como sin respaldo.
_UNIDAD_PAT = {
    "porcentaje": r"\s*(?:%|por\s?ciento)",
    "cuotas": r"\s+cuotas?\b",
    "dias": r"\s+d[ií]as?\b",
    "meses": r"\s+mes(?:es)?\b",
    "horas": r"\s*(?:hs\b|horas?\b)",
}
_RANGOS = {
    clase: re.compile(rf"(\d{{1,3}})\s*(?:a|y|o|hasta)\s*(\d{{1,3}}){pat}",
                      re.IGNORECASE)
    for clase, pat in _UNIDAD_PAT.items()
}


def _numeros_de_texto(texto: str, clase: str) -> set[int]:
    nums = {int(m.group(1)) for m in _CLASES[clase].finditer(texto or "")}
    for m in _RANGOS[clase].finditer(texto or ""):
        nums.add(int(m.group(1)))
        nums.add(int(m.group(2)))
    return nums


def _pool_de_evidencia(evidencia: list[dict],
                       temas: set[str] | None = None) -> dict[str, set[int]]:
    """Pool de numeros verdaderos por clase. Si temas viene, SOLO esos temas de
    FAQ aportan (ancla del turno); si no, aporta toda la FAQ y el catalogo."""
    pool: dict[str, set[int]] = {c: set() for c in _CLASES}
    for item in evidencia or []:
        tipo = item.get("tipo")
        if tipo == "faq":
            if temas is not None and str(item.get("tema") or item.get("id") or "") not in temas:
                continue
            for clase in _CLASES:
                pool[clase] |= _numeros_de_texto(item.get("respuesta", ""), clase)
            for v in item.get("valores", []) or []:
                unidad = str(v.get("unidad") or "").strip().lower()
                clase = _UNIDAD_A_CLASE.get(unidad)
                if clase in pool and isinstance(v.get("monto"), (int, float)):
                    pool[clase].add(int(v["monto"]))
                for clase_c in _CLASES:
                    pool[clase_c] |= _numeros_de_texto(
                        str(v.get("condicion", "")), clase_c)
        elif tipo == "producto" and temas is None:
            g = item.get("garantia_meses")
            if isinstance(g, (int, float)) and int(g) > 0:
                pool["meses"].add(int(g))
    return pool


def _respaldado(n: int, clase: str, pool: dict[str, set[int]]) -> bool:
    vals = pool.get(clase) or set()
    if not vals:
        # Sin dato de esa clase en la fuente no se puede juzgar: no se acusa.
        return True
    if clase in _EXACTAS:
        return n in vals
    if clase == "cuotas":
        # "hasta X cuotas": ofrecer menos cuotas que el tope es legitimo.
        return n <= max(vals)
    return min(vals) <= n <= max(vals)


def verificar_faq_numerica(respuesta: str, evidencia: list[dict]) -> dict:
    """Chequea cada numero con unidad de clase contra el pool GLOBAL (toda la FAQ
    + catalogo). Devuelve {"ok": bool, "sin_respaldo": [{clase, n}]}."""
    pool = _pool_de_evidencia(evidencia)
    sin_respaldo: list[dict] = []
    for clase, rx in _CLASES.items():
        for m in rx.finditer(respuesta or ""):
            n = int(m.group(1))
            if not _respaldado(n, clase, pool):
                d = {"clase": clase, "n": n}
                if d not in sin_respaldo:
                    sin_respaldo.append(d)
    return {"ok": not sin_respaldo, "sin_respaldo": sin_respaldo}


def autocorregir_faq_numerica(respuesta: str, evidencia: list[dict],
                              temas_consultados: set[str] | None = None,
                              trace_id: str | None = None) -> dict:
    """Safe-override anclado al tema: corrige una cifra de clase sin respaldo
    SOLO si este turno se consulto la FAQ (query_faq) y el pool de esa clase en
    LOS TEMAS CONSULTADOS tiene un unico valor. Devuelve el mismo contrato que
    autocorregir_montos: {cambiada, respuesta, correcciones, verificacion}."""
    base = verificar_faq_numerica(respuesta, evidencia)
    if base["ok"] or not temas_consultados:
        return {"cambiada": False, "respuesta": respuesta,
                "correcciones": [], "verificacion": base}

    pool_ancla = _pool_de_evidencia(evidencia, temas=set(temas_consultados))
    malos = {(d["clase"], d["n"]) for d in base["sin_respaldo"]}
    reemplazos: list[tuple] = []
    correcciones: list[dict] = []
    for clase, rx in _CLASES.items():
        candidatos = pool_ancla.get(clase) or set()
        if len(candidatos) != 1:
            continue
        bueno = next(iter(candidatos))
        for m in rx.finditer(respuesta or ""):
            n = int(m.group(1))
            if (clase, n) not in malos or n == bueno:
                continue
            s, e = m.span(1)
            reemplazos.append((s, e, str(bueno)))
            correcciones.append({"de": n, "a": bueno, "concepto": clase})
    if not reemplazos:
        return {"cambiada": False, "respuesta": respuesta,
                "correcciones": [], "verificacion": base}
    nuevo = respuesta
    for s, e, token in sorted(reemplazos, reverse=True):
        nuevo = nuevo[:s] + token + nuevo[e:]
    verif2 = verificar_faq_numerica(nuevo, evidencia)
    log.info("autocorrige_faq_numerica", trace_id=trace_id,
             correcciones=correcciones[:8], quedo_ok=verif2["ok"])
    return {"cambiada": True, "respuesta": nuevo,
            "correcciones": correcciones, "verificacion": verif2}


def temas_de_meta(meta: dict) -> set[str]:
    """Temas de FAQ consultados este turno (query_faq): el principal + las
    relacionadas. Es el ancla para la correccion."""
    temas: set[str] = set()
    for tc in (meta or {}).get("tools_called", []) or []:
        if tc.get("name") != "query_faq":
            continue
        res = tc.get("result")
        if not isinstance(res, dict) or not res.get("encontrada"):
            continue
        if res.get("tema"):
            temas.add(str(res["tema"]))
        for rel in res.get("relacionadas", []) or []:
            t = (rel or {}).get("tema")
            if t:
                temas.add(str(t))
    return temas
