"""
VERIFICADOR DETERMINISTA — linea cero de la anti alucinacion.

La decision final de mandar o no la respuesta la toma el CODIGO, no un modelo.
A diferencia del Checker de Verifika, que es un LLM juzgando a otro LLM y por eso
es no determinista y se equivoca, este verificador es codigo puro:

- Escanea la respuesta y junta cada cifra de dinero.
- Exige que cada cifra salga de una fuente real: un precio del catalogo, un valor
  o un numero del texto de la FAQ, o un PROOF de la calculadora (de este turno o
  de turnos recientes guardados en memoria).
- Si una cifra no tiene respaldo en ninguna fuente, es alucinacion y se bloquea.

No descompone en afirmaciones, no llama a ningun modelo, no tiene umbrales de
confianza. Es exacto, instantaneo y no entra en loop de casos borde.

Cubre lo que importa garantizar en una venta: precios, totales, subtotales,
descuentos y montos de envio. Un producto inventado se caza igual, porque su
precio no va a estar en el catalogo.
"""
import re
from typing import Optional

from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

# Solo miramos cifras de dinero. Las chicas, cantidades pedidas, porcentajes o
# numeros de modelo (JBL 510), se ignoran: no son el numero que hay que verificar.
_MIN_MONETARIO = 1000

# Tolerancia de redondeo en pesos.
_TOLERANCIA = 2

# Cantidad maxima razonable de una misma linea, para aceptar precio x cantidad
# (ej "2x $12.000 = $24.000") como aritmetica legitima del catalogo.
_MAX_CANTIDAD = 20

_NUM_RE = re.compile(r"\d[\d.]*")

# Separador de miles, ej 273.000, para distinguir plata de una direccion o modelo.
_MILES_RE = re.compile(r"\d\.\d{3}")
_MONEDA_POST_RE = re.compile(r"\s*(pesos|peso|ars)\b", re.IGNORECASE)
# Unidades de especificacion: si un numero las sigue, es una spec, no plata.
# Ej "30.000 DPI", "75Hz", "8000 dpi". Evita confundir specs con precios.
_UNIDAD_SPEC_RE = re.compile(
    r"\s*(dpi|hz|ghz|mhz|fps|rpm|nits|mah|gramos|gr|kg|g|mm|cm|pulgadas|px|gb|tb|bits?|w)\b",
    re.IGNORECASE)


def _es_monto(texto: str, match) -> bool:
    """Decide si un numero del texto es una cifra de dinero y no una direccion,
    un numero de modelo, una spec o una cantidad. Es plata si tiene separador de
    miles (273.000), o signo pesos antes, o la palabra pesos despues. NO es plata
    si la sigue una unidad de spec como DPI o Hz."""
    start, end = match.span()
    post = texto[end:end + 9]
    if _UNIDAD_SPEC_RE.match(post):
        return False
    token = match.group()
    if _MILES_RE.search(token):
        return True
    pre = texto[max(0, start - 2):start]
    if "$" in pre:
        return True
    if _MONEDA_POST_RE.match(post):
        return True
    return False


_CONTEXTO_TOTAL_RE = re.compile(
    r"(?:sub)?total(?:\s+final)?\s*(?:es\s+de|de|es|:)?\s*\$?\s*$",
    re.IGNORECASE)


def _contexto_total(texto: str, start: int) -> bool:
    """True si el numero viene pegado a la palabra total/subtotal. Un monto
    chico ahi es plata SEGURO (tipicamente un total TRUNCADO por el modelo:
    'Total: $594' por $594.000) y no puede ampararse en el umbral que filtra
    numeros de modelo."""
    return bool(_CONTEXTO_TOTAL_RE.search(texto[max(0, start - 24):start]))


def _parse_num(token: str):
    """Convierte '273.000' o '273000' a 273000. None si no es numero."""
    t = token.replace(".", "").strip()
    if not t.isdigit():
        return None
    try:
        return int(t)
    except ValueError:
        return None


def _es_descuento(extra: dict) -> bool:
    ef = (extra.get("efecto") or "").strip().lower()
    if ef in ("descuento", "recargo", "informativo"):
        return ef == "descuento"
    return "descuento" in str(extra.get("concepto", "")).lower()


