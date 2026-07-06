"""El Juez de Sparring: veredicto con puntaje y evidencia.

La firma del producto: cada dimensión sale con una cita textual de la
conversación como prueba, el puntaje final lo arma EL CÓDIGO con una
fórmula fija, y el reporte señala el turno exacto donde la venta se
enfrió, usando la línea de interés real del cliente simulado.
"""
import re

from . import llm
from .cliente import INTERES_INICIAL

_SYSTEM_JUEZ = """Sos un entrenador de ventas exigente y justo. Evaluás la
actuación del VENDEDOR en la conversación adjunta contra un cliente
simulado. Conocés la condición oculta de compra del cliente, el vendedor no
la conocía: evaluás si su técnica lo acercó o lo alejó de descubrirla.

Persona del cliente: {titulo} — {objecion}
Condición oculta de compra: {condicion}
Gatillos de fuga: {gatillos}

Calificá de 0 a 100 estas cuatro dimensiones. Para CADA una: puntaje,
veredicto de UNA oración en voseo dirigida al vendedor, y "evidencia" con la
cita TEXTUAL de un mensaje del vendedor que justifique el puntaje. La cita
debe ser copia exacta de un mensaje o fragmento; si la dimensión estuvo
ausente, citá el mensaje donde más se nota la ausencia y aclaralo en el
veredicto. Sé exigente: 80 o más es solo para ejecución realmente buena.

1. descubrimiento: ¿preguntó por la necesidad, el uso, el contexto, antes de
   vender? ¿O tiró producto y precio de entrada?
2. manejo_objecion: ¿trabajó la objeción con valor y argumentos, o la
   esquivó, la discutió o la tapó con descuento?
3. avance: ¿propuso pasos siguientes concretos y con fecha, intentó cerrar?
   ¿O dejó la charla morir en "cualquier cosa avisame"?
4. tono: ¿mantuvo control y calidez, mensajes del largo justo, sin ponerse
   defensivo ni ansioso?

Además: "consejo_principal", el ÚNICO cambio de conducta que más puntaje le
daría a este vendedor la próxima vez, en dos oraciones máximo, voseo.

Respondé SOLO JSON:
{{"descubrimiento": {{"puntaje": n, "veredicto": "...", "evidencia": "..."}},
  "manejo_objecion": {{"puntaje": n, "veredicto": "...", "evidencia": "..."}},
  "avance": {{"puntaje": n, "veredicto": "...", "evidencia": "..."}},
  "tono": {{"puntaje": n, "veredicto": "...", "evidencia": "..."}},
  "consejo_principal": "..."}}"""

_PESOS = {
    "manejo_objecion": 0.30,
    "descubrimiento": 0.25,
    "avance": 0.25,
    "tono": 0.20,
}

_RE_DESCUENTO = re.compile(
    r"descuento|te lo dejo|te hago precio|\d+\s*%\s*(off|menos)|rebaja",
    re.IGNORECASE,
)


def _senales_duras(historial: list[dict]) -> dict:
    """Señales que computa el código, sin LLM. Deterministas y explicables."""
    vendedor = [m["texto"] for m in historial if m["rol"] == "vendedor"]
    primeros = vendedor[:3]
    preguntas_tempranas = sum(1 for t in primeros if "?" in t)
    descuento_idx = next(
        (i for i, t in enumerate(vendedor) if _RE_DESCUENTO.search(t)), None
    )
    descuento_gratuito = descuento_idx is not None and descuento_idx < 2
    muros = [t for t in vendedor if len(t) > 420]
    return {
        "preguntas_en_primeros_3": preguntas_tempranas,
        "descuento_gratuito": descuento_gratuito,
        "muros_de_texto": len(muros),
    }


def _momento_clave(historial: list[dict], estados: list[dict]) -> dict | None:
    """El turno con la mayor caída de interés y el mensaje del vendedor que la causó."""
    if not estados:
        return None
    interes_previo = INTERES_INICIAL
    peor = None
    for e in estados:
        caida = interes_previo - e["interes"]
        if peor is None or caida > peor["caida"]:
            peor = {
                "turno": e["turno"],
                "caida": caida,
                "interes": e["interes"],
                "nota_cliente": e["nota_interna"],
            }
        interes_previo = e["interes"]
    if peor is None or peor["caida"] <= 0:
        return None
    vendedor_previos = [
        m["texto"]
        for m in historial[: peor["turno"] * 2]
        if m["rol"] == "vendedor"
    ]
    peor["mensaje_vendedor"] = vendedor_previos[-1] if vendedor_previos else ""
    return peor


def evaluar(persona: dict, historial: list[dict], estados: list[dict],
            resultado: str) -> dict:
    """Devuelve el reporte completo. `estados`: [{turno, interes, nota_interna}]."""
    transcripcion = "\n".join(
        f"{'VENDEDOR' if m['rol'] == 'vendedor' else 'CLIENTE'}: {m['texto']}"
        for m in historial
    )
    system = _SYSTEM_JUEZ.format(
        titulo=persona["titulo"],
        objecion=persona["objecion_principal"],
        condicion=persona["condicion_oculta"],
        gatillos=" | ".join(persona["gatillos_de_fuga"]),
    )
    dims = llm.charla_json(
        system,
        [{"role": "user", "content": f"CONVERSACIÓN:\n{transcripcion}"}],
        temperatura=0.1,
    )

    senales = _senales_duras(historial)
    base = 0.0
    for dim, peso in _PESOS.items():
        puntaje = max(0, min(100, int(dims.get(dim, {}).get("puntaje", 0))))
        dims.setdefault(dim, {})["puntaje"] = puntaje
        base += puntaje * peso

    ajustes = []
    if senales["descuento_gratuito"]:
        base -= 10
        ajustes.append("Regalaste descuento antes de defender el valor: -10.")
    if senales["preguntas_en_primeros_3"] == 0:
        base -= 5
        ajustes.append("Ni una pregunta en tus primeros tres mensajes: -5.")
    if senales["muros_de_texto"]:
        base -= 3 * senales["muros_de_texto"]
        ajustes.append(
            f"{senales['muros_de_texto']} muro(s) de texto de folleto: "
            f"-{3 * senales['muros_de_texto']}."
        )
    if resultado == "compra":
        base += 10
        ajustes.append("Cerraste la venta: +10.")
    elif resultado == "avanza":
        base += 8
        ajustes.append("Conseguiste un paso siguiente concreto y con fecha: +8.")
    elif resultado == "se_va":
        base -= 10
        ajustes.append("El cliente se fue: -10.")

    return {
        "puntaje_final": int(max(0, min(100, round(base)))),
        "resultado": resultado,
        "dimensiones": {d: dims[d] for d in _PESOS},
        "consejo_principal": dims.get("consejo_principal", ""),
        "ajustes_del_codigo": ajustes,
        "senales": senales,
        "momento_clave": _momento_clave(historial, estados),
        "condicion_oculta_revelada": persona["condicion_oculta"],
        "linea_interes": [
            {"turno": e["turno"], "interes": e["interes"]} for e in estados
        ],
    }
