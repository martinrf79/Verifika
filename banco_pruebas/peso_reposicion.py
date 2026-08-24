"""
LA ETAPA FANTASMA, medida.

YA NO ES FANTASMA, Y ESTE SCRIPT PASO A SER EL TESTIGO INDEPENDIENTE. Hasta el
21-ago `peso_del_censo.py` solo veia la etapa `salida`, y las SEIS funciones de
REPOSICION -las que reescriben lo que el modelo declaro, ANTES de redactar-
estaban declaradas en el grafo y no se observaban: habia que envolverlas a mano,
que es lo que hace este script. La FICHA 01 las cableo a `registrar()`.

POR QUE NO SE BORRA. Envuelve las funciones DESDE AFUERA, sin depender de que el
hub este bien cableado, asi que mide lo mismo por otro camino. El 21-ago los dos
dieron el MISMO 44% para `_cuenta_con_lo_declarado`, y esa coincidencia es lo
unico que prueba que el instrumento nuevo no se esta midiendo a si mismo. El dia
que los dos numeros discrepen, hay un nodo cableado en el lugar equivocado.

POR QUE IMPORTA. Si la interpretacion fuera del todo robusta, esta etapa
deberia estar casi vacia. Cuanto interviene ES la medida de cuan robusta es en
la practica, y hasta el 18-ago-2026 nadie la habia medido. Medido ese dia:
`_cuenta_con_lo_declarado` corrige al modelo en el 44% de los turnos, o sea que
no es una guardia, es la resolucion del punto `precio` puesta despues de que el
modelo escribio.

Ademas junta los veredictos que hoy van a `anotar()` y se pierden en una linea
de log: el reconciliador -que reclama en el 57% de los turnos- y los PUNTOS del
pedido, que es la evidencia directa de que hace falta un contrato de cobertura.

NO TOCA `app/`.

USO
    python3 banco_pruebas/peso_reposicion.py
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

from app.core import reposicion as H  # noqa: E402
from app.verifika import grafo as G  # noqa: E402
from banco_pruebas.casete import CASETES, reproducir_charla  # noqa: E402

# ── las seis de reposicion, envueltas ───────────────────────────────
# VIVEN EN `reposicion.py` DESDE LA FICHA 11, y son las mismas seis: el modulo
# cambio, los nombres y la medicion no. Se envuelven una por una a proposito,
# que es lo que le da a este instrumento su independencia del grafo: mide
# desde afuera y por eso pudo confirmar el 44% de `cuenta_repuesta`.
REPO = ["_busqueda_de_lo_declarado", "_condicion_faltante_aplicada",
        "_cuenta_con_lo_declarado", "_reparto_de_pago_declarado",
        "_supuesto_de_pago", "_bloques_a_uno"]

CORRIO = defaultdict(int)
CAMBIO = defaultdict(int)


def envolver(nombre):
    orig = getattr(H, nombre)

    def espia(llamadas, *a, **k):
        antes = json.dumps(llamadas, sort_keys=True, default=str)
        out = orig(llamadas, *a, **k)
        CORRIO[nombre] += 1
        if json.dumps(out, sort_keys=True, default=str) != antes:
            CAMBIO[nombre] += 1
        return out
    setattr(H, nombre, espia)


for n in REPO:
    envolver(n)

# ── los veredictos que hoy se pierden ──────────────────────────────
TURNOS = []
_anotar_orig = G.anotar
_buffer = {}


def anotar_espia(clave, valor):
    _buffer[str(clave)] = valor
    if str(clave) == "aduana":          # ultima nota del turno
        TURNOS.append(dict(_buffer))
        _buffer.clear()
    return _anotar_orig(clave, valor)


G.anotar = anotar_espia

casetes = sorted(p for p in CASETES.glob("*.json") if not p.name.startswith("_"))
for p in casetes:
    try:
        reproducir_charla(p)
    except Exception as e:  # noqa: BLE001
        print("XX", p.stem, type(e).__name__, str(e)[:80], file=sys.stderr)

# ── informe ────────────────────────────────────────────────
print("\n" + "=" * 74)
print("REPOSICION — el codigo reescribiendo lo que el modelo declaro")
print("=" * 74)
print(f"{'funcion':<32} {'corrio':>7} {'cambio':>7} {'%':>5}")
for n in REPO:
    c, m = CORRIO.get(n, 0), CAMBIO.get(n, 0)
    print(f"{n:<32} {c:>7} {m:>7} {round(100*m/c) if c else 0:>4}%")

n = len(TURNOS) or 1
rec_falt = sum(1 for t in TURNOS if (t.get("reconciliador") or {}).get("faltantes"))
rec_preg = sum(1 for t in TURNOS if (t.get("reconciliador") or {}).get("preguntar"))
rec_sinb = sum(1 for t in TURNOS if (t.get("reconciliador") or {}).get("sin_buscar"))
puntos = sum(t.get("puntos_del_pedido") or 0 for t in TURNOS)
sinmat = sum(len(t.get("sin_material") or []) for t in TURNOS)
sincon = sum(len(t.get("sin_contestar") or []) for t in TURNOS)
t_sincon = sum(1 for t in TURNOS if t.get("sin_contestar"))
t_sinmat = sum(1 for t in TURNOS if t.get("sin_material"))
adu = sum((t.get("aduana") or {}).get("rojas", 0) for t in TURNOS)
adu_rep = sum((t.get("aduana") or {}).get("reparadas", 0) for t in TURNOS)

print("\n" + "=" * 74)
print(f"EL RECONCILIADOR ({len(TURNOS)} turnos)")
print("=" * 74)
print(f"  turnos con FALTANTES (el modelo no busco lo que declaro) : {rec_falt:>3}  {round(100*rec_falt/n)}%")
print(f"  turnos donde manda PREGUNTAR (ambiguo)                   : {rec_preg:>3}  {round(100*rec_preg/n)}%")
print(f"  turnos con SIN_BUSCAR                                    : {rec_sinb:>3}  {round(100*rec_sinb/n)}%")

print("\n" + "=" * 74)
print("LOS PUNTOS DEL PEDIDO — la cobertura, ya medida y ya perdida")
print("=" * 74)
print(f"  puntos abiertos, total                       : {puntos}")
print(f"  puntos SIN MATERIAL (la fuente no trajo nada): {sinmat}  ({round(100*sinmat/puntos) if puntos else 0}%)")
print(f"  puntos SIN CONTESTAR al final del turno      : {sincon}  ({round(100*sincon/puntos) if puntos else 0}%)")
print(f"  turnos con al menos un punto sin material    : {t_sinmat}/{len(TURNOS)}  ({round(100*t_sinmat/n)}%)")
print(f"  turnos con al menos un punto sin contestar   : {t_sincon}/{len(TURNOS)}  ({round(100*t_sincon/n)}%)")
print(f"  aduana: {adu} rojas, {adu_rep} reparadas")
# EL AVISO CAMBIO DE SIGNO EL 23-AGO (FICHA 06). Hasta ese dia decia que las
# cuatro familias informativas no abrian punto y que el numero de abajo era un
# PISO. Ahora `registrar_pedido` las declara y el numero es el REAL. Como es
# peor que el piso viejo, el aviso sigue haciendo falta: sin esto, la sesion
# que vea 21% donde antes habia 11% lee una regresion y revierte un acierto.
print("\nOJO CON LOS PUNTOS: desde el 23-ago las DIEZ familias se abren, asi")
print("que este numero ya no es un piso: es el REAL. Y por eso SUBIO —de 22")
print("sobre 206 a 49 sobre 238—. No es una regresion: las preguntas")
print("informativas antes no abrian punto, asi que lo que no se contestaba de")
print("ellas no se contaba. Es la verdad apareciendo, y baja con la FICHA 08,")
print("que convierte la cobertura de log en PUERTA.")

(_RAIZ / "banco_pruebas" / "reposicion.json").write_text(json.dumps({
    "reposicion": {k: {"corrio": CORRIO.get(k, 0), "cambio": CAMBIO.get(k, 0)} for k in REPO},
    "turnos": len(TURNOS), "reconciliador_faltantes": rec_falt,
    "reconciliador_preguntar": rec_preg,
    "puntos": puntos, "sin_material": sinmat, "sin_contestar": sincon,
    "turnos_sin_contestar": t_sincon, "turnos_sin_material": t_sinmat,
}, indent=1, ensure_ascii=False), encoding="utf-8")
