"""LO QUE TRADUJERON LOS MODELOS, TURNO POR TURNO, POR EL CAMINO FIJO — sin modelo (10-nov-2026, FICHA 92 paso 1).

Reemplaza a `forma_normal/regrado.py`, que pasaba por el turno vivo y desde el 30-oct ya no llegaba al ejecutor.

`traduccion58_corridas.jsonl` tiene la agenda que devolvio cada modelo en cada turno de las 58 y las K, en cinco formas
de escribir cada mensaje. Para cada turno grabado, los turnos anteriores de la charla corren con su agenda a mano,
`agendas58.py`, por el camino fijo de `camino_fijo.py`; el turno grabado corre dos veces desde el mismo estado: con la
agenda del modelo y con la agenda a mano, las dos con el mismo mensaje.

La vara, la de la FICHA 92: esta bien si deja LOS MISMOS PRODUCTOS mostrados, EL MISMO PEDIDO y LOS MISMOS MONTOS que la
agenda a mano. Las casillas de la vara se cuentan aparte: en los primeros turnos son flojas.

  python3 banco_pruebas/camino_grabadas.py                    Gemini, todo, con lo que falla por capa
  python3 banco_pruebas/camino_grabadas.py --todos            los seis modelos
  python3 banco_pruebas/camino_grabadas.py K20 C47            esas charlas
  python3 banco_pruebas/camino_grabadas.py --guardar X        guarda en banco_pruebas/camino_grabadas_X.json
  python3 banco_pruebas/camino_grabadas.py --contra X         lo que arregla y lo que rompe contra lo guardado
"""
import asyncio
import collections
import copy
import json
import os
import re
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AQUI)
sys.path[:0] = [REPO]
os.chdir(REPO)

MODELOS = ("prod", "deepseek", "haiku", "luna", "mini54", "terra")


def grabadas(modelos, ids) -> dict:
    """{(charla, turno): [corrida]}, la primera vuelta de cada modelo."""
    out = collections.defaultdict(list)
    for linea in open(os.path.join(AQUI, "traduccion58_corridas.jsonl"), encoding="utf-8"):
        r = json.loads(linea)
        if (r.get("modelo") or "prod") in modelos and r.get("rep", 0) == 0 and (not ids or r["charla"] in ids):
            out[(r["charla"], r["turno"])].append(r)
    return out


def _huella(estado: dict, texto: str) -> dict:
    """Lo que no se discute: los productos, el pedido y los montos. El destino se compara normalizado: "Córdoba" y
    "Cordoba" son el mismo para el cliente."""
    from app.core.flujo import catalogo as K
    return {"mostrados": sorted({m["id"] for m in estado["mostrados"]}),
            "pedido": sorted(f"{a.get('id')}x{a.get('cantidad')}@{K.n(a.get('destino'))}" for a in estado["pedido"]),
            "montos": sorted(set(re.findall(r"\$\s?[\d.]+", texto)))}


def _capa(agenda: dict) -> str:
    """La capa del turno: la accion principal de la agenda a mano, en el orden del plan por capas."""
    acciones = [p.get("accion") for p in agenda.get("preguntas") or []]
    for a in ("cuenta", "comprar", "compatibilidad", "envio", "politica", "explicar", "producto", "buscar"):
        if a in acciones:
            return a
    return "otro"


