"""
AREA: Cierre — captura de datos del cliente por regex (forma de pago, direccion).

Herramientas del bot cubiertas: extraer_forma_pago y extraer_direccion
(app/core/cierre.py).

PATRON DE ESTA AREA (plantilla del proyecto): los casos viven en una TABLA, no en
funciones repetidas. Agregar una forma nueva vista en WhatsApp es agregar una
FILA, no un archivo. Cada fila es (mensaje, esperado, id). Las que hoy fallan son
los errores confirmados; las que hoy pasan son locks que protegen lo que anda.

Errores sembrados:
  E8   Captura la forma de pago RECHAZADA en vez de la elegida.
  E9   'mp' de megapixeles se toma como Mercado Pago.
  E10  La direccion agarra 'mandar a 4 cuotas' como domicilio.
"""
import pytest

from app.core import cierre


# ── Forma de pago: (mensaje, forma esperada) ────────────────────────────────
CASOS_FORMA_PAGO = [
    # Errores confirmados (hoy ROJO):
    ("no quiero pagar con transferencia, prefiero efectivo", "efectivo"),  # E8
    ("la camara tiene 48 mp de resolucion", ""),                          # E9
    # Locks de camino feliz (hoy VERDE): protegen lo que funciona.
    ("lo pago con transferencia", "transferencia"),
    ("pago en efectivo", "efectivo"),
    ("con mercado pago", "mercado pago"),
]


@pytest.mark.parametrize("mensaje, esperado", CASOS_FORMA_PAGO)
def test_forma_pago(mensaje, esperado):
    assert cierre.extraer_forma_pago(mensaje) == esperado


# ── Direccion: (mensaje, fragmento esperado o "" si no debe capturar) ────────
CASOS_DIRECCION = [
    # Error confirmado (hoy ROJO): 'cuotas' no es un domicilio.
    ("me lo podes mandar a 4 cuotas?", ""),  # E10
    # Locks de camino feliz (hoy VERDE): una direccion real se captura.
    ("envio a la calle San Martin 1234, Cordoba", "1234"),
    ("mi casa es Av Colon 850", "850"),
]


@pytest.mark.parametrize("mensaje, fragmento", CASOS_DIRECCION)
def test_direccion(mensaje, fragmento):
    r = cierre.extraer_direccion(mensaje)
    if fragmento == "":
        assert r == "", "No debe capturar un domicilio donde no lo hay."
    else:
        assert fragmento in r, f"Debe capturar la direccion (contiene {fragmento})."


# ── D: gatillo del lead fuerte por la pregunta de cierre ─────────────────────
# El sistema hace UNA pregunta de cierre cuando ya hay intencion suficiente. La
# respuesta del cliente decide de forma determinista, sin depender de la
# confianza del LLM: cualquier respuesta que NO sea un no claro dispara el lead
# fuerte; un no lo toma un humano. Estos tests fijan ese gatillo. HOY fallan.

def test_d_pregunta_de_cierre_es_la_acordada():
    """La pregunta de cierre es la elegida con Martin: apunta a seguir con el
    pedido y dejarlo preparado, sin apurar el pago de frente."""
    from app.core import leads
    assert leads.PREGUNTA_CIERRE == (
        "¿Seguimos adelante con tu pedido así te lo dejo preparado?")


# (respuesta del cliente, es_no_interesado esperado)
CASOS_NO_INTERES = [
    ("no gracias", True),
    ("no, todavia no", True),
    ("no me interesa", True),
    ("ahora no", True),
    ("despues lo veo", True),
    ("mas adelante", True),
    # Afirmativas o neutras: NO son un no, disparan el lead.
    ("dale", False),
    ("si, avancemos", False),
    ("bueno, sigamos", False),
    ("obvio", False),
    ("listo, cerramos", False),
]


