"""
AREA: MEMORIA REFERENCIAL BORROSA (paso 3) — "el que te dije, no me acuerdo cuál".

Lockea app/core/memoria_ref: qué frases cuentan como referencia borrosa a un
producto anterior, y qué guía arma el código según la memoria (un visto -> lo
ancla; varios -> manda preguntar; ninguno -> manda no inventar). Es guía previa
al solver, el código dueño de la memoria. Lógica pura, sin LLM ni Firestore.
"""
from app.core.memoria_ref import es_referencia_memoria, guia_memoria


# ── DETECCION DE LA REFERENCIA ──────────────────────────────────────────

def test_detecta_referencias_borrosas():
    for m in ["el que te dije antes", "no me acuerdo cuál era",
              "el que vimos hoy", "el que me mostraste", "el de antes",
              "el anterior me servía", "dame el primero"]:
        assert es_referencia_memoria(m), m


def test_no_dispara_en_mensaje_normal():
    for m in ["quiero un mouse gamer", "cuánto sale el teclado Kumara",
              "hola, buenas", "me lo llevo, cómo pago"]:
        assert not es_referencia_memoria(m), m


# ── GUIA SEGUN LA MEMORIA ───────────────────────────────────────────────

def test_un_solo_visto_se_ancla():
    vistos = [{"id": "MOU0011", "nombre": "Mouse Genius DX-110 Negro", "precio": 8000}]
    g = guia_memoria("el que te dije antes", vistos)
    assert "[[PROD:MOU0011]]" in g
    assert "Mouse Genius DX-110 Negro" in g


def test_varios_vistos_manda_preguntar():
    vistos = [
        {"id": "MOU0011", "nombre": "Mouse Genius DX-110 Negro", "precio": 8000},
        {"id": "TEC0020", "nombre": "Teclado Redragon Kumara", "precio": 45000},
    ]
    g = guia_memoria("no me acuerdo cuál era", vistos)
    assert "cuál" in g.lower()
    assert "Mouse Genius DX-110 Negro" in g and "Teclado Redragon Kumara" in g
    # No se ancla ningun id: hay que preguntar, no elegir.
    assert "[[PROD:" not in g


def test_sin_memoria_manda_no_inventar():
    g = guia_memoria("el que te dije antes", [])
    assert "no inventes" in g.lower() or "no te quedó registrado" in g.lower()
    assert "[[PROD:" not in g


def test_mensaje_normal_no_arma_guia():
    vistos = [{"id": "MOU0011", "nombre": "Mouse Genius DX-110 Negro"}]
    assert guia_memoria("quiero un teclado nuevo", vistos) == ""


def test_vistos_sin_id_no_rompe():
    vistos = [{"nombre": "sin id"}, {"id": "", "nombre": "vacio"}]
    g = guia_memoria("el que te dije", vistos)
    # Ninguno valido -> cae al caso 'sin memoria'.
    assert "[[PROD:" not in g