def _totales_derivables(proof: dict) -> set:
    """Totales que se pueden derivar legitimamente del PROOF: el subtotal, el
    subtotal con descuentos aplicados, y con cada opcion de envio incluido envio
    gratis (0). Resuelve el caso del total con envio gratis, que el bot calcula
    cuando la compra supera el umbral aunque la calculadora haya usado el rango."""
    cands: set[int] = set()
    sub = proof.get("subtotal_productos")
    if not isinstance(sub, (int, float)):
        ops = proof.get("operandos_productos", []) or []
        s = sum(o.get("monto", 0) for o in ops
                if isinstance(o.get("monto"), (int, float)))
        sub = s or None
    if sub is None:
        return cands
    sub = int(sub)
    cands.add(sub)

    descuentos = 0
    envios = {0}  # envio gratis siempre es una opcion derivable
    for e in proof.get("operandos_extras", []) or []:
        modalidad = e.get("modalidad")
        if modalidad == "porcentaje":
            m = e.get("monto_calculado_ars")
            if isinstance(m, (int, float)):
                if _es_descuento(e):
                    descuentos += int(m)
                else:
                    envios.add(int(m))
        elif modalidad == "rango":
            for k in ("monto_min", "monto_max"):
                m = e.get(k)
                if isinstance(m, (int, float)):
                    envios.add(int(m))
        else:  # fijo
            m = e.get("monto")
            if isinstance(m, (int, float)):
                if _es_descuento(e):
                    descuentos += int(m)
                else:
                    envios.add(int(m))

    neto = sub - descuentos
    cands.add(neto)
    for env in envios:
        cands.add(neto + env)
        cands.add(sub + env)
    return cands


def numeros_confiables(evidence: list[dict]):
    """Junta los numeros verdaderos de la evidencia: precios de catalogo, valores
    y numeros del texto de la FAQ, y todo lo que computo la calculadora en sus
    PROOF. Devuelve un set de montos exactos y una lista de rangos (min, max)."""
    nums: set[int] = set()
    rangos: list[tuple] = []

    def _add(v):
        if isinstance(v, (int, float)):
            nums.add(int(v))

    def _add_texto(txt: str):
        for tok in _NUM_RE.findall(str(txt or "")):
            n = _parse_num(tok)
            if n is not None and n >= _MIN_MONETARIO:
                nums.add(n)

    for item in evidence or []:
        tipo = item.get("tipo")
        if tipo == "producto":
            _add(item.get("precio_ars"))
        elif tipo == "faq":
            for v in item.get("valores", []) or []:
                for k in ("monto", "monto_min", "monto_max",
                          "monto_calculado_ars", "base_ars"):
                    _add(v.get(k))
                _add_texto(v.get("condicion", ""))
            _add_texto(item.get("respuesta", ""))
        elif tipo == "proof":
            proof = item.get("proof", {}) or {}
            for k in ("resultado", "resultado_min", "resultado_max",
                      "subtotal_productos"):
                _add(proof.get(k))
            for o in proof.get("operandos_productos", []) or []:
                _add(o.get("monto"))
                # Precio unitario declarado por la calculadora: respalda el
                # "$X c/u" aunque el producto no este en la evidencia del
                # catalogo del turno (caso Esteban 12-jun: tablet verdadera
                # bloqueada como no respaldada -> fallback en falso).
                _add(o.get("precio_unitario"))
            for e in proof.get("operandos_extras", []) or []:
                for k in ("monto", "monto_min", "monto_max",
                          "monto_calculado_ars", "base_ars"):
                    _add(e.get(k))
            rmin, rmax = proof.get("resultado_min"), proof.get("resultado_max")
            if isinstance(rmin, (int, float)) and isinstance(rmax, (int, float)):
                rangos.append((int(rmin), int(rmax)))
            # Campo generico: cualquier herramienta puede declarar sus numeros
            # verdaderos aca (ej ahorro, diferencia de precio).
            for v in proof.get("valores", []) or []:
                _add(v)
            # Totales derivables (con descuento, con envio gratis, etc).
            nums |= _totales_derivables(proof)
    return nums, rangos


