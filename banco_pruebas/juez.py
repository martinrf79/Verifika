"""
JUEZ DE INVARIANTES — chequeo determinista de cada respuesta del banco.

La tanda de charlas no depende de que un humano LEA cada salida: el juez
aplica los MISMOS detectores del camino vivo (verificador_stock, guardia de
promesas, ancla de precio del verificador) contra el catalogo completo del
doble, mas invariantes de salida (marcador sin estampar, narracion interna).
Si una respuesta viola un invariante, la tanda falla sola.

No trae casos hardcodeados: son invariantes, no ejemplos. Conservador como
los verificadores que reusa: ancla unica o no acusa.
"""
import re

from app.core import verificador_stock as VS
from app.core import guardia_promesas as GP

# Monto en pesos con separador de miles argentino, o entero pelado tras $.
_RE_MONTO = re.compile(r"\$\s?(\d{1,3}(?:\.\d{3})+|\d+)")

# La cifra viene de una CUENTA (total, envio, descuento, cuota): no es el precio
# de lista del producto nombrado y el ancla de precio no la juzga (los totales
# los verifica el pipeline con el proof de la calculadora, no este juez).
_RE_CONTEXTO_CUENTA = re.compile(
    r"(?:total|subtotal|env[ií]o|descuento|cuotas?|se[ñn]a|c/u|por\s+los?\s+\d)",
    re.IGNORECASE)

# Pregunta de CONFIRMACION del cierre (no de dato): dos en una misma respuesta
# es el doble cierre robotico. Conservador: solo frases inequivocas.
_RE_PREGUNTA_CIERRE = re.compile(
    r"¿[^¿?]*(?:confirm|seguimos|avanzamos|cerramos|lo dejamos|lo preparo|"
    r"reserv|lo pedimos|hacemos el pedido)[^¿?]*\?", re.IGNORECASE)

# Narracion interna del solver filtrada al cliente ("el sistema me tiro un
# detalle", "me pide mas precision"): el cliente nunca tiene que ver la cocina.
_RE_NARRACION = re.compile(
    r"(?:el\s+sistema\s+(?:me|tom[oó]|tir[oó]|dice|marc[oó])|"
    r"la\s+herramienta\s+me|me\s+tir[oó]\s+un\s+detalle|"
    r"ah[ií]\s+me\s+pide|la\s+tool\b)",
    re.IGNORECASE)


def _catalogo_evidencia(tienda_id: str = "verifika_prod") -> list[dict]:
    from app.storage.firestore_client import get_all_products
    return [{"tipo": "producto", **p}
            for p in get_all_products(tienda_id=tienda_id)]


def _tarifas_envio_conocidas(tienda_id: str) -> set[int]:
    """Todos los montos de envio que la tienda puede cobrar (config por
    provincia, tarifas_envio de la tienda, valores de la FAQ costo_envio). Una
    cifra igual a una tarifa es plausiblemente un envio del pedido aunque no
    diga la palabra 'envio' cerca ('Mouse a Cordoba: $7.500'): no se acusa
    como precio de lista pisado."""
    montos: set[int] = set()
    try:
        from app.config import get_settings
        montos |= {int(v) for v in
                   get_settings().ENVIO_INTERIOR_POR_PROVINCIA.values()}
    except Exception:
        pass
    try:
        from app.storage.firestore_client import get_config
        provincias = (get_config("tarifas_envio", tienda_id=tienda_id)
                      or {}).get("provincias") or {}
        montos |= {int(v) for v in provincias.values()
                   if isinstance(v, (int, float))}
    except Exception:
        pass
    try:
        from app.storage.firestore_client import get_all_faq
        valores = ((get_all_faq(tienda_id=tienda_id) or {})
                   .get("costo_envio") or {}).get("valores") or []
        for v in valores:
            for k in ("monto", "monto_min", "monto_max"):
                if isinstance(v.get(k), (int, float)):
                    montos.add(int(v[k]))
    except Exception:
        pass
    return montos


