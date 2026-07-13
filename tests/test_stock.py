"""
AREA: Stock — el campo que el blindaje de plata NO cubria (hueco real del 2-jul:
el solver invento faltantes "DX-110 no tiene stock" y upselleo a lo caro).

Herramientas del bot cubiertas: verificador_stock (deteccion de afirmaciones de
disponibilidad contra el catalogo + safe-override de la cifra de unidades) y
guia_compra (el "mas barato con stock" lo computa el CODIGO, el solver no elige).

Mismo patron que el verificador de plata: anclado al producto NOMBRADO, corrige
solo cuando el ancla es UNICA e inequivoca; ante ambiguedad no toca.
"""
from app.core import verificador_stock as VS


def _prod(pid, nombre, stock, precio=10000):
    return {"tipo": "producto", "id": pid, "nombre": nombre,
            "stock": stock, "precio_ars": precio}


EVIDENCIA = [
    _prod("TEC0010", "Teclado Redragon Kumara K552", 5),
    _prod("TEC0020", "Teclado HyperX Alloy Origins", 0),
    _prod("MOU0001", "Mouse Logitech G203 Lightsync Negro", 3),
]


# ── Deteccion de contradiccion de TEXTO (negar stock que existe y viceversa) ──

def test_niega_stock_que_existe_se_detecta():
    """El caso real del 2-jul: el solver niega stock de un producto que SI tiene.
    Anclado al nombre; devuelve la clase y el stock real para la reescritura."""
    r = ("El Teclado Redragon Kumara no tiene stock por ahora, "
         "te recomiendo otro modelo.")
    dets = VS.detectar_stock_contradicho(r, EVIDENCIA)
    assert len(dets) == 1
    assert dets[0]["clase"] == "sin_stock_falso"
    assert dets[0]["id"] == "TEC0010"
    assert dets[0]["stock"] == 5


def test_afirma_stock_de_producto_agotado_se_detecta():
    """El otro flanco: ofrecer como disponible un producto con stock 0."""
    r = "El Teclado HyperX Alloy Origins esta disponible, te lo reservo?"
    dets = VS.detectar_stock_contradicho(r, EVIDENCIA)
    assert len(dets) == 1
    assert dets[0]["clase"] == "con_stock_falso"
    assert dets[0]["id"] == "TEC0020"


def test_negacion_verdadera_no_dispara():
    """Decir que un producto agotado no tiene stock es HONESTIDAD, no mentira."""
    r = "El Teclado HyperX Alloy Origins no tiene stock en este momento."
    assert VS.detectar_stock_contradicho(r, EVIDENCIA) == []


def test_condicional_no_dispara():
    """'si no tiene stock te aviso' es hipotetico, no una afirmacion."""
    r = ("Te reservo el Teclado Redragon Kumara; si no tiene stock "
         "al despachar, te aviso.")
    assert VS.detectar_stock_contradicho(r, EVIDENCIA) == []


def test_ancla_ambigua_no_dispara():
    """Dos productos nombrados en la ventana -> ambiguo, no se acusa a ninguno."""
    r = ("Entre el Teclado Redragon Kumara y el Teclado HyperX Alloy "
         "no tiene stock ninguno.")
    assert VS.detectar_stock_contradicho(r, EVIDENCIA) == []


def test_sin_producto_nombrado_no_dispara():
    """Una frase de stock sin producto anclado no se puede juzgar: no se toca."""
    r = "Ese modelo no tiene stock."
    assert VS.detectar_stock_contradicho(r, EVIDENCIA) == []


def test_variante_de_color_nombrada_dispara():
    """Dos variantes del mismo modelo en evidencia (Negro con stock, Blanco sin):
    la nombrada con su color matchea MAS tokens y gana el desempate. Antes las
    dos variantes dejaban el ancla ambigua y la mentira pasaba (visto en el
    banco: ofrecio el DX-110 Blanco agotado como disponible con 11 en stock)."""
    ev = [_prod("MOU0023", "Mouse Genius DX-110 Negro", 11),
          _prod("MOU0024", "Mouse Genius DX-110 Blanco", 0)]
    r = "Tenemos el Mouse Genius DX-110 Blanco disponible, te lo sumo?"
    dets = VS.detectar_stock_contradicho(r, ev)
    assert [d["id"] for d in dets] == ["MOU0024"]
    assert dets[0]["clase"] == "con_stock_falso"