# ────────────────────────────────────────────────────────────
# AUTOCORRECCION DETERMINISTA (Fase 1: partida doble de la verdad)
# ────────────────────────────────────────────────────────────
# Cuando una cifra del texto NO tiene respaldo, hoy el codigo solo bloquea (y, con
# AUTOFIX, repromptea al Solver: una corrida LLM extra, lenta y no determinista).
# Fase 1 mete un paso anterior: si la VERDAD esta en la evidencia, el codigo
# REESCRIBE la cifra mala por la buena, sin llamar a ningun modelo.
#
# Corte conservador: solo se corrige el TOTAL/resultado, que es el error mas comun
# y mas dañino (suma mal hecha, envio mal aplicado). Para no meter nunca el numero
# equivocado, solo se corrige cuando el reemplazo es INEQUIVOCO: tiene que existir
# UN UNICO total valido derivable del PROOF dentro de una banda alrededor de la
# cifra mala. Si hay ambiguedad (cero o varios candidatos), no se toca y cae al
# comportamiento de siempre (AUTOFIX/fallback). El libro de asientos de Fase 2
# permitira corregir mas clases sin esta heuristica.


def _totales_validos(evidence: list[dict]) -> set:
    """Junta los valores de clase 'total/resultado' respaldados por la evidencia:
    los totales derivables del PROOF (subtotal, con descuento, con cada envio,
    envio gratis) y los resultado/resultado_min/max que declaro la calculadora.
    Son los unicos candidatos legitimos para reemplazar un total mal calculado."""
    tot: set[int] = set()
    for item in evidence or []:
        if item.get("tipo") != "proof":
            continue
        proof = item.get("proof", {}) or {}
        tot |= _totales_derivables(proof)
        for k in ("resultado", "resultado_min", "resultado_max"):
            v = proof.get(k)
            if isinstance(v, (int, float)):
                tot.add(int(v))
    tot.discard(0)
    return tot


def _fmt_ar(n: int) -> str:
    """Formatea un entero al estilo argentino con separador de miles: 273000 ->
    '273.000'. Asi el numero reescrito queda igual que como lo escribe el bot."""
    return f"{n:,}".replace(",", ".")


def autocorregir_montos(respuesta: str,
                        evidence: list[dict],
                        trace_id: Optional[str] = None,
                        precios_validos: Optional[set] = None) -> dict:
    """Intenta CORREGIR las cifras de total sin respaldo reemplazandolas por el
    valor verdadero de la evidencia. Determinista, sin LLM.

    Devuelve:
        {
          "cambiada": bool,             # se reescribio al menos una cifra
          "respuesta": str,             # texto (corregido si cambiada, original si no)
          "correcciones": [{de, a}],    # cada reemplazo aplicado
          "verificacion": dict,         # verificar_respuesta del texto resultante
        }

    Conservador: solo reescribe una cifra sin respaldo por el total valido del
    PROOF mas cercano, y solo si ese error es plausible (la verdad esta a <=15% de
    la cifra mala, o sea un error de calculo/envio, no un numero inventado de la
    nada) y el mas cercano es UNICO (sin empate de distancia). Cualquier ambiguedad
    -> no la toca. El llamador debe usar el resultado solo si verificacion['ok'] es
    True; si sigue fallando, descartar y seguir con el comportamiento de siempre.
    """
    base = verificar_respuesta(respuesta, evidence, trace_id=trace_id)
    no_resp = set(base.get("numeros_no_respaldados", []) or [])
    if base.get("ok") or not no_resp:
        return {"cambiada": False, "respuesta": respuesta,
                "correcciones": [], "verificacion": base}

    totales = _totales_validos(evidence)
    if not totales:
        return {"cambiada": False, "respuesta": respuesta,
                "correcciones": [], "verificacion": base}

    # Plan de reemplazos: para cada monto del texto que este sin respaldo, busca el
    # total valido mas cercano y lo reescribe solo si el error es plausible (<=15%)
    # y el mas cercano es unico (sin empate de distancia). Si no, se saltea.
    _BANDA = 0.15
    reemplazos: list[tuple] = []  # (start, end, token_nuevo)
    correcciones: list[dict] = []
    for m in _NUM_RE.finditer(respuesta or ""):
        if not _es_monto(respuesta, m):
            continue
        n = _parse_num(m.group())
        if n is None or n not in no_resp:
            continue
        # NUNCA pisar un numero que sea un precio real de catalogo: que no este en
        # la evidencia de ESTE turno no lo hace falso, puede venir de un producto
        # citado de un turno anterior. Corregirlo lo corromperia (caso Corsair).
        if precios_validos and n in precios_validos:
            continue
        # TOTAL TRUNCADO: un monto chico pegado a "total" cuyos digitos son el
        # PREFIJO de un unico total valido ($594 vs $594.000) es la misma cifra
        # cortada por el modelo: se reescribe entera. Va antes de la banda
        # porque la distancia numerica es enorme aunque el error sea trivial.
        if n < _MIN_MONETARIO and _contexto_total(respuesta, m.start()):
            prefijo = [t for t in totales if str(t).startswith(str(n))]
            if len(set(prefijo)) == 1:
                reemplazos.append((m.start(), m.end(), _fmt_ar(prefijo[0])))
                correcciones.append({"de": n, "a": prefijo[0]})
                continue
        ordenados = sorted(totales, key=lambda r: abs(r - n))
        r = ordenados[0]
        if r == n or abs(r - n) > _BANDA * n:
            continue
        # Empate de distancia entre dos totales validos -> ambiguo, no tocar.
        if len(ordenados) > 1 and abs(ordenados[1] - n) == abs(r - n):
            continue
        reemplazos.append((m.start(), m.end(), _fmt_ar(r)))
        correcciones.append({"de": n, "a": r})

    if not reemplazos:
        return {"cambiada": False, "respuesta": respuesta,
                "correcciones": [], "verificacion": base}

    # Reescribe de atras hacia adelante para no correr los offsets.
    nuevo = respuesta
    for start, end, token in sorted(reemplazos, reverse=True):
        nuevo = nuevo[:start] + token + nuevo[end:]

    verif2 = verificar_respuesta(nuevo, evidence, trace_id=trace_id)
    log.info("autocorrige_montos", trace_id=trace_id,
             correcciones=correcciones[:10], quedo_ok=verif2.get("ok"))

    return {"cambiada": True, "respuesta": nuevo,
            "correcciones": correcciones, "verificacion": verif2}


