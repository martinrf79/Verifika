"""
EL CANDADO DE LO QUE QUEDA A MEDIAS — y del PLAN.

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
gratis en la corrida offline**, sin gastar un token ni una prueba real.

Y LOS DOS CIERRES AUTOMATICOS, que son los que lo hacen distinto de una lista:

  - `strict=True` quiere decir que si alguien ARREGLA la cosa y no saca la
    marca, el test se pone ROJO por pasar. No se puede cerrar en silencio.
  - El TECHO solo puede BAJAR. Una sesion no puede dejar mas cosas pendientes
    de las que encontro, que es exactamente como se acumularon los 70 flags:
    de a una, cada una con su razon del momento.


LA SEGUNDA ETIQUETA: "PLAN:"  (Martin, 21-ago-2026)
---------------------------------------------------

Directiva: **cada paso, hueco y fuga que haya que resolver se escribe como un
test que hoy no pasa, y la actividad de cada etapa es ponerlos en verde.**

Ese trabajo usa el MISMO mecanismo —`xfail(strict=True)`, mismo cierre
automatico, mismo CI verde— pero **no puede compartir el contador**, porque
responde otra pregunta:

    A MEDIAS:  algo que se EMPEZO y no se termino.
    PLAN:      algo que TODAVIA NO SE EMPEZO.

Si el plan entrara como "A MEDIAS", el numero que Martin mira para saber si
quedo algo sin terminar pasaria a incluir trabajo que ni siquiera arranco, y
dejaria de significar lo que significa. Dos preguntas, dos numeros. **Ninguna
pieza nueva:** las dos etiquetas se leen del mismo `xfail` y las dos exigen
`strict=True`.

Los dos numeros salen gratis al final de la bateria offline:

    A MEDIAS  -> cuantas actividades quedaron sin cerrar. Tiene que ser CERO.
    PLAN      -> cuanto falta del recorte. Baja a medida que se hace.
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
TECHO_PLAN = TESTS / "plan_techo.json"

_PREFIJOS = ("A MEDIAS:", "PLAN:")

# `@pytest.mark.xfail(...)` con todo lo que le sigue hasta el parentesis que
# cierra, para poder leerle el motivo aunque este partido en varias lineas.
_RE_XFAIL = re.compile(r"@pytest\.mark\.xfail\((.*?)\)\s*\n\s*def\s+(\w+)",
                       re.DOTALL)


def _marcadas() -> list:
    """(archivo, test, motivo) de cada cosa declarada pendiente."""
    fuera = []
    for f in sorted(TESTS.glob("test_*.py")):
        if f.name == Path(__file__).name:
            continue
        for cuerpo, nombre in _RE_XFAIL.findall(f.read_text(encoding="utf-8")):
            motivo = " ".join(re.findall(r'"([^"]*)"', cuerpo)) or cuerpo
            fuera.append((f.name, nombre, " ".join(motivo.split())))
    return fuera


def _de(prefijo: str) -> list:
    return [x for x in _marcadas() if x[2].strip().startswith(prefijo)]


def _leer_techo(ruta: Path, clave: str) -> int:
    try:
        return int(json.loads(ruta.read_text(encoding="utf-8"))[clave])
    except (OSError, ValueError, KeyError):
        return 0


def test_toda_marca_dice_que_le_falta():
    """Un `xfail` sin motivo claro es un test roto disfrazado de pendiente, y
    la sesion siguiente no puede saber cual de las dos cosas es."""
    mudas = [(a, t) for a, t, m in _marcadas()
             if not m.strip().startswith(_PREFIJOS)]
    assert not mudas, (
        "estos tests estan marcados como esperados-a-fallar y no declaran que "
        f"les falta: {mudas}. El motivo tiene que empezar con 'A MEDIAS:' "
        "(se empezo y no se termino) o con 'PLAN:' (todavia no se empezo), y "
        "decir que hace falta para cerrarlo.")


def test_toda_marca_es_estricta():
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
    """EL TECHO DE LO EMPEZADO Y NO TERMINADO, y solo puede BAJAR.

    Este es el numero que le importa a Martin: cuantas actividades se
    anunciaron y quedaron sin cerrar. **Tiene que llegar a cero.**"""
    hoy = _de("A MEDIAS:")
    techo = _leer_techo(TECHO, "a_medias")
    assert len(hoy) <= techo, (
        f"quedaron {len(hoy)} cosas a medias y el techo es {techo}:\n  "
        + "\n  ".join(f"{a}::{t} — {m}" for a, t, m in hoy)
        + "\n\nO se cierran, o se baja el techo a mano explicando por que en "
          "el commit. Marcar es para lo que necesita una decision, no para lo "
          "que no se termino.")


def test_el_plan_no_crece_solo():
    """EL TECHO DEL PLAN, y tambien solo puede BAJAR.

    Que el plan sea un contador y no una lista de deseos depende de esto: se
    pueden CERRAR pasos, y sumar uno nuevo obliga a subir el techo a mano y a
    explicar en el commit por que aparecio un paso que no estaba. Sin el, el
    plan crece de a un test por sesion y nunca termina, que es la version en
    tests del mismo problema que tuvieron los 70 flags."""
    hoy = _de("PLAN:")
    techo = _leer_techo(TECHO_PLAN, "plan")
    assert len(hoy) <= techo, (
        f"el plan tiene {len(hoy)} pasos abiertos y el techo es {techo}:\n  "
        + "\n  ".join(f"{a}::{t}" for a, t, _ in hoy)
        + "\n\nSumar un paso al plan no es gratis: se sube el techo a mano y "
          "el commit dice por que apareció.")


def test_cada_paso_del_plan_dice_el_numero_de_hoy_y_el_objetivo():
    """Un paso del plan sin numeros es una intencion, no un paso.

    La diferencia entre \"hay que simplificar la salida\" y \"la salida tiene
    18 nodos y tiene que tener 4\" es que la segunda se puede verificar, se
    puede discutir, y se sabe cuando esta hecha. El motivo de cada `PLAN:`
    tiene que traer los dos numeros o alguna forma de 'HOY ... OBJETIVO ...'.
    """
    flojos = [(a, t) for a, t, m in _de("PLAN:")
              if "HOY" not in m or "OBJETIVO" not in m]
    assert not flojos, (
        f"estos pasos del plan no dicen de donde salen ni a donde van: "
        f"{flojos}. El motivo lleva 'HOY <lo que mide ahora>' y "
        "'OBJETIVO <lo que tiene que medir>'.")
