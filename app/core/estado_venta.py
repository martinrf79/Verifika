"""
ESTADO DE VENTA — fuente unica de verdad del turno, accesible por todas las etapas.

Hasta ahora el estado de la venta vivia disperso: seis campos sueltos en el
documento de la conversacion (productos vistos, carrito, ultimo total, ultima
localidad, proofs) MAS los datos del cliente en un documento de lead aparte. Cada
etapa leia un pedazo distinto: el solver el bloque de venta, el cierre el lead, las
herramientas nada. Esa fragmentacion fue la causa de bugs como pedir la direccion
dos veces (el solver y el cierre no compartian la misma verdad).

Este modulo consolida todo en UN objeto `estado` que se construye una sola vez por
turno (desde la conversacion + el lead) y viaja por una contextvar, igual que la
tienda y el destino. Asi el interprete, el compositor, las herramientas
deterministas y el cierre leen la MISMA verdad sin recibirla por parametro.

Regla de escritura (una sola por dato): el significado lo escribe el interprete;
los numeros las herramientas con su PROOF; la redaccion el compositor. El estado
es de LECTURA para todos; cada dato lo actualiza solo su dueno.
"""
import re
from contextvars import ContextVar
from typing import Any

# Criterio de eleccion que el cliente deja dicho: "lo mas barato". Se detecta con
# codigo (no con el LLM) para que sea determinista y viaje por el estado. La raiz
# 'barat' cubre barato/barata/baratos/baratito; 'econom' cubre economico/economica.
_CRITERIO_BARATO_RE = re.compile(r"barat|econ[oó]mic", re.IGNORECASE)
# "Algo intermedio" o el RECHAZO explicito del minimo (caso real del banco
# 11-jul: "economicos pero no lo mas barato que haya" armaba los MAS baratos,
# lo contrario de lo pedido). Se chequea ANTES que el de barato: la negacion
# contiene la palabra 'barato' y sin el orden ganaria el criterio equivocado.
_CRITERIO_INTERMEDIO_RE = re.compile(
    r"intermedi|t[eé]rmino medio|gama media|del medio"
    r"|n[oi] (?:el |lo )?m[aá]s barat|ni tan barat", re.IGNORECASE)


def detectar_criterio(mensaje: str) -> str:
    """Criterio de precio que el cliente dejo dicho en el mensaje: 'más barato'
    o 'intermedio'. Devuelve '' si el mensaje no trae ninguno. Determinista: el
    mismo texto siempre da el mismo criterio, sin llamar a ningun modelo."""
    if _CRITERIO_INTERMEDIO_RE.search(mensaje or ""):
        return "intermedio"
    if _CRITERIO_BARATO_RE.search(mensaje or ""):
        return "más barato"
    return ""


def criterio_del_interprete(interp) -> bool:
    """El SEGUNDO interprete del criterio: la lectura del LLM. El regex de arriba
    no entiende 'eco' ni abreviaturas ni modismos; el interprete si (campo
    'criterio' del schema). True si el LLM leyo que el cliente quiere lo mas
    barato."""
    if not isinstance(interp, dict):
        return False
    return str(interp.get("criterio") or "").strip() == "mas_barato"


def criterio_llm(interp) -> str:
    """El criterio crudo que leyo el LLM: 'mas_barato', 'intermedio' o ''."""
    if not isinstance(interp, dict):
        return ""
    v = str(interp.get("criterio") or "").strip()
    return v if v in ("mas_barato", "intermedio") else ""


