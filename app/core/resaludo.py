"""
NO_RESALUDO — el bot saluda en el primer mensaje, no a mitad de charla.

Bug visto: el Solver abre con "hola" o "buenas" en el segundo o tercer mensaje.
Es estilo del modelo, no del estado: aunque el estado no vuelva a saludo, la
prosa igual puede arrancar saludando. Re-saludar a mitad de charla suena a bot y
rompe el hilo de una venta.

Esta pieza saca por codigo el saludo INICIAL de la respuesta, conservando el
resto y capitalizando lo que queda. No toca respuestas que sean SOLO un saludo
(ahi el saludo es la respuesta entera). El orchestrator la aplica solo cuando ya
hay historial (no es el primer turno) y la respuesta salio del Solver, nunca
sobre un saludo deliberado por codigo.

Funcion PURA. Detras del flag NO_RESALUDO (default off).
"""
import re

# Saludo de apertura: una formula de saludo al principio, con su puntuacion y un
# "como va / como andas" opcional pegado. Solo al inicio del texto.
_SALUDO_INICIAL = re.compile(
    r"^\s*[¡!]*\s*"
    # Las formulas de varias palabras van PRIMERO: si "hola" pegara antes que
    # "hola de nuevo", quedaria "de nuevo" colgado.
    r"(?:hola\s+de\s+nuevo|buenas\s+tardes|buenas\s+noches"
    r"|buen[oa]s?\s+d[ií]as?|qu[eé]\s+tal|hola+|holis|buenas|saludos)"
    r"[\s,!.¡?\-–—]*"
    r"(?:(?:c[oó]mo|como)\s+(?:va|and[aá]s|est[aá]s|te\s+va|anda)\s*\??"
    r"[\s,!.¡?\-–—]*)?",
    re.IGNORECASE)


def quitar_resaludo(texto: str) -> str:
    """Saca el saludo inicial de la respuesta del bot. Si el texto era SOLO el
    saludo, lo deja intacto (no se devuelve vacio)."""
    if not texto or not texto.strip():
        return texto
    nuevo = _SALUDO_INICIAL.sub("", texto, count=1).lstrip()
    if not nuevo:
        # La respuesta era solo el saludo: no la borramos.
        return texto
    if nuevo == texto.lstrip():
        # No habia saludo inicial: nada que sacar.
        return texto
    # Capitaliza el nuevo arranque si quedo en minuscula tras el corte.
    if nuevo[0].islower():
        nuevo = nuevo[0].upper() + nuevo[1:]
    return nuevo
