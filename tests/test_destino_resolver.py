"""
TESTS de resolver_destino y coercionar_destinos (refactor completo 24-jul).

Cubre los criterios de aceptación del problem statement:
  1. Destino nuevo T1: declarado en mensaje, real en geo_cp → validado_nuevo.
  2. Confirmación T2 sin repetir destino: en memoria → validado_memoria;
     el radar interpretador_destino_fantasma NO dispara.
  3. Dos destinos que sobreviven a T2.
  4. Destino nuevo T2 que no borra T1.
  5. Lugar real en geo_cp pero nunca declarado → no_respaldado.
  6. Destino inventado por el intérprete → no_respaldado.
  7. Variante ortográfica / mayúsculas / comas → canonizada y aceptada.
  8. Localidad ambigua entre provincias → ambiguo (declarada en mensaje)
     o no_respaldado (no declarada).
  9. Corrección explícita: destino nuevo en mensaje reemplaza al viejo en pedido.
 10. Multidestino: coercionar_destinos con varios renglones.
 11. Provincia sticky desambigua una localidad ambigua.
 12. Estado vacío / None no crashea.

Todos son offline (sin LLM, sin Firestore real).
"""
import pytest


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def limpia_estado():
    """Asegura que el estado de venta está vacío antes y después de cada test."""
    from app.core.estado_venta import set_current_estado
    set_current_estado({})
    yield
    set_current_estado(None)


@pytest.fixture(autouse=True)
def _carga_geo():
    """Pre-carga la tabla geo_cp una vez por sesión de tests."""
    from app.core import geo_cp
    geo_cp._cargar()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _resolver(texto, mensaje="", memoria=None, provincia=""):
    from app.core.destino_resolver import resolver_destino
    return resolver_destino(
        texto=texto,
        mensaje_actual=mensaje,
        memoria_destinos=memoria or [],
        provincia_sticky=provincia,
    )


def _coercionar(pedido_items, mensaje, localidades_envio=None, provincia_envio=""):
    from app.core.interpretador import coercionar_destinos
    from app.core.estado_venta import set_current_estado
    set_current_estado({
        "localidades_envio": localidades_envio or [],
        "provincia_envio": provincia_envio,
    })
    resultado = {"pedido": list(pedido_items)}
    coercionar_destinos(resultado, mensaje)
    return resultado["pedido"]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Destino nuevo T1 — declarado en mensaje, real en geo_cp
# ═══════════════════════════════════════════════════════════════════════════════

def test_destino_nuevo_t1_validado_nuevo():
    """Palpalá dicha en el mensaje, sin memoria previa → validado_nuevo."""
    res = _resolver("palpala", mensaje="quiero envio a palpala jujuy")
    assert res["estado"] == "validado_nuevo"
    assert res["localidad_canonica"] == "palpala"
    assert res["provincia"] == "jujuy"


def test_destino_nuevo_t1_con_provincia_en_destino():
    """El intérprete extrae 'palpala jujuy' como destino, el cliente dijo 'palpala'."""
    res = _resolver("palpala jujuy", mensaje="quiero envio a palpala")
    # El loc_canon "palpala" está en el mensaje → validado_nuevo
    assert res["estado"] == "validado_nuevo"
    assert res["localidad_canonica"] == "palpala"


def test_destino_nuevo_t1_unambiguo_interior():
    """Localidad inequívoca del interior sin provincias → validado_nuevo."""
    res = _resolver("serodino", mensaje="envio a serodino")
    assert res["estado"] == "validado_nuevo"
    assert res["provincia"] == "santa fe"


def test_destino_nuevo_t1_provincia_sola():
    """Solo se menciona la provincia (sin localidad específica) → validado_nuevo."""
    res = _resolver("cordoba", mensaje="envio a cordoba")
    assert res["estado"] == "validado_nuevo"
    assert res["provincia"] == "cordoba"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Confirmación T2 sin repetir destino — destino de memoria sobrevive
# ═══════════════════════════════════════════════════════════════════════════════

def test_confirmacion_t2_destino_de_memoria():
    """'dale, confirmalo' no nombra destinos pero Palpalá está en memoria → validado_memoria."""
    res = _resolver(
        "palpala jujuy",
        mensaje="dale, confirmalo",
        memoria=["palpala jujuy"],
    )
    assert res["estado"] == "validado_memoria"


