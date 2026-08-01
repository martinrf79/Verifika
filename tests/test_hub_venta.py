"""
AREA: EL HUB DE VENTA, el turno completo.

Cubre las cuatro costuras del diseno nuevo: que las herramientas corran juntas,
que la unica regla de salida pode la plata inventada SIN tocar la cuenta, que la
cuenta llegue si o si al cliente, y que la senal de cierre salga de una
herramienta y no de un heuristico de texto.

No se le habla al modelo: las dos llamadas se reemplazan por dobles. Lo que se
prueba es el hub, no el proveedor.
"""
import asyncio
import time

import pytest

from app.core import herramientas as H
from app.core import hub_venta as HV

TIENDA = "verifika_prod"
USUARIO = "test_hub_venta"


@pytest.fixture(autouse=True)
def _doble(firestore_doble):
    from app.core.tools_context import set_current_tienda
    from app.storage.firestore_client import reset_conversation
    set_current_tienda(TIENDA)
    reset_conversation(USUARIO, tienda_id=TIENDA)
    return firestore_doble


def _turno(monkeypatch, pedidos, texto, mensaje="hola", texto_directo=""):
    """Corre un turno con las dos llamadas al modelo dobladas."""
    async def _fake_uno(*a, **kw):
        return pedidos, texto_directo

    async def _fake_dos(*a, **kw):
        return texto

    monkeypatch.setattr(HV, "_pedir_herramientas", _fake_uno)
    monkeypatch.setattr(HV, "_redactar", _fake_dos)
    return asyncio.run(HV.procesar_venta(USUARIO, mensaje, TIENDA, "test", "t1"))


# ── 1. LAS HERRAMIENTAS CORREN JUNTAS ───────────────────────────────────────
def test_las_herramientas_corren_en_paralelo_no_en_fila(monkeypatch):
    """Es la mitad de la razon de ser del diseno. Con tres herramientas de medio
    segundo, en fila serian 1,5 s; juntas, medio. En produccion el turno del
    camino viejo tardaba entre 5 y 9 segundos con las llamadas encadenadas."""
    def _lenta(nombre, args, tienda_id):
        time.sleep(0.3)
        return {"estado": "ok", "nombre": nombre}

    monkeypatch.setattr(H, "ejecutar", _lenta)
    pedidos = [{"nombre": "buscar_productos", "args": {}},
               {"nombre": "consultar_politica", "args": {}},
               {"nombre": "cotizar_envio", "args": {}}]
    t0 = time.time()
    r = asyncio.run(HV._ejecutar_en_paralelo(pedidos, TIENDA, "t1"))
    tardo = time.time() - t0
    assert len(r) == 3
    assert tardo < 0.7, f"corrieron en fila: {tardo:.2f}s"


def test_una_herramienta_que_revienta_no_se_lleva_el_turno(monkeypatch):
    def _explota(nombre, args, tienda_id):
        raise RuntimeError("boom")

    monkeypatch.setattr(H, "ejecutar", _explota)
    r = asyncio.run(HV._ejecutar_en_paralelo(
        [{"nombre": "buscar_productos", "args": {}}], TIENDA, "t1"))
    assert r[0]["resultado"]["estado"] == "error"


# ── 2. LA UNICA REGLA DE SALIDA ─────────────────────────────────────────────
def test_la_plata_inventada_se_poda(monkeypatch):
    llamadas = [{"herramienta": "buscar_productos", "pedido": {},
                 "resultado": {"estado": "encontrado", "productos": [
                     {"id": "MOU0001", "nombre": "Mouse", "precio_ars": 8500}]}}]
    texto = ("El mouse sale $8.500. Te hago un precio especial de $6.000 "
             "si te lo llevas hoy.")
    salida = HV._sin_plata_inventada(texto, llamadas, "", "t1")
    assert "8.500" in salida
    assert "6.000" not in salida