def test_variante_de_color_cifra_se_corrige():
    """La cifra de stock de la variante nombrada se corrige por la real aunque
    la otra variante del modelo tambien este en la evidencia."""
    ev = [_prod("MOU0023", "Mouse Genius DX-110 Negro", 11),
          _prod("MOU0024", "Mouse Genius DX-110 Blanco", 0)]
    r = "Mouse Genius DX-110 Blanco - $8.500 (11 en stock)."
    fix = VS.corregir_unidades_stock(r, ev)
    assert fix["correcciones"] == [
        {"de": 11, "a": 0, "id": "MOU0024", "concepto": "stock"}]


def test_tenemos_el_producto_agotado_dispara():
    """'Tenemos el X' de un producto con stock 0 es la misma promesa falsa
    aunque no diga la palabra stock; el nombre viene DESPUES del verbo y lo
    ancla la ventana hacia adelante (visto en el banco)."""
    ev = [_prod("MOU0023", "Mouse Genius DX-110 Negro", 11),
          _prod("MOU0024", "Mouse Genius DX-110 Blanco", 0)]
    r = "Tenemos el Mouse Genius DX-110 Blanco, justo lo que buscas."
    dets = VS.detectar_stock_contradicho(r, ev)
    assert [d["id"] for d in dets] == ["MOU0024"]
    assert dets[0]["clase"] == "con_stock_falso"


def test_no_tenemos_el_agotado_no_dispara():
    """'No lo tenemos' de un agotado es honestidad: la negacion pegada al
    match lo apaga."""
    ev = [_prod("MOU0024", "Mouse Genius DX-110 Blanco", 0)]
    r = "No lo tenemos al Mouse Genius DX-110 Blanco por ahora."
    assert VS.detectar_stock_contradicho(r, ev) == []


def test_sin_stock_con_nombre_despues_dispara():
    """'No hay stock del X' con el nombre despues del verbo: ancla adelante."""
    ev = [_prod("MOU0023", "Mouse Genius DX-110 Negro", 11)]
    r = "Uf, no hay stock del Mouse Genius DX-110 Negro, te paso otro."
    dets = VS.detectar_stock_contradicho(r, ev)
    assert [d["id"] for d in dets] == ["MOU0023"]
    assert dets[0]["clase"] == "sin_stock_falso"


def test_empate_real_sigue_ambiguo():
    """Si ninguna variante junta mas tokens que la otra (ninguno de los dos
    colores esta en la ventana), sigue siendo ambiguo y no se acusa a nadie."""
    ev = [_prod("MOU0023", "Mouse Genius DX-110 Negro", 11),
          _prod("MOU0024", "Mouse Genius DX-110 Blanco", 0)]
    r = "El Mouse Genius DX-110 no tiene stock."
    assert VS.detectar_stock_contradicho(r, ev) == []


# ── Safe-override de la CIFRA de unidades ────────────────────────────────────

def test_cifra_de_unidades_equivocada_se_corrige():
    """'quedan 9' cuando el catalogo dice 5: se reescribe la cifra, solo la
    cifra, con el resto del texto intacto (edicion minima)."""
    r = "Del Teclado Redragon Kumara quedan 9 unidades, aprovechalo."
    fix = VS.corregir_unidades_stock(r, EVIDENCIA)
    assert fix["correcciones"] == [
        {"de": 9, "a": 5, "id": "TEC0010", "concepto": "stock"}]
    assert "quedan 5 unidades" in fix["respuesta"]
    assert "aprovechalo" in fix["respuesta"]


def test_cifra_correcta_no_se_toca():
    r = "Del Mouse Logitech G203 Negro hay 3 en stock."
    fix = VS.corregir_unidades_stock(r, EVIDENCIA)
    assert fix["correcciones"] == []
    assert fix["respuesta"] == r


