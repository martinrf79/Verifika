"""EL ORDEN QUE PIDIO EL CLIENTE — vara de `resolver_orden`, estacion T5.1.

Corre `banco_pruebas/barrido_orden.py`, que es offline y gratis: doble local de
Firestore con el catalogo real, cero llamadas al modelo. El barrido dice sobre
CUANTAS frases paso, no solo que paso, y el piso vive en
`banco_pruebas/orden_piso.json` para que una regresion se vea sola.

Por que existe: el 11-sep-2026 la sonda mostro que para "armame un presupuesto
acorde a la crisis" la interpretacion salio BIEN y la traduccion a la busqueda
salio al reves -`precio_ars max`-, y el bot ofrecio el teclado de $512.500
cuando el mas barato sale $12.000. El detalle numerado esta en D16 del
`arquitectura/MAPA_CABLEADO.md`.
"""

import json
import os

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PISO = os.path.join(RAIZ, "banco_pruebas", "orden_piso.json")


@pytest.fixture(scope="module")
def barrido():
    from banco_pruebas import barrido_orden
    return barrido_orden.corrida()


def _piso() -> dict:
    with open(PISO, encoding="utf-8") as fh:
        return json.load(fh)


def test_el_orden_no_empeora(barrido):
    """El piso solo sube. Si baja, algo que andaba dejo de andar."""
    piso = _piso()
    filas = barrido["duros"]
    verdes = [f["frase"] for f in filas if f["estado"] == "ok"]
    rojas = [f"{f['frase']} -> {f['salio']}" for f in filas if f["estado"] != "ok"]
    assert len(verdes) >= piso["duro_verdes"], (
        f"el bloque duro bajo de {piso['duro_verdes']} a {len(verdes)} "
        f"sobre {len(filas)}. En rojo ahora: {rojas}")


def test_ninguna_frase_se_borro(barrido):
    """Bajar el denominador es la forma silenciosa de aflojar la vara."""
    piso = _piso()
    assert len(barrido["duros"]) >= piso["duro_total"], (
        f"el barrido mide {len(barrido['duros'])} frases y el piso pide "
        f"{piso['duro_total']}. Una frase del barrido se corrige, no se borra.")


@pytest.mark.xfail(strict=True, reason=(
    "PLAN: la restriccion en prosa se traduce a (campo, direccion) sin "
    "equivocarse. HOY el bloque duro da 54 de 59 y los 5 rojos son la FAMILIA "
    "B de D16: nombrar el rubro le roba el campo al precio. 'el teclado mas "
    "barato' ordena por `switch_teclado`, 'la memoria ram mas barata' y 'la "
    "placa de video mas barata' por `memoria_video`, 'el procesador mas "
    "barato' por `procesador` y 'el almacenamiento externo mas barato' por "
    "`almacenamiento`. Son 5 de las 22 categorias del catalogo vivo. La causa "
    "es que el nombre del campo se busca por raiz compartida contra las "
    "palabras del cliente y gana el primero que pega, sin mirar que la palabra "
    "que pego es el RUBRO y no el eje: es la misma enfermedad que D3 y D4, "
    "aparear por palabras en vez de por un veredicto. OBJETIVO 59 de 59. La "
    "FAMILIA A cerro el 11-sep-2026 y el piso subio de 45 a 54."))
def test_ninguna_restriccion_sale_al_reves(barrido):
    filas = barrido["duros"]
    rojas = [f"{f['frase']} espera {f['espera']} salio {f['salio']}"
             for f in filas if f["estado"] != "ok"]
    assert filas and not rojas, f"{len(rojas)} de {len(filas)}: {rojas}"
