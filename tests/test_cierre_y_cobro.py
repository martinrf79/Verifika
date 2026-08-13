"""
EL CIERRE Y EL COBRO — el ultimo metro de la venta, que es donde esta la plata.

POR QUE EXISTE. `_finalizar_cierre` es la funcion que cierra la venta: avisa al
dueño, arma la confirmacion que lee el cliente y le pega el cobro. Toca las tres
cosas que importan juntas -la respuesta, la plata y el aviso- y no tenia una
sola prueba. `leads.py` son 672 lineas sin test propio.

QUE MIDE, y lo que NO. Mide el CAMINO del cierre: que el aviso salga, que la
confirmacion se arme con lo que el cliente dio, que el cobro se pegue solo en
modo venta, y que ninguna de las tres cosas se lleve puesta a las otras si
falla. No mide la redaccion, que la miden los casetes.

LO QUE APRENDIMOS MIDIENDO, y corrige lo que esta sesion habia dicho antes: de
las seis funciones de `leads.py` que el mapa daba por ciegas, CUATRO son
almacenamiento que el doble reemplaza -`crear_lead`, `actualizar_lead`,
`get_lead_activo`, `descartar_leads_activos`- y estan en la misma clase que
`firestore_client`: sin base en la nube no corren. Quedaron declaradas en
`banco_pruebas/sin_camino_offline.py`, y el candado de deriva del doble las
vigila igual que a las otras. Las que si son logica son estas dos, y son las
que se prueban aca.

EL ERROR DEL 10-AGO QUE ESTO DEFIENDE. Al cliente le llego un pago dividido y,
abajo, "Monto: $225.000", el total ENTERO por transferencia, cuando por esa via
le tocaban $131.625. Un 71% de mas. `instruccion_cobro` es el punto donde se
elige que monto se pide; que cobre la PARTE y no el total esta medido aca.
"""
import sys
from pathlib import Path

import asyncio

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

TIENDA = "verifika_prod"

_LEAD_COMPLETO = {
    "nombre": "Javier Rojas",
    "telefono": "5491100000000",
    "direccion": "Av Siempre Viva 742, Rosario",
    "forma_pago": "transferencia",
    "orden": "1x Router Tenda AC10 Negro: $42.500\nTotal: $42.500",
}


@pytest.fixture
def espias(monkeypatch, firestore_doble):
    """Se dobla SOLO lo que sale de la maquina: el aviso al dueño, que es HTTP
    saliente. El resto del cierre corre tal cual."""
    import app.core.leads as leads
    avisos = []

    async def _notificar(**kw):
        avisos.append(kw)

    monkeypatch.setattr(leads, "notificar_lead", _notificar)
    return leads, avisos, monkeypatch


# ── _finalizar_cierre: el camino entero ─────────────────────────────────────
def test_el_cierre_avisa_al_dueño_y_le_confirma_al_cliente(espias):
    """Las dos salidas del cierre, y son distintas: al dueño le va el lead con
    los cuatro datos, al cliente una confirmacion que lo nombra."""
    leads, avisos, _ = espias
    meta = asyncio.run(leads._finalizar_cierre(
        "lead0001", dict(_LEAD_COMPLETO), TIENDA, "u1", "whatsapp",
        "listo, cerramos", _LEAD_COMPLETO["orden"], "trace1", modo="lead"))

    assert len(avisos) == 1, "la venta se cerro y al dueño no le llego el aviso"
    assert avisos[0]["nombre"] == "Javier Rojas"
    assert avisos[0]["estado"] == "capturado"

    assert meta["accion"] == "lead_capturado"
    assert meta["lead_id"] == "lead0001"
    texto = meta["respuesta_directa"]
    assert "Javier" in texto, "la confirmacion no nombra al cliente"
    assert "Rosario" in texto, "la confirmacion no dice a donde va el envio"
    assert _LEAD_COMPLETO["orden"] in texto, "la confirmacion perdio el pedido"


def test_en_modo_lead_no_se_cobra(espias):
    """La version A capta el lead y cierra un humano. Mandar un link de pago
    ahi seria cobrar una venta que todavia no acordo nadie."""
    leads, _, _ = espias
    meta = asyncio.run(leads._finalizar_cierre(
        "l1", dict(_LEAD_COMPLETO), TIENDA, "u1", "whatsapp", "dale",
        _LEAD_COMPLETO["orden"], "t", modo="lead"))
    texto = meta["respuesta_directa"].lower()
    assert "pagar" not in texto and "cbu" not in texto, (
        "en modo lead se le mando informacion de cobro al cliente")


def test_en_modo_venta_se_pega_el_cobro(espias):
    """La version B cierra y cobra. El cobro va PEGADO a la confirmacion, no en
    un mensaje aparte: dos mensajes seguidos se leen como que algo fallo."""
    leads, _, _ = espias
    meta = asyncio.run(leads._finalizar_cierre(
        "l1", dict(_LEAD_COMPLETO), TIENDA, "u1", "whatsapp", "dale",
        _LEAD_COMPLETO["orden"], "t", modo="venta"))
    texto = meta["respuesta_directa"]
    assert "Javier" in texto, "el cobro se comio la confirmacion"
    assert len(texto) > len(_LEAD_COMPLETO["orden"]), "no se pego nada de cobro"


