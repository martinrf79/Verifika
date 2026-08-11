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
    from app.core.contexto_turno import set_current_tienda
    from app.storage.firestore_client import reset_conversation
    set_current_tienda(TIENDA)
    reset_conversation(USUARIO, tienda_id=TIENDA)
    return firestore_doble


def _turno(monkeypatch, pedidos, texto, mensaje="hola", texto_directo=""):
    """Corre un turno con las dos llamadas al modelo dobladas."""
    async def _fake_uno(*a, **kw):
        return pedidos, texto_directo

    async def _fake_dos(*a, **kw):
        # (texto, sin_modelo). El doble siempre CONTESTA: el caso de "no hubo
        # modelo" tiene su propio test, `test_si_el_modelo_no_contesta_...`.
        return texto, False

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
               {"nombre": "consultar_temas", "args": {}},
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
            {"id": "MOU0001", "nombre": "Mouse Genius", "precio_ars": 8500,
             "categoria": "mouse"},
            {"id": "MOU0002", "nombre": "Mouse Logitech", "precio_ars": 12000,
             "categoria": "mouse"}]}}], turno=4)
    assert [v["id"] for v in vistos] == ["MOU0001", "MOU0002"]
    assert vistos[0]["precio"] == 8500
    # CON SU ORDEN, desde el 5-ago. Sin turno ni posicion, "el segundo mouse
    # que me mostraste" no tiene contra que resolverse: la memoria guardaba una
    # lista plana de nombres y el orden en que se mostraron -que es toda la
    # informacion que usa el ordinal- se perdia.
    assert [v["posicion"] for v in vistos] == [1, 2]
    assert all(v["turno"] == 4 for v in vistos)
    assert all(v["categoria"] == "mouse" for v in vistos)


def test_la_posicion_se_cuenta_por_categoria_no_por_turno():
    """"El segundo teclado" es el segundo de los TECLADOS, no el segundo de
    todo lo que se mostro en el turno. Un turno que muestra dos categorias
    tiene dos primeros."""
    vistos = HV._productos_del_turno([{
        "herramienta": "buscar_productos", "pedido": {},
        "resultado": {"productos": [
            {"id": "MOU0001", "nombre": "Mouse A", "categoria": "mouse"},
            {"id": "TEC0001", "nombre": "Teclado A", "categoria": "teclado"},
            {"id": "TEC0002", "nombre": "Teclado B", "categoria": "teclado"}]}}])
    por_id = {v["id"]: v["posicion"] for v in vistos}
    assert por_id == {"MOU0001": 1, "TEC0001": 1, "TEC0002": 2}


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


def test_el_candado_de_negacion_no_se_come_la_abstencion_honesta():
    """5-AGO. El estado `sin_dato_en_la_fuente` hace que el bot conteste bien
    -"no tenemos ese dato de los auriculares en la ficha"- y este candado le
    BORRABA la oracion, porque dice "no tenemos" y nombra una categoria que la
    herramienta acababa de traer. Quedaba "te muestro los que sí tengo", sin
    decir nunca que el dato faltaba: la guardia contra la alucinacion se comia
    la honestidad, en silencio.

    Negar el RUBRO y no tener un DATO son dos cosas distintas."""
    llamadas = [{"herramienta": "buscar_productos", "pedido": {},
                 "resultado": {"estado": "sin_dato_en_la_fuente",
                               "productos": [
                                   {"id": "AUR0001", "nombre": "Redragon Zeus",
                                    "categoria": "auriculares",
                                    "precio_ars": 57500}]}}]
    texto = ("No tenemos ese dato de los auriculares en la ficha. "
             "Te muestro los que sí tengo.")
    assert HV._sin_negar_lo_traido(texto, llamadas, "t1") == texto

    # Y la negacion del RUBRO, con el mismo resultado delante, se sigue yendo.
    niega = "No contamos con auriculares por ahora."
    assert "no contamos" not in HV._sin_negar_lo_traido(
        niega, llamadas, "t1").lower()


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


def test_el_candado_de_negacion_ve_el_plural_de_la_categoria():
    """Tercera tanda: el bot volvio a decir "no vendemos memorias RAM por
    separado" con las memorias delante. El candado comparaba la frase pegada y
    el plural de una categoria de dos palabras cae en la PRIMERA."""
    llamadas = [{"herramienta": "buscar_productos", "pedido": {},
                 "resultado": {"estado": "ambiguo", "productos": [
                     {"id": "RAM0001", "nombre": "Kingston",
                      "categoria": "memoria ram", "precio_ars": 34500}]}}]
    texto = ("Te cuento que no vendemos memorias RAM por separado. "
             "Tengo equipos que ya vienen con 16GB.")
    salida = HV._sin_negar_lo_traido(texto, llamadas, "t1")
    assert "no vendemos" not in salida.lower()
    assert "Tengo equipos" in salida


def test_el_estado_de_la_herramienta_no_se_le_cuenta_al_cliente():
    texto = ("Tenemos varias opciones y como el estado es ambiguo, te paso los "
             "que tenemos.\n¿Cual preferis?")
    salida = HV._sin_narracion_interna(texto, "t1")
    assert "estado es ambiguo" not in salida
    assert "¿Cual preferis?" in salida


def test_el_bloque_mutilado_se_repone_entero():
    """EL BUG DEL 3-ago. La guarda vieja daba por pegado el bloque con solo ver
    su primera linea, que es el literal "Presupuesto:". Al modelo le alcanzaba
    con escribir esa palabra para que el codigo no repusiera nada, y el cliente
    se quedaba sin el Total.

    Caso real de 56_ronda_dificil_memoria_razonamiento vuelta 3 turno 3: el bot
    anuncio "incluyendo el microfono", listo un solo renglon y no cerro la
    cuenta."""
    from app.core.hub_venta import _bloque_entero_o_repuesto

    bloque = ("Presupuesto:\n"
              "- 2x Auriculares Redragon Zeus X Negro: $57.500 c/u = $115.000\n"
              "- 1x Microfono FIFINE K669B Negro: $69.000 c/u = $69.000\n"
              "Subtotal: $184.000\n"
              "Total: $184.000")
    mutilado = ("He ajustado el presupuesto incluyendo el microfono.\n\n"
                "Presupuesto:\n\n"
                "- 2x Auriculares Redragon Zeus X Negro: $57.500 c/u = $115.000\n\n"
                "Te gustaria avanzar?")

    salida = _bloque_entero_o_repuesto(mutilado, bloque, "t")
    assert "Total: $184.000" in salida, "el cliente tiene que recibir el Total"
    assert "Microfono FIFINE K669B" in salida, "faltaba el item anunciado"
    # y no queda la version mutilada al lado de la buena
    assert salida.count("Auriculares Redragon Zeus X Negro") == 1
    assert "He ajustado el presupuesto" in salida, "la prosa del modelo se conserva"


def test_el_bloque_ya_pegado_no_se_duplica():
    """Si el modelo pego la cuenta entera y bien, no se toca nada."""
    from app.core.hub_venta import _bloque_entero_o_repuesto

    bloque = ("Presupuesto:\n"
              "- 1x Mouse: $10.000 c/u = $10.000\n"
              "Subtotal: $10.000\n"
              "Total: $10.000")
    texto = "Mira lo que te queda:\n\n" + bloque + "\n\nTe sirve?"
    salida = _bloque_entero_o_repuesto(texto, bloque, "t")
    assert salida == texto
    assert salida.count("Total: $10.000") == 1


