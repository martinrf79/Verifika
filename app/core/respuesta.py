"""EL TURNO, EN UNA SOLA LLAMADA. Desde el 11-sep-2026 este es el camino vivo.

QUE REEMPLAZA. A `turno.py` y a las ocho etapas: moldes, decisor con
herramientas, resolver, mesa, redactor, obligaciones. Todo eso esta apagado en
`archivo/apagado_11sep/`. No conviven: hay un solo camino.

EL FLUJO, entero:

  1. FUENTE   el codigo pone el inventario -dos renglones sobre el catalogo
              entero-, las politicas de la casa que el mensaje pisa, y el
              ENVIO ya cotizado: el destino sale del mensaje o de la charla y
              la tarifa de la tabla, antes de que el modelo hable.
  2. MODELO   ve la voz de la casa, la memoria, los VEINTE TIPOS y el motor de
              busqueda. BUSCA EL: escribe la consulta, el codigo la ejecuta, y
              con lo que volvio contesta. El precio lo copia de la ficha que
              trajo; el envio y la suma van como hueco, porque no los sabe.
  3. NUMEROS  el codigo escribe el envio que ya cotizo y el total, y tira
              abajo la respuesta si quedo una sola cifra que la fuente no
              tiene. La procedencia se mide contra TODO lo que viajo.
  4. CIERRE   si el cliente decidio comprar, se toma el pedido y se manda el
              link de pago. `leads` y `cierre` no se tocaron.
  5. MEMORIA  se guarda la charla, igual que siempre.

POR QUE UNA SOLA LLAMADA. Tres llamadas por turno daban entre 4,4 y 5,8
segundos medidos y se comian la cuota diaria de a tres. Una sola con los veinte
moldes adentro pesa menos que la primera de las tres que habia.

DE DONDE SACA EL MODELO LA RESPUESTA, que es la pregunta que define todo esto:
de las fichas que EL busco con `motor.buscar` y de las politicas que el codigo
certifica, y de ningun otro lado. Por eso la ficha viaja con el precio ya
escrito, y por eso la guarda de procedencia mira exactamente esas fichas.

POR QUE EL MODELO BUSCA Y NO EL CODIGO. El codigo no razona, asi que no puede
traducir "un rectangulo con teclas" a `teclado` ni "acorde a la crisis" a un
orden por precio. Cuando lo intento -`resolver_inclusion` y sus hermanas,
cortando raices de cuatro letras- dio lo que tenia que dar: "que no sea de
marca china" resolvia a `origen no_contiene marc`, la raiz de "marca", que esta
en los 880 origenes. Cero productos, y el bot diciendo que no hay nada.

LO QUE EL MODELO NO PUEDE HACER, y lo garantiza el codigo, no el prompt:
escribir un numero que la fuente no tenga -precio, plazo o spec, da igual-,
calcular un envio o una suma, afirmar que existe un producto que no esta en las
fichas, e inventar una politica de la casa.
"""
import json
import time

from app.config import get_settings
from app.core import numeros as N
from app.core import tipos as TP
from app.core.llm_reintento import llamar_con_reintento
from app.logger import get_logger
from app.storage.firestore_client import get_conversation, save_conversation

log = get_logger(__name__)
settings = get_settings()


