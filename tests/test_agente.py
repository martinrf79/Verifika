"""EL AGENTE Y EL TURNO NUEVO — `app/core/agente.py` y `respuesta.procesar_turno`.

La vara del camino que reemplazo al interprete el 26-sep-2026. Sin modelo de
verdad: un modelo de mentira devuelve llamadas y textos fijos, y lo que se mide
es lo que hace el codigo con eso. El modelo real se mide en el banco con
`sonda_charlas.py --vara 58 --camino agente`.
"""
import asyncio
import json
from types import SimpleNamespace as NS

import pytest

from app.core import agente as A
from app.core import respuesta as R

TIENDA = "verifika_prod"


@pytest.fixture(autouse=True)
def _doble(firestore_doble):
    from app.core.contexto_turno import set_current_tienda
    from app.core.filtros_catalogo import limpiar_cache
    set_current_tienda(TIENDA)
    limpiar_cache()
    A.CLIENTE_DIJO.set("")
    return firestore_doble


# ── EL MODELO DE MENTIRA ─────────────────────────────────────────────────────

def _llamada(herr, **args):
    return NS(id=f"c_{herr}", function=NS(name=herr, arguments=json.dumps(args)),
              model_dump=lambda n=herr, a=args: {"id": f"c_{n}", "type": "function",
                                                   "function": {"name": n, "arguments": json.dumps(a)}})


def _resp(texto="", llamadas=None):
    return NS(choices=[NS(message=NS(content=texto, tool_calls=llamadas or None))],
              usage=NS(prompt_tokens=100, prompt_tokens_details=None))


class Modelo:
    """Devuelve en orden las respuestas del guion y anota lo que recibio."""

    def __init__(self, guion):
        self.guion, self.pedidos = list(guion), []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kw):
        self.pedidos.append(kw)
        return self.guion.pop(0) if self.guion else _resp("listo")


@pytest.fixture
def modelo(monkeypatch):
    def poner(guion):
        m = Modelo(guion)
        monkeypatch.setattr("app.core.llm_reintento._cliente", lambda: m)
        return m
    return poner


def _turno(historial, mensaje, memoria=""):
    return asyncio.run(A.turno(historial, mensaje, TIENDA, "t", memoria=memoria))


# ── EL INDICE Y LAS HERRAMIENTAS ─────────────────────────────────────────────

def test_el_indice_ubica_la_jerga_por_los_alias():
    assert A.ubicar("el coso de internet", "rubros", TIENDA)[0] == "router"
    assert A.ubicar("disco externo", "rubros", TIENDA)[0] == "almacenamiento externo"
    assert A.ubicar("me vino roto", "temas", TIENDA)[0] == "defectuoso"


def test_un_filtro_con_el_dato_en_otro_campo_se_repite_donde_vive():
    """DDR5 no esta en `ram` sino en el nombre. Un vacio el modelo lo lee como
    'no tenemos', y habia nueve."""
    r = A.h_buscar(TIENDA, rubro="memoria ram",
                   condiciones=[{"campo": "ram", "operador": "contiene", "valor": "DDR5"}])
    assert r["veredicto"] != "no_existe"
    assert all("DDR5" in f["nombre"] for f in r["filas"])
    assert "nota" in r


def test_varias_condiciones_que_juntas_dan_cero_se_buscan_por_separado():
    """'G305' y 'G203' en el nombre a la vez no lo cumple nadie: el modelo dijo
    que no tenia ninguno de los dos."""
    r = A.h_buscar(TIENDA, rubro="mouse", condiciones=[
        {"campo": "nombre", "operador": "contiene", "valor": "G305"},
        {"campo": "nombre", "operador": "contiene", "valor": "G203"}])
    assert "aviso" in r and len(r["por_condicion"]) == 2


def test_la_cuenta_suma_el_envio_y_la_hace_la_calculadora():
    r = A.h_cuenta(TIENDA, items=[{"producto": "G305 negro", "cantidad": 1}], destino="Rosario")
    assert r["cuenta"]["total_ars"] == 87500
    assert r["envio"]["filas"][0]["monto_ars"] == 7000


