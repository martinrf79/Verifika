"""EL TURNO. Uno solo, de punta a punta, y reemplaza al hub entero.

    mensaje del cliente
      |
      1. INTERPRETAR   llamada UNO. `registrar_pedido`, temperatura 0.
      |                El modelo DECLARA. No busca.
      2. RESOLVER      codigo. De lo declarado salen las busquedas, la ficha,
      |                el stock, la compatibilidad, los temas, los envios y la
      |                cuenta. Todo determinista.
      3. TABLA         codigo. Una fila por cosa preguntada, con su estado y
      |                SOLO los campos que esa pregunta necesita.
      4. REDACTAR      llamada DOS. Devuelve la tabla LLENA, con esquema. No
      |                escribe numeros de plata: no tiene donde.
      5. ARMAR         codigo. Ordena, pega la cuenta sellada al final y, si
      |                quedo un punto sin contestar, escribe UNA pregunta. El
      |                estado de la fila manda sobre lo que escribio el modelo:
      |                una fila abierta se pregunta aunque el modelo escribiera
      |                encima, y una fila sin material no puede traer cifras.
      6. CIERRE        codigo. Lead o datos de cobro, y la memoria del turno.

LO QUE YA NO EXISTE, a proposito: las cuatro puertas de salida con sus
veintitres piezas, la reposicion por cirugia de strings, el indice de cobertura
medido contra el texto, el grafo por engranaje, la atadura de prosa y las trece
reglas del componedor. No se reemplazaron por una guardia mejor: dejaron de
hacer falta porque el modelo ya no devuelve prosa libre que haya que vigilar.

    plata inventada      no hay casilla para un numero de plata
    punto omitido        hay una casilla por punto y el esquema las pide todas
    dos preguntas        `pregunta_final` es un campo, no una lista
    dato inventado       si la fuente no lo tiene, el material sale VACIO
    identidad elegida    `ambiguo` sale como pregunta CON los candidatos

LO QUE SI SIGUE, porque es politica y no plomeria: el saludo la primera vez, la
honestidad si preguntan si es un bot, la linea del camino al cobro cuando hay
total cerrado, y la memoria entera de la charla.

Reemplaza a `hub_venta.procesar_venta` en el camino vivo. El viejo esta entero
en `archivo/`, con su fila. Se vuelve con `git revert` de este commit.

Las funciones de abajo hasta `_reloj` vienen del hub TAL CUAL, con sus
comentarios: cada uno es una medicion que costo un dia y no se reescribe de
memoria. Lo nuevo empieza en `_redactar`.
"""
import asyncio
import contextlib
import json
import time

from app.config import get_settings
from app.core import herramientas as H
from app.core import pedido as P
from app.core import tabla as TB
from app.core.llm_reintento import (_cliente, _cliente_decisor, _extra_decisor,
                                    _modelo, _modelo_decisor)
from app.core.resolver import resolver
from app.logger import get_logger
from app.storage.firestore_client import get_conversation, save_conversation

log = get_logger(__name__)
settings = get_settings()

_TIMEOUT_S = 14
_MAX_HERRAMIENTAS = 10
_SIN_MODELO: set = set()

_SISTEMA_MINIMO = ("Sos el vendedor de {negocio}. Contesta en español "
                   "rioplatense, corto y directo, sin markdown.")

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

# LA INSTRUCCION DE LA LLAMADA DOS YA NO PIDE UN MENSAJE: PIDE LA TABLA LLENA.
# La diferencia con la de antes no es de redaccion. Antes decia "contesta TODO
# lo que el cliente pregunto" y el modelo tenia que deducir de un volcado de
# herramientas QUE le habian preguntado. Ahora lo tiene escrito, fila por fila,
# al lado de su evidencia, y lo unico que le queda es escribir.
_INSTRUCCION_DOS = """Abajo esta la MESA del turno: una fila por cada cosa que
el cliente pregunto, con lo que el sistema encontro para contestarla.

Devolve la mesa LLENA, una casilla por fila, con el mismo id y en el mismo
orden. Ninguna se saltea.

  con_material  contestala con el material de ESA fila y nada mas.
  sin_material  no hay dato. Decilo honesto o pediselo. NO lo completes de
                memoria ni lo deduzcas: si la fuente no lo dice, no lo sabemos.
  pregunta      no se contesta, se pregunta. Si trae candidatos, preguntale
                cual de esos es.
  sellado       dejala VACIA. Ese texto lo pega el codigo tal cual.

NO ESCRIBAS NINGUN NUMERO DE PLATA. Los precios y el total salen del bloque
sellado, que se pega solo. Si nombras un producto, usa el nombre que dice su
fila.

`apertura` es una frase corta para arrancar, o vacio. `pregunta_final` es UNA
sola pregunta al final, o vacio. Escribi las casillas para que se lean seguidas,
como un solo mensaje de un vendedor, no como una lista de respuestas sueltas."""


