"""
EL CANDADO DE LA PUERTA DETERMINISTA.

Lo que mide y por que, en `banco_pruebas/puerta_determinista.py`. Aca vive la
vara, y es un PISO, no un techo: estos numeros estan para SUBIR. Lo que el
candado impide es que bajen sin que nadie se entere, que es como se perdio mas
de una mejora en este repo.

Es la misma mecanica del piso de los casetes y del techo del peso del turno. Se
sube con `python3 banco_pruebas/puerta_determinista.py --fijar` despues de
mejorar de verdad, y ese commit deja escrito que la mejora existio.
"""
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import puerta_determinista as PD  # noqa: E402


def test_la_verdad_de_referencia_no_se_achica(firestore_doble):
    """El corpus son los turnos REALES grabados, con el `registrar_pedido` que
    el modelo emitio al lado. Si alguien borra casetes, la medicion se vuelve
    mas facil sin que el sistema haya mejorado."""
    casos = PD.verdad()
    esperado = PD.piso().get("_turnos", 0)
    assert len(casos) >= esperado, (
        f"el corpus bajo de {esperado} a {len(casos)} turnos: se borraron "
        f"casetes o dejaron de traer su registrar_pedido")


def test_lo_que_el_codigo_entiende_sin_modelo_no_puede_bajar(firestore_doble):
    """LA VARA. Cada uno de estos porcentajes es cuanto del mensaje del cliente
    reconstruye el codigo SOLO, sin llamar al modelo. Es el numero que decide
    si el sistema puede contestar con el LLM apagado."""
    r = PD.medir()
    base = PD.piso()
    caidas = []
    for campo, valor in base.items():
        if campo.startswith("_"):
            continue
        hoy = r["campos"][campo]["recall"]
        if hoy < valor - 0.05:
            caidas.append(f"{campo}: {valor}% -> {hoy}%")
    hoy_exactos = r["campos"]["items"]["turnos_exactos_pct"]
    if hoy_exactos < base.get("_items_turnos_exactos_pct", 0) - 0.05:
        caidas.append(f"turnos con el pedido entero bien: "
                      f"{base['_items_turnos_exactos_pct']}% -> {hoy_exactos}%")
    assert not caidas, (
        "la puerta determinista entiende MENOS que antes:\n  "
        + "\n  ".join(caidas))


def test_los_huecos_declarados_siguen_declarados(firestore_doble):
    """Los campos sin pieza determinista estan escritos en `PIEZAS` con `None`.
    Si alguien construye la pieza, tiene que sacarlo de ahi en el mismo push:
    un hueco que ya no existe y sigue declarado manda a la sesion siguiente a
    construir algo que ya esta."""
    r = PD.medir()
    for campo, pieza in PD.PIEZAS.items():
        if pieza is None:
            assert r["campos"][campo]["recall"] == 0.0, (
                f"{campo} declara que no tiene pieza determinista y sin "
                f"embargo el banco reconstruye algo: actualiza PIEZAS")
