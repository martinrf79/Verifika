"""
LIBRO DE ASIENTOS DE NUMEROS — Fase 2 de la "partida doble de la verdad".

Idea (cerrada con Martin): el Solver no solo escribe la prosa, ademas declara un
LIBRO con cada CIFRA DE DINERO que afirmo, como asientos {valor, fuente, que es}.
El codigo audita cada asiento contra la evidencia real del turno (partida doble):
  - cuadra con la fuente  -> aprobado, no se toca.
  - valor mal pero la verdad esta en su fuente -> el codigo lo REESCRIBE por el
    verdadero (corrige, no solo marca).
  - sin respaldo en ninguna fuente -> es una fuga: queda como problema y lo frena
    el piso duro (verificador determinista) que corre igual despues.

Por que el libro mejora a la autocorreccion de Fase 1: en Fase 1 el codigo tenia
que ADIVINAR que era cada numero (el total mas cercano). Aca cada cifra viene
ETIQUETADA con su fuente declarada, asi la correccion es precisa: un precio se
corrige contra el catalogo, un total contra la calculadora, un envio contra la
FAQ. Solo cubre NUMEROS/plata, la clase mas riesgosa (Fase 2 acotada).

Codigo puro, sin LLM. Detras del flag LIBRO_ASIENTOS (default off). Reusa los
helpers del verificador determinista para no duplicar la nocion de "numero real".
"""
import os
import re
from typing import Optional

from app.logger import get_logger
from app.core.verificador import (
    numeros_confiables,
    _totales_validos,
    _parse_num,
    _NUM_RE,
    _es_monto,
    _fmt_ar,
    _TOLERANCIA,
    _MIN_MONETARIO,
    _MAX_CANTIDAD,
)

log = get_logger(__name__)

# ────────────────────────────────────────────────────────────
# SINK DE DIAGNOSTICO (solo para el molino / pruebas, off en prod)
# ────────────────────────────────────────────────────────────
# El molino silencia los log.info, asi que la telemetria del libro (si el Solver
# lo emitio, cuanto corrigio, que fugas vio la guarda) no se ve. Con DIAG_LIBRO=true
# el orchestrator acumula esos datos por key (user_id) en un dict de modulo, y el
# molino los lee despues de cada respuesta y los vuelca al reporte. En prod el flag
# esta off: diag_record es un no-op y el dict queda vacio, sin costo ni memoria.
DIAG: dict = {}


def diag_record(key: Optional[str], **kv) -> None:
    """Acumula datos de diagnostico bajo key. No-op si DIAG_LIBRO no esta on."""
    if not key or os.getenv("DIAG_LIBRO", "false").lower() != "true":
        return
    DIAG.setdefault(key, {}).update(kv)


def diag_pop(key: str) -> dict:
    """Devuelve y limpia el diagnostico acumulado para key."""
    return DIAG.pop(key, {})


# Banda de error plausible para aceptar una correccion: la verdad tiene que estar
# a <=15% de la cifra mala. Un error de suma o de envio cae cerca; un numero
# inventado de la nada no, y ese lo frena el piso duro, no lo "corrige" el libro.
_BANDA = 0.15

# Vocabulario CERRADO de fuentes. El Solver no puede inventar otras; si declara una
# desconocida, se trata como sin fuente fiable (se valida contra todo el universo).
_FUENTES = ("calculo", "catalogo", "faq")

# Fragmento que se suma al prompt del Solver cuando el flag esta on. Le pide emitir
# el libro al final, con formato fijo y fuente de un set cerrado. El bloque es para
# control interno: el codigo lo extrae y lo saca antes de mostrar nada al cliente.
PROMPT_LIBRO = """

═══ LIBRO DE ASIENTOS — OBLIGATORIO AL FINAL ═══
Despues de tu respuesta al cliente, agrega SIEMPRE un bloque que liste cada CIFRA DE DINERO que mencionaste, una por linea, con este formato EXACTO:
[[LIBRO]]
<numero> | <fuente> | <que es>
[[/LIBRO]]
Reglas del bloque:
- <numero> va sin puntos ni signo peso: 255000, no $255.000.
- <fuente> es UNA sola de estas tres palabras: calculo (vino de calculate_total o find_within_budget), catalogo (es el precio de un producto), faq (es un costo de la FAQ como envio).
- <que es> es una descripcion corta, por ejemplo total con envio o precio del mouse.
- Lista TODA cifra de dinero que dijiste, sin excepcion. Si no dijiste ninguna, deja el bloque vacio igual.
- Es control interno: el cliente NO ve este bloque. No lo menciones en tu respuesta."""

