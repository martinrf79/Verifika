"""
HUB ATADO — el turno completo con los DOS atados y SIN la pila de guardas.

Camino:
  1. INTERPRETE (Gemini, schema estricto): entiende y devuelve datos.
  2. SOLVER (solver_gemini): LLAMA las tools de area; el dato duro sale de la
     tool, no de la cabeza del modelo.
  3. ESTAMPADO por codigo del numero sellado y el producto real.
  4. MEMORIA: se persiste el estado esencial para que la charla recuerde entre
     turnos (history, resumen largo, productos vistos, carrito, destinos,
     criterio, provincia).

NO corre ninguna de las ~40 guardas/parches de interprete_libre. Reusa solo las
funciones PURAS de estado y estampado. Es candidato a reemplazar interprete_libre
en el camino vivo una vez medido en la bateria; hoy convive solo para medirse,
el orchestrator sigue en interprete_libre hasta que el numero lo justifique.
"""
import re
import time

from app.core.interpretador import interpretar_mensaje
from app.core.pedido_helpers import _destinos_de_interp
from app.core.estado_venta import (
    construir_estado, set_current_estado,
    productos_de_meta, carrito_de_meta, envio_de_meta, merge_productos,
    detectar_criterio, criterio_del_interprete, get_envio_localidades)
from app.core.tools_context import set_current_tienda
from app.core.pedido_helpers import _presupuesto_de_meta
from app.config import get_settings
from app.logger import get_logger
from app.storage.firestore_client import (
    get_conversation, save_conversation, get_config, get_product_by_id)

log = get_logger(__name__)
settings = get_settings()

# El solver a veces FILTRA el id interno del catalogo en el texto al cliente
# ("Genius KB-110X (id: TEC0019)"). El cliente no debe verlo. Limpieza del
# estampado, no una guarda; lo ideal es que el prompt del solver no lo emita.
_RE_ID_FILTRADO = re.compile(
    r"[\s,]*\(\s*(?:(?:id|sku|codigo)\s*[:=]?\s*)?"
    r"[A-Z]{2,5}\d{2,}(?:\s*/\s*[A-Z]{2,5}\d{2,})*\s*\)"
    r"|[\s,]*\b(?:id|sku|codigo)\s*[:=]\s*[A-Z]{2,5}\d{2,}",
    re.IGNORECASE)
_RE_TOTAL = re.compile(r"[Tt]otal:\s*\$?\s*([\d.]+)")


def _tools_traza(meta) -> list[str]:
    """Resumen COMPACTO de las tools que llamo el solver, con el arg clave: es
    la costura donde se ve un envio sin cotizar o un producto equivocado que se
    le mando a la calculadora."""
    out: list[str] = []
    for tc in (meta or {}).get("tools_called", []) or []:
        n = tc.get("name")
        a = tc.get("args") or {}
        r = tc.get("result")
        if n == "cotizar_envio":
            costo = r.get("costo") if isinstance(r, dict) else None
            out.append(f"cotizar_envio(loc={a.get('localidad')},costo={costo})")
        elif n == "calculate_total":
            items = a.get("items") or []
            its = ",".join(f"{i.get('product_id')}x{i.get('cantidad')}"
                           for i in items if isinstance(i, dict))
            out.append(f"calculate_total([{its}])")
        else:
            out.append(str(n))
    return out


def _carrito_traza(carrito) -> list:
    return [(c.get("nombre"), c.get("cantidad"))
            for c in (carrito or []) if isinstance(c, dict)]


def _evidencia_del_texto(texto: str, meta: dict, estado: dict,
                         tienda_id: str, trace_id: str) -> list:
    """La EVIDENCIA del turno: tools llamadas, productos vistos releidos vivos,
    productos nombrados en el texto y la FAQ con sus valores. Es la fuente
    contra la que juzga TODA la red determinista de abajo.

    Se arma UNA sola vez y se comparte. Antes vivia adentro del verificador de
    montos, y cada verificador que se enchufaba la re-armaba: tres recorridas
    del catalogo por turno y, peor, tres versiones de "la verdad" que podian
    diferir entre si."""
    from app.core.evidencia import (build_evidence_from_tools,
                                    productos_nombrados_en)
    from app.storage.firestore_client import get_product_by_id
    vistos = []
    for p in (estado.get("productos_vistos") or []):
        if not isinstance(p, dict):
            continue
        vivo = None
        pid = str(p.get("id") or "").upper()
        if pid:
            try:
                vivo = get_product_by_id(pid, tienda_id=tienda_id)
            except Exception:
                vivo = None
        vistos.append(vivo if isinstance(vivo, dict) and vivo.get("precio_ars")
                      is not None else
                      {**p, "precio_ars": p.get("precio_ars", p.get("precio"))})
    evidencia = build_evidence_from_tools(
        meta.get("tools_called", []) or [], tienda_id, productos_vistos=vistos)
    _ids = {str(i.get("id") or "").upper() for i in evidencia
            if i.get("tipo") == "producto"}
    for pn in productos_nombrados_en(texto, tienda_id):
        if str(pn.get("id") or "").upper() not in _ids:
            evidencia.append({"tipo": "producto", **pn})
    for i in evidencia:
        if (i.get("tipo") == "producto" and i.get("precio_ars") is None
                and isinstance(i.get("precio"), (int, float))):
            i["precio_ars"] = i["precio"]
    return evidencia


