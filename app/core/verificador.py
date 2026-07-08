"""
VERIFICADOR DETERMINISTA — linea cero de la anti alucinacion.

La decision final de mandar o no la respuesta la toma el CODIGO, no un modelo.
A diferencia del Checker de Verifika, que es un LLM juzgando a otro LLM y por eso
es no determinista y se equivoca, este verificador es codigo puro:

- Escanea la respuesta y junta cada cifra de dinero.
- Exige que cada cifra salga de una fuente real: un precio del catalogo, un valor
  estructurado de la FAQ cuantitativa (monto, rango o el numero de su condicion),
  o un PROOF de la calculadora (de este turno o de turnos recientes en memoria).
  La prosa libre de una FAQ NO respalda: un numero suelto en el texto de respuesta
  no alcanza para blanquear un precio (evita el falso positivo del umbral de envio).
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

# Contexto de plata para un numero SIN formato (sin puntos, sin signo, sin
# 'pesos'): precedido por un verbo de precio (sale, cuesta, vale, total...) o
# seguido de 'total'. Asi un precio que el modelo tipea pelado igual se cuenta y
# se verifica, en vez de esquivar el control por no venir formateado.
_PRECIO_PRE_RE = re.compile(
    r"\b(sale|salen|cuesta|cuestan|vale|valen|son|paga|pagas|abona|abonas|"
    r"queda|quedan|precio|total|subtotal)\s*(?:de\s+)?\$?\s*$",
    re.IGNORECASE)
_TOTAL_POST_RE = re.compile(r"\s*(?:en\s+)?(?:sub)?total\b", re.IGNORECASE)


def _es_monto(texto: str, match) -> bool:
    """Decide si un numero del texto es una cifra de dinero y no una direccion,
    un numero de modelo, una spec o una cantidad. Es plata si tiene separador de
    miles (273.000), o signo pesos antes, o la palabra pesos despues, o si viene en
    contexto explicito de precio (sale/cuesta/total) aunque este sin formato. NO es
    plata si la sigue una unidad de spec como DPI o Hz."""
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
    # Numero sin formato en contexto de plata: verbo de precio antes, o 'total'
    # despues. Cubre el precio pelado (999999) que si no se colaba sin verificar.
    if _PRECIO_PRE_RE.search(texto[max(0, start - 24):start]):
        return True
    if _TOTAL_POST_RE.match(texto[end:end + 12]):
        return True
    return False


_CONTEXTO_TOTAL_RE = re.compile(
    r"(?:sub)?total(?:\s+final)?\s*(?:es\s+de|de|es|:)?\s*\*{0,2}\s*\$?\s*$",
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
    # Envios: en multi-destino hay un envio por destino y el total los SUMA todos,
    # no son alternativas entre si. Cada slot aporta su monto; un rango aporta su
    # piso y su techo, asi el total sale con la suma minima o con la maxima. El 0
    # (envio gratis por umbral) es la unica alternativa que reemplaza al envio
    # entero. Sumar en vez de alternar es lo que distingue un total que incluye
    # todos los envios de uno que se come alguno (ese ultimo ya no valida).
    suma_min = 0
    suma_max = 0
    for e in proof.get("operandos_extras", []) or []:
        modalidad = e.get("modalidad")
        if modalidad == "rango":
            mn, mx = e.get("monto_min"), e.get("monto_max")
            if isinstance(mn, (int, float)):
                suma_min += int(mn)
            if isinstance(mx, (int, float)):
                suma_max += int(mx)
        elif modalidad == "porcentaje":
            m = e.get("monto_calculado_ars")
            if isinstance(m, (int, float)):
                if _es_descuento(e):
                    descuentos += int(m)
                else:
                    suma_min += int(m)
                    suma_max += int(m)
        else:  # fijo
            m = e.get("monto")
            if isinstance(m, (int, float)):
                if _es_descuento(e):
                    descuentos += int(m)
                else:
                    suma_min += int(m)
                    suma_max += int(m)

    envios = {0, suma_min, suma_max}
    neto = sub - descuentos
    cands.add(neto)
    for env in envios:
        cands.add(neto + env)
        cands.add(sub + env)
    return cands


def _total_multienvio(evidence: list[dict]) -> set:
    """Total de un pedido con VARIOS envios a zonas distintas: el subtotal de
    productos mas la SUMA de todas las cotizaciones de envio de la evidencia.

    El solver cotiza cada destino por separado, un PROOF de envio (cotizar_envio)
    por zona, y la calculadora da el subtotal de productos. Ese combinado es el
    UNICO total correcto del multienvio, y ningun PROOF suelto lo deriva: la
    calculadora colapsa a una sola zona y cada PROOF de envio trae una sola
    tarifa. Sin esto la melliza activa bloquea el total correcto y hasta
    'corrige' el que se come un envio hacia el subtotal pelado (le saca TODOS
    los envios). Solo aplica con 2+ cotizaciones, el caso real de multi-destino.
    Suma pura: agrega el total verdadero, nunca puede bendecir uno equivocado."""
    subtotales: set[int] = set()
    envios: list[int] = []
    for item in evidence or []:
        if item.get("tipo") != "proof":
            continue
        proof = item.get("proof", {}) or {}
        if proof.get("tipo") == "envio":
            m = proof.get("resultado")
            if not isinstance(m, (int, float)):
                m = proof.get("monto")
            if isinstance(m, (int, float)) and int(m) > 0:
                envios.append(int(m))
        else:
            sub = proof.get("subtotal_productos")
            if isinstance(sub, (int, float)):
                subtotales.add(int(sub))
    if not subtotales or len(envios) < 2:
        return set()
    suma = sum(envios)
    return {sub + suma for sub in subtotales}


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
            # Solo lo ESTRUCTURADO respalda: montos/rangos de los valores y el
            # numero de su condicion (ej umbral de envio gratis). La prosa libre de
            # la respuesta NO entra al pool: un numero suelto ahi blanqueaba precios
            # alucinados que coincidian con el (E7). El dato de verdad es el valor.
            for v in item.get("valores", []) or []:
                for k in ("monto", "monto_min", "monto_max",
                          "monto_calculado_ars", "base_ars"):
                    _add(v.get(k))
                _add_texto(v.get("condicion", ""))
        elif tipo == "proof":
            proof = item.get("proof", {}) or {}
            for k in ("resultado", "resultado_min", "resultado_max",
                      "subtotal_productos"):
                _add(proof.get(k))
            # PROOF del split de pago: base, total final, descuento y cada parte
            # (monto por medio y monto con descuento) son cifras que computo la
            # calculadora, no el solver. Sin esto la respuesta CORRECTA del
            # reparto (ej "transferencia $754.650, MP $838.500") se bloquea en
            # falso, porque esos montos no salen de un resultado suelto.
            for m in proof.get("montos", []) or []:
                _add(m)
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
    # Total del multienvio: subtotal + suma de todas las cotizaciones de envio.
    # Lo unico que ata las cotizaciones sueltas de cada zona en un gran total.
    nums |= _total_multienvio(evidence)
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
        # El PROOF de cotizar_envio NO es un total: su resultado es el costo de
        # envio. Si entrara aca, un costo de envio (ej 7.500) quedaria como total
        # valido y el corrector podria reescribir un total por una cifra de envio.
        # El total tiene una sola fuente: el PROOF de calculate_total.
        if proof.get("tipo") == "envio":
            continue
        tot |= _totales_derivables(proof)
        for k in ("resultado", "resultado_min", "resultado_max"):
            v = proof.get(k)
            if isinstance(v, (int, float)):
                tot.add(int(v))
    # Total del multienvio (subtotal + suma de cotizaciones): candidato legitimo
    # para corregir un total que se comio uno de varios envios. Sin esto el
    # corrector reescribia ese total hacia el subtotal pelado, sacando los envios.
    tot |= _total_multienvio(evidence)
    tot.discard(0)
    return tot


def _envios_validos(evidence: list[dict]) -> set:
    """Montos de ENVIO respaldados: el resultado/valores de un PROOF de envio
    (cotizar_envio), los extras de envio (no descuento) de calculate_total y la
    tarifa cargada en la FAQ costo_envio. Es el pool para corregir un costo de
    envio mal tipeado por el modelo. El 0 (envio gratis) se descarta: no se
    reescribe una cifra por cero, eso cambiaria la frase y se maneja aparte."""
    env: set[int] = set()

    def _add(v):
        if isinstance(v, (int, float)) and int(v) > 0:
            env.add(int(v))

    for item in evidence or []:
        tipo = item.get("tipo")
        if tipo == "proof":
            proof = item.get("proof", {}) or {}
            if proof.get("tipo") == "envio":
                _add(proof.get("resultado"))
                _add(proof.get("monto"))
                for v in proof.get("valores", []) or []:
                    _add(v)
            for e in proof.get("operandos_extras", []) or []:
                if _es_descuento(e):
                    continue
                for k in ("monto", "monto_min", "monto_max", "monto_calculado_ars"):
                    _add(e.get(k))
        elif tipo == "faq" and str(item.get("id") or "") == "costo_envio":
            for v in item.get("valores", []) or []:
                for k in ("monto", "monto_min", "monto_max",
                          "monto_calculado_ars", "base_ars"):
                    _add(v.get(k))
    return env


_ENVIO_CTX = ("envio", "envío", "flete")


def _contexto_envio(texto: str, start: int) -> bool:
    """True si el numero viene en contexto de envio (la palabra envio/flete aparece
    justo antes). Ancla la cifra al concepto envio para no corregirla con un total."""
    pre = texto[max(0, start - 30):start].lower()
    return any(k in pre for k in _ENVIO_CTX)


def _tokens_significativos(nombre: str) -> list[str]:
    """Palabras distintivas de un nombre de producto: alfanumericas de 4+ chars.
    Descarta conectores y sufijos cortos (de, pro, v4) que dan falsos match."""
    return [t for t in re.findall(r"[a-z0-9]+", (nombre or "").lower())
            if len(t) >= 4]


# Entre el nombre del producto y su cifra, en un RENGLON de presupuesto, solo
# hay separadores y aritmetica ("1x NOMBRE: $14.000 c/u = $"). Letras sueltas
# de prosa ("sale", "el otro que viste") rompen la adyacencia.
_ADYACENTE_RE = re.compile(r"[\s:;,.\-–—*()=$/\dxcu%]*")


def _producto_nombrado(texto: str, start: int,
                       evidence: list[dict]) -> Optional[tuple]:
    """(precio, ids, adyacente) del producto que el solver nombro justo antes de
    esta cifra. Ancla el numero al NOMBRE: si en la ventana previa aparece, sin
    ambiguedad, el nombre de UN solo producto del catalogo, devuelve su
    precio_ars, el set de ids que resuelven a ese precio, y si la cifra esta
    PEGADA al nombre como renglon de presupuesto (adyacente=True: entre nombre y
    cifra solo hay separadores). Asi un precio mal tipeado se corrige por el del
    producto que el modelo realmente nombro, no por el numero mas cercano de
    cualquier lado. Si matchean dos productos con precios distintos, es ambiguo
    y no se toca (devuelve None)."""
    ventana = texto[max(0, start - 90):start].lower()
    # Ancla EXACTA primero (mismo criterio que el verificador de stock): el
    # nombre COMPLETO del producto esta literal en la ventana. Gana aunque
    # hermanos de la marca compartan tokens ("Genius NX-7000" vs "Genius
    # DX-110": el ancla por tokens los empata y el precio tipeado a mano
    # quedaba sin corregir, visto en el banco con $8.000 por $14.000).
    exactos = [i for i in evidence or []
               if i.get("tipo") == "producto"
               and isinstance(i.get("precio_ars"), (int, float))
               and str(i.get("nombre") or "").strip()
               and str(i["nombre"]).lower() in ventana]
    precios_ex = {int(i["precio_ars"]) for i in exactos}
    if len(precios_ex) == 1:
        fin_nombre = max(ventana.rfind(str(i["nombre"]).lower())
                         + len(str(i["nombre"])) for i in exactos)
        adyacente = bool(_ADYACENTE_RE.fullmatch(ventana[fin_nombre:]))
        return (precios_ex.pop(),
                {str(i.get("id") or "").upper() for i in exactos},
                adyacente)
    puntuados: list[tuple[int, int, str]] = []  # (tokens presentes, precio, id)
    for item in evidence or []:
        if item.get("tipo") != "producto":
            continue
        precio = item.get("precio_ars")
        if not isinstance(precio, (int, float)):
            continue
        toks = _tokens_significativos(item.get("nombre", ""))
        if not toks:
            continue
        presentes = sum(1 for t in toks if t in ventana)
        if presentes >= min(2, len(toks)):
            puntuados.append((presentes, int(precio),
                              str(item.get("id") or "").upper()))
    precios = {p for _, p, _ in puntuados}
    if len(precios) == 1:
        return (precios.pop(), {i for _, _, i in puntuados}, False)
    # Desempate entre variantes (mismo criterio que stock): el que matchea MAS
    # tokens es el nombrado; empate real de puntaje sigue siendo ambiguo.
    if puntuados:
        puntuados.sort(reverse=True)
        if len(puntuados) == 1 or puntuados[0][0] > puntuados[1][0]:
            return (puntuados[0][1], {puntuados[0][2]}, False)
    return None


def _precio_de_producto_nombrado(texto: str, start: int,
                                 evidence: list[dict]) -> Optional[int]:
    """Solo el precio del producto nombrado (ver _producto_nombrado)."""
    r = _producto_nombrado(texto, start, evidence)
    return r[0] if r else None


def _mejor_candidato(n: int, pool: set, banda: float) -> Optional[int]:
    """El valor del pool mas cercano a n, solo si el error es plausible (<= banda)
    y el mas cercano es UNICO (sin empate de distancia). None si no hay candidato
    inequivoco. Regla conservadora compartida por total y envio."""
    if not pool:
        return None
    ordenados = sorted(pool, key=lambda r: abs(r - n))
    r = ordenados[0]
    if r == n or abs(r - n) > banda * n:
        return None
    if len(ordenados) > 1 and abs(ordenados[1] - n) == abs(r - n):
        return None
    return r


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

    Conservador y ANCLADO AL CONCEPTO. Para cada cifra sin respaldo decide por el
    contexto si es precio de producto, envio o total, y la reescribe solo con el
    pool de ESE concepto:
      - precio: se ancla al NOMBRE del producto que el solver nombro antes de la
        cifra; si en la ventana previa aparece, sin ambiguedad, un solo producto del
        catalogo, se usa SU precio_ars. No depende de cercania numerica.
      - envio: el monto de envio mas cercano (cotizar_envio/FAQ costo_envio), con
        banda ancha (50%) porque el envio es chico y el error puede ser proporcional.
      - total: el total valido del PROOF mas cercano con banda fina (15%), mas el
        caso del total truncado ($594 por $594.000).
    En todos, el candidato debe ser UNICO (sin empate). Cualquier ambiguedad -> no la
    toca. Cada correccion lleva su 'concepto' para loguear que se piso y por que. El
    llamador debe usar el resultado solo si verificacion['ok'] es True; si sigue
    fallando, descartar y seguir con el comportamiento de siempre.
    """
    base = verificar_respuesta(respuesta, evidence, trace_id=trace_id)
    no_resp = set(base.get("numeros_no_respaldados", []) or [])

    totales = _totales_validos(evidence)
    envios = _envios_validos(evidence)
    hay_precio = any(
        i.get("tipo") == "producto" and isinstance(i.get("precio_ars"), (int, float))
        for i in (evidence or []))
    # El ancla de precio por NOMBRE actua aunque no haya cifras marcadas sin
    # respaldo: un precio de lista mal tipeado puede coincidir con un numero del
    # pool y no marcarse. Por eso NO se corta temprano por base.ok si hay productos
    # para anclar. Sin cifras sin respaldo NI productos, no hay nada que hacer.
    if not no_resp and not hay_precio:
        return {"cambiada": False, "respuesta": respuesta,
                "correcciones": [], "verificacion": base}
    if not (totales or envios or hay_precio):
        return {"cambiada": False, "respuesta": respuesta,
                "correcciones": [], "verificacion": base}

    # Renglones que COMPUTO la calculadora (operandos del PROOF, con id): un
    # renglon legitimo "3x Notebook X: $693.000 c/u = $2.079.000" tiene el
    # nombre del producto en la ventana y una cifra distinta del precio
    # unitario, y el sello del precio de lista lo pisaba por $693.000 (visto
    # 8-jul con el presupuesto sellado de la guia de pedido). La exencion es
    # por IDENTIDAD: solo exime el monto computado PARA EL MISMO producto
    # nombrado; un monto computado para OTRO producto (el solver le puso el
    # nombre equivocado, caso Zeus X Negro con el subtotal de un tercero) se
    # sigue corrigiendo al precio del nombrado.
    operandos_proof = [
        o for i in (evidence or []) if i.get("tipo") == "proof"
        for o in ((i.get("proof") or {}).get("operandos_productos") or [])
        if isinstance(o, dict)]

    # Plan de reemplazos: para cada monto del texto sin respaldo se decide el
    # concepto por el CONTEXTO (precio de producto, envio o total) y se reescribe
    # solo con el pool de ESE concepto, de forma inequivoca. Asi una cifra de precio
    # no se corrige con un total ni viceversa. El envio admite mas error (banda
    # ancha) porque es chico; el total es fino (15%). El precio se ancla al NOMBRE
    # del producto que el solver nombro, no a la cercania numerica.
    _BANDA_TOTAL = 0.15
    _BANDA_ENVIO = 0.5
    reemplazos: list[tuple] = []  # (start, end, token_nuevo)
    correcciones: list[dict] = []
    for m in _NUM_RE.finditer(respuesta or ""):
        if not _es_monto(respuesta, m):
            continue
        n = _parse_num(m.group())
        if n is None:
            continue
        # Candado Corsair: un numero que es un precio real de catalogo citado no
        # se pisa por cercania (ramas b/c/d) — puede ser un producto citado de un
        # turno anterior. La UNICA excepcion es el ancla por nombre ADYACENTE
        # (rama a): en un renglon de presupuesto ("1x Zeus X Negro: $62.500") el
        # vinculo nombre-cifra es inequivoco, y que la cifra sea el precio real
        # de OTRO producto (el Pandora) es justamente el error de etiqueta que el
        # sello corrige (visto en el banco 8-jul; sin esto el candado anulaba al
        # sello para todo precio del pool).
        n_protegido = bool(precios_validos and n in precios_validos)
        en_total = _contexto_total(respuesta, m.start())
        en_envio = _contexto_envio(respuesta, m.start())
        candidato: Optional[int] = None
        concepto: Optional[str] = None
        # a) PRECIO anclado al NOMBRE: en contexto de precio puro (ni total ni
        #    envio) corre aunque la cifra figure "respaldada" por el pool.
        #    El ancla al nombre es mas fuerte que la pertenencia al pool: el numero
        #    puede ser el precio real de OTRO producto (KB-110X tipeado a $16.500,
        #    que es precio de un tercero, se corrige a su $12.000 real). Cierra el
        #    hueco del precio de lista mal tipeado que no se marcaba como sin
        #    respaldo. Sobre un precio protegido del pool solo actua con ancla
        #    ADYACENTE (renglon de presupuesto); en prosa suelta el candado manda.
        if not en_total and not en_envio:
            _anclado = _producto_nombrado(respuesta, m.start(), evidence)
            if _anclado and _anclado[0] != n:
                pr, _ids_anclados, _adyacente = _anclado
                _renglon_propio = any(
                    str(o.get("id") or "").upper() in _ids_anclados
                    and o.get("monto") == n
                    for o in operandos_proof)
                if not _renglon_propio and (_adyacente or not n_protegido):
                    candidato, concepto = pr, "precio"
        if candidato is None and n_protegido:
            continue
        # b/c/d) envio y total: SOLO para cifras efectivamente sin respaldo (se
        #    corrigen por cercania al pool, no por nombre). Una cifra respaldada en
        #    esos contextos no se toca.
        # b) ENVIO: la cifra viene en contexto de envio -> pool de envios.
        if candidato is None and n in no_resp and en_envio:
            c = _mejor_candidato(n, envios, _BANDA_ENVIO)
            if c is not None:
                candidato, concepto = c, "envio"
        # c) TOTAL TRUNCADO: $594 pegado a "total" cuyos digitos son el PREFIJO de
        #    un unico total valido ($594 por $594.000), misma cifra cortada.
        if candidato is None and n in no_resp and n < _MIN_MONETARIO and en_total:
            prefijo = [t for t in totales if str(t).startswith(str(n))]
            if len(set(prefijo)) == 1:
                candidato, concepto = prefijo[0], "total"
        # d) TOTAL por banda: el total valido mas cercano si el error es plausible.
        if candidato is None and n in no_resp:
            c = _mejor_candidato(n, totales, _BANDA_TOTAL)
            if c is not None:
                candidato, concepto = c, "total"
        if candidato is None or candidato == n:
            continue
        reemplazos.append((m.start(), m.end(), _fmt_ar(candidato)))
        correcciones.append({"de": n, "a": candidato, "concepto": concepto})

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


