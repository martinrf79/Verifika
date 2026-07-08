"""
AREA: Guía de venta — convierte la decisión del router en la instrucción de la
MOVIDA que se inyecta al solver. Cubre app/core/guia_venta.py. Lógica pura.

La guía es instruccional (el brief de la movida), no trae números: el dato duro
sigue sellado por tools/estado/verificador. Conservador: "" en camino normal.
"""
from app.core.guia_venta import guia_venta


def _interp(**kw):
    base = {"intencion": "pregunta_especifica", "confianza": 0.9,
            "producto_resuelto": None, "candidatos": [], "ofrecer_opciones": []}
    base.update(kw)
    return base


def test_movida_descuento_inyecta_brief():
    g = guia_venta("me haces un precio?", _interp(), {})
    assert "[VENTA (B4):" in g
    assert "transferencia" in g.lower()
    assert "no los inventes" in g.lower()


def test_movida_objecion_precio():
    g = guia_venta("esta muy caro", _interp(), {})
    assert "[VENTA (B5):" in g


def test_preguntar_ambiguedad_no_da_precio():
    g = guia_venta("quiero el DX-110", _interp(candidatos=["DX-110 Negro", "DX-110 Blanco"]), {})
    assert "[VENTA (B7):" in g
    assert "preguntá" in g.lower() or "pregunta" in g.lower()


def test_confianza_baja_pregunta_no_afirma():
    # B4 con confianza baja se degrada a preguntar (no afirma la movida).
    g = guia_venta("me haces un precio?", _interp(confianza=0.4), {})
    assert "[VENTA (B4):" in g
    # no debe traer el brief de afirmar, sino el de aclarar
    assert "aclarar" in g.lower() or "una pregunta" in g.lower()


def test_movidas_nuevas_inyectan_brief():
    casos = {
        "quiero el DX-110 pero no el negro": "B3",
        "lo necesito para el viernes": "B13",
        "tienen precio por mayor?": "B14",
        "tengo $50.000, que me alcanza?": "B15",
        "es para regalar": "B16",
        "es una verguenza, nadie responde": "B17",
        "sos un bot?": "B18",
        "quiero cancelar el pedido": "B19",
        "aceptan cripto?": "B20",
        "hacen envios a uruguay?": "B21",
        "mandame fotos reales": "B22",
        "se me rompio el mouse": "B23",
    }
    for msg, cat in casos.items():
        g = guia_venta(msg, _interp(), {})
        assert f"[VENTA ({cat}):" in g, f"{msg} -> esperaba {cat}, dio: {g[:80]}"


def test_humano_dice_la_verdad_del_bot():
    g = guia_venta("sos un bot?", _interp(), {})
    assert "asistente autom" in g.lower()


def test_urgencia_prohibe_dia_puntual():
    g = guia_venta("lo necesito para manana", _interp(), {})
    assert "PROHIBIDO" in g and "día puntual" in g


def test_queja_no_vende():
    g = guia_venta("es una verguenza, nadie me responde", _interp(), {})
    assert "NO vendas" in g


def test_camino_normal_no_inyecta_nada():
    assert guia_venta("hola, tenes mouse?", _interp(), {}) == ""


def test_interp_none_no_rompe():
    assert guia_venta("cualquier cosa", None, None) == ""


def test_no_incluye_numeros_hardcodeados():
    # El brief nunca trae un monto: los datos duros salen sellados aparte.
    import re
    for msg in ["me haces un precio?", "esta caro", "es seguro?"]:
        g = guia_venta(msg, _interp(), {})
        assert not re.search(r"\$\s?\d", g), f"la guia trajo un monto: {msg}"
