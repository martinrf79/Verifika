"""
AREA: ENSAMBLADOR — colocación coherente de bloques sellados en la prosa.

Lockea colocar_bloque: un dato de una línea entra en el lugar del marcador; un
bloque de varias líneas se levanta a su propio párrafo y nunca queda incrustado
en medio de una oración (el detalle del "dato colgado" que marcó Martín). Lógica
pura, sin LLM ni Firestore.
"""
from app.core.ensamblador import colocar_bloque, normalizar


def test_dato_inline_va_en_su_lugar():
    out = colocar_bloque("El envío te sale [[ENVIO]] y llega rápido.",
                         "[[ENVIO]]", "Envío a Córdoba: $7.500")
    assert out == "El envío te sale Envío a Córdoba: $7.500 y llega rápido."
    assert "[[" not in out


def test_bloque_multilinea_va_a_su_propio_parrafo():
    presupuesto = "Tu pedido:\n- Teclado $12.000\n- Total: $12.000"
    out = colocar_bloque("Genial, ahí va: [[PRESUPUESTO]] ¿te sirve?",
                         "[[PRESUPUESTO]]", presupuesto)
    lineas = out.split("\n")
    # El bloque quedó en su propio párrafo, la prosa de alrededor intacta.
    assert "Genial, ahí va:" in lineas[0]
    assert "Tu pedido:" in out and "- Total: $12.000" in out
    assert "¿te sirve?" in lineas[-1]
    # No quedó incrustado en la misma línea que la prosa.
    assert "ahí va: Tu pedido:" not in out
    assert "[[" not in out


def test_bloque_vacio_quita_marcador_y_limpia():
    out = colocar_bloque("El total es [[PRESUPUESTO]] gracias.",
                         "[[PRESUPUESTO]]", "")
    assert "[[" not in out
    assert "El total es" in out and "gracias." in out
    # Sin doble espacio dejado por el hueco.
    assert "  " not in out


def test_marcador_ausente_no_toca():
    txt = "Un mensaje sin marcadores."
    assert colocar_bloque(txt, "[[ENVIO]]", "algo") == txt


def test_normalizar_colapsa_lineas_en_blanco():
    assert normalizar("hola\n\n\n\nchau  \n") == "hola\n\nchau"


def test_bloque_al_final_no_deja_blancos_colgando():
    out = colocar_bloque("Mirá: [[PRESUPUESTO]]",
                         "[[PRESUPUESTO]]", "linea1\nlinea2")
    assert out.endswith("linea2")
    assert not out.endswith("\n")