def decidir_accion_no_respaldado(verificacion_ok: bool,
                                 hay_tools: bool,
                                 hay_memoria: bool) -> str:
    """Melliza activa: cuando queda una cifra de plata SIN respaldo, decide que
    hacer con el mensaje. Tres acciones:
        "responder"  la verificacion cerro, sale intacto.
        "shadow"     queda un residual sin respaldo pero HAY de donde pudo salir
                     (tools de este turno o evidencia en memoria): sale igual y
                     solo se loguea; cortar aca mata respuestas legitimas.
        "bloquear"   no hay NINGUNA evidencia (ni tools ni memoria): el numero es
                     alucinacion pura, no llega al cliente y va el canned.

    El error que corrige A: antes se bloqueaba por 'este turno no llamo tools'.
    Pero el solver que repite un presupuesto ya calculado en turnos anteriores no
    llama tools y sus cifras son legitimas: la evidencia esta en MEMORIA. La
    decision correcta mira si hay evidencia en cualquier lado, no solo en el turno.
    """
    if verificacion_ok:
        return "responder"
    if not hay_tools and not hay_memoria:
        return "bloquear"
    return "shadow"


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


# ────────────────────────────────────────────────────────────
# ASIENTOS DEL PRESUPUESTO: el Subtotal declarado = suma de los renglones
# ────────────────────────────────────────────────────────────
# Candidata del RESUMEN (banco 5-jul: "Total $44.500 con renglones que sumaban
# $33.500") vista de nuevo el 8-jul: "Subtotal: $232.500" con renglones que
# sumaban $290.000 (el solver puso el precio del ultimo item como subtotal).
# Regla CERRADA: si el mensaje tiene renglones de presupuesto parseables y una
# linea de Subtotal cuya cifra NO es la suma, y la suma SI esta respaldada por
# la evidencia (proof de la calculadora), se reescribe el subtotal por la suma.
# Conservador: cualquier renglon ambiguo (sin monto claro) aborta.