# ── EL PROMPT ───────────────────────────────────────────────────────────────
#
# Corto a proposito. Lo unico largo son los veinte moldes, que son el trabajo
# del modelo. Cada regla de aca tiene ademas su candado en codigo: el prompt
# pide, el codigo obliga.
_REGLAS = """Sos el vendedor. Contestas UN mensaje de WhatsApp.

Abajo tenes VEINTE TIPOS de pregunta con el molde de su respuesta. Eligi el
tipo que corresponde al mensaje del cliente y contestale con ESE molde, escrito
con tus palabras, corto y natural. Si el mensaje mezcla dos tipos, contesta los
dos en el mismo mensaje.

LA PLATA. El precio de un producto lo escribis VOS, copiado TAL CUAL del campo
`precio` de su ficha, hasta el ultimo digito. Es el unico numero de plata que
podes escribir, y solo si esa ficha esta abajo.

Los otros dos NO los sabes y no los podes deducir: el costo del ENVIO escribilo
{{envio}}, y la SUMA de varias cosas escribila {{total}}. No los calcules, no
los estimes, no los redondees. Los pone el codigo.

Cualquier cifra de plata que no salga de una ficha o de esos dos huecos tira la
respuesta entera abajo y el cliente se queda sin contestar. Si no tenes el
precio, decilo; nunca lo aproximes.

Lo que en el molde va entre signos de menor y mayor -<producto>, <stock>,
<opciones>- NO se copia: ahi va la palabra real, sacada de la ficha que tenes
abajo. Las llaves dobles son las tres unicas que el codigo llena.

PARA HABLAR DE UN PRODUCTO, PRIMERO BUSCA. Tenes la herramienta `buscar` y es
el UNICO lugar del que salen las fichas y los precios. No contestes de memoria
ni con lo que sepas de esos productos: si no lo buscaste, no lo tenes.

Traduci vos lo que el cliente dijo. "Un rectangulo con teclas" es la categoria
`teclado`. "Algo acorde a la crisis" es ordenar por precio de menor a mayor.
Eso es tu trabajo, no el del codigo.

Si el cliente pidio varias cosas, mandalas como varias consultas en UNA sola
llamada. Si lo que volvio no sirve, busca de nuevo con otra consulta.

LEE LO QUE LA BUSQUEDA TE CONTESTA, que dice mas que la lista:
- `no_aplicado` es una condicion que el catalogo NO puede cumplir. Deciselo al
  cliente; no la des por cumplida ni la ignores.
- `veredicto: ambiguo` significa que hay varios que pegan igual. NO elijas:
  preguntale cual.
- `veredicto: no_existe` con filas al lado es lo mas parecido, no lo que pidio.
  Decile que eso exacto no hay y mostrale esto.
- `sin_dato` son los que no tienen ese dato cargado. No es un no.

SOLO EXISTE LO QUE LA BUSQUEDA DEVOLVIO. Si un producto no aparecio, no lo
vendemos y se lo decis. Si un dato no esta en la ficha, no lo tenemos y se lo
decis.

Contesta SOLO con este JSON, sin nada alrededor:
{"tipo": "<uno de los veinte>", "texto": "<el mensaje para el cliente>"}

LOS VEINTE TIPOS:
"""


def _prompt_sistema(negocio: str) -> str:
    from app.core.guia_venta_prosa import identidad
    voz = identidad(negocio) or ""
    return "\n".join(x for x in (voz, _REGLAS + TP.bloque_para_el_prompt()) if x)


def _memoria_texto(conv: dict) -> str:
    """Lo que el modelo tiene que recordar de la charla, en pocas lineas.

    LA MEMORIA NO SE APAGO Y NO SE APAGA. Es el objetivo 3 del proyecto: una
    referencia lejana tiene que resolver. Lo que se apago es la maquinaria que
    la rodeaba, no lo que el sistema recuerda.
    """
    partes = []
    resumen = (conv.get("summary") or "").strip()
    if resumen:
        partes.append("De lo que ya hablaron: " + resumen)
    vistos = [str(p.get("nombre") or "") for p in (conv.get("productos_vistos") or [])]
    if vistos:
        partes.append("Productos que ya le mostraste: " + ", ".join(vistos[:8]))
    carrito = [str(p.get("nombre") or "") for p in (conv.get("carrito_vigente") or [])]
    if carrito:
        partes.append("En el pedido: " + ", ".join(carrito[:8]))
    descartados = [str(x) for x in (conv.get("descartados") or [])]
    if descartados:
        partes.append("Ya dijo que NO a: " + ", ".join(descartados[:6]))
    loc = (conv.get("ultima_localidad") or "").strip()
    if loc:
        partes.append("Envia a: " + loc)
    datos = conv.get("datos_cliente_parciales") or {}
    if datos.get("nombre"):
        partes.append("Se llama: " + str(datos["nombre"]))
    return "\n".join(partes)


