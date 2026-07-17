"""
AREA: El fiscal de dos niveles sobre la mitad blanda (17-jul).

Nivel 2 (verificador_intencion): estructura contra estructura, sin LLM. La
respuesta se cruza con las preferencias leidas por el interprete: producto de
marca/origen excluido se poda quirurgico; todo arriba del tope se marca.

Nivel 3 (checker_afirmaciones): la parte DETERMINISTA del contrato. La llamada
al modelo chico se mide viva; aca se lockea lo que decide el CODIGO con el
veredicto: que se poda, que se respeta, y que la evidencia se arma de la
fuente.
"""
from app.core.verificador_intencion import (verificar_intencion,
                                            _producto_excluido,
                                            _quitar_lineas_con)
from app.core.checker_afirmaciones import (podar_sin_respaldo,
                                           evidencia_de_meta, _SCHEMA)


# ── Nivel 2: exclusiones y tope ──────────────────────────────────────────────

# TEC0015 es el Redragon Kumara REAL del catalogo: el fiscal enriquece la
# ficha desde la fuente. El segundo producto usa un id inexistente para
# ejercitar el fallback al dict crudo de la tool.
_META_REDRAGON = {"tools_called": [{
    "name": "get_product_details",
    "result": {"encontrado": True, "producto": {
        "id": "TEC0015", "nombre": "Teclado Redragon Kumara K552 Negro",
        "precio_ars": 55000}}}]}

_META_CRUDO = {"tools_called": [{
    "name": "get_product_details",
    "result": {"encontrado": True, "producto": {
        "id": "ZZZ9999", "nombre": "Teclado Redragon Fantasma",
        "precio_ars": 55000, "marca": "Redragon",
        "origen": "Marca Redragon de China. Fabricado en China."}}}]}


def test_producto_excluido_por_marca_y_origen():
    prod = {"marca": "Redragon",
            "origen": "Marca Redragon de China. Fabricado en China."}
    assert _producto_excluido(prod, [{"tipo": "marca", "valor": "redragon"}])
    assert _producto_excluido(prod, [{"tipo": "origen", "valor": "chinas"}])
    suizo = {"marca": "Logitech",
             "origen": "Marca Logitech de Suiza. Fabricado en China."}
    assert not _producto_excluido(suizo, [{"tipo": "origen", "valor": "china"}])


def test_quitar_lineas_con_nombre():
    texto = ("Te recomiendo estos:\n"
             "- Teclado Redragon Kumara K552 a $55.000\n"
             "- Teclado Genius KB-110 a $12.000")
    out = _quitar_lineas_con(texto, "Teclado Redragon Kumara K552")
    assert "Redragon" not in out and "Genius" in out


def test_fiscal_poda_excluido_si_queda_respuesta(firestore_doble):
    """La ficha se enriquece desde el CATALOGO real (TEC0015 es Redragon)."""
    prefs = {"exclusiones": [{"tipo": "marca", "valor": "redragon"}]}
    respuesta = ("Mira estas opciones:\n"
                 "- Teclado Redragon Kumara K552 Negro a $55.000\n"
                 "Tambien tengo otros teclados si queres.")
    out = verificar_intencion(respuesta, _META_REDRAGON, prefs, "verifika_prod")
    assert any(e["tipo"] == "exclusion_violada" for e in out["eventos"])
    assert "Redragon" not in out["respuesta"]
    assert "otros teclados" in out["respuesta"]


def test_fiscal_fallback_al_crudo_de_la_tool(firestore_doble):
    """Id que no resuelve en catalogo: la marca/origen sale del dict crudo que
    devolvio la tool (mismo dato que vio el cliente)."""
    prefs = {"exclusiones": [{"tipo": "origen", "valor": "china"}]}
    respuesta = ("- Teclado Redragon Fantasma a $55.000\n"
                 "Tambien tengo otras opciones.")
    out = verificar_intencion(respuesta, _META_CRUDO, prefs, "verifika_prod")
    assert any(e["tipo"] == "exclusion_violada" for e in out["eventos"])
    assert "Fantasma" not in out["respuesta"]


def test_fiscal_no_deja_turno_mudo(firestore_doble):
    """Si podar lo excluido vaciara la respuesta, se conserva y solo marca."""
    prefs = {"exclusiones": [{"tipo": "marca", "valor": "redragon"}]}
    respuesta = "Teclado Redragon Kumara K552 Negro a $55.000"
    out = verificar_intencion(respuesta, _META_REDRAGON, prefs, "verifika_prod")
    assert out["respuesta"] == respuesta
    assert any(e["tipo"] == "exclusion_violada" for e in out["eventos"])


