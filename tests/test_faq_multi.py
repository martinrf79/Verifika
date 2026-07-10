"""
FALLAS de la charla real de WhatsApp del 10-jul, lockeadas:
1. "cuanto demoran los envios" / "en cuanto tiempo llegan" caian al tema
   generico 'envios' (Andreani y OCA) y el cliente pregunto la demora CINCO
   veces sin respuesta -> señal determinista de PLAZO en el ranking.
2. Un turno con VARIAS preguntas de politica recibia UNA sola respuesta ->
   _faq_temas_multi sirve hasta 3 temas sin solapamiento.
"""
import pytest

from app.core.tools import query_faq, _faq_temas_multi


@pytest.fixture(autouse=True)
def _doble(firestore_doble):
    yield


def _faq():
    # Import tardio: el doble parchea el modulo DESPUES del import del test.
    from app.storage import firestore_client as fc
    return fc.get_all_faq(tienda_id="verifika_prod")


_PREGUNTAS_PLAZO = [
    "cuanto demoran los envios",
    "en cuanto tiempo llegan los productos",
    "alguien que me responda en cuanto llegan o demoran los envios",
    "dime cuanto tiempo demora",
    "cuanto tarda el envio a rosario?",
]


def test_toda_forma_de_preguntar_demora_rutea_a_plazo():
    for q in _PREGUNTAS_PLAZO:
        assert query_faq(q).get("tema") == "plazo_envio", q


def test_costo_y_generico_no_regresionan():
    assert query_faq("cuanto sale el envio a cordoba").get("tema") == "costo_envio"
    assert query_faq("hacen envios a todo el pais?").get("tema") == "envios"


def test_multi_pregunta_sirve_los_tres_temas():
    # El turno 2 textual de la charla real: seguridad + demora + garantia.
    temas = _faq_temas_multi(
        "Dime Es segura la compra por aqui y dime cuanto demoran los envios "
        "Y si los productos tienen garantia", _faq())
    assert set(temas) == {"confianza_seguridad", "plazo_envio", "garantia"}


def test_pregunta_simple_sirve_un_solo_tema():
    faq = _faq()
    assert _faq_temas_multi("cuanto sale el envio a cordoba", faq) == ["costo_envio"]
    # plazo no arrastra al generico 'envios' de la misma familia
    assert _faq_temas_multi("cuanto demoran los envios", faq) == ["plazo_envio"]