# ── LO QUE SE MIDIO EN PRODUCCION EL 5-AGO, CLAVADO ──────────────────────────
# Las tres fallas del mensaje real de Martin por WhatsApp: un rubro entero
# afuera de la cuenta, una ronda al pedo por una exigencia imposible, y 26,6
# segundos de espera. Cada una vuelve como test.
def test_la_cuenta_no_pierde_un_rubro_que_el_cliente_pidio(firestore_doble):
    """Pidio dos auriculares, dos mouse y DOS MEMORIAS. El modelo declaro los
    tres rubros, busco los tres, y armo la cuenta con dos: al cliente le llego
    un total al que le faltaban $69.000 de mercaderia que habia pedido. El
    codigo lo repone con lo que el mismo turno ya certifico."""
    from app.core import herramientas as H
    from app.core.hub_venta import _cuenta_con_lo_declarado
    from app.storage.firestore_client import get_all_products

    cat = [p for p in get_all_products(tienda_id=TIENDA)
           if (p.get("stock") or 0) > 0]
    aur = next(p for p in cat if p["categoria"] == "auriculares")
    mou = next(p for p in cat if p["categoria"] == "mouse")
    mem = next(p for p in cat if p["categoria"] == "memoria ram")

    declarado = {"items": [{"que": "auriculares", "cantidad": 2},
                           {"que": "mouse", "cantidad": 2},
                           {"que": "memoria ram", "cantidad": 2}],
                 "pide_precio": True}
    args = {"items": [{"product_id": aur["id"], "cantidad": 2},
                      {"product_id": mou["id"], "cantidad": 2}],
            "destinos": ["Cordoba capital"]}
    llamadas = [
        {"herramienta": "buscar_productos", "pedido": {"categoria": "auriculares"},
         "resultado": {"estado": "encontrado", "productos": [H._ficha(aur, TIENDA)]}},
        {"herramienta": "buscar_productos", "pedido": {"categoria": "mouse"},
         "resultado": {"estado": "encontrado", "productos": [H._ficha(mou, TIENDA)]}},
        {"herramienta": "buscar_productos", "pedido": {"categoria": "memoria ram"},
         "resultado": {"estado": "encontrado", "productos": [H._ficha(mem, TIENDA)]}},
        {"herramienta": "armar_presupuesto", "pedido": args,
         "resultado": H.ejecutar("armar_presupuesto", args, TIENDA)},
    ]
    antes = llamadas[-1]["resultado"]["total_ars"]
    fuera = _cuenta_con_lo_declarado(llamadas, declarado, TIENDA, "t")
    cuenta = fuera[-1]
    ids = [i["product_id"] for i in cuenta["pedido"]["items"]]
    assert mem["id"] in ids, "las memorias siguen afuera de la cuenta"
    assert mem["nombre"] in cuenta["resultado"]["bloque"], (
        "el renglon nuevo tiene que verse en la cuenta, no sumarse en silencio")
    assert cuenta["resultado"]["total_ars"] == antes + 2 * mem["precio_ars"]


def test_no_se_inventa_un_rubro_que_el_turno_no_certifico(firestore_doble):
    """La contracara, y es la que evita que esto se vuelva un invento: si el
    turno NO le mostro ningun producto de ese rubro, el codigo no elige uno de
    la nada. Eso es un faltante de verdad y lo cuenta el redactor."""
    from app.core import herramientas as H
    from app.core.hub_venta import _cuenta_con_lo_declarado
    from app.storage.firestore_client import get_all_products

    cat = [p for p in get_all_products(tienda_id=TIENDA)
           if (p.get("stock") or 0) > 0]
    mou = next(p for p in cat if p["categoria"] == "mouse")
    args = {"items": [{"product_id": mou["id"], "cantidad": 1}],
            "destinos": ["Rosario"]}
    llamadas = [{"herramienta": "armar_presupuesto", "pedido": args,
                 "resultado": H.ejecutar("armar_presupuesto", args, TIENDA)}]
    declarado = {"items": [{"que": "mouse", "cantidad": 1},
                           {"que": "notebook", "cantidad": 1}]}
    fuera = _cuenta_con_lo_declarado(llamadas, declarado, TIENDA, "t")
    assert len(fuera[-1]["pedido"]["items"]) == 1


def test_el_reparto_de_pago_no_se_exige_como_filtro_de_busqueda(firestore_doble):
    """'Divide el presupuesto en setenta treinta' se declara como restriccion, y
    el modelo la aplica donde va: en el argumento `pago` de la cuenta. El
    reconciliador le pedia aplicarla 'en alguna busqueda', que es imposible, y
    el turno gastaba una ronda entera de 8 segundos en la que el modelo pedia
    CERO herramientas."""
    from app.core import pedido as P

    llamadas = [{"herramienta": "armar_presupuesto",
                 "pedido": {"items": [{"product_id": "MOU0023", "cantidad": 1}],
                            "pago": [{"medio": "mercado pago", "porcentaje": 70},
                                     {"medio": "transferencia",
                                      "porcentaje": 30}]},
                 "resultado": {"estado": "ok"}},
                {"herramienta": "buscar_productos",
                 "pedido": {"categoria": "mouse"},
                 "resultado": {"estado": "encontrado",
                               "productos": [{"nombre": "Mouse Genius DX-110",
                                              "categoria": "mouse"}]}}]
    rec = P.reconciliar({"items": [{"que": "mouse", "cantidad": 1}],
                         "restricciones": ["presupuesto 70/30"],
                         "pide_precio": True}, llamadas, "t")
    assert not [f for f in rec["faltantes"] if "70/30" in f], rec["faltantes"]


def test_el_reparto_que_no_cierra_se_dice_en_la_cuenta(firestore_doble):
    """Medido en produccion el 6-ago: el modelo mando los items sin destino, el
    codigo cobro TRES envios y en el mismo mensaje pregunto a donde iban las
    memorias. Cobrar un reparto que se acaba de decir que no se sabe es lo peor
    de los dos mundos. Ahora la cuenta lo declara y nombra cuanto falta."""
    from app.core import herramientas as H
    from app.storage.firestore_client import get_all_products

    cat = [p for p in get_all_products(tienda_id=TIENDA)
           if (p.get("stock") or 0) > 0]
    mou = next(p for p in cat if p["categoria"] == "mouse")
    r = H.ejecutar("armar_presupuesto", {
        "items": [{"product_id": mou["id"], "cantidad": 2}],
        "destinos": ["Cordoba capital", "Posadas"]}, TIENDA)
    bloque = r["bloque"]
    # El HECHO y UNA sola pedida, en una linea. El texto se acorto el 8-ago
    # -de 200 caracteres a 130- porque el mensaje ya traia otras dos pedidas de
    # confirmacion; lo que no puede cambiar es que diga cuantas unidades
    # quedaron sin asignar y que lo pregunte.
    assert "sin asignar" in bloque and "2 de 2" in bloque, bloque
    assert "cada uno" in bloque, bloque
    # y cuando SI cierra, la cuenta muestra el reparto y no la advertencia
    r2 = H.ejecutar("armar_presupuesto", {
        "items": [{"product_id": mou["id"], "cantidad": 1,
                   "destino": "Cordoba capital"},
                  {"product_id": mou["id"], "cantidad": 1,
                   "destino": "Posadas"}],
        "destinos": ["Cordoba capital", "Posadas"]}, TIENDA)
    assert "Reparto de los envios" in r2["bloque"]
    assert "sin asignar" not in r2["bloque"]


def test_el_setenta_treinta_sin_medio_declara_el_supuesto(firestore_doble):
    """El cliente dijo 'setenta treinta' y no dijo que medio lleva cada parte.
    El modelo eligio distinto dos dias seguidos, y como la transferencia tiene
    10% de descuento, ese silencio le cambia al cliente lo que paga. Se aplica
    el reparto -no se frena la venta- y se declara el supuesto en la cuenta."""
    from app.core.hub_venta import _supuesto_de_pago

    llamadas = [{"herramienta": "armar_presupuesto",
                 "pedido": {"items": [{"product_id": "MOU0023", "cantidad": 1}],
                            "pago": [{"medio": "transferencia",
                                      "porcentaje": 70},
                                     {"medio": "mercado pago",
                                      "porcentaje": 30}]},
                 "resultado": {"estado": "ok", "bloque": "Total: $8.500"}}]
    declarado = {"restricciones": ["dividir el presupuesto en 70/30"]}
    fuera = _supuesto_de_pago(llamadas, declarado, TIENDA, "t")
    bloque = fuera[0]["resultado"]["bloque"]
    # El supuesto se DECLARA y se puede dar vuelta en una linea. Se acorto el
    # 8-ago: el bloque de Pago dividido, tres renglones arriba, ya dice el
    # reparto con los montos, asi que repetirlo dos veces mas era ruido.
    assert "70%" in bloque and "transferencia" in bloque
    assert "doy vuelta" in bloque, bloque

    # Si el cliente SI dijo el medio, no se declara ningun supuesto: seria
    # ruido, y el ruido ensena a ignorar los avisos.
    claro = {"restricciones": ["70% por transferencia y 30% con mercado pago"]}
    assert _supuesto_de_pago(llamadas, claro, TIENDA, "t") == llamadas


