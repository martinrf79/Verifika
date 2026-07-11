"""
AREA: SELECTOR del menu cerrado (decision 10-jul, construido 11-jul).

Logica pura offline: validar_plan (el filtro del JSON del LLM) y la
ejecucion del plan por el compositor (cada tipo del menu mapea a una
seccion determinista que arma el codigo desde la fuente). La llamada LLM
en si se prueba con el banco vivo.
"""
from app.core.selector import validar_plan, TIPOS_MENU, _schema_selector
from app.core.compositor import componer


def test_validar_plan_filtra_basura():
    d = {"secciones": [
        {"tipo": "ficha_producto", "argumento": "Mouse M170"},
        {"tipo": "inventado", "argumento": None},
        {"tipo": "faq", "argumento": None},
        {"tipo": "faq", "argumento": "otro"},  # tipo repetido: fuera
        "no soy dict",
    ]}
    plan = validar_plan(d)
    assert plan == [
        {"tipo": "ficha_producto", "argumento": "Mouse M170"},
        {"tipo": "faq", "argumento": None},
    ]


def test_validar_plan_tope_tres():
    d = {"secciones": [{"tipo": t, "argumento": None}
                       for t in ("saludo", "faq", "envio", "rechazo")]}
    assert len(validar_plan(d)) == 3


def test_validar_plan_vacio_none():
    assert validar_plan({"secciones": []}) is None
    assert validar_plan(None) is None
    assert validar_plan({"secciones": [{"tipo": "cualquiera",
                                        "argumento": None}]}) is None


def test_schema_estricto_bien_formado():
    s = _schema_selector()
    item = s["properties"]["secciones"]["items"]
    assert item["properties"]["tipo"]["enum"] == list(TIPOS_MENU)
    assert item["additionalProperties"] is False
    # v2: los argumentos estructurados de calcular_pedido tambien requeridos
    # (strict de OpenAI exige todo campo en required; van null si no aplican).
    assert set(item["required"]) == {"tipo", "argumento", "items",
                                     "destinos", "pago"}


def test_plan_ficha_produce_ficha(firestore_doble):
    plan = [{"tipo": "ficha_producto",
             "argumento": "Mouse Logitech M170 Negro"}]
    texto, meta = componer("cerrame con el mouse que te dije",
                           {}, {}, "verifika_prod", plan=plan)
    assert "M170" in texto and "$" in texto


def test_plan_categoria_y_envio_en_orden(firestore_doble):
    plan = [{"tipo": "opciones_categoria", "argumento": "teclado"},
            {"tipo": "envio", "argumento": None}]
    texto, _ = componer("tenes teclados? llega a Cordoba capital?",
                        {}, {}, "verifika_prod", plan=plan)
    assert "De teclado tengo" in texto
    assert "envío" in texto.lower()
    assert texto.index("teclado") < texto.lower().index("envío a")


def test_plan_argumento_que_no_reconcilia_cae_a_cascada(firestore_doble):
    # Un plan cuyo argumento no respalda (producto inexistente) no produce
    # texto: cae a la cascada y el turno no queda mudo.
    plan = [{"tipo": "ficha_producto", "argumento": "Producto Inventado XZ9"}]
    interp = {"intencion": "pregunta_especifica", "candidatos": [],
              "producto_resuelto": None, "confianza": 0.5}
    texto, _ = componer("hacen factura A?", interp, {}, "verifika_prod",
                        plan=plan)
    assert texto  # respondio la cascada (la FAQ de factura)
    assert "factura" in texto.lower()


def test_plan_preguntar_texto_fijo(firestore_doble):
    plan = [{"tipo": "preguntar", "argumento": "destino de envio"}]
    texto, _ = componer("y cuanto sale el envio?", {}, {}, "verifika_prod",
                        plan=plan)
    assert "localidad y provincia" in texto


def test_plan_not_found_validado_contra_catalogo(firestore_doble):
    # El selector pide not_found de algo que SI existe: la validacion contra
    # catalogo lo frena y cae a la cascada (jamas 'no trabajamos mouse').
    plan = [{"tipo": "not_found", "argumento": "mouse"}]
    texto, _ = componer("tenes mouse?", {"candidatos": ["mouse"]}, {},
                        "verifika_prod", plan=plan)
    assert "no trabajamos" not in texto


def test_plan_movida_emocional_manda_sobre_plan(firestore_doble):
    # Una queja rutea B17 ANTES del plan: regla de negocio, no eleccion.
    interp = {"intencion": "otra", "candidatos": [], "producto_resuelto": None,
              "confianza": 0.8}
    plan = [{"tipo": "opciones_categoria", "argumento": "mouse"}]
    texto, _ = componer("es una verguenza, nadie me responde",
                        interp, {}, "verifika_prod", plan=plan)
    assert "disculpas" in texto.lower()
    assert "De mouse tengo" not in texto