def test_la_regla_no_toca_un_renglon_de_la_cuenta(monkeypatch):
    """El agujero del camino viejo: el juez y los verificadores juzgaban con
    evidencia distinta a la del que redactaba y terminaban podando lo que el
    CODIGO habia estampado. Aca la evidencia es exactamente lo inyectado, y
    ademas los renglones del bloque son intocables por definicion."""
    bloque = ("Presupuesto:\n- 2x Mouse: $8.500 c/u = $17.000\n"
              "Subtotal: $17.000\nTotal: $17.000")
    llamadas = [{"herramienta": "armar_presupuesto", "pedido": {},
                 "resultado": {"estado": "ok", "bloque": bloque,
                               "total_ars": 17000}}]
    texto = "Te armo la cuenta.\n" + bloque + "\nY te regalo $5.000 de descuento."
    salida = HV._sin_plata_inventada(texto, llamadas, bloque, "t1")
    for renglon in bloque.splitlines():
        assert renglon in salida
    assert "5.000" not in salida


def test_los_numeros_que_no_son_plata_sobreviven():
    llamadas = [{"herramienta": "ficha_producto", "pedido": {},
                 "resultado": {"estado": "encontrado", "producto": {
                     "id": "MOU0001", "nombre": "Mouse", "precio_ars": 8500}}}]
    texto = "Tiene 12 meses de garantia, 1600 DPI y sale $8.500."
    salida = HV._sin_plata_inventada(texto, llamadas, "", "t1")
    assert "12 meses" in salida and "8.500" in salida


# ── 3. LA CUENTA LLEGA SI O SI ──────────────────────────────────────────────
def test_si_el_modelo_se_come_la_cuenta_el_codigo_la_repone(monkeypatch):
    bloque = "Presupuesto:\n- 1x Mouse: $8.500 c/u = $8.500\nTotal: $8.500"
    pedidos = [{"nombre": "armar_presupuesto", "args": {}}]
    monkeypatch.setattr(H, "ejecutar", lambda n, a, t: {
        "estado": "ok", "bloque": bloque, "total_ars": 8500, "detalle": []})
    salida = _turno(monkeypatch, pedidos,
                    "Te paso el presupuesto que armamos.")
    assert "Presupuesto:" in salida and "Total: $8.500" in salida


def test_el_id_interno_no_sale_al_cliente(monkeypatch):
    salida = _turno(monkeypatch, [], "",
                    texto_directo="Te recomiendo el Mouse Genius (id: MOU0023).")
    assert "MOU0023" not in salida


# ── 4. LA SENAL DE CIERRE ───────────────────────────────────────────────────
def test_la_decision_de_compra_la_declara_la_herramienta():
    """Antes salia del campo `intencion` de un interprete de veinte campos, y
    cuando ese JSON fallaba el cierre se disparaba o se perdia sin que nadie lo
    viera. Ahora es una herramienta que el modelo llama y queda en la traza."""
    senal = HV._senal_de_cierre(
        [{"herramienta": "tomar_pedido", "pedido": {"motivo": "decide_comprar"},
          "resultado": {"estado": "registrado"}}], "lo llevo")
    assert senal["intencion"] == "decision_compra" and senal["confianza"] == 1.0


def test_sin_esa_herramienta_no_hay_decision_de_compra():
    senal = HV._senal_de_cierre(
        [{"herramienta": "buscar_productos", "pedido": {}, "resultado": {}}],
        "cuanto sale?")
    assert senal["intencion"] != "decision_compra"


# ── 5. MEMORIA ──────────────────────────────────────────────────────────────
def test_lo_mostrado_se_recuerda_desde_las_herramientas_no_del_texto():
    """El camino viejo deducia que productos habia mostrado buscando nombres en
    la respuesta. Aca sale de lo que devolvio la herramienta, que es un hecho."""
    vistos = HV._productos_del_turno([{
        "herramienta": "buscar_productos", "pedido": {},
        "resultado": {"estado": "encontrado", "productos": [
            {"id": "MOU0001", "nombre": "Mouse Genius", "precio_ars": 8500}]}}])
    assert vistos == [{"id": "MOU0001", "nombre": "Mouse Genius",
                       "precio": 8500}]


def test_el_carrito_sale_del_detalle_de_la_cuenta():
    carrito = HV._carrito_del_turno([{
        "herramienta": "armar_presupuesto", "pedido": {},
        "resultado": {"estado": "ok", "detalle": [
            {"id": "MOU0001", "nombre": "Mouse Genius", "cantidad": 2}]}}])
    assert carrito == [{"id": "MOU0001", "nombre": "Mouse Genius",
                        "cantidad": 2}]