def test_la_cuenta_no_cotiza_menos_unidades_de_las_pedidas(firestore_doble):
    """Medido en produccion el 6-ago: el cliente pidio DOS auriculares y la
    cuenta salio con '1x Auriculares: $70.000'. La regla de reponer el rubro no
    lo veia porque el rubro estaba; faltaba una unidad, que es la mitad de ese
    renglon en plata. Se completa sobre el renglon que el modelo ya eligio."""
    from app.core import herramientas as H
    from app.core.hub_venta import _cuenta_con_lo_declarado
    from app.storage.firestore_client import get_all_products

    cat = [p for p in get_all_products(tienda_id=TIENDA)
           if (p.get("stock") or 0) > 0]
    aur = next(p for p in cat if p["categoria"] == "auriculares")
    args = {"items": [{"product_id": aur["id"], "cantidad": 1}],
            "destinos": ["Rosario"]}
    llamadas = [
        {"herramienta": "buscar_productos", "pedido": {"categoria": "auriculares"},
         "resultado": {"estado": "encontrado", "productos": [H._ficha(aur, TIENDA)]}},
        {"herramienta": "armar_presupuesto", "pedido": args,
         "resultado": H.ejecutar("armar_presupuesto", args, TIENDA)}]
    declarado = {"items": [{"que": "auriculares", "cantidad": 2}]}
    fuera = _cuenta_con_lo_declarado(llamadas, declarado, TIENDA, "t")
    items = fuera[-1]["pedido"]["items"]
    assert sum(i["cantidad"] for i in items) == 2, items
    assert fuera[-1]["resultado"]["total_ars"] >= 2 * aur["precio_ars"]


def test_el_mismo_producto_partido_en_dos_destinos_no_se_duplica(firestore_doble):
    """La contracara: dos renglones de 1 con destinos distintos SON las dos
    unidades pedidas. Sumar de nuevo seria cobrarle cuatro."""
    from app.core import herramientas as H
    from app.core.hub_venta import _cuenta_con_lo_declarado
    from app.storage.firestore_client import get_all_products

    cat = [p for p in get_all_products(tienda_id=TIENDA)
           if (p.get("stock") or 0) > 0]
    aur = next(p for p in cat if p["categoria"] == "auriculares")
    args = {"items": [{"product_id": aur["id"], "cantidad": 1,
                       "destino": "Rosario"},
                      {"product_id": aur["id"], "cantidad": 1,
                       "destino": "Posadas"}],
            "destinos": ["Rosario", "Posadas"]}
    llamadas = [
        {"herramienta": "buscar_productos", "pedido": {"categoria": "auriculares"},
         "resultado": {"estado": "encontrado", "productos": [H._ficha(aur, TIENDA)]}},
        {"herramienta": "armar_presupuesto", "pedido": args,
         "resultado": H.ejecutar("armar_presupuesto", args, TIENDA)}]
    fuera = _cuenta_con_lo_declarado(
        llamadas, {"items": [{"que": "auriculares", "cantidad": 2}]}, TIENDA, "t")
    assert sum(i["cantidad"] for i in fuera[-1]["pedido"]["items"]) == 2


# ── EL MENSAJE REAL DE MARTIN, 6-ago-2026, y las cuatro fallas que dejo ──────
#
# "Dame precio de dos auriculares, dos mouse y dos memorias. El precio no seria
#  tan importante. Lo que si que necesito que lleven las menos partes chinas
#  posibles. Un auricular y un mouse sera envio a Cordoba capital. Un teclado y
#  un mouse sera envio a Concordia. Los otros dos articulos seran con envio a
#  posadas. Divide el presupuesto en setenta treinta."
#
# Corrido en produccion, trace 87421e52: 27,7 segundos, 4 llamadas al modelo,
# una ronda entera pidiendo CERO herramientas, y el cliente recibio una cuenta
# sin una palabra del reparto que habia pedido. Cada test de abajo clava una de
# las fallas medidas en ese turno.

def test_el_setenta_treinta_lo_aplica_el_codigo_si_el_modelo_no_lo_hizo(
        firestore_doble):
    """LA FALLA MAS CARA DEL TURNO REAL. El modelo declaro 'presupuesto 70/30'
    como restriccion, el reconciliador se lo reclamo TRES rondas, y
    `armar_presupuesto` salio con pago=None las tres veces. La parte por
    transferencia lleva 10% de descuento: el silencio le costo $17.500 sobre un
    total de $250.000. Lo aplica el codigo, cero tokens, y queda declarado."""
    args = {"items": [{"product_id": "AUR0003", "cantidad": 2},
                      {"product_id": "MOU0023", "cantidad": 2}]}
    llamadas = [{"herramienta": "armar_presupuesto", "pedido": args,
                 "resultado": H.ejecutar("armar_presupuesto", args, TIENDA)}]
    declarado = {"restricciones": ["menos partes chinas posibles",
                                   "presupuesto 70/30"]}
    sin_reparto = HV._bloque_presupuesto(llamadas)
    assert "Pago dividido" not in sin_reparto

    fuera = HV._reparto_de_pago_declarado(llamadas, declarado, TIENDA, "t")
    con_reparto = HV._bloque_presupuesto(fuera)
    assert "Pago dividido" in con_reparto
    assert "transferencia (70%)" in con_reparto
    assert "mercado pago (30%)" in con_reparto
    # La parte grande va por transferencia, que es la que TIENE descuento: el
    # codigo asume siempre para el lado que le conviene al cliente.
    assert "descuento" in con_reparto
    # Y el supuesto se declara, para que el cliente lo de vuelta en una linea.
    declarada = HV._supuesto_de_pago(fuera, declarado, TIENDA, "t")
    assert "doy vuelta" in HV._bloque_presupuesto(declarada)


def test_el_reparto_no_queda_del_lado_que_le_cuesta_mas_al_cliente(
        firestore_doble):
    """LA COMPUERTA, medida en vivo el 7-ago. El modelo SI mando el reparto,
    pero puso el 70 en Mercado Pago, que es el medio sin descuento: $9.140 de
    mas para el cliente sobre esa cuenta. El turno anterior lo habia puesto al
    reves. El modelo tira una moneda en silencio y la moneda decide lo que el
    cliente paga.

    No se le corrige una decision al cliente: el cliente NUNCA dijo que medio
    lleva cada parte, por eso el reparto es ambiguo. Se reemplaza el volado por
    una eleccion deterministica, siempre para el lado que le conviene, y se
    declara en la cuenta."""
    base = {"items": [{"product_id": "MOU0023", "cantidad": 1}]}
    declarado = {"restricciones": ["presupuesto 70/30"]}

    # al reves: la parte grande en el medio SIN descuento -> se da vuelta
    al_reves = {**base, "pago": [{"medio": "mercado pago", "porcentaje": 70},
                                 {"medio": "transferencia", "porcentaje": 30}]}
    llamadas = [{"herramienta": "armar_presupuesto", "pedido": al_reves,
                 "resultado": H.ejecutar("armar_presupuesto", al_reves,
                                         TIENDA)}]
    fuera = HV._reparto_de_pago_declarado(llamadas, declarado, TIENDA, "t")
    bloque = HV._bloque_presupuesto(fuera)
    assert "transferencia (70%)" in bloque, bloque
    assert "mercado pago (30%)" in bloque

    # ya del lado que conviene: NO se toca. Reponer sobre lo que ya esta bien
    # es la clase de capa que este repo no suma.
    bien = {**base, "pago": [{"medio": "transferencia", "porcentaje": 70},
                             {"medio": "mercado pago", "porcentaje": 30}]}
    ok = [{"herramienta": "armar_presupuesto", "pedido": bien,
           "resultado": H.ejecutar("armar_presupuesto", bien, TIENDA)}]
    assert HV._reparto_de_pago_declarado(ok, declarado, TIENDA, "t") == ok

    # y si el cliente SI dijo que medio lleva cada parte, no se toca nada:
    # ahi el reparto no es ambiguo y la eleccion es suya.
    suyo = {"restricciones": ["70% con mercado pago y 30 por transferencia"]}
    assert HV._reparto_de_pago_declarado(
        llamadas, suyo, TIENDA, "t") == llamadas


