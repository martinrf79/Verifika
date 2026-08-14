"""
LA CALCULADORA — la cuenta y la tarifa de envio, selladas por codigo.

Se llamaba `tools.py` hasta el 3-ago y ese nombre era una trampa: al lado vive
`herramientas.py`, que es la MISMA palabra en el otro idioma, y no son lo mismo.
`herramientas.py` es el menu que ve el modelo -moldes Pydantic, enums de la
fuente, validacion de argumentos-. Esto de aca es la cuenta: `calculate_total`
arma el presupuesto renglon por renglon y `cotizar_envio` resuelve la tarifa por
zona. Es el unico lugar donde nace un peso.

No se fusionaron en un solo archivo a proposito. No son dos capas que compiten:
una es el adaptador de cara al modelo y la otra es la aritmetica, y meter
quinientas lineas de calculo adentro del menu de herramientas no haria que el
bot venda mejor ni que alucine menos. Lo que si costaba caro era el nombre, que
invitaba a editar el archivo equivocado; eso se arreglo.

Multi-tenant: cada funcion resuelve la tienda actual desde `contexto_turno`
(ContextVar). El LLM no ve ese parametro; lo setea el hub antes del turno.
"""
from app.storage.firestore_client import (
    get_all_products,
    get_product_by_id,
    get_categories,
    get_all_faq,
)
import re

from app.config import get_settings
from app.logger import get_logger
from app.core.contexto_turno import get_current_tienda

log = get_logger(__name__)
settings = get_settings()


# ────────────────────────────────────────────────────────────
# 1) BUSCAR PRODUCTOS (con búsqueda híbrida)
# ────────────────────────────────────────────────────────────

# search_products y find_within_budget se borraron el 29-jul. Eran las tools de
# busqueda libre del solver viejo; en el camino atado la recuperacion es otra y
# es determinista: recall_modelos arma el enum del interprete y universo_productos
# arma el conjunto de productos del turno. Con ellas se fue app/storage/search.py
# entero, la busqueda hibrida que en los hechos nunca corrio en produccion.

# ────────────────────────────────────────────────────────────
# 2) DETALLE
# ────────────────────────────────────────────────────────────



# ────────────────────────────────────────────────────────────
# 3) CALCULAR TOTAL
# ────────────────────────────────────────────────────────────

def _efecto_porcentaje(tema: str, concepto: str, valor: dict) -> str:
    """
    Decide como impacta un extra porcentual en el total.
    - descuento: resta del subtotal (ej descuento por transferencia).
    - recargo: suma al subtotal (ej recargo por financiacion).
    - informativo: no toca el total, solo se informa el monto calculado (ej sena
      de reserva, que es un pago parcial, no un descuento ni un recargo).
    Prioriza un campo explicito valor['efecto'] si viene cargado en la FAQ.
    Si no, infiere por el nombre del tema o del concepto.
    """
    explicito = (valor.get("efecto") or "").strip().lower()
    if explicito in ("descuento", "recargo", "informativo"):
        return explicito
    texto = f"{tema} {concepto}".lower()
    if "descuento" in texto:
        return "descuento"
    if "sena" in texto or "seña" in texto or "reserva" in texto:
        return "informativo"
    if "recargo" in texto or "interes" in texto or "interés" in texto:
        return "recargo"
    # Por defecto no arriesgamos mover el total en la direccion equivocada.
    return "informativo"


def _money(n) -> str:
    """Formatea un entero como pesos con separador de miles: 273000 -> $273.000."""
    try:
        return "$" + f"{int(round(n)):,}".replace(",", ".")
    except Exception:
        return str(n)


def _label_extra(e: dict) -> str:
    """Texto legible de un extra del presupuesto (envio, descuento, sena)."""
    concepto = str(e.get("concepto", "")).lower()
    modalidad = e.get("modalidad")
    es_desc = ("descuento" in concepto) or (e.get("efecto") == "descuento")
    es_sena = ("sena" in concepto) or ("reserva" in concepto)
    if modalidad == "porcentaje":
        pct = e.get("porcentaje", e.get("monto", ""))
        monto = e.get("monto_calculado_ars", 0)
        if es_desc:
            return f"Descuento {pct}%: -{_money(monto)}"
        if es_sena:
            return f"Sena {pct}%: {_money(monto)} (pago parcial)"
        return f"Recargo {pct}%: +{_money(monto)}"
    _dest = int(e.get("destinos", 1) or 1)
    _suf = f" ({_dest} envios)" if _dest > 1 else ""
    if modalidad == "rango":
        return (f"Envio{_suf}: entre {_money(e.get('monto_min', 0))} y "
                f"{_money(e.get('monto_max', 0))}")
    monto = e.get("monto", 0)
    if "envio" in concepto:
        return f"Envio{_suf}: gratis" if int(monto) == 0 else f"Envio{_suf}: {_money(monto)}"
    if es_desc:
        return f"Descuento: -{_money(monto)}"
    if modalidad == "informativo":
        # Dato no monetario (ej cuotas). NO es plata, no lleva $. Se muestra como
        # condicion legible: "Cuotas sin interes: hasta 6 cuotas".
        concepto_legible = str(e.get("concepto", "")).replace("_", " ").strip()
        unidad = str(e.get("unidad", "")).strip()
        val = e.get("valor_num", "")
        return f"{concepto_legible.capitalize()}: hasta {val} {unidad}".strip()
    return f"{concepto}: {_money(monto)}"


# Unidades que SI son dinero. Un extra "fijo" solo suma al total si su unidad es
# monetaria. Una unidad como "cuotas" es una cantidad, no pesos: nunca se suma.
_UNIDADES_MONETARIAS = {"", "ars", "pesos", "peso", "$"}

# Techo de destinos separados de un pedido (multi-destino). Generoso para una
# compra real y a la vez guarda contra un numero disparatado del modelo.
_MAX_DESTINOS = 10


