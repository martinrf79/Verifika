"""EL TURNO — el agente busca, el codigo certifica, cierra y recuerda (26-sep-2026).

QUE REEMPLAZA. Al turno del interprete de la ficha 58: una llamada que
traducia el mensaje a una ficha, el codigo que compilaba y el motor que
buscaba una vez, con el redactor detras. Medido en el banco —fichas 59 a 62—,
el modelo parte y resuelve la memoria de cabeza y se equivocaba al escribir un
esquema grande; ahora busca solo con herramientas chicas. Todo eso vive en
`app/core/agente.py`. No conviven: el interprete se borro en este commit.

EL FLUJO, entero:
  1. TABLERO  `tablero.turno`, desde el 30-sep: el modelo parte el mensaje en
              piezas, el codigo corre las herramientas del agente —buscar,
              producto, envio, politica, compatibilidad, cuenta, reservar— y
              un redactor contesta solo con lo que volvio. FICHA 65.
  2. NUMEROS  la guarda de procedencia de siempre: si quedo una cifra de plata
              que ninguna herramienta devolvio, la respuesta no sale.
  3. CIERRE   si el cliente decidio comprar, se toma el pedido y se manda el
              link de pago. `leads` y `cierre` no se tocaron.
  4. MEMORIA  se guarda la charla, lo que el cliente vio y el ultimo
              presupuesto, igual que siempre.

LO QUE EL MODELO NO PUEDE HACER, y lo garantiza el codigo, no el prompt:
escribir una cifra que no salio de una herramienta, afirmar la identidad de un
producto que el motor no certifico, e inventar una politica de la casa.
"""
import json
import re
import time

from app.config import get_settings
from app.core import numeros as N
from app.logger import get_logger
from app.storage.firestore_client import get_conversation, save_conversation