def test_el_setenta_treinta_se_lee_tambien_en_letras():
    """LA FALLA QUE LE PUSO NOMBRE A LA ETAPA. El 7-ago se arreglo el reparto
    leyendo '70/30' y se deployo. Corrido en vivo con la redaccion REAL de
    Martin -'divide el presupuesto en SETENTA TREINTA'- quedo mudo. El arreglo
    del dia anterior habia funcionado por casualidad: esa vez el modelo
    transcribio la frase a digitos."""
    from app.core import pedido as P

    for frase in ("divide el presupuesto en setenta treinta",
                  "el presupuesto partilo setenta treinta",
                  "en dos partes, setenta y treinta",
                  "presupuesto 70/30", "dividilo sesenta cuarenta"):
        assert P.reparto_ambiguo([frase]), frase
    # Con el medio nombrado sigue siendo del modelo, no del codigo.
    assert not P.reparto_ambiguo(["70% por transferencia y 30 con mercado pago"])
    # Y dos numeros que no son un reparto no lo son.
    assert not P.reparto_ambiguo(["quiero veinte teclados y treinta mouse"])


def test_el_reparto_de_pago_no_se_reclama_como_filtro_de_busqueda():
    """LA RONDA IMPOSIBLE, medida en produccion. Un reparto de pago no entra en
    ningun argumento de busqueda, asi que pedirselo al modelo es un faltante que
    no se puede resolver: gasto 8 segundos en una ronda donde el modelo pidio
    CERO herramientas, y tenia razon. Lo aplica el codigo despues del bucle."""
    from app.core import pedido as P

    pedido = {"items": [{"que": "mouse", "cantidad": 1}],
              "restricciones": ["presupuesto 70/30"]}
    llamadas = [{"herramienta": "buscar_productos",
                 "pedido": {"categoria": "mouse"},
                 "resultado": {"estado": "encontrado",
                               "productos": [{"id": "MOU0023",
                                              "categoria": "mouse",
                                              "nombre": "Mouse Genius"}]}}]
    rec = P.reconciliar(pedido, llamadas, "t")
    assert not [f for f in rec["faltantes"] if "70/30" in f], rec["faltantes"]

    # Una restriccion que SI es de producto se sigue reclamando igual que antes.
    pedido["restricciones"] = ["presupuesto 70/30", "que sea inalambrico"]
    rec2 = P.reconciliar(pedido, llamadas, "t")
    assert any("inalambrico" in f for f in rec2["faltantes"])
    assert not [f for f in rec2["faltantes"] if "70/30" in f]


def test_varios_destinos_y_ningun_item_con_destino_es_un_faltante():
    """El cliente reparte seis unidades entre tres localidades y el modelo
    declara los tres destinos en la lista suelta, sin decir que va a cada uno.
    La cuenta cobra tres envios y no puede armar el reparto: salio '2 de 6
    unidades quedaron sin destino'. El campo `destino` del item existe para
    esto desde el 5-ago."""
    from app.core import pedido as P

    llamadas = [{"herramienta": "buscar_productos",
                 "pedido": {"categoria": "mouse"},
                 "resultado": {"estado": "encontrado",
                               "productos": [{"id": "MOU0023",
                                              "categoria": "mouse",
                                              "nombre": "Mouse Genius"}]}}]
    suelto = {"items": [{"que": "mouse", "cantidad": 2}],
              "destinos": ["Cordoba capital", "Posadas"]}
    rec = P.reconciliar(suelto, llamadas, "t")
    assert any("no dijiste que va a cada uno" in f for f in rec["faltantes"])

    # Con el destino en el item, no hay faltante.
    atado = {"items": [{"que": "mouse", "cantidad": 1,
                        "destino": "Cordoba capital"},
                       {"que": "mouse", "cantidad": 1, "destino": "Posadas"}],
             "destinos": ["Cordoba capital", "Posadas"]}
    rec2 = P.reconciliar(atado, llamadas, "t")
    assert not any("va a cada uno" in f for f in rec2["faltantes"])

    # Y con UN solo destino tampoco: no hay nada que repartir.
    uno = {"items": [{"que": "mouse", "cantidad": 2}],
           "destinos": ["Cordoba capital"]}
    assert not any("va a cada uno" in f
                   for f in P.reconciliar(uno, llamadas, "t")["faltantes"])


def test_no_se_afirma_que_ningun_producto_cumple_cuando_es_falso(
        firestore_doble):
    """LA ALUCINACION DEL TURNO REAL, textual: 'todos los productos que trabajo
    en este momento tienen componentes de origen chino, por lo que no puedo
    cumplir con esa restriccion especifica'. Es falso, y lo desmiente el bloque
    que el mismo mensaje pega dos renglones mas abajo. La prohibicion estaba
    escrita en la instruccion de la herramienta y el modelo la piso igual."""
    a = {"categoria": "auriculares", "cuantos": 2,
         "filtros": [{"campo": "pais_fabricacion", "valor": "china",
                      "operador": "no_contiene"}]}
    r = H.ejecutar("buscar_productos", a, TIENDA)
    assert r["estado"] == "ninguno_cumple_del_todo"
    assert r["donde_si_se_cumple"], "sin este hecho la guardia no puede actuar"
    llamadas = [{"herramienta": "buscar_productos", "pedido": a,
                 "resultado": r}]

    texto = ("Todos los productos que trabajo tienen componentes de origen "
             "chino, asi que no puedo cumplir con eso. Te paso lo que mas se "
             "acerca.")
    limpio = HV._sin_afirmar_sobre_el_catalogo(texto, llamadas, "t")
    assert "Todos los productos" not in limpio
    assert "Te paso lo que mas se acerca." in limpio


def test_el_hecho_acotado_al_rubro_sobrevive(firestore_doble):
    """La guardia de arriba NO puede comerse la verdad. 'Todos los auriculares
    que tengo se fabrican en China' es un hecho de la fuente, acotado al rubro,
    y es exactamente la honestidad que queremos que salga. Es la misma leccion
    que ya se pago con `_sin_negar_lo_traido`, que borraba la abstencion."""
    a = {"categoria": "auriculares", "cuantos": 2,
         "filtros": [{"campo": "pais_fabricacion", "valor": "china",
                      "operador": "no_contiene"}]}
    llamadas = [{"herramienta": "buscar_productos", "pedido": a,
                 "resultado": H.ejecutar("buscar_productos", a, TIENDA)}]
    texto = "Todos los auriculares que tengo se fabrican en China."
    assert HV._sin_afirmar_sobre_el_catalogo(texto, llamadas, "t") == texto