def test_reservar_certifica_el_producto_y_pide_el_nombre():
    # Desde el 27-sep el color lo tiene que haber dicho el cliente.
    A.CLIENTE_DIJO.set("me llevo el G203 negro")
    r = A.h_reservar(TIENDA, producto="G203 negro", cantidad=1)
    assert r["veredicto"] == "listo_para_cerrar" and r["id"] == "MOU0001"
    assert "nombre" in r["falta"]


def test_el_prompt_no_crece_con_el_catalogo():
    """Lo que viaja fijo son las reglas, las herramientas y los rubros: ningun
    producto, ninguna marca, ningun precio."""
    s = A.sistema(TIENDA) + json.dumps(A.esquema(TIENDA))
    assert "G305" not in s and "$" not in s
    assert len(s) < 9000


# ── LA BOCA INVARIANTE: el mismo pedido dicho de otra forma, los mismos hechos ──
#
# 26-sep, 23:59, WhatsApp, la pregunta compleja de siempre. En produccion el
# modelo pidio el rubro como condicion `categoria` y el motor la ignoro: las
# tres busquedas volvieron con los mismos dos procesadores y el cliente leyo
# "el sistema no reconoce auriculares, mouse o memoria ram". Por el clon, la
# misma pregunta pidio "sin China" como exclusion dura: cero, y el bot dijo que
# todo era chino, cuando las memorias son "taiwan o china segun linea". Las dos
# veces el catalogo tenia el pais de fabricacion y la fila que volvia no lo
# traia. Lo que no puede pasar es que la respuesta dependa de COMO lo pidio.

def test_el_rubro_pedido_como_condicion_categoria_se_busca_en_el_rubro():
    for rubro, prefijo in (("auriculares", "AUR"), ("mouse", "MOU"), ("memoria ram", "RAM")):
        r = A.h_buscar(TIENDA, cuantos=2, condiciones=[
            {"campo": "categoria", "operador": "igual", "valor": rubro}])
        assert r["filas"] and all(f["id"].startswith(prefijo) for f in r["filas"]), rubro
        assert "no_aplicado" not in r


def test_la_fila_trae_el_valor_del_campo_que_se_pidio():
    r = A.h_buscar(TIENDA, rubro="auriculares", cuantos=2, condiciones=[
        {"campo": "pais_fabricacion", "operador": "evita", "valor": "China"}])
    assert all(f.get("pais_fabricacion") == "china" for f in r["filas"])


def test_exclusion_dura_o_blanda_devuelven_los_mismos_hechos_del_rubro():
    """"sin China" y "lo menos chino posible" tienen que dejarle al modelo el
    mismo hecho: que valores hay en el rubro y cuantos de cada uno."""
    for op in ("no_contiene", "evita", "igual"):
        a = A.h_buscar(TIENDA, rubro="auriculares", cuantos=2, condiciones=[
            {"campo": "pais_fabricacion", "operador": op, "valor": "China"}])
        m = A.h_buscar(TIENDA, rubro="memoria ram", cuantos=2, condiciones=[
            {"campo": "pais_fabricacion", "operador": op, "valor": "China"}])
        assert a["valores_en_el_rubro"]["pais_fabricacion"] == {"china": 46}, op
        assert m["valores_en_el_rubro"]["pais_fabricacion"] == {"taiwan o china segun linea": 96}, op
        assert a["filas"] and m["filas"], op


def test_las_fichas_del_turno_traen_el_precio_en_numero_para_la_suma_verificada():
    """"los dos $49.500" es una suma correcta de dos precios que volvieron. Sin
    `precio_ars` en las fichas la guarda no podia comprobarla y tiraba la
    respuesta entera."""
    fichas, _, _ = R._lo_que_volvio([{"herramienta": "buscar", "vuelve": {"filas": [
        {"id": "MOU0001", "nombre": "G203", "precio": "$37.500"},
        {"id": "MOU0009", "nombre": "M170", "precio": "$12.000"}]}}])
    assert [f["precio_ars"] for f in fichas] == [37500, 12000]
    from app.core import numeros as N
    _, inf = N.llenar("El G203 sale $37.500 y el M170 $12.000, los dos $49.500.", fichas)
    assert not inf["inventada"]


