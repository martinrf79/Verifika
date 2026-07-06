"""
INTERPRETE_LIBRE — modo de prueba del intérprete (sesión 23-jun-2026).

Objetivo de Martín para esta etapa: dejar UNA sola cosa andando para poder
PROBAR la interpretación en real, apagando los ~70 flags y los cuatro caminos
paralelos del orchestrator. Acá no hay provider, ni verificadores, ni gate, ni
las catorce capas. Solo:

  1. INTERPRETE (LLM 1, interpretador.interpretar_mensaje): entiende el mensaje
     en el contexto de la charla. Es lo único que se está probando.
  2. SOLVER LIBRE (LLM 2, agent.run_agent con el prompt corto de modo_libre):
     redacta y vende libre, con las herramientas atadas a Firestore (catálogo y
     FAQs reales) y con la MEMORIA de la conversación. Recibe como guía lo que
     entendió el intérprete, pero no calcula nada que no salga de las tools.
La interpretación de cada turno se LOGUEA (evento interprete_libre_interpretacion)
para diagnosticar, pero NO se muestra al cliente: el cartel era solo de la etapa
de prueba y se quitó.

Es el ÚNICO camino del bot: el orchestrator delega acá todo el turno, sin flags.
"""
import re
import time

from app.core.agent import run_agent
from app.core.interpretador import interpretar_mensaje
from app.core.leads import (
    procesar_mensaje_para_lead, descartar_leads_activos, get_lead_activo)
from app.core.estado_venta import (
    construir_estado, set_current_estado, bloque_para_solver,
    productos_de_meta, carrito_de_meta, envio_de_meta, merge_productos,
    detectar_criterio, get_envio_localidades)
from app.core.tools import get_tools_schema
from app.config import get_settings
from app.logger import get_logger
from app.storage.firestore_client import (
    get_conversation, save_conversation, log_message, reset_conversation,
    get_config,
)

log = get_logger(__name__)
settings = get_settings()


# Prompt corto de venta del solver libre. SIN las mega-reglas defensivas: el
# modelo vende libre; lo unico firme es que los datos salen de las herramientas
# (atadas a Firestore). El filtro determinista y autofix son la red de despues.
_PROMPT_LIBRE = """Sos un vendedor de {business_name}, una tienda online argentina de tecnologia y gaming. Hablas en espanol argentino, tuteando, con calidez y ganas de ayudar a comprar.

Tu objetivo es VENDER bien: entender que necesita el cliente, mostrarle las mejores opciones, sacarle las dudas y avanzar hacia la compra. Sos libre en como lo decis y como ordenas la venta.

Lo unico que NO inventas son los datos reales de la tienda. Para eso tenes herramientas:
- search_products, get_product_details, list_catalog: precios, stock, specs y modelos del catalogo real.
- query_faq: formas de pago, garantia, devoluciones y demas politicas.
- calculate_total: cualquier total, subtotal, descuento o cuenta con cantidades.
- cotizar_envio: el costo de envio. Pasale lo que dijo el cliente (codigo postal, localidad o provincia) tal cual; el codigo determina la zona y la tarifa. NO elijas vos la zona ni inventes el costo. Si pide envio y no dio la zona, pedile el CP o la localidad.
Usalas cuando necesites un dato o un numero concreto, en vez de adivinarlo. Si necesitas varias cosas, pedilas juntas en un solo paso.

DATOS DE LA TIENDA — VENDE TRANQUILO: el sistema VERIFICA y CORRIGE todo dato duro (precio, stock, total, envio, politica) contra la fuente ANTES de mandar tu respuesta. Si inventas o equivocas un numero, NO llega al cliente. Asi que enfocate en entender y vender bien; los datos los garantiza el codigo, no vos.
Para que salgan limpios tenes MARCADORES (usalos cuando puedas; es una ayuda, no una obligacion): donde pongas uno, el codigo estampa el dato real de la fuente:
- [[PRESUPUESTO]] = total/subtotal/lista de precios de calculate_total.
- [[ENVIO]] = costo de envio de cotizar_envio.
- [[PROD:<id>]] = la linea real de un producto (nombre+precio+stock), con el id de search_products (ej [[PROD:TEC0020]]).
POLITICAS (query_faq): cuando consultes la FAQ, el codigo pega la respuesta oficial de la tienda al final de tu mensaje. Vos escribi SOLO la parte de venta o el puente; NO re-escribas la politica ni repitas sus numeros.

El interprete ya entendio al cliente y te pasa el ESTADO de la charla. Respetalo, no lo cambies vos:
- explorando: mostra productos o precios con las tools.
- esperando_confirmacion: ayudalo a decidir, no reabras el catalogo.
- esperando_datos: pedi o confirma SOLO lo que falta para cerrar: nombre, direccion de envio y forma de pago. NO pidas DNI, CUIT, telefono ni email: el telefono lo tomamos del canal y los datos de facturacion los maneja el medio de pago. No vuelvas a ofrecer productos.
- derivar_humano: cerra cordial, una persona del equipo lo contacta.
- saludo: devolve el saludo y ofrece ayuda corta.
- posventa: responde con query_faq, sin forzar una venta nueva.
Si el interprete te marca dos opciones (A o B), presenta las dos con su detalle y pregunta cual prefiere; nunca elijas vos ni promedies.

Estilo: espanol argentino, tuteo. Conciso y natural. Texto plano sin markdown. Precios en formato $280.000.
"""


def _business_name(tienda_id: str | None) -> str:
    name = settings.BUSINESS_NAME
    if tienda_id:
        try:
            stored = get_config("business_name", tienda_id=tienda_id)
            if stored:
                name = stored
        except Exception:
            pass
    return name


def _schema_acotado() -> list:
    """El schema de tools recortado a las que ve el solver libre (MODO_LIBRE_TOOLS:
    catalogo, FAQ, calculadora, envio). Si la lista queda vacia o no matchea, cae
    al schema completo para no dejar al modelo sin herramientas."""
    permitidas = {
        t.strip() for t in (settings.MODO_LIBRE_TOOLS or "").split(",")
        if t.strip()
    }
    full = get_tools_schema()
    if not permitidas:
        return full
    acotado = [s for s in full
               if s.get("function", {}).get("name") in permitidas]
    return acotado or full


def _presupuesto_de_meta(meta: dict) -> str:
    """Saca el presupuesto YA VERIFICADO (campo presentacion de calculate_total)
    del meta del solver, para que el cierre y el link de pago usen el total real
    de la calculadora, nunca uno inventado. "" si el solver no calculo este turno."""
    for tc in reversed((meta or {}).get("tools_called", []) or []):
        if tc.get("name") == "calculate_total":
            pres = (tc.get("result") or {}).get("presentacion")
            if pres:
                return pres
    return ""


def _money(n):
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return None


def _linea_producto(p: dict) -> str:
    """Linea REAL de un producto desde el catalogo: nombre + precio + stock. La
    verdad de la fuente, la usa el estampado de [[PROD:id]] y la guarda de
    producto para re-anclar con el dato real, no re-tipeado."""
    if not isinstance(p, dict):
        return ""
    nombre = str(p.get("nombre", "")).strip()
    precio = _money(p.get("precio_ars"))
    stock = p.get("stock", 0)
    partes = [nombre]
    if precio:
        partes.append(f"- ${precio}")
    if isinstance(stock, int) and stock > 0:
        partes.append(f"({stock} en stock)")
    return " ".join(partes).strip()