def test_confirmacion_t2_no_nula_el_destino():
    """coercionar_destinos NO anula el destino cuando está en memoria."""
    pedido = _coercionar(
        [{"producto": "notebook", "cantidad": 1, "destino": "Palpalá, Jujuy"}],
        mensaje="dale, confirmalo",
        localidades_envio=["palpala jujuy"],
    )
    assert pedido[0]["destino"] == "Palpalá, Jujuy"


def test_radar_fantasma_no_dispara_para_destino_de_memoria(caplog):
    """El log interpretador_destino_fantasma NO aparece para destinos legítimos."""
    import logging
    with caplog.at_level(logging.WARNING, logger="app.core.interpretador"):
        _coercionar(
            [{"producto": "mouse", "cantidad": 1, "destino": "palpala jujuy"}],
            mensaje="confirmalo",
            localidades_envio=["palpala jujuy"],
        )
    assert "interpretador_destino_fantasma" not in caplog.text


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Dos destinos que sobreviven a T2
# ═══════════════════════════════════════════════════════════════════════════════

def test_dos_destinos_t1_sobreviven_en_t2():
    """Dos destinos de memoria sobreviven intactos en T2 (confirmación).
    Se usan localidades inequívocas (rio tercero, serodino) para evitar
    que _canonizar_destinos_cp las divida en sub-renglones."""
    pedido = _coercionar(
        [
            {"producto": "notebook", "cantidad": 1, "destino": "palpala jujuy"},
            {"producto": "teclado", "cantidad": 1, "destino": "rio tercero"},
        ],
        mensaje="dale, confirmalo",
        localidades_envio=["palpala jujuy", "rio tercero"],
    )
    destinos = [it["destino"] for it in pedido]
    assert "palpala jujuy" in destinos
    assert "rio tercero" in destinos


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Destino nuevo T2 no borra T1
# ═══════════════════════════════════════════════════════════════════════════════

def test_destino_nuevo_t2_no_borra_t1():
    """En T2, destino de memoria (T1) + destino nuevo en mensaje: ambos válidos."""
    pedido = _coercionar(
        [
            {"producto": "notebook", "cantidad": 1, "destino": "palpala jujuy"},
            {"producto": "mouse", "cantidad": 1, "destino": "rio cuarto"},
        ],
        mensaje="y también pasalo a rio cuarto, cordoba",
        localidades_envio=["palpala jujuy"],
    )
    # palpala: en memoria → validado_memoria → sobrevive
    assert pedido[0]["destino"] == "palpala jujuy"
    # rio cuarto: en mensaje → validado_nuevo → sobrevive
    assert pedido[1]["destino"] == "rio cuarto"


# ═══════════════════════════════════════════════════════════════════════════════
# 5 & 6. Lugar real en geo_cp no declarado → rechazado
# ═══════════════════════════════════════════════════════════════════════════════

def test_lugar_real_no_declarado_es_rechazado():
    """Rosario existe en geo_cp pero el cliente nunca lo mencionó → no_respaldado."""
    res = _resolver("Rosario", mensaje="quiero un mouse barato", memoria=[])
    assert res["estado"] == "no_respaldado"


def test_destino_inventado_se_anula():
    """coercionar_destinos anula el destino inventado por el intérprete."""
    pedido = _coercionar(
        [{"producto": "mouse", "cantidad": 1, "destino": "Rosario"}],
        mensaje="quiero un mouse barato",
        localidades_envio=[],
    )
    assert pedido[0]["destino"] is None


def test_inventado_con_provincia_no_declarada():
    """'Córdoba Capital' existe en geo_cp pero no fue mencionada → rechazado."""
    res = _resolver(
        "cordoba capital",
        mensaje="dame el precio más barato",
        memoria=[],
    )
    # cordoba y capital federal son alias de provincia; 'cordoba' es prov real.
    # No está en el mensaje → no_respaldado.
    assert res["estado"] in ("no_respaldado", "no_encontrado")


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Variante ortográfica canonizada
# ═══════════════════════════════════════════════════════════════════════════════

def test_tilde_y_mayusculas_aceptadas():
    """'Palpalá, Jujuy' (con tilde y coma) se acepta si el mensaje dice 'palpala'."""
    res = _resolver(
        "Palpalá, Jujuy",
        mensaje="envio a palpala",
        memoria=[],
    )
    # El loc_canon 'palpala' está en el mensaje → validado_nuevo
    assert res["estado"] == "validado_nuevo"
    assert res["localidad_canonica"] == "palpala"


