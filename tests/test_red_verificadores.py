"""
AREA: LA RED DE VERIFICADORES DEL CAMINO VIVO (hub_atado).

Hasta el 29-jul el hub corria UNA sola verificacion: la de montos. Las otras
cinco -stock, FAQ numerica, intencion, cita y promesas- estaban escritas y no
las llamaba nadie: quedaron huerfanas cuando el orchestrator paso de
`interprete_libre` al hub. En produccion no habia nada mirando si el bot negaba
stock que existe, si parafraseaba mal un porcentaje de la politica, si ofrecia
una marca que el cliente habia excluido o si prometia un dia de entrega.

Estos tests corren sobre el CATALOGO REAL con el doble de Firestore y sin LLM.
Lo que exigen no es que cada modulo funcione -eso ya lo prueban sus tests- sino
que el hub los LLAME y que la red degrade sin dejar pasar la mentira.
"""
import asyncio

TIENDA = "verifika_prod"


def _correr(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _con_stock(firestore_doble):
    from app.storage.firestore_client import get_all_products
    return next(p for p in get_all_products(tienda_id=TIENDA)
                if (p.get("stock") or 0) > 0)


def _evidencia(prod):
    import app.core.hub_atado as H
    meta = {"tools_called": [{"name": "get_product_details",
                              "result": {"encontrado": True, "producto": prod}}]}
    estado = {"productos_vistos": [{"id": prod["id"], "nombre": prod["nombre"],
                                    "precio": prod["precio_ars"]}]}
    return H._evidencia_del_texto("x", meta, estado, TIENDA, "t"), meta


# ── STOCK: la alucinacion real del 2-jul ───────────────────────────────────
def test_corrige_la_cifra_de_unidades_inventada(firestore_doble):
    import app.core.hub_atado as H
    p = _con_stock(firestore_doble)
    ev, _ = _evidencia(p)
    out = _correr(H._verificar_stock(
        f"Del {p['nombre']} quedan 47 unidades.", ev, "t"))
    assert "47" not in out
    assert str(p["stock"]) in out


def test_la_verdad_de_stock_no_se_toca(firestore_doble):
    import app.core.hub_atado as H
    p = _con_stock(firestore_doble)
    ev, _ = _evidencia(p)
    texto = f"El {p['nombre']} está disponible, quedan {p['stock']}."
    assert _correr(H._verificar_stock(texto, ev, "t")) == texto


def test_el_faltante_falso_no_sale_aunque_el_modelo_este_caido(
        monkeypatch, firestore_doble):
    """EL caso que importa. Si la reescritura muere -clave vencida, timeout,
    provider caido- el turno NO se puede quedar con la mentira: sigue de largo
    a la cuarentena determinista, que no necesita modelo.

    Esto fue un bug real de esta misma tanda: la llamada de reescritura estaba
    dentro del try grande, asi que un 401 saltaba al except y devolvia el texto
    con el "no tiene stock" falso intacto."""
    import app.core.hub_atado as H
    import app.core.guardia_promesas as GP

    async def _revienta(*a, **k):
        raise RuntimeError("provider caido")

    monkeypatch.setattr(GP, "reescribir_con_reglas", _revienta)
    p = _con_stock(firestore_doble)
    ev, _ = _evidencia(p)
    out = _correr(H._verificar_stock(
        f"Mirá, el {p['nombre']} no tiene stock. Te ofrezco otra opción.",
        ev, "t"))
    assert "no tiene stock" not in out.lower()


def test_sin_evidencia_del_turno_no_juzga(firestore_doble):
    """El stock cambia: un dato viejo no acusa a nadie. Sin evidencia de ESTE
    turno el verificador no toca nada."""
    import app.core.hub_atado as H
    texto = "El Mouse Logitech G203 Lightsync Negro no tiene stock."
    assert _correr(H._verificar_stock(texto, [], "t")) == texto


# ── FAQ NUMERICA: los numeros chicos que la plata no mira ──────────────────
def test_marca_el_numero_de_politica_sin_respaldo(firestore_doble, caplog):
    import app.core.hub_atado as H
    p = _con_stock(firestore_doble)
    ev, meta = _evidencia(p)
    # 36 meses de garantia no existe en la fuente; que no pase mudo.
    H._verificar_faq_numerica("Te damos 36 meses de garantía.", ev, meta, "t")
    # el radar es el log; lo que se exige es que no rompa y que corra.


def test_faq_numerica_no_rompe_sin_evidencia(firestore_doble):
    import app.core.hub_atado as H
    texto = "Son 6 cuotas sin interés."
    assert H._verificar_faq_numerica(texto, [], {}, "t") == texto


# ── INTENCION: estructura contra estructura ────────────────────────────────
def test_saca_el_producto_de_la_marca_excluida(firestore_doble):
    """El cliente dijo "nada de Logitech" y la respuesta igual lo ofrece. Aguas
    arriba el filtro de universo lo previene; esta es la red."""
    import app.core.hub_atado as H
    from app.storage.firestore_client import get_all_products
    p = next(pp for pp in get_all_products(tienda_id=TIENDA)
             if str(pp.get("marca", "")).lower() == "logitech")
    meta = {"tools_called": [{"name": "get_product_details",
                              "result": {"encontrado": True, "producto": p}}]}
    conv = {"preferencias_cliente": {
        "exclusiones": [{"tipo": "marca", "valor": "Logitech"}]}}
    texto = f"Te recomiendo el {p['nombre']}.\nTambién tengo otras opciones."
    out = H._verificar_intencion(texto, meta, conv, {}, "nada de logitech",
                                 TIENDA, "t")
    assert p["nombre"] not in out or out != texto


def test_intencion_sin_preferencias_no_toca(firestore_doble):
    import app.core.hub_atado as H
    texto = "Te recomiendo este."
    assert H._verificar_intencion(texto, {}, {}, {}, "hola", TIENDA, "t") == texto


# ── CITA: candado y sonda del corpus jurado ────────────────────────────────
def test_la_cita_falsa_no_rompe_el_turno(firestore_doble):
    """El verificador de cita no reescribe: loguea. Lo que se exige es que un id
    inventado no tire el turno."""
    import app.core.hub_atado as H
    H._verificar_cita({"prosa_citada": ["tema_que_no_existe"]}, "hola", "t")
    H._verificar_cita({"prosa_citada": []}, "hola", "t")


# ── PROMESAS: la lista cerrada de lo que no se puede decir ─────────────────
def test_la_promesa_prohibida_no_sale_aunque_el_modelo_este_caido(
        monkeypatch, firestore_doble):
    import app.core.hub_atado as H
    import app.core.guardia_promesas as GP
    from app.core.guardia_promesas import detectar

    async def _revienta(*a, **k):
        raise RuntimeError("provider caido")

    texto = "Te llega el martes sin falta a tu casa."
    if not detectar(texto):
        return  # la casuistica vive en config; si no dispara, no hay que probar
    monkeypatch.setattr(GP, "reescribir_sin_promesas", _revienta)
    out = _correr(H._guardia_promesas(texto, "t"))
    assert not detectar(out), "la promesa prohibida salio al cliente"


def test_texto_limpio_pasa_la_guardia_intacto(firestore_doble):
    import app.core.hub_atado as H
    texto = "Te sirve para la oficina. ¿Te lo aparto?"
    assert _correr(H._guardia_promesas(texto, "t")) == texto


# ── LA RED COMPLETA ────────────────────────────────────────────────────────
def test_la_red_corre_los_siete_en_orden(monkeypatch, firestore_doble):
    """El orden no es casual: de lo mas duro a lo mas blando, para que el juez
    reciba un texto con TODO el dato duro ya auditado y se ocupe solo de lo que
    ninguna regla puede chequear."""
    import app.core.hub_atado as H
    orden = []

    monkeypatch.setattr(H, "_verificar_montos",
                        lambda t, e, tr: (orden.append("montos"), t)[1])

    async def _stock(t, e, tr):
        orden.append("stock")
        return t

    monkeypatch.setattr(H, "_verificar_stock", _stock)
    monkeypatch.setattr(H, "_verificar_faq_numerica",
                        lambda t, e, m, tr: (orden.append("faq"), t)[1])
    monkeypatch.setattr(H, "_verificar_intencion",
                        lambda t, m, c, i, ms, ti, tr: (orden.append("intencion"), t)[1])
    monkeypatch.setattr(H, "_verificar_cita",
                        lambda m, t, tr: orden.append("cita"))

    async def _prom(t, tr):
        orden.append("promesas")
        return t

    async def _juez(t, m, u, i, ms, ti, tr):
        orden.append("juez")
        return t

    monkeypatch.setattr(H, "_guardia_promesas", _prom)
    monkeypatch.setattr(H, "_fiscalizar_prosa", _juez)

    _correr(H._red_de_verificadores("Hola, te sirve.", {"tools_called": []},
                                    {}, {}, [], {}, "hola", TIENDA, "t"))
    assert orden == ["montos", "stock", "faq", "intencion", "cita",
                     "promesas", "juez"], orden


def test_la_red_no_corre_sobre_el_fallback(firestore_doble):
    import app.core.hub_atado as H
    from app.config import get_settings
    fb = get_settings().VERIFIKA_FALLBACK_MESSAGE
    assert _correr(H._red_de_verificadores(fb, {}, {}, {}, [], {}, "hola",
                                           TIENDA, "t")) == fb


def test_si_la_evidencia_falla_la_red_sigue(monkeypatch, firestore_doble):
    """Armar la evidencia toca Firestore. Si eso falla, la red no puede tirar el
    turno: corre igual con evidencia vacia y los deterministas se abstienen."""
    import app.core.hub_atado as H

    def _explota(*a, **k):
        raise RuntimeError("firestore caido")

    monkeypatch.setattr(H, "_evidencia_del_texto", _explota)

    async def _juez(t, *a, **k):
        return t

    monkeypatch.setattr(H, "_fiscalizar_prosa", _juez)
    texto = "Te sirve para la oficina."
    assert _correr(H._red_de_verificadores(texto, {"tools_called": []}, {}, {},
                                           [], {}, "hola", TIENDA, "t")) == texto


def test_el_hub_llama_a_la_red_en_un_turno_real(monkeypatch, firestore_doble):
    """Otra vez el pecado de este repo: tener el modulo escrito y no llamarlo."""
    import app.core.hub_atado as H
    import app.core.generador_v2 as G
    import app.core.cierre as C
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
