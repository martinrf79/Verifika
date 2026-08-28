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
import contextlib
import json
import time
from collections import Counter

from app.config import get_settings
from app.core import atadura_prosa as AP
from app.core import herramientas as H
from app.core import indice_turno as IT
from app.core import pedido as P
from app.core.resolver import resolver
# El bloque sellado de la cuenta y el hallazgo todavia se leen de reposicion:
# salida.py tambien los usa (FICHA 35). El hub ya no llama a completar.
from app.core import reposicion as R
# LA ETAPA DE SALIDA, en su propio modulo desde la FICHA 10: cuatro puertas en
# vez de dieciocho guardias sueltas. Los dos patrones de renglon de cuenta se
# leen de alla porque alla viven las piezas que los usan.
from app.core import salida as S
from app.core.salida import _RE_HAY_CUENTA, _norm_renglon
from app.logger import get_logger
from app.storage.firestore_client import get_conversation, save_conversation
from app.verifika import grafo as G

log = get_logger(__name__)
settings = get_settings()

_TIMEOUT_S = 14
_MAX_HERRAMIENTAS = 10
# DOS LLAMADAS AL MODELO POR TURNO, FIJAS. El bucle de hasta cuatro rondas se
# saco el 17-ago y con el la variable que mas latencia costaba: cada vuelta son
# entre 3 y 8 segundos y vuelve a pagar los 25.370 bytes del esquema enteros.
#
# EL UNICO MOTIVO REAL por el que existia la ronda dos es que para armar la
# cuenta hacen falta los ids y los ids los trae otra herramienta. Eso es trabajo
# de CODIGO y ya estaba escrito: las reposiciones del paso 2-bis arman la cuenta
# con lo declarado sin preguntarle nada al modelo. La ronda le pagaba al modelo
# por hacer lo que el codigo ya hace.
#
# Y lo que costaba esta medido en este mismo repo, en los comentarios de
# `pedido.py`: ante un reclamo del reconciliador el modelo pidio CERO
# herramientas 3 de 3 veces, y de 88 faltantes emitidos 41 se repitieron en dos
# o mas rondas del MISMO turno. O sea que la vuelta extra no solo tardaba: en el
# caso tipico no traia nada.

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


# LA INSTRUCCION DE LA LLAMADA UNO, DESPUES DE LA PUERTA UNICA (FICHA 06). Ya
# no explica como repartir el trabajo entre nueve herramientas: hay una sola y
# lo unico que se le pide al modelo es que DECLARE completo. Lo que hay que
# buscar lo deriva `_derivar_las_busquedas` de lo declarado.
_INSTRUCCION_UNO = """Llama a registrar_pedido declarando TODO lo que entendiste
del ultimo mensaje. No busques nada: de lo que declares, el sistema busca solo y
te lo trae para que escribas.

Un renglon por CADA cosa que el cliente pidio o pregunto, en el campo que
corresponda: lo que quiere comprar, el dato duro de un producto, si lo tenemos,
si le sirve para lo que tiene, y cualquier cosa que conteste la casa -una
politica, un consejo, una situacion de venta-. Si pregunto tres cosas, van las
tres: lo que no declares no se busca, y el cliente se queda sin esa respuesta.

Contá los items uno por uno como los pidio, y si algo del mensaje no cierra
-cantidades que no dan, algo nombrado en el envio que no esta en el pedido- va
en contradicciones: NO lo resuelvas vos.

Si el mensaje no pide ningun dato -un saludo, un gracias, una respuesta a algo
que preguntaste vos- contesta directamente, sin llamar nada."""

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
    # LO QUE EL CLIENTE DEJO DECIDIDO Y SIGUE VALIENDO. Los tres se guardaban
    # -desde hoy- y ninguno llegaba hasta aca, asi que el turno siguiente
    # arrancaba sin la decision tomada y volvia a preguntar lo mismo.
    prov = str(estado.get("provincia_envio") or "").strip()
    if prov and not any(prov.lower() in str(l).lower() for l in locs):
        partes.append(f"Provincia del cliente, ya dada: {prov}. No se la "
                      f"vuelvas a pedir.")
    ancla = estado.get("producto_anotado") or {}
    if ancla.get("nombre"):
        pid = str(ancla.get("id") or "").upper()
        partes.append(
            f"Producto que el cliente ELIGIO y pidio guardar: "
            f"{ancla['nombre']}" + (f" [{pid}]" if pid else "") +
            ". Si dice 'el que te dije al principio', 'el anotado' o 'el de "
            "antes', habla de ESTE.")
    crit = str(estado.get("criterio") or "").strip()
    if crit:
        partes.append(f"Criterio de precio que ya eligio: {crit}. Vale para "
                      f"todo el pedido; no se lo vuelvas a preguntar.")
    cond = [str(c) for c in
            ((estado.get("preferencias") or {}).get("condiciones") or []) if c]
    if cond:
        partes.append("Condiciones que puso y siguen valiendo, aplicalas en "
                      "cada busqueda: " + ", ".join(cond))
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


# LOS TURNOS EN LOS QUE NO SE LE PUDO HABLAR AL MODELO, por trace_id. Es un
# conjunto y no una variable porque el decisor se llama en un bucle de rondas y
# el turno entero tiene que enterarse; se limpia al terminar el turno, asi que
# nunca crece. No cambia el comportamiento del bot mas que en UNA cosa: que se
# le dice al cliente cuando el turno no pudo contestar.
_SIN_MODELO: set = set()


def _marcar_sin_modelo(trace_id: str) -> None:
    """Anota el turno y NO deja crecer el conjunto. El turno lo borra al
    terminar, pero si explota antes el id quedaria adentro para siempre: un
    tope hace que la peor consecuencia sea olvidar una marca, nunca una fuga de
    memoria en un proceso que vive dias."""
    if len(_SIN_MODELO) > 200:
        _SIN_MODELO.clear()
    _SIN_MODELO.add(trace_id)