def concordancia_criterio(mensaje: str, interp) -> str:
    """DOS interpretes del criterio de precio (decision de Martin, 9-jul):
    el CODIGO (regex determinista) y el LLM (entiende 'eco', 'lo mas conveniente'
    y typos que el regex no cubre). Regla:
      - alguno lee INTERMEDIO -> 'intermedio' (proponer el del medio y
        confirmar; JAMAS armar los mas baratos: es lo contrario de lo pedido)
      - ambos leen barato     -> 'actuar'    (se arma sin preguntar)
      - solo uno lee barato   -> 'confirmar' (pregunta corta '¿los mas baratos?')
      - ninguno               -> ''          (no es un turno de criterio)
    Asi 'eco' se entiende sin listar sinonimos a mano, pero un disparo dudoso de
    UN solo interprete se confirma en vez de sellar un total que el cliente
    quiza no pidio. Generar > confirmar antes de comprometer plata."""
    cod = detectar_criterio(mensaje)
    llm = criterio_llm(interp)
    if "intermedio" in (cod, llm):
        return "intermedio"
    cod_b = cod == "más barato"
    llm_b = llm == "mas_barato"
    if cod_b and llm_b:
        return "actuar"
    if cod_b or llm_b:
        return "confirmar"
    return ""

_current_estado: ContextVar[dict | None] = ContextVar("current_estado", default=None)

# Localidades que cotizar_envio clasifico con exito en este turno, EN ORDEN. Es el
# puente entre las dos herramientas mellizas de envio: cotizar_envio (UNICA que
# calcula el costo) las escribe, y calculate_total las lee para pedirle a
# cotizar_envio el monto de CADA destino con el subtotal real, sin recalcular zona
# ni tarifa por su cuenta. Es una LISTA y no una sola: un pedido multi-destino
# cotiza varias localidades en el mismo turno y cada una cobra SU tarifa (antes se
# guardaba solo la ultima y dos destinos distintos cobraban dos veces la misma).
_envio_localidades: ContextVar[list | None] = ContextVar(
    "envio_localidades", default=None)

# Product_id que las tools DEVOLVIERON este turno (search, details, catalogo,
# calculadora): son los ids CERTIFICADOS del turno. La calculadora los usa para
# aplicar la regla cero mecanicamente: con un pedido vigente, un id que no sale
# ni del carrito, ni de lo ya mostrado, ni de una tool del turno es un id
# INFERIDO de memoria y muta la identidad del pedido en silencio.
_ids_certificados: ContextVar[set | None] = ContextVar(
    "ids_certificados", default=None)


def set_current_estado(estado: dict | None, inicio_turno: bool = True):
    """Setea el estado de venta del request. Al ARRANCAR el turno (default)
    limpia las localidades cotizadas del turno anterior. Un re-seteo a mitad
    de turno (el generador lo hace para sus tools) va con inicio_turno=False:
    antes borraba las cotizadas del propio turno y la memoria de destinos
    nunca persistia — el envio se caia del total al confirmar (agujero del
    12-jul, cerrado 20-jul con el guion 48)."""
    _current_estado.set(estado)
    if inicio_turno:
        _envio_localidades.set([])
        _ids_certificados.set(set())


def set_envio_localidad(localidad: str | None):
    """Suma la localidad que cotizar_envio clasifico bien este turno. Re-cotizar la
    misma localidad (el cliente corrige o el solver repite) no crea otro destino:
    se deduplica por texto y queda al final como la mas reciente."""
    loc = (localidad or "").strip()
    if not loc:
        return
    locs = [l for l in (_envio_localidades.get() or [])
            if l.lower() != loc.lower()]
    locs.append(loc)
    _envio_localidades.set(locs)


def get_envio_localidad() -> str | None:
    """Ultima localidad cotizada este turno, o None. Compatibilidad para quien
    necesita UNA sola (pedido de un destino)."""
    locs = _envio_localidades.get() or []
    return locs[-1] if locs else None


def get_envio_localidades() -> list[str]:
    """Todas las localidades cotizadas con exito este turno, en orden. Las lee
    calculate_total para cobrar cada destino de un multi-destino con su tarifa."""
    return list(_envio_localidades.get() or [])


