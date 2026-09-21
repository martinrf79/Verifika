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

from banco_pruebas import observador, sim_firestore  # noqa: E402
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
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    vara = cargar_vara()
    quiero = {x.strip().upper() for x in args.solo.split(",") if x.strip()}
    mensajes = [m for m in vara["mensajes"]
                if not quiero or m["id"].upper() in quiero]
    if not mensajes:
        print(f"ningun mensaje de la vara con --solo {args.solo}")
        return 1

    sim_firestore.install()
    observador.instalar(consola=False)
    observador.limpiar()

    vistos, caidos = [], []
    for i, m in enumerate(mensajes):
        if i and args.pausa:
            await asyncio.sleep(args.pausa)
        t = await _un_turno(m["texto"], f"banco-{m['id']}")
        print(f"{m['id']:<4} {len(t['vueltas'])} llamada(s)  {t['ms']}ms"
              + (f"  RADARES: {','.join(sorted(set(t['radares'])))}"
                 if t["radares"] else ""))
        (caidos if t["caido"] else vistos).append((t, m))

    if caidos:
        print(f"\nCAIDOS Y NO SE CUENTAN: "
              f"{', '.join(m['id'] for _t, m in caidos)}  "
              f"— casi siempre el 429 de la clave gratis, no el modelo")
    if not vistos:
        print("\nningun turno sano: no hay nada que puntuar")
        return 1
    codigo = puntuar(vistos)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump([{"id": m["id"], **t} for t, m in vistos + caidos], f,
                      ensure_ascii=False, indent=2)
        print(f"\ncrudo en {args.json}")
    return codigo


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