# --- SELECTOR v2: la primitiva calcular_pedido (11-jul) ---

_ESTADO_V2 = {
    "carrito": [
        {"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro",
         "cantidad": 2},
        {"id": "TEC0020", "nombre": "Teclado Genius KB-110X Blanco",
         "cantidad": 2},
    ],
    "productos_vistos": [
        {"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro",
         "precio": 8500},
        {"id": "TEC0020", "nombre": "Teclado Genius KB-110X Blanco",
         "precio": 12000},
    ],
    "localidades_envio": ["rosario"],
}


def test_validar_plan_v2_argumentos_estructurados():
    d = {"secciones": [{
        "tipo": "calcular_pedido", "argumento": None,
        "items": [{"producto": "Mouse Genius DX-110 Negro", "cantidad": 1,
                   "destino": None}],
        "destinos": ["salta"],
        "pago": [{"medio": "transferencia", "porcentaje": 50},
                 {"medio": "mercado pago", "porcentaje": 50}]}]}
    plan = validar_plan(d)
    assert plan[0]["items"][0]["producto"] == "Mouse Genius DX-110 Negro"
    assert plan[0]["destinos"] == ["salta"]
    assert plan[0]["pago"][0]["porcentaje"] == 50


def test_plan_calculo_split_sobre_carrito(firestore_doble):
    from app.core.estado_venta import set_current_estado
    set_current_estado(dict(_ESTADO_V2))
    plan = [{"tipo": "calcular_pedido", "argumento": None, "items": None,
             "destinos": None,
             "pago": [{"medio": "transferencia", "porcentaje": 50},
                      {"medio": "mercado pago", "porcentaje": 50}]}]
    texto, meta = componer("mitad y mitad como queda?", {},
                           dict(_ESTADO_V2), "verifika_prod", plan=plan)
    assert "Pago dividido" in texto
    assert "10% descuento" in texto
    # la mitad de Mercado Pago NO lleva descuento
    lineas_mp = [l for l in texto.splitlines() if "mercado pago" in l.lower()]
    assert lineas_mp and "descuento" not in lineas_mp[0]
    tools = [t["name"] for t in meta.get("tools_called", [])]
    assert "calculate_total" in tools


def test_plan_calculo_items_editados(firestore_doble):
    from app.core.estado_venta import set_current_estado
    set_current_estado(dict(_ESTADO_V2))
    plan = [{"tipo": "calcular_pedido", "argumento": None,
             "items": [{"producto": "Mouse Genius DX-110 Negro",
                        "cantidad": 1, "destino": None},
                       {"producto": "Teclado Genius KB-110X Blanco",
                        "cantidad": 3, "destino": None}],
             "destinos": None, "pago": None}]
    texto, _ = componer("dejame 1 mouse y 3 teclados", {},
                        dict(_ESTADO_V2), "verifika_prod", plan=plan)
    assert "1x Mouse Genius DX-110 Negro" in texto
    assert "3x Teclado Genius KB-110X Blanco" in texto


def test_plan_calculo_argumento_invalido_cae_a_cascada(firestore_doble):
    from app.core.estado_venta import set_current_estado
    set_current_estado(dict(_ESTADO_V2))
    # producto que no reconcilia con carrito/vistos: la primitiva NO corre
    plan = [{"tipo": "calcular_pedido", "argumento": None,
             "items": [{"producto": "Producto Fantasma Z", "cantidad": 1,
                        "destino": None}],
             "destinos": None, "pago": None}]
    texto, _ = componer("hacen factura A?", {"candidatos": []},
                        dict(_ESTADO_V2), "verifika_prod", plan=plan)
    assert "Pago dividido" not in texto and "Presupuesto" not in texto
    # porcentajes que no suman 100: tampoco
    plan2 = [{"tipo": "calcular_pedido", "argumento": None, "items": None,
              "destinos": None,
              "pago": [{"medio": "transferencia", "porcentaje": 60},
                       {"medio": "mercado pago", "porcentaje": 60}]}]
    texto2, _ = componer("hacen factura A?", {"candidatos": []},
                         dict(_ESTADO_V2), "verifika_prod", plan=plan2)
    assert "Pago dividido" not in texto2


def test_plan_calculo_destino_que_no_resuelve_escapa(firestore_doble):
    from app.core.estado_venta import set_current_estado
    set_current_estado(dict(_ESTADO_V2))
    plan = [{"tipo": "calcular_pedido", "argumento": None, "items": None,
             "destinos": ["localidad inventada xyz"], "pago": None}]
    texto, _ = componer("mandalo a localidad inventada xyz", {},
                        dict(_ESTADO_V2), "verifika_prod", plan=plan)
    assert "Presupuesto" not in texto