def _bloque_fuente(politicas: list, inventario: str = "",
                   envio: str = "") -> str:
    """Lo que el codigo pone delante del modelo SIN que lo pida.

    YA NO HAY FICHAS ACA, y es el cambio de la FICHA 50: las trae el modelo con
    `buscar`. Queda lo que ninguna busqueda puede contestar y por eso viaja
    siempre.

    EL INVENTARIO. Medido el 11-sep: a "¿cuantos productos vendes?" el bot
    contesto "5 modelos de memorias RAM", porque el encabezado le decia "es
    todo lo que existe" arriba de las cinco fichas que la relevancia habia
    traido. Una pregunta sobre el catalogo ENTERO no la contesta ninguna
    busqueda por parecido: son dos renglones y van siempre.

    LAS POLITICAS siguen certificadas por el codigo. Son el mapa 3 y no cambian
    en esta vuelta.

    EL ENVIO ES EL MAPA 2 y entra igual que el inventario: resuelto por el
    codigo, sin que el modelo lo pida. No es una herramienta mas porque no hay
    nada que razonar —el destino sale del codigo postal— y porque cada vuelta
    al modelo vuelve a pagar el prompt entero.
    """
    partes = []
    if inventario:
        partes.append(inventario)
    if envio:
        partes.append(envio)
    if politicas:
        partes.append("POLITICAS DE LA CASA que tocan este mensaje:\n"
                      + "\n".join(f"- {p['tema']}: {p['texto']}" for p in politicas))
    return "\n\n".join(partes)


# Los dos temas que el bloque de envio REEMPLAZA. No son todos los de envio: el
# plazo, el express, el exterior y el embalaje siguen siendo politica, porque el
# bloque no los contesta.
TEMAS_DEL_ENVIO = ("costo_envio", "envios")


def _sin_el_tema_del_envio(politicas: list) -> list:
    """UN SOLO CAMINO PARA EL NUMERO DEL ENVIO.

    La politica `costo_envio` publica el RANGO del interior -de 5.000 a 12.000-
    y el bloque de envio trae la tarifa EXACTA de esa provincia, sacada de la
    misma fuente. Con las dos delante el modelo escribia el rango, que es el
    numero flojo, teniendo el exacto al lado. Por cada cosa que se prende se
    apaga una.
    """
    return [p for p in (politicas or []) if p["tema"] not in TEMAS_DEL_ENVIO]


def _parsear(crudo: str) -> dict:
    """El JSON del modelo, o el texto pelado si no vino como JSON. Un modelo
    que se olvida del formato no puede dejar mudo al bot."""
    t = (crudo or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):] if "{" in t else t
    try:
        d = json.loads(t[t.index("{"):t.rindex("}") + 1])
        if isinstance(d, dict) and (d.get("texto") or "").strip():
            return {"tipo": str(d.get("tipo") or ""), "texto": str(d["texto"])}
    except Exception:  # noqa: BLE001 — abajo esta la salida honesta
        pass
    return {"tipo": "", "texto": (crudo or "").strip()}


# Cuantas veces puede buscar el modelo en un turno. Dos, y el numero tiene
# motivo: una para buscar y otra para corregir si lo que salio no sirve, que es
# la capacidad que la FICHA 50 pide con todas las letras. La tercera no la pide
# nadie y cada vuelta es una llamada al modelo.
VUELTAS_DE_BUSQUEDA = 2


