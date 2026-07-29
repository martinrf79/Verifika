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


# ── HALLAZGOS DEL BANCO VIVO DEL 29-jul ────────────────────────────────────
def test_el_juez_no_puede_borrar_un_numero_de_la_fuente(firestore_doble):
    """LA falla del guion 68 turno 2. El codigo estampo "Memoria RAM: 4GB"
    desde el catalogo, el juez no veia el mapa de specs en su evidencia, lo
    marco sin respaldo y su reescritura lo borro: al cliente le llego
    "Memoria RAM." pelado. Un numero que esta en la evidencia lo puso el
    codigo desde la fuente; el reescritor no lo puede tocar."""
    from app.core.checker_afirmaciones import rewrite_segura
    original = "Memoria RAM: 4GB. Almacenamiento: 128GB. Es ideal para vos."
    corregida = "Memoria RAM. Almacenamiento. Es ideal para vos."
    evidencia = 'FICHA: {"specs": {"ram": "4GB", "almacenamiento": "128GB"}}'
    assert rewrite_segura(original, corregida, evidencia) is None


def test_el_juez_si_puede_sacar_un_numero_que_invento(firestore_doble):
    """La otra direccion: "sumergible hasta 3 metros" no esta en la ficha, asi
    que sacarlo es exactamente lo que el juez tiene que hacer."""
    from app.core.checker_afirmaciones import rewrite_segura
    original = "Es comodo y es sumergible hasta 3 metros de profundidad."
    corregida = "Es comodo para el uso diario en tu escritorio."
    evidencia = 'FICHA: {"material": "plastico", "garantia_meses": 24}'
    assert rewrite_segura(original, corregida, evidencia) == corregida


def test_la_ficha_que_ve_el_juez_lleva_las_specs(firestore_doble):
    """Causa raiz del caso anterior: la evidencia llevaba once campos curados y
    el mapa `specs` no estaba entre ellos. Va la ficha ENTERA."""
    from app.core.checker_afirmaciones import evidencia_de_meta
    from app.storage.firestore_client import get_all_products
    p = next(x for x in get_all_products(tienda_id=TIENDA) if x.get("specs"))
    meta = {"tools_called": [{"name": "get_product_details",
                              "result": {"encontrado": True, "producto": p}}]}
    ev = evidencia_de_meta(meta, TIENDA)
    assert "specs" in ev, "el juez sigue sin ver lo que el codigo estampa"


def test_una_consulta_simple_no_dispara_la_guarda_del_presupuesto(
        firestore_doble):
    """Guion 54 turno 1: "busco un mouse para gaming" recibia "¡Buena compra la
    que estas armando! Necesito que me digas los modelos", cuando el cliente
    todavia no estaba armando nada. Solo es un pedido por categorias si pide
    VARIAS unidades o VARIAS categorias."""
    import app.core.hub_atado as H
    from app.core.guia_pedido import cantidades_por_categoria
    cats = cantidades_por_categoria("hola, busco un mouse para gaming", TIENDA) or []
    assert len(cats) < 2 and not any(n > 1 for n, _c in cats), (
        "el mensaje simple trae categorias como si fuera un pedido multiple")


def test_preguntar_compatibilidad_no_es_pedir_ese_producto(firestore_doble):
    """Guion 54 turno 2: "el mas barato sirve para PS5?" pregunta por el mouse.
    Contestarle "PS5 no trabajamos" es un despropósito y encima tapa la
    respuesta real."""
    from app.core.guia_compra import categoria_no_vendida
    assert categoria_no_vendida("el mas barato que tengas sirve para PS5?",
                                TIENDA) is None
    assert categoria_no_vendida("anda con la play?", TIENDA) is None
    # pero pedirla SI dispara el no honesto
    assert categoria_no_vendida("tenes PS5?", TIENDA) is not None


def test_no_saluda_de_nuevo_en_el_turno_5(firestore_doble):
    """Un vendedor no te saluda cinco veces en la misma charla."""
    from app.core.guardas_salida import sin_saludo_del_modelo
    assert not sin_saludo_del_modelo(
        "¡Hola! Entiendo perfectamente, el M170 anda bien.").startswith("¡Hola")
    assert sin_saludo_del_modelo(
        "¡Qué tal! Te entiendo, el blanco queda impecable."
    ).startswith("Te entiendo")
    # y no se come una frase que arranca parecido pero no es saludo
    assert sin_saludo_del_modelo(
        "Buenas noticias: volvio el stock.").startswith("Buenas noticias")