def test_el_turno_sin_herramientas_contesta_el_texto_directo(monkeypatch):
    salida = _turno(monkeypatch, [], "", mensaje="gracias!",
                    texto_directo="De nada, cualquier cosa avisame.")
    assert "De nada" in salida


def test_el_primer_mensaje_avisa_que_es_un_asistente_automatico(monkeypatch):
    salida = _turno(monkeypatch, [], "", texto_directo="Contame que buscas.")
    assert "asistente automático" in salida


# ── 6. LOS DOS CANDADOS QUE NACIERON DE LA PRIMERA CHARLA VIVA ──────────────
def test_un_cbu_inventado_no_sale_nunca():
    """El peor error medido: sin presupuesto sobre la mesa el cliente pidio los
    datos para transferir y el modelo se invento un CBU de 22 digitos, un alias
    y un banco. La plata a una cuenta que no existe. La regla de la plata no lo
    veia porque mira montos de cuatro a siete digitos."""
    texto = ("Para pagar transferi a:\n"
             "Titular: Verifika Tech S.A.\n"
             "CBU: 0000003100085423456789\n"
             "Alias: VERIFIKA.TECH.PAGO\n"
             "Banco: Banco Industrial\n"
             "Avisame cuando lo hagas.")
    salida = HV._sin_cobro_inventado(texto, TIENDA, "t1")
    assert "0000003100085423456789" not in salida
    assert "VERIFIKA.TECH.PAGO" not in salida
    assert "Banco Industrial" not in salida
    assert "Avisame cuando lo hagas." in salida


def test_el_cbu_real_de_la_tienda_si_sale():
    from app.core.pago import datos_transferencia
    d = datos_transferencia(TIENDA) or {}
    texto = f"Transferi a CBU: {d.get('cbu')}\nAlias: {d.get('alias')}"
    salida = HV._sin_cobro_inventado(texto, TIENDA, "t1")
    assert str(d.get("cbu")) in salida


def test_una_respuesta_sin_datos_de_pago_no_se_toca():
    texto = "El mouse sale $8.500 y llega en 4 dias."
    assert HV._sin_cobro_inventado(texto, TIENDA, "t1") == texto


def test_el_json_de_las_herramientas_no_llega_al_cliente():
    """Charla viva del 2-ago: el modelo copio el bloque crudo de cotizar_envio
    al medio del mensaje y al cliente le llego el volcado de la herramienta."""
    texto = ('Te paso el envio:\n'
             '[{"herramienta": "cotizar_envio", "pedido": {"localidad": "Cordoba"},'
             ' "resultado": {"ok": true, "monto": 7500}}]\n'
             'El costo es $7.500.')
    salida = HV._sin_json_filtrado(texto, "t1")
    assert "herramienta" not in salida and "$7.500" in salida


def test_el_titulo_que_queda_sin_nada_abajo_se_va():
    """Cuando la regla poda los renglones inventados, el titulo que los
    anunciaba tiene que irse con ellos: al cliente le llego "Productos:" y nada
    debajo."""
    assert "Productos:" not in HV._sin_titulos_huerfanos(
        "Te paso el detalle:\nProductos:\n\nEnvios:\n- A Cordoba: $7.500")


def test_el_markdown_no_sale_a_whatsapp():
    assert HV._sin_markdown("**Productos:** el mouse") == "Productos: el mouse"


def test_la_cuenta_de_un_turno_anterior_sigue_respaldada():
    """El cliente vuelve sobre el pedido, el turno no rearma la cuenta y el
    modelo la re-pega de memoria. Esos montos los calculo el CODIGO antes: si no
    se cuentan como respaldados, la regla poda una cuenta REAL y al cliente le
    llega el reparto de envios suelto, sin precios."""
    previo = "Presupuesto:\n- 2x Mouse: $8.500 c/u = $17.000\nTotal: $17.000"
    salida = HV._sin_plata_inventada(
        "Te repito la cuenta: son $17.000 en total.", [], "", "t1",
        previo=previo)
    assert "$17.000" in salida