def verificar_respuesta(respuesta: str,
                        evidence: list[dict],
                        trace_id: Optional[str] = None) -> dict:
    """
    Verifica que cada cifra de dinero de la respuesta tenga respaldo en la
    evidencia. Devuelve:
        {
          "ok": bool,                     # True si toda cifra esta respaldada
          "accion": "responder"|"bloquear",
          "numeros_no_respaldados": [...],
          "total_numeros": int,
        }
    """
    nums, rangos = numeros_confiables(evidence)

    # Aritmetica legitima del catalogo: precio de un producto por una cantidad
    # razonable. Cubre las lineas que el bot a veces calcula de cabeza, como
    # "2x $12.000 = $24.000", sin tener que llamar a la calculadora.
    precios_catalogo = [
        int(i["precio_ars"]) for i in (evidence or [])
        if i.get("tipo") == "producto"
        and isinstance(i.get("precio_ars"), (int, float))
    ]
    for p in precios_catalogo:
        for q in range(1, _MAX_CANTIDAD + 1):
            nums.add(p * q)

    def _directo(n: int) -> bool:
        if n in nums:
            return True
        for lo, hi in rangos:
            if lo <= n <= hi:
                return True
        for t in nums:
            if abs(n - t) <= _TOLERANCIA:
                return True
        return False

    # Montos del texto. Bajo el umbral solo entra el que esta pegado a la
    # palabra total/subtotal: ahi es plata seguro (caso "total: $594" truncado).
    montos: list[int] = []
    for m in _NUM_RE.finditer(respuesta or ""):
        if not _es_monto(respuesta, m):
            continue
        n = _parse_num(m.group())
        if n is None or (n < _MIN_MONETARIO
                         and not _contexto_total(respuesta, m.start())):
            continue
        montos.append(n)

    # Atomos para subtotales: los montos del texto que ya son confiables solos,
    # tipicamente las lineas precio x cantidad. Un subtotal es la suma de esas.
    atomos = sorted({n for n in montos if _directo(n)})

    def _es_suma_de_atomos(n: int) -> bool:
        alcanzables = {0}
        for a in atomos:
            alcanzables |= {r + a for r in set(alcanzables) if r + a <= n + _TOLERANCIA}
        return any(abs(n - r) <= _TOLERANCIA for r in alcanzables if r > 0)

    total = 0
    no_respaldados: list[int] = []
    for n in montos:
        total += 1
        if _directo(n) or _es_suma_de_atomos(n):
            continue
        no_respaldados.append(n)

    ok = len(no_respaldados) == 0
    accion = "responder" if ok else "bloquear"

    log.info("verificador_determinista", trace_id=trace_id, accion=accion,
             total_numeros=total, no_respaldados=no_respaldados[:10])

    return {
        "ok": ok,
        "accion": accion,
        "numeros_no_respaldados": no_respaldados,
        "total_numeros": total,
    }
