"""
EL CENSO DE ENGRANAJES, offline y gratis.

Reproduce las charlas grabadas por el camino vivo (el modelo reemplazado por su
casete) y cuenta, nodo por nodo del grafo: cuantas veces CORRIO y cuantas veces
INTERVINO -o sea, cambio algo-.

POR QUE EXISTE. `PASO0_CENSO.md` afirma que 8 de los 17 nodos de salida no
intervienen NUNCA en 54 turnos. Sin este script eso es una afirmacion escrita a
mano, y una afirmacion escrita a mano envejece: es la misma enfermedad del 44 de
la FAQ que resultaron ser 50. El numero sale de aca o no sale.

NO TOCA `app/`. Los espias envuelven `grafo.registrar` desde afuera.

CLASIFICACION
  MUERTO      corre y nunca interviene       -> candidato a borrar, PERO ojo:
                                                 prueba que estas charlas no lo
                                                 ejercitan, no que sobre
  ESTRUCTURAL interviene SIEMPRE que corre   -> no es una guardia: es una pieza
                                                 del contrato en la etapa
                                                 equivocada
  A VECES     interviene a veces             -> aca viven los bugs reales
  NUNCA CORRE no se ejecuto                  -> sin evidencia

USO
    python3 banco_pruebas/peso_del_censo.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import sim_firestore  # noqa: E402

sim_firestore.install()

from app.verifika import grafo as G  # noqa: E402
from banco_pruebas.casete import CASETES, reproducir_charla  # noqa: E402

# ── el colector: envuelve registrar() sin tocar el codigo del hub ────────────
CORRIO = defaultdict(int)
INTERVINO = defaultdict(int)
DETALLES = defaultdict(list)
NOTAS = defaultdict(int)

_registrar_original = G.registrar
_anotar_original = G.anotar


def registrar_espiado(nodo_id, intervino, detalle=""):
    CORRIO[nodo_id] += 1
    if intervino:
        INTERVINO[nodo_id] += 1
        if detalle:
            DETALLES[nodo_id].append(str(detalle)[:40])
    return _registrar_original(nodo_id, intervino, detalle)


def anotar_espiado(clave, valor):
    NOTAS[str(clave)] += 1
    return _anotar_original(clave, valor)


G.registrar = registrar_espiado
G.anotar = anotar_espiado

casetes = sorted(p for p in CASETES.glob("*.json") if not p.name.startswith("_"))
print(f"casetes: {len(casetes)}")

turnos = 0
fallos = []
for p in casetes:
    try:
        res = reproducir_charla(p)
        turnos += len(res.get("respuestas") or [])
        print(f"  ok  {p.stem}: {len(res.get('respuestas') or [])} turnos")
    except Exception as e:  # noqa: BLE001
        fallos.append(f"{p.stem}: {type(e).__name__}: {str(e)[:120]}")
        print(f"  XX  {p.stem}: {type(e).__name__}: {str(e)[:120]}")

# ── el censo ──────────────────────────────────────────────────
declarados = {n.id: n.etapa for n in G.NODOS}
filas = []
for nodo_id, etapa in declarados.items():
    c = CORRIO.get(nodo_id, 0)
    i = INTERVINO.get(nodo_id, 0)
    if c == 0:
        clase = "NUNCA CORRE"
    elif i == 0:
        clase = "MUERTO"
    elif i == c:
        clase = "ESTRUCTURAL"
    else:
        clase = "A VECES"
    filas.append({"nodo": nodo_id, "etapa": etapa, "corrio": c,
                  "intervino": i,
                  "pct": round(100 * i / c) if c else 0,
                  "clase": clase,
                  "muestra": DETALLES.get(nodo_id, [])[:3]})

# nodos que registraron pero no estan declarados en NODOS
huerfanos = sorted(set(CORRIO) - set(declarados))

salida = {
    "casetes": len(casetes),
    "turnos": turnos,
    "fallos": fallos,
    "nodos_declarados": len(declarados),
    "huerfanos": huerfanos,
    "notas": dict(NOTAS),
    "censo": sorted(filas, key=lambda f: (f["etapa"], -f["intervino"])),
}
(_RAIZ / "banco_pruebas" / "censo.json").write_text(
    json.dumps(salida, indent=1, ensure_ascii=False), encoding="utf-8")

ORDEN = {"MUERTO": 0, "A VECES": 1, "ESTRUCTURAL": 2, "NUNCA CORRE": 3}
print(f"\n{'='*74}\nCENSO — {turnos} turnos de {len(casetes)} charlas\n{'='*74}")
print(f"{'clase':<12} {'etapa':<11} {'nodo':<28} {'corrio':>6} {'intervino':>9} {'%':>4}")
for f in sorted(filas, key=lambda f: (ORDEN[f["clase"]], f["etapa"], -f["corrio"])):
    print(f"{f['clase']:<12} {f['etapa']:<11} {f['nodo']:<28} "
          f"{f['corrio']:>6} {f['intervino']:>9} {f['pct']:>3}%")

print("\nRESUMEN POR CLASE")
for clase in ORDEN:
    n = [f for f in filas if f["clase"] == clase]
    print(f"  {clase:<12} {len(n):>3} nodos")
if huerfanos:
    print(f"\nHUERFANOS (registran y no estan en NODOS): {huerfanos}")

# EL AGUJERO DEL INSTRUMENTO, dicho por el propio script para que no se olvide:
# el grafo declara 32 nodos y solo registran los de `salida`, porque el unico
# que llama a `registrar()` es `G.paso` y `G.paso` envuelve transformaciones de
# TEXTO. Las etapas entrada, decision, reposicion, redaccion, memoria y cierre
# estan declaradas con su contrato y NO se observan. Para esas corre
# `peso_reposicion.py`, que las envuelve a mano.
sin_registrar = [f["nodo"] for f in filas if f["clase"] == "NUNCA CORRE"]
if sin_registrar:
    print(f"\nAVISO: {len(sin_registrar)} nodos declarados NO llaman a registrar().")
    print("       No quiere decir que no corran: quiere decir que el grafo NO LOS VE.")
    print("       Para la etapa de reposicion, corre peso_reposicion.py")