def _informe_en_blanco() -> dict:
    """EL NUMERO DEL MOTOR, un renglon por turno.

    QUE CONTESTA, que es lo que hoy no se puede contestar de ninguna otra
    forma: si el modelo USA el motor o lo esquiva, cuantas vueltas le cuesta
    -y cada vuelta vuelve a pagar el prompt entero-, si lo que vuelve le
    sirve o tiene que buscar de nuevo, y QUE LE FALTA A LA FUENTE, que sale
    solo de `campos`: una condicion que el catalogo no puede cumplir es un
    campo que habria que agregar, y hasta hoy eso se descubria leyendo
    charlas a mano.

    Las cuatro perillas del motor -dos vueltas, ocho filas, seis consultas,
    cinco por defecto- estan puestas a ojo. Este renglon es lo que permite
    moverlas mirando, y por eso va antes que cualquier arreglo de robustez.
    """
    return {"vueltas": 0, "llamadas": 0, "consultas": 0, "repetidas": 0,
            "veredictos": [], "filas": 0, "rescates": 0, "vacios": 0,
            "sin_dato": 0, "campos": [], "fichas": 0}


def _anotar(informe: dict, consultas: list, pedidas: set, r: dict) -> None:
    """Suma al informe lo que hizo ESTA llamada al motor.

    LA CONSULTA REPETIDA SE CUENTA APARTE, y es el unico numero de aca que no
    se puede sacar del resultado: entre vuelta y vuelta el modelo no ve lo que
    ya pidio, solo lo que volvio, asi que puede gastar la segunda vuelta
    repitiendo la primera. Si eso pasa seguido, el arreglo no es subir el tope
    de vueltas: es decirle que ya lo busco.
    """
    for c in (consultas or []):
        informe["consultas"] += 1
        seña = json.dumps(c, ensure_ascii=False, sort_keys=True, default=str)
        if seña in pedidas:
            informe["repetidas"] += 1
        else:
            pedidas.add(seña)
    for res in (r or {}).get("resultados") or []:
        veredicto = str(res.get("veredicto") or "")
        filas = len(res.get("filas") or [])
        informe["veredictos"].append(veredicto)
        informe["filas"] += filas
        informe["sin_dato"] += int(res.get("sin_dato") or 0)
        if not filas:
            informe["vacios"] += 1
        elif veredicto == "no_existe":
            # Trajo lo mas parecido: la condicion no se pudo cumplir entera.
            informe["rescates"] += 1
        for na in res.get("no_aplicado") or []:
            campo = str((na or {}).get("campo") or "")
            if campo:
                informe["campos"].append(campo)


