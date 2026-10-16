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



# ── EN EL CAMINO VIVO EL MEDIO ES TEXTO DEL CLIENTE (16-oct) ────────────────
# El esquema del tablero no cierra el medio, y el motor solo rechaza el valor
# `medio_no_disponible`, que el esquema vivo ya no ofrece. Cerrarlo contra la
# FAQ de formas de pago se probo el 16-oct y rompio K21 grabada: ante "setenta
# treinta" el interprete pone "setenta" como medio y `tablero._reparto` lo deja
# porque el cliente lo dijo. Primero hay que sacar eso de `_reparto`.

@pytest.mark.xfail(strict=True, reason="PLAN: el motor rechaza el medio que la FAQ de formas de pago no nombra; "
                                       "antes, tablero._reparto tiene que dejar de tomar 'setenta' como medio")
def test_un_medio_que_la_tienda_no_toma_no_entra_al_total_en_el_camino_vivo(firestore_doble):
    r = MT.buscar([], TIENDA, "t", cuenta={"items": UN_ITEM},
                  reparto_pago=[{"medio": "cripto", "porcentaje": 50},
                                {"medio": "transferencia", "porcentaje": 50}])
    assert (r.get("cuenta") or {}).get("medio_no_disponible"), "'cripto' entro al total sin avisar que no se toma"
