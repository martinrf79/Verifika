"""
REDACTOR — "el LLM elige, el codigo redacta" (sesion 5-jul-2026).

El giro de arquitectura que cierra el pozo de meses: cual meter el dato duro
del codigo DENTRO de la prosa del LLM. La respuesta es no tejer. El solver deja
de redactar el mensaje y pasa a ELEGIR: devuelve un PLAN en JSON con las piezas
que van, sus ids certificados, y solo huecos chicos de texto libre SIN datos
(saludo, transicion, proxima pregunta). El codigo RENDERIZA el mensaje final
desde ese plan, estampando cada dato duro de la fuente.

Por que asi y no pidiendole al solver que integre prosa:
- DeepSeek cumple JSON estructurado de forma confiable; la inclusion verbatim de
  un texto en su prosa NO se puede forzar por prompt (no hay decodificacion
  restringida por API). Elegir piezas es salida estructurada, no obediencia.
- El tono libre queda confinado a huecos que no llevan numeros ni ids, asi no
  pueden mentir sobre un dato. El verificador final igual audita el mensaje.
- La coherencia multi-area sale sola: cada area es UNA pieza del plan, nunca se
  cae una pregunta (era el bug del 5-jul: dos preguntas, una respuesta).
- Es reutilizable en cualquier rubro: el patron no sabe de gaming ni de precios.

Este modulo es SOLO el render determinista + el contrato del plan. Es la base;
el cableado del plan al solver y la corrida en el banco vienen despues. No toca
el camino vivo todavia. Conservador: una pieza sin su dato (id inexistente,
tema sin curada, presupuesto que no se calculo) se DESCARTA, no se inventa.
"""
from app.logger import get_logger

log = get_logger(__name__)

# Tipos de pieza que el codigo sabe renderizar. El solver solo puede elegir de
# esta lista cerrada; una pieza de tipo desconocido se ignora. Cada tipo tiene
# UNA fuente de verdad y la respeta:
#   - producto:     ficha (nombre+precio+stock) leida del catalogo por id.
#   - presupuesto:  la presentacion YA verificada de calculate_total del turno.
#   - envio:        el bloque de cotizar_envio del turno.
#   - politica:     la respuesta curada verbatim del tema, con sus valores.
PIEZAS_VALIDAS = {"producto", "presupuesto", "envio", "politica"}

# Huecos de texto libre del plan: los UNICOS lugares donde el solver pone prosa
# suya. No llevan datos duros; su lugar es la voz de venta (saludo, puente,
# proxima pregunta). Se renderizan en este orden alrededor de las piezas.
_HUECO_SALUDO = "saludo"
_HUECO_TRANSICION = "transicion"
_HUECO_PREGUNTA = "pregunta"


def _money(n) -> str | None:
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return None


def _linea_producto(pid: str, tienda_id: str) -> str:
    """Ficha de una pieza producto: nombre + precio + stock REALES del catalogo.
    Mismo formato que el estampado de [[PROD:id]] del camino actual. Id que no
    existe -> "" (se descarta), el solver no puede inventar un producto."""
    from app.storage.firestore_client import get_product_by_id
    try:
        p = get_product_by_id((pid or "").strip().upper(), tienda_id=tienda_id)
    except Exception:
        p = None
    if not p:
        return ""
    nombre = str(p.get("nombre", "")).strip()
    precio = _money(p.get("precio_ars"))
    stock = p.get("stock", 0)
    partes = [nombre]
    if precio:
        partes.append(f"- ${precio}")
    if isinstance(stock, int) and stock > 0:
        partes.append(f"({stock} en stock)")
    return " ".join(partes).strip()


def _bloque_politica(tema: str, tienda_id: str) -> str:
    """La respuesta curada VERBATIM del tema, con sus huecos {{concepto}}
    estampados desde los valores de la MISMA FAQ. "" si el tema no existe, no
    esta curado o algun valor no resuelve: una politica a medias no se muestra."""
    from app.storage.firestore_client import get_all_faq
    from app.core.curadas import estampar_valores
    data = (get_all_faq(tienda_id=tienda_id) or {}).get((tema or "").strip()) or {}
    texto = str(data.get("respuesta_curada") or "").strip()
    if not texto:
        return ""
    estampada = estampar_valores(texto, data)
    return estampada or ""


