#!/usr/bin/env python3
"""LA TANDA DE LA INTERPRETACION — el mismo numero, sin esperar un WhatsApp.

QUE ES. Corre los mensajes de `vara_interpretacion.json` por el camino VIVO
del turno —`respuesta._preguntar`, el modelo de verdad, el tablero de verdad—
y los puntua con la MISMA vara y el MISMO puntaje que
`leer_interpretacion.py` usa sobre los logs de produccion.

POR QUE NO ES UN BANCO NUEVO, y eso importa porque el repo tiene prohibido
ramificar en bancos —ya se pago tres veces—. No trae una definicion propia de
"correcto": el puntaje es `leer_interpretacion.puntuar` y la vara es el mismo
archivo. Lo unico que cambia es DE DONDE salen los turnos. Tampoco simula el
turno: usa el camino vivo entero y el doble local de Firestore, igual que
`tanda_tablero.py`, del que copia el arnes.

Y LEE LO MISMO QUE PRODUCCION, literalmente. El `motor_pedido` no se
reconstruye: se captura con `observador`, que es el mismo evento de structlog
que en produccion se consulta en Cloud Logging. Si el camino vivo deja de
loguearlo, esta tanda se apaga igual que la lectura de produccion, que es
exactamente lo que tiene que pasar.

PARA QUE SIRVE Y PARA QUE NO. Sirve para ITERAR: cambiar la forma del tablero
y ver el numero en minutos en vez de en una tanda de WhatsApp. NO reemplaza la
medicion real: el dia que el numero cierre, se manda por WhatsApp y se compara.
Si los dos numeros no coinciden, manda el de produccion.

CON LA CLAVE GRATIS, regla 4. Es mas lenta y devuelve 429; por eso la pausa
entre mensajes, igual que en `tanda_tablero.py`: sin pausa esto mide la cuota
y no al bot, y un turno caido por cuota se lee IGUAL que uno donde el modelo
no declaro nada, o sea que acusa al modelo de algo que no hizo.

Uso, desde la raiz:
    python3 banco_pruebas/tanda_interpretacion.py
    python3 banco_pruebas/tanda_interpretacion.py --solo M1,M6
    python3 banco_pruebas/tanda_interpretacion.py --pausa 0 --vueltas 1
"""
import argparse
import asyncio
import json
import os
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from banco_pruebas import clon_produccion, observador  # noqa: E402
from banco_pruebas import sim_firestore  # noqa: E402
from banco_pruebas.leer_interpretacion import (  # noqa: E402
    cargar_vara, puntuar)

TIENDA = "verifika_prod"


