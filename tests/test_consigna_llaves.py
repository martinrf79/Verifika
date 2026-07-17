"""
AREA: Las tres llaves que destaparon las consignas 39-46 (17-jul).

La corrida de la consigna mostro UN sintoma (turnos mudos o saludo pelado ante
preguntas reales) con tres causas de cableado:
  1. PISO DE COMPOSICION (fila Z): nunca sale un turno sin sustancia; si las
     podas dejaron un residuo hueco ante un mensaje con contenido, sale el
     honesto con derivacion y repregunta.
  2. CERTIFICADOR DE CATEGORIA: una categoria que NO vendemos (celular,
     consola) la decide el codigo con honestidad + alternativa real, no el
     modelo siguiendo la premisa.
  3. TYPOS EN EL UNIVERSO: 'mause', 'auris' matchean su categoria real; sin
     eso el universo quedaba vacio y el modelo sin nada que ofrecer.
"""
from app.core.interprete_libre import _mensaje_con_contenido, _sin_sustancia

# guia_compra y generador_v2 se importan DENTRO de cada test: un import a
# nivel de modulo corre en la recoleccion, antes de que la fixture instale el
# doble de Firestore, y clava referencias reales (visto: media bateria roja
# con DefaultCredentialsError).


# ── 1. Piso de composicion ───────────────────────────────────────────────────

def test_mensaje_con_contenido():
    assert _mensaje_con_contenido("hola, busco una notebook para editar video")
    assert _mensaje_con_contenido("qiero un mause inalambrico")
    assert not _mensaje_con_contenido("hola")
    assert not _mensaje_con_contenido("¡Buenas tardes!")
    assert not _mensaje_con_contenido("buen dia")
    assert not _mensaje_con_contenido("")


def test_sin_sustancia_caza_residuos_de_poda():
    # Los residuos reales que dejo la consigna:
    assert _sin_sustancia("¡Qué hacés! Te cuento,")
    assert _sin_sustancia("Te cuento cómo nos manejamos")
    assert _sin_sustancia("")
    assert _sin_sustancia("   ")


def test_sin_sustancia_respeta_respuestas_validas():
    # Corta pero con pregunta que mueve la charla: valida.
    assert not _sin_sustancia("¿Qué estás buscando?")
    # Con dato estampado: valida.
    assert not _sin_sustancia("El M170 sale $12.000.")
    # Larga y con contenido: valida.
    assert not _sin_sustancia(
        "Eso puntual no lo tengo confirmado ahora, lo consulto con el "
        "equipo y te escribo apenas lo tenga.")


# ── 2. Certificador de categoria ─────────────────────────────────────────────

def test_celular_no_vendido_con_alternativa(firestore_doble):
    from app.core.guia_compra import categoria_no_vendida
    out = categoria_no_vendida(
        "Busco un celular bueno para fotos, no quiero gastar mas de 500 mil",
        "verifika_prod")
    assert out is not None
    pedida, alt = out
    assert pedida == "celular"
    assert alt == "tablet"  # la alternativa es una categoria REAL


def test_consola_no_vendida_sin_alternativa(firestore_doble):
    from app.core.guia_compra import categoria_no_vendida
    out = categoria_no_vendida("tenes consolas playstation?", "verifika_prod")
    assert out is not None and out[1] is None


def test_categoria_real_en_el_mensaje_no_dispara(firestore_doble):
    """'Auriculares para la play' es compatibilidad de un producto REAL: lo
    conduce el generador, no el certificador de categoria."""
    from app.core.guia_compra import categoria_no_vendida
    assert categoria_no_vendida(
        "tenes auriculares que anden en playstation?", "verifika_prod") is None


def test_mensaje_comun_no_dispara(firestore_doble):
    from app.core.guia_compra import categoria_no_vendida
    assert categoria_no_vendida("hola, cuanto sale el mouse mas barato?",
                                "verifika_prod") is None
    # 'telefono' y 'play' quedan afuera a proposito (ambiguas: dato de
    # contacto, 'anda en play 5').
    assert categoria_no_vendida("mi telefono es 351555", "verifika_prod") is None


# ── 3. Typos en el universo ──────────────────────────────────────────────────

def test_universo_matchea_typo_mause(firestore_doble):
    from app.core.generador_v2 import universo_productos
    uni = universo_productos("qiero un mause inalambrico q sea barato",
                             {}, "verifika_prod")
    assert any(p.get("categoria") == "mouse" for p in uni)


def test_universo_matchea_auris(firestore_doble):
    from app.core.generador_v2 import universo_productos
    uni = universo_productos("tenes auris tmbn? q no sean tan caros",
                             {}, "verifika_prod")
    assert any(p.get("categoria") == "auriculares" for p in uni)


def test_universo_sin_falsos_positivos(firestore_doble):
    """Un mensaje sin categoria nombrada no infla el universo por el difuso."""
    from app.core.generador_v2 import universo_productos
    uni = universo_productos("quiero gastar lo menos posible", {}, "verifika_prod")
    assert uni == []


