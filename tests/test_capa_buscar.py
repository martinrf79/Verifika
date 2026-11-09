"""LAS CAPAS BUSCAR, PRODUCTO Y COMPRAR — candado de lo medido el 9-nov-2026, `arquitectura/PLAN_CAPAS.md`.

Lo que tradujeron los modelos, grabado en `banco_pruebas/traduccion58_corridas.jsonl`, pasa por la forma normal y el
ejecutor sin modelo, y tiene que mostrar los mismos productos que la agenda a mano. El techo de fallas por modelo vive en
`tests/capa_buscar_techo.json` y solo baja. Abajo, cada regla de la capa con su forma minima.
"""
import json
import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TECHO = os.path.join(RAIZ, "tests", "capa_buscar_techo.json")
TID = "verifika_prod"


@pytest.fixture(scope="module")
def entorno():
    sys.path.insert(0, os.path.join(RAIZ, "banco_pruebas"))
    from banco_pruebas.plantilla_venta import llenar as LL
    LL.entorno()


@pytest.mark.parametrize("tipo", ["buscar", "producto", "comprar"])
def test_lo_grabado_muestra_los_mismos_productos(entorno, tipo):
    from banco_pruebas import capa_buscar as CB
    techo = json.load(open(TECHO, encoding="utf-8"))[tipo]
    res = CB.correr(tuple(techo), tipo)
    for m, tope in techo.items():
        xs = [v["bien"] for k, v in res.items() if k.startswith(f"{m}|")]
        mal = len(xs) - sum(xs)
        print(f"capa {tipo} {m}: {sum(xs)} de {len(xs)} bien, {mal} mal, techo {tope}")
        assert mal <= tope, f"{m}: {mal} fallas, el techo es {tope}"
        assert tope - mal <= 2, f"{m}: el techo {tope} quedo viejo, hoy fallan {mal}: bajalo"


def _normal(preguntas, mensaje=""):
    from app.core.flujo import estado as E
    from app.core.flujo import normal as N
    ag = {"preguntas": preguntas, **({"mensaje": mensaje} if mensaje else {})}
    return N.normalizar(ag, E.leer({}), TID, {})


def test_orden_que_no_dijo(entorno):
    ag, rs = _normal([{"n": 1, "cita": "dos mouse, el precio no es tan importante", "accion": "buscar", "rubro": "mouse",
                       "orden": "mas caro"}])
    assert ag["preguntas"][0]["orden"] == "nada" and "orden_que_no_dijo" in rs
    ag, rs = _normal([{"n": 1, "cita": "dos auris", "accion": "buscar", "rubro": "auriculares", "orden": "mas barato"}],
                     "dos auris y dos mouse los mas baartos")
    assert ag["preguntas"][0]["orden"] == "mas barato" and "orden_que_no_dijo" not in rs
    ag, _ = _normal([{"n": 1, "cita": "la menor cantidad de partes chinas", "accion": "buscar", "rubro": "mouse",
                      "orden": "mas caro"}])
    assert ag["preguntas"][0]["orden"] == "nada"  # "menor" no es "mejor"


def test_lo_corregido(entorno):
    ag, rs = _normal([{"n": 1, "cita": "un teclado redragon", "accion": "buscar", "rubro": "teclado",
                       "condiciones": ["redragon"]},
                      {"n": 2, "cita": "ah no", "accion": "otro", "que": "corrige"},
                      {"n": 3, "cita": "mejor logitech", "accion": "buscar", "rubro": "teclado", "condiciones": ["logitech"]}])
    assert [p.get("condiciones") for p in ag["preguntas"] if p["accion"] == "buscar"] == [["logitech"]]
    assert "lo_corregido" in rs


def test_rubro_con_marca(entorno):
    ag, rs = _normal([{"n": 1, "cita": "tenes auriculares jbl", "accion": "producto", "producto": "auriculares jbl",
                       "quiere_saber": "stock"}])
    p = ag["preguntas"][0]
    assert (p["accion"], p["rubro"], p["condiciones"]) == ("buscar", "auriculares", ["jbl"]) and "rubro_con_marca" in rs
    ag, rs = _normal([{"n": 1, "cita": "tenes el g305", "accion": "producto", "producto": "G305"}])
    assert ag["preguntas"][0]["accion"] == "producto" and "rubro_con_marca" not in rs  # un modelo no es un rubro


def test_alternativa_compatible(entorno):
    ag, rs = _normal([{"n": 1, "cita": "si la fury ddr4 no va", "accion": "compatibilidad",
                       "producto": "Kingston Fury Beast DDR4 16GB", "con": "pc de escritorio con placa ddr5"},
                      {"n": 2, "cita": "que otra hay", "accion": "buscar", "rubro": "memoria ram", "si": {"de": 1, "da": "no"}}])
    assert ag["preguntas"][1]["condiciones"] == ["ddr5"] and "alternativa_compatible" in rs


def test_producto_del_envio(entorno):
    ag, rs = _normal([{"n": 1, "cita": "cuanto sale mandar un g203 a rosario", "accion": "envio", "destino": "rosario"}])
    # el producto con su envio pide ademas la cuenta: la regla de antes, `precio_con_envio`
    assert [p["accion"] for p in ag["preguntas"]][:2] == ["envio", "producto"] and "producto_del_envio" in rs
    ag, rs = _normal([{"n": 1, "cita": "otro a rio tercero a sabatini 2000", "accion": "envio", "destino": "rio tercero"}])
    assert "producto_del_envio" not in rs  # un numero solo no es un producto


def test_compra_si_sale(entorno):
    ag, rs = _normal([{"n": 1, "cita": "tienen 50 off, no?", "accion": "politica", "tema": "promociones"},
                      {"n": 2, "cita": "si el K120 negro sale menos de 10 mil llevo dos", "accion": "comprar",
                       "si": {"de": 1, "da": "si"}, "agrega": [{"producto": "K120", "color": "negro", "cantidad": 2}]}])
    prod = next(p for p in ag["preguntas"] if p["accion"] == "producto")
    compra = next(p for p in ag["preguntas"] if p["accion"] == "comprar")
    assert prod["producto"] == "K120" and compra["si"] == {"de": prod["n"], "da": "si"} and "compra_si_sale" in rs


def test_cuenta_de_lo_nombrado_con_cantidad_afirmada(entorno):
    ag, rs = _normal([{"n": 1, "cita": "dos g305 negros", "accion": "producto", "producto": "G305", "color": "negro",
                       "afirma": "cantidad 2"},
                      {"n": 2, "cita": "cuanto es", "accion": "cuenta"}])
    compra = next(p for p in ag["preguntas"] if p["accion"] == "comprar")
    assert compra["agrega"][0]["cantidad"] == 2 and "cuenta_de_lo_nombrado" in rs
