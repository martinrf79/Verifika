"""
AREA: Acople del bloque curado de FAQ a la prosa del solver (curadas.py).

El bloque curado del tema consultado por query_faq se pega en VERTICAL debajo
de la prosa del solver. Reglas lockeadas:
  - composicion vertical: la costura es un salto de linea, no una conjuncion;
  - un solo cierre por mensaje: si la prosa ya termina preguntando, el gancho
    final del bloque (su ultima oracion interrogativa) se recorta;
  - sin duplicados: si el solver pego la curada tal cual, no se agrega de nuevo;
  - el bloque sale del ULTIMO query_faq del turno y estampa desde los valores
    del MISMO tema; sin consulta valida o sin curada, no hay bloque.
"""
from app.core import curadas as C


# ── acoplar_bloque: la composicion pura ──────────────────────────────────────

def test_acopla_vertical_con_gancho():
    prosa = "Genial, el mouse te encanta."
    bloque = "Tenes 10 dias corridos para arrepentirte. Queres que te ayude?"
    out = C.acoplar_bloque(prosa, bloque)
    assert out == prosa + "\n\n" + bloque


def test_un_solo_cierre_recorta_gancho_del_bloque():
    prosa = "Te lo agrego al pedido. Confirmamos?"
    bloque = "Tenes 10 dias corridos para arrepentirte. Queres que te ayude?"
    out = C.acoplar_bloque(prosa, bloque)
    assert out.endswith("arrepentirte.")
    assert "Queres que te ayude?" not in out
    assert "Confirmamos?" in out


def test_no_duplica_si_el_solver_pego_la_curada():
    bloque = "Tenes 10 dias corridos para arrepentirte. Queres que te ayude?"
    prosa = "Mira: Tenes 10 dias corridos para arrepentirte. Algo mas?"
    out = C.acoplar_bloque(prosa, bloque)
    assert out == prosa


def test_prosa_vacia_sale_el_bloque_solo():
    bloque = "Tenes 10 dias corridos para arrepentirte."
    assert C.acoplar_bloque("", bloque) == bloque
    assert C.acoplar_bloque("Hola.", "") == "Hola."


def test_bloque_todo_pregunta_no_se_recorta_a_vacio():
    # Si el bloque entero es una pregunta, recortar el gancho lo dejaria vacio:
    # se conserva aunque queden dos preguntas (peor es perder la politica).
    prosa = "Dale, lo vemos. Te interesa?"
    bloque = "Queres que te lo reserve?"
    out = C.acoplar_bloque(prosa, bloque)
    assert "Queres que te lo reserve?" in out


# ── bloque_curado_de_meta: el ancla al query_faq del turno ───────────────────

def _meta_faq(tema, encontrada=True):
    return {"tools_called": [
        {"name": "query_faq", "result": {"encontrada": encontrada, "tema": tema}},
    ]}


def test_bloque_del_tema_consultado_estampa(firestore_doble):
    bc = C.bloque_curado_de_meta(_meta_faq("devoluciones"), "verifika_prod")
    assert bc is not None
    tema, bloque = bc
    assert tema == "devoluciones"
    assert "10 dias corridos" in bloque
    assert "{{" not in bloque


def test_sin_query_faq_no_hay_bloque(firestore_doble):
    assert C.bloque_curado_de_meta({"tools_called": []}, "verifika_prod") is None
    assert C.bloque_curado_de_meta(
        _meta_faq("devoluciones", encontrada=False), "verifika_prod") is None


def test_tema_inexistente_no_hay_bloque(firestore_doble):
    assert C.bloque_curado_de_meta(
        _meta_faq("tema_que_no_existe"), "verifika_prod") is None


# ── Bloque por RUTEO del mensaje: no depende del query_faq del solver ────────

def test_bloque_por_mensaje_sin_toolcall(firestore_doble):
    # 'tienen local para retirar?' en medio de una venta: el solver no llamo
    # query_faq, pero el interprete ve pregunta y el ruteo matchea retiro_local.
    interp = {"intencion": "pregunta_especifica", "confianza": 0.9}
    bc = C.bloque_curado_por_mensaje(
        "tienen local para retirar?", interp, "verifika_prod")
    assert bc is not None
    tema, bloque = bc
    assert tema == "retiro_local"
    assert "sin punto de retiro" in bloque


def test_bloque_por_mensaje_respeta_intencion(firestore_doble):
    # Con intencion de compra no se rutea bloque: el turno es de venta pura.
    interp = {"intencion": "decision_compra", "confianza": 0.9}
    assert C.bloque_curado_por_mensaje(
        "dale lo quiero, retiro yo?", interp, "verifika_prod") is None


# ── Pertinencia del bloque (charla viva 4-jul): cuando NO va ─────────────────

def test_gancho_se_recorta_con_pregunta_en_el_medio():
    # El solver suele preguntar con lista numerada en el medio, sin cerrar
    # con "?": igual es UNA pregunta del mensaje y el gancho del bloque sobra.
    prosa = "Decime:\n1. ¿A que CP la mandamos?\n2. Como pagas (transferencia)."
    bloque = "Tenes 10 dias corridos para arrepentirte. Queres que te ayude?"
    out = C.acoplar_bloque(prosa, bloque)
    assert "Queres que te ayude?" not in out
    assert "arrepentirte." in out


def test_tool_del_dominio_cubre_el_tema():
    meta = {"tools_called": [
        {"name": "cotizar_envio", "result": {"ok": True, "monto": 6000}},
        {"name": "calculate_total", "result": {"ok": True, "detalle": [{}]}},
    ]}
    cubiertos = C.temas_cubiertos_por_tools(meta)
    assert "envios" in cubiertos and "costo_envio" in cubiertos
    assert "descuento_transferencia" in cubiertos
    assert "devoluciones" not in cubiertos


def test_tool_fallida_no_cubre():
    meta = {"tools_called": [{"name": "cotizar_envio", "result": {"ok": False}}]}
    assert C.temas_cubiertos_por_tools(meta) == set()


def test_solapa_prosa_detecta_parafraseo():
    bloque = ("Aceptamos transferencia bancaria, Mercado Pago y tarjetas Visa, "
              "Mastercard y American Express, credito o debito. Con transferencia "
              "ademas tenes descuento. Contame que producto te interesa y te paso "
              "el total con cada forma de pago.")
    prosa = ("Las formas de pago son: transferencia bancaria (con descuento), "
             "Mercado Pago con tarjeta de credito o debito Visa, Mastercard o "
             "American Express. Todo en pesos.")
    assert C.solapa_prosa(prosa, bloque)
    assert not C.solapa_prosa("Buenisima eleccion, el mouse anda muy bien.", bloque)