def correr(modelos=("prod",), ids=()) -> dict:
    from banco_pruebas import camino_fijo as F
    from banco_pruebas import clon_produccion as C
    from banco_pruebas import sim_firestore as S
    from banco_pruebas.agendas58 import AGENDAS
    from banco_pruebas.sonda_charlas import nota_casilla
    F.instalar()
    charlas = {c["id"]: c for c in F.todas()}
    uid, out, t0 = "grabadas", {}, time.time()

    def _uno(agenda, texto, guardado):
        S._CONV.clear()
        S._CONV.update(copy.deepcopy(guardado[0]))
        F.ESTADOS[uid], F.PRESUPUESTOS[uid] = copy.deepcopy(guardado[1]), guardado[2]
        F.COLA[uid] = [agenda]
        resp = "\n".join(asyncio.run(C.turno(uid, texto)))
        return resp, _huella(F.ESTADOS[uid], resp)

    for (cid, n), corridas in sorted(grabadas(modelos, ids).items()):
        ch, ags = charlas.get(cid), AGENDAS.get(cid)
        if not ch or not ags or n >= len(ags):
            continue
        C.reiniciar_cliente(uid)
        F.COLA[uid], F.ESTADOS[uid] = list(ags[:n]), None
        F.PRESUPUESTOS.pop(uid, None)
        previas = ["\n".join(asyncio.run(C.turno(uid, t["texto"]))) for t in ch["turnos"][:n]]
        guardado = (copy.deepcopy(S._CONV), copy.deepcopy(F.ESTADOS[uid]), F.PRESUPUESTOS.get(uid))
        oro = {}
        for r in corridas:
            if r["forma"] not in oro:
                oro[r["forma"]] = _uno(dict(copy.deepcopy(ags[n]), mensaje=r["texto"]), r["texto"], guardado)
            ag = {k: v for k, v in (r.get("agenda") or {}).items() if k != "_crudo"} \
                if isinstance(r.get("agenda"), dict) else {}
            ag["mensaje"] = r["texto"]
            resp, h = _uno(ag, r["texto"], guardado)
            malas = [c["n"] for c in ch["turnos"][n]["casillas"] if nota_casilla(c, [], resp, previas + [resp]) is not True]
            distinto = [k for k in h if h[k] != oro[r["forma"]][1][k]]
            out[f"{r.get('modelo') or 'prod'}|{cid}|{n}|{r['forma']}"] = {
                # Un error del camino es una falla aunque la agenda a mano rompa igual: si no, dos errores son iguales.
                "bien": not distinto and "ERROR DEL CAMINO" not in resp + oro[r["forma"]][0], "distinto": distinto, "casillas": not malas, "capa": _capa(ags[n]),
                "texto": r["texto"], "respuesta": resp, "oro": oro[r["forma"]][0]}
    print(f"[{len(out)} casos en {time.time() - t0:.0f} s]", flush=True)
    return out


def informe(res: dict, contra: dict = None) -> None:
    por_m = collections.defaultdict(list)
    for k, v in res.items():
        por_m[k.split("|")[0]].append(v)
    for m, xs in por_m.items():
        print(f"{m:9} {sum(x['bien'] for x in xs)} de {len(xs)} iguales a la agenda a mano; "
              f"casillas {sum(x['casillas'] for x in xs)}")
    print("\npor capa, Gemini:" if "prod" in por_m else "\npor capa:")
    capas = collections.defaultdict(list)
    for k, v in res.items():
        if k.startswith("prod|") or "prod" not in por_m:
            capas[v["capa"]].append(v)
    for c, xs in sorted(capas.items(), key=lambda x: -len(x[1])):
        print(f"  {c:15} {sum(x['bien'] for x in xs)} de {len(xs)}")
    if contra is not None:
        arregla = sorted(k for k in res if res[k]["bien"] and k in contra and not contra[k]["bien"])
        rompe = sorted(k for k in res if not res[k]["bien"] and k in contra and contra[k]["bien"])
        print(f"\ncontra la referencia: arregla {len(arregla)}, rompe {len(rompe)}")
        for k in rompe[:20]:
            print(f"  ROMPE {k}: {res[k]['texto'][:100]}")


if __name__ == "__main__":
    ARGS = sys.argv[1:]
    sacar = {ARGS[ARGS.index(f) + 1] for f in ("--guardar", "--contra") if f in ARGS}
    ids = [a for a in ARGS if not a.startswith("--") and a not in sacar]
    res = correr(MODELOS if "--todos" in ARGS else ("prod",), ids)
    contra = None
    if "--contra" in ARGS:
        contra = json.load(open(os.path.join(AQUI, f"camino_grabadas_{ARGS[ARGS.index('--contra') + 1]}.json"),
                                encoding="utf-8"))
    informe(res, contra)
    if "--guardar" in ARGS:
        with open(os.path.join(AQUI, f"camino_grabadas_{ARGS[ARGS.index('--guardar') + 1]}.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=0)
