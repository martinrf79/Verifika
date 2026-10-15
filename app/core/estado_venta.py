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


# EL CLIENTE SOLTANDO EL CRITERIO. Hace falta porque el criterio es STICKY: se
# dice una vez y vale para todo el pedido, asi que sin una forma de soltarlo el
# sistema le arrastra al cliente una decision que acaba de aflojar. Es el mismo
# mensaje real del 12-ago: pidio "el mas barato" en un turno y dos turnos
# despues abrio con "el precio no seria tan importante".
_CRITERIO_LIBRE_RE = re.compile(
    r"(?:el\s+)?precio\s+no\s+(?:es|ser[ií]a|me)\s+(?:tan\s+|lo\s+)?"
    r"(?:importa\w*|relevante|problema)"
    r"|no\s+(?:me\s+)?importa\s+(?:el|tanto el)\s+precio"
    r"|da\s+igual\s+(?:el\s+)?precio|sin\s+importar\s+(?:el\s+)?precio",
    re.IGNORECASE)


# EL CLIENTE PIDIENDO SUMAR ALGO A LO QUE YA ARMO. Se lee del MENSAJE y con
# codigo, por el mismo motivo que el criterio de precio: tiene que ser
# determinista y no depender de que el modelo lo entienda ese dia.
#
# POR QUE HACE FALTA UNA SEÑAL PROPIA. El contrato con el modelo dice que
# `registrar_pedido` declara el pedido COMPLETO en cada turno, y sobre eso se
# apoya la poda: lo que estaba en el carrito y ya no aparece, sale. Es la regla
# correcta para una correccion -"dejame los dos mouse"- y es exactamente la
# equivocada para un agregado: en la charla real del 12-ago el cliente pidio
# "agrega un teclado" sobre un presupuesto de seis articulos, el modelo declaro
# UN teclado, y la cuenta salio con un solo renglon de $12.000 y tres envios de
# $24.000. Los seis articulos no los saco el cliente: se cayeron solos.
_RE_AGREGAR_AL_PEDIDO = re.compile(
    r"\b(?:agreg[aá]\w*|agregue\w*|a[ñn]ad[ií]\w*|a[ñn]ade\w*|sumal[eo]\b"
    r"|sumame\b|incorpor[aá]\w*|met[eé]l[eo]\b"
    r"|(?:tambi[eé]n|adem[aá]s)\s+(?:quiero|llevo|sumame|necesito|dame))\b",
    re.IGNORECASE)
# La negacion y el pedido de sacar mandan sobre el verbo de agregar: "no
# agregues nada mas", "saca el teclado y agrega el envio a la cuenta".
_RE_NO_AGREGAR = re.compile(
    r"\bno\s+(?:me\s+)?(?:agregues|agregue|sumes|a[ñn]adas|incorpores)\b"
    r"|\b(?:sac[aá]\w*|quit[aá]\w*|elimin[aá]\w*|borr[aá]\w*)\b",
    re.IGNORECASE)


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


def get_envio_localidades() -> list[str]:
    """Todas las localidades cotizadas con exito este turno, en orden. Las lee
    calculate_total para cobrar cada destino de un multi-destino con su tarifa."""
    return list(_envio_localidades.get() or [])


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
        # MEMORIA NEGATIVA (5-ago): lo que el cliente saco del pedido. Los
        # demas campos guardan lo que quiere; este es el unico que guarda lo
        # que dijo que NO, para que un producto retractado no reaparezca
        # cuando la charla se comprime y la negacion se pierde.
        "descartados": conv.get("descartados") or [],
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


# ── RECHAZO / EDICION DE PEDIDO (11-jul, banco: guiones 09 y 28) ─────────────
# "Los auriculares dejalos", "el auricular no, sacalo": antes el turno
# re-ofrecia las mismas opciones o caia al fallback. El rechazo se detecta
# determinista y: con carrito, se QUITA el item y se recalcula sellado; sin
# carrito, el compositor reconoce el descarte en vez de insistir.

_RE_RECHAZO = re.compile(
    r"no me convence|no me gusta|mejor no\b|descartal|sacal[oa]s?\b"
    r"|no l[oa]s? quiero|ya no quiero|dejal[oa]s\b", re.IGNORECASE)


# Asignacion PARCIAL de destino (11-jul, guion 29: "una parte va a Rafaela,
# un teclado y un mouse van ahi" pisaba el pedido de 3+2 con uno de 1+1).
_RE_ASIGNA_DESTINO = re.compile(
    r"una parte|el resto|van? ah[ií]\b|van? all[aá]\b|parte va", re.IGNORECASE)

