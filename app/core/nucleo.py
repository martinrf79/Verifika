"""
NUCLEO FUENTE DE VERDAD — orquesta las cuatro puertas, el redactor y el gate.

Flujo cuando NUCLEO_FUENTE_VERDAD esta on:
  1. resolver_puertas decide la salida sobre la fuente de verdad.
  2. confirmar / consultar -> respuesta DETERMINISTA, sin LLM. No puede alucinar.
  3. responder -> el redactor (LLM) viste el hecho + capa de venta, y el GATE por
     gravedad lo controla; hasta 2 intentos. Si el redactor no pasa el gate, se
     cae al DATO CURADO pelado, que es verdad por construccion. O sea, la puerta
     responder NUNCA termina en un dato inventado: en el peor caso manda la
     verdad sin vestir.
  4. seguir -> el nucleo no maneja, delega al resto del pipeline (producto,
     cotizacion).

El gate por GRAVEDAD reusa los verificadores que ya existen: plata (numeros),
servicios y hechos. Son las clases de alta gravedad; el tono y lo blando no se
gatean. Si alguno bloquea, no pasa.

El llamado al modelo se INYECTA (llamar_modelo), asi el modulo se testea sin LLM.
"""
from typing import Awaitable, Callable, Optional

from app.logger import get_logger
from app.core.faq_responder import resolver_puertas
from app.core.objecion import (
    detectar_objecion, hechos_de_objecion, directiva_de_objecion)
from app.core.redactor import construir_prompt, parsear_salida
from app.core.verificador import verificar_respuesta
from app.core.verificador_servicios import verificar_servicios
from app.core.verificador_hechos import verificar_hechos

log = get_logger(__name__)

MENSAJE_CONSULTAR = ("Buena pregunta, dejame confirmarlo bien y te respondo a la "
                     "brevedad asi no te paso un dato equivocado.")

MAX_INTENTOS_REDACTOR = 2


def _evidencia_faq(faq: dict) -> list[dict]:
    """La FAQ entera como evidencia para el gate, asi tiene la foto completa de
    lo que la tienda SI ofrece."""
    ev = []
    for tema, data in (faq or {}).items():
        item = {"tipo": "faq", "id": tema, "tema": tema,
                "respuesta": (data or {}).get("respuesta", ""),
                "faq_tipo": (data or {}).get("tipo", "informativo")}
        if (data or {}).get("valores"):
            item["valores"] = data["valores"]
        ev.append(item)
    return ev


def gate_gravedad(respuesta: str, evidencia: list[dict],
                  trace_id: Optional[str] = None) -> dict:
    """Piso por gravedad: corre los verificadores de alta gravedad, plata,
    servicios y hechos. Bloquea si ALGUNO bloquea. Devuelve {ok, verificador}."""
    for fn in (verificar_respuesta, verificar_servicios, verificar_hechos):
        try:
            r = fn(respuesta, evidencia, trace_id=trace_id)
            if not r.get("ok", True):
                log.info("gate_bloqueo", trace_id=trace_id, verificador=fn.__name__)
                return {"ok": False, "verificador": fn.__name__,
                        "detalle": r}
        except Exception as e:
            log.error("gate_error", trace_id=trace_id, verificador=fn.__name__,
                      error=str(e)[:160])
    return {"ok": True}


def _hay_producto(interp: Optional[dict]) -> bool:
    """Mencion de un producto resuelto (no candidatos sueltos). Una pregunta de
    politica puede arrastrar uno por el anclaje; por eso un match FUERTE de la
    fuente le gana a esto."""
    return bool(interp and interp.get("producto_resuelto"))


def _compra_activa(interp: Optional[dict]) -> bool:
    """Intencion de comprar. Esto SI manda al solver para cotizar y cerrar,
    aunque haya un match de FAQ."""
    return bool(interp and interp.get("intencion") == "decision_compra")


def _es_consulta_info(interp: Optional[dict], hay_prod: bool) -> bool:
    if hay_prod or not interp:
        return False
    return interp.get("intencion") in ("pregunta_especifica", "otra")


