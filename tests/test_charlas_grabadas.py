"""
EL TURNO COMPLETO, EN CADA PUSH, GRATIS.

Este archivo es la red que faltaba. Corre las charlas grabadas por el camino
VIVO entero -interprete, universo, solver atado, render, los siete
verificadores, las cinco guardas, el cierre y la memoria- con el catalogo real y
el modelo reemplazado por su grabacion. Sin clave, sin red, sin costo, en
segundos.

QUE CUBRE QUE LOS 666 TESTS DE ANTES NO CUBRIAN. Medido el 29-jul: de 666 tests,
31 tocaban el turno entero y la cobertura del camino vivo era 61%. Los dos bugs
de ese dia -el webhook de Telegram llamando a una funcion borrada, y 57 fichas
contradiciendo su propio modelo- pasaron por delante de una bateria en verde. La
diferencia no es cuantos tests hay: es que ninguno corria la charla completa.

QUE NO CUBRE, dicho claro. El modelo esta grabado, asi que esto NO mide si el
modelo mejoro o empeoro. Para eso esta el banco vivo pago, que se corre a
proposito. Lo que se mide aca son las 18 reescrituras encadenadas del texto, que
es donde vivieron todos los bugs de esta semana.

LA REGLA: el numero no baja. `PISO` es el puntaje que quedo la ultima vez que se
regrabo. Si un cambio lo baja, el test se cae y hay que mirar por que; si lo
sube, se actualiza el piso en el mismo commit. Eso es lo que convierte "robusto"
de opinion en dato.
"""
import asyncio
import json
from pathlib import Path

import pytest

from banco_pruebas.casete import Casete, reproducir
from banco_pruebas.puntaje import leer_guion, puntaje_global, puntuar_charla

TIENDA = "verifika_prod"
_GUIONES = Path(__file__).resolve().parent.parent / "banco_pruebas" / "guiones"
_PISO_JSON = (Path(__file__).resolve().parent.parent / "banco_pruebas"
              / "casetes" / "_piso.json")


def _piso() -> int:
    """El puntaje a defender. Vive al lado de los casetes y se actualiza en el
    mismo commit que los regraba."""
    try:
        return int(json.loads(_PISO_JSON.read_text(encoding="utf-8"))["piso"])
    except Exception:
        return 0


def _correr_casete(casete: Casete, firestore_doble) -> dict:
    from app.config import get_settings
    from app.core.hub_atado import procesar_atado
    from app.storage.firestore_client import reset_conversation

    guion = _GUIONES / f"{casete.nombre}.txt"
    turnos = leer_guion(guion.read_text(encoding="utf-8"))
    user = f"casete_test_{casete.nombre}"
    try:
        reset_conversation(user, tienda_id=TIENDA)
    except Exception:
        pass

    respuestas: list[str] = []
    with reproducir(casete):
        for i, turno in enumerate(turnos, 1):
            casete.abrir_turno(turno["mensaje"])
            try:
                r = asyncio.run(procesar_atado(
                    user, turno["mensaje"], TIENDA, "casete",
                    f"test_{casete.nombre}_{i}"))
            except Exception as e:
                # que el turno reviente ES el hallazgo: se anota y la charla
                # sigue, para ver el efecto completo y no solo el primer desvio
                r = ""
                casete.fallas.append(f"turno {i} reviento: "
                                     f"{type(e).__name__}: {str(e)[:100]}")
            respuestas.append(r or "")
        huecos = list(casete.fallas)

    res = puntuar_charla(turnos, respuestas, TIENDA,
                         get_settings().VERIFIKA_FALLBACK_MESSAGE, huecos)
    res["nombre"] = casete.nombre
    return res


_CASETES = Casete.todos()


@pytest.mark.skipif(not _CASETES,
                    reason="no hay casetes grabados: correr "
                           "banco_pruebas/grabar_casetes.py con la clave")
@pytest.mark.parametrize("casete", _CASETES, ids=lambda c: c.nombre)
def test_charla_no_revienta_ni_miente(casete, firestore_doble):
    """Cada charla, turno por turno, por el camino vivo entero.

    Falla ante lo que NO se negocia: un turno que revienta, una mentira sobre
    stock o plata, una promesa prohibida. Lo blando -que la respuesta sea buena-
    lo mide el puntaje global del test de abajo."""
    res = _correr_casete(casete, firestore_doble)
    duras = [f for f in res["fallas"]
             if "reviento" in f or "miente" in f]
    assert not duras, (f"{casete.nombre}: {len(duras)} fallas duras\n  "
                       + "\n  ".join(duras[:8]))


@pytest.mark.skipif(not _CASETES, reason="no hay casetes grabados")
def test_el_numero_no_baja(firestore_doble, capsys):
    """EL NUMERO. Un solo puntaje sobre todas las charlas grabadas.

    Es la definicion de terminado que no existia: si esto no sube, el sistema no
    mejoro, por mas tests de unidad que se hayan sumado."""
    resultados = [_correr_casete(c, firestore_doble) for c in _CASETES]
    numero = puntaje_global(resultados)
    with capsys.disabled():
        print(f"\n\n{'=' * 62}\nEL NUMERO: {numero}/100 sobre "
              f"{len(resultados)} charlas (piso {_piso()})")
        for r in sorted(resultados, key=lambda x: x["puntaje"])[:8]:
            print(f"  {r['puntaje']:3}/100  {r['nombre']}")
            for f in r["fallas"][:3]:
                print(f"          ! {f}")
        print("=" * 62)
    assert numero >= _piso(), (
        f"el numero BAJO: {numero} contra un piso de {_piso()}. "
        f"Algun cambio empeoro las charlas; mirar el detalle de arriba.")
