"""
COMPOSITOR — el modelo NUNCA le escribe al cliente. (Decision de Martin, 8-jul.)

REEMPLAZA al solver de texto libre en el camino vivo. Semanas de corregir la
prosa del LLM probaron que corregir texto libre es una guerra imposible: cada
charla real produce una variacion nueva. Los numeros ya estaban sellados; la
CONDUCTA del texto libre era la fuga. Se elimina la clase entera de error:

  - UNA llamada al LLM por turno: el INTERPRETE constreñido (schema estricto,
    la unica pieza que jamas aluciono en real; banco 16/16). Devuelve SOLO
    datos: intencion, producto, pedido, candidatos, estado.
  - El CODIGO compone el 100% del mensaje: plantillas cortas en la voz de la
    tienda + curadas aprobadas + datos sellados de las tools. La alucinacion
    conversacional queda materialmente imposible.

El resto del pipeline (estampado, verificadores, guardias, cierre, memoria)
queda como cinturon: audita igual, pero ya no tiene prosa libre que corregir.

Composicion por SECCIONES: un turno puede responder varias cosas (producto +
envio + politica) concatenando bloques, con UN solo gancho al final. Cada
seccion sale de una fuente determinista; si ninguna seccion aplica, sale el
fallback cordial fijo (nunca texto inventado).
"""
import re
import unicodedata

from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _linea(p: dict) -> str:
    from app.core.interprete_libre import _linea_producto
    return _linea_producto(p)


def _registrar(meta: dict, name: str, result: dict, args: dict | None = None):
    """Anota una tool determinista en meta.tools_called con su proof, para que
    evidencia, carrito, presupuesto y persistencia fluyan como siempre."""
    entrada = {"name": name, "args": args or {}, "result": result}
    if isinstance(result, dict) and result.get("proof"):
        entrada["proof"] = result["proof"]
    meta.setdefault("tools_called", []).append(entrada)


# ── Detectores de tema del mensaje (cerrados) ────────────────────────────────
_RE_QUIERE_ENVIO = re.compile(
    r"env[ií]o|envio|llega|llegan|mandan|codigo postal|\bcp\b|tarifa")
_RE_QUIERE_TOTAL = re.compile(
    r"\btotal\b|cuanto (sale|queda|es) todo|\bpresupuesto\b|sumal[eo]|en total")
_RE_QUIERE_PRECIO = re.compile(
    r"cuanto (sale|cuesta|vale|esta)|\bprecio\b|\bsale\b|\bvale\b")
_RE_QUIERE_STOCK = re.compile(r"\bstock\b|unidades|\bhay\b|\btenes\b|\btienen\b")


def _gancho(texto: str, gancho: str) -> str:
    """Un solo cierre por mensaje: agrega el gancho solo si el texto todavia
    no pregunta nada."""
    if "?" in texto or "¿" in texto:
        return texto
    return texto + "\n\n" + gancho


# ── Secciones ────────────────────────────────────────────────────────────────

def _sec_saludo_puro(interp: dict, tienda_id: str) -> str | None:
    """Saludo sin pedido: bienvenida corta + que vendemos (categorias reales).
    La linea 'soy el asistente automatico' la antepone el saludo inicial."""
    if interp.get("intencion") != "saludo":
        return None
    from app.storage.firestore_client import get_categories
    cats = list(get_categories(tienda_id=tienda_id) or [])[:8]
    lista = ", ".join(str(c) for c in cats) if cats else "tecnologia y gaming"
    return (f"Trabajamos {lista} y más. "
            "¿Qué estás buscando? Si me decís el producto o la categoría te "
            "paso precios y stock al instante.")


def _resolver_producto(nombre: str, tienda_id: str) -> dict | None:
    from app.core.interprete_libre import _resolver_nombre_a_producto
    from app.storage.firestore_client import get_all_products
    return _resolver_nombre_a_producto(nombre, get_all_products(tienda_id=tienda_id))


