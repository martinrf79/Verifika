"""EL CAMINO AL COBRO — las dos mitades del ultimo escalon de la venta, juntas."""
import re
import unicodedata

from app.logger import get_logger

log = get_logger(__name__)


def _n(texto: str) -> str:
    crudo = unicodedata.normalize("NFD", str(texto or "").lower())
    return "".join(c for c in crudo if unicodedata.category(c) != "Mn")


# ── LO QUE SE PUEDE DECIR: LA MODALIDAD, UNA VEZ, CON EL TOTAL CERRADO ──────
_RE_PREGUNTA = re.compile(r"[?¿]")

# Como se dice que ya se dijo. Es de la CHARLA y por eso alcanza con la seña
# fuerte: la modalidad nombrada en una oracion que habla de plata.
_RE_YA_DICHO = re.compile(
    r"transferencia bancaria|link de pago|medios? de pago|formas? de pago|"
    r"mercado ?pago|deposito bancario")


def _pct_descuento_transferencia(tienda_id: str) -> int:
    """El porcentaje de descuento por transferencia, de la FAQ. 0 si no esta."""
    try:
        from app.storage.firestore_client import get_all_faq
        valores = (((get_all_faq(tienda_id=tienda_id) or {})
                    .get("descuento_transferencia") or {}).get("valores") or [])
        dv = next((v for v in valores
                   if str(v.get("unidad") or "").lower() == "porcentaje"), None)
        return int(dv.get("monto", 0)) if dv else 0
    except Exception as e:  # noqa: BLE001 — sin el dato se dice la modalidad sola
        log.warning("camino_cobro_pct_faq_error",
                    error=f"{type(e).__name__}: {str(e)[:120]}")
        return 0


def linea_de_cobro(texto: str, dichos: str, tienda_id: str,
                   trace_id: str = "", *, declarado: dict | None = None,
                   cierre: bool = False) -> str:
    """Pega COMO SE PAGA al final del mensaje que cierra un total, una sola vez."""
    from app.core.familias import abiertas
    fam = set(abiertas(declarado, cierre=cierre))
    if not fam & {"pide_precio", "temas", "reparto_pago", "cierre"}:
        return texto
    from app.core.pago import extraer_total_verificado
    if not (texto or "").strip():
        return texto
    if extraer_total_verificado(texto) is None:
        return texto
    if _RE_PREGUNTA.search(texto):
        return texto
    if _RE_YA_DICHO.search(_n(texto)) or _RE_YA_DICHO.search(_n(dichos)):
        return texto

    from app.core.guia_venta_prosa import mensaje
    pct = _pct_descuento_transferencia(tienda_id)
    if pct:
        linea = mensaje(
            "cobro_como_se_paga_con_descuento",
            "Podés pagar por transferencia bancaria, con {pct}% de descuento, "
            "o con link de pago. Para armarlo solo necesito tu nombre.",
            pct=pct)
    else:
        linea = mensaje(
            "cobro_como_se_paga",
            "Podés pagar por transferencia bancaria o con link de pago. "
            "Para armarlo solo necesito tu nombre.")
    linea = str(linea or "").strip()
    if not linea:
        return texto
    log.info("camino_cobro_dicho", trace_id=trace_id, pct=pct)
    return (texto or "").rstrip() + "\n\n" + linea


# ── LO QUE NO SE PUEDE DECIR NUNCA: UNA CUENTA QUE NO ES LA DE LA TIENDA ────

# UN NUMERO DE CUENTA, tolerando como lo escribe la gente.
_RE_CORRIDA = re.compile(r"\d[\d\s.\-]{14,40}\d")

# Las cinco etiquetas con las que se nombra una cuenta.
_RE_ETIQUETA = re.compile(r"(?i)\b(cbu|cvu|alias|titular|banco)\b")

# UN ALIAS: palabras pegadas con puntos, como los escribe el banco.
_RE_ALIAS = re.compile(r"(?i)\b[a-z][a-z0-9]{1,}(?:\.[a-z0-9]{2,}){1,3}\b")
_DOMINIOS = ("com", "ar", "net", "org", "io", "gov", "edu", "py", "uy", "cl",
             "br", "es", "mx", "co", "html", "php", "json", "csv", "py3")

# LA ORACION HABLA DE UNA CUENTA. Es lo que arma la mitad del alias: sin esto,
# `mercadolibre.com.ar` o un `G.Skill` del catalogo entrarian a la poda.
_RE_CTX_CUENTA = re.compile(
    r"(?i)transfer|deposit|cuenta|cbu|cvu|alias|titular|banco|acredit")

# EL TITULAR DICHO EN PROSA, sin etiqueta: "la cuenta esta a nombre de X".
_RE_A_NOMBRE_DE = re.compile(r"(?i)\ba nombre de\b")

# El cortador de oraciones. Corta en salto de linea, que es donde el modelo escribe los renglones de una
# cuenta, y en punto SOLO si al punto le sigue un espacio o el final.
_RE_ORACION_COBRO = re.compile(r"(?:[^.\n;!?]|\.(?!\s|$))+[.\n;!?]*")


