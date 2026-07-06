"""Motor del cliente simulado.

Cada turno el modelo actúa la persona y devuelve, además del mensaje,
su estado interno: interés 0-100, qué le provocó el vendedor y una
decisión. El estado interno no se muestra durante la partida; alimenta
la línea de temperatura y el veredicto del reporte.
"""
from . import llm

_SYSTEM = """Sos un CLIENTE en una simulación de entrenamiento de vendedores.
Actuás a la persona descripta abajo, por chat estilo WhatsApp, en español
rioplatense. Nunca rompés el personaje, nunca mencionás que sos una
simulación, nunca ayudás al vendedor.

PERSONA
Contexto: {contexto}
Personalidad: {personalidad}
Objeción visible: {objecion}
CONDICIÓN OCULTA DE COMPRA (el vendedor no la conoce): {condicion}
GATILLOS DE FUGA (si ocurren, tu interés cae fuerte): {gatillos}

REGLAS DE JUEGO, ESTRICTAS:
1. Tu interés al comenzar este turno es {interes_actual}. Subilo solo cuando el vendedor
   avanza de verdad hacia tu condición oculta; bajalo ante gatillos de fuga,
   respuestas genéricas o presión. Sé exigente: los movimientos son graduales,
   nada de saltar 40 puntos por una frase linda.
2. decision "compra" SOLO si tu condición oculta quedó satisfecha en la
   conversación de forma explícita. Nunca antes del cuarto mensaje del
   vendedor. No regalés la venta.
3. decision "avanza" si aceptás definitivamente un paso siguiente concreto y
   con fecha propuesto por el vendedor: una visita, una seña, una llamada
   agendada. No es compra, pero cierra la partida como avance logrado.
4. decision "se_va" si tu interés queda por debajo de 15, o si un gatillo de
   fuga se repite. Despedite en el personaje, seco o amable según quién sos.
5. El resto del tiempo, decision "sigue".
6. Mensajes con el largo y el tono de la persona. Una persona seca escribe
   corto. Nada de listas ni formato: es un chat.

Respondé SOLO un JSON válido:
{{"mensaje": "lo que le escribís al vendedor",
  "interes": entero 0-100,
  "nota_interna": "una frase: qué te provocó el último mensaje del vendedor",
  "decision": "sigue" | "compra" | "avanza" | "se_va"}}"""

INTERES_INICIAL = 40


def responder(persona: dict, historial: list[dict],
              interes_actual: int = INTERES_INICIAL) -> dict:
    """historial: [{"rol": "vendedor"|"cliente", "texto": str}, ...]

    La conversación va como transcripción en UN mensaje de usuario: si los
    turnos del cliente se mapean como turnos de asistente en texto plano,
    el modelo imita ese formato y deja de emitir el JSON pedido.
    """
    system = _SYSTEM.format(
        contexto=persona["contexto"],
        personalidad=persona["personalidad"],
        objecion=persona["objecion_principal"],
        condicion=persona["condicion_oculta"],
        gatillos=" | ".join(persona["gatillos_de_fuga"]),
        interes_actual=interes_actual,
    )
    transcripcion = "\n".join(
        f"{'VENDEDOR' if m['rol'] == 'vendedor' else 'VOS'}: {m['texto']}"
        for m in historial
    )
    n_vendedor = sum(1 for m in historial if m["rol"] == "vendedor")
    pedido = (
        f"CONVERSACIÓN HASTA AHORA:\n{transcripcion}\n\n"
        f"Mensajes del vendedor hasta ahora: {n_vendedor}. "
        "El último mensaje es del vendedor. Respondé tu próximo turno como "
        "el JSON indicado."
    )
    out = llm.charla_json(system, [{"role": "user", "content": pedido}],
                          temperatura=0.8)
    return {
        "mensaje": str(out.get("mensaje", "...")),
        "interes": max(0, min(100, int(out.get("interes", INTERES_INICIAL)))),
        "nota_interna": str(out.get("nota_interna", "")),
        "decision": out.get("decision", "sigue")
        if out.get("decision") in ("sigue", "compra", "avanza", "se_va")
        else "sigue",
    }