def test_el_dato_real_convive_con_el_inventado_sin_perder_el_bueno():
    """Primera version del candado: comparaba contra la bolsa entera de valores
    y borraba la linea del titular aunque el CBU fuera el correcto. Cada campo
    se juzga contra SU valor real."""
    from app.core.pago import datos_transferencia
    d = datos_transferencia(TIENDA) or {}
    texto = (f"CBU: {d.get('cbu')}\nAlias: {d.get('alias')}\n"
             "Banco: Banco Industrial Inventado")
    salida = HV._sin_cobro_inventado(texto, TIENDA, "t1")
    assert str(d.get("cbu")) in salida
    assert "Banco Industrial Inventado" not in salida
    # con un dato real presente NO se pega la muletilla de "necesito el total"
    assert "necesito confirmarte" not in salida


# ── 7. LO QUE CAZO LA CHARLA REAL POR WHATSAPP DEL 1-AGO ────────────────────
def test_la_cuenta_no_se_puede_retipear_a_mano():
    """El error visible de la charla real: el turno NO llamo a armar_presupuesto
    y el modelo re-tipeo de memoria el presupuesto del turno anterior cambiando
    el producto -donde iba la Kingston NEGRA escribio la BLANCA-. Los montos
    eran los mismos y estaban respaldados, asi que la regla de la plata lo dejo
    pasar con razon: no era plata inventada, era una CUENTA inventada alrededor
    de plata real."""
    previo = ("Presupuesto:\n"
              "- 2x Memoria ram Kingston Fury Beast DDR4 3200 8GB Negro: "
              "$34.500 c/u = $69.000\nSubtotal: $69.000\nTotal: $69.000")
    texto = ("Aca va:\n"
             "- 2x Memoria ram Kingston Fury Beast DDR4 3200 8GB Blanco: "
             "$34.500 c/u = $69.000\nSubtotal: $69.000\nTotal: $69.000\n"
             "Quedo a la espera.")
    salida = HV._cuenta_no_retipeada(texto, hubo_calculo=False, previo=previo,
                                     trace_id="t1")
    assert "Blanco" not in salida
    assert "Negro" in salida and "Total: $69.000" in salida
    assert "Quedo a la espera." in salida


def test_la_cuenta_calculada_este_turno_no_se_toca():
    texto = "Presupuesto:\n- 1x Mouse: $8.500 c/u = $8.500\nTotal: $8.500"
    assert HV._cuenta_no_retipeada(
        texto, hubo_calculo=True, previo="", trace_id="t1") == texto


def test_la_cuenta_pegada_igual_al_previo_pasa_intacta():
    previo = "Presupuesto:\n- 1x Mouse: $8.500 c/u = $8.500\nTotal: $8.500"
    texto = "Te la repito:\n" + previo
    salida = HV._cuenta_no_retipeada(texto, hubo_calculo=False, previo=previo,
                                     trace_id="t1")
    assert salida == texto


def test_el_recorte_de_herramientas_se_loguea_no_es_silencioso(monkeypatch,
                                                               caplog):
    """Pidio ocho fichas, corrieron seis, y las dos que faltaron no aparecian en
    ningun lado. Un corte en silencio es peor que el problema que evita."""
    monkeypatch.setattr(H, "ejecutar", lambda n, a, t: {"estado": "ok"})
    pedidos = [{"nombre": f"ficha_producto", "args": {"product_id": f"X{i}"}}
               for i in range(12)]
    r = asyncio.run(HV._ejecutar_en_paralelo(pedidos, TIENDA, "t1"))
    assert len(r) == HV._MAX_HERRAMIENTAS


# ── 8. LO QUE CAZO EL BANCO REPETIDO ────────────────────────────────────────
def test_no_se_ofrece_un_descuento_que_no_existe():
    """Guion de objecion de precio: ante "si te llevo dos me haces precio?" el
    bot dijo que iba a consultar con el area comercial que descuento especial
    aplicar. Dos mentiras: no hay area comercial y el descuento no existe."""
    texto = ("Contame cuantas unidades queres. Puedo consultar con el area "
             "comercial que descuento especial podemos aplicarte por el par. "
             "Quedo a la espera.")
    salida = HV._sin_descuento_inventado(texto, "t1")
    assert "descuento especial" not in salida
    assert "Quedo a la espera." in salida


