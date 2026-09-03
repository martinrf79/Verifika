"""CANDADO: el nocturno no puede volver a apuntar al hub apagado.

El 3-sep el cron `calidad` quedo rojo en 23 segundos, sin hablarle al modelo:
`banco_repetido._Espia` importaba `hub_venta` (apagado el mismo dia) y
`calidad.yml` pedia `tests/test_mapa.py` (archivado). El camino vivo del banco
ya era `clon_produccion.turno` -> webhook -> `turno.py`. Solo el espia estaba
sordo.

Este test corre en cada push, gratis, y cubre esa clase de error: el espia
escucha `app.core.turno.log`, los candados son eventos que ese modulo emite, y
el workflow no pide un test que no esta.
"""
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent


def test_el_espia_escucha_el_turno_vivo_en_un_caso():
    fuente = (_RAIZ / "banco_pruebas" / "banco_repetido.py").read_text(
        encoding="utf-8")
    assert "hub_venta" not in fuente, (
        "banco_repetido.py volvio a nombrar hub_venta. El hub esta apagado; "
        "el espia tiene que parchar app.core.turno.log")

    from banco_pruebas.banco_repetido import _CANDADOS, _Espia
    from app.core import turno as T

    assert _CANDADOS, "un mapa vacio esconde que el espia no mide nada"
    assert all(k.startswith("turno_") for k in _CANDADOS), (
        "los candados tienen que ser eventos de turno.py, no del hub apagado: "
        + ", ".join(_CANDADOS))
    fuente_turno = Path(T.__file__).read_text(encoding="utf-8")
    faltan = [k for k in _CANDADOS if k not in fuente_turno]
    assert not faltan, (
        "candados que turno.py no emite (no se inventan eventos): "
        + ", ".join(faltan))

    with _Espia() as espia:
        T.log.warning("turno_pedidos_recortados")
        T.log.error("turno_respuesta_no_es_la_mesa")
    assert "herramientas recortadas" in espia.candados()
    assert "respuesta no es la mesa" in espia.candados()


def test_calidad_yml_no_pide_el_mapa_archivado_en_un_archivo():
    yml = (_RAIZ / ".github" / "workflows" / "calidad.yml").read_text(
        encoding="utf-8")
    assert "pytest tests/test_mapa.py" not in yml, (
        "calidad.yml volvio a pedir tests/test_mapa.py. Ese test esta en "
        "archivo/; no se revive contra el inventario de turno.py sin ficha")
