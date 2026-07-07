"""
RUTEO DE VENTA — la columna vertebral que elige la MOVIDA para una pregunta
compleja, o manda PREGUNTAR cuando no está claro.

Es logica pura, sin LLM ni Firestore: recibe la lectura del interprete (interp)
y el estado de la venta (estado) y devuelve una DECISION determinista. Mismo
patron conservador que `curadas.servir_curada` y las guias `guia_mas_barato` /
`guia_memoria`: ante cualquier duda NO fuerza nada, devuelve accion 'normal' y el
turno sigue por el camino de siempre (solver + verificadores).

Contrato con el resto del sistema, decidido asi para que el cableado calce con
el flujo real de `interprete_libre`:

  - ENTRADA: mensaje del cliente, interp (dict del interpretador con intencion,
    confianza, producto_resuelto, candidatos, ofrecer_opciones, estado) y estado
    de la venta (dict con productos_vistos, carrito, criterio).
  - SALIDA: dict {categoria, accion, movida, motivo}.
      accion 'movida'    -> corresponde la curada de venta `movida` (B1..B12);
                            el cableado inyecta su brief como guia previa al solver.
      accion 'preguntar' -> hay que pedir UNA aclaracion (escape); el solver
                            pregunta, no afirma.
      accion 'normal'    -> ninguna movida aplica con seguridad; camino de siempre.

Este modulo NO redacta la curada ni estampa huecos: solo DECIDE. La redaccion de
los nexos la hace el LLM sobre el brief aprobado; los huecos los sella el codigo.
Los borradores de las movidas viven en BORRADORES_CURADAS_VENTA.md y la taxonomia
en CATEGORIAS_PREGUNTAS_VENTA.md. Es la unica fuente de verdad del espacio de
etiquetas: el interprete y el router leen de aca.
"""
import re
import unicodedata

# Umbral de confianza del interprete para animarse a una movida sin preguntar.
# Debajo de esto, aunque se detecte la categoria, se prefiere el escape.
_UMBRAL_CONF = 0.6


# ── Registro de categorias (fuente de verdad del espacio de etiquetas) ──────
# familia: 'comun' | 'compleja' | 'memoria'. escape_default: la accion cuando la
# categoria se detecta pero falta certeza o dato. Las de memoria quedan LISTADAS
# pero el router no las rutea todavia (se abordan con la capa de memoria).
CATEGORIAS: dict[str, dict] = {
    "B1": {"nombre": "indecision", "familia": "compleja", "escape_default": "preguntar"},
    "B2": {"nombre": "cambio_producto", "familia": "compleja", "escape_default": "preguntar"},
    "B3": {"nombre": "negacion_intraturno", "familia": "compleja", "escape_default": "normal"},
    "B4": {"nombre": "presion_descuento", "familia": "compleja", "escape_default": "movida"},
    "B5": {"nombre": "objecion_precio", "familia": "compleja", "escape_default": "movida"},
    "B6": {"nombre": "desconfianza", "familia": "compleja", "escape_default": "movida"},
    "B7": {"nombre": "ambiguedad_variante", "familia": "compleja", "escape_default": "preguntar"},
    "B8": {"nombre": "producto_inexistente", "familia": "compleja", "escape_default": "preguntar"},
    "B9": {"nombre": "precio_falso", "familia": "compleja", "escape_default": "movida"},
    "B10": {"nombre": "multidestino", "familia": "compleja", "escape_default": "normal"},
    "B11": {"nombre": "postergacion", "familia": "compleja", "escape_default": "movida"},
    "B12": {"nombre": "fuera_de_tema", "familia": "compleja", "escape_default": "normal"},
    # Memoria: listadas, NO ruteadas por ahora (ver memoria_ref.py y taxonomia C).
    "C1": {"nombre": "referencia_borrosa", "familia": "memoria", "escape_default": "normal"},
    "C2": {"nombre": "retomar_charla_vieja", "familia": "memoria", "escape_default": "normal"},
    "C3": {"nombre": "contradiccion_lejana", "familia": "memoria", "escape_default": "normal"},
    "C4": {"nombre": "dato_viejo", "familia": "memoria", "escape_default": "normal"},
}


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


# ── Detectores deterministas por categoria ─────────────────────────────────
# Conservadores: frases inequivocas de cada situacion, no cualquier palabra que
# daria falsos positivos. Se leen sobre el mensaje normalizado sin acentos.

_RE_DESCUENTO = re.compile(
    r"\bme haces (un )?(precio|descuento)\b|\bhaceme (un )?(precio|descuento)\b|"
    r"\bun descuentito\b|\bmejor precio\b|\brebaja\b|"
    r"\bsi llevo (dos|tres|varios|mas)\b|\bpor cantidad\b|\bhay descuento\b")