# ── 4. Caos real de WhatsApp 17-jul: destinos fantasma y presupuesto pedido ──

def test_destino_fantasma_se_anula():
    """El interprete metio 'Rosario' sin que el cliente lo dijera: un destino
    que no aparece en el mensaje va None (invariante determinista)."""
    from app.core.interpretador import coercionar_destinos
    r = {"pedido": [
        {"producto": "Mouse Genius DX-110 Negro", "cantidad": 2,
         "destino": "Rosario"},
        {"producto": "Teclado Genius KB-110X Blanco", "cantidad": 2,
         "destino": "Carlos Paz"},
    ]}
    coercionar_destinos(r, "Y el presupuesto? mandalo todo a carlos paz")
    assert r["pedido"][0]["destino"] is None       # Rosario: fantasma
    assert r["pedido"][1]["destino"] == "Carlos Paz"  # dicho en el mensaje


def test_pedir_presupuesto_re_sirve_el_sellado(firestore_doble):
    """'¿Y el presupuesto?' y 'seguis sin mandarme precios' con carrito
    vigente disparan el calculo SELLADO del codigo (el cliente lo pidio TRES
    veces en la charla real y el bot nunca lo mando)."""
    from app.core.generador_v2 import presupuesto_precalculado
    estado = {"carrito": [
        {"id": "TEC0015", "nombre": "Teclado Redragon Kumara K552 Negro",
         "cantidad": 2},
    ]}
    for msg in ("Y el presupuesto?", "Seguis sin mandarme los precios"):
        texto, tools = presupuesto_precalculado(msg, estado, "verifika_prod")
        assert texto and "$" in texto, msg
        assert any(t.get("name") == "calculate_total" for t in tools), msg


def test_pregunta_de_precio_singular_no_re_sirve(firestore_doble):
    """'que precio tiene el mouse' con carrito NO re-sirve el presupuesto
    entero: es pregunta de UN producto, la responde el generador."""
    from app.core.generador_v2 import presupuesto_precalculado
    estado = {"carrito": [{"id": "TEC0015", "cantidad": 2}]}
    texto, _ = presupuesto_precalculado(
        "que precio tiene el mouse M170?", estado, "verifika_prod")
    assert texto is None


def test_termino_medio_arma_menu_intermedio(firestore_doble):
    """'Dame un termino medio asi elijo' con carrito vigente (caso real
    20:47): el CODIGO arma el menu con el intermedio real de cada categoria,
    precio estampado; el cliente lo recibe siempre por la red de posicionado."""
    from app.core.generador_v2 import bloque_intermedio
    estado = {"carrito": [
        {"id": "TEC0020", "cantidad": 2},
        {"id": "MOU0023", "cantidad": 2},
    ]}
    texto, tools = bloque_intermedio(
        "Ok pero dame un termino medio asi elijo", estado, "verifika_prod")
    assert texto and "$" in texto
    assert len(tools) >= 2  # un intermedio por categoria, con su proof


def test_termino_medio_sin_carrito_no_dispara(firestore_doble):
    from app.core.generador_v2 import bloque_intermedio
    texto, tools = bloque_intermedio("dame algo intermedio", {}, "verifika_prod")
    assert texto is None and tools == []


def test_presupuesto_sellado_viaja_por_la_red_del_generador(firestore_doble):
    """El sellado ya no saltea al generador: viaja como presupuesto externo y
    si el modelo no lo posiciona, la red lo inyecta igual. El cliente SIEMPRE
    recibe el bloque sellado, y el resto del mensaje se responde alrededor."""
    from app.core.generador_v2 import renderizar
    presu = ("Presupuesto:\n- 1x Tablet Samsung Galaxy Tab A9 Gris: "
             "$211.500 c/u = $211.500\nTotal: $211.500")
    ptools = [{"name": "calculate_total", "result": {"presentacion": presu}}]
    frags = [{"tipo": "faq", "tema": "plazo_envio"},
             {"tipo": "faq", "tema": "envoltorio_regalo"}]
    texto, tools = renderizar(frags, [], {}, "verifika_prod",
                              presupuesto_pre=presu, presupuesto_tools=ptools)
    assert "211.500" in texto            # el sellado llego si o si (red)
    assert any(t["name"] == "calculate_total" for t in tools)


def test_cierre_enlatado_sin_total_es_suave(firestore_doble):
    """Sin un total sobre la mesa, el cierre no pide la forma de pago (queja
    real: preguntaba el medio de pago de entrada)."""
    from app.core.generador_v2 import renderizar
    frags = [{"tipo": "prosa", "texto": "Buena eleccion, es un equipo solido"},
             {"tipo": "cierre"}]
    texto, _ = renderizar(frags, [], {}, "verifika_prod")
    assert "forma de pago" not in texto
    assert "?" in texto  # igual invita a avanzar