def test_sin_tilde_en_mensaje_acepta_destino_con_tilde():
    """Mensaje sin tilde ('palpala jujuy') acepta destino interpretado con tilde."""
    pedido = _coercionar(
        [{"producto": "mouse", "cantidad": 1, "destino": "Palpalá, Jujuy"}],
        mensaje="envio todo a palpala jujuy",
    )
    assert pedido[0]["destino"] == "Palpalá, Jujuy"


def test_variante_ortografica_en_memoria():
    """Memoria tiene 'palpala jujuy'; destino es 'Palpalá, Jujuy' → validado_memoria."""
    res = _resolver(
        "Palpalá, Jujuy",
        mensaje="dale",
        memoria=["palpala jujuy"],
    )
    assert res["estado"] == "validado_memoria"


def test_destino_normalizado_monte_ralo_con_provincia():
    """'Monte Ralo, Córdoba' declarado en mensaje → validado_nuevo, canonizado."""
    res = _resolver(
        "Monte Ralo, Córdoba",
        mensaje="envio a monte ralo, cordoba",
        memoria=[],
    )
    assert res["estado"] == "validado_nuevo"
    assert res["localidad_canonica"] == "monte ralo"
    assert res["provincia"] == "cordoba"


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Ambigüedad entre provincias
# ═══════════════════════════════════════════════════════════════════════════════

def test_ambiguo_declarado_en_mensaje():
    """Isla Verde declarada en el mensaje pero ambigua → estado 'ambiguo' (no rechazada)."""
    res = _resolver(
        "Isla Verde",
        mensaje="envio a Isla Verde",
        memoria=[],
        provincia="",
    )
    assert res["estado"] == "ambiguo"
    assert res["localidad_canonica"] == "isla verde"


def test_ambiguo_no_declarado_es_rechazado():
    """Isla Verde existe pero el cliente nunca la mencionó → no_respaldado."""
    res = _resolver(
        "Isla Verde",
        mensaje="quiero 2 mouse",
        memoria=[],
    )
    assert res["estado"] == "no_respaldado"


def test_provincia_sticky_desambigua():
    """Monte Ralo es ambigua (Córdoba / La Pampa); sticky 'cordoba' la resuelve."""
    res = _resolver(
        "Monte Ralo",
        mensaje="envio a monte ralo",
        memoria=[],
        provincia="cordoba",
    )
    assert res["estado"] == "validado_nuevo"
    assert res["provincia"] == "cordoba"
    assert res["localidad_canonica"] == "monte ralo"


def test_provincia_sticky_desambigua_desde_memoria():
    """Destino ambiguo en memoria se desambigua con provincia sticky."""
    res = _resolver(
        "Monte Ralo",
        mensaje="dale confirmalo",
        memoria=["monte ralo"],
        provincia="cordoba",
    )
    assert res["estado"] == "validado_memoria"
    assert res["provincia"] == "cordoba"


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Corrección explícita: destino nuevo en T2 pisa el anterior en el pedido
# ═══════════════════════════════════════════════════════════════════════════════

def test_correccion_explicita_destino():
    """Mensaje T2 tiene nuevo destino 'cordoba'; el anterior 'palpala' vino de memoria.
    Ambos sobreviven en sus respectivos renglones."""
    pedido = _coercionar(
        [
            {"producto": "notebook", "cantidad": 1, "destino": "palpala jujuy"},
            {"producto": "teclado", "cantidad": 1, "destino": "cordoba"},
        ],
        mensaje="no, cambialo, el teclado va a cordoba",
        localidades_envio=["palpala jujuy"],
    )
    # palpala está en memoria → sobrevive
    assert pedido[0]["destino"] == "palpala jujuy"
    # cordoba está en el mensaje nuevo → sobrevive
    assert pedido[1]["destino"] == "cordoba"


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Multidestino: coercionar_destinos con varios renglones
# ═══════════════════════════════════════════════════════════════════════════════

def test_multidestino_tres_renglones():
    """Tres destinos declarados en mensaje → los tres sobreviven.
    Se usan localidades inequívocas (palpala jujuy, serodino, rio cuarto)
    para evitar que _canonizar_destinos_cp las divida en sub-renglones."""
    pedido = _coercionar(
        [
            {"producto": "notebook", "cantidad": 1, "destino": "palpala jujuy"},
            {"producto": "teclado", "cantidad": 1, "destino": "serodino"},
            {"producto": "auriculares", "cantidad": 1, "destino": "rio cuarto"},
        ],
        mensaje=(
            "un notebook a palpala jujuy, un teclado a serodino "
            "y los auriculares a rio cuarto"
        ),
    )
    destinos = [it["destino"] for it in pedido]
    assert "palpala jujuy" in destinos
    assert "serodino" in destinos
    assert "rio cuarto" in destinos