def _verificar_montos(texto: str, evidencia: list, trace_id: str) -> str:
    """RED DE NUMEROS del camino atado. Hasta hoy el numero se protegia solo
    porque el CODIGO lo estampaba; al pasar la FAQ y la venta a redaccion del
    solver, el numero lo teje el LLM y necesita verificacion. Autocorrige
    cualquier cifra sin respaldo por el valor real de la fuente. Sin LLM,
    conservador: solo reemplaza lo inequivoco. Gateado por AUTOCORRIGE_MONTOS."""
    if not settings.AUTOCORRIGE_MONTOS:
        return texto
    try:
        from app.core.verificador import autocorregir_montos
        precios_validos = {int(i["precio_ars"]) for i in evidencia
                           if i.get("tipo") == "producto"
                           and isinstance(i.get("precio_ars"), (int, float))}
        fix = autocorregir_montos(texto, evidencia, trace_id,
                                  precios_validos=precios_validos)
        if fix.get("cambiada"):
            log.warning("hub_atado_monto_corregido", trace_id=trace_id,
                        correcciones=(fix.get("correcciones") or [])[:8])
            return fix.get("respuesta") or texto
    except Exception as e:
        log.warning("hub_atado_verificar_montos_error", trace_id=trace_id,
                    error=str(e)[:150])
    return texto


async def _verificar_stock(texto: str, evidencia: list, trace_id: str) -> str:
    """STOCK: el campo por donde se filtro la alucinacion real del 2-jul, cuando
    el solver invento un faltante ("DX-110 no tiene stock", falso) y upselleo a
    lo caro. Mismo patron que la plata, en tres escalones de dureza creciente:

      1. la CIFRA de unidades que contradice el catalogo se reescribe sola;
      2. la CONTRADICCION de texto ("no tiene stock" de uno que si tiene) no se
         arregla con un numero: se reescribe con una regla explicita;
      3. si despues de reescribir la mentira SIGUE ahi, se poda la linea. Y si
         ni podando queda algo decente, sale el fallback: preferimos un turno
         soso a decirle al cliente que no tenemos algo que si tenemos.

    Solo juzga productos cuyo stock REAL esta en la evidencia DE ESTE turno: el
    stock cambia, y un dato viejo no acusa a nadie.
    """
    if not evidencia:
        return texto
    try:
        from app.core.verificador_stock import (corregir_unidades_stock,
                                                detectar_stock_contradicho,
                                                instruccion_stock,
                                                cuarentena_stock)
        fix = corregir_unidades_stock(texto, evidencia)
        if fix["correcciones"]:
            log.warning("hub_atado_stock_cifra_corregida", trace_id=trace_id,
                        correcciones=fix["correcciones"][:8])
            texto = fix["respuesta"]
        contradicho = detectar_stock_contradicho(texto, evidencia)
        if not contradicho:
            return texto
        log.warning("hub_atado_stock_contradicho", trace_id=trace_id,
                    casos=contradicho[:6], respuesta_preview=texto[:200])
        # La reescritura va en SU PROPIO try. Si revienta -clave vencida,
        # timeout, provider caido- el turno NO se puede quedar con la mentira:
        # tiene que seguir de largo hasta la cuarentena determinista de abajo,
        # que no necesita modelo. Medido el 29-jul: con la clave de OpenAI
        # vencida esta llamada tiraba 401 y, atrapada por el try grande, el
        # "no tiene stock" falso salia intacto al cliente.
        try:
            from app.core.guardia_promesas import reescribir_con_reglas
            nueva = await reescribir_con_reglas(
                texto, instruccion_stock(contradicho), trace_id)
            if nueva:
                texto = nueva
        except Exception as e:
            log.warning("hub_atado_stock_reescritura_error", trace_id=trace_id,
                        error=f"{type(e).__name__}: {str(e)[:120]}")
        quedan = detectar_stock_contradicho(texto, evidencia)
        if not quedan:
            log.info("hub_atado_stock_reescrito", trace_id=trace_id)
            return texto
        poda = cuarentena_stock(texto, evidencia)
        if poda and not detectar_stock_contradicho(poda, evidencia):
            log.warning("hub_atado_stock_cuarentena", trace_id=trace_id,
                        casos=quedan[:6])
            return poda
        log.warning("hub_atado_stock_bloqueado", trace_id=trace_id,
                    casos=quedan[:6])
        return settings.VERIFIKA_FALLBACK_MESSAGE
    except Exception as e:
        log.warning("hub_atado_stock_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:140]}")
        return texto


def _verificar_faq_numerica(texto: str, evidencia: list, meta: dict,
                            trace_id: str) -> str:
    """Los numeros CHICOS de politica que el verificador de plata no mira: un
    "25% de descuento" cuando es 20, "24 cuotas" cuando son 6, "45 dias" cuando
    son de 2 a 7, "36 meses de garantia" cuando son 24. Mienten igual que un
    precio, y con la FAQ REDACTADA por el solver los teje el modelo.

    Corrige solo anclado al tema consultado este turno y con pool univoco; sin
    ancla clara marca y no toca, mismo criterio conservador que la plata."""
    if not evidencia:
        return texto
    try:
        from app.core.verificador_faq import (autocorregir_faq_numerica,
                                              temas_de_meta)
        fix = autocorregir_faq_numerica(
            texto, evidencia, temas_consultados=set(temas_de_meta(meta)),
            trace_id=trace_id)
        if fix["cambiada"] and fix["verificacion"]["ok"]:
            log.warning("hub_atado_faq_numerica_corregida", trace_id=trace_id,
                        correcciones=fix["correcciones"][:8])
            return fix["respuesta"]
        if not fix["verificacion"]["ok"]:
            log.warning("hub_atado_faq_numerica_sin_respaldo", trace_id=trace_id,
                        sin_respaldo=fix["verificacion"]["sin_respaldo"][:8],
                        respuesta_preview=texto[:200])
    except Exception as e:
        log.warning("hub_atado_faq_numerica_error", trace_id=trace_id,
                    error=str(e)[:150])
    return texto


