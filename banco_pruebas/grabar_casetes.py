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
    """Graba UNA charla por el camino VIVO.

    POR QUE POR EL CLON Y NO POR `procesar_venta`. Es la leccion mas cara de
    este repo, y se pago dos veces: el banco llamaba directo al hub y se
    salteaba `app.main._process_and_reply_whatsapp`, que es lo que de verdad
    atiende el webhook -antijailbreak, RESET_CODE, el corte en partes-. Un
    banco que prueba OTRO camino da verde mientras el cliente recibe cualquier
    cosa. El casete se graba y se reproduce por donde entra el mensaje real."""
    from app.config import get_settings
    from banco_pruebas import clon_produccion as clon

    nombre = path.stem
    turnos = leer_guion(path.read_text(encoding="utf-8"))
    user = f"casete_{nombre}"
    clon.reiniciar_cliente(user)

    respuestas: list[str] = []
    print(f"\n=== {nombre} ({len(turnos)} turnos) ===")
    with grabando(nombre) as casete:
        for i, turno in enumerate(turnos, 1):
            casete.abrir_turno(turno["mensaje"])
            print(f"  [{i}] {turno['mensaje'][:70]}")
            try:
                partes = await clon.turno(user, turno["mensaje"])
                r = "\n".join(partes)
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


def _fijar_piso() -> int:
    """Refija el piso SIN gastar un token: reproduce los casetes que ya estan y
    escribe el numero. Hace falta cuando se grabo en tandas -la clave gratis
    obliga- o cuando un arreglo del CODIGO sube el puntaje sin tocar el modelo,
    que es justo lo que se quiere ver."""
    from banco_pruebas import clon_produccion as clon
    from banco_pruebas.casete import reproducir_charla
    clon.instalar()
    casetes = [p for p in sorted(CASETES.glob("*.json"))
               if not p.name.startswith("_")]
    if not casetes:
        print("no hay casetes")
        return 2
    resultados = [reproducir_charla(p) for p in casetes]
    _escribir_piso(resultados)
    return 0


def _escribir_piso(resultados: list) -> None:
    numero = puntaje_global(resultados)
    llamadas = [n for r in resultados
                for n in (r.get("llamadas_por_turno") or [])]
    largos = [len(t) for r in resultados for t in (r.get("respuestas") or [])]
    _PISO.parent.mkdir(parents=True, exist_ok=True)
    _PISO.write_text(json.dumps(
        {"piso": numero,
         "puntos": sum(r["puntos"] for r in resultados),
         "total": sum(r["total"] for r in resultados),
         "charlas": len(resultados),
         "llamadas_max": max(llamadas) if llamadas else 0,
         "llamadas_total": sum(llamadas),
         "largo_max": max(largos) if largos else 0,
         "largo_promedio": sum(largos) // len(largos) if largos else 0,
         "grabado": _dt.date.today().isoformat(),
         "_doc": "El piso que defiende tests/test_charlas_grabadas.py. Manda "
                 "`puntos`, que es el crudo: `piso` esta redondeado y una "
                 "regresion de un par de turnos podia seguir redondeando igual "
                 "y pasar el gate. `llamadas_max` es la LATENCIA medida sin "
                 "reloj: cada llamada al modelo son entre 3 y 8 segundos, y no "
                 "puede crecer. Se refija con `grabar_casetes.py --piso`, que "
                 "no gasta la clave. "
                 "EL TOPE DE LARGO BAJA DE ESCALON Y NO VUELVE A SUBIR "
                 "(FICHA 05, 22-ago-2026): despues de cada corte se fija en el "
                 "MAXIMO REAL que quedo, sin aire. Hasta esa fecha el piso solo "
                 "impedia que el largo creciera, y un tope que solo prohibe "
                 "empeorar deja el numero donde esta para siempre: 1.882 habia "
                 "subido dos veces y no habia bajado nunca. Asi la concision es "
                 "un efecto MEDIDO del recorte y no una tarea aparte que no "
                 "llega: cada pieza que se saca de la cadena de salida baja el "
                 "numero un escalon, y el escalon queda."},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\npiso: {numero}/100, {sum(r['puntos'] for r in resultados)} puntos, "
          f"hasta {max(llamadas) if llamadas else 0} llamadas por turno, "
          f"mensaje mas largo {max(largos) if largos else 0} caracteres")


async def _main(nombres: list[str]) -> int:
    # El clon instala el doble de Firestore Y engancha el conector de banco en
    # `app.main`, que es lo que hace que el camino del webhook corra entero.
    from banco_pruebas import clon_produccion as clon
    info = clon.instalar()
    print(f"clon: {info.get('clave')} | modelo {info.get('solver_model')} | "
          f"{info.get('productos', '?')} productos")
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

    # EL PISO se escribe cuando lo grabado cubre TODOS los casetes que hay. Si
    # se regraba un guion suelto y quedan otros viejos al lado, el numero no es
    # comparable y tocarlo seria bajar la vara sin querer.
    #
    # Y SE MIDE POR REPRODUCCION, no por la grabacion: el CI reproduce, y un
    # piso medido con otra vara no defiende nada. Puede dar distinto -un hueco
    # de casete descuenta al reproducir y no al grabar-, y esa diferencia es
    # justamente lo que hay que ver.
    grabados = {p.stem for p in CASETES.glob("*.json")
                if not p.name.startswith("_")}
    pedidos = {Path(n).stem for n in nombres} if nombres else grabados
    if grabados and grabados <= pedidos:
        from banco_pruebas.casete import reproducir_charla
        _escribir_piso([reproducir_charla(p)
                        for p in sorted(CASETES.glob("*.json"))
                        if not p.name.startswith("_")])
    else:
        print("piso NO tocado: se regrabaron guiones sueltos, no la tanda entera")
    return 0


if __name__ == "__main__":
    if "--piso" in sys.argv:
        # Refijar el piso con lo ya grabado, sin llamar al modelo.
        raise SystemExit(_fijar_piso())
    raise SystemExit(asyncio.run(_main(sys.argv[1:])))