async def _pedir_herramientas(negocio, memoria, history, mensaje, tienda_id,
                              trace_id):
    """QUE BUSCAR. Devuelve (lista de pedidos, texto directo si no pidio nada).

    Es la LLAMADA UNO y es la unica vez por turno que el modelo elige
    herramientas. El modo de segunda ronda se saco el 17-ago: lo que hacia
    -encadenar la cuenta despues de tener los ids- lo hace el codigo en las
    reposiciones, sin gastar una vuelta al modelo."""
    cli = _cliente_decisor()
    if cli is None:
        return [], ""
    esquemas = H.esquemas(tienda_id)
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
        # LA MISMA PUERTA QUE EL REDACTOR, y se descubrio el 11-ago intentando
        # regrabar dos casetes con la clave gratis: si el que se cae es el
        # DECISOR, el turno se queda sin herramientas y sin texto, y terminaba
        # igual en "No tengo esa información confirmada en el catálogo". Cerrar
        # una sola de las dos puertas no cerraba nada.
        _marcar_sin_modelo(trace_id)
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
        # LOS IDS QUE UNA TOOL DEVOLVIO QUEDAN CERTIFICADOS. Sin esto la regla
        # cero de la calculadora -con un pedido vigente, un id que no sale del
        # carrito, de lo ya mostrado o de una tool del turno es un id inferido-
        # se quedaba con las dos primeras fuentes y NINGUNA tercera:
        # `certificar_ids_de_resultado` existia, estaba probada y no la llamaba
        # nadie en el camino vivo -la llamaba el loop del agente viejo, que el
        # hub reemplazo-. Consecuencia medida en el turno 6 de
        # `80_charla_real_12ago`: con un carrito de microfonos, el cliente pide
        # auriculares, mouse y memorias, el turno los BUSCA y encuentra, y la
        # cuenta rechaza los seis ids recien traidos por "no certificados". O
        # sea que con un pedido vigente NO se podia cotizar nada nuevo.
        #
        # Se certifica ACA, en el hilo del turno: las tools corren en hilos
        # aparte y una contextvar escrita en otro hilo no vuelve al que suma,
        # que es la misma trampa que ya tenia anotada `armar_presupuesto`.
        try:
            from app.core.estado_venta import certificar_ids_de_resultado
            certificar_ids_de_resultado(r)
        except Exception:  # noqa: BLE001 — certificar no puede tumbar un turno
            pass
        llamadas.append({"herramienta": p["nombre"], "pedido": p.get("args") or {},
                         "resultado": r})
    return llamadas


async def _redactar(negocio, memoria, history, mensaje, llamadas, trace_id,
                    obligacion="") -> tuple[str, bool]:
    """LLAMADA FINAL. El modelo escribe con el JSON delante.

    `obligacion` es lo que el RECONCILIADOR encontró que no cierra y el modelo
    no puede resolver eligiendo. Va al final del prompt, que es donde más pesa.

    Devuelve `(texto, sin_modelo)`. `sin_modelo` en True significa que la
    llamada NO se pudo hacer -sin cliente, o 429 y timeouts hasta agotar los
    reintentos-, que es distinto de que el modelo haya contestado vacio. Ver el
    fallback del turno: al cliente se le dice una cosa o la otra.
    """
    cli = _cliente()
    if cli is None:
        return "", True
    datos = H.contexto_json(llamadas)
    # LA ATADURA DE LA PROSA viaja con la instruccion de redactar, no en una
    # llamada aparte: marcar de donde sale cada dato es parte de escribir, y
    # una vuelta mas al modelo costaria los segundos que estamos peleando.
    instr = _INSTRUCCION_DOS + "\n\n" + AP.INSTRUCCION
    instr += ("\n\n" + obligacion) if obligacion else ""
    msgs = _mensajes(negocio, memoria, history, mensaje, instr, datos)

    def _call():
        r = cli.chat.completions.create(
            model=_modelo(), messages=msgs, temperature=0.6, max_tokens=1200,
            extra_body={"reasoning_effort": settings.REDACTOR_REASONING})
        return r.choices[0].message.content or ""

    from app.core.llm_reintento import llamar_con_reintento
    try:
        return await llamar_con_reintento(_call, timeout_s=_TIMEOUT_S,
                                          trace_id=trace_id), False
    except Exception as e:
        log.warning("hub_venta_llamada_dos_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:160]}")
        # EL SEGUNDO VALOR ES "el modelo NO contesto", y no es un detalle: de
        # el depende que se le diga al cliente. Ver el fallback del turno.
        return "", True




def _reparto_que_se_guarda(del_turno, guardado, carrito) -> list | None:
    """El reparto de envios que queda persistido al cerrar el turno.

    Si el turno resolvio uno, manda ese. Si no, sigue valiendo el guardado...
    salvo que ya no cuadre con el pedido, y ahi se limpia.

    POR QUE, y lo encontro el barrido de memoria del 13-ago sobre una
    transicion que ninguna charla tenia: el reparto se guarda por merge, asi
    que un turno que no calcula ninguno CONSERVA el anterior. Cuando el cliente
    saca un producto, el carrito baja y el reparto guardado sigue repartiendo
    las unidades viejas: quedo uno de cinco unidades con un carrito de dos. Hoy
    el daño lo ataja el todo-o-nada -no se repone un reparto que no cuadra- pero
    un dato guardado que miente es un error esperando su turno, y es exactamente
    la familia del 12-ago: la cuenta vieja que se reestampaba.

    Devuelve None para "no toques lo guardado", que es lo que el save entiende.
    """
    if del_turno:
        return del_turno
    if not guardado:
        return None
    reparte = sum(int(c.get("n") or 0) for g in guardado
                  for c in (g.get("cats") or []) if isinstance(c, dict))
    tiene = sum(int(c.get("cantidad") or 1) for c in (carrito or []))
    if reparte == tiene:
        return None
    log.info("reparto_guardado_ya_no_cuadra", reparte=reparte, carrito=tiene)
    return []


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
    if R._bloque_presupuesto(llamadas):
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