_BLOQUE_RE = re.compile(r"\[\[\s*LIBRO\s*\]\](.*?)\[\[\s*/\s*LIBRO\s*\]\]",
                        re.IGNORECASE | re.DOTALL)
# Por si el modelo abre el bloque y no lo cierra: limpiamos cualquier resto.
_APERTURA_RE = re.compile(r"\[\[\s*/?\s*LIBRO\s*\]\].*", re.IGNORECASE | re.DOTALL)


def parsear_libro(texto: str) -> tuple:
    """Extrae el libro de asientos del texto crudo del Solver.

    Devuelve (prosa_sin_libro, asientos, hubo_libro):
      - prosa_sin_libro: el texto para el cliente, con el bloque del libro quitado.
      - asientos: lista de {valor:int, fuente:str, afirmacion:str}.
      - hubo_libro: bool, si aparecio el bloque (aunque venga vacio).

    Tolerante: si el bloque no aparece, devuelve el texto intacto y asientos vacio.
    Si aparece abierto sin cerrar, igual saca todo lo que cuelga para no filtrarlo.
    """
    if not texto:
        return texto, [], False

    m = _BLOQUE_RE.search(texto)
    if not m:
        # Sin bloque bien formado. Si quedo una apertura suelta, la barremos.
        if _APERTURA_RE.search(texto):
            prosa = _APERTURA_RE.sub("", texto).strip()
            return prosa, [], False
        return texto, [], False

    cuerpo = m.group(1)
    prosa = (texto[:m.start()] + texto[m.end():]).strip()

    asientos: list[dict] = []
    for linea in cuerpo.splitlines():
        linea = linea.strip()
        if not linea or "|" not in linea:
            continue
        partes = [p.strip() for p in linea.split("|")]
        valor = _parse_num(partes[0])
        if valor is None:
            continue
        fuente = (partes[1].lower() if len(partes) > 1 else "")
        if fuente not in _FUENTES:
            fuente = "?"
        afirmacion = partes[2] if len(partes) > 2 else ""
        asientos.append({"valor": valor, "fuente": fuente,
                         "afirmacion": afirmacion})
    return prosa, asientos, True


def _sets_por_fuente(evidence: list[dict]) -> dict:
    """Arma el set de numeros verdaderos POR fuente, para corregir con precision:
    calculo -> totales/resultados de la calculadora; catalogo -> precios de
    producto y sus multiplos por cantidad; faq -> numeros de la FAQ."""
    calc: set[int] = set(_totales_validos(evidence))
    catalogo: set[int] = set()
    faq: set[int] = set()

    for item in evidence or []:
        tipo = item.get("tipo")
        if tipo == "producto":
            p = item.get("precio_ars")
            if isinstance(p, (int, float)):
                pi = int(p)
                for q in range(1, _MAX_CANTIDAD + 1):
                    catalogo.add(pi * q)
        elif tipo == "proof":
            proof = item.get("proof", {}) or {}
            for k in ("resultado", "resultado_min", "resultado_max",
                      "subtotal_productos"):
                v = proof.get(k)
                if isinstance(v, (int, float)):
                    calc.add(int(v))
            for v in proof.get("valores", []) or []:
                if isinstance(v, (int, float)):
                    calc.add(int(v))
        elif tipo == "faq":
            for v in item.get("valores", []) or []:
                for k in ("monto", "monto_min", "monto_max",
                          "monto_calculado_ars", "base_ars"):
                    x = v.get(k)
                    if isinstance(x, (int, float)):
                        faq.add(int(x))
            for tok in _NUM_RE.findall(str(item.get("respuesta", "") or "")):
                n = _parse_num(tok)
                if n is not None and n >= _MIN_MONETARIO:
                    faq.add(n)
    return {"calculo": calc, "catalogo": catalogo, "faq": faq}


def _respaldado(n: int, nums: set, rangos: list) -> bool:
    """True si n cuadra contra algun numero real de la evidencia (igual criterio
    que el verificador determinista: exacto, dentro de un rango, o por tolerancia)."""
    if n in nums:
        return True
    for lo, hi in rangos:
        if lo <= n <= hi:
            return True
    for t in nums:
        if abs(n - t) <= _TOLERANCIA:
            return True
    return False


