"""
HUB DE VENTA — el turno completo, en dos llamadas.

Reemplaza al hub atado. El camino viejo era: interprete que traducia el mensaje
a una taxonomia de veinte campos, solver que emitia fragmentos atados a enums,
render que estampaba, y despues once modulos que CORREGIAN al modelo -el juez,
la red de verificadores, las guardas de salida-. Tres capas peleando por la
misma verdad, y la que ganaba borraba a las otras.

Aca el control esta ANTES de que el modelo escriba:

  1. LLAMADA UNO. El modelo ve la charla y las siete herramientas, y decide QUE
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
SISTEMA = """Sos el vendedor de {negocio}, una tienda argentina de tecnologia e
informatica. Escribis en español argentino, de vos, para WhatsApp: parrafos
cortos, sin markdown, sin titulos, sin asteriscos.

Los datos duros -precio, stock, specs, politicas, totales- te los traen las
herramientas, ya escritos. Copialos tal cual. Lo que no te trajeron, no lo
sabes, y no se completa de memoria. Eso incluye los SERVICIOS: no ofrezcas
retiro en el local, dia de entrega, ni que alguien lo va a llamar despues. Si
una herramienta no lo trajo, esta tienda no lo hace.

Todo lo demas es tu trabajo, y tu trabajo es PENSAR como piensa un buen vendedor
de mostrador:

Entende que necesita de verdad, no solo lo que escribio. Si te dice que el
precio no es lo importante no te esta pidiendo lo mas caro; te esta diciendo que
mires otra cosa. Si pone una condicion, esa condicion manda sobre el resto.

Fijate si el pedido CIERRA antes de contestar. Si las cuentas no dan, si nombra
algo que no habia pedido, si falta un dato para poder cotizar: preguntalo.
Elegir por el cliente es la peor forma de equivocarse, peor que no saber.

Cuando no tengas exactamente lo que pide, no cierres con un no. Deci la verdad
de lo que no se cumple Y mostrale lo mas parecido que si tenes, con su precio,
explicando en una linea por que se lo ofreces. Un no seco con el dato en la mano
es una venta perdida, no honestidad.

Contesta TODO lo que te preguntaron, no una parte. Y cerra moviendo la venta:
una pregunta util o el paso que sigue."""

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

Si el cliente pide una recomendacion, una comparacion o para que sirve algo,
sumale consultar_criterio: sin eso vas a opinar de tu cabeza y no con el
criterio de la casa."""

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


def _modelo_decisor() -> str:
    """El modelo de la llamada UNO. Por default el mismo que redacta; se le
    puede poner uno mas grande SOLO acá, que es donde se decide."""
    return settings.DECISOR_MODEL or _modelo()


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
            vistos.append(f"{p['nombre']} [{pid}]" if pid else str(p["nombre"]))
    if vistos:
        partes.append("Productos que ya le mostraste, con su id entre corchetes "
                      "para que puedas usarlos en las herramientas (el id NUNCA "
                      "se escribe en el mensaje): " + ", ".join(dict.fromkeys(vistos)))
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


