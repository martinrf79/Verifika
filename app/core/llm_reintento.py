"""
REINTENTO DE LLAMADA LLM — red comun contra el hipo transitorio del proveedor.

Nacio de un banco end-to-end (23-jul): un 429 en RAFAGA de Gemini hacia que el
solver devolviera CERO fragmentos y el bot emitiera el fallback "dejame
consultar y te confirmo", una promesa que nunca cumple. Ni el interprete ni el
solver reintentaban. En produccion (clave paga) los 429 son rafagas que se
recuperan en menos de un segundo: un backoff acotado los absorbe sin que el
cliente vea nada.

UN solo helper para las DOS llamadas (interprete y solver): consolidacion, no
dos copias. Solo reintenta el error TRANSITORIO (429/5xx/timeout/overloaded);
cualquier otro se re-lanza al toque, igual que antes. Acotado: agrega a lo sumo
la suma de los backoffs cuando de verdad hay hipo, cero en el camino feliz.
"""
import asyncio

from app.logger import get_logger

log = get_logger(__name__)

# Marcas de error que SI conviene reintentar: cuota momentanea, 5xx, saturacion,
# timeout. Se matchea sobre el texto del error (los SDK OpenAI-compat lo traen).
_TRANSITORIO = ("429", "500", "502", "503", "504", "overloaded",
                "unavailable", "timeout", "timed out", "quota", "rate limit")


def es_transitorio(e: BaseException) -> bool:
    if isinstance(e, (asyncio.TimeoutError, TimeoutError)):
        return True
    s = str(e).lower()
    return any(t in s for t in _TRANSITORIO)


async def llamar_con_reintento(fn, *, timeout_s: float | None = None,
                               intentos: int = 3, base_s: float = 0.6,
                               trace_id: str = "") -> str:
    """Corre fn() (bloqueante) en un thread; si falla con error transitorio,
    reintenta con backoff exponencial (base_s, 2*base_s, ...). Re-lanza el ultimo
    error si se agotan los intentos o el error NO es transitorio. Con timeout_s
    cada intento tiene su propio tope; sin el, no se impone timeout."""
    ultimo: BaseException | None = None
    for i in range(intentos):
        try:
            tarea = asyncio.to_thread(fn)
            if timeout_s is not None:
                return await asyncio.wait_for(tarea, timeout_s)
            return await tarea
        except Exception as e:  # noqa: BLE001 — se re-lanza abajo si no es transitorio
            ultimo = e
            if i < intentos - 1 and es_transitorio(e):
                log.warning("llm_reintento", intento=i + 1,
                            error=str(e)[:80], trace_id=trace_id)
                await asyncio.sleep(base_s * (2 ** i))
                continue
            raise
    assert ultimo is not None
    raise ultimo
