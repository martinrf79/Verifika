"""LOS INVARIANTES DE PRODUCCION CON UN PRESUPUESTO POR DESTINO (1-oct-2026).

`produccion.py` revisa cada mensaje real con `banco_pruebas/invariantes.py`.
Desde que el bot manda un presupuesto por destino y un total general, tres
totales en un mensaje no son una contradiccion: son tres bloques. Lo que
sigue siendo falla es una cuenta que no cierra adentro de su bloque, un
reparto que no suma, o el mismo bloque calcado dos veces.
"""
from banco_pruebas import invariantes as I

TRES = """Cordoba:
- 1x Auriculares A: $100.000 c/u = $100.000
Subtotal: $100.000
Envio: $7.500
Total: $107.500
Posadas:
- 1x Memoria B: $30.000 c/u = $30.000
Subtotal: $30.000
Envio: $10.000
Total: $40.000

Total general de los 2 presupuestos: $147.500

Pago dividido:
- parte 1 (70%): $103.250
- parte 2 (30%): $44.250
Total final: $147.500"""


def test_un_presupuesto_por_destino_no_es_una_contradiccion():
    assert len(I.presupuestos(TRES)) == 2
    assert I.revisar(TRES) == []


def test_el_reparto_del_total_general_que_no_suma_sigue_siendo_falla():
    fallas = I.revisar(TRES.replace("$44.250", "$44.000"))
    assert [f["regla"] for f in fallas] == ["el_pago_dividido_no_suma_el_total"]


def test_el_mismo_bloque_calcado_sigue_siendo_falla():
    uno = "- 1x A: $1.000 c/u = $1.000\nSubtotal: $1.000\nTotal: $1.000"
    assert "la_cuenta_dos_veces" in [f["regla"] for f in I.revisar(uno + "\n" + uno)]


def test_el_banco_frena_una_tanda_paga_que_pasa_el_tope():
    from banco_pruebas import sonda_charlas as S
    cola = S.charlas("compleja")
    assert not S.frenar_por_costo(cola, "gemini-3.1-flash-lite (paga)", 0.01)
    assert S.frenar_por_costo(cola, "gemini-3.1-flash-lite", 0.01)  # la gratis no frena
