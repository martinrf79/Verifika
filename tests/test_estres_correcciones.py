"""
AREA: Estres de la MELLIZA ACTIVA en casos dificiles (indecision, cambio de
producto, frases mezcladas). La preocupacion real: cuando el solver dice algo
ambiguo y la herramienta corrige, no siempre queda bien.

Estos casos NO prueban el camino feliz: prueban que la correccion (a) corrige lo
inequivoco, (b) NO toca lo ambiguo, y (c) nunca corrompe un dato verdadero. La
regla que se lockea es la conservadora: ante la duda, no tocar.

Corren offline contra los modulos REALES (verificador, verificador_faq,
verificador_stock, estampado), sin LLM.
"""
from app.core.verificador import autocorregir_montos, verificar_respuesta
from app.core import verificador_faq as VF
from app.core import verificador_stock as VS


def _prod(pid, nombre, precio, stock=5):
    return {"tipo": "producto", "id": pid, "nombre": nombre,
            "precio_ars": precio, "stock": stock}


def _proof_total(subtotal, envio=None):
    ops = [{"id": "X", "monto": subtotal, "precio_unitario": subtotal,
            "fuente": "catalogo"}]
    extras = []
    if envio is not None:
        extras.append({"faq_tema": "costo_envio", "concepto": "envio",
                       "modalidad": "fijo", "monto": envio})
    return {"tipo": "proof", "proof": {
        "tipo": "calculo_total_fijo", "operandos_productos": ops,
        "operandos_extras": extras, "subtotal_productos": subtotal,
        "resultado": subtotal + (envio or 0)}}


# ── A: cambio de producto a mitad de charla ──────────────────────────────────

def test_cambio_de_producto_no_arrastra_el_total_viejo():
    """El cliente cambio del producto A (proof viejo en memoria) al B. El solver
    cotiza B con su precio REAL: la melliza NO debe 'corregirlo' hacia el total
    viejo de A. Un precio real de catalogo nunca se pisa."""
    evidencia = [
        _prod("TEC0001", "Teclado Redragon Kumara", 93000),
        _proof_total(150000),  # total del producto ANTERIOR, quedo en memoria
    ]
    r = "El Teclado Redragon Kumara sale $93.000, te lo preparo?"
    precios_validos = {93000}
    fix = autocorregir_montos(r, evidencia, precios_validos=precios_validos)
    assert not fix["cambiada"], (
        "El precio real del producto NUEVO no se corrige hacia el total viejo.")


def test_total_ambiguo_entre_dos_proofs_no_se_toca():
    """Indecision: el cliente barajo DOS pedidos y hay dos proofs vigentes. Un
    total tipeado mal a igual distancia de ambos es ambiguo: NO se elige uno."""
    evidencia = [_proof_total(100000), _proof_total(120000)]
    r = "El total te queda en $110.000."
    fix = autocorregir_montos(r, evidencia)
    assert not fix["cambiada"], (
        "Empate de candidatos = ambiguedad = no tocar (regla conservadora).")


def test_total_unico_cercano_si_se_corrige():
    """Lock del caso bueno: un solo proof, total mal tipeado dentro de banda ->
    se corrige al total real."""
    evidencia = [_proof_total(100000, envio=7500)]
    r = "Con envio, el total es de $108.000."
    fix = autocorregir_montos(r, evidencia)
    assert fix["cambiada"] and fix["verificacion"]["ok"]
    assert "107.500" in fix["respuesta"]


def test_dos_productos_precio_de_uno_mal_se_ancla_al_nombre():
    """Frase con DOS productos, un precio mal tipeado: se corrige con el precio
    del producto NOMBRADO antes de la cifra, no con el numero mas cercano."""
    evidencia = [
        _prod("MOU0001", "Mouse Logitech G203 Lightsync", 37500),
        _prod("MOU0009", "Mouse Razer Viper Mini", 52000),
    ]
    r = ("El Mouse Logitech G203 Lightsync sale $39.500 "
         "y el Mouse Razer Viper Mini sale $52.000.")
    fix = autocorregir_montos(r, evidencia, precios_validos={37500, 52000})
    assert fix["cambiada"]
    assert "37.500" in fix["respuesta"]
    assert "52.000" in fix["respuesta"], "El precio correcto no se toca."


def test_correccion_que_no_cierra_se_descarta():
    """Si despues de corregir la verificacion NO cierra, el llamador debe poder
    descartar: el contrato devuelve verificacion del texto corregido."""
    evidencia = [_proof_total(100000)]
    # Dos cifras malas: una corregible (99.000->100.000), otra imposible.
    r = "Total: $99.000. Ademas te cobro $777.000 de gestion."
    fix = autocorregir_montos(r, evidencia)
    if fix["cambiada"]:
        assert not fix["verificacion"]["ok"], (
            "Queda cifra sin respaldo: el pipeline no debe dar esto por bueno.")


# ── B: FAQ numerica en frases mezcladas ──────────────────────────────────────