def _preferencias_al_dia(previas: dict, declarado: dict, llamadas: list) -> dict:
    """Las condiciones que el cliente puso y siguen valiendo, acumuladas.

    POR QUE ACUMULA Y NO PISA. El cliente pone una condicion una vez -"las menos
    partes chinas posibles"- y despues habla de otra cosa: destinos, pago, un
    producto mas. Si la condicion viviera solo en el turno donde se dijo, la
    busqueda del turno siguiente ya no la aplicaria. El campo
    `preferencias_cliente` existia en la conversacion y en el estado desde el
    16-jul y no lo escribia NADIE: llegaba siempre vacio.

    De donde salen: de las restricciones que viajan en `declarado`, que para
    cuando el turno cierra ya traen lo que el modelo declaro MAS lo que el
    codigo dedujo de los filtros de la busqueda. Es la misma lista que ya usan
    el reconciliador y el indice. No se inventa ninguna condicion nueva.

    `llamadas` entra para completar la union cuando el turno no paso por el
    enriquecido -un turno sin reconciliador-, que es el mismo dato por la otra
    puerta."""
    previas = previas if isinstance(previas, dict) else {}
    condiciones = [str(c).strip() for c in (previas.get("condiciones") or [])
                   if str(c or "").strip()]
    try:
        completo = _restricciones_de_los_filtros(declarado or {}, llamadas)
    except Exception:  # noqa: BLE001 — la memoria nunca tumba el turno
        completo = declarado or {}
    nuevas = [str(r).strip() for r in (completo.get("restricciones") or [])
              if str(r or "").strip()]
    for c in nuevas:
        if c.lower() not in {x.lower() for x in condiciones}:
            condiciones.append(c)
    if not condiciones:
        return {}
    return {"condiciones": condiciones[-6:]}


def _restricciones_de_los_filtros(declarado: dict, llamadas: list,
                                  trace_id: str = "") -> dict:
    """LO QUE EL MODELO APLICO Y NO DECLARO, entra igual a lo declarado.

    EL CASO, medido el 12-ago con el banco de interpretacion y es el que Martin
    ve en real: el cliente pide "las menos partes chinas posibles" y el sistema
    SI lo entiende — la busqueda sale con `pais_fabricacion no_contiene china` y
    `pais_marca no_contiene china`, que son dos campos reales del catalogo—.
    Pero el criterio NO aparece en las restricciones que declara
    `registrar_pedido`, y falla asi en 3 de 6 redacciones de la misma pregunta.

    POR QUE ESO SOLO YA ROMPE LA RESPUESTA. El reconciliador y el indice del
    turno trabajan sobre lo DECLARADO. Un criterio que no se declaro queda
    afuera de todos los controles: nadie puede exigir que se conteste algo que
    nunca se anoto. El bot busca, no encuentra ninguno que cumpla del todo —y
    puede ser cierto, si todo el rubro es chino— y contesta el "no tengo esa
    informacion", teniendo en la mano el bloque de lo que MAS SE ACERCA y la
    lista de donde SI se cumple, que es la respuesta razonada que hace falta.

    ES LA MISMA FALLA DE PLOMERIA DE TODA LA SEMANA: el mismo hecho existe en
    una puerta —los filtros de la busqueda— y no en la otra —las restricciones
    declaradas—. Se completa de la puerta que lo tiene.

    NO ES EL CODIGO INVENTANDO UN CRITERIO: la condicion la escribio el modelo
    en su propia llamada, sobre un campo real del catalogo. Aca solo se copia al
    lugar donde los controles la pueden ver."""
    if not declarado:
        return declarado
    from app.core.filtros_catalogo import DERIVADOS

    ya = H._norm(" ".join(str(r) for r in (declarado.get("restricciones") or [])))
    nuevas = []
    for l in llamadas or []:
        for f in ((l.get("pedido") or {}).get("filtros") or []):
            if not isinstance(f, dict) or not f.get("campo"):
                continue
            valor = str(f.get("valor") or "").strip()
            if not valor:
                continue
            campo = str(f["campo"])
            desc = DERIVADOS.get(campo, campo.replace("_", " "))
            op = str(f.get("operador") or "").lower()
            frase = (f"sin {valor} en {desc}" if op == "no_contiene"
                     else f"{desc} mayor a {valor}" if op == "mayor"
                     else f"{desc} menor a {valor}" if op == "menor"
                     else f"{desc} {valor}")
            if H._norm(valor) in ya or H._norm(frase) in ya:
                continue
            ya += " " + H._norm(frase)
            nuevas.append(frase)
    if not nuevas:
        return declarado
    log.info("restriccion_declarada_por_codigo", trace_id=trace_id,
             nuevas=nuevas[:4])
    fuera = dict(declarado)
    fuera["restricciones"] = list(declarado.get("restricciones") or []) + nuevas
    return fuera




def _senal_de_cierre(llamadas: list, mensaje: str) -> dict:
    """La interpretacion MINIMA que necesita el cierre. Antes eran veinte campos
    de un interprete; lo unico que `leads` mira es la intencion y la confianza.

    LA SEÑAL DE COMPRA SALE DEL MENSAJE, NO DE UNA HERRAMIENTA (FICHA 06,
    23-ago-2026, y es la trampa 4 de la ficha). `tomar_pedido` dejo de ser
    visible para el modelo junto con las otras siete, y en 55 turnos grabados no
    se habia llamado NUNCA, asi que colgar el cierre de ella era colgarlo de una
    puerta que nadie usaba. La marca determinista ya existia y ya la miraba
    `_cerrar`: `_RE_PIDE_COBRO` sobre el mensaje del cliente. Ahora la miran los
    dos, con UNA definicion. La herramienta sigue viva para el turno en que el
    codigo la necesite; lo que se saco es que la decision dependa de que el
    modelo se acuerde de llamarla."""
    from app.core.leads import _RE_PIDE_COBRO
    for l in llamadas:
        if l.get("herramienta") == "tomar_pedido":
            return {"intencion": "decision_compra", "confianza": 1.0,
                    "motivo": (l.get("pedido") or {}).get("motivo")}
    if _RE_PIDE_COBRO.search(mensaje or ""):
        return {"intencion": "decision_compra", "confianza": 1.0,
                "motivo": "pide_datos_de_pago"}
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


