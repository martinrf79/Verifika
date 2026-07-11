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
    assert set(item["required"]) == {"tipo", "argumento"}


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