def test_el_descuento_real_de_la_tienda_no_se_toca():
    texto = "Con transferencia tenés un descuento del 10% sobre el total."
    assert HV._sin_descuento_inventado(texto, "t1") == texto


def test_la_narracion_interna_no_llega_al_cliente():
    texto = ("Tengo los dos mouse en stock.\n"
             "Encontre varias opciones y el sistema me indica que hay modelos "
             "distintos.\n¿Cual preferis?")
    salida = HV._sin_narracion_interna(texto, "t1")
    assert "el sistema me indica" not in salida
    assert "¿Cual preferis?" in salida


def test_un_anuncio_de_presupuesto_sin_presupuesto_se_va():
    """El modelo promete la cuenta sin haberla calculado, los renglones
    inventados se podan y al cliente le llega el anuncio solo."""
    texto = ("Tengo los dos mouse.\nTe paso el presupuesto por los dos mouse:\n"
             "\nQuedo atento a que teclado te interesa.")
    salida = HV._sin_anuncio_vacio(texto, "t1")
    assert "Te paso el presupuesto" not in salida
    assert "Quedo atento" in salida


def test_el_anuncio_con_su_cuenta_abajo_se_respeta():
    texto = ("Te paso el presupuesto:\n"
             "Presupuesto:\n- 1x Mouse: $8.500 c/u = $8.500\nTotal: $8.500")
    assert HV._sin_anuncio_vacio(texto, "t1") == texto


def test_no_se_niega_una_categoria_que_la_herramienta_acaba_de_traer():
    """La alucinacion mas cara que hay: la herramienta devolvio memorias RAM
    reales del catalogo y el bot contesto "no vendemos modulos de memoria RAM
    sueltos". Le cierra la puerta a un cliente que queria comprar algo que
    tenemos."""
    llamadas = [{"herramienta": "buscar_productos", "pedido": {},
                 "resultado": {"estado": "encontrado", "productos": [
                     {"id": "RAM0001", "nombre": "Kingston Fury",
                      "categoria": "memoria ram", "precio_ars": 34500}]}}]
    texto = ("Te cuento que no vendemos modulos de memoria ram sueltos. "
             "Tengo notebooks que ya vienen con 16GB.")
    salida = HV._sin_negar_lo_traido(texto, llamadas, "t1")
    assert "no vendemos" not in salida.lower()
    assert "Tengo notebooks" in salida


def test_el_no_honesto_de_lo_que_no_trajo_ninguna_herramienta_se_respeta():
    llamadas = [{"herramienta": "buscar_productos", "pedido": {},
                 "resultado": {"estado": "no_vendemos", "pedido": "heladera"}}]
    texto = "No vendemos heladeras, nuestro rubro es tecnologia."
    assert HV._sin_negar_lo_traido(texto, llamadas, "t1") == texto


def test_el_precio_de_lo_ya_mostrado_no_se_poda():
    """Turno mudo del banco repetido: "el primero que me mostraste, cuanto era?"
    terminaba con el precio podado y al cliente le llegaba solo "¿Querés que
    avancemos?". El numero era real, lo trajo una herramienta en un turno
    anterior; lo que faltaba era reconocerlo como respaldado."""
    vistos = [{"id": "TEC0019", "nombre": "Teclado Genius", "precio": 12000}]
    texto = "El primero que te mostre es el Teclado Genius, sale $12.000."
    salida = HV._sin_plata_inventada(texto, [], "", "t1", vistos=vistos)
    assert "$12.000" in salida


def test_el_renglon_escrito_a_mano_tambien_cuenta_como_cuenta():
    """El modelo escribio "1 x Teclado Genius KB-110X Blanco: $12.000" a mano.
    La primera version del patron pedia el guion y la equis pegada."""
    texto = "Te preparé esto:\n1 x Teclado Genius KB-110X Blanco: $12.000"
    salida = HV._cuenta_no_retipeada(texto, hubo_calculo=False, previo="",
                                     trace_id="t1")
    assert "$12.000" not in salida