log = get_logger(__name__)
settings = get_settings()


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
    vistos = conv.get("productos_vistos") or []
    ultimo = max((int(p.get("turno") or 0) for p in vistos), default=0)
    recien = [p for p in vistos if ultimo and int(p.get("turno") or 0) == ultimo]
    if recien:
        # "EL SEGUNDO", "EL MAS BARATO DE ESOS", "ESE". Es lo que nombro tu
        # ultimo mensaje, numerado en el orden en que el cliente lo leyo, que
        # es el unico orden al que el cliente se puede referir.
        #
        # UN MODELO EN DOS COLORES ES UN RENGLON, porque asi lo lee el cliente:
        # "el G203 en negro o blanco" es UNA opcion. Numerados por separado,
        # "el segundo" caia en el G203 blanco y no en el G502 —medido en la
        # tanda de charlas del 22-sep, CH2—.
        grupos: list = []
        for p in recien:
            clave = p.get("grupo") or p.get("modelo") or p.get("id")
            if grupos and grupos[-1][0] == clave:
                grupos[-1][1].append(p)
            elif any(g[0] == clave for g in grupos):
                next(g for g in grupos if g[0] == clave)[1].append(p)
            else:
                grupos.append((clave, [p]))
        partes.append(
            "LO QUE NOMBRASTE EN TU ULTIMO MENSAJE, en el orden en que el "
            "cliente lo leyo. 'El segundo' es el 2; 'ese', 'lo', 'el mismo' "
            "o 'esos' es esto, y 'de esos' se elige ENTRE ESTOS, no en el "
            "catalogo:\n"
            + "\n".join(
                f"{n}. " + " / ".join(
                    f"{p.get('id')}: {p.get('nombre')}"
                    + (f", {p['precio']}" if p.get("precio") else "")
                    + (RESPUESTA if p.get("respuesta") else "")
                    for p in ps)
                for n, (_c, ps) in enumerate(grupos[:8], 1)))
        vistos = [p for p in vistos if p not in recien]
    if vistos:
        # CON ID Y CON PRECIO, y las dos cosas por un caso medido.
        #
        # EL 12-SEP A LAS 00:06 y a las 00:08 el bot le contesto DOS VECES
        # seguidas "no tengo esa informacion confirmada" a un cliente que estaba
        # armando un presupuesto. Lo que paso adentro: el modelo escribio los
        # precios de lo que ya habia mostrado SACANDOLOS DE SU CABEZA -algunos
        # acertados, otros sumados a mano- y la guarda de procedencia tiro la
        # respuesta entera, con razon.
        #
        # No podia hacer otra cosa: este bloque le mandaba los NOMBRES pelados.
        # Sin el precio no tenia de donde copiarlo; sin el id no podia ni volver
        # a buscarlo, aunque `buscar` acepta ids y su descripcion dice, textual,
        # "para volver a un producto que ya le mostraste". La capacidad estaba
        # escrita y el modelo no tenia con que usarla.
        #
        # El precio aca ES fuente -viaja en el prompt, igual que el inventario-
        # asi que copiarlo de aca ya no es inventar.
        partes.append(
            "Productos que le mostraste ANTES, con su id y su precio, del "
            "mas viejo al mas reciente"
            + ("" if recien else
               "; si dice 'ese' o 'el que me dijiste', es el ultimo")
            + ":\n"
            + "\n".join(
                f"- {p.get('id')}: {p.get('nombre')}"
                + (f", {p['precio']}" if p.get("precio") else "")
                + (RESPUESTA if p.get("respuesta") else "")
                for p in vistos[-8:]))
    # EL ULTIMO PRESUPUESTO, Y ES FUENTE COMO EL PRECIO DE ARRIBA (15-sep-2026).
    #
    # MEDIDO EN WHATSAPP ESE MISMO DIA, cuatro turnos sobre UN pedido: el total
    # salio 207.500, despues 284.000 y despues 395.000, y el cuarto turno no
    # llego al cliente porque el modelo escribio $250.000 y la guarda tiro la
    # respuesta entera. Ninguna de las tres cuentas estaba mal sumada: cada
    # turno ELIGIO productos y cantidades distintas, porque lo unico que
    # sobrevivia al turno eran los nombres de lo mostrado.
    #
    # Con el presupuesto delante el modelo no rearma el carrito: lo copia. Y al
    # viajar en el prompt es FUENTE, asi que copiar ese total ya no es inventar
    # y la guarda de procedencia deja de matar la respuesta.
    #
    # LA REGLA DE FRESCURA VA PEGADA AL DATO, que es donde se usa: si el pedido
    # cambio, se pide la cuenta de nuevo. Corregir un total a mano es la unica
    # forma de que vuelva a aparecer una cifra sin procedencia.
    presu = (conv.get("ultimo_presupuesto") or "").strip()
    if presu:
        partes.append(
            "EL ULTIMO PRESUPUESTO que ya le pasaste. Estos numeros son "
            "fuente: copialos tal cual. Si el pedido cambio, pedi la cuenta de "
            "nuevo con la herramienta cuenta en vez de corregirlos a mano:\n" + presu[:700])
    grupos = [g for g in (conv.get("grupos_envio") or []) if isinstance(g, dict) and g.get("items")]
    if len(grupos) > 1:
        # UN PRESUPUESTO POR DESTINO, y el reparto que pida despues es sobre
        # todos (1-oct, K07). El presupuesto de arriba es solo el ultimo bloque.
        from app.storage.firestore_client import get_product_by_id as _gp
        partes.append("LOS PRESUPUESTOS POR DESTINO que ya le pasaste, y un total general:\n" + "\n".join(
            f"- {g.get('destino')}: " + ", ".join(
                f"{i.get('cantidad') or 1}x {i.get('producto')} "
                f"{(_gp(str(i.get('producto'))) or {}).get('nombre') or ''}".strip() for i in g["items"])
            for g in grupos[:4]))
    carrito = conv.get("carrito_vigente") or []
    if carrito:
        # CON ID Y CON CANTIDAD, por lo mismo que los productos vistos: sin el
        # id el modelo no puede volver a pedir la cuenta de lo mismo, y sin la
        # cantidad la vuelve a elegir -medido: el cliente pidio dos de cada uno
        # y el turno siguiente cotizo uno-.
        partes.append("EN EL PEDIDO, tal como se conto: " + " · ".join(
            f"{p.get('cantidad') or 1}x {p.get('id')} {p.get('nombre') or ''}".strip()
            for p in carrito[:8]))
    busco = (conv.get("criterio_cliente") or "").strip()
    if busco:
        # LO QUE EL CLIENTE BUSCO, no lo que el bot mostro (1-oct): "y teclados?"
        # o "y el mas barato?" heredan de aca el alcance y las condiciones.
        partes.append("LO ULTIMO QUE BUSCO EL CLIENTE, como se interpreto. Un mensaje que sigue la busqueda "
                      "—'y teclados?', 'y el mas barato?'— hereda de aca el alcance y las condiciones que no "
                      "cambio; 'toda la tienda' es sin rubro:\n" + busco[:400])
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


