"""
AREA: Sello del precio de lista en prosa — el hueco del $16.500 del KB-110X.

El solver escribe un precio de lista pegado al nombre de un producto que no
coincide con el catalogo. Aunque la cifra coincida con algun numero del pool y
no se marque "sin respaldo", el ancla al NOMBRE la autocorrige al precio real.
Cubre autocorregir_montos (app/core/verificador.py). Logica pura.
"""
from app.core.verificador import autocorregir_montos


def _prod(id_, nombre, precio):
    return {"tipo": "producto", "id": id_, "nombre": nombre, "precio_ars": precio}


def test_precio_de_lista_mal_tipeado_se_sella_al_catalogo():
    """KB-110X Blanco escrito a $16.500; catalogo $12.000. Se corrige aunque no
    este marcado sin respaldo."""
    ev = [_prod("TEC0020", "Teclado Genius KB-110X Blanco", 12000)]
    r = "El Teclado Genius KB-110X Blanco sale $16.500."
    fix = autocorregir_montos(r, ev)
    assert fix["cambiada"]
    assert "12.000" in fix["respuesta"]
    assert "16.500" not in fix["respuesta"]


def test_precio_que_es_de_OTRO_producto_igual_se_corrige_al_nombrado():
    """La cifra $52.000 es un precio REAL (de otro producto) y por eso figura en
    el pool, pero esta escrita como precio del KB-110X: el ancla al nombre manda."""
    ev = [_prod("TEC0020", "Teclado Genius KB-110X Blanco", 12000),
          _prod("AUR0019", "Auriculares Redragon Zeus X Negro", 52000)]
    r = "El Teclado Genius KB-110X Blanco sale $52.000."
    fix = autocorregir_montos(r, ev)
    assert fix["cambiada"] and "12.000" in fix["respuesta"]


def test_precio_correcto_no_se_toca():
    ev = [_prod("TEC0020", "Teclado Genius KB-110X Blanco", 12000)]
    r = "El Teclado Genius KB-110X Blanco sale $12.000."
    fix = autocorregir_montos(r, ev)
    assert not fix["cambiada"]


def test_precio_real_citado_en_precios_validos_no_se_pisa():
    """Candado Corsair intacto: un precio real citado (precios_validos) no se
    corrige aunque quede cerca de otro nombre."""
    ev = [_prod("TEC0001", "Teclado Redragon Kumara", 93000)]
    r = "El Teclado Redragon Kumara sale $93.000, te lo preparo?"
    fix = autocorregir_montos(r, ev, precios_validos={93000})
    assert not fix["cambiada"]


def test_total_con_nombre_en_la_frase_no_se_toca_por_ancla_de_precio():
    """Un TOTAL que comparte la frase con un producto NO se corrige con el precio
    de lista de ese producto: el ancla de precio solo actua en contexto de precio
    puro, no en contexto de total."""
    ev = [_prod("TEC0020", "Teclado Genius KB-110X Blanco", 12000)]
    # 24000 es el total de 2 unidades; contexto 'total', no precio de lista.
    r = "Por 2 Teclado Genius KB-110X Blanco, el total es $24.000."
    fix = autocorregir_montos(r, ev)
    assert not fix["cambiada"], "un total no se pisa con el precio de lista del producto"


# Hallado 8-jul con el presupuesto sellado de la guia de pedido: el sello pisaba
# los subtotales por renglon ("3x X: $693.000 c/u = $2.079.000" -> corregia
# 2.079.000 a 693.000) y hasta el total, porque el nombre del producto queda en
# la ventana y la cifra difiere del precio unitario. La partida doble manda: un
# monto que la calculadora COMPUTO (proof) nunca se corrige por el nombre.

def _proof_pedido():
    return {"tipo": "proof", "proof": {
        "tipo": "calculo_total",
        "operandos_productos": [
            {"id": "NOT0019", "monto": 2079000, "precio_unitario": 693000},
            {"id": "MOU0023", "monto": 25500, "precio_unitario": 8500},
        ],
        "subtotal_productos": 2104500,
        "resultado": 2104500,
    }}


def test_sello_no_pisa_subtotal_por_renglon_del_proof():
    from app.core.verificador import autocorregir_montos
    ev = [
        {"tipo": "producto", "id": "NOT0019",
         "nombre": "Notebook HP 245 G9 Core i5 16GB 512GB SSD Gris",
         "precio_ars": 693000},
        {"tipo": "producto", "id": "MOU0023",
         "nombre": "Mouse Genius DX-110 Negro", "precio_ars": 8500},
        _proof_pedido(),
    ]
    texto = ("- 3x Notebook HP 245 G9 Core i5 16GB 512GB SSD Gris: "
             "$693.000 c/u = $2.079.000\n"
             "- 3x Mouse Genius DX-110 Negro: $8.500 c/u = $25.500\n"
             "Total: $2.104.500")
    fix = autocorregir_montos(texto, ev, "test")
    assert fix["cambiada"] is False, fix["correcciones"]
    assert fix["respuesta"] == texto


