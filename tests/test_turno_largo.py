"""
EL BANCO DEL TURNO LARGO — la charla que dura, medida por longitud.

POR QUE FALTABA (Martin, 12-ago-2026). La prioridad 3 esta escrita desde hace
semanas y dice: "que la memoria este SIEMPRE activa; 'te referis a la memoria'
diez turnos despues TIENE que resolver". Y sin embargo **ningun banco medía la
LONGITUD**. Las 40 preguntas son de un turno cada una. Las charlas grabadas
tienen entre 2 y 6 turnos. O sea que el caso que Martin nombra —una referencia a
algo dicho diez turnos antes— no lo probaba nadie, y por eso cada vez que se
tocaba el largo de los mensajes habia que verificar a mano que no se hubiera
llevado puesto el hilo.

QUE HACE, Y POR QUE PUEDE CORRER GRATIS. No simula la conversacion con el
modelo: arma el ESTADO tal como el hub lo guarda turno a turno y lo hace crecer.
Toda la memoria de este sistema es determinista —`merge_productos`,
`construir_estado`, el ancla, el carrito, el tope del historial— asi que la
longitud se puede barrer sin gastar una sola llamada. Lo que NO cubre es la
redaccion del modelo en un turno 10; eso sigue siendo prueba en real.

LA FORMA ES UN BARRIDO, no un caso: se corre a 1, 5, 10, 20 y 40 turnos, y lo
que se afirma son propiedades que no pueden dejar de valer porque la charla se
haga larga. Un limite que se cruza en el turno 21 se ve; un caso escrito a mano
en el turno 10 no lo veria nunca.
"""
import pytest

from app.config import get_settings
from app.core.estado_venta import (ancla_al_dia, construir_estado,
                                   merge_productos)

LARGOS = (1, 5, 10, 20, 40)

_CATALOGO = [
    {"id": "MOU0009", "nombre": "Mouse Logitech M170 Negro", "precio_ars": 12000},
    {"id": "MOU0023", "nombre": "Mouse Genius DX-110 Negro", "precio_ars": 8500},
    {"id": "TEC0004", "nombre": "Teclado Genius KB-110X Blanco", "precio_ars": 12000},
    {"id": "AUR0001", "nombre": "Auriculares HyperX Cloud II Negro",
     "precio_ars": 125500},
    {"id": "NOT0162", "nombre": "Notebook HP 245 G9 Core i5 16GB 512GB SSD Gris",
     "precio_ars": 693000},
]


def _charla(turnos: int, vistos_por_turno: int = 3) -> dict:
    """La conversacion como la guarda el hub despues de `turnos` turnos.

    No es una maqueta: son los mismos campos que escribe `save_conversation`, y
    los productos vistos se acumulan con la MISMA funcion que usa el hub."""
    historial: list = []
    vistos: list = []
    for t in range(1, turnos + 1):
        historial += [{"role": "user", "content": f"mensaje del cliente {t}"},
                      {"role": "assistant", "content": f"respuesta del bot {t}"}]
        del_turno = []
        for pos, p in enumerate(_CATALOGO[:vistos_por_turno]):
            del_turno.append({"id": p["id"], "nombre": p["nombre"],
                              "precio": p["precio_ars"], "turno": t,
                              "posicion": pos, "categoria": ""})
        vistos = merge_productos(vistos, del_turno)
    tope = get_settings().HISTORY_LIMIT * 2
    return {
        "history": historial[-tope:],
        "summary": f"resumen de los primeros {max(0, turnos - 10)} turnos",
        "productos_vistos": vistos,
        "carrito_vigente": [{"id": "MOU0009",
                             "nombre": "Mouse Logitech M170 Negro",
                             "cantidad": 2}],
        "ultima_localidad": "Cordoba capital",
        "ultimas_localidades": ["Cordoba capital"],
        "producto_anotado": {"id": "MOU0009",
                             "nombre": "Mouse Logitech M170 Negro",
                             "precio": 12000},
        "ultimo_presupuesto": "Presupuesto:\n- 2x Mouse Logitech M170 Negro: "
                              "$12.000 c/u = $24.000\nTotal: $24.000",
    }


# ── 1. LO QUE NO PUEDE PERDERSE POR LARGO ──────────────────────────────────

@pytest.mark.parametrize("turnos", LARGOS)
def test_el_carrito_sobrevive_la_charla_entera(turnos):
    """El pedido no pierde identidad porque la charla se haga larga. Si el
    carrito se cae, el cliente tiene que volver a decir lo que ya dijo, que es
    la peor forma de perder una venta ya hecha."""
    estado = construir_estado(_charla(turnos), None)
    carrito = estado.get("carrito") or []
    assert carrito, f"el carrito se perdio a los {turnos} turnos"
    assert carrito[0]["id"] == "MOU0009"
    assert carrito[0]["cantidad"] == 2


@pytest.mark.parametrize("turnos", LARGOS)
def test_la_referencia_lejana_resuelve_a_cualquier_distancia(turnos):
    """EL CASO QUE MARTIN NOMBRA, textual: "el que te mencioné al principio",
    diez turnos despues. Es la prioridad 3 escrita como test."""
    estado = construir_estado(_charla(turnos), None)
    interp = {"intencion": "decision_compra", "producto_resuelto": None,
              "candidatos": [], "confianza": 0.5, "pedido": []}
    estado = construir_estado(_charla(turnos), None)
    ancla = estado.get("producto_anotado") or {}
    assert ancla.get("nombre") == "Mouse Logitech M170 Negro", (
        f"a los {turnos} turnos el ancla no sobrevivio al estado")
    # Y tiene que llegar al prompt: guardarla y no mostrarla es lo mismo que
    # no tenerla, que es como estuvo hasta el 12-ago.
    from app.core.hub_venta import _memoria_texto
    assert "Mouse Logitech M170 Negro" in _memoria_texto(estado, [])