async def _preguntar(sistema: str, memoria: str, history: list, mensaje: str,
                     fuente: str, trace_id: str, tienda_id: str) -> tuple:
    """La llamada al modelo, con el motor de busqueda en la mano.

    EL MODELO BUSCA Y DESPUES CONTESTA, y esa es la vuelta que agrega la FICHA
    50. Antes el codigo adivinaba que fichas ponerle delante leyendo el mensaje
    crudo; ahora el modelo escribe la consulta y el codigo la ejecuta.

    Devuelve (salida, fichas, informe). Las fichas son las del motor: es lo que
    `numeros` usa como procedencia, asi que un precio que no este en lo que el
    modelo EFECTIVAMENTE busco no puede salir al cliente.

    EL INFORME ES EL NUMERO DEL MOTOR, y por eso se arma aca y no adentro de
    `motor.py`: el motor ve UNA llamada, y lo que hay que medir es el TURNO
    -cuantas vueltas costo, si el modelo re-busco, si repitio la misma consulta,
    y que condicion no se pudo aplicar-. Nada de esto se puede reconstruir
    despues desde afuera: si no sale del turno, no existe.
    """
    from app.core import motor as MT
    from app.core.llm_reintento import _cliente, _modelo
    informe = _informe_en_blanco()
    cli = _cliente()
    if cli is None:
        log.warning("respuesta_sin_clave", trace_id=trace_id)
        return {}, [], informe
    msgs = [{"role": "system", "content": sistema}]
    if memoria:
        msgs.append({"role": "system", "content": memoria})
    for h in (history or [])[-(settings.HISTORY_LIMIT * 2):]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            msgs.append({"role": h["role"], "content": str(h["content"])[:900]})
    msgs.append({"role": "user",
                 "content": f"Mensaje del cliente: {mensaje}\n\n{fuente}"})

    try:
        herramientas = [MT.esquema(tienda_id)]
    except Exception as e:  # noqa: BLE001 — sin esquema se contesta sin buscar
        log.warning("respuesta_esquema_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")
        herramientas = []

    # NO SE LE REENVIA AL MODELO SU PROPIA LLAMADA, y no es una eleccion de
    # estilo. El protocolo de herramientas pide devolver el mensaje `assistant`
    # con sus `tool_calls` y despues el rol `tool`; Gemini ademas exige que ese
    # eco traiga un `thought_signature` suyo, y sin el contesta 400 -medido el
    # 11-sep, seis de seis-. Reenviar campos propios de un proveedor ata el
    # turno a ese proveedor.
    #
    # Lo que se hace en cambio: el resultado de la busqueda se le pone delante
    # como UN BLOQUE MAS de la fuente, que es exactamente lo que es. La vuelta
    # siguiente es una llamada limpia con ese bloque adentro. Funciona igual en
    # cualquier proveedor compatible y no tiene protocolo que mantener.
    fichas: list = []
    hallazgos: list = []
    pedidas: set = set()
    for vuelta in range(VUELTAS_DE_BUSQUEDA + 1):
        informe["vueltas"] += 1
        cuerpo = f"Mensaje del cliente: {mensaje}\n\n{fuente}"
        if hallazgos:
            cuerpo += ("\n\nLO QUE DEVOLVIO TU BUSQUEDA. Es toda la fuente que "
                       "tenes sobre productos; de aca salen las fichas y los "
                       "precios:\n" + "\n".join(hallazgos))
        turno = msgs + [{"role": "user", "content": cuerpo}]
        # En la ultima vuelta la herramienta ya no viaja: es la vuelta de
        # CONTESTAR. Sin esto el modelo puede quedarse buscando para siempre y
        # el cliente sin respuesta.
        tools = herramientas if (herramientas and vuelta < VUELTAS_DE_BUSQUEDA) else None

        def _call(_tools=tools, _msgs=turno):
            extra = {"tools": _tools, "tool_choice": "auto"} if _tools else {}
            r = cli.chat.completions.create(
                model=_modelo(), messages=_msgs, temperature=0.3,
                max_tokens=900, **extra)
            return r.choices[0].message if r.choices else None

        try:
            msg = await llamar_con_reintento(
                _call, timeout_s=settings.LLM_TIMEOUT_SECONDS,
                trace_id=trace_id)
        except Exception as e:  # noqa: BLE001 — el turno no se rompe por el modelo
            log.warning("respuesta_modelo_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:150]}")
            informe["fichas"] = len(fichas)
            return {}, fichas, informe
        if msg is None:
            informe["fichas"] = len(fichas)
            return {}, fichas, informe

        llamadas = list(getattr(msg, "tool_calls", None) or [])
        if not llamadas:
            informe["fichas"] = len(fichas)
            return _parsear(msg.content or ""), fichas, informe

        for c in llamadas:
            informe["llamadas"] += 1
            try:
                args = json.loads(c.function.arguments or "{}")
            except Exception:  # noqa: BLE001 — un JSON roto no tumba el turno
                args = {}
                log.warning("motor_argumentos_rotos", trace_id=trace_id,
                            crudo=str(c.function.arguments)[:200])
            consultas = args.get("consultas") or []
            r = MT.buscar(consultas, tienda_id, trace_id)
            _anotar(informe, consultas, pedidas, r)
            for f in MT.fichas_de(r):
                if str(f.get("id")) not in {str(x.get("id")) for x in fichas}:
                    fichas.append(f)
            hallazgos.append(
                "Buscaste: " + json.dumps(consultas, ensure_ascii=False)[:900]
                + "\nVolvio: " + json.dumps(r, ensure_ascii=False)[:8000])
    informe["fichas"] = len(fichas)
    return {}, fichas, informe


