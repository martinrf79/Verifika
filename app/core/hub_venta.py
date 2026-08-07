"""
HUB DE VENTA — el turno completo, en dos llamadas.

Reemplaza al hub atado. El camino viejo era: interprete que traducia el mensaje
a una taxonomia de veinte campos, solver que emitia fragmentos atados a enums,
render que estampaba, y despues once modulos que CORREGIAN al modelo -el juez,
la red de verificadores, las guardas de salida-. Tres capas peleando por la
misma verdad, y la que ganaba borraba a las otras.

Aca el control esta ANTES de que el modelo escriba:

  1. LLAMADA UNO. El modelo ve la charla y las ocho herramientas, y decide QUE
     BUSCAR. No traduce el mensaje a nada nuestro: pide datos.
  2. EJECUCION EN PARALELO. Todas las herramientas que pidio salen juntas con
     asyncio.gather. Antes cada llamada esperaba a la anterior y el turno tardaba
     entre cinco y nueve segundos.
  3. LLAMADA DOS. El modelo redacta con el JSON de resultados delante. Lo que la
     herramienta no trajo, no existe para el.
  4. UNA sola regla determinista sobre la salida: todo peso que aparezca tiene
     que venir de lo que calculo el codigo. Si no, se poda la oracion.

La plata la arma `armar_presupuesto` y vuelve como bloque ya escrito, renglon
por renglon. El modelo lo pega, no lo recompone. Esa es la unica parte del
mensaje que el modelo no redacta.

El cierre y el cobro los sigue resolviendo `leads`, la misma funcion del camino
anterior: no se duplico. La senal que antes salia del campo `intencion` del
interprete ahora sale de una herramienta que el modelo llama explicitamente,
`tomar_pedido`, y queda en la traza.
"""
import asyncio
import json
import re
import time

from app.config import get_settings
from app.core import herramientas as H
from app.core import pedido as P
from app.logger import get_logger
from app.storage.firestore_client import get_conversation, save_conversation

log = get_logger(__name__)
settings = get_settings()

_TIMEOUT_S = 14
_MAX_HERRAMIENTAS = 10
# EL BUCLE ACOTADO reemplaza a las dos rondas fijas (Martin, 2-ago). Una
# pregunta dificil tiene profundidad desconocida de antemano: buscar, mirar lo
# que volvio, darse cuenta de que falta algo, buscar distinto, y recien ahi
# contestar. Con dos rondas clavadas eso era imposible por diseño. Corta solo,
# apenas el reconciliador no encuentra huecos, asi que un saludo sigue costando
# una sola llamada y un pedido simple dos.
_MAX_RONDAS = 4

# ── LOS CANDADOS ─────────────────────────────────────────────────────────────
# Las reglas viven en UN solo lugar y valen para las dos llamadas. Antes estaban
# repartidas entre el prompt del interprete, el del solver y ocho guardas que
# corrian despues sobre el texto ya escrito.
#
# LA VOZ NO VIVE ACA (3-ago). El texto que define quien es el vendedor, como
# escribe y como piensa salio a `base_conocimiento.json`, junto al criterio, las
# movidas y los mensajes fijos. Era la ultima prosa clavada en codigo: limarle
# una linea al vendedor obligaba a tocar un modulo de Python y deployar. Ahora
# es una edicion de la fuente. Lo que queda aca es la INSTRUCCION de cada
# llamada, que es mecanica del turno, no voz.
_SISTEMA_MINIMO = ("Sos el vendedor de {negocio}. Contesta en español "
                   "argentino, de vos, corto y sin markdown. Los datos duros "
                   "te los traen las herramientas: lo que no trajeron, no lo "
                   "sabes.")


def sistema(negocio: str = "") -> str:
    """La voz del vendedor, leida de la fuente. El minimo de arriba es la red
    por si el archivo faltara: un prompt vacio dejaria al modelo sin ninguna
    atadura, que es peor que uno corto."""
    from app.core.guia_venta_prosa import identidad
    return identidad(negocio) or _SISTEMA_MINIMO.format(negocio=negocio)


_INSTRUCCION_UNO = """Si el cliente pide productos, precios, un presupuesto o un
envio, lo PRIMERO es llamar a registrar_pedido declarando lo que entendiste, en
la misma tanda que las demas herramientas. Contá los items uno por uno como los
pidio el cliente, y si algo del mensaje no cierra -cantidades que no dan, algo
nombrado en el envio que no esta en el pedido- va en contradicciones, NO lo
resuelvas vos.

Despues mira la charla y decidi que datos necesitas para
contestar el ultimo mensaje. Podes pedir varias herramientas a la vez y
conviene: si el cliente pregunta por un producto Y por el envio, pedi las dos
juntas. Si el mensaje no necesita ningun dato -un saludo, un gracias, una
respuesta a algo que vos preguntaste- contesta directamente sin herramientas.

Contesta cada cosa que te preguntaron con lo que la casa tiene escrito, no de
tu cabeza: sumale consultar_temas con UN TEMA POR CADA COSA. Si preguntaron
tres, van tres temas en la misma llamada."""

_INSTRUCCION_RONDA_DOS = """Estos son los datos que trajeron las herramientas
que pediste. Si con esto ya podes contestar todo lo que el cliente pregunto, no
pidas nada mas.

Pedi mas herramientas SOLO si ahora podes hacer algo que antes no: tipico, ya
tenes los ids de los productos y recien ahora podes armar el presupuesto con
armar_presupuesto, ver una ficha completa o chequear compatibilidad. Nunca
escribas vos un precio ni un total: eso lo arma la herramienta.

Y si el cliente pregunto cuanto sale algo, LLAMA a armar_presupuesto por lo que
ya esta definido, aunque falte elegir otra cosa. Cotiza lo que se puede y pedi
lo que falta: dejarlo sin ningun numero es peor que cotizar de a partes."""

_INSTRUCCION_DOS = """Escribile ahora la respuesta al cliente usando SOLO los
datos de abajo.

Si hay un bloque de presupuesto, pegalo TAL CUAL, sin cambiar un numero ni
reordenar los renglones, y escribi tu texto antes y despues.
Contesta TODO lo que el cliente pregunto en su mensaje, no una parte.
Si algun dato falta o la herramienta no lo trajo, decilo honesto: no lo rellenes."""


