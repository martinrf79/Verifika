"""
Dos fixes de comportamiento del banco end-to-end (23-jul), probados deterministas
(el solver vivo es no-determinista, la logica de codigo no):

1. ANCLA sin producto elegido: si sale un total pero el cliente no eligio, se
   PREGUNTA cual en vez de asumir el mas barato (_exige_eleccion_de_producto).
2. COLETILLA de cierre: la misma invitacion no se repite turno a turno; se elige
   una variante no usada recientemente (_cierre_suave con history).
"""
from app.core.hub_atado import _exige_eleccion_de_producto
from app.core.generador_v2 import (_cierre_suave, _variar_cierre,
                                   _CIERRES_SUAVES, _CIERRES_PAGO)


# ── 1. ANCLA ─────────────────────────────────────────────────────────────────
_VISTOS2 = {"productos_vistos": [{"id": "MOU0023"}, {"id": "MOU0010"}]}


def test_exige_eleccion_cuando_total_sin_ancla_con_varios_mostrados():
    # total mostrado (present truthy), sin ancla valida, 2 mostrados -> preguntar
    assert _exige_eleccion_de_producto({"intencion": "aporta_dato"}, _VISTOS2,
                                       present="Total: $8.500", ancla_valida=False)


def test_no_exige_si_no_hubo_total():
    # sin presupuesto sobre la mesa no hay nada que asumir: no se pregunta
    assert not _exige_eleccion_de_producto({}, _VISTOS2, present=None,
                                           ancla_valida=False)


def test_no_exige_con_ancla_valida():
    # "cerremos con el que te dije": el producto resolvio a uno real -> se cierra
    assert not _exige_eleccion_de_producto({}, _VISTOS2, present="Total: $x",
                                           ancla_valida=True)


def test_no_exige_con_un_solo_producto_mostrado():
    # un solo candidato: asumirlo NO es una asuncion, es lo obvio
    estado = {"productos_vistos": [{"id": "MOU0023"}]}
    assert not _exige_eleccion_de_producto({}, estado, present="Total: $x",
                                           ancla_valida=False)


def test_no_exige_con_carrito():
    estado = {"productos_vistos": [{"id": "A"}, {"id": "B"}],
              "carrito": [{"nombre": "Mouse", "cantidad": 1}]}
    assert not _exige_eleccion_de_producto({}, estado, present="Total: $x",
                                           ancla_valida=False)


def test_no_exige_con_criterio_de_seleccion():
    # "los dos mas baratos" / categoria nueva: el solver elige legitimo
    interp = {"solicitud_nueva": [{"categoria": "mouse", "criterio": "mas_barato"}]}
    assert not _exige_eleccion_de_producto(interp, _VISTOS2, present="Total: $x",
                                           ancla_valida=False)


# ── 2. COLETILLA ─────────────────────────────────────────────────────────────
def test_cierre_evita_la_variante_del_turno_anterior():
    # la ultima linea del bot en el turno previo fue una variante; el cierre de
    # este turno elige OTRA, no la repite.
    previa = _CIERRES_SUAVES[0]
    hist = [{"role": "assistant", "content": "algo mostrado\n" + previa}]
    salida = _cierre_suave(["contenido nuevo del turno"], hist)
    assert salida != previa
    assert salida in _CIERRES_SUAVES


def test_cierre_sin_historial_sigue_saliendo():
    salida = _cierre_suave(["contenido"], None)
    assert salida in _CIERRES_SUAVES


def test_cierre_no_repite_en_tres_turnos_seguidos():
    # simula tres turnos: cada cierre entra al historial; ninguna variante sale
    # tres veces (lo que cazaba el juez).
    hist: list = []
    salidas = []
    for i in range(3):
        s = _cierre_suave([f"turno {i} distinto"], hist)
        salidas.append(s)
        hist.append({"role": "assistant", "content": f"cuerpo {i}\n" + s})
    # ninguna de las variantes usadas aparece 3 veces
    assert all(salidas.count(s) < 3 for s in salidas)


def test_cierre_con_total_tampoco_se_repite_en_cinco_turnos():
    # el cierre CON total (pide forma de pago) se repetia 4-5 veces en charlas
    # multi-total (guiones 52/53). Con el pool variado, cada variante < 3 en 5.
    hist: list = []
    salidas = []
    for i in range(5):
        s = _variar_cierre(_CIERRES_PAGO, [f"Total: ${i}000"], hist)
        salidas.append(s)
        hist.append({"role": "assistant", "content": f"Presupuesto {i}\n" + s})
    assert all(salidas.count(s) < 3 for s in salidas)
    # y todas conservan el dato de los medios de pago (no se pierde la info)
    assert all("Mercado Pago" in s for s in salidas)