def test_fiscal_marca_tope_superado(firestore_doble):
    prefs = {"tope_presupuesto": 20000}
    out = verificar_intencion("El Kumara sale $55.000.",
                              _META_REDRAGON, prefs, "verifika_prod")
    assert any(e["tipo"] == "tope_superado" for e in out["eventos"])
    # Marca, no corrige: el precio REAL del catalogo manda sobre el del banco.
    assert out["respuesta"] == "El Kumara sale $55.000."


def test_fiscal_sin_preferencias_es_noop():
    out = verificar_intencion("hola", _META_REDRAGON, {}, "verifika_prod")
    assert out == {"respuesta": "hola", "eventos": []}


# ── Nivel 3: la decision determinista sobre el veredicto ─────────────────────

def test_poda_afirmacion_sin_respaldo_verbatim():
    r = ("El Kumara es un teclado solido. Es sumergible y apto para agua. "
         "¿Te lo sumo al pedido?")
    texto, podadas = podar_sin_respaldo(r, ["Es sumergible y apto para agua."])
    assert "sumergible" not in texto
    assert "¿Te lo sumo al pedido?" in texto
    assert podadas == ["Es sumergible y apto para agua."]


def test_no_poda_frases_con_numeros_ni_no_verbatim():
    r = "El Kumara sale $55.000 y tiene switches azules."
    # Con digitos/$: territorio del verificador de plata, no se toca.
    texto, podadas = podar_sin_respaldo(r, ["El Kumara sale $55.000"])
    assert texto == r and not podadas
    # No verbatim: no se arriesga cirugia sobre texto que no matchea.
    texto, podadas = podar_sin_respaldo(r, ["tiene switches rojos"])
    assert texto == r and not podadas


def test_no_poda_si_queda_vacio():
    r = "Es resistente al agua."
    texto, podadas = podar_sin_respaldo(r, ["Es resistente al agua."])
    assert texto == r and not podadas


def test_evidencia_sale_de_la_fuente(firestore_doble):
    meta = {"tools_called": [
        {"name": "get_product_details",
         "result": {"producto": {"id": "MOU0001", "nombre": "x",
                                 "precio_ars": 1}}},
        {"name": "query_faq",
         "result": {"tema": "garantia", "respuesta": "La garantia es oficial."}},
        {"name": "consultar_guia_venta",
         "result": {"id": "mouse", "texto": "criterio jurado del mouse"}},
    ]}
    ev = evidencia_de_meta(meta, "verifika_prod")
    assert "FICHA" in ev and "FAQ garantia" in ev and "CRITERIO JURADO" in ev


def test_schema_del_checker_es_enum_cerrado():
    v = _SCHEMA["properties"]["afirmaciones"]["items"]["properties"]["veredicto"]
    assert v["enum"] == ["respaldada", "sin_respaldo", "neutral"]


# ── Nivel 3, ronda 2 (consigna): honestidad intocable y cirugia por oracion ──

def test_no_poda_la_honestidad():
    """'No vendemos celulares' es exactamente lo que queremos que diga: el
    checker la marque como la marque, la poda NO la toca."""
    r = ("Te soy sincero: celulares no vendemos. Cuota Simple no la "
         "trabajamos por ahora. ¿Te muestro tablets?")
    texto, podadas = podar_sin_respaldo(
        r, ["celulares no vendemos", "Cuota Simple no la trabajamos por ahora."])
    assert texto == r and not podadas


def test_poda_por_oracion_completa_sin_munones():
    """La afirmacion se saca como ORACION entera; un match parcial al medio de
    una frase no deja 'te cuento que , pero'."""
    r = ("El teclado es resistente al polvo y al agua. Viene con cable "
         "desmontable. ¿Lo sumo?")
    texto, podadas = podar_sin_respaldo(
        r, ["El teclado es resistente al polvo y al agua."])
    assert "resistente al polvo" not in texto
    assert "Viene con cable desmontable. ¿Lo sumo?" in texto.replace("\n", " ")
    # Fragmento que NO es oracion completa (match parcial): no se opera.
    r2 = "Te cuento que es liviano, pero robusto. ¿Seguimos?"
    texto2, podadas2 = podar_sin_respaldo(r2, ["es liviano"])
    assert texto2 == r2 and not podadas2


def test_saludo_inicial_recorta_bienvenida_doble():
    from app.core.interprete_libre import _con_saludo_inicial
    r = ("¡Hola! Bienvenido a Verifika Tech, soy tu asistente. Qué bueno que "
         "nos contactes, te ayudo enseguida a elegir ese mouse.\n\n"
         "Para gaming te recomiendo el M170.")
    out = _con_saludo_inicial(r, "Verifika")
    assert out.count("asistente") == 1  # solo la linea oficial
    assert "Bienvenido a Verifika Tech" not in out
    assert "M170" in out
    # Un cuerpo sin bienvenida redundante queda intacto.
    out2 = _con_saludo_inicial("Tengo el M170 a buen precio. ¿Te lo muestro?",
                               "Verifika")
    assert "Tengo el M170" in out2
