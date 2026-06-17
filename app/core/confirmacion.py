"""
CONFIRMACION_PROVIDER — la pregunta de confirmacion la arma el CODIGO, con datos.

Cuando el cliente es ambiguo ("3 teclados, creo que inalambricos naranja, o
capaz otro color"), hoy el Provider marca los candidatos y el SOLVER compone el
A/B, decide el armado y difiere el total. Eso es lo fragil: la pregunta y su
ruteo quedan en manos del modelo.

Esta pieza arma la frase de confirmacion por codigo, desde los candidatos REALES
que el Provider ya tiene en mano: el A/B de foco (dos productos del registro) o
los ambiguos de multi (un termino con varios modelos). Ninguna frase con datos
nace del LLM.

Reparto acordado: el Interprete solo CLASIFICA el tipo de ambiguedad (campo
tipo_confirmacion: "a_o_b" | "te_referis_a" | "confirmar_compra"), una señal sin
datos. Esa señal entra aca como PISTA, no como veredicto: el CODIGO decide si
finalmente se pregunta segun lo que el catalogo realmente dio. Si el interprete
marco ambiguo pero el Provider resolvio a un solo producto, NO se pregunta
(evita la friccion de preguntar de mas). Si el Provider tiene ambiguedad real,
se pregunta aunque el interprete no la haya marcado.

La confirmacion es un campo SIEMPRE-PRESENTE: necesita=False y vacio cuando no
hace falta, nunca null. Misma disciplina que estado_pedido. Asi la maquina
determinista nunca queda sin material y el Solver solo vende.

Funcion PURA: lee el dict de proveer() y la interpretacion. Detras del flag
CONFIRMACION_PROVIDER (default off). Nadie la consume todavia.
"""
from typing import Optional

from app.logger import get_logger

log = get_logger(__name__)


def _money(v) -> str:
    if not isinstance(v, (int, float)):
        return ""
    return f"${v:,.0f}".replace(",", ".")


def _con_precio(v) -> str:
    m = _money(v)
    return f" a {m}" if m else ""


def _precio_cot(cot: dict) -> Optional[float]:
    """Precio unitario de una opcion del A/B: sale del detalle de la calculadora
    (precio_unitario), con el total como respaldo."""
    calc = cot.get("calc") or {}
    detalle = calc.get("detalle") or []
    if detalle and isinstance(detalle[0], dict):
        pu = detalle[0].get("precio_unitario")
        if isinstance(pu, (int, float)):
            return pu
    for k in ("total_ars", "total_min_ars", "subtotal_productos_ars"):
        if isinstance(calc.get(k), (int, float)):
            return calc[k]
    return None


def _vacio(hint: str) -> dict:
    """El campo siempre presente: no hace falta confirmar. Nunca null."""
    return {"necesita": False, "tipo": "", "texto": "", "opciones": [],
            "hint": hint}


def construir_confirmacion(prov: dict, *,
                           interpretacion: Optional[dict] = None,
                           estado_conv: Optional[str] = None,
                           trace_id: Optional[str] = None) -> dict:
    """Arma la confirmacion del turno por codigo, o el campo vacio si no hace
    falta. SIEMPRE devuelve el mismo objeto con todas las claves.

    Returns:
        {"necesita", "tipo", "texto", "opciones", "hint"}. opciones: los
        candidatos reales {id, nombre, precio_ars}. hint: la señal del
        interprete (solo informativa; el codigo ya decidio con el catalogo).
    """
    prov = prov or {}
    hint = str((interpretacion or {}).get("tipo_confirmacion") or "").strip().lower()

    # ── A/B: el foco matcheo DOS productos del registro ──
    ab = prov.get("ab")
    if ab and len(ab.get("opciones") or []) >= 2:
        opciones, partes = [], []
        for letra, cot in zip(("A", "B"), ab["opciones"][:2]):
            precio = _precio_cot(cot)
            opciones.append({"id": cot.get("producto_id"),
                             "nombre": cot.get("nombre"),
                             "precio_ars": precio})
            partes.append(f"{letra}) {cot.get('nombre')}{_con_precio(precio)}")
        texto = ("Tengo dos opciones segun a cual te refieras: "
                 + ", o ".join(partes) + ". Cual preferis?")
        log.info("confirmacion_armada", trace_id=trace_id, tipo="a_o_b",
                 opciones=len(opciones), hint=hint)
        return {"necesita": True, "tipo": "a_o_b", "texto": texto,
                "opciones": opciones, "hint": hint}

    # ── MULTI ambiguos: un termino con varios modelos reales ──
    multi = prov.get("multi")
    if multi and multi.get("ambiguos"):
        frases, opciones = [], []
        for amb in multi["ambiguos"]:
            cands = amb.get("candidatos") or []
            if not cands:
                continue
            lista = " o ".join(
                f"{c.get('nombre')}{_con_precio(c.get('precio_ars'))}"
                for c in cands)
            cant = amb.get("cantidad")
            term = amb.get("termino")
            prefijo = f"Para {f'{cant} ' if cant else ''}{term}".rstrip()
            frases.append(f"{prefijo} tengo estas opciones: {lista}")
            for c in cands:
                opciones.append({"id": c.get("id"), "nombre": c.get("nombre"),
                                 "precio_ars": c.get("precio_ars"),
                                 "termino": term})
        if frases:
            cierre = ("Cual preferis de cada uno?" if len(frases) > 1
                      else "Cual preferis?")
            texto = ". ".join(frases) + ". " + cierre
            log.info("confirmacion_armada", trace_id=trace_id,
                     tipo="te_referis_a", terminos=len(frases), hint=hint)
            return {"necesita": True, "tipo": "te_referis_a", "texto": texto,
                    "opciones": opciones, "hint": hint}

    # El catalogo resolvio (o no hay ambiguedad): NO se pregunta, aunque el
    # interprete haya marcado una pista. El codigo manda.
    if hint:
        log.info("confirmacion_no_necesaria", trace_id=trace_id, hint=hint)
    return _vacio(hint)
