"""
EL CENSO DE ENGRANAJES, offline y gratis.

Reproduce las charlas grabadas por el camino vivo (el modelo reemplazado por su
casete) y cuenta, nodo por nodo: cuantas veces CORRIO y cuantas veces INTERVINO
-o sea, cambio algo-.

POR QUE EXISTE. `PASO0_CENSO.md` afirma que hay nodos que no intervienen NUNCA
sobre el corpus. Sin este script eso es una afirmacion escrita a mano, y una
afirmacion escrita a mano envejece: es la misma enfermedad del 44 de la FAQ que
resultaron ser 50. El numero sale de aca o no sale.

**YA NO ENVUELVE NADA, Y ESE ES EL CAMBIO DE LA FICHA 12.** Hasta hoy este
script le ponia un espia a `grafo.registrar` y a `grafo.anotar` desde afuera, y
contaba lo que el espia veia. Ahora cuenta el grafo: `registrar()` suma a su
propio censo acumulado y aca solo se lee `G.censo()`. La diferencia no es de
prolijidad. Un instrumento que necesita que alguien le ponga un espia encima
mide **lo que el espia envuelve**, y el dia que una pieza deje su marca por otro
camino el espia no se entera: el censo cuenta cero, y un cero indistinguible de
'no corrio' es como se pasaron por alto los nodos ciegos la primera vez.

QUE VE. Las SEIS etapas del turno, y ademas los HUERFANOS -los engranajes que
dejan marca y no estan declarados en `NODOS`-. Esos son las piezas de adentro de
las puertas de `salida` y `reposicion`: despues de las FICHAS 10 y 11 el grafo
declara las PUERTAS y las piezas siguen registrando una por una con su id
propio. **No se esconden ni se cuentan como si fueran nodos declarados**: van en
su propia columna, con sus numeros, porque son engranajes reales del turno y un
censo que los tira a una lista de nombres miente por abajo.

CUANTOS son y CUANTO interviene cada uno NO se escribe en ningun texto: se corre
esto y se mira. `tests/test_censo_del_grafo.py` afirma sobre cuantos nodos midio,
para que no pueda pasar por vacio.

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
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import sim_firestore  # noqa: E402

sim_firestore.install()

from app.verifika import grafo as G  # noqa: E402
from banco_pruebas.casete import CASETES, reproducir_charla  # noqa: E402

# Se arranca de cero: si esta corrida arrastrara lo que conto una anterior, los
# porcentajes serian de dos corpus mezclados y nadie podria decir cual.
G.censo_reiniciar()

casetes = sorted(p for p in CASETES.glob("*.json") if not p.name.startswith("_"))
print(f"casetes: {len(casetes)}")

fallos = []
for p in casetes:
    try:
        res = reproducir_charla(p)
        print(f"  ok  {p.stem}: {len(res.get('respuestas') or [])} turnos")
    except Exception as e:  # noqa: BLE001
        fallos.append(f"{p.stem}: {type(e).__name__}: {str(e)[:120]}")
        print(f"  XX  {p.stem}: {type(e).__name__}: {str(e)[:120]}")

# ── el censo, leido del grafo ──────────────────────────────────
c = G.censo()
filas = c["filas"]
turnos = c["turnos"]

salida = dict(c, casetes=len(casetes), fallos=fallos)
(_RAIZ / "banco_pruebas" / "censo.json").write_text(
    json.dumps(salida, indent=1, ensure_ascii=False), encoding="utf-8")

ORDEN = {"MUERTO": 0, "A VECES": 1, "ESTRUCTURAL": 2, "NUNCA CORRE": 3}
print(f"\n{'='*78}\nCENSO — {turnos} turnos de {len(casetes)} charlas\n{'='*78}")
print(f"{'clase':<12} {'etapa':<14} {'nodo':<28} {'corrio':>6} {'intervino':>9} {'%':>4}")
for f in sorted(filas, key=lambda f: (ORDEN[f["clase"]], f["etapa"], -f["corrio"])):
    print(f"{f['clase']:<12} {f['etapa']:<14} {f['nodo']:<28} "
          f"{f['corrio']:>6} {f['intervino']:>9} {f['pct']:>3}%")

print("\nRESUMEN POR CLASE")
for clase in ORDEN:
    n = [f for f in filas if f["clase"] == clase]
    print(f"  {clase:<12} {len(n):>3} nodos")

print(f"\nMIDIO {c['nodos_medidos']} NODOS: {c['declarados_medidos']} de los "
      f"{c['nodos_declarados']} declarados en NODOS, y {c['huerfanos_medidos']} "
      "HUERFANOS.")
print(f"  las etapas que dejaron marca: {', '.join(c['etapas_medidas'])}")

# EL AVISO SE QUEDA, y no es un resto: si mañana entra un nodo al grafo y nadie
# lo cablea a `registrar()`, sale NUNCA CORRE y el censo lo grita en vez de
# contarlo como cero en silencio. Un instrumento que no avisa cuando le falta un
# ojo es el que dejo pasar los nodos muertos la primera vez.
if c["ciegos"]:
    print(f"\nAVISO: {len(c['ciegos'])} nodos declarados NO dejaron marca.")
    print("       No quiere decir que no corran: quiere decir que el grafo NO LOS VE.")
    print(f"       Los ciegos: {c['ciegos']}")
else:
    print(f"\nLAS {len(G.ETAPAS)} ETAPAS REGISTRAN: los {c['nodos_declarados']} "
          "nodos declarados dejan marca, ninguno esta ciego.")

# EL HUERFANO NO ES UN ERROR, ES UNA DEUDA DE DECLARACION: la pieza corre, deja
# su marca y se mide, pero NO tiene nodo en `NODOS`, o sea que no tiene contrato
# declarado y el barrido de `test_grafo_cableado.py` -que saca su lista de ahi-
# no la corre. Se listan con sus numeros para que la deuda tenga tamaño.
huerfanos = [f for f in filas if not f["declarado"] and f["corrio"]]
if huerfanos:
    print(f"\nHUERFANOS: {len(huerfanos)} engranajes registran y no estan en "
          "NODOS, asi que corren SIN CONTRATO declarado y el barrido no los ve.")
    for f in sorted(huerfanos, key=lambda f: -f["intervino"]):
        print(f"       {f['nodo']:<28} {f['corrio']:>4} corrio "
              f"{f['intervino']:>4} intervino  {f['clase']}")

# UNA MARCA POR NODO Y POR TURNO. Si un nodo marcara dos veces, el censo
# contaria de mas y TODOS los porcentajes quedarian mal en silencio.
if c["marcan_de_mas"]:
    print(f"\nAVISO: estos nodos marcaron mas veces que turnos hubo ({turnos}): "
          f"{c['marcan_de_mas']}. Los porcentajes de esos nodos estan mal.")

if fallos:
    print(f"\nFALLARON {len(fallos)} casetes: {fallos}")
