"""
AREA: RESET_CODE — la palabra clave de PRUEBA ("verifika2026") que borra la
conversacion para testear desde el mismo usuario. Vive en el orchestrator para
que funcione con CUALQUIER camino (se rompio cuando el orchestrator paso de
interprete_libre al flujo atado y el reset quedo en el camino viejo, sin efecto).
"""
import asyncio

from app.core.orchestrator import process_message
from app.config import get_settings

settings = get_settings()


def _correr(msg, user="u_reset", canal="sim"):
    return asyncio.new_event_loop().run_until_complete(
        process_message(user, msg, tienda_id="verifika_prod", canal=canal))


def test_reset_code_reinicia_y_confirma_sin_llm(firestore_doble):
    # el RESET_CODE exacto devuelve la confirmacion directa, sin pasar por el LLM.
    r = _correr(settings.RESET_CODE)
    assert r == "Listo, conversacion reiniciada. Empezamos de cero."


def test_reset_code_tolera_mayusculas_y_espacios(firestore_doble):
    r = _correr(f"  {settings.RESET_CODE.upper()} ")
    assert r == "Listo, conversacion reiniciada. Empezamos de cero."


def test_mensaje_normal_no_dispara_reset(monkeypatch, firestore_doble):
    # un mensaje que NO es el codigo no resetea: se despacha al flujo (mockeado).
    import app.core.orchestrator as O

    async def _fake_atado(user_id, raw_message, tid, canal, trace_id):
        return "RESPUESTA_DEL_FLUJO"

    monkeypatch.setattr(O, "procesar_atado", _fake_atado)
    assert _correr("hola tenes mouse?") == "RESPUESTA_DEL_FLUJO"
    # y "nueva compra" (frase natural) tampoco resetea: el bot mantiene continuidad.
    assert _correr("quiero hacer una nueva compra") == "RESPUESTA_DEL_FLUJO"
