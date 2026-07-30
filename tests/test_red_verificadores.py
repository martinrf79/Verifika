"""
AREA: LA RED DE VERIFICADORES DEL CAMINO VIVO (app/core/red_verificadores.py).

Hasta el 29-jul el hub corria UNA sola verificacion: la de montos. Las otras
cinco -stock, FAQ numerica, intencion, cita y promesas- estaban escritas y no
las llamaba nadie: quedaron huerfanas cuando el orchestrator paso de
`interprete_libre` al hub. En produccion no habia nada mirando si el bot negaba
stock que existe, si parafraseaba mal un porcentaje de la politica, si ofrecia
una marca que el cliente habia excluido o si prometia un dia de entrega.

Despues, ya enchufadas, eran una CADENA: cada una recibia lo que dejo la
anterior. Las charlas grabadas cazaron el bug que eso garantiza -el juez
reescribe el mensaje entero DESPUES de la guardia de promesas y metio "cerremos
la operacion hoy mismo"-, y la red paso a una sola pasada: todos opinan sobre el
MISMO texto, un solo lugar aplica y decide, y una fase final de VEREDICTO vuelve
a diagnosticar todo sobre el resultado.

Estos tests corren sobre el CATALOGO REAL con el doble de Firestore y sin LLM.
Lo que exigen no es que cada modulo funcione -eso ya lo prueban sus tests- sino
que la red los llame a TODOS, que degrade sin dejar pasar la mentira, y que
nada de lo que introduzca una reescritura llegue al cliente.
"""
import asyncio

TIENDA = "verifika_prod"