def _sec_producto(mensaje: str, interp: dict, estado: dict,
                  tienda_id: str, meta: dict) -> str | None:
    """Ficha del producto puntual: linea real + descripcion del catalogo.
    Con candidatos multiples, pregunta A/B con las variantes reales."""
    m = _norm(mensaje)
    resuelto = str(interp.get("producto_resuelto") or "").strip()
    cands = [str(c) for c in (interp.get("candidatos") or []) if str(c).strip()]

    if resuelto:
        p = _resolver_producto(resuelto, tienda_id)
        if p:
            _registrar(meta, "get_product_details",
                       {"encontrado": True, "producto": p},
                       {"product_id": p.get("id")})
            partes = [_linea(p)]
            desc = str(p.get("descripcion") or "").strip()
            if desc and not _RE_QUIERE_PRECIO.search(m):
                partes.append(desc[:220])
            elif desc:
                partes.append(desc[:140])
            if p.get("stock", 0) <= 0:
                partes.append("Ahora mismo está sin stock; si querés te "
                              "muestro una alternativa parecida con stock.")
            return "\n".join(partes)
    if len(cands) >= 2:
        lineas = []
        for c in cands[:3]:
            p = _resolver_producto(c, tienda_id)
            if p:
                lineas.append("- " + _linea(p))
        if len(lineas) >= 2:
            return ("Tengo estas opciones y no quiero errarle:\n"
                    + "\n".join(lineas) + "\n¿Cuál preferís?")
    return None


def _sec_categoria(mensaje: str, interp: dict, tienda_id: str) -> str | None:
    """Listado de una categoria consultada ('tenes mouse?'): opciones reales
    CON stock, de la mas barata para arriba."""
    from app.core.guia_pedido import opciones_por_categoria
    from app.storage.firestore_client import get_categories
    m = _norm(mensaje)
    palabras = {w[:-1] if len(w) > 3 and w.endswith("s") else w
                for w in m.split()}
    cat_hit = None
    for c in (get_categories(tienda_id=tienda_id) or []):
        cn = _norm(c)
        if cn in palabras or (cn[:-1] if cn.endswith("s") else cn) in palabras:
            cat_hit = str(c)
            break
    if not cat_hit:
        return None
    ops = opciones_por_categoria(cat_hit, tienda_id, k=4)
    if not ops:
        return (f"De {cat_hit} justo estamos sin stock ahora. "
                "¿Te muestro otra categoría?")
    lineas = "\n".join("- " + _linea(p) for p in ops)
    return (f"De {cat_hit} tengo, de lo más económico para arriba:\n{lineas}")


def _sec_mas_barato(mensaje: str, interp: dict, estado: dict, tienda_id: str,
                    meta: dict) -> str | None:
    """'El mas barato': lo computa el codigo, problema cerrado. El criterio lo
    leen los DOS interpretes (regex + LLM), asi 'lo mas eco' tambien dispara.
    Aca solo se MUESTRA el mas barato (informativo, sin sellar un total), por
    eso alcanza con que UNO de los dos lo vea."""
    from app.core.estado_venta import concordancia_criterio
    if not concordancia_criterio(mensaje, interp):
        return None
    from app.core.guia_compra import mas_barato_con_stock, _categorias_en_juego
    from app.core.tools_context import set_current_tienda
    set_current_tienda(tienda_id)
    cats = _categorias_en_juego(mensaje, estado.get("productos_vistos"))
    p = mas_barato_con_stock(cats[0] if cats else None)
    if not p:
        return None
    _registrar(meta, "search_products",
               {"encontrados": 1, "productos": [p]}, {"query": "mas barato"})
    return ("El más barato con stock es:\n- " + _linea(p))


def _sec_envio(mensaje: str, estado: dict, tienda_id: str,
               meta: dict) -> str | None:
    """Tarifa de envio: cotiza deterministamente la localidad del mensaje o la
    de memoria; sin zona resoluble, pide la provincia con el texto oficial."""
    m = _norm(mensaje)
    if not _RE_QUIERE_ENVIO.search(m):
        return None
    from app.core.tools import cotizar_envio
    from app.core.guia_pedido import cotizar_destinos_del_mensaje
    from app.core.tools_context import set_current_tienda
    set_current_tienda(tienda_id)
    destinos = cotizar_destinos_del_mensaje(mensaje)
    if not destinos:
        # el mensaje entero como localidad (cubre 'llega a Neuquen capital?')
        q = cotizar_envio(localidad=mensaje)
        if q.get("ok"):
            _registrar(meta, "cotizar_envio", q, {"localidad": mensaje})
            monto = q.get("monto")
            costo = "gratis" if monto in (0, None) and q.get(
                "concepto") == "envio_gratis" else f"${monto:,}".replace(",", ".")
            zona = str(q.get("provincia") or q.get("zona") or "tu zona")
            return (f"El envío a {zona.replace('_', ' ')} sale {costo}. "
                    "Superando los $250.000 el envío va gratis. "
                    "Envío orientativo, puede variar al confirmar la compra.")
        loc_mem = (estado.get("localidad_envio") or "").strip()
        if not loc_mem:
            return ("Llegamos a todo el país. Pasame tu provincia o código "
                    "postal y te digo la tarifa exacta. Superando los "
                    "$250.000 el envío va gratis.")
        return None
    partes = []
    for d in destinos:
        q = cotizar_envio(localidad=d)
        if q.get("ok"):
            _registrar(meta, "cotizar_envio", q, {"localidad": d})
            monto = q.get("monto")
            costo = ("gratis" if monto in (0, None) else
                     f"${monto:,}".replace(",", "."))
            partes.append(f"- Envío a {d}: {costo}")
    if not partes:
        return None
    return ("Envíos cotizados:\n" + "\n".join(partes)
            + "\nEnvío orientativo, puede variar al confirmar la compra.")