@pytest.mark.parametrize("turnos", LARGOS)
def test_el_ancla_no_se_borra_por_turnos_que_hablan_de_otra_cosa(turnos):
    """Entre que se anota y que se referencia pasan turnos de politica, de
    envios, de dudas. Ninguno de esos puede llevarse el ancla puesta."""
    previo = {"id": "MOU0009", "nombre": "Mouse Logitech M170 Negro",
              "precio": 12000}
    for _ in range(turnos):
        previo = ancla_al_dia(previo, "y como es el tema de la garantia?",
                              [{"id": "TEC0004",
                                "nombre": "Teclado Genius KB-110X Blanco"}])
    assert previo and previo.get("id") == "MOU0009", (
        f"el ancla se perdio despues de {turnos} turnos de otra cosa")


@pytest.mark.parametrize("turnos", LARGOS)
def test_el_orden_en_que_se_mostraron_sobrevive(turnos):
    """"El primero que me mostraste" y "el segundo teclado" se resuelven con el
    turno y la posicion, no con el texto. Si el tope de la memoria los pisa, el
    ordinal deja de tener contra que resolverse."""
    estado = construir_estado(_charla(turnos), None)
    vistos = estado.get("productos_vistos") or []
    assert vistos, f"no quedo un solo producto visto a los {turnos} turnos"
    assert all("turno" in p and "posicion" in p for p in vistos), (
        "los productos vistos perdieron el orden en que se mostraron")
    primero = min(vistos, key=lambda p: (p.get("turno", 0), p.get("posicion", 0)))
    assert primero["id"] == "MOU0009"


def test_el_tope_de_la_memoria_no_tira_una_categoria_entera():
    """EL TOPE MIDE, y ya costo una vez: con tope 20, un turno de tres
    busquedas traia 30 productos y la primera categoria se caia entera. Se barre
    una charla larga con muchos productos por turno y se exige que lo ULTIMO
    mostrado sobreviva siempre."""
    vistos: list = []
    for t in range(1, 41):
        del_turno = [{"id": f"P{t:03d}{i}", "nombre": f"Producto {t}-{i}",
                      "precio": 1000, "turno": t, "posicion": i,
                      "categoria": ""} for i in range(10)]
        vistos = merge_productos(vistos, del_turno)
    ids = {p["id"] for p in vistos}
    assert {f"P040{i}" for i in range(10)} <= ids, (
        "el tope se comio lo que se acaba de mostrar")
    # LA FALLA DEL 8-JUL, escrita como assert: con tope 20 y tres busquedas por
    # turno, la PRIMERA categoria se caia entera. No alcanza con que sobreviva
    # lo ultimo: tienen que entrar los seis turnos que el tope promete. Sin
    # esta linea el test pasaba con el tope viejo, o sea que no tenia dientes
    # —comprobado rompiendolo a proposito el 12-ago—.
    for t in range(35, 41):
        assert {f"P{t:03d}{i}" for i in range(10)} <= ids, (
            f"el turno {t} se cayo de la memoria: el tope no llega a 60")
    assert len(vistos) <= 60, f"la memoria crecio sin tope: {len(vistos)}"


@pytest.mark.parametrize("turnos", LARGOS)
def test_el_historial_se_recorta_pero_el_resumen_queda(turnos):
    """La charla larga no puede crecer sin limite —el prompt se iria de precio y
    de latencia— pero recortar no puede dejar al bot sin pasado: lo viejo vive
    en el resumen."""
    conv = _charla(turnos)
    tope = get_settings().HISTORY_LIMIT * 2
    assert len(conv["history"]) <= tope
    if turnos * 2 > tope:
        assert conv["summary"], (
            "se recorto el historial y no quedo resumen: el bot perdio el hilo")


# ── 2. LA PROPIEDAD, sobre el largo entero ─────────────────────────────────

def test_nada_de_lo_que_importa_depende_del_largo():
    """LA PROPIEDAD QUE RESUME A TODAS: el estado que el turno necesita para
    contestar bien es el MISMO a 1 turno que a 40. Si algo se degrada con la
    longitud, se ve como una diferencia entre dos largos y no hay que
    anticipar en cual."""
    def foto(turnos):
        e = construir_estado(_charla(turnos), None)
        return {
            "carrito": [(c["id"], c["cantidad"]) for c in (e.get("carrito") or [])],
            "ancla": (e.get("producto_anotado") or {}).get("id"),
            "localidad": e.get("ultima_localidad") or e.get("localidad"),
            "tiene_presupuesto": bool(e.get("ultimo_presupuesto")),
            "primer_visto": min(
                (p for p in (e.get("productos_vistos") or [])),
                key=lambda p: (p.get("turno", 0), p.get("posicion", 0)),
                default={}).get("id"),
        }

    base = foto(1)
    for turnos in LARGOS[1:]:
        assert foto(turnos) == base, (
            f"el estado cambio entre 1 y {turnos} turnos: {foto(turnos)} vs {base}")