def _texto_libre(s) -> str:
    """Un hueco de texto libre, saneado. Es prosa del solver: se limpia el
    espacio, nada mas. El dato duro NO viaja por aca (las piezas lo traen); el
    verificador final igual audita todo numero del mensaje entero."""
    return str(s or "").strip()


def _render_pieza(pieza: dict, tienda_id: str, contexto: dict) -> str:
    """Renderiza UNA pieza del plan desde su fuente de verdad. "" si la pieza no
    tiene dato para mostrar (se descarta silenciosa)."""
    if not isinstance(pieza, dict):
        return ""
    tipo = str(pieza.get("tipo") or "").strip().lower()
    if tipo == "producto":
        return _linea_producto(str(pieza.get("id") or ""), tienda_id)
    if tipo == "politica":
        return _bloque_politica(str(pieza.get("tema") or ""), tienda_id)
    if tipo == "presupuesto":
        return _texto_libre(contexto.get("presupuesto"))
    if tipo == "envio":
        return _texto_libre(contexto.get("envio"))
    return ""


def validar_plan(obj) -> dict | None:
    """Normaliza el JSON que devolvio el solver a un plan seguro, o None si no
    es un plan usable (ahi el llamador cae al camino actual). No confia en la
    forma: filtra piezas invalidas, ids/temas vacios y tipos desconocidos.
    Un plan sin NINGUNA pieza ni hueco util es None (no hay nada que renderizar)."""
    if not isinstance(obj, dict):
        return None
    piezas_in = obj.get("piezas")
    piezas: list[dict] = []
    if isinstance(piezas_in, list):
        for p in piezas_in:
            if not isinstance(p, dict):
                continue
            tipo = str(p.get("tipo") or "").strip().lower()
            if tipo not in PIEZAS_VALIDAS:
                continue
            if tipo == "producto" and not str(p.get("id") or "").strip():
                continue
            if tipo == "politica" and not str(p.get("tema") or "").strip():
                continue
            piezas.append({**p, "tipo": tipo})
    plan = {
        _HUECO_SALUDO: _texto_libre(obj.get(_HUECO_SALUDO)),
        "piezas": piezas,
        _HUECO_TRANSICION: _texto_libre(obj.get(_HUECO_TRANSICION)),
        _HUECO_PREGUNTA: _texto_libre(obj.get(_HUECO_PREGUNTA)),
    }
    tiene_algo = bool(piezas) or any(
        plan[h] for h in (_HUECO_SALUDO, _HUECO_TRANSICION, _HUECO_PREGUNTA))
    return plan if tiene_algo else None


def renderizar(plan: dict, tienda_id: str, contexto: dict | None = None) -> str:
    """Arma el mensaje final desde el plan: saludo, las piezas en orden, la
    transicion y la proxima pregunta. Composicion VERTICAL por segmentos, la
    costura es un salto de linea (nunca una conjuncion, asi la gramatica no
    puede quedar mal). Cada pieza trae su dato de la fuente; los huecos traen
    solo la voz del solver. Una pieza vacia se descarta, no deja un renglon
    fantasma. "" si no quedo nada renderizable (el llamador cae a fallback).

    `contexto` trae los datos del turno que no salen del catalogo/FAQ por id:
      - presupuesto: la presentacion de calculate_total (ya verificada);
      - envio: el bloque de cotizar_envio.
    """
    if not isinstance(plan, dict):
        return ""
    contexto = contexto or {}
    partes: list[str] = []

    saludo = _texto_libre(plan.get(_HUECO_SALUDO))
    if saludo:
        partes.append(saludo)

    for pieza in plan.get("piezas") or []:
        bloque = _render_pieza(pieza, tienda_id, contexto)
        if bloque:
            partes.append(bloque)

    transicion = _texto_libre(plan.get(_HUECO_TRANSICION))
    if transicion:
        partes.append(transicion)

    pregunta = _texto_libre(plan.get(_HUECO_PREGUNTA))
    if pregunta:
        partes.append(pregunta)

    # Dedup defensivo: si el saludo o la transicion repiten textual una pieza
    # (el solver a veces copia), no se duplica el segmento.
    vistos: list[str] = []
    for seg in partes:
        s = seg.strip()
        if s and s not in vistos:
            vistos.append(s)
    return "\n\n".join(vistos).strip()