def _estampar_productos(texto: str, tienda_id: str, trace_id: str = None) -> str:
    """Reemplaza cada [[PROD:<id>]] por nombre + precio + stock REALES del catalogo.
    El solver ELIGE que producto mostrar (curaduria de venta); el codigo pone el DATO
    (verdad de la fuente). Un id que no existe se quita: el solver no puede inventar un
    producto ni un precio. Asi el listado nace del catalogo, no del texto del modelo."""
    if not texto or "[[PROD:" not in texto:
        return texto or ""
    from app.storage.firestore_client import get_product_by_id

    def _rep(m):
        pid = (m.group(1) or "").strip().upper()
        try:
            p = get_product_by_id(pid, tienda_id=tienda_id)
        except Exception:
            p = None
        if not p:
            log.warning("interprete_libre_prod_inexistente", trace_id=trace_id, pid=pid)
            return ""
        return _linea_producto(p)

    return re.sub(r"\[\[PROD:([A-Za-z0-9_\-]+)\]\]", _rep, texto)


def _guia_para_solver(interp: dict) -> str:
    """Inyecta al solver libre lo que entendió el intérprete, como GUÍA de qué
    quiere el cliente. No trae datos del catálogo: eso lo sacan las tools."""
    if not isinstance(interp, dict):
        return ""
    partes = []
    estado = interp.get("estado_conversacion")
    if estado:
        partes.append(f"estado={estado}")
    intencion = interp.get("intencion")
    if intencion:
        partes.append(f"intención={intencion}")
    if interp.get("producto_resuelto"):
        partes.append(f"se refiere a={interp['producto_resuelto']}")
    cands = interp.get("candidatos") or []
    if cands:
        partes.append("posibles=" + ", ".join(str(c) for c in cands[:3]))
    if interp.get("respondiendo_a"):
        partes.append(f"responde a={interp['respondiendo_a']}")
    if interp.get("ofrecer_opciones"):
        partes.append(f"ofrecer opción A o B={interp['ofrecer_opciones']}")
    if not partes:
        return ""
    return ("\n\n[El intérprete leyó este mensaje así: " + "; ".join(partes)
            + ". Actuá según el estado y la intención, no vuelvas a interpretar. "
            "Los precios, specs y datos de la tienda salen SOLO de las "
            "herramientas, no los inventes.]")


def _forzar_pregunta_si_ambiguo(interp: dict, respuesta: str) -> str | None:
    """Guarda determinista del caso 'interprete BIEN, solver MAL': cuando el
    interprete marco ofrecer_opciones (hay dos caminos y no se puede elegir con
    certeza) pero el solver NO planteo la eleccion, se FUERZA la pregunta A o B en
    vez de dejar que el solver elija por el cliente. Asi la divergencia no se
    resuelve con una alucinacion silenciosa, sino con una pregunta de confirmacion.
    Devuelve el texto a usar, o None si no corresponde tocar la respuesta."""
    if not isinstance(interp, dict):
        return None
    opciones = interp.get("ofrecer_opciones")
    if not isinstance(opciones, list) or len(opciones) < 2:
        return None
    a, b = str(opciones[0]).strip(), str(opciones[1]).strip()
    if not a or not b:
        return None
    import unicodedata

    def _n(s):
        s = unicodedata.normalize("NFKD", str(s or "").lower())
        return "".join(c for c in s if not unicodedata.combining(c))

    r = _n(respuesta)
    ya_pregunta = ("?" in (respuesta or "")) or ("¿" in (respuesta or ""))

    def _menciona(op):
        toks = [t for t in _n(op).split() if len(t) > 3][:3]
        return bool(toks) and any(t in r for t in toks)

    # Si el solver YA pregunta y nombra las dos opciones, planteo la eleccion bien:
    # se respeta su redaccion. En cualquier otro caso (eligio una, o no pregunto),
    # se fuerza la pregunta con el detalle que dio el interprete.
    if ya_pregunta and _menciona(a) and _menciona(b):
        return None
    return ("Quiero darte la opción correcta, tengo dos y no me quiero equivocar:\n"
            f"- Opción A: {a}\n- Opción B: {b}\n\n¿Cuál preferís?")


# Confianza minima del interprete para PISAR al solver por divergencia de
# producto. Si el interprete no esta seguro del producto, no se override al
# solver: la guarda solo actua cuando la lectura es UNIVOCA (conf alta) y el
# nombre resuelto reconcilia con UN unico producto del catalogo. Umbral
# operativo, vive en codigo (config, no flag apagada).
_CONF_MIN_PRODUCTO = 0.8


def _resolver_nombre_a_producto(resuelto: str, catalogo: list) -> dict | None:
    """Reconcilia el NOMBRE que resolvio el interprete con UN producto del
    catalogo. Ojo, esto NO es el certificador de queries del cliente (ese
    descarta modificadores genericos y da 'ambiguous' para un nombre completo
    como 'Mouse Genius DX-110 Negro', porque comparte 'mouse' con medio
    catalogo). Aca el interprete ya resolvio un NOMBRE, asi que se matchea por
    nombre completo: el nombre del catalogo esta contenido en el resuelto o al
    reves. Devuelve el producto SOLO si matchea uno unico; ante cero o varios,
    None (no se pisa al solver). Un termino vago como 'mouse' matchea muchos y
    cae a None, que es lo que queremos."""
    import unicodedata

    def _n(s):
        s = unicodedata.normalize("NFKD", str(s or "").lower())
        return "".join(c for c in s if not unicodedata.combining(c)).strip()

    r = _n(resuelto)
    if not r:
        return None
    hits: dict[str, dict] = {}
    for p in catalogo or []:
        nom = _n(p.get("nombre"))
        pid = str(p.get("id") or "")
        if nom and pid and (nom in r or r in nom):
            hits[pid] = p
    return next(iter(hits.values())) if len(hits) == 1 else None


def _reanclar_si_producto_divergente(interp: dict, respuesta: str,
                                     ids_mostrados: list, tienda_id: str) -> str | None:
    """Guarda determinista del caso 'interprete BIEN, solver MAL' sobre el
    PRODUCTO (gemela de _forzar_pregunta_si_ambiguo, para un solo producto).

    Si el interprete resolvio CON CONFIANZA un producto, ese nombre reconcilia
    con UN unico producto del catalogo y el solver mostro OTRO id, no se deja
    pasar el producto equivocado: se re-ancla al producto correcto con su LINEA
    REAL del catalogo y una pregunta de confirmacion. No cierra sobre esto: solo
    pregunta, nunca compromete una venta sobre un id inferido (Regla Cero).
    Triple candado para no pisar respuestas buenas: confianza alta, nombre que
    reconcilia UNICO, y que ese id NO este entre los que el solver ya mostro (si
    ya lo mostro, la divergencia era solo textual, ej categoria vs nombre).
    Devuelve el texto re-anclado o None."""
    if not isinstance(interp, dict):
        return None
    try:
        conf = float(interp.get("confianza") or 0)
    except (TypeError, ValueError):
        conf = 0.0
    if conf < _CONF_MIN_PRODUCTO:
        return None
    resuelto = str(interp.get("producto_resuelto") or "").strip()
    if not resuelto:
        return None
    from app.core.divergencia import detectar_divergencias
    if not any(d.get("eje") == "producto"
               for d in detectar_divergencias(interp, respuesta, ids_mostrados)):
        return None
    from app.storage.firestore_client import get_all_products
    p = _resolver_nombre_a_producto(resuelto, get_all_products(tienda_id=tienda_id))
    if not isinstance(p, dict) or not p.get("nombre"):
        return None  # nombre vago o que no reconcilia unico: no se pisa al solver
    pid = str(p.get("id") or "").upper()
    ya_mostrados = {str(i).upper() for i in (ids_mostrados or [])}
    if not pid or pid in ya_mostrados:
        return None  # el solver YA mostro ese producto: no hay divergencia real
    linea = _linea_producto(p)
    return (f"Pará que no me quiero equivocar: vos buscás el {p['nombre']}, "
            f"¿verdad?\n{linea}\n¿Avanzo con ese?")