def test_un_modelo_en_dos_colores_es_un_renglon_y_lo_sin_stock_baja():
    """A "dos mouse" volvian el DX-110 negro y el blanco sin stock: el modelo
    armo la cuenta con el blanco y la cuenta no salio."""
    r = A.h_buscar(TIENDA, rubro="mouse", cuantos=2, condiciones=[
        {"campo": "pais_fabricacion", "operador": "no_contiene", "valor": "China"}])
    ids = [f["id"] for f in r["filas"]]
    assert len(r["filas"]) == 2 and not {"MOU0023", "MOU0024"} <= set(ids)
    assert all(f["stock"] > 0 for f in r["filas"])
    dx = next(f for f in r["filas"] if f["id"] in ("MOU0023", "MOU0024"))
    assert {v["color"]: v["stock"] for v in dx["variantes"]} == {"Negro": 11, "Blanco": 0}


def test_la_ficha_de_un_modelo_en_dos_colores_es_un_renglon():
    """"tenes el G305?" volvia dos fichas enteras, negro y blanco, con los
    mismos datos, la misma garantia y la misma caja: medido el 28-sep sobre
    las tres tandas de base, `producto` era el 39% de todo lo que volvia. El
    color no se pierde: va en `variantes` y lo sigue eligiendo el cliente."""
    r = A.h_producto(TIENDA, "Logitech G305")
    assert len(r["filas"]) == 1
    assert {v["id"] for v in r["filas"][0]["variantes"]} == {"MOU0029", "MOU0030"}
    assert r["veredicto"] == "ambiguo" and "color" in r["motivo"]


def test_la_variante_no_repite_el_precio_del_renglon():
    r = A._juntar_colores({"filas": [{"id": "MOU0001", "precio": "$37.500", "stock": 5},
                                     {"id": "MOU0002", "precio": "$40.000", "stock": 2}]}, 5, TIENDA)
    v = {x["id"]: x for x in r["filas"][0]["variantes"]}
    assert "precio" not in v["MOU0001"] and v["MOU0002"]["precio"] == "$40.000"


def test_el_dato_que_ya_esta_en_la_fila_no_se_repite_en_datos():
    r = A.h_buscar(TIENDA, rubro="mouse", cuantos=2, condiciones=[
        {"campo": "conexion", "operador": "contiene", "valor": "inalambrico"}])
    assert all(f.get("conexion") and "conexion" not in (f.get("datos") or {}) for f in r["filas"])


def test_la_variante_sin_precio_toma_el_del_renglon_en_las_fichas_del_turno():
    fichas, _, _ = R._lo_que_volvio([{"herramienta": "producto", "vuelve": A.h_producto(TIENDA, "Logitech G305")}])
    assert {f["id"]: f["precio_ars"] for f in fichas} == {"MOU0029": 80500, "MOU0030": 80500}


def test_reservar_ve_el_stock_del_color_elegido():
    A.CLIENTE_DIJO.set("me llevo 20 G305 blancos")
    assert A.h_reservar(TIENDA, "MOU0030", 20)["veredicto"] == "listo_para_cerrar"
    A.CLIENTE_DIJO.set("me llevo 20 G305 negros")
    assert A.h_reservar(TIENDA, "MOU0029", 20)["veredicto"] != "listo_para_cerrar"


def test_el_color_que_no_se_mostro_primero_queda_en_la_memoria_del_turno():
    fichas, _, _ = R._lo_que_volvio([{"herramienta": "buscar", "vuelve": A.h_buscar(
        TIENDA, rubro="mouse", que="G203", cuantos=1)}])
    assert {"MOU0001", "MOU0002"} <= {f["id"] for f in fichas}
    assert next(f for f in fichas if f["id"] == "MOU0002")["nombre"].endswith("Blanco")


