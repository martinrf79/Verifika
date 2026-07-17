"""
AREA: Preferencias del cliente en el idioma del interprete (16-jul).

El cliente dice de mil formas la misma cosa; el interprete la normaliza a tres
campos nuevos (tope_presupuesto, exclusiones por origen/marca, uso_previsto) y
esos campos VIAJAN: sticky en el estado entre turnos, y al generador que filtra
el universo POR CONSTRUCCION (lo excluido ni entra al enum). Estos tests lockean
la logica pura: coercion, merge sticky y filtro del universo. La lectura del
LLM se mide en el banco de parafrasis (vivo).
"""
from app.core.interpretador import coercionar_preferencias, _schema_interprete
from app.core.estado_venta import construir_estado, preferencias_actualizadas
from app.core.generador_v2 import filtrar_por_preferencias, _pais_de_marca


# ── Coercion defensiva del interprete ────────────────────────────────────────

def test_coercion_tope_valido_y_basura():
    r = {"tope_presupuesto": "50000", "exclusiones": None, "uso_previsto": " gaming "}
    coercionar_preferencias(r)
    assert r["tope_presupuesto"] == 50000
    assert r["exclusiones"] == []
    assert r["uso_previsto"] == "gaming"
    r2 = {"tope_presupuesto": "mucho", "exclusiones": "china", "uso_previsto": ""}
    coercionar_preferencias(r2)
    assert r2["tope_presupuesto"] is None
    assert r2["exclusiones"] == []
    assert r2["uso_previsto"] is None


def test_coercion_exclusiones_filtra_invalidas():
    r = {"exclusiones": [
        {"tipo": "origen", "valor": "china"},
        {"tipo": "color", "valor": "rojo"},      # tipo invalido
        {"tipo": "marca", "valor": "  "},         # valor vacio
        "suelto",                                  # no dict
    ]}
    coercionar_preferencias(r)
    assert r["exclusiones"] == [{"tipo": "origen", "valor": "china"}]


def test_schema_incluye_preferencias():
    s = _schema_interprete([])
    assert "tope_presupuesto" in s["properties"]
    assert "exclusiones" in s["properties"]
    assert "uso_previsto" in s["properties"]
    assert set(s["required"]) == set(s["properties"])
    tipos = s["properties"]["exclusiones"]["items"]["properties"]["tipo"]["enum"]
    assert tipos == ["origen", "marca"]


# ── Merge sticky en el estado ────────────────────────────────────────────────

def test_preferencias_acumulan_y_pisan():
    previas = {"exclusiones": [{"tipo": "origen", "valor": "china"}],
               "tope_presupuesto": 80000}
    interp = {"exclusiones": [{"tipo": "marca", "valor": "Redragon"}],
              "tope_presupuesto": 50000, "uso_previsto": "oficina"}
    prefs = preferencias_actualizadas(previas, interp)
    assert {"tipo": "origen", "valor": "china"} in prefs["exclusiones"]
    assert {"tipo": "marca", "valor": "Redragon"} in prefs["exclusiones"]
    assert prefs["tope_presupuesto"] == 50000
    assert prefs["uso_previsto"] == "oficina"


def test_preferencias_dedup_y_sin_novedad():
    previas = {"exclusiones": [{"tipo": "origen", "valor": "china"}]}
    interp = {"exclusiones": [{"tipo": "origen", "valor": "China"}]}
    prefs = preferencias_actualizadas(previas, interp)
    assert len(prefs["exclusiones"]) == 1
    # Sin interp nuevo, lo previo persiste igual (sticky).
    assert preferencias_actualizadas(previas, {})["exclusiones"] == \
        previas["exclusiones"]


def test_preferencias_se_limpian_con_frase():
    previas = {"exclusiones": [{"tipo": "marca", "valor": "Redragon"}],
               "uso_previsto": "gaming"}
    prefs = preferencias_actualizadas(previas, {}, "ya no importa la marca, cualquiera va")
    assert "exclusiones" not in prefs
    assert prefs["uso_previsto"] == "gaming"


def test_estado_levanta_preferencias():
    estado = construir_estado(
        {"preferencias_cliente": {"tope_presupuesto": 60000}}, None)
    assert estado["preferencias"] == {"tope_presupuesto": 60000}
    assert construir_estado({}, None)["preferencias"] == {}


# ── Filtro del universo por construccion ─────────────────────────────────────