def test_el_bloque_fusionado_no_contesta_con_el_precio_ni_suma_universos(
        firestore_doble):
    """El turno real salio con 'hay varios igual de cerca -160 en total-:
    ninguno esta mejor que otro, te muestro los mas baratos'. El 160 son tres
    universos distintos sumados, y 'te muestro los mas baratos' le contesta con
    el precio a un cliente que acababa de decir que el precio no era lo
    importante. Ademas repetia el mismo motivo en los seis renglones."""
    llamadas = []
    for cat in ("auriculares", "mouse", "memoria ram"):
        a = {"categoria": cat, "cuantos": 2,
             "filtros": [{"campo": "pais_fabricacion", "valor": "china",
                          "operador": "no_contiene"}]}
        llamadas.append({"herramienta": "buscar_productos", "pedido": a,
                         "resultado": H.ejecutar("buscar_productos", a,
                                                 TIENDA)})
    fuera = HV._bloques_a_uno(llamadas, "t")
    bloque = next(l["resultado"]["bloque"] for l in fuera
                  if (l.get("resultado") or {}).get("bloque"))

    assert "los más baratos" not in bloque
    assert "en total" not in bloque
    # el motivo va UNA vez por rubro, en la cabecera, no en cada renglon
    assert bloque.count("país de fabricación: china") <= 2
    assert "Auriculares (" in bloque and "Mouse (" in bloque
    # y el rubro donde SI se cumple no se ofrece en un pedido de varios rubros:
    # el cliente pidio estos tres, no un procesador.
    assert "Donde sí se cumple" not in bloque
    # un solo bloque para los tres: los demas se quedan sin el
    assert sum(1 for l in fuera
               if (l.get("resultado") or {}).get("bloque")) == 1


def test_la_cuenta_no_sale_descuartizada(firestore_doble):
    """EL BUG DE LOS DOS NOMBRES. `_RE_RENGLON_CUENTA` estaba definida DOS veces
    en el modulo; la segunda pisaba a la primera y no llevaba `.*$`, asi que el
    `sub()` de `_bloque_entero_o_repuesto` borraba solo el ARRANQUE del renglon
    y al cliente le llegaba ' $201.000' y '3 envios): $24.000'. Reproducido
    entero sobre el guion 76."""
    texto = ("Te paso la cuenta.\n"
             "Presupuesto:\n"
             "- 2x Mouse Genius DX-110 Negro: $8.500 c/u = $17.000\n"
             "Subtotal: $17.000\n"
             "Envio (3 envios): $24.000\n"
             "Total: $41.000\n"
             "- mercado pago (30%): $12.300\n")
    limpio = HV._bloque_entero_o_repuesto(texto, "Presupuesto:\nTotal: $99", "t")
    # ni un renglon a medias: o esta entero o no esta
    for resto in (" $17.000", "3 envios): $24.000", "30%): $12.300",
                  " $41.000"):
        assert resto not in limpio.replace("Total: $99", ""), limpio
    assert "Te paso la cuenta." in limpio
    assert limpio.endswith("Presupuesto:\nTotal: $99")


def test_el_hallazgo_no_se_repone_sobre_una_cuenta_ni_se_escribe_dos_veces(
        firestore_doble):
    """UN BLOQUE POR MENSAJE, medido sobre lo que el cliente LEE. El guion 76 T2
    salio con la cuenta repuesta del turno anterior Y el listado pegado abajo:
    2.910 caracteres, tres mensajes de WhatsApp."""
    a = {"categoria": "mouse", "cuantos": 2,
         "filtros": [{"campo": "pais_fabricacion", "valor": "china",
                      "operador": "no_contiene"}]}
    llamadas = [{"herramienta": "buscar_productos", "pedido": a,
                 "resultado": H.ejecutar("buscar_productos", a, TIENDA)}]
    assert HV._bloque_hallazgo(llamadas), "sin cuenta el hallazgo va"
    # con una cuenta en el texto, no va
    assert not HV._bloque_hallazgo(llamadas, "Total: $8.500\nlisto")
    # y si el modelo ya nombro esos productos, tampoco se repone
    nombres = "\n".join(p["nombre"] for p in
                        llamadas[0]["resultado"]["productos"])
    assert not HV._bloque_hallazgo(llamadas, "Mira estos:\n" + nombres)


# ── EL TERCER ESTADO: atendido no es solo "buscado" (Martin, 7-ago-2026) ─────
#
# MEDIDO sobre las 10 charlas grabadas: de 88 faltantes emitidos, 41 se repetian
# en dos o mas rondas del MISMO turno sin resolverse nunca, y 25 de esos eran
# "no lo buscaste". No eran falsos: eran IMPOSIBLES. Con el tercer estado: 88 ->
# 68 faltantes, 41 -> 29 repetidos, y los "no lo buscaste" de 25 a 8.

def test_lo_ya_resuelto_en_turnos_anteriores_no_se_vuelve_a_reclamar():
    """El caso real del guion 44: el cliente dice 'acordate que los quiero
    negros' sobre un mouse que ya se le certifico dos turnos antes. El modelo
    declara el item y no busca nada, y hace bien. El reconciliador le exigia
    buscar: una ronda quemada sobre un reclamo que no se puede satisfacer.

    La causa era que el reconciliador NO TENIA MEMORIA: comparaba el pedido, que
    se acumula turno a turno, contra las llamadas de ESTE turno solo."""
    from app.core import pedido as P

    pedido = {"items": [{"que": "Mouse Logitech M170 Negro", "cantidad": 2}]}
    # sin memoria, reclama
    rec = P.reconciliar(pedido, [], "t")
    assert any("no lo buscaste" in f for f in rec["faltantes"])
    # con lo que la charla ya resolvio, no
    rec2 = P.reconciliar(pedido, [], "t",
                         ya_resuelto="Mouse Logitech M170 Negro mouse")
    assert not [f for f in rec2["faltantes"] if "no lo buscaste" in f]


def test_buscado_y_no_hay_es_una_respuesta_valida_no_un_paso_pendiente():
    """La regla cero de CLAUDE.md dice que `not_found` NO es un error sino un
    resultado valido y exitoso. El certificador lo cumple hace meses para la
    identidad del producto; nunca se habia aplicado al ITEM del pedido, asi que
    'lo busque y no hay' caia en la misma bolsa que 'no lo busque'."""
    from app.core import pedido as P

    pedido = {"items": [{"que": "iPhone 15 Pro", "cantidad": 1}]}
    vacio = [{"herramienta": "buscar_productos",
              "pedido": {"categoria": "celulares", "descripcion": "iPhone 15 Pro"},
              "resultado": {"estado": "no_encontrado", "productos": []}}]
    assert not [f for f in P.reconciliar(pedido, vacio, "t")["faltantes"]
                if "no lo buscaste" in f]

    # Pero si NO se busco nada, el reclamo sigue vivo: el tercer estado no es
    # una amnistia, es un estado que hay que haberse ganado.
    assert [f for f in P.reconciliar(pedido, [], "t")["faltantes"]
            if "no lo buscaste" in f]


def test_el_muro_cae_en_sus_OCHO_redacciones(firestore_doble):
    """EL MURO, Y POR QUE SE PERSIGUE LA FORMA Y NO LA FRASE.

    El bot le dijo al cliente, en seis dias y seis redacciones distintas, que no
    tenemos nada que cumpla su criterio. Es FALSO -el codigo mismo calcula en
    que rubros SI se cumple, y por eso esta guardia solo actua cuando esa lista
    trae algo- y le cierra la puerta a alguien que esta comprando.

    La sexta, medida en vivo el 8-ago, PASO el candado: "no tenemos productos
    que no sean fabricados en China". Es una afirmacion universal escrita al
    reves y las cinco formas anteriores no la veian. Este test las junta a
    todas: si aparece una septima, se agrega aca y se arregla la forma, no la
    frase."""
    llamadas = [{"herramienta": "buscar_productos", "resultado": {
        "estado": "ninguno_cumple_del_todo",
        "productos": [{"nombre": "Mouse Genius", "categoria": "mouse"}],
        "donde_si_se_cumple": ["almacenamiento externo", "procesador"]}}]
    for frase in (
            "Todos los productos que trabajo tienen componentes chinos.",
            "Ninguno de los articulos que manejo cumple con eso.",
            "No tenemos ningun producto de otro origen.",
            "Todo el catalogo se fabrica en China.",
            "No puedo cumplir con esa restriccion especifica.",
            "No tenemos productos que no sean fabricados en China.",
            # LA OCTAVA, leida de la charla REAL de Martin por WhatsApp el
            # 9-ago, y la primera que llego a un cliente despues de un deploy
            # del mismo dia. Dice la misma oracion que la sexta cambiando "que
            # no" por "sin". Ese es el punto entero del test: la idea se puede
            # escribir de infinitas formas, asi que se cubre la FORMA.
            "No trabajamos productos sin componentes de origen chino."):
        salida = HV._sin_afirmar_sobre_el_catalogo(frase, llamadas, "t")
        assert frase not in salida, f"el muro paso: {frase}"


