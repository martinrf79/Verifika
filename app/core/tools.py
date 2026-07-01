"""
TOOLS v4 — funciones que el LLM puede invocar.

Multi-tenant: cada tool resuelve la tienda actual desde tools_context (ContextVar).
El LLM no ve este parámetro. El orchestrator lo setea antes de invocar al agente.
"""
from app.storage.firestore_client import (
    get_all_products,
    get_product_by_id,
    get_categories,
    get_all_faq,
)
from app.storage.search import hybrid_search_relajada
from app.config import get_settings
from app.logger import get_logger
from app.core.tools_context import get_current_tienda

log = get_logger(__name__)
settings = get_settings()


# ────────────────────────────────────────────────────────────
# 1) BUSCAR PRODUCTOS (con búsqueda híbrida)
# ────────────────────────────────────────────────────────────

def search_products(query: str | None = None,
                    categoria: str | None = None,
                    precio_min: int | None = None,
                    precio_max: int | None = None) -> dict:
    """Busca productos en Firestore con escalera de relajacion: si la palabra
    del cliente no engancha pero la categoria tiene productos reales, los ofrece
    igual en vez de negar stock que existe (cura el bug de 0 ventas por negar
    stock). Es el unico camino de busqueda; sin flag."""
    tid = get_current_tienda()

    r = hybrid_search_relajada(
        query=query, categoria=categoria, precio_min=precio_min,
        precio_max=precio_max, top_n=settings.SEARCH_TOP_N, tienda_id=tid)
    productos = r["productos"]
    if productos and not r["match_exacto"]:
        cat = r.get("categoria_usada") or "esa"
        return {
            "encontrados": len(productos),
            "productos": [_resumir(p) for p in productos],
            "match_exacto": False,
            "mensaje_para_llm": (
                f"No encontre coincidencia textual con '{query}', pero la "
                f"categoria '{cat}' tiene {r['total_categoria']} productos "
                f"reales en stock; aca van los mas economicos. OFRECELOS al "
                f"cliente como opciones. NO digas que no tenemos: el dato "
                f"especifico que pidio no figura textual, pero estos "
                f"productos existen y estan disponibles."
            ),
        }
    if not productos:
        cats = r.get("categorias_disponibles") or []
        return {
            "encontrados": 0,
            "productos": [],
            "mensaje_para_llm": (
                "No hay productos que cumplan los criterios. "
                "Decile al cliente honestamente que no tenemos algo así y "
                f"ofrecele la categoría más cercana. Categorías reales del "
                f"catálogo: {cats}."
            ),
        }
    return {
        "encontrados": len(productos),
        "productos": [_resumir(p) for p in productos],
    }


# ────────────────────────────────────────────────────────────
# 2) DETALLE
# ────────────────────────────────────────────────────────────

def get_product_details(product_id: str) -> dict:
    tid = get_current_tienda()
    p = get_product_by_id(product_id, tienda_id=tid)
    if not p:
        return {
            "encontrado": False,
            "mensaje_para_llm": f"No existe producto con ID {product_id}.",
        }
    return {"encontrado": True, "producto": _resumir(p)}


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


