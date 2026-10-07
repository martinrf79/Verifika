"""LOS EJEMPLOS RESUELTOS DEL INTERPRETE — cada uno valido, y los elige el parecido (FICHA 67, 7-oct-2026).

Un ejemplo es un pedido que el modelo copia. Si un ejemplo nombra un rubro, un
campo o un tema que la tienda no tiene, o un id que no existe, el modelo lo
copia mal en todos los mensajes parecidos. Por eso cada uno pasa por la misma
atadura que la salida del modelo, sin errores y sin correcciones.
"""
import csv
import json
import re

import pytest

from app.core import ejemplos as E
from app.core import tablero as T

TIENDA = "verifika_prod"
CATALOGO = {p["id"]: p["nombre"] for p in csv.DictReader(
    open("data/clientes/verifika_prod/productos.csv", encoding="utf-8"))}


@pytest.fixture(autouse=True)
def _doble(firestore_doble):
    from app.core.contexto_turno import set_current_tienda
    from app.core.filtros_catalogo import limpiar_cache
    set_current_tienda(TIENDA)
    limpiar_cache()
    return firestore_doble


def test_cada_ejemplo_pasa_la_atadura_sin_tocarlo():
    malos = []
    for e in E.EJEMPLOS:
        piezas, errores, corregidos = T.atar(json.loads(json.dumps(e["piezas"])), TIENDA)
        if errores or corregidos or len(piezas) != len(e["piezas"]):
            malos.append((e["id"], errores, corregidos))
    assert not malos, malos
    assert len(E.EJEMPLOS) >= 75, f"{len(E.EJEMPLOS)} ejemplos: la lista solo crece"


def test_cada_id_existe_y_va_con_su_nombre():
    malos = []
    for e in E.EJEMPLOS:
        texto = e["memoria"] + json.dumps(e["piezas"], ensure_ascii=False)
        for i in set(re.findall(r"\b[A-Z]{3}\d{4}\b", texto)):
            if i not in CATALOGO:
                malos.append((e["id"], i, "no existe"))
            elif re.search(i + r"[: ]", texto) and CATALOGO[i] not in texto:
                malos.append((e["id"], i, "otro nombre"))
    assert not malos, malos


def test_ids_unicos():
    ids = [e["id"] for e in E.EJEMPLOS]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("mensaje, esperado", [
    ("si el K380 anda con mi Mac me lo llevo", "C29"),
    ("cuanto sale el envio a Salta y cuanto demora?", "C10"),
    ("quiero cuatro K120, tres a Rosario y uno a Parana", "C26b"),
    ("de esos dame el mas barato", "C27b"),
    ("que es lo mas caro que venden?", "N61"),
])
def test_el_parecido_trae_el_ejemplo_de_la_misma_clase(mensaje, esperado):
    assert esperado in [e["id"] for e in E.elegir(mensaje)]


def test_el_bloque_tiene_tope_y_va_al_prompt_del_interprete():
    b = E.bloque("me llevo dos G305 negros a Rosario y un K120 a Salta, pago 70 transferencia y 30 Mercado Pago")
    assert 1 <= b.count("CLIENTE: ") <= 8
    assert T.con_ejemplos("SISTEMA", "tenes el G305?").startswith("SISTEMA\n\nEJEMPLOS RESUELTOS")
    assert T.con_ejemplos("SISTEMA", "") == "SISTEMA"