def test_multidestino_parcial_inventado():
    """Dos destinos reales + uno inventado: solo el inventado se anula."""
    pedido = _coercionar(
        [
            {"producto": "notebook", "cantidad": 1, "destino": "palpala jujuy"},
            {"producto": "teclado", "cantidad": 1, "destino": "Bahia Blanca"},  # no dicho
            {"producto": "auriculares", "cantidad": 1, "destino": "rio cuarto"},
        ],
        mensaje="notebook a palpala jujuy y auriculares a rio cuarto",
    )
    assert pedido[0]["destino"] == "palpala jujuy"
    assert pedido[1]["destino"] is None  # Bahia Blanca: real pero no declarada
    assert pedido[2]["destino"] == "rio cuarto"


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Estado vacío / None no crashea
# ═══════════════════════════════════════════════════════════════════════════════

def test_estado_vacio_no_crashea():
    """resolver_destino y coercionar_destinos toleran estado None / listas vacías."""
    from app.core.destino_resolver import resolver_destino
    from app.core.estado_venta import set_current_estado

    # resolver_destino directo con datos vacíos
    res = resolver_destino("", "", [], "")
    assert res["estado"] == "no_encontrado"
    assert res["localidad_canonica"] is None

    # coercionar_destinos con estado None
    set_current_estado(None)
    from app.core.interpretador import coercionar_destinos
    r = {"pedido": [{"producto": "mouse", "cantidad": 1, "destino": "palpala"}]}
    coercionar_destinos(r, "envio a palpala")
    # No crashea; el destino puede o no sobrevivir dependiendo del estado


def test_destino_sin_campo_destino_no_toca():
    """Renglones sin campo destino no se modifican."""
    pedido = _coercionar(
        [{"producto": "mouse", "cantidad": 2}],
        mensaje="quiero 2 mouse",
    )
    assert "destino" not in pedido[0] or pedido[0].get("destino") is None


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Campo localidad_envio singular (legado) no contamina la memoria
# ═══════════════════════════════════════════════════════════════════════════════

def test_campo_singular_legado_no_valida_destino():
    """El campo 'localidad_envio' singular (legado) NO debe rescatar un destino
    que no está en 'localidades_envio' (plural).  El bug del 24-jul era que
    coercionar_destinos leía el campo legado y aceptaba destinos no declarados."""
    from app.core.interpretador import coercionar_destinos
    from app.core.estado_venta import set_current_estado

    # Estado con el campo SINGULAR legado pero NO el plural
    set_current_estado({
        "localidad_envio": "rosario",   # campo singular legado
        "localidades_envio": [],         # correcto: vacío
        "provincia_envio": "",
    })
    r = {"pedido": [{"producto": "mouse", "cantidad": 1, "destino": "Rosario"}]}
    coercionar_destinos(r, "quiero un mouse barato")
    set_current_estado(None)

    # Rosario no está en el mensaje ni en localidades_envio (plural) → fantasma
    assert r["pedido"][0]["destino"] is None


def test_campo_plural_si_valida_destino():
    """El campo 'localidades_envio' (plural, correcto) sí rescata el destino."""
    from app.core.interpretador import coercionar_destinos
    from app.core.estado_venta import set_current_estado

    set_current_estado({
        "localidades_envio": ["palpala jujuy"],  # campo plural correcto
        "provincia_envio": "",
    })
    r = {"pedido": [{"producto": "notebook", "cantidad": 1,
                     "destino": "Palpalá, Jujuy"}]}
    coercionar_destinos(r, "dale, confirmalo")
    set_current_estado(None)

    assert r["pedido"][0]["destino"] == "Palpalá, Jujuy"


# ═══════════════════════════════════════════════════════════════════════════════
# 13. es_destino_valido helper
# ═══════════════════════════════════════════════════════════════════════════════

def test_es_destino_valido_helper():
    from app.core.destino_resolver import es_destino_valido, ESTADOS_VALIDOS, ESTADOS_FANTASMA
    for estado in ESTADOS_VALIDOS:
        assert es_destino_valido({"estado": estado})
    for estado in ESTADOS_FANTASMA:
        assert not es_destino_valido({"estado": estado})
