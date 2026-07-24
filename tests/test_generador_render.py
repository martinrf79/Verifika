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


# ── fragmento ficha que CONTESTA (guion 39, 19-jul) ──────────────────────────

def test_descripcion_no_se_corta_a_mitad_de_palabra():
    """El corte cierra en oración completa: nunca más 'Uso rec'."""
    from app.core.generador_v2 import _texto_ficha_limpio
    desc = ("Notebook HP 245 G9 Core i5 16GB 512GB SSD, color Gris. "
            "peso 1500g. dimensiones 39.1x25.1x1.9 cm. Carcasa de Aluminio. "
            "Garantia oficial 12 meses. Uso recomendado: Trabajo y estudio.")
    out = _texto_ficha_limpio(desc, tope=200)
    assert not out.endswith("rec")
    assert out.endswith(".") or out.endswith("…")


def test_descripcion_duplicada_del_csv_se_depura():
    from app.core.generador_v2 import _texto_ficha_limpio
    out = _texto_ficha_limpio(
        "Core i5 16GB 512GB SSD, Core i5 16GB 512GB SSD. peso 1500g.")
    assert out.count("Core i5 16GB 512GB SSD") == 1


def test_spec_preguntada_ausente_sale_el_honesto():
    """Hz y Thunderbolt preguntados, la ficha no los trae -> honesto."""
    from app.core.generador_v2 import _honesto_specs_faltantes
    prod = {"nombre": "Notebook HP 245 G9",
            "descripcion": "Core i5 16GB 512GB SSD. peso 1500g.",
            "garantia_detalle": "12 meses", "origen": "China"}
    hon = _honesto_specs_faltantes(
        "¿Y la pantalla de cuántos Hz es? ¿Viene con puerto Thunderbolt?",
        prod)
    assert "no lo especifica" in hon
    assert "hercios" in hon and "Thunderbolt" in hon


def test_spec_presente_en_ficha_no_dispara_honesto():
    from app.core.generador_v2 import _honesto_specs_faltantes
    prod = {"nombre": "Monitor Samsung", "descripcion": "Pantalla de 75 Hz."}
    assert _honesto_specs_faltantes("¿de cuántos Hz es?", prod) == ""


def test_sin_pregunta_de_spec_no_hay_honesto():
    from app.core.generador_v2 import _honesto_specs_faltantes
    prod = {"nombre": "Mouse Genius", "descripcion": "Mouse USB."}
    assert _honesto_specs_faltantes("¿cuánto sale el mouse?", prod) == ""
