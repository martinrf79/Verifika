"""EL MEDIO DE PAGO SE CIERRA — era el ultimo campo que afirmaba algo de la
tienda sin verificarse.

EL CENSO DEL 21-sep. Se listaron los 22 campos que el modelo puede escribir y
se probo cada uno con un valor inventado. Cuatro de cinco huecos ya avisaban:
un valor que la fuente no usa, un valor sobre un campo de alta variedad, un id
que no existe y un equipo que el vocabulario no conoce. **El unico que no
avisaba era el medio de pago.**

Y SALIA PEOR QUE MUDO. La regla de `pago_split` es que todo lo que NO es
Mercado Pago cuenta como transferencia y lleva el descuento, asi que con
`medio: "criptomonedas"` el bot cotizaba un 10% menos por un medio que la
tienda no acepta. Eso es plata mal, que es el objetivo 1 de CLAUDE.md.
"""
import pytest

from app.core import motor as MT

TIENDA = "verifika_prod"
UN_ITEM = [{"id": "TEC0001", "cantidad": 1}]


def _props():
    return (MT.esquema(TIENDA)["function"]["parameters"]["properties"]
            ["reparto_pago"]["items"]["properties"])


def test_el_medio_ya_no_es_texto_libre(firestore_doble):
    enum = _props()["medio"].get("enum")
    assert enum, "el medio volvio a ser texto libre: se puede inventar de nuevo"
    assert set(enum) == {"transferencia", "mercado_pago", "tarjeta",
                         "medio_no_disponible"}


def test_hay_UNA_SALIDA_y_no_un_relleno(firestore_doble):
    """`medio_no_disponible` es el SIN_CAMPO del pago. Sin el, un cliente que
    dice 'mitad en efectivo' obliga al modelo a acomodarlo al mas parecido, y
    acomodar en silencio es exactamente lo que se estaba tapando."""
    assert "medio_no_disponible" in _props()["medio"]["enum"]
    d = _props()["medio"]["description"].lower()
    assert "parecido" in d, "el tablero no dice que NO se acomode"


def test_un_medio_que_no_se_toma_NO_ENTRA_AL_TOTAL(firestore_doble):
    r = MT.buscar([], TIENDA, "t", cuenta={"items": UN_ITEM},
                  reparto_pago=[{"medio": "medio_no_disponible",
                                 "porcentaje": 50},
                                {"medio": "transferencia", "porcentaje": 50}])
    c = r.get("cuenta") or {}
    assert c.get("medio_no_disponible"), (
        "el medio que la tienda no toma paso sin una palabra: es el defecto "
        "medido con 'criptomonedas'")


def test_y_EL_MOTIVO_VIAJA_ESCRITO(firestore_doble):
    """El dato es del codigo y la prosa del modelo: el motivo vuelve redactado
    para que el modelo lo COPIE en vez de inventar como decirlo."""
    r = MT.buscar([], TIENDA, "t", cuenta={"items": UN_ITEM},
                  reparto_pago=[{"medio": "medio_no_disponible",
                                 "porcentaje": 100}])
    m = (r.get("cuenta") or {}).get("medio_no_disponible") or ""
    for palabra in ("transferencia", "mercado pago", "tarjeta"):
        assert palabra in m.lower(), f"el motivo no nombra {palabra}"


def test_un_reparto_NORMAL_sigue_saliendo_igual(firestore_doble):
    """La vieja no se rompe por la nueva."""
    r = MT.buscar([], TIENDA, "t", cuenta={"items": UN_ITEM},
                  reparto_pago=[{"medio": "transferencia", "porcentaje": 70},
                                {"medio": "mercado_pago", "porcentaje": 30}])
    c = r.get("cuenta") or {}
    assert c.get("total_ars"), "un reparto valido dejo de dar total"
    assert not c.get("medio_no_disponible")