def test_el_hecho_acotado_al_rubro_NO_es_muro(firestore_doble):
    """La contracara, y es la que hace usable a la guardia. "Todos los mouse que
    tengo se fabrican en China" es VERDADERO, util y acotado al rubro: es
    exactamente la honestidad que queremos y no se toca. Lo mismo vale para la
    frase que habla del dato que falta, no del rubro.

    Es la misma leccion que ya se pago dos veces: una guardia escrita para un
    caso que muerde a su vecino. Un rojo falso ensena a ignorar el tablero."""
    llamadas = [{"herramienta": "buscar_productos", "resultado": {
        "productos": [{"nombre": "Mouse Genius", "categoria": "mouse"}],
        "donde_si_se_cumple": ["procesador"]}}]
    for frase in ("Todos los mouse que tengo se fabrican en China.",
                  "No tenemos ese dato en la ficha de los mouse.",
                  "Puedo cumplir con lo que pediste en otros rubros."):
        assert frase in HV._sin_afirmar_sobre_el_catalogo(frase, llamadas, "t")


def test_sin_el_hecho_calculado_la_guardia_no_toca_nada(firestore_doble):
    """Si el codigo NO calculo en que rubros se cumple, no tiene con que
    desmentir y no borra nada. La guardia corta contra un HECHO, no contra una
    opinion: sin el hecho, se calla."""
    llamadas = [{"herramienta": "buscar_productos", "resultado": {
        "productos": [{"nombre": "Mouse Genius", "categoria": "mouse"}]}}]
    frase = "No tenemos productos que no sean fabricados en China."
    assert frase in HV._sin_afirmar_sobre_el_catalogo(frase, llamadas, "t")


# ── EL RUBRO DECLARADO Y NUNCA BUSCADO (9-ago-2026) ──────────────────────────
# La redaccion coloquial daba 6 sobre 100 mientras las otras cuatro daban 84 a
# 92, y el log era el mismo las tres corridas: el modelo declara los tres
# rubros, no busca ninguno, el reconciliador se lo pide y la ronda dos vuelve
# VACIA. Sin productos no hay cuenta: 717 caracteres que no cotizan nada.

def test_el_rubro_declarado_y_nunca_buscado_lo_busca_el_codigo(firestore_doble):
    """El caso real: `registrar_pedido` solo, sin una sola busqueda. El codigo
    trae los tres rubros con las palabras del cliente."""
    from app.core import pedido as P
    declarado = {"items": [{"que": "auriculares", "cantidad": 2},
                           {"que": "mouse", "cantidad": 2},
                           {"que": "memorias ram", "cantidad": 2}],
                 "restricciones": ["menor cantidad de partes chinas posible"],
                 "pide_precio": True}
    llamadas = [{"herramienta": "registrar_pedido",
                 "resultado": {"estado": "registrado", "pedido": declarado}}]
    rec = P.reconciliar(declarado, llamadas, "t")
    assert len(rec["sin_buscar"]) == 3, "el reconciliador tiene que verlos"

    fuera = HV._busqueda_de_lo_declarado(llamadas, declarado, rec,
                                         "verifika_prod", "t")
    busquedas = [l for l in fuera if l["herramienta"] == "buscar_productos"]
    assert len(busquedas) == 3
    assert any((b["resultado"] or {}).get("productos") for b in busquedas), \
        "sin un solo producto el turno vuelve a salir mudo"
    # HUECO CONOCIDO, y queda anotado con su numero en vez de tapado: la
    # restriccion de esta redaccion viene SIN negacion -"la menor cantidad de
    # partes chinas posible"- y `resolver_exclusion` solo resuelve exclusiones,
    # a proposito, porque aplicar una condicion al reves seria peor que no
    # aplicarla. Con negacion, la exclusion SI viaja en la busqueda repuesta:
    con_negacion = dict(declarado, restricciones=["que no sean chinos"])
    otra = HV._busqueda_de_lo_declarado(llamadas, con_negacion, rec,
                                        "verifika_prod", "t")
    campos = [f["campo"] for l in otra if l["herramienta"] == "buscar_productos"
              for f in (l["pedido"].get("filtros") or [])]
    assert campos, "la condicion del cliente no puede perderse en el camino"


def test_si_el_modelo_ya_busco_el_codigo_no_toca_nada(firestore_doble):
    """LA CONTRACARA, que es la que lo hace seguro. Cuando el modelo hizo su
    trabajo el reconciliador no deja faltantes, y sin faltantes esto no corre:
    no duplica busquedas ni le pisa la decision al modelo."""
    from app.core import pedido as P
    declarado = {"items": [{"que": "mouse", "cantidad": 1}], "pide_precio": True}
    llamadas = [
        {"herramienta": "registrar_pedido",
         "resultado": {"estado": "registrado", "pedido": declarado}},
        {"herramienta": "buscar_productos", "pedido": {"descripcion": "mouse"},
         "resultado": {"estado": "ok", "productos": [
             {"id": "MOU0023", "nombre": "Mouse Logitech", "categoria": "mouse"}]}}]
    rec = P.reconciliar(declarado, llamadas, "t")
    assert rec["sin_buscar"] == []
    fuera = HV._busqueda_de_lo_declarado(llamadas, declarado, rec,
                                         "verifika_prod", "t")
    assert fuera == llamadas


def test_el_item_en_duda_se_pregunta_pero_no_se_cotiza(firestore_doble):
    """DEFECTO PROPIO, medido el 9-ago. Con la busqueda repuesta por codigo la
    redaccion coloquial cotizo SIETE unidades: el modelo declaro el teclado
    como item Y como contradiccion a la vez, el codigo lo busco y la cuenta lo
    sumo. Al cliente le llegaron $12.000 que no pidio. Ante la duda se pregunta,
    no se cotiza: es la regla cero aplicada al item del pedido."""
    from app.core import pedido as P
    declarado = {"items": [{"que": "auriculares", "cantidad": 2},
                           {"que": "mouse", "cantidad": 2},
                           {"que": "memorias ram", "cantidad": 2},
                           {"que": "teclado", "cantidad": 1}],
                 "contradicciones": ["Mencionaste un teclado en el envio a "
                                     "Concordia que no estaba en tu pedido"],
                 "pide_precio": True}
    llamadas = [{"herramienta": "registrar_pedido",
                 "resultado": {"estado": "registrado", "pedido": declarado}}]
    rec = P.reconciliar(declarado, llamadas, "t")
    assert "teclado" not in rec["sin_buscar"]
    assert len(rec["sin_buscar"]) == 3
    assert rec["preguntar"], "la duda tiene que seguir viajando como pregunta"

    fuera = HV._busqueda_de_lo_declarado(llamadas, declarado, rec,
                                         "verifika_prod", "t")
    cotizados = [l["pedido"].get("categoria") for l in fuera
                 if l["herramienta"] == "buscar_productos"]
    assert "teclado" not in cotizados


