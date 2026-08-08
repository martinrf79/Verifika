"""
EL DUELO: el intérprete VIEJO contra el de hoy, midiendo lo mismo.

POR QUE EXISTE (Martin, 7-ago-2026, textual): "me quedo esa espina de una
decision que tomé y quiero asegurarme de que el sistema que tenia la
interpretacion antigua era, a mi modo de ver, mas propensa a entender mensajes
complejos. O nos sorprendemos de los numeros o lo descartamos."

Es la pregunta mas honesta de todo el dia: **¿la decision del 1-ago de matar el
interprete fue un error?** Se venia contestando con memoria y con intuicion. Acá
se contesta con el mismo instrumento para los dos, sobre las mismas cinco
redacciones, y el que gana gana.

COMO SE HACE SIN TOCAR NADA. El interprete viejo se saca de git tal cual estaba
-`f56c094^:app/core/interpretador.py`, 1387 lineas- y se deja congelado en
`banco_pruebas/interprete_viejo/`. Importa solo `openai`, `app.config` y
`app.logger`, las tres vivas, asi que corre sin resucitar nada: no entra al
camino de produccion, no se deploya, y se puede borrar sin consecuencias.

LA VARA ES LA MISMA PARA LOS DOS, y es la de `interpretacion.py`: los once
hechos escritos en el mensaje de Martin. La unica diferencia es de donde sale la
declaracion:

  HOY    del argumento de `registrar_pedido` que pide el modelo.
  VIEJO  del JSON tipado que devolvia `interpretar_mensaje`.

Como los dos esquemas nombran las cosas distinto, hay un traductor -`_del_viejo`-
que lleva la salida vieja al mismo molde. **El traductor es lo unico que puede
mentir en esta medicion**, asi que es corto, esta a la vista, y no interpreta:
solo cambia nombres de campo.

USO:
    python3 banco_pruebas/duelo_interprete.py --repeticiones 3
"""
import asyncio
import os
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas.interpretacion import medir_declaracion  # noqa: E402
from banco_pruebas.objetivo import VARIANTES  # noqa: E402

TIENDA = "verifika_prod"


def _del_viejo(r: dict) -> dict:
    """Traduce la salida del interprete viejo al molde que mide la vara.

    NO INTERPRETA, solo cambia nombres. Cada linea de abajo se puede verificar
    contra el esquema viejo, que esta en `interprete_viejo/interpretador.py`.
    """
    r = r or {}
    items = []
    for it in (r.get("pedido") or []):
        items.append({"que": it.get("producto") or it.get("categoria") or "",
                      "cantidad": it.get("cantidad") or 1,
                      "destino": it.get("destino") or None})
    for it in (r.get("solicitud_nueva") or []):
        items.append({"que": it.get("categoria") or "",
                      "cantidad": it.get("cantidad") or 1,
                      "destino": it.get("destino") or None})
    # Las exclusiones tipadas del viejo se aplanan a la bolsa de restricciones
    # que espera la vara. Se conserva el valor, que es lo que se mide.
    restr = []
    for e in (r.get("exclusiones") or []):
        if isinstance(e, dict):
            restr.append(f"{e.get('tipo', '')} {e.get('valor', '')}".strip())
        elif e:
            restr.append(str(e))
    # EL CAMPO QUE HOY NO EXISTE. El viejo tenia `pago_reparto` tipado; la vara
    # busca los porcentajes en las restricciones, asi que se vuelcan ahi.
    for p in (r.get("pago_reparto") or []):
        if isinstance(p, dict):
            restr.append(f"{p.get('medio', '')} "
                         f"{int(float(p.get('porcentaje') or 0))}".strip())
    if r.get("tope_presupuesto"):
        restr.append(str(r["tope_presupuesto"]))
    if r.get("criterio"):
        restr.append(str(r["criterio"]))
    orden = r.get("orden") or {}
    if isinstance(orden, dict) and orden.get("atributo"):
        restr.append(f"{orden.get('direccion', '')} {orden['atributo']}".strip())
    destinos = [it["destino"] for it in items if it.get("destino")]
    return {"items": items, "restricciones": restr,
            "destinos": destinos or (r.get("destinos") or []),
            # GENEROSO A PROPOSITO con el viejo: si declaro algo para cotizar
            # -en `pedido` o en `solicitud_nueva`- el cliente esta pidiendo. No
            # se lo hace fallar por como nombro la intencion, que es otro eje.
            "pide_precio": bool(r.get("pedido") or r.get("solicitud_nueva")
                                or r.get("intencion") in
                                ("pregunta_especifica", "compra", "pedido",
                                 "cotizacion")),
            "contradicciones": ([str(r.get("consulta"))]
                                if r.get("ofrecer_opciones") else [])
            + ([str(x) for x in (r.get("candidatos") or [])]),
            "_crudo": r}


async def _viejo(msg: str, i: int) -> dict:
    from banco_pruebas.interprete_viejo import interpretador as IV
    return await IV.interpretar_mensaje(msg, [], f"duelo_{i}",
                                        tienda_id=TIENDA)


def main(argv: list) -> int:
    reps = 3
    if "--repeticiones" in argv:
        reps = int(argv[argv.index("--repeticiones") + 1])
    if os.environ.get("GEMINI_API_KEY_PROD"):
        os.environ["GEMINI_API_KEY"] = os.environ["GEMINI_API_KEY_PROD"]
    from banco_pruebas import sim_firestore
    sim_firestore.install()

    filas = []
    for nombre, msg in VARIANTES.items():
        notas, fallas = [], []
        for i in range(max(1, reps)):
            try:
                crudo = asyncio.get_event_loop().run_until_complete(
                    _viejo(msg, i))
            except Exception as e:                        # pragma: no cover
                print(f"  !! {nombre} corrida {i}: {type(e).__name__}: "
                      f"{str(e)[:200]}")
                notas.append(0)
                fallas.append("EXPLOTO")
                continue
            dec = medir_declaracion(_del_viejo(crudo))
            notas.append(round(100 * sum(1 for _, ok, _ in dec if ok)
                               / max(1, len(dec))))
            fallas += [k for k, ok, _ in dec if not ok]
        filas.append({"variante": nombre,
                      "prom": round(sum(notas) / max(1, len(notas))),
                      "min": min(notas) if notas else 0, "fallas": fallas})

    print("=" * 78)
    print(f"EL INTERPRETE VIEJO — {len(filas)} redacciones x {reps}")
    print("=" * 78)
    print("| redacción | ENTIENDE (viejo) |")
    print("|---|---|")
    for f in filas:
        print(f"| {f['variante']} | **{f['prom']}** |")
    prom = round(sum(f["prom"] for f in filas) / max(1, len(filas)))
    print(f"\nVIEJO {prom}/100   contra   HOY 91/100")
    from collections import Counter
    c = Counter(x for f in filas for x in f["fallas"])
    print("\nQUE NO ENTIENDE EL VIEJO:")
    for k, v in c.most_common():
        print(f"  {v:3d}  {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
