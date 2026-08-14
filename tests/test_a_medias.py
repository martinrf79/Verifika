"""
EL CANDADO DE LO QUE QUEDA A MEDIAS.

POR QUE EXISTE (Martin, 14-ago-2026, y es el problema que mas lo frena hoy):
*"se dice que se va a realizar una actividad, se empieza a hacer, y quedan
cosas a medias... no tengo manera de chequear, salvo con pruebas reales"*.

EL DIAGNOSTICO, sin adornos. Lo que quedaba a medias se contaba en PROSA, al
final del parte, y por lo tanto dependia de que quien escribiera el parte se
acordara y quisiera decirlo. Eso no es un mecanismo, es una promesa. Este repo
ya aprendio que la prosa envejece y que el unico documento que no puede mentir
es el que genera y verifica una maquina: paso con los numeros de la fuente,
paso con la lista de barridos, y estaba pasando otra vez un nivel mas arriba.

LA REGLA, y son tres lineas:

  1. Lo que queda a medias se escribe como un TEST que afirma el comportamiento
     que QUEREMOS y hoy no pasa, marcado `xfail(strict=True)`.
  2. El motivo empieza con "A MEDIAS:" y dice QUE falta. No alcanza con
     "pendiente": tiene que poder leerse sin contexto.
  3. NO SE MARCA LO QUE SE PUEDE CERRAR. Marcar es para lo que necesita una
     decision o un trabajo que no entra en la sesion, no para lo que da fiaca.

LO QUE ESTO LE DA A MARTIN, que era lo que faltaba: **un numero que se ve
gratis en la corrida offline**, sin gastar un token ni una prueba real. La
cantidad de `xfailed` al final de la bateria ES la cantidad de cosas a medias.
Si dice 0, no hay ninguna. Si dice 3, hay tres y cada una tiene nombre.

Y LOS DOS CIERRES AUTOMATICOS, que son los que lo hacen distinto de una lista:

  - `strict=True` quiere decir que si alguien ARREGLA la cosa y no saca la
    marca, el test se pone ROJO por pasar. No se puede cerrar en silencio.
  - El TECHO de abajo solo puede BAJAR. Una sesion no puede dejar mas cosas a
    medias de las que encontro, que es exactamente como se acumularon los 70
    flags: de a una, cada una con su razon del momento.
"""
import json
import re
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

TESTS = Path(__file__).resolve().parent
TECHO = TESTS / "a_medias_techo.json"

# `@pytest.mark.xfail(...)` con todo lo que le sigue hasta el parentesis que
# cierra, para poder leerle el motivo aunque este partido en varias lineas.
_RE_XFAIL = re.compile(r"@pytest\.mark\.xfail\((.*?)\)\s*\n\s*def\s+(\w+)",
                       re.DOTALL)


def _marcadas() -> list:
    """(archivo, test, motivo) de cada cosa declarada a medias."""
    fuera = []
    for f in sorted(TESTS.glob("test_*.py")):
        if f.name == Path(__file__).name:
            continue
        for cuerpo, nombre in _RE_XFAIL.findall(f.read_text(encoding="utf-8")):
            motivo = " ".join(re.findall(r'"([^"]*)"', cuerpo)) or cuerpo
            fuera.append((f.name, nombre, " ".join(motivo.split())))
    return fuera


def _techo() -> int:
    try:
        return int(json.loads(TECHO.read_text(encoding="utf-8"))["a_medias"])
    except (OSError, ValueError, KeyError):
        return 0


def test_toda_cosa_a_medias_dice_que_le_falta():
    """Un `xfail` sin motivo claro es un test roto disfrazado de pendiente, y
    la sesion siguiente no puede saber cual de las dos cosas es."""
    mudas = [(a, t) for a, t, m in _marcadas()
             if not m.strip().startswith("A MEDIAS:")]
    assert not mudas, (
        "estos tests estan marcados como esperados-a-fallar y no declaran que "
        f"les falta: {mudas}. El motivo tiene que empezar con 'A MEDIAS:' y "
        "decir que hace falta para cerrarlo.")


def test_toda_cosa_a_medias_es_estricta():
    """Sin `strict=True` la marca no se entera de que la arreglaron: el test
    pasa, sigue contando como pendiente, y queda ahi para siempre. Es el
    mecanismo de CIERRE, no un detalle de estilo."""
    flojas = []
    for f in sorted(TESTS.glob("test_*.py")):
        if f.name == Path(__file__).name:
            continue
        for cuerpo, nombre in _RE_XFAIL.findall(f.read_text(encoding="utf-8")):
            if "strict=True" not in cuerpo:
                flojas.append((f.name, nombre))
    assert not flojas, (
        f"estas marcas no son estrictas: {flojas}. Sin strict, el dia que se "
        "arreglen nadie se entera y la marca queda para siempre.")


def test_no_se_dejan_mas_cosas_a_medias_de_las_que_habia():
    """EL TECHO, y solo puede BAJAR. Es la misma mecanica del techo del peso
    del turno. Una sesion puede CERRAR cosas a medias; dejar mas de las que
    encontro es como se acumularon los 70 flags, de a una y con su razon."""
    hoy = _marcadas()
    techo = _techo()
    assert len(hoy) <= techo, (
        f"quedaron {len(hoy)} cosas a medias y el techo es {techo}:\n  "
        + "\n  ".join(f"{a}::{t} — {m}" for a, t, m in hoy)
        + "\n\nO se cierran, o se baja el techo a mano explicando por que en "
          "el commit. Marcar es para lo que necesita una decision, no para lo "
          "que no se termino.")
