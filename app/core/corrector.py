"""
CORRECTOR ANCLADO — segunda pasada stateless que aterriza la respuesta del
Solver a la fuente de verdad del turno.

Idea (cerrada con Martin): el Solver responde con TODO el contexto y la memoria,
incluido el read-back "si te referis a...", las opciones A/B o el "confirmame".
El corrector recibe ESA respuesta tal cual MAS la evidencia real del turno
(productos que se buscaron, FAQ, PROOF de la calculadora), SIN memoria, sin
historial y SIN ver la pregunta original. Es como abrir un chat nuevo: limpio,
afinado para una sola cosa.

Su unica tarea: que cada HECHO de la respuesta este respaldado por la evidencia.
Si un hecho no esta o contradice la evidencia, lo corrige con el dato real o lo
quita. PRESERVA la estructura del Solver (opciones A/B, confirmacion), el tono de
venta y el idioma. No decide la conversacion: HEREDA la forma del Solver y solo
aterriza los hechos. Por eso funciona sin contexto: corregir un precio no
necesita saber por que se pidieron 3 unidades.

Filosofia: constrenir la generacion en vez de detectar despues. El corrector no
puede afirmar un hecho que no esta en la evidencia que recibio. Es capa
complementaria, NO reemplaza el piso duro: despues de el siguen corriendo el
verificador determinista de numeros y los demas gates.

Detras del flag CORRECTOR_ANCLADO (default off). Modelo configurable por el rol
'corrector' del llm_adapter (VERIFIKA_CORRECTOR_PROVIDER/MODEL), default deepseek.
"""
from typing import Optional

from app.logger import get_logger
from app.verifika.checker import _format_evidence
from app.verifika.llm_adapter import llm_complete

log = get_logger(__name__)

_SYSTEM_PROMPT = """\
Sos un CORRECTOR de hechos de una tienda. Recibis una RESPUESTA borrador escrita \
por un vendedor y la EVIDENCIA real de la tienda para este caso. No tenes memoria \
de la conversacion ni ves la pregunta del cliente: trabajas SOLO con el borrador \
y la evidencia.

Distingui DOS tipos de afirmacion y trata cada una distinto:

A) DATOS DE LA TIENDA (estricto, SIEMPRE salen de la evidencia): precios, stock, \
plazos de entrega, politicas (envio, pago, garantia, devolucion, retiro), \
servicios que ofrece la tienda, especificaciones y compatibilidad del producto, \
colores y variantes disponibles, nombres y existencia de productos.
  - Si coincide con la evidencia, dejalo igual.
  - Si contradice la evidencia, corregilo con el dato REAL de la evidencia.
  - Si NO figura en la evidencia, quitalo o reemplazalo por una formula honesta \
tipo "eso te lo confirmo en el momento". NUNCA inventes un dato de la tienda ni \
agregues productos, precios, colores o servicios que no esten en la evidencia.

  NEGACIONES Y HONESTIDAD: esta regla es la MAS IMPORTANTE de todas.
  - Si el borrador NIEGA algo ("No tenemos X", "No hacemos X") y X no figura en la evidencia, DEJALO intacto. La ausencia de X en el catalogo respalda la negacion. Solo corregi si la evidencia muestra que SI existe X.
  - Si el borrador dice "No tenemos X, pero dejame consultar" o "te confirmo en el momento", DEJALO. Eso es un vendedor honesto, no un error a corregir.
  - EJEMPLO CRITICO: borrador="No tenemos servicio de envoltorio para regalo, pero dejame consultar con el area correspondiente si podemos coordinar algo y te confirmo en un rato." -> respuesta correcta=EL MISMO BORRADOR, sin cambios. No hay envoltorio en la evidencia, asi que "No tenemos" es correcto, y "dejame consultar" es honesto. NO lo reemplaces por "No tengo esa informacion confirmada" porque eso destruye la respuesta de venta.
  - Solo corregi si la evidencia contradice la negacion: borrador="No tenemos envio gratis" pero FAQ="envio gratis en compras mayores a $100.000" -> corregi.

B) CONOCIMIENTO GENERAL DEL MUNDO (libre): geografia (en que provincia o region \
queda una ciudad), para que sirve o que uso tiene un producto, datos tecnicos \
generales que no son del catalogo.
  - Esto el vendedor lo puede decir aunque NO este en la evidencia. NO lo borres.
  - Solo corregilo si es claramente falso. Y NUNCA presentes un dato general como \
un compromiso de la tienda (un envio, un precio, un plazo, un servicio).

Reglas de forma CRITICAS (violarlas es peor que no corregir):
0. NUNCA reemplaces toda la respuesta por una frase corta tipo "No tengo esa informacion". Si no podes verificar una parte, quita SOLO esa parte y conserva el resto. Una respuesta parcialmente correcta es mejor que un fallback. Solo devolve una respuesta corta si el borrador entero es insalvable.
0b. NUNCA uses la frase "No tengo esa informacion confirmada en el catalogo" ni ninguna variante. Esa frase pertenece al verificador, no al corrector. Si un dato no esta en la evidencia, reemplazalo por "eso te lo confirmo en el momento" o quitale precision, pero NO tires toda la respuesta.
0c. Si el borrador tiene 2 o mas oraciones y solo una tiene un dato sin evidencia, corregi SOLO esa oracion y dejá las demas intactas.

Reglas de forma:
1. PRESERVA la estructura del borrador: si ofrece una opcion A o B, corregi cada \
opcion por separado y deja las dos; si pide confirmar algo, mante la pregunta de \
confirmacion; si es una respuesta directa, dejala directa.
2. PRESERVA el tono de venta, el idioma (espanol argentino, voseo) y el largo \
aproximado. No agregues advertencias ni mensajes de sistema.
3. Los numeros que vienen en un PROOF de la evidencia ya estan calculados y son \
validos: no los recalcules ni los toques.

Devolve UNICAMENTE la respuesta corregida final, lista para mandar al cliente, \
sin explicaciones, sin comillas y sin JSON."""


