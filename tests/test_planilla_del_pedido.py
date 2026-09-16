"""LA PLANILLA — el pedido del cliente existe antes de decidir por donde va.

EL DEFECTO, MEDIDO DOS VECES EN WHATSAPP EL 16-sep, a las 12:05 y a las 19:47,
con el mismo mensaje y con dos versiones distintas del bot en el medio:

    "las menos partes chinas posibles"      ->  cero condiciones, las dos veces
    "divide el presupuesto en setenta treinta"  ->  cero cuentas, las dos veces

NO ES QUE LOS RESOLVIO MAL: ES QUE NO DEJARON RASTRO. El modelo escribia
`consultas`, y lo que no le parecia una consulta no existia en ningun lado. El
turno no podia saber que le faltaba algo, el log no podia contarlo, y la
respuesta ni los mencionaba. Dos arreglos seguidos sobre la SALIDA —la guarda
de estado y despues la correccion— mejoraron la frase y no movieron esto ni un
milimetro, porque el problema estaba una estacion antes.

LO QUE CAMBIA. El modelo anota primero, en `pedido`, TODO lo que el cliente
pidio, con las palabras del cliente y sin traducir. Despues dice en `atiende`
cuales cubre esa llamada. El codigo resta y devuelve `sin_atender`.

EL CRUCE ES POR ID, y eso es lo que lo hace distinto de los cuatro intentos que
este repo ya pago. Aparear por palabras compartidas es D3, D4, D6 y D16 en el
`MAPA_CABLEADO`: la junta blanda decide con una coincidencia de tres letras cual
evidencia contesta cual pregunta. Aca no hay nada que adivinar.

UN RENGLON SIN ATENDER NO ES UN ERROR, es un pendiente. Hay pedidos que la
fuente no puede cumplir —el origen es D8 y es de FUENTE— y ahi la respuesta
correcta es DECIRLO, no callarlo. Por eso vuelve como dato y no como excepcion.
"""
import asyncio
import json

import pytest

from app.core import bocas as BC
from app.core import motor as MT
from app.core import respuesta as R

TIENDA = "verifika_prod"


@pytest.fixture(autouse=True)
def _doble(firestore_doble):
    from app.core.contexto_turno import set_current_tienda
    from app.core.filtros_catalogo import limpiar_cache
    set_current_tienda(TIENDA)
    limpiar_cache()
    return firestore_doble


# EL PEDIDO DEL 16-sep, tal como el modelo tendria que anotarlo.
_PEDIDO = [
    {"id": "r1", "dice": "dos auriculares"},
    {"id": "r2", "dice": "dos mouse"},
    {"id": "r3", "dice": "dos memorias"},
    {"id": "r4", "dice": "las menos partes chinas posibles"},
    {"id": "r5", "dice": "envio a Cordoba capital"},
    {"id": "r6", "dice": "envio a Concordia"},
    {"id": "r7", "dice": "envio a Posadas"},
    {"id": "r8", "dice": "dividir el presupuesto en setenta treinta"},
]


def test_EL_CASO_lo_que_el_cliente_pidio_y_nadie_atendio_vuelve():
    """El turno real: se atienden los productos y los envios, y los dos que el
    bot ignoro las dos veces quedan a la vista con las palabras del cliente."""
    r = MT.buscar(
        [{"categoria": "auriculares", "busco": "varios"},
         {"categoria": "mouse", "busco": "varios"}],
        TIENDA, "t", envios=["Posadas"],
        pedido=_PEDIDO, atiende=["r1", "r2", "r3", "r5", "r6", "r7"])
    pendientes = [x["dice"] for x in r.get("sin_atender") or []]
    assert pendientes == ["las menos partes chinas posibles",
                          "dividir el presupuesto en setenta treinta"], pendientes


def test_el_cruce_es_por_ID_y_no_por_palabras_compartidas():
    """LA ENFERMEDAD QUE EL MAPA_CABLEADO TIENE NUMERADA CUATRO VECES. Dos
    renglones que comparten todas las palabras menos una siguen siendo dos, y
    atender uno no atiende al otro."""
    pedido = [{"id": "a", "dice": "envio a Cordoba"},
              {"id": "b", "dice": "envio a Concordia"}]
    r = MT.buscar([], TIENDA, "t", temas=["garantia"],
                  pedido=pedido, atiende=["a"])
    assert [x["id"] for x in r["sin_atender"]] == ["b"]


def test_un_pedido_ENTERAMENTE_atendido_no_devuelve_la_caja():
    """La caja que nadie pidio no viaja: una clave vacia en cada turno es ruido
    adentro de la caja donde todo lo demas es dato certificado."""
    r = MT.buscar([{"categoria": "teclado"}], TIENDA, "t",
                  pedido=[{"id": "r1", "dice": "un teclado"}],
                  atiende=["r1"])
    assert "sin_atender" not in r


