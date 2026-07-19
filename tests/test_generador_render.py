"""
AREA: Guardias del render del generador — destino fantasma y anti-robot.

Nacieron de la corrida viva del 19-jul (evidencia en banco_pruebas/corridas/):
el modelo invento un destino en un fragmento calculo y el turno 1 cobro $9.000
de envio a una provincia que el cliente jamas nombro; y la coletilla de cierre
salio identica en todos los turnos de todos los guiones.
"""


# ── destino fantasma en el fragmento calculo ─────────────────────────────────

def test_destino_inventado_por_el_modelo_no_vale():
    """Un destino que no esta ni en el mensaje ni en la memoria se cae."""
    from app.core.generador_v2 import _destino_respaldado
    assert not _destino_respaldado(
        "santiago del estero", "hola, quiero dos mouse genius dx-110 negro",
        {})


def test_destino_dicho_en_el_mensaje_actual_vale():
    from app.core.generador_v2 import _destino_respaldado
    assert _destino_respaldado(
        "cordoba capital", "uno va a Córdoba capital y el otro a Mendoza",
        {})


def test_destino_de_la_memoria_de_la_charla_vale():
    """El cliente lo dijo en un turno ANTERIOR: esta en localidades_envio y
    el modelo puede repetirlo para el total ('y el total de todo?')."""
    from app.core.generador_v2 import _destino_respaldado
    estado = {"localidades_envio": ["cordoba capital", "mendoza capital"]}
    assert _destino_respaldado("Mendoza Capital", "y el total de todo?",
                               estado)


def test_destino_respaldado_por_provincia_sticky():
    from app.core.generador_v2 import _destino_respaldado
    assert _destino_respaldado("cordoba", "y el total?",
                               {"provincia_envio": "Cordoba"})


def test_destino_vacio_no_vale():
    from app.core.generador_v2 import _destino_respaldado
    assert not _destino_respaldado("", "a cordoba", {})


# ── coletilla de cierre suave: rotacion anti-robot ───────────────────────────

def test_cierre_suave_es_determinista():
    """Misma charla, misma salida: nada de random."""
    from app.core.generador_v2 import _cierre_suave
    partes = ["Tengo estos mouse:", "- lista"]
    assert _cierre_suave(partes) == _cierre_suave(list(partes))


def test_cierre_suave_varia_entre_turnos_distintos():
    """Contenidos distintos rotan la coletilla: en una charla real de varios
    turnos no sale siempre la misma frase (robotico, corrida 19-jul)."""
    from app.core.generador_v2 import _cierre_suave
    salidas = {_cierre_suave([f"contenido del turno {i} con mas texto"])
               for i in range(12)}
    assert len(salidas) >= 2


def test_cierres_suaves_sin_digitos_ni_duplicados():
    """Invariante del corpus enlatado: cero numeros, todas distintas."""
    import re
    from app.core.generador_v2 import _CIERRES_SUAVES
    assert len(set(_CIERRES_SUAVES)) == len(_CIERRES_SUAVES)
    for c in _CIERRES_SUAVES:
        assert not re.search(r"\d", c)