@pytest.mark.parametrize("pregunta", [
    "medios de pago y descuentos por cantidad",
    "que medios de pago reciben y si tienen descuentos por cantidad",
    "Dime qué medios de pago reciben Y si tienen descuentos por cantidad"])
def test_una_pregunta_de_la_casa_con_varios_temas_trae_todos(pregunta):
    """El bot dijo "no tenemos descuentos por cantidad": `mayoristas` quedo
    cuarto y el corte era tres."""
    temas = A.temas_de(pregunta, TIENDA)
    assert "mayoristas" in temas and "formas_pago" in temas
    r = A.h_politica(TIENDA, pregunta=pregunta)
    assert any("cantidad" in json.dumps(p, ensure_ascii=False).lower() for p in r["politicas"])


# ── LA COMPLETITUD, MECANICA ─────────────────────────────────────────────────
#
# Medido el 19-sep cuatro de cuatro y el 26-sep otra vez: el reparto de pago y
# los destinos se caen del turno. Cambiar el texto del prompt no lo arreglo
# nunca. El codigo lee el mensaje, ve que pidio y que no se consulto, y se lo
# marca al modelo UNA vez antes de que conteste.

COMPLEJA = ("Dame precio de dos auriculares, dos mouse y dos memorias. El precio no sería tan "
            "importante. Lo que sí que necesito que lleven las menos partes chinas posibles. Un "
            "auricular y un mouse será envío a Córdoba capital. Un teclado y un mouse será envío a "
            "Concordia. Los otros dos artículos serán con envío a posadas. Divide el presupuesto en "
            "setenta treinta, ya que veré en la fase siguiente cómo seguimos")


def test_la_completitud_ve_los_destinos_y_el_reparto_de_la_pregunta_compleja():
    f = A.faltantes(COMPLEJA, [])
    assert sorted(f["destinos"]) == ["Concordia", "Córdoba capital", "posadas"]
    assert f["reparto"]


def test_lo_consultado_no_falta():
    llamadas = [{"herramienta": "envio", "args": {"destinos": ["Cordoba", "Concordia, Entre Rios"]}},
                {"herramienta": "cuenta", "args": {"items": [], "destino": "Posadas",
                                                   "reparto_pago": [{"medio": "transferencia", "porcentaje": 70}]}}]
    assert A.faltantes(COMPLEJA, llamadas) == {}


@pytest.mark.parametrize("msg", [
    "que parlantes tenes?", "el G305 anda con mi Mac?", "una compu portatil para la facu",
    "hola, soy de Posadas, Misiones", "algo para escuchar musica sin cables en el colectivo",
    "quiero una notebook con 64 GB de RAM por menos de 200 mil", "tienen 50 por ciento off en todo, no?",
    "una silla para viciar horas", "me lo llevo a casa", "dame el precio del 12/09",
    "sumame dos K120 negros y un G203 negro", "cual es la capital de Francia?"])
def test_la_completitud_no_inventa_pedidos(msg):
    assert A.faltantes(msg, []) == {}


@pytest.mark.parametrize("msg,destinos,reparto", [
    ("cuanto sale el envio a Posadas?", ["Posadas"], False),
    ("mandame un G203 a Rosario y otro a Mendoza", ["Rosario", "Mendoza"], False),
    ("me equivoque, era para Cordoba, no Rosario", ["Cordoba"], False),
    ("me llevo el K120, pago 70 por ciento transferencia y 30 por ciento Mercado Pago", [], True),
    ("dividilo 60/40", [], True),
    ("mitad y mitad", [], True)])
def test_la_completitud_ve_lo_que_se_pidio(msg, destinos, reparto):
    f = A.faltantes(msg, [])
    assert f.get("destinos", []) == destinos and bool(f.get("reparto")) == reparto


# LA COMPRA QUE SE CAE (27-sep-2026). Medido en tres tandas de las 58 por el
# clon: "si anda con Mac me lo llevo" y "dame el que sea inalambrico" nunca
# llaman a reservar; "el primero" y "ese me lo llevo" una vez de cada tres.

def _ll(herr, **args):
    return {"herramienta": herr, "args": args}


