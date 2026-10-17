"""CALCULADORA DEFENSIVA — normaliza y valida los inputs del modelo antes de calcular."""


def normalizar_inputs(items, items_extra):
    """Normaliza y valida los inputs de calculate_total."""
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

        # ── P5: multi-destino. Varios costo_envio con conceptos distintos son

    return items_norm, items_extra_norm, None