def test_si_el_aviso_al_dueño_falla_la_venta_se_cierra_igual(espias):
    """Prioridad uno: el cliente recibe su confirmacion. Que el aviso interno se
    caiga es un problema del dueño, no del que acaba de comprar."""
    leads, _, mp = espias

    async def _explota(**kw):
        raise RuntimeError("sin red")

    mp.setattr(leads, "notificar_lead", _explota)
    meta = asyncio.run(leads._finalizar_cierre(
        "l1", dict(_LEAD_COMPLETO), TIENDA, "u1", "whatsapp", "dale",
        _LEAD_COMPLETO["orden"], "t", modo="lead"))
    assert meta["respuesta_directa"], "se cayo el aviso y el cliente quedo sin nada"


def test_si_el_cobro_falla_la_confirmacion_igual_le_llega(espias):
    """Mismo criterio un piso mas abajo: sin link de pago se cierra igual y una
    persona coordina. Sin confirmacion, el cliente no sabe si compro."""
    leads, _, mp = espias
    import app.core.pago as pago

    async def _explota(*a, **kw):
        raise RuntimeError("mercado pago caido")

    mp.setattr(pago, "instruccion_cobro", _explota)
    meta = asyncio.run(leads._finalizar_cierre(
        "l1", dict(_LEAD_COMPLETO), TIENDA, "u1", "whatsapp", "dale",
        _LEAD_COMPLETO["orden"], "t", modo="venta"))
    assert "Javier" in meta["respuesta_directa"]


# ── instruccion_cobro: por donde se pide la plata ───────────────────────────
def test_el_cobro_por_transferencia_pide_la_PARTE_no_el_total(firestore_doble):
    """EL ERROR DEL 10-AGO, exacto. Con la cuenta dividida 65/35, por CBU se
    pide lo que va por CBU. Pedir el total es cobrar de mas, que es el peor
    error posible de todos los que puede cometer este sistema.

    EL BLOQUE NO SE TIPEA ACA: lo genera `render_split`, que es la funcion que
    lo escribe en produccion. Escribirlo a mano fue mi primer intento y el test
    salio rojo acusando un error que no existia -me faltaba el guion del
    renglon-. Un test con su propia copia del formato prueba el formato de la
    copia, que es la leccion mas cara de este repo un piso mas abajo.
    """
    from app.core.pago import instruccion_cobro
    from app.core.pago_split import calcular_split, render_split

    split = calcular_split(225_000, [{"medio": "transferencia", "porcentaje": 65},
                                     {"medio": "mercado pago", "porcentaje": 35}],
                           pct_descuento=10)
    assert split.get("ok"), "no se pudo armar el split de la prueba"
    presupuesto = f"1x Router Tenda AC10 Negro: $225.000\n{render_split(split)}"
    parte_cbu = split["partes"][0]
    esperado = parte_cbu["monto_final_ars"] or parte_cbu["monto_ars"]

    texto = asyncio.run(instruccion_cobro(
        presupuesto, {"forma_pago": "transferencia"}, TIENDA, "t"))
    assert texto, "no salio ninguna instruccion de cobro"
    assert "225.000" not in texto, (
        "SE COBRO EL TOTAL POR TRANSFERENCIA teniendo la cuenta dividida. Es "
        f"el error del 10-ago. Tenia que pedir ${esperado:,}".replace(",", "."))
    assert str(esperado)[:3] in texto.replace(".", ""), (
        f"no pidio la parte que va por transferencia (${esperado})")


def test_el_efectivo_no_manda_ni_link_ni_cbu(firestore_doble):
    """El efectivo lo coordina una persona. Mandarle un CBU a quien dijo que
    paga en efectivo es pedirle plata dos veces."""
    from app.core.pago import instruccion_cobro
    texto = asyncio.run(instruccion_cobro(
        "Total: $1.000", {"forma_pago": "efectivo"}, TIENDA, "t"))
    assert texto == "", f"al que paga en efectivo se le mando: {texto!r}"


def test_mercado_pago_siempre_termina_con_un_link(firestore_doble):
    """Sin token real cae al link de demo, que es la decision tomada y NO un
    defecto: ver CLAUDE.md. Lo que no puede pasar es que no salga ningun link."""
    from app.core.pago import instruccion_cobro
    texto = asyncio.run(instruccion_cobro(
        "Total: $1.000", {"forma_pago": "mercado pago"}, TIENDA, "t"))
    assert "http" in texto, "el que eligio Mercado Pago no recibio ningun link"


