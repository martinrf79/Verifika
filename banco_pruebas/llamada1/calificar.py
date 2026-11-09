"""Califica llamada1.jsonl con el banco del repo: mismos productos que la agenda a mano, por tipo y version."""
import collections, json, os, sys
REPO = "/home/user/Verifika"
sys.path[:0] = [REPO, REPO + "/banco_pruebas"]
from banco_pruebas.plantilla_venta import llenar as LL
LL.entorno()
from banco_pruebas.agendas58 import AGENDAS
from banco_pruebas.capa_buscar import _ids
from app.core.flujo import ejecutor as X, estado as E
TID = "verifika_prod"


def prods(ag):
    try:
        return _ids(X.ejecutar(ag, E.leer({}), TID).hechos)
    except Exception as e:  # noqa
        return {f"ERROR {type(e).__name__}"}


filas = [json.loads(l) for l in open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "llamada1.jsonl"))]
oro = {c: prods(AGENDAS[c][0]) for c in {f["charla"] for f in filas}}
tipos = {c: {p["accion"] for p in AGENDAS[c][0]["preguntas"]} & {"buscar", "producto", "comprar"} for c in oro}
res = {}
for f in filas:
    ag = dict(f["agenda"] or {"preguntas": []}); ag["mensaje"] = f["texto"]
    res[(f["v"], f["charla"], f["forma"])] = prods(ag) == oro[f["charla"]]
cuenta = collections.Counter()
for (v, c, fo), ok in res.items():
    for t in tipos[c]:
        cuenta[(v, t, "n")] += 1; cuenta[(v, t, "bien")] += ok
for t in ("comprar", "producto", "buscar"):
    print(t, " · ".join(f"{v} {cuenta[(v, t, 'bien')]} de {cuenta[(v, t, 'n')]}" for v in ("A", "B", "B2")))
V = sys.argv[1] if len(sys.argv) > 1 else "B"
gana = sorted(k[1:] for k in res if k[0] == V and res[k] and ("A",) + k[1:] in res and not res[("A",) + k[1:]])
pierde = sorted(k[1:] for k in res if k[0] == V and not res[k] and ("A",) + k[1:] in res and res[("A",) + k[1:]])
print(V, "gana en:", gana); print(V, "pierde en:", pierde)