def _render_presentacion(detalle, extras, subtotal,
                         total_ars=None, total_min=None, total_max=None) -> str:
    """Arma el presupuesto en texto, por codigo. El Solver lo copia tal cual,
    asi ningun numero sale de la cabeza del modelo."""
    lineas = ["Presupuesto:"]
    for d in detalle:
        lineas.append(
            f"- {d['cantidad']}x {d['nombre']}: {_money(d['precio_unitario'])} "
            f"c/u = {_money(d['subtotal'])}"
        )
    lineas.append(f"Subtotal: {_money(subtotal)}")
    for e in extras or []:
        lineas.append(_label_extra(e))
    if total_ars is not None:
        lineas.append(f"Total: {_money(total_ars)}")
    else:
        lineas.append(f"Total: entre {_money(total_min)} y {_money(total_max)}")
    return "\n".join(lineas)


def _subtotales_por_grupo(grupos: list, locs: list,
                          cat_precios: dict) -> dict:
    """{localidad: subtotal_del_paquete} cuando cada localidad mapea a UN
    grupo declarado por el cliente y cada categoria tiene UN solo precio en
    el pedido. {} ante cualquier ambiguedad: el que llama sigue con el
    promedio. Es la pieza de plata de grupos_envio (pendiente 10-jul; charla
    real 19-jul: el promedio regalo el envio del paquete chico)."""
    import unicodedata

    def _n(s):
        s = unicodedata.normalize("NFKD", str(s or "").lower())
        s = "".join(c for c in s if not unicodedata.combining(c))
        return set(w for w in re.sub(r"[^\w\s]", " ", s).split() if w)

    out: dict = {}
    usados: set[int] = set()
    for loc in locs:
        pl = _n(loc)
        duenos = [i for i, g in enumerate(grupos) if i not in usados
                  and (_n(g.get("destino")) <= pl or pl <= _n(g.get("destino")))]
        if len(duenos) != 1:
            return {}
        usados.add(duenos[0])
        sub = 0
        for par in (grupos[duenos[0]].get("cats") or []):
            try:
                if isinstance(par, dict):
                    n, cat = int(par.get("n")), str(
                        par.get("cat") or "").strip().lower()
                else:
                    n, cat = int(par[0]), str(par[1] or "").strip().lower()
            except (TypeError, ValueError, IndexError):
                return {}
            precios = cat_precios.get(cat) or set()
            if len(precios) != 1 or n < 1:
                return {}
            sub += n * next(iter(precios))
        if sub <= 0:
            return {}
        out[loc] = sub
    return out


