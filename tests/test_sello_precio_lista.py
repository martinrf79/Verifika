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
