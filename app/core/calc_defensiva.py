"""
CALCULADORA DEFENSIVA — normaliza y valida los inputs del modelo antes de calcular.

Misma filosofia que el verificador determinista, pero aplicada a la ENTRADA en
vez de a la salida: el codigo no confia en lo que manda el modelo. Antes de que
calculate_total sume nada, esta capa limpia y valida los argumentos y resuelve
dualidades de input. Si algo no se puede normalizar de forma segura, devuelve un
error claro para que calculate_total responda ok False y el bot vuelva a
preguntar, en vez de armar un total sucio.

Esta primera version cubre:
- P2: cantidad cero o negativa o no numerica -> se rechaza.
- P3: concepto de FAQ con otra capitalizacion -> se normaliza a minuscula (igual
  que ya se hace con faq_tema), asi matchea contra el valor de la FAQ.
- P4: el mismo product_id mandado en dos lineas -> se fusiona en una sola,
  sumando las cantidades.
- P1: el mismo extra (faq_tema + concepto) mandado dos veces -> se deduplica.

- P5: dos conceptos de envio DISTINTOS -> se elige uno filtrando por el destino
  del cliente (caba_gba o interior), igual que filtra la busqueda de productos.
  El destino lo inyecta el backend por contextvar, el LLM no lo elige. Si no hay
  destino claro, se rechaza para que el bot pregunte, sin adivinar el envio.

Es el unico camino de calculate_total (ex flag CALC_DEFENSIVA, consolidado): la
tool siempre invoca esta capa antes de calcular.
"""

# Palabras que delatan el destino del envio en el texto del cliente. Se buscan
# como subcadena sobre el mensaje normalizado a minuscula sin acentos.
_KW_CABA_GBA = (
    "caba", "capital", "ciudad autonoma", "ciudad de buenos aires", "microcentro",
    "gba", "gran buenos aires", "conurbano", "zona norte", "zona sur", "zona oeste",
    "provincia de buenos aires", "buenos aires",
)
_KW_INTERIOR = (
    "interior", "provincia", "cordoba", "rosario", "santa fe", "mendoza", "tucuman",
    "salta", "neuquen", "bariloche", "mar del plata", "la plata", "jujuy", "chaco",
    "misiones", "corrientes", "entre rios", "san juan", "san luis", "catamarca",
    "formosa", "chubut", "rio negro", "santa cruz", "tierra del fuego", "la rioja",
    "santiago del estero", "la pampa",
)


def _norm(texto: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(texto or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def destino_a_categoria(texto: str):
    """Detecta el destino del envio en el texto del cliente y lo categoriza en
    'caba_gba', 'interior' o None si no es claro. Determinista, sin modelo.
    'la plata' (interior) gana a 'buenos aires' (caba_gba) por especificidad: se
    revisa interior primero solo cuando el match es mas largo y especifico."""
    c = _norm(texto)
    # 'buenos aires' es ambiguo: aparece tanto en CABA como en 'provincia de
    # buenos aires'. Por eso interior pesa cuando hay una localidad puntual.
    hit_interior = next((k for k in _KW_INTERIOR if k in c), None)
    hit_caba = next((k for k in _KW_CABA_GBA if k in c), None)
    if hit_interior and hit_caba:
        # Si el match de interior es mas especifico (mas largo), gana interior.
        return "interior" if len(hit_interior) >= len(hit_caba) else "caba_gba"
    if hit_interior:
        return "interior"
    if hit_caba:
        return "caba_gba"
    return None


def _concepto_a_categoria(concepto: str):
    """Categoriza un concepto de envio de la FAQ por su nombre."""
    c = concepto.lower()
    if "caba" in c or "gba" in c:
        return "caba_gba"
    if "interior" in c:
        return "interior"
    return None


def normalizar_inputs(items, items_extra, destino=None):
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

        # ── P5: dos conceptos de envio DISTINTOS -> uno solo por destino ──
        envios = [e for e in items_extra_norm if e["faq_tema"] == "costo_envio"]
        distintos = {e["concepto"] for e in envios}
        if len(distintos) > 1:
            if not destino:
                return None, None, (
                    "Hay mas de un costo de envio posible y no me queda claro el "
                    "destino. Preguntale al cliente si el envio es a CABA o GBA o "
                    "al interior, y volve a cotizar con esa respuesta. NO elijas "
                    "un envio al azar."
                )
            elegidos = {
                e["concepto"] for e in envios
                if _concepto_a_categoria(e["concepto"]) == destino
            }
            if len(elegidos) != 1:
                return None, None, (
                    f"No puedo resolver el envio para el destino '{destino}' entre "
                    f"los conceptos {sorted(distintos)}. Confirmale el destino al "
                    f"cliente antes de cotizar."
                )
            keep = elegidos.pop()
            # Conservar todo lo que no sea envio, mas el unico envio elegido.
            items_extra_norm = [
                e for e in items_extra_norm
                if e["faq_tema"] != "costo_envio" or e["concepto"] == keep
            ]

    return items_norm, items_extra_norm, None
