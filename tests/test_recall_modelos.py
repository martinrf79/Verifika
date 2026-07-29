"""
Tests del RECALL de modelos (`app/core/recall_modelos.py`), la etapa 1 del
interprete: que modelos pueden entrar al enum de `producto_resuelto`.

Lo que se prueba no es "devuelve algo", es lo que rompia en produccion: que el
cliente pueda nombrar un producto con SUS palabras y no con la etiqueta del
catalogo. El numero grande sobre los 482 modelos lo da
`banco_pruebas/banco_recall_modelos.py`; aca quedan clavados los casos que
explican POR QUE el numero es ese.
"""
import pytest

from app.core import recall_modelos as rm


# ── tokenizador ────────────────────────────────────────────────────────────
def test_tokens_conserva_letras_sueltas_y_numeros():
    """'G Pro X' e 'IdeaPad 3' se distinguen justo por lo que el tokenizador
    viejo tiraba: la letra suelta y el digito."""
    t = rm.tokens("Auriculares Logitech G Pro X")
    assert {"g", "pro", "x"} <= t
    assert "3" in rm.tokens("Lenovo IdeaPad 3")


def test_tokens_saca_palabras_de_funcion_y_no_datos():
    t = rm.tokens("tenes el mouse gamer para la compu?")
    assert "el" not in t and "para" not in t and "la" not in t
    # 'mouse' y 'gamer' SI quedan: no son palabras de funcion, son dato. Que
    # pesen poco lo decide el idf con el catalogo, no una lista fija.
    assert {"mouse", "gamer"} <= t


# ── indice ─────────────────────────────────────────────────────────────────
def _catalogo():
    return [
        {"marca": "Redragon", "modelo": "Kumara K552", "categoria": "teclado",
         "nombre": "Teclado Mecanico Redragon Kumara K552 RGB",
         "tags": "teclado, mecanico, rgb, switch azul", "descripcion": "USB"},
        {"marca": "Logitech", "modelo": "G203 Lightsync", "categoria": "mouse",
         "nombre": "Mouse Logitech G203 Lightsync Negro",
         "tags": "mouse, mause, raton, puntero, optico", "descripcion": "USB"},
        {"marca": "Genius", "modelo": "DX-110", "categoria": "mouse",
         "nombre": "Mouse Genius DX-110 Negro",
         "tags": "mouse, mause, raton, economico", "descripcion": "USB"},
    ]


def _modelos():
    return [rm.etiqueta_modelo(p) for p in _catalogo()]


def _idx(monkeypatch):
    """Instala el catalogo de arriba como si viniera de Firestore."""
    import app.storage.firestore_client as fc
    monkeypatch.setattr(fc, "get_all_products",
                        lambda **kw: _catalogo(), raising=False)
    rm.invalidar()
    return rm.indice("t_test")


def test_indice_agrupa_por_modelo_no_por_producto(monkeypatch):
    idx = _idx(monkeypatch)
    assert set(idx) == {"redragon kumara k552", "logitech g203 lightsync",
                        "genius dx-110"}


def test_token_en_todos_los_modelos_no_distingue(monkeypatch):
    """'usb' esta en los tres: su peso tiene que quedar casi en cero. Sin este
    descuento, mirar la descripcion mete mas ruido que senal."""
    idx = _idx(monkeypatch)
    pesos = idx["logitech g203 lightsync"]
    assert pesos["usb"] < 0.1 * pesos["g203"]


# ── recall: el caso que rompia ─────────────────────────────────────────────
def test_encuentra_por_tags_sin_compartir_palabra_con_la_etiqueta(monkeypatch):
    """LA falla: la etiqueta es 'Redragon Kumara K552' y el cliente escribe
    'teclado mecanico rgb'. Cero palabras en comun; el recall viejo devolvia
    lista vacia y el interprete no lo podia nombrar."""
    _idx(monkeypatch)
    r = rm.candidatos("me interesa el teclado mecanico rgb", _modelos(),
                      tienda_id="t_test")
    assert r and r[0] == "Redragon Kumara K552"


def test_sinonimo_cargado_por_la_tienda(monkeypatch):
    """'mause' y 'raton' viven en los tags del catalogo. Estaban cargados en
    Firestore desde el 27-jul y nadie los consultaba."""
    _idx(monkeypatch)
    for palabra in ("mause", "raton", "puntero"):
        r = rm.candidatos(f"busco un {palabra} optico", _modelos(),
                          tienda_id="t_test")
        assert "Logitech G203 Lightsync" in r, palabra


