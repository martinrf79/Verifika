"""
AREA: Memoria larga — el resumen acumulativo de la charla que salio del
historial vivo (C2-C4). Cubre app/core/memoria_larga.py y su cableado: el
resumen entra al estado (bloque del solver) y al contexto del interprete.
"""
import asyncio

from app.core.memoria_larga import (_compactar_determinista, actualizar_resumen,
                                    _MAX_CHARS)


def test_compactar_determinista_agrega_lineas_crudas():
    out = _compactar_determinista("Cliente busca mouse gamer.", [
        {"role": "user", "content": "quiero el DX-110 negro"},
        {"role": "assistant", "content": "Perfecto, lo anoto."},
    ])
    assert "Cliente busca mouse gamer." in out
    assert "Cliente: quiero el DX-110 negro" in out
    assert "Bot: Perfecto, lo anoto." in out


def test_compactar_respeta_el_tope_conservando_la_cola():
    viejos = [{"role": "user", "content": f"mensaje numero {i} " + "x" * 150}
              for i in range(30)]
    out = _compactar_determinista("", viejos)
    assert len(out) <= _MAX_CHARS
    assert "mensaje numero 29" in out  # lo mas reciente sobrevive


def test_actualizar_sin_descartados_devuelve_el_previo():
    r = asyncio.run(actualizar_resumen("resumen previo", []))
    assert r == "resumen previo"


def test_fallo_del_llm_cae_a_la_red_determinista(monkeypatch):
    # Sin proveedor real: el cliente explota y el resumen sale igual (red).
    import app.core.agent as agent
    def _boom():
        raise RuntimeError("sin LLM en offline")
    monkeypatch.setattr(agent, "_get_client", _boom)
    r = asyncio.run(actualizar_resumen("ya hablado", [
        {"role": "user", "content": "mi direccion es Falsa 123, Cordoba"}]))
    assert "ya hablado" in r
    assert "Falsa 123" in r


# ── Cableado: el resumen viaja al solver y al interprete ─────────────────────
def test_estado_lleva_el_resumen_y_el_bloque_lo_muestra():
    from app.core.estado_venta import construir_estado, bloque_para_solver
    conv = {"summary": "El cliente ya dio su direccion en Rio Tercero."}
    estado = construir_estado(conv, None)
    assert estado["resumen_charla"] == "El cliente ya dio su direccion en Rio Tercero."
    bloque = bloque_para_solver(estado)
    assert "Rio Tercero" in bloque
    assert "memoria" in bloque.lower()


def test_contexto_del_interprete_incluye_el_resumen():
    from app.core.interpretador import construir_contexto_conversacional
    ctx = construir_contexto_conversacional(
        [{"role": "user", "content": "hola"}],
        resumen="Cliente eligio el DX-110 y rechazo el blanco.")
    assert "LO HABLADO ANTES" in ctx
    assert "rechazo el blanco" in ctx


def test_sin_historial_pero_con_resumen_no_dice_sin_historial():
    from app.core.interpretador import construir_contexto_conversacional
    ctx = construir_contexto_conversacional([], resumen="Charla previa: mouse.")
    assert "Sin historial previo" not in ctx
    assert "Charla previa: mouse." in ctx


# ── Vacuna del bug real 8-jul: el doble valida tipos como Firestore real ─────
def test_doble_rechaza_arrays_anidados_como_firestore(firestore_doble):
    # Una lista de listas rompia el save REAL con 400 'Nested arrays are not
    # allowed' y el bot quedaba amnesico. El doble ahora explota igual.
    import pytest
    from app.storage.firestore_client import save_conversation
    with pytest.raises(ValueError, match="Nested arrays"):
        save_conversation("u1", [], tienda_id="verifika_prod",
                          pedido_categorias_pendiente=[[4, "notebook"]])


def test_pendiente_de_categorias_persiste_como_dicts(firestore_doble):
    # El formato bueno (lista de dicts) pasa la validacion del doble.
    from app.storage.firestore_client import (save_conversation,
                                              get_conversation)
    save_conversation("u2", [], tienda_id="verifika_prod",
                      pedido_categorias_pendiente=[
                          {"cantidad": 4, "categoria": "notebook"},
                          {"cantidad": 5, "categoria": "mouse"}])
    conv = get_conversation("u2", tienda_id="verifika_prod")
    assert conv["pedido_categorias_pendiente"][0]["cantidad"] == 4