def test_sin_planilla_el_motor_anda_igual():
    """Un turno viejo, o un modelo que no la mando: el motor no se rompe ni
    inventa pendientes. La planilla la obliga el esquema, no una excepcion."""
    r = MT.buscar([{"categoria": "teclado"}], TIENDA, "t")
    assert "sin_atender" not in r
    assert r["resultados"]


# ── EL ESQUEMA ──────────────────────────────────────────────────────────────

def test_la_planilla_es_lo_UNICO_obligatorio_del_tablero():
    """Y EL CANDADO ES ESTE, no el prompt. Si `pedido` fuera opcional, el
    modelo la saltea el dia que tiene apuro y volvemos al 16-sep.

    Se mide sobre el esquema ARMADO y no sobre el codigo que lo arma: habia un
    `"required": []` mas abajo que pisaba en silencio al de arriba, o sea que
    la pieza salia apagada sin que nadie lo viera."""
    p = MT.esquema(TIENDA)["function"]["parameters"]
    assert p.get("required") == ["pedido"], p.get("required")


def test_el_pedido_y_el_cruce_estan_en_el_tablero():
    props = MT.esquema(TIENDA)["function"]["parameters"]["properties"]
    assert "pedido" in props and "atiende" in props
    assert props["pedido"]["items"]["required"] == ["id", "dice"]


def test_el_retorno_EXPLICA_que_hacer_con_lo_que_quedo_pendiente():
    """Una caja nueva que vuelve muda es una caja que el modelo tira. El
    candado general esta en `test_retorno_se_explica`; esto fija lo que la
    instruccion tiene que DECIR, que es que se resuelve o se dice."""
    lee = BC.para_el_retorno()
    assert "`sin_atender`" in lee
    assert "se DICE" in lee or "se dice" in lee


# ── EL NUMERO ───────────────────────────────────────────────────────────────

def test_el_turno_CUENTA_los_renglones_y_los_pendientes():
    """Sin estos dos numeros no hay forma de saber si la pieza se esta usando:
    `renglones` en cero significa que el modelo no la llena, y `sin_atender`
    es EL numero de la unidad."""
    informe = R._informe_en_blanco()
    r = MT.buscar([{"categoria": "teclado"}], TIENDA, "t",
                  pedido=_PEDIDO, atiende=["r1"])
    R._anotar(informe, [{"categoria": "teclado"}], set(), r, _PEDIDO)
    assert informe["renglones"] == 8
    assert "las menos partes chinas posibles" in informe["sin_atender"]
    assert len(informe["sin_atender"]) == 7


def test_el_informe_y_la_pelicula_nombran_lo_mismo():
    """El candado de siempre, aplicado a los dos campos nuevos."""
    from banco_pruebas import produccion as P
    assert set(P.CAMPOS) == set(R._informe_en_blanco())


# ── EL TURNO ENTERO ─────────────────────────────────────────────────────────

def test_el_turno_le_devuelve_al_modelo_lo_que_quedo_pendiente(monkeypatch):
    """END TO END, con el modelo doblado: el pendiente tiene que LLEGARLE en la
    vuelta siguiente. Que el motor lo calcule no sirve de nada si el bloque no
    viaja, que es exactamente el defecto que costo el envio cotizado y no dicho.
    """
    from tests.test_correccion_de_estado import _Call, _ClienteFalso, _Msg
    from app.core import llm_reintento as LR

    pedido = json.dumps(_PEDIDO, ensure_ascii=False)
    guion = [
        # vuelta 1: anota el pedido ENTERO y atiende solo una parte
        _Msg(tool_calls=[_Call(
            '{"pedido": ' + pedido + ', "atiende": ["r1"], '
            '"consultas": [{"categoria": "auriculares", "busco": "varios"}]}')]),
        _Msg('{"tipo": "lista", "texto": "Ahi va."}'),
    ]
    cli = _ClienteFalso(guion)
    monkeypatch.setattr(LR, "_cliente", lambda: cli)
    monkeypatch.setattr(LR, "_modelo", lambda: "doble")
    _, _, _, _, informe = asyncio.run(R._preguntar(
        "", "", [], "dame dos auriculares sin partes chinas", "", "t", TIENDA))

    assert informe["renglones"] == 8
    assert len(informe["sin_atender"]) == 7
    # LO QUE IMPORTA: que le haya LLEGADO en la vuelta de contestar.
    ultimo = "\n".join(str(m.get("content") or "")
                       for m in cli.vistos[-1]["messages"])
    assert "las menos partes chinas posibles" in ultimo, (
        "el pendiente se calculo y no viajo: el modelo no puede decir lo que "
        "no ve")
    assert "sin_atender" in ultimo