def _sec_faq(mensaje: str, interp: dict, tienda_id: str,
             meta: dict) -> str | None:
    """Politica de la tienda: SIEMPRE la curada oficial estampada. Sin las
    restricciones del atajo viejo: aca no hay solver con quien pisarse."""
    from app.storage.firestore_client import get_all_faq
    from app.core.tools import _faq_ranking_palabras
    from app.core.curadas import estampar_valores
    faq = get_all_faq(tienda_id=tienda_id) or {}
    ranking = _faq_ranking_palabras(mensaje or "", faq)
    if not ranking:
        return None
    tema = ranking[0][1]
    data = faq.get(tema) or {}
    texto = str(data.get("respuesta_curada") or "").strip()
    if not texto:
        texto = str(data.get("respuesta") or "").strip()
        return texto or None
    estampada = estampar_valores(texto, data)
    if estampada:
        _registrar(meta, "query_faq",
                   {"encontrada": True, "tema": tema,
                    "respuesta": estampada, "ok": True}, {"consulta": mensaje})
    return estampada


# Plantillas de las MOVIDAS de venta (las curadas B, ahora texto del codigo).
# Movidas de venta con texto FIJO del codigo (las curadas B que no dependen de
# una FAQ). Constante de modulo: el test de coherencia del router la lockea.
_MOVIDAS_FIJAS = {
        "B4": ("Te entiendo, a todos nos gusta pagar menos. La forma real de "
               "bajarlo es pagando por transferencia: tenés 10% de descuento "
               "sobre el total. ¿Te armo el presupuesto así lo ves?"),
        "B5": ("Entiendo que quieras comparar. Nuestros precios son finales "
               "con garantía oficial y envío a todo el país, y por "
               "transferencia bajan un 10%. ¿Avanzamos?"),
        "B11": ("Tranquilo, pensalo con calma. Lo que estuvimos viendo te "
                "queda anotado y cuando quieras lo cerramos en un minuto. "
                "Acá estoy."),
        "B17": ("Te pido disculpas por la mala experiencia, tenés razón en "
                "molestarte. Contame puntualmente qué pasó y lo resuelvo "
                "ahora; si hace falta te paso con una persona del equipo."),
        "B18": ("Sí, te lo digo derecho: soy el asistente automático de la "
                "tienda. Puedo resolverte precios, stock y envíos al "
                "instante, y si preferís hablar con una persona del equipo "
                "te derivo. ¿Cómo seguimos?"),
        "B19": ("Listo, queda cancelado, sin problema. Cuando necesites algo "
                "estamos acá. ¡Que andes bien!"),
        "B22": ("Por este canal no puedo mandarte fotos, pero te paso el "
                "detalle completo de la ficha de lo que estés mirando. "
                "¿Qué producto era?"),
}

# Movidas cuyo bloque oficial sale de la FAQ curada del tema.
_MOVIDAS_FAQ = ("B6", "B13", "B20", "B21", "B23")


def _sec_movida(mensaje: str, interp: dict, estado: dict, tienda_id: str,
                meta: dict) -> str | None:
    from app.core.ruteo_venta import rutear_venta
    d = rutear_venta(mensaje, interp, estado)
    cat = d.get("categoria")
    if not cat or d.get("accion") == "normal":
        return None

    def _curada_tema(tema: str) -> str | None:
        from app.storage.firestore_client import get_all_faq
        from app.core.curadas import estampar_valores
        data = (get_all_faq(tienda_id=tienda_id) or {}).get(tema) or {}
        texto = str(data.get("respuesta_curada") or data.get("respuesta")
                    or "").strip()
        if not texto:
            return None
        return estampar_valores(texto, data) or texto

    if cat == "B6":
        # Desconfianza ('¿es seguro?', 'las calidades son buenas?'): empatia
        # fija + la curada OFICIAL de confianza, no la tarifa de envio.
        oficial = _curada_tema("confianza_seguridad") or _curada_tema(
            "marcas_originales") or ""
        return ("Comprar sin ver da un poco de reparo, es normal, así que te "
                "lo digo con hechos:\n\n" + oficial).strip()

    faqmsg = _sec_faq(mensaje, interp, tienda_id, meta)
    if cat in _MOVIDAS_FIJAS:
        base = _MOVIDAS_FIJAS[cat]
        # Si hay curada de FAQ pertinente (queja de envios, garantia...), va
        # abajo como bloque oficial.
        if faqmsg and cat in _MOVIDAS_FAQ:
            return base + "\n\n" + faqmsg
        return base
    if cat in _MOVIDAS_FAQ and faqmsg:
        return faqmsg
    if d.get("accion") == "preguntar":
        return ("Quiero darte el dato justo y me falta una cosa: "
                "¿me confirmás exactamente qué producto o modelo estás "
                "mirando?")
    return None


