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
import re
import time
from collections import Counter

from app.config import get_settings
from app.core import atadura_prosa as AP
from app.core import herramientas as H
from app.core import indice_turno as IT
from app.core import pedido as P
from app.logger import get_logger
from app.storage.firestore_client import get_conversation, save_conversation
from app.verifika import grafo as G
# El patron del renglon de la cuenta, del nucleo de invariantes: una sola
# definicion, igual que la comparte la aduana.
from app.verifika import invariantes as INV

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


_RE_ORACIONES = re.compile(r"(?:[^.!?\n]|(?<=\d)[.,](?=\d))+[.!?]?")
# EL PUNTO DE LOS MILES NO TERMINA UNA ORACION (17-ago-2026). Este patron
# era `[^.!?\n]+[.!?]?` y partia "$67.500 - 10% descuento = $60.750" en tres
# pedazos, cortando POR ADENTRO de los numeros. Cualquier guardia que borre
# una "oracion" podia entonces llevarse medio renglon de plata y dejar una
# cifra que nadie calculo: medido ese dia, quedo "$67.750" donde iban $67.500
# y $60.750, y lo cazo el invariante de que las partes suman el total. Un
# punto entre digitos ahora es parte del numero, que es lo que siempre fue.
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
    de consultar_temas y no los toca esta regla.

    EL HUECO QUE QUEDA ABIERTO, y esta declarado con test en
    `tests/test_bot_sin_modelo.py`: esta regla pide DOS cosas en la misma
    oracion, el beneficio y la gestion, o sea que caza el descuento OFRECIDO
    -"puedo consultar que descuento aplicarte"- y deja pasar el AFIRMADO -"te
    hago un 25% de descuento por ser vos"-, que es la mentira mas cara de las
    dos porque no deja lugar a duda.

    Y ESTA ESCRITO ACA POR QUE NO SE TAPA CON OTRA REGLA DE PROSA. El 17-ago se
    intento: se le agrego una segunda mitad que podaba toda oracion con un
    porcentaje de descuento que ninguna herramienta hubiera traido. Duro veinte
    minutos. El renglon REAL del pago dividido -"transferencia (30%): $67.500 -
    10% descuento = $60.750"- se parte en oraciones por los puntos de los miles,
    y el pedazo que le tocaba a la regla no tenia la palabra "transferencia"
    adentro, asi que la exencion no lo salvo: le corto el medio y dejo "$67.750".
    O sea que un candado contra la alucinacion INVENTO UN PRECIO, que es
    exactamente lo que el sistema entero existe para que no pase, y lo cazo el
    invariante de que las partes tienen que sumar el total.

    La leccion, que es la del plan de recorte entero: esto se cierra en la
    ATADURA, contrastando la afirmacion contra la fuente, no sumando la regla
    numero dieciocho sobre el texto ya escrito."""
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
    # LA DOBLE NEGACION, y es la SEXTA redaccion del mismo defecto. Medida en
    # vivo el 8-ago: "no tenemos productos QUE NO SEAN fabricados en China".
    # Dice exactamente lo mismo que "todos son chinos" y las cinco formas que
    # el patron ya cubria no la veian, asi que el muro salio al cliente entero.
    # Es falso -hay 86 de 880 que cumplen- y le cierra la puerta a alguien que
    # esta comprando.
    #
    # No se persigue la redaccion nueva: se agrega la FORMA. "No + verbo de
    # tener + ... + que no" es una afirmacion universal escrita al reves, y
    # cualquier redaccion futura de esa idea cae adentro. Las otras dos
    # condiciones de la guardia no se tocan, asi que sigue haciendo falta que
    # la frase hable del catalogo entero y NO nombre un rubro que trajimos.
    # LA OCTAVA, leida de la charla REAL de Martin por WhatsApp el 9-ago:
    # "no trabajamos productos SIN componentes de origen chino". La forma ya
    # estaba -negacion mas carencia- pero escrita solo con "que no", y esta la
    # dice con "sin". Son la misma oracion: "sin X" es "que no tienen X". Se
    # suma la preposicion a la MISMA rama, no una regla nueva.
    r"no\s+(?:tengo|tenemos|hay|manejo|manejamos|trabajo|trabajamos|"
    r"vendo|vendemos|cuento|contamos)\b[^.!?\n]*\b(?:que\s+no|sin)\b|"
    r"(?:todo|nada)\s+(?:el|mi)\s+cat[aá]logo|la\s+totalidad",
    re.IGNORECASE)

# EL MURO SIN SUSTANTIVO, que la condicion del catalogo no puede ver. "No puedo
# cumplir con esa restriccion" no nombra productos ni catalogo, asi que
# `_RE_TODO_EL_CATALOGO` no matchea y la frase pasaba. `objetivo.py` ya la
# cuenta como falla de comunicacion en NO_PUEDE_DECIR -"el muro: mata la venta
# y ademas es mentira"-, y lo era: se dice justo cuando el codigo YA calculo en
# que rubros si se cumple. Se juzga sola, sin pedir el sustantivo global, pero
# con el mismo hecho atras: solo cae si `donde_si_se_cumple` trajo algo.
_RE_MURO = re.compile(
    r"no\s+(?:puedo|podemos|logro|logramos|llego|llegamos)\s+"
    r"(?:a\s+)?(?:cumplir|satisfacer|ofrecerte|darte|conseguirte|"
    r"cubrir|garantizar)", re.IGNORECASE)
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
    # LA BUSQUEDA QUE NO SE PUDO HACER. Ver el comentario de abajo: es la otra
    # puerta por la que esta guardia tiene que actuar.
    busqueda_fallida = False
    for l in (llamadas or []):
        r = l.get("resultado") or {}
        for d in (r.get("donde_si_se_cumple") or []):
            if d not in cumplen:
                cumplen.append(d)
        for p in (r.get("productos") or []):
            if isinstance(p, dict) and p.get("categoria"):
                categorias.add(H._norm(p["categoria"]))
        if (l.get("herramienta") in ("buscar_productos", "consultar_catalogo")
                and str(r.get("estado") or "") in
                ("no_encontrado", "no_se_pudo", "error")):
            busqueda_fallida = True
    # LA GUARDIA SE APAGABA JUSTO CUANDO MAS FALTA HACIA (11-ago-2026).
    #
    # EL CASO REAL. Martin pidio "productos que no sean fabricados en china".
    # `buscar_productos` volvio `no_encontrado` -el pedido no traia rubro, y el
    # log lo dijo: `hueco_de_fuente sin_rubro`-, asi que NINGUNA herramienta
    # trajo `donde_si_se_cumple`, la guardia salio por este return y al cliente
    # le llego: **"hoy no tengo ningun producto en stock que no sea de origen
    # chino"**. Una afirmacion sobre los 880 productos, dicha sin haber mirado
    # uno solo.
    #
    # La guardia pedia evidencia para poder podar, y sin evidencia se rendia.
    # Pero el caso "no buscamos nada" es al REVES: sin haber mirado el
    # catalogo, un universal sobre el catalogo no puede salir por definicion.
    # No hace falta saber cual es la respuesta correcta para saber que esa esta
    # mal, que es la misma idea de los invariantes.
    if not cumplen and not busqueda_fallida:
        return texto
    fuera = []
    for m in _RE_ORACIONES.finditer(texto or ""):
        frase = m.group(0)
        # El muro sin sustantivo entra por su propia puerta: no puede pedirsele
        # que nombre el catalogo, justamente porque no lo nombra.
        if not _RE_MURO.search(frase):
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
              se_cumple_en=cumplen[:4], frases=[f[:80] for f in fuera[:3]],
              motivo=("sin_buscar" if not cumplen else "contra_la_fuente"))
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
    r"|-\s*(?:mercado pago|transferencia)\s*\("
    # Los extras que escribe `_label_extra`: seña, descuento, recargo y cuotas.
    # FALTABAN, y costo plata (12-ago, barrido del codigo): sin la seña acá, el
    # renglon "Sena 20%: $1.700 (pago parcial)" contaba como PROSA y partia el
    # bloque de la cuenta en dos, asi que la regla 5 tomaba el "Total: $8.500"
    # de abajo por un bloque repetido y lo borraba. Al cliente le llegaba un
    # presupuesto SIN total. Son renglones de plata escritos por el codigo,
    # como el subtotal: se piden con el importe adelante para no confundirlos
    # con una frase que empiece igual.
    r"|(?:se[ñn]a|descuento|recargo)[^:\n]{0,12}:\s*[-+]?\s*\$"
    r"|cuotas[^:\n]{0,20}:\s*hasta\s+\d)")
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
    limpio = re.sub(r"\n{3,}", "\n\n", "\n".join(
        l for i, l in enumerate(lineas) if i not in fuera)).strip()
    # LA VALVULA, y la encontro el barrido del cableado el 12-ago: cuando el
    # anuncio es TODO el mensaje —"Te paso el presupuesto por los dos
    # productos:" y nada mas, que es justo lo que pasa cuando la cuenta se
    # podo—, esta poda devolvia vacio y el turno salia con el texto de
    # respaldo. Es la misma leccion del 24-jul escrita en `mensaje.py`: un
    # turno mudo es peor que un turno feo. Si podar se lleva todo, no se poda.
    if not limpio:
        log.warning("hub_venta_anuncio_vacio_descartado", trace_id=trace_id)
        return texto
    log.warning("hub_venta_anuncio_vacio", trace_id=trace_id, lineas=len(fuera))
    return limpio


# Un renglon de TABLA markdown: empieza y termina en pipe. El separador es el
# de guiones y dos puntos que va debajo del encabezado.
_RE_FILA_TABLA = re.compile(r"(?m)^\s*\|.*\|\s*$")
_RE_SEPARADOR_TABLA = re.compile(r"^[\s|:-]+$")


def _sin_markdown(texto: str) -> str:
    """WhatsApp no renderiza markdown: los asteriscos dobles salen como
    asteriscos. El prompt lo pide y el modelo igual los pone.

    Y LAS TABLAS TAMBIEN, que es lo que se colaba (charla real del 15-ago). Al
    cliente le llego una tabla de cuatro columnas -Producto, Cantidad, Destino,
    Precio- con sus pipes y su renglon de guiones, o sea catorce caracteres de
    puntuacion por fila que en el telefono se leen como basura. Esta guarda
    intervino en ese turno y no la vio: miraba asteriscos y almohadillas nada
    mas.

    Cada fila se pasa a renglon de texto con sus celdas separadas por " - ", y
    el separador de guiones se va entero porque no dice nada. No se pierde
    ningun dato: las celdas se conservan todas, en el mismo orden."""
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", texto or "")
    t = re.sub(r"(?m)^\s*#{1,6}\s*", "", t)
    if not _RE_FILA_TABLA.search(t):
        return t

    def _fila(m):
        crudo = m.group(0).strip().strip("|")
        if _RE_SEPARADOR_TABLA.match(crudo):
            return "\x00"          # marca para borrar el renglon entero
        celdas = [c.strip() for c in crudo.split("|")]
        return " - ".join(c for c in celdas if c)

    t = _RE_FILA_TABLA.sub(_fila, t)
    t = "\n".join(l for l in t.splitlines() if l.strip() != "\x00")
    return re.sub(r"\n{3,}", "\n\n", t)


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


def _cuenta_de_otro_pedido(previo: str, declarado: dict,
                           carrito: list | None = None) -> bool:
    """True si la cuenta guardada NO es la del pedido vigente.

    DOS CONTROLES, y el primero es el que faltaba:

    1. CONTRA EL CARRITO, renglon por renglon. Si la cuenta guardada cotiza un
       producto que ya no esta en el pedido, es de otro pedido y punto.

       LA FALLA, de la charla real del 12-ago a las 18:07, y es plata: el
       cliente dijo "anula el teclado" y el sistema lo entendio -el carrito lo
       podo, el log lo dice-. Dos turnos despues el modelo re-tipeo de memoria
       la cuenta del turno 1, con el teclado adentro y el reparto de pago al
       reves de lo que el cliente acababa de pedir, y esta guardia la dejo
       pasar porque salia IDENTICA a la guardada. El control de rubros no lo
       veia: auriculares, mouse y memorias seguian estando. El teclado es un
       item de mas, no un rubro distinto.

       Sacar la cuenta no deja al cliente sin numeros: el contrato NO_OMITE
       corre despues y arma la cuenta buena con el carrito vigente.

    2. CONTRA LOS RUBROS DECLARADOS, que es el control que ya existia: si ni
       uno solo de los rubros que el cliente acaba de pedir se reconoce en esa
       cuenta, tampoco es la suya.

    LA FALLA, del turno 6 de `80_charla_real_12ago`. El cliente venia de un
    presupuesto de tres microfonos y en este turno pide OTRA cosa: dos
    auriculares, dos mouse y dos memorias a tres destinos. El turno no pudo
    armar la cuenta -el modelo mando un id que no existe y la calculadora lo
    rechazo, que es lo correcto-, el modelo re-tipeo de memoria la cuenta de
    los microfonos, y como salia identica a la anterior la guardia la dio por
    respaldada y la dejo pasar. Encima el componedor la resumio en 'Sin cambios
    en la cuenta. Total final: $260.820'. O sea: al pedido nuevo se le contesto
    con el total del pedido viejo, presentado como si fuera el de ahora.

    La exencion de la guardia es correcta cuando el cliente reconfirma LO MISMO
    -'dale, confirmalo'- y falsa cuando el pedido cambio. Se decide con el
    carrito y con lo que el modelo declaro, que ya viajan en cada turno, no con
    una adivinanza."""
    if not (previo or "").strip():
        return False
    # 1. UN RENGLON QUE YA NO ESTA EN EL PEDIDO. El carrito vigente es la lista
    #    de lo que el cliente quiere HOY; la cuenta guardada es una foto que
    #    puede ser de antes.
    carrito = [c for c in (carrito or []) if isinstance(c, dict) and c.get("nombre")]
    if carrito:
        en_el_pedido = " | ".join(P._norm(c["nombre"]) for c in carrito)
        for m in INV._RE_ITEM.finditer(previo):
            nombre = P._norm(m.group("nombre"))
            if nombre and nombre not in en_el_pedido:
                return True
    items = [str(i.get("que") or "").strip()
             for i in ((declarado or {}).get("items") or [])
             if isinstance(i, dict)]
    items = [q for q in items if q]
    if not items:
        return False
    en_la_cuenta = P._norm(previo)
    for q in items:
        raices = {w[:5] for w in P._norm(q).split() if len(w) >= 4}
        if raices and any(r in en_la_cuenta for r in raices):
            return False
    return True


def _cuenta_no_retipeada(texto: str, hubo_calculo: bool, previo: str,
                         trace_id: str, declarado: dict | None = None,
                         carrito: list | None = None) -> str:
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
    # LA CUENTA DE OTRO PEDIDO NO SIRVE DE RESPALDO, ni siquiera identica. Ver
    # `_cuenta_de_otro_pedido`: ahi los renglones se van y no se repone nada,
    # porque no hay ninguna cuenta buena que poner. El turno cierra sin total y
    # el indice lo marca sin contestar, que es lo honesto: mejor sin cuenta que
    # con el total de otro pedido presentado como si fuera este.
    if _cuenta_de_otro_pedido(previo, declarado or {}, carrito):
        log.warning("hub_venta_cuenta_de_otro_pedido", trace_id=trace_id,
                    renglones=len(renglones))
        return re.sub(r"\n{3,}", "\n\n", "\n".join(
            l for l in (texto or "").splitlines()
            if not _RE_ARRANQUE_CUENTA.match(l))).strip()
    previo_lineas = {l.strip() for l in (previo or "").splitlines() if l.strip()}
    if all(l.strip() in previo_lineas for l in renglones):
        return texto
    # SE VAN TODOS LOS RENGLONES, tambien los que coinciden con el previo, y el
    # bloque bueno entra ENTERO en el lugar del primero. Hasta el 14-ago el
    # renglon que coincidia se dejaba en su lugar Y ademas se pegaba el previo
    # completo abajo, que trae ese mismo renglon adentro: con el caso normal
    # -el modelo repite el encabezado "Presupuesto:" y despues inventa los
    # importes- al cliente le llegaba el titulo DOS VECES. Media cuenta del
    # modelo mas la cuenta del codigo no es una cuenta: la del codigo va sola.
    salida, repuesto = [], False
    for linea in (texto or "").splitlines():
        if not _RE_ARRANQUE_CUENTA.match(linea):
            salida.append(linea)
            continue
        if previo and not repuesto:
            salida.append(previo.strip())
            repuesto = True
    log.warning("hub_venta_cuenta_retipeada", trace_id=trace_id,
                renglones=len(renglones), repuesta=bool(previo))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(salida)).strip()


def _la_cuenta_y_la_plata(texto: str, llamadas: list, bloque: str,
                          trace_id: str, previo: str = "",
                          vistos: list | None = None,
                          declarado: dict | None = None,
                          carrito: list | None = None) -> str:
    """LA CUENTA SE RESUELVE PRIMERO, Y RECIEN DESPUES SE PODA LA PLATA.

    UN NODO Y NO DOS (14-ago-2026). `peso_de_la_cadena.py` midio que
    `cuenta_no_retipeada` y `sin_plata_inventada` intervienen sobre los MISMOS
    mensajes el 81,8% de las veces, muy por encima de cualquier otro par. No
    hacen lo mismo —una repone el bloque de la cuenta, la otra borra importes
    sin respaldo— pero corrian sueltas, en dos nodos, sin saber una de la otra.
    Eso no era una molestia teorica: costaba la respuesta.

    LA FALLA MEDIDA, con el turno reproducido. El turno no calcula, el modelo
    re-tipea la cuenta de memoria y le cambia un importe. En el orden viejo la
    plata corria PRIMERO: podaba esos renglones por no tener respaldo -bien
    podados- y cuando llegaba la cuenta ya no quedaba ningun renglon que
    reponer, asi que se iba sin hacer nada. **Al cliente le llegaba "Te
    confirmo el pedido. Presupuesto:" y NADA abajo**, teniendo el sistema la
    cuenta buena guardada del turno anterior. El titulo sobrevivia porque abajo
    quedaba una frase suelta, asi que ni la limpieza de titulos huerfanos lo
    veia.

    EL ORDEN CORRECTO SALE SOLO DE MIRARLO: primero se pone la cuenta que armo
    el CODIGO, y despues se juzga la plata sobre el texto ya corregido. Asi la
    poda nunca puede comerse el bloque bueno, porque cuando le toca mirar, los
    importes que hay son los de la cuenta sellada y estan respaldados por
    definicion. Al reves, la poda decide sobre un texto que todavia esta mal.

    Y GANA VERIFICACION, no la pierde. Como nodo unico se le cobran los CUATRO
    contratos con `repone=("previo",)`; `cuenta_no_retipeada` sola no tenia
    NO_INVENTA_PLATA, o sea que la mitad que MAS toca plata era la menos
    controlada. Las dos mitades siguen siendo dos funciones con sus pruebas
    propias: lo que se fusiona es el paso del turno, para que no se las pueda
    volver a separar ni reordenar sin darse cuenta.
    """
    texto = _cuenta_no_retipeada(texto, hubo_calculo=bool(bloque),
                                 previo=previo, trace_id=trace_id,
                                 declarado=declarado, carrito=carrito)
    return _sin_plata_inventada(texto, llamadas, bloque, trace_id,
                                previo=previo, vistos=vistos)


def _buscar_certificando(args: dict, tienda_id: str):
    """La busqueda que hace EL CODIGO, con sus ids certificados.

    EL AGUJERO QUE CIERRA (FICHA 04, 21-ago-2026), y es la mitad que faltaba de
    un arreglo que ya se habia hecho. `_ejecutar_en_paralelo` certifica lo que
    devuelven las herramientas que pidio EL MODELO, y su comentario nombra el
    turno 6 de `80_charla_real_12ago` como el caso que lo motivo. Pero las
    reposiciones buscan por su cuenta —el modelo declaro un rubro y no lo
    busco, asi que lo busca el codigo— y esos resultados no pasaban por ahi.

    CONSECUENCIA MEDIDA, en ese mismo turno 6: el carrito tiene microfonos, el
    cliente pide auriculares, mouse y memorias, el CODIGO los busca y los
    encuentra, el mensaje se los MUESTRA con nombre y precio... y despues
    `calculate_total` rechaza los tres ids por "no certificados" y el turno
    cierra sin un solo total. El log lo decia con todas las letras:
    `id_no_certificado sueltos=['AUR0019', 'MOU0023', 'RAM0001']`.

    NO AFLOJA LA REGLA CERO, y conviene decir por que. La regla es que la
    IDENTIDAD la decide el codigo y nunca el modelo. Estos ids salen del
    catalogo, por la misma herramienta, en el mismo turno, y los pidio el
    codigo: son MAS certificados que los del modelo, no menos. Lo que la regla
    frena es el id inferido de memoria, y eso sigue frenado igual.

    Se certifica en el hilo del turno, sincronico, que es donde vive la
    contextvar: la misma trampa que ya tenia anotada `_ejecutar_en_paralelo`."""
    r = H.ejecutar("buscar_productos", args, tienda_id)
    try:
        from app.core.estado_venta import certificar_ids_de_resultado
        certificar_ids_de_resultado(r)
    except Exception:  # noqa: BLE001 — certificar no puede tumbar un turno
        pass
    return r


# Tope de busquedas que el codigo deriva de UNA declaracion. El modelo ya no
# elige herramienta, asi que el tope no defiende de un modelo desbocado sino de
# una declaracion enorme -veinte items, quince temas-: cada llamada derivada es
# una consulta a la fuente y un pedazo de JSON que despues viaja al redactor.
# Si se corta, se dice: cortar en silencio es peor que el problema que evita.
_MAX_DERIVADAS = 14
# Los estados con los que una busqueda vuelve SIN el producto. Se nombran todos,
# y el que manda es `no_vendemos`: es el que sale cuando lo que pidio el cliente
# no es de ningun rubro de la casa.
_NO_LO_TENEMOS = ("no_vendemos", "no_encontrado", "sin_resultados",
                  "no_se_pudo", "error")


def _id_para(que: str, llamadas: list, memoria: list, laxo: bool = True):
    """EL PRODUCTO DEL QUE HABLA EL CLIENTE, resuelto por el codigo.

    EL ORDEN ES MEMORIA PRIMERO, y es la trampa 5 de la FICHA 06 escrita como
    codigo. Un turno puede necesitar un producto que el cliente NO describio:
    "y ese cuanto pesa", "el otro sirve para la ps5". Eso no lo resuelve la
    declaracion, lo resuelve el estado. Si al derivar se pierde el anclaje a lo
    ya mostrado, la memoria larga se rompe, y la memoria es la prioridad 3 del
    objetivo.

    DOS PREDICADOS Y NO UNO, y es la misma leccion que ya tenia anotada
    `_producto_para`. `_cubierto` es LAXO a proposito -le alcanza UNA raiz- y
    con eso "Mouse Genius DX-110 Negro" pegaba en el Logitech que estaba en la
    memoria, porque los dos son un mouse: el cliente pregunta por uno y el bot
    le contesta la ficha de otro, que es alucinar con la cara de tener el dato.
    Asi que primero se busca ESTRICTO -todas las raices de lo que dijo el
    cliente en ese producto- y el laxo queda para cuando el turno ya trajo
    candidatos. `laxo=False` es "resolvelo solo si es claramente el mismo".

    Y NO CERTIFICA NADA NUEVO: elige entre productos que YA salieron de la
    fuente -el carrito, lo mostrado, lo que trajo este mismo turno-. La regla
    cero sigue entera: el id no lo dice el modelo, lo dice el codigo."""
    vistos = list(memoria or [])
    for l in (llamadas or []):
        r = l.get("resultado") or {}
        vistos = list(r.get("productos") or []) + (
            [r["producto"]] if isinstance(r.get("producto"), dict) else []) + vistos
    if not vistos:
        return ""
    raices = P._stems(que)
    if not raices:
        # "ese", "el otro": no hay ninguna raiz con que buscar, asi que lo que
        # el cliente nombro es el ULTIMO producto que vio. Elegir cualquier
        # otro seria inventar; no elegir nada deja la pregunta sin contestar.
        return str(vistos[0].get("id") or "")

    def _texto(prod):
        return H._norm(prod.get("categoria")) + " " + H._norm(prod.get("nombre"))

    exacto = next((p for p in vistos
                   if all(r in _texto(p) for r in raices)), None)
    if exacto or not laxo:
        return str((exacto or {}).get("id") or "")
    prod = _producto_para(que, vistos, set())
    return str((prod or {}).get("id") or "")


def _derivar_las_busquedas(llamadas: list, declarado: dict, memoria: list,
                           tienda_id: str, trace_id: str) -> list:
    """LA PUERTA UNICA (FICHA 06, 23-ago-2026). El modelo DECLARA; el codigo
    deriva de esa declaracion todo lo que hay que ir a buscar.

    POR QUE. Hasta hoy el modelo veia nueve herramientas y ELEGIA, y en el 57%
    de los turnos declaraba una cosa y buscaba otra. Toda la maquinaria del
    reconciliador y de las reposiciones existe para tapar esa distancia. Si las
    busquedas se derivan de la declaracion, la distancia no puede existir: el
    reconciliador queda en CERO faltantes POR CONSTRUCCION, y ese —no los
    tests— es el chequeo de aceptacion de esta unidad.

    POR QUE CORRE ANTES DEL RECONCILIADOR y no en la etapa de reposicion. Una
    reposicion arregla lo que el reconciliador ya reclamo; esto hace que no haya
    nada que reclamar. Puesto despues, el reconciliador veria una declaracion
    sin ninguna busqueda al lado y reclamaria los items enteros, todos los
    turnos: el numero de aceptacion diria 100% de faltantes con el sistema
    andando perfecto.

    NO ES EL CODIGO ELIGIENDO POR EL CLIENTE. Busca lo que el modelo MISMO
    declaro que el cliente pidio, con las palabras del cliente. Traer un dato no
    es elegir por nadie.
    """
    if not declarado:
        return llamadas
    from app.core import filtros_catalogo as FC
    from app.core.guia_pedido import categorias_nombradas

    fuera = list(llamadas)
    hechas: list = []
    cortadas: list = []

    def _agregar(nombre: str, args: dict):
        """Corre una herramienta interna, UNA sola vez por argumento. Devuelve
        el resultado, sea el nuevo o el que ya estaba: quien decide en base al
        estado -si la busqueda no encontro nada- tiene que ver lo mismo la
        segunda vez que pasa por aca."""
        for l in fuera:
            if l.get("herramienta") == nombre and (l.get("pedido") or {}) == args:
                return l.get("resultado") or {}
        if len(hechas) >= _MAX_DERIVADAS:
            cortadas.append(nombre)
            return {}
        if nombre == "buscar_productos":
            r = _buscar_certificando(args, tienda_id)
        else:
            r = H.ejecutar(nombre, args, tienda_id)
            try:
                from app.core.estado_venta import certificar_ids_de_resultado
                certificar_ids_de_resultado(r)
            except Exception:  # noqa: BLE001 — certificar no tumba un turno
                pass
        fuera.append({"herramienta": nombre, "pedido": args, "resultado": r})
        hechas.append((nombre, (r or {}).get("estado")))
        return r

    # ── 1. LAS CONDICIONES, resueltas una vez para todas las busquedas ──
    # `resolver_exclusion` no interpreta la frase: mira en que campo del
    # catalogo esa palabra aparece como VALOR, que es un hecho.
    # `resolver_orden` es su gemela para el extremo -"el mas barato"-, que
    # hasta hoy viajaba en `buscar_productos.ordenar_por` y lo elegia el modelo.
    # TRES PUERTAS Y UNA SOLA POR CONDICION, en este orden. El EXTREMO primero
    # -"el mas barato" es un orden, no un filtro, y filtrar por "barato" no
    # existe-; despues la EXCLUSION, que sabe dar vuelta la negacion; y al final
    # la INCLUSION, que se lleva lo que queda. Ninguna interpreta la frase: las
    # dos de filtro miran en que campo del catalogo esa palabra aparece como
    # VALOR, que es un hecho, y la del orden sale del nombre del campo.
    filtros: list = []
    sueltas: list = []
    orden = None
    for r in (declarado.get("restricciones") or []):
        r = str(r)
        extremo = FC.resolver_orden(r, tienda_id)
        if extremo:
            orden = orden or extremo
            continue
        cond = (FC.resolver_exclusion(r, tienda_id)
                or FC.resolver_inclusion(r, tienda_id))
        if cond:
            if cond not in filtros:
                filtros.append(cond)
            continue
        # LO QUE NO ENTRA EN NINGUN CAMPO VIAJA EN LA DESCRIPCION, y sin esto
        # se perdia entero. "que ande para jugar", "para trabajar": el uso no
        # es una columna del catalogo -`uso_recomendado` es prosa y ahi pega
        # cualquier palabra-, asi que no hay filtro posible. Antes de la puerta
        # unica esto no se perdia porque el modelo lo metia en la descripcion
        # de la busqueda: escribia "mouse inalambrico gamer barato". El
        # ordenador por parecido lo usa igual, que es exactamente para lo que
        # esta.
        #
        # SOLO SI NO TRAE NEGACION, y es la unica linea que importa de esta
        # regla. Meter "sin partes chinas" en el texto de relevancia sube a los
        # chinos, o sea aplica la condicion AL REVES: es peor que perderla. Una
        # negacion que no se pudo estructurar se deja afuera y el punto queda
        # abierto, que es honesto.
        if not FC.tiene_negacion(r):
            sueltas.append(r)

    def _buscar(que: str, categoria: str = ""):
        args: dict = {"descripcion": " ".join([que] + sueltas), "cuantos": 3}
        cat = categoria or next(iter(categorias_nombradas(que, tienda_id)), "")
        if cat:
            args["categoria"] = cat
        if filtros:
            args["filtros"] = list(filtros)
        # EL EXTREMO PUEDE VENIR EN EL ITEM Y NO EN LA CONDICION. "la notebook
        # mas barata que tengas" es UNA frase: el modelo la declara entera en
        # `que` y no tiene por que partirla en dos campos.
        o = orden or FC.resolver_orden(que, tienda_id)
        if o:
            args["ordenar_por"] = o["campo"]
            args["direccion"] = o["direccion"]
        return _agregar("buscar_productos", args)

    # ── 2. CADA ITEM: una busqueda con las palabras del cliente ─────────
    for it in (declarado.get("items") or []):
        que = str((it or {}).get("que") or "").strip()
        if que:
            _buscar(que, str((it or {}).get("categoria") or "").strip())

    # ── 3. STOCK: lo mismo, y si no aparece se mira el CATALOGO ENTERO ──
    # Es la obligacion que llevaba `consultar_catalogo` en su descripcion:
    # antes de decir "no tenemos nada de eso" hay que haber mirado los 880. Sin
    # este segundo paso el bot niega el stock sin haber mirado uno solo, que es
    # la peor forma de alucinar porque suena a respuesta normal.
    sin_hallar = False
    for q in (declarado.get("stock") or []):
        q = str(q or "").strip()
        if not q:
            continue
        r = _buscar(q)
        # `no_vendemos` ES EL ESTADO QUE IMPORTA, y casi se me escapa: es el que
        # devuelve la busqueda cuando lo que pidio el cliente no es de ningun
        # rubro nuestro -"celulares samsung", "una play 5"-, o sea EL caso por el
        # que existe este segundo paso. `no_encontrado` es el otro lado: el rubro
        # existe y el producto puntual no.
        if str((r or {}).get("estado") or "") in _NO_LO_TENEMOS:
            sin_hallar = True
    if sin_hallar:
        _agregar("consultar_catalogo",
                 {"operacion": "valores", "campo": "categoria"})

    # ── 4. ATRIBUTOS: la ficha del producto que el cliente nombro ───────
    # LA REGLA CERO MANDA ACA TAMBIEN. Si la busqueda vuelve `ambiguo` —varios
    # modelos se llaman parecido— el codigo NO elige uno para traer su ficha:
    # dejaria pasar como dato de la fuente el atributo de un producto que el
    # cliente no nombro. El resultado ambiguo ya viaja al redactor con sus
    # candidatos y su instruccion de repreguntar, que es lo que corresponde.
    ambiguos: list = []

    def _resolver(que: str) -> str:
        pid = _id_para(que, fuera, memoria, laxo=False)
        if pid:
            return pid
        r = _buscar(que)
        if str((r or {}).get("estado") or "") == "ambiguo":
            ambiguos.append(que)
            return ""
        return _id_para(que, fuera, memoria)

    for a in (declarado.get("atributos") or []):
        de = str((a or {}).get("de") or "").strip()
        if not de:
            continue
        pid = _resolver(de)
        if pid:
            _agregar("ficha_producto", {"product_id": pid})

    # ── 5. COMPATIBILIDAD: los dos lados, certificados ─────────────────
    for c in (declarado.get("compatibilidad") or []):
        que = str((c or {}).get("que") or "").strip()
        para = str((c or {}).get("para") or "").strip()
        if not que:
            continue
        pid = _resolver(que)
        if not pid:
            continue
        args = {"product_id": pid}
        # EL OTRO LADO SOLO SI YA ES UN PRODUCTO CONOCIDO. "mi notebook" puede
        # ser una que le mostramos, y ahi el cruce ficha contra ficha es mucho
        # mas preciso; "jugar" no es un producto y no resuelve a ninguno. No se
        # sale a buscarlo: buscar "jugar" traeria cualquier cosa y el cruce
        # saldria contra un producto que el cliente nunca nombro.
        otro = _id_para(para, fuera, memoria) if para else ""
        if otro and otro != pid:
            args["contra_product_id"] = otro
        elif para:
            args["equipo"] = para
        _agregar("ver_compatibilidad", args)

    # ── 6. TEMAS: lo que el modelo nombro libre, CERTIFICADO ────────────
    cert = H.certificar_temas(declarado.get("temas") or [], tienda_id)
    if cert["temas"]:
        _agregar("consultar_temas", {"temas": cert["temas"]})
    if declarado.get("temas"):
        # EL TEMA CERTIFICADO VUELVE A LA DECLARACION, y sin esto la cobertura
        # se rompia en silencio. `indice_turno` abre un punto de politica por
        # cada tema declarado y despues busca su evidencia comparando ese nombre
        # contra el `tema` que devolvio `consultar_temas`. Si el punto se abre
        # con "envio al exterior" y la herramienta contesta `envio_exterior`,
        # los dos nombran lo mismo y no se encuentran nunca: el punto sale sin
        # contestar aunque este contestado. Es la misma clase de defecto que el
        # anclaje por identidad vino a arreglar el 12-ago.
        #
        # EL QUE NO RESOLVIO SE QUEDA CON LAS PALABRAS DEL CLIENTE, a proposito.
        # Sacarlo cerraria el punto y la pregunta desapareceria del indice: el
        # cliente pregunto algo, nadie lo contesto, y el numero de omision no lo
        # veria. Se queda abierto, sale como punto sin contestar, y el redactor
        # recibe la obligacion de decirlo honesto.
        declarado["temas"] = cert["temas"] + cert["sin_resolver"]

    # ── 7. DESTINOS: un envio cotizado por cada localidad nombrada ──────
    for d in (declarado.get("destinos") or []):
        d = str(d or "").strip()
        if d:
            _agregar("cotizar_envio", {"localidad": d})

    if cortadas:
        log.warning("busquedas_derivadas_recortadas", trace_id=trace_id,
                    tope=_MAX_DERIVADAS, descartadas=cortadas[:6])
    log.info("busquedas_derivadas", trace_id=trace_id, hechas=hechas,
             filtros=[f.get("campo") for f in filtros], sueltas=sueltas[:3],
             orden=(orden or {}).get("campo"),
             sin_identificar=ambiguos[:3],
             temas_sin_resolver=cert["sin_resolver"][:3],
             temas_ambiguos=[a[0] for a in cert["ambiguos"]][:3])
    return fuera


def _busqueda_de_lo_declarado(llamadas: list, declarado: dict, rec: dict,
                              tienda_id: str, trace_id: str) -> list:
    """EL RUBRO QUE EL MODELO DECLARO Y NUNCA BUSCO, lo busca el CODIGO.

    LA FALLA, medida el 9-ago con `objetivo.py --vivo`. La redaccion coloquial
    de la pregunta de Martin daba 6 sobre 100 -y 8 el dia anterior-, siempre el
    mismo numero, mientras las otras cuatro daban 84, 88 y 92. El log de las
    tres corridas, identico:

        ronda 1 -> ['registrar_pedido', 'consultar_temas']
        reconciliador faltan: "El cliente pidio 'auriculares' y no lo
        buscaste. Buscalo." + mouse + memorias ram
        ronda 2 -> []

    El modelo DECLARA bien los tres rubros -entiende perfecto, ya estaba
    medido en 100 sobre 15 de 15- y despues no busca ninguno. El reconciliador
    lo caza, se lo pide, y en la ronda dos el modelo pide CERO herramientas. Sin
    productos no hay cuenta, no hay precio y no hay respuesta: el cliente recibe
    un mensaje de 717 caracteres que no cotiza nada.

    ES EL MISMO HECHO QUE YA ESTABA ESCRITO DOS VECES EN ESTE ARCHIVO: ante una
    correccion del reconciliador el modelo pide CERO herramientas 3 de 3 veces
    -medido el 5-ago para la condicion sin aplicar, y otra vez para el rubro que
    la cuenta perdia-. Las dos veces la salida fue la misma y funciono: que lo
    haga el codigo. Esta es la tercera cara de esa misma moneda, y la mas cara,
    porque las otras dos rompian una parte del turno y esta lo rompe entero.

    NO ES EL CODIGO DECIDIENDO POR EL CLIENTE. Busca lo que el modelo MISMO
    declaro que el cliente pidio, con las palabras del cliente, y le suma la
    exclusion que el cliente puso, resuelta por `resolver_exclusion`, que no
    interpreta la frase: mira en que campo del catalogo esa palabra aparece como
    valor, que es un hecho. Traer un dato no es elegir por nadie; lo que no se
    hace es cotizar solo, y por eso esto corre ANTES de las reposiciones que ya
    estaban: primero existe el producto, y recien despues la cuenta se arma con
    lo declarado, con sus reglas de siempre.

    Y CUESTA CERO TOKENS: es la misma herramienta con los argumentos que el
    reconciliador ya tenia tipados. La ronda vacia que hoy se quema esperando
    que el modelo obedezca, se ahorra.
    """
    faltan = [q for q in (rec or {}).get("sin_buscar") or [] if str(q).strip()]
    if not faltan:
        return llamadas
    from app.core import filtros_catalogo as FC
    from app.core.guia_pedido import categorias_nombradas

    # La exclusion que el cliente puso, una sola vez para todos los rubros.
    filtros: list = []
    for r in (declarado or {}).get("restricciones") or []:
        cond = FC.resolver_exclusion(str(r), tienda_id)
        if cond and cond not in filtros:
            filtros.append(cond)

    fuera = list(llamadas)
    hechas = []
    for que in faltan:
        # LA CATEGORIA VA SI Y SOLO SI ES UNA DE LA TIENDA, y la resuelve
        # `categorias_nombradas` contra la fuente viva. Con la descripcion sola
        # -"auriculares", "memorias ram"- la busqueda vuelve `no_encontrado`:
        # esta pensada para lo que el cliente describe, no para un rubro pelado.
        # El test lo cazo antes de que llegara a produccion.
        args = {"descripcion": que, "cuantos": 3}
        cats = categorias_nombradas(que, tienda_id)
        if cats:
            args["categoria"] = cats[0]
        if filtros:
            args["filtros"] = list(filtros)
        # LA MISMA BUSQUEDA NO SE AGREGA DOS VECES, y no es una optimizacion:
        # lo encontro el barrido de la decision con el contrato de
        # idempotencia. El turno puede pasar por aca en dos rondas seguidas con
        # el MISMO reclamo -que el reconciliador repita un faltante es un
        # defecto conocido y abierto-, y sin esta guarda la segunda vuelta
        # agregaba una llamada calcada: el redactor veia el mismo producto dos
        # veces y lo escribia dos veces. El defecto no se ve aca, se ve en el
        # mensaje del cliente, que es donde nadie lo iba a atribuir a esto.
        if any(l.get("herramienta") == "buscar_productos"
               and (l.get("pedido") or {}) == args for l in fuera):
            continue
        r = _buscar_certificando(args, tienda_id)
        fuera.append({"herramienta": "buscar_productos", "pedido": args,
                      "resultado": r})
        hechas.append((que, (r or {}).get("estado")))
    log.info("busqueda_de_lo_declarado", trace_id=trace_id, hechas=hechas,
             filtros=[f.get("campo") for f in filtros])
    return fuera


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
    r = _buscar_certificando(args, tienda_id)
    log.info("condicion_faltante_aplicada", trace_id=trace_id,
             condiciones=sumadas, estado=(r or {}).get("estado"))
    fuera = list(llamadas)
    fuera[idx] = {"herramienta": "buscar_productos", "pedido": args,
                  "resultado": r}
    return fuera


def _producto_para(que: str, vistos: list, del_carrito: set):
    """EL PRODUCTO QUE UNA CATEGORIA YA TENIA RESUELTO NO SE VUELVE A ELEGIR.

    LA FALLA, y estaba abierta en PENDIENTE con dos sintomas que parecian
    distintos y son el mismo: "los auriculares pasaron de Negro a Blanco sin
    que el cliente lo pidiera" y "2 mouse salio Genius y Logitech juntos".
    Casetes `80` turno 7 y `81` turno 2.

    LA CAUSA, reproducida antes de tocar nada. La reposicion elegia el PRIMER
    producto de `vistos` que cubriera el rubro, y `vistos` trae primero lo que
    buscO ESTE turno y despues lo que ya estaba en el carrito. Entonces, con un
    mouse Negro ya cotizado, si el turno vuelve a buscar "mouse" y la busqueda
    devuelve el Blanco primero, la cuenta sale con el Blanco. El cliente no
    pidio cambiar nada: pidio agregar un teclado.

    LA REGLA QUE LO ARREGLA, y es una sola: si el producto que YA estaba en el
    carrito sigue satisfaciendo lo que el cliente nombro, gana el del carrito.
    Si no lo satisface -el carrito tiene el Negro y el cliente ahora dice
    "mouse blanco"- entonces el cliente SI esta pidiendo otro, y gana la
    busqueda del turno.

    DOS PREDICADOS Y NO UNO, y esto lo encontre probando el otro lado antes de
    darlo por bueno. `_cubierto` es LAXO a proposito -le alcanza UNA raiz- y
    esta bien que lo sea, porque su trabajo es decir si el item fue atendido y
    ahi conviene no acusar faltantes falsos. Pero para decidir si el del
    carrito sigue siendo el que el cliente nombro, esa laxitud lo rompe: con el
    Negro en el carrito, "mouse blanco" tambien daba cubierto por la raiz
    "mouse" y el cliente no podia cambiar de color nunca mas. Un arreglo que
    congela el carrito es peor que el defecto.

    Asi que el carrito gana solo con el predicado ESTRICTO -todas las raices de
    lo que dijo el cliente tienen que estar en ese producto-, y la busqueda del
    turno sigue eligiendo con el laxo de siempre. Si el carrito no tiene nada
    de ese rubro, el comportamiento es identico al de antes, linea por linea.
    """
    def _texto(p):
        return H._norm(p.get("categoria")) + " " + H._norm(p.get("nombre"))

    raices = P._stems(que)

    def _es_el_mismo(p):
        """Estricto: todo lo que el cliente nombro esta en este producto."""
        return bool(raices) and all(s in _texto(p) for s in raices)

    return (next((p for p in vistos
                  if str(p.get("id") or "").upper() in del_carrito
                  and _es_el_mismo(p)), None)
            or next((p for p in vistos if P._cubierto(que, _texto(p))), None))


def _cuenta_con_lo_declarado(llamadas: list, declarado: dict, tienda_id: str,
                             trace_id: str, memoria: list | None = None) -> list:
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
    # LA CHARLA TAMBIEN CERTIFICA, no solo el turno. Esta funcion decia "el
    # turno -o la charla-" desde que nacio y miraba unicamente el turno, y esa
    # distancia entre la intencion y el codigo costo un caso real: el cliente
    # pide el precio de DOS unidades de la notebook que venia mirando, el turno
    # no llama a ninguna herramienta porque no hace falta -el producto ya esta
    # certificado y en el carrito-, `vistos` sale vacio y la reparacion se
    # apaga. Al cliente le llego una frase de venta sin un solo numero.
    #
    # NO AFLOJA LA REGLA CERO: lo que entra son ids que YA fueron certificados
    # cuando entraron al carrito o se mostraron, que son los mismos que
    # `calculate_total` acepta. Van DESPUES de los del turno, asi que si este
    # turno mostro algo, ese gana.
    ya = {str(p.get("id") or "").upper() for p in vistos}
    # LOS DEL CARRITO, aparte, porque son los que tienen PRIORIDAD cuando el
    # rubro ya estaba resuelto. Ver `_producto_para`.
    del_carrito = set()
    for p in (memoria or []):
        pid = str((p or {}).get("id") or "").upper()
        if not pid or not p.get("nombre"):
            continue
        del_carrito.add(pid)
        if pid not in ya:
            ya.add(pid)
            vistos.append({"id": pid, "nombre": p["nombre"],
                           "categoria": str(p.get("categoria") or "")})
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
            cand = _producto_para(que, vistos, del_carrito)
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
        # EL REPARTO DE PAGO VIAJA CON LA CUENTA, y sin esto se perdia justo en
        # el turno donde mas importa. Charla real del 12-ago, 18:05: el cliente
        # dice "anula el teclado, y va 70 mercado pago", la llamada del modelo
        # se cae por un id no certificado, esta reposicion rehace la cuenta
        # SIN pago, y el mensaje sale con el total y sin una palabra del
        # reparto que el cliente acababa de cambiar. El dato estaba declarado
        # en el mismo turno; lo unico que faltaba era pasarlo.
        pago = [{"medio": p.get("medio") or "", "porcentaje": p.get("porcentaje")}
                for p in (declarado.get("reparto_pago") or [])
                if isinstance(p, dict) and p.get("porcentaje")]
        if pago:
            args["pago"] = pago
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

    # ── UN RUBRO PEDIDO UNA VEZ, UN SOLO PRODUCTO ──────────────────────────
    #
    # EL DEFECTO, de la charla real: el cliente pide "2 mouse" y la cuenta sale
    # con un Genius y un Logitech. **El cliente no pidio dos modelos distintos:
    # la variedad la invento el sistema, y se la cobra.** Es mandarle algo que
    # no pidio en la parte que se paga, o sea la prioridad uno.
    #
    # POR QUE SE UNIFICA Y NO SE PREGUNTA. Preguntar seria lo correcto si la
    # ambiguedad fuera del cliente, y no lo es: el cliente nombro un rubro, una
    # vez, con una cantidad. El que se contradijo fue el sistema. Preguntar
    # quema un turno y no vende.
    #
    # LAS TRES ATADURAS QUE LO HACEN SEGURO:
    #   1. Solo cuando el cliente nombro ese rubro UNA sola vez. Si declaro dos
    #      items del mismo rubro, esta pidiendo dos cosas distintas y no se
    #      toca.
    #   2. Se unifica DENTRO de cada destino. El mismo producto a dos ciudades
    #      repite con razon, y juntarlos romperia el reparto de envios.
    #   3. El producto que queda lo elige `_producto_para`, o sea el mismo que
    #      ya venia resuelto en el carrito si sigue sirviendo. No se elige uno
    #      nuevo: se vuelve al que el cliente ya tenia.
    #
    # Y LA PLATA NO SE REESCRIBE: se cambia el ITEM y la cuenta la vuelve a
    # calcular `armar_presupuesto` unas lineas mas abajo, con los precios de la
    # fuente. El codigo nunca estampa un total que no calculo la calculadora.
    for it in (declarado.get("items") or []):
        que = H._norm(it.get("que"))
        if not que:
            continue
        if sum(1 for x in (declarado.get("items") or [])
               if H._norm(x.get("que")) == que) != 1:
            continue
        elegido = _producto_para(que, vistos, del_carrito)
        if not elegido:
            continue
        # SE AGRUPA POR CATEGORIA, NO POR `_cubierto`. Lo encontro el barrido de
        # la decision con el contrato de idempotencia, y era grave: `_cubierto`
        # es LAXO -le alcanza una raiz- asi que dos rubros DISTINTOS caian en el
        # mismo grupo y se unificaban en uno. O sea que el arreglo contra
        # cobrarle al cliente algo que no pidio se comia mercaderia que SI habia
        # pedido, que es peor. La categoria es un dato de la ficha, no una
        # coincidencia de palabras.
        cat = H._norm(elegido.get("categoria"))
        mismos = [i for i in items
                  if cat and H._norm(por_id.get(str(i.get("product_id")), {})
                                     .get("categoria")) == cat]
        if len({str(i.get("product_id")) for i in mismos}) < 2:
            continue
        por_destino: dict = {}
        for i in mismos:
            d = str(i.get("destino") or "")
            por_destino.setdefault(d, []).append(i)
        for d, grupo in por_destino.items():
            if len({str(i.get("product_id")) for i in grupo}) < 2:
                continue
            total = sum(max(1, int(i.get("cantidad") or 1)) for i in grupo)
            for i in grupo[1:]:
                items.remove(i)
            grupo[0]["product_id"] = elegido["id"]
            grupo[0]["cantidad"] = total
            sumados.append(f"unificado a {total}x {elegido.get('nombre')}")
            log.info("rubro_unificado_a_un_producto", trace_id=trace_id,
                     rubro=que, destino=d or "unico",
                     quedaba=elegido["id"], era=len(grupo))

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
        cand = _producto_para(que, vistos, del_carrito)
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
    # EL CAMPO TIPADO PRIMERO, la lectura de castellano como red.
    amb = (P.reparto_declarado(declarado)
           or P.reparto_ambiguo((declarado or {}).get("restricciones")))
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
    amb = (P.reparto_declarado(declarado)
           or P.reparto_ambiguo((declarado or {}).get("restricciones")))
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
    # EL SUPUESTO, EN UNA LINEA Y PEGADO A LA POSDATA DE ARRIBA. La version
    # anterior repetia el reparto DOS veces mas -"Dijiste 70/30" y "lo arme con
    # transferencia 70%, mercado pago 30%"- cuando el bloque de Pago dividido,
    # tres renglones mas arriba, ya lo dice con los montos. Tres veces el mismo
    # numero en el mismo mensaje.
    #
    # Lo que la regla cero EXIGE que se diga sigue dicho: que el medio de cada
    # parte lo asumio el sistema, cual asumio, y que se da vuelta en una linea.
    # Y va con UN solo salto, no dos, para que quede una posdata sola en vez de
    # dos bloques seguidos pidiendo lo mismo.
    mayor = max(partes, key=lambda p: float(p.get("porcentaje") or 0))
    linea = (f"El {int(float(mayor.get('porcentaje') or 0))}% "
             f"lo puse por {mayor.get('medio')}, que es la que tiene "
             f"descuento: si va al revés, decime y lo doy vuelta.")
    # EL SUPUESTO SE DICE UNA VEZ. Lo encontro el barrido de la decision con el
    # contrato de idempotencia: si el turno pasa dos veces por aca, el cliente
    # leia la misma aclaracion dos veces adentro de la misma cuenta. Es
    # exactamente la repeticion que la prioridad dos no tolera.
    if linea in str(res.get("bloque") or ""):
        return llamadas
    res["bloque"] = res["bloque"] + "\n" + linea
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

    # ── CON LA CUENTA SOBRE LA MESA, LA VIDRIERA NO VA ──────────────────────
    #
    # ES EL RECORTE MAS GRANDE QUE QUEDABA, y Martin lo viene marcando desde el
    # 7-ago: "el bloque de hallazgo pegado ENTERO cuando ya hay cuenta". Medido
    # sobre su mensaje del 9-ago: el bloque son 640 caracteres de 1.731, MAS
    # que la cuenta, y lista productos que NO son los que se cotizan -mostraba
    # el Zeus X Blanco y cobraba el Negro, mostraba el Logitech y cobraba el
    # Genius-. O sea que los 640 no solo sobran: confunden.
    #
    # POR QUE ESTE CORTE SI Y EL DEL 9-AGO NO. Ese dia se probo borrar el grupo
    # entero y la nota cayo de 89 a 77, porque con los renglones se iba el
    # HECHO -"pais de fabricacion: china"-, que es el unico criterio que el
    # cliente puso. La leccion quedo escrita: borrar solo es seguro cuando lo
    # borrado esta demostrablemente repetido. Aca no se borra el hecho: se
    # CONSERVA, en una linea por rubro, y lo que se va son los renglones de
    # producto, que si estan repetidos -el producto que el cliente compra esta
    # en la cuenta, con su nombre y su precio, tres renglones mas abajo-.
    #
    # Y EL HECHO QUE SOBREVIVE ES EL DEL PRODUCTO COTIZADO, no el del primero
    # de la lista. Con eso se cierra de raiz la vidriera que contradecia a la
    # factura, que estaba abierta desde el 9-ago a la mañana.
    ids_cotizados, hay_cuenta = set(), False
    for l in llamadas:
        if (l.get("herramienta") == "armar_presupuesto"
                and (l.get("resultado") or {}).get("bloque")):
            hay_cuenta = True
            for it in ((l.get("pedido") or {}).get("items") or []):
                ids_cotizados.add(str(it.get("product_id") or "").upper())

    if hay_cuenta:
        cortas = []
        for i in idx:
            r = llamadas[i]["resultado"]
            cat = r.get("categoria") or (r["productos"][0].get("categoria") or "")
            prods = r.get("productos") or []
            elegida = next((f for f in prods
                            if str(f.get("id") or "").upper() in ids_cotizados),
                           prods[0] if prods else {})
            hecho = str(elegida.get("por_que") or "").strip()
            if hecho:
                cortas.append(f"{str(cat).capitalize()}: {hecho}")
        if cortas:
            fuera = list(llamadas)
            for n, i in enumerate(candidatos):
                r = dict(llamadas[i]["resultado"])
                r["bloque"] = "\n".join(cortas) if i == idx[0] else ""
                r["instruccion"] = (
                    "Pegá el bloque TAL CUAL, sin cambiar un renglón: es el "
                    "origen de cada rubro y es el criterio que el cliente puso. "
                    "NO listes productos: los que compra ya están en la cuenta "
                    "con su nombre y su precio. PROHIBIDO afirmar nada sobre el "
                    "catálogo entero." if i == idx[0] else
                    "Ya está dicho en el bloque de arriba: no lo repitas.")
                fuera[i] = {**llamadas[i], "resultado": r}
            log.info("bloques_a_uno_con_cuenta", trace_id=trace_id,
                     rubros=len(cortas), largo=len("\n".join(cortas)))
            return fuera

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


def _punto_omitido_repuesto(texto: str, declarado: dict, llamadas: list,
                            memoria: list, tienda_id: str,
                            trace_id: str) -> str:
    """EL CONTRATO NO_OMITE: un punto que el cliente pidio y que el sistema
    SABE contestar no puede salir sin contestar.

    POR QUE ES EL QUE FALTABA (Martin, 12-ago-2026). Las diecisiete guardias de
    salida son todas RESTAS: podan lo inventado, lo repetido, lo no respaldado.
    Ninguna SUMA. Por eso una omision las atraviesa a las diecisiete sin que
    nadie la vea: no hay nada mal escrito, hay algo que no esta. El mensaje que
    lo mostro es real y esta en los casetes — el cliente pregunta cuanto sale
    llevar DOS unidades de la notebook que venia mirando, y le llega una frase
    de venta entera, sin un solo numero.

    POR QUE ACA Y NO ANTES DE REDACTAR. Se probaron las dos y esta gano con el
    numero en la mano. Reponer antes obliga a adivinar si el modelo va a decir
    el precio, y adivinar de mas cuesta caro: en un turno medido, la ficha ya
    decia "Precio: $693.000" y la cuenta repuesta lo estampo dos veces mas. El
    mismo numero TRES veces, que es la repeticion que la prioridad 2 no tolera.
    Aca el texto ya existe, asi que no se adivina: se mira. Solo se repone lo
    que de verdad falta.

    LO QUE PEGA NO LO ESCRIBE NADIE: es el bloque SELLADO de la calculadora,
    con ids ya certificados —los del turno o los del carrito, que se
    certificaron cuando entraron—. No inventa un producto, no inventa un
    numero, y si no puede armar la cuenta no toca el mensaje."""
    if not declarado or not (texto or "").strip():
        return texto
    try:
        faltan = IT.cobertura(declarado, texto, trace_id + "|guardia",
                              llamadas=llamadas, memoria=memoria)["faltan"]
    except Exception as e:  # noqa: BLE001 — un control no puede tumbar el turno
        log.warning("punto_omitido_error", trace_id=trace_id, error=str(e)[:120])
        return texto
    if not any(p.get("tipo") == "precio" for p in faltan):
        return texto
    repuestas = _cuenta_con_lo_declarado(llamadas, declarado, tienda_id,
                                         trace_id, memoria=memoria)
    bloque = _bloque_presupuesto(repuestas)
    if not bloque or _norm_renglon(bloque) in _norm_renglon(texto):
        log.warning("punto_omitido_sin_reponer", trace_id=trace_id,
                    puntos=[p["texto"][:40] for p in faltan][:3])
        return texto
    log.info("punto_omitido_repuesto", trace_id=trace_id,
             puntos=[p["id"] for p in faltan][:3], largo=len(bloque))
    return (texto.rstrip() + "\n\n" + bloque).strip()


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
    # Se inicializa aca: si el turno no pide ninguna herramienta -un saludo, un
    # gracias- no se reconcilia y `rec` quedaria sin definir.
    rec: dict = {}
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

        # ── RECONCILIAR: lo declarado contra lo hecho ───────────────────
        # Acá está el control que faltaba. Los diecinueve que había miraban la
        # prosa ya escrita; este mira la DECISION, antes de escribir. Si el
        # pedido tiene una contradicción, el turno termina PREGUNTANDO y no
        # eligiendo por el cliente.
        for l in llamadas:
            if l.get("herramienta") == "registrar_pedido":
                declarado = (l.get("resultado") or {}).get("pedido") or declarado
        # La condicion que el modelo APLICO en la busqueda y no declaro entra
        # aca, antes de reconciliar: si no, queda fuera de todos los controles.
        # Con red: completar lo declarado es una MEJORA, y una mejora no puede
        # dejar sin respuesta a un cliente. Si falla, el turno sigue como antes.
        try:
            declarado = _restricciones_de_los_filtros(declarado, llamadas,
                                                      trace_id)
        except Exception as e:  # noqa: BLE001
            log.warning("restriccion_declarada_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
        # ── LA PUERTA UNICA: el codigo deriva que buscar ────────────────
        # VA ANTES DE RECONCILIAR, y ese orden es la unidad entera. El modelo
        # ya no elige herramienta: declara. Si las busquedas salen de la
        # declaracion, lo declarado y lo hecho no pueden diferir, y el
        # reconciliador queda en cero faltantes POR CONSTRUCCION. Puesto
        # despues, reclamaria la declaracion entera en cada turno.
        llamadas = G.paso_datos("busquedas_derivadas", _derivar_las_busquedas,
                                llamadas, declarado, _memoria_idx, tienda_id,
                                trace_id)
        # LA MEMORIA DEL RECONCILIADOR: lo que la charla ya resolvio. Sin
        # esto le exige buscar de nuevo algo que se certifico dos turnos atras.
        ya = " ".join([str(p.get("nombre") or "") + " " +
                       str(p.get("categoria") or "")
                       for p in (estado.get("productos_vistos") or [])] +
                      [str(c.get("nombre") or "")
                       for c in (conv.get("carrito_vigente") or [])])
        rec = P.reconciliar(declarado, llamadas, trace_id, ya_resuelto=ya,
                            tienda_id=tienda_id)
        obligacion = P.instruccion_de_preguntas(rec)
        # QUE SIGNIFICA QUE EL RECONCILIADOR INTERVINO: que RECLAMO algo. Si
        # no reclama nada, lo declarado y lo hecho coinciden y el turno sigue
        # igual que si no existiera.
        _rec_n = sum(len(rec.get(k) or [])
                     for k in ("faltantes", "preguntar", "sin_buscar"))
        G.veredicto("reconciliador", _rec_n > 0, f"reclamos:{_rec_n}")
        G.anotar("reconciliador", {
            "faltantes": len(rec.get("faltantes") or []),
            "preguntar": len(rec.get("preguntar") or []),
            "sin_buscar": len(rec.get("sin_buscar") or []),
            # LAS DOS MARCAS TIPADAS VAN AL LOG DEL TURNO (FICHA 06). Son lo
            # que la reposicion todavia tiene que hacer, no un defecto, y por
            # eso no cuentan como faltante; pero un hueco que no se ve en el
            # log lo termina pagando el cliente.
            "falta_la_cuenta": bool(rec.get("falta_la_cuenta")),
            "falta_el_reparto": bool(rec.get("falta_el_reparto"))})
        # EL FALTANTE YA NO VUELVE AL DECISOR. Lo que se puede resolver sin el
        # modelo lo resuelven las reposiciones de abajo; lo que ni asi se puede,
        # se lo dice el INDICE al redactor, que mira el MATERIAL que quedo y no
        # la intencion. Se loguea igual: es la señal de que una reposicion no
        # alcanzo, y es donde hay que mirar cuando una respuesta sale corta.
        if rec.get("faltantes"):
            log.info("hub_venta_faltantes", trace_id=trace_id,
                     faltantes=(rec.get("faltantes") or [])[:4])
    # ── 2-bis. LO QUE EL MODELO NO APLICA, LO APLICA EL CODIGO ───────────
    # EL ORDEN ES EL DE LA DEPENDENCIA: primero que el producto EXISTA -si el
    # modelo no busco nada, las tres reposiciones de abajo no tienen sobre que
    # trabajar y el turno sale mudo-, despues la condicion, y al final la
    # cuenta con lo declarado.
    llamadas = G.paso_datos("busqueda_repuesta", _busqueda_de_lo_declarado,
                            llamadas, declarado, rec, tienda_id, trace_id)
    llamadas = G.paso_datos("condicion_repuesta", _condicion_faltante_aplicada,
                            llamadas, rec, tienda_id, trace_id)
    # LA MEMORIA ENTRA SOLO SI EL TURNO NO CERTIFICO NADA (17-ago, al sacar las
    # rondas). Hasta hoy no entraba nunca, y el motivo estaba bien medido: con
    # un producto del carrito, reponer la cuenta le agregaba el bloque a turnos
    # que YA contestaban el precio en la ficha, y el mismo numero salia TRES
    # veces en un mensaje. Pero ese caso necesita que el turno haya traido una
    # ficha; cuando el turno no certifico NADA no hay con que duplicar.
    #
    # Y sin la ronda dos esa es la unica forma de que el cliente reciba un
    # numero. Medido al sacar el bucle: en el turno 2 de `78_reparto_por_destino`
    # el modelo declara tres items y tres destinos, no busca nada porque la
    # charla ya lo tenia resuelto, y el mensaje salia sin un solo peso. Antes lo
    # tapaba la vuelta extra al modelo; ahora lo resuelve el codigo con ids que
    # YA estaban certificados, que es mas barato y mas seguro que preguntar.
    _certifico_algo = any((l.get("resultado") or {}).get("productos")
                          or (l.get("resultado") or {}).get("producto")
                          for l in llamadas)
    # ── EL TOTAL PERDIDO (FICHA 04, 21-ago-2026) ────────────────────────
    #
    # EL DEFECTO, VIVO EN PRODUCCION DESDE EL 17-AGO Y TAPADO POR EL CORPUS.
    # `_certifico_algo` apagaba la memoria ENTERA cuando el turno certificaba
    # cualquier cosa, y ese todo-o-nada es demasiado grueso: en el turno 8 de
    # la charla real del 12-ago el cliente dice "agregá un teclado" al
    # presupuesto de los seis articulos, el turno certifica TECLADOS, y por
    # eso mismo se le niega el carrito donde viven los otros seis. Sin ellos
    # `_producto_para` no encuentra nada que cotizar, la cuenta no se arma, y
    # el cliente que pidio el precio recibe un mensaje sin un solo total.
    # Regrabado dos veces: fallan los MISMOS turnos 6 y 8, con el mismo motivo.
    #
    # EL RECLAMO EXISTIA Y NADIE LO ATENDIA. La regla 5 del reconciliador ya
    # dice "El cliente pidio precio y todavia no armaste la cuenta", pero esa
    # frase esta escrita para el MODELO y desde que el turno tiene dos llamadas
    # fijas no hay ronda siguiente que se la lea.
    #
    # LA CONDICION AHORA ES EL RECLAMO, NO LA CERTIFICACION, y esa distincion
    # es la que lo hace seguro. No se repone "porque hay productos" -eso seria
    # el codigo decidiendo por el cliente, y ademas alarga el mensaje-: se
    # repone cuando el reconciliador dice que el cliente PIDIO precio y la
    # cuenta no esta. `_cuenta_con_lo_declarado` ya pone los productos del
    # turno ADELANTE de los de la memoria, asi que abrirle la memoria no le
    # cambia la eleccion cuando el turno si trajo lo que hacia falta.
    #
    # NO SUBE LAS LLAMADAS AL MODELO: la cuenta la arma la calculadora, que
    # cuesta cero tokens. `llamadas_max: 2` sigue defendiendolo.
    _falta_la_cuenta = bool(rec.get("falta_la_cuenta"))
    llamadas = G.paso_datos(
        "cuenta_repuesta", _cuenta_con_lo_declarado,
        llamadas, declarado, tienda_id, trace_id,
        memoria=(_memoria_idx if (_falta_la_cuenta or not _certifico_algo)
                 else None))
    # EL ORDEN IMPORTA: primero se aplica el reparto que falta, y despues se
    # declara el supuesto sobre la cuenta que ya lo tiene adentro.
    llamadas = G.paso_datos("reparto_repuesto", _reparto_de_pago_declarado,
                            llamadas, declarado, tienda_id, trace_id)
    llamadas = G.paso_datos("supuesto_de_pago", _supuesto_de_pago,
                            llamadas, declarado, tienda_id, trace_id)
    llamadas = G.paso_datos("bloques_a_uno", _bloques_a_uno,
                            llamadas, trace_id)

    # ── 2-ter. EL INDICE DEL TURNO: lo interpretado, punto por punto ─────
    # EL NEXO QUE FALTABA (Martin, 9-ago). La interpretacion entiende 100 y la
    # respuesta se cae igual, porque entre las dos no habia nadie: el
    # reconciliador compara lo declarado contra las LLAMADAS, y ningun control
    # mira si el punto llego al TEXTO. Aca se desarma lo interpretado en puntos
    # con id y se marca cuales tienen con que contestarse, ANTES de redactar.
    #
    # VA EN LA MISMA LLAMADA, no en una vuelta nueva: la obligacion se suma al
    # prompt de redaccion que ya se iba a hacer. Cuesta CERO latencia, que es la
    # queja mas fuerte hoy -21,5 segundos medidos en produccion-.
    material = " ".join(
        [str((l.get("resultado") or {}).get("bloque") or "") for l in llamadas]
        + [str(l.get("pedido") or "") for l in llamadas
           if l.get("herramienta") == "armar_presupuesto"])
    # LA MEMORIA TAMBIEN ES EVIDENCIA: el carrito vigente y lo ya mostrado
    # contestan un punto que este turno no volvio a buscar, y hace bien en no
    # volver a buscarlo.
    idx = IT.cobertura(declarado, material, trace_id, llamadas=llamadas,
                       memoria=_memoria_idx)
    # QUE SIGNIFICA QUE EL INDICE INTERVINO: que encontro un punto SIN
    # material y por eso le sumo una obligacion al prompt de redaccion. Si
    # todos los puntos tienen con que contestarse, mira y no toca nada.
    G.veredicto("indice_turno", bool(idx.get("faltan")),
                f"puntos:{len(idx.get('puntos') or [])} "
                f"faltan:{len(idx.get('faltan') or [])}")
    G.anotar("puntos_del_pedido", len(idx.get("puntos") or []))
    G.anotar("sin_material", [p["id"] for p in (idx.get("faltan") or [])][:5])
    pendiente = IT.instruccion(idx["faltan"])
    if pendiente:
        obligacion = (obligacion + "\n\n" if obligacion else "") + pendiente
        # LA HONESTIDAD, QUE ANTES LA DISPARABA AGOTAR LAS RONDAS. Con una sola
        # ronda no hay vueltas que agotar, asi que la señal pasa a ser la buena:
        # que despues de las reposiciones TODAVIA falte material. Va pegada al
        # pedido de completar, porque sin esto "agregalo" sobre un punto sin
        # material es una invitacion a inventarlo.
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

    # ── 3-bis. LA ATADURA DE LA PROSA ───────────────────────────────────
    # Va PRIMERA, apenas el modelo escribe y antes que cualquier otra guardia:
    # las etiquetas son sintaxis nuestra y las guardias de abajo cuentan
    # oraciones y buscan cifras, asi que tienen que ver la prosa ya limpia,
    # exactamente igual que antes de que esto existiera.
    texto = G.paso("atadura", AP.verificar, texto, llamadas, trace_id,
                   tienda_id=tienda_id)

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

    # ── 4. LA REGLA ─────────────────────────────────────────────────────
    # CADA GUARDIA PASA POR `G.paso` Y DEJA SU VEREDICTO. No es una capa nueva:
    # es la misma llamada de siempre, envuelta en el unico lugar que puede
    # decir si el nodo intervino, y lo dice COMPARANDO el texto que entro con
    # el que salio. Sin esto, cuando la respuesta sale mal hay que leer la
    # charla entera para saber cual de los veintipico de engranajes la rompio.
    bloque = _bloque_presupuesto(llamadas)
    texto = G.paso("sin_json", _sin_json_filtrado, texto, trace_id)
    texto = G.paso("sin_markdown", _sin_markdown, texto)
    texto = G.paso("la_cuenta_y_la_plata", _la_cuenta_y_la_plata,
                   texto, llamadas, bloque, trace_id,
                   previo=conv.get("ultimo_presupuesto") or "",
                   vistos=estado.get("productos_vistos") or [],
                   declarado=declarado,
                   carrito=conv.get("carrito_vigente") or [])
    texto = G.paso("sin_cobro_inventado", _sin_cobro_inventado,
                   texto, tienda_id, trace_id)
    texto = G.paso("sin_negar_lo_traido", _sin_negar_lo_traido,
                   texto, llamadas, trace_id)
    texto = G.paso("sin_afirmar_del_catalogo", _sin_afirmar_sobre_el_catalogo,
                   texto, llamadas, trace_id)
    texto = G.paso("sin_descuento_inventado", _sin_descuento_inventado,
                   texto, trace_id)
    texto = G.paso("sin_narracion_interna", _sin_narracion_interna,
                   texto, trace_id)
    texto = G.paso("sin_anuncio_vacio", _sin_anuncio_vacio, texto, trace_id)
    # La cuenta se manda entera: si el modelo la reescribio o se la comio, el
    # bloque del codigo vuelve al final. No se negocia, es la unica parte del
    # mensaje que el modelo no redacta.
    texto = G.paso("bloque_repuesto", _bloque_entero_o_repuesto,
                   texto, bloque, trace_id)
    # EL HALLAZGO, mismo trato que la cuenta. Va DESPUES de la poda de plata a
    # proposito: sus precios salen de la fuente y no se podan, pero si el
    # modelo escribio otros, esos si se fueron.
    texto = G.paso("hallazgo_repuesto", _bloque_entero_o_repuesto,
                   texto, _bloque_hallazgo(llamadas, texto), trace_id,
                   barrer_cuenta=False)
    texto = _RE_ID_INTERNO.sub("", texto).strip()

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

    # ── 6. LO QUE NO PUEDE DEPENDER DEL PROMPT ──────────────────────────
    # Dos cosas, y solo dos. La honestidad de bot porque el prompt solo no
    # alcanzo nunca, y el aviso de que es un asistente automatico en el primer
    # mensaje porque es una obligacion, no un criterio de redaccion.
    try:
        texto = G.paso("honestidad_bot",
                       lambda t: gs.asegurar_honestidad_bot(raw_message, t,
                                                            negocio), texto)
        if not history:
            texto = G.paso("saludo", gs.con_saludo_inicial, texto, negocio)
        else:
            texto = G.paso("saludo", gs.sin_saludo_del_modelo, texto)
    except Exception as e:
        log.warning("hub_venta_guardas_error", trace_id=trace_id,
                    error=str(e)[:120])

    # ── 6-ante. EL CONTRATO NO_OMITE ────────────────────────────────────
    # La unica guardia que SUMA. Va despues de todas las que restan y antes del
    # componedor, que es quien decide el largo: si lo repuesto sobra, ese lo
    # poda con sus reglas de siempre.
    texto = G.paso("punto_omitido", _punto_omitido_repuesto, texto, declarado,
                   llamadas, _memoria_idx, tienda_id, trace_id)

    # ── 6-bis. EL LARGO, EN UN SOLO LUGAR ───────────────────────────────
    # Va ULTIMO a proposito. Hasta acá cada pieza pegó lo suyo -la prosa del
    # modelo, la cuenta, el hallazgo, el cierre, el saludo- y ninguna miró el
    # total; este es el unico punto del turno donde el mensaje existe entero y
    # todavia se puede acortar. Adelantarlo aunque sea un paso lo dejaria
    # midiendo un mensaje que despues crece.
    try:
        from app.core.mensaje import componer
        anterior = next((h.get("content") for h in reversed(history or [])
                         if h.get("role") == "assistant"), "")
        texto = G.paso("componedor", componer, texto,
                       anterior=str(anterior or ""),
                       trace_id=trace_id, pregunta=raw_message)
    except Exception as e:
        # Un componedor roto NO puede dejar mudo al bot: se manda el mensaje
        # largo, que es lo que se mandaba ayer.
        log.warning("hub_venta_componedor_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")

    # ── 6-ter. LA ADUANA: LOS INVARIANTES, ANTES DE MANDAR ──────────────
    # Los invariantes del 10-ago encontraron el error de plata y seis defectos
    # mas, pero corrian DESPUES, sobre lo que el cliente ya habia leido. Aca
    # corren en el ultimo metro: el mensaje existe entero y todavia no salio.
    # Repara lo que puede probar -etiqueta fugada, titulo sin lista, renglon
    # calcado- sin tocar un peso, y lo que no puede reparar lo grita con el
    # trace_id en vez de esperar a que alguien lea la charla.
    try:
        from app.core.aduana import revisar_salida
        anterior_bot = next((h.get("content") for h in reversed(history or [])
                             if h.get("role") == "assistant"), "")
        texto = G.paso("aduana", revisar_salida, texto,
                       anterior=str(anterior_bot or ""),
                       trace_id=trace_id, tienda_id=tienda_id)
    except Exception as e:
        log.warning("hub_venta_aduana_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")

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
            ultimo_presupuesto=(bloque or conv.get("ultimo_presupuesto") or None))
        G.veredicto("memoria", True,
                    f"turnos:{len(history) // 2} carrito:{len(carrito or [])}")
    except Exception as e:
        G.veredicto("memoria", False, f"no_guardo:{type(e).__name__}")
        log.warning("hub_venta_save_error", trace_id=trace_id, error=str(e)[:150])

    # EL INDICE, MEDIDO SOBRE LO QUE EL CLIENTE VA A LEER. La pasada de arriba
    # mira el material y sirve para PEDIR; esta mira el texto final y sirve para
    # SABER. Es la regla de tau-bench: se juzga por lo observado, no por lo que
    # el agente cuenta que hizo. Sin esto, "el destino no llego al mensaje" solo
    # se descubre leyendo una charla a mano, que es como se descubrio hoy.
    _idx_final = IT.cobertura(declarado, texto, trace_id + "|final",
                              llamadas=llamadas, memoria=_memoria_idx)
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
