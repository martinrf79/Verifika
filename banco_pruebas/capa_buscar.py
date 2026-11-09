"""LA CAPA BUSCAR — lo que el modelo tradujo, grabado, contra la agenda a mano, por los productos que muestra el codigo
(9-nov-2026, orden de Martin: el plan por capas, `arquitectura/PLAN_CAPAS.md`).

Sin modelo. Toma las agendas que ya escribieron los modelos, `traduccion58_corridas.jsonl`, en el primer turno de cada
charla cuya agenda a mano tiene una busqueda. Cada agenda pasa por el codigo de hoy —la forma normal y el ejecutor— y
se compara con la agenda a mano, `agendas58.py`, por lo unico que no se puede discutir: QUE PRODUCTOS MUESTRA. Esta bien
si muestra los mismos.

Por que no las casillas de la vara: en los primeros turnos son flojas. Medido el 9-nov sobre las 375 de produccion: con
la agenda de Gemini pasan todas, pero con la agenda vacia pasan 105, y con el rubro cambiado, 255.

    python3 banco_pruebas/capa_buscar.py                      produccion, con el detalle de lo que falla
    python3 banco_pruebas/capa_buscar.py --todos              los seis modelos grabados
    python3 banco_pruebas/capa_buscar.py --guardar X          guarda el resultado en banco_pruebas/capa_buscar_X.json
    python3 banco_pruebas/capa_buscar.py --contra X           lo que arregla y lo que rompe contra lo guardado
    python3 banco_pruebas/capa_buscar.py --tipo producto      la capa de otro tipo: las charlas cuya agenda a mano lo trae
"""
import collections
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
sys.path[:0] = [REPO, AQUI]
TID = "verifika_prod"


def _ids(x) -> set:
    """Los ids de producto de los hechos del ejecutor: listas, productos, pedidos, en cualquier profundidad."""
    if isinstance(x, dict):
        return ({str(x["id"])} if "id" in x and "nombre" in x else set()).union(*[_ids(v) for v in x.values()] or [set()])
    if isinstance(x, list):
        return set().union(*[_ids(v) for v in x] or [set()])
    return set()


def correr(modelos=("prod",), tipo: str = "buscar") -> dict:
    """{clave: {"bien", "faltan", "sobran", "reglas"}}; clave = modelo|charla|forma|rep."""
    from banco_pruebas.plantilla_venta import llenar as LL
    LL.entorno()
    from banco_pruebas.agendas58 import AGENDAS
    from app.core.flujo import ejecutor as X
    from app.core.flujo import estado as E
    from app.core.flujo import normal as N
    reglas = []

    def _anotada(*a, **kw):
        ag, rs = N.normalizar(*a, **kw)
        reglas.extend(rs)
        return ag, rs
    X.normalizar = _anotada

    def productos(ag):
        reglas.clear()
        try:
            return _ids(X.ejecutar(ag, E.leer({}), TID).hechos), list(reglas)
        except Exception as e:  # noqa: BLE001 — una agenda que rompe el codigo es una falla, no corta la corrida
            return {f"ERROR {type(e).__name__}"}, list(reglas)
    con_buscar = {c for c, ags in AGENDAS.items() if any(p.get("accion") == tipo for p in ags[0]["preguntas"])}
    oro = {c: productos(AGENDAS[c][0])[0] for c in con_buscar}
    out = {}
    for linea in open(os.path.join(AQUI, "traduccion58_corridas.jsonl"), encoding="utf-8"):
        r = json.loads(linea)
        m = r.get("modelo") or "prod"
        if m not in modelos or r["turno"] != 0 or r["charla"] not in con_buscar:
            continue
        ag = {k: v for k, v in (r.get("agenda") or {}).items() if k != "_crudo"} if isinstance(r.get("agenda"), dict) else {}
        ag["mensaje"] = r["texto"]  # en el camino nuevo la caja 2 tiene el mensaje del cliente
        ids, rs = productos(ag)
        o = oro[r["charla"]]
        out[f"{m}|{r['charla']}|{r['forma']}|{r.get('rep', 0)}"] = {
            "bien": ids == o, "faltan": len(o - ids), "sobran": len(ids - o), "reglas": rs, "texto": r["texto"]}
    return out


def informe(res: dict, contra: dict = None) -> None:
    por_m = collections.defaultdict(list)
    for k, v in res.items():
        por_m[k.split("|")[0]].append(v["bien"])
    for m, xs in por_m.items():
        print(f"{m:9} {sum(xs)} de {len(xs)} con los mismos productos que la agenda a mano")
    por_c = collections.defaultdict(list)
    for k, v in res.items():
        por_c[tuple(k.split("|")[:2])].append(v)
    malas = {c: xs for c, xs in sorted(por_c.items()) if not all(x["bien"] for x in xs)}
    print("falla en: " + ", ".join(f"{m} {c} {sum(not x['bien'] for x in xs)}/{len(xs)}" for (m, c), xs in malas.items()))
    if contra is not None:
        arregla = sorted(k for k in res if res[k]["bien"] and k in contra and not contra[k]["bien"])
        rompe = sorted(k for k in res if not res[k]["bien"] and k in contra and contra[k]["bien"])
        print(f"contra la referencia: arregla {len(arregla)}, rompe {len(rompe)}")
        for k in rompe[:20]:
            print(f"  ROMPE {k}: {res[k]['texto'][:100]} · reglas {res[k]['reglas']}")


if __name__ == "__main__":
    ARGS, sys.argv = sys.argv[1:], [sys.argv[0]]
    modelos = ("prod", "deepseek", "haiku", "luna", "mini54", "terra") if "--todos" in ARGS else ("prod",)
    tipo = ARGS[ARGS.index("--tipo") + 1] if "--tipo" in ARGS else "buscar"
    res = correr(modelos, tipo)
    contra = None
    if "--contra" in ARGS:
        contra = json.load(open(os.path.join(AQUI, f"capa_buscar_{ARGS[ARGS.index('--contra') + 1]}.json"), encoding="utf-8"))
    informe(res, contra)
    if "--guardar" in ARGS:
        with open(os.path.join(AQUI, f"capa_buscar_{ARGS[ARGS.index('--guardar') + 1]}.json"), "w", encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=0)
