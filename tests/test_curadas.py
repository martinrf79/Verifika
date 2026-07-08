"""
AREA: Respuestas curadas — el atajo determinista de FAQ (curadas.py).

Dos pisos:
  1. LOCK DE FORMATO sobre el faq.json REAL: toda respuesta_curada cargada debe
     estampar TODOS sus huecos contra los valores de su tema. Un typo en la
     curacion rompe este test y el gate del CI lo frena antes del deploy.
  2. COMPORTAMIENTO: el atajo solo actua en pregunta PURA de politica; con
     producto, carrito, cierre pendiente o intencion de compra, cae al camino
     normal (None). Conservador: ante la duda, no ataja.
"""
from app.core import curadas as C


# ── 1. Lock de formato sobre los datos reales ────────────────────────────────

def test_toda_curada_del_repo_estampa_completa(firestore_doble):
    from app.storage.firestore_client import get_all_faq
    faq = get_all_faq(tienda_id="verifika_prod")
    con_curada = {t: d for t, d in faq.items() if d.get("respuesta_curada")}
    assert con_curada, "Debe haber al menos una respuesta curada cargada."
    for tema, data in con_curada.items():
        out = C.estampar_valores(data["respuesta_curada"], data)
        assert out, f"La curada de '{tema}' tiene un hueco que no resuelve."
        assert "{{" not in out and "}}" not in out


def test_hueco_sin_valor_no_se_sirve():
    data = {"tema": "x", "valores": [], "respuesta_curada": "Sale {{precio}}."}
    assert C.estampar_valores(data["respuesta_curada"], data) is None


def test_formatos_de_valor():
    tema = {"tema": "t", "valores": [
        {"concepto": "tarifa", "modalidad": "fijo", "monto": 3000, "unidad": "ars"},
        {"concepto": "desc", "modalidad": "fijo", "monto": 10, "unidad": "porcentaje"},
        {"concepto": "cuo", "modalidad": "fijo", "monto": 6, "unidad": "cuotas"},
        {"concepto": "rango", "modalidad": "rango", "monto_min": 5000, "monto_max": 12000},
        {"concepto": "gratis", "modalidad": "fijo", "monto": 0, "umbral_ars": 250000},
    ]}
    out = C.estampar_valores(
        "{{tarifa}} | {{desc}} | {{cuo}} | {{rango}} | {{gratis}}", tema)
    assert out == "$3.000 | 10% | 6 | entre $5.000 y $12.000 | $250.000"


# ── 2. Comportamiento del atajo ──────────────────────────────────────────────

def _interp(intencion="pregunta_especifica", **kw):
    return {"intencion": intencion, "confianza": 0.9, **kw}


def test_pregunta_pura_de_envio_sirve_la_curada(firestore_doble):
    r = C.servir_curada("cuanto sale el envio?", _interp(), {},
                        pregunta_cierre_previa=False, tienda_id="verifika_prod")
    assert r is not None
    tema, texto = r
    assert tema == "costo_envio"
    assert "$3.000" in texto and "$250.000" in texto
    assert "{{" not in texto


def test_descuento_sirve_con_porcentaje_real(firestore_doble):
    r = C.servir_curada("hay descuento por transferencia?", _interp(), {},
                        pregunta_cierre_previa=False, tienda_id="verifika_prod")
    assert r is not None and "10%" in r[1]


def test_con_carrito_no_ataja(firestore_doble):
    r = C.servir_curada("cuanto sale el envio?", _interp(),
                        {"carrito": [{"id": "X", "cantidad": 1}]},
                        pregunta_cierre_previa=False, tienda_id="verifika_prod")
    assert r is None


def test_con_producto_resuelto_no_ataja(firestore_doble):
    r = C.servir_curada("cuanto sale el envio del teclado?",
                        _interp(producto_resuelto="TEC0010"), {},
                        pregunta_cierre_previa=False, tienda_id="verifika_prod")
    assert r is None


def test_con_cierre_pendiente_no_ataja(firestore_doble):
    r = C.servir_curada("cuanto sale el envio?", _interp(), {},
                        pregunta_cierre_previa=True, tienda_id="verifika_prod")
    assert r is None


def test_intencion_de_compra_no_ataja(firestore_doble):
    r = C.servir_curada("dale lo quiero, cuanto el envio?",
                        _interp("decision_compra"), {},
                        pregunta_cierre_previa=False, tienda_id="verifika_prod")
    assert r is None


def test_interp_caido_no_ataja(firestore_doble):
    r = C.servir_curada("cuanto sale el envio?", {}, {},
                        pregunta_cierre_previa=False, tienda_id="verifika_prod")
    assert r is None


def test_tema_sin_curada_no_ataja(firestore_doble, monkeypatch):
    # Un tema SIN respuesta_curada va al camino normal. Desde el 4-jul los 44
    # temas reales estan curados, asi que el caso se arma con una FAQ sintetica.
    import app.storage.firestore_client as fc
    sin_curada = {"horarios": {"tema": "horarios",
                               "keywords": ["horarios", "horario"],
                               "respuesta": "de 9 a 18", "tipo": "informativo",
                               "valores": []}}
    monkeypatch.setattr(fc, "get_all_faq", lambda tienda_id=None: sin_curada)
    r = C.servir_curada("que horarios tienen?", _interp(), {},
                        pregunta_cierre_previa=False, tienda_id="verifika_prod")
    assert r is None


def test_fallback_bloqueado_sirve_la_curada_si_hay(firestore_doble):
    # Caso seña (banco 8-jul): la respuesta del solver se bloqueo (ofrecio un
    # producto sin stock) y salio el enlatado generico, comiendose la pregunta
    # de POLITICA. Si el ruteo matchea un tema curado, sale esa respuesta.
    from app.core.interprete_libre import _fallback_o_curada
    interp = {"intencion": "pregunta_especifica", "confianza": 0.8,
              "producto_resuelto": None, "candidatos": []}
    out = _fallback_o_curada("como es la seña para reservar?", interp,
                             "verifika_prod")
    from app.config import get_settings
    assert out != get_settings().VERIFIKA_FALLBACK_MESSAGE
    assert "reserv" in out.lower() or "seña" in out.lower()


def test_fallback_sin_tema_curado_cae_al_enlatado(firestore_doble):
    from app.core.interprete_libre import _fallback_o_curada
    from app.config import get_settings
    interp = {"intencion": "decision_compra", "confianza": 0.9}
    out = _fallback_o_curada("dale lo llevo", interp, "verifika_prod")
    assert out == get_settings().VERIFIKA_FALLBACK_MESSAGE