_RE_RENGLON = re.compile(
    r"^\s*[-*•]?\s*\**\d+\s*x\s+[^:\n]+\**:?\s*.*?\$\s*([\d.]+)\s*\**\s*$",
    re.IGNORECASE | re.MULTILINE)
_RE_SUBTOTAL = re.compile(
    r"^(\s*[-*•]?\s*\**\s*subtotal\s*\**\s*:?\s*\**\s*\$\s*)([\d.]+)",
    re.IGNORECASE | re.MULTILINE)


def corregir_subtotal_renglones(respuesta: str, evidence: list[dict],
                                trace_id: Optional[str] = None) -> dict:
    """Corrige la linea 'Subtotal: $X' cuando X no es la suma de los renglones
    del MISMO mensaje y la suma esta respaldada. Devuelve
    {cambiada, respuesta, de, a}."""
    out = {"cambiada": False, "respuesta": respuesta, "de": None, "a": None}
    if not respuesta or "ubtotal" not in respuesta:
        return out
    m_sub = _RE_SUBTOTAL.search(respuesta)
    if not m_sub:
        return out
    renglones = []
    for m in _RE_RENGLON.finditer(respuesta):
        # Un renglon con "c/u = $X" tiene dos montos; _RE_RENGLON captura el
        # ULTIMO de la linea (el subtotal del renglon), que es el que suma.
        n = _parse_num(m.group(1))
        if n is None:
            return out  # renglon ilegible: no se corrige nada
        renglones.append(n)
    if not renglones:
        return out
    suma = sum(renglones)
    declarado = _parse_num(m_sub.group(2))
    if declarado is None or declarado == suma:
        return out
    nums, _ = numeros_confiables(evidence)
    if suma not in nums:
        return out  # la suma no esta respaldada por ninguna fuente: no tocar
    nuevo = (respuesta[:m_sub.start()] + m_sub.group(1) + _fmt_ar(suma)
             + respuesta[m_sub.end():])
    log.warning("subtotal_renglones_corregido", trace_id=trace_id,
                de=declarado, a=suma, renglones=len(renglones))
    return {"cambiada": True, "respuesta": nuevo, "de": declarado, "a": suma}
