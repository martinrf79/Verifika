"""Por cada turno de las 58 y las K: el mensaje, la libreta que vio el modelo, la tabla y la agenda a mano."""
import asyncio, copy, json, os, sys
REPO = "/home/user/Verifika"; sys.path.insert(0, REPO); os.chdir(REPO)
from banco_pruebas import cableado58 as R
from banco_pruebas import clon_produccion as C
from banco_pruebas.agendas58 import AGENDAS, EXPLICAR
it = R.instalar()
real_libreta, real_tabla = it.libreta, None
from app.core.flujo import marcador
OUT = os.path.join(os.path.dirname(__file__), "turnos.jsonl")
f = open(OUT, "w")
for ch in R.charlas():
    ags = list(AGENDAS.get(ch["id"]) or [])
    if len(ags) != len(ch["turnos"]): continue
    uid = f"jev_{ch['id']}"; C.reiniciar_cliente(uid); cola = list(ags); n = [0]
    async def _interp(mensaje, historial, estado, tienda_id, trace_id="", _c=ch):
        ag = cola.pop(0)
        f.write(json.dumps({"charla": _c["id"], "turno": n[0], "mensaje": mensaje,
                            "libreta": it.libreta(estado, historial, tienda_id),
                            "tabla": marcador.tabla(mensaje, tienda_id),
                            "numeros": {k: (v if isinstance(v, str) else v.get("texto") or v.get("que") or str(v)[:80]) for k, v in it.numeros(estado).items()},
                            "agenda": ag}, ensure_ascii=False) + "\n")
        n[0] += 1
        return ag
    async def _expl(p, *a, **k): return EXPLICAR.get(p, "")
    it.interpretar, it.explicar = _interp, _expl
    for t in ch["turnos"]:
        asyncio.run(C.turno(uid, t["texto"]))
f.close()
print(sum(1 for _ in open(OUT)), "turnos")
