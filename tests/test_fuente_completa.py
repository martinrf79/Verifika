"""
AREA: Fuente de verdad completa (11-jul, orden de Martin) — curadas de
conocimiento, reservas con keywords reales, despedida B31 y la respuesta
honesta a preguntas SIN fuente.
"""
from app.core.compositor import componer
from app.core.ruteo_venta import rutear_venta

_INTERP_Q = {"intencion": "pregunta_especifica", "candidatos": [],
             "producto_resuelto": None, "confianza": 0.7}


def test_membrana_vs_mecanico_responde_conocimiento(firestore_doble):
    texto, _ = componer("cual es la diferencia entre membrana y mecanico?",
                        dict(_INTERP_Q), {}, "verifika_prod")
    assert "switch" in texto.lower()
    assert "membrana" in texto.lower()
    assert "no te terminé de entender" not in texto


def test_me_lo_guardas_sirve_curada_de_reserva(firestore_doble):
    texto, _ = componer("me lo guardas hasta el viernes?",
                        dict(_INTERP_Q), {}, "verifika_prod")
    assert "reservar" in texto.lower() or "seña" in texto.lower() \
        or "sena" in texto.lower()


def test_despedida_cierra_cordial(firestore_doble):
    interp = {"intencion": "otra", "candidatos": [],
              "producto_resuelto": None, "confianza": 0.5}
    texto, _ = componer("bueno listo, no quiero nada mas",
                        interp, {}, "verifika_prod")
    assert "Que andes bien" in texto
    assert "no te terminé de entender" not in texto


def test_despedida_rutea_b31():
    d = rutear_venta("eso es todo, gracias! chau",
                     {"intencion": "otra", "candidatos": []}, {})
    assert d["categoria"] == "B31"
    assert d["accion"] == "movida"


def test_pregunta_sin_fuente_honesta(firestore_doble):
    # Pregunta real sin respaldo en catalogo ni FAQ: honestidad + derivacion,
    # nunca "no te entendi" ni un invento.
    texto, _ = componer("dan capacitacion para usar los programas?",
                        dict(_INTERP_Q), {}, "verifika_prod")
    assert "no la tengo confirmada" in texto
    assert "persona del equipo" in texto


def test_no_pregunta_sigue_con_fallback_clasico(firestore_doble):
    interp = {"intencion": "otra", "candidatos": [],
              "producto_resuelto": None, "confianza": 0.3}
    texto, _ = componer("asdkjh qwerty", interp, {}, "verifika_prod")
    assert "no te terminé de entender" in texto


def test_dpi_responde_conocimiento(firestore_doble):
    texto, _ = componer("que es el dpi?", dict(_INTERP_Q), {},
                        "verifika_prod")
    assert "sensibilidad" in texto.lower()


# --- NO REPETIR EL ENLATADO + sin fuente (charla real 11-jul 17:59) ---

def test_bloque_repetido_detecta():
    from app.core.curadas import bloque_repetido
    bloque = ("Aceptamos transferencia bancaria, Mercado Pago y tarjetas "
              "Visa, Mastercard y American Express, credito o debito.")
    estado = {"ultima_respuesta_bot": "bla bla\n\n" + bloque + "\n\nchau"}
    assert bloque_repetido(bloque, estado, "y las tarjetas van directo?")
    # pidio repetir: se repite
    assert not bloque_repetido(bloque, estado, "repetime las formas de pago")
    # sin ultima respuesta: no filtra
    assert not bloque_repetido(bloque, {}, "y las tarjetas?")


def test_detalle_sin_fuente_no_repite_enlatado(firestore_doble):
    # Guion 33: la curada de formas de pago acaba de salir; la pregunta de
    # detalle no la re-sirve y cae al honesto sin-fuente.
    from app.core.compositor import componer
    from app.storage.firestore_client import get_all_faq
    faq = get_all_faq(tienda_id="verifika_prod") or {}
    bloque = faq["formas_pago"]["respuesta_curada"]
    interp = {"intencion": "pregunta_especifica", "candidatos": [],
              "producto_resuelto": None, "confianza": 0.7}
    estado = {"ultima_respuesta_bot": "Presupuesto...\n\n" + bloque}
    texto, _ = componer(
        "Las tarjetas como medio de pago son a traves de mercado pago o "
        "con la tarjeta directo", interp, estado, "verifika_prod")
    assert "no la tengo confirmada" in texto
    assert "Aceptamos transferencia" not in texto