def test_cantidad_pedida_no_es_stock():
    """'te confirmo 10 unidades' es la CANTIDAD del pedido, no una afirmacion de
    stock: sin cue de disponibilidad no se corrige (era el falso positivo)."""
    r = "Te confirmo 10 unidades del Mouse Logitech G203 Negro para tu pedido."
    fix = VS.corregir_unidades_stock(r, EVIDENCIA)
    assert fix["correcciones"] == []


def test_quedan_dias_no_es_stock():
    """'quedan 3 dias de oferta' no es una cifra de stock."""
    r = "Del Mouse Logitech G203 Negro te aviso: quedan 3 dias de oferta."
    fix = VS.corregir_unidades_stock(r, EVIDENCIA)
    assert fix["correcciones"] == []


def test_instruccion_de_reescritura_lleva_el_dato_real():
    dets = [{"clase": "sin_stock_falso", "id": "TEC0010",
             "nombre": "Teclado Redragon Kumara K552", "stock": 5}]
    instr = VS.instruccion_stock(dets)
    assert "Teclado Redragon Kumara K552" in instr
    assert "5" in instr


# ── Guia determinista: el "mas barato con stock" lo computa el codigo ────────

def test_mas_barato_con_stock_por_categoria(firestore_doble):
    """El codigo computa el mas barato CON stock de una categoria: nunca uno
    agotado, nunca elegido por el modelo."""
    from app.core.guia_compra import mas_barato_con_stock
    from app.core.tools import get_all_products

    p = mas_barato_con_stock(categoria="mouse")
    assert p is not None and p["stock"] > 0 and p["categoria"] == "mouse"
    reales = [x for x in get_all_products()
              if x["categoria"] == "mouse" and x.get("stock", 0) > 0]
    assert p["precio_ars"] == min(x["precio_ars"] for x in reales)


def test_guia_mas_barato_trae_id_y_marcador(firestore_doble):
    """La guia inyectable trae el id real como [[PROD:id]] para que el estampado
    ponga nombre+precio+stock de la fuente."""
    from app.core.guia_compra import guia_mas_barato

    guia = guia_mas_barato("quiero el mouse mas barato", productos_vistos=[])
    assert guia and "[[PROD:" in guia
    assert "mas barato CON STOCK" in guia


# ── Cuarentena determinista (red cuando la reescritura LLM deja la mentira) ──

def test_cuarentena_poda_la_linea_contradicha():
    """La linea entera con la afirmacion falsa se poda; el resto del mensaje
    queda intacto (mismo patron que la cuarentena de la guardia)."""
    ev = [_prod("MOU0023", "Mouse Genius DX-110 Negro", 11),
          _prod("MOU0024", "Mouse Genius DX-110 Blanco", 0)]
    r = ("Buenas!\n"
         "Tenemos el Mouse Genius DX-110 Blanco disponible, te lo reservo?\n"
         "El Mouse Genius DX-110 Negro tiene 11 en stock.")
    poda = VS.cuarentena_stock(r, ev)
    assert "Blanco" not in poda
    assert "Negro" in poda and "Buenas!" in poda
    assert VS.detectar_stock_contradicho(poda, ev) == []


def test_cuarentena_devuelve_vacio_si_todo_era_mentira():
    ev = [_prod("MOU0024", "Mouse Genius DX-110 Blanco", 0)]
    r = "Tenemos el Mouse Genius DX-110 Blanco disponible."
    assert VS.cuarentena_stock(r, ev) == ""


def test_producto_duplicado_en_evidencia_no_es_ambiguedad():
    """El mismo producto entra a la evidencia por varios caminos (mostrado +
    nombrado + busqueda del turno): dos entradas identicas no son ambiguedad y
    el ancla exacta sigue firmando (bug visto en el banco: el duplicado
    tumbaba el ancla y la oferta del Blanco agotado pasaba)."""
    b = _prod("MOU0024", "Mouse Genius DX-110 Blanco", 0)
    ev = [b, dict(b), _prod("MOU0050", "Mouse Genius NX-7000 Blanco", 18)]
    r = "Tenemos el mismo modelo en blanco:\n\nMouse Genius DX-110 Blanco - $8.500"
    dets = VS.detectar_stock_contradicho(r, ev)
    assert [d["id"] for d in dets] == ["MOU0024"]