@contextlib.contextmanager
def _reloj(etapas: dict, nombre: str):
    """EL RELOJ POR ETAPA. El turno logueaba UN solo `latency_ms` total, asi que
    "tarda 26 segundos" no se podia repartir entre el decisor, las herramientas
    y el redactor: cualquier cambio de modelo o de proveedor se medía a ciegas y
    la discusion terminaba en opinion. Acumula por nombre y ademas CUENTA las
    veces, porque el decisor entra una vez por ronda y el reparto entre "tarda
    mucho" y "entra muchas veces" es justamente lo que hay que separar.

    No decide nada ni puede romper el turno: solo mide."""
    t = time.perf_counter()
    try:
        yield
    finally:
        ms = int((time.perf_counter() - t) * 1000)
        etapas[nombre] = etapas.get(nombre, 0) + ms
        etapas[nombre + "_n"] = etapas.get(nombre + "_n", 0) + 1


async def procesar_venta(user_id: str, raw_message: str, tienda_id: str,
                         canal: str, trace_id: str) -> str:
    """Un turno completo. Devuelve el texto para el cliente."""
    t0 = time.time()
    etapas: dict = {}
    from app.core.estado_venta import (construir_estado, set_current_estado,
                                       get_envio_localidades, merge_productos)
    from app.core.contexto_turno import set_current_tienda
    from app.core import guardas_salida as gs

    G.abrir_turno()
    conv = get_conversation(user_id, tienda_id=tienda_id)
    history = conv.get("history", []) or []
    estado = construir_estado(conv, None)
    # QUE SIGNIFICA QUE EL ESTADO INTERVINO: que trajo algo de la charla
    # anterior. En el primer turno no hay nada que traer y no interviene, que
    # es exactamente lo que tiene que decir el instrumento.
    G.veredicto("estado",
                any((estado.get(k) or []) for k in
                    ("carrito", "productos_vistos", "localidades_envio")),
                f"carrito:{len(estado.get('carrito') or [])} "
                f"vistos:{len(estado.get('productos_vistos') or [])}")
    # EL MENSAJE DEL CLIENTE, EN EL ESTADO. Las herramientas deterministas leen
    # del estado y no reciben el mensaje por parametro -su firma la ve el
    # modelo-, asi que sin esto la cuenta no puede saber que el cliente pidio
    # SUMAR algo a lo que ya tenia en vez de declarar un pedido nuevo. Es la
    # misma clase de dato que el criterio de precio o los destinos: se lee del
    # mensaje, con codigo, y no depende de que el modelo lo entienda ese dia.
    estado["mensaje_del_turno"] = raw_message or ""
    set_current_tienda(tienda_id)
    set_current_estado(estado)

    negocio = gs.business_name(tienda_id)
    memoria = _memoria_texto(estado, history, tienda_id)
    # QUE SIGNIFICA QUE INTERVINO: que le puso memoria delante al modelo. Si
    # sale vacio, el modelo ve la charla sin nada mas, y eso hay que verlo.
    G.veredicto("memoria_texto", bool((memoria or "").strip()),
                f"largo:{len(memoria or '')}")

    # ── 1 y 2. QUE BUSCAR, y TODO JUNTO ─────────────────────────────────
    # Dos rondas como mucho. Adentro de cada ronda las herramientas corren en
    # paralelo; la segunda existe solo para lo que se DESBLOQUEA con lo que
    # trajo la primera, que en la practica es armar el presupuesto con los ids
    # ya certificados. Mas rondas no: seria volver a una cadena larga.
    llamadas: list = []
    texto_directo = ""
    obligacion = ""
    declarado: dict = {}
    # LA CHARLA, NO SOLO EL TURNO: el carrito vigente y lo ya mostrado son
    # productos CERTIFICADOS. Lo necesitan la derivacion -para que "y ese
    # cuanto pesa" resuelva contra lo que el cliente ya vio- y las reposiciones
    # de mas abajo, cuando el turno no volvio a buscar nada porque no hacia
    # falta. Se arma una sola vez, arriba de las dos.
    _memoria_idx = ((conv.get("carrito_vigente") or [])
                    + (estado.get("productos_vistos") or []))
    with _reloj(etapas, "decisor"):
        pedidos, texto_directo = await _pedir_herramientas(
            negocio, memoria, history, raw_message, tienda_id, trace_id)
    # QUE SIGNIFICA QUE EL DECISOR INTERVINO: que mando a buscar. Cuando
    # contesta directo -un saludo, un gracias- no manda a buscar nada, y el
    # detalle guarda cual de los dos caminos fue.
    G.veredicto("decisor", bool(pedidos),
                f"pedidos:{len(pedidos)}" if pedidos
                else f"directo:{len(texto_directo or '')}")
    log.info("hub_venta_pedidos", trace_id=trace_id,
             herramientas=[p["nombre"] for p in pedidos],
             args=[p.get("args") for p in pedidos][:4])
    if pedidos:
        with _reloj(etapas, "herramientas"):
            llamadas = await _ejecutar_en_paralelo(pedidos, tienda_id, trace_id)
        # QUE SIGNIFICA QUE INTERVINO: que volvio con evidencia. Un pedido que
        # vuelve con cero llamadas deja al redactor sin nada, y hasta hoy eso
        # no dejaba marca en ningun lado.
        G.veredicto("herramientas", bool(llamadas), f"llamadas:{len(llamadas)}")
        log.info("hub_venta_resultados", trace_id=trace_id,
                 estados=[(l["herramienta"],
                           (l["resultado"] or {}).get("estado"))
                          for l in llamadas])
        G.anotar("herramientas_usadas",
                 sorted({l["herramienta"] for l in llamadas}))
        _log_fuente(llamadas, trace_id, 1)

        for l in llamadas:
            if l.get("herramienta") == "registrar_pedido":
                declarado = (l.get("resultado") or {}).get("pedido") or declarado
        try:
            declarado = _restricciones_de_los_filtros(declarado, llamadas,
                                                      trace_id)
        except Exception as e:  # noqa: BLE001
            log.warning("restriccion_declarada_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
    # ── 2. RESOLVER: una sola opinion, desde lo declarado (FICHA 34) ────
    # El hub deja de llamar a reconciliar y a completar. Busquedas, cuenta
    # y contrato salen del declarado. Si el piso baja, revert entero.
    out = resolver(declarado, _memoria_idx, tienda_id, trace_id,
                   llamadas=llamadas,
                   descartados=conv.get("descartados") or [],
                   diferida=conv.get("oferta_diferida") or [])
    G.veredicto("resolver", bool(out["llamadas"]) or bool(declarado),
                f"llamadas:{len(out['llamadas'])} "
                f"puntos:{len((out['contrato'] or {}).get('puntos') or [])}")
    llamadas = out["llamadas"]
    idx = out["contrato"] or {}
    bloque = out["bloque"] or ""
    G.veredicto("indice_turno", bool(idx.get("faltan")),
                f"puntos:{len(idx.get('puntos') or [])} "
                f"faltan:{len(idx.get('faltan') or [])}")
    G.anotar("puntos_del_pedido", len(idx.get("puntos") or []))
    G.anotar("sin_material", [p["id"] for p in (idx.get("faltan") or [])][:5])
    pendiente = IT.instruccion(idx.get("faltan") or [])
    if pendiente:
        obligacion = (obligacion + "\n\n" if obligacion else "") + pendiente
    if bloque:
        sello = ("CUENTA SELLADA DEL CODIGO. Pegala tal cual.\n" + bloque)
        obligacion = (sello + "\n\n" + obligacion) if obligacion else sello
    if any(p.get("tipo") != "oferta" for p in (idx.get("faltan") or [])):
        obligacion += ("\n\nSi para alguno de esos puntos no tenés el dato en "
                       "lo que trajeron las herramientas, decilo honesto y "
                       "pedile al cliente lo que falte. No lo completes de "
                       "memoria ni lo deduzcas.")

    # ── 3. REDACTAR CON EL DATO DELANTE ─────────────────────────────────
    sin_modelo = False
    if llamadas:
        with _reloj(etapas, "redactor"):
            texto, sin_modelo = await _redactar(
                negocio, memoria, history, raw_message, llamadas, trace_id,
                obligacion=obligacion)
        # QUE SIGNIFICA QUE EL REDACTOR INTERVINO: que escribio algo. El
        # detalle dice si lo escribio el modelo o el respaldo sin modelo, que
        # es la diferencia que mas importa cuando una respuesta sale rara.
        G.veredicto("redactor", bool((texto or "").strip()),
                    f"largo:{len(texto or '')}"
                    + (" sin_modelo" if sin_modelo else ""))
    else:
        # Sin herramientas el modelo ya contesto en la llamada uno: es un
        # saludo, un gracias o una respuesta a algo que preguntamos nosotros.
        texto = texto_directo

    if not (texto or "").strip():
        # LA MENTIRA QUE SE ARREGLO EL 11-AGO, y salio de medir la clave
        # gratis. Cuando el 429 tumbaba la llamada del redactor, al cliente le
        # llegaba "No tengo esa información confirmada en el catálogo" —
        # medido: pregunto por auriculares con microfono, la herramienta los
        # habia ENCONTRADO, y se le contesto que no habia dato. El proveedor se
        # cayo y el bot le echo la culpa al catalogo: es una afirmacion FALSA
        # sobre el stock, que es justo lo que el sistema entero existe para
        # evitar, y ademas se lee como una respuesta normal y no como una
        # falla. Si no hubo modelo se dice que hay demanda y se pide que
        # reintente; el "no tengo el dato" queda solo para cuando el modelo SI
        # contesto y no trajo nada.
        if sin_modelo or trace_id in _SIN_MODELO:
            from app.core.guia_venta_prosa import mensaje as _prosa
            texto = _prosa("sobrecarga",
                           "Perdón, estoy con mucha demanda en este momento. "
                           "Probá de nuevo en un ratito y te respondo. 🙏")
            log.warning("hub_venta_sin_modelo", trace_id=trace_id)
        else:
            texto = settings.VERIFIKA_FALLBACK_MESSAGE
            log.warning("hub_venta_sin_texto", trace_id=trace_id)

    # ── 4. LA SALIDA: CUATRO PUERTAS, Y ESTAS SON LAS DOS QUE RESTAN ────
    # ERAN DIECIOCHO NODOS EN FILA (FICHA 10, 24-ago-2026). Ninguno sobraba:
    # cada uno nacio de una alucinacion medida y sigue corriendo, con su
    # docstring y sus pruebas, adentro de la puerta que le toca. Lo que se
    # agrupo es el PASO DEL TURNO. Dieciocho piezas en fila son diecisiete
    # costuras, y las costuras -no las piezas- son donde vivieron los dos
    # errores de plata de agosto: `peso_de_la_cadena.py` los encontro midiendo
    # que dos nodos intervenian sobre los mismos mensajes el 81,8% de las veces
    # sin saber uno del otro. Con cuatro puertas quedan tres costuras, y el
    # orden de adentro esta fijo en `salida.py` en vez de repartido acá.
    #
    # CADA PUERTA PASA POR `G.paso` Y CADA PIEZA TAMBIEN, asi que el veredicto
    # por engranaje no se pierde: se sigue midiendo comparando el texto, pieza
    # por pieza, y la ficha del turno dice lo mismo que decia con dieciocho.
    bloque = bloque or R._bloque_presupuesto(llamadas)
    # ── LA FRONTERA, Y ES LA UNICA VEZ QUE EXISTE (FICHA 21) ──────────────
    # Desde la linea siguiente, `texto` deja de ser lo que escribio el modelo:
    # cuatro puertas podan y una SUMA prosa propia. Despues no hay forma de
    # saber cual mitad la escribio quien —adentro, las dos son el mismo str—,
    # y eso es lo que hizo la regresion: `camino_cobro` estampaba "link de
    # pago" y "tu nombre", y `punto_de_oferta` leia esos literales suyos como
    # si los hubiera decidido el modelo, daba el turno por CERRANDO y mataba
    # cuatro ofertas de quince charlas.
    #
    # SE GUARDA ACA Y NO SE RECONSTRUYE DESPUES. Recortar la linea del cobro
    # del texto final seria tapar este caso y dejar la costura entera abierta
    # para la proxima puerta que estampe algo. Es la regla 13 de ARRANQUE.md.
    texto_del_modelo = texto
    texto = G.paso("procedencia", S.procedencia,
                   texto, llamadas, trace_id, tienda_id)
    texto = G.paso("plata", S.plata, texto, llamadas, bloque, trace_id,
                   previo=conv.get("ultimo_presupuesto") or "",
                   vistos=estado.get("productos_vistos") or [],
                   declarado=declarado,
                   carrito=conv.get("carrito_vigente") or [])

    # ── 5. CIERRE Y COBRO ───────────────────────────────────────────────
    senal = _senal_de_cierre(llamadas, raw_message)
    _texto_antes_del_cierre = texto
    with _reloj(etapas, "cierre"):
        texto, datos_cliente, pregunta_cierre_hecha = await _cerrar(
            conv, user_id, canal, tienda_id, raw_message, texto, trace_id,
            senal, bloque)
    G.veredicto("cierre", texto != _texto_antes_del_cierre,
                f"{len(_texto_antes_del_cierre or '')}->{len(texto or '')}"
                if texto != _texto_antes_del_cierre else "")

    # ── 6. LA OBLIGACION: lo que tiene que estar si o si ────────────────
    # Cuatro cosas y solo cuatro, ninguna opinable: que es un bot si preguntan,
    # el saludo la primera vez, el punto que el cliente pregunto y el sistema
    # sabia contestar, y COMO SE PAGA cuando hay un total cerrado. Es la UNICA
    # puerta que suma, y por eso va despues de las dos que restan y antes de la
    # que mide el largo.
    #
    # `dichos` es TODO lo que el bot ya le dijo al cliente en esta charla, no
    # solo el mensaje anterior: el camino al cobro se dice UNA vez por charla, y
    # con el ultimo mensaje solo se veria si se dijo en el turno de recien.
    dichos = "\n".join(str(h.get("content") or "") for h in (history or [])
                       if h.get("role") == "assistant")
    texto = G.paso("obligacion", S.obligacion, texto, raw_message, negocio,
                   not history, declarado, llamadas, _memoria_idx, tienda_id,
                   trace_id, conv.get("descartados") or [], dichos,
                   texto_del_modelo)

    # ── 7. LA HIGIENE: el mensaje entero, una sola vez ──────────────────
    # Va ULTIMA a proposito. Hasta acá cada puerta pegó o podó lo suyo y
    # ninguna miró el total; este es el unico punto del turno donde el mensaje
    # existe entero y todavia se puede acortar. Adelantarla aunque sea un paso
    # la dejaria midiendo un mensaje que despues crece.
    anterior = next((h.get("content") for h in reversed(history or [])
                     if h.get("role") == "assistant"), "")
    texto = G.paso("higiene", S.higiene, texto, str(anterior or ""),
                   raw_message, trace_id, tienda_id)

    # ── 7. MEMORIA ──────────────────────────────────────────────────────
    history = history + [{"role": "user", "content": raw_message},
                         {"role": "assistant", "content": texto}]
    resumen = conv.get("summary", "") or ""
    descartados = history[:-(settings.HISTORY_LIMIT * 2)]
    if descartados:
        try:
            from app.core.memoria_larga import actualizar_resumen
            with _reloj(etapas, "memoria"):
                resumen = await actualizar_resumen(resumen, descartados,
                                                   trace_id)
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
    #
    # SALVO QUE EL CLIENTE HAYA PEDIDO AGREGAR. Ahi la declaracion es de lo que
    # se SUMA, no del pedido entero, y leerla como pedido completo borra lo que
    # ya habia: "agrega un teclado" sobre seis articulos dejaba el carrito en un
    # teclado y anotaba los seis en la memoria negativa, o sea que no volvian
    # nunca mas. Es el mismo mensaje real del 12-ago que rompia la cuenta.
    from app.core.estado_venta import (ancla_al_dia, detectar_criterio,
                                       libera_criterio,
                                       pide_agregar_al_pedido)
    agrega = pide_agregar_al_pedido(raw_message)
    carrito = _carrito_del_turno(llamadas)
    dados_de_baja = []
    if not carrito and not agrega:
        carrito, dados_de_baja = _carrito_podado(
            conv.get("carrito_vigente") or [], declarado)
    elif not carrito:
        carrito = conv.get("carrito_vigente") or []
    declarado_ahora = _declarados(declarado)
    if agrega and declarado_ahora:
        # La foto del pedido es la de antes MAS lo que se sumo: si se guardara
        # sola la parte agregada, el turno siguiente compararia contra ella y
        # daria de baja todo lo anterior.
        declarado_ahora = list(dict.fromkeys(
            (conv.get("ultimo_declarado") or []) + declarado_ahora))
    descartados = _descartados_nuevos(
        conv.get("descartados") or [], dados_de_baja, carrito,
        declarado_antes=(None if agrega else conv.get("ultimo_declarado") or []),
        declarado_ahora=declarado_ahora)
    localidades = get_envio_localidades() or (conv.get("ultimas_localidades") or [])
    # LOS TRES CAMPOS DE MEMORIA QUE SE LEIAN Y NO ESCRIBIA NADIE (12-ago).
    #
    # `construir_estado` levanta de la conversacion `criterio_cliente`,
    # `provincia_envio` y `preferencias_cliente` en CADA turno, y el hub nunca
    # los guardaba: los tres llegaban siempre vacios. No es que estuvieran mal
    # calculados, es que no existian. Lo que costaba cada uno:
    #   - criterio: "lo mas barato" se perdia al turno siguiente y el bot volvia
    #     a preguntar modelo y color de algo que el cliente ya habia decidido.
    #   - provincia: `cotizar_envio` la LEE del estado para resolver un pueblo
    #     ambiguo sin volver a pedir el CP -y siempre leia ""-. Es el
    #     "necesito el codigo postal de Correa y San Nicolas" de la charla real.
    #   - preferencias: "las menos partes chinas posibles" no sobrevivia al
    #     turno, asi que la busqueda siguiente ya no la aplicaba.
    # Los tres salen de datos deterministas que el turno ya tiene: el mensaje
    # del cliente y lo que el modelo declaro. Sticky: si este turno no dice
    # nada, se conserva lo anterior.
    # El criterio es STICKY, asi que tiene que poder soltarse: sin eso el
    # sistema le arrastra al cliente una decision que acaba de aflojar
    # ("el precio no seria tan importante", charla real del 12-ago).
    criterio = ("" if libera_criterio(raw_message)
                else detectar_criterio(raw_message)
                or (conv.get("criterio_cliente") or ""))
    provincia = conv.get("provincia_envio") or ""
    try:
        from app.core.geo_cp import resolver as _geo_resolver
        _prov, _ = _geo_resolver(raw_message)
        if _prov:
            provincia = str(_prov).replace("_", " ")
    except Exception as e:  # noqa: BLE001 — la memoria nunca tumba el turno
        log.warning("hub_venta_provincia_error", trace_id=trace_id,
                    error=str(e)[:120])
    preferencias = _preferencias_al_dia(conv.get("preferencias_cliente") or {},
                                        declarado, llamadas)
    # EL ANCLA: el producto que el cliente eligio y pidio guardar. Los
    # candidatos son los que el turno dejo sobre la mesa, en orden: el pedido
    # vigente si es uno solo, y si no lo que se mostro este turno.
    _cands = ([{"id": c.get("id"), "nombre": c.get("nombre")}
               for c in carrito] if len(carrito) == 1
              else _productos_del_turno(llamadas, turno=len(history) // 2))
    ancla = ancla_al_dia(conv.get("producto_anotado") or {}, raw_message, _cands)
    # EL REPARTO DE ENVIOS, PERSISTIDO. Lo escribe en el estado el que lo
    # resuelve -el parser del mensaje o la cuenta, con el reparto que declaro
    # el modelo item por item- y hasta hoy moria con el turno: dos turnos
    # despues, con el mismo carrito, el bloque volvia a pedir "decime que va a
    # cada uno" (charla real del 12-ago). Se guarda el ultimo que cerro; si el
    # turno no cerro ninguno, va None y el merge conserva el anterior.
    try:
        from app.core.estado_venta import get_current_estado as _gce_grupos
        _grupos_envio = (_gce_grupos() or {}).get("grupos_envio") or None
    except Exception:  # noqa: BLE001 — la memoria nunca tumba el save
        _grupos_envio = None
    _grupos_envio = _reparto_que_se_guarda(
        _grupos_envio, conv.get("grupos_envio") or [], carrito)
    # EL INDICE, MEDIDO SOBRE LO QUE EL CLIENTE VA A LEER. La pasada de arriba
    # mira el material y sirve para PEDIR; esta mira el texto final y sirve para
    # SABER. Es la regla de tau-bench: se juzga por lo observado, no por lo que
    # el agente cuenta que hizo. Sin esto, "el destino no llego al mensaje" solo
    # se descubre leyendo una charla a mano, que es como se descubrio hoy.
    # VAN LOS DESCARTADOS DE ESTE TURNO, no los de antes: la medicion es sobre
    # el estado con que el turno cierra, y aca `descartados` ya incluye lo que
    # el cliente acaba de sacar del pedido.
    #
    # VA ANTES DEL SAVE DESDE LA FICHA 16B, y no es un detalle de orden: esta
    # pasada es la que dice que oferta quedo DIFERIDA, y eso se guarda con el
    # resto de la memoria del turno. Calcularla despues del save obligaria a una
    # segunda cuenta o a un segundo save, y las dos formas son una costura.
    # VA `texto_del_modelo` (FICHA 21): esta pasada es la que decide que oferta
    # queda DIFERIDA y la guarda en la conversacion. Con el texto final, la
    # linea del cobro apagaba la oferta con motivo tipado `cerrando` y
    # `pendientes` salia vacio, o sea que no la difería: la mataba.
    _idx_final = IT.cobertura(declarado, texto, trace_id + "|final",
                              llamadas=llamadas, memoria=_memoria_idx,
                              descartados=descartados,
                              diferida=conv.get("oferta_diferida") or [],
                              texto_del_modelo=texto_del_modelo)
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
            grupos_envio=_grupos_envio,
            # VA EL VALOR, NO `or None`: `None` significa 'no toques lo
            # guardado', asi que soltar el criterio -que lo deja en ""- no
            # se hubiera guardado nunca y el sticky no se soltaba mas.
            criterio_cliente=criterio,
            producto_anotado=(ancla if ancla != (conv.get("producto_anotado") or {})
                              else None),
            provincia_envio=provincia or None,
            preferencias_cliente=preferencias or None,
            datos_cliente_parciales=datos_cliente,
            pregunta_cierre_hecha=pregunta_cierre_hecha,
            # LA OFERTA DIFERIDA (FICHA 16B). Va SIEMPRE el valor, nunca
            # `or None`: la lista vacia es el dato que APAGA la oferta
            # pendiente —el cliente la rechazo, ya esta en el carrito, el turno
            # cerraba, o el turno la ofrecio de verdad— y con `or None` no se
            # hubiera guardado nunca, asi que el producto se arrastraria para
            # siempre. Eso es exactamente la insistencia que el punto evita.
            oferta_diferida=_idx_final.get("diferida") or [],
            ultimo_presupuesto=(bloque or conv.get("ultimo_presupuesto") or None))
        G.veredicto("memoria", True,
                    f"turnos:{len(history) // 2} carrito:{len(carrito or [])}")
    except Exception as e:
        G.veredicto("memoria", False, f"no_guardo:{type(e).__name__}")
        log.warning("hub_venta_save_error", trace_id=trace_id, error=str(e)[:150])

    G.anotar("sin_contestar", [p["id"] for p in (_idx_final.get("faltan") or [])][:5])
    # EN QUE TERMINO CADA PUNTO (FICHA 08). `sin_contestar` mete cuatro cosas
    # distintas en la misma bolsa y tres no son un defecto: el turno pregunto,
    # no habia con que contestarlo, o el cliente se contradijo. Aca se separan,
    # y lo que queda SIN_ESTADO es la omision pelada —la unica que la puerta de
    # la ficha 09 va a frenar—. Sin esta linea el numero no se ve en ningun
    # lado y la puerta se escribiria a ciegas.
    _censo = Counter(p.get("estado") or "SIN_ESTADO"
                     for p in (_idx_final.get("puntos") or []))
    G.anotar("estados", dict(_censo))
    G.anotar("sin_estado", [p["id"] for p in (_idx_final.get("puntos") or [])
                            if not p.get("estado")][:5])
    # EL VEREDICTO DE LA PUERTA, SOBRE EL TEXTO QUE EL CLIENTE VA A LEER
    # (FICHA 09). La guardia de arriba ya repuso lo que sabia reponer, asi que
    # lo que la puerta marque ACA es lo que se fue sin decir teniendo el dato:
    # el numero que hasta hoy solo se veia leyendo una charla a mano. `puede`
    # en False no retiene el mensaje —#14 y #16 de DECISIONES— pero deja el
    # turno en rojo, que es lo que hace que el numero se pueda perseguir.
    _puerta = IT.puede_salir(_idx_final.get("puntos") or [])
    G.veredicto("puerta_cobertura", not _puerta["puede"],
                f"omitidos:{len(_puerta['omitidos'])} "
                f"sin_prueba:{len(_puerta['sin_prueba'])}")
    if not _puerta["puede"]:
        log.warning("turno_salio_con_omision", trace_id=trace_id,
                    motivo=_puerta["motivo"][:200],
                    puntos=[p["id"] for p in _puerta["omitidos"]][:5])
    # LA MEMORIA, EN LA MISMA FICHA. Era el unico engranaje del turno que no se
    # veia: lo que el turno RECORDABA y lo que GUARDA solo se podian saber
    # bajando el documento de Firestore y comparandolo a mano contra el
    # anterior. Por eso cuatro campos estuvieron muertos sin que nadie lo
    # notara —el reparto, el criterio, la provincia y las preferencias, leidos
    # en cada turno y escritos por nadie—. Ahora la linea dice cuantos items
    # tiene el pedido, si hay ancla, y que decisiones del cliente siguen
    # vigentes. Un campo que se vacia se ve en el turno en que pasa.
    G.anotar("memoria", {
        "carrito": len(carrito or []),
        "vistos": len(productos_vistos or []),
        "descartados": len(descartados or []),
        "destinos": len(localidades or []),
        "reparto": len(_grupos_envio or []),
        "ancla": bool((ancla or {}).get("id")),
        "criterio": criterio or "",
        "provincia": provincia or "",
        "condiciones": len((preferencias or {}).get("condiciones") or []),
        "resumen": len(resumen or ""),
        # Lo que el CODIGO repuso en la cuenta desde la memoria: el pedido de
        # antes cuando el cliente pidio agregar, y el reparto que la charla ya
        # habia cerrado. Son las dos veces que la plata sale de la memoria y no
        # de lo que el modelo declaro, asi que tienen que verse.
        "repuso": sorted({r for l in llamadas
                          for r in ((l.get("resultado") or {}).get("repuso") or [])
                          if isinstance(l.get("resultado"), dict)}),
    })
    try:
        from app.core.aduana import marcador as _marcador_aduana
        _m = _marcador_aduana()
        G.anotar("aduana", {k: _m[k] for k in ("rojas", "defectos", "reparadas")})
    except Exception:  # noqa: BLE001 — la ficha nunca puede tumbar un turno
        pass

    _SIN_MODELO.discard(trace_id)
    # EL VEREDICTO DEL TURNO, en la misma linea que ya se lee. Dice QUE
    # engranaje toco el mensaje, medido comparando, no preguntandole a cada
    # uno. Cuando una respuesta sale mal, este es el primer lugar donde mirar.
    log.info("hub_venta_ok", trace_id=trace_id,
             latency_ms=int((time.time() - t0) * 1000),
             etapas_ms=etapas, largo=len(texto or ""),
             herramientas=len(llamadas), con_presupuesto=bool(bloque),
             **G.veredicto_del_turno())
    return texto
