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


def test_dos_preguntas_distintas_no_ataja(firestore_doble):
    # Caso real 5-jul: el cliente encaja retiro + ubicacion + cuotas en un
    # mensaje. El atajo servia SOLO las cuotas (tema top del ranking) y el
    # solver ni corria, asi que el retiro quedaba mudo. Ahora cae al camino
    # normal (None) para que el solver conteste TODO.
    r = C.servir_curada(
        "puedo retirar por el local? donde estan? y en cuantas cuotas?",
        _interp(), {}, pregunta_cierre_previa=False, tienda_id="verifika_prod")
    assert r is None


def test_dos_topicos_en_una_pregunta_no_ataja(firestore_doble):
    # Hueco del conteo de preguntas: dos TOPICOS distintos unidos por "y" en una
    # sola oracion interrogativa (envio + cuotas). Un signo de pregunta pero dos
    # temas de FAQ disjuntos: tampoco se ataja, o el segundo quedaria mudo.
    r = C.servir_curada("cuanto sale el envio y en cuantas cuotas?", _interp(),
                        {}, pregunta_cierre_previa=False, tienda_id="verifika_prod")
    assert r is None


def test_dos_topicos_sin_signos_no_ataja(firestore_doble):
    # Ni siquiera con signos de pregunta: "retiro en local y cuotas" toca dos
    # topicos distintos, el atajo cae al solver igual.
    r = C.servir_curada("retiro en el local y cuotas sin interes", _interp(),
                        {}, pregunta_cierre_previa=False, tienda_id="verifika_prod")
    assert r is None


def test_una_pregunta_de_un_tema_con_temas_relacionados_si_ataja(firestore_doble):
    # Guarda contra sobre-disparo: "cuanto sale el envio?" matchea costo_envio
    # y envios, pero con scores DISTINTOS (no empatan) y una sola pregunta, asi
    # que el atajo sigue vivo. La mejora no debe matar el camino barato legitimo.
    r = C.servir_curada("cuanto sale el envio?", _interp(), {},
                        pregunta_cierre_previa=False, tienda_id="verifika_prod")
    assert r is not None and r[0] == "costo_envio"


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