def corregir_respuesta(
    respuesta_solver: str,
    evidence: list[dict],
    trace_id: Optional[str] = None,
) -> dict:
    """Aterriza la respuesta del Solver a la evidencia del turno.

    Devuelve dict:
      - respuesta_final: texto corregido listo para mandar
      - cambiada: bool, si el corrector modifico algo
      - ok: bool, si la pasada corrio sin caer a fail-open

    Diseno fail-open: si no hay evidencia, si el modelo devuelve vacio o si algo
    falla, devuelve la respuesta original sin tocar. El piso duro (verificador
    determinista + gates) corre IGUAL despues, asi que un fail-open no afloja la
    garantia de numeros; solo significa que esta pasada no aporto.
    """
    original = (respuesta_solver or "").strip()

    if not original:
        return {"respuesta_final": respuesta_solver, "cambiada": False, "ok": False}

    # Sin evidencia no hay contra que aterrizar. No tocar; dejar el piso duro.
    if not evidence:
        log.info("corrector_sin_evidencia", trace_id=trace_id)
        return {"respuesta_final": respuesta_solver, "cambiada": False, "ok": False}

    evidencia_txt = _format_evidence(evidence)
    user = (
        f"EVIDENCIA:\n{evidencia_txt}\n\n"
        f"RESPUESTA BORRADOR:\n{original}\n\n"
        f"Respuesta corregida:"
    )

    try:
        result = llm_complete(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            role="corrector",
            temperature=0.1,
            max_tokens=900,
            trace_id=trace_id,
        )
    except Exception as e:
        log.error("corrector_error", trace_id=trace_id, error=str(e)[:200])
        return {"respuesta_final": respuesta_solver, "cambiada": False, "ok": False}

    corregida = (result.get("content") or "").strip()

    # Salida vacia o absurdamente corta = el modelo fallo. Fail-open al original.
    if len(corregida) < 8:
        log.warning("corrector_salida_vacia", trace_id=trace_id,
                    largo=len(corregida))
        return {"respuesta_final": respuesta_solver, "cambiada": False, "ok": False}

    cambiada = corregida != original
    log.info("corrector_ok", trace_id=trace_id, cambiada=cambiada,
             largo_in=len(original), largo_out=len(corregida),
             model=result.get("model"))

    return {"respuesta_final": corregida, "cambiada": cambiada, "ok": True}
