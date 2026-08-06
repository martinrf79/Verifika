"""
EL TURNO COMPLETO, GRATIS Y EN CADA PUSH — el test que faltaba.

QUE ES. Cada casete de `banco_pruebas/casetes/` tiene lo que el modelo contesto
en una charla real, grabado una vez. Aca esa charla se vuelve a correr ENTERA
por el camino vivo -`app.main._process_and_reply_whatsapp`, el mismo que atiende
el webhook de WhatsApp- con el modelo reemplazado por su grabacion. Corre el
hub, el bucle de rondas, el reconciliador, las once guardas de salida, la
memoria y el corte en partes. Sin red, sin clave y sin costo.

POR QUE FALTABA Y POR QUE DUELE. La maquina de casetes existe desde el 29-jul y
`casete.py` apunta bien al hub vivo, pero ESTE archivo no existia: el CI lo
llamaba con `|| true` y imprimia "sin casetes grabados", en verde, hace cinco
dias. Medido el 5-ago con `banco_pruebas/mapa.py`: 26 de las 38 funciones del
hub -incluidas las ONCE guardas que deciden lo que el cliente lee- no las tocaba
ninguna prueba. Esta es la que las toca.

LAS DOS VARAS, y son distintas a proposito:

  1. INVARIANTES DUROS, por turno. Lo que el CODIGO garantiza pase lo que pase:
     que no se invente plata, que no salga el enlatado de disculpa, que la
     respuesta no venga vacia. Un rojo aca es un bug, no una opinion.
  2. EL NUMERO, contra `casetes/_piso.json`. Todo lo demas -que conteste lo que
     el guion pide, que sirva, que no repita bloques- puntua de 0 a 100 y se
     compara con el piso. **No baja.** Lo que hoy el codigo no previene queda
     ADENTRO del piso, medido y a la vista, en vez de dejar el CI rojo para
     siempre: exactamente lo mismo que hace el candado del mapa.

REGRABAR: `python3 banco_pruebas/grabar_casetes.py` con la clave, cuando cambia
el CONTRATO con el modelo -el esquema de las herramientas, los enums-. Ajustar
una frase de un prompt NO obliga a regrabar: el casete se indexa por turno y
etapa, no por el texto del prompt.
"""
import json
import sys
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas.casete import CASETES, reproducir_charla  # noqa: E402
from banco_pruebas.puntaje import puntaje_global  # noqa: E402

PISO = CASETES / "_piso.json"


def _casetes() -> list:
    return sorted(p for p in CASETES.glob("*.json") if not p.name.startswith("_"))


def _correr(path: Path) -> dict:
    """Reproduce una charla entera por el camino vivo y devuelve su puntaje.
    La definicion vive en `casete.reproducir_charla`, y la comparte con el
    grabador: si cada uno midiera a su manera, el piso y el gate compararian
    cosas distintas."""
    return reproducir_charla(path)


@pytest.mark.skipif(not _casetes(), reason="no hay casetes grabados")
@pytest.mark.parametrize("path", _casetes(), ids=lambda p: p.stem)
def test_la_charla_no_miente_ni_se_cae(path, firestore_doble):
    """VARA 1, la dura: lo que el codigo garantiza en cada turno. Plata sin
    respaldo, el enlatado de disculpa y la respuesta vacia son bugs, no
    opiniones, y ninguno depende de que el modelo tenga un buen dia."""
    from banco_pruebas import clon_produccion as clon

    res = _correr(path)
    for i, texto in enumerate(res["respuestas"], 1):
        assert texto.strip(), f"turno {i}: el cliente no recibio NADA"
        assert not clon.es_fallback(texto), (
            f"turno {i}: salio el enlatado de produccion, o sea que el turno "
            f"exploto:\n{texto[:200]}")
    # La plata sin respaldo la marca el juez turno por turno, con el prefijo T{i}
    miente = [f for f in res["fallas"]
              if "plata" in f.lower() or "invent" in f.lower()]
    assert not miente, f"{path.stem}: {miente}"


@pytest.mark.skipif(not _casetes() or not PISO.exists(),
                    reason="no hay casetes o piso grabado")
def test_la_latencia_no_crece(firestore_doble):
    """LA LATENCIA, COMO NUMERO. Cada llamada al modelo son entre 3 y 8 segundos
    en produccion: medido por WhatsApp el 5-ago, 26,6 segundos de espera con
    cuatro llamadas, una de ellas una ronda entera que pidio CERO herramientas.

    Contar las llamadas es la unica forma honesta de medir latencia sin red: el
    reloj de un runner no dice nada, la cantidad de idas y vueltas si. El piso
    guarda el maximo de hoy y no lo deja crecer. Cuando el codigo arme la cuenta
    solo -la opcion C- este numero tiene que BAJAR, y el piso se refija."""
    piso = json.loads(PISO.read_text(encoding="utf-8"))
    tope = piso.get("llamadas_max")
    if not tope:
        pytest.skip("el piso no tiene el maximo de llamadas: regraba")
    peores = []
    for p in _casetes():
        res = _correr(p)
        for i, n in enumerate(res.get("llamadas_por_turno") or [], 1):
            if n > tope:
                peores.append(f"{res['nombre']} turno {i}: {n} llamadas")
    assert not peores, (
        f"EL TURNO PIDE MAS VUELTAS QUE ANTES (tope {tope}): "
        + "; ".join(peores))


@pytest.mark.skipif(not _casetes() or not PISO.exists(),
                    reason="no hay casetes o piso grabado")
def test_el_numero_no_baja(firestore_doble):
    """VARA 2, el numero. Manda `puntos`, el crudo: `piso` esta redondeado y una
    regresion de un par de turnos podia seguir redondeando igual y colarse."""
    piso = json.loads(PISO.read_text(encoding="utf-8"))
    resultados = [_correr(p) for p in _casetes()]
    puntos = sum(r["puntos"] for r in resultados)
    total = sum(r["total"] for r in resultados)
    numero = puntaje_global(resultados)

    fallas = [f"{r['nombre']}: {f}" for r in resultados
              for f in (r.get("fallas") or [])][:12]
    print(f"\nEL NUMERO: {numero}/100 ({puntos} de {total} puntos, "
          f"{len(resultados)} charlas)")
    for f in fallas:
        print(f"  ! {f}")

    assert puntos >= piso["puntos"], (
        f"EL NUMERO BAJO: {puntos} puntos contra un piso de {piso['puntos']}.\n"
        + "\n".join(f"  ! {f}" for f in fallas))
