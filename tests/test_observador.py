"""
AREA: Observador del banco — captura de los eventos radar del camino vivo.

El observador (banco_pruebas/observador.py) captura por processor de structlog
los MISMOS eventos que en produccion se leen en Cloud Logging, cortados por
turno. Es la pieza que hace fidedigna una corrida del banco: un radar que
dispara queda registrado y juzgable, no se pierde en el scroll.
"""
import pytest


@pytest.fixture()
def obs():
    from banco_pruebas import observador
    observador.instalar(consola=False)
    observador.limpiar()
    return observador


def test_captura_corta_por_turno_y_clasifica_radar(obs):
    """Cada turno ve SOLO sus eventos; radar = warning o peor, info no."""
    from app.logger import get_logger
    log = get_logger("test_obs")
    with obs.turno() as t1:
        log.info("evento_info", dato=1)
        log.warning("radar_uno", trace_id="abc123", destinos=["x"])
    with obs.turno() as t2:
        log.error("radar_dos")
    assert "evento_info" in t1.nombres()
    assert t1.nombres(solo_radar=True) == ["radar_uno"]
    assert t2.nombres() == ["radar_dos"]
    assert t2.nombres(solo_radar=True) == ["radar_dos"]


def test_el_radar_conserva_los_campos_de_evidencia(obs):
    """trace_id y los campos del evento viajan enteros a la captura."""
    from app.logger import get_logger
    get_logger("test_obs").warning("radar_campos", trace_id="t1",
                                   destinos=["Monte Ralo"])
    with obs.turno() as t:
        get_logger("test_obs").warning("radar_campos", trace_id="t2",
                                       monto=7500)
    e = t.radares()[0]
    assert e["trace_id"] == "t2" and e["monto"] == 7500


def test_turno_captura_aunque_el_codigo_explote(obs):
    """Si el turno tira excepcion, los eventos previos igual quedan."""
    from app.logger import get_logger
    with pytest.raises(RuntimeError):
        with obs.turno() as t:
            get_logger("test_obs").warning("radar_antes_del_error")
            raise RuntimeError("boom")
    assert t.nombres(solo_radar=True) == ["radar_antes_del_error"]


def test_resumen_radares_cuenta_toda_la_corrida(obs):
    from app.logger import get_logger
    log = get_logger("test_obs")
    turnos = []
    for _ in range(2):
        with obs.turno() as t:
            log.warning("radar_repetido")
            log.info("ruido_info")
        turnos.append(t)
    with obs.turno() as t3:
        log.error("radar_unico")
    turnos.append(t3)
    assert obs.resumen_radares(turnos) == {"radar_repetido": 2,
                                           "radar_unico": 1}


def test_captura_un_radar_real_del_camino_vivo(obs):
    """Integracion con codigo de produccion REAL: coercionar_destinos loguea
    interpretador_destino_fantasma y el observador lo caza con sus campos.

    El caso ademas DOCUMENTA el punto flaco pendiente (RESUMEN 18-jul): el
    guardia solo mira el mensaje ACTUAL, asi que un destino legitimo dicho en
    un turno ANTERIOR (memoria) tambien se anula. Cuando se arregle con
    memoria multiturno, este test cambia con el nuevo contrato."""
    from app.core.interpretador import coercionar_destinos
    resultado = {"pedido": [{"categoria": "mouse", "cantidad": 1,
                             "destino": "Monte Ralo"}]}
    with obs.turno() as t:
        coercionar_destinos(resultado, "si, dale, ese quiero")
    assert resultado["pedido"][0]["destino"] is None
    radares = t.radares()
    assert [e["event"] for e in radares] == ["interpretador_destino_fantasma"]
    assert radares[0]["destinos"] == ["Monte Ralo"]