def certificar_ids_de_resultado(result):
    """Registra los product_id que una tool devolvio este turno. Lo llama el
    loop del agente despues de CADA tool: un solo lugar cubre search, details,
    catalogo y calculadora (mismas claves que lee productos_de_meta)."""
    if not isinstance(result, dict):
        return
    ids = _ids_certificados.get()
    if ids is None:
        ids = set()
        _ids_certificados.set(ids)
    cands = list(result.get("productos") or [])
    if isinstance(result.get("producto"), dict):
        cands.append(result["producto"])
    cands += list(result.get("detalle") or [])
    for p in cands:
        if isinstance(p, dict) and p.get("id"):
            ids.add(str(p["id"]).upper())


def get_ids_certificados() -> set:
    """Los product_id certificados por tools en este turno (copia)."""
    return set(_ids_certificados.get() or set())


def get_current_estado() -> dict:
    """Devuelve el estado de venta del request, o un dict vacio si no se seteo
    (ej tests que llaman una tool suelta). Nunca None, para leer sin guardas."""
    return _current_estado.get() or {}


def _money(n: Any) -> str:
    """Entero a formato argentino con separador de miles: 48000 -> '48.000'."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(n)


def productos_de_meta(meta: dict) -> list[dict]:
    """Productos que las tools mostraron este turno (id, nombre, precio REAL), desde
    el catalogo y el detalle de la calculadora. El precio sale verbatim de la tool,
    nunca del texto del solver. Lo escribe la herramienta, no el modelo."""
    vistos: dict[str, dict] = {}
    for tc in (meta or {}).get("tools_called", []) or []:
        res = tc.get("result")
        if not isinstance(res, dict):
            continue
        cands = list(res.get("productos") or [])
        if isinstance(res.get("producto"), dict):
            cands.append(res["producto"])
        cands += list(res.get("detalle") or [])
        for p in cands:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("id") or "").upper()
            precio = p.get("precio_ars")
            if precio is None:
                precio = p.get("precio_unitario")
            nombre = p.get("nombre")
            if pid and nombre and isinstance(precio, (int, float)):
                vistos[pid] = {"id": pid, "nombre": nombre, "precio": int(precio)}
    return list(vistos.values())


def carrito_de_meta(meta: dict) -> list[dict]:
    """Items del ultimo calculate_total que cerro bien (id, nombre, cantidad), para
    que el pedido no pierda identidad entre turnos."""
    for tc in reversed((meta or {}).get("tools_called", []) or []):
        if tc.get("name") != "calculate_total":
            continue
        res = tc.get("result")
        if not isinstance(res, dict) or res.get("ok") is False or not res.get("detalle"):
            continue
        items = [{"id": d["id"], "nombre": d.get("nombre", ""),
                  "cantidad": d.get("cantidad", 1)}
                 for d in res["detalle"] if isinstance(d, dict) and d.get("id")]
        if items:
            return items
    return []


def envio_de_meta(meta: dict) -> str:
    """Zona/provincia y costo del ultimo cotizar_envio que cerro bien, como texto
    listo para el estado. '' si no se cotizo nada valido este turno."""
    for tc in reversed((meta or {}).get("tools_called", []) or []):
        if tc.get("name") != "cotizar_envio":
            continue
        res = tc.get("result")
        if not isinstance(res, dict) or not res.get("ok"):
            continue
        zona = res.get("provincia") or res.get("zona") or "esa zona"
        zona = str(zona).replace("_", " ")
        if res.get("modalidad") == "rango":
            costo = (f"entre ${_money(res.get('monto_min'))} y "
                     f"${_money(res.get('monto_max'))}")
        else:
            m = res.get("monto", 0)
            costo = "gratis" if m in (0, None) else f"${_money(m)}"
        return f"{zona}: {costo}"
    return ""


def merge_productos(memoria: list[dict], turno: list[dict],
                    tope: int = 60) -> list[dict]:
    """Une los productos vistos en memoria con los del turno, deduplicando por id (el
    dato del turno pisa al viejo) y dejando los ultimos `tope`.

    Tope 60 (era 20): un solo turno de tres busquedas trae 30 productos y el tope
    viejo TIRABA la primera categoria entera (visto 8-jul: las notebooks caian de
    la memoria y el enum del interprete no podia referenciarlas, asi que el pedido
    extraido salia sin notebook y con el mouse duplicado)."""
    por_id: dict[str, dict] = {}
    for p in (memoria or []) + (turno or []):
        pid = str(p.get("id") or "").upper()
        if pid:
            por_id[pid] = p
    return list(por_id.values())[-tope:]


def construir_estado(conv: dict | None, lead: dict | None) -> dict:
    """Arma el objeto estado del turno desde la conversacion persistida y el lead
    activo. Consolida en un solo lugar lo que antes se leia de seis campos sueltos
    mas el documento de lead. Defensivo: tolera dicts vacios o None."""
    conv = conv or {}
    datos_cliente = {}
    if lead:
        for campo in ("nombre", "telefono", "direccion", "forma_pago"):
            v = str(lead.get(campo, "") or "").strip()
            if v:
                datos_cliente[campo] = v
    return {
        "productos_vistos": conv.get("productos_vistos") or [],
        "carrito": conv.get("carrito_vigente") or [],
        "presupuesto": (conv.get("ultimo_presupuesto") or "").strip(),
        "localidad_envio": (conv.get("ultima_localidad") or "").strip(),
        "localidades_envio": conv.get("ultimas_localidades") or [],
        "provincia_envio": (conv.get("provincia_envio") or "").strip(),
        "criterio": (conv.get("criterio_cliente") or "").strip(),
        "datos_cliente": datos_cliente,
        # Memoria larga: el resumen acumulado de la charla que ya salio del
        # historial vivo (turnos viejos fundidos). Contexto, no fuente de datos.
        "resumen_charla": (conv.get("summary") or "").strip(),
        # ANCLA del producto que el cliente eligio y pidio guardar ("me gusta
        # X, anotalo"). {id, nombre, precio} o {}. Resuelve "el que te dije
        # al principio" sin adivinar (falla madre del banco 11-jul).
        "producto_anotado": (conv.get("producto_anotado")
                             if isinstance(conv.get("producto_anotado"), dict)
                             else {}) or {},
        # PREFERENCIAS del cliente (16-jul): exclusiones por origen/marca, tope
        # de presupuesto y uso previsto, leidas por el interprete y STICKY entre
        # turnos como la provincia. Las consume el generador para filtrar el
        # universo por construccion.
        "preferencias": (conv.get("preferencias_cliente")
                         if isinstance(conv.get("preferencias_cliente"), dict)
                         else {}) or {},
        # GRUPOS DE ENVIO declarados por el cliente (que item va a cada
        # destino): memoria de la charla, el reprecio del cierre los reusa
        # para el umbral de gratis por paquete (20-jul, guion 48).
        "grupos_envio": (conv.get("grupos_envio")
                         if isinstance(conv.get("grupos_envio"), list)
                         else []) or [],
    }


_RE_LIMPIA_PREFERENCIAS = re.compile(
    r"no importa (la marca|el origen|de donde)|cualquier marca|da igual la marca"
    r"|me da igual (la marca|el origen)", re.IGNORECASE)


def preferencias_actualizadas(previas: dict | None, interp: dict | None,
                              mensaje: str = "") -> dict:
    """Merge sticky de las preferencias del cliente: las exclusiones se ACUMULAN
    (dedup por tipo+valor), tope y uso los pisa el ultimo dicho. Una frase que
    las suelta ('no importa la marca', 'cualquier marca') limpia las
    exclusiones. Devuelve dict listo para persistir; {} si no hay nada."""
    prefs = dict(previas or {}) if isinstance(previas, dict) else {}
    interp = interp if isinstance(interp, dict) else {}
    if _RE_LIMPIA_PREFERENCIAS.search(mensaje or ""):
        prefs.pop("exclusiones", None)
    exc_prev = [e for e in (prefs.get("exclusiones") or [])
                if isinstance(e, dict) and e.get("valor")]
    vistas = {(str(e.get("tipo")), str(e.get("valor")).strip().lower())
              for e in exc_prev}
    for e in (interp.get("exclusiones") or []):
        clave = (str(e.get("tipo")), str(e.get("valor") or "").strip().lower())
        if clave[1] and clave not in vistas:
            exc_prev.append({"tipo": clave[0], "valor": str(e["valor"]).strip()})
            vistas.add(clave)
    if exc_prev:
        prefs["exclusiones"] = exc_prev
    if interp.get("tope_presupuesto"):
        prefs["tope_presupuesto"] = int(interp["tope_presupuesto"])
    if interp.get("uso_previsto"):
        prefs["uso_previsto"] = str(interp["uso_previsto"]).strip()
    return {k: v for k, v in prefs.items() if v}



# ── ANCLA DE PRODUCTO ANOTADO (11-jul, falla madre del banco) ────────────────
# El cliente elige un producto y pide guardarlo ("me gusta el M170, anotalo");
# diez turnos despues cierra con "el que te mencione al principio". Antes ese
# ancla no existia: el cierre listaba todo de nuevo o acertaba de casualidad
# (si el elegido era el mas barato). Tres piezas deterministas:
#   - deteccion de ANOTAR este turno (regex + candidato unico del interprete)
#   - deteccion de REFERENCIA a lo anotado (regex de memoria)
#   - actualizacion del ancla persistida (nuevo ancla / limpieza por negacion)

_RE_ANOTAR = re.compile(
    r"anotal[oa]\b|\banota\b|dejal[oa] anotado|me gusta\b|me interesa\b"
    r"|me quedo con\b|quiero ese\b|ese quiero\b", re.IGNORECASE)
_RE_REF_ANOTADO = re.compile(
    r"que te (dije|mencione|mencioné|nombre|nombré|anote|anoté|pedi|pedí)"
    r"|al principio|al comienzo|el anotado|el que anotaste|el que elegi"
    r"|el que elegí|el de antes\b", re.IGNORECASE)
_RE_QUITAR_ANOTADO = re.compile(
    r"sacal[oa]\b|no l[oa] quiero|ya no l[oa] quiero|cancelal[oa]\b"
    r"|olvidal[oa]\b|dejal[oa]s\b", re.IGNORECASE)
_RE_PEDIDO_ANOTADO = re.compile(
    r"\btotal\b|cerra|cerremos|cerrame|comprar|lo llevo|lo compro"
    r"|confirmo|presupuesto|armame", re.IGNORECASE)


def _norm_ancla(s) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c)).strip()


def _variantes_singular(tok: str) -> list[str]:
    """El token y sus singulares castellanos simples: auriculares ->
    [auriculares, auricular, auriculare]. Para que 'el auricular' matchee
    el nombre en plural del catalogo."""
    out = [tok]
    if len(tok) > 4 and tok.endswith("es"):
        out.append(tok[:-2])
    if len(tok) > 3 and tok.endswith("s"):
        out.append(tok[:-1])
    return out


def _nombre_en_mensaje(nombre: str, mensaje: str) -> bool:
    """True si algun token distintivo del nombre (largo > 3, no generico) esta
    en el mensaje, tolerando singular/plural. Para la LIMPIEZA del ancla:
    'el mouse no, sacalo' limpia el mouse anotado; 'los auriculares dejalos'
    NO toca un mouse anotado."""
    m = _norm_ancla(mensaje)
    for tok in _norm_ancla(nombre).split():
        if len(tok) <= 3:
            continue
        if any(v in m for v in _variantes_singular(tok)):
            return True
    return False


def aplicar_ancla_producto(interp: dict, mensaje: str, estado: dict,
                           catalogo: list) -> str:
    """Muta interp con el ancla, en dos direcciones. Devuelve el evento ('' si
    no hizo nada):
      - 'anotado': el cliente elige/anota este turno y el interprete no
        resolvio producto pero dejo UN candidato que reconcilia unico ->
        producto_resuelto se completa (el compositor muestra la ficha en vez
        del fallback 'no te entendi').
      - 'referencia': el mensaje referencia lo anotado ('el que te dije al
        principio') sin resolver producto -> producto_resuelto = el ancla, y
        si ademas pide total/cierre, el pedido se arma con ese producto para
        que la guia selle el presupuesto real."""
    if not isinstance(interp, dict):
        return ""
    from app.core.interprete_libre import _resolver_nombre_a_producto
    estado = estado if isinstance(estado, dict) else {}
    m = _norm_ancla(mensaje)

    # Referencia a lo anotado: el ancla persistida manda.
    ancla = estado.get("producto_anotado") or {}
    if (ancla.get("nombre") and _RE_REF_ANOTADO.search(m)
            and not str(interp.get("producto_resuelto") or "").strip()
            and not (interp.get("pedido") or [])):
        interp["producto_resuelto"] = ancla["nombre"]
        if _RE_PEDIDO_ANOTADO.search(m):
            interp["pedido"] = [{"producto": ancla["nombre"], "cantidad": 1,
                                 "destino": None}]
            try:
                conf = float(interp.get("confianza") or 0)
            except (TypeError, ValueError):
                conf = 0.0
            interp["confianza"] = max(conf, 0.7)
        return "referencia"

    # Anotar este turno: candidato unico + palabras de eleccion.
    if (_RE_ANOTAR.search(m)
            and not str(interp.get("producto_resuelto") or "").strip()):
        cands = [str(c) for c in (interp.get("candidatos") or [])
                 if str(c).strip()]
        if len(cands) == 1:
            p = _resolver_nombre_a_producto(cands[0], catalogo)
            if isinstance(p, dict) and p.get("nombre"):
                interp["producto_resuelto"] = p["nombre"]
                return "anotado"
    return ""


def producto_anotado_actualizado(previo: dict | None, interp: dict,
                                 mensaje: str, catalogo: list) -> dict:
    """El ancla que se PERSISTE al final del turno. Regla conservadora:
      - producto_resuelto del turno (ya pasado por aplicar_ancla_producto)
        que reconcilia unico con el catalogo -> nuevo ancla, salvo intencion
        'otra' (rechazo/off-topic no ancla).
      - negacion sobre el anotado ('el mouse no, sacalo') -> se limpia, SOLO
        si el mensaje nombra un token distintivo del ancla (no se limpia por
        rechazar OTRO producto).
      - si no, queda el previo."""
    previo = previo if isinstance(previo, dict) else {}
    interp = interp if isinstance(interp, dict) else {}
    if (previo.get("nombre") and _RE_QUITAR_ANOTADO.search(mensaje or "")
            and _nombre_en_mensaje(previo["nombre"], mensaje)):
        return {}
    if str(interp.get("intencion") or "") == "otra":
        return previo
    resuelto = str(interp.get("producto_resuelto") or "").strip()
    if not resuelto:
        return previo
    # Solo ancla una ELECCION: palabras de anotar/elegir en el mensaje o una
    # intencion de compra/aporte. Una pregunta suelta sobre OTRO producto
    # ("¿cuanto sale el DX-110?") no pisa el ancla del elegido.
    if not (_RE_ANOTAR.search(mensaje or "")
            or str(interp.get("intencion") or "") in
            ("decision_compra", "aporta_dato")):
        return previo
    from app.core.interprete_libre import _resolver_nombre_a_producto
    p = _resolver_nombre_a_producto(resuelto, catalogo)
    if isinstance(p, dict) and p.get("id") and p.get("nombre"):
        try:
            precio = int(p.get("precio_ars") or 0)
        except (TypeError, ValueError):
            precio = 0
        return {"id": str(p["id"]).upper(), "nombre": str(p["nombre"]),
                "precio": precio}
    return previo


# ── RECHAZO / EDICION DE PEDIDO (11-jul, banco: guiones 09 y 28) ─────────────
# "Los auriculares dejalos", "el auricular no, sacalo": antes el turno
# re-ofrecia las mismas opciones o caia al fallback. El rechazo se detecta
# determinista y: con carrito, se QUITA el item y se recalcula sellado; sin
# carrito, el compositor reconoce el descarte en vez de insistir.

_RE_RECHAZO = re.compile(
    r"no me convence|no me gusta|mejor no\b|descartal|sacal[oa]s?\b"
    r"|no l[oa]s? quiero|ya no quiero|dejal[oa]s\b", re.IGNORECASE)


def es_rechazo(mensaje: str) -> bool:
    """True si el mensaje descarta algo. 'Dejalo anotado' NO es rechazo."""
    m = str(mensaje or "")
    if _RE_ANOTAR.search(m) and "anotado" in _norm_ancla(m):
        return False
    return bool(_RE_RECHAZO.search(m))


def rechazados_del_carrito(carrito: list, mensaje: str,
                           catalogo: list) -> tuple[list, list]:
    """Separa el carrito en (quitados, restantes) segun el rechazo del
    mensaje. Un item se quita si el mensaje nombra un token distintivo de su
    NOMBRE o su CATEGORIA (singular). Sin rechazo detectado devuelve
    ([], carrito) intacto."""
    carrito = [c for c in (carrito or []) if isinstance(c, dict)]
    if not carrito or not es_rechazo(mensaje):
        return [], carrito
    m = _norm_ancla(mensaje)
    cat_por_id = {str(p.get("id") or "").upper(): _norm_ancla(p.get("categoria"))
                  for p in (catalogo or []) if isinstance(p, dict)}
    quitados, restantes = [], []
    for it in carrito:
        nombre = str(it.get("nombre") or "")
        cat = cat_por_id.get(str(it.get("id") or "").upper(), "")
        hit = _nombre_en_mensaje(nombre, mensaje) or (
            cat and any(v in m for v in _variantes_singular(cat)))
        (quitados if hit else restantes).append(it)
    return quitados, restantes


# Asignacion PARCIAL de destino (11-jul, guion 29: "una parte va a Rafaela,
# un teclado y un mouse van ahi" pisaba el pedido de 3+2 con uno de 1+1).
_RE_ASIGNA_DESTINO = re.compile(
    r"una parte|el resto|van? ah[ií]\b|van? all[aá]\b|parte va", re.IGNORECASE)


def es_asignacion_destino(mensaje: str) -> bool:
    """True si el mensaje reparte el pedido vigente entre destinos, en vez de
    pedir productos nuevos."""
    return bool(_RE_ASIGNA_DESTINO.search(mensaje or ""))


def cantidades_vigentes_por_categoria(carrito: list, pendiente_cats: list,
                                      catalogo: list) -> dict:
    """{categoria: cantidad} del pedido vigente: el carrito (con la categoria
    real del catalogo por id) o, sin carrito, el pendiente de categorias."""
    out: dict[str, int] = {}
    cat_por_id = {str(p.get("id") or "").upper(): _norm_ancla(p.get("categoria"))
                  for p in (catalogo or []) if isinstance(p, dict)}
    for it in (carrito or []):
        if not isinstance(it, dict):
            continue
        cat = cat_por_id.get(str(it.get("id") or "").upper())
        if cat:
            try:
                out[cat] = out.get(cat, 0) + int(it.get("cantidad") or 1)
            except (TypeError, ValueError):
                continue
    if out:
        return out
    for c in (pendiente_cats or []):
        if isinstance(c, dict) and c.get("categoria"):
            try:
                out[_norm_ancla(c["categoria"])] = int(c.get("cantidad") or 0)
            except (TypeError, ValueError):
                continue
    return out