def _fallback(estado: dict) -> str:
    pend = estado.get("pedido_categorias_pendiente") or []
    if pend:
        return ("Seguimos con tu pedido cuando quieras: decime los modelos "
                "que elegís, o escribí \"los más baratos\" y te armo el "
                "total al instante.")
    return ("Quiero ayudarte bien y no te terminé de entender. Contame qué "
            "producto o categoría buscás, o preguntame por envíos, pagos o "
            "garantía.")


# ── Composicion del turno ────────────────────────────────────────────────────
def componer(mensaje: str, interp: dict | None, estado: dict | None,
             tienda_id: str, trace_id: str | None = None) -> tuple[str, dict]:
    """El mensaje ENTERO del turno, armado por el codigo. Devuelve
    (texto, meta) con meta.tools_called para el resto del pipeline."""
    interp = interp if isinstance(interp, dict) else {}
    estado = estado if isinstance(estado, dict) else {}
    meta: dict = {"tools_called": []}

    secciones: list[str] = []
    usadas: list[str] = []

    def _add(nombre, texto):
        if texto:
            secciones.append(texto.strip())
            usadas.append(nombre)

    # Movidas emocionales/de politica dura primero: si hay queja, cancelacion
    # o pedido de humano, ese ES el turno (no se vende encima).
    movida = _sec_movida(mensaje, interp, estado, tienda_id, meta)
    from app.core.ruteo_venta import rutear_venta
    _ruteo = rutear_venta(mensaje, interp, estado)
    _cat_mov = _ruteo.get("categoria")
    _accion_mov = _ruteo.get("accion")
    if movida and _cat_mov in ("B6", "B17", "B18", "B19", "B11"):
        log.info("compositor_secciones", trace_id=trace_id,
                 secciones=[_cat_mov])
        return movida, meta

    _add("saludo", _sec_saludo_puro(interp, tienda_id))
    _add("producto", _sec_producto(mensaje, interp, estado, tienda_id, meta))
    if "producto" not in usadas:
        _add("mas_barato",
             _sec_mas_barato(mensaje, interp, estado, tienda_id, meta))
    if "producto" not in usadas and "mas_barato" not in usadas:
        _add("categoria", _sec_categoria(mensaje, interp, tienda_id))
    _add("envio", _sec_envio(mensaje, estado, tienda_id, meta))
    if "saludo" not in usadas:
        _add("faq", None if movida else _sec_faq(mensaje, interp, tienda_id, meta))
    if movida and _cat_mov not in ("B17", "B18", "B19", "B11"):
        # El "preguntar" generico ('¿que producto?') NO se apila sobre una
        # respuesta de datos: si ya salio ficha, mas barato, categoria, envio
        # o FAQ, esa es la respuesta. Solo va como fallback cuando nada mas
        # respondio (evita el 'mas barato + ¿que producto?' contradictorio).
        _hay_datos = any(u in usadas for u in
                         ("producto", "mas_barato", "categoria", "envio", "faq"))
        if not (_accion_mov == "preguntar" and _hay_datos):
            _add("movida", movida)

    if not secciones:
        log.info("compositor_secciones", trace_id=trace_id, secciones=["fallback"])
        return _fallback(estado), meta

    texto = "\n\n".join(secciones)
    # Un solo gancho al final si nadie pregunto todavia.
    if usadas == ["saludo"]:
        pass  # el saludo ya pregunta
    elif "producto" in usadas or "mas_barato" in usadas:
        texto = _gancho(texto, "¿Te lo sumo al pedido o querés ver algo más?")
    elif "categoria" in usadas:
        texto = _gancho(texto, "¿Cuál te muestro en detalle?")
    elif "envio" in usadas or "faq" in usadas:
        texto = _gancho(texto, "¿Qué producto estás mirando? Así te paso el "
                               "total con envío incluido.")
    log.info("compositor_secciones", trace_id=trace_id, secciones=usadas)
    return texto, meta