@pytest.mark.parametrize("msg,llamadas,historial", [
    ("si el G305 anda con Mac, me lo llevo", [_ll("compatibilidad", producto="G305", con="Mac")], []),
    ("entre el G305 y el G203, dame el que sea inalambrico", [_ll("buscar", que="G305 G203")], []),
    ("ah no, el otro, y ese me lo llevo", [],
     [{"role": "user", "content": "me gusta el G305"},
      {"role": "assistant", "content": "el G305 negro es inalambrico y sale $80.500"}]),
    ("el primero", [],
     [{"role": "user", "content": "me llevo uno"},
      {"role": "assistant", "content": "cual de los dos, el G203 o el G305?"}]),
])
def test_la_completitud_ve_la_compra_sin_reservar(msg, llamadas, historial):
    assert A.faltantes(msg, llamadas, historial).get("compra")
    assert "reservar" in A._aviso({"compra": True})


@pytest.mark.parametrize("msg,llamadas,historial", [
    ("me lo llevo a casa", [], []),
    ("me llevo dos G305 negros", [_ll("reservar", producto="G305 negro", cantidad=2)], []),
    ("el G203 es inalambrico, no? lo quiero para viajar", [_ll("producto", nombre="G203")], []),
    ("que parlantes tenes?", [_ll("buscar", rubro="parlante")], []),
    ("Martin", [], [{"role": "user", "content": "me lo llevo"},
                    {"role": "assistant", "content": "Listo, reservado. ¿Me pasas tu nombre?"}]),
    ("y en blanco?", [_ll("buscar", que="blanco")],
     [{"role": "user", "content": "busco un mouse Logitech con cable"},
      {"role": "assistant", "content": "tengo el G203 y el G502 Hero, ¿cual te gusta?"}]),
])
def test_la_compra_no_se_inventa(msg, llamadas, historial):
    assert not A.faltantes(msg, llamadas, historial).get("compra")


# LA CONDICION DE ANTES QUE SE PIERDE (27-sep-2026). Medido en tres tandas de
# las 58 por el clon, tres de tres: "busco un teclado que no sea Redragon" y
# despues "y alguno mecanico?" busca mecanicos sin sacar Redragon.

_SIN_REDRAGON = [{"role": "user", "content": "busco un teclado que no sea Redragon"},
                 {"role": "assistant", "content": "tengo el K120 y el Keychron K2"}]


def test_la_completitud_ve_la_exclusion_de_antes_que_se_perdio():
    f = A.faltantes("y alguno mecanico?", [_ll("buscar", rubro="teclado", condiciones=[
        {"campo": "switch_teclado", "operador": "contiene", "valor": "mecanico"}])], _SIN_REDRAGON, TIENDA)
    assert f.get("excluidas") == ["Redragon"]
    assert "Redragon" in A._aviso(f)


@pytest.mark.parametrize("msg,llamadas", [
    ("y alguno mecanico?", [_ll("buscar", rubro="teclado", condiciones=[
        {"campo": "marca", "operador": "no_contiene", "valor": "Redragon"}])]),
    ("y alguno mecanico?", [_ll("buscar", rubro="teclado", condiciones=[
        {"campo": "marca", "operador": "evita", "valor": "redragon"}])]),
    ("bueno, mostrame los Redragon mecanicos", [_ll("buscar", rubro="teclado", que="redragon")]),
    ("ya no importa la marca, alguno mecanico?", [_ll("buscar", rubro="teclado")]),
    ("y mouse tenes?", [_ll("buscar", rubro="mouse")]),
    ("y alguno mecanico?", []),
])
def test_la_exclusion_de_antes_no_se_inventa(msg, llamadas):
    assert not A.faltantes(msg, llamadas, _SIN_REDRAGON, TIENDA).get("excluidas")


def test_una_exclusion_que_no_es_marca_no_se_arrastra():
    h = [{"role": "user", "content": "busco un teclado que no sea caro"},
         {"role": "assistant", "content": "tengo el K120"}]
    assert not A.faltantes("y alguno mecanico?", [_ll("buscar", rubro="teclado")], h, TIENDA).get("excluidas")