def calculate_total(items: list[dict] | None = None,
                    items_extra: list[dict] | None = None,
                    destinos: int = 1,
                    pago: list[dict] | None = None,
                    grupos: list[dict] | None = None) -> dict:
    log.info(f"calculate_total INICIO items={items} items_extra={items_extra} "
             f"destinos={destinos} pago={pago}")
    # PAGO DIVIDIDO POR PORCENTAJE: si el cliente reparte el total entre medios
    # (50/50, 70/30, etc.), el descuento por transferencia lo dueña el split, NO
    # el items_extra. Se saca un descuento_transferencia que el solver haya
    # pasado para no aplicarlo dos veces; el reparto lo aplica abajo con el pct
    # real de la FAQ.
    if pago:
        items_extra = [e for e in (items_extra or [])
                       if (e.get("faq_tema") or "").strip().lower()
                       != "descuento_transferencia"]
    # Envios separados (multi-destino): el costo de envio se cobra una vez por
    # destino. Piso 1 (un solo envio, como funcionaba antes) y un techo sano para
    # no inventar multiplicadores absurdos si el modelo manda un numero disparatado.
    # Antes se capaba en 3 EN SILENCIO y el cuarto destino viajaba gratis (E13).
    try:
        n_envios = max(1, min(int(destinos or 1), _MAX_DESTINOS))
    except (TypeError, ValueError):
        n_envios = 1
    if not items:
        # El Solver no paso items: si hay un carrito vigente en el ESTADO del turno
        # (lo dejo un calculate_total anterior), se parte de ahi. Asi "cuanto es el
        # total" sobre el pedido ya armado no responde "no tengo pedido". Solo actua
        # cuando el modelo no manda nada; si manda items, se respetan tal cual.
        from app.core.estado_venta import get_current_estado
        _seed = [{"product_id": c.get("id"), "cantidad": c.get("cantidad", 1)}
                 for c in (get_current_estado().get("carrito") or []) if c.get("id")]
        if _seed:
            log.info(f"calculate_total carrito_estado items={len(_seed)}")
            items = _seed
    if not items:
        return {
            "ok": False,
            # Redactado en voz cliente-segura a proposito: el Solver a veces
            # pega este texto TAL CUAL en la respuesta (visto 12-jun con
            # "cuanto era el total de mi pedido?" sin pedido vigente), asi que
            # tiene que poder leerse como respuesta al cliente sin verguenza.
            "mensaje_para_llm": (
                "No tengo un pedido armado para sumar. Decime que productos "
                "y cantidades queres y te paso el total."
            ),
        }
    """
    Calcula total exacto de productos del catalogo, mas extras verificados
    contra FAQ cuantitativa (envios, descuentos, recargos).

    items: lista de {"product_id", "cantidad"} del catalogo.
    items_extra: lista opcional de {"faq_tema", "concepto"}, donde faq_tema es
        el ID de la FAQ y concepto es el id del valor estructurado dentro de esa
        FAQ. La funcion busca el monto o rango en la FAQ. Si no existe rechaza.

    Devuelve total_ars cuando todo es fijo, o total_min_ars y total_max_ars
    cuando algun extra es de modalidad rango.
    """
    # Capa defensiva (unico camino, sin flag): normaliza y valida los inputs del
    # modelo antes de calcular. Rechaza cantidades cero o negativas, normaliza el
    # concepto de FAQ, fusiona el mismo producto mandado en dos lineas y deduplica
    # un extra identico. Asi un input sucio del modelo no ensucia el total.
    from app.core.calc_defensiva import normalizar_inputs
    items, items_extra, _err = normalizar_inputs(items, items_extra)
    if _err:
        return {"ok": False, "mensaje_para_llm": _err}

    # REGLA CERO mecanica: con un pedido VIGENTE, los items solo pueden venir de
    # ids CERTIFICADOS (el carrito, los productos ya mostrados o los devueltos
    # por una tool de ESTE turno). Un id inferido de memoria muta la identidad
    # del pedido en silencio: visto en el banco, el solver pidio el total con el
    # NX-7000 cuando el carrito era el DX-110 y el cliente recibio numeros
    # reales del producto equivocado. Sin carrito no se restringe (el flujo de
    # primer turno arma el pedido con lo que la busqueda del turno devuelve).
    from app.core.estado_venta import get_current_estado, get_ids_certificados
    _est = get_current_estado()
    _carrito = [c for c in (_est.get("carrito") or []) if c.get("id")]
    if _carrito:
        _permitidos = get_ids_certificados()
        _permitidos |= {str(c["id"]).upper() for c in _carrito}
        _permitidos |= {str(p.get("id") or "").upper()
                        for p in (_est.get("productos_vistos") or [])
                        if isinstance(p, dict) and p.get("id")}
        _sueltos = sorted({str(i.get("product_id") or "").upper()
                           for i in items
                           if str(i.get("product_id") or "").upper()
                           not in _permitidos})
        if _sueltos:
            _orden = ", ".join(
                f"{c.get('cantidad', 1)}x {c.get('nombre', '')} "
                f"(product_id {c['id']})" for c in _carrito)
            log.warning(f"calculate_total id_no_certificado sueltos={_sueltos}")
            return {"ok": False, "mensaje_para_llm": (
                f"Los product_id {', '.join(_sueltos)} no salen ni del pedido "
                f"vigente ni de una busqueda de este turno: no uses ids de "
                f"memoria. El pedido vigente del cliente es: {_orden}. Llama "
                f"calculate_total con ESOS product_id; si el cliente pidio "
                f"OTRO producto, primero resolvelo con search_products o "
                f"get_product_details y despues sumalo.")}

    # PEDIDO SELLADO DEL TURNO (guia_pedido, 8-jul): el interprete ya extrajo el
    # pedido de este turno y el codigo lo calculo entero. Un calculate_total del
    # solver que AGREGA productos fuera del pedido sellado (+carrito) muta el
    # pedido en silencio: visto en el banco, el solver sumo un microfono de
    # $76.500 que el cliente nunca eligio. Quitar o repetir items sellados esta
    # bien (subconjunto); agregar, no.
    _sellado = {str(i).upper() for i in (_est.get("pedido_sellado_turno") or [])}
    if _sellado:
        _extras_pedido = sorted(
            {str(i.get("product_id") or "").upper() for i in items}
            - _sellado - {str(c["id"]).upper() for c in _carrito})
        if _extras_pedido:
            log.warning(f"calculate_total pedido_sellado_extras={_extras_pedido}")
            return {"ok": False, "mensaje_para_llm": (
                "El pedido de este turno YA fue calculado por el sistema con "
                "lo que el cliente eligio; no agregues productos que no pidio "
                f"({', '.join(_extras_pedido)}). Pone el marcador "
                "[[PRESUPUESTO]] donde va el detalle del presupuesto y NO "
                "vuelvas a llamar calculate_total.")}

    tid = get_current_tienda()
    detalle = []
    total = 0
    no_encontrados = []
    _cat_precios: dict[str, set] = {}  # para el umbral por grupo de envio
    for item in items:
        pid = item.get("product_id", "")
        cantidad = int(item.get("cantidad", 1))
        producto = get_product_by_id(pid, tienda_id=tid)
        if not producto:
            no_encontrados.append(pid)
            continue
        if cantidad > producto.get("stock", 0):
            return {
                "ok": False,
                "mensaje_para_llm": (
                    f"Stock insuficiente: {producto['nombre']} tiene "
                    f"{producto.get('stock', 0)} unidades, el cliente quiere {cantidad}."
                ),
            }
        subtotal = producto["precio_ars"] * cantidad
        total += subtotal
        _cat_precios.setdefault(
            str(producto.get("categoria") or "").strip().lower(),
            set()).add(int(producto["precio_ars"]))
        detalle.append({
            "id": producto["id"],
            "nombre": producto["nombre"],
            "cantidad": cantidad,
            "precio_unitario": producto["precio_ars"],
            "subtotal": subtotal,
        })
    if no_encontrados:
        return {
            "ok": False,
            "mensaje_para_llm": f"IDs no existentes: {no_encontrados}.",
        }

    extras_detalle = []
    extra_min = 0
    extra_max = 0
    hay_rango = False
    envio_gratis_aplicado = False
    if items_extra:
        from app.storage.firestore_client import get_all_faq
        faqs = get_all_faq(tienda_id=tid)
        extras_no_validos = []
        # El ENVIO no se calcula aca. Su UNICA fuente es cotizar_envio, que deduce
        # zona y tarifa de la localidad. La calculadora separa el envio del resto de
        # extras (descuentos, recargos, sena, cuotas), que SI salen de la FAQ, y mas
        # abajo le pide el costo a cotizar_envio. Que el modelo haya pasado un
        # concepto de envio es solo la senal de "incluir envio"; el concepto se
        # IGNORA, lo resuelve el codigo. Asi el costo de envio nace en un solo lugar.
        pide_envio = any(
            (e.get("faq_tema") or "").strip().lower() == "costo_envio"
            for e in items_extra)
        otros_extra = [
            e for e in items_extra
            if (e.get("faq_tema") or "").strip().lower() != "costo_envio"]
        for ex in otros_extra:
            tema = (ex.get("faq_tema") or "").strip().lower()
            concepto = (ex.get("concepto") or "").strip()
            faq = faqs.get(tema)
            if not faq or faq.get("tipo") != "cuantitativo":
                extras_no_validos.append(f"{tema}:{concepto} (FAQ no cuantitativa)")
                continue
            valores = faq.get("valores") or []
            valor = next((v for v in valores if v.get("concepto") == concepto), None)
            if not valor:
                extras_no_validos.append(f"{tema}:{concepto} (concepto no existe)")
                continue
            unidad = (valor.get("unidad") or "").strip().lower()
            if unidad == "porcentaje":
                # El monto guardado es un porcentaje, no pesos. Se calcula sobre
                # el subtotal de productos ya acumulado en total.
                pct = int(valor.get("monto", 0))
                base = total
                monto_calc = round(base * pct / 100)
                efecto = _efecto_porcentaje(tema, concepto, valor)
                if efecto == "descuento":
                    extra_min -= monto_calc
                    extra_max -= monto_calc
                elif efecto == "recargo":
                    extra_min += monto_calc
                    extra_max += monto_calc
                # efecto informativo: no altera el total, solo se reporta el monto.
                extras_detalle.append({
                    "faq_tema": tema, "concepto": concepto,
                    "modalidad": "porcentaje", "porcentaje": pct,
                    "base_ars": base, "monto_calculado_ars": monto_calc,
                    "efecto": efecto,
                    "condicion": valor.get("condicion", ""),
                })
            elif valor.get("modalidad") == "fijo":
                m = int(valor.get("monto", 0))
                if unidad in _UNIDADES_MONETARIAS:
                    extra_min += m
                    extra_max += m
                    extras_detalle.append({
                        "faq_tema": tema, "concepto": concepto,
                        "modalidad": "fijo", "monto": m,
                        "condicion": valor.get("condicion", ""),
                    })
                else:
                    # Unidad NO monetaria (ej cuotas): es una cantidad, no pesos.
                    # NO se suma al total ni se muestra con $. Se reporta como dato.
                    extras_detalle.append({
                        "faq_tema": tema, "concepto": concepto,
                        "modalidad": "informativo", "valor_num": m,
                        "unidad": unidad,
                        "condicion": valor.get("condicion", ""),
                    })
            elif valor.get("modalidad") == "rango":
                mn = int(valor.get("monto_min", 0))
                mx = int(valor.get("monto_max", 0))
                extra_min += mn
                extra_max += mx
                hay_rango = True
                extras_detalle.append({
                    "faq_tema": tema, "concepto": concepto,
                    "modalidad": "rango", "monto_min": mn, "monto_max": mx,
                    "condicion": valor.get("condicion", ""),
                })
            else:
                extras_no_validos.append(f"{tema}:{concepto} (modalidad invalida)")
        if extras_no_validos:
            # Veredicto + opciones: sin la lista de extras validos el modelo
            # improvisa una disculpa y mata el cierre (visto en el molino
            # multiturno con el descuento por transferencia). Con la lista,
            # reintenta con el par exacto. Unico camino, sin flag.
            cuantitativas = {
                t: [v.get("concepto") for v in (f.get("valores") or [])]
                for t, f in faqs.items()
                if f.get("tipo") == "cuantitativo"
            }
            msg = (f"Extras no validos: {extras_no_validos}. Los UNICOS extras "
                   f"validos son (faq_tema: conceptos): {cuantitativas}. "
                   f"Reintenta calculate_total usando exactamente uno de esos pares.")
            return {"ok": False, "mensaje_para_llm": msg}

        # ── ENVIO: lo cotiza cotizar_envio (unica fuente), la calculadora solo lo
        #    TOMA y lo cobra una vez por destino. Se le pasa el subtotal real, asi
        #    el envio gratis por umbral lo decide tambien cotizar_envio, no esta
        #    funcion. Si no hay zona (falta direccion), se devuelve ok False con el
        #    pedido de cotizar_envio: nunca se inventa un costo de envio.
        if pide_envio:
            from app.core.estado_venta import get_envio_localidades
            # Envio gratis por umbral en MULTI-destino: el umbral se mira POR
            # DESTINO, no por la suma del pedido. Los items no declaran a que
            # destino van, asi que se usa el promedio (suma/destinos): solo
            # libera el envio si el reparto claramente supera el umbral. Antes 4
            # destinos chicos sumados daban "todo gratis" (visto en real 2-jul).
            _sub_umbral = total if n_envios <= 1 else total // n_envios
            # DESTINOS DISTINTOS, TARIFAS DISTINTAS: si este turno se cotizaron
            # varias localidades, cada destino cobra SU tarifa real (Cordoba +
            # Rosario suma 7500 + 6000, no dos veces la ultima). Con una sola
            # localidad conocida, los n destinos van a esa tarifa, como antes.
            _locs = get_envio_localidades()
            if not _locs:
                # Memoria del pedido: destinos cotizados en turnos ANTERIORES.
                # Sin esto, "y el total de todo?" un turno despues de cotizar
                # dos destinos no encuentra ninguna localidad y vuelve a pedir
                # un CP que el cliente ya dio (visto en el banco de charlas).
                from app.core.estado_venta import get_current_estado
                _locs = [str(l).strip() for l in
                         (get_current_estado().get("localidades_envio") or [])
                         if str(l or "").strip()]
            # DESTINO UNICO (sticky del estado): el cliente dijo "mandalo todo
            # a X" / "me mude". Todo va a UN lugar; un destino viejo que el
            # solver re-cotice desde el historial queda OBSOLETO y no se
            # cobra (visto en el banco 8-jul: mudanza Mendoza->Salta cobro dos
            # envios). Se queda con el destino de la MEMORIA si esta entre los
            # cotizados; si no, con el ultimo cotizado del turno.
            from app.core.estado_venta import get_current_estado as _gce_du
            if _gce_du().get("destino_unico") and len(_locs) > 1:
                _mem_du = [str(l).strip() for l in
                           (_gce_du().get("localidades_envio") or [])
                           if str(l or "").strip()]
                _elegida = next(
                    (l for l in _locs
                     if _mem_du and l.lower() == _mem_du[-1].lower()),
                    _locs[-1])
                log.info(f"calculate_total destino_unico "
                         f"cotizados={_locs} usado={_elegida}")
                _locs = [_elegida]
            if _gce_du().get("destino_unico") and n_envios > 1:
                n_envios = 1
                _sub_umbral = total

            # DESTINOS SIN COTIZAR NO SE COBRAN NI SE INVENTAN: si el solver
            # declara MAS destinos que localidades cotizadas (turno + memoria),
            # antes se rellenaba duplicando la ultima tarifa (E13, para no
            # regalar el envio) — pero eso COBRO DE MAS en real: tras "mandalo
            # todo a Salta" (UN destino) el solver mando destinos=2 y el total
            # sumo dos envios de $9.000 (banco 8-jul). Ahora se pide cotizar el
            # destino faltante: ni capa en silencio (E13) ni duplica tarifa.
            if _locs and n_envios > len(_locs):
                log.warning(f"calculate_total destinos_sin_cotizar "
                            f"declarados={n_envios} cotizados={len(_locs)}")
                return {"ok": False, "mensaje_para_llm": (
                    f"Declaraste {n_envios} destinos pero hay "
                    f"{len(_locs)} localidad(es) cotizada(s): "
                    f"{', '.join(_locs)}. Si de verdad hay mas destinos, "
                    f"cotiza cada uno con cotizar_envio (uno por localidad, "
                    f"aunque la ciudad se repita) y volve a llamar. Si es UN "
                    f"solo destino, llama con destinos={len(_locs)}. No cobro "
                    f"envios sin cotizar.")}
            if n_envios > 1 and len(_locs) > 1:
                _locs = _locs[-n_envios:]
            else:
                _locs = _locs[-1:] or [None]
            _cuentas = [1] * len(_locs)
            _cuentas[-1] += max(0, n_envios - len(_locs))
            # UMBRAL POR GRUPO (grupos_envio, pendiente del 10-jul, cerrado
            # 19-jul): si el cliente dijo QUE va a cada destino, el envio
            # gratis se decide con el subtotal REAL de cada paquete, no con
            # el promedio (que regalaba el envio del paquete chico). Todo-o-
            # nada: ante cualquier ambiguedad sigue el promedio de siempre.
            _sub_grupo: dict = {}
            if grupos and n_envios > 1 and len(grupos) == len(_locs):
                _sub_grupo = _subtotales_por_grupo(grupos, _locs, _cat_precios)
                if _sub_grupo:
                    log.info(f"calculate_total grupos_envio="
                             f"{ {k: v for k, v in _sub_grupo.items()} }")
            _env_min = _env_max = 0
            _env_rango = False
            concepto_env = "envio"
            for _loc, _n in zip(_locs, _cuentas):
                quote = cotizar_envio(
                    localidad=_loc,
                    subtotal=_sub_grupo.get(_loc, _sub_umbral))
                if not quote.get("ok"):
                    return {"ok": False, "mensaje_para_llm": quote.get(
                        "mensaje_para_llm",
                        "Para sumar el envio al total necesito la zona. Pedile al "
                        "cliente la provincia o el codigo postal y cotiza el envio "
                        "con cotizar_envio antes de calcular el total.")}
                concepto_env = quote.get("concepto") or concepto_env
                if quote.get("modalidad") == "rango":
                    _env_rango = True
                    _env_min += int(quote.get("monto_min", 0)) * _n
                    _env_max += int(quote.get("monto_max", 0)) * _n
                else:
                    m = int(quote.get("monto", 0)) * _n
                    _env_min += m
                    _env_max += m
            extra_min += _env_min
            extra_max += _env_max
            if _env_rango:
                hay_rango = True
                extras_detalle.append({
                    "faq_tema": "costo_envio", "concepto": concepto_env,
                    "modalidad": "rango", "monto_min": _env_min,
                    "monto_max": _env_max,
                    **({"destinos": n_envios} if n_envios > 1 else {}),
                    "condicion": "tarifa de envio cotizada por zona",
                })
            else:
                if _env_min == 0:
                    envio_gratis_aplicado = True
                extras_detalle.append({
                    "faq_tema": "costo_envio", "concepto": concepto_env,
                    "modalidad": "fijo", "monto": _env_min,
                    **({"destinos": n_envios} if n_envios > 1 else {}),
                    **({"envio_gratis_auto": True} if _env_min == 0 else {}),
                    "condicion": ("envio gratis por umbral" if _env_min == 0
                                  else "tarifa de envio cotizada por zona"),
                })

    _nota_envio = None
    if envio_gratis_aplicado:
        _nota_envio = (
            "Envio GRATIS aplicado automaticamente porque la compra supera el "
            "umbral. Este ES el total final: mostralo tal cual, NO busques otro "
            "tipo de envio ni vuelvas a llamar calculate_total por el envio."
        )

    if hay_rango:
        return {
            "ok": True,
            "mensaje_para_llm": _nota_envio,
            "total_min_ars": total + extra_min,
            "total_max_ars": total + extra_max,
            "subtotal_productos_ars": total,
            "detalle": detalle,
            "extras": extras_detalle,
            "presentacion": _render_presentacion(
                detalle, extras_detalle, total,
                total_min=total + extra_min, total_max=total + extra_max),
            "proof": {
                "tipo": "calculo_total_rango",
                "formula": "suma_productos + suma_extras_rango (extras pueden ser montos fijos, rangos o porcentajes; los descuentos restan)",
                "operandos_productos": [
                    {"id": d["id"], "monto": d["subtotal"],
                     "precio_unitario": d["precio_unitario"],
                     "fuente": "catalogo"}
                    for d in detalle
                ],
                "operandos_extras": extras_detalle,
                "subtotal_productos": total,
                "resultado_min": total + extra_min,
                "resultado_max": total + extra_max,
            },
        }
    # ── PAGO DIVIDIDO POR PORCENTAJE: el CODIGO dueña TODA la cuenta ──────────
    # base = productos + envio (el descuento por transferencia ya se saco de los
    # extras arriba; lo aplica el reparto a lo que no es Mercado Pago). Una sola
    # funcion cubre cualquier reparto: 50/50, 70/30, tres medios, etc. El solver
    # no calcula ni una cifra: pasa 'pago' y el codigo devuelve el bloque sellado.
    base_total = total + extra_min
    if pago and not hay_rango:
        from app.core.pago_split import calcular_split, render_split
        _pct = 0
        try:
            from app.storage.firestore_client import get_all_faq as _gaf_pct
            _vt = (((_gaf_pct(tienda_id=tid) or {}).get("descuento_transferencia")
                    or {}).get("valores") or [])
            _dv = next((v for v in _vt
                        if (v.get("unidad") or "").lower() == "porcentaje"), None)
            if _dv:
                _pct = int(_dv.get("monto", 0))
        except Exception as _e:
            log.warning(f"calculate_total split_pct_faq_error {_e}")
        _split = calcular_split(base_total, pago, _pct)
        if _split.get("ok"):
            _pres = _render_presentacion(
                detalle, extras_detalle, total, total_ars=base_total)
            _pres = _pres + "\n\n" + render_split(_split)
            # El proof del split respalda TODOS los montos de la presentacion:
            # renglones, subtotal y EXTRAS (envio). Sin el envio en el proof,
            # el verificador lo tomaba por no respaldado y lo "autocorregia"
            # a un valor de la FAQ (visto 11-jul: envio La Plata $6.000
            # cotizado bien y pisado a $5.000 en el mensaje final).
            _montos_proof = ([base_total, _split["total_final_ars"],
                              _split["descuento_total_ars"], total]
                             + [p["monto_ars"] for p in _split["partes"]]
                             + [p["monto_final_ars"] for p in _split["partes"]]
                             + [d["subtotal"] for d in detalle]
                             + [d["precio_unitario"] for d in detalle]
                             + [e.get("monto") for e in extras_detalle
                                if isinstance(e.get("monto"), (int, float))])
            return {
                "ok": True,
                "mensaje_para_llm": _nota_envio,
                "total_ars": base_total,
                "total_final_ars": _split["total_final_ars"],
                "split_pago": _split,
                "subtotal_productos_ars": total,
                "presentacion": _pres,
                "proof": {
                    "tipo": "calculo_total_split_pago",
                    "formula": ("base productos+envio repartida por porcentaje; "
                                "descuento por transferencia a lo que no es "
                                "Mercado Pago"),
                    "operandos_productos": [
                        {"id": d["id"], "monto": d["subtotal"],
                         "precio_unitario": d["precio_unitario"],
                         "fuente": "catalogo"}
                        for d in detalle
                    ],
                    "operandos_extras": extras_detalle,
                    "subtotal_productos": total,
                    "base_total": base_total,
                    "split": _split,
                    "montos": _montos_proof,
                    "resultado": _split["total_final_ars"],
                },
                "detalle": detalle,
                "extras": extras_detalle,
            }
        log.warning(f"calculate_total split_invalido motivo={_split.get('motivo')}")

    return {
        "ok": True,
        "mensaje_para_llm": _nota_envio,
        "total_ars": total + extra_min,
        "subtotal_productos_ars": total,
        "presentacion": _render_presentacion(
            detalle, extras_detalle, total, total_ars=total + extra_min),
        "proof": {
            "tipo": "calculo_total_fijo",
            "formula": "suma_productos + suma_extras (extras pueden ser montos fijos o porcentajes; los descuentos restan)",
            "operandos_productos": [
                {"id": d["id"], "monto": d["subtotal"],
                 "precio_unitario": d["precio_unitario"],
                 "fuente": "catalogo"}
                for d in detalle
            ],
            "operandos_extras": extras_detalle,
            "subtotal_productos": total,
            "resultado": total + extra_min,
        },
        "detalle": detalle,
        "extras": extras_detalle,
    }