def test_negacion_honesta_no_acusa_a_la_alternativa_siguiente():
    """'no tiene stock. Mira estas opciones: Y...': la alternativa ofrecida en
    la ORACION siguiente no se ancla a la negacion (falso positivo visto en el
    banco, acusaba sin_stock_falso al producto CON stock que se ofrecia)."""
    ev = [_prod("MOU0024", "Mouse Genius DX-110 Blanco", 0),
          _prod("MOU0031", "Mouse Glorious Model O Negro", 23)]
    r = ("Uf, el blanco no tiene stock por ahora. "
         "Pero mira estas opciones: Mouse Glorious Model O Negro - $95.000.")
    assert VS.detectar_stock_contradicho(r, ev) == []


# ── Guarda de VARIANTE por COLOR (falso positivo real del solver Gemini) ──────
def _prodc(pid, nombre, stock, color, precio=10000):
    """Como _prod pero con el campo `color` que trae el catalogo real."""
    d = _prod(pid, nombre, stock, precio)
    d["color"] = color
    return d


_EV_COLOR = [_prodc("TEC0020", "Teclado Genius KB-110X Blanco", 11, "Blanco"),
             _prodc("TEC0021", "Teclado Genius KB-110X Negro", 0, "Negro")]


def test_color_otra_variante_sin_stock_no_acusa_al_nombrado():
    """Gemini honesto: el blanco tiene stock, el negro NO. El ancla cae al
    Blanco nombrado, pero la clausula del 'sin stock' habla del NEGRO -> es otra
    variante y no se acusa al Blanco (falso positivo real del solver Gemini)."""
    r = ("El Teclado Genius KB-110X Blanco a $12.000. "
         "El de color negro esta sin stock en este momento.")
    assert VS.detectar_stock_contradicho(r, _EV_COLOR) == []


def test_color_otra_variante_agotado_pegado_no_acusa():
    """Mismo caso con 'agotado' pegado tras el nombre del producto con stock."""
    r = "Te llevo el Teclado Genius KB-110X Blanco, ojo que el negro esta agotado."
    assert VS.detectar_stock_contradicho(r, _EV_COLOR) == []


def test_color_mismo_niega_stock_real_sigue_disparando():
    """La guarda de color NO tapa la mentira real: negar stock del Blanco, que SI
    tiene, con el color Blanco pegado a la negacion, sigue disparando."""
    r = "El Teclado Genius KB-110X Blanco no tiene stock ahora."
    dets = VS.detectar_stock_contradicho(r, _EV_COLOR)
    assert [d["id"] for d in dets] == ["TEC0020"]
    assert dets[0]["clase"] == "sin_stock_falso"


def test_color_mismo_ofrece_agotado_sigue_disparando():
    """Ofrecer el Negro (agotado) como disponible, con su color, sigue cazandose."""
    r = "Tenemos el Teclado Genius KB-110X Negro disponible para vos."
    dets = VS.detectar_stock_contradicho(r, _EV_COLOR)
    assert [d["id"] for d in dets] == ["TEC0021"]
    assert dets[0]["clase"] == "con_stock_falso"


def test_token_substring_no_ancla_producto_ausente():
    """Falso positivo 13-jul: 'model' (token del Glorious Model O) matcheaba
    por SUBSTRING adentro de la palabra 'modelo', y con 'blanco' llegaba al
    umbral de 2 tokens: acusaba sin_stock_falso a un producto que NO estaba en
    el texto. Los tokens anclan con limite de palabra."""
    ev = [_prodc("MOU0023", "Mouse Genius DX-110 Negro", 11, "Negro"),
          _prodc("MOU0024", "Mouse Genius DX-110 Blanco", 0, "Blanco"),
          _prodc("MOU0028", "Mouse Glorious Model O Blanco", 23, "Blanco")]
    r = ("El Mouse Genius DX-110 (Negro) es un clasico de cable, comodo y "
         "preciso. Tiene garantia oficial. (Nota: el color blanco de este "
         "modelo actualmente esta sin stock).")
    assert VS.detectar_stock_contradicho(r, ev) == []
