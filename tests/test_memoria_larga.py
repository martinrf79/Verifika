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




# ── Cableado: el resumen viaja al estado y al interprete ─────────────────────
def test_estado_lleva_el_resumen():
    from app.core.estado_venta import construir_estado
    conv = {"summary": "El cliente ya dio su direccion en Rio Tercero."}
    estado = construir_estado(conv, None)
    assert estado["resumen_charla"] == "El cliente ya dio su direccion en Rio Tercero."






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