def _nombrados(texto: str, fichas: list, tienda_id: str) -> list:
    """Las fichas que la respuesta NOMBRA, en el orden en que las nombra.

    SE APAREA POR MODELO, que es la palabra que distingue un producto en una
    respuesta —"el K120", "el G203"—, y no por el nombre entero, que el modelo
    casi nunca copia tal cual. Un modelo de menos de tres letras no se busca:
    aparear por parecido es la enfermedad que el MAPA_CABLEADO tiene numerada.
    El mismo modelo en dos colores queda en el lugar donde se nombro, con el
    color que la respuesta dice primero.
    """
    import re
    from app.storage.firestore_client import get_product_by_id
    t = _norm_simple(texto)
    hallados = []
    for f in fichas or []:
        try:
            prod = get_product_by_id(str(f.get("id")), tienda_id=tienda_id) or {}
        except Exception:  # noqa: BLE001 — sin producto no se aparea
            prod = {}
        apariciones = sorted({m.start() for k in _claves_modelo(prod.get("modelo"))
                              for m in re.finditer(re.escape(k), t)})
        if not apariciones:
            continue
        # SI EL MODELO SE NOMBRA UNA VEZ, sus colores son UN renglon: "el G203
        # en negro o blanco". SI SE NOMBRA POR COLOR -"1. G203 negro, 2. G203
        # blanco"- cada color es su renglon, y la posicion es la de la
        # aparicion que sigue su color. Manda lo que el cliente leyo.
        color = _norm_simple(prod.get("color"))
        i = apariciones[0]
        if len(apariciones) > 1 and color:
            i = next((a for a in apariciones
                      if color in t[a:a + 60].split(",")[0]), i)
        j = t.find(color, i) if color else -1
        grupo = (str(prod.get("modelo") or "") if len(apariciones) == 1
                 else str(f.get("id")))
        hallados.append((i, j if j >= 0 else 10 ** 6,
                         dict(f, modelo=str(prod.get("modelo") or ""),
                              grupo=grupo)))
    hallados.sort(key=lambda x: (x[0], x[1]))
    visto, fuera = set(), []
    for _i, _j, f in hallados:
        if str(f.get("id")) not in visto:
            visto.add(str(f.get("id")))
            fuera.append(f)
    return fuera


def _claves_modelo(modelo) -> list:
    """Como se nombra un modelo en una respuesta: entero -"G Pro X
    Superlight"- o por la parte que lleva numeros -"G203" de "G203
    Lightsync"-, que es la que usan el cliente y el bot. Una palabra sin
    numeros no alcanza: "Pro" o "Core" estan en veinte modelos."""
    import re
    m = _norm_simple(modelo)
    claves = [m] if len(m) >= 3 else []
    claves += [w for w in re.split(r"\s+", m)
               if len(w) >= 3 and any(c.isdigit() for c in w)
               and any(c.isalpha() for c in w) and w != m]
    return claves