def _digitos(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _hay_cuenta(texto: str) -> bool:
    """LA PUERTA, y se arma por el HECHO. Cualquiera de las tres formas de nombrar una cuenta alcanza: un numero
    largo, una etiqueta, o un alias en una oracion que habla de transferir."""
    t = texto or ""
    if any(18 <= len(_digitos(m.group(0))) <= 26
           for m in _RE_CORRIDA.finditer(t)):
        return True
    if _RE_ETIQUETA.search(t):
        return True
    if not _RE_CTX_CUENTA.search(t):
        return False
    return bool(_alias_candidatos(t) or _RE_A_NOMBRE_DE.search(t))


def _alias_candidatos(texto: str) -> list:
    """Los tokens con pinta de alias bancario que hay en el texto, sin los que
    son dominios de internet ni parte de una URL."""
    fuera = []
    for m in _RE_ALIAS.finditer(texto or ""):
        tok = m.group(0)
        if "//" in (texto or "")[max(0, m.start() - 8):m.start()]:
            continue
        if tok.lower().rsplit(".", 1)[-1] in _DOMINIOS:
            continue
        fuera.append(tok)
    return fuera


def _reales(tienda_id: str) -> dict:
    """Los datos de cobro de la tienda, de la config."""
    try:
        from app.core.pago import datos_transferencia
        return datos_transferencia(tienda_id) or {}
    except Exception as e:  # noqa: BLE001 — se registra y la guardia se cierra
        log.error("camino_cobro_config_ilegible", tienda_id=str(tienda_id),
                  error=f"{type(e).__name__}: {str(e)[:120]}")
        return {}


def sin_cobro_inventado(texto: str, tienda_id: str, trace_id: str) -> str:
    """UNA CUENTA QUE NO ES LA DE LA TIENDA NO SALE."""
    if not _hay_cuenta(texto or ""):
        return texto
    d = _reales(tienda_id)
    campos = {"cbu": str(d.get("cbu") or ""), "cvu": str(d.get("cbu") or ""),
              "alias": str(d.get("alias") or ""),
              "titular": str(d.get("titular_cuenta") or ""),
              "banco": str(d.get("banco") or "")}
    cbu_real = _digitos(campos["cbu"])
    alias_real = campos["alias"].lower()

    salida, borradas, quedo_real = [], [], False
    for m in _RE_ORACION_COBRO.finditer(texto or ""):
        pedazo = m.group(0)
        veredicto = _juzgar(pedazo, campos, cbu_real, alias_real)
        if veredicto == "inventado":
            borradas.append(pedazo.strip()[:60])
            # El salto de linea se conserva para no pegar dos renglones que no
            # tenian nada que ver: la poda saca la oracion, no la separacion.
            salida.append("\n" if pedazo.endswith("\n") else "")
            continue
        if veredicto == "real":
            quedo_real = True
        salida.append(pedazo)

    if not borradas:
        return texto
    log.error("hub_venta_cobro_inventado", trace_id=trace_id,
              lineas=borradas[:4])
    fuera = "".join(salida)
    if not quedo_real:
        from app.core.guia_venta_prosa import mensaje
        # La clave YA EXISTE en la fuente y dice exactamente esto: se reusa en vez de escribir una gemela.
        fuera = fuera.rstrip() + "\n" + mensaje(
            "pago_falta_el_total",
            "Para pasarte los datos de pago necesito confirmarte primero el "
            "total. Decime y te los paso enseguida.")
    return re.sub(r"\n{3,}", "\n\n", fuera).strip()


def _juzgar(pedazo: str, campos: dict, cbu_real: str, alias_real: str) -> str:
    """`real`, `inventado` o `` para una oracion."""
    baja = pedazo.lower()
    toca = ""

    # 1. UN NUMERO DE CUENTA. Se compara por DIGITOS, asi que el CBU real escrito con espacios sigue siendo el
    # real y el inventado sigue siendo inventado: el formato no decide nada, el numero si.
    for m in _RE_CORRIDA.finditer(pedazo):
        dig = _digitos(m.group(0))
        if not 18 <= len(dig) <= 26:
            continue
        if cbu_real and dig == cbu_real:
            toca = "real"
        else:
            return "inventado"

    # 2. UN ALIAS. Solo si la oracion habla de una cuenta; ahi un token con
    #    puntos que no es el alias de la tienda es un alias inventado.
    if _RE_CTX_CUENTA.search(pedazo):
        for tok in _alias_candidatos(pedazo):
            if alias_real and tok.lower() == alias_real:
                toca = "real"
            else:
                return "inventado"

    # 3. UNA ETIQUETA CON SU VALOR: `Titular: X`, `Banco: Y`.
    for m in _RE_ETIQUETA.finditer(pedazo):
        etiqueta = m.group(1).lower()
        detras = re.match(r"\s*:\s*(\S.*)?", pedazo[m.end():])
        if not detras or not detras.group(1):
            continue
        real = campos.get(etiqueta, "").lower()
        if real and real in baja:
            toca = "real"
        elif etiqueta in ("cbu", "cvu") and cbu_real and cbu_real in _digitos(pedazo):
            toca = "real"
        else:
            return "inventado"

    # 4. EL TITULAR EN PROSA. "La cuenta esta a nombre de X" afirma un titular sin escribir la etiqueta, y es
    # la forma en que el modelo lo dice cuando no esta armando una ficha de datos.
    if _RE_A_NOMBRE_DE.search(pedazo) and _RE_CTX_CUENTA.search(pedazo):
        titular = campos.get("titular", "").lower()
        if titular and titular in baja:
            toca = "real"
        else:
            return "inventado"
    return toca