def _senal(tipo: str, mensaje: str) -> dict:
    """La interpretacion MINIMA que pide el cierre: intencion y confianza.

    LA SEÑAL SALE DE DOS LADOS Y NINGUNO ES UNA HERRAMIENTA. Del TIPO que
    eligio el modelo -`intencion_compra` es literalmente eso-, y de la marca
    determinista sobre el mensaje, que ya existia y no depende de que el modelo
    se acuerde de nada. Con que uno de los dos diga compra, alcanza.
    """
    from app.core.leads import _RE_PIDE_COBRO
    if _RE_PIDE_COBRO.search(mensaje or ""):
        return {"intencion": "decision_compra", "confianza": 1.0,
                "motivo": "pide_datos_de_pago"}
    if str(tipo or "") == "intencion_compra":
        return {"intencion": "decision_compra", "confianza": 1.0,
                "motivo": "tipo_intencion_compra"}
    if str(tipo or "") in ("precio_simple", "precio_multiple", "envio_costo"):
        return {"intencion": "pregunta_especifica", "confianza": 0.9}
    return {"intencion": "exploracion", "confianza": 0.6}


async def _cerrar(conv, user_id, canal, tienda_id, mensaje, texto, trace_id,
                  senal) -> tuple:
    """CIERRE Y COBRO. La misma funcion de siempre: `leads` no se toco.

    El bot que contesta bien y no toma el pedido no sirve para vender, asi que
    esta etapa sobrevivio al apagon entera. Devuelve (texto, datos del cliente,
    si ya se pregunto el cierre).
    """
    from app.core.cierre import extraer_datos_cliente, extraer_determinista
    from app.core.leads import _RE_PIDE_COBRO, procesar_mensaje_para_lead
    datos_previos = conv.get("datos_cliente_parciales") or {}
    datos_turno: dict = {}
    try:
        datos_turno.update(extraer_determinista(mensaje))
        if senal.get("intencion") == "decision_compra":
            for k, v in extraer_datos_cliente(mensaje, trace_id).items():
                if v:
                    datos_turno[k] = v
    except Exception as e:  # noqa: BLE001 — el cierre nunca tumba el turno
        log.warning("respuesta_extractor_error", trace_id=trace_id,
                    error=str(e)[:120])
    datos = {**datos_previos, **datos_turno}
    pide_cobro = bool(_RE_PIDE_COBRO.search(mensaje or ""))
    meta: dict = {}
    if (texto and texto != settings.VERIFIKA_FALLBACK_MESSAGE) or pide_cobro:
        try:
            _, meta = await procesar_mensaje_para_lead(
                user_id, canal, tienda_id, mensaje, texto, trace_id,
                interpretacion=senal,
                presupuesto=conv.get("ultimo_presupuesto") or "",
                datos_turno=datos_turno, datos_previos=datos,
                presupuesto_nuevo=False,
                pregunta_cierre_hecha=bool(conv.get("pregunta_cierre_hecha")))
            rd = (meta.get("respuesta_directa") or "").strip()
            # EL COBRO NO SE ENTREGA DOS VECES: se compara por el DATO -el CBU
            # o el alias-, no por el texto.
            if rd and meta.get("accion") == "cobro_datos":
                try:
                    from app.core.pago import datos_transferencia
                    d = datos_transferencia(tienda_id) or {}
                    clave = str(d.get("cbu") or d.get("alias") or "")
                    if clave and clave in (texto or ""):
                        log.info("respuesta_cobro_ya_entregado", trace_id=trace_id)
                        rd = ""
                except Exception as e:  # noqa: BLE001
                    log.warning("respuesta_cobro_dedup_error", trace_id=trace_id,
                                error=str(e)[:120])
            if rd:
                base = (texto or "").strip()
                if not base or base == settings.VERIFIKA_FALLBACK_MESSAGE:
                    texto = rd
                elif base[:80] and base[:80] in rd:
                    texto = rd
                else:
                    texto = base + "\n\n" + rd
                log.info("respuesta_cierre", trace_id=trace_id,
                         accion=meta.get("accion"))
        except Exception as e:  # noqa: BLE001
            log.warning("respuesta_lead_error", trace_id=trace_id,
                        error=str(e)[:160])
    hecha = meta.get("accion") in ("pregunta_cierre", "pregunta_pendiente_cierre")
    return texto, datos, hecha