def _mas_cercano_unico(n: int, candidatos: set) -> Optional[int]:
    """Devuelve el candidato mas cercano a n SOLO si es unico (sin empate de
    distancia) y el error es plausible (<=15%). Si no, None."""
    if not candidatos:
        return None
    ordenados = sorted(candidatos, key=lambda r: abs(r - n))
    r = ordenados[0]
    if r == n or abs(r - n) > _BANDA * n:
        return None
    if len(ordenados) > 1 and abs(ordenados[1] - n) == abs(r - n):
        return None
    return r


def auditar_libro(asientos: list[dict],
                  evidence: list[dict],
                  trace_id: Optional[str] = None,
                  precios_validos: Optional[set] = None) -> dict:
    """Audita cada asiento numerico contra la evidencia (partida doble).

    Devuelve:
      {
        "ok": bool,                  # True si ningun asiento quedo sin respaldo
        "correcciones": [{de,a,fuente,afirmacion}],  # reescrituras a aplicar
        "problemas": [asiento, ...], # asientos sin respaldo ni correccion posible
        "total": int,                # cantidad de asientos auditados
      }

    No toca prosa: solo decide. Aplicar las correcciones con aplicar_correcciones.
    El piso duro (verificador determinista) corre IGUAL despues, asi que un
    problema no corregible no se escapa: lo frena el gate.
    """
    nums, rangos = numeros_confiables(evidence)
    sets = _sets_por_fuente(evidence)

    correcciones: list[dict] = []
    problemas: list[dict] = []
    for a in asientos:
        v = a.get("valor")
        if not isinstance(v, int):
            continue
        if _respaldado(v, nums, rangos):
            continue  # el asiento cuadra contra una fuente real
        # NUNCA pisar un numero que sea un precio real de catalogo: que no este en
        # la evidencia de ESTE turno no lo hace falso, puede venir de un producto
        # citado de un turno anterior (en multiturno el bot cita precios de memoria
        # sin re-buscar). Corregirlo lo corromperia con el precio mas cercano de
        # otro producto (caso Corsair 20000->17000). Se trata como respaldado.
        if precios_validos and v in precios_validos:
            continue
        # No respaldado: buscar la verdad en su fuente declarada; si la fuente es
        # desconocida ("?"), probar contra todo el universo de numeros reales.
        f = a.get("fuente", "?")
        universo = sets.get(f) if f in _FUENTES else (nums | set().union(*sets.values()))
        cand = _mas_cercano_unico(v, universo or set())
        if cand is not None:
            correcciones.append({"de": v, "a": cand, "fuente": f,
                                 "afirmacion": a.get("afirmacion", "")})
        else:
            problemas.append(a)

    ok = len(problemas) == 0
    log.info("auditar_libro", trace_id=trace_id, total=len(asientos),
             correcciones=correcciones[:10], problemas=[p.get("valor") for p in problemas][:10])
    return {"ok": ok, "correcciones": correcciones, "problemas": problemas,
            "total": len(asientos)}


def _suma_alcanzable(n: int, atomos: list, tol: int) -> bool:
    """True si n se puede formar sumando algunos de los atomos (cada uno una vez),
    dentro de la tolerancia. Cubre la aritmetica obvia que el Solver hace de cabeza
    (subtotal = suma de lineas) sin tener que declarar cada parcial en el libro."""
    alcanzables = {0}
    for a in atomos:
        alcanzables |= {r + a for r in set(alcanzables) if r + a <= n + tol}
    return any(abs(n - r) <= tol for r in alcanzables if r > 0)