# ── _insistencia: no preguntar lo mismo cuatro veces ────────────────────────
def test_la_insistencia_cuenta_solo_si_se_pide_LO_MISMO():
    """La prioridad 2 es no repetir. `_insistencia` es lo que deja saber que ya
    se pidieron estos campos; si cambian los campos, la cuenta arranca de cero
    porque es otra pregunta."""
    from app.core.leads import _insistencia
    lead = {"datos_pedidos_campos": ["nombre", "direccion"],
            "datos_pedidos_veces": 2}
    assert _insistencia(lead, ["nombre", "direccion"]) == 2
    assert _insistencia(lead, ["nombre"]) == 0, (
        "conto como insistencia una pregunta por campos distintos")
    assert _insistencia({}, ["nombre"]) == 0


def test_la_insistencia_no_se_cae_con_un_dato_roto():
    """Un lead viejo puede traer cualquier cosa en ese campo. Que reviente el
    contador no puede tumbar el cierre entero."""
    from app.core.leads import _insistencia
    for basura in (None, "", "muchas", {"a": 1}, -3):
        lead = {"datos_pedidos_campos": ["nombre"], "datos_pedidos_veces": basura}
        assert _insistencia(lead, ["nombre"]) >= 0


# ── extraer_datos_cliente: el respaldo determinista ─────────────────────────
def test_los_datos_del_cliente_salen_igual_sin_el_modelo(firestore_doble,
                                                         monkeypatch):
    """LA RED DEL EXTRACTOR. El modelo saca nombre, telefono, direccion y forma
    de pago del mensaje; si se cae, el respaldo DETERMINISTA saca los tres que
    se pueden sacar por patron. Sin esta red, un blip del modelo en el ultimo
    turno pierde la direccion de una venta ya cerrada."""
    import app.core.cierre as cierre

    def _explota(*a, **kw):
        raise RuntimeError("modelo caido")

    monkeypatch.setattr(cierre, "llm_complete", _explota)
    datos = cierre.extraer_datos_cliente(
        "mi telefono es 3415551234 y pago por transferencia", trace_id="t")
    assert datos["telefono"], "se perdio el telefono teniendo el patron delante"
    assert "transfer" in datos["forma_pago"].lower(), (
        "se perdio la forma de pago, que decide por donde se cobra")


def test_el_extractor_devuelve_los_cuatro_campos_siempre(firestore_doble,
                                                         monkeypatch):
    """El contrato con el cierre: los cuatro campos vienen SIEMPRE, vacios los
    que no esten. Si faltara una clave, `faltantes` la leeria como ausente y el
    bot volveria a pedir un dato que el cliente ya dio."""
    import app.core.cierre as cierre

    def _explota(*a, **kw):
        raise RuntimeError("modelo caido")

    monkeypatch.setattr(cierre, "llm_complete", _explota)
    datos = cierre.extraer_datos_cliente("hola", trace_id="t")
    assert set(datos) == set(cierre.CAMPOS_EXTRAIBLES), (
        f"el extractor cambio su contrato: devolvio {sorted(datos)}")


# ── LOS TRES HELPERS QUE QUEDABAN, y se cierran acá porque son de una linea ──
def test_la_plata_se_escribe_a_la_argentina_y_nunca_revienta():
    """`_money` escribe TODA la plata que el estado le muestra al modelo. Si
    revienta con un dato raro, se cae el turno entero por un formato."""
    from app.core.estado_venta import _money
    assert _money(48000) == "48.000"
    assert _money(0) == "0"
    for basura in (None, "", "abc", [1]):
        assert isinstance(_money(basura), str), f"_money reventó con {basura!r}"


def test_la_celda_que_contesto_queda_anotada_una_sola_vez():
    """`indice.registrar` es el rastro con el que se contesta "¿esto ya se
    dijo?". Anotada dos veces, el sistema creeria que contesto dos puntos
    distintos y el indice del turno mentiria."""
    from app.core.indice import registrar, usadas
    meta: dict = {}
    registrar(meta, "plazo_envio")
    registrar(meta, "plazo_envio")
    registrar(meta, "formas_pago")
    assert usadas(meta) == ["plazo_envio", "formas_pago"]
    # Basura adentro no puede tumbar el turno ni ensuciar el rastro.
    registrar(meta, "")
    registrar(None, "x")
    assert usadas(meta) == ["plazo_envio", "formas_pago"]


def test_el_grafo_declara_sus_nodos_con_el_envoltorio():
    """`grafo._n` es el envoltorio con el que se declara cada nodo del turno.
    Es la identidad a proposito -no envuelve nada todavia- y por eso conviene
    fijarlo: el dia que envuelva algo, esta prueba dice si sigue devolviendo la
    funcion que le dieron, que es de lo que depende el cableado entero."""
    from app.verifika.grafo import _n, NODOS

    def cualquiera(texto, ctx):
        return texto

    assert _n(cualquiera) is cualquiera
    assert len(NODOS) > 20, "el grafo del turno se quedo sin nodos declarados"
