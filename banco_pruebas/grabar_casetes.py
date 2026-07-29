#!/usr/bin/env python3
"""
GRABAR CASETES — corre los guiones contra el modelo REAL una vez y guarda lo que
devuelve, para que despues el turno completo corra gratis en cada push.

Es lo UNICO de esta maquinaria que gasta plata y necesita la clave. Se corre a
proposito, no en CI, y solo cuando cambia el CONTRATO con el modelo: el schema
del interprete, los tipos de fragmento del solver, el schema del juez. Ajustar
una frase de un prompt NO obliga a regrabar: el casete se indexa por (turno,
etapa), no por el texto del prompt. Ver banco_pruebas/casete.py.

Uso:
    python banco_pruebas/grabar_casetes.py                 # todos los guiones
    python banco_pruebas/grabar_casetes.py 54_x.txt 12_y.txt
    BANCO_PAUSA_S=8 python banco_pruebas/grabar_casetes.py # pausa entre turnos

Al terminar imprime el puntaje de cada charla y EL NUMERO global. Ese numero es
el que despues defiende el test de CI.
"""
import asyncio
import datetime as _dt
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from banco_pruebas.casete import CASETES, grabando            # noqa: E402
from banco_pruebas.puntaje import (leer_guion, puntaje_global,  # noqa: E402
                                   puntuar_charla)
from banco_pruebas.sim_firestore import install                # noqa: E402

TIENDA = "verifika_prod"
GUIONES = Path(__file__).resolve().parent / "guiones"
_PISO = CASETES / "_piso.json"


async def _grabar_una(path: Path, pausa_s: float) -> dict:
    from app.config import get_settings
    from app.core.hub_atado import procesar_atado
    from app.storage.firestore_client import reset_conversation

    nombre = path.stem
    turnos = leer_guion(path.read_text(encoding="utf-8"))
    user = f"casete_{nombre}"
    try:
        reset_conversation(user, tienda_id=TIENDA)
    except Exception:
        pass

    respuestas: list[str] = []
    print(f"\n=== {nombre} ({len(turnos)} turnos) ===")
    with grabando(nombre) as casete:
        for i, turno in enumerate(turnos, 1):
            casete.abrir_turno(turno["mensaje"])
            print(f"  [{i}] {turno['mensaje'][:70]}")
            try:
                r = await procesar_atado(user, turno["mensaje"], TIENDA,
                                         "casete", f"grab_{nombre}_{i}")
            except Exception as e:
                r = ""
                print(f"      ERROR: {type(e).__name__}: {str(e)[:120]}")
            respuestas.append(r or "")
            print(f"      -> {(r or '')[:100]}")
            if pausa_s and i < len(turnos):
                time.sleep(pausa_s)
        ruta = casete.guardar()

    fallback = get_settings().VERIFIKA_FALLBACK_MESSAGE
    res = puntuar_charla(turnos, respuestas, TIENDA, fallback)
    print(f"  casete: {ruta.name} | puntaje {res['puntaje']}/100")
    for f in res["fallas"][:6]:
        print(f"      ! {f}")
    return res


async def _main(nombres: list[str]) -> int:
    install()
    pausa_s = float(os.getenv("BANCO_PAUSA_S", "0") or 0)
    paths = ([GUIONES / n for n in nombres] if nombres
             else sorted(GUIONES.glob("*.txt")))
    faltan = [p for p in paths if not p.exists()]
    if faltan:
        print("no existen:", [p.name for p in faltan])
        return 2
    resultados = [await _grabar_una(p, pausa_s) for p in paths]
    numero = puntaje_global(resultados)
    print(f"\n{'=' * 60}\nEL NUMERO: {numero}/100 sobre {len(resultados)} charlas")

    # EL PISO se escribe solo, y solo cuando se regrabo TODO. Si se regraba un
    # guion suelto el numero no es comparable y tocarlo seria bajar la vara sin
    # querer: el piso lo defiende el test en cada push, asi que un piso mal
    # puesto es peor que no tener piso.
    if not nombres:
        _PISO.parent.mkdir(parents=True, exist_ok=True)
        _PISO.write_text(json.dumps(
            {"piso": numero,
             "puntos": sum(r["puntos"] for r in resultados),
             "total": sum(r["total"] for r in resultados),
             "charlas": len(resultados),
             "grabado": _dt.date.today().isoformat(),
             "_doc": "El puntaje que defiende tests/test_charlas_grabadas.py. "
                     "Manda `puntos`, que es el crudo: `piso` esta redondeado y "
                     "una regresion de un par de turnos podia seguir "
                     "redondeando igual y pasar el gate. Si un cambio lo baja, "
                     "el CI se cae. Si lo sube, se actualiza en el mismo "
                     "commit."},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"piso actualizado en {_PISO}")
    else:
        print("piso NO tocado: se regrabaron guiones sueltos, no la tanda entera")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main(sys.argv[1:])))