# EL COLOR LO ELIGE EL CLIENTE (27-sep-2026). Medido en WhatsApp: el bot
# pregunto "¿negro o blanco?", el cliente no contesto el color, y en el turno
# siguiente el modelo reservo el negro. La identidad no la infiere el modelo:
# reservar solo acepta una variante que el cliente nombro.

def test_reservar_no_acepta_un_color_que_el_cliente_no_dijo():
    A.CLIENTE_DIJO.set("entre el G305 y el G203, dame el que sea inalambrico\nsi el G305 anda con Mac, me lo llevo")
    r = A.h_reservar(TIENDA, "Mouse Logitech G305 Lightspeed Negro", 1)
    assert r["veredicto"] == "falta_elegir"
    assert {"Negro", "Blanco"} <= set(r["opciones"])


def test_reservar_acepta_el_color_que_el_cliente_dijo():
    A.CLIENTE_DIJO.set("el G305 en blanco, me lo llevo")
    assert A.h_reservar(TIENDA, "MOU0030", 1)["veredicto"] == "listo_para_cerrar"


def test_un_producto_de_un_solo_color_no_pregunta_el_color():
    A.CLIENTE_DIJO.set("me llevo el monitor LG 24MK430H")
    assert A.h_reservar(TIENDA, "MON0001", 1)["veredicto"] == "listo_para_cerrar"


def test_el_turno_le_dice_a_reservar_lo_que_dijo_el_cliente(modelo):
    m = modelo([_resp("", [_llamada("reservar", producto="MOU0029", cantidad=1)]),
                _resp("¿Negro o blanco?")])
    r = _turno([{"role": "user", "content": "entre el G305 y el G203, dame el que sea inalambrico"},
                {"role": "assistant", "content": "El G305. ¿Negro o blanco?"}],
               "si anda con Mac me lo llevo")
    assert r["llamadas"][0]["vuelve"]["veredicto"] == "falta_elegir"


def test_el_turno_le_pasa_la_charla_a_la_completitud(modelo):
    m = modelo([_resp("Es el G203, ¿en que color?"),
                _resp("", [_llamada("reservar", producto="G203 negro", cantidad=1)]),
                _resp("Listo, pasame tu nombre.")])
    r = _turno([{"role": "user", "content": "me llevo uno"},
                {"role": "assistant", "content": "cual de los dos, el G203 o el G305?"}], "el primero")
    assert "reservar" in m.pedidos[1]["messages"][-1]["content"]
    assert r["texto"] == "Listo, pasame tu nombre."


def test_si_falta_algo_el_modelo_tiene_una_vuelta_mas_con_el_aviso(modelo):
    m = modelo([_resp("Tengo auriculares HyperX."),
                _resp("", [_llamada("envio", destinos=["Posadas"])]),
                _resp("El envio a Posadas sale $10.000.")])
    r = _turno([], "tenes auriculares? y cuanto sale el envio a Posadas?")
    assert r["texto"] == "El envio a Posadas sale $10.000."
    aviso = m.pedidos[1]["messages"][-1]
    assert aviso["role"] == "user" and "Posadas" in aviso["content"]
    assert "Tengo auriculares HyperX." not in json.dumps(m.pedidos[1]["messages"], ensure_ascii=False)


def test_lo_que_el_codigo_lee_en_el_mensaje_va_en_la_primera_vuelta(modelo):
    """28-sep, producción: la pregunta compleja costaba 5 vueltas, 17.000
    tokens y 10 segundos, porque los destinos y el reparto se marcaban DESPUÉS
    de que el modelo contestaba. Lo mismo que lee la completitud va con el
    mensaje desde la primera vuelta."""
    m = modelo([_resp("dale")])
    _turno([], COMPLEJA)
    nota = m.pedidos[0]["messages"][-1]
    assert nota["role"] == "user" and nota["content"] != COMPLEJA
    assert all(d in nota["content"] for d in ("Córdoba capital", "Concordia", "posadas"))
    assert "reparto_pago" in nota["content"]
    assert m.pedidos[0]["messages"][-2] == {"role": "user", "content": COMPLEJA}