def sistema(negocio: str = "") -> str:
    """La voz del vendedor, leida de la fuente. El minimo de arriba es la red
    por si el archivo faltara: un prompt vacio dejaria al modelo sin ninguna
    atadura, que es peor que uno corto."""
    from app.core.guia_venta_prosa import identidad
    return identidad(negocio) or _SISTEMA_MINIMO.format(negocio=negocio)












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

    `turno_pedidos` ya dice que herramienta se pidio; esto dice que volvio:
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
        log.info("turno_fuente", trace_id=trace_id, ronda=ronda,
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
        log.warning("turno_llamada_uno_error", trace_id=trace_id,
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
        log.warning("turno_pedidos_recortados", trace_id=trace_id,
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
            log.warning("turno_herramienta_excepcion", trace_id=trace_id,
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
        if l.get("herramienta") not in ("armar_presupuesto", "cotizar"):
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
    if any(l.get("herramienta") in ("armar_presupuesto", "cotizar") for l in llamadas):
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
        log.warning("turno_extractor_error", trace_id=trace_id,
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
                        log.info("turno_cobro_ya_entregado", trace_id=trace_id)
                        rd = None
                except Exception as e:
                    log.warning("turno_cobro_dedup_error", trace_id=trace_id,
                                error=str(e)[:120])
            if rd:
                base = (texto or "").strip()
                if not base or base == settings.VERIFIKA_FALLBACK_MESSAGE:
                    texto = rd.strip()
                elif base[:80] and base[:80] in rd:
                    texto = rd.strip()
                else:
                    texto = base + "\n\n" + rd.strip()
                log.info("turno_cierre", trace_id=trace_id,
                         accion=meta_lead.get("accion"))
        except Exception as e:
            log.warning("turno_lead_error", trace_id=trace_id,
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

# ══════════════════════════════════════════════════════════════════════════
# LO NUEVO: LA MESA EN EL MEDIO
# ══════════════════════════════════════════════════════════════════════════

async def _redactar(negocio, memoria, history, mensaje, mesa, trace_id):
    """LLAMADA DOS. El modelo devuelve la MESA LLENA, no un mensaje.

    Devuelve `(respuesta, sin_modelo)`. `sin_modelo` en True significa que la
    llamada no se pudo hacer o que lo que volvio no era la mesa; las dos cosas
    terminan igual para el cliente y por eso comparten bandera.

    SI NO SE PUEDE PARSEAR, NO SE MANDA LA PROSA CRUDA. Es tentador -al menos
    el cliente recibe algo- y es exactamente el agujero que este diseño cierra:
    una prosa que no paso por la mesa puede traer un precio que nadie calculo.
    Vale mas decir que hay demanda y que reintente. Se loguea fuerte porque un
    modelo que deja de respetar el esquema tiene que verse el mismo dia.
    """
    cli = _cliente()
    if cli is None:
        return {}, True
    datos = json.dumps(mesa, ensure_ascii=False, default=str)
    msgs = _mensajes(negocio, memoria, history, mensaje, _INSTRUCCION_DOS,
                     datos)

    def _call():
        r = cli.chat.completions.create(
            model=_modelo(), messages=msgs, temperature=0.6, max_tokens=1500,
            response_format={"type": "json_schema", "json_schema": {
                "name": "respuesta_del_turno", "strict": True,
                "schema": TB.ESQUEMA_RESPUESTA}},
            extra_body={"reasoning_effort": settings.REDACTOR_REASONING})
        return r.choices[0].message.content or ""

    from app.core.llm_reintento import llamar_con_reintento
    try:
        crudo = await llamar_con_reintento(_call, timeout_s=_TIMEOUT_S,
                                           trace_id=trace_id)
    except Exception as e:
        log.warning("turno_llamada_dos_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:160]}")
        return {}, True
    resp = _parsear(crudo)
    if resp is None:
        log.error("turno_respuesta_no_es_la_mesa", trace_id=trace_id,
                  largo=len(crudo or ""), muestra=(crudo or "")[:200])
        return {}, True
    return resp, False


def _parsear(crudo: str):
    """La respuesta del modelo como dict, o None.

    Con `response_format` puesto viene JSON limpio. La valla de las comillas
    triples esta igual porque un proveedor que ignore el esquema devuelve el
    JSON adentro de un bloque de codigo, y eso es un fallo de forma, no de
    contenido: se arregla acá y no se pierde el turno.
    """
    t = (crudo or "").strip()
    if t.startswith("```"):
        t = t.split("```")[1] if "```" in t[3:] else t[3:]
        t = t[4:] if t.lower().startswith("json") else t
        t = t.strip("` \n")
    try:
        d = json.loads(t)
    except (ValueError, TypeError):
        return None
    if not isinstance(d, dict) or not isinstance(d.get("puntos"), list):
        return None
    return d


def _obligaciones(texto: str, mesa: dict, negocio: str, primera_vez: bool,
                  mensaje: str, dichos: str, tienda_id: str,
                  trace_id: str) -> str:
    """Lo que tiene que estar si o si y no sale de la mesa. Tres cosas, y las
    tres son POLITICA de la casa, no plomeria: por eso sobreviven al apagado.

      1. Que es un bot, si preguntan. Nunca se niega.
      2. El saludo, la primera vez y solo la primera.
      3. Como se paga, cuando hay un total cerrado y el turno no pregunta.

    El cuarto que hacia la puerta vieja -reponer el punto omitido- ya no existe:
    la mesa tiene una casilla por punto y el armado escribe la pregunta cuando
    queda vacia, asi que no hay nada que reponer con cirugia de strings.
    """
    from app.core import guardas_salida as gs
    from app.core import camino_cobro as cc
    try:
        # (mensaje del cliente, respuesta, nombre del negocio). Hasta el 3-sep
        # se llamaba con dos argumentos y cruzados: tiraba TypeError en CADA
        # turno, el `except` de abajo lo tapaba, y la guarda que declara que es
        # un bot no corrio nunca. Se veia en produccion como `turno_guarda_error`
        # dos veces en dos turnos seguidos.
        texto = gs.asegurar_honestidad_bot(mensaje, texto, negocio)
        texto = (gs.con_saludo_inicial(texto, negocio, tienda_id)
                 if primera_vez else gs.sin_saludo_del_modelo(texto))
    except Exception as e:  # noqa: BLE001 — una guarda no tumba el turno
        log.warning("turno_guarda_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")
    try:
        texto = cc.linea_de_cobro(texto, mesa.get("bloque") or "", dichos,
                                  tienda_id)
    except Exception as e:  # noqa: BLE001
        log.warning("turno_cobro_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")
    return texto


async def procesar_turno(user_id: str, raw_message: str, tienda_id: str,
                         canal: str, trace_id: str) -> str:
    """Un turno completo. Devuelve el texto para el cliente.

    Misma firma que `hub_venta.procesar_venta`, para que el orchestrator cambie
    una linea y nada mas.
    """
    t0 = time.time()
    etapas: dict = {}
    from app.core.estado_venta import (construir_estado, set_current_estado,
                                       get_envio_localidades, merge_productos)
    from app.core.contexto_turno import set_current_tienda
    from app.core import guardas_salida as gs

    conv = get_conversation(user_id, tienda_id=tienda_id)
    history = conv.get("history", []) or []
    estado = construir_estado(conv, None)
    estado["mensaje_del_turno"] = raw_message or ""
    set_current_tienda(tienda_id)
    set_current_estado(estado)

    negocio = gs.business_name(tienda_id)
    memoria = _memoria_texto(estado, history, tienda_id)
    _memoria_idx = ((conv.get("carrito_vigente") or [])
                    + (estado.get("productos_vistos") or []))

    # ── 1. INTERPRETAR ──────────────────────────────────────────────────
    llamadas: list = []
    declarado: dict = {}
    with _reloj(etapas, "decisor"):
        pedidos, texto_directo = await _pedir_herramientas(
            negocio, memoria, history, raw_message, tienda_id, trace_id)
    log.info("turno_pedidos", trace_id=trace_id,
             herramientas=[p["nombre"] for p in pedidos])
    if pedidos:
        with _reloj(etapas, "herramientas"):
            llamadas = await _ejecutar_en_paralelo(pedidos, tienda_id, trace_id)
        _log_fuente(llamadas, trace_id, 1)
        for l in llamadas:
            if l.get("herramienta") == "registrar_pedido":
                declarado = (l.get("resultado") or {}).get("pedido") or declarado
        try:
            declarado = _restricciones_de_los_filtros(declarado, llamadas,
                                                      trace_id)
        except Exception as e:  # noqa: BLE001
            log.warning("turno_restriccion_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")

    # ── 2. RESOLVER ─────────────────────────────────────────────────────
    with _reloj(etapas, "resolver"):
        out = resolver(declarado, _memoria_idx, tienda_id, trace_id,
                       llamadas=llamadas,
                       descartados=conv.get("descartados") or [],
                       diferida=conv.get("oferta_diferida") or [])
    llamadas = out["llamadas"]
    bloque = out["bloque"] or ""

    # ── 3. LA MESA ──────────────────────────────────────────────────────
    mesa = TB.tabla(declarado, llamadas, bloque)
    log.info("turno_mesa", trace_id=trace_id, puntos=len(mesa["puntos"]),
             sin_material=sum(1 for p in mesa["puntos"]
                              if p["estado"] == "sin_material"),
             peso=len(json.dumps(mesa, ensure_ascii=False, default=str)))

    # ── 4. REDACTAR Y 5. ARMAR ──────────────────────────────────────────
    sin_modelo = False
    informe: dict = {}
    if mesa["puntos"]:
        with _reloj(etapas, "redactor"):
            respuesta, sin_modelo = await _redactar(
                negocio, memoria, history, raw_message, mesa, trace_id)
        texto = (TB.armar(respuesta, mesa, trace_id, informe)
                 if not sin_modelo else "")
    else:
        # Sin puntos el modelo ya contesto en la llamada uno: un saludo, un
        # gracias, una respuesta a algo que preguntamos nosotros.
        texto = texto_directo

    if not (texto or "").strip():
        # LA MENTIRA QUE SE ARREGLO EL 11-AGO Y QUE NO SE VUELVE A HACER: si el
        # modelo no contesto, se dice que hay demanda. El "no tengo el dato" es
        # una afirmacion sobre el catalogo y solo se dice cuando el catalogo
        # efectivamente no lo tiene.
        if sin_modelo or trace_id in _SIN_MODELO:
            from app.core.guia_venta_prosa import mensaje as _prosa
            texto = _prosa("sobrecarga",
                           "Perdón, estoy con mucha demanda en este momento. "
                           "Probá de nuevo en un ratito y te respondo. 🙏")
            log.warning("turno_sin_modelo", trace_id=trace_id)
        else:
            texto = settings.VERIFIKA_FALLBACK_MESSAGE
            log.warning("turno_sin_texto", trace_id=trace_id)

    # ── 6. LAS OBLIGACIONES QUE NO SALEN DE LA MESA ─────────────────────
    dichos = "\n".join(str(h.get("content") or "") for h in (history or [])
                       if h.get("role") == "assistant")
    texto = _obligaciones(texto, mesa, negocio, not history, raw_message,
                          dichos, tienda_id, trace_id)

    # ── 7. CIERRE Y COBRO ───────────────────────────────────────────────
    senal = _senal_de_cierre(llamadas, raw_message)
    with _reloj(etapas, "cierre"):
        texto, datos_cliente, pregunta_cierre_hecha = await _cerrar(
            conv, user_id, canal, tienda_id, raw_message, texto, trace_id,
            senal, bloque)

    # ── 8. MEMORIA ──────────────────────────────────────────────────────
    history = history + [{"role": "user", "content": raw_message},
                         {"role": "assistant", "content": texto}]
    resumen = conv.get("summary", "") or ""
    descartados_viejos = history[:-(settings.HISTORY_LIMIT * 2)]
    if descartados_viejos:
        try:
            from app.core.memoria_larga import actualizar_resumen
            with _reloj(etapas, "memoria"):
                resumen = await actualizar_resumen(resumen, descartados_viejos,
                                                   trace_id)
        except Exception as e:  # noqa: BLE001
            log.warning("turno_memoria_error", trace_id=trace_id,
                        error=str(e)[:120])
    history = history[-(settings.HISTORY_LIMIT * 2):]

    productos_vistos = merge_productos(
        conv.get("productos_vistos") or [],
        _productos_del_turno(llamadas, turno=len(history) // 2))
    from app.core.estado_venta import (ancla_al_dia, detectar_criterio,
                                       libera_criterio, pide_agregar_al_pedido)
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
        declarado_ahora = list(dict.fromkeys(
            (conv.get("ultimo_declarado") or []) + declarado_ahora))
    descartados = _descartados_nuevos(
        conv.get("descartados") or [], dados_de_baja, carrito,
        declarado_antes=(None if agrega else conv.get("ultimo_declarado") or []),
        declarado_ahora=declarado_ahora)
    localidades = (get_envio_localidades()
                   or (conv.get("ultimas_localidades") or []))
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
        log.warning("turno_provincia_error", trace_id=trace_id,
                    error=str(e)[:120])
    preferencias = _preferencias_al_dia(conv.get("preferencias_cliente") or {},
                                        declarado, llamadas)
    _cands = ([{"id": c.get("id"), "nombre": c.get("nombre")} for c in carrito]
              if len(carrito) == 1
              else _productos_del_turno(llamadas, turno=len(history) // 2))
    ancla = ancla_al_dia(conv.get("producto_anotado") or {}, raw_message, _cands)
    try:
        from app.core.estado_venta import get_current_estado as _gce
        _grupos_envio = (_gce() or {}).get("grupos_envio") or None
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
            ultimo_declarado=(declarado_ahora
                              or conv.get("ultimo_declarado") or []),
            ultima_localidad=(localidades[-1] if localidades
                              else (conv.get("ultima_localidad") or "")),
            ultimas_localidades=localidades,
            grupos_envio=_grupos_envio,
            criterio_cliente=criterio,
            producto_anotado=(ancla
                              if ancla != (conv.get("producto_anotado") or {})
                              else None),
            provincia_envio=provincia or None,
            preferencias_cliente=preferencias or None,
            datos_cliente_parciales=datos_cliente,
            pregunta_cierre_hecha=pregunta_cierre_hecha,
            # LA OFERTA DIFERIDA SE CONSERVA TAL CUAL. La calculaba el indice de
            # cobertura, que se apago; la mesa no tiene concepto de oferta.
            # Conservarla es lo unico honesto: apagarla haria que el bot vuelva
            # a ofrecer lo que el cliente ya rechazo, que es la insistencia que
            # la ficha 16B saco. Que el bot OFREZCA de nuevo por su cuenta es
            # una decision de venta de Martin, y hoy no la toma el codigo.
            oferta_diferida=conv.get("oferta_diferida") or [],
            ultimo_presupuesto=(bloque or conv.get("ultimo_presupuesto")
                                or None))
    except Exception as e:  # noqa: BLE001
        log.warning("turno_save_error", trace_id=trace_id, error=str(e)[:150])

    # ── 9. LO QUE LA COMPUERTA VIO ──────────────────────────────────────
    #
    # UN TURNO INCOMPLETO DEJA DE LOGUEARSE COMO CORRECTO. Medido en vivo el
    # 3-sep: los turnos tg_524215778 y tg_524215783 salieron con puntos que la
    # mesa sabia sin contestar, y el unico renglon que quedo en el log fue
    # `turno_ok`. Desde afuera -que es el unico lugar desde donde se mira
    # produccion- el turno pasaba por bueno. El aviso va ANTES del `turno_ok`
    # para que el que lee los logs de arriba hacia abajo lo vea pegado.
    if informe.get("abiertos") or informe.get("salteados"):
        log.warning("turno_incompleto", trace_id=trace_id,
                    abiertos=informe.get("abiertos") or [],
                    salteados=informe.get("salteados") or [],
                    pregunto=bool(informe.get("pregunto")))
    log.info("turno_ok", trace_id=trace_id,
             latency_ms=int((time.time() - t0) * 1000),
             etapas=etapas, largo=len(texto or ""),
             puntos=len(mesa["puntos"]),
             abiertos=len(informe.get("abiertos") or []),
             salteados=len(informe.get("salteados") or []))
    return texto