def guarda_completitud(prosa: str,
                       libro_aprob: list[dict],
                       evidence: Optional[list[dict]] = None,
                       trace_id: Optional[str] = None) -> dict:
    """GUARDA DE COMPLETITUD (Fase 4): red anti-Solver. Extrae cada cifra de dinero
    de la prosa final y exige que pase por el libro aprobado. El libro es el UNICO
    canal de hechos de plata: un numero que aparece en el texto y no esta en el
    libro (ni es suma de sus valores) es una FUGA, aunque exista en la evidencia.

    Devuelve:
      {
        "ok": bool,                       # True si no hay fugas
        "fugas": [{valor, en_evidencia}], # cifras del texto fuera del libro
        "total_montos": int,
      }

    Clasifica cada fuga con en_evidencia: True = numero real que el Solver no
    declaro (contrabando, ej. cajon equivocado); False = inventado. Util para
    medir en shadow si conviene bloquear o todavia hay libros incompletos.
    """
    aprob = sorted({int(a["valor"]) for a in (libro_aprob or [])
                    if isinstance(a.get("valor"), (int, float))})

    # Montos de la prosa, mismo criterio que el verificador determinista.
    montos: list[int] = []
    for m in _NUM_RE.finditer(prosa or ""):
        if not _es_monto(prosa, m):
            continue
        n = _parse_num(m.group())
        if n is None or n < _MIN_MONETARIO:
            continue
        montos.append(n)

    # Para clasificar la fuga (en_evidencia) usamos el MISMO criterio que el
    # verificador de plata: numeros de la evidencia MAS la aritmetica de catalogo
    # (precio x cantidad). Asi un total legitimo como 2x214.000 no se marca como
    # "invento" cuando en realidad es un numero real que el Solver no declaro.
    if evidence:
        nums_ev, rangos_ev = numeros_confiables(evidence)
        nums_ev = nums_ev | _sets_por_fuente(evidence)["catalogo"]
    else:
        nums_ev, rangos_ev = set(), []

    fugas: list[dict] = []
    for n in montos:
        # Respaldado por el libro: figura como asiento (tolerancia) o es suma de
        # asientos (aritmetica obvia que no hace falta declarar parcial por parcial).
        if any(abs(n - v) <= _TOLERANCIA for v in aprob):
            continue
        if _suma_alcanzable(n, aprob, _TOLERANCIA):
            continue
        fugas.append({"valor": n,
                      "en_evidencia": _respaldado(n, nums_ev, rangos_ev)})

    ok = len(fugas) == 0
    log.info("guarda_completitud", trace_id=trace_id, ok=ok,
             total_montos=len(montos), fugas=fugas[:10])
    return {"ok": ok, "fugas": fugas, "total_montos": len(montos)}


def libro_aprobado(asientos: list[dict], auditoria: dict) -> list[dict]:
    """Devuelve el libro APROBADO para atar el render (Fase 3): los asientos con
    las correcciones ya aplicadas y SIN las fugas (los problemas sin respaldo, que
    no son verdad y no deben presentarse como tal). Cada item {valor, fuente,
    afirmacion} es una cifra de plata confiable que el corrector debe usar tal cual."""
    correg = {c["de"]: c["a"] for c in (auditoria.get("correcciones") or [])}
    fugas = {id(p) for p in (auditoria.get("problemas") or [])}
    aprobado: list[dict] = []
    for a in asientos:
        if id(a) in fugas:
            continue
        v = a.get("valor")
        aprobado.append({
            "valor": correg.get(v, v),
            "fuente": a.get("fuente", "?"),
            "afirmacion": a.get("afirmacion", ""),
        })
    return aprobado


def aplicar_correcciones(prosa: str, correcciones: list[dict],
                         trace_id: Optional[str] = None) -> dict:
    """Reescribe en la prosa cada cifra mala por la verdadera, segun las
    correcciones del auditor. Reemplaza solo cifras de dinero (mismo criterio de
    monto del verificador) cuyo valor coincida con un 'de'. Devuelve {respuesta,
    cambiada, aplicadas}."""
    if not correcciones or not prosa:
        return {"respuesta": prosa, "cambiada": False, "aplicadas": []}

    mapa = {c["de"]: c["a"] for c in correcciones if c["de"] != c["a"]}
    if not mapa:
        return {"respuesta": prosa, "cambiada": False, "aplicadas": []}

    reemplazos: list[tuple] = []  # (start, end, token_nuevo, de, a)
    for m in _NUM_RE.finditer(prosa):
        if not _es_monto(prosa, m):
            continue
        n = _parse_num(m.group())
        if n in mapa:
            reemplazos.append((m.start(), m.end(), _fmt_ar(mapa[n]), n, mapa[n]))

    if not reemplazos:
        return {"respuesta": prosa, "cambiada": False, "aplicadas": []}

    nuevo = prosa
    aplicadas = []
    for start, end, token, de, a in sorted(reemplazos, key=lambda x: x[0],
                                           reverse=True):
        nuevo = nuevo[:start] + token + nuevo[end:]
        aplicadas.append({"de": de, "a": a})
    log.info("aplicar_correcciones", trace_id=trace_id, aplicadas=aplicadas[:10])
    return {"respuesta": nuevo, "cambiada": True, "aplicadas": aplicadas}