@pytest.mark.parametrize("respuesta, esperado", CASOS_NO_INTERES)
def test_d_detecta_no_interesado(respuesta, esperado):
    assert cierre.es_no_interesado(respuesta) is esperado


def test_d_dispara_lead_fuerte_solo_con_pregunta_hecha_y_sin_no():
    """El gatillo: hecha la pregunta, una respuesta que no sea un no dispara el
    lead fuerte. Sin pregunta previa no dispara; un no tampoco."""
    assert cierre.dispara_lead_fuerte(pregunta_hecha=True, respuesta="dale") is True
    assert cierre.dispara_lead_fuerte(
        pregunta_hecha=True, respuesta="no gracias") is False
    assert cierre.dispara_lead_fuerte(
        pregunta_hecha=False, respuesta="dale") is False


# (mensaje del cliente, es una pregunta o duda)
CASOS_PREGUNTA = [
    ("estas seguro que el envio llega a Santa Ana?", True),
    ("¿llega a Cordoba?", True),
    ("cuanto tarda el envio?", True),
    ("me lo confirmas?", True),
    ("en serio llega hasta alla", True),
    # Confirmaciones o datos: NO son preguntas, cierran.
    ("dale, cerremos", False),
    ("si, avancemos", False),
    ("listo, mi nombre es Juan Perez", False),
]


@pytest.mark.parametrize("mensaje, esperado", CASOS_PREGUNTA)
def test_d_detecta_pregunta_o_duda(mensaje, esperado):
    assert cierre.parece_pregunta(mensaje) is esperado


def test_d_una_duda_no_dispara_el_cierre():
    """El apuro real: el cliente pregunta '¿estas seguro que el envio llega a
    Santa Ana?' y el bot salta a pedir datos. Una duda NO es una confirmacion:
    no debe disparar el lead fuerte, el bot tiene que contestar la duda."""
    assert cierre.dispara_lead_fuerte(
        pregunta_hecha=True,
        respuesta="estas seguro que el envio llega a Santa Ana?") is False
    # Pero un dale despues sigue cerrando.
    assert cierre.dispara_lead_fuerte(
        pregunta_hecha=True, respuesta="dale, cerremos") is True


# ── Switch de version A/B del bot ────────────────────────────────────────────
# Dos versiones del producto, un solo lugar para prenderla:
#   Version A = lead fuerte, el bot capta y avisa, cierra un humano  -> modo 'lead'
#   Version B = el bot cierra la venta y manda el cobro              -> modo 'venta'
# Se configura poniendo "A" o "B" (o los nombres largos), asi es simple de flipear.

def test_switch_version_a_es_lead_y_b_es_venta():
    from app.core import leads
    assert leads._normalizar_modo("A") == "lead"
    assert leads._normalizar_modo("B") == "venta"
    assert leads._normalizar_modo("version b") == "venta"
    assert leads._normalizar_modo("opcion a") == "lead"
    # Los nombres internos siguen valiendo, sin romper lo que ya andaba.
    assert leads._normalizar_modo("lead") == "lead"
    assert leads._normalizar_modo("venta") == "venta"
    assert leads._normalizar_modo("off") == "off"
    # Un valor desconocido no inventa: devuelve "" y el llamador cae al default.
    assert leads._normalizar_modo("cualquiera") == ""


# ── VERSION A (modo 'lead'): el lead fuerte NO pide datos ─────────────────────
# El acuerdo con Martin: cuando el cliente confirma el cierre en modo 'lead', el
# bot capta el lead fuerte y avisa al dueño, pero NO le empieza a pedir datos
# (nombre, telefono, documento). Sigue conversando con el cliente. Estos tests
# fijan ese comportamiento sin Firestore ni LLM: se monkeypatchea la persistencia
# y la notificacion, y se verifica la DECISION de la capa de leads.

