"""LAS TRADUCCIONES GRABADAS, CALIFICADAS DE NUEVO CON EL CODIGO DE HOY — sin modelo, gratis (21-oct-2026).

`traduccion58_corridas.jsonl` tiene la agenda que devolvio cada modelo en cada turno de las 525: la de produccion y las
de otros cinco. Aca cada una vuelve a pasar por el flujo vivo entero, con los turnos anteriores de la charla con su
agenda a mano, y se califica con las casillas de `vara_58.json`. Asi un cambio en el codigo que esta despues del
interprete se mide contra unas tres mil traducciones reales, de seis modelos, sin llamar a ninguno.

  python3 banco_pruebas/forma_normal/regrado.py                 todos, contra lo grabado
  python3 banco_pruebas/forma_normal/regrado.py --guardar X     y guarda el resultado como X.json, para comparar
  python3 banco_pruebas/forma_normal/regrado.py --contra X      lo que arregla y lo que rompe contra X.json
  python3 banco_pruebas/forma_normal/regrado.py C47 K21         solo esas charlas

`elegir` va sin eleccion y `vender` apagado, como en el cableado: lo que no se resolvio queda con su repregunta.
"""
import asyncio
import copy
import json
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, REPO)
os.chdir(REPO)

MODELOS = ("prod", "deepseek", "haiku", "luna", "mini54", "terra")


def grabadas() -> dict:
    """{(modelo, charla, turno, forma): corrida}, la primera vuelta de cada modelo."""
    out = {}
    for linea in open(os.path.join(REPO, "banco_pruebas", "traduccion58_corridas.jsonl"), encoding="utf-8"):
        r = json.loads(linea)
        m = r.get("modelo") or "prod"
        if m not in MODELOS or r.get("rep", 0) != 0:
            continue
        out[(m, r["charla"], r["turno"], r["forma"])] = r
    return out


def correr(solo=None, modelos=MODELOS) -> dict:
    from banco_pruebas import cableado58 as R
    from banco_pruebas import clon_produccion as C
    from banco_pruebas import sim_firestore as S
    from banco_pruebas.agendas58 import AGENDAS, EXPLICAR
    from banco_pruebas.sonda_charlas import nota_casilla
    from banco_pruebas.traduccion58 import _explicacion
    it = R.instalar()
    from app.core.flujo import ejecutor
    from app.core.flujo import normal as N
    aplicadas = []

    def _anotada(*a, **kw):
        ag, reglas = N.normalizar(*a, **kw)
        aplicadas.extend(reglas)
        return ag, reglas
    ejecutor.normalizar = _anotada
    charlas = {c["id"]: c for c in R.charlas()}
    todas = grabadas()
    por_turno = {}
    for k, r in todas.items():
        if (solo and k[1] not in solo) or k[0] not in modelos:
            continue
        por_turno.setdefault((k[1], k[2]), []).append(k)
    out, uid, t0 = {}, "regrado", time.time()
    for (cid, n), claves in sorted(por_turno.items()):
        ch, ags = charlas[cid], AGENDAS[cid]
        C.reiniciar_cliente(uid)
        previas = []
        for i, t in enumerate(ch["turnos"][:n]):
            async def _mano(*a, _ag=ags[i], **kw):
                return _ag

            async def _expl(pregunta, *a, _ag=ags[i], **kw):
                return _explicacion(_ag, EXPLICAR)
            it.interpretar, it.explicar = _mano, _expl
            previas.append("\n".join(asyncio.run(C.turno(uid, t["texto"]))))
        guardado = copy.deepcopy(S._CONV)
        casillas = ch["turnos"][n]["casillas"]
        for k in sorted(claves):
            S._CONV.clear()
            S._CONV.update(copy.deepcopy(guardado))
            r = todas[k]
            ag = {kk: vv for kk, vv in (r.get("agenda") or {}).items() if kk != "_crudo"}

            async def _grabada(*a, _ag=ag, **kw):
                return copy.deepcopy(_ag)

            async def _expl_k(pregunta, *a, **kw):
                return _explicacion(ags[n], EXPLICAR)
            it.interpretar, it.explicar = _grabada, _expl_k
            aplicadas.clear()
            texto = "\n".join(asyncio.run(C.turno(uid, r["texto"])))
            malas = [c["n"] for c in casillas if nota_casilla(c, [], texto, previas + [texto]) is not True]
            out[k] = {"bien": not malas, "malas": malas, "antes": r["bien"], "respuesta": texto,
                      "reglas": sorted(set(aplicadas))}
    print(f"[{len(out)} casos en {time.time() - t0:.0f} s]", flush=True)
    return out


def informe(res: dict, contra: dict = None) -> None:
    print(f"\n{'modelo':9} {'grabado':>8} {'hoy':>5} {'de':>5}")
    for m in MODELOS:
        ks = [k for k in res if k[0] == m]
        if ks:
            print(f"{m:9} {sum(res[k]['antes'] for k in ks):8} {sum(res[k]['bien'] for k in ks):5} {len(ks):5}")
    tot = len(res)
    print(f"{'todos':9} {sum(r['antes'] for r in res.values()):8} {sum(r['bien'] for r in res.values()):5} {tot:5}")
    if contra is not None:
        arregla = sorted(k for k in res if res[k]["bien"] and k in contra and not contra[k]["bien"])
        rompe = sorted(k for k in res if not res[k]["bien"] and k in contra and contra[k]["bien"])
        print(f"\ncontra la referencia: arregla {len(arregla)}, rompe {len(rompe)}")
        for k in rompe:
            print("  ROMPE", k, res[k]["malas"], res[k].get("reglas"))
        por = {}
        for k in arregla:
            for r in res[k].get("reglas") or ["ninguna"]:
                por[r] = por.get(r, 0) + 1
        print("  arreglos por regla:", por)


def _clave(k) -> str:
    return json.dumps(list(k))


if __name__ == "__main__":
    args = sys.argv[1:]
    guardar = args[args.index("--guardar") + 1] if "--guardar" in args else None
    contra = args[args.index("--contra") + 1] if "--contra" in args else None
    solo = [a for a in args if a[:1] in "CK" and a[1:].isdigit()] or None
    res = correr(solo)
    ref = None
    if contra:
        ref = {tuple(json.loads(k)): v for k, v in json.load(open(os.path.join(AQUI, contra + ".json"))).items()}
    informe(res, ref)
    if guardar:
        json.dump({_clave(k): v for k, v in res.items()}, open(os.path.join(AQUI, guardar + ".json"), "w",
                  encoding="utf-8"), ensure_ascii=False)
