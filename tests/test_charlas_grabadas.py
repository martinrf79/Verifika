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
import re
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
    # LOS TURNOS CON HUECO NO SE JUZGAN POR EL TEXTO, y el 11-ago se vio por
    # que. Un hueco es que al casete le FALTA la grabacion del redactor: el
    # modelo nunca hablo en ese turno, asi que lo que salga no lo escribio el
    # bot. Hasta hoy ese turno emitia "No tengo esa informacion confirmada en
    # el catalogo" y pasaba como respuesta buena — o sea que dos de las trece
    # charlas se puntuaban sobre un turno donde el modelo no dijo una palabra.
    # Desde que el codigo distingue "no hubo modelo" de "el modelo no trajo
    # nada", ese turno sale con el enlatado de sobrecarga, que es la respuesta
    # HONESTA y no una explosion. El hueco ya se castiga en el puntaje
    # (`puntuar_charla`), que es donde tiene que doler; lo que hay que hacer es
    # regrabar el casete, no aflojar la regla del enlatado.
    con_hueco = {int(m.group(1)) for h in (res.get("huecos") or [])
                 if (m := re.match(r"turno (\d+)", str(h)))}
    for i, texto in enumerate(res["respuestas"], 1):
        assert texto.strip(), f"turno {i}: el cliente no recibio NADA"
        if i in con_hueco:
            continue
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
def test_el_mensaje_no_se_alarga(firestore_doble):
    """EL LARGO, COMO NUMERO. El turno real del 6-ago salio en 2.977 caracteres
    y tres mensajes de WhatsApp, y la MITAD eran tres bloques calcados que
    escribe nuestro codigo. Con el largo en el piso, un mensaje que crece se ve
    en el CI y no leyendo una charla."""
    piso = json.loads(PISO.read_text(encoding="utf-8"))
    tope = piso.get("largo_max")
    if not tope:
        pytest.skip("el piso no tiene el largo maximo: refijalo")
    largos = [(r["nombre"], i, len(t))
              for p in _casetes() for r in [_correr(p)]
              for i, t in enumerate(r["respuestas"], 1)]
    peores = [f"{n} turno {i}: {x} caracteres" for n, i, x in largos if x > tope]
    assert not peores, (f"EL MENSAJE CRECIO (tope {tope}): " + "; ".join(peores))


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


@pytest.mark.skipif(not _casetes(), reason="no hay casetes grabados")
def test_los_invariantes_valen_en_toda_charla(firestore_doble):
    """VARA 3, LA NUEVA: las propiedades que NINGUNA respuesta correcta viola.

    POR QUE HACIA FALTA UNA TERCERA VARA. Las otras dos comparan contra algo que
    alguien escribio: la vara 1 contra lo que el codigo garantiza, la 2 contra
    el puntaje de un guion. Las dos encuentran el error que alguien ANTICIPO.
    El 10-ago Martin lo dijo con todas las letras -"en cada prueba en real
    aparecen nuevos errores"- y tenia razon, y la causa es esa.

    Esta vara no sabe cual es la respuesta correcta. Afirma que la cuenta cierre,
    que lo cobrado sea lo facturado, que el reparto cubra el pedido, que nada se
    diga dos veces y que no se fugue nada interno. Por eso corre sobre CUALQUIER
    conversacion, incluida una que nadie escribio.

    LA PRUEBA DE QUE SIRVE, medida el mismo dia: corrida sobre las charlas
    REALES de produccion, sin decirle que buscar, encontro el error de plata que
    habia costado una hora de leer logs a mano -cobrarle $225.000 a un cliente
    que debia $131.625- mas seis defectos que nadie habia visto.

    Corre sobre los casetes en cada push, gratis y sin clave: los invariantes
    son aritmetica y texto, no llaman al modelo."""
    from app.verifika.invariantes import revisar_charla

    sucias = []
    for path in _casetes():
        fallas = revisar_charla(_correr(path)["respuestas"])
        for f in fallas:
            sucias.append(f"{path.stem} turno {f['turno']}: {f['regla']} — "
                          f"{f['detalle']}")
    assert not sucias, ("INVARIANTES VIOLADOS:\n  " + "\n  ".join(sucias))