def _correr_lead_fuerte(monkeypatch, mensaje, datos_turno, modo,
                        lead_activo=None):
    """Corre procesar_mensaje_para_lead con persistencia y notificacion falsas.
    Devuelve (meta, updates, creado) para inspeccionar la decision."""
    import asyncio
    from app.core import leads as L

    creado: dict = {}
    updates: list = []

    def _fake_crear_lead(**kw):
        creado.update(kw)
        return "LEAD_TEST"

    async def _fake_notificar(**kw):
        creado.setdefault("_notificaciones", []).append(kw.get("estado"))
        return None

    monkeypatch.setattr(L, "get_lead_activo",
                        lambda user_id, canal, tienda_id: lead_activo)
    monkeypatch.setattr(L, "crear_lead", _fake_crear_lead)
    monkeypatch.setattr(L, "actualizar_lead",
                        lambda lead_id, tienda_id, cambios: updates.append(cambios))
    monkeypatch.setattr(L, "notificar_lead", _fake_notificar)
    monkeypatch.setattr(L, "modo_cierre", lambda tid: modo)

    interp = {"intencion": "decision_compra", "confianza": 0.95}
    presup = "Presupuesto:\n1x Camara: $100.000\nTotal: $100.000"
    meta = asyncio.new_event_loop().run_until_complete(
        L.procesar_mensaje_para_lead(
            user_id="u1", canal="whatsapp", tienda_id="verifika_prod",
            mensaje=mensaje, respuesta_solver="Genial.", trace_id="t1",
            interpretacion=interp, presupuesto=presup,
            datos_turno=dict(datos_turno)))[1]
    return meta, updates, creado


def test_modo_lead_capta_fuerte_sin_pedir_datos(monkeypatch):
    """En modo 'lead', un cierre confirmado capta el lead fuerte y avisa, y ahora
    responde un CIERRE distinto (tomamos tu pedido) en vez de dejar que el solver
    reitere el presupuesto (arreglo del loop del 'si', charla Monte Ralo). No
    pide datos: cierra suave y deriva a un humano."""
    meta, updates, creado = _correr_lead_fuerte(
        monkeypatch, "dale, lo quiero", {}, modo="lead")
    assert meta["accion"] == "lead_fuerte_captado"
    # Ahora SI hay respuesta_directa (cierre), para no re-mandar el presupuesto.
    assert "tomamos tu pedido" in (meta.get("respuesta_directa") or "").lower()
    # El lead quedo captado y avisado, no en 'datos_solicitados'.
    assert creado.get("estado_inicial") == "capturado"
    assert "lead_fuerte_captado" in creado.get("_notificaciones", [])


def test_modo_lead_no_reavisa_si_ya_hay_lead_fuerte(monkeypatch):
    """Si ya hay un lead fuerte captado activo, no se crea otro ni se re-avisa,
    pero SI se responde un cierre corto distinto (arreglo del loop): antes no
    devolvia nada y el solver re-mandaba el presupuesto en cada 'si'."""
    from app.core import leads
    activo = {"lead_id": "L1", "nivel": "fuerte", "estado": "capturado"}
    meta, updates, creado = _correr_lead_fuerte(
        monkeypatch, "dale, lo quiero", {}, modo="lead", lead_activo=activo)
    assert meta["accion"] == "lead_fuerte_ya_captado"
    assert meta.get("respuesta_directa") == leads.MENSAJE_PEDIDO_YA_TOMADO
    # No se creo un lead nuevo.
    assert creado.get("estado_inicial") is None


def test_modo_venta_sigue_pidiendo_datos(monkeypatch):
    """El modo 'venta' (version B) no cambia: sigue pidiendo los datos que faltan
    para cerrar y mandar el cobro."""
    meta, updates, creado = _correr_lead_fuerte(
        monkeypatch, "dale, lo quiero", {}, modo="venta")
    assert meta["accion"] == "pidiendo_datos"
    assert "respuesta_directa" in meta
    assert creado.get("estado_inicial") == "datos_solicitados"