_EVID_FAQ = [
    {"tipo": "faq", "id": "descuento_transferencia",
     "tema": "descuento_transferencia",
     "respuesta": "Pagando por transferencia tenes 20% de descuento.",
     "valores": [{"concepto": "transferencia", "unidad": "porcentaje",
                  "monto": 20, "modalidad": "fijo"}]},
    {"tipo": "faq", "id": "cuotas", "tema": "cuotas",
     "respuesta": "Hasta 6 cuotas sin interes.",
     "valores": [{"concepto": "sin_interes", "unidad": "cuotas", "monto": 6,
                  "modalidad": "fijo"}]},
]


def test_frase_mixta_corrige_solo_lo_malo():
    """'25% y 6 cuotas' con el tema del descuento consultado: corrige el 25%
    (pool unico {20}) y deja las 6 cuotas (verdaderas) intactas."""
    r = "Tenes 25% de descuento por transferencia y hasta 6 cuotas sin interes."
    fix = VF.autocorregir_faq_numerica(
        r, _EVID_FAQ, temas_consultados={"descuento_transferencia", "cuotas"})
    assert fix["cambiada"]
    assert "20% de descuento" in fix["respuesta"]
    assert "6 cuotas" in fix["respuesta"]


def test_porcentaje_de_spec_no_se_corrige_sin_ancla():
    """'100% original' no es una politica: sin tema consultado no se toca (queda
    para el log). La correccion nunca actua sin ancla del turno."""
    r = "Es 100% original de fabrica."
    fix = VF.autocorregir_faq_numerica(r, _EVID_FAQ, temas_consultados=set())
    assert not fix["cambiada"]
    assert fix["respuesta"] == r


def test_cuotas_fuera_de_tope_con_ancla_se_corrige_al_tope():
    r = "Lo pagas hasta en 24 cuotas."
    fix = VF.autocorregir_faq_numerica(r, _EVID_FAQ,
                                       temas_consultados={"cuotas"})
    assert fix["cambiada"]
    assert "6 cuotas" in fix["respuesta"]


# ── C: stock en frases de contraste (indecision entre dos productos) ────────

_EVID_STOCK = [
    _prod("TEC0010", "Teclado Redragon Kumara K552", 93000, stock=4),
    _prod("TEC0020", "Teclado HyperX Alloy Origins", 155000, stock=7),
]


def test_contraste_acusa_al_producto_correcto():
    """'El Kumara no tiene stock, pero el HyperX si' cuando el Kumara SI tiene:
    debe acusar al Kumara (nombrado antes de la negacion), no al HyperX."""
    r = ("El Teclado Redragon Kumara K552 no tiene stock, "
         "pero el Teclado HyperX Alloy Origins si.")
    dets = VS.detectar_stock_contradicho(r, _EVID_STOCK)
    assert [d["id"] for d in dets] == ["TEC0010"]


def test_dos_cifras_solo_se_corrige_la_anclada_sin_ambiguedad():
    """'quedan 9 del Kumara ... quedan 2 del HyperX': la primera cifra tiene
    ancla unica (Kumara, ventana previa limpia) y se corrige; la segunda tiene
    DOS nombres en la ventana previa -> ambigua -> no se toca."""
    r = ("Del Teclado Redragon Kumara K552 quedan 9 en stock. "
         "Del Teclado HyperX Alloy Origins quedan 2 en stock.")
    fix = VS.corregir_unidades_stock(r, _EVID_STOCK)
    des = [c["de"] for c in fix["correcciones"]]
    assert 9 in des, "La cifra con ancla unica se corrige."
    # La segunda NO debe corregirse MAL (a un producto equivocado): si se
    # corrigio, tiene que ser hacia el stock del HyperX (7), nunca el del otro.
    for c in fix["correcciones"]:
        if c["de"] == 2:
            assert c["a"] == 7 and c["id"] == "TEC0020"


# ── D: estampado con ids sucios (el marcador no puede romper el texto) ───────

def test_estampado_id_inexistente_se_quita_limpio(firestore_doble):
    from app.core.interprete_libre import _estampar_productos
    r = "Te recomiendo [[PROD:NOEXISTE99]] que es excelente."
    out = _estampar_productos(r, "verifika_prod")
    assert "[[" not in out and "]]" not in out
    assert "excelente" in out


def test_estampado_id_en_minuscula_igual_estampa(firestore_doble):
    from app.core.interprete_libre import _estampar_productos
    from app.core.tools import get_all_products
    p = get_all_products()[0]
    r = f"Mira [[PROD:{p['id'].lower()}]] esta buenisimo."
    out = _estampar_productos(r, "verifika_prod")
    assert p["nombre"] in out


# ── E: la verificacion pura nunca da falso OK en frases dificiles ────────────

def test_numero_inventado_entre_dos_verdaderos_no_pasa():
    evidencia = [
        _prod("A1", "Producto Alfa Uno", 50000),
        _prod("B2", "Producto Beta Dos", 80000),
    ]
    r = "El Alfa sale $50.000, el Beta $80.000 y el combo $115.000."
    v = verificar_respuesta(r, evidencia)
    assert not v["ok"], "El 'combo' inventado no tiene respaldo: no pasa."