def test_typo_queda_ARRIBA_no_al_fondo(monkeypatch):
    """El recall viejo encontraba el typo y a la vez lo escondia: entraba con
    puntaje fijo, detras de todos los que habian pegado por una palabra floja.
    Corrigiendo el TOKEN, el corregido puntua por lo que vale."""
    _idx(monkeypatch)
    r = rm.candidatos("cuanto sale el kumzra k552", _modelos(),
                      tienda_id="t_test")
    assert r[0] == "Redragon Kumara K552"


def test_el_exacto_le_gana_al_corregido(monkeypatch):
    _idx(monkeypatch)
    r = rm.candidatos("quiero el genius dx-110", _modelos(), tienda_id="t_test")
    assert r[0] == "Genius DX-110"


# ── contratos que no se pueden romper ──────────────────────────────────────
def test_nunca_devuelve_algo_fuera_del_vocabulario_autorizado(monkeypatch):
    """Lo que sale de aca va al enum del schema. Un modelo que no este en la
    lista autorizada haria fallar la generacion estructurada."""
    _idx(monkeypatch)
    autorizados = ["Logitech G203 Lightsync"]
    r = rm.candidatos("teclado mecanico rgb mouse raton", autorizados,
                      tienda_id="t_test")
    assert set(r) <= set(autorizados)


def test_sin_catalogo_cae_al_recall_por_etiqueta(monkeypatch):
    """Tests puros y arranque en frio: sin indice abajo, el recall sigue
    funcionando por la etiqueta. Degrada, no se rompe."""
    import app.storage.firestore_client as fc
    monkeypatch.setattr(fc, "get_all_products", lambda **kw: [], raising=False)
    rm.invalidar()
    r = rm.candidatos("la zenbook 14 cuanto sale",
                      ["Asus Zenbook 14", "Genius DX-110"], tienda_id="t_vacio")
    assert r == ["Asus Zenbook 14"]


def test_mensaje_sin_palabras_utiles_no_inventa(monkeypatch):
    _idx(monkeypatch)
    assert rm.candidatos("hola, gracias", _modelos(), tienda_id="t_test") == []
    assert rm.candidatos("teclado", [], tienda_id="t_test") == []


def test_tope_respetado(monkeypatch):
    _idx(monkeypatch)
    r = rm.candidatos("mouse teclado usb", _modelos(), tope=2,
                      tienda_id="t_test")
    assert len(r) <= 2


def test_mira_el_contexto_de_la_charla(monkeypatch):
    """La repregunta no repite el nombre: 'y esa cuanto pesa?'. El producto
    tiene que venir del contexto."""
    _idx(monkeypatch)
    r = rm.candidatos("y esa cuanto pesa?", _modelos(),
                      contexto="Cliente: tenes el kumara k552?",
                      tienda_id="t_test")
    assert r and r[0] == "Redragon Kumara K552"


# ── sobre el catalogo REAL, con el doble de Firestore ──────────────────────
def test_el_numero_del_banco_no_baja(firestore_doble, capsys):
    """El banco de recall corre EN la bateria, no solo a mano. Asi una mejora
    de otro dia que empeore el recall se cae en el CI y no en una charla real.
    El piso vive en el banco (PISO); aca solo se exige que corra y pase."""
    from banco_pruebas import banco_recall_modelos as banco
    rm.invalidar()
    assert banco.main() == 0, capsys.readouterr().out[-2000:]


def test_catalogo_real_variantes_de_un_modelo_son_un_solo_documento(
        firestore_doble):
    """La Zenbook 14 tiene nueve variantes entre CPU y color. El indice las
    junta en UN modelo: lo que dice cualquiera sirve para encontrarlo."""
    rm.invalidar()
    idx = rm.indice("verifika_prod")
    assert 400 < len(idx) < 600, len(idx)
    from app.core.interpretador import modelos_del_catalogo
    modelos = modelos_del_catalogo("verifika_prod")
    r = rm.candidatos("la zenbok 14 cuanto sale", modelos,
                      tienda_id="verifika_prod")
    assert any("zenbook" in m.lower() for m in r)
