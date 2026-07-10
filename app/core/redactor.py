"""
REDACTOR — nivel 2 de la escalera (decision de Martin, 10-jul).

El codigo arma los bloques sellados (compositor: ficha, presupuesto, envio,
politica); el modelo escribe SOLO la prosa de union entre bloques, para que el
mensaje salga coherente y vendedor en vez de bloques apilados. La atadura NO
depende de la obediencia del modelo: su salida usa marcadores [[B1]]..[[Bn]] y
el CODIGO estampa los bloques reales; el texto crudo del modelo nunca viaja al
cliente.

Sellos mecanicos (todo-o-nada; cualquier violacion -> None y sale el texto del
compositor puro, el peor caso es un mensaje mas soso, nunca un dato falso):
1. Cada marcador aparece exactamente UNA vez y en el MISMO orden.
2. La prosa fuera de los marcadores no trae digitos ni nombres de productos.
3. Tope de largo de la prosa (el redactor une, no diserta).
"""
import asyncio
import re

from app.config import get_settings
from app.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

# Tope de prosa TOTAL (sin contar los bloques). Une bloques, no reescribe.
_MAX_PROSA = 600
_TIMEOUT_S = 12


def _marcadores(n: int) -> list[str]:
    return [f"[[B{i}]]" for i in range(1, n + 1)]


def ensamblar_si_valido(salida: str, secciones: list[str],
                        nombres_prohibidos: list[str] | None = None) -> str | None:
    """Valida la salida del modelo y estampa los bloques reales. None si viola
    un sello. Puro y determinista: es lo que lockean los tests offline."""
    if not salida or not secciones:
        return None
    marcas = _marcadores(len(secciones))

    # Sello 1: cada marcador exactamente una vez, y en orden.
    posiciones = []
    for m in marcas:
        if salida.count(m) != 1:
            return None
        posiciones.append(salida.index(m))
    if posiciones != sorted(posiciones):
        return None

    # Sello 2: la prosa (lo que queda al sacar los marcadores) sin digitos ni
    # nombres de productos. Un numero fuera de un bloque sellado no tiene
    # forma de estar respaldado: se rechaza entero.
    prosa = salida
    for m in marcas:
        prosa = prosa.replace(m, " ")
    if re.search(r"\d", prosa):
        return None
    prosa_low = prosa.lower()
    for nombre in (nombres_prohibidos or []):
        n = str(nombre or "").strip().lower()
        if len(n) >= 4 and n in prosa_low:
            return None

    # Sello 3: tope de prosa.
    if len(prosa.strip()) > _MAX_PROSA:
        return None

    texto = salida
    for m, bloque in zip(marcas, secciones):
        texto = texto.replace(m, bloque.strip())
    # Colapsar lineas en blanco de mas.
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()
    return texto or None


def _prompt(mensaje: str, secciones: list[str]) -> str:
    marcas = _marcadores(len(secciones))
    bloques = "\n\n".join(
        f"{m} =\n{s.strip()}" for m, s in zip(marcas, secciones))
    return (
        "Sos el redactor de un bot de ventas de una tienda online argentina. "
        "El sistema ya armo los bloques OFICIALES con los datos verificados; "
        "vos escribis el mensaje final para el cliente usando los marcadores "
        f"{', '.join(marcas)} donde va cada bloque, en ESE orden.\n\n"
        "Reglas duras:\n"
        "- Pone cada marcador una sola vez, en su orden. El contenido del "
        "bloque NO lo escribas vos: solo el marcador.\n"
        "- Entre marcadores agrega frases CORTAS de union, calidas y "
        "vendedoras, que respondan al tono del cliente.\n"
        "- PROHIBIDO escribir numeros, precios, cantidades o nombres de "
        "productos: eso ya vive en los bloques.\n"
        "- No inventes datos, plazos ni promesas.\n"
        "- Espanol argentino, tuteo, texto plano sin markdown.\n"
        "- Cerra con UNA pregunta corta de venta SOLO si ningun bloque ya "
        "pregunta.\n\n"
        f"Mensaje del cliente:\n{mensaje.strip()}\n\n"
        f"Bloques oficiales:\n{bloques}\n\n"
        "Respondeme SOLO con el mensaje final (prosa + marcadores)."
    )


async def redactar(mensaje: str, secciones: list[str], tienda_id: str,
                   trace_id: str | None = None,
                   productos_vistos: list[dict] | None = None) -> str | None:
    """Prosa de union del turno. None = usar el texto del compositor puro."""
    secciones = [s for s in (secciones or []) if str(s or "").strip()]
    if len(secciones) < 2:
        return None  # un solo bloque: no hay nada que coser

    from app.core.agent import _get_client, modelo_solver
    from app.config import (deepseek_extra_body, gemini_thinking_off,
                            nvidia_thinking_off, openrouter_reasoning_off)
    client = _get_client()
    modelo = modelo_solver()
    extra = (nvidia_thinking_off(settings.LLM_PROVIDER, modelo)
             or openrouter_reasoning_off(settings.LLM_PROVIDER, modelo)
             or gemini_thinking_off(settings.LLM_PROVIDER, modelo)
             or deepseek_extra_body(modelo))

    def _llamar() -> str:
        kw = dict(model=modelo,
                  messages=[{"role": "user",
                             "content": _prompt(mensaje, secciones)}],
                  temperature=0.3, max_tokens=500)
        if extra:
            kw["extra_body"] = extra
        r = client.chat.completions.create(**kw)
        return (r.choices[0].message.content or "").strip()

    try:
        salida = await asyncio.wait_for(
            asyncio.to_thread(_llamar), timeout=_TIMEOUT_S)
    except Exception as e:
        log.warning("redactor_llm_error", trace_id=trace_id,
                    error=str(e)[:120])
        return None

    nombres = [p.get("nombre") for p in (productos_vistos or [])
               if isinstance(p, dict)]
    texto = ensamblar_si_valido(salida, secciones, nombres)
    if texto is None:
        log.warning("redactor_sello_rechazo", trace_id=trace_id,
                    salida_preview=(salida or "")[:200])
    return texto