def _parece_aportar_dato(mensaje: str) -> bool:
    """Heuristica barata: el mensaje parece traer un dato de cierre (numero, pago,
    o cue de domicilio), aunque el interprete no lo haya marcado como aporta_dato.
    Abre el extractor LLM en cotizaciones que ya mencionan direccion o pago."""
    if not mensaje:
        return False
    t = mensaje.lower()
    if any(ch.isdigit() for ch in t):
        return True
    claves = ("transferenc", "mercado pago", "efectivo", "tarjeta", "debito",
              "credito", "calle", "avenida", " av ", "direccion", "domicilio",
              "envio a", "enviar a", "me llamo", "mi nombre")
    return any(k in t for k in claves)


async def procesar_interprete_libre(user_id: str, raw_message: str,
                                    tienda_id: str, canal: str,
                                    trace_id: str) -> str:
    """Maneja el turno entero: intérprete + solver libre + memoria. La
    interpretación se loguea para diagnosticar, no se muestra al cliente."""
    t0 = time.time()

    conv = get_conversation(user_id, tienda_id=tienda_id)
    history = conv.get("history", []) or []
    estado_anterior = conv.get("estado_conversacion", "saludo") or "saludo"
    # PROOF de turnos anteriores: respaldan un total que el cliente confirma y el
    # bot repite sin recalcular, asi el filtro determinista no bloquea en falso.
    proofs_memoria = conv.get("proofs_recientes", []) or []

    # ── RESET_CODE: palabra clave de PRUEBA para arrancar de cero ────────
    # El bot mantiene CONTINUIDAD siempre. NO resetea con frases naturales como
    # "nueva compra" (un cliente real las usa para seguir comprando, no para
    # borrar todo). Para las pruebas hay una palabra clave dedicada (RESET_CODE,
    # ej "verifika2026"): si el mensaje es EXACTAMENTE esa, se borra la conversacion
    # entera y se confirma. Con clientes reales no hace falta; es solo para testear
    # desde el mismo numero sin tocar el entorno.
    _rc = (settings.RESET_CODE or "").strip().lower()
    if _rc and (raw_message or "").strip().lower() == _rc:
        try:
            reset_conversation(user_id, tienda_id=tienda_id)
            descartar_leads_activos(user_id, canal, tienda_id)
        except Exception as e:
            log.warning("interprete_libre_reset_error", trace_id=trace_id,
                        error=str(e)[:120])
        log.info("interprete_libre_reset_code", trace_id=trace_id, user_id=user_id)
        return "Listo, conversacion reiniciada. Empezamos de cero."

    # ── ESTADO DE VENTA: fuente unica del turno, una sola carga ─────────────
    # Se arma desde la conversacion persistida + el lead activo y se setea en la
    # contextvar, asi el interprete, el solver, las herramientas y el cierre leen
    # la MISMA verdad sin recibirla por parametro (igual que tienda y destino).
    lead_activo = None
    try:
        lead_activo = get_lead_activo(user_id, canal, tienda_id)
    except Exception as e:
        log.warning("interprete_libre_lead_lookup_error", trace_id=trace_id,
                    error=str(e)[:120])
    estado = construir_estado(conv, lead_activo)
    set_current_estado(estado)

    # ── PASO 1: INTERPRETE ──────────────────────────────────────────────
    interp = {}
    try:
        interp = await interpretar_mensaje(
            raw_message, history, trace_id,
            estado_anterior=estado_anterior, tienda_id=tienda_id)
    except Exception as e:
        log.error("interprete_libre_interp_error", trace_id=trace_id,
                  error=str(e)[:200])

    estado_nuevo = (interp.get("estado_conversacion")
                    or estado_anterior) if isinstance(interp, dict) else estado_anterior

    # La interpretacion va al LOG para diagnosticar (reemplaza el cartel que antes
    # se mostraba al cliente). Asi se juzga la interpretacion sin molestar la charla.
    if isinstance(interp, dict):
        log.info("interprete_libre_interpretacion", trace_id=trace_id,
                 intencion=interp.get("intencion"), confianza=interp.get("confianza"),
                 estado=interp.get("estado_conversacion"),
                 producto=interp.get("producto_resuelto"),
                 responde_a=interp.get("respondiendo_a"),
                 candidatos=interp.get("candidatos"))

    # Flag one-shot del gatillo de cierre (se lee ACA porque tambien condiciona
    # el atajo curado: con una pregunta de cierre pendiente no se ataja nada).
    pregunta_cierre_previa = bool(conv.get("pregunta_cierre_hecha"))

    # ── ATAJO CURADO: pregunta PURA de politica -> respuesta aprobada ───────
    # Patron "LLM compila offline, runtime determinista": si el ruteo de FAQ
    # matchea un tema con respuesta_curada y el turno no tiene venta en juego
    # (sin producto, sin carrito, sin cierre pendiente), sale el texto aprobado
    # por la tienda con los numeros estampados de los valores. El solver NI
    # CORRE: cero alucinacion posible y un turno mas barato. Ante cualquier
    # duda devuelve None y el turno sigue por el camino normal.
    respuesta_curada_servida = False
    respuesta = ""
    meta: dict = {}
    try:
        from app.core.curadas import servir_curada
        _cur = servir_curada(raw_message, interp, estado,
                             pregunta_cierre_previa, tienda_id)
        if _cur:
            respuesta = _cur[1]
            respuesta_curada_servida = True
            log.info("interprete_libre_curada_servida", trace_id=trace_id,
                     tema=_cur[0])
    except Exception as e:
        log.warning("interprete_libre_curada_error", trace_id=trace_id,
                    error=str(e)[:120])

    # ── PASO 2: SOLVER LIBRE (con la guía del intérprete + estado de venta) ──
    # El solver ve, ademas del mensaje y la guia del interprete, el ESTADO DE LA
    # VENTA armado arriba: productos con precio real, carrito, total, envio cotizado
    # y datos del cliente ya capturados. Asi no re-pregunta la direccion ni
    # re-inventa un precio que ya salio de una tool.
    system_prompt = _PROMPT_LIBRE.format(business_name=_business_name(tienda_id))
    tools_schema = _schema_acotado()
    mensaje_enriquecido = (raw_message + _guia_para_solver(interp)
                           + bloque_para_solver(estado))

    # GUIA DETERMINISTA "mas barato con stock" (blindaje del hueco real 2-jul):
    # si el criterio del cliente es el precio (dicho este turno o sticky en
    # memoria), elegir el minimo es un problema CERRADO y lo computa el CODIGO.
    # La guia viaja en el mensaje con el [[PROD:id]] ya decidido; el solver
    # conserva la redaccion, no la eleccion. Generar > corregir > verificar.
    if detectar_criterio(raw_message) or (estado.get("criterio") or "").strip():
        try:
            from app.core.guia_compra import guia_mas_barato
            _guia_barato = guia_mas_barato(
                raw_message, estado.get("productos_vistos"))
            if _guia_barato:
                mensaje_enriquecido += _guia_barato
                log.info("interprete_libre_guia_mas_barato", trace_id=trace_id)
        except Exception as e:
            log.warning("interprete_libre_guia_barato_error", trace_id=trace_id,
                        error=str(e)[:120])

    # GUIA DE MEMORIA BORROSA (paso 3): el cliente referencia algo anterior ("el
    # que te dije", "no me acuerdo cual"). El CODIGO es dueño de la memoria: si
    # hay UN unico producto visto lo ancla ([[PROD:id]] real), si hay varios manda
    # preguntar cual, si no hay ninguno manda no inventar. Asi el solver no
    # adivina un id de memoria (la raiz del error del banco 5-jul). Inyeccion
    # previa, mismo patron que la guia del mas barato; compone con los
    # verificadores. No decide identidad sobre un id inferido: solo ancla lo YA
    # mostrado o manda preguntar (Regla Cero).
    try:
        from app.core.memoria_ref import guia_memoria
        _guia_mem = guia_memoria(raw_message, estado.get("productos_vistos"))
        if _guia_mem:
            mensaje_enriquecido += _guia_mem
            log.info("interprete_libre_guia_memoria", trace_id=trace_id)
    except Exception as e:
        log.warning("interprete_libre_guia_memoria_error", trace_id=trace_id,
                    error=str(e)[:120])

    log.info("interprete_libre_inicio", trace_id=trace_id,
             intencion=interp.get("intencion") if isinstance(interp, dict) else None,
             tools=len(tools_schema), hist=len(history))

    if not respuesta_curada_servida:
        try:
            respuesta, meta = await run_agent(
                mensaje_enriquecido, history, trace_id,
                tienda_id=tienda_id, user_id=user_id,
                system_prompt=system_prompt, tools_schema=tools_schema)
        except Exception as e:
            log.error("interprete_libre_solver_error", trace_id=trace_id,
                      error=str(e)[:200])
            respuesta = settings.FALLBACK_MESSAGE

    # ── DIAGNOSTICO DE INTEGRACION (solver <-> herramientas mellizas) ──────────
    # Loguea, por turno, lo que DEVOLVIERON las tools deterministas (result/proof)
    # y la respuesta CRUDA del solver, ANTES de estampar/corregir. Sin esto no se
    # puede ver si el dato real de la herramienta llega al mensaje o el solver lo
    # re-tipea distinto. Compacto y truncado; son datos de la tienda, no del
    # cliente. Comparar contra respuesta_preview (final) cierra el triplete.
    try:
        _tools_dump = [
            {"t": tc.get("name"), "res": str(tc.get("result"))[:180]}
            for tc in (meta.get("tools_called") or [])
        ]
        log.info("interprete_libre_solver_crudo", trace_id=trace_id,
                 respuesta_cruda=(respuesta or "")[:400],
                 tools=_tools_dump[:8])
    except Exception:
        pass

    # ── CLON (ESTAMPA): los datos duros NACEN de la fuente, no del modelo ──
    # El solver pone un marcador donde va cada dato duro; el codigo lo reemplaza por
    # el bloque real renderizado desde la tool/Firestore (precio = presentacion de
    # calculate_total; envio = cotizar_envio; politica = respuesta verbatim de
    # query_faq). Asi ni el presupuesto, ni el envio, ni una politica se re-tipean o
    # se inventan. Marcador sin dato (la tool no corrio) -> se quita, no se inventa.
    # Se loguea cuando el solver dio el presupuesto SIN marcador, para medir.
    _env = envio_de_meta(meta)
    _present = _presupuesto_de_meta(meta)
    _marcadores = {
        "[[PRESUPUESTO]]": _present,
        "[[ENVIO]]": (f"Envio a {_env}" if _env else ""),
        # El marcador [[FAQ]] se retiro (consolidacion): la politica ahora entra
        # SIEMPRE por el ACOPLE del bloque curado, decidido por el codigo, no por
        # un marcador que el solver podia no poner. Uno que haya quedado en el
        # texto se limpia como marcador sin dato.
        "[[FAQ]]": "",
    }
    # El Ensamblador coloca cada bloque cuidando la congruencia: un dato de una
    # linea va donde el solver puso el marcador; un bloque de varias lineas
    # (presupuesto, politica) se levanta a su propio parrafo y no queda
    # incrustado en medio de una oracion. Un marcador sin dato se quita limpio.
    from app.core.ensamblador import colocar_bloque
    _tenia_marcador_presup = "[[PRESUPUESTO]]" in (respuesta or "")
    for _marca, _bloque in _marcadores.items():
        if _marca not in (respuesta or ""):
            continue
        respuesta = colocar_bloque(respuesta, _marca, _bloque)
        if _bloque:
            log.info("interprete_libre_estampado", trace_id=trace_id, marca=_marca)
        else:
            log.warning("interprete_libre_marcador_sin_dato",
                        trace_id=trace_id, marca=_marca)
    if _present and not _tenia_marcador_presup:
        log.warning("interprete_libre_presupuesto_sin_marcador", trace_id=trace_id)

    # Productos: el solver los referencia por [[PROD:<id>]] y el codigo pone
    # nombre+precio+stock reales del catalogo (curaduria del solver, datos de la
    # fuente). Un id inventado se cae solo.
    # Los ids que el solver mostro (antes de estampar): son el QUE realmente en la
    # respuesta. Se guardan para respaldar sus precios reales en el verificador.
    _ids_mostrados = re.findall(r"\[\[PROD:([A-Za-z0-9_\-]+)\]\]", respuesta or "")
    if "[[PROD:" in (respuesta or ""):
        respuesta = _estampar_productos(respuesta, tienda_id, trace_id)
        log.info("interprete_libre_productos_estampados", trace_id=trace_id)

    # ── MEDICION DE DIVERGENCIA intérprete <-> solver (paso 1: SOLO mide) ────
    # No cambia la respuesta. Loguea, por turno, cuándo el solver hizo algo
    # distinto a lo que leyó el intérprete en los ejes CERRADOS (producto,
    # opciones A/B, estado del embudo). Se calcula sobre la respuesta del solver
    # ya estampada, ANTES de la guarda A/B y los verificadores, para ver la
    # conducta CRUDA del solver. Es la base para enforzar en los pasos 2, 3 y 4:
    # primero medir el tamaño real del problema en el banco de charlas vivas.
    try:
        from app.core.divergencia import detectar_divergencias
        _divs = detectar_divergencias(interp, respuesta, _ids_mostrados)
        if _divs:
            log.warning("interprete_libre_divergencia", trace_id=trace_id,
                        divergencias=_divs[:6],
                        respuesta_preview=(respuesta or "")[:200])
    except Exception as e:
        log.warning("interprete_libre_divergencia_error", trace_id=trace_id,
                    error=str(e)[:120])

    # ── ACOPLE CURADO de FAQ (reemplaza al marcador [[FAQ]]) ────────────────
    # Si el turno consulto la FAQ, la politica sale del BLOQUE curado del tema
    # (texto aprobado por la tienda con los numeros estampados de los valores),
    # pegado en VERTICAL debajo de la prosa del solver. Lo decide el CODIGO por
    # el query_faq del turno, no un marcador que el solver podia no poner. Un
    # solo cierre por mensaje y sin duplicar si el solver pego el texto tal
    # cual. Corre antes de los verificadores, que auditan el mensaje final.
    tema_acoplado = ""
    if not respuesta_curada_servida and respuesta != settings.FALLBACK_MESSAGE:
        try:
            from app.core.curadas import (
                bloque_curado_de_meta, bloque_curado_por_mensaje, acoplar_bloque)
            # Doble ancla: primero el query_faq que el solver llamo; si no llamo
            # ninguno pero el interprete ve una pregunta de politica y el ruteo
            # matchea un tema curado, el bloque va IGUAL (el codigo decide, no
            # depende de la obediencia del solver).
            _bc = (bloque_curado_de_meta(meta, tienda_id)
                   or bloque_curado_por_mensaje(raw_message, interp, tienda_id))
            if _bc:
                from app.core.curadas import (
                    solapa_prosa, temas_cubiertos_por_tools, prosa_trae_valores)
                from app.storage.firestore_client import get_all_faq as _gaf
                _tema_bc, _bloque_bc = _bc
                _valores_bc = ((_gaf(tienda_id=tienda_id) or {})
                               .get(_tema_bc) or {}).get("valores")
                _tiene_valores = bool(_valores_bc)
                # Pertinencia (vista en real 4-jul): el bloque NO va cuando una
                # tool del mismo dominio ya dio la respuesta concreta (envio
                # cotizado, descuento en el total), ni cuando la prosa ya dice
                # lo mismo Y el tema es de texto puro. Un tema con numeros
                # lleva SIEMPRE su bloque: el numero oficial no se negocia.
                if _tema_bc in temas_cubiertos_por_tools(meta):
                    log.info("interprete_libre_acople_salteado", trace_id=trace_id,
                             tema=_tema_bc, motivo="tool_cubre")
                elif not _tiene_valores and solapa_prosa(respuesta, _bloque_bc):
                    log.info("interprete_libre_acople_salteado", trace_id=trace_id,
                             tema=_tema_bc, motivo="prosa_solapa")
                # Tema NUMERICO cuya prosa ya trae TODOS los montos oficiales
                # y ademas dice lo mismo que el bloque: pegarlo repetiria la
                # politica dos veces con un segundo gancho (visto en el banco,
                # guion de acople). El numero oficial esta literal en la prosa
                # y el verificador de FAQ numerica lo audita igual.
                elif (_tiene_valores and prosa_trae_valores(respuesta, _valores_bc)
                        and solapa_prosa(respuesta, _bloque_bc)):
                    log.info("interprete_libre_acople_salteado", trace_id=trace_id,
                             tema=_tema_bc, motivo="prosa_trae_valores")
                else:
                    respuesta = acoplar_bloque(respuesta, _bloque_bc)
                    tema_acoplado = _tema_bc
                    log.info("interprete_libre_faq_acoplada", trace_id=trace_id,
                             tema=tema_acoplado)
        except Exception as e:
            log.warning("interprete_libre_acople_error", trace_id=trace_id,
                        error=str(e)[:120])

    # ── PASO 2a: FILTRO DETERMINISTA — CLON DEL MOTOR DE PRECIOS/ENVIO ──────
    # Partida doble de la verdad. Las herramientas deterministas (calculadora,
    # tarifa de envio, ficha del catalogo) le dan los numeros al Solver via
    # tool-call. Su PROOF queda guardado. ACA ese MISMO motor se usa como CLON
    # para auditar la respuesta que el Solver redacto:
    #   - si cada cifra de dinero coincide con el PROOF, la respuesta pasa intacta;
    #   - si el Solver CAMBIO un total y la verdad esta en el PROOF, el codigo
    #     REESCRIBE la cifra mala por la buena, sin llamar a ningun modelo
    #     (autocorregir_montos, conservador: solo un reemplazo INEQUIVOCO).
    # Con AUTOCORRIGE_MONTOS=false vuelve a modo observacion: solo loguea, no toca.
    proofs_turno = [t["proof"] for t in (meta.get("tools_called") or [])
                    if t.get("proof")]
    # La evidencia del turno se comparte con los verificadores por campo de mas
    # abajo (stock, FAQ numerica): se declara afuera del try para que un error en
    # el filtro de plata no los deje sin fuente.
    evidencia: list = []
    if respuesta != settings.FALLBACK_MESSAGE:
        try:
            from app.core.evidencia import build_evidence_from_tools
            from app.core.verificador import (
                verificar_respuesta, autocorregir_montos)
            # Productos vistos en turnos anteriores: su precio REAL respalda una
            # cifra que el bot ya mostro y repite, asi el filtro no la marca en
            # falso. El estado los guarda con la clave 'precio'; el verificador
            # lee 'precio_ars', por eso se normaliza al pasarlos.
            # Cada visto se re-lee VIVO del catalogo por id: asi la evidencia
            # trae el precio Y el stock actuales y los verificadores (plata y
            # stock) pueden juzgar afirmaciones sobre productos de turnos
            # anteriores. La memoria guarda el precio de cuando se mostro; el
            # que juzga es siempre el dato vivo de la fuente. Si la lectura
            # falla, queda el precio de memoria (sin stock: no acusa a nadie).
            from app.storage.firestore_client import get_product_by_id as _gpid_ev
            prods_vistos = []
            for p in (estado.get("productos_vistos") or []):
                if not isinstance(p, dict):
                    continue
                _vivo = None
                _pid = str(p.get("id") or "").upper()
                if _pid:
                    try:
                        _vivo = _gpid_ev(_pid, tienda_id=tienda_id)
                    except Exception:
                        _vivo = None
                if isinstance(_vivo, dict) and _vivo.get("precio_ars") is not None:
                    prods_vistos.append(_vivo)
                else:
                    prods_vistos.append(
                        {**p, "precio_ars": p.get("precio_ars", p.get("precio"))})
            evidencia = build_evidence_from_tools(
                meta.get("tools_called", []) or [], tienda_id,
                productos_vistos=prods_vistos)
            evidencia += [{"tipo": "proof", "proof": p} for p in proofs_memoria]
            # Productos que el solver MOSTRO ([[PROD:id]]): se respaldan con su
            # precio_ars REAL de get_product_by_id, asi un precio real mostrado nunca
            # cae como "sin respaldo" (es el QUE que de verdad esta en la respuesta).
            if _ids_mostrados:
                from app.storage.firestore_client import get_product_by_id as _gpid
                for _pid in {i.upper() for i in _ids_mostrados}:
                    try:
                        _pp = _gpid(_pid, tienda_id=tienda_id)
                    except Exception:
                        _pp = None
                    if isinstance(_pp, dict) and _pp.get("precio_ars") is not None:
                        evidencia.append({"tipo": "producto", **_pp})
            # Todo producto NOMBRADO con su nombre completo en la respuesta
            # entra VIVO a la evidencia: la melliza no puede juzgar lo que no
            # ve. Visto en el banco: el solver tipeo a mano una linea de
            # producto sin tool ni marcador ("NX-7000 - $8.000, 11 en stock",
            # precio y stock de fantasia) y ni la plata ni el stock la
            # corrigieron porque el producto no estaba en la evidencia.
            from app.core.evidencia import productos_nombrados_en
            _ids_ev = {str(i.get("id") or "").upper() for i in evidencia
                       if i.get("tipo") == "producto"}
            for _pn in productos_nombrados_en(respuesta, tienda_id):
                if str(_pn.get("id") or "").upper() not in _ids_ev:
                    evidencia.append({"tipo": "producto", **_pn})
            # QUE PROACTIVO: el codigo busca en el catalogo lo que el cliente pidio,
            # SIN depender de que el solver haya buscado. Esos productos REALES entran
            # como evidencia COMPLETA del QUE, asi el corrector valida/corrige contra
            # la fuente y no marca en falso un precio real ni deja pasar uno inventado.
            try:
                from app.core.tools import search_products as _search_que
                _ids_ya = {str(i.get("id") or "").upper()
                           for i in evidencia if i.get("tipo") == "producto"}
                _qres = _search_que(query=raw_message) or {}
                for _p in (_qres.get("productos") or [])[:12]:
                    if isinstance(_p, dict) and str(_p.get("id") or "").upper() not in _ids_ya:
                        evidencia.append({"tipo": "producto", **_p})
            except Exception as e:
                log.warning("interprete_libre_que_proactivo_error",
                            trace_id=trace_id, error=str(e)[:120])
            # El catalogo guarda el precio bajo 'precio' o 'precio_ars' segun la
            # fuente; el verificador lee SOLO precio_ars. Se normaliza TODA la
            # evidencia de productos para que un precio real no caiga como
            # "sin respaldo" por un nombre de campo (causa del falso positivo 14500).
            for _i in evidencia:
                if (_i.get("tipo") == "producto" and _i.get("precio_ars") is None
                        and isinstance(_i.get("precio"), (int, float))):
                    _i["precio_ars"] = _i["precio"]
            # Precios reales del catalogo: nunca se pisan aunque el filtro no los
            # vea respaldados en este turno (pueden venir de uno anterior).
            precios_validos = {
                int(i["precio_ars"]) for i in evidencia
                if i.get("tipo") == "producto"
                and isinstance(i.get("precio_ars"), (int, float))
            }
            if settings.AUTOCORRIGE_MONTOS:
                fix = autocorregir_montos(
                    respuesta, evidencia, trace_id,
                    precios_validos=precios_validos)
                if fix["cambiada"] and fix["verificacion"].get("ok"):
                    # El Solver habia cambiado el total y se reescribio por el real.
                    log.warning("interprete_libre_monto_corregido",
                                trace_id=trace_id,
                                correcciones=fix["correcciones"][:8],
                                respuesta_preview=fix["respuesta"][:220])
                    respuesta = fix["respuesta"]
                elif fix["cambiada"]:
                    # Se intento corregir pero el texto sigue sin cerrar: no se
                    # arriesga un numero a medias, queda el original (shadow).
                    log.warning("interprete_libre_correccion_descartada",
                                trace_id=trace_id,
                                correcciones=fix["correcciones"][:8])
                elif not fix["verificacion"].get("ok"):
                    # Cifra de plata sin respaldo que no se pudo corregir. La
                    # melliza activa decide: bloquea (canned) SOLO si no hay
                    # ninguna evidencia de donde pudo salir el numero, ni tools de
                    # este turno ni memoria. El solver que repite un presupuesto ya
                    # calculado en turnos anteriores no llama tools pero sus cifras
                    # son legitimas: la evidencia esta en proofs/productos de
                    # memoria, asi que queda en shadow y la respuesta sale.
                    from app.core.verificador import decidir_accion_no_respaldado
                    hay_tools = bool(meta.get("tools_called"))
                    hay_memoria = bool(proofs_memoria) or bool(prods_vistos)
                    accion = decidir_accion_no_respaldado(
                        verificacion_ok=False, hay_tools=hay_tools,
                        hay_memoria=hay_memoria)
                    if accion == "bloquear":
                        log.warning("interprete_libre_numero_bloqueado",
                                    trace_id=trace_id,
                                    no_respaldados=fix["verificacion"]["numeros_no_respaldados"][:8],
                                    respuesta_preview=respuesta[:220])
                        respuesta = settings.VERIFIKA_FALLBACK_MESSAGE
                    else:
                        log.warning("interprete_libre_numero_no_respaldado_shadow",
                                    trace_id=trace_id,
                                    no_respaldados=fix["verificacion"]["numeros_no_respaldados"][:8],
                                    respuesta_preview=respuesta[:220])
            else:
                veredicto = verificar_respuesta(respuesta, evidencia, trace_id)
                if not veredicto["ok"]:
                    log.warning("interprete_libre_numero_no_respaldado_shadow",
                                trace_id=trace_id,
                                no_respaldados=veredicto["numeros_no_respaldados"][:8],
                                respuesta_preview=respuesta[:220])
        except Exception as e:
            log.warning("interprete_libre_verif_error", trace_id=trace_id,
                        error=str(e)[:160])

    # ── PASO 2a-ter: VERIFICADOR DE STOCK (mismo patron por campo) ──────────
    # La plata ya esta cubierta; este es el campo por donde se filtro la
    # alucinacion real del 2-jul (negar stock que existia). Dos piezas:
    # 1) la CIFRA de unidades contradicha se reescribe por la real (safe-override
    #    determinista); 2) una CONTRADICCION de texto (negar stock existente,
    #    ofrecer un agotado) se reescribe con la maquinaria de guardia_promesas,
    #    con el dato real del catalogo en la regla. Solo juzga productos cuyo
    #    stock REAL esta en la evidencia de este turno.
    if respuesta != settings.FALLBACK_MESSAGE and evidencia:
        try:
            from app.core.verificador_stock import (
                corregir_unidades_stock, detectar_stock_contradicho,
                instruccion_stock, cuarentena_stock)
            _fix_stock = corregir_unidades_stock(respuesta, evidencia)
            if _fix_stock["correcciones"]:
                log.warning("interprete_libre_stock_cifra_corregida",
                            trace_id=trace_id,
                            correcciones=_fix_stock["correcciones"][:8])
                respuesta = _fix_stock["respuesta"]
            _contradicho = detectar_stock_contradicho(respuesta, evidencia)
            if _contradicho:
                log.warning("interprete_libre_stock_contradicho",
                            trace_id=trace_id, casos=_contradicho[:6],
                            respuesta_preview=respuesta[:200])
                from app.core.guardia_promesas import reescribir_con_reglas
                _nueva = await reescribir_con_reglas(
                    respuesta, instruccion_stock(_contradicho), trace_id)
                if _nueva:
                    respuesta = _nueva
                _quedan = detectar_stock_contradicho(respuesta, evidencia)
                if _quedan:
                    # Red DETERMINISTA (mismo patron que la guardia, visto en
                    # el banco: la reescritura dejo la mentira y salio al
                    # cliente): se podan las lineas contradichas; sin mensaje
                    # decente, canned. Antes aca solo se logueaba stock_persiste.
                    _poda = cuarentena_stock(respuesta, evidencia)
                    if _poda and not detectar_stock_contradicho(_poda, evidencia):
                        respuesta = _poda
                        log.warning("interprete_libre_stock_cuarentena",
                                    trace_id=trace_id, casos=_quedan[:6],
                                    respuesta_preview=_poda[:200])
                    else:
                        respuesta = settings.VERIFIKA_FALLBACK_MESSAGE
                        log.warning("interprete_libre_stock_bloqueado",
                                    trace_id=trace_id, casos=_quedan[:6])
                else:
                    log.info("interprete_libre_stock_reescrito",
                             trace_id=trace_id)
        except Exception as e:
            log.warning("interprete_libre_stock_error", trace_id=trace_id,
                        error=str(e)[:160])

    # ── PASO 2a-quater: FAQ NUMERICA (porcentaje, cuotas, plazos, garantia) ──
    # Los numeros chicos de politica que la plata no mira. Si el numero
    # contradice la fuente y el turno consulto la FAQ (ancla del tema), se
    # estampa el valor verdadero; sin ancla univoca, queda logueado.
    if respuesta != settings.FALLBACK_MESSAGE and evidencia:
        try:
            from app.core.verificador_faq import (
                autocorregir_faq_numerica, temas_de_meta)
            # El tema del bloque ACOPLADO tambien ancla: si el codigo pego la
            # politica oficial de un tema, un numero de la prosa del solver que
            # la contradiga se juzga contra ESE tema aunque el solver no haya
            # llamado query_faq (visto en real 4-jul: '3 a 5 dias' inventado).
            _temas_turno = set(temas_de_meta(meta))
            if tema_acoplado:
                _temas_turno.add(tema_acoplado)
            _fix_faq = autocorregir_faq_numerica(
                respuesta, evidencia,
                temas_consultados=_temas_turno, trace_id=trace_id)
            if _fix_faq["cambiada"] and _fix_faq["verificacion"]["ok"]:
                log.warning("interprete_libre_faq_numerica_corregida",
                            trace_id=trace_id,
                            correcciones=_fix_faq["correcciones"][:8])
                respuesta = _fix_faq["respuesta"]
            elif not _fix_faq["verificacion"]["ok"]:
                log.warning("interprete_libre_faq_numerica_sin_respaldo",
                            trace_id=trace_id,
                            sin_respaldo=_fix_faq["verificacion"]["sin_respaldo"][:8],
                            respuesta_preview=respuesta[:200])
        except Exception as e:
            log.warning("interprete_libre_faq_numerica_error",
                        trace_id=trace_id, error=str(e)[:160])
    proofs_recientes = (proofs_memoria + proofs_turno)[-settings.VERIFICADOR_PROOF_MEMORY:]

    # ── PASO 2a-bis: GUARDIA DE PROMESAS PROHIBIDAS (enforce) ───────────────
    # Linea cero del TEXTO: un conjunto cerrado de afirmaciones que el bot no puede
    # decir aunque el cliente insista (dia exacto de entrega, retiro en local,
    # servicios fuera de la FAQ). Si la deteccion determinista dispara, el codigo
    # reescribe el mensaje sin la promesa antes de mandarlo. Una sola llamada extra
    # al modelo y SOLO en los turnos que disparan, no en todos.
    if respuesta != settings.FALLBACK_MESSAGE:
        try:
            from app.core.guardia_promesas import (
                detectar, reescribir_sin_promesas, cuarentena_prohibidas)
            clases = detectar(respuesta)
            if clases:
                log.warning("interprete_libre_promesa_prohibida", trace_id=trace_id,
                            clases=clases, respuesta_preview=respuesta[:200])
                nueva = ""
                try:
                    nueva = await reescribir_sin_promesas(respuesta, clases, trace_id)
                except Exception as e:
                    log.warning("interprete_libre_reescritura_error",
                                trace_id=trace_id, error=str(e)[:120])
                if nueva and not detectar(nueva):
                    respuesta = nueva
                    log.info("interprete_libre_promesa_reescrita",
                             trace_id=trace_id, clases=clases)
                else:
                    # Red DETERMINISTA (hueco real 4-jul: el editor devolvio vacio
                    # y una direccion inventada salio al cliente). Se podan las
                    # lineas con promesa; si no queda mensaje decente, canned.
                    poda = cuarentena_prohibidas(nueva or respuesta)
                    if poda and not detectar(poda):
                        respuesta = poda
                        log.warning("interprete_libre_promesa_cuarentena",
                                    trace_id=trace_id, clases=clases,
                                    respuesta_preview=poda[:200])
                    else:
                        respuesta = settings.VERIFIKA_FALLBACK_MESSAGE
                        log.warning("interprete_libre_promesa_bloqueada",
                                    trace_id=trace_id, clases=clases)
        except Exception as e:
            log.warning("interprete_libre_guardia_error", trace_id=trace_id,
                        error=str(e)[:160])

    # ── GUARDA DE DIVERGENCIA (caso interprete BIEN, solver MAL) ────────────
    # Si el interprete marco ofrecer_opciones (dos caminos, no se puede elegir con
    # certeza) pero el solver NO planteo la eleccion, se FUERZA la pregunta A/B.
    # Asi la divergencia se resuelve con una pregunta de confirmacion, no con una
    # eleccion silenciosa del solver. Si esto dispara, no se cierra este turno: no
    # se cierra sobre un producto todavia ambiguo.
    ambiguo_forzado = False
    if respuesta != settings.FALLBACK_MESSAGE:
        _preg_amb = _forzar_pregunta_si_ambiguo(interp, respuesta)
        if _preg_amb:
            respuesta = _preg_amb
            ambiguo_forzado = True
            log.info("interprete_libre_pregunta_ambiguo_forzada", trace_id=trace_id)

    # ── GUARDA DE PRODUCTO (paso 2: interprete BIEN, solver MAL sobre el QUE) ──
    # Extiende el MISMO patron de la guarda A/B al producto unico: si el
    # interprete resolvio con confianza un producto que el certificador confirma
    # como unico y real, y el solver mostro OTRO, se re-ancla al producto
    # correcto con su linea REAL del catalogo y una pregunta de confirmacion. Si
    # dispara, no se cierra este turno: el producto todavia no esta confirmado.
    producto_forzado = False
    if respuesta != settings.FALLBACK_MESSAGE and not ambiguo_forzado:
        try:
            _re_prod = _reanclar_si_producto_divergente(
                interp, respuesta, _ids_mostrados, tienda_id)
            if _re_prod:
                respuesta = _re_prod
                producto_forzado = True
                log.warning("interprete_libre_producto_reanclado",
                            trace_id=trace_id,
                            producto=str(interp.get("producto_resuelto"))[:60])
        except Exception as e:
            log.warning("interprete_libre_producto_guarda_error",
                        trace_id=trace_id, error=str(e)[:120])

    # ── PASO 2b: CIERRE (codigo) — capta el lead, pide datos, manda el link ──
    # El codigo toma el control SOLO cuando hay que cerrar: detecta la decision de
    # compra por la interpretacion, junta nombre/telefono/direccion/forma de pago y
    # genera el link de Mercado Pago con el total VERIFICADO de la calculadora (de
    # presentacion, nunca un monto del modelo). Si no hay cierre, la respuesta libre
    # del solver queda intacta. El presupuesto sale del turno o de la memoria.
    _present_turno = _presupuesto_de_meta(meta)
    presupuesto = _present_turno or (conv.get("ultimo_presupuesto") or "")
    # Presupuesto NUEVO = la calculadora dio un total ESTE turno (no de memoria).
    # Es el momento natural para la pregunta suave de cierre, asi no se repite.
    presupuesto_nuevo = bool(_present_turno)

    # ── ACUMULAR DATOS DEL CLIENTE turno a turno (raiz del re-pedido) ────────
    # El cliente suele dar la direccion, el pago o el nombre ANTES de la decision
    # de compra, o DENTRO de un mensaje de otra intencion (ej una cotizacion que ya
    # menciona "pago transferencia"). Antes la extraccion estaba atada a la intencion
    # (solo aporta_dato/decision_compra), asi que ese dato se perdia y el cierre lo
    # volvia a pedir. Ahora: (1) la extraccion DETERMINISTA (telefono, pago,
    # direccion por patron) corre SIEMPRE, barata y sin LLM; (2) el extractor LLM
    # corre cuando el interprete sugiere datos O el mensaje trae numeros/cue de dato.
    # El acumulado viaja al cierre y se persiste al final del turno.
    _intent = interp.get("intencion") if isinstance(interp, dict) else None
    datos_previos = conv.get("datos_cliente_parciales") or {}
    datos_turno: dict = {}
    try:
        from app.core.cierre import extraer_determinista, extraer_datos_cliente
        # Determinista, en CADA turno: el codigo manda en los datos.
        datos_turno.update(extraer_determinista(raw_message))
        # LLM, cuando hay senal de dato (intencion o el texto lo parece).
        if _intent in ("aporta_dato", "decision_compra") or _parece_aportar_dato(raw_message):
            for k, v in extraer_datos_cliente(raw_message, trace_id).items():
                if v:
                    datos_turno[k] = v
    except Exception as e:
        log.warning("interprete_libre_extractor_error", trace_id=trace_id,
                    error=str(e)[:120])
    datos_acumulados = {**datos_previos, **datos_turno}
    if datos_turno:
        log.info("interprete_libre_datos_turno", trace_id=trace_id,
                 user_id=user_id, intencion=_intent,
                 campos=sorted(datos_turno.keys()),
                 acumulado=sorted(datos_acumulados.keys()))

    # El flag one-shot del gatillo de cierre (D) ya se leyo arriba (condiciona
    # tambien el atajo curado): si el turno pasado el bot hizo la pregunta de
    # cierre, este turno la respuesta del cliente la decide.
    meta_lead: dict = {}
    # No se cierra cuando una guarda forzo una pregunta (ambiguedad A/B o
    # re-ancla de producto): el producto todavia no esta confirmado, cerrar seria
    # sobre algo indefinido.
    if (respuesta != settings.FALLBACK_MESSAGE
            and not ambiguo_forzado and not producto_forzado):
        try:
            _, meta_lead = await procesar_mensaje_para_lead(
                user_id, canal, tienda_id, raw_message, respuesta, trace_id,
                interpretacion=interp if isinstance(interp, dict) else None,
                presupuesto=presupuesto,
                datos_turno=datos_turno, datos_previos=datos_acumulados,
                presupuesto_nuevo=presupuesto_nuevo,
                pregunta_cierre_hecha=pregunta_cierre_previa)
            if meta_lead.get("respuesta_directa"):
                respuesta = meta_lead["respuesta_directa"]
                log.info("interprete_libre_cierre", trace_id=trace_id,
                         accion=meta_lead.get("accion"))
        except Exception as e:
            log.warning("interprete_libre_lead_error", trace_id=trace_id,
                        error=str(e)[:160])
    # Queda marcado el turno en que se hizo la pregunta; al siguiente se consume y
    # vuelve a False, asi la pregunta se hace una sola vez. EXCEPCION: si el cliente
    # respondio con una duda o pregunta, el cierre sigue PENDIENTE (no se consume),
    # asi un "dale" en el turno siguiente todavia cierra.
    pregunta_cierre_hecha = (
        meta_lead.get("accion") in ("pregunta_cierre", "pregunta_pendiente_cierre"))

    # El cliente recibe la respuesta limpia: el cartel de interpretacion se quito
    # (ahora va al log). La interpretacion se sigue viendo en interprete_libre_interpretacion.
    respuesta_final = respuesta

    # ── MEMORIA: guardar el turno (el solver siempre recuerda la charla) ──
    history = history + [
        {"role": "user", "content": raw_message},
        {"role": "assistant", "content": respuesta},
    ]
    history = history[-(settings.HISTORY_LIMIT * 2):]

    # ── ESTADO DE VENTA: mergear lo de este turno con la memoria y persistir ──
    # Los datos deterministas (productos con precio real, carrito, envio) que las
    # tools generaron este turno se suman a los de turnos anteriores, asi el bloque
    # del proximo turno los tiene a la vista. Si este turno no llamo una tool, queda
    # lo que ya habia en memoria.
    # Los productos que el bot MOSTRO ([[PROD:id]] estampados, ej. los que trae la
    # guia determinista) tambien son vistos, aunque el turno no haya llamado tools.
    # Sin esto el turno de la guia no deja rastro y el solver del proximo turno
    # ADIVINA el id de memoria (visto en el banco: pidio el total con un teclado de
    # $172.500 en vez del de $12.000 mostrado). Nombre y precio salen del catalogo.
    mostrados: list[dict] = []
    if _ids_mostrados:
        from app.storage.firestore_client import get_product_by_id as _gpid_mem
        for _pid in {i.upper() for i in _ids_mostrados}:
            try:
                _pp = _gpid_mem(_pid, tienda_id=tienda_id)
            except Exception:
                _pp = None
            if (isinstance(_pp, dict) and _pp.get("nombre")
                    and isinstance(_pp.get("precio_ars"), (int, float))):
                mostrados.append({"id": _pid, "nombre": _pp["nombre"],
                                  "precio": int(_pp["precio_ars"])})
    productos_vistos = merge_productos(
        conv.get("productos_vistos") or [], productos_de_meta(meta) + mostrados)
    carrito_vigente = carrito_de_meta(meta) or (conv.get("carrito_vigente") or [])
    ultima_localidad = envio_de_meta(meta) or (conv.get("ultima_localidad") or "")
    # TODAS las localidades cotizadas con exito (multi-destino), no solo la
    # ultima: si este turno no se cotizo ninguna queda lo de memoria. Sin esto,
    # "y el total de todo?" al turno siguiente de cotizar dos destinos vuelve a
    # pedir un CP que el cliente ya dio (visto en el banco, guion multi-destino).
    ultimas_localidades = get_envio_localidades() or (
        conv.get("ultimas_localidades") or [])
    # Criterio del cliente ("lo mas barato"): se detecta determinista en el mensaje
    # y es STICKY. Una vez dicho persiste entre turnos hasta que el cliente diga
    # otro, asi el solver no vuelve a preguntar modelo ni color (arreglo B).
    criterio_cliente = detectar_criterio(raw_message) or (
        conv.get("criterio_cliente") or "")
    # Provincia del cliente: se detecta determinista y es STICKY. Una vez dada
    # persiste entre turnos y se aplica a TODOS los destinos, asi el bot no repide
    # el CP de cada pueblo (arreglo C, el 'ya te dije pueblo y provincia').
    from app.core.envio import clasificar_provincia
    provincia_envio = (clasificar_provincia(raw_message) or "") or (
        conv.get("provincia_envio") or "")

    latency_ms = int((time.time() - t0) * 1000)
    try:
        save_conversation(user_id, history, conv.get("summary", ""),
                          tienda_id=tienda_id,
                          estado_conversacion=estado_nuevo,
                          ultimo_presupuesto=presupuesto,
                          proofs_recientes=proofs_recientes,
                          productos_vistos=productos_vistos,
                          carrito_vigente=carrito_vigente,
                          ultima_localidad=ultima_localidad,
                          ultimas_localidades=ultimas_localidades,
                          criterio_cliente=criterio_cliente,
                          provincia_envio=provincia_envio,
                          pregunta_cierre_hecha=pregunta_cierre_hecha,
                          datos_cliente_parciales=datos_acumulados)
    except Exception as e:
        log.warning("interprete_libre_save_failed", trace_id=trace_id,
                    error=str(e)[:120])
    try:
        log_message(user_id, raw_message, respuesta_final,
                    meta.get("tools_called", []),
                    latency_ms, trace_id, tienda_id=tienda_id)
    except Exception as e:
        log.warning("interprete_libre_log_failed", trace_id=trace_id,
                    error=str(e)[:120])

    # Preview de la respuesta del bot en CADA turno: sin esto el texto que el bot
    # contesta no queda en Cloud Logging (solo en Firestore y solo en los WARNING
    # de correccion), y se diagnostica a ciegas. Es la salida del bot, no dato del
    # cliente; truncado para no inflar el log. Permite leer que dijo el bot por
    # trace_id sin depender de copiar a mano.
    log.info("interprete_libre_ok", trace_id=trace_id, ms=latency_ms,
             respuesta_preview=(respuesta_final or "")[:300])
    return respuesta_final