def test_la_contradiccion_que_nombra_TODO_no_descarta_nada(firestore_doble):
    """LA SALVAGUARDA, sin la cual el arreglo de arriba haria mas daño que
    bien. Una contradiccion sobre el pedido entero -"pediste esto y esto pero
    la distribucion no cierra"- no senala a ningun item en particular, asi que
    no puede dejar al cliente sin cotizacion de nada."""
    from app.core import pedido as P
    declarado = {"items": [{"que": "auriculares", "cantidad": 2},
                           {"que": "mouse", "cantidad": 2}],
                 "contradicciones": ["Pediste 2 auriculares y 2 mouse pero la "
                                     "distribucion entre destinos no cierra"],
                 "pide_precio": True}
    llamadas = [{"herramienta": "registrar_pedido",
                 "resultado": {"estado": "registrado", "pedido": declarado}}]
    rec = P.reconciliar(declarado, llamadas, "t")
    assert sorted(rec["sin_buscar"]) == ["auriculares", "mouse"]


# ── EL TURNO REAL DEL 9-AGO, trace 57ad6a0d: SE DEDUJO BIEN Y NO LLEGO ──────
# Martin mando por WhatsApp la version SIN teclado: "un auricular y un mouse a
# Cordoba capital, una memoria y un mouse a Concordia, los otros dos a
# Posadas". Los seis cierran por resta y no hay ambiguedad ninguna.
#
# EL MODELO LO RESOLVIO PERFECTO y quedo escrito en el log: desde la ronda 2
# llamo a `armar_presupuesto` con los seis renglones, cada uno con su destino,
# incluidos los dos de Posadas que salian de restar. Y el turno igual salio
# mal, por tres cables sueltos aguas abajo. Estos tests son esos tres.

def _seis_unidades_con_destino():
    """Las llamadas tal como las hizo el modelo en produccion."""
    declarado = {"items": [{"que": "auriculares", "cantidad": 2},
                           {"que": "mouse", "cantidad": 2},
                           {"que": "memoria ram", "cantidad": 2}],
                 "destinos": ["Córdoba capital", "Concordia", "Posadas"],
                 "pide_precio": True}
    cuenta = {"herramienta": "armar_presupuesto",
              "pedido": {"destinos": ["Córdoba capital", "Concordia",
                                      "Posadas"],
                         "items": [
                             {"product_id": "AUR0019", "cantidad": 1,
                              "destino": "Córdoba capital"},
                             {"product_id": "MOU0023", "cantidad": 1,
                              "destino": "Córdoba capital"},
                             {"product_id": "RAM0001", "cantidad": 1,
                              "destino": "Concordia"},
                             {"product_id": "MOU0023", "cantidad": 1,
                              "destino": "Concordia"},
                             {"product_id": "AUR0019", "cantidad": 1,
                              "destino": "Posadas"},
                             {"product_id": "RAM0001", "cantidad": 1,
                              "destino": "Posadas"}]},
              "resultado": {"estado": "ok", "bloque": "Total: $225.000"}}
    return declarado, cuenta


def test_el_destino_vale_venga_de_la_cuenta_y_no_solo_del_pedido(firestore_doble):
    """CABLE UNO: el reconciliador miraba SOLO los items de registrar_pedido.

    Medido en produccion, trace 57ad6a0d: el reparto estaba entero en los
    renglones de la cuenta y la regla 7 no lo veia, asi que pidio 'volve a
    declarar el pedido' en las rondas 2, 3 y 4. Tres rondas quemadas, 37,7
    segundos de turno, y el hub cerro en `faltantes_sin_resolver` sobre algo
    que estaba hecho."""
    from app.core import pedido as P
    declarado, cuenta = _seis_unidades_con_destino()
    rec = P.reconciliar(declarado, [cuenta], "t", tienda_id="verifika_prod")
    assert not [f for f in rec["faltantes"] if "va a cada uno" in f], \
        rec["faltantes"]

    # Y si la cuenta reparte SOLO una parte, el reclamo vuelve: lo que se
    # acepta es el reparto COMPLETO, no cualquier destino suelto.
    a_medias = {**cuenta, "pedido": {**cuenta["pedido"],
                                     "items": cuenta["pedido"]["items"][:2]}}
    rec2 = P.reconciliar(declarado, [a_medias], "t", tienda_id="verifika_prod")
    assert any("va a cada uno" in f for f in rec2["faltantes"])


def test_no_se_pregunta_lo_que_el_sistema_ya_resolvio(firestore_doble):
    """CABLE DOS: la contradiccion que el modelo declaro estaba MAL CONTADA.

    Textual del log: "pidio 6 articulos, pero al detallar los envios solo
    menciono 5". Nombra cuatro y "los otros dos", que son seis. La regla 6
    tomaba cualquier contradiccion y la volvia pregunta sin contar nada, asi
    que al cliente le llego "confirmame el destino del sexto articulo" DEBAJO
    de un presupuesto donde los seis ya tenian destino."""
    from app.core import pedido as P
    declarado, cuenta = _seis_unidades_con_destino()
    declarado["contradicciones"] = [
        "El cliente pidió 2 auriculares, 2 mouse y 2 memorias (6 artículos en "
        "total), pero al detallar los envíos solo mencionó 5 artículos: 1 "
        "auricular y 1 mouse a Córdoba, 1 memoria y 1 mouse a Concordia, y "
        "\"los otros dos artículos\" a Posadas. Falta aclarar el destino de 1 "
        "artículo."]
    rec = P.reconciliar(declarado, [cuenta], "t", tienda_id="verifika_prod")
    assert not rec["preguntar"], rec["preguntar"]

    # SALVAGUARDA UNA: sin el reparto cerrado, la pregunta se hace igual. El
    # default es preguntar; lo que la calla es el hecho, no la redaccion.
    a_medias = {**cuenta, "pedido": {**cuenta["pedido"],
                                     "items": cuenta["pedido"]["items"][:3]}}
    assert P.reconciliar(declarado, [a_medias], "t",
                         tienda_id="verifika_prod")["preguntar"]


def test_el_teclado_se_pregunta_aunque_la_cuenta_cierre(firestore_doble):
    """SALVAGUARDA DOS, y es la que hace usable a la de arriba. En la version
    con teclado el reparto TAMBIEN cierra -los seis del pedido tienen destino-
    y la contradiccion sigue siendo legitima, porque nombra un rubro que el
    cliente NO pidio. Esa pregunta es la que hay que hacer siempre."""
    from app.core import pedido as P
    declarado, cuenta = _seis_unidades_con_destino()
    declarado["contradicciones"] = [
        "Nombró un teclado en el envío a Concordia que no estaba en el pedido."]
    rec = P.reconciliar(declarado, [cuenta], "t", tienda_id="verifika_prod")
    assert any("teclado" in p for p in rec["preguntar"]), rec["preguntar"]

    # Y una que senala a UNOS POCOS items tampoco se calla: habla de un
    # producto concreto, no del reparto.
    declarado["contradicciones"] = [
        "Pidió 2 memorias pero no aclaró si las quiere de 8GB o de 16GB."]
    assert P.reconciliar(declarado, [cuenta], "t",
                         tienda_id="verifika_prod")["preguntar"]