def _mensajes(negocio: str, memoria: str, history: list, mensaje: str,
              instruccion: str, datos: str = "") -> list:
    msgs = [{"role": "system", "content": SISTEMA.format(negocio=negocio)}]
    if memoria:
        msgs.append({"role": "system", "content": memoria})
    for h in (history or [])[-10:]:
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
    cli = _cliente()
    if cli is None:
        return [], ""
    esquemas = H.esquemas(tienda_id)
    if llamadas:
        # AHORRO MEDIDO: en las vueltas de encadenado el modelo ya declaró el
        # pedido y ya buscó. Mandarle otra vez los ocho esquemas cuesta ~1200
        # tokens por turno al pedo, y los 93 enums de consultar_criterio son el
        # 28% de eso. Van solo las que puede encadenar de verdad.
        encadenables = {"buscar_productos", "ficha_producto", "cotizar_envio",
                        "armar_presupuesto", "ver_compatibilidad",
                        "tomar_pedido", "consultar_politica"}
        esquemas = [e for e in esquemas
                    if e.get("function", e).get("name") in encadenables]
        instr = _INSTRUCCION_RONDA_DOS + (("\n\n" + revision) if revision else "")
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
            tool_choice="auto", temperature=0.3, max_tokens=3000,
            extra_body={"reasoning_effort": settings.DECISOR_REASONING})
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
            extra_body={"reasoning_effort": "none"})
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
    de consultar_politica y no los toca esta regla."""
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
        if not _RE_RENGLON_CUENTA.match(siguiente):
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


# Un renglon de cuenta, lo escriba como lo escriba: con guion o sin el, "2x" o
# "1 x". La primera version pedia el guion y la equis pegada, y se le escapo
# "1 x Teclado Genius KB-110X Blanco: $12.000" escrito a mano por el modelo
# (banco repetido, guion 71).
_RE_RENGLON_CUENTA = re.compile(
    r"(?im)^\s*(?:presupuesto\s*:|subtotal\s*:|env[ií]o?\s*[(:]|"
    r"total\s*:|total final\s*:|pago dividido\s*:"
    r"|-?\s*\d+\s*x\s+.+:\s*\$"
    r"|-\s*(?:mercado pago|transferencia)\s*\()")


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
                 if _RE_RENGLON_CUENTA.match(l)]
    if not renglones:
        return texto
    previo_lineas = {l.strip() for l in (previo or "").splitlines() if l.strip()}
    if all(l.strip() in previo_lineas for l in renglones):
        return texto
    salida, reemplazado = [], False
    for linea in (texto or "").splitlines():
        if not _RE_RENGLON_CUENTA.match(linea):
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


def _bloque_presupuesto(llamadas: list) -> str:
    for l in llamadas:
        r = l.get("resultado") or {}
        if l.get("herramienta") == "armar_presupuesto" and r.get("bloque"):
            return str(r["bloque"])
    return ""


def _productos_del_turno(llamadas: list) -> list:
    """Los productos que el turno mostro, para la memoria. Salen de lo que
    devolvieron las herramientas, no de buscar nombres en el texto."""
    out, vistos = [], set()

    def _add(p):
        pid = str((p or {}).get("id") or "").upper()
        if pid and pid not in vistos and p.get("nombre"):
            vistos.add(pid)
            precio = p.get("precio_ars")
            out.append({"id": pid, "nombre": p["nombre"],
                        "precio": int(precio) if isinstance(precio, (int, float))
                        else 0})

    for l in llamadas:
        r = l.get("resultado") or {}
        for p in (r.get("productos") or []):
            _add(p)
        for p in (r.get("lo_mas_cercano") or []):
            _add(p)
        if isinstance(r.get("producto"), dict):
            _add(r["producto"])
    return out


def _carrito_del_turno(llamadas: list) -> list:
    for l in llamadas:
        if l.get("herramienta") != "armar_presupuesto":
            continue
        detalle = (l.get("resultado") or {}).get("detalle") or []
        carrito = [{"id": str(d.get("id") or "").upper(),
                    "nombre": d.get("nombre"),
                    "cantidad": int(d.get("cantidad") or 1)}
                   for d in detalle if d.get("id")]
        if carrito:
            return carrito
    return []


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
    from app.core.tools_context import set_current_tienda
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

        # ── RECONCILIAR: lo declarado contra lo hecho ───────────────────
        # Acá está el control que faltaba. Los diecinueve que había miraban la
        # prosa ya escrita; este mira la DECISION, antes de escribir. Si algo
        # falta se lo devolvemos al modelo para la vuelta siguiente; si el
        # pedido tiene una contradicción, el turno termina PREGUNTANDO y no
        # eligiendo por el cliente.
        for l in llamadas:
            if l.get("herramienta") == "registrar_pedido":
                declarado = (l.get("resultado") or {}).get("pedido") or declarado
        rec = P.reconciliar(declarado, llamadas, trace_id)
        obligacion = P.instruccion_de_preguntas(rec)
        revision = P.instruccion_de_faltantes(rec)
        if not revision:
            break
        if ronda == _MAX_RONDAS:
            # Se agotaron las vueltas con el hueco abierto. NO se completa por
            # nuestra cuenta: se le dice al redactor que pregunte lo que falta.
            log.warning("hub_venta_faltantes_sin_resolver", trace_id=trace_id,
                        faltantes=rec.get("faltantes", [])[:4])
            obligacion = (obligacion + "\n\n" if obligacion else "") + (
                "No pudiste conseguir todo lo que el cliente pidió. Contá "
                "honesto qué falta y pedile el dato que haga falta. No "
                "completes de memoria lo que no trajo ninguna herramienta.")

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
    texto = _sin_descuento_inventado(texto, trace_id)
    texto = _sin_narracion_interna(texto, trace_id)
    texto = _sin_anuncio_vacio(texto, trace_id)
    # La cuenta se manda entera: si el modelo la reescribio o se la comio, el
    # bloque del codigo vuelve al final. No se negocia, es la unica parte del
    # mensaje que el modelo no redacta.
    if bloque and bloque.splitlines()[0].strip() not in texto:
        texto = (texto + "\n\n" + bloque).strip()
        log.warning("hub_venta_bloque_repuesto", trace_id=trace_id)
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
                                       _productos_del_turno(llamadas))
    carrito = _carrito_del_turno(llamadas) or (conv.get("carrito_vigente") or [])
    localidades = get_envio_localidades() or (conv.get("ultimas_localidades") or [])
    try:
        save_conversation(
            user_id, history, resumen, tienda_id=tienda_id,
            estado_conversacion="en_curso",
            productos_vistos=productos_vistos, carrito_vigente=carrito,
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