def juzgar(respuesta: str, tienda_id: str = "verifika_prod",
           mensaje: str = "") -> list[str]:
    """Lista de violaciones de invariantes en la respuesta ([] = limpia).
    Con el mensaje del cliente ademas juzga contra lo DECLARADO (invariante
    11, envios perdidos)."""
    problemas: list[str] = []
    if not respuesta:
        return ["respuesta vacia"]
    ev = _catalogo_evidencia(tienda_id)

    # 1. Disponibilidad contradicha contra el stock real del catalogo.
    for d in VS.detectar_stock_contradicho(respuesta, ev):
        problemas.append(
            f"stock {d['clase']}: {d['nombre']} tiene stock real {d['stock']}")
    for c in VS.corregir_unidades_stock(respuesta, ev)["correcciones"]:
        problemas.append(
            f"cifra de stock {c['de']} distinta del real {c['a']} ({c['id']})")

    # 2. Promesas prohibidas (dia de entrega, retiro en local, servicio no
    #    ofrecido): el mismo detector de la guardia.
    for clase in GP.detectar(respuesta):
        problemas.append(f"promesa prohibida en la salida: {clase}")

    # 3. Marcador interno sin estampar.
    if "[[" in respuesta or "]]" in respuesta:
        problemas.append("marcador interno sin estampar en la salida")

    # 4. Precio de lista contradicho: cifra $ anclada por NOMBRE COMPLETO a UN
    #    producto que no es su precio real ni una cuenta declarada. El nombre
    #    completo es el ancla porque el estampado siempre lo imprime entero;
    #    contra el catalogo completo el ancla por tokens empata entre hermanos.
    tarifas = _tarifas_envio_conocidas(tienda_id)
    for m in _RE_MONTO.finditer(respuesta):
        ventana_previa = respuesta[max(0, m.start() - 30):m.start()]
        if _RE_CONTEXTO_CUENTA.search(ventana_previa):
            continue
        ventana = respuesta[max(0, m.start() - 110):m.start()].lower()
        nombrados = [p for p in ev
                     if (p.get("nombre") or "").strip()
                     and str(p["nombre"]).lower() in ventana
                     and isinstance(p.get("precio_ars"), (int, float))]
        if len(nombrados) != 1:
            continue
        # Si entre el nombre anclado y la cifra ya aparece OTRO monto, el ancla
        # no vale: aquel monto era el precio de ese producto y esta cifra es de
        # otra cosa ("...DX-110 Negro a $8.500. Y los Zeus X salen $57.500",
        # donde el nombre completo de los Zeus no esta en la ventana).
        nombre = str(nombrados[0]["nombre"]).lower()
        entre = ventana[ventana.rfind(nombre) + len(nombre):]
        if _RE_MONTO.search(entre):
            continue
        n = int(m.group(1).replace(".", ""))
        if n in tarifas:
            continue
        pr = int(nombrados[0]["precio_ars"])
        if pr != n and (pr == 0 or n % pr != 0):
            problemas.append(
                f"precio ${n} de {nombrados[0]['nombre']} no coincide con el "
                f"catalogo (${pr})")

    # 5. Narracion interna filtrada al cliente.
    if _RE_NARRACION.search(respuesta):
        problemas.append("narracion interna filtrada al cliente")

    # ── INVARIANTES DE COMPLETITUD (18-jul, tras cazar en logs reales que un
    #    presupuesto sin envio ni total pasaba como "limpio"). El juez de
    #    invariantes medía "no mintió"; ahora también mide "contestó completo".
    #    Todo text-only y conservador: solo dispara con senal fuerte.

    # 6. Presupuesto incompleto: si hay estructura de presupuesto (varias lineas
    #    de producto con precio, o el rotulo Subtotal), TIENE que cerrar con un
    #    Total. Un presupuesto que lista items y no da el total es el bug real de
    #    la conversacion 2 (envio y total tragados por presupuesto_sin_marcador).
    _lineas_prod = re.findall(r"^\s*[-•]\s*\d+\s*[xX].*\$", respuesta, re.M)
    _hay_presup = bool(re.search(r"(?im)^\s*subtotal\s*:", respuesta)) or \
        len(_lineas_prod) >= 1 and bool(re.search(r"(?i)presupuesto", respuesta))
    if _hay_presup:
        _tiene_total = bool(re.search(
            r"(?im)^\s*total\s*:\s*(?:\$?\s?\d|gratis|entre)", respuesta))
        if not _tiene_total:
            problemas.append("presupuesto incompleto: lista items pero no cierra "
                             "con un Total")

    # 7. Rotulo de cuenta con la cifra VACIA: "Envio: " / "Total: " / "Subtotal: "
    #    sin monto detras. Es el bug real de la conversacion 1 (Envio en blanco
    #    por destino fantasma). El codigo calculo pero no estampo el valor.
    for _m in re.finditer(r"(?im)^\s*(subtotal|total|env[ií]o[^:\n]*)\s*:\s*"
                          r"(.*)$", respuesta):
        _val = _m.group(2).strip()
        if not _val or not re.search(r"(?i)\d|gratis|entre|consult", _val):
            problemas.append(
                f"linea de cuenta vacia o sin monto: '{_m.group(1).strip()}:'")

    # 8. Respuesta CORTADA: termina en dos puntos, coma o un conector colgado,
    #    o justo despues del rotulo Presupuesto. Es truncamiento, el cliente
    #    recibe una frase a medias.
    _fin = respuesta.rstrip()
    if re.search(r"[:,]\s*$", _fin) or \
            re.search(r"(?i)\b(te cuento|presupuesto|el detalle|y|de|que|con|"
                      r"para|asi|entonces)\s*$", _fin):
        problemas.append("respuesta cortada: termina en conector o rotulo colgado")

    # 9. Turno MUDO: sacado el saludo enlatado, no queda contenido con sustancia.
    #    Es el "solo saludo" que no contesta la pregunta del cliente.
    _sin_saludo = re.sub(
        r"(?i)¡?\s*hola!?\s*(soy el asistente autom[aá]tico[^.\n]*\.?\s*"
        r"(te ayudo con[^.\n]*\.?)?)?", "", respuesta).strip()
    if len(re.sub(r"[\s.,¡!¿?]", "", _sin_saludo)) < 12:
        problemas.append("turno mudo: solo saludo, sin contestar")

    # 10. DOBLE PREGUNTA DE CIERRE (banco 19-jul): dos preguntas de confirmacion
    #     en la misma respuesta ("¿Lo dejamos confirmado?" + "¿Seguimos adelante
    #     con tu pedido?") suenan roboticas: el cierre pregunta UNA vez.
    if len(_RE_PREGUNTA_CIERRE.findall(respuesta)) >= 2:
        problemas.append("doble pregunta de cierre en la misma respuesta")

    # 11. ENVIOS PERDIDOS (charla real 19-jul, trace 8507a0b6): el cliente
    #     declaro N destinos REALES (validados contra la tabla geo) y el
    #     presupuesto cobra menos envios ("tres destinos" -> "2 envios").
    #     Solo con presupuesto sobre la mesa, para no acusar charla previa.
    if mensaje and re.search(r"(?im)^\s*total\s*:", respuesta):
        from app.core.guia_pedido import _hitos_destinos, _norm as _gnorm
        n_decl = len(_hitos_destinos(_gnorm(mensaje)))
        if n_decl >= 2:
            m_env = re.search(r"\((\d+)\s+env[ií]os\)", respuesta)
            n_resp = (int(m_env.group(1)) if m_env
                      else 1 if re.search(r"(?im)^\s*env[ií]o\s*:", respuesta)
                      else None)
            if n_resp is not None and n_resp < n_decl:
                problemas.append(
                    f"envios perdidos: el mensaje declara {n_decl} destinos "
                    f"y el presupuesto cobra {n_resp}")

    return problemas


def juzgar_charla(respuestas: list[str]) -> list[str]:
    """Invariantes de la CHARLA entera, lo que ningun turno suelto muestra.
    Hoy uno solo: la COLETILLA REPETIDA (corrida 19-jul, guion 45: la misma
    linea de cierre salio identica en 4/4 turnos, robotica). Conservador: la
    MISMA linea final, normalizada, en 3 o mas respuestas."""
    problemas: list[str] = []
    finales: dict[str, int] = {}
    for r in respuestas or []:
        lineas = [l.strip() for l in (r or "").splitlines() if l.strip()]
        if not lineas:
            continue
        fin = re.sub(r"\s+", " ", lineas[-1].lower())
        finales[fin] = finales.get(fin, 0) + 1
    for fin, n in finales.items():
        if n >= 3:
            problemas.append(
                f"coletilla repetida en {n} turnos: '{fin[:70]}'")
    return problemas