def _verificar_intencion(texto: str, meta: dict, conv: dict, interp,
                         mensaje: str, tienda_id: str, trace_id: str) -> str:
    """ESTRUCTURA contra ESTRUCTURA, sin LLM: lo que el interprete leyo del
    cliente (exclusiones, tope) contra lo que la respuesta ofrece. Un producto
    de una marca u origen que el cliente EXCLUYO se saca quirurgico; ofrecer
    todo arriba del tope se marca, no se corrige, porque avisar puede ser venta
    legitima. Aguas arriba el filtro de universo ya lo previene: esta es la red
    para lo que no pasa por ese filtro."""
    try:
        from app.core.verificador_intencion import verificar_intencion
        from app.core.estado_venta import preferencias_actualizadas
        prefs = preferencias_actualizadas(
            conv.get("preferencias_cliente"), interp, mensaje)
        if not prefs:
            return texto
        vi = verificar_intencion(texto, meta, prefs, tienda_id)
        if vi["eventos"]:
            log.warning("hub_atado_intencion_fiscal", trace_id=trace_id,
                        eventos=vi["eventos"],
                        corrigio=vi["respuesta"] != texto)
            return vi["respuesta"]
    except Exception as e:
        log.warning("hub_atado_intencion_error", trace_id=trace_id,
                    error=str(e)[:150])
    return texto


def _verificar_cita(meta: dict, texto: str, trace_id: str) -> None:
    """CANDADO Y SONDA de la cita de prosa: cada bloque de criterio que el
    solver dice haber usado tiene que existir de verdad en el corpus jurado.
    No reescribe nada -la prosa buena sale igual-, solo loguea: en el camino
    sano los ids salen del propio corpus y siempre validan, asi que un rojo aca
    significa que el contrato se rompio."""
    try:
        from app.core.verificador_cita import verificar_meta
        vc = verificar_meta(meta)
        if vc["citas"]:
            (log.warning if not vc["ok"] else log.info)(
                "hub_atado_cita_prosa", trace_id=trace_id,
                validas=vc["validas"], invalidas=vc["invalidas"])
    except Exception as e:
        log.warning("hub_atado_cita_error", trace_id=trace_id,
                    error=str(e)[:150])


async def _guardia_promesas(texto: str, trace_id: str) -> str:
    """LINEA CERO DEL TEXTO: un conjunto cerrado de promesas que el bot no puede
    hacer aunque el cliente insista -dia exacto de entrega, retiro en local,
    servicios fuera de la FAQ-. La deteccion es determinista; solo los turnos
    que disparan pagan una llamada de reescritura. Si la reescritura no limpia,
    se poda por codigo."""
    if not texto or texto == settings.VERIFIKA_FALLBACK_MESSAGE:
        return texto
    try:
        from app.core.guardia_promesas import (detectar, reescribir_sin_promesas,
                                               cuarentena_prohibidas)
        clases = detectar(texto)
        if not clases:
            return texto
        log.warning("hub_atado_promesa_prohibida", trace_id=trace_id,
                    clases=clases, respuesta_preview=texto[:200])
        nueva = ""
        try:
            nueva = await reescribir_sin_promesas(texto, clases, trace_id)
        except Exception as e:
            log.warning("hub_atado_promesa_reescritura_error", trace_id=trace_id,
                        error=str(e)[:120])
        if nueva and not detectar(nueva):
            return nueva
        poda = cuarentena_prohibidas(nueva or texto)
        if poda and not detectar(poda):
            log.warning("hub_atado_promesa_cuarentena", trace_id=trace_id,
                        clases=clases)
            return poda
        # TERCER ESCALON, el que faltaba. Si el mensaje ENTERO era la promesa
        # -"te llega el martes sin falta"- la poda no deja nada en pie, y hasta
        # recien eso devolvia el texto original CON la promesa adentro. Un turno
        # soso es mucho mejor que prometerle al cliente un dia de entrega que no
        # podemos cumplir. Mismo criterio que el escalon final de stock.
        log.warning("hub_atado_promesa_bloqueada", trace_id=trace_id,
                    clases=clases)
        return settings.VERIFIKA_FALLBACK_MESSAGE
    except Exception as e:
        log.warning("hub_atado_promesa_error", trace_id=trace_id,
                    error=str(e)[:150])
    return texto


