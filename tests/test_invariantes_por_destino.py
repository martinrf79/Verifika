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


def test_al_reproducir_se_juzga_el_codigo_sobre_los_hechos():
    """2-oct: las casillas de la vara, sobre lo que el codigo le dio al redactor."""
    from banco_pruebas import sonda_charlas as S
    hechos = [{"tipo": "cuenta", "resultado": {"cuenta": {"detalle": "- 1x Mouse Genius DX-110: $8.500 c/u = $8.500\\n"
                                                                     "Total: $15.500", "id": "MOU0023"}}}]
    txt = S.texto_de_hechos(hechos)
    assert S.nota_codigo({"tipo": "plata", "monto": 15500}, txt, []) is True
    assert S.nota_codigo({"tipo": "articulos", "minimos": {"mouse": 1}}, txt, []) is True
    # la jerga es de la redaccion: sobre los hechos, que traen ids, no aplica
    assert S.nota_codigo({"tipo": "no_patron", "patron": r"[a-z]{3}\\d{4}"}, txt, []) is None
    assert S.nota_codigo({"tipo": "pregunta"}, txt, []) is False
    assert S.nota_codigo({"tipo": "pregunta"}, S.texto_de_hechos([{"pregunta_al_cliente": "x"}]), []) is True


def test_el_libro_de_la_paga_anota_y_frena_en_el_tope_del_dia(tmp_path, monkeypatch):
    """2-oct: un tope por corrida no frena cinco corridas. El del libro es por dia."""
    from types import SimpleNamespace as NS
    import pytest
    from banco_pruebas import libro_paga as L
    monkeypatch.setattr(L, "LIBRO", tmp_path / "libro.jsonl")
    monkeypatch.setattr(L, "TOPE_DIARIO", 0.001)
    uso = NS(prompt_tokens=10000, completion_tokens=1000)
    cli = NS(chat=NS(completions=NS(create=lambda **k: NS(usage=uso))))
    L.envolver(cli).chat.completions.create(model="gemini-3.1-flash-lite")
    assert L.hoy() > 0.001
    with pytest.raises(L.TopeDiario):
        cli.chat.completions.create(model="gemini-3.1-flash-lite")
