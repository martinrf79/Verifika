"""
REDACTOR — capa 2 del nucleo. Viste de VENTA los hechos ya resueltos.

Regla madre: el modelo es libre en la FORMA, nunca en el HECHO. Por eso el
redactor recibe SOLO los hechos que el codigo ya verifico y resolvio de la fuente
de verdad, mas la etapa de venta y, si existe, el angulo de conversion curado. NO
recibe el mensaje crudo como fuente de hechos. Su unico trabajo es ponerle
lenguaje de vendedor a lo que ya es verdad.

Salida ESTRUCTURADA: {analisis_interno, respuesta_final}. El codigo se queda solo
con respuesta_final; el cliente nunca ve el analisis. Obligar al modelo a
escribir primero que hechos usa (cadena de pensamiento oculta) baja la
alucinacion y, de paso, le da material al gate para chequear fidelidad.

Este modulo arma el prompt y parsea la salida. La llamada al modelo y el gate
viven afuera. Las funciones de armado y parseo son puras y testeables sin LLM.
"""
import json
import re
from typing import Optional

from app.core.constitucion import constitucion_como_prompt

# Guia por etapa de venta. Pocas y claras, no un micro-Solver por cada cosa.
# Cada una solo cambia el ENFOQUE, nunca habilita inventar un hecho.
ETAPA_GUIA = {
    "saludo": "Saluda corto y ofrece ayuda concreta.",
    "exploracion": "Mostra el dato con entusiasmo medido y abri la puerta al "
                   "siguiente paso de compra.",
    "objecion": "Tranquiliza la duda con el hecho, sin exagerar, y reencauza "
                "hacia la compra.",
    "cierre": "El cliente esta por comprar: confirma el dato y avanza directo al "
              "cierre o al dato que falta.",
    "info": "Responde claro y util, y si hay un siguiente paso de venta natural, "
            "ofrecelo sin presionar.",
    "posventa": "Responde de servicio, sin forzar una venta nueva.",
}


def construir_prompt(hechos: list[str],
                     etapa: str,
                     venta: str = "",
                     directiva: str = "",
                     business_name: str = "la tienda") -> str:
    """Arma el prompt del redactor. hechos = lista de afirmaciones YA verificadas
    por el codigo. venta = angulo de conversion curado, opcional. directiva =
    instruccion de movimiento de venta (ej objecion), opcional. El modelo solo
    puede AFIRMAR lo que esta en los hechos."""
    guia = ETAPA_GUIA.get((etapa or "").strip().lower(), ETAPA_GUIA["info"])
    bloque_hechos = "\n".join(f"- {h}" for h in hechos if str(h).strip()) \
        or "- (sin hechos: no afirmes ningun dato)"
    bloque_venta = (f"\nANGULO DE VENTA YA APROBADO (podes usarlo tal cual o con "
                    f"tu tono):\n- {venta}\n" if venta.strip() else "")
    bloque_dir = (f"\nINSTRUCCION DE ESTA RESPUESTA:\n- {directiva}\n"
                  if directiva.strip() else "")
    return (
        f"Sos vendedor de {business_name}, hablas en espanol argentino, voseo, "
        f"calido y breve.\n\n"
        f"{constitucion_como_prompt()}\n\n"
        f"HECHOS VERIFICADOS, lo UNICO que podes afirmar. No agregues ningun dato "
        f"que no este aca, ni precio, ni plazo, ni fecha, ni detalle. Y NO los "
        f"resumas en vago: si el hecho es una lista, medios de pago, plazos, "
        f"nombralos tal cual, no digas 'los que manejamos':\n"
        f"{bloque_hechos}\n"
        f"{bloque_venta}"
        f"{bloque_dir}\n"
        f"ETAPA DE LA VENTA: {etapa}. {guia}\n\n"
        f"Devolve SOLO un JSON con dos campos:\n"
        f'{{"analisis_interno": "que hechos de arriba usaste y por que, una linea", '
        f'"respuesta_final": "tu mensaje al cliente, 1 a 3 oraciones, texto plano, '
        f'sin markdown"}}'
    )


def parsear_salida(raw: str) -> Optional[str]:
    """Saca respuesta_final del JSON del modelo. Devuelve None si no se pudo, para
    que el llamador decida (reintento o fallback). Nunca devuelve el analisis."""
    if not raw:
        return None
    txt = raw.strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```(?:json)?\s*", "", txt)
        txt = re.sub(r"\s*```$", "", txt).strip()
    try:
        data = json.loads(txt)
        final = str(data.get("respuesta_final", "") or "").strip()
        return final or None
    except (json.JSONDecodeError, AttributeError):
        # Fallback tolerante: intentar pescar el campo por regex.
        m = re.search(r'"respuesta_final"\s*:\s*"((?:[^"\\]|\\.)*)"', txt)
        if m:
            return m.group(1).encode().decode("unicode_escape").strip() or None
        return None