async def _red_de_verificadores(texto: str, meta: dict, estado: dict, conv: dict,
                                universo, interp, mensaje: str, tienda_id: str,
                                trace_id: str) -> str:
    """LA RED, en un solo lugar y en un solo orden.

    Hasta el 29-jul el camino vivo corria UNA sola de estas: la de montos. Las
    otras cinco estaban escritas y no las llamaba nadie -quedaron huerfanas al
    pasar el orchestrator de `interprete_libre` al hub-, asi que en produccion
    no habia nada mirando stock, numeros de politica, citas, exclusiones del
    cliente, promesas prohibidas ni prosa.

    El ORDEN no es casual, va de lo mas duro a lo mas blando y cada escalon
    entrega su salida al siguiente:
      1. montos      dato duro, determinista, corrige con la fuente
      2. stock       dato duro, determinista + reescritura si hace falta
      3. faq numerica  dato duro chico, determinista
      4. intencion   estructura contra estructura, sin LLM
      5. cita        candado del corpus, solo loguea
      6. promesas    lista cerrada de lo que no se puede prometer
      7. el JUEZ     lo blando, lo unico que necesita un modelo
    Asi el juez recibe un texto con TODO el dato duro ya auditado y se ocupa
    solo de lo que ninguna regla puede chequear. Ninguno rompe el turno: cada
    uno degrada a devolver el texto que recibio.
    """
    if not texto or texto == settings.VERIFIKA_FALLBACK_MESSAGE:
        return texto
    try:
        evidencia = _evidencia_del_texto(texto, meta, estado, tienda_id, trace_id)
    except Exception as e:
        log.warning("hub_atado_evidencia_error", trace_id=trace_id,
                    error=str(e)[:150])
        evidencia = []
    texto = _verificar_montos(texto, evidencia, trace_id)
    texto = await _verificar_stock(texto, evidencia, trace_id)
    texto = _verificar_faq_numerica(texto, evidencia, meta, trace_id)
    texto = _verificar_intencion(texto, meta, conv, interp, mensaje, tienda_id,
                                 trace_id)
    _verificar_cita(meta, texto, trace_id)
    texto = await _guardia_promesas(texto, trace_id)
    return await _fiscalizar_prosa(texto, meta, universo, interp, mensaje,
                                   tienda_id, trace_id)


def _evidencia_del_turno(meta: dict, universo, interp, mensaje, tienda_id,
                         trace_id) -> None:
    """Carga en `meta` TODO lo que el codigo le paso al solver este turno, para
    que el juez de abajo mire exactamente la misma evidencia.

    Esto es lo que hace que el juez sirva. Un juez con menos evidencia que el
    redactor no detecta alucinacion: PODA prosa fundada, que es peor. Por eso no
    se recupera nada nuevo aca -no es una busqueda propia del fiscal- sino que se
    llama a las MISMAS funciones de `generador_v2` con las MISMAS entradas. Son
    deterministas, asi que devuelven el mismo paquete que armo el prompt.

    Las fichas de los productos y la FAQ que el modelo SI emitio ya viajan en
    `meta['tools_called']` desde `renderizar`. Lo que falta, y es justo lo que
    hace podar de mas, es el grounding que el modelo tuvo delante y no cito.
    """
    import re as _re
    from app.core import generador_v2
    try:
        _ids, menu = generador_v2._criterios_del_turno(mensaje, universo, interp)
        ya = {t.get("id") for t in (meta.get("prosa_evidencia") or [])}
        bloques = []
        for linea in (menu or "").split("\n"):
            m = _re.match(r"\s*\[([^\]]+)\]\s*(.+)", linea)
            if m and m.group(1) not in ya:
                bloques.append({"id": m.group(1), "texto": m.group(2)})
        if bloques:
            meta["prosa_evidencia"] = (meta.get("prosa_evidencia") or []) + bloques
    except Exception as e:
        log.warning("hub_atado_evidencia_criterio_error", trace_id=trace_id,
                    error=str(e)[:120])
    try:
        menu_faq, _temas = generador_v2._faq_del_turno(mensaje, interp, tienda_id)
        bloques = []
        for linea in (menu_faq or "").split("\n"):
            m = _re.match(r"\s*\[([^\]]+)\]\s*(.+)", linea)
            if m:
                bloques.append({"tema": m.group(1), "texto": m.group(2)})
        if bloques:
            meta["faq_evidencia"] = bloques
    except Exception as e:
        log.warning("hub_atado_evidencia_faq_error", trace_id=trace_id,
                    error=str(e)[:120])


async def _fiscalizar_prosa(texto: str, meta: dict, universo, interp,
                            mensaje: str, tienda_id: str, trace_id: str) -> str:
    """EL JUEZ. Lo unico que puede chequear la mitad blanda de la respuesta.

    El codigo ata el dato duro: el precio, el stock y la spec los estampa la
    fuente y el verificador de montos los audita. Pero "es ideal para gaming" o
    "te sirve para esa notebook" no tienen numero que auditar, y hasta hoy salian
    sin que nada los mirara. Un modelo chico SI puede juzgarlo -chequear es mucho
    mas facil que redactar- contra la evidencia del turno.

    El reparto de poder no cambia: el juez OPINA con veredicto atado por enum, el
    CODIGO decide. Una afirmacion sin respaldo se poda solo si aparece como
    oracion completa, no tiene digitos (esos ya los goberno el verificador de
    plata) y no es una frase de honestidad. Lo demas queda MARCADO en el log, que
    es el radar. Ante error, timeout o falta de clave, no-op: el turno sale igual.

    Estaba escrito desde el 17-jul y no lo llamaba nadie: quedo huerfano cuando
    el orchestrator paso de `interprete_libre` al hub.
    """
    if not texto or texto == settings.VERIFIKA_FALLBACK_MESSAGE:
        return texto
    try:
        from app.core.checker_afirmaciones import (chequear, podar_sin_respaldo,
                                                   rewrite_segura)
        _evidencia_del_turno(meta, universo, interp, mensaje, tienda_id, trace_id)
        chk = await chequear(texto, meta, tienda_id, trace_id)
        if not chk:
            return texto
        if not chk["sin_respaldo"]:
            log.info("hub_atado_juez_ok", trace_id=trace_id,
                     afirmaciones=len(chk["afirmaciones"]))
            return texto
        # CRITICO-REESCRITOR: la misma llamada ya trajo la version corregida. Se
        # usa si pasa la red de codigo (no inventa numeros ni marcadores, no deja
        # muñon); si no, se cae a la poda determinista. Cero llamada extra.
        reescrita = rewrite_segura(texto, chk.get("corregida") or "")
        if reescrita and reescrita != texto:
            log.info("hub_atado_juez_reescribio", trace_id=trace_id,
                     sin_respaldo=chk["sin_respaldo"][:6])
            return reescrita
        nuevo, podadas = podar_sin_respaldo(texto, chk["sin_respaldo"])
        log.warning("hub_atado_juez_sin_respaldo", trace_id=trace_id,
                    sin_respaldo=chk["sin_respaldo"][:6], podadas=len(podadas))
        return nuevo
    except Exception as e:
        log.warning("hub_atado_juez_error", trace_id=trace_id,
                    error=f"{type(e).__name__}: {str(e)[:120]}")
        return texto


