"""
EL CANDADO QUE FALTABA: UN ENLATADO NO ENTRA A UN CASETE.

EL DIA QUE LO PAGO (25-ago-2026). La cuota gratis se agoto a mitad de tanda y
`grabar_casetes.py` siguio grabando como si nada. Los 429 no viajan como
excepcion: `hub_venta` los atrapa, marca `sin_modelo` y devuelve el enlatado de
sobrecarga, asi que cada turno "salio bien" y el casete se guardo. 22 de 23
turnos quedaron con "estoy con mucha demanda" adentro y hubo que restaurar a
mano con git.

POR QUE ES GRAVE Y NO UNA MOLESTIA. El casete ES el corpus contra el que se
miden la vara de venta, el censo de la oferta, el piso de los casetes y el tope
de largo. Un turno enlatado no dice "falto el modelo": dice "el bot contesto
esto", y los cinco numeros bajan sin que nadie haya tocado el bot.

LO QUE SE AFIRMA ACA, y cuantos casos: seis del detector, y dos de la puerta
—que el casete viejo sobrevive al corte, y que la tanda no sigue con las que
faltan—.
"""
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas.grabar_casetes import (  # noqa: E402
    SinModelo, _enlatado_de_sobrecarga, _sin_modelo)


def _enlatado() -> str:
    return _enlatado_de_sobrecarga()


# ── el detector ──────────────────────────────────────────────────────────────

def test_el_enlatado_sale_de_la_fuente_no_de_una_copia():
    """Si un dia la frase cambia, cambia en `base_conocimiento.json` y el
    candado la sigue cazando. Un candado con su propia copia deja de cazar
    justo el dia que alguien toca lo que el cliente lee."""
    from app.core.guia_venta_prosa import mensaje
    assert _enlatado() == mensaje("sobrecarga", "")
    assert "demanda" in _enlatado()


CASOS_SIN_MODELO = [
    ("vacio", "", True),
    ("solo espacios", "   \n  ", True),
    ("el enlatado entero", None, True),
    ("el enlatado detras del saludo", None, True),
    ("una respuesta real", "El Logitech G203 sale $25.900 y tiene 12 meses de "
                           "garantia. ¿Te lo cargo al pedido?", False),
    # ESTE ES EL QUE NO SE CAZA, Y ES A PROPOSITO: sale cuando el modelo SI
    # contesto y no trajo nada. Es una respuesta real del bot y tiene que poder
    # vivir en un casete; cazarla haria imposible grabar las charlas que la
    # ejercitan.
    ("el fallback de catalogo", "No tengo esa información confirmada en el "
                                "catálogo. Dejame consultar y te confirmo en "
                                "breve.", False),
]


@pytest.mark.parametrize("nombre,texto,espera", CASOS_SIN_MODELO)
def test_el_detector_separa_el_turno_sin_modelo(nombre, texto, espera):
    if texto is None:
        texto = (_enlatado() if nombre == "el enlatado entero"
                 else "¡Hola! Soy el asistente automático.\n" + _enlatado())
    assert _sin_modelo(texto) is espera, nombre


def test_el_detector_corrio_los_seis_casos():
    """Un test que no dice cuantos casos corrio puede pasar por vacio."""
    assert len(CASOS_SIN_MODELO) == 6


# ── la puerta ────────────────────────────────────────────────────────────────

def test_el_casete_viejo_sobrevive_al_corte(tmp_path, monkeypatch):
    """LO QUE DE VERDAD IMPORTA: el corte va ANTES de `casete.guardar()`, asi
    que salir por la excepcion deja el casete que ya estaba en el disco. Es la
    diferencia entre parar y tener que restaurar a mano con git."""
    import asyncio

    from banco_pruebas import grabar_casetes as g

    guion = tmp_path / "99_falso.txt"
    guion.write_text("CLIENTE: hola\nCLIENTE: y el precio?\n", encoding="utf-8")

    casete_viejo = g.CASETES / "99_falso.json"
    casete_viejo.write_text('{"turnos": [{"mensaje": "LO QUE YA ESTABA"}]}',
                            encoding="utf-8")

    async def _turno_enlatado(user, mensaje):
        return [_enlatado()]

    from banco_pruebas import clon_produccion as clon
    monkeypatch.setattr(clon, "turno", _turno_enlatado)
    monkeypatch.setattr(clon, "reiniciar_cliente", lambda u: None)

    try:
        with pytest.raises(SinModelo) as e:
            asyncio.run(g._grabar_una(guion, 0))
        assert "turno 1 de 2" in str(e.value)
        assert "LO QUE YA ESTABA" in casete_viejo.read_text(encoding="utf-8")
    finally:
        casete_viejo.unlink(missing_ok=True)


def test_la_tanda_no_sigue_con_las_que_faltan(tmp_path, monkeypatch, capsys):
    """Si la cuota se agoto, las que siguen salen igual de enlatadas: seguir es
    gastar el resto del dia en llenar el corpus de basura."""
    import asyncio

    from banco_pruebas import grabar_casetes as g

    intentadas: list = []

    async def _explota(path, pausa_s):
        intentadas.append(path.stem)
        raise SinModelo(f"{path.stem} turno 1 de 1: el turno salio sin modelo.")

    monkeypatch.setattr(g, "_grabar_una", _explota)
    monkeypatch.setattr(g, "GUIONES", tmp_path)
    for n in ("a_uno", "b_dos", "c_tres"):
        (tmp_path / f"{n}.txt").write_text("CLIENTE: hola\n", encoding="utf-8")

    from banco_pruebas import clon_produccion as clon
    monkeypatch.setattr(clon, "instalar", lambda: {})

    codigo = asyncio.run(g._main(["a_uno.txt", "b_dos.txt", "c_tres.txt"]))
    salida = capsys.readouterr().out

    assert codigo == 3, "la tanda cortada no puede devolver 0"
    assert intentadas == ["a_uno"], "siguio grabando despues del corte"
    assert "TANDA CORTADA" in salida
    assert "se grabaron 0 de 3" in salida
    assert "b_dos" in salida and "c_tres" in salida
    assert "el piso NO se toco" in salida
