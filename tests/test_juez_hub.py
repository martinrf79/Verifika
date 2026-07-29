"""
AREA: EL JUEZ DE PROSA EN EL CAMINO VIVO (hub_atado).

El checker de afirmaciones estaba escrito desde el 17-jul y no lo llamaba
NADIE: quedo huerfano cuando el orchestrator paso de `interprete_libre` al hub.
O sea que en produccion no habia nada mirando la mitad blanda de la respuesta
-criterio, comparacion, compatibilidad, uso-, que es justamente la que el codigo
no puede chequear con un numero.

Estos tests no llaman al LLM: mockean el veredicto del juez y exigen lo que
importa, que es el REPARTO DE PODER. El juez opina; el CODIGO decide:

  - lo sin respaldo y sin numeros se poda,
  - lo que tiene numeros NO se toca (territorio del verificador de plata),
  - la HONESTIDAD ("no lo vendemos") nunca se poda: es lo que queremos que diga,
  - ante error o timeout el turno sale igual, nunca se rompe,
  - y el juez ve la MISMA evidencia que vio el solver, si no poda por ciego.
"""
import asyncio

TIENDA = "verifika_prod"


def _correr(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _fiscalizar(monkeypatch, texto, veredicto, meta=None):
    """Corre el fiscal del hub con un veredicto del juez ya decidido."""
    import app.core.checker_afirmaciones as CH
    import app.core.hub_atado as H
    import app.core.red_verificadores as R

    async def _fake_chequear(respuesta, meta, tienda_id=None, trace_id=None):
        return veredicto

    monkeypatch.setattr(CH, "chequear", _fake_chequear)
    return _correr(R._juez(texto, {
        "meta": meta if meta is not None else {}, "universo": [], "interp": {},
        "mensaje": "hola", "tienda_id": TIENDA, "trace_id": "t_juez",
        "evidencia_juez": lambda: H._evidencia_del_turno(
            meta if meta is not None else {}, [], {}, "hola", TIENDA, "t_juez"),
    }))


# ── el juez corta lo que no tiene respaldo ─────────────────────────────────
def test_poda_la_afirmacion_sin_respaldo(monkeypatch, firestore_doble):
    texto = ("Te sirve para gaming pesado. Es resistente al agua. "
             "¿Te lo aparto?")
    out = _fiscalizar(monkeypatch, texto, {
        "afirmaciones": [{"texto": "Es resistente al agua.",
                          "veredicto": "sin_respaldo"}],
        "sin_respaldo": ["Es resistente al agua."], "corregida": ""})
    assert "resistente al agua" not in out.lower()
    assert "gaming pesado" in out, "se llevo puesta la prosa de venta legitima"
    assert "¿Te lo aparto?" in out


def test_usa_la_reescritura_del_juez_si_es_segura(monkeypatch, firestore_doble):
    """Manera 3: la misma llamada trae la version corregida. Se prefiere a la
    poda porque conserva el tono de venta en vez de dejar un hueco."""
    texto = "Es resistente al agua y anda joya para la oficina."
    out = _fiscalizar(monkeypatch, texto, {
        "afirmaciones": [], "sin_respaldo": ["Es resistente al agua"],
        "corregida": "Anda joya para la oficina y es comodo para el uso diario."})
    assert out == "Anda joya para la oficina y es comodo para el uso diario."


def test_rechaza_la_reescritura_que_inventa_un_numero(monkeypatch,
                                                      firestore_doble):
    """La red de codigo sobre el reescritor: si mete una cifra que no estaba,
    se descarta la reescritura entera y se cae a la poda. El numero es
    territorio del verificador de plata, jamas del que redacta."""
    texto = "Es resistente al agua y anda joya para la oficina."
    out = _fiscalizar(monkeypatch, texto, {
        "afirmaciones": [], "sin_respaldo": ["Es resistente al agua"],
        "corregida": "Anda joya para la oficina y sale $99.999."})
    assert "99.999" not in out


# ── lo que el juez NO puede tocar ──────────────────────────────────────────
def test_no_poda_una_linea_con_numeros(monkeypatch, firestore_doble):
    """Los numeros ya los goberno el verificador de montos. Si el juez tambien
    los podara, dos reglas pisarian el mismo dato y el precio real podria
    desaparecer de la respuesta."""
    texto = "Sale $37.500. Es resistente al agua."
    out = _fiscalizar(monkeypatch, texto, {
        "afirmaciones": [], "corregida": "",
        "sin_respaldo": ["Sale $37.500.", "Es resistente al agua."]})
    assert "$37.500" in out
    assert "resistente al agua" not in out.lower()


def test_no_poda_la_honestidad(monkeypatch, firestore_doble):
    """El bot dice "no vendemos celulares" y la evidencia no lo DICE, asi que
    el juez lo marca sin respaldo. Podarlo seria borrar la honestidad recien
    generada, que es exactamente lo que queremos que el bot diga."""
    texto = "Celulares no vendemos, nuestro rubro es informatica."
    out = _fiscalizar(monkeypatch, texto, {
        "afirmaciones": [], "corregida": "",
        "sin_respaldo": ["Celulares no vendemos, nuestro rubro es informatica."]})
    assert "no vendemos" in out


def test_veredicto_limpio_deja_el_texto_intacto(monkeypatch, firestore_doble):
    texto = "Te sirve para la oficina y viene con garantia oficial."
    out = _fiscalizar(monkeypatch, texto, {
        "afirmaciones": [{"texto": texto, "veredicto": "respaldada"}],
        "sin_respaldo": [], "corregida": ""})
    assert out == texto


# ── el juez jamas rompe el turno ───────────────────────────────────────────
def test_sin_juez_el_turno_sale_igual(monkeypatch, firestore_doble):
    """Sin clave, timeout o error -> chequear devuelve None y no-op."""
    texto = "Te sirve para gaming."
    assert _fiscalizar(monkeypatch, texto, None) == texto


def test_si_el_juez_explota_el_turno_sale_igual(monkeypatch, firestore_doble):
    import app.core.checker_afirmaciones as CH
    import app.core.hub_atado as H
    import app.core.red_verificadores as R

    async def _explota(*a, **k):
        raise RuntimeError("gemini caido")

    monkeypatch.setattr(CH, "chequear", _explota)
    texto = "Te sirve para gaming."
    assert _correr(R._juez(texto, {
        "meta": {}, "universo": [], "interp": {}, "mensaje": "hola",
        "tienda_id": TIENDA, "trace_id": "t_x",
        "evidencia_juez": lambda: None})) == texto


def test_no_corre_sobre_el_fallback(monkeypatch, firestore_doble):
    from app.config import get_settings
    fb = get_settings().VERIFIKA_FALLBACK_MESSAGE
    assert _fiscalizar(monkeypatch, fb, {"afirmaciones": [], "corregida": "",
                                         "sin_respaldo": [fb]}) == fb


# ── LA EVIDENCIA: el juez tiene que ver lo mismo que vio el solver ─────────
def test_la_evidencia_lleva_el_grounding_que_el_modelo_no_cito(firestore_doble):
    """Un juez con menos evidencia que el redactor no detecta alucinacion:
    poda prosa fundada. Por eso el paquete se arma llamando a las MISMAS
    funciones de generador_v2 que armaron el prompt del solver."""
    import app.core.hub_atado as H
    meta = {"tools_called": []}
    interp = {"categorias": ["garantia"], "productos_consultados": []}
    H._evidencia_del_turno(meta, [], interp, "que garantia tiene?", TIENDA,
                           "t_ev")
    assert meta.get("prosa_evidencia") or meta.get("faq_evidencia"), (
        "el juez iba a juzgar sin el grounding que el solver SI tuvo delante")


def test_la_evidencia_entra_al_texto_que_ve_el_juez(firestore_doble):
    from app.core.checker_afirmaciones import evidencia_de_meta
    meta = {"tools_called": [],
            "prosa_evidencia": [{"id": "garantia", "texto": "12 meses"}],
            "faq_evidencia": [{"tema": "envio", "texto": "gratis desde 250mil"}]}
    ev = evidencia_de_meta(meta, TIENDA)
    assert "CRITERIO JURADO garantia: 12 meses" in ev
    assert "FAQ envio: gratis desde 250mil" in ev


# ── y que el HUB lo llame de verdad, no solo que la funcion exista ─────────
def test_el_hub_llama_al_juez_en_un_turno_real(monkeypatch, firestore_doble):
    """El pecado de este repo fue tener el modulo escrito y no llamarlo. Este
    test corre un turno COMPLETO del hub y exige que el fiscal haya corrido."""
    import app.core.cierre as C
    import app.core.generador_v2 as G
    import app.core.hub_atado as H
    import app.core.red_verificadores as R
    from app.storage.firestore_client import reset_conversation

    llamado = {}

    async def _fake_interpretar(*a, **k):
        return {"intencion": "pregunta_especifica", "producto_resuelto": None,
                "productos_consultados": [], "pedido": [],
                "solicitud_nueva": [], "categorias": ["mouse"]}

    async def _fake_fragmentos(*a, **k):
        return ([{"tipo": "prosa", "texto": "Te sirve para la oficina."}],
                [], "", [], {})

    async def _espia(texto, ctx):
        llamado["si"] = True
        return texto

    monkeypatch.setattr(C, "extraer_datos_cliente", lambda *a, **k: {})
    monkeypatch.setattr(H, "interpretar_mensaje", _fake_interpretar)
    monkeypatch.setattr(G, "generar_fragmentos", _fake_fragmentos)
    monkeypatch.setattr(R, "_juez", _espia)

    reset_conversation("u_juez", tienda_id=TIENDA)
    _correr(H.procesar_atado("u_juez", "sirve para la oficina?", TIENDA,
                             "sim", "t_hub_juez"))
    assert llamado.get("si"), "el hub NO llama al juez: sigue huerfano"
