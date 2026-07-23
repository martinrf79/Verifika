"""
AREA: filtro determinista anti-duplicado (app/core/dedup.py), refuerzo final del
flujo de mensaje. Saca duplicados EXACTOS y contiguos sin tocar lo legitimo.
"""
from app.core.dedup import deduplicar_respuesta as D


def test_respuesta_entera_repetida_en_dos_mitades():
    cuerpo = ("Hola, te ayudo.\n\nPresupuesto:\n- 1x Mouse: $8.500\nTotal: $8.500"
              "\n\n¿Lo dejamos confirmado?")
    doble = cuerpo + "\n\n" + cuerpo
    assert D(doble) == cuerpo


def test_bloque_contiguo_identico_se_saca():
    t = "Intro.\n\nPresupuesto:\nTotal: $100\n\nPresupuesto:\nTotal: $100\n\nCierre."
    r = D(t)
    assert r.count("Total: $100") == 1
    assert "Intro." in r and "Cierre." in r


def test_lineas_contiguas_identicas_se_sacan():
    t = "Para pagar por transferencia:\nCBU: 000\nCBU: 000\nAlias: demo"
    r = D(t)
    assert r.count("CBU: 000") == 1
    assert "Alias: demo" in r


def test_bloque_sustancial_repetido_no_contiguo_se_saca():
    """El presupuesto que el solver mostro y el cierre repite en su 'Resumen'
    (no contiguo) queda una sola vez. Caso real del modo lead por el flujo atado."""
    t = ("¡Excelente!\n\nPresupuesto:\n- 2x Mouse: $17.000\nTotal: $17.000\n\n"
         "¿Lo dejamos confirmado así?\n\nListo, tomamos tu pedido.\nResumen:\n\n"
         "Presupuesto:\n- 2x Mouse: $17.000\nTotal: $17.000\n\nEl equipo te contacta.")
    r = D(t)
    assert r.count("Presupuesto:") == 1
    assert "Listo, tomamos tu pedido." in r


def test_coletilla_corta_repetida_no_contigua_se_conserva():
    """Un bloque CORTO puede repetirse legitimo (no es sustancial): solo se dedup
    si es contiguo, no a distancia."""
    t = "¿Seguimos?\n\nMouse A - $12.000\n\n¿Seguimos?"
    assert D(t).count("¿Seguimos?") == 2


def test_no_toca_lista_legitima_mismo_precio():
    # dos productos al mismo precio son lineas DISTINTAS: no se tocan.
    t = ("De mouse tengo:\n- Mouse Logitech M170 Negro - $12.000\n"
         "- Mouse Logitech M170 Blanco - $12.000")
    assert D(t) == t


def test_no_toca_respuesta_normal():
    t = ("¡Hola! Te ayudo a elegir.\n\nPresupuesto:\n- 1x Mouse: $8.500\n"
         "Total: $8.500\n\n¿Seguimos con alguno?")
    assert D(t) == t


def test_idempotente():
    cuerpo = "Bloque A.\n\nBloque B."
    doble = cuerpo + "\n\n" + cuerpo
    una = D(doble)
    assert D(una) == una == cuerpo


def test_vacio_y_none_no_rompen():
    assert D("") == ""
    assert D(None) == ""