def test_sello_sigue_corrigiendo_precio_mal_tipeado_sin_proof():
    # El caso original del sello (KB-110X a $16.500) sigue cubierto: precio de
    # lista mal tipeado SIN proof que lo respalde se corrige al del catalogo.
    from app.core.verificador import autocorregir_montos
    ev = [{"tipo": "producto", "id": "TEC0020",
           "nombre": "Teclado Genius KB-110X Blanco", "precio_ars": 12000}]
    texto = "El Teclado Genius KB-110X Blanco esta $16.500, aprovechalo."
    fix = autocorregir_montos(texto, ev, "test")
    assert fix["cambiada"] is True
    assert any(c["de"] == 16500 and c["a"] == 12000
               for c in fix["correcciones"])


def test_sello_corrige_monto_computado_de_otro_producto():
    # Caso Zeus X (banco vivo 8-jul): el solver calculo con OTRO producto
    # (AUR0045) y le puso el nombre del Zeus X Negro. El monto esta computado
    # en el proof, pero para OTRO id: la exencion por identidad NO aplica y el
    # precio se corrige al del producto nombrado.
    from app.core.verificador import autocorregir_montos
    ev = [
        {"tipo": "producto", "id": "AUR0019",
         "nombre": "Auriculares Redragon Zeus X Negro", "precio_ars": 57500},
        {"tipo": "proof", "proof": {
            "tipo": "calculo_total",
            "operandos_productos": [
                {"id": "AUR0045", "monto": 62500, "precio_unitario": 62500}],
            "subtotal_productos": 62500,
            "resultado": 71500,
        }},
    ]
    texto = "- 1x Auriculares Redragon Zeus X Negro: $62.500"
    fix = autocorregir_montos(texto, ev, "test")
    assert fix["cambiada"] is True
    assert any(c["de"] == 62500 and c["a"] == 57500
               for c in fix["correcciones"])


def test_contexto_total_tolera_negrita_markdown():
    from app.core.verificador import _contexto_total
    t = "**Subtotal:** $2.148.000"
    assert _contexto_total(t, t.index("2.148"))
    t2 = "**Total: $71.500**"
    assert _contexto_total(t2, t2.index("71.500"))


def test_renglon_de_presupuesto_con_precio_de_otro_producto_se_corrige():
    # Caso Zeus/Pandora del banco (8-jul): el solver calculo con el Pandora
    # ($62.500, precio real en el pool) pero el renglon nombra al Zeus X Negro.
    # En un renglon de presupuesto (cifra PEGADA al nombre) el ancla manda
    # sobre el candado del pool.
    ev = [_prod("AUR0019", "Auriculares Redragon Zeus X Negro", 57500),
          _prod("AUR0045", "Auriculares Redragon Pandora Negro", 62500)]
    r = "- 1x Auriculares Redragon Zeus X Negro: $62.500 c/u = $62.500"
    fix = autocorregir_montos(r, ev, precios_validos={57500, 62500})
    assert fix["cambiada"]
    assert "62.500" not in fix["respuesta"]
    assert "57.500" in fix["respuesta"]


def test_prosa_suelta_con_precio_del_pool_respeta_el_candado():
    # "el otro que viste $62.500": la cifra NO esta pegada al nombre (hay prosa
    # en el medio) y es un precio real del pool: el candado Corsair la protege.
    ev = [_prod("AUR0019", "Auriculares Redragon Zeus X Negro", 57500)]
    r = ("El Auriculares Redragon Zeus X Negro sale $57.500 y el otro que "
         "viste $62.500.")
    fix = autocorregir_montos(r, ev, precios_validos={57500, 62500})
    assert not fix["cambiada"]


def test_renglones_consecutivos_no_confunden_el_ancla():
    # Caso real WhatsApp 8-jul: "...Acer: $732.500" en el renglon anterior y
    # "K120 Blanco: $732.500" abajo. La ventana cruza el salto de linea y los
    # dos nombres la volvian ambigua; el nombre del MISMO renglon desempata y
    # el precio robado se corrige.
    ev = [_prod("NOT0064", "Notebook Acer Aspire 5 Core i5 16GB 512GB SSD Gris", 732500),
          _prod("TEC0030", "Teclado Logitech K120 Blanco", 14500)]
    r = ("- 1x Notebook Acer Aspire 5 Core i5 16GB 512GB SSD Gris: $732.500\n"
         "- 1x Teclado Logitech K120 Blanco: $732.500")
    fix = autocorregir_montos(r, ev, precios_validos={732500, 14500})
    assert fix["cambiada"]
    assert any(c["de"] == 732500 and c["a"] == 14500 for c in fix["correcciones"])
    # el renglon del Acer (correcto) quedo intacto
    assert "Acer Aspire 5 Core i5 16GB 512GB SSD Gris: $732.500" in fix["respuesta"]
