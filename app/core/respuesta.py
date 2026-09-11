"""EL TURNO, EN UNA SOLA LLAMADA. Desde el 11-sep-2026 este es el camino vivo.

QUE REEMPLAZA. A `turno.py` y a las ocho etapas: moldes, decisor con
herramientas, resolver, mesa, redactor, obligaciones. Todo eso esta apagado en
`archivo/apagado_11sep/`. No conviven: hay un solo camino.

EL FLUJO, entero:

  1. FUENTE   el codigo busca en el catalogo y en la FAQ con el mensaje del
              cliente, y se queda con lo poco que puede hacer falta.
  2. MODELO   UNA llamada. Ve la voz de la casa, la memoria de la charla, los
              VEINTE TIPOS con su molde de respuesta, y la fuente de arriba.
              Contesta con un tipo y un texto. El precio lo copia de la ficha;
              el envio y la suma van como hueco, porque no los sabe.
  3. NUMEROS  el codigo pone el envio y el total, y tira abajo la respuesta si
              quedo una sola cifra que la fuente no tiene.
  4. CIERRE   si el cliente decidio comprar, se toma el pedido y se manda el
              link de pago. `leads` y `cierre` no se tocaron.
  5. MEMORIA  se guarda la charla, igual que siempre.

POR QUE UNA SOLA LLAMADA. Tres llamadas por turno daban entre 4,4 y 5,8
segundos medidos y se comian la cuota diaria de a tres. Una sola con los veinte
moldes adentro pesa menos que la primera de las tres que habia.

DE DONDE SACA EL MODELO LA RESPUESTA, que es la pregunta que define todo esto:
de las fichas y las politicas que el codigo le pone delante en la etapa uno, y
de ningun otro lado. Por eso la ficha viaja con el precio ya escrito.

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

Los OTROS huecos del molde -{{producto}}, {{stock}}, {{opciones}} y los demas-
NO se copian: ahi va la palabra real, sacada de la ficha que tenes abajo.

SOLO EXISTE LO QUE ESTA EN LA FUENTE que te paso abajo. Si un producto no esta
en las fichas, no lo vendemos y se lo decis. Si un dato no esta en la ficha, no
lo tenemos y se lo decis. No completes con lo que sepas de esos productos.

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


def _bloque_fuente(fichas: list, politicas: list) -> str:
    partes = []
    if fichas:
        partes.append("FICHAS DEL CATALOGO, es todo lo que existe:\n"
                      + json.dumps(fichas, ensure_ascii=False))
    else:
        partes.append("FICHAS DEL CATALOGO: ninguna. El catalogo no tiene nada "
                      "que se parezca a lo que pregunto.")
    if politicas:
        partes.append("POLITICAS DE LA CASA que tocan este mensaje:\n"
                      + "\n".join(f"- {p['tema']}: {p['texto']}" for p in politicas))
    return "\n\n".join(partes)


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


async def _preguntar(sistema: str, memoria: str, history: list, mensaje: str,
                     fuente: str, trace_id: str) -> dict:
    from app.core.llm_reintento import _cliente, _modelo
    cli = _cliente()
    if cli is None:
        log.warning("respuesta_sin_clave", trace_id=trace_id)
        return {}
    msgs = [{"role": "system", "content": sistema}]
    if memoria:
        msgs.append({"role": "system", "content": memoria})
    for h in (history or [])[-(settings.HISTORY_LIMIT * 2):]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            msgs.append({"role": h["role"], "content": str(h["content"])[:900]})
    msgs.append({"role": "user",
                 "content": f"Mensaje del cliente: {mensaje}\n\n{fuente}"})

    def _call():
        r = cli.chat.completions.create(
            model=_modelo(), messages=msgs, temperature=0.3, max_tokens=900)
        return (r.choices[0].message.content or "") if r.choices else ""

    try:
        crudo = await llamar_con_reintento(
            _call, timeout_s=settings.LLM_TIMEOUT_SECONDS, trace_id=trace_id)
    except Exception as e:  # noqa: BLE001 — el turno no se rompe por el modelo
        log.warning("respuesta_modelo_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:150]}")
        return {}
    return _parsear(crudo)


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
    fichas = F.fichas_relevantes(raw_message, tienda_id)
    politicas = F.politicas_relevantes(raw_message, tienda_id)
    etapas["fuente"] = int((time.time() - t) * 1000)

    # ── 2. MODELO ───────────────────────────────────────────────────────
    t = time.time()
    salida = await _preguntar(_prompt_sistema(negocio), _memoria_texto(conv),
                              history, raw_message,
                              _bloque_fuente(fichas, politicas), trace_id)
    etapas["modelo"] = int((time.time() - t) * 1000)

    texto = (salida.get("texto") or "").strip()
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
        texto, informe = N.llenar(texto, fichas, raw_message, trace_id,
                                  politicas=politicas)
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
    localidad = conv.get("ultima_localidad") or ""
    try:
        from app.core.geo_cp import resolver as geo
        prov, cp = geo(raw_message)
        if prov or cp:
            localidad = str(cp or prov).replace("_", " ")
    except Exception as e:  # noqa: BLE001
        log.warning("respuesta_geo_error", trace_id=trace_id, error=str(e)[:120])
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
             huecos_llenos=len((informe or {}).get("llenos") or []),
             huecos_sin_dato=len((informe or {}).get("sin_dato") or []),
             plata_inventada=len((informe or {}).get("inventada") or []))
    return texto
