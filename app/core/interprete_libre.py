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
    detectar_criterio)
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
- [[FAQ]] = una politica/respuesta de query_faq.
- [[PROD:<id>]] = la linea real de un producto (nombre+precio+stock), con el id de search_products (ej [[PROD:TEC0020]]).

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


def _faq_de_meta(meta: dict) -> str:
    """Respuesta VERBATIM del ultimo query_faq (texto cargado en Firestore) + las
    relacionadas, para estampar una politica tal cual la fuente, sin que el solver
    la parafrasee mal. "" si no hubo consulta de FAQ valida este turno."""
    for tc in reversed((meta or {}).get("tools_called", []) or []):
        if tc.get("name") != "query_faq":
            continue
        res = tc.get("result")
        if not isinstance(res, dict) or not res.get("encontrada"):
            continue
        partes = [str(res.get("respuesta", "")).strip()]
        for rel in res.get("relacionadas", []) or []:
            r = str((rel or {}).get("respuesta", "")).strip()
            if r:
                partes.append(r)
        return "\n".join(p for p in partes if p)
    return ""


def _estampar_productos(texto: str, tienda_id: str, trace_id: str = None) -> str:
    """Reemplaza cada [[PROD:<id>]] por nombre + precio + stock REALES del catalogo.
    El solver ELIGE que producto mostrar (curaduria de venta); el codigo pone el DATO
    (verdad de la fuente). Un id que no existe se quita: el solver no puede inventar un
    producto ni un precio. Asi el listado nace del catalogo, no del texto del modelo."""
    if not texto or "[[PROD:" not in texto:
        return texto or ""
    from app.storage.firestore_client import get_product_by_id

    def _money(n):
        try:
            return f"{int(n):,}".replace(",", ".")
        except (TypeError, ValueError):
            return None

    def _rep(m):
        pid = (m.group(1) or "").strip().upper()
        try:
            p = get_product_by_id(pid, tienda_id=tienda_id)
        except Exception:
            p = None
        if not p:
            log.warning("interprete_libre_prod_inexistente", trace_id=trace_id, pid=pid)
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

    log.info("interprete_libre_inicio", trace_id=trace_id,
             intencion=interp.get("intencion") if isinstance(interp, dict) else None,
             tools=len(tools_schema), hist=len(history))

    meta = {}
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
        "[[FAQ]]": _faq_de_meta(meta),
    }
    _tenia_marcador_presup = "[[PRESUPUESTO]]" in (respuesta or "")
    for _marca, _bloque in _marcadores.items():
        if _marca not in (respuesta or ""):
            continue
        if _bloque:
            respuesta = respuesta.replace(_marca, _bloque)
            log.info("interprete_libre_estampado", trace_id=trace_id, marca=_marca)
        else:
            respuesta = respuesta.replace(_marca, "").strip()
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
            prods_vistos = [
                {**p, "precio_ars": p.get("precio_ars", p.get("precio"))}
                for p in (estado.get("productos_vistos") or [])
                if isinstance(p, dict)
            ]
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
                instruccion_stock)
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
                        log.warning("interprete_libre_stock_persiste",
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
            _fix_faq = autocorregir_faq_numerica(
                respuesta, evidencia,
                temas_consultados=temas_de_meta(meta), trace_id=trace_id)
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
            from app.core.guardia_promesas import detectar, reescribir_sin_promesas
            clases = detectar(respuesta)
            if clases:
                log.warning("interprete_libre_promesa_prohibida", trace_id=trace_id,
                            clases=clases, respuesta_preview=respuesta[:200])
                nueva = await reescribir_sin_promesas(respuesta, clases, trace_id)
                if nueva:
                    quedan = detectar(nueva)
                    respuesta = nueva
                    if quedan:
                        log.warning("interprete_libre_promesa_persiste",
                                    trace_id=trace_id, clases=quedan)
                    else:
                        log.info("interprete_libre_promesa_reescrita",
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

    # Flag one-shot del gatillo de cierre (D): si el turno pasado el bot hizo la
    # pregunta de cierre, este turno la respuesta del cliente la decide. Se lee de
    # la conversacion y se recalcula abajo segun lo que pase este turno.
    pregunta_cierre_previa = bool(conv.get("pregunta_cierre_hecha"))
    meta_lead: dict = {}
    # No se cierra cuando la guarda forzo una pregunta de ambiguedad: el producto
    # todavia no esta elegido, cerrar seria sobre algo indefinido.
    if respuesta != settings.FALLBACK_MESSAGE and not ambiguo_forzado:
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
    productos_vistos = merge_productos(
        conv.get("productos_vistos") or [], productos_de_meta(meta))
    carrito_vigente = carrito_de_meta(meta) or (conv.get("carrito_vigente") or [])
    ultima_localidad = envio_de_meta(meta) or (conv.get("ultima_localidad") or "")
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
