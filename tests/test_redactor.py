"""
REDACTOR (nivel 2): los SELLOS mecanicos son deterministas y se lockean acá.
La garantía: el texto crudo del modelo nunca llega al cliente; o cumple los
sellos y el código estampa los bloques reales, o se descarta entero (None) y
sale el compositor puro.
"""
import asyncio

from app.core.redactor import ensamblar_si_valido, redactar

_B1 = "Mouse Genius DX-110 Negro - $8.500 (23 en stock)"
_B2 = "Envio a Cordoba capital: $6.000."
_SECS = [_B1, _B2]


def test_salida_valida_estampa_los_bloques_reales():
    salida = ("¡Buenísima elección!\n\n[[B1]]\n\nY mirá lo que sale "
              "llevártelo hasta tu casa:\n\n[[B2]]\n\n¿Te lo confirmo?")
    texto = ensamblar_si_valido(salida, _SECS)
    assert _B1 in texto and _B2 in texto
    assert "[[B1]]" not in texto and "[[B2]]" not in texto
    assert "Buenísima" in texto


def test_marcador_faltante_rechaza():
    assert ensamblar_si_valido("Hola [[B1]] y listo", _SECS) is None


def test_marcador_duplicado_rechaza():
    assert ensamblar_si_valido("[[B1]] [[B1]] [[B2]]", _SECS) is None


def test_orden_invertido_rechaza():
    assert ensamblar_si_valido("[[B2]] y despues [[B1]]", _SECS) is None


def test_digito_en_la_prosa_rechaza():
    # El modelo re-tipeo un precio fuera del bloque: se descarta ENTERO.
    salida = "Sale $8.500 nomas!\n[[B1]]\n[[B2]]"
    assert ensamblar_si_valido(salida, _SECS) is None


def test_nombre_de_producto_en_la_prosa_rechaza():
    salida = "El DX-110 Negro es lo mas vendido!\n[[B1]]\n[[B2]]"
    assert ensamblar_si_valido(
        salida, _SECS, ["Mouse Genius DX-110 Negro"]) is None


def test_prosa_kilometrica_rechaza():
    salida = ("bla " * 300) + "[[B1]] [[B2]]"
    assert ensamblar_si_valido(salida, _SECS) is None


def test_un_solo_bloque_no_llama_al_modelo():
    # Con menos de dos bloques no hay nada que coser: None inmediato, sin LLM
    # (si intentara llamar, explotaria por cliente/clave y el test lo veria).
    assert asyncio.run(redactar("hola", [_B1], "t1")) is None
    assert asyncio.run(redactar("hola", [], "t1")) is None