def test_la_compra_de_la_charla_va_en_la_primera_vuelta(modelo):
    m = modelo([_resp("dale")])
    _turno([{"role": "user", "content": "me llevo uno"},
            {"role": "assistant", "content": "cual de los dos, el G203 o el G305?"}], "el primero")
    assert "reservar" in m.pedidos[0]["messages"][-1]["content"]


def test_lo_anticipado_y_consultado_no_se_vuelve_a_avisar(modelo):
    m = modelo([_resp("", [_llamada("envio", destinos=["Posadas"])]),
                _resp("El envio a Posadas sale $10.000.")])
    r = _turno([], "cuanto sale el envio a Posadas?")
    assert r["texto"] == "El envio a Posadas sale $10.000." and len(m.pedidos) == 2


def test_el_aviso_de_completitud_se_da_una_sola_vez(modelo):
    m = modelo([_resp("No se."), _resp("Sigo sin saber.")])
    r = _turno([], "cuanto sale el envio a Posadas?")
    assert r["texto"] == "Sigo sin saber." and len(m.pedidos) == 2


def test_si_el_modelo_se_cae_despues_del_aviso_sale_el_borrador(modelo, monkeypatch):
    pedidos = []

    def _create(**kw):
        pedidos.append(kw)
        if len(pedidos) == 1:
            return _resp("El envio a Posadas no lo tengo.")
        raise ValueError("400 bad request")
    monkeypatch.setattr("app.core.llm_reintento._cliente",
                        lambda: NS(chat=NS(completions=NS(create=_create))))
    assert _turno([], "cuanto sale el envio a Posadas?")["texto"] == "El envio a Posadas no lo tengo."


def test_la_condicion_categoria_no_llega_al_motor_aunque_venga_el_rubro():
    r = A.h_buscar(TIENDA, rubro="mouse", condiciones=[{"campo": "categoria", "operador": "igual", "valor": "mouse"}])
    assert "no_aplicado" not in r and r["filas"][0]["id"].startswith("MOU")


def test_si_el_modelo_se_cae_a_mitad_no_sale_el_texto_de_antes_de_buscar(modelo, monkeypatch):
    def _create(**kw):
        if kw["messages"][-1]["role"] == "tool":
            raise ValueError("400 bad request")
        return _resp("Dejame buscar...", [_llamada("buscar", rubro="mouse")])
    monkeypatch.setattr("app.core.llm_reintento._cliente",
                        lambda: NS(chat=NS(completions=NS(create=_create))))
    assert _turno([], "que mouse tenes?")["texto"] == ""


# ── EL LOOP ──────────────────────────────────────────────────────────────────

def test_el_agente_consulta_lee_y_contesta(modelo):
    m = modelo([_resp(llamadas=[_llamada("producto", nombre="K120 negro")]),
                _resp("El K120 negro sale $14.500.")])
    r = _turno([], "cuanto sale el K120 negro?")
    assert r["texto"] == "El K120 negro sale $14.500."
    assert [x["herramienta"] for x in r["llamadas"]] == ["producto"]
    assert m.pedidos[1]["messages"][-1]["role"] == "tool"


def test_la_misma_consulta_dos_veces_no_se_vuelve_a_ejecutar(modelo):
    ll = _llamada("envio", destinos=["Rosario"])
    modelo([_resp(llamadas=[ll]), _resp(llamadas=[ll]), _resp("A Rosario sale $7.000.")])
    r = _turno([], "cuanto a rosario?")
    assert "aviso" in r["llamadas"][1]["vuelve"]


def test_la_ultima_vuelta_obliga_a_contestar(modelo):
    """Un modelo que no para de consultar no deja al bot mudo: la ultima vuelta
    va sin herramientas habilitadas."""
    m = modelo([_resp(llamadas=[_llamada("politica", pregunta=f"p{i}")]) for i in range(A.MAX_VUELTAS)]
               + [_resp("te cuento")])
    r = _turno([], "hola")
    assert r["texto"] == "te cuento"
    assert m.pedidos[-1]["tool_choice"] == "none"


