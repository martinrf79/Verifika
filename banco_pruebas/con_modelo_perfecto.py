#!/usr/bin/env python3
"""
CON EL MODELO PERFECTO — cuantas charlas pasa el CODIGO solo.

LA CONSIGNA (Martin, 18-ago-2026): "igualá los test simulando que el modelo
llamó bien, para que el código pase todas esas charlas. Verás que pasa pocas,
porque hay sobreingeniería".

LA IDEA, y es la que faltaba hace meses: mientras el modelo sea una variable,
cada medicion mezcla dos culpas y ninguna se cierra. Si el modelo llama bien
por construccion y escribe TODO lo que le damos, entonces **cada falla que
queda es del codigo**, es deterministica y se arregla. Lo que siga fallando
despues, por descarte, es del modelo, y eso es otro plan.

LA VARA, y es a proposito la mas dura que se puede sostener:

  1. COBERTURA. Cada cosa que el cliente pidio -cada item, cada destino, cada
     condicion, el precio- tiene que llegar al mensaje. Lo mide el indice del
     turno, que ya corre en produccion. Un punto sin contestar es el codigo que
     no lo busco, o que lo busco y lo perdio en el camino.
  2. INVARIANTES. Ninguna respuesta puede violar las propiedades que valen
     siempre: que la cuenta cierre, que lo cobrado sea lo facturado, que no se
     fugue nada interno, que nada se diga dos veces.

Una charla PASA si no le falta un solo punto y no viola un solo invariante.

POR QUE EL REDACTOR ES BOBO A PROPOSITO. Escribe todo lo que las herramientas
trajeron y ni una palabra mas. Cualquier redaccion mas linda seria el modelo
tapando un hueco del codigo, que es justo lo que hay que ver.

CORRE OFFLINE Y GRATIS: sin clave, sin red, sin modelo. Se puede repetir todas
las veces que haga falta, que es la condicion para que un loop sirva.

USO:
    python3 banco_pruebas/con_modelo_perfecto.py
    python3 banco_pruebas/con_modelo_perfecto.py --detalle 80_charla_real_12ago
"""
import argparse
import asyncio
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import modelo_sintetico as MS          # noqa: E402
from banco_pruebas.sim_firestore import install           # noqa: E402

TIENDA = "verifika_prod"
GUIONES = _RAIZ / "banco_pruebas" / "guiones"


def _correr(nombre: str) -> dict:
    """Una charla entera por el camino vivo, con el modelo llamando bien."""
    from banco_pruebas import clon_produccion as clon
    from banco_pruebas.puntaje import leer_guion
    from app.core import indice_turno as IT
    from app.storage.firestore_client import get_all_products
    from app.verifika.invariantes import revisar_charla

    turnos = leer_guion((GUIONES / f"{nombre}.txt").read_text(encoding="utf-8"))
    clon.instalar()
    user = f"perfecto_{nombre}"
    clon.reiniciar_cliente(user)

    faltan_por_turno = []

    async def _charla(estado):
        fuera, previo = [], {}
        for t in turnos:
            texto = "\n".join(await clon.turno(user, t["mensaje"]))
            fuera.append(texto)
            # EL MISMO declarado que el doble le paso al sistema, acumulado.
            # Medir contra otra cosa seria juzgar al codigo por un pedido que
            # nadie le declaro.
            previo = MS.acumular(previo, MS._declarar(t["mensaje"], TIENDA))
            # LAS LLAMADAS DE LA CHARLA, como evidencia. Es lo que hace el hub
            # vivo y sin esto el banco exige que CADA turno vuelva a contestar
            # todo lo que se pidio alguna vez: el cliente nombro Cordoba una
            # vez y el banco reclamaba Cordoba en los cinco turnos siguientes.
            # Eso no es un hueco del codigo, es el banco midiendo mal.
            idx = IT.cobertura(previo, texto, "perfecto",
                               llamadas=list(estado.get("llamadas") or []))
            faltan_por_turno.append([p["texto"] for p in (idx.get("faltan") or [])])
        return fuera

    with MS.sin_modelo(TIENDA, modo="fiel") as estado:
        respuestas = asyncio.run(_charla(estado))

    vocab = {str(p.get("nombre") or "") for p in
             get_all_products(tienda_id=TIENDA) if p.get("nombre")}
    violaciones = revisar_charla(respuestas, vocabulario=vocab)
    return {"nombre": nombre, "turnos": len(turnos), "respuestas": respuestas,
            "faltan": faltan_por_turno, "violaciones": violaciones}


def main(argv: list) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--detalle", default="")
    ap.add_argument("--limite", type=int, default=0)
    args = ap.parse_args(argv)

    install()
    nombres = sorted(p.stem for p in GUIONES.glob("*.txt"))
    if args.detalle:
        nombres = [n for n in nombres if args.detalle in n]
    elif args.limite:
        nombres = nombres[:args.limite]

    print("=" * 78)
    print("CON EL MODELO PERFECTO — que pasa el CODIGO solo")
    print("=" * 78)
    pasan, fallan, sin_puntos, sin_invar = 0, [], 0, 0
    for n in nombres:
        try:
            r = _correr(n)
        except Exception as e:  # noqa: BLE001 — una charla rota es un dato
            fallan.append((n, f"EXPLOTO: {type(e).__name__}: {str(e)[:70]}"))
            continue
        huecos = sum(len(f) for f in r["faltan"])
        viol = len(r["violaciones"])
        if huecos:
            sin_puntos += 1
        if viol:
            sin_invar += 1
        if not huecos and not viol:
            pasan += 1
            continue
        detalle = []
        if huecos:
            primero = next((f for f in r["faltan"] if f), [])
            detalle.append(f"{huecos} puntos sin contestar, p.ej. {primero[:2]}")
        if viol:
            detalle.append(f"{viol} invariantes: "
                           + ", ".join(sorted({v['regla'] for v in r['violaciones']}))[:60])
        fallan.append((n, " | ".join(detalle)))
        if args.detalle:
            for i, t in enumerate(r["respuestas"], 1):
                print(f"\n--- T{i} ---\n{t[:500]}")

    for n, d in fallan:
        print(f"  FALLA  {n:44} {d}")
    print("=" * 78)
    total = len(nombres)
    print(f"CHARLAS: {total}   PASAN: {pasan}   FALLAN: {total - pasan}")
    print(f"  con puntos sin contestar: {sin_puntos}")
    print(f"  con invariantes violados: {sin_invar}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