async def _aplicar_cierre(conv, user_id, canal, tienda_id, raw_message, texto,
                          trace_id, interp, present):
    """Cablea el CIERRE y COBRO al hub reusando la MISMA funcion del camino vivo
    (leads.procesar_mensaje_para_lead), no la duplica: entrega los datos de pago
    cuando el cliente los pide, capta el lead en la decision de compra y hace la
    pregunta suave de cierre. Arma los mismos insumos que interprete_libre. Devuelve
    (texto posiblemente pisado por el cierre, datos acumulados, flag de pregunta de
    cierre, presupuesto string) para persistir."""
    from app.core.leads import procesar_mensaje_para_lead
    presupuesto = present or (conv.get("ultimo_presupuesto") or "")
    presupuesto_nuevo = bool(present)
    _intent = interp.get("intencion") if isinstance(interp, dict) else None
    datos_previos = conv.get("datos_cliente_parciales") or {}
    datos_turno: dict = {}
    try:
        from app.core.cierre import extraer_determinista, extraer_datos_cliente
        from app.core.pedido_helpers import _parece_aportar_dato
        datos_turno.update(extraer_determinista(raw_message))
        if (_intent in ("aporta_dato", "decision_compra")
                or _parece_aportar_dato(raw_message)):
            for k, v in extraer_datos_cliente(raw_message, trace_id).items():
                if v:
                    datos_turno[k] = v
    except Exception as e:
        log.warning("hub_atado_extractor_error", trace_id=trace_id,
                    error=str(e)[:120])
    datos_acumulados = {**datos_previos, **datos_turno}
    pregunta_cierre_previa = bool(conv.get("pregunta_cierre_hecha"))
    meta_lead: dict = {}
    # No se cierra sobre el fallback: no hay respuesta real que confirmar. PERO el
    # PEDIDO DE COBRO ("pasame los datos/enlaces para pagar") es determinista y NO
    # depende del solver: el solver atado no tiene fragmento para el cobro y cae al
    # fallback, y ahi se perdia la entrega del CBU/link (bug real, guion 48 T3 por
    # el flujo atado). Si el cliente pide el cobro, se corre igual y la entrega
    # reemplaza al fallback.
    from app.core.leads import _RE_PIDE_COBRO
    _pide_cobro = bool(_RE_PIDE_COBRO.search(raw_message or ""))
    if (texto and texto != settings.VERIFIKA_FALLBACK_MESSAGE) or _pide_cobro:
        try:
            _, meta_lead = await procesar_mensaje_para_lead(
                user_id, canal, tienda_id, raw_message, texto, trace_id,
                interpretacion=interp if isinstance(interp, dict) else None,
                presupuesto=presupuesto, datos_turno=datos_turno,
                datos_previos=datos_acumulados,
                presupuesto_nuevo=presupuesto_nuevo,
                pregunta_cierre_hecha=pregunta_cierre_previa)
            rd = meta_lead.get("respuesta_directa")
            if rd:
                # CONTINUIDAD: el cierre se SUMA a la respuesta del solver, no la
                # reemplaza (antes el enlatado pisaba la respuesta y se comia la
                # pregunta que venia en el mismo mensaje: T3 "sirve para PS5", T9
                # "confirmame que va a cada ciudad"). PERO el path pregunta_suave
                # arma respuesta_directa = respuesta_solver + pregunta, o sea ya
                # trae el cuerpo entero: sumarlo duplicaba TODA la respuesta
                # (banco guion 59 T2 y 60 T2). Si rd ya reconstruyo el cuerpo, se
                # REEMPLAZA; si aporta solo su parte (datos de pago, linea de
                # cierre), se SUMA. Sin cuerpo sustancial, rd manda.
                base = (texto or "").strip()
                rd_s = rd.strip()
                sustancial = base and base != settings.VERIFIKA_FALLBACK_MESSAGE
                if not sustancial:
                    texto, modo = rd_s, "reemplazo"
                elif base[:80] and base[:80] in rd_s:
                    texto, modo = rd_s, "reemplazo_dedup"
                else:
                    texto, modo = base + "\n\n" + rd_s, "suma"
                log.info("hub_atado_cierre", trace_id=trace_id,
                         accion=meta_lead.get("accion"), modo=modo)
        except Exception as e:
            log.warning("hub_atado_lead_error", trace_id=trace_id,
                        error=str(e)[:160])
    pregunta_cierre_hecha = (meta_lead.get("accion")
                             in ("pregunta_cierre", "pregunta_pendiente_cierre"))
    return texto, datos_acumulados, pregunta_cierre_hecha, presupuesto