def calculate_total(items: list[dict] | None = None,
                    items_extra: list[dict] | None = None,
                    destinos: int = 1) -> dict:
    log.info(f"calculate_total INICIO items={items} items_extra={items_extra} destinos={destinos}")
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

    tid = get_current_tienda()
    detalle = []
    total = 0
    no_encontrados = []
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
            from app.core.estado_venta import get_envio_localidad
            quote = cotizar_envio(localidad=get_envio_localidad(), subtotal=total)
            if not quote.get("ok"):
                return {"ok": False, "mensaje_para_llm": quote.get(
                    "mensaje_para_llm",
                    "Para sumar el envio al total necesito la zona. Pedile al "
                    "cliente la provincia o el codigo postal y cotiza el envio "
                    "con cotizar_envio antes de calcular el total.")}
            concepto_env = quote.get("concepto") or "envio"
            if quote.get("modalidad") == "rango":
                mn = int(quote.get("monto_min", 0)) * n_envios
                mx = int(quote.get("monto_max", 0)) * n_envios
                extra_min += mn
                extra_max += mx
                hay_rango = True
                extras_detalle.append({
                    "faq_tema": "costo_envio", "concepto": concepto_env,
                    "modalidad": "rango", "monto_min": mn, "monto_max": mx,
                    **({"destinos": n_envios} if n_envios > 1 else {}),
                    "condicion": "tarifa de envio cotizada por zona",
                })
            else:
                m = int(quote.get("monto", 0)) * n_envios
                extra_min += m
                extra_max += m
                if m == 0:
                    envio_gratis_aplicado = True
                extras_detalle.append({
                    "faq_tema": "costo_envio", "concepto": concepto_env,
                    "modalidad": "fijo", "monto": m,
                    **({"destinos": n_envios} if n_envios > 1 else {}),
                    **({"envio_gratis_auto": True} if m == 0 else {}),
                    "condicion": ("envio gratis por umbral" if m == 0
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

def find_within_budget(presupuesto_max: int,
                       categorias: list[str] | None = None) -> dict:
    tid = get_current_tienda()
    productos = get_all_products(tienda_id=tid)
    if categorias is None:
        categorias = ["monitores", "teclados", "mouse", "audio"]

    cats_validas_global = set(get_categories(tienda_id=tid))
    cats_validas = [c for c in categorias if c in cats_validas_global]
    if not cats_validas:
        return {
            "ok": False,
            "mensaje_para_llm": (
                f"Categorías inválidas. Disponibles: {sorted(cats_validas_global)}."
            ),
        }

    seleccion = []
    restante = presupuesto_max

    for cat in cats_validas:
        candidatos = [
            p for p in productos
            if p["categoria"] == cat and p.get("stock", 0) > 0
        ]
        candidatos.sort(key=lambda p: p["precio_ars"])
        elegido = next((p for p in candidatos if p["precio_ars"] <= restante), None)
        if elegido:
            seleccion.append(elegido)
            restante -= elegido["precio_ars"]

    cats_ordenadas = sorted(
        cats_validas,
        key=lambda c: max(
            (p["precio_ars"] for p in productos if p["categoria"] == c),
            default=0,
        ),
        reverse=True,
    )

    for cat in cats_ordenadas:
        actual = next((p for p in seleccion if p["categoria"] == cat), None)
        if not actual:
            continue
        candidatos_upgrade = [
            p for p in productos
            if p["categoria"] == cat
            and p.get("stock", 0) > 0
            and p["precio_ars"] > actual["precio_ars"]
            and (p["precio_ars"] - actual["precio_ars"]) <= restante
        ]
        if candidatos_upgrade:
            mejor_upgrade = max(candidatos_upgrade, key=lambda p: p["precio_ars"])
            restante -= (mejor_upgrade["precio_ars"] - actual["precio_ars"])
            idx = seleccion.index(actual)
            seleccion[idx] = mejor_upgrade

    seleccion = [_resumir(p) for p in seleccion]

    if not seleccion:
        precios = [p["precio_ars"] for p in productos if p.get("stock", 0) > 0]
        min_precio = min(precios) if precios else 0
        return {
            "ok": False,
            "presupuesto": presupuesto_max,
            "mensaje_para_llm": (
                f"Con ${presupuesto_max:,} no llegamos a armar nada. "
                f"El producto más barato es ${min_precio:,}."
            ),
        }

    total = sum(p["precio_ars"] for p in seleccion)
    ahorro = presupuesto_max - total
    return {
        "ok": True,
        "presupuesto": presupuesto_max,
        "total_seleccion": total,
        "ahorro": ahorro,
        "productos": seleccion,
        "completo": len(seleccion) == len(cats_validas),
        # PROOF para que el verificador respalde el total y el ahorro.
        "proof": {
            "tipo": "presupuesto",
            "valores": [total, ahorro, presupuesto_max]
                       + [int(p["precio_ars"]) for p in seleccion],
            "resultado": total,
        },
    }


# ────────────────────────────────────────────────────────────
# 5) COMPARAR
# ────────────────────────────────────────────────────────────

def compare_products(product_ids: list[str]) -> dict:
    if len(product_ids) < 2:
        return {"ok": False, "mensaje_para_llm": "Mínimo 2 productos."}

    tid = get_current_tienda()
    productos = []
    no_encontrados = []
    for pid in product_ids:
        p = get_product_by_id(pid, tienda_id=tid)
        if p:
            productos.append(_resumir(p))
        else:
            no_encontrados.append(pid)

    if no_encontrados:
        return {"ok": False, "mensaje_para_llm": f"No existen: {no_encontrados}."}

    precios = [p["precio_ars"] for p in productos]
    diferencia = max(precios) - min(precios)
    return {
        "ok": True,
        "productos": productos,
        "mas_caro": productos[precios.index(max(precios))]["nombre"],
        "mas_barato": productos[precios.index(min(precios))]["nombre"],
        "diferencia_precio": diferencia,
        # PROOF para que el verificador respalde la diferencia de precio.
        "proof": {
            "tipo": "comparacion",
            "valores": [diferencia] + precios,
        },
    }


# ────────────────────────────────────────────────────────────
# 6) RECOMENDAR
# ────────────────────────────────────────────────────────────

def recommend_product(criterio: str = "precio_calidad",
                      categoria: str | None = None) -> dict:
    tid = get_current_tienda()
    productos = get_all_products(tienda_id=tid)
    if categoria:
        candidatos = [
            p for p in productos
            if p["categoria"].lower() == categoria.lower() and p.get("stock", 0) > 0
        ]
    else:
        candidatos = [p for p in productos if p.get("stock", 0) > 0]

    if not candidatos:
        return {"ok": False, "mensaje_para_llm": "No hay productos disponibles."}

    candidatos.sort(key=lambda p: p["precio_ars"])

    if criterio == "precio_calidad":
        elegido = candidatos[len(candidatos) // 2]
        razon = "buena relación precio-calidad (precio intermedio)"
    elif criterio == "principiante":
        elegido = candidatos[0]
        razon = "ideal para empezar, opción más accesible"
    elif criterio == "premium":
        elegido = candidatos[-1]
        razon = "la opción top de la categoría"
    else:
        return {"ok": False, "mensaje_para_llm": f"Criterio '{criterio}' no válido."}

    return {"ok": True, "producto": _resumir(elegido), "razon": razon}


# ────────────────────────────────────────────────────────────
# 7) FAQ
# ────────────────────────────────────────────────────────────

def _norm_txt(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(s).lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _canon_palabra(w: str) -> str:
    """saca una s final para tolerar plurales (envios->envio, cuotas->cuota)."""
    return w[:-1] if len(w) > 3 and w.endswith("s") else w


def _faq_ranking_palabras(consulta: str, faq: dict) -> list[tuple[int, str]]:
    """Rankea temas de FAQ: una keyword matchea si TODAS sus palabras aparecen
    en la consulta (normalizadas, tolerantes a plural), aunque haya palabras en
    el medio. Asi 'costo envio' engancha 'costo de envio a cordoba' y el tema
    especifico con el numero le gana al generico. Devuelve [(score, tema)]
    de mayor a menor, solo los que matchean."""
    palabras_consulta = {_canon_palabra(w) for w in _norm_txt(consulta).split()}
    ranking = []
    for tema, data in faq.items():
        score = 0
        for kw in data.get("keywords", []) or []:
            k = _norm_txt(kw)
            kws = {_canon_palabra(w) for w in k.split()}
            if kws and kws <= palabras_consulta:
                score += len(k)
        if score > 0:
            ranking.append((score, tema))
    ranking.sort(key=lambda t: (-t[0], t[1]))
    return ranking


def _faq_keyword_match(consulta: str, faq: dict):
    """Elige el tema de FAQ por keywords, sin modelo. Puntua por largo de las
    keywords que matchean, asi las frases mas especificas, costo envio, ganan
    a las generales, envio. Devuelve None si no matchea, para caer al modelo."""
    c = _norm_txt(consulta)
    mejor, mejor_score = None, 0
    for tema, data in faq.items():
        score = 0
        for kw in data.get("keywords", []) or []:
            k = _norm_txt(kw)
            if k and k in c:
                score += len(k)
        if score > mejor_score:
            mejor_score, mejor = score, tema
    return mejor if mejor_score > 0 else None


def _faq_candidatos(consulta: str, faq: dict, n: int = 5) -> list[str]:
    """Preselecciona los N temas mas plausibles para el fallback del LLM, cuando
    el match estricto fallo. Score = palabras de la consulta que aparecen en las
    keywords o en el nombre del tema (solapamiento PARCIAL, basta una palabra).
    Asi el LLM recibe pocos candidatos en vez de los 44 temas enteros: mismo
    rescate semantico, mucho menos prompt. Devuelve los temas de mayor a menor."""
    palabras = {_canon_palabra(w) for w in _norm_txt(consulta).split() if len(w) > 2}
    if not palabras:
        return list(faq.keys())[:n]
    puntajes = []
    for tema, data in faq.items():
        vocab = {_canon_palabra(w) for w in _norm_txt(tema).split()}
        for kw in data.get("keywords", []) or []:
            vocab |= {_canon_palabra(w) for w in _norm_txt(kw).split()}
        score = len(palabras & vocab)
        if score > 0:
            puntajes.append((score, tema))
    if not puntajes:
        return list(faq.keys())[:n]
    puntajes.sort(key=lambda t: (-t[0], t[1]))
    return [tema for _, tema in puntajes[:n]]


def _faq_resp(tema: str, data: dict) -> dict:
    resp = {
        "encontrada": True,
        "tema": tema,
        "respuesta": data.get("respuesta", ""),
        "tipo": data.get("tipo", "informativo"),
    }
    if data.get("tipo") == "cuantitativo":
        resp["conceptos_disponibles"] = [
            v.get("concepto") for v in data.get("valores", []) if v.get("concepto")
        ]
    return resp


def query_faq(consulta: str) -> dict:
    """
    Busca FAQ relevante usando el LLM como retriever semantico.
    Le pasa al LLM la lista de temas con sus respuestas y el LLM decide
    cual aplica. Resuelve reformulaciones, sinonimos, errores de tipeo.
    """
    from app.verifika.llm_adapter import llm_complete
    import json as _json

    tid = get_current_tienda()
    faq = get_all_faq(tienda_id=tid)
    if not faq:
        return {"encontrada": False, "mensaje_para_llm": "FAQ vacia"}

    # Matcheo por palabras (unico camino, sin flag): el tema especifico gana al
    # generico y la respuesta lleva hasta dos temas relacionados, asi el Solver ve
    # el cajon con el numero (costo_envio) y no solo el informativo (envios).
    ranking = _faq_ranking_palabras(consulta, faq)
    if ranking:
        principal = ranking[0][1]
        log.info("query_faq_palabras_hit", tema=principal,
                 relacionadas=[t for _, t in ranking[1:3]])
        resp = _faq_resp(principal, faq[principal])
        relacionadas = []
        for _, tema in ranking[1:3]:
            rel = _faq_resp(tema, faq[tema])
            rel.pop("encontrada", None)
            relacionadas.append(rel)
        if relacionadas:
            resp["relacionadas"] = relacionadas
        return resp

    # Keyword-first: si matchea, resolvemos sin llamar al modelo.
    tema_kw = _faq_keyword_match(consulta, faq)
    if tema_kw:
        log.info("query_faq_keyword_hit", tema=tema_kw)
        return _faq_resp(tema_kw, faq[tema_kw])

    # Fallback semantico: solo los temas candidatos y solo su nombre + keywords,
    # no la respuesta entera de los 44. Recorta el prompt sin perder la eleccion:
    # el LLM elige el TEMA y la respuesta completa la trae el codigo despues.
    candidatos = _faq_candidatos(consulta, faq)
    temas_texto = ""
    for tema in candidatos:
        kws = ", ".join((faq[tema].get("keywords") or [])[:8])
        temas_texto += "\n- tema: " + tema + "\n  cubre: " + kws + "\n"

    system_prompt = (
        "Sos un buscador de FAQ. Recibis una consulta y una lista de temas con las "
        "palabras que cubre cada uno. Elegi UN tema que responda directamente, o deci "
        "que ninguno aplica.\n"
        "REGLAS:\n"
        "1. Solo elegi un tema si claramente cubre lo que pide el cliente.\n"
        "2. Si la consulta menciona costos, plazos, pagos, envios, garantia, devoluciones, "
        "buscá el tema que cubra eso.\n"
        "3. Si ningun tema aplica, devolve tema vacio.\n"
        "4. Devolve SOLO JSON estricto: "
        '{\"tema\": \"nombre\" o \"\"}'
    )

    user_message = "CONSULTA:\n" + consulta + "\n\nTEMAS DISPONIBLES:" + temas_texto + "\n\nDevolve el JSON."

    try:
        result = llm_complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            role="proposer",
            temperature=0.0,
            max_tokens=80,
        )
    except Exception as e:
        log.warning("query_faq_llm_error", error=str(e)[:150])
        return {"encontrada": False, "mensaje_para_llm": "error de busqueda"}

    content = result.get("content", "").strip()
    if content.startswith("```"):
        content = content.split("```")[1] if "```" in content[3:] else content[3:]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    try:
        parsed = _json.loads(content)
        tema_elegido = parsed.get("tema", "").strip()
    except Exception:
        tema_elegido = ""

    if tema_elegido and tema_elegido in faq:
        log.info("query_faq_hit", tema=tema_elegido)
        return _faq_resp(tema_elegido, faq[tema_elegido])

    return {
        "encontrada": False,
        "mensaje_para_llm": (
            "No hay FAQ que responda a esto. Decile al cliente que vas a "
            "consultar y le confirmas, o pedile que reformule."
        ),
    }


# ────────────────────────────────────────────────────────────
# 8) LISTAR CATALOGO
# ────────────────────────────────────────────────────────────

def list_catalog(categoria: str | None = None) -> dict:
    """
    Lista el catalogo completo, o el de una categoria, en formato compacto.
    Para responder "que tenes", "mostrame todo", "lista completa". A diferencia
    de search_products, NO depende de que la busqueda por keywords enganche:
    devuelve TODO el inventario real de la tienda.
    """
    tid = get_current_tienda()
    productos = get_all_products(tienda_id=tid)
    if categoria:
        cat = categoria.strip().lower()
        productos = [
            p for p in productos
            if str(p.get("categoria", "")).lower() == cat
        ]
        if not productos:
            cats = sorted(get_categories(tienda_id=tid))
            return {
                "ok": False,
                "mensaje_para_llm": (
                    f"No hay productos en la categoria '{categoria}'. "
                    f"Categorias disponibles: {cats}."
                ),
            }
    productos = sorted(
        productos,
        key=lambda p: (str(p.get("categoria", "")), p.get("precio_ars", 0)),
    )
    items = [
        {
            "id": p["id"],
            "nombre": p["nombre"],
            "categoria": str(p.get("categoria", "")),
            "precio_ars": p["precio_ars"],
            "stock": p.get("stock", 0),
        }
        for p in productos
    ]
    resumen: dict[str, int] = {}
    for it in items:
        resumen[it["categoria"]] = resumen.get(it["categoria"], 0) + 1
    return {
        "ok": True,
        "total": len(items),
        "categorias_resumen": resumen,
        "productos": items,
    }


# Helper
# ────────────────────────────────────────────────────────────

def _resumir(p: dict) -> dict:
    """
    Devuelve TODOS los campos del producto (excepto embedding y campos internos)
    para que el Solver y Verifika puedan ver toda la informacion del catalogo.
    Esto resuelve alucinaciones tipo "todos hechos en China" o "es de aluminio"
    cuando el cliente extendio el CSV con campos como origen, material, garantia, etc.
    """
    EXCLUIR = {"embedding", "_id", "created_at", "updated_at"}
    return {k: v for k, v in p.items() if k not in EXCLUIR and not k.startswith("_")}


# ────────────────────────────────────────────────────────────
# REGISTRY: schemas y mapeo de funciones
# ────────────────────────────────────────────────────────────

def _build_schema():
    """Schema dinámico. Las categorías reflejan las de la tienda actual."""
    try:
        cats = get_categories(tienda_id=get_current_tienda())
    except Exception:
        cats = []

    schemas = [
        {
            "type": "function",
            "function": {
                "name": "search_products",
                "description": (
                    "Busca productos en el catálogo. Usar SIEMPRE que el cliente "
                    "mencione cualquier producto, marca, categoría o palabra "
                    "relacionada. Devuelve los TOP 10 más relevantes."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Texto libre para buscar. Opcional.",
                        },
                        "categoria": {
                            "type": "string",
                            "description": f"Categoría a filtrar. Disponibles: {cats}",
                        },
                        "precio_min": {"type": "integer"},
                        "precio_max": {"type": "integer"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_product_details",
                "description": "Detalle completo de un producto por su ID.",
                "parameters": {
                    "type": "object",
                    "properties": {"product_id": {"type": "string"}},
                    "required": ["product_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calculate_total",
                "description": (
                    "Calcula total exacto de N productos del catalogo, opcionalmente sumando "
                    "extras verificados contra FAQ cuantitativa (envios, descuentos, recargos). "
                    "USAR SIEMPRE para sumas. NUNCA calcules vos mismo. "
                    "Si el cliente pide total con envio u otro concepto de FAQ, pasalo en items_extra. "
                    "PAGO MIXTO: si el cliente paga unidades con metodos distintos (una por "
                    "transferencia, otra con otro medio), hace UNA llamada por cada grupo de pago, "
                    "cada una con sus items y su descuento si corresponde. NUNCA repartas ni "
                    "prorratees un descuento entre unidades vos mismo."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "description": "Productos del catalogo",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "product_id": {"type": "string"},
                                    "cantidad": {"type": "integer", "minimum": 1},
                                },
                                "required": ["product_id", "cantidad"],
                            },
                        },
                        "items_extra": {
                            "type": "array",
                            "description": "Extras del total. Para descuentos, recargos, sena o cuotas: faq_tema es el ID de la FAQ cuantitativa y concepto es el id del valor (ej transferencia, financiacion). Para INCLUIR EL ENVIO en el total: pasa un extra con faq_tema costo_envio; el concepto es opcional y se ignora, el costo lo resuelve cotizar_envio por la zona. Cotiza el envio con cotizar_envio ANTES de pedir el total con envio.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "faq_tema": {"type": "string"},
                                    "concepto": {"type": "string"},
                                },
                                "required": ["faq_tema", "concepto"],
                            },
                        },
                        "destinos": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "description": "Cantidad de envios SEPARADOS del pedido (direcciones distintas). 1 por defecto. Si el cliente pide mandar a varias direcciones distintas, poner ese numero: el costo de envio se cobra una vez por cada destino y el total sale como rango.",
                        },
                    },
                    "required": ["items"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "find_within_budget",
                "description": "Arma combinación de productos dentro de un presupuesto.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "presupuesto_max": {"type": "integer"},
                        "categorias": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["presupuesto_max"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "compare_products",
                "description": "Compara 2+ productos lado a lado.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 2,
                        },
                    },
                    "required": ["product_ids"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "recommend_product",
                "description": "Recomienda producto: precio_calidad | principiante | premium.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "criterio": {
                            "type": "string",
                            "enum": ["precio_calidad", "principiante", "premium"],
                        },
                        "categoria": {"type": "string"},
                    },
                    "required": ["criterio"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_faq",
                "description": (
                    "Consulta FAQ del negocio: envíos, pagos, garantía, "
                    "devoluciones, horarios, ubicación, factura."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"consulta": {"type": "string"}},
                    "required": ["consulta"],
                },
            },
        },
    ]

    # Herramienta de listar catalogo completo o por categoria.
    schemas.append({
        "type": "function",
        "function": {
            "name": "list_catalog",
            "description": (
                "Lista el catalogo completo o el de una categoria. Usar "
                "cuando el cliente pide ver TODO, la lista completa, que "
                "productos hay o que tenes en general. Para busquedas "
                "puntuales por nombre o marca usa search_products. El "
                "parametro categoria es opcional."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "categoria": {
                        "type": "string",
                        "description": (
                            f"Categoria opcional para filtrar. "
                            f"Disponibles: {cats}"
                        ),
                    },
                },
            },
        },
    })

    # Tool determinista de envio por zona (unico camino, sin flag): el costo lo
    # resuelve el codigo desde el CP o la localidad, nunca el modelo. cotizar_envio
    # ya implica cobertura (si puede cotizar, la tienda despacha ahi), por eso no
    # hay una tool aparte de cubre_envio: una herramienta menos que decidir.
    schemas.append({
        "type": "function",
        "function": {
            "name": "cotizar_envio",
            "description": (
                "Cotiza el costo de envio. El CODIGO determina la zona desde "
                "el codigo postal o la localidad del cliente y devuelve la "
                "tarifa real. USALO siempre que el cliente pregunte el costo "
                "de envio, si llegan a su zona, o a donde mandar. NO elijas vos "
                "la zona ni la tarifa. Si devuelve zona null, pedile el codigo "
                "postal o la localidad y provincia, no asumas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "localidad": {
                        "type": "string",
                        "description": (
                            "Lo que el cliente dijo de a donde enviar: codigo "
                            "postal, localidad y/o provincia. Tal cual, sin "
                            "interpretarlo vos."
                        ),
                    },
                    "subtotal": {
                        "type": "integer",
                        "description": (
                            "Subtotal de productos, para envio gratis por "
                            "umbral si corresponde. Opcional."
                        ),
                    },
                },
                "required": ["localidad"],
            },
        },
    })

    # Tool determinista de fecha/plazo de entrega. Siempre en el schema completo
    # (posventa se conserva); el solver vivo no la ve porque MODO_LIBRE_TOOLS la
    # filtra, pero queda disponible para exponerla cuando se decida.
    if True:
        schemas.append({
            "type": "function",
            "function": {
                "name": "calcular_entrega",
                "description": (
                    "Estima el plazo y la ventana de fechas de entrega. El CODIGO "
                    "calcula los dias habiles desde el pago por la zona del codigo "
                    "postal. USALO cuando el cliente pregunta cuando llega o para "
                    "que fecha. NUNCA prometas un dia exacto vos: pasa la ventana "
                    "que devuelve el tool, que es una estimacion no garantizada."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "localidad": {
                            "type": "string",
                            "description": (
                                "Codigo postal, localidad y/o provincia, tal cual "
                                "lo dijo el cliente."
                            ),
                        },
                        "fecha_pago": {
                            "type": "string",
                            "description": (
                                "Opcional. Fecha de pago acreditado en formato "
                                "YYYY-MM-DD. Si no se da, se usa hoy."
                            ),
                        },
                    },
                    "required": ["localidad"],
                },
            },
        })

    # Tools de posventa (devolucion, garantia, CUIT). Siempre en el schema completo
    # (posventa se conserva); el solver vivo no las ve porque MODO_LIBRE_TOOLS las
    # filtra, pero quedan disponibles para exponerlas cuando se decida.
    if True:
        schemas.append({
            "type": "function",
            "function": {
                "name": "plazo_devolucion",
                "description": (
                    "Plazo de devolucion por arrepentimiento. Usalo cuando "
                    "preguntan si pueden devolver o hasta cuando. Si el cliente da "
                    "la fecha de compra, calcula si esta en termino."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_compra": {
                            "type": "string",
                            "description": "Opcional, fecha de compra YYYY-MM-DD.",
                        },
                    },
                },
            },
        })
        schemas.append({
            "type": "function",
            "function": {
                "name": "garantia_vigente",
                "description": (
                    "Calcula hasta cuando cubre la garantia de un producto y si "
                    "esta vigente. Necesita la fecha de compra y los meses de "
                    "garantia del producto (de get_product_details). NO afirmes "
                    "garantia vigente sin calcularla aca."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fecha_compra": {"type": "string",
                                         "description": "Fecha de compra YYYY-MM-DD."},
                        "meses": {"type": "integer",
                                  "description": "Meses de garantia del producto."},
                    },
                    "required": ["fecha_compra", "meses"],
                },
            },
        })
        schemas.append({
            "type": "function",
            "function": {
                "name": "validar_cuit",
                "description": (
                    "Valida un CUIT o CUIL argentino por su digito verificador. "
                    "Usalo cuando el cliente pasa un CUIT, por ejemplo para "
                    "factura A."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cuit": {"type": "string",
                                 "description": "El CUIT/CUIL a validar."},
                    },
                    "required": ["cuit"],
                },
            },
        })

    # El schema completo se devuelve entero. El recorte de tools que ve el solver
    # vivo lo hace MODO_LIBRE_TOOLS en interprete_libre (ex flag TOOLS_MINIMAS).
    return schemas


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