# ────────────────────────────────────────────────────────────
# 4) ENCONTRAR DENTRO DE PRESUPUESTO
# ────────────────────────────────────────────────────────────

# ────────────────────────────────────────────────────────────
# 5) COMPARAR
# ────────────────────────────────────────────────────────────

# ────────────────────────────────────────────────────────────
# 6) RECOMENDAR
# ────────────────────────────────────────────────────────────

# ────────────────────────────────────────────────────────────
# 7) FAQ
# ────────────────────────────────────────────────────────────

# Senal determinista de PLAZO de entrega (charla real 10-jul: "cuanto demoran
# los envios" y "en cuanto tiempo llegan los productos" caian al tema generico
# 'envios' y el cliente pregunto CINCO veces la demora sin respuesta). Las
# conjugaciones (demoran/tardan/llegan) y "cuanto tiempo" no matchean las
# keywords de plazo_envio; esta senal re-rankea plazo_envio arriba de todo
# cuando la consulta habla de tiempo de entrega.
import re as _re_plazo
_RE_SENAL_PLAZO = _re_plazo.compile(
    r"\b(demora\w*|tarda\w*|plazo\w*|cuanto tiempo|cuantos dias|"
    r"en cuanto (tiempo )?(llega\w*|esta\w*|tengo)|cuando (llega\w*|estaria))\b")