def _cliente():
    """La UNICA puerta al modelo. Sin clave devuelve None y el turno cae al
    mensaje de fallback en vez de romperse."""
    import os
    from openai import OpenAI
    key = (settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY") or "")
    key = key.split()[0] if key else ""
    if not key:
        return None
    return OpenAI(api_key=key, base_url=settings.GEMINI_BASE_URL)


def _modelo() -> str:
    return settings.GEMINI_MODEL or "gemini-3.1-flash-lite"


def _cliente_decisor():
    """El cliente de la llamada UNO, la que ELIGE herramientas.

    Por defecto es el mismo de siempre: sin DECISOR_BASE_URL devuelve `_cliente()`
    y el decisor va por Gemini, igual que antes de existir esta funcion. Con la
    base_url puesta apunta a otro provider compatible con la API de OpenAI, para
    poder MEDIR si otro modelo decide mejor o mas rapido. Es config, no una capa:
    el REDACTOR nunca pasa por aca, sigue en Gemini."""
    import os
    from openai import OpenAI
    base = (settings.DECISOR_BASE_URL or "").strip()
    if not base:
        return _cliente()
    key = (settings.DECISOR_API_KEY or os.environ.get("DECISOR_API_KEY") or "")
    key = key.split()[0] if key else ""
    if not key:
        # Sin la clave del decisor no se cae el turno: se vuelve a Gemini, que es
        # el camino que ya funciona. Un decisor mal configurado no puede dejar
        # mudo al bot en produccion.
        log.warning("hub_venta_decisor_sin_clave", base_url=base)
        return _cliente()
    return OpenAI(api_key=key, base_url=base)


def _modelo_decisor() -> str:
    """El modelo de la llamada UNO. Por default el mismo que redacta; se le
    puede poner uno mas grande SOLO acá, que es donde se decide."""
    return settings.DECISOR_MODEL or _modelo()


def _extra_decisor() -> dict:
    """`reasoning_effort` es de Gemini. Mandarselo a Groq o a OpenAI hace saltar
    la llamada con 400, asi que solo viaja cuando el decisor va por Gemini. Con
    Gemini manda DECISOR_REASONING, o sea el decisor sigue PENSANDO."""
    if (settings.DECISOR_BASE_URL or "").strip():
        return {}
    return {"reasoning_effort": settings.DECISOR_REASONING}
def _memoria_texto(estado: dict, history: list, tienda_id: str = "") -> str:
    """Lo que el modelo tiene que recordar de la charla. Reemplaza a los campos
    que el interprete rellenaba a mano: el foco, lo ya mostrado y el criterio no
    se declaran, se leen de la conversacion como los lee una persona."""
    partes = []
    resumen = str(estado.get("resumen_charla") or "").strip()
    if resumen:
        partes.append("De lo hablado antes: " + resumen)
    # LO YA MOSTRADO VIAJA CON SU ID. El cliente no lo ve nunca -el hub lo poda
    # de la prosa-, pero el modelo lo NECESITA para las herramientas: sin el id,
    # en el turno siguiente no puede armar el presupuesto de algo que ya mostro y
    # el intento sale con id invalido. Charla viva del 2-ago: "dale la llevo" dos
    # turnos despues de ver la notebook y armar_presupuesto no pudo resolverla.
    vistos = []
    for p in (estado.get("productos_vistos") or [])[-8:]:
        if isinstance(p, dict) and p.get("nombre"):
            pid = str(p.get("id") or "").upper()
            linea = f"{p['nombre']} [{pid}]" if pid else str(p["nombre"])
            # EL ORDEN EN QUE SE MOSTRARON, que es lo que el ordinal usa. "El
            # segundo teclado que me mostraste" no se puede resolver contra una
            # lista plana de nombres; con el turno y la posicion por categoria,
            # si.
            if p.get("posicion"):
                linea += f" (fue la opcion {p['posicion']}"
                if p.get("categoria"):
                    linea += f" de {p['categoria']}"
                if p.get("turno"):
                    linea += f", turno {p['turno']}"
                linea += ")"
            vistos.append(linea)
    if vistos:
        partes.append("Productos que ya le mostraste, con su id entre corchetes "
                      "para que puedas usarlos en las herramientas (el id NUNCA "
                      "se escribe en el mensaje) y en que orden se los "
                      "mostraste, para cuando diga 'el primero' o 'el segundo "
                      "teclado': " + ", ".join(dict.fromkeys(vistos)))
    # LO QUE EL CLIENTE SACO. Va explicito porque es lo primero que se pierde
    # cuando la charla se comprime, y volver a meter un producto retractado es
    # de los errores que mas enojan al cliente.
    fuera = [str(d) for d in (estado.get("descartados") or []) if d]
    if fuera:
        partes.append("El cliente SACO estos del pedido o dijo que no los "
                      "queria. NO los vuelvas a sumar salvo que los pida de "
                      "nuevo explicitamente: " + ", ".join(fuera))
    carrito = estado.get("carrito") or []
    if carrito:
        partes.append("Pedido vigente: " + ", ".join(
            f"{c.get('cantidad', 1)}x {c.get('nombre')}" for c in carrito))
        # LA FICHA DE LO QUE YA ESTA SOBRE LA MESA, no solo el nombre. Charla
        # viva del 2-ago: el cliente pidio "lo que menos partes chinas tenga"
        # sobre el pedido ya armado y el bot contesto que NO tenia el dato de
        # origen. Lo tenia: esta en la ficha de cada producto del pedido. No lo
        # veia porque ese turno no llamo a buscar_productos, y el pedido vigente
        # solo viajaba como una lista de nombres.
        fichas = []
        for c in carrito[:6]:
            pid = str(c.get("id") or "").upper()
            if not pid:
                continue
            try:
                from app.storage.firestore_client import get_product_by_id
                p = get_product_by_id(pid, tienda_id=tienda_id)
            except Exception:
                p = None
            if not isinstance(p, dict):
                continue
            f = H._ficha(p, tienda_id)
            linea = f"- {f.get('nombre')}: {f.get('precio')}"
            if f.get("marca"):
                linea += f" | marca {f['marca']}"
            if f.get("origen"):
                linea += f" | origen: {f['origen']}"
            if f.get("garantia"):
                linea += f" | garantia {f['garantia']}"
            # LAS SPECS TAMBIEN. Sin ellas el bot contestaba "no cuento con el
            # dato tecnico" sobre una memoria que se llama "DDR4 3200 8GB"
            # (charla viva del 2-ago, turno 4). El dato estaba en la fuente y en
            # el propio nombre; lo que faltaba era que el turno lo tuviera
            # delante sin depender de que el modelo pidiera la ficha.
            specs = f.get("specs") if isinstance(f.get("specs"), dict) else {}
            if specs:
                linea += " | " + "; ".join(
                    f"{k}: {v}" for k, v in list(specs.items())[:8])
            fichas.append(linea)
        if fichas:
            partes.append("Ficha de lo que ya esta en el pedido (dato REAL de "
                          "la fuente, contestá con esto):\n" + "\n".join(fichas))
    presu = str(estado.get("presupuesto") or "").strip()
    if presu:
        partes.append("Presupuesto vigente, calculado por el codigo. Si lo "
                      "volves a mostrar, pegalo TAL CUAL, no lo reescribas ni "
                      "cambies un producto:\n" + presu)
    locs = estado.get("localidades_envio") or []
    if locs:
        partes.append("Destinos ya dados: " + ", ".join(locs))
    dc = estado.get("datos_cliente") or {}
    if dc:
        partes.append("Datos que ya dio: " + ", ".join(
            f"{k}: {v}" for k, v in dc.items()))
    return "\n".join(partes)


def _log_fuente(llamadas: list, trace_id: str, ronda: int) -> None:
    """QUE TRAJO LA FUENTE ESTE TURNO. Una linea, para poder medir lo que hasta
    hoy no se medía: si el modelo pide la MOVIDA cuando el turno es una
    situacion de venta -esta caro, una queja, una despedida- o si la improvisa.

    `hub_venta_pedidos` ya dice que herramienta se pidio; esto dice que volvio:
    por cada tema servido, con QUE mitades vino. Un turno de objecion sin
    `movida` en esta linea es el modelo vendiendo de memoria con la movida
    escrita al lado, sin usarla; y un tema que vuelve `sin_nada` es un agujero
    de la fuente, no del modelo."""
    servidos = []
    for l in llamadas:
        if l.get("herramienta") != "consultar_temas":
            continue
        for t in ((l.get("resultado") or {}).get("temas") or []):
            mitades = [k for k in ("politica", "criterio", "movida") if t.get(k)]
            servidos.append((t.get("tema"), "+".join(mitades) or "sin_nada"))
    if servidos:
        log.info("hub_venta_fuente", trace_id=trace_id, ronda=ronda,
                 temas=servidos)


def _mensajes(negocio: str, memoria: str, history: list, mensaje: str,
              instruccion: str, datos: str = "") -> list:
    msgs = [{"role": "system", "content": sistema(negocio)}]
    if memoria:
        msgs.append({"role": "system", "content": memoria})
    # TODO EL HISTORIAL QUE EL SISTEMA GUARDA, no la mitad. Estaba clavado en
    # `[-10:]`, que son MENSAJES y no turnos: en el turno 12 el modelo veia
    # SIETE turnos mientras Firestore tenia DIEZ guardados y pagos. La memoria
    # ya estaba comprada y el prompt la tiraba. `HISTORY_LIMIT` manda en los dos
    # lados: lo que se guarda es lo que se muestra.
    for h in (history or [])[-(settings.HISTORY_LIMIT * 2):]:
        rol = h.get("role")
        if rol in ("user", "assistant") and h.get("content"):
            msgs.append({"role": rol, "content": str(h["content"])[:900]})
    cuerpo = f"Mensaje del cliente: {mensaje}\n\n{instruccion}"
    if datos:
        cuerpo += "\n\nDATOS QUE TRAJERON LAS HERRAMIENTAS:\n" + datos
    msgs.append({"role": "user", "content": cuerpo})
    return msgs


async def _pedir_herramientas(negocio, memoria, history, mensaje, tienda_id,
                              trace_id, llamadas=None, revision=""):
    """QUE BUSCAR. Devuelve (lista de pedidos, texto directo si no pidio nada).

    Con `llamadas` es la SEGUNDA ronda: el modelo ve lo que ya trajo y puede
    pedir lo que recien ahora es posible. Existe porque en una sola tanda no se
    puede encadenar, y el caso que lo pario es el central del negocio: para
    armar un presupuesto hacen falta los ids, y los ids los trae otra
    herramienta. Medido en la primera charla viva: el modelo pidio los envios,
    no pidio los productos, escribio los precios de memoria y la regla de plata
    se los podo enteros. El cliente recibio "Productos:" y nada abajo."""
    cli = _cliente_decisor()
    if cli is None:
        return [], ""
    esquemas = H.esquemas(tienda_id)
    if llamadas:
        # AHORRO MEDIDO: en las vueltas de encadenado el modelo ya declaró el
        # pedido y ya buscó. Mandarle otra vez los ocho esquemas cuesta ~1200
        # tokens por turno al pedo. Van solo las que puede encadenar de verdad.
        encadenables = {"buscar_productos", "ficha_producto", "cotizar_envio",
                        "armar_presupuesto", "ver_compatibilidad",
                        "tomar_pedido", "consultar_temas"}
        esquemas = [e for e in esquemas
                    if e.get("function", e).get("name") in encadenables]
        # EL FALTANTE VA PRIMERO, NO AL FINAL. `_INSTRUCCION_RONDA_DOS` abre con
        # "si con esto ya podes contestar, no pidas nada mas", y la correccion
        # del reconciliador se pegaba DESPUES. Medido el 5-ago con el modelo
        # vivo, con y sin razonamiento: el reconciliador cazo bien que la
        # condicion de origen no se habia aplicado, y en la ronda dos el modelo
        # no pidio NADA las dos veces. El desaliento le ganaba a la correccion,
        # asi que el turno terminaba en el muro que el reconciliador acababa de
        # detectar. Un chequeo que detecta y no corrige no sirve de nada.
        instr = ((revision + "\n\n" + _INSTRUCCION_RONDA_DOS) if revision
                 else _INSTRUCCION_RONDA_DOS)
        msgs = _mensajes(negocio, memoria, history, mensaje, instr,
                         H.contexto_json(llamadas))
    else:
        msgs = _mensajes(negocio, memoria, history, mensaje, _INSTRUCCION_UNO)

    def _call():
        # max_tokens ALTO a proposito: el pensamiento se descuenta de acá. Con
        # 900 y thinking prendido el JSON de tool_calls sale cortado o vacío,
        # que es el bug del 10-jun por el que se apagó el thinking en su
        # momento. El tope alto no se cobra si no se usa: se cobra lo generado.
        r = cli.chat.completions.create(
            model=_modelo_decisor(), messages=msgs, tools=esquemas,
            # TEMPERATURA CERO EN EL DECISOR. Elegir que argumento pedir no es
            # una tarea creativa: es TRADUCCION del pedido del cliente a los
            # campos de la fuente. La temperatura ahi no compra nada y vende
            # inconsistencia. Medido el 5-ago con la clave paga: la MISMA
            # pregunta -"el mouse que menos partes chinas tenga"- en dos vueltas
            # seguidas mando la condicion de origen una vez y la otra no. La
            # respuesta al cliente cambiaba por el dado, no por el mensaje.
            # El redactor sigue en 0.6, que ahi si se quiere variedad: es la voz.
            tool_choice="auto", temperature=0.0, max_tokens=3000,
            extra_body=_extra_decisor())
        m = r.choices[0].message
        pedidos = []
        for tc in (getattr(m, "tool_calls", None) or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except (ValueError, TypeError):
                args = {}
            pedidos.append({"nombre": tc.function.name, "args": args})
        return json.dumps({"pedidos": pedidos, "texto": m.content or ""},
                          ensure_ascii=False)

    from app.core.llm_reintento import llamar_con_reintento
    try:
        raw = await llamar_con_reintento(_call, timeout_s=_TIMEOUT_S,
                                         trace_id=trace_id)
        data = json.loads(raw)
        return data.get("pedidos") or [], data.get("texto") or ""
    except Exception as e:
        log.warning("hub_venta_llamada_uno_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:160]}")
        return [], ""


async def _ejecutar_en_paralelo(pedidos: list, tienda_id: str,
                                trace_id: str) -> list:
    """PARALELO de verdad: las herramientas son sincronas -tocan Firestore y las
    tablas- asi que cada una va a su hilo y se esperan todas juntas. Antes esto
    era una fila y el turno pagaba la suma de todas."""
    if not pedidos:
        return []
    # El tope existe para que un modelo desbocado no dispare veinte consultas,
    # pero CORTAR EN SILENCIO es peor que el problema que evita: el 1-ago pidio
    # ocho fichas, se ejecutaron seis y las dos que faltaron no aparecian en
    # ningun lado. Si se corta, se dice.
    if len(pedidos) > _MAX_HERRAMIENTAS:
        log.warning("hub_venta_pedidos_recortados", trace_id=trace_id,
                    pidio=len(pedidos), corre=_MAX_HERRAMIENTAS,
                    descartadas=[p["nombre"] for p in pedidos[_MAX_HERRAMIENTAS:]])
    pedidos = pedidos[:_MAX_HERRAMIENTAS]
    tareas = [asyncio.to_thread(H.ejecutar, p["nombre"], p.get("args") or {},
                                tienda_id)
              for p in pedidos]
    resultados = await asyncio.gather(*tareas, return_exceptions=True)
    llamadas = []
    for p, r in zip(pedidos, resultados):
        if isinstance(r, BaseException):
            log.warning("hub_venta_herramienta_excepcion", trace_id=trace_id,
                        herramienta=p["nombre"], error=str(r)[:160])
            r = {"estado": "error", "nombre": p["nombre"]}
        llamadas.append({"herramienta": p["nombre"], "pedido": p.get("args") or {},
                         "resultado": r})
    return llamadas


async def _redactar(negocio, memoria, history, mensaje, llamadas, trace_id,
                    obligacion=""):
    """LLAMADA FINAL. El modelo escribe con el JSON delante.

    `obligacion` es lo que el RECONCILIADOR encontró que no cierra y el modelo
    no puede resolver eligiendo. Va al final del prompt, que es donde más pesa.
    """
    cli = _cliente()
    if cli is None:
        return ""
    datos = H.contexto_json(llamadas)
    instr = _INSTRUCCION_DOS + (("\n\n" + obligacion) if obligacion else "")
    msgs = _mensajes(negocio, memoria, history, mensaje, instr, datos)

    def _call():
        r = cli.chat.completions.create(
            model=_modelo(), messages=msgs, temperature=0.6, max_tokens=1200,
            extra_body={"reasoning_effort": settings.REDACTOR_REASONING})
        return r.choices[0].message.content or ""

    from app.core.llm_reintento import llamar_con_reintento
    try:
        return await llamar_con_reintento(_call, timeout_s=_TIMEOUT_S,
                                          trace_id=trace_id)
    except Exception as e:
        log.warning("hub_venta_llamada_dos_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:160]}")
        return ""


_RE_ORACION = re.compile(r"(?<=[.!?])\s+|\n")
_RE_ID_INTERNO = re.compile(
    r"[\s,]*\(\s*(?:(?:id|sku|codigo)\s*[:=]?\s*)?"
    r"[A-Z]{2,5}\d{2,}(?:\s*/\s*[A-Z]{2,5}\d{2,})*\s*\)"
    r"|[\s,]*\b(?:id|sku|codigo)\s*[:=]\s*[A-Z]{2,5}\d{2,}",
    re.IGNORECASE)


def _sin_plata_inventada(texto: str, llamadas: list, bloque: str,
                         trace_id: str, previo: str = "",
                         vistos: list | None = None) -> str:
    """LA REGLA. Todo peso que salga tiene que haberlo calculado el codigo.

    Es una sola, y reemplaza a los once verificadores del camino anterior. Con
    ellos el problema no era que el modelo alucinara plata: era que cada capa
    juzgaba con evidencia distinta y terminaba podando lo que el codigo habia
    estampado. Aca la evidencia es exactamente lo que se le inyecto, asi que un
    numero fundado no puede quedar sin respaldo.

    Los renglones del bloque de presupuesto no se tocan nunca: son la cuenta.
    """
    respaldados = H.montos_respaldados([l.get("resultado") for l in llamadas])
    # EL PRESUPUESTO DE UN TURNO ANTERIOR SIGUE RESPALDADO: lo calculo el
    # codigo, no el modelo. Sin esto, cuando el cliente vuelve sobre el pedido y
    # el turno no rearma la cuenta, la regla podaba renglon por renglon una
    # cuenta REAL y al cliente le llegaba el reparto de envios suelto, sin
    # precios (charla viva del 2-ago, turnos 3, 4 y 6).
    if previo:
        respaldados |= H.montos_respaldados([previo])
    # LO YA MOSTRADO TAMBIEN ESTA RESPALDADO. Esos precios los trajo una
    # herramienta en un turno anterior y los estampo el codigo desde el
    # catalogo. Sin esto, "el primero que me mostraste, cuanto era?" terminaba
    # con el precio podado y el turno MUDO: al cliente le llego solo "¿Querés
    # que avancemos?" (banco repetido, guion 70). El numero era real; lo que
    # faltaba era reconocerlo.
    if vistos:
        respaldados |= {int(p["precio"]) for p in vistos
                        if isinstance(p, dict)
                        and isinstance(p.get("precio"), (int, float))}
    fuera = H.plata_inventada(texto, respaldados)
    if not fuera:
        return texto
    lineas_bloque = {l.strip() for l in (bloque or "").splitlines() if l.strip()}
    salida, podadas = [], 0
    for linea in (texto or "").splitlines():
        if linea.strip() in lineas_bloque:
            salida.append(linea)
            continue
        trozos = [t for t in _RE_ORACION.split(linea) if t is not None]
        quedan = [t for t in trozos if not H.plata_inventada(t, respaldados)]
        if len(quedan) != len(trozos):
            podadas += len(trozos) - len(quedan)
        salida.append(" ".join(x for x in quedan if x.strip()))
    log.warning("hub_venta_plata_inventada", trace_id=trace_id,
                montos=fuera[:6], oraciones_podadas=podadas)
    return _sin_titulos_huerfanos(
        re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip())


_RE_TITULO = re.compile(r"^\s*\**\s*[A-Za-zÁÉÍÓÚÑáéíóúñ ]{3,24}:\s*\**\s*$")


def _sin_titulos_huerfanos(texto: str) -> str:
    """Un titulo que quedo sin nada abajo se va con lo que anunciaba.

    Medido en la primera charla viva: la regla podo los renglones de precio que
    el modelo habia inventado -bien podados- y al cliente le llego "Productos:"
    y despues nada. La poda tiene que dejar un mensaje que se pueda leer, no un
    esqueleto."""
    lineas = (texto or "").splitlines()
    fuera = []
    for i, l in enumerate(lineas):
        if not _RE_TITULO.match(l):
            continue
        siguiente = next((x for x in lineas[i + 1:] if x.strip()), "")
        if not siguiente or _RE_TITULO.match(siguiente):
            fuera.append(i)
    salida = [l for i, l in enumerate(lineas) if i not in fuera]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip()


_RE_CBU = re.compile(r"\b\d{18,26}\b")
_RE_LINEA_COBRO = re.compile(
    r"(?im)^.*\b(cbu|cvu|alias|titular|banco)\b\s*:?.*$")


def _sin_cobro_inventado(texto: str, tienda_id: str, trace_id: str) -> str:
    """UN CBU QUE NO ES EL DE LA TIENDA NO SALE. Nunca.

    El peor error medido en el camino nuevo, charla viva del 2-ago: el cliente
    pidio los datos para transferir, no habia presupuesto armado, el cierre no
    entrego nada y el modelo se invento un CBU de 22 digitos, un alias y un
    banco. Un cliente le manda la plata a una cuenta que no existe.

    La regla de la plata no lo veia -mira montos de cuatro a siete digitos- y
    ninguna otra tampoco. Asi que va su propio candado, del mismo tipo: se
    compara contra la fuente y lo que no coincide se borra. La herramienta
    `tomar_pedido` ya le entrega los datos REALES; esto es la red por si igual
    escribe otros."""
    if not _RE_CBU.search(texto or "") and "alias" not in (texto or "").lower():
        return texto
    try:
        from app.core.pago import datos_transferencia
        d = datos_transferencia(tienda_id) or {}
    except Exception:
        d = {}
    # Cada campo se juzga contra SU valor real, no contra la bolsa entera: con
    # la comparacion global se borraba la linea del titular aunque el CBU fuera
    # el correcto, y el mensaje quedaba con la cuenta a medias.
    campos = {"cbu": str(d.get("cbu") or ""), "cvu": str(d.get("cbu") or ""),
              "alias": str(d.get("alias") or ""),
              "titular": str(d.get("titular_cuenta") or ""),
              "banco": str(d.get("banco") or "")}
    salida, borradas, quedo_real = [], [], False
    for linea in (texto or "").splitlines():
        m = _RE_LINEA_COBRO.match(linea)
        if not m:
            salida.append(linea)
            continue
        baja = linea.lower()
        etiqueta = m.group(1).lower()
        real = campos.get(etiqueta, "").lower()
        if real and real in baja:
            salida.append(linea)
            quedo_real = True
        else:
            borradas.append(linea.strip()[:60])
    if borradas:
        log.error("hub_venta_cobro_inventado", trace_id=trace_id,
                  lineas=borradas[:4])
        if not quedo_real:
            salida.append("Para pasarte los datos de pago necesito confirmarte "
                          "primero el total. Decime y te los paso enseguida.")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip()


_RE_JSON_FILTRADO = re.compile(
    r'(?m)^.*(?:\[\s*\{\s*"herramienta"|"resultado"\s*:\s*\{|'
    r'"estado"\s*:\s*"(?:ok|encontrado|no_encontrado)").*$')


def _sin_json_filtrado(texto: str, trace_id: str) -> str:
    """El JSON que se le inyecta NO es parte del mensaje. Charla viva del 2-ago:
    el modelo copio el bloque entero de `cotizar_envio` al medio de la respuesta
    y al cliente le llego el volcado crudo de la herramienta."""
    limpio = _RE_JSON_FILTRADO.sub("", texto or "")
    if limpio != (texto or ""):
        log.warning("hub_venta_json_filtrado", trace_id=trace_id)
    return re.sub(r"\n{3,}", "\n\n", limpio).strip()


_RE_ORACIONES = re.compile(r"[^.!?\n]+[.!?]?")
# La oracion habla de un beneficio de precio...
_RE_BENEFICIO = re.compile(
    r"descuento|rebaja|precio especial|bonificaci[oó]n|"
    r"mejor(?:ar|amos|o|arte)\s+(?:el\s+)?precio|hacer(?:te)?\s+(?:un\s+)?precio",
    re.IGNORECASE)
# ...y lo OFRECE o lo deja abierto. El orden de las dos piezas no importa: "puedo
# consultar que descuento aplicarte" y "el descuento lo puedo consultar" son la
# misma promesa, y la primera version del candado solo veia una de las dos.
_RE_GESTION = re.compile(
    r"consult|averigu|gestion|puedo|podemos|podr[ií]a|veamos|vemos|"
    r"area comercial|te lo hago|te lo dejo|para vos|aplicart|ofrecert",
    re.IGNORECASE)
# Los descuentos REALES de la tienda. Si la oracion nombra uno, es politica.
_RE_DESCUENTO_REAL = re.compile(
    r"transferenc|mayorist|cuotas sin inter[eé]s", re.IGNORECASE)


def _sin_descuento_inventado(texto: str, trace_id: str) -> str:
    """NO SE OFRECE UN DESCUENTO QUE NO EXISTE. Ni siquiera como posibilidad.

    Banco repetido del 1-ago, guion de objecion de precio: ante "si te llevo dos
    me haces precio?" el bot contesto que iba a "consultar con el area comercial
    que descuento especial podemos aplicarte". Dos mentiras en una linea: no hay
    area comercial que consultar, y el descuento no existe. Es la puerta por la
    que se cuela una promesa comercial que despues alguien tiene que sostener.

    Los descuentos REALES de la tienda -transferencia, mayorista, cuotas- salen
    de consultar_temas y no los toca esta regla."""
    fuera = []
    for m in _RE_ORACIONES.finditer(texto or ""):
        frase = m.group(0)
        if (_RE_BENEFICIO.search(frase) and _RE_GESTION.search(frase)
                and not _RE_DESCUENTO_REAL.search(frase)):
            fuera.append(frase)
    if not fuera:
        return texto
    limpio = texto
    for frase in fuera:
        limpio = limpio.replace(frase, "")
    log.warning("hub_venta_descuento_inventado", trace_id=trace_id,
                frases=[f[:70] for f in fuera[:3]])
    return re.sub(r"\n{3,}", "\n\n", limpio).strip()


_RE_NARRACION = re.compile(
    r"(?im)^[^.!?\n]*\b(?:el\s+sistema\s+(?:me|dice|indica|marca|tir[oó])|"
    r"la\s+herramienta|mi\s+sistema|en\s+mi\s+base\s+de\s+datos|"
    r"seg[uú]n\s+el\s+sistema|el\s+estado\s+es\s+ambiguo|"
    r"me\s+aparecen?\s+(?:varios|en\s+el\s+sistema))\b[^.!?\n]*[.!?]?")


_RE_NIEGA = re.compile(
    r"no\s+(?:vendemos|trabajamos|manejamos|comercializamos|tenemos|"
    r"contamos\s+con|ofrecemos|dispon)", re.IGNORECASE)

# NEGAR EL RUBRO NO ES LO MISMO QUE NO TENER UN DATO, y esta guardia no las
# distinguia. Medido el 5-ago, con el estado `sin_dato_en_la_fuente` recien
# puesto: ante "auriculares con cancelacion de ruido activa" el bot contestaba
# bien -"no tenemos ese dato de los auriculares en la ficha"- y esta funcion le
# BORRABA esa oracion, porque dice "no tenemos" y nombra una categoria que
# acabamos de traer. Quedaba "te muestro los que sí tengo", sin decir nunca que
# el dato faltaba. La guardia contra la alucinacion se comia la honestidad, en
# silencio y sin log.
#
# Es la misma familia que la poda de prosa que borraba la respuesta de spec por
# tener digitos: una guardia escrita para un caso que muerde a su vecino. La
# frase se salva cuando habla del DATO -la ficha, la especificacion, lo que no
# esta confirmado-, porque ahi no esta negando que vendamos el rubro.
_RE_ES_SOBRE_EL_DATO = re.compile(
    r"\b(?:ese|este|esa|esta|el|la)\s+(?:dato|detalle|especificaci|info)|"
    r"\bfichas?\b|\bespecifica|\bconfirmad|\bno\s+figura|\bno\s+lo\s+dice",
    re.IGNORECASE)


def _sin_negar_lo_traido(texto: str, llamadas: list, trace_id: str) -> str:
    """NO SE NIEGA UNA CATEGORIA QUE LA HERRAMIENTA ACABA DE TRAER.

    Banco repetido del 1-ago, guion de pregunta combinada: el cliente pregunto
    por memoria RAM de 16GB, la herramienta devolvio memorias REALES del
    catalogo -las nuestras son de 8- y el bot contesto "no vendemos modulos de
    memoria RAM sueltos". Con las memorias delante. Es la alucinacion mas cara
    que hay: le cierra la puerta a un cliente que queria comprar algo que
    tenemos.

    Es la misma familia que la regla de la plata: se contrasta la salida contra
    exactamente lo que se le inyecto. Si el texto niega el rubro de un producto
    que vino en los resultados, esa oracion se va."""
    categorias = set()
    for l in (llamadas or []):
        r = l.get("resultado") or {}
        if r.get("estado") in ("no_vendemos", "no_encontrado"):
            continue
        for p in (r.get("productos") or []):
            if isinstance(p, dict) and p.get("categoria"):
                categorias.add(H._norm(p["categoria"]))
        prod = r.get("producto")
        if isinstance(prod, dict) and prod.get("categoria"):
            categorias.add(H._norm(prod["categoria"]))
    if not categorias:
        return texto
    fuera = []
    for m in _RE_ORACIONES.finditer(texto or ""):
        frase = m.group(0)
        if not _RE_NIEGA.search(frase):
            continue
        if _RE_ES_SOBRE_EL_DATO.search(frase):
            # Habla del dato que falta, no del rubro. Se deja: es justamente la
            # respuesta honesta que queremos.
            continue
        palabras = set(H._norm(frase).replace(",", " ").split())
        for cat in categorias:
            # POR TOKEN, no por la frase pegada. El plural de una categoria de
            # dos palabras cae en la PRIMERA -"memorias ram"-, asi que buscar
            # "memoria ram" como substring no matcheaba y la negacion pasaba
            # igual: medido en la tercera tanda, el bot volvio a decir "no
            # vendemos memorias RAM por separado" con las memorias delante.
            fichas = [t for t in cat.split() if len(t) > 2]
            if fichas and all(any(t == w or t == w.rstrip("s")
                                  or w == t.rstrip("s") for w in palabras)
                              for t in fichas):
                fuera.append(frase)
                break
    if not fuera:
        return texto
    limpio = texto
    for frase in fuera:
        limpio = limpio.replace(frase, "")
    log.error("hub_venta_nego_lo_traido", trace_id=trace_id,
              categorias=sorted(categorias)[:4],
              frases=[f[:70] for f in fuera[:3]])
    return re.sub(r"\n{3,}", "\n\n", limpio).strip()


# ── LA AFIRMACION SOBRE LOS 880 ─────────────────────────────────────────────
# LA ALUCINACION, textual, medida en produccion el 6-ago: "todos los productos
# que trabajo en este momento tienen componentes de origen chino, por lo que no
# puedo cumplir con esa restriccion especifica". Es falso, y lo desmiente el
# bloque que el propio mensaje pega DOS RENGLONES MAS ABAJO: "donde si se cumple
# del todo lo que pedis es en: almacenamiento externo, procesador". El bot se
# contradijo a si mismo dentro del mismo mensaje y le cerro la puerta a un
# cliente que estaba comprando.
#
# La prohibicion ya estaba escrita en la instruccion de la herramienta -"PROHIBIDO
# afirmar nada sobre el catalogo entero: viste unos pocos productos, no los
# 880"- y el modelo la piso igual. Es literalmente la rueda que `_bloque_hallazgo`
# describe: cada vez que se pierde la pelea se le agregan palabras al prompt. Se
# corta como se cortaron las otras dos, contra un HECHO que el codigo ya calculo.
#
# EL HECHO ES PROVABLE, no es criterio: `donde_si_se_cumple` sale de recorrer los
# 880 y devuelve las categorias donde las condiciones SI se cumplen del todo. Si
# esa lista tiene algo, "ninguno de mis productos cumple" es demostrablemente
# falso y la oracion se va. Si esta vacia, esta guardia no toca nada.
_RE_UNIVERSAL = re.compile(
    r"todos?\s+(?:los|las|mis)|ningun[oa]?\s+de\s+(?:los|las|mis)|"
    r"no\s+(?:tengo|tenemos|hay|manejo|manejamos|trabajo|trabajamos|"
    r"vendo|vendemos)\s+(?:ningun|ninguna|nada|nigun)|"
    r"(?:todo|nada)\s+(?:el|mi)\s+cat[aá]logo|la\s+totalidad",
    re.IGNORECASE)
# El sustantivo GLOBAL. Sin esto la guardia se comeria "todos los auriculares
# que tengo se fabrican en China", que es un hecho VERDADERO, util y acotado al
# rubro: exactamente la honestidad que queremos. Solo cae la frase que habla del
# catalogo entero.
_RE_TODO_EL_CATALOGO = re.compile(
    r"\b(?:productos?|art[ií]culos?|[ií]tems?|mercader[ií]a|cat[aá]logo|"
    r"stock|marcas?)\b|lo\s+que\s+(?:trabajo|manejo|tengo|vendo|vendemos|"
    r"trabajamos|manejamos)", re.IGNORECASE)


def _sin_afirmar_sobre_el_catalogo(texto: str, llamadas: list,
                                   trace_id: str) -> str:
    """NO SE AFIRMA NADA SOBRE LOS 880 CUANDO EL CODIGO SABE QUE ES FALSO.

    Misma familia que `_sin_plata_inventada` y `_sin_negar_lo_traido`: se
    contrasta la salida contra un dato que el codigo YA calculo sobre la fuente
    entera, no contra una opinion. Ver el comentario de arriba.
    """
    cumplen: list = []
    categorias: set = set()
    for l in (llamadas or []):
        r = l.get("resultado") or {}
        for d in (r.get("donde_si_se_cumple") or []):
            if d not in cumplen:
                cumplen.append(d)
        for p in (r.get("productos") or []):
            if isinstance(p, dict) and p.get("categoria"):
                categorias.add(H._norm(p["categoria"]))
    if not cumplen:
        return texto
    fuera = []
    for m in _RE_ORACIONES.finditer(texto or ""):
        frase = m.group(0)
        if not _RE_UNIVERSAL.search(frase):
            continue
        if not _RE_TODO_EL_CATALOGO.search(frase):
            continue
        # Acotada a un rubro que trajimos: es un hecho del rubro, no del
        # catalogo. Se deja, por el mismo motivo que `_RE_ES_SOBRE_EL_DATO`
        # salva la abstencion honesta en la guardia de al lado.
        palabras = set(H._norm(frase).replace(",", " ").split())
        acotada = False
        for cat in categorias:
            fichas = [t for t in cat.split() if len(t) > 2]
            if fichas and all(any(t == w or t == w.rstrip("s")
                                  or w == t.rstrip("s") for w in palabras)
                              for t in fichas):
                acotada = True
                break
        if not acotada:
            fuera.append(frase)
    if not fuera:
        return texto
    limpio = texto
    for frase in fuera:
        limpio = limpio.replace(frase, "")
    log.error("hub_venta_afirmo_sobre_el_catalogo", trace_id=trace_id,
              se_cumple_en=cumplen[:4], frases=[f[:80] for f in fuera[:3]])
    return re.sub(r"\n{3,}", "\n\n", limpio).strip()


# ── EL RENGLON DE CUENTA, UNA SOLA DEFINICION Y DOS USOS ────────────────────
#
# EL BUG QUE ESTO CIERRA, y es de los caros. Este modulo definia `_RE_RENGLON_CUENTA`
# DOS VECES a nivel de modulo: aca, con `.*$` al final para poder BORRAR el
# renglon entero, y otra vez 90 lineas mas abajo, mas estricta pero SIN `.*$`,
# para poder MATCHEAR el arranque. La segunda pisa a la primera al importar, asi
# que `_bloque_entero_o_repuesto` -escrito contra la primera- terminaba corriendo
# con la segunda y su `.sub("")` borraba solo el ARRANQUE del renglon.
#
# Lo que le llegaba al cliente, medido sobre el guion 76 reproducido entero:
#
#     57.500 c/u = $115.000
#      $201.000
#     3 envios): $24.000
#      $225.000
#     70%): $157.500
#
# Una cuenta descuartizada, con parentesis huerfanos y sin la palabra Total, y
# abajo el bloque bueno pegado al lado. Nadie lo vio porque el piso lo absorbia
# y el chequeo de "Total" del guion matcheaba de casualidad con la frase "hay
# varios igual de cerca -210 en TOTAL-" del otro bloque. Dos casualidades tapando
# un renglon roto.
#
# Ahora hay UNA regla y dos formas de la misma: `_ARRANQUE` para preguntar si un
# renglon es de cuenta, `_ENTERO` para borrarlo. Derivada, no copiada: si se
# edita el patron, las dos se mueven juntas.
_RE_ARRANQUE_CUENTA = re.compile(
    r"(?im)^\s*(?:presupuesto\s*:|subtotal\s*:|env[ií]o?\s*[(:]|"
    r"total\s*:|total final\s*:|pago dividido\s*:"
    r"|-?\s*\d+\s*x\s+.+:\s*\$"
    r"|-\s*(?:mercado pago|transferencia)\s*\()")
_RE_RENGLON_CUENTA_ENTERO = re.compile(_RE_ARRANQUE_CUENTA.pattern + r".*$",
                                       re.IGNORECASE | re.MULTILINE)
# "¿Este mensaje ya lleva una cuenta?". Solo los marcadores que NO aparecen en
# otra cosa: un total, un subtotal o el encabezado. Deliberadamente mas angosta
# que las dos de arriba.
_RE_HAY_CUENTA = re.compile(
    r"(?im)^\s*(?:presupuesto\s*:|subtotal\s*:|total(?:\s+final)?\s*:)")


def _norm_renglon(s: str) -> str:
    """Compara renglones sin que un espacio de mas los haga distintos."""
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def _bloque_entero_o_repuesto(texto: str, bloque: str, trace_id: str,
                              barrer_cuenta: bool = True) -> str:
    """LA CUENTA VIAJA ENTERA O NO VIAJA.

    El bug que esto cierra: la guarda vieja daba por pegado el bloque con solo
    encontrar su PRIMERA linea, y esa linea es el literal "Presupuesto:". Al
    modelo le alcanzaba con escribir esa palabra para que el codigo no repusiera
    nada. Medido el 3-ago en 56_ronda_dificil: el modelo anuncio "incluyendo el
    microfono", listo un solo renglon, el candado de plata le podo el resto por
    no estar respaldado, y el cliente recibio un presupuesto SIN el microfono y
    SIN Total. El turno se logueo hub_venta_ok.

    Ahora se exige el bloque COMPLETO, renglon por renglon. Si falta uno solo,
    se barren los renglones de cuenta que escribio el modelo -para no dejar la
    version mutilada al lado de la buena- y se pega el bloque del codigo.

    `barrer_cuenta` EXISTE PORQUE ESTA FUNCION ATIENDE DOS BLOQUES DISTINTOS.
    Barrer los renglones de cuenta tiene sentido cuando el bloque que se repone
    ES la cuenta: se saca la version mutilada del modelo y se pega la buena.
    Cuando el bloque es el HALLAZGO -la lista de lo que mas se acerca-, barrer
    la cuenta no tiene nada que ver, y hacia daño: medido sobre el guion 76 T2,
    `_cuenta_no_retipeada` habia repuesto -bien- el presupuesto del turno
    anterior, y este barrido se lo comia entero porque el hallazgo no estaba
    pegado. Al cliente le llegaba la charla sin un solo numero."""
    if not bloque:
        return texto
    esperados = [ln for ln in bloque.splitlines() if ln.strip()]
    presentes = {_norm_renglon(ln) for ln in (texto or "").splitlines()}
    if all(_norm_renglon(ln) in presentes for ln in esperados):
        return texto
    limpio = (_RE_RENGLON_CUENTA_ENTERO.sub("", texto or "") if barrer_cuenta
              else (texto or ""))
    limpio = re.sub(r"\n{3,}", "\n\n", limpio).strip()
    log.warning("hub_venta_bloque_repuesto", trace_id=trace_id,
                faltaban=[ln[:40] for ln in esperados
                          if _norm_renglon(ln) not in presentes][:3])
    return (limpio + "\n\n" + bloque).strip()


def _sin_narracion_interna(texto: str, trace_id: str) -> str:
    """El cliente no ve la cocina. La regla esta en el prompt y el modelo igual
    la rompe: "encontre varias opciones y el sistema me indica que hay modelos
    distintos". Medido en el banco repetido."""
    limpio = _RE_NARRACION.sub("", texto or "")
    if limpio != (texto or ""):
        log.warning("hub_venta_narracion_interna", trace_id=trace_id)
    return re.sub(r"\n{3,}", "\n\n", limpio).strip()


_RE_ANUNCIO = re.compile(
    r"(?im)^[^\n]*\b(?:te\s+(?:paso|pas[eé]|dejo|armo|comparto)|aqu[ií]\s+"
    r"(?:ten[eé]s|va)|ac[aá]\s+(?:ten[eé]s|va))\b[^\n]*"
    r"(?:presupuesto|cotizaci[oó]n|detalle|total)[^\n]*:\s*$")


def _sin_anuncio_vacio(texto: str, trace_id: str) -> str:
    """Un anuncio de presupuesto sin presupuesto abajo se va con lo que
    anunciaba. Pasa cuando el modelo promete la cuenta sin haberla calculado y
    los renglones inventados se podan: al cliente le llega "Te paso el
    presupuesto por los dos mouse:" y despues nada."""
    lineas = (texto or "").splitlines()
    fuera = []
    for i, l in enumerate(lineas):
        if not _RE_ANUNCIO.match(l):
            continue
        if not next((x for x in lineas[i + 1:] if x.strip()), ""):
            fuera.append(i)
            continue
        # lo que sigue tiene que ser la cuenta, no otra frase de prosa
        siguiente = next(x for x in lineas[i + 1:] if x.strip())
        if not _RE_ARRANQUE_CUENTA.match(siguiente):
            fuera.append(i)
    if not fuera:
        return texto
    log.warning("hub_venta_anuncio_vacio", trace_id=trace_id, lineas=len(fuera))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(
        l for i, l in enumerate(lineas) if i not in fuera)).strip()


def _sin_markdown(texto: str) -> str:
    """WhatsApp no renderiza markdown: los asteriscos dobles salen como
    asteriscos. El prompt lo pide y el modelo igual los pone."""
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", texto or "")
    t = re.sub(r"(?m)^\s*#{1,6}\s*", "", t)
    return t


def _cuenta_no_retipeada(texto: str, hubo_calculo: bool, previo: str,
                         trace_id: str) -> str:
    """LA CUENTA NO SE ESCRIBE A MANO. Si el turno no la calculo, el modelo NO
    puede redactarla: se le pone la del codigo, tal cual quedo.

    Charla real del 1-ago por WhatsApp. El cliente pidio rearmar el precio, el
    turno no llamo a `armar_presupuesto`, y el modelo re-tipeo de memoria el
    presupuesto del turno anterior... cambiando el producto: donde iba la
    Kingston Fury Beast NEGRA escribio la BLANCA. Los montos eran los mismos y
    estaban respaldados, asi que la regla de la plata lo dejo pasar con razon:
    no era plata inventada, era una CUENTA inventada alrededor de plata real.

    Es el mismo principio que ya vale para el dinero, un escalon mas arriba: el
    bloque lo arma el codigo, el modelo lo pega. Si no hay bloque de este turno
    ni de un turno anterior, los renglones se van: mejor sin cuenta que con una
    cuenta que el modelo se acuerda mal."""
    if hubo_calculo:
        return texto
    renglones = [l for l in (texto or "").splitlines()
                 if _RE_ARRANQUE_CUENTA.match(l)]
    if not renglones:
        return texto
    previo_lineas = {l.strip() for l in (previo or "").splitlines() if l.strip()}
    if all(l.strip() in previo_lineas for l in renglones):
        return texto
    salida, reemplazado = [], False
    for linea in (texto or "").splitlines():
        if not _RE_ARRANQUE_CUENTA.match(linea):
            salida.append(linea)
            continue
        if linea.strip() in previo_lineas:
            salida.append(linea)
            continue
        if previo and not reemplazado:
            salida.append(previo.strip())
            reemplazado = True
    log.warning("hub_venta_cuenta_retipeada", trace_id=trace_id,
                renglones=len(renglones), repuesta=bool(previo))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip()


def _condicion_faltante_aplicada(llamadas: list, rec: dict, tienda_id: str,
                                 trace_id: str) -> list:
    """La condicion que el cliente puso, el modelo declaro y ninguna busqueda
    aplico: la aplica el CODIGO y se rehace la busqueda.

    EL NUMERO QUE LO JUSTIFICA (5-ago, clave paga, nueve corridas). El
    reconciliador cazaba bien la condicion sin aplicar, y en la ronda dos el
    modelo pedia CERO herramientas 3 de 3, con la correccion primera en el
    prompt y con el orden rechazado a la vista. Tres redacciones distintas de la
    instruccion no movieron el numero: desde el punto de vista del modelo ya lo
    habia resuelto. Seguir escribiendo prosa para convencerlo es la rueda que
    hay que cortar.

    El codigo no interpreta la frase: `resolver_exclusion` busca en QUE CAMPO
    del catalogo aparece esa palabra como valor, que es un hecho. Y solo actua
    sobre EXCLUSIONES -hace falta una negacion en las palabras del cliente-,
    porque aplicar una condicion al reves seria peor que no aplicarla.

    Rehacer la busqueda cuesta CERO tokens: es la misma herramienta, corriendo
    con una condicion mas. Y cuando la exclusion no deja nada, la busqueda
    entrega el bloque de hechos que el modelo pega, o sea que el muro deja de
    escribirlo el modelo de su cabeza.
    """
    faltantes = [f for f in (rec or {}).get("faltantes", [])
                 if "condicion" in f.lower()]
    if not faltantes:
        return llamadas
    idx = next((i for i, l in enumerate(llamadas)
                if l.get("herramienta") == "buscar_productos"), None)
    if idx is None:
        return llamadas
    from app.core import filtros_catalogo as FC
    args = dict(llamadas[idx].get("pedido") or {})
    sumadas = []
    for f in faltantes:
        # el texto de la condicion viene entre comillas en el faltante
        m = re.search(r"'([^']+)'", f)
        cond = FC.resolver_exclusion(m.group(1) if m else f, tienda_id)
        if cond and cond not in (args.get("filtros") or []):
            args["filtros"] = list(args.get("filtros") or []) + [cond]
            sumadas.append(cond)
    if not sumadas:
        return llamadas
    # El orden que el modelo pidio puede haber sido su intento de aplicar esta
    # misma condicion; con la condicion puesta de verdad, ya no hace falta.
    args.pop("ordenar_por", None)
    r = H.ejecutar("buscar_productos", args, tienda_id)
    log.info("condicion_faltante_aplicada", trace_id=trace_id,
             condiciones=sumadas, estado=(r or {}).get("estado"))
    fuera = list(llamadas)
    fuera[idx] = {"herramienta": "buscar_productos", "pedido": args,
                  "resultado": r}
    return fuera


def _cuenta_con_lo_declarado(llamadas: list, declarado: dict, tienda_id: str,
                             trace_id: str) -> list:
    """EL RUBRO QUE EL CLIENTE PIDIO Y LA CUENTA PERDIO, lo repone el CODIGO.

    LA FALLA, medida en produccion el 5-ago con el mensaje real de Martin. Pidio
    "dos auriculares, dos mouse y dos memorias". El modelo declaro los TRES
    rubros, busco los TRES, y despues llamo a `armar_presupuesto` con DOS: las
    memorias se cayeron en el camino. El cliente recibio un total de $181.000
    que le faltaban $69.000 de mercaderia que habia pedido. El reconciliador no
    lo vio porque su regla 5 chequea que la cuenta EXISTA, no que lo declarado
    este ADENTRO de la cuenta.

    POR QUE LO ARREGLA EL CODIGO Y NO OTRA RONDA. Devolverselo al modelo cuesta
    una vuelta entera -entre 3 y 8 segundos- y no garantiza nada: medido el
    5-ago, ante una correccion del reconciliador el modelo pidio CERO
    herramientas 3 de 3 veces. Rehacer la cuenta cuesta CERO tokens y
    milisegundos, y es la misma herramienta con un item mas.

    NO ES EL CODIGO DECIDIENDO POR EL CLIENTE. Se repone solo lo que el modelo
    MISMO declaro que el cliente pidio, y solo con un producto que ESTE MISMO
    TURNO ya certifico y le mostro. El producto elegido es el primero que se le
    mostro, que es el orden que ya calculo el codigo. Y no queda escondido: el
    renglon sale en la cuenta con su nombre y su precio, que es como el cliente
    lo ve.
    """
    if not declarado:
        return llamadas
    idx = next((i for i, l in enumerate(llamadas)
                if l.get("herramienta") == "armar_presupuesto"
                and (l.get("resultado") or {}).get("estado") == "ok"), None)
    if idx is None and not declarado.get("pide_precio"):
        return llamadas

    # Los productos que ESTE turno certifico, por categoria y por nombre, en el
    # orden en que se los mostro al cliente.
    vistos: list = []
    for l in llamadas:
        r = l.get("resultado") or {}
        for p in (r.get("productos") or []) + ([r["producto"]]
                                               if r.get("producto") else []):
            if p.get("id") and p not in vistos:
                vistos.append(p)
    if not vistos:
        return llamadas
    por_id = {p["id"]: p for p in vistos}

    # ── LA CUENTA QUE NO EXISTE, y es la falla que mas puntos cuesta ────────
    #
    # MEDIDO EL 7-AGO EN VIVO, 15 corridas de la pregunta de Martin en cinco
    # redacciones: CUATRO terminaron sin ninguna cuenta. El cliente pidio precio
    # de seis productos y no recibio un solo numero. Son exactamente las
    # corridas de 10 y 12 puntos sobre 100, o sea el PEOR CASO, que es el que
    # decide si esto se puede vender.
    #
    # La reparacion de abajo existia desde el 6-ago pero exigia que YA hubiera
    # una cuenta a la cual reponerle el rubro que falto. Cuando el modelo no
    # llama a `armar_presupuesto` ni una vez, no habia nada que reparar y el
    # turno salia sin numeros.
    #
    # Es el mismo principio que ya se aplico dos veces con resultado: la
    # compuerta determinista que arregla la LLAMADA en vez de pedirle al modelo
    # otra ronda. Aca la compuerta no completa una cuenta: la crea, con los
    # productos que el turno -o la charla- ya certifico, y solo cuando el modelo
    # mismo declaro que el cliente pidio precio. Si no hay ningun producto
    # certificado para lo declarado, no inventa nada y el turno sigue sin cuenta,
    # que es el comportamiento honesto.
    if idx is None:
        nuevos = []
        for it in (declarado.get("items") or []):
            que = H._norm(it.get("que"))
            cand = next((p for p in vistos
                         if P._cubierto(que, H._norm(p.get("categoria")) + " "
                                        + H._norm(p.get("nombre")))), None)
            if not cand:
                continue
            fila = {"product_id": cand["id"],
                    "cantidad": max(1, int(it.get("cantidad") or 1))}
            if it.get("destino"):
                fila["destino"] = it["destino"]
            nuevos.append(fila)
        if not nuevos:
            return llamadas
        args = {"items": nuevos}
        if declarado.get("destinos"):
            args["destinos"] = list(declarado["destinos"])
        r = H.ejecutar("armar_presupuesto", args, tienda_id)
        if (r or {}).get("estado") != "ok":
            log.warning("cuenta_no_se_pudo_crear", trace_id=trace_id)
            return llamadas
        log.info("cuenta_creada_por_codigo", trace_id=trace_id,
                 items=len(nuevos))
        return llamadas + [{"herramienta": "armar_presupuesto", "pedido": args,
                            "resultado": r}]

    args = dict(llamadas[idx].get("pedido") or {})
    items = [dict(i) for i in (args.get("items") or [])]
    ya = " ".join(
        H._norm(por_id.get(str(i.get("product_id")), {}).get("categoria"))
        + " " + H._norm(por_id.get(str(i.get("product_id")), {}).get("nombre"))
        for i in items)
    sumados = []
    for it in (declarado.get("items") or []):
        que = H._norm(it.get("que"))
        if not que:
            continue
        # ── LA CANTIDAD TAMBIEN CUENTA, no solo el rubro ────────────────────
        # Medido en produccion el 6-ago, mismo mensaje: el cliente pidio DOS
        # auriculares y la cuenta salio con "1x Auriculares HyperX: $70.000".
        # La regla de reponer el rubro que falta no lo veia, porque el rubro
        # estaba: lo que faltaba era una unidad. Es plata igual, la mitad de
        # ese renglon.
        #
        # Se suma por RUBRO y no por renglon: el mismo producto puede venir
        # partido en dos renglones con destinos distintos, y eso esta bien.
        if P._cubierto(que, ya):
            pedidas = max(1, int(it.get("cantidad") or 1))
            iguales = [i for i in items
                       if P._cubierto(que, H._norm(
                           por_id.get(str(i.get("product_id")), {})
                           .get("categoria")) + " " + H._norm(
                           por_id.get(str(i.get("product_id")), {})
                           .get("nombre")))]
            tiene = sum(max(1, int(i.get("cantidad") or 1)) for i in iguales)
            if iguales and tiene < pedidas:
                # Se completa sobre el PRIMER renglon de ese rubro, que es el
                # que el modelo eligio: no se elige otro producto ni se abre uno
                # nuevo, solo se lleva la cantidad a la que el cliente pidio.
                iguales[0]["cantidad"] = (max(1, int(iguales[0].get("cantidad")
                                                     or 1)) + pedidas - tiene)
                sumados.append(f"+{pedidas - tiene}x "
                               f"{por_id.get(str(iguales[0]['product_id']), {}).get('nombre')}")
            continue
        # El primero que se le mostro de ese rubro. Si no se le mostro ninguno,
        # no se inventa: eso es un faltante de verdad y lo cuenta el redactor.
        cand = next((p for p in vistos
                     if P._cubierto(que, H._norm(p.get("categoria")) + " "
                                    + H._norm(p.get("nombre")))), None)
        if not cand:
            continue
        # EL DESTINO VIAJA CON EL ITEM. Sin esto el renglon repuesto entra
        # huerfano y el reparto de envios sigue sin cerrar, o sea que se arregla
        # la plata y se rompe el envio. Medido el 6-ago en produccion: la cuenta
        # cobro tres envios y no pudo decir que iba a donde.
        nuevo = {"product_id": cand["id"],
                 "cantidad": max(1, int(it.get("cantidad") or 1))}
        if it.get("destino"):
            nuevo["destino"] = it["destino"]
        items.append(nuevo)
        sumados.append(f"{it.get('cantidad') or 1}x {cand.get('nombre')}")
    if not sumados:
        return llamadas

    args["items"] = items
    r = H.ejecutar("armar_presupuesto", args, tienda_id)
    if (r or {}).get("estado") != "ok":
        log.warning("cuenta_no_se_pudo_completar", trace_id=trace_id,
                    faltaban=sumados)
        return llamadas
    log.info("cuenta_completada_por_codigo", trace_id=trace_id,
             sumados=sumados)
    fuera = list(llamadas)
    fuera[idx] = {"herramienta": "armar_presupuesto", "pedido": args,
                  "resultado": r}
    return fuera


def _reparto_de_pago_declarado(llamadas: list, declarado: dict, tienda_id: str,
                               trace_id: str) -> list:
    """EL REPARTO QUE EL CLIENTE PIDIO Y LA CUENTA NO LLEVA: lo aplica el CODIGO.

    LA FALLA, medida en produccion el 6-ago sobre el mensaje real de Martin.
    Cerro con "divide el presupuesto en setenta treinta". El modelo lo declaro
    bien como restriccion, el reconciliador lo reclamo TRES rondas seguidas, y
    `armar_presupuesto` salio con `pago=None` las tres veces. Al cliente le
    llego la cuenta sin una palabra del reparto que habia pedido.

    Y no es solo que falte un renglon: la parte que va por transferencia lleva
    10% de descuento. Sobre ese mismo total, el reparto declarado da $232.500 en
    vez de $250.000. **El silencio le costo $17.500 al cliente**, en un turno
    donde el precio era lo unico que el habia dicho que no le importaba.

    POR QUE LO ARREGLA EL CODIGO Y NO OTRA RONDA. Es la misma cuenta que ya se
    hizo para el rubro perdido: devolverselo al modelo cuesta entre 3 y 8
    segundos y no garantiza nada -esta medido, 3 de 3 rondas sin resultado-,
    mientras que rehacer la cuenta cuesta CERO tokens y milisegundos. Ademas el
    reclamo era IMPOSIBLE de resolver por busqueda, que es lo que lo hacia
    eterno; eso se corto en `reconciliar`, regla 3.

    NO ELIGE POR EL CLIENTE. El reparto es del cliente: 70 y 30 los dijo el. Lo
    unico que el codigo asume es CUAL medio lleva cada parte, porque el cliente
    no lo dijo, y lo asume siempre para el mismo lado -la parte grande por
    transferencia, que es la que tiene descuento, o sea la que le conviene al
    cliente- en vez de que el modelo elija distinto cada vez, que es lo que
    hacia. Y no queda escondido: `_supuesto_de_pago`, que corre justo despues,
    escribe el supuesto adentro de la cuenta para que el cliente lo de vuelta en
    una linea si va al reves.
    """
    idx = next((i for i, l in enumerate(llamadas)
                if l.get("herramienta") == "armar_presupuesto"
                and (l.get("resultado") or {}).get("estado") == "ok"), None)
    if idx is None:
        return llamadas
    args = dict(llamadas[idx].get("pedido") or {})
    amb = P.reparto_ambiguo((declarado or {}).get("restricciones"))
    if not amb:
        return llamadas
    _, mayor, menor = amb
    puesto = list(args.get("pago") or [])
    if puesto:
        # ── LA COMPUERTA: EL REPARTO NO SE DEJA DEL LADO QUE LE CUESTA MAS ───
        #
        # Medido en vivo el 7-ago, y es la unica falla de estado que sobrevivio
        # a todo lo demas: el modelo SI mando el reparto, pero puso el 70 en
        # Mercado Pago, que es el medio SIN descuento. Sobre esa cuenta son
        # $9.140 de mas para el cliente. El turno anterior lo habia puesto al
        # reves. O sea: el modelo tira una moneda, en silencio, y la moneda
        # decide lo que el cliente paga.
        #
        # NO SE LE ESTA CORRIGIENDO UNA DECISION AL CLIENTE: el cliente NUNCA
        # dijo que medio lleva cada parte -por eso el reparto es `ambiguo`-. Lo
        # unico que se reemplaza es el volado del modelo por una eleccion
        # deterministica y siempre para el mismo lado, el que le conviene al
        # cliente. Y se declara: `_supuesto_de_pago` corre despues y lo escribe
        # en la cuenta para que lo de vuelta en una linea.
        #
        # Es el patron de "Reason Less, Verify More": una compuerta determinista
        # que mira la llamada propuesta ANTES de ejecutarla y la corrige con una
        # razon, en vez de escribirle otra instruccion al prompt.
        grande = max(puesto, key=lambda x: float(x.get("porcentaje") or 0))
        if "transferencia" in H._norm(grande.get("medio")):
            return llamadas                      # ya esta del lado que conviene
        log.warning("reparto_de_pago_al_reves", trace_id=trace_id,
                    tenia=[(p.get("medio"), p.get("porcentaje"))
                           for p in puesto])
    args["pago"] = [{"medio": "transferencia", "porcentaje": mayor},
                    {"medio": "mercado pago", "porcentaje": menor}]
    r = H.ejecutar("armar_presupuesto", args, tienda_id)
    if (r or {}).get("estado") != "ok":
        log.warning("reparto_de_pago_no_se_pudo", trace_id=trace_id,
                    pedido=amb[0])
        return llamadas
    log.info("reparto_de_pago_por_codigo", trace_id=trace_id, pedido=amb[0],
             aplicado=f"transferencia {mayor}%, mercado pago {menor}%")
    fuera = list(llamadas)
    fuera[idx] = {"herramienta": "armar_presupuesto", "pedido": args,
                  "resultado": r}
    return fuera


def _supuesto_de_pago(llamadas: list, declarado: dict, tienda_id: str,
                      trace_id: str) -> list:
    """EL REPARTO DE PAGO QUE EL CLIENTE NO ASIGNO A NINGUN MEDIO.

    LA FALLA, medida en produccion sobre el mismo mensaje dos dias seguidos.
    "Divide el presupuesto en setenta treinta" no dice QUE medio lleva el 70 ni
    cual el 30. El modelo eligio, en silencio, y eligio DISTINTO cada vez: el
    5-ago puso Mercado Pago 70 y transferencia 30; el 6-ago al reves. Como la
    transferencia tiene 10% de descuento, ese silencio le cambia al cliente lo
    que paga.

    ES LA REGLA CERO APLICADA AL PAGO: ante lo ambiguo el sistema no elige por
    el cliente. Pero tampoco frena la venta preguntando y dejandolo sin numero:
    aplica el reparto, y DECLARA el supuesto en la cuenta, que es la parte que
    el modelo no puede reescribir. El cliente ve lo que se asumio y lo corrige
    en una linea.

    El hecho lo mira sobre lo DECLARADO, no sobre el mensaje crudo: si una
    restriccion trae dos porcentajes y no nombra ningun medio de pago, el que
    despues aparece en la cuenta lo puso el modelo, no el cliente.
    """
    idx = next((i for i, l in enumerate(llamadas)
                if l.get("herramienta") == "armar_presupuesto"
                and (l.get("resultado") or {}).get("bloque")), None)
    if idx is None:
        return llamadas
    partes = ((llamadas[idx].get("pedido") or {}).get("pago") or [])
    if len(partes) < 2:
        return llamadas
    amb = P.reparto_ambiguo((declarado or {}).get("restricciones"))
    if not amb:
        return llamadas
    ambigua = amb[0]
    dicho = ", ".join(f"{p.get('medio')} {int(float(p.get('porcentaje') or 0))}%"
                      for p in partes)
    from app.core import huecos
    huecos.anotar(tienda_id, "supuesto", "medio_de_pago", ambigua)
    log.info("supuesto_de_pago_declarado", trace_id=trace_id, pedido=ambigua,
             asumido=dicho)
    fuera = list(llamadas)
    res = dict(llamadas[idx]["resultado"])
    res["bloque"] = (res["bloque"] + "\n\nDijiste " + ambigua +
                     " y no me aclaraste que medio lleva cada parte: lo arme "
                     "con " + dicho + ". Si va al reves, decimelo y lo doy "
                     "vuelta.")
    fuera[idx] = {**llamadas[idx], "resultado": res}
    return fuera


def _bloque_presupuesto(llamadas: list) -> str:
    for l in llamadas:
        r = l.get("resultado") or {}
        if l.get("herramienta") == "armar_presupuesto" and r.get("bloque"):
            return str(r["bloque"])
    return ""


def _bloques_a_uno(llamadas: list, trace_id: str) -> list:
    """TRES RUBROS, UN SOLO BLOQUE. El recorte mas grande del mensaje, y no lo
    hace el modelo: lo hace el codigo, que es quien lo escribe.

    LA MEDICION, sobre el turno real del 6-ago: la respuesta salio en 2.977
    caracteres y 3 mensajes de WhatsApp. De esos, 1.476 -la MITAD- eran tres
    bloques calcados, uno por rubro, cada uno con su cabecera, su linea de
    empate y la MISMA cola "donde si se cumple del todo: almacenamiento externo,
    procesador", repetida textual tres veces.

    No es culpa del modelo: cada busqueda devuelve su bloque y la instruccion le
    dice que lo pegue tal cual, asi que pego tres. La solucion no es pedirle que
    resuma -eso es rogarle a la prosa- sino entregarle UNO.

    Se arma de los DATOS, no pegando textos: rubro, dos productos con su precio
    y el dato que falla, el empate en una linea y la cola una sola vez.
    """
    candidatos = [i for i, l in enumerate(llamadas)
                  if l.get("herramienta") == "buscar_productos"
                  and (l.get("resultado") or {}).get("bloque")
                  and (l.get("resultado") or {}).get("productos")]
    # UN RUBRO, UNA VEZ. Cuando el turno da varias vueltas, el modelo vuelve a
    # buscar la misma categoria y se acumulan los resultados: medido en el
    # guion 76, ocho busquedas para tres rubros. Se queda la ULTIMA de cada
    # rubro, que es la mas afinada, y se descartan las anteriores.
    por_rubro: dict = {}
    for i in candidatos:
        r = llamadas[i]["resultado"]
        cat = H._norm(r.get("categoria")
                      or (r.get("productos") or [{}])[0].get("categoria"))
        por_rubro[cat] = i
    idx = sorted(por_rubro.values())
    if len(idx) < 2:
        return llamadas

    lineas, hubo_empate = [], False
    for i in idx:
        r = llamadas[i]["resultado"]
        cat = r.get("categoria") or (r["productos"][0].get("categoria") or "")
        fichas = (r.get("productos") or [])[:2]
        # ── EL DATO QUE FALLA VA EN LA CABECERA CUANDO ES EL MISMO ──────────
        # Medido sobre el turno del 6-ago: los seis renglones terminaban en
        # "— país de fabricación: china", el mismo texto seis veces. Es un
        # hecho del RUBRO, no de cada producto, y repetirlo por renglon no
        # agrega un dato: agrega 190 caracteres y hace que la respuesta se lea
        # como una excusa repetida en vez de un hallazgo.
        motivos = {f.get("por_que") for f in fichas if f.get("por_que")}
        comun = motivos.pop() if len(motivos) == 1 else ""
        # EL EMPATE, POR RUBRO Y SIN LA FRASE QUE CONTRADICE AL CLIENTE. Antes
        # se sumaban los tres y salia "hay varios igual de cerca -160 en total-:
        # ninguno está mejor que otro, te muestro los más baratos". Ese 160 no
        # significa nada -son tres universos distintos sumados- y "te muestro
        # los más baratos" le contesta con el precio a un cliente que acababa de
        # decir que el precio no era lo importante. El numero por rubro SI es un
        # hecho: dice cuanto surtido hay atras.
        n = int(r.get("empatados_igual_de_cerca") or 0)
        cabeza = str(cat).capitalize()
        detalle = []
        if n > len(fichas):
            detalle.append(f"{n} igual de cerca")
            hubo_empate = True
        if comun:
            detalle.append(comun)
        lineas.append(cabeza + (f" ({', '.join(detalle)})" if detalle else "")
                      + ":")
        for f in fichas:
            renglon = f"- {f.get('nombre')}"
            if f.get("precio"):
                renglon += f": {f['precio']}"
            if f.get("por_que") and not comun:
                renglon += f" — {f['por_que']}"
            lineas.append(renglon)

    partes = ["Lo que más se acerca a lo que pediste:", "\n".join(lineas)]
    if hubo_empate:
        partes.append("Dentro de cada rubro la ficha no los distingue entre "
                      "sí, así que te muestro dos de cada uno y te paso el "
                      "resto si querés comparar.")
    # `donde_si_se_cumple` NO ENTRA EN UN PEDIDO DE VARIOS RUBROS. Sirve para
    # "tenés algo sin China?", que es una pregunta sobre el catalogo. Acá el
    # cliente pidió auriculares, mouse y memorias: contestarle "donde sí se
    # cumple es en almacenamiento externo y procesador" no le resuelve nada,
    # le cambia el pedido, y ocupa un renglón en un mensaje que ya sobra.
    unico = "\n\n".join(partes)

    fuera = list(llamadas)
    for n, i in enumerate(candidatos):
        r = dict(llamadas[i]["resultado"])
        if i == idx[0]:
            r["bloque"] = unico
            r["instruccion"] = (
                "Pegá el bloque TAL CUAL, sin cambiar un renglón: ya trae los "
                "rubros juntos. Escribí vos lo de antes y lo de después, corto. "
                "NO repitas los productos afuera del bloque y PROHIBIDO afirmar "
                "nada sobre el catálogo entero.")
        else:
            # El resto se queda SIN bloque: si no, el modelo pega los tres.
            r.pop("bloque", None)
            r["instruccion"] = ("Estos productos ya están en el bloque del "
                                "primer resultado. NO los vuelvas a listar.")
        fuera[i] = {**llamadas[i], "resultado": r}
    log.info("bloques_fusionados", trace_id=trace_id, rubros=len(idx),
             largo=len(unico))
    return fuera


def _bloque_hallazgo(llamadas: list, texto: str = "") -> str:
    """El bloque de hechos que escribe `buscar_productos` cuando ninguno cumple
    del todo. Mismo trato que la cuenta: se pega entero o se repone.

    UN BLOQUE POR MENSAJE, Y SE MIDE SOBRE LO QUE EL CLIENTE LEE. La primera
    version preguntaba si ESTE TURNO habia calculado un presupuesto, y eso deja
    un agujero que se vio en el guion 76 T2: el turno no cotizo, pero
    `_cuenta_no_retipeada` repuso -bien- la cuenta del turno anterior, asi que
    el mensaje SI llevaba cuenta y encima se le pego el listado. Dos bloques,
    2.910 caracteres, tres mensajes de WhatsApp. La regla es sobre el mensaje,
    no sobre la lista de llamadas.

    Y NO SE REPONE LO QUE YA ESTA DICHO. `_bloque_entero_o_repuesto` exige el
    bloque textual, renglon por renglon, que es lo correcto para la cuenta -ahi
    un numero distinto es plata mal contada-. Para el hallazgo es demasiado
    duro: si el modelo ya nombro los mismos productos con otro formato, los
    HECHOS le llegaron al cliente, y pegar la version del codigo abajo es
    escribir dos veces lo mismo. Es la falla `bloque repetido en 2 turnos` que
    el piso ya venia contando en este mismo guion.
    """
    if _bloque_presupuesto(llamadas):
        return ""
    # Los marcadores DUROS de una cuenta, no `_RE_ARRANQUE_CUENTA`: aquella
    # matchea tambien "Envio:" a secas, que el modelo escribe en cualquier
    # respuesta de politica, y con eso el hallazgo se habria callado de mas.
    if texto and _RE_HAY_CUENTA.search(texto):
        return ""
    bloque = ""
    for l in llamadas:
        r = l.get("resultado") or {}
        if l.get("herramienta") == "buscar_productos" and r.get("bloque"):
            bloque = str(r["bloque"])
            break
    if not bloque or not texto:
        return bloque
    # Los nombres de producto del bloque, que son el hecho. Si estan todos en
    # el texto, el cliente ya los tiene.
    nombres = [ln.lstrip("- ").split(":")[0].strip()
               for ln in bloque.splitlines() if ln.strip().startswith("-")]
    plano = _norm_renglon(texto)
    if nombres and all(_norm_renglon(n) in plano for n in nombres):
        return ""
    return bloque


def _productos_del_turno(llamadas: list, turno: int = 0) -> list:
    """Los productos que el turno mostro, para la memoria. Salen de lo que
    devolvieron las herramientas, no de buscar nombres en el texto.

    CADA UNO CON SU TURNO, SU POSICION Y SU CATEGORIA. Sin eso "el primero que
    me mostraste", "el segundo teclado" y "la ultima opcion" no tienen contra
    que resolverse: se guardaba id, nombre y precio en una lista plana, y el
    orden en que se mostraron -que es toda la informacion que el ordinal usa- se
    perdia en cuanto un turno mostraba dos categorias. Medido el 5-ago: seis
    productos vistos, cero forma de saber cual era el segundo teclado.
    """
    out, vistos = [], set()

    def _add(p, pos):
        pid = str((p or {}).get("id") or "").upper()
        if pid and pid not in vistos and p.get("nombre"):
            vistos.add(pid)
            precio = p.get("precio_ars")
            out.append({"id": pid, "nombre": p["nombre"],
                        "precio": int(precio) if isinstance(precio, (int, float))
                        else 0,
                        "turno": turno, "posicion": pos,
                        "categoria": str(p.get("categoria") or "")})

    for l in llamadas:
        r = l.get("resultado") or {}
        # La posicion se cuenta POR CATEGORIA y por lista: "el segundo teclado"
        # es el segundo de los teclados, no el segundo de todo lo que se mostro.
        por_cat: dict = {}
        for clave in ("productos", "lo_mas_cercano", "hay_en_la_categoria"):
            for p in (r.get(clave) or []):
                cat = str((p or {}).get("categoria") or "")
                por_cat[cat] = por_cat.get(cat, 0) + 1
                _add(p, por_cat[cat])
        if isinstance(r.get("producto"), dict):
            _add(r["producto"], 1)
    return out


def _carrito_del_turno(llamadas: list) -> list:
    for l in llamadas:
        if l.get("herramienta") != "armar_presupuesto":
            continue
        detalle = (l.get("resultado") or {}).get("detalle") or []
        # EL DESTINO POR ITEM SE CALCULABA Y NO SE GUARDABA. `armar_presupuesto`
        # lo recibe, lo cotiza y lo escribe bien en el bloque -medido 3 de 3
        # destinos correctos-, pero el carrito que se persiste guardaba solo id,
        # nombre y cantidad. Al turno siguiente el reparto no existia y el
        # cliente tenia que volver a decir a donde iba cada cosa. Se recupera
        # del pedido que hizo el modelo, que es donde viaja.
        por_id: dict = {}
        for it in ((l.get("pedido") or {}).get("items") or []):
            if isinstance(it, dict) and it.get("destino"):
                por_id.setdefault(str(it.get("product_id") or "").upper(),
                                  str(it["destino"]).strip())
        carrito = []
        for d in detalle:
            if not d.get("id"):
                continue
            item = {"id": str(d.get("id") or "").upper(),
                    "nombre": d.get("nombre"),
                    "cantidad": int(d.get("cantidad") or 1)}
            destino = por_id.get(item["id"])
            if destino:
                item["destino"] = destino
            carrito.append(item)
        if carrito:
            return carrito
    return []


def _carrito_podado(previo: list, declarado: dict) -> list:
    """EL PEDIDO QUE BAJA, sin tener que recotizar.

    EL AGUJERO, medido el 5-ago. El carrito se escribia UNICAMENTE como efecto
    de `armar_presupuesto`: `_carrito_del_turno` lee su detalle y si el turno no
    cotizo devuelve vacio, con lo cual el hub conservaba el carrito anterior
    INTACTO. O sea que "el teclado sacalo, dejame los dos mouse" -sin pedir la
    cuenta- dejaba el teclado adentro, y reaparecia en el presupuesto siguiente.
    No habia operacion de quitar en ningun lado.

    ESTO NO ES UN DELTA y la distincion importa, porque el delta ya se probo y
    no funciono. El modelo no declara "sacá el teclado": declara, como declara
    siempre y en cada turno, el pedido COMPLETO tal como lo entendio. Eso ya
    existe y ya viaja -es `registrar_pedido`, que el prompt obliga a llamar
    ante cualquier pedido de productos, precio o envio-. Lo unico que se agrega
    es LEERLO: lo que estaba en el carrito y ya no aparece en la declaracion,
    sale.

    Se poda por PALABRA, no por id, porque la declaracion es la del cliente
    -"los dos mouse"- y no trae ids. Un item sobrevive si alguna palabra de lo
    declarado aparece en su nombre o en su categoria. Conservador a proposito:
    ante la duda el item se queda, porque borrar del carrito algo que el cliente
    si queria es peor que dejar de mas, y lo de mas se corrige solo en cuanto
    vuelva a cotizar.
    """
    items = [i for i in ((declarado or {}).get("items") or [])
             if isinstance(i, dict) and str(i.get("que") or "").strip()]
    if not previo or not items:
        return previo or [], []

    def _palabras(txt):
        return {w[:5] for w in P._norm(txt).split() if len(w) >= 4}

    quedan, fuera = [], []
    for c in previo:
        texto = P._norm(f"{c.get('nombre', '')} {c.get('categoria', '')}")
        # el item declarado que habla de ESTE producto del carrito
        decl = next((i for i in items
                     if any(w in texto for w in _palabras(i["que"]))), None)
        if decl is None:
            fuera.append(c)
            continue
        nuevo = dict(c)
        # LA CANTIDAD TAMBIEN SE LEE. Medido: "uno de los auriculares era solo
        # una consulta" bajaba de 2 a 1 en la declaracion y el carrito seguia
        # con 2, porque la poda sacaba items enteros y nunca ajustaba unidades.
        # La mitad de las correcciones del cliente son de cantidad, no de alta
        # o baja.
        cant = int(decl.get("cantidad") or 1)
        if cant > 0 and cant != nuevo.get("cantidad"):
            nuevo["cantidad"] = cant
        quedan.append(nuevo)
        if decl.get("destino") and not nuevo.get("destino"):
            nuevo["destino"] = str(decl["destino"]).strip()

    # SI NO QUEDA NADA, EL PEDIDO SE REEMPLAZO. Antes esto se trataba como un
    # no-match y se conservaba el carrito entero "por las dudas", y medido en la
    # Serie 1 eso hacia fallar el caso central: "dejá el teclado y sacá el
    # mouse" declaraba teclado, no matcheaba con el mouse guardado y el mouse
    # se quedaba adentro. La declaracion es el pedido COMPLETO del cliente: si
    # no nombra nada de lo que habia, lo que habia ya no esta.
    if len(quedan) != len(previo):
        log.info("carrito_podado_por_declaracion", antes=len(previo),
                 despues=len(quedan), saco=[c.get("nombre") for c in fuera][:4])
    return quedan, fuera


def _declarados(declarado: dict) -> list:
    """Lo que el cliente declaro querer este turno, en sus palabras."""
    return [str(i.get("que")).strip()
            for i in ((declarado or {}).get("items") or [])
            if isinstance(i, dict) and str(i.get("que") or "").strip()]


def _descartados_nuevos(previos: list, dados_de_baja: list, carrito: list,
                        declarado_antes: list | None = None,
                        declarado_ahora: list | None = None) -> list:
    """LA MEMORIA NEGATIVA. Lo que el cliente SACO del pedido, anotado.

    EL AGUJERO, medido el 5-ago sobre las series de doce turnos. El estado tiene
    doce campos y los doce guardan lo que el cliente QUIERE: el carrito, los
    vistos, el presupuesto, los destinos, el producto anotado, las preferencias.
    NINGUNO guarda lo que dijo que NO. Asi que "los auriculares los nombre como
    posibilidad, no los sumes" vivia unicamente en la prosa del historial, y la
    prosa se trunca a diez mensajes y despues se resume a mil quinientos
    caracteres. Lo primero que pierde un resumen son las negaciones.

    Un chat de IA no necesita esto porque relee el hilo entero. Verifika
    comprime, asi que lo necesita.

    Se guarda el NOMBRE, no el id: el cliente descarta "los auriculares", no un
    id. Y si el producto vuelve a entrar al carrito, sale de la lista: el
    cliente cambio de idea otra vez y eso tambien hay que respetarlo.
    """
    nombres_en_carrito = [P._norm(c.get("nombre") or "") for c in (carrito or [])]

    def _sigue_en_el_pedido(txt: str) -> bool:
        raices = {w[:5] for w in P._norm(txt).split() if len(w) >= 4}
        return any(any(r in n for r in raices) for n in nombres_en_carrito)

    fuera = [d for d in (previos or []) if not _sigue_en_el_pedido(str(d))]

    for c in (dados_de_baja or []):
        n = str(c.get("nombre") or "").strip()
        if n and n not in fuera and not _sigue_en_el_pedido(n):
            fuera.append(n)

    # LO QUE SE NOMBRO Y NUNCA LLEGO AL CARRITO. El caso central de la Serie 15
    # y de la pregunta 9: "los auriculares solo los nombre como posibilidad, no
    # los sumes". Ese producto nunca estuvo en el pedido -el turno solo busco-,
    # asi que comparar contra el carrito no lo ve. Se ve comparando DOS
    # declaraciones: el turno 1 declaro mouse, teclado y auriculares; el turno 3
    # declaro mouse y teclado. Lo que se cayo de la declaracion es lo que el
    # cliente saco.
    #
    # NO ES UN DELTA: son dos fotos completas del pedido, que es lo que el
    # modelo ya emite en cada turno, y la resta la hace el codigo. Solo se
    # compara cuando el turno declaro algo; un turno sin declaracion -"cuanto
    # tarda el envio?"- no puede dar de baja nada.
    if declarado_ahora:
        ahora = [P._norm(x) for x in declarado_ahora]
        for antes in (declarado_antes or []):
            raices = {w[:5] for w in P._norm(antes).split() if len(w) >= 4}
            if not raices:
                continue
            sigue = any(any(r in a for r in raices) for a in ahora)
            if not sigue and not _sigue_en_el_pedido(antes) \
                    and antes not in fuera:
                fuera.append(antes)
    return fuera[-10:]


def _senal_de_cierre(llamadas: list, mensaje: str) -> dict:
    """La interpretacion MINIMA que necesita el cierre. Antes eran veinte campos
    de un interprete; lo unico que `leads` mira es la intencion y la confianza.
    Ahora la decision de compra la declara el modelo llamando `tomar_pedido`, que
    queda en la traza y se puede auditar."""
    for l in llamadas:
        if l.get("herramienta") == "tomar_pedido":
            return {"intencion": "decision_compra", "confianza": 1.0,
                    "motivo": (l.get("pedido") or {}).get("motivo")}
    if any(l.get("herramienta") == "armar_presupuesto" for l in llamadas):
        return {"intencion": "pregunta_especifica", "confianza": 0.9}
    return {"intencion": "exploracion", "confianza": 0.6}


async def _cerrar(conv, user_id, canal, tienda_id, mensaje, texto, trace_id,
                  senal, presupuesto):
    """CIERRE Y COBRO. Reusa la misma funcion del camino anterior."""
    from app.core.leads import procesar_mensaje_para_lead, _RE_PIDE_COBRO
    from app.core.cierre import extraer_determinista, extraer_datos_cliente
    datos_previos = conv.get("datos_cliente_parciales") or {}
    datos_turno = {}
    try:
        datos_turno.update(extraer_determinista(mensaje))
        if senal.get("intencion") == "decision_compra":
            for k, v in extraer_datos_cliente(mensaje, trace_id).items():
                if v:
                    datos_turno[k] = v
    except Exception as e:
        log.warning("hub_venta_extractor_error", trace_id=trace_id,
                    error=str(e)[:120])
    datos_acumulados = {**datos_previos, **datos_turno}
    pide_cobro = bool(_RE_PIDE_COBRO.search(mensaje or ""))
    meta_lead = {}
    if (texto and texto != settings.VERIFIKA_FALLBACK_MESSAGE) or pide_cobro:
        try:
            _, meta_lead = await procesar_mensaje_para_lead(
                user_id, canal, tienda_id, mensaje, texto, trace_id,
                interpretacion=senal,
                presupuesto=presupuesto or (conv.get("ultimo_presupuesto") or ""),
                datos_turno=datos_turno, datos_previos=datos_acumulados,
                presupuesto_nuevo=bool(presupuesto),
                pregunta_cierre_hecha=bool(conv.get("pregunta_cierre_hecha")))
            rd = meta_lead.get("respuesta_directa")
            # EL COBRO NO SE ENTREGA DOS VECES. Ahora que `tomar_pedido` le da
            # al modelo los datos REALES, el modelo los escribe bien, y el
            # cierre los volvia a pegar abajo: al cliente le llegaba el CBU
            # duplicado. Se compara por el DATO, no por el texto.
            if rd and meta_lead.get("accion") == "cobro_datos":
                try:
                    from app.core.pago import datos_transferencia
                    _d = datos_transferencia(tienda_id) or {}
                    _clave = str(_d.get("cbu") or _d.get("alias") or "")
                    if _clave and _clave in (texto or ""):
                        log.info("hub_venta_cobro_ya_entregado", trace_id=trace_id)
                        rd = None
                except Exception as e:
                    log.warning("hub_venta_cobro_dedup_error", trace_id=trace_id,
                                error=str(e)[:120])
            if rd:
                base = (texto or "").strip()
                if not base or base == settings.VERIFIKA_FALLBACK_MESSAGE:
                    texto = rd.strip()
                elif base[:80] and base[:80] in rd:
                    texto = rd.strip()
                else:
                    texto = base + "\n\n" + rd.strip()
                log.info("hub_venta_cierre", trace_id=trace_id,
                         accion=meta_lead.get("accion"))
        except Exception as e:
            log.warning("hub_venta_lead_error", trace_id=trace_id,
                        error=str(e)[:160])
    hecha = meta_lead.get("accion") in ("pregunta_cierre",
                                        "pregunta_pendiente_cierre")
    return texto, datos_acumulados, hecha


async def procesar_venta(user_id: str, raw_message: str, tienda_id: str,
                         canal: str, trace_id: str) -> str:
    """Un turno completo. Devuelve el texto para el cliente."""
    t0 = time.time()
    from app.core.estado_venta import (construir_estado, set_current_estado,
                                       get_envio_localidades, merge_productos)
    from app.core.contexto_turno import set_current_tienda
    from app.core import guardas_salida as gs

    conv = get_conversation(user_id, tienda_id=tienda_id)
    history = conv.get("history", []) or []
    estado = construir_estado(conv, None)
    set_current_tienda(tienda_id)
    set_current_estado(estado)

    negocio = gs.business_name(tienda_id)
    memoria = _memoria_texto(estado, history, tienda_id)

    # ── 1 y 2. QUE BUSCAR, y TODO JUNTO ─────────────────────────────────
    # Dos rondas como mucho. Adentro de cada ronda las herramientas corren en
    # paralelo; la segunda existe solo para lo que se DESBLOQUEA con lo que
    # trajo la primera, que en la practica es armar el presupuesto con los ids
    # ya certificados. Mas rondas no: seria volver a una cadena larga.
    llamadas: list = []
    texto_directo = ""
    revision = ""
    obligacion = ""
    declarado: dict = {}
    # Se inicializa aca: si el turno no pide ninguna herramienta -un saludo, un
    # gracias- el bucle corta antes de reconciliar y `rec` quedaba sin definir.
    rec: dict = {}
    for ronda in range(1, _MAX_RONDAS + 1):
        pedidos, texto_directo = await _pedir_herramientas(
            negocio, memoria, history, raw_message, tienda_id, trace_id,
            llamadas if ronda > 1 else None, revision=revision)
        log.info("hub_venta_pedidos", trace_id=trace_id, ronda=ronda,
                 herramientas=[p["nombre"] for p in pedidos],
                 args=[p.get("args") for p in pedidos][:4])
        if not pedidos:
            break
        llamadas += await _ejecutar_en_paralelo(pedidos, tienda_id, trace_id)
        log.info("hub_venta_resultados", trace_id=trace_id, ronda=ronda,
                 estados=[(l["herramienta"],
                           (l["resultado"] or {}).get("estado"))
                          for l in llamadas])
        _log_fuente(llamadas, trace_id, ronda)

        # ── RECONCILIAR: lo declarado contra lo hecho ───────────────────
        # Acá está el control que faltaba. Los diecinueve que había miraban la
        # prosa ya escrita; este mira la DECISION, antes de escribir. Si algo
        # falta se lo devolvemos al modelo para la vuelta siguiente; si el
        # pedido tiene una contradicción, el turno termina PREGUNTANDO y no
        # eligiendo por el cliente.
        for l in llamadas:
            if l.get("herramienta") == "registrar_pedido":
                declarado = (l.get("resultado") or {}).get("pedido") or declarado
        # LA MEMORIA DEL RECONCILIADOR: lo que la charla ya resolvio. Sin
        # esto le exige buscar de nuevo algo que se certifico dos turnos atras.
        ya = " ".join([str(p.get("nombre") or "") + " " +
                       str(p.get("categoria") or "")
                       for p in (estado.get("productos_vistos") or [])] +
                      [str(c.get("nombre") or "")
                       for c in (conv.get("carrito_vigente") or [])])
        rec = P.reconciliar(declarado, llamadas, trace_id, ya_resuelto=ya)
        obligacion = P.instruccion_de_preguntas(rec)
        revision = P.instruccion_de_faltantes(rec)
        if not revision:
            break
        # NO SE CORTA EL BUCLE POR REPETICION, y esta medido. Se probaron las
        # dos formas sobre las 10 charlas grabadas: cortar cuando el faltante se
        # repite UNA vez baja las llamadas al modelo de 119 a 90 -un 24% de
        # latencia- pero el numero cae de 94 a 89, porque en el guion 76 el
        # modelo estaba yendo a buscar de verdad y le sacabamos la cuenta al
        # cliente; cortar a las DOS repeticiones no ahorra una sola llamada, o
        # sea que es una capa que no hace nada. Se deja el tope de rondas, que
        # ya acota. La ronda al pedo que se midio en produccion el 5-ago se
        # arreglo en la raiz: era un faltante IMPOSIBLE -pedirle que aplicara un
        # reparto de pago como filtro de busqueda-, y eso ya no pasa.
        if ronda == _MAX_RONDAS:
            # Se agotaron las vueltas con el hueco abierto. NO se completa por
            # nuestra cuenta: se le dice al redactor que pregunte lo que falta.
            log.warning("hub_venta_faltantes_sin_resolver", trace_id=trace_id,
                        faltantes=rec.get("faltantes", [])[:4])
            obligacion = (obligacion + "\n\n" if obligacion else "") + (
                "No pudiste conseguir todo lo que el cliente pidió. Contá "
                "honesto qué falta y pedile el dato que haga falta. No "
                "completes de memoria lo que no trajo ninguna herramienta.")

    # ── 2-bis. LO QUE EL MODELO NO APLICA, LO APLICA EL CODIGO ───────────
    llamadas = _condicion_faltante_aplicada(llamadas, rec, tienda_id, trace_id)
    llamadas = _cuenta_con_lo_declarado(llamadas, declarado, tienda_id, trace_id)
    # EL ORDEN IMPORTA: primero se aplica el reparto que falta, y despues se
    # declara el supuesto sobre la cuenta que ya lo tiene adentro.
    llamadas = _reparto_de_pago_declarado(llamadas, declarado, tienda_id,
                                          trace_id)
    llamadas = _supuesto_de_pago(llamadas, declarado, tienda_id, trace_id)
    llamadas = _bloques_a_uno(llamadas, trace_id)

    # ── 3. REDACTAR CON EL DATO DELANTE ─────────────────────────────────
    if llamadas:
        texto = await _redactar(negocio, memoria, history, raw_message,
                                llamadas, trace_id, obligacion=obligacion)
    else:
        # Sin herramientas el modelo ya contesto en la llamada uno: es un
        # saludo, un gracias o una respuesta a algo que preguntamos nosotros.
        texto = texto_directo
    if not (texto or "").strip():
        texto = settings.VERIFIKA_FALLBACK_MESSAGE
        log.warning("hub_venta_sin_texto", trace_id=trace_id)

    # ── 4. LA REGLA ─────────────────────────────────────────────────────
    bloque = _bloque_presupuesto(llamadas)
    texto = _sin_json_filtrado(texto, trace_id)
    texto = _sin_markdown(texto)
    texto = _sin_plata_inventada(texto, llamadas, bloque, trace_id,
                                 previo=conv.get("ultimo_presupuesto") or "",
                                 vistos=estado.get("productos_vistos") or [])
    texto = _sin_cobro_inventado(texto, tienda_id, trace_id)
    texto = _cuenta_no_retipeada(
        texto, hubo_calculo=bool(bloque),
        previo=conv.get("ultimo_presupuesto") or "", trace_id=trace_id)
    texto = _sin_negar_lo_traido(texto, llamadas, trace_id)
    texto = _sin_afirmar_sobre_el_catalogo(texto, llamadas, trace_id)
    texto = _sin_descuento_inventado(texto, trace_id)
    texto = _sin_narracion_interna(texto, trace_id)
    texto = _sin_anuncio_vacio(texto, trace_id)
    # La cuenta se manda entera: si el modelo la reescribio o se la comio, el
    # bloque del codigo vuelve al final. No se negocia, es la unica parte del
    # mensaje que el modelo no redacta.
    texto = _bloque_entero_o_repuesto(texto, bloque, trace_id)
    # EL HALLAZGO, mismo trato que la cuenta. Va DESPUES de la poda de plata a
    # proposito: sus precios salen de la fuente y no se podan, pero si el
    # modelo escribio otros, esos si se fueron.
    texto = _bloque_entero_o_repuesto(texto, _bloque_hallazgo(llamadas, texto),
                                      trace_id, barrer_cuenta=False)
    texto = _RE_ID_INTERNO.sub("", texto).strip()

    # ── 5. CIERRE Y COBRO ───────────────────────────────────────────────
    senal = _senal_de_cierre(llamadas, raw_message)
    texto, datos_cliente, pregunta_cierre_hecha = await _cerrar(
        conv, user_id, canal, tienda_id, raw_message, texto, trace_id,
        senal, bloque)

    # ── 6. LO QUE NO PUEDE DEPENDER DEL PROMPT ──────────────────────────
    # Dos cosas, y solo dos. La honestidad de bot porque el prompt solo no
    # alcanzo nunca, y el aviso de que es un asistente automatico en el primer
    # mensaje porque es una obligacion, no un criterio de redaccion.
    try:
        texto = gs.asegurar_honestidad_bot(raw_message, texto, negocio)
        if not history:
            texto = gs.con_saludo_inicial(texto, negocio)
        else:
            texto = gs.sin_saludo_del_modelo(texto)
    except Exception as e:
        log.warning("hub_venta_guardas_error", trace_id=trace_id,
                    error=str(e)[:120])

    # ── 7. MEMORIA ──────────────────────────────────────────────────────
    history = history + [{"role": "user", "content": raw_message},
                         {"role": "assistant", "content": texto}]
    resumen = conv.get("summary", "") or ""
    descartados = history[:-(settings.HISTORY_LIMIT * 2)]
    if descartados:
        try:
            from app.core.memoria_larga import actualizar_resumen
            resumen = await actualizar_resumen(resumen, descartados, trace_id)
        except Exception as e:
            log.warning("hub_venta_memoria_error", trace_id=trace_id,
                        error=str(e)[:120])
    history = history[-(settings.HISTORY_LIMIT * 2):]

    productos_vistos = merge_productos(conv.get("productos_vistos") or [],
                                       _productos_del_turno(
                                           llamadas, turno=len(history) // 2))
    # EL CARRITO. Si el turno cotizo, manda la cuenta. Si no cotizo pero el
    # modelo DECLARO el pedido, se poda el anterior con esa declaracion: es la
    # unica forma de que "sacá el teclado" baje algo sin obligar a recotizar.
    carrito = _carrito_del_turno(llamadas)
    dados_de_baja = []
    if not carrito:
        carrito, dados_de_baja = _carrito_podado(
            conv.get("carrito_vigente") or [], declarado)
    declarado_ahora = _declarados(declarado)
    descartados = _descartados_nuevos(
        conv.get("descartados") or [], dados_de_baja, carrito,
        declarado_antes=conv.get("ultimo_declarado") or [],
        declarado_ahora=declarado_ahora)
    localidades = get_envio_localidades() or (conv.get("ultimas_localidades") or [])
    try:
        save_conversation(
            user_id, history, resumen, tienda_id=tienda_id,
            estado_conversacion="en_curso",
            productos_vistos=productos_vistos, carrito_vigente=carrito,
            descartados=descartados,
            ultimo_declarado=(declarado_ahora or
                              conv.get("ultimo_declarado") or []),
            ultima_localidad=(localidades[-1] if localidades else
                              (conv.get("ultima_localidad") or "")),
            ultimas_localidades=localidades,
            datos_cliente_parciales=datos_cliente,
            pregunta_cierre_hecha=pregunta_cierre_hecha,
            ultimo_presupuesto=(bloque or conv.get("ultimo_presupuesto") or None))
    except Exception as e:
        log.warning("hub_venta_save_error", trace_id=trace_id, error=str(e)[:150])

    log.info("hub_venta_ok", trace_id=trace_id,
             latency_ms=int((time.time() - t0) * 1000),
             herramientas=len(llamadas), con_presupuesto=bool(bloque))
    return texto