_RE_OBJ_PRECIO = re.compile(
    r"\bcaro\b|\bcarisimo\b|\bes mucho\b|\bmuy caro\b|\bse me va de precio\b|"
    r"\ben otro lado (sale|esta|lo consigo)\b|\bmas barato en\b|\bno me da el presupuesto\b")

_RE_DESCONFIANZA = re.compile(
    r"\bes seguro\b|\bes confiable\b|\bson (originales|truchos|replica)\b|"
    r"\bno sera (trucho|falso|estafa)\b|\bpuedo confiar\b|\bes una estafa\b|"
    r"\bde verdad (llega|existe)\b")

_RE_POSTERGACION = re.compile(
    r"\blo pienso\b|\bme lo pienso\b|\bdespues (vuelvo|veo|te digo)\b|"
    r"\bmas tarde\b|\blo consulto\b|\btengo que (pensarlo|verlo|consultar\w*)\b|"
    r"\bpor ahora no\b|\bcualquier cosa (vuelvo|te aviso)\b")

_RE_INDECISION = re.compile(
    r"\bno se cual\b|\bcual me (recomendas|conviene|llevo)\b|\bque me recomendas\b|"
    r"\bvos que (decis|elegis|me recomendas)\b|\bel que vos (digas|elijas)\b|"
    r"\bconfio en (vos|tu eleccion|tu criterio)\b|\bestoy indeciso\b|\bno me decido\b")

_RE_CAMBIO_PROD = re.compile(
    r"\bese no\b|\bno ese\b|\bmejor (el|la) otro\b|\bmejor otro\b|"
    r"\ben (vez|lugar) del?\b|\bcambia(me|lo)?\b|\bprefiero (el|la) otro\b|"
    r"\bno,? mejor\b")

# Off-topic es dificil de acusar por regex sin falsos positivos; el router no lo
# rutea por ahora (queda 'normal'). Precio_falso (B9), inexistente (B8) y
# multidestino (B10) necesitan el catalogo / tools y se resuelven en el cableado,
# no en esta logica pura.


def _decidir(categoria: str, mensaje: str, interp: dict, estado: dict) -> dict:
    """Aplica el escape por confianza sobre la categoria detectada."""
    meta = CATEGORIAS.get(categoria, {})
    accion = meta.get("escape_default", "normal")
    conf = 0.0
    try:
        conf = float(interp.get("confianza") or 0.0)
    except (TypeError, ValueError):
        conf = 0.0
    # Si la movida deberia afirmar algo (accion 'movida') pero la confianza del
    # interprete es baja, se degrada a preguntar: mejor una aclaracion que una
    # afirmacion floja. Las que YA son 'preguntar' o 'normal' no cambian.
    if accion == "movida" and conf < _UMBRAL_CONF:
        accion = "preguntar"
    return {
        "categoria": categoria,
        "accion": accion,
        "movida": categoria if accion == "movida" else None,
        "motivo": meta.get("nombre", ""),
    }


def rutear_venta(mensaje: str, interp: dict | None, estado: dict | None) -> dict:
    """Decide la movida de venta o el escape. Determinista y conservador: ante
    cualquier duda devuelve accion 'normal' (camino de siempre)."""
    normal = {"categoria": None, "accion": "normal", "movida": None, "motivo": ""}
    if not isinstance(interp, dict) or not interp:
        return normal
    estado = estado if isinstance(estado, dict) else {}
    m = _norm(mensaje)

    # B7 AMBIGUEDAD: el interprete resolvio mas de un candidato o pidio A/B.
    # Es una senal estructurada del propio interprete, la mas fuerte: preguntar.
    cands = interp.get("candidatos") or []
    opciones = interp.get("ofrecer_opciones") or []
    if (isinstance(cands, list) and len(cands) >= 2) or \
       (isinstance(opciones, list) and len(opciones) >= 2):
        return {"categoria": "B7", "accion": "preguntar", "movida": None,
                "motivo": "ambiguedad_variante"}

    # Deteccion por frase, orden de mas especifico a mas general. La primera que
    # matchea gana; son mutuamente excluyentes en la practica.
    if _RE_DESCUENTO.search(m):
        return _decidir("B4", mensaje, interp, estado)
    if _RE_OBJ_PRECIO.search(m):
        return _decidir("B5", mensaje, interp, estado)
    if _RE_DESCONFIANZA.search(m):
        return _decidir("B6", mensaje, interp, estado)
    if _RE_POSTERGACION.search(m):
        return _decidir("B11", mensaje, interp, estado)
    if _RE_CAMBIO_PROD.search(m):
        return _decidir("B2", mensaje, interp, estado)
    if _RE_INDECISION.search(m):
        return _decidir("B1", mensaje, interp, estado)

    return normal