# ────────────────────────────────────────────────────────────
# 8) LISTAR CATALOGO
# ────────────────────────────────────────────────────────────

# Helper
# ────────────────────────────────────────────────────────────



# ────────────────────────────────────────────────────────────
# REGISTRY: schemas y mapeo de funciones
# ────────────────────────────────────────────────────────────

def _umbral_envio_gratis(valores: list) -> int:
    """Umbral de envio gratis desde la FAQ costo_envio: UNICA fuente, el MISMO dato
    que se le dice al cliente. Lo saca del concepto envio_gratis (campo estructurado
    umbral_ars/base_ars/monto_min, o el numero de su 'condicion', ej 'compra mayor a
    250000'). Cae al default de plataforma SOLO si la FAQ no lo trae. Asi el numero
    que el codigo aplica y el que el bot publica nunca pueden divergir (era el bug:
    FAQ 250000 vs setting 300000)."""
    for v in valores or []:
        if str(v.get("concepto", "")).lower() != "envio_gratis":
            continue
        for k in ("umbral_ars", "base_ars", "monto_min"):
            n = v.get(k)
            if isinstance(n, (int, float)) and n > 0:
                return int(n)
        digitos = "".join(c for c in str(v.get("condicion", "")) if c.isdigit())
        if digitos:
            return int(digitos)
    return settings.UMBRAL_ENVIO_GRATIS


