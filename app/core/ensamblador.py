"""
ENSAMBLADOR — arma el mensaje final con los bloques SELLADOS del código y la
prosa del solver, garantizando congruencia.

Estrategia acordada con Martín (6-jul): el LLM no es dueño de ningún dato duro.
Escribe la prosa y marca DÓNDE va cada bloque con un marcador; el código estampa
el bloque real de la fuente en ese lugar. Este módulo se ocupa de que el
resultado LEA BIEN: un dato de una línea entra donde el solver puso el marcador,
pero un bloque de varias líneas (un presupuesto, una política) NUNCA queda
incrustado en medio de una oración; se levanta a su propio párrafo y se limpia
el hueco. Así el detalle que marcó Martín, el dato colgado en mitad del párrafo,
no puede pasar. Lógica pura, determinista, sin LLM ni Firestore.
"""
import re


def _es_multilinea(bloque: str) -> bool:
    return "\n" in (bloque or "").strip()


def normalizar(texto: str) -> str:
    """Sin espacios al final de línea, sin más de una línea en blanco seguida,
    sin blancos al borde del mensaje. Deja la prosa prolija tras estampar."""
    lineas = [l.rstrip() for l in (texto or "").split("\n")]
    out: list[str] = []
    blanco_previo = False
    for l in lineas:
        es_blanco = (l.strip() == "")
        if es_blanco and (blanco_previo or not out):
            continue
        out.append(l)
        blanco_previo = es_blanco
    return "\n".join(out).strip()


def colocar_bloque(texto: str, marca: str, bloque: str) -> str:
    """Estampa un bloque en el lugar del marcador, cuidando la congruencia.

    - marcador ausente -> el texto no se toca.
    - bloque vacío (la tool no corrió) -> se quita el marcador y se limpia el
      hueco: nunca se inventa un dato.
    - bloque de UNA línea (dato inline, ej "Envío a Córdoba: $7.500") -> va donde
      el solver puso el marcador, la oración se lee natural.
    - bloque de VARIAS líneas (presupuesto, política) -> a su propio párrafo,
      separado por líneas en blanco, para que no quede incrustado en una oración.
    """
    if not texto or marca not in texto:
        return texto or ""
    bloque = (bloque or "").strip()
    if not bloque:
        # Al quitar el marcador queda un hueco (doble espacio o espacio antes de
        # puntuacion): se colapsa para que la oracion no muestre la costura.
        limpio = texto.replace(marca, "")
        limpio = re.sub(r"[ \t]{2,}", " ", limpio)
        limpio = re.sub(r" +([,.;:!?])", r"\1", limpio)
        return normalizar(limpio)
    if not _es_multilinea(bloque):
        return normalizar(texto.replace(marca, bloque))
    return normalizar(texto.replace(marca, "\n\n" + bloque + "\n\n"))