def test_lo_fijo_va_adelante_y_lo_que_cambia_atras(modelo):
    """El caché del proveedor reusa el comienzo idéntico: el sistema primero,
    después la memoria, la charla y el mensaje."""
    m = modelo([_resp("dale")])
    _turno([{"role": "user", "content": "hola"}, {"role": "assistant", "content": "que tal"}],
           "y el G305?", memoria="Envia a: Rosario")
    msgs = m.pedidos[0]["messages"]
    assert msgs[0]["content"] == A.sistema(TIENDA)
    assert "Rosario" in msgs[1]["content"]
    assert msgs[-1] == {"role": "user", "content": "y el G305?"}


# ── EL TURNO ENTERO ──────────────────────────────────────────────────────────

def _agente_fijo(monkeypatch, texto, llamadas):
    async def falso(historial, mensaje, tienda_id, trace_id="", memoria=""):
        return {"texto": texto, "llamadas": llamadas, "uso": []}
    monkeypatch.setattr(A, "turno", falso)


def _procesar(uid, msg):
    return asyncio.run(R.procesar_turno(uid, msg, TIENDA, "whatsapp", "t"))


def test_la_plata_que_ninguna_herramienta_devolvio_no_sale(monkeypatch):
    _agente_fijo(monkeypatch, "El K120 sale $99.999.",
                 [{"herramienta": "producto", "args": {}, "vuelve": {"filas": [
                     {"id": "TEC0029", "nombre": "Teclado Logitech K120 Negro", "precio": "$14.500"}]}}])
    from app.config import get_settings
    texto = _procesar("t_agente_plata", "cuanto sale el k120?")
    assert get_settings().VERIFIKA_FALLBACK_MESSAGE in texto and "99.999" not in texto


def test_sin_texto_del_modelo_el_bot_no_queda_mudo(monkeypatch):
    _agente_fijo(monkeypatch, "", [])
    assert _procesar("t_agente_mudo", "hola").strip()


def test_la_cuenta_y_el_destino_quedan_en_la_charla(monkeypatch):
    cuenta = A.h_cuenta(TIENDA, items=[{"producto": "G305 negro", "cantidad": 1}], destino="Rosario")
    _agente_fijo(monkeypatch, "Con el envio a Rosario, el total es $87.500.",
                 [{"herramienta": "cuenta", "args": {}, "vuelve": cuenta}])
    _procesar("t_agente_cuenta", "mandamelo a rosario, cuanto seria?")
    from app.storage.firestore_client import get_conversation
    conv = get_conversation("t_agente_cuenta", tienda_id=TIENDA)
    assert "87.500" in (conv.get("ultimo_presupuesto") or "")
    assert conv.get("ultima_localidad")
    assert conv["carrito_vigente"][0]["id"] == "MOU0029"


def test_reservar_es_la_señal_de_compra_para_el_cierre():
    assert R._senal([{"herramienta": "reservar", "vuelve": {"veredicto": "listo_para_cerrar"}}],
                    "dale")["intencion"] == "decision_compra"
    assert R._senal([{"herramienta": "buscar", "vuelve": {}}], "que teclados hay?")["intencion"] == "exploracion"


def test_lo_que_el_cliente_vio_queda_en_la_memoria(monkeypatch):
    _agente_fijo(monkeypatch, "El G203 negro sale $37.500.",
                 [{"herramienta": "producto", "args": {}, "vuelve": {"filas": [
                     {"id": "MOU0001", "nombre": "Mouse Logitech G203 Lightsync Negro", "precio": "$37.500"}]}}])
    _procesar("t_agente_vistos", "cuanto sale el g203 negro?")
    from app.storage.firestore_client import get_conversation
    conv = get_conversation("t_agente_vistos", tienda_id=TIENDA)
    assert [p["id"] for p in conv["productos_vistos"]] == ["MOU0001"]
    assert "MOU0001" in R._memoria_texto(conv)
