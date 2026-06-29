"""
CALCULADORA DEFENSIVA — normaliza y valida los inputs del modelo antes de calcular.

Misma filosofia que el verificador determinista, pero aplicada a la ENTRADA en
vez de a la salida: el codigo no confia en lo que manda el modelo. Antes de que
calculate_total sume nada, esta capa limpia y valida los argumentos y resuelve
dualidades de input. Si algo no se puede normalizar de forma segura, devuelve un
error claro para que calculate_total responda ok False y el bot vuelva a
preguntar, en vez de armar un total sucio.

Esta version cubre:
- P2: cantidad cero o negativa o no numerica -> se rechaza.
- P3: concepto de FAQ con otra capitalizacion -> se normaliza a minuscula (igual
  que ya se hace con faq_tema), asi matchea contra el valor de la FAQ.
- P4: el mismo product_id mandado en dos lineas -> se fusiona en una sola,
  sumando las cantidades.
- P1: el mismo extra (faq_tema + concepto) mandado dos veces -> se deduplica.
- P5: varios extras de costo_envio -> se colapsan en UN disparador. El costo de
  envio NO se decide aca: su unica fuente es cotizar_envio, que deduce la zona de
  la direccion. El concepto de envio que mande el modelo es irrelevante, lo ignora
  la calculadora. Por eso esta capa ya no clasifica zona ni desempata por destino.

Es el unico camino de calculate_total (ex flag CALC_DEFENSIVA, consolidado): la
tool siempre invoca esta capa antes de calcular.
"""


def normalizar_inputs(items, items_extra):
    """
    Normaliza y valida los inputs de calculate_total.

    Devuelve una tupla (items_norm, items_extra_norm, error):
    - Si error no es None, calculate_total debe devolver ok False con ese texto.
    - Si error es None, items_norm e items_extra_norm son los inputs limpios.

    No toca Firestore ni la tienda: es pura normalizacion de los argumentos.
    """
    # items vacio: lo maneja calculate_total con su propio mensaje. No tocar.
    if not items:
        return items, items_extra, None

    # ── Productos: validar cantidad y fusionar duplicados por product_id ──
    acumulado: dict[str, int] = {}
    orden: list[str] = []
    for it in items:
        pid = str(it.get("product_id", "")).strip()
        cant_raw = it.get("cantidad", 1)
        try:
            cant = int(cant_raw)
        except (TypeError, ValueError):
            return None, None, (
                f"Cantidad invalida para {pid or 'un producto'}: "
                f"'{cant_raw}' no es un numero entero. Pedile al cliente que "
                f"aclare cuantas unidades quiere."
            )
        if cant <= 0:
            return None, None, (
                f"Cantidad invalida para {pid or 'un producto'}: debe ser 1 o "
                f"mas. Confirmale al cliente cuantas unidades quiere."
            )
        if pid not in acumulado:
            acumulado[pid] = 0
            orden.append(pid)
        acumulado[pid] += cant
    items_norm = [{"product_id": pid, "cantidad": acumulado[pid]} for pid in orden]

    # ── Extras: normalizar capitalizacion y deduplicar identicos ──
    items_extra_norm = None
    if items_extra:
        items_extra_norm = []
        vistos: set[tuple] = set()
        for ex in items_extra:
            tema = (ex.get("faq_tema") or "").strip().lower()
            concepto = (ex.get("concepto") or "").strip().lower()
            clave = (tema, concepto)
            if clave in vistos:
                continue  # mismo extra mandado dos veces: una sola vez
            vistos.add(clave)
            items_extra_norm.append({"faq_tema": tema, "concepto": concepto})

        # ── P5: un solo disparador de envio. El costo lo resuelve cotizar_envio
        # (unica fuente); el concepto es irrelevante. Si vinieron varios extras de
        # costo_envio, se deja uno y se descartan los demas, sin clasificar zona.
        envios = [e for e in items_extra_norm if e["faq_tema"] == "costo_envio"]
        if len(envios) > 1:
            items_extra_norm = [
                e for e in items_extra_norm if e["faq_tema"] != "costo_envio"
            ] + [envios[0]]

    return items_norm, items_extra_norm, None
