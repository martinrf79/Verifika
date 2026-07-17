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