async def _un_turno(texto: str, trace: str) -> dict:
    """El turno vivo, y el pedido leido del MISMO evento que produccion."""
    from app.core import fuente as F
    from app.core import guardas_salida as gs
    from app.core import respuesta as R
    from app.core.contexto_turno import set_current_tienda

    set_current_tienda(TIENDA)
    bloque = R._bloque_fuente([], F.texto_inventario(TIENDA))
    t0 = time.time()
    with observador.turno() as t:
        try:
            salida, _f, _e, _c, informe = await R._preguntar(
                R._voz(gs.business_name(TIENDA)), "", [], texto, bloque,
                trace, TIENDA)
        except Exception as e:  # noqa: BLE001 — un turno caido no tumba la tanda
            salida, informe = None, {"vueltas": 0, "llamadas": 0}
            print(f"   ERROR {type(e).__name__}: {str(e)[:140]}")
    vueltas = []
    for e in t.eventos:
        if e.get("event") != "motor_pedido":
            continue
        try:
            vueltas.append(json.loads(e["pedido"]))
        except Exception:  # noqa: BLE001 — un pedido roto no tumba la lectura
            pass
    # UN TURNO SIN UNA SOLA LLAMADA AL MOTOR NO ES UN CERO DEL MODELO: es un
    # turno caido, casi siempre por el 429 de la cuota gratis. Se marca y se
    # cuenta aparte, que es lo que `tablero_piso.json` ya hace.
    return {"trace": trace, "texto": texto, "rev": "banco",
            "vueltas": vueltas, "ms": int((time.time() - t0) * 1000),
            "caido": not vueltas and not (salida or {}),
            "radares": [str(r.get("event")) for r in t.radares()]}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", default="", help="ids de la vara: M1,M6")
    ap.add_argument("--pausa", type=float, default=20.0)
    # UNA CORRIDA NO ES UN NUMERO. El modelo decide distinto entre llamadas
    # identicas, asi que un 12 de 12 suelto no distingue "quedo atado" de
    # "salio bien esta vez". Lo que dice si un cambio sirvio es en CUANTAS de
    # N corridas se llena cada casilla, y cual es la que tiembla.
    ap.add_argument("--repeticiones", type=int, default=1)
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    # LA CLAVE LA ELIGE `clon_produccion`, Y NO HAY UNA SEGUNDA FORMA. La
    # gratis es el default y la paga entra solo por la variable
    # `BANCO_CLAVE_PAGA`, que es la decision del 4-ago despues de que toda
    # corrida de banco se fuera a la paga sin que nadie lo pidiera. Escribir
    # aca un segundo selector seria justo la clase de cosa suelta que la
    # regla 2 prohibe.
    clon_produccion.preparar_entorno()

    vara = cargar_vara()
    quiero = {x.strip().upper() for x in args.solo.split(",") if x.strip()}
    mensajes = [m for m in vara["mensajes"]
                if not quiero or m["id"].upper() in quiero]
    if not mensajes:
        print(f"ningun mensaje de la vara con --solo {args.solo}")
        return 1

    sim_firestore.install()
    # EL BUFFER ARRANCA VACIO EN UN PROCESO FRESCO, asi que no se limpia. Y
    # hay un motivo para no escribir esa linea aunque sea inocua: el censo del
    # cableado aparea por NOMBRE PELADO, asi que un `observador.limpiar()` aca
    # hacia figurar a `app/core/huecos.py:limpiar` como instrumento y bajaba
    # el censo de 24 a 23 sin que nadie hubiera enchufado nada. Una mejora
    # falsa en un techo que solo baja es peor que no medir. El defecto del
    # censo queda anotado en PENDIENTE; no se arregla desde aca.
    observador.instalar(consola=False)

    corridas, crudo = [], []
    primero = True
    for vuelta in range(max(1, args.repeticiones)):
        if args.repeticiones > 1:
            print(f"\n{'#'*60}\n# CORRIDA {vuelta + 1} de "
                  f"{args.repeticiones}\n{'#'*60}")
        vistos, caidos = [], []
        for m in mensajes:
            if not primero and args.pausa:
                await asyncio.sleep(args.pausa)
            primero = False
            t = await _un_turno(m["texto"], f"banco-{m['id']}-{vuelta + 1}")
            print(f"{m['id']:<4} {len(t['vueltas'])} llamada(s)  {t['ms']}ms"
                  + (f"  RADARES: {','.join(sorted(set(t['radares'])))}"
                     if t["radares"] else ""))
            (caidos if t["caido"] else vistos).append((t, m))
            crudo.append({"corrida": vuelta + 1, "id": m["id"], **t})

        if caidos:
            print(f"\nCAIDOS Y NO SE CUENTAN: "
                  f"{', '.join(m['id'] for _t, m in caidos)}  "
                  f"— casi siempre el 429 de la clave, no el modelo")
        if not vistos:
            print("\nningun turno sano en esta corrida")
            continue
        corridas.append(puntuar(vistos))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(crudo, f, ensure_ascii=False, indent=2)
        print(f"\ncrudo en {args.json}")
    if not corridas:
        return 1
    if len(corridas) > 1:
        _estabilidad(corridas)
    # VERDE SOLO SI TODAS LAS CORRIDAS LLENARON TODO. Una sola que falle deja
    # el codigo en 1, que es lo que convierte esto en algo que se corre en
    # loop y se mira el resultado, en vez de leerlo a ojo cada vez.
    return 0 if all(c["v1"] == c["de"] for c in corridas) else 1


def _estabilidad(corridas: list) -> None:
    """EN CUANTAS DE N CORRIDAS SE LLENO CADA COSA, y cual es la que tiembla.

    Es el renglon que convierte un 12 de 12 en un numero. Un promedio no
    sirve: esconde justo lo que hay que ver, que es si una casilla se llena
    SIEMPRE o se llena A VECES.
    """
    n = len(corridas)
    print(f"\n{'='*60}\nESTABILIDAD sobre {n} corridas")
    for mid in list(corridas[0]["por_mensaje"]):
        filas = [c["por_mensaje"][mid] for c in corridas
                 if mid in c["por_mensaje"]]
        de = filas[0]["de"]
        plenos = sum(1 for f in filas if f["v1"] == de)
        flojas: dict = {}
        for f in filas:
            for nombre in f["fallaron"]:
                flojas[nombre] = flojas.get(nombre, 0) + 1
        reng = sorted({f["renglones"] for f in filas})
        print(f"  {mid:<4} {plenos}/{len(filas)} corridas en {de} de {de}"
              f"   renglones={'-'.join(str(x) for x in reng)}")
        for nombre, veces in sorted(flojas.items(), key=lambda kv: -kv[1]):
            print(f"         FALLO {veces}/{len(filas)}: {nombre}")
    v1 = [c["v1"] for c in corridas]
    de = corridas[0]["de"]
    print(f"\n  vuelta 1: min {min(v1)} · max {max(v1)} · de {de}"
          f"   ({sum(1 for x in v1 if x == de)}/{n} corridas perfectas)")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