def calcular_entrega(localidad: str | None = None,
                     fecha_pago: str | None = None) -> dict:
    """Estima la VENTANA de entrega de forma determinista: zona por codigo postal
    + plazo de la tienda en dias habiles, salteando fines de semana y feriados.
    Nunca un dia garantizado. fecha_pago opcional en formato ISO YYYY-MM-DD."""
    from app.core.envio import clasificar_zona
    from app.core.entrega import estimar_entrega
    import datetime as _dt

    zona = clasificar_zona(localidad or "")
    desde = None
    if fecha_pago:
        try:
            desde = _dt.date.fromisoformat(fecha_pago.strip()[:10])
        except Exception:
            desde = None
    return estimar_entrega(zona, desde=desde)


def plazo_devolucion(fecha_compra: str | None = None) -> dict:
    """Plazo de devolucion por arrepentimiento. Con fecha de compra (ISO
    YYYY-MM-DD) calcula hasta cuando puede devolver y si esta en termino."""
    from app.core.posventa import plazo_devolucion as _pd
    return _pd(fecha_compra)


def garantia_vigente(fecha_compra: str | None = None,
                     meses: int | None = None) -> dict:
    """Calcula hasta cuando cubre la garantia de un producto. Necesita la fecha de
    compra (ISO) y los meses de garantia del producto (de get_product_details)."""
    from app.core.posventa import garantia_vigente as _gv
    return _gv(fecha_compra, meses)


def validar_cuit(cuit: str | None = None) -> dict:
    """Valida un CUIT/CUIL argentino por su digito verificador."""
    from app.core.posventa import validar_cuit as _vc
    return _vc(cuit)


TOOLS_REGISTRY = {
    "search_products": search_products,
    "cotizar_envio": cotizar_envio,
    "calcular_entrega": calcular_entrega,
    "plazo_devolucion": plazo_devolucion,
    "garantia_vigente": garantia_vigente,
    "validar_cuit": validar_cuit,
    "get_product_details": get_product_details,
    "calculate_total": calculate_total,
    "find_within_budget": find_within_budget,
    "compare_products": compare_products,
    "recommend_product": recommend_product,
    "query_faq": query_faq,
    # Siempre en el registry; el flag controla si aparece en el schema del LLM.
    "list_catalog": list_catalog,
}


def get_tools_schema():
    """Schema fresco en cada llamada (las categorías pueden variar por tienda)."""
    return _build_schema()