# ── LA PREGUNTA MANDA SOBRE EL SCORE (decidido 3-jul) ────────────────────────
# El disparo del lead no debe depender de que decision_compra venga con confianza
# alta: cuando el interprete ve una decision de compra SIN confianza suficiente y
# ya hay un presupuesto mostrado (de este turno o de memoria), el sistema hace SU
# pregunta de cierre. La respuesta a esa pregunta decide determinista (gatillo D).
# Antes ese caso caia en "nada": ni cerraba ni preguntaba, y el lead solo salia
# si el score justo superaba 0.85 (visto en la charla real del 1-jul).

def _correr_cierre(monkeypatch, mensaje, intencion, confianza,
                   presupuesto, presupuesto_nuevo, modo="lead",
                   respuesta_solver="Genial."):
    """Corre procesar_mensaje_para_lead con fakes, variando intencion/confianza
    y si el presupuesto es nuevo o de memoria. Devuelve el meta de la decision."""
    import asyncio
    from app.core import leads as L

    monkeypatch.setattr(L, "get_lead_activo",
                        lambda user_id, canal, tienda_id: None)
    monkeypatch.setattr(L, "crear_lead", lambda **kw: "LEAD_TEST")
    monkeypatch.setattr(L, "actualizar_lead",
                        lambda lead_id, tienda_id, cambios: None)

    async def _fake_notificar(**kw):
        return None

    monkeypatch.setattr(L, "notificar_lead", _fake_notificar)
    monkeypatch.setattr(L, "modo_cierre", lambda tid: modo)

    interp = {"intencion": intencion, "confianza": confianza}
    return asyncio.new_event_loop().run_until_complete(
        L.procesar_mensaje_para_lead(
            user_id="u1", canal="whatsapp", tienda_id="verifika_prod",
            mensaje=mensaje, respuesta_solver=respuesta_solver, trace_id="t1",
            interpretacion=interp, presupuesto=presupuesto,
            presupuesto_nuevo=presupuesto_nuevo))[1]


def test_decision_sin_confianza_con_presupuesto_de_memoria_pregunta(monkeypatch):
    """decision_compra con confianza baja + presupuesto YA mostrado (memoria):
    el sistema hace la pregunta de cierre en vez de no hacer nada."""
    from app.core import leads
    meta = _correr_cierre(
        monkeypatch, "me parece que lo llevo", "decision_compra", 0.6,
        presupuesto="Total: $100.000", presupuesto_nuevo=False)
    assert meta["accion"] == "pregunta_cierre"
    assert meta["respuesta_directa"].endswith(leads.PREGUNTA_CIERRE)


def test_exploracion_con_presupuesto_de_memoria_no_pregunta(monkeypatch):
    """Explorar con un presupuesto viejo en memoria NO gatilla la pregunta: solo
    la decision de compra la adelanta."""
    meta = _correr_cierre(
        monkeypatch, "que otros teclados tenes?", "exploracion", 0.9,
        presupuesto="Total: $100.000", presupuesto_nuevo=False)
    assert meta["accion"] == "ninguna"


def test_lock_presupuesto_nuevo_sigue_preguntando(monkeypatch):
    """Lock del camino que ya andaba: presupuesto NUEVO + interes -> pregunta."""
    meta = _correr_cierre(
        monkeypatch, "cuanto queda con envio?", "pregunta_especifica", 0.7,
        presupuesto="Total: $100.000", presupuesto_nuevo=True)
    assert meta["accion"] == "pregunta_cierre"


