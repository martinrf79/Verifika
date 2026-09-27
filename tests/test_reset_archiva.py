"""EL RESET ARCHIVA, NO BORRA (27-sep-2026).

Martin probo cuatro veces la misma pregunta con `Verifika2026` entre cada una,
y de tres respuestas no quedo nada: el reset borraba el unico lugar donde
vive el texto que recibio el cliente. Ahora la charla se copia a
`conversaciones_archivo` antes de borrarse, y `produccion.py` la lee de ahi.
"""
import importlib.util
from pathlib import Path

# El doble de Firestore de la bateria reemplaza `reset_conversation` en el
# modulo; se carga una copia aparte para probar la funcion de verdad.
_spec = importlib.util.spec_from_file_location(
    "firestore_client_real", Path(__file__).resolve().parents[1] / "app/storage/firestore_client.py")
FC = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FC)


class _Doc:
    def __init__(self, base, col, id_):
        self.base, self.col, self.id = base, col, id_

    def get(self):
        d = self.base.get((self.col, self.id))
        return type("S", (), {"exists": d is not None, "to_dict": lambda s: dict(d or {})})()

    def set(self, datos):
        self.base[(self.col, self.id)] = datos

    def delete(self):
        self.base.pop((self.col, self.id), None)


class _Tienda:
    def __init__(self):
        self.base = {}

    def collection(self, col):
        return type("C", (), {"document": lambda s, i: _Doc(self.base, col, i)})()


def test_el_reset_deja_la_charla_en_el_archivo_y_la_saca_de_las_vivas(monkeypatch):
    t = _Tienda()
    t.base[("conversaciones", "549111")] = {"history": [{"role": "assistant", "content": "hola"}]}
    monkeypatch.setattr(FC, "_tienda_ref", lambda tienda_id=None: t)
    FC.reset_conversation("549111", tienda_id="verifika_prod")
    assert ("conversaciones", "549111") not in t.base
    archivadas = [v for (c, i), v in t.base.items() if c == "conversaciones_archivo" and i.startswith("549111_")]
    assert len(archivadas) == 1 and archivadas[0]["history"][0]["content"] == "hola"
    assert archivadas[0]["usuario"] == "549111"


def test_sin_charla_el_reset_no_archiva_nada(monkeypatch):
    t = _Tienda()
    monkeypatch.setattr(FC, "_tienda_ref", lambda tienda_id=None: t)
    FC.reset_conversation("549222", tienda_id="verifika_prod")
    assert t.base == {}