async def procesar_atado(user_id: str, raw_message: str, tienda_id: str,
                         canal: str, trace_id: str) -> str:
    """Un turno del bot por el flujo atado. Devuelve el texto para el cliente."""
    t0 = time.time()
    conv = get_conversation(user_id, tienda_id=tienda_id)
    history = conv.get("history", []) or []
    estado_anterior = conv.get("estado_conversacion", "saludo") or "saludo"

    estado = construir_estado(conv, None)
    from app.core.envio import clasificar_provincia
    _prov_msg = clasificar_provincia(raw_message) or ""
    if _prov_msg:
        estado["provincia_envio"] = _prov_msg
    set_current_tienda(tienda_id)
    set_current_estado(estado)

    # ── INTERPRETE ──────────────────────────────────────────────────────
    resumen = estado.get("resumen_charla") or ""
    interp = await interpretar_mensaje(
        raw_message, history, trace_id, estado_anterior=estado_anterior,
        tienda_id=tienda_id, productos_vistos=estado.get("productos_vistos"),
        resumen=resumen)
    estado_nuevo = (interp.get("estado_conversacion") or estado_anterior
                    if isinstance(interp, dict) else estado_anterior)
    log.info("hub_atado_interp", trace_id=trace_id,
             intencion=interp.get("intencion"),
             producto=interp.get("producto_resuelto"),
             consultados=interp.get("productos_consultados"))

    # El anclado del pedido, la categoria pedida no mostrada y los consultados
    # ya NO viajan como guia de texto al solver: generador_v2 los ata por
    # construccion al armar el universo del turno desde los campos estructurados
    # del interprete (universo_productos consume solicitud_nueva, pedido y
    # productos_consultados). Un solo mecanismo de atadura, el enum, no dos.

    # ── SOLVER ATADO POR ENUM: generador_v2 (salida estructurada) ───────
    # El modelo emite FRAGMENTOS atados a enums de la fuente -ids del universo
    # del turno, temas de FAQ, bloques de criterio- por responseSchema strict,
    # el MISMO mecanismo que el interprete. El CODIGO estampa cada dato al
    # renderizar: precio, stock, total NACEN de la fuente, no del modelo.
    # Reemplaza al solver de prosa libre, cuya salida sin schema dejaba pasar la
    # alucinacion (stock inventado, banco guion 59). renderizar ya devuelve el
    # texto final estampado; el unico texto libre es el pegamento, podado de dato.
    from app.core import generador_v2
    _primer_turno = not (estado.get("productos_vistos") or estado.get("carrito"))
    frags, universo, presu_txt, presu_tools, respuestas_cat = \
        await generador_v2.generar_fragmentos(
            raw_message, history, estado, tienda_id, interp, trace_id)
    if frags:
        texto, _tools_called = generador_v2.renderizar(
            frags, universo, estado, tienda_id, trace_id,
            presupuesto_pre=presu_txt, presupuesto_tools=presu_tools,
            mensaje=raw_message, primer_turno=_primer_turno,
            respuestas_cat=respuestas_cat)
        meta = {"tools_called": _tools_called, "secciones": [],
                "prosa_citada": [], "turno_criterio": False}
        log.info("hub_atado_generador_v2", trace_id=trace_id,
                 fragmentos=len(frags), tools=len(_tools_called))
    else:
        texto, meta = settings.VERIFIKA_FALLBACK_MESSAGE, {"tools_called": []}
        log.warning("hub_atado_generador_v2_sin_fragmentos", trace_id=trace_id)

    # ── GARANTIA del "no" honesto (categoria no vendida, fuente no_vendidas.json).
    # El solver ya ofrece la alternativa real (nota + universo), pero el "no" no
    # puede depender de que el modelo lo diga: el CODIGO lo estampa al frente si el
    # texto no declino claro. La CASUISTICA vive en config; esto es el mecanismo.
    try:
        from app.core.guia_compra import categoria_no_vendida
        _cnv = categoria_no_vendida(raw_message, tienda_id)
        _declina = any(k in (texto or "").lower() for k in
                       ("no vend", "no trabaj", "no manej", "no tenemos",
                        "no lo tenemos", "no contamos", "no comerci",
                        "no ofrecemos", "no dispon"))
        if _cnv and not _declina:
            texto = (f"Te soy honesto: {_cnv[0]} no trabajamos, nuestro rubro es "
                     f"tecnología e informática.\n\n" + (texto or "")).strip()
            log.info("hub_atado_no_vendida_estampada", trace_id=trace_id,
                     pedida=_cnv[0])
    except Exception as e:
        log.warning("hub_atado_no_vendida_error", trace_id=trace_id,
                    error=str(e)[:120])

    # ── HONESTIDAD DE SPEC (fuente specs_preguntables.json): si el cliente
    # pregunto una spec que la ficha NO trae, el CODIGO saca la afirmacion del
    # modelo y estampa "la ficha no lo especifica". El producto en cuestion sale
    # del que el interprete resolvio o del unico mostrado este turno.
    try:
        from app.core.generador_v2 import estampar_honestidad_specs
        from app.core.pedido_helpers import certificar_producto
        _prod_spec, _variantes = None, []
        # el FOCO del turno: lo que el interprete resolvio o lo que el cliente
        # pregunto. Antes solo servia un producto UNICO y, como el catalogo
        # tiene variantes de color y de CPU, casi nunca habia uno solo: el
        # guardia no corria nunca y el modelo contestaba la spec por su cuenta.
        _nombres = []
        if isinstance(interp, dict):
            if interp.get("producto_resuelto"):
                _nombres.append(str(interp["producto_resuelto"]))
            _nombres += [str(c.get("producto")) for c in
                         (interp.get("productos_consultados") or [])
                         if isinstance(c, dict) and c.get("producto")]
        if _nombres:
            from app.storage.firestore_client import get_all_products
            _todos = get_all_products(tienda_id=tienda_id)
            for _n in _nombres:
                _v, _hits = certificar_producto(_n, _todos)
                if _hits:
                    _variantes, _prod_spec = _hits, _hits[0]
                    break
        if not _prod_spec:
            _sh = productos_de_meta(meta)
            if len(_sh) == 1 and _sh[0].get("id"):
                _prod_spec = get_product_by_id(str(_sh[0]["id"]).upper(),
                                               tienda_id=tienda_id)
                _variantes = [_prod_spec] if _prod_spec else []
        if isinstance(_prod_spec, dict):
            _antes_sp = texto
            # las specs que preguntó el cliente las TRADUJO el interprete al
            # enum de la fuente; el regex sobre el mensaje queda solo de red.
            _decl = (interp.get("specs_preguntadas")
                     if isinstance(interp, dict) else None)
            texto = estampar_honestidad_specs(texto, raw_message, _prod_spec,
                                              _variantes, _decl)
            if texto != _antes_sp:
                log.info("hub_atado_spec_honesta", trace_id=trace_id,
                         producto=_prod_spec.get("nombre"),
                         variantes=len(_variantes), declaradas=_decl)
    except Exception as e:
        log.warning("hub_atado_spec_error", trace_id=trace_id,
                    error=str(e)[:120])

    # ── El dato ya lo estampo renderizar desde la fuente. Aca solo se leen el
    # presupuesto y los productos mostrados para el cierre y la memoria; NO se
    # re-inyecta (renderizar no deja marcadores [[PROD]] ni [[PRESUPUESTO]]).
    present = presu_txt or _presupuesto_de_meta(meta)
    ids_mostrados = [str(p.get("id")).upper()
                     for p in productos_de_meta(meta) if p.get("id")]
    texto = _RE_ID_FILTRADO.sub("", texto).strip()

    # ── CIERRE Y COBRO ──────────────────────────────────────────────────
    # Reusa la logica del camino vivo: entrega datos de pago a pedido, capta el
    # lead en la decision de compra, pregunta suave de cierre. Puede pisar el
    # texto (ej "pasame los datos para transferir" -> CBU + link). Corre sobre el
    # texto YA estampado y antes de guardarlo en la memoria.
    texto, datos_cli_parciales, pregunta_cierre_hecha, presupuesto_str = \
        await _aplicar_cierre(conv, user_id, canal, tienda_id, raw_message, texto,
                              trace_id, interp, present)

    # ── RED DE NUMEROS: verificacion de montos contra la fuente ─────────
    # Ahora que la FAQ y la venta las REDACTA el solver, el numero lo teje el LLM
    # y se chequea aca contra la evidencia del turno (antes se protegia solo por
    # el estampado). Determinista, conservador: corrige lo inequivoco.
    # La red entera, en orden de dureza: montos, stock, FAQ numerica,
    # intencion, cita, promesas y el juez. Antes del dedup y de la memoria,
    # para que lo que se guarda sea exactamente lo que se manda.
    texto = await _red_de_verificadores(texto, meta, estado, conv, universo,
                                        interp, raw_message, tienda_id, trace_id)

    # ── FILTRO ANTI-DUPLICADO (refuerzo final, determinista) ────────────
    # Ultima red antes de mandar y de guardar en memoria: saca cualquier
    # duplicado exacto y contiguo que se haya colado en algun paso. Conservador,
    # no toca lo legitimo.
    from app.core.dedup import deduplicar_respuesta
    _antes = texto
    texto = deduplicar_respuesta(texto)
    if texto != _antes:
        log.info("hub_atado_dedup", trace_id=trace_id,
                 quito=len(_antes) - len(texto))

    # ── MEMORIA ─────────────────────────────────────────────────────────
    history = history + [
        {"role": "user", "content": raw_message},
        {"role": "assistant", "content": texto}]
    resumen_charla = conv.get("summary", "") or ""
    descartados = history[:-(settings.HISTORY_LIMIT * 2)]
    if descartados:
        try:
            from app.core.memoria_larga import actualizar_resumen
            resumen_charla = await actualizar_resumen(
                resumen_charla, descartados, trace_id)
        except Exception as e:
            log.warning("hub_atado_memoria_error", trace_id=trace_id,
                        error=str(e)[:120])
    history = history[-(settings.HISTORY_LIMIT * 2):]

    mostrados: list[dict] = []
    for pid in {i.upper() for i in ids_mostrados}:
        try:
            pp = get_product_by_id(pid, tienda_id=tienda_id)
        except Exception:
            pp = None
        if (isinstance(pp, dict) and pp.get("nombre")
                and isinstance(pp.get("precio_ars"), (int, float))):
            mostrados.append({"id": pid, "nombre": pp["nombre"],
                              "precio": int(pp["precio_ars"])})
    productos_vistos = merge_productos(
        conv.get("productos_vistos") or [], productos_de_meta(meta) + mostrados)
    _intent = interp.get("intencion") if isinstance(interp, dict) else None
    carrito_vigente = ((carrito_de_meta(meta) if _intent not in ("otra",) else [])
                       or (conv.get("carrito_vigente") or []))
    ultima_localidad = envio_de_meta(meta) or (conv.get("ultima_localidad") or "")
    ultimas_localidades = get_envio_localidades() or (
        conv.get("ultimas_localidades") or [])
    criterio_cliente = (
        detectar_criterio(raw_message)
        or ("más barato" if criterio_del_interprete(interp) else "")
        or (conv.get("criterio_cliente") or ""))
    provincia_envio = _prov_msg or (conv.get("provincia_envio") or "")

    # MEMORIA STICKY que el camino viejo persistia y el atado NO estaba
    # guardando (27-jul): al pasar produccion al hub, estas tres se leian en
    # construir_estado pero nunca se escribian, asi que se perdian TODOS los
    # turnos. Eran memoria muerta:
    #   - preferencias: "no quiero de China", tope de plata, uso previsto. El
    #     generador filtra el universo con ellas; sin persistir, valian un turno.
    #   - producto_anotado: el ancla de "me gusta ese, anotalo", que resuelve
    #     "el que te dije al principio".
    #   - grupos_envio: que item va a cada destino, que usa el reprecio del cierre.
    try:
        from app.core.estado_venta import (producto_anotado_actualizado,
                                           preferencias_actualizadas,
                                           get_current_estado)
        from app.storage.firestore_client import get_all_products
        producto_anotado = producto_anotado_actualizado(
            conv.get("producto_anotado"), interp, raw_message,
            get_all_products(tienda_id=tienda_id))
        preferencias_cliente = preferencias_actualizadas(
            conv.get("preferencias_cliente"), interp, raw_message)
        grupos_envio = ((get_current_estado() or {}).get("grupos_envio")
                        or conv.get("grupos_envio") or [])
        if preferencias_cliente != (conv.get("preferencias_cliente") or {}):
            log.info("hub_atado_preferencias", trace_id=trace_id,
                     preferencias=preferencias_cliente)
    except Exception as e:
        log.warning("hub_atado_sticky_error", trace_id=trace_id,
                    error=str(e)[:150])
        producto_anotado = conv.get("producto_anotado") or {}
        preferencias_cliente = conv.get("preferencias_cliente") or {}
        grupos_envio = conv.get("grupos_envio") or []

    try:
        save_conversation(
            user_id, history, resumen_charla, tienda_id=tienda_id,
            estado_conversacion=estado_nuevo,
            productos_vistos=productos_vistos, carrito_vigente=carrito_vigente,
            ultima_localidad=ultima_localidad,
            ultimas_localidades=ultimas_localidades,
            criterio_cliente=criterio_cliente, provincia_envio=provincia_envio,
            datos_cliente_parciales=datos_cli_parciales,
            pregunta_cierre_hecha=pregunta_cierre_hecha,
            ultimo_presupuesto=(presupuesto_str or None),
            producto_anotado=producto_anotado,
            preferencias_cliente=preferencias_cliente,
            grupos_envio=grupos_envio)
    except Exception as e:
        log.warning("hub_atado_save_error", trace_id=trace_id, error=str(e)[:150])

    # ── TRAZA POR COSTURA (modalidad de diagnostico) ────────────────────
    # UNA linea por turno con el dato en cada juntura del flujo, para ver de una
    # DONDE se corto: que leyo el interprete, si viajo la guia, que tools llamo
    # el solver y con que, el total que quedo sellado, y el carrito antes->despues.
    _tot = _RE_TOTAL.search(texto or "")
    log.info("hub_atado_traza", trace_id=trace_id,
             # 1. INTERPRETE
             i_intencion=interp.get("intencion"),
             i_producto=interp.get("producto_resuelto"),
             i_consultados=[c.get("producto")
                            for c in (interp.get("productos_consultados") or [])
                            if isinstance(c, dict)],
             i_pedido=[(it.get("producto"), it.get("cantidad"),
                        it.get("destino"))
                       for it in (interp.get("pedido") or [])
                       if isinstance(it, dict)],
             i_criterio=interp.get("criterio"),
             i_orden=interp.get("orden"),
             i_specs=interp.get("specs_preguntadas"),
             i_categorias=interp.get("categorias"),
             # 2. SEÑALES DE ATADURA que alimentan el ENUM del universo
             i_solicitud_nueva=[s.get("categoria")
                                for s in (interp.get("solicitud_nueva") or [])
                                if isinstance(s, dict)],
             destinos_forzados=_destinos_de_interp(interp),
             # 3. SOLVER: tools que llamo, con el arg clave
             tools=_tools_traza(meta),
             # 4. SELLADO
             total_sellado=(_tot.group(1) if _tot else None),
             # 5. MEMORIA: carrito antes -> despues
             carrito_prev=_carrito_traza(conv.get("carrito_vigente")),
             carrito_nuevo=_carrito_traza(carrito_vigente))

    log.info("hub_atado_ok", trace_id=trace_id,
             latency_ms=int((time.time() - t0) * 1000),
             tools=len((meta or {}).get("tools_called", [])))
    return texto