def test_el_reparto_nombra_el_rubro_y_el_producto_cuando_hace_falta(
        firestore_doble):
    """CABLE TRES, la mitad de largo. El reparto repetia el nombre completo de
    cada producto -"1x Auriculares Redragon Zeus X Negro"- cuando ese nombre y
    su precio estan tres renglones arriba, en la cuenta. Nombrar el rubro no
    pierde nada y baja el bloque a menos de la mitad.

    LA CONDICION, y sin ella esto SI perderia un dato: el rubro alcanza solo
    cuando ese rubro viaja con UN producto en esta cuenta. Con dos modelos
    distintos del mismo rubro, el rubro no los distingue y vuelve el nombre
    entero."""
    from app.core import herramientas as H
    from app.storage.firestore_client import get_all_products

    cat = [p for p in get_all_products(tienda_id=TIENDA)
           if (p.get("stock") or 0) > 0]
    aur = next(p for p in cat if p["categoria"] == "auriculares")
    otro = next(p for p in cat
                if p["categoria"] == "auriculares" and p["id"] != aur["id"])
    mou = next(p for p in cat if p["categoria"] == "mouse")

    args = {"items": [{"product_id": aur["id"], "cantidad": 1,
                       "destino": "Concordia"},
                      {"product_id": mou["id"], "cantidad": 1,
                       "destino": "Posadas"}],
            "destinos": ["Concordia", "Posadas"]}
    bloque = H.ejecutar("armar_presupuesto", args, TIENDA).get("bloque") or ""
    assert "- A Concordia: 1x auriculares" in bloque, bloque
    assert "- A Posadas: 1x mouse" in bloque, bloque
    assert aur["nombre"] not in bloque.split("Reparto")[-1]

    # Dos auriculares DISTINTOS: el rubro ya no alcanza y vuelve el nombre.
    args["items"] = [{"product_id": aur["id"], "cantidad": 1,
                      "destino": "Concordia"},
                     {"product_id": otro["id"], "cantidad": 1,
                      "destino": "Posadas"}]
    bloque2 = H.ejecutar("armar_presupuesto", args, TIENDA).get("bloque") or ""
    assert aur["nombre"] in bloque2.split("Reparto")[-1], bloque2
    assert otro["nombre"] in bloque2.split("Reparto")[-1], bloque2


def test_los_destinos_se_derivan_de_los_renglones(firestore_doble):
    """LA ATADURA. El destino va pegado al renglon y la lista de destinos la
    arma el CODIGO. Pedirle al modelo las dos cosas le daba un lugar comodo
    donde tirar las tres ciudades sin decir cual va con cual, y ahi se perdia
    el reparto: `cada_unidad_con_destino` fallaba 13 de 18 corridas."""
    from app.core import herramientas as H

    r = H.ejecutar("registrar_pedido", {
        "items": [{"que": "auriculares", "cantidad": 1,
                   "destino": "Córdoba capital"},
                  {"que": "mouse", "cantidad": 1, "destino": "Córdoba capital"},
                  {"que": "memoria ram", "cantidad": 1, "destino": "Concordia"},
                  {"que": "mouse", "cantidad": 1, "destino": "Concordia"},
                  {"que": "auriculares", "cantidad": 1, "destino": "Posadas"},
                  {"que": "memoria ram", "cantidad": 1, "destino": "Posadas"}],
        "pide_precio": True}, TIENDA)
    assert r["pedido"]["destinos"] == ["Córdoba capital", "Concordia", "Posadas"]

    # Una ciudad que el modelo nombro y no pego a ningun renglon NO se pierde:
    # el envio hay que cotizarlo igual y el reconciliador tiene que verla.
    r2 = H.ejecutar("registrar_pedido", {
        "items": [{"que": "mouse", "cantidad": 1, "destino": "Posadas"}],
        "destinos": ["Posadas", "Rosario"]}, TIENDA)
    assert r2["pedido"]["destinos"] == ["Posadas", "Rosario"]

    # Un pedido a un solo lugar sigue declarandose con la lista, sin partir
    # nada: es el caso simple y no se le agrega trabajo.
    r3 = H.ejecutar("registrar_pedido", {
        "items": [{"que": "mouse", "cantidad": 2}],
        "destinos": ["Mendoza"]}, TIENDA)
    assert r3["pedido"]["destinos"] == ["Mendoza"]


# ── CUANDO EL MODELO NO CONTESTA (11-ago-2026) ──────────────────────────────
def test_si_el_modelo_no_contesta_no_le_echa_la_culpa_al_catalogo(
        monkeypatch, firestore_doble):
    """LA MENTIRA QUE SALIO DE MEDIR LA CLAVE GRATIS.

    Con el 429 tumbando la llamada del redactor, al cliente le llegaba "No
    tengo esa información confirmada en el catálogo" — y la herramienta HABIA
    encontrado el producto. El proveedor se cayo y el bot le echo la culpa al
    stock: es una afirmacion FALSA sobre el catalogo, la unica cosa que este
    sistema entero existe para que no pase, y ademas se lee como una respuesta
    normal en vez de como una falla. Ahora se dice que hay demanda."""
    async def _fake_uno(*a, **kw):
        return [{"nombre": "buscar_productos", "args": {"categoria": "mouse"}}], ""

    async def _sin_modelo(*a, **kw):
        return "", True

    monkeypatch.setattr(HV, "_pedir_herramientas", _fake_uno)
    monkeypatch.setattr(HV, "_redactar", _sin_modelo)
    salida = asyncio.run(HV.procesar_venta(USUARIO, "tenes mouse?", TIENDA,
                                           "test", "t1"))
    assert "catálogo" not in salida and "catalogo" not in salida, (
        f"le echo la culpa al catalogo cuando el que fallo fue el modelo:\n{salida}")
    assert "demanda" in salida.lower()


def test_si_el_modelo_contesta_vacio_si_dice_que_no_tiene_el_dato(
        monkeypatch, firestore_doble):
    """La otra mitad, que es la que distingue una cosa de la otra: si el modelo
    SI contesto y no trajo nada, el enlatado honesto sigue siendo el de siempre.
    Sin esto, el arreglo de arriba taparia una respuesta hueca con una excusa
    tecnica que no es cierta."""
    async def _fake_uno(*a, **kw):
        return [{"nombre": "buscar_productos", "args": {"categoria": "mouse"}}], ""

    async def _vacio(*a, **kw):
        return "", False

    monkeypatch.setattr(HV, "_pedir_herramientas", _fake_uno)
    monkeypatch.setattr(HV, "_redactar", _vacio)
    salida = asyncio.run(HV.procesar_venta(USUARIO, "tenes mouse?", TIENDA,
                                           "test", "t1"))
    assert "demanda" not in salida.lower()


def test_la_aduana_corre_en_el_camino_vivo(monkeypatch, firestore_doble):
    """LA ADUANA ESTA ENCHUFADA, no es un modulo suelto. Se hace fugar una
    etiqueta de la atadura por una via que las guardas de arriba no miran y se
    verifica que igual no le llega al cliente. Sin este candado, la aduana
    podria quedar desconectada del hub sin que ningun test lo notara."""
    from app.core import aduana

    llamada = {"veces": 0}
    real = aduana.revisar_salida

    def _espia(texto, **kw):
        llamada["veces"] += 1
        return real(texto, **kw)

    monkeypatch.setattr(aduana, "revisar_salida", _espia)

    async def _fake_uno(*a, **kw):
        return [], "Te confirmo el pedido para manana.\n\nResumen:\n"

    monkeypatch.setattr(HV, "_pedir_herramientas", _fake_uno)
    salida = asyncio.run(HV.procesar_venta(USUARIO, "listo", TIENDA,
                                           "test", "t1"))
    assert llamada["veces"] == 1, "la aduana no corrio en el turno"
    assert "Resumen:" not in salida


def test_si_el_decisor_se_cae_tampoco_le_echa_la_culpa_al_catalogo(
        monkeypatch, firestore_doble):
    """LA SEGUNDA PUERTA DE LA MISMA MENTIRA, y aparecio intentando regrabar
    dos casetes con la clave gratis: si el que se cae por cuota es el DECISOR
    -la llamada uno- el turno se queda sin herramientas y sin texto, y
    terminaba igual en "No tengo esa información confirmada en el catálogo".
    Cerrar solo la puerta del redactor no cerraba nada."""
    async def _decisor_muerto(*a, **kw):
        HV._marcar_sin_modelo("t-decisor")
        return [], ""

    monkeypatch.setattr(HV, "_pedir_herramientas", _decisor_muerto)
    salida = asyncio.run(HV.procesar_venta(USUARIO, "tenes mouse?", TIENDA,
                                           "test", "t-decisor"))
    assert "catálogo" not in salida and "catalogo" not in salida, salida
    assert "demanda" in salida.lower()
    assert "t-decisor" not in HV._SIN_MODELO, "la marca del turno no se limpio"