def _norm_simple(t) -> str:
    import unicodedata
    t = unicodedata.normalize("NFD", str(t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


# LO QUE RESPONDIO A LO QUE EL CLIENTE PIDIO POR CRITERIO (2-oct, K18): "el mas
# caro" mostraba cinco notebooks y la memoria los guardaba iguales, asi que
# "sumame uno de cada uno" sumaba los cinco. La respuesta era el primero; los
# otros eran contexto. La marca va pegada al id y `tablero._elegidos` la lee.
RESPUESTA = " · fue la respuesta a lo que pidio"


def _vistos_al_dia(vistos: list, fichas: list, texto: str, turno: int,
                   tienda_id: str, respondidos: list = None) -> list:
    """La lista de productos vistos despues de este turno.

    LO NOMBRADO VA AL FINAL, EN SU ORDEN Y CON SU TURNO. Si la respuesta no
    nombra ninguna ficha por su modelo —una charla sobre envio, o un nombre que
    no se pudo aparear— se guardan las fichas como antes, para no perder el id:
    olvidar es peor que recordar de mas.
    """
    nombrados = _nombrados(texto, fichas, tienda_id)
    nuevos = nombrados or [f for f in fichas or []
                           if str(f.get("id")) not in
                           {str(p.get("id")) for p in vistos}]
    ids = {str(f.get("id")) for f in nuevos}
    fuera = [p for p in vistos if str(p.get("id")) not in ids]
    for f in nuevos:
        # EL PRECIO SE GUARDA: sin el, el turno siguiente no puede decir
        # cuanto salia lo que ya se mostro.
        fuera.append({"id": f.get("id"), "nombre": f.get("nombre"),
                      "precio": f.get("precio"),
                      "modelo": f.get("modelo") or "",
                      "grupo": f.get("grupo") or f.get("modelo") or "",
                      "turno": turno if nombrados else 0,
                      **({"respuesta": True} if str(f.get("id")) in set(map(str, respondidos or [])) else {})})
    return fuera


def _senal(llamadas: list, mensaje: str) -> dict:
    """La interpretacion MINIMA que pide el cierre: intencion y confianza.

    Sale de dos lados. De lo que el agente HIZO —si llamo a `reservar` y el
    producto quedo listo para cerrar, el cliente decidio comprar— y de la
    marca determinista sobre el mensaje, que no depende de que el modelo se
    acuerde de nada. Con que uno de los dos diga compra, alcanza.
    """
    from app.core.leads import _RE_PIDE_COBRO
    if _RE_PIDE_COBRO.search(mensaje or ""):
        return {"intencion": "decision_compra", "confianza": 1.0,
                "motivo": "pide_datos_de_pago"}
    if any(x.get("herramienta") == "reservar"
           and (x.get("vuelve") or {}).get("veredicto") == "listo_para_cerrar"
           for x in llamadas or []):
        return {"intencion": "decision_compra", "confianza": 1.0,
                "motivo": "reservo"}
    if any(x.get("herramienta") in ("producto", "cuenta", "envio") for x in llamadas or []):
        return {"intencion": "pregunta_especifica", "confianza": 0.9}
    return {"intencion": "exploracion", "confianza": 0.6}


def _lo_que_volvio(llamadas: list) -> tuple:
    """De lo que devolvieron las herramientas: las fichas que se vieron, las
    tarifas por destino y la ultima cuenta hecha."""
    fichas, envios, cuenta = [], {}, None

    def filas(r):
        for f in (r or {}).get("filas") or []:
            if f.get("id") and str(f["id"]) not in {str(x.get("id")) for x in fichas}:
                # EL PRECIO TAMBIEN EN NUMERO: la guarda de plata suma con
                # `precio_ars`, y sin el tiraba por inventada una suma correcta
                # de dos precios que si volvieron.
                ars = re.sub(r"\D", "", str(f.get("precio") or ""))
                fichas.append({"id": f["id"], "nombre": f.get("nombre"), "precio": f.get("precio"),
                               **({"precio_ars": int(ars)} if ars else {})})
            # Los otros colores del renglon tambien se vieron: "y en blanco?"
            # tiene que poder volver a ellos por su id.
            for v in f.get("variantes") or []:
                if v.get("id") and str(v["id"]) not in {str(x.get("id")) for x in fichas}:
                    # Sin precio propio es el del renglon: la variante solo
                    # lo trae cuando es otro.
                    ars = re.sub(r"\D", "", str(v.get("precio") or f.get("precio") or ""))
                    from app.storage.firestore_client import get_product_by_id
                    prod = get_product_by_id(str(v["id"])) or {}
                    fichas.append({"id": v["id"], "nombre": prod.get("nombre") or f.get("nombre"),
                                   "precio": v.get("precio") or f.get("precio"),
                                   **({"precio_ars": int(ars)} if ars else {})})
        for sub in (r or {}).get("por_condicion") or []:
            filas(sub)

    for x in llamadas or []:
        v = x.get("vuelve") or {}
        filas(v)
        for e in ((v.get("envio") or v) if x.get("herramienta") in ("envio", "cuenta") else {}).get("filas") or []:
            if isinstance(e, dict) and e.get("monto_ars") is not None and e.get("destino"):
                envios[str(e["destino"])] = int(e["monto_ars"])
        if x.get("herramienta") == "cuenta" and (v.get("cuenta") or {}).get("total_ars") is not None:
            cuenta = v["cuenta"]
            for it in cuenta.get("items") or []:
                if it.get("id") and str(it["id"]) not in {str(f.get("id")) for f in fichas}:
                    fichas.append({"id": it["id"], "nombre": it.get("nombre")})
    return fichas, envios, cuenta


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

    Misma firma que el turno viejo: el orchestrator no cambia."""
    t0 = time.time()
    etapas: dict = {}
    from app.core import guardas_salida as gs
    from app.core import tablero
    from app.core.contexto_turno import set_current_tienda

    set_current_tienda(tienda_id)
    conv = get_conversation(user_id, tienda_id=tienda_id) or {}
    history = conv.get("history", []) or []
    negocio = gs.business_name(tienda_id)

    # ── 1. AGENTE ───────────────────────────────────────────────────────
    t = time.time()
    memoria = _memoria_texto(conv)
    r = await tablero.turno([{"role": m.get("role"), "content": m.get("content") or ""}
                            for m in history if m.get("role") in ("user", "assistant")],
                           raw_message, tienda_id, trace_id=trace_id, memoria=memoria,
                           pedido=conv.get("pedido_pendiente"))
    llamadas = r.get("llamadas") or []
    fichas, envios, cuenta = _lo_que_volvio(llamadas)
    etapas["turno"] = int((time.time() - t) * 1000)
    if not llamadas:
        # Se CUENTA cada turno que contesto sin consultar: no se bloquea —la
        # guarda de procedencia ya impide que salga una cifra que no vio—,
        # pero es como se sabe si el modelo busca o contesta de memoria.
        log.warning("turno_sin_buscar", trace_id=trace_id)

    texto = (r.get("texto") or "").strip()
    informe: dict = {}
    if not texto:
        from app.core.guia_venta_prosa import mensaje as _prosa
        texto = _prosa("sobrecarga",
                       "Perdón, estoy con mucha demanda en este momento. "
                       "Probá de nuevo en un ratito y te respondo. 🙏")
        log.warning("respuesta_sin_modelo", trace_id=trace_id)
    else:
        # ── 2. NUMEROS ──────────────────────────────────────────────────
        # LA PROCEDENCIA SE MIDE CONTRA TODO LO QUE VIO EL MODELO: la memoria,
        # lo que el bot ya dijo en la charla —que paso por esta misma guarda— y
        # cada cosa que devolvio una herramienta, tal cual viajo.
        t = time.time()
        dicho = "\n".join(str(m.get("content") or "") for m in history if m.get("role") == "assistant")
        fuente = memoria + "\n" + dicho + "\n" + json.dumps([x.get("vuelve") for x in llamadas],
                                              ensure_ascii=False, default=str)
        texto, informe = N.llenar(
            texto, fichas, trace_id, fuente_texto=fuente,
            envio_monto=(list(envios.values())[0] if len(envios) == 1 else None),
            envios=envios, cuenta=cuenta)
        etapas["numeros"] = int((time.time() - t) * 1000)
        if informe.get("inventada"):
            # LA RESPUESTA CON PLATA INVENTADA NO SALE: el numero ya contamino
            # la frase y no hay forma honesta de corregirla renglon por renglon.
            texto = settings.VERIFIKA_FALLBACK_MESSAGE
        texto = gs.con_saludo_inicial(gs.sin_saludo_del_modelo(texto), negocio) \
            if not history else gs.sin_saludo_del_modelo(texto)

    # ── 3. CIERRE Y COBRO ───────────────────────────────────────────────
    t = time.time()
    texto, datos_cliente, cierre_hecho = await _cerrar(
        conv, user_id, canal, tienda_id, raw_message, texto, trace_id,
        _senal(llamadas, raw_message))
    etapas["cierre"] = int((time.time() - t) * 1000)

    # ── 4. MEMORIA ──────────────────────────────────────────────────────
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
    # LO QUE SE RECUERDA ES LO QUE EL CLIENTE LEYO, EN EL ORDEN EN QUE LO LEYO:
    # lo nombrado en la respuesta va al final, en su orden, marcado con el turno.
    previos = conv.get("productos_vistos") or []
    vistos = _vistos_al_dia(
        previos, fichas, texto,
        max((int(p.get("turno") or 0) for p in previos), default=0) + 1,
        tienda_id, r.get("respondidos"))
    # EL DESTINO QUE SE GUARDA ES EL QUE SE COTIZO, ya estable —la provincia,
    # no "Posadas"—, para que dentro de tres turnos vuelva a clasificar solo.
    from app.core import fuente as F
    previa = conv.get("ultima_localidad") or ""
    primero = next(iter(envios), "")
    localidad = (F.estable_de(primero, previa) or primero or previa) \
        if primero else previa
    # LA CUENTA SOBREVIVE AL TURNO: `leads` lee `ultimo_presupuesto` para
    # decidir si puede cerrar. Una cuenta que no se pudo hacer no pisa la
    # anterior, que sigue siendo lo ultimo que el cliente vio.
    presupuesto = carrito = None
    if (cuenta or {}).get("total_ars") is not None:
        presupuesto = str(cuenta.get("detalle") or "")[:900] or None
        carrito = cuenta.get("items") or None
    try:
        save_conversation(user_id, history, resumen, tienda_id=tienda_id,
                          estado_conversacion="en_curso",
                          productos_vistos=vistos[-20:],
                          ultima_localidad=localidad or None,
                          ultimo_presupuesto=presupuesto,
                          carrito_vigente=carrito,
                          datos_cliente_parciales=datos_cliente,
                          criterio_cliente=r.get("busqueda") or None,
                          # Una cuenta de un solo destino borra los bloques viejos.
                          grupos_envio=r.get("bloques") or ([] if presupuesto else None),
                          pedido_pendiente=r.get("pedido"),
                          pregunta_cierre_hecha=cierre_hecho)
    except Exception as e:  # noqa: BLE001
        log.warning("respuesta_save_error", trace_id=trace_id, error=str(e)[:150])
    etapas["memoria"] = int((time.time() - t) * 1000)

    log.info("turno_ok", trace_id=trace_id,
             latency_ms=int((time.time() - t0) * 1000), etapas=etapas,
             largo=len(texto or ""), herramientas=[x.get("herramienta") for x in llamadas][:10],
             fichas=len(fichas), envio_destinos=list(envios)[:3],
             envio_montos=list(envios.values())[:3],
             cuenta_total=(cuenta or {}).get("total_ars"),
             cuenta_final=(cuenta or {}).get("total_final_ars"),
             huecos_llenos=len((informe or {}).get("llenos") or []),
             huecos_sin_dato=len((informe or {}).get("sin_dato") or []),
             plata_inventada=len((informe or {}).get("inventada") or []))
    return texto