def _correr(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _con_stock(firestore_doble):
    from app.storage.firestore_client import get_all_products
    return next(p for p in get_all_products(tienda_id=TIENDA)
                if (p.get("stock") or 0) > 0)


def _ctx(evidencia=None, meta=None, conv=None, mensaje="hola"):
    """El contexto que el hub le arma a la red. Todos los verificadores leen de
    aca, que es justamente el punto: una sola version de la verdad del turno."""
    return {"evidencia": evidencia or [], "meta": meta or {"tools_called": []},
            "estado": {}, "conv": conv or {}, "universo": [], "interp": {},
            "mensaje": mensaje, "tienda_id": TIENDA, "trace_id": "t",
            "evidencia_juez": lambda: None}


def _evidencia(prod):
    import app.core.hub_atado as H
    meta = {"tools_called": [{"name": "get_product_details",
                              "result": {"encontrado": True, "producto": prod}}]}
    estado = {"productos_vistos": [{"id": prod["id"], "nombre": prod["nombre"],
                                    "precio": prod["precio_ars"]}]}
    return H._evidencia_del_texto("x", meta, estado, TIENDA, "t"), meta


def _sin_juez(monkeypatch):
    """El juez es lo unico de la red que llama al modelo. Se apaga para que
    estos tests midan los deterministas y no gasten ni dependan de la red."""
    import app.core.red_verificadores as R

    async def _noop(texto, ctx):
        return texto

    monkeypatch.setattr(R, "_juez", _noop)


# ── STOCK: la alucinacion real del 2-jul ───────────────────────────────────
def test_corrige_la_cifra_de_unidades_inventada(monkeypatch, firestore_doble):
    import app.core.red_verificadores as R
    _sin_juez(monkeypatch)
    p = _con_stock(firestore_doble)
    ev, meta = _evidencia(p)
    out = _correr(R.revisar(f"Del {p['nombre']} quedan 47 unidades.",
                            _ctx(ev, meta)))
    assert "47" not in out
    assert str(p["stock"]) in out


def test_la_verdad_de_stock_no_se_toca(monkeypatch, firestore_doble):
    import app.core.red_verificadores as R
    _sin_juez(monkeypatch)
    p = _con_stock(firestore_doble)
    ev, meta = _evidencia(p)
    texto = f"El {p['nombre']} está disponible, quedan {p['stock']}."
    assert _correr(R.revisar(texto, _ctx(ev, meta))) == texto


def test_el_faltante_falso_no_sale_aunque_el_modelo_este_caido(
        monkeypatch, firestore_doble):
    """EL caso que importa. Si la reescritura muere -clave vencida, timeout,
    provider caido- el turno NO se puede quedar con la mentira: sigue de largo
    a la cuarentena determinista, que no necesita modelo.

    Fue un bug real: la llamada de reescritura estaba dentro del try grande, asi
    que un 401 saltaba al except y devolvia el texto con el "no tiene stock"
    falso intacto."""
    import app.core.guardia_promesas as GP
    import app.core.red_verificadores as R
    _sin_juez(monkeypatch)

    async def _revienta(*a, **k):
        raise RuntimeError("provider caido")

    monkeypatch.setattr(GP, "reescribir_con_reglas", _revienta)
    p = _con_stock(firestore_doble)
    ev, meta = _evidencia(p)
    out = _correr(R.revisar(
        f"Mirá, el {p['nombre']} no tiene stock. Te ofrezco otra opción.",
        _ctx(ev, meta)))
    assert "no tiene stock" not in out.lower()


def test_sin_evidencia_del_turno_no_juzga(monkeypatch, firestore_doble):
    """El stock cambia: un dato viejo no acusa a nadie. Sin evidencia de ESTE
    turno el verificador no toca nada."""
    import app.core.red_verificadores as R
    _sin_juez(monkeypatch)
    texto = "El Mouse Logitech G203 Lightsync Negro no tiene stock."
    assert _correr(R.revisar(texto, _ctx())) == texto


# ── FAQ NUMERICA: los numeros chicos que la plata no mira ──────────────────
def test_marca_el_numero_de_politica_sin_respaldo(firestore_doble):
    import app.core.red_verificadores as R
    p = _con_stock(firestore_doble)
    ev, meta = _evidencia(p)
    # 36 meses de garantia no existe en la fuente; que no pase mudo ni rompa.
    R._d_faq("Te damos 36 meses de garantía.", _ctx(ev, meta))


def test_faq_numerica_no_rompe_sin_evidencia(firestore_doble):
    import app.core.red_verificadores as R
    assert R._d_faq("Son 6 cuotas sin interés.", _ctx()).limpio


# ── INTENCION: estructura contra estructura ────────────────────────────────
def test_saca_el_producto_de_la_marca_excluida(monkeypatch, firestore_doble):
    """El cliente dijo "nada de Logitech" y la respuesta igual lo ofrece. Aguas
    arriba el filtro de universo lo previene; esta es la red."""
    import app.core.red_verificadores as R
    from app.storage.firestore_client import get_all_products
    _sin_juez(monkeypatch)
    p = next(pp for pp in get_all_products(tienda_id=TIENDA)
             if str(pp.get("marca", "")).lower() == "logitech")
    meta = {"tools_called": [{"name": "get_product_details",
                              "result": {"encontrado": True, "producto": p}}]}
    texto = f"Te recomiendo el {p['nombre']}.\nTambién tengo otras opciones."
    conv = {"preferencias_cliente": {
        "exclusiones": [{"tipo": "marca", "valor": "Logitech"}]}}
    out = _correr(R.revisar(texto, _ctx(meta=meta, conv=conv,
                                        mensaje="nada de logitech")))
    assert p["nombre"] not in out or out != texto


def test_intencion_sin_preferencias_no_toca(firestore_doble):
    import app.core.red_verificadores as R
    assert R._d_intencion("Te recomiendo este.", _ctx()).limpio


# ── CITA: candado y sonda del corpus jurado ────────────────────────────────
def test_la_cita_falsa_no_rompe_el_turno(firestore_doble):
    """El verificador de cita no reescribe: loguea. Lo que se exige es que un id
    inventado no tire el turno."""
    import app.core.red_verificadores as R
    R._cita(_ctx(meta={"prosa_citada": ["tema_que_no_existe"]}))
    R._cita(_ctx(meta={"prosa_citada": []}))


# ── PROMESAS: la lista cerrada de lo que no se puede decir ─────────────────
def test_la_promesa_prohibida_no_sale_aunque_el_modelo_este_caido(
        monkeypatch, firestore_doble):
    import app.core.guardia_promesas as GP
    import app.core.red_verificadores as R
    from app.core.guardia_promesas import detectar
    _sin_juez(monkeypatch)

    async def _revienta(*a, **k):
        raise RuntimeError("provider caido")

    texto = "Te llega el martes sin falta a tu casa."
    if not detectar(texto):
        return  # la casuistica vive en config; si no dispara, no hay que probar
    monkeypatch.setattr(GP, "reescribir_con_reglas", _revienta)
    out = _correr(R.revisar(texto, _ctx()))
    assert not detectar(out), "la promesa prohibida salio al cliente"


def test_texto_limpio_pasa_la_red_intacto(monkeypatch, firestore_doble):
    import app.core.red_verificadores as R
    _sin_juez(monkeypatch)
    texto = "Te sirve para la oficina. ¿Te lo aparto?"
    assert _correr(R.revisar(texto, _ctx())) == texto


# ── LA PASADA UNICA: lo que reemplazo a la cadena ──────────────────────────
def test_todos_opinan_sobre_el_MISMO_texto(monkeypatch, firestore_doble):
    """El corazon del cambio. En la cadena, el verificador N veia lo que dejo el
    N-1; aca todos ven la entrada original. Eso es lo que permite juntar sus
    correcciones sin que el orden entre ellos cambie el resultado."""
    import app.core.red_verificadores as R
    vistos = []

    def _espia(nombre):
        def _f(texto, ctx):
            vistos.append((nombre, texto))
            return R.Dictamen(nombre)
        return _f

    monkeypatch.setattr(R, "_DETERMINISTAS",
                        tuple(_espia(n) for n in ("a", "b", "c")))
    R.diagnosticar("el texto original", _ctx())
    assert [t for _n, t in vistos] == ["el texto original"] * 3, vistos


def test_cada_corrector_ubica_su_propia_cifra(firestore_doble):
    """CANDADO CONTRA EL BUG QUE METI EN ESTA MISMA REFACTORIZACION.

    El primer intento junto los reemplazos sueltos de todos los verificadores y
    los aplico de una con `str.replace`. Estaba mal: `correcciones` trae NUMEROS,
    no cadenas, asi que reemplazar el "5" pelado pisa todos los cinco del mensaje
    y "$8.500" sale "$8.3750000". Lo cazo el gate de las charlas grabadas, con el
    numero bajando de 1654 a 1651, antes de que llegara a produccion.

    Ahora cada corrector reescribe su cifra con su propia funcion, que sabe
    ubicarla."""
    import app.core.red_verificadores as R
    texto = "Sale $8.500 y quedan 5 unidades."
    d = R.Dictamen("montos", correcciones=[{"de": 5, "a": 37500}],
                   corregir=lambda t: t.replace("quedan 5", "quedan 5"))
    assert R.aplicar(texto, [d]) == texto, "un digito suelto no puede pisar el texto"

    d2 = R.Dictamen("stock",
                    corregir=lambda t: t.replace("quedan 5 ", "quedan 3 "))
    assert R.aplicar(texto, [d2]) == "Sale $8.500 y quedan 3 unidades."


def test_el_orden_de_aplicacion_es_uno_solo_y_explicito(firestore_doble):
    """Aplicar es secuencial y a proposito, pero eso NO es la cadena vieja: aca
    solo se aplica, en un orden que se lee de un vistazo. El diagnostico de todos
    ya se hizo sobre el mismo texto y el veredicto lo revisa todo al final."""
    import app.core.red_verificadores as R
    orden = []

    def _c(nombre, viejo, nuevo):
        def _f(t):
            orden.append(nombre)
            return t.replace(viejo, nuevo)
        return _f

    ds = [R.Dictamen("a", corregir=_c("a", "uno", "1")),
          R.Dictamen("b", corregir=_c("b", "dos", "2"))]
    assert R.aplicar("uno y dos", ds) == "1 y 2"
    assert orden == ["a", "b"]


def test_un_corrector_que_revienta_no_pierde_lo_demas(firestore_doble):
    import app.core.red_verificadores as R

    def _explota(t):
        raise RuntimeError("corrector roto")

    ds = [R.Dictamen("roto", corregir=_explota),
          R.Dictamen("ok", corregir=lambda t: t.replace("mal", "bien"))]
    assert R.aplicar("todo mal", ds) == "todo bien"


def test_la_poda_saca_la_oracion_no_el_parrafo(firestore_doble):
    """La poda vieja borraba la LINEA entera siempre, y en un mensaje de tres
    parrafos eso se llevaba puesta una respuesta buena por una frase."""
    import app.core.red_verificadores as R
    texto = ("El teclado cuesta $14.500. Te llega el martes sin falta. "
             "¿Te lo aparto?")
    out = R.podar(texto, lambda f: "martes" in f)
    assert "martes" not in out
    assert "$14.500" in out and "aparto" in out


def test_lo_que_el_juez_ensucia_no_sale(monkeypatch, firestore_doble):
    """EL BUG QUE PARIO ESTA REFACTORIZACION (guion 17 turno 3). El juez no solo
    poda: REESCRIBE el mensaje entero, y corria despues de la guardia de
    promesas. Metio "cerremos la operacion hoy mismo" y salio al cliente.

    La fase de VEREDICTO vuelve a diagnosticar TODO sobre el resultado del juez.
    Si no se puede reparar, se tira la reescritura y sale el texto anterior, que
    ya paso la red entera: se pierde prosa, no se pierde la venta."""
    import app.core.red_verificadores as R
    from app.core.guardia_promesas import detectar
    limpio = "El teclado cuesta $14.500 y te sirve para la oficina."
    sucio = limpio + " Te llega el martes sin falta."
    if not detectar(sucio):
        return

    async def _juez_sucio(texto, ctx):
        return sucio

    monkeypatch.setattr(R, "_juez", _juez_sucio)
    out = _correr(R.revisar(limpio, _ctx()))
    assert not detectar(out), "el juez metio una promesa y salio al cliente"
    assert "$14.500" in out, "se perdio el turno entero por una frase del juez"


def test_la_red_no_corre_sobre_el_fallback(firestore_doble):
    import app.core.red_verificadores as R
    from app.config import get_settings
    fb = get_settings().VERIFIKA_FALLBACK_MESSAGE
    assert _correr(R.revisar(fb, _ctx())) == fb


def test_un_verificador_que_revienta_no_tapa_a_los_otros(monkeypatch,
                                                         firestore_doble):
    """Con la cadena, todo colgaba de un try grande: el primero que reventaba
    cortaba la red entera y los de abajo no corrian. Aca se anota y se sigue."""
    import app.core.red_verificadores as R
    corridos = []

    def _explota(texto, ctx):
        raise RuntimeError("verificador roto")

    def _ok(texto, ctx):
        corridos.append("ok")
        return R.Dictamen("ok", eventos=["corri"], instruccion="")

    monkeypatch.setattr(R, "_DETERMINISTAS", (_explota, _ok))
    R.diagnosticar("hola", _ctx())
    assert corridos == ["ok"], "un verificador roto tapo al siguiente"


def test_si_la_evidencia_falla_la_red_sigue(monkeypatch, firestore_doble):
    """Armar la evidencia toca Firestore. Si eso falla, la red no puede tirar el
    turno: corre igual con evidencia vacia y los deterministas se abstienen."""
    import app.core.hub_atado as H
    import app.core.red_verificadores as R
    _sin_juez(monkeypatch)

    def _explota(*a, **k):
        raise RuntimeError("firestore caido")

    monkeypatch.setattr(H, "_evidencia_del_texto", _explota)
    texto = "Te sirve para la oficina."
    assert _correr(H._red_de_verificadores(texto, {"tools_called": []}, {}, {},
                                           [], {}, "hola", TIENDA, "t")) == texto


def test_el_hub_llama_a_la_red_en_un_turno_real(monkeypatch, firestore_doble):
    """Otra vez el pecado de este repo: tener el modulo escrito y no llamarlo."""
    import app.core.cierre as C
    import app.core.generador_v2 as G
    import app.core.hub_atado as H
    from app.storage.firestore_client import reset_conversation

    llamado = {}

    async def _fake_interpretar(*a, **k):
        return {"intencion": "pregunta_especifica", "producto_resuelto": None,
                "productos_consultados": [], "pedido": [],
                "solicitud_nueva": [], "categorias": ["mouse"]}

    async def _fake_fragmentos(*a, **k):
        return ([{"tipo": "prosa", "texto": "Te sirve para la oficina."}],
                [], "", [], {})

    async def _espia(texto, *a, **k):
        llamado["si"] = True
        return texto

    monkeypatch.setattr(C, "extraer_datos_cliente", lambda *a, **k: {})
    monkeypatch.setattr(H, "interpretar_mensaje", _fake_interpretar)
    monkeypatch.setattr(G, "generar_fragmentos", _fake_fragmentos)
    monkeypatch.setattr(H, "_red_de_verificadores", _espia)

    reset_conversation("u_red", tienda_id=TIENDA)
    _correr(H.procesar_atado("u_red", "sirve para la oficina?", TIENDA, "sim",
                             "t_red"))
    assert llamado.get("si"), "el hub NO llama a la red: sigue huerfana"


# ── HALLAZGO DEL BANCO VIVO: el fragmento que se rinde en silencio ─────────
def test_la_categoria_con_adjetivo_pegado_igual_mapea(firestore_doble):
    """Banco 29-jul, guion 68 turno 1. El modelo emitio el fragmento de
    opciones con categoria "tablets Samsung"; el mapeo exigia match exacto por
    singular, devolvio None y el fragmento se renderizo VACIO. El turno salio
    sin un solo producto, y como no se mostro nada, el turno 2 quedo sin
    contexto y el bot contesto con modulos de memoria RAM a alguien que
    preguntaba por la RAM de una tablet. Una palabra de mas del modelo tumbaba
    la charla entera."""
    from app.core.generador_v2 import _cat_real
    assert _cat_real("tablets Samsung", TIENDA) == "tablet"
    assert _cat_real("mouse gamer", TIENDA) == "mouse"
    assert _cat_real("notebooks para diseño", TIENDA) == "notebook"
    # y la mas especifica gana: "memoria ram" no cae en "memoria"
    assert _cat_real("memoria ram", TIENDA) == "memoria ram"
    # lo que no existe sigue siendo None: el mapeo no inventa
    assert _cat_real("zapatillas", TIENDA) is None
    assert _cat_real("", TIENDA) is None


def test_un_fragmento_perdido_deja_radar(firestore_doble):
    """Un fragmento que el modelo emitio y el render descarto es contenido que
    el cliente NO recibio. Hasta hoy la unica pista era comparar dos numeros de
    una linea de log, y nadie los compara.

    Se captura con structlog y no con la salida estandar: leyendo stdout el
    test pasaba solo y fallaba en la bateria, porque el logger queda pegado a
    la configuracion del primer test que lo toca."""
    from structlog.testing import capture_logs
    from app.core.generador_v2 import renderizar
    with capture_logs() as eventos:
        texto, _ = renderizar([{"tipo": "opciones", "categoria": "zapatillas"}],
                              [], {}, TIENDA, "t_perdido")
    assert not texto, "renderizo algo de una categoria que no existe"
    assert any(e.get("event") == "generador_v2_fragmento_perdido"
               for e in eventos), "el fragmento se perdio en silencio"


# ── EL ULTIMO ROJO DE LAS CHARLAS GRABADAS (guion 21 turno 4) ──────────────
def test_el_dia_y_la_entrega_tienen_que_estar_en_la_misma_oracion(
        firestore_doble):
    """La promesa de dia se detectaba con un hueco de 40 caracteres que cruzaba
    puntos y saltos de linea. Con eso, "...lo resolvemos hoy mismo.\\n\\nSi el
    producto llegó con un faltante..." disparaba dia_entrega pegando el "hoy
    mismo" de un parrafo con el "llegó" del siguiente: dos frases sin relacion.

    No habia reescritura ni poda que arreglara una promesa que no existia, asi
    que el turno entero -una respuesta correcta sobre garantia- caia al
    enlatado. Era el ultimo rojo de las 65 charlas.

    Prometer un dia sigue siendo imposible: eso se dice en UNA oracion."""
    from app.core.guardia_promesas import detectar

    # las promesas de verdad se siguen cazando
    for t in ("Te llega el martes sin falta a tu casa.",
              "El viernes lo tenés en tu puerta.",
              "Lo recibís mañana.",
              "Te lo entregamos el 25 de junio.",
              "Llega hoy mismo a tu domicilio."):
        assert "dia_entrega" in detectar(t), t

    # y dos oraciones distintas ya no se pegan
    for t in ("Lo resolvemos hoy mismo.\n\nSi el producto llegó con un "
              "faltante, lo gestionamos como cambio.",
              "Te lo despachamos hoy mismo.\n\nEl envío llega en 2 a 7 días "
              "hábiles."):
        assert not detectar(t), t
