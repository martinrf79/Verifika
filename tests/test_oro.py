"""
EL CANDADO DE LOS CASOS DE ORO.

La vara por capa del paso 0 de `arquitectura/BRIEF_MOTOR_V2.md`. Los casos
viven en `tests/oro/` y los corre `banco_pruebas/oro.py`; aca se cuida que el
numero SOLO SUBA y que los archivos sigan siendo legibles.

Todo esto corre offline y gratis: las capas 2, 4 y 5 son cableado puro, no
tienen una sola llamada al modelo adentro.
"""
import json
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
ORO = _RAIZ / "tests" / "oro"


@pytest.fixture(scope="module")
def corrida():
    from banco_pruebas import oro
    return oro.correr()


def test_el_piso_de_cada_capa_no_baja(corrida):
    """El numero de cada capa puede SUBIR. Si baja, algo se rompio y el CI lo
    grita con el nombre de los casos que se cayeron.

    Se refija con `python3 banco_pruebas/oro.py --fijar`, y esa linea va en su
    PROPIO commit, antes del trabajo que la hace pasar."""
    from banco_pruebas import oro
    piso = oro.piso()
    assert piso, "falta banco_pruebas/oro_piso.json: corre oro.py --fijar"
    for n, filas in corrida.items():
        verdes = [f["id"] for f in filas if f["ok"]]
        rojas = [f["id"] for f in filas if not f["ok"]]
        assert len(verdes) >= piso[f"capa{n}"], (
            f"la capa {n} bajo de {piso[f'capa{n}']} a {len(verdes)}. "
            f"En rojo ahora: {rojas}")


def test_ningun_caso_se_borro(corrida):
    """Un caso de oro se corrige a mano; no se borra. Bajar el denominador es
    la otra forma de aflojar la vara, y es la mas silenciosa."""
    from banco_pruebas import oro
    piso = oro.piso()
    for n, filas in corrida.items():
        assert len(filas) >= piso[f"capa{n}_total"], (
            f"la capa {n} tenia {piso[f'capa{n}_total']} casos y ahora tiene "
            f"{len(filas)}: un caso de oro no se borra")


@pytest.mark.parametrize("capa", ["capa2", "capa4", "capa5"])
def test_cada_caso_dice_de_donde_sale_y_que_mide(capa):
    """Un caso sin `que` es un numero sin significado: cuando se pone rojo,
    nadie sabe que se rompio."""
    archivos = sorted((ORO / capa).glob("*.json"))
    assert archivos, f"{capa} se quedo sin casos"
    for a in archivos:
        c = json.loads(a.read_text(encoding="utf-8"))
        assert c.get("id") == a.stem, f"{a.name}: el id no coincide con el archivo"
        assert c.get("que"), f"{a.name}: no dice que mide"
        assert c.get("espera"), f"{a.name}: no espera nada, asi que no mide nada"


def test_las_40_estan_todas_en_la_capa_2():
    """La capa 2 se mide SOBRE LAS 40 PREGUNTAS, no sobre una seleccion comoda.
    Si `las_40.py` suma una, aca falta su caso de oro."""
    from banco_pruebas.las_40 import LAS_40
    cubiertas = {json.loads(p.read_text(encoding="utf-8")).get("de")
                 for p in (ORO / "capa2").glob("*.json")}
    faltan = sorted({id_ for id_, *_ in LAS_40} - cubiertas)
    assert not faltan, f"las 40 sin caso de oro en la capa 2: {faltan}"
