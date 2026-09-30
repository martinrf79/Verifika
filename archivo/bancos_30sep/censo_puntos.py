"""
EL CENSO DE `SIN_ESTADO` — en cuantos PUNTOS, de cualquier tipo, el turno se
fue sin la casilla `estado` (FICHA 22).

POR QUE EXISTE. `censo_oferta.py` ya cuenta esta casilla vacia, pero SOLO para
el punto sintetico `oferta`. `DECISIONES.md` #3 y la FICHA 09 declaran algo mas
ancho: "el turno no sale si un punto quedo sin estado", para CUALQUIER tipo de
punto —item, atributo, stock, precio, duda, politica, lo que sea—. Sin un
censo que mire los quince tipos a la vez, "sin estado" seguia siendo una frase
de `PENDIENTE.md` en vez de un numero que se corre solo.

DE DONDE SALE. Del mismo evento `indice_turno` que ya loguea cada turno —
`app/core/indice_turno.py::cobertura()`, campo `sin_estado` (el conteo) y
`estados` (`"tipo:n=ESTADO"`, o `"tipo:n=SIN_ESTADO"` cuando la casilla esta
vacia). No se reimplementa nada: se LEE lo que el codigo ya calculo y logueo,
igual que hace `censo_oferta.py` con la oferta. `cobertura()` corre mas de una
vez por turno; vale la ULTIMA, que es la que vio el texto final.

QUE CUENTA Y QUE NO. El punto `oferta` YA tiene su censo propio
(`censo_oferta.py`) y su propia excepcion declarada: `NO_CORRESPONDE` no es un
vacio, es un estado de pleno derecho. Por eso esta cuenta EXCLUYE los puntos
`oferta` —doble conteo con otro instrumento— y cuenta el resto tal cual los
declara `ESTADOS_TERMINALES` en `indice_turno.py`: si no es RESUELTO, AMBIGUO,
NO_SE_SABE, CONFLICTO ni OFRECIDO/NO_CORRESPONDE, es la casilla vacia.

USO
    python3 banco_pruebas/censo_puntos.py             # el total y por tipo
    python3 banco_pruebas/censo_puntos.py --detalle   # turno por turno
"""
import asyncio
import json
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from banco_pruebas import vara_de_venta as vara  # noqa: E402
from banco_pruebas import clon_produccion as clon, observador  # noqa: E402
from banco_pruebas.casete import Casete, reproducir  # noqa: E402
from banco_pruebas.puntaje import leer_guion  # noqa: E402


def _ultimo_indice(eventos: list) -> dict | None:
    """El ULTIMO `indice_turno` del turno: `cobertura()` corre mas de una vez
    y solo el ultimo vio el texto que el cliente lee de verdad, igual criterio
    que usa `censo_oferta._estado_de_la_oferta`."""
    indices = [e for e in eventos if e.get("event") == "indice_turno"]
    return indices[-1] if indices else None


def _sin_estado_del_turno(eventos: list) -> list:
    """Los `"tipo:n"` que quedaron con la casilla vacia en ESTE turno,
    sin contar `oferta` -tiene su propio censo en `censo_oferta.py`-."""
    marca = _ultimo_indice(eventos)
    if not marca:
        return []
    fuera = []
    for linea in (marca.get("estados") or []):
        pid, _, estado = str(linea).partition("=")
        if pid.startswith("oferta:"):
            continue
        if estado == "SIN_ESTADO":
            fuera.append(pid)
    return fuera


def correr_charla(path: Path) -> dict:
    datos = json.loads(Path(path).read_text(encoding="utf-8"))
    casete = Casete(Path(path).stem, datos.get("turnos") or [])
    guion = Path(path).resolve().parent.parent / "guiones" / f"{Path(path).stem}.txt"
    turnos = (leer_guion(guion.read_text(encoding="utf-8")) if guion.exists()
              else [{"mensaje": t.get("mensaje", "")} for t in casete.turnos])

    user = f"censo_puntos_{Path(path).stem}"
    clon.reiniciar_cliente(user)
    filas: list = []

    async def _charla():
        for i, t in enumerate(turnos, 1):
            casete.abrir_turno(t["mensaje"])
            with observador.turno() as obs:
                await clon.turno(user, t["mensaje"])
            filas.append({"turno": i, "mensaje": (t["mensaje"] or "")[:60],
                          "sin_estado": _sin_estado_del_turno(obs.eventos)})

    with reproducir(casete):
        asyncio.run(_charla())
    return {"nombre": Path(path).stem, "turnos": filas}


def medir(paths: list | None = None) -> dict:
    with vara._escuchando():
        charlas = [correr_charla(p) for p in (paths or vara._casetes())]
    filas = [f for c in charlas for f in c["turnos"]]
    total_puntos_vacios = sum(len(f["sin_estado"]) for f in filas)
    turnos_afectados = sum(1 for f in filas if f["sin_estado"])
    por_tipo: dict = {}
    for f in filas:
        for pid in f["sin_estado"]:
            tipo = pid.split(":", 1)[0]
            por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
    return {"charlas": len(charlas), "turnos": len(filas),
            "puntos_sin_estado": total_puntos_vacios,
            "turnos_afectados": turnos_afectados,
            "por_tipo": por_tipo, "_charlas": charlas}


def _main() -> int:
    detalle = "--detalle" in sys.argv
    r = medir()
    print(f"CENSO DE SIN_ESTADO (sin contar `oferta`) — "
          f"{r['charlas']} charlas, {r['turnos']} turnos")
    print(f"  puntos en SIN_ESTADO   {r['puntos_sin_estado']}")
    print(f"  turnos afectados       {r['turnos_afectados']}")
    print(f"  por tipo               {r['por_tipo']}")
    if detalle:
        for c in r["_charlas"]:
            for f in c["turnos"]:
                if f["sin_estado"]:
                    print(f"  {c['nombre']} t{f['turno']}  {f['sin_estado']}  "
                          f"{f['mensaje']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