def cotizar_envio(localidad: str | None = None,
                  subtotal: int | None = None) -> dict:
    """Cotiza el envio de forma determinista: el CODIGO clasifica la zona desde el
    codigo postal o la localidad (no el modelo) y devuelve la tarifa de la tienda.

    localidad: texto con el codigo postal, la localidad y/o la provincia del cliente.
    subtotal: subtotal de productos, para aplicar envio gratis por umbral si supera.
    """
    from app.core.envio import clasificar_zona

    # Si el Solver no paso localidad pero el cliente YA dio su direccion (esta en el
    # ESTADO del turno), se usa esa para clasificar la zona. Asi no se le vuelve a
    # pedir el codigo postal que ya dio. Solo actua cuando el modelo no manda nada.
    if not (localidad or "").strip():
        from app.core.estado_venta import get_current_estado
        _dc = get_current_estado().get("datos_cliente") or {}
        _dir = (_dc.get("direccion") or "").strip()
        if _dir:
            log.info(f"cotizar_envio direccion_estado={_dir[:60]}")
            localidad = _dir

    # Disclaimer de envio (determinista): el Solver lo cierra como oracion aparte y
    # EXACTA, asi no se mezcla con su redaccion ni promete un precio grabado. Cubre
    # la realidad inflacionaria sin asustar al cliente. No aplica a envio gratis.
    _NOTA_ENVIO = (
        " Cerra la parte del envio con esta frase EXACTA, como oracion aparte: "
        "\"Envío orientativo, puede variar al confirmar la compra.\"")

    tid = get_current_tienda()
    zona = clasificar_zona(localidad or "")
    if zona is None and (localidad or "").strip():
        # PROVINCIA DE LA CHARLA: si el cliente ya dio la provincia (en este
        # mensaje o en turnos anteriores, sticky en el estado), una localidad
        # ambigua o desconocida se reintenta como "localidad, provincia" (la
        # tabla resuelve ambiguas solo con la provincia en el texto). Caso real
        # 8-jul: 'Los Condores' fallaba con 'todos en provincia de Cordoba'
        # dicho en el MISMO mensaje, y el bot re-pedia el CP que ya tenia.
        from app.core.estado_venta import get_current_estado
        _prov = (get_current_estado().get("provincia_envio") or "").strip()
        # La provincia sticky NO completa basura (charla real 19-jul: "la otra
        # direccion" + "santa fe" cotizaba como destino valido): el reintento
        # corre solo si el texto nombra un lugar de la tabla geo.
        from app.core.geo_cp import es_lugar_conocido
        if _prov and es_lugar_conocido(localidad):
            _con_prov = f"{localidad}, {_prov}"
            zona = clasificar_zona(_con_prov)
            if zona is not None:
                log.info(f"cotizar_envio provincia_de_charla={_prov}")
                localidad = _con_prov
    if zona is None:
        # Con tabla por provincia, el dato util es la PROVINCIA o el CP: con eso
        # la tarifa sale exacta, no en rango. Nunca se adivina la zona.
        return {
            "ok": False,
            "zona": None,
            "mensaje_para_llm": (
                "No pude determinar la zona con ese dato. Pedile UNA vez la "
                "PROVINCIA o el CODIGO POSTAL (ej: cordoba, o CP 5121): con "
                "eso te doy la tarifa exacta. NO asumas la zona ni la tarifa."
            ),
        }

    # Zona resuelta: guardo la localidad efectiva para que calculate_total le pida
    # el costo a ESTA misma herramienta (unica fuente del envio), sin recalcularla.
    from app.core.estado_venta import set_envio_localidad
    set_envio_localidad(localidad)

    faqs = get_all_faq(tienda_id=tid) or {}
    faq = faqs.get("costo_envio")
    if not faq or faq.get("tipo") != "cuantitativo":
        return {
            "ok": False,
            "zona": zona,
            "mensaje_para_llm": (
                "No tengo cargada la tarifa de envio de la tienda. Deci que lo "
                "consultas y lo confirmas, no inventes un monto."
            ),
        }
    valores = faq.get("valores") or []

    # Envio gratis por umbral: sale de la FAQ costo_envio (UNICA fuente, el mismo
    # numero que el bot le dice al cliente), con el default de plataforma solo como
    # respaldo. Si el subtotal lo supera, es gratis.
    umbral = _umbral_envio_gratis(valores)
    if subtotal and isinstance(subtotal, (int, float)) and subtotal > umbral:
        return {
            "ok": True, "zona": zona, "concepto": "envio_gratis",
            "modalidad": "fijo", "monto": 0,
            "mensaje_para_llm": (
                f"Envio GRATIS: la compra supera {umbral} pesos. Zona {zona}. "
                f"Para dar el TOTAL llama calculate_total con TODOS los "
                f"productos del pedido e items_extra "
                f"{{faq_tema: costo_envio, concepto: envio_gratis}}; NO sumes "
                f"a mano ni dejes productos afuera."),
            "proof": {"tipo": "envio", "valores": [0], "resultado": 0},
        }

    # Tarifa EXACTA por provincia (unico camino, sin flag): si la provincia se
    # determina con certeza, se devuelve su monto fijo en vez del rango generico de
    # interior. La fuente de verdad es config.py (ENVIO_INTERIOR_POR_PROVINCIA); una
    # tabla en Firestore 'tarifas_envio' pisa ese default por tienda. Si la provincia
    # no se determina, cae al colapso por tope de abajo: nunca se adivina la zona.
    if zona == "interior":
        from app.core.envio import clasificar_provincia
        from app.storage.firestore_client import get_config
        prov = clasificar_provincia(localidad or "")
        if prov:
            try:
                tabla = get_config("tarifas_envio", tienda_id=tid) or {}
            except Exception as e:
                log.warning("tarifas_envio_read_error", error=str(e)[:120])
                tabla = {}
            # Firestore pisa; si no hay, el mapa del codigo (fuente de verdad).
            monto_prov = (tabla.get("provincias") or {}).get(prov) \
                or settings.ENVIO_INTERIOR_POR_PROVINCIA.get(prov)
            if monto_prov:
                monto_prov = int(monto_prov)
                prov_legible = prov.replace("_", " ").title()
                return {
                    "ok": True, "zona": zona, "provincia": prov,
                    "concepto": f"envio_{prov}".replace(" ", "_"),
                    "modalidad": "fijo", "monto": monto_prov,
                    "mensaje_para_llm": (
                        f"Envio a {prov_legible}: {monto_prov} pesos, tarifa "
                        f"exacta de esa provincia. Usa este monto, no el rango. "
                        f"Para dar el TOTAL llama calculate_total con TODOS los "
                        f"productos del pedido e items_extra "
                        f"{{faq_tema: costo_envio, concepto: envio_{prov}}}; "
                        f"NO sumes a mano ni dejes productos afuera." + _NOTA_ENVIO),
                    "proof": {"tipo": "envio", "valores": [monto_prov],
                              "resultado": monto_prov},
                }

    # Mapeo zona -> concepto por SUBCADENA del nombre (no por nombre exacto), asi
    # tolera variantes de naming entre tiendas. caba/gba comparten tarifa metropolitana.
    claves = ("caba", "gba", "metropol", "amba") if zona in ("caba", "gba") \
        else ("interior",)
    valor = next((v for v in valores
                  if any(k in str(v.get("concepto", "")).lower() for k in claves)),
                 None)
    if not valor:
        return {
            "ok": False, "zona": zona,
            "mensaje_para_llm": (
                f"La tienda no tiene tarifa cargada para la zona {zona}. Deci que "
                "lo consultas, no inventes el monto."),
        }

    modalidad = (valor.get("modalidad") or "fijo").lower()
    if modalidad == "rango":
        mn, mx = int(valor.get("monto_min", 0)), int(valor.get("monto_max", 0))
        # MATAR EL RANGO EN LA FUENTE: sin tarifa exacta por provincia, el interior
        # devuelve UN numero fijo (el tope publicado monto_max: dato real, nunca
        # inventado) en vez de un rango. Asi el Solver no tiene rango dentro del cual
        # inventar una cifra (el caso $7.500), la melliza tiene un valor exacto que
        # enforce y el total sale unico. Conservador: cobra el tope, y el disclaimer
        # avisa que puede variar; cargar tarifas_envio por provincia lo afina hacia
        # abajo cuando la tienda quiera tarifas mas finas.
        monto = mx
        return {
            "ok": True, "zona": zona, "concepto": valor.get("concepto"),
            "modalidad": "fijo", "monto": monto,
            "mensaje_para_llm": (
                f"Envio a zona {zona}: {monto} pesos, tarifa fija de la zona. Usa "
                f"este monto EXACTO, nunca un rango ni un promedio. Para dar el "
                f"TOTAL llama calculate_total con TODOS los productos del pedido e "
                f"items_extra {{faq_tema: costo_envio, concepto: {valor.get('concepto')}}}; "
                f"NO sumes a mano ni dejes productos afuera." + _NOTA_ENVIO),
            "proof": {"tipo": "envio", "valores": [monto], "resultado": monto},
        }
    monto = int(valor.get("monto", 0))
    return {
        "ok": True, "zona": zona, "concepto": valor.get("concepto"),
        "modalidad": "fijo", "monto": monto,
        "mensaje_para_llm": (
            f"Envio a zona {zona}: {monto} pesos. Para dar el TOTAL llama "
            f"calculate_total con TODOS los productos del pedido e items_extra "
            f"{{faq_tema: costo_envio, concepto: {valor.get('concepto')}}}; "
            f"NO sumes a mano ni dejes productos afuera." + _NOTA_ENVIO),
        "proof": {"tipo": "envio", "valores": [monto], "resultado": monto},
    }








# TOOLS_REGISTRY y get_tools_schema se borraron el 29-jul: eran el contrato de
# TOOL CALLING del solver viejo. El camino atado no llama tools, emite fragmentos
# con responseSchema y el codigo ejecuta lo que hace falta. Lo unico que quedo
# del vocabulario de tools son los NOMBRES, que generador_v2 sigue usando como
# etiqueta de traza para que evidencia.py arme la evidencia del turno.
