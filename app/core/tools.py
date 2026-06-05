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
from app.storage.search import hybrid_search
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
    """Busca productos en Firestore con búsqueda híbrida."""
    tid = get_current_tienda()
    resultados = hybrid_search(
        query=query,
        categoria=categoria,
        precio_min=precio_min,
        precio_max=precio_max,
        top_n=settings.SEARCH_TOP_N,
        tienda_id=tid,
    )

    if not resultados:
        return {
            "encontrados": 0,
            "productos": [],
            "mensaje_para_llm": (
                "No hay productos que cumplan los criterios. "
                "Decile al cliente honestamente que no tenemos algo así. "
                "Si querés, ofrecé la categoría más cercana del catálogo."
            ),
        }

    return {
        "encontrados": len(resultados),
        "productos": [_resumir(p) for p in resultados],
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
    if modalidad == "rango":
        return (f"Envio: entre {_money(e.get('monto_min', 0))} y "
                f"{_money(e.get('monto_max', 0))}")
    monto = e.get("monto", 0)
    if "envio" in concepto:
        return "Envio: gratis" if int(monto) == 0 else f"Envio: {_money(monto)}"
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
                    items_extra: list[dict] | None = None) -> dict:
    log.info(f"calculate_total INICIO items={items} items_extra={items_extra}")
    if not items:
        return {
            "ok": False,
            "mensaje_para_llm": (
                "No hay items para sumar. Pedile al cliente que te diga que "
                "productos y cantidades quiere, o sugerile una combinacion vos. "
                "Sumar todo el catalogo no es una cotizacion util."
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
    # Capa defensiva: normaliza y valida los inputs del modelo antes de calcular.
    # Detras del flag CALC_DEFENSIVA. Apagada, comportamiento identico al previo.
    if settings.CALC_DEFENSIVA:
        from app.core.calc_defensiva import normalizar_inputs
        from app.core.tools_context import get_current_destino
        items, items_extra, _err = normalizar_inputs(
            items, items_extra, destino=get_current_destino())
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
        for ex in items_extra:
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
            # Envio gratis automatico por umbral: si el subtotal de PRODUCTOS
            # supera UMBRAL_ENVIO_GRATIS, el envio es gratis sin importar el
            # concepto pedido. Asi el total sale entero y deterministico de la
            # calculadora y el modelo no improvisa (causa de fallback en cierres).
            if tema == "costo_envio" and total > settings.UMBRAL_ENVIO_GRATIS:
                if not envio_gratis_aplicado:
                    extras_detalle.append({
                        "faq_tema": tema, "concepto": concepto,
                        "modalidad": "fijo", "monto": 0,
                        "envio_gratis_auto": True,
                        "condicion": (f"envio gratis por compra mayor a "
                                      f"{settings.UMBRAL_ENVIO_GRATIS}"),
                    })
                    envio_gratis_aplicado = True
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
            return {
                "ok": False,
                "mensaje_para_llm": f"Extras no validos: {extras_no_validos}",
            }

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
                    {"id": d["id"], "monto": d["subtotal"], "fuente": "catalogo"}
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
                {"id": d["id"], "monto": d["subtotal"], "fuente": "catalogo"}
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
    # CAPA DE VENTA de la fuente de verdad. La FAQ trae, en algunos temas, un
    # cierre comercial ya redactado y verificado contra la politica (campo
    # 'venta'). Hasta ahora ese texto era dato muerto: query_faq no lo devolvia,
    # asi que el Solver nunca lo veia. Con PROMPT_VENTA on se lo pasamos como
    # sugerencia_venta para que avance la venta sin inventar (la Regla 9 del
    # prompt le dice como usarlo). Sin el flag, la respuesta es identica a antes.
    if settings.PROMPT_VENTA:
        venta = (data.get("venta", "") or "").strip()
        if venta:
            resp["sugerencia_venta"] = venta
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

    # Keyword-first: si matchea, resolvemos sin llamar al modelo.
    tema_kw = _faq_keyword_match(consulta, faq)
    if tema_kw:
        log.info("query_faq_keyword_hit", tema=tema_kw)
        return _faq_resp(tema_kw, faq[tema_kw])

    temas_texto = ""
    for tema, data in faq.items():
        respuesta = data.get("respuesta", "")
        temas_texto += "\n- tema: " + tema + "\n  respuesta: " + respuesta + "\n"

    system_prompt = (
        "Sos un buscador de FAQ. Recibis una consulta y una lista de temas con respuestas. "
        "Elegi UN tema que responda directamente, o deci que ninguno aplica.\n"
        "REGLAS:\n"
        "1. Solo elegi un tema si la respuesta contiene la informacion exacta que pide el cliente.\n"
        "2. Si la consulta menciona costos, plazos, pagos, envios, garantia, devoluciones, "
        "buscá entre los temas el que tenga esa info concreta.\n"
        "3. Si ningun tema responde, devolve tema vacio.\n"
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
                    "Si el cliente pide total con envio u otro concepto de FAQ, pasalo en items_extra."
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
                            "description": "Extras desde FAQ cuantitativa. faq_tema es el ID de la FAQ (ej costo_envio) y concepto es el id del valor estructurado (ej envio_interior o envio_caba_gba). Solo usar conceptos que existan en la FAQ.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "faq_tema": {"type": "string"},
                                    "concepto": {"type": "string"},
                                },
                                "required": ["faq_tema", "concepto"],
                            },
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

    return schemas


TOOLS_REGISTRY = {
    "search_products": search_products,
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
