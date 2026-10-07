"""UN SOLO MENSAJE DE SISTEMA — la puerta de Gemini tira todos menos el ultimo (7-oct-2026).

El tablero mandaba sus reglas y despues la memoria como otro sistema. Gemini,
por su puerta OpenAI, se quedaba solo con la memoria: desde el segundo mensaje
de la charla el interprete y el redactor corrian sin instrucciones. Aca se
mira que lo que sale hacia el modelo lleve un solo sistema con todo adentro.
"""
import asyncio
from types import SimpleNamespace as NS

from app.core import tablero as T
from app.core.llm_reintento import un_sistema


def test_junta_los_sistemas_en_orden_y_deja_el_resto():
    msgs = [{"role": "system", "content": "REGLAS"}, {"role": "system", "content": "MEMORIA"},
            {"role": "user", "content": "hola"}, {"role": "assistant", "content": "que tal"},
            {"role": "user", "content": "chau"}]
    out = un_sistema(msgs)
    assert out[0] == {"role": "system", "content": "REGLAS\n\nMEMORIA"}
    assert out[1:] == msgs[2:]
    assert sum(m["role"] == "system" for m in out) == 1


def test_con_un_sistema_no_cambia_nada():
    msgs = [{"role": "system", "content": "REGLAS"}, {"role": "user", "content": "hola"}]
    assert un_sistema(msgs) == msgs


def test_el_tablero_le_manda_al_modelo_un_solo_sistema_con_reglas_y_memoria():
    vistos = []

    class Cli:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    vistos.append(kw["messages"])
                    return NS(choices=[NS(message=NS(content="{}"))],
                              usage=NS(prompt_tokens=1, completion_tokens=1, prompt_tokens_details=None))

    charla = T._charla([], "el cliente busco mouse", "y teclados?")
    asyncio.run(T._pedir(Cli, [{"role": "system", "content": "REGLAS"}] + charla, 0.0, None, "t", [], "x"))
    assert len(vistos) == 1
    sistemas = [m for m in vistos[0] if m["role"] == "system"]
    assert len(sistemas) == 1 and "REGLAS" in sistemas[0]["content"] and "el cliente busco mouse" in sistemas[0]["content"]