_UNIVERSO = [
    {"id": "MOU0001", "nombre": "Mouse Logitech", "precio_ars": 37500,
     "marca": "Logitech", "origen": "Marca Logitech de Suiza. Fabricado en China."},
    {"id": "MOU0002", "nombre": "Mouse Redragon", "precio_ars": 8500,
     "marca": "Redragon", "origen": "Marca Redragon de China. Fabricado en China."},
    {"id": "TEC0001", "nombre": "Teclado Genius", "precio_ars": 12000,
     "marca": "Genius", "origen": "Marca Genius de Taiwan. Fabricado en China."},
]


def test_pais_de_marca():
    assert _pais_de_marca(_UNIVERSO[0]) == "suiza"
    assert _pais_de_marca(_UNIVERSO[1]) == "china"
    assert _pais_de_marca({"origen": ""}) == ""


def test_filtro_excluye_marca_china_no_fabricacion():
    """'Sin marcas chinas' saca la marca china, NO todo lo fabricado en China
    (casi todo se fabrica ahi; el cliente habla de la marca)."""
    prefs = {"exclusiones": [{"tipo": "origen", "valor": "chinas"}]}
    ids = [p["id"] for p in filtrar_por_preferencias(_UNIVERSO, prefs)]
    assert ids == ["MOU0001", "TEC0001"]


def test_filtro_excluye_por_marca_nombrada():
    prefs = {"exclusiones": [{"tipo": "marca", "valor": "redragon"}]}
    ids = [p["id"] for p in filtrar_por_preferencias(_UNIVERSO, prefs)]
    assert "MOU0002" not in ids and len(ids) == 2


def test_filtro_por_tope_presupuesto():
    prefs = {"tope_presupuesto": 15000}
    ids = [p["id"] for p in filtrar_por_preferencias(_UNIVERSO, prefs)]
    assert ids == ["MOU0002", "TEC0001"]


def test_filtro_nunca_vacia_el_universo():
    """Si el filtro dejara cero productos, vuelve el universo entero: el modelo
    explica honesto (las preferencias van en el prompt) en vez de quedarse mudo."""
    prefs = {"tope_presupuesto": 100}
    assert filtrar_por_preferencias(_UNIVERSO, prefs) == _UNIVERSO


def test_sin_preferencias_no_toca():
    assert filtrar_por_preferencias(_UNIVERSO, {}) == _UNIVERSO
    assert filtrar_por_preferencias(_UNIVERSO, None) == _UNIVERSO


# ── Valvula del criterio: razonar sin bloque jurado ──────────────────────────

def test_criterio_sin_bloque_igual_sale(firestore_doble):
    """Pregunta nueva sin bloque jurado que aplique: la frase razonada del
    modelo SALE igual (sin cita, poda de digitos intacta) en vez de dejar al
    cliente sin respuesta. Es la valvula anti-robot; el warning en el log es el
    radar de huecos del corpus."""
    from app.core.generador_v2 import renderizar
    frags = [{"tipo": "criterio", "criterio_id": None,
              "texto": "El Logitech es marca suiza, te va a durar y tiene "
                       "buen soporte en Argentina."}]
    texto, tools = renderizar(frags, _UNIVERSO, {}, "verifika_prod")
    assert "marca suiza" in texto
    assert not any(t["name"] == "consultar_guia_venta" for t in tools)


def test_criterio_con_bloque_cita_como_siempre(firestore_doble):
    """Con id jurado real la cita sigue saliendo como evidencia verificable."""
    from app.core.generador_v2 import renderizar
    from app.core.guia_venta_prosa import GUIA_VENTA
    cid = next(iter(GUIA_VENTA))
    frags = [{"tipo": "criterio", "criterio_id": cid,
              "texto": "Para lo que buscas te conviene ese, va muy bien."}]
    texto, tools = renderizar(frags, _UNIVERSO, {}, "verifika_prod")
    assert "te conviene" in texto
    citas = [t for t in tools if t["name"] == "consultar_guia_venta"]
    assert citas and citas[0]["result"]["id"] == cid


def test_criterio_con_digitos_se_poda(firestore_doble):
    """La valvula NO afloja la poda: un criterio con numeros no sale."""
    from app.core.generador_v2 import renderizar
    frags = [{"tipo": "criterio", "criterio_id": None,
              "texto": "Sale 9999 pesos y es lo mejor."}]
    texto, _ = renderizar(frags, _UNIVERSO, {}, "verifika_prod")
    assert "9999" not in texto
