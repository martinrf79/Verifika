"""
AREA: Costuras del banco 11-jul — envio con destino dado + sellos nuevos del
redactor (saludo a mitad de charla, frase cortada).
"""
from app.core.compositor import _sec_envio, componer
from app.core.redactor import ensamblar_si_valido
from app.core.estado_venta import set_current_estado


def test_villa_maria_cordoba_cotiza_sin_repedir(firestore_doble):
    # Guion 28 turno 9: 'el envio va a Villa Maria, Cordoba, cuanto me queda?'
    # respondia 'pasame tu provincia o CP'. La curada standalone ya no ataja
    # un mensaje con localidad y el compositor cotiza.
    set_current_estado({})
    texto = _sec_envio("el envio va a Villa Maria, Cordoba, cuanto me queda?",
                       {}, "verifika_prod", {})
    assert texto and "$7.500" in texto
    assert "Pasame tu provincia" not in texto


def test_va_todo_a_destino_cotiza_sin_keyword_envio(firestore_doble):
    # Guion 29 turno 7: 'va todo a San Francisco, Cordoba' no traia la
    # palabra envio y el destino se perdia (el presupuesto salia sin flete).
    set_current_estado({})
    texto = _sec_envio("va todo a San Francisco, Cordoba",
                       {}, "verifika_prod", {})
    assert texto and "$7.500" in texto


def test_curada_envio_no_ataja_con_localidad(firestore_doble):
    from app.core.curadas import servir_curada
    r = servir_curada("el envio va a Villa Maria, Cordoba, cuanto me queda?",
                      {"intencion": "pregunta_especifica", "confianza": 0.8,
                       "candidatos": [], "producto_resuelto": None},
                      {}, False, "verifika_prod")
    assert r is None


_SECS = ["Bloque uno con datos.", "Bloque dos con datos."]


def test_sello_saludo_en_prosa_rechaza():
    salida = "¡Hola! Qué bueno que consultes. [[B1]] Y además [[B2]] ¿Avanzamos?"
    assert ensamblar_si_valido(salida, _SECS) is None


def test_sello_frase_cortada_rechaza():
    salida = "Mirá, [[B1]] El envío tiene un costo de [[B2]] ¿Avanzamos?"
    assert ensamblar_si_valido(salida, _SECS) is None


def test_prosa_sana_pasa():
    salida = ("Buenísima elección. [[B1]] Y sobre lo otro que preguntaste: "
              "[[B2]] ¿Avanzamos con el pedido?")
    r = ensamblar_si_valido(salida, _SECS)
    assert r and "Bloque uno con datos." in r and "Bloque dos con datos." in r


def test_secciones_duplicadas_no_se_pegan(firestore_doble):
    # El mismo texto llegando por dos caminos sale UNA vez.
    interp = {"intencion": "pregunta_especifica", "candidatos": [],
              "producto_resuelto": None, "confianza": 0.7}
    texto, _ = componer("hacen factura A?", interp, {}, "verifika_prod")
    assert texto.count("factura A") <= 2  # una vez el dato, sin bloque doble
