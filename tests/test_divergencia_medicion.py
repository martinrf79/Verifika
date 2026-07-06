"""
AREA: MEDICION de divergencia intérprete <-> solver (paso 1 del plan 6-jul).

Lockea el detector puro de app/core/divergencia.py: qué cuenta como divergencia
inequívoca en cada eje cerrado (producto, opciones A/B, estado) y qué NO. Es
MEDICION, no enforcement: no cambia respuestas, solo detecta para loguear y
dimensionar el problema en el banco antes de enforzar (pasos 2, 3, 4).

Distinto de tests/test_divergencia.py, que cubre la guarda A/B ya viva
(_forzar_pregunta_si_ambiguo). Sin LLM ni Firestore: string puro.
"""
from app.core.divergencia import detectar_divergencias


def _ejes(divs):
    return {d["eje"] for d in divs}


# ── EJE PRODUCTO ────────────────────────────────────────────────────────

def test_producto_alineado_no_diverge():
    interp = {"producto_resuelto": "Teclado Redragon Kumara"}
    resp = "Mira, el Teclado Redragon Kumara sale $45.000, buenisimo para gaming."
    assert detectar_divergencias(interp, resp, ids_mostrados=["TEC0020"]) == []


def test_producto_divergente_solver_mostro_otro():
    interp = {"producto_resuelto": "Teclado Redragon Kumara"}
    resp = "Te recomiendo el Mouse Logitech G203, sale $18.000."
    divs = detectar_divergencias(interp, resp, ids_mostrados=["MOU0011"])
    assert "producto" in _ejes(divs)


def test_producto_sin_mostrar_nada_no_diverge():
    # Prosa pura, el solver no mostro productos: no se acusa divergencia de
    # producto aunque no nombre el resuelto (puede ser pregunta de politica).
    interp = {"producto_resuelto": "Teclado Redragon Kumara"}
    resp = "Si, aceptamos transferencia y tarjeta. Con que te gustaria pagar?"
    assert detectar_divergencias(interp, resp, ids_mostrados=[]) == []


def test_producto_sin_resuelto_no_diverge():
    interp = {"producto_resuelto": None}
    resp = "Tenemos varios mouse, este sale $18.000."
    assert detectar_divergencias(interp, resp, ids_mostrados=["MOU0011"]) == []


# ── EJE OPCIONES A/B ────────────────────────────────────────────────────

def test_opciones_planteadas_no_diverge():
    interp = {"ofrecer_opciones": ["Teclado mecanico Kumara", "Teclado membrana K552"]}
    resp = "Tengo dos: el Kumara mecanico y el K552 membrana. Cual preferis?"
    assert "opciones" not in _ejes(detectar_divergencias(interp, resp))


def test_opciones_no_planteadas_diverge():
    interp = {"ofrecer_opciones": ["Teclado mecanico Kumara", "Teclado membrana K552"]}
    resp = "Te llevo el Kumara mecanico, es el mejor. Sale $45.000."
    assert "opciones" in _ejes(detectar_divergencias(interp, resp))


def test_opciones_pregunta_pero_no_nombra_ambas_diverge():
    interp = {"ofrecer_opciones": ["Teclado mecanico Kumara", "Teclado membrana K552"]}
    resp = "Queres el Kumara? Es una gran opcion."
    assert "opciones" in _ejes(detectar_divergencias(interp, resp))


# ── EJE ESTADO (embudo) ─────────────────────────────────────────────────

def test_estado_cierre_con_productos_diverge():
    interp = {"estado_conversacion": "esperando_datos"}
    resp = "Perfecto. Ah, y mira tambien el Mouse G203, sale $18.000."
    divs = detectar_divergencias(interp, resp, ids_mostrados=["MOU0011"])
    assert "estado" in _ejes(divs)


def test_estado_explorando_con_productos_no_diverge():
    interp = {"estado_conversacion": "explorando"}
    resp = "Tenemos el Mouse G203 a $18.000 y el G502 a $32.000."
    divs = detectar_divergencias(interp, resp, ids_mostrados=["MOU0011", "MOU0012"])
    assert "estado" not in _ejes(divs)


def test_estado_datos_sin_productos_no_diverge():
    interp = {"estado_conversacion": "esperando_datos"}
    resp = "Genial. Me pasas tu nombre y la direccion de envio para cerrar?"
    assert detectar_divergencias(interp, resp, ids_mostrados=[]) == []


# ── ROBUSTEZ ────────────────────────────────────────────────────────────

def test_interp_no_dict_no_rompe():
    assert detectar_divergencias(None, "cualquier cosa", ["X"]) == []


def test_respuesta_vacia_no_rompe():
    interp = {"producto_resuelto": "Mouse G203", "estado_conversacion": "explorando"}
    assert detectar_divergencias(interp, "", []) == []