async def procesar_turno(user_id: str, raw_message: str, tienda_id: str,
                         canal: str, trace_id: str) -> str:
    """Un turno completo. Devuelve el texto para el cliente.

    Misma firma que el turno viejo: el orchestrator cambia una linea."""
    t0 = time.time()
    etapas: dict = {}
    from app.core import fuente as F
    from app.core import guardas_salida as gs
    from app.core.contexto_turno import set_current_tienda

    set_current_tienda(tienda_id)
    conv = get_conversation(user_id, tienda_id=tienda_id) or {}
    history = conv.get("history", []) or []
    negocio = gs.business_name(tienda_id)

    # ── 1. FUENTE ───────────────────────────────────────────────────────
    t = time.time()
    politicas = F.politicas_relevantes(raw_message, tienda_id)
    inventario = F.texto_inventario(tienda_id)
    envio = F.texto_envio(raw_message, conv.get("ultima_localidad") or "",
                          tienda_id)
    if envio.get("texto"):
        politicas = _sin_el_tema_del_envio(politicas)
    bloque = _bloque_fuente(politicas, inventario, envio.get("texto") or "")
    etapas["fuente"] = int((time.time() - t) * 1000)

    # ── 2. MODELO, QUE AHORA BUSCA EL ──────────────────────────────────
    #
    # LAS FICHAS YA NO LAS ELIGE EL CODIGO. Salen de lo que el modelo busco con
    # el motor. Es el cambio entero de la FICHA 50: el codigo no razona, asi
    # que no puede elegir que ponerle delante, y el catalogo entero no entra.
    t = time.time()
    salida, fichas, motor = await _preguntar(
        _prompt_sistema(negocio), _memoria_texto(conv), history, raw_message,
        bloque, trace_id, tienda_id)
    etapas["modelo"] = int((time.time() - t) * 1000)
    # EL NUMERO DEL MOTOR, UN RENGLON POR TURNO. Sale SIEMPRE, haya buscado o
    # no: un turno que no busco es un dato, no un hueco en la serie. Lo agrega
    # `banco_pruebas/produccion.py` sobre la ventana que se pida, asi que el
    # numero se lee desde el issue 31 sin entrar a la consola de nadie.
    log.info("motor_turno", trace_id=trace_id,
             vueltas=motor["vueltas"], llamadas=motor["llamadas"],
             consultas=motor["consultas"], repetidas=motor["repetidas"],
             veredictos=motor["veredictos"][:12], filas=motor["filas"],
             rescates=motor["rescates"], vacios=motor["vacios"],
             sin_dato=motor["sin_dato"], campos=motor["campos"][:8],
             fichas=motor["fichas"])
    if not motor["llamadas"]:
        # EL TERCER CANDADO DE LA FICHA 50: se mide cada turno que contesto sin
        # haber buscado. No se bloquea —la guarda de procedencia ya impide que
        # salga un numero que no vio—, se CUENTA, que es como sabemos si el
        # modelo usa el motor o lo esquiva.
        log.warning("turno_sin_buscar", trace_id=trace_id)

    texto = (salida.get("texto") or "").strip()
    if texto and not (salida.get("tipo") or "").strip():
        # EL TIPO VACIO NO TUMBA EL TURNO PERO SE CUENTA. Medido el 11-sep:
        # tres de seis turnos volvieron sin tipo, o sea que el modelo contesto
        # sin encasillar. El texto igual sale -el parseo tolera texto pelado-,
        # pero sin este renglon no habia forma de saber cuantas veces pasa.
        log.warning("tipo_vacio", trace_id=trace_id, largo=len(texto))
    if not texto:
        from app.core.guia_venta_prosa import mensaje as _prosa
        texto = _prosa("sobrecarga",
                       "Perdón, estoy con mucha demanda en este momento. "
                       "Probá de nuevo en un ratito y te respondo. 🙏")
        log.warning("respuesta_sin_modelo", trace_id=trace_id)
        informe = {}
    else:
        # ── 3. NUMEROS ──────────────────────────────────────────────────
        t = time.time()
        texto, informe = N.llenar(texto, fichas, trace_id,
                                  fuente_texto=bloque,
                                  envio_monto=envio.get("monto"))
        etapas["numeros"] = int((time.time() - t) * 1000)
        if informe.get("inventada"):
            # LA RESPUESTA CON PLATA INVENTADA NO SALE. No hay forma honesta de
            # corregirla renglon por renglon: el numero ya contamino la frase.
            texto = settings.VERIFIKA_FALLBACK_MESSAGE
        texto = gs.con_saludo_inicial(gs.sin_saludo_del_modelo(texto), negocio) \
            if not history else gs.sin_saludo_del_modelo(texto)

    # ── 4. CIERRE Y COBRO ───────────────────────────────────────────────
    t = time.time()
    texto, datos_cliente, cierre_hecho = await _cerrar(
        conv, user_id, canal, tienda_id, raw_message, texto, trace_id,
        _senal(salida.get("tipo") or "", raw_message))
    etapas["cierre"] = int((time.time() - t) * 1000)

    # ── 5. MEMORIA ──────────────────────────────────────────────────────
    t = time.time()
    history = history + [{"role": "user", "content": raw_message},
                         {"role": "assistant", "content": texto}]
    resumen = conv.get("summary", "") or ""
    viejos = history[:-(settings.HISTORY_LIMIT * 2)]
    if viejos:
        try:
            from app.core.memoria_larga import actualizar_resumen
            resumen = await actualizar_resumen(resumen, viejos, trace_id)
        except Exception as e:  # noqa: BLE001 — la memoria nunca tumba el turno
            log.warning("respuesta_memoria_error", trace_id=trace_id,
                        error=str(e)[:120])
    history = history[-(settings.HISTORY_LIMIT * 2):]
    vistos = list(conv.get("productos_vistos") or [])
    ids = {str(p.get("id")) for p in vistos}
    for f in fichas:
        if str(f.get("id")) not in ids:
            vistos.append({"id": f.get("id"), "nombre": f.get("nombre")})
    # EL DESTINO DE LA CHARLA LO ESCRIBE QUIEN LO RESOLVIO. Habia una SEGUNDA
    # resolucion aca -otra llamada a `geo`, con otro criterio que el del motor
    # de envio- y guardaba un codigo postal pelado. Ahora se guarda el destino
    # que cotizo de verdad, ya nombrado con la palabra: el turno siguiente lo
    # vuelve a clasificar sin depender de que el cliente lo repita.
    localidad = envio.get("destino") or conv.get("ultima_localidad") or ""
    try:
        save_conversation(user_id, history, resumen, tienda_id=tienda_id,
                          estado_conversacion="en_curso",
                          productos_vistos=vistos[-20:],
                          ultima_localidad=localidad or None,
                          datos_cliente_parciales=datos_cliente,
                          pregunta_cierre_hecha=cierre_hecho)
    except Exception as e:  # noqa: BLE001
        log.warning("respuesta_save_error", trace_id=trace_id, error=str(e)[:150])
    etapas["memoria"] = int((time.time() - t) * 1000)

    log.info("turno_ok", trace_id=trace_id,
             latency_ms=int((time.time() - t0) * 1000), etapas=etapas,
             tipo=salida.get("tipo") or "", largo=len(texto or ""),
             fichas=len(fichas), politicas=len(politicas),
             envio_destino=envio.get("destino") or "",
             envio_zona=envio.get("zona") or "",
             envio_monto=envio.get("monto"),
             huecos_llenos=len((informe or {}).get("llenos") or []),
             huecos_sin_dato=len((informe or {}).get("sin_dato") or []),
             plata_inventada=len((informe or {}).get("inventada") or []))
    return texto
