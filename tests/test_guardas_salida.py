"""
AREA: GUARDAS DE SALIDA en el camino vivo (hub_atado + guardas_salida).

Las cinco guardas deterministas que vivian en `interprete_libre` y se perdieron
cuando el orchestrator paso al hub. Sus tests seguian en verde probando codigo
que ya no corria, que es la peor clase de verde.

Los tests de la logica pura de cada una viven en sus archivos historicos
(test_saludo, test_consigna_llaves, test_curadas, test_guia_pedido), repuntados
al modulo nuevo. Aca se exige lo otro, lo que faltaba: que el HUB las llame.
"""
import asyncio

TIENDA = "verifika_prod"


def _correr(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _turno(monkeypatch, user, mensaje, texto_solver, interp=None):
    """Un turno REAL del hub con el interprete y el solver mockeados."""
    import app.core.hub_atado as H
    import app.core.generador_v2 as G
    import app.core.cierre as C

    base = {"intencion": "pregunta_especifica", "producto_resuelto": None,
            "productos_consultados": [], "pedido": [], "solicitud_nueva": [],
            "categorias": []}

    async def _fake_interpretar(*a, **k):
        return {**base, **(interp or {})}

    async def _fake_fragmentos(*a, **k):
        return ([{"tipo": "prosa", "texto": texto_solver}], [], "", [], {})

    async def _sin_red(texto, *a, **k):
        return texto

    monkeypatch.setattr(C, "extraer_datos_cliente", lambda *a, **k: {})
    monkeypatch.setattr(H, "interpretar_mensaje", _fake_interpretar)
    monkeypatch.setattr(G, "generar_fragmentos", _fake_fragmentos)
    # la red ya tiene sus propios tests; aca se aislan las guardas
    monkeypatch.setattr(H, "_red_de_verificadores", _sin_red)
    return _correr(H.procesar_atado(user, mensaje, TIENDA, "sim", "t_guardas"))


# ── 1. HONESTIDAD DE BOT ───────────────────────────────────────────────────
def test_el_hub_dice_la_verdad_si_preguntan_si_es_un_bot(monkeypatch,
                                                         firestore_doble):
    """El prompt solo no alcanza: en el banco el solver esquivaba la pregunta.
    El codigo antepone la verdad, determinista."""
    from app.storage.firestore_client import reset_conversation
    reset_conversation("u_bot", tienda_id=TIENDA)
    # primer turno para que la charla ya este empezada y no se mezcle el saludo
    _turno(monkeypatch, "u_bot", "hola, busco un mouse", "Tengo varios mouse.")
    out = _turno(monkeypatch, "u_bot", "sos un bot?",
                 "¡Claro! Estoy para ayudarte con lo que necesites.")
    assert "asistente automático" in out.lower()


def test_no_repite_la_verdad_si_la_respuesta_ya_la_dice(monkeypatch,
                                                        firestore_doble):
    from app.storage.firestore_client import reset_conversation
    reset_conversation("u_bot2", tienda_id=TIENDA)
    _turno(monkeypatch, "u_bot2", "hola", "Hola, ¿qué buscás?")
    out = _turno(monkeypatch, "u_bot2", "con quien hablo?",
                 "Soy un bot, el asistente automático de la tienda.")
    assert out.lower().count("asistente automático") == 1


# ── 2. SALUDO Y AVISO, una sola vez ────────────────────────────────────────
def test_el_primer_mensaje_avisa_que_es_automatico(monkeypatch, firestore_doble):
    from app.storage.firestore_client import reset_conversation
    reset_conversation("u_saludo", tienda_id=TIENDA)
    out = _turno(monkeypatch, "u_saludo", "hola, que tenes?",
                 "Tenemos mouse, teclados y notebooks.")
    assert "asistente automático" in out.lower()
    assert "Tenemos mouse" in out


def test_el_aviso_va_UNA_sola_vez_en_la_charla(monkeypatch, firestore_doble):
    from app.storage.firestore_client import reset_conversation
    reset_conversation("u_saludo2", tienda_id=TIENDA)
    _turno(monkeypatch, "u_saludo2", "hola", "Hola, ¿qué buscás?")
    out = _turno(monkeypatch, "u_saludo2", "un mouse", "Tengo varios mouse.")
    assert "asistente automático" not in out.lower(), (
        "el aviso se repite en cada turno: molesta y roba lugar a la venta")


# ── 3. RESPUESTA HUECA ─────────────────────────────────────────────────────
def test_una_respuesta_hueca_no_sale_al_cliente(monkeypatch, firestore_doble):
    """Vacia, o corta y sin ningun dato ni pregunta que mueva la charla."""
    from app.storage.firestore_client import reset_conversation
    from app.config import get_settings
    reset_conversation("u_hueco", tienda_id=TIENDA)
    _turno(monkeypatch, "u_hueco", "hola", "Hola.")
    out = _turno(monkeypatch, "u_hueco", "cuanto sale el mouse mas barato?",
                 "Claro.")
    assert out != "Claro."
    assert out.strip(), "la guarda dejo el turno mudo"


def test_un_hola_pelado_no_exige_sustancia(monkeypatch, firestore_doble):
    """'hola' solo NO exige una respuesta con datos: el saludo alcanza."""
    from app.storage.firestore_client import reset_conversation
    reset_conversation("u_hola", tienda_id=TIENDA)
    out = _turno(monkeypatch, "u_hola", "hola", "¡Hola! ¿Qué andás buscando?")
    assert "buscando" in out.lower()


# ── 4. PRESUPUESTO SIN MODELOS ─────────────────────────────────────────────
def test_no_arma_presupuesto_si_el_cliente_no_dijo_los_modelos(firestore_doble):
    """Caso real de WhatsApp del 8-jul: pidio N por categoria sin decir cuales
    y el modelo armo un total eligiendo productos por su cuenta, con un teclado
    al precio de una notebook. En vez del total inventado, opciones REALES."""
    from app.core.guardas_salida import forzar_opciones_si_presupuesto
    out = forzar_opciones_si_presupuesto(
        "Presupuesto:\n- 2x Teclado: $50.000\n- 3x Mouse: $30.000\n"
        "Total: $80.000",
        [(2, "teclado"), (3, "mouse")], TIENDA)
    assert out, "la guarda dejo pasar el presupuesto sin modelos"
    assert "Total: $80.000" not in out
    assert "modelo" in out.lower(), "no le pidio los modelos al cliente"
    assert "$" in out, "no le mostro opciones reales con precio"


def test_si_el_cliente_ya_dijo_los_modelos_el_presupuesto_sale(firestore_doble):
    """La guarda es quirurgica: sin categorias pendientes no toca nada."""
    from app.core.guardas_salida import forzar_opciones_si_presupuesto
    assert forzar_opciones_si_presupuesto(
        "Presupuesto:\nTotal: $80.000", [], TIENDA) is None


def test_el_hub_llama_a_la_guarda_del_presupuesto(monkeypatch, firestore_doble):
    from app.storage.firestore_client import reset_conversation
    from app.core import guardas_salida as GS
    llamado = {}

    def _espia(respuesta, cats, tienda_id):
        llamado["cats"] = cats
        return None

    monkeypatch.setattr(GS, "forzar_opciones_si_presupuesto", _espia)
    reset_conversation("u_presu", tienda_id=TIENDA)
    _turno(monkeypatch, "u_presu", "necesito 2 teclados y 3 mouse",
           "Te paso opciones.",
           interp={"solicitud_nueva": [
               {"categoria": "teclado", "cantidad": 2, "criterio": None},
               {"categoria": "mouse", "cantidad": 3, "criterio": None}]})
    assert llamado.get("cats"), "el hub no le pasa las categorias pendientes"


# ── 5. QUE EL HUB LAS LLAME, no solo que existan ───────────────────────────
def test_las_guardas_corren_despues_de_la_red(monkeypatch, firestore_doble):
    """El orden importa: las guardas van DESPUES de la red de verificadores,
    para que ninguna correccion de la red se lleve puesto el aviso de bot."""
    import app.core.hub_atado as H
    import app.core.generador_v2 as G
    import app.core.cierre as C
    from app.storage.firestore_client import reset_conversation
    from app.core import guardas_salida as GS

    orden = []

    async def _fake_interpretar(*a, **k):
        return {"intencion": "pregunta_especifica", "producto_resuelto": None,
                "productos_consultados": [], "pedido": [],
                "solicitud_nueva": [], "categorias": []}

    async def _fake_fragmentos(*a, **k):
        return ([{"tipo": "prosa", "texto": "Tenemos varios."}], [], "", [], {})

    async def _red(texto, *a, **k):
        orden.append("red")
        return texto

    def _saludo(texto, negocio):
        orden.append("guardas")
        return texto

    monkeypatch.setattr(C, "extraer_datos_cliente", lambda *a, **k: {})
    monkeypatch.setattr(H, "interpretar_mensaje", _fake_interpretar)
    monkeypatch.setattr(G, "generar_fragmentos", _fake_fragmentos)
    monkeypatch.setattr(H, "_red_de_verificadores", _red)
    monkeypatch.setattr(GS, "con_saludo_inicial", _saludo)

    reset_conversation("u_orden", tienda_id=TIENDA)
    _turno_out = _correr(H.procesar_atado("u_orden", "hola que tenes", TIENDA,
                                          "sim", "t_orden"))
    assert orden == ["red", "guardas"], orden