def test_solver_ya_cerro_no_se_pega_doble_pregunta(monkeypatch):
    """DOBLE CIERRE (banco 19-jul): el solver ya cerro con su propia pregunta
    de confirmacion; la enlatada NO se pega encima. La del solver vale como LA
    pregunta y el 'si' del proximo turno cae igual en el gatillo."""
    from app.core import leads
    meta = _correr_cierre(
        monkeypatch, "cuanto queda con envio?", "pregunta_especifica", 0.7,
        presupuesto="Total: $28.000", presupuesto_nuevo=True,
        respuesta_solver="Total: $28.000\n\n¿Lo dejamos confirmado así?")
    assert meta["accion"] == "pregunta_cierre"
    assert leads.PREGUNTA_CIERRE not in meta["respuesta_directa"]
    assert meta["respuesta_directa"].rstrip().endswith(
        "¿Lo dejamos confirmado así?")


def test_pregunta_de_dato_del_solver_no_frena_la_enlatada(monkeypatch):
    """Una pregunta de DATO del solver no es un cierre: la enlatada va igual."""
    from app.core import leads
    meta = _correr_cierre(
        monkeypatch, "cuanto queda con envio?", "pregunta_especifica", 0.7,
        presupuesto="Total: $28.000", presupuesto_nuevo=True,
        respuesta_solver="Sale $28.000. ¿A qué localidad te lo mando?")
    assert meta["respuesta_directa"].endswith(leads.PREGUNTA_CIERRE)


# ── LOOP DEL "SI" REPETIDO (18-jul, charla real Monte Ralo) ──────────────────
# En modo lead, con el lead YA captado, la confirmacion no devolvia respuesta y
# el solver re-mandaba el presupuesto en cada "si". El arreglo: el cierre
# responde algo distinto y corta el loop.

def _correr_con_lead_activo(monkeypatch, lead_activo, mensaje, intencion,
                            confianza, presupuesto, modo="lead"):
    import asyncio
    from app.core import leads as L
    monkeypatch.setattr(L, "get_lead_activo",
                        lambda user_id, canal, tienda_id: lead_activo)
    monkeypatch.setattr(L, "crear_lead", lambda **kw: "LEAD_NEW")
    monkeypatch.setattr(L, "actualizar_lead",
                        lambda lead_id, tienda_id, cambios: None)

    async def _fake_notificar(**kw):
        return None

    monkeypatch.setattr(L, "notificar_lead", _fake_notificar)
    monkeypatch.setattr(L, "modo_cierre", lambda tid: modo)
    interp = {"intencion": intencion, "confianza": confianza}
    return asyncio.new_event_loop().run_until_complete(
        L.procesar_mensaje_para_lead(
            user_id="u1", canal="whatsapp", tienda_id="verifika_prod",
            mensaje=mensaje, respuesta_solver="Genial.", trace_id="t1",
            interpretacion=interp, presupuesto=presupuesto,
            presupuesto_nuevo=True))[1]


def test_lead_ya_captado_corta_el_loop(monkeypatch):
    """El bug real: lead fuerte YA captado + otro 'si' -> antes devolvia None (el
    solver re-mandaba el presupuesto). Ahora devuelve un cierre corto distinto."""
    from app.core import leads
    lead = {"lead_id": "L1", "nivel": "fuerte", "estado": "capturado"}
    meta = _correr_con_lead_activo(
        monkeypatch, lead, "si", "decision_compra", 0.95,
        presupuesto="Presupuesto:\n- 1x Tablet: $211.500\nTotal: $211.500")
    assert meta["accion"] == "lead_fuerte_ya_captado"
    assert meta.get("respuesta_directa") == leads.MENSAJE_PEDIDO_YA_TOMADO


def test_lead_fuerte_captado_devuelve_cierre(monkeypatch):
    """Al captar el lead fuerte en modo lead, el bot responde el cierre (tomamos
    tu pedido) en vez de dejar que el solver reitere el presupuesto."""
    meta = _correr_con_lead_activo(
        monkeypatch, None, "dale, lo confirmo", "decision_compra", 0.95,
        presupuesto="Presupuesto:\n- 1x Tablet: $211.500\nTotal: $211.500")
    assert meta["accion"] == "lead_fuerte_captado"
    assert "tomamos tu pedido" in (meta.get("respuesta_directa") or "").lower()