async def procesar_nucleo(
        raw_message: str,
        interpretacion: Optional[dict],
        faq: dict,
        llamar_modelo: Callable[[str], Awaitable[str]],
        *,
        etapa: str = "info",
        business_name: str = "la tienda",
        trace_id: Optional[str] = None) -> dict:
    """Procesa el mensaje por el nucleo. Devuelve:
      {manejado: True, puerta, respuesta}  si el nucleo respondio.
      {manejado: False, puerta: 'seguir'}  si hay que delegar al pipeline viejo.
    """
    hay_prod = _hay_producto(interpretacion)
    compra = _compra_activa(interpretacion)
    es_info = _es_consulta_info(interpretacion, hay_prod or compra)
    v = resolver_puertas(raw_message, faq, hay_producto=hay_prod,
                         compra_activa=compra, es_consulta_info=es_info,
                         trace_id=trace_id)
    puerta = v.get("puerta")

    if puerta == "confirmar":
        return {"manejado": True, "puerta": "confirmar",
                "respuesta": v["mensaje"]}

    if puerta in ("consultar", "seguir"):
        # Antes de consultar o delegar, mirar si es una OBJECION (regateo,
        # descuento por cantidad, pedido de servicio que no damos). Esas las
        # maneja el redactor en etapa objecion, groundeado: niega con cortesia y
        # pivotea a lo que SI hay, mejor que un fallback o un "dejame consultar".
        tipo = detectar_objecion(raw_message)
        hechos_obj = hechos_de_objecion(tipo, faq) if tipo else []
        if tipo and hechos_obj:
            respuesta, vestido = await _vestir(
                hechos_obj, etapa="objecion", venta="",
                directiva=directiva_de_objecion(tipo), faq=faq,
                llamar_modelo=llamar_modelo, business_name=business_name,
                curado=" ".join(hechos_obj), trace_id=trace_id)
            log.info("nucleo_objecion", trace_id=trace_id, tipo=tipo,
                     vestido=vestido)
            return {"manejado": True, "puerta": "objecion", "respuesta": respuesta,
                    "vestido": vestido, "tipo_objecion": tipo}
        if puerta == "consultar":
            return {"manejado": True, "puerta": "consultar",
                    "respuesta": MENSAJE_CONSULTAR}
        return {"manejado": False, "puerta": "seguir"}

    # puerta == responder: vestir el hecho + capa de venta.
    hecho = v.get("respuesta", "")
    venta = v.get("venta", "")
    curado = hecho + (("\n\n" + venta) if venta else "")
    respuesta, vestido = await _vestir(
        [hecho], etapa=etapa, venta=venta, directiva="", faq=faq,
        llamar_modelo=llamar_modelo, business_name=business_name,
        curado=curado, trace_id=trace_id)
    return {"manejado": True, "puerta": "responder", "respuesta": respuesta,
            "vestido": vestido}


async def _vestir(hechos, *, etapa, venta, directiva, faq, llamar_modelo,
                  business_name, curado, trace_id):
    """Render con el redactor + gate por gravedad, hasta 2 intentos. Si no pasa,
    cae al texto curado (verdad por construccion). Devuelve (respuesta, vestido)."""
    prompt = construir_prompt(hechos, etapa=etapa, venta=venta,
                              directiva=directiva, business_name=business_name)
    evidencia = _evidencia_faq(faq)
    for _ in range(MAX_INTENTOS_REDACTOR):
        try:
            raw = await llamar_modelo(prompt)
        except Exception as e:
            log.error("redactor_llm_error", trace_id=trace_id, error=str(e)[:160])
            break
        cand = parsear_salida(raw)
        if not cand:
            continue
        if gate_gravedad(cand, evidencia, trace_id=trace_id).get("ok"):
            return cand, True
        prompt = (prompt + "\n\n[El gate rechazo tu respuesta anterior. Reescribi "
                  "usando UNICAMENTE los hechos dados, sin agregar ningun dato.]")
    log.info("redactor_fallback_curado", trace_id=trace_id)
    return curado, False
